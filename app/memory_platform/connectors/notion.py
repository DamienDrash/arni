"""Notion Connector – bidirectional sync with Notion workspaces.

Implements the full Notion integration lifecycle:
1. OAuth 2.0 authentication flow
2. Initial full sync of selected pages/databases
3. Incremental sync via Notion API polling
4. Real-time sync via Notion Webhooks (page.content_updated events)
5. Content parsing and ingestion into the Memory Platform

Uses the official Notion API v2022-06-28 and the notion-sdk-py client.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import structlog

from app.memory_platform.connectors import BaseConnector
from app.memory_platform.models import ContentChunk, DocumentSourceType

logger = structlog.get_logger()

# ── Notion API Constants ─────────────────────────────────────────────

NOTION_API_VERSION = "2022-06-28"
NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API_BASE = "https://api.notion.com/v1"


class NotionConnector(BaseConnector):
    """Full-featured Notion integration connector."""

    connector_name = "notion"
    connector_type = "knowledge_source"

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._workspace_id: str | None = None
        self._workspace_name: str | None = None
        self._bot_id: str | None = None
        self._connected: bool = False
        self._sync_state: dict[str, Any] = {}  # page_id -> last_edited_time
        self._webhook_secret: str | None = None

    # ── OAuth 2.0 Flow ───────────────────────────────────────────────

    def get_oauth_url(self, redirect_uri: str, state: str = "") -> str:
        """Generate the Notion OAuth authorization URL.

        The user is redirected to this URL to authorize the integration.
        After authorization, Notion redirects back with an auth code.
        """
        client_id = os.getenv("NOTION_CLIENT_ID", "")
        params = {
            "client_id": client_id,
            "response_type": "code",
            "owner": "user",
            "redirect_uri": redirect_uri,
        }
        if state:
            params["state"] = state
        return f"{NOTION_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange the OAuth authorization code for an access token.

        Returns the token response including access_token, workspace_id,
        workspace_name, and bot_id.
        """
        import httpx

        client_id = os.getenv("NOTION_CLIENT_ID", "")
        client_secret = os.getenv("NOTION_CLIENT_SECRET", "")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                NOTION_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(client_id, client_secret),
                headers={"Notion-Version": NOTION_API_VERSION},
            )

            if response.status_code != 200:
                logger.error(
                    "notion.oauth_exchange_failed",
                    status=response.status_code,
                    body=response.text,
                )
                return {"error": f"OAuth exchange failed: {response.status_code}"}

            data = response.json()
            self._access_token = data.get("access_token")
            self._workspace_id = data.get("workspace_id")
            self._workspace_name = data.get("workspace_name")
            self._bot_id = data.get("bot_id")
            self._connected = True

            logger.info(
                "notion.oauth_success",
                workspace=self._workspace_name,
                workspace_id=self._workspace_id,
            )

            return {
                "access_token": self._access_token,
                "workspace_id": self._workspace_id,
                "workspace_name": self._workspace_name,
                "bot_id": self._bot_id,
            }

    # ── BaseConnector Interface ──────────────────────────────────────

    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Connect using stored credentials (access token)."""
        self._access_token = credentials.get("access_token")
        self._workspace_id = credentials.get("workspace_id")
        self._workspace_name = credentials.get("workspace_name")

        if not self._access_token:
            logger.error("notion.connect_no_token")
            return False

        # Verify the token is still valid
        test = await self.test_connection(credentials)
        self._connected = test.get("success", False)
        return self._connected

    async def disconnect(self) -> None:
        """Disconnect and clear credentials."""
        self._access_token = None
        self._workspace_id = None
        self._connected = False
        logger.info("notion.disconnected")

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        """Test the Notion connection by fetching the user info."""
        token = credentials.get("access_token", self._access_token)
        if not token:
            return {"success": False, "error": "Kein Access Token vorhanden"}

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{NOTION_API_BASE}/users/me",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Notion-Version": NOTION_API_VERSION,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "user": data.get("name", ""),
                        "type": data.get("type", ""),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API returned {response.status_code}",
                    }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Page & Database Discovery ────────────────────────────────────

    async def list_pages(
        self,
        query: str = "",
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for pages and databases in the connected workspace."""
        if not self._access_token:
            return []

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                payload: dict[str, Any] = {"page_size": page_size}
                if query:
                    payload["query"] = query

                response = await client.post(
                    f"{NOTION_API_BASE}/search",
                    headers={
                        "Authorization": f"Bearer {self._access_token}",
                        "Notion-Version": NOTION_API_VERSION,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code != 200:
                    logger.error("notion.search_failed", status=response.status_code)
                    return []

                data = response.json()
                results = []
                for item in data.get("results", []):
                    obj_type = item.get("object", "")
                    title = self._extract_title(item)
                    results.append({
                        "id": item.get("id", ""),
                        "type": obj_type,
                        "title": title,
                        "url": item.get("url", ""),
                        "last_edited_time": item.get("last_edited_time", ""),
                        "created_time": item.get("created_time", ""),
                    })

                return results

        except Exception as exc:
            logger.error("notion.list_pages_error", error=str(exc))
            return []

    # ── Full Sync ────────────────────────────────────────────────────

    async def sync(
        self,
        tenant_id: int,
        page_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Perform a full sync of selected pages.

        If page_ids is None, syncs all accessible pages.
        Returns a summary of synced content.
        """
        if not self._access_token:
            return {"error": "Nicht verbunden", "synced": 0}

        synced_pages = 0
        synced_chunks = 0
        errors: list[str] = []

        # Get pages to sync
        if page_ids:
            pages = [{"id": pid} for pid in page_ids]
        else:
            pages = await self.list_pages(page_size=100)

        for page_info in pages:
            page_id = page_info.get("id", "")
            if not page_id:
                continue

            try:
                chunks = await self._fetch_page_content(page_id)
                if chunks:
                    # Ingest via the ingestion service
                    from app.memory_platform.ingestion import get_ingestion_service
                    service = get_ingestion_service()

                    title = page_info.get("title", f"Notion Page {page_id[:8]}")
                    content = "\n\n".join([c.content for c in chunks])

                    await service.ingest_text(
                        tenant_id=tenant_id,
                        content=content,
                        title=f"[Notion] {title}",
                        source_type=DocumentSourceType.NOTION,
                        metadata={
                            "notion_page_id": page_id,
                            "notion_url": page_info.get("url", ""),
                            "last_edited_time": page_info.get("last_edited_time", ""),
                        },
                    )

                    synced_pages += 1
                    synced_chunks += len(chunks)

                    # Update sync state
                    self._sync_state[page_id] = page_info.get("last_edited_time", "")

            except Exception as exc:
                errors.append(f"Page {page_id}: {str(exc)}")
                logger.error("notion.sync_page_error", page_id=page_id, error=str(exc))

        logger.info(
            "notion.sync_completed",
            pages=synced_pages,
            chunks=synced_chunks,
            errors=len(errors),
        )

        return {
            "synced_pages": synced_pages,
            "synced_chunks": synced_chunks,
            "errors": errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Incremental Sync ─────────────────────────────────────────────

    async def incremental_sync(self, tenant_id: int) -> dict[str, Any]:
        """Sync only pages that have changed since the last sync."""
        if not self._access_token:
            return {"error": "Nicht verbunden", "synced": 0}

        pages = await self.list_pages(page_size=100)
        changed_pages = []

        for page in pages:
            page_id = page.get("id", "")
            last_edited = page.get("last_edited_time", "")
            stored_time = self._sync_state.get(page_id, "")

            if last_edited != stored_time:
                changed_pages.append(page)

        if not changed_pages:
            return {"synced_pages": 0, "message": "Keine Änderungen seit dem letzten Sync"}

        page_ids = [p["id"] for p in changed_pages]
        return await self.sync(tenant_id, page_ids=page_ids)

    # ── Webhook Handler ──────────────────────────────────────────────

    async def handle_webhook(
        self,
        tenant_id: int,
        payload: dict[str, Any],
        signature: str | None = None,
    ) -> dict[str, Any]:
        """Handle an incoming Notion webhook event.

        Notion webhooks send events like:
        - page.content_updated
        - page.created
        - page.deleted
        - page.property_changed
        """
        # Verify webhook signature if secret is configured
        if self._webhook_secret and signature:
            if not self._verify_signature(payload, signature):
                logger.warning("notion.webhook_invalid_signature")
                return {"error": "Invalid signature"}

        event_type = payload.get("type", "")
        entity = payload.get("entity", {})
        page_id = entity.get("id", "")

        logger.info(
            "notion.webhook_received",
            event_type=event_type,
            page_id=page_id,
        )

        if event_type in ("page.content_updated", "page.created"):
            # Re-sync the affected page
            return await self.sync(tenant_id, page_ids=[page_id])

        elif event_type == "page.deleted":
            # TODO: Remove the page from the knowledge base
            logger.info("notion.page_deleted", page_id=page_id)
            return {"action": "deleted", "page_id": page_id}

        return {"action": "ignored", "event_type": event_type}

    def set_webhook_secret(self, secret: str) -> None:
        """Set the webhook verification secret."""
        self._webhook_secret = secret

    def _verify_signature(self, payload: dict, signature: str) -> bool:
        """Verify the webhook signature using HMAC-SHA256."""
        if not self._webhook_secret:
            return True
        body = json.dumps(payload, separators=(",", ":")).encode()
        expected = hmac.new(
            self._webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── Content Fetching ─────────────────────────────────────────────

    async def _fetch_page_content(self, page_id: str) -> list[ContentChunk]:
        """Fetch and parse the content of a Notion page."""
        if not self._access_token:
            return []

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                # Fetch page blocks (content)
                blocks = await self._fetch_all_blocks(client, page_id)

                if not blocks:
                    return []

                # Convert blocks to markdown
                markdown = self._blocks_to_markdown(blocks)

                if not markdown.strip():
                    return []

                # Split into chunks
                chunks = self._split_content(markdown, page_id)
                return chunks

        except Exception as exc:
            logger.error("notion.fetch_content_error", page_id=page_id, error=str(exc))
            return []

    async def _fetch_all_blocks(
        self,
        client: Any,
        block_id: str,
        depth: int = 0,
    ) -> list[dict[str, Any]]:
        """Recursively fetch all blocks for a page."""
        if depth > 3:  # Limit recursion depth
            return []

        blocks: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            url = f"{NOTION_API_BASE}/blocks/{block_id}/children"
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor

            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Notion-Version": NOTION_API_VERSION,
                },
                params=params,
            )

            if response.status_code != 200:
                break

            data = response.json()
            for block in data.get("results", []):
                blocks.append(block)

                # Recursively fetch children
                if block.get("has_children"):
                    children = await self._fetch_all_blocks(
                        client, block["id"], depth + 1
                    )
                    block["_children"] = children

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return blocks

    def _blocks_to_markdown(self, blocks: list[dict[str, Any]]) -> str:
        """Convert Notion blocks to Markdown format."""
        parts: list[str] = []

        for block in blocks:
            block_type = block.get("type", "")
            block_data = block.get(block_type, {})

            if block_type == "paragraph":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                parts.append(text)

            elif block_type.startswith("heading_"):
                level = int(block_type[-1])
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                parts.append(f"{'#' * level} {text}")

            elif block_type == "bulleted_list_item":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                parts.append(f"- {text}")

            elif block_type == "numbered_list_item":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                parts.append(f"1. {text}")

            elif block_type == "to_do":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                checked = "x" if block_data.get("checked") else " "
                parts.append(f"- [{checked}] {text}")

            elif block_type == "toggle":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                parts.append(f"<details><summary>{text}</summary>")

            elif block_type == "code":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                lang = block_data.get("language", "")
                parts.append(f"```{lang}\n{text}\n```")

            elif block_type == "quote":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                parts.append(f"> {text}")

            elif block_type == "callout":
                text = self._rich_text_to_str(block_data.get("rich_text", []))
                icon = block_data.get("icon", {}).get("emoji", "💡")
                parts.append(f"> {icon} {text}")

            elif block_type == "divider":
                parts.append("---")

            elif block_type == "table":
                # Tables are handled through children
                pass

            elif block_type == "table_row":
                cells = block_data.get("cells", [])
                row = " | ".join(
                    self._rich_text_to_str(cell) for cell in cells
                )
                parts.append(f"| {row} |")

            elif block_type == "image":
                img_type = block_data.get("type", "")
                url = block_data.get(img_type, {}).get("url", "")
                caption = self._rich_text_to_str(block_data.get("caption", []))
                parts.append(f"![{caption}]({url})")

            elif block_type == "bookmark":
                url = block_data.get("url", "")
                caption = self._rich_text_to_str(block_data.get("caption", []))
                parts.append(f"[{caption or url}]({url})")

            elif block_type == "equation":
                expression = block_data.get("expression", "")
                parts.append(f"$$\n{expression}\n$$")

            # Process children
            children = block.get("_children", [])
            if children:
                child_md = self._blocks_to_markdown(children)
                if child_md:
                    parts.append(child_md)

        return "\n\n".join(parts)

    @staticmethod
    def _rich_text_to_str(rich_text: list[dict[str, Any]]) -> str:
        """Convert Notion rich text array to plain string."""
        parts = []
        for rt in rich_text:
            text = rt.get("plain_text", "")
            annotations = rt.get("annotations", {})

            if annotations.get("bold"):
                text = f"**{text}**"
            if annotations.get("italic"):
                text = f"*{text}*"
            if annotations.get("strikethrough"):
                text = f"~~{text}~~"
            if annotations.get("code"):
                text = f"`{text}`"

            href = rt.get("href")
            if href:
                text = f"[{text}]({href})"

            parts.append(text)
        return "".join(parts)

    @staticmethod
    def _extract_title(page: dict[str, Any]) -> str:
        """Extract the title from a Notion page or database object."""
        properties = page.get("properties", {})

        # Try "title" property (pages)
        title_prop = properties.get("title", properties.get("Name", {}))
        if title_prop:
            title_items = title_prop.get("title", [])
            if title_items:
                return "".join(t.get("plain_text", "") for t in title_items)

        # Fallback: try all properties for a title type
        for prop in properties.values():
            if prop.get("type") == "title":
                title_items = prop.get("title", [])
                if title_items:
                    return "".join(t.get("plain_text", "") for t in title_items)

        return "Untitled"

    def _split_content(
        self,
        content: str,
        page_id: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> list[ContentChunk]:
        """Split content into chunks with overlap."""
        if len(content) <= chunk_size:
            return [ContentChunk(
                content=content,
                content_type="text",
                metadata={"notion_page_id": page_id},
            )]

        chunks: list[ContentChunk] = []
        start = 0
        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]
            if chunk_text.strip():
                chunks.append(ContentChunk(
                    content=chunk_text.strip(),
                    content_type="text",
                    metadata={
                        "notion_page_id": page_id,
                        "char_start": start,
                    },
                ))
            start = end - overlap

        return chunks

    # ── Status ───────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get the current connector status."""
        return {
            "connected": self._connected,
            "workspace_id": self._workspace_id,
            "workspace_name": self._workspace_name,
            "synced_pages": len(self._sync_state),
            "last_sync_state": dict(self._sync_state),
        }


# ── Singleton ────────────────────────────────────────────────────────

_connector: NotionConnector | None = None


def get_notion_connector() -> NotionConnector:
    """Return the singleton Notion connector."""
    global _connector
    if _connector is None:
        _connector = NotionConnector()
    return _connector
