"""ARIIA v2.0 – Member Memory Adapter.

@ARCH: Sprint 2 (Integration Roadmap), Task S2.2
Concrete adapter for the ARIIA Member Memory system. Wraps the existing
member_memory tool and member_memory_analyzer into the BaseAdapter interface,
providing standardized capability routing for the DynamicToolResolver.

The Member Memory system provides long-term, per-member recall of facts,
preferences, goals, and sentiment patterns extracted from chat conversations.

Supported Capabilities:
  - memory.member.search   → Search for specific facts about a member
  - memory.member.summary  → Get the analytical summary for a member
  - memory.member.history  → Get conversation history for a member
  - memory.member.index    → Index/re-index a member's memory profile
  - memory.member.list     → List all members with memory profiles
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from app.domains.identity.models import Tenant
from app.domains.support.models import ChatMessage, ChatSession, StudioMember
from app.integrations.adapters.base import AdapterResult, BaseAdapter
from app.shared.db import open_session

logger = structlog.get_logger()


class MemberMemoryAdapter(BaseAdapter):
    """Adapter for the ARIIA Member Memory system.

    Routes capability calls to the existing member_memory tool and
    member_memory_analyzer, wrapping results in the standardized
    AdapterResult format.
    """

    @property
    def integration_id(self) -> str:
        return "member_memory"

    @property
    def supported_capabilities(self) -> list[str]:
        return [
            "memory.member.search",
            "memory.member.summary",
            "memory.member.history",
            "memory.member.index",
            "memory.member.list",
        ]

    # ── Abstract Method Stubs (BaseAdapter compliance) ───────────────────

    @property
    def display_name(self) -> str:
        return "Member Memory"

    @property
    def category(self) -> str:
        return "knowledge"

    def get_config_schema(self) -> dict:
        return {
            "fields": [],
        }

    async def get_contacts(
        self,
        tenant_id: int,
        config: dict,
        last_sync_at=None,
        sync_mode=None,
    ) -> "SyncResult":
        from app.integrations.adapters.base import SyncResult
        return SyncResult(
            success=True,
            records_fetched=0,
            contacts=[],
            metadata={"note": "Member Memory does not support contact sync."},
        )

    async def test_connection(self, config: dict) -> "ConnectionTestResult":
        from app.integrations.adapters.base import ConnectionTestResult
        return ConnectionTestResult(
            success=True,
            message="Member Memory-Adapter geladen (Verbindungstest nicht implementiert).",
        )

    async def _execute(
        self,
        capability_id: str,
        tenant_id: int,
        **kwargs: Any,
    ) -> AdapterResult:
        """Route capability calls to the appropriate member memory method."""
        handlers = {
            "memory.member.search": self._search,
            "memory.member.summary": self._summary,
            "memory.member.history": self._history,
            "memory.member.index": self._index,
            "memory.member.list": self._list_members,
        }
        handler = handlers.get(capability_id)
        if handler:
            return await handler(tenant_id, **kwargs)
        return AdapterResult(success=False, error=f"Unknown capability: {capability_id}")

    # ── memory.member.search ─────────────────────────────────────────

    async def _search(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Search for specific facts about a member in long-term memory.

        Required kwargs:
            user_identifier (str): Member ID, member number, or email.
            query (str): What to search for (e.g. "Trainingsziele").
        """
        user_identifier = kwargs.get("user_identifier")
        query = kwargs.get("query")

        if not user_identifier:
            return AdapterResult(
                success=False,
                error="Parameter 'user_identifier' is required for memory.member.search",
                error_code="MISSING_PARAM",
            )
        if not query:
            return AdapterResult(
                success=False,
                error="Parameter 'query' is required for memory.member.search",
                error_code="MISSING_PARAM",
            )

        try:
            from app.swarm.tools.member_memory import search_member_memory

            result = search_member_memory(
                user_identifier=user_identifier,
                query=query,
                tenant_id=tenant_id,
            )

            is_not_found = "Keine spezifischen Langzeit-Erinnerungen" in result or "fehlgeschlagen" in result

            return AdapterResult(
                success=True,
                data=result,
                metadata={
                    "user_identifier": user_identifier,
                    "query": query,
                    "found": not is_not_found,
                },
            )
        except Exception as exc:
            logger.error("member_memory_adapter.search_failed", error=str(exc), tenant_id=tenant_id)
            return AdapterResult(success=False, error=f"Member memory search failed: {exc}")

    # ── memory.member.summary ────────────────────────────────────────

    async def _summary(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get the analytical summary for a specific member.

        Reads the member's markdown profile file and extracts the
        analytical summary section.

        Required kwargs:
            member_id (str): The member's customer_id or member_number.
        """
        member_id = kwargs.get("member_id")
        if not member_id:
            return AdapterResult(
                success=False,
                error="Parameter 'member_id' is required for memory.member.summary",
                error_code="MISSING_PARAM",
            )

        try:
            slug = self._resolve_tenant_slug(tenant_id)
            content = self._read_member_file(str(member_id), slug)

            if not content:
                return AdapterResult(
                    success=True,
                    data="Kein Profil für dieses Mitglied gefunden.",
                    metadata={"member_id": member_id, "found": False},
                )

            # Extract analytical summary section
            summary = content
            if "## Analytische Zusammenfassung" in content:
                try:
                    summary = content.split("## Analytische Zusammenfassung")[1].split("##")[0].strip()
                except Exception:
                    summary = content[:2000]

            return AdapterResult(
                success=True,
                data=summary,
                metadata={"member_id": member_id, "found": True},
            )
        except Exception as exc:
            logger.error("member_memory_adapter.summary_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Member summary retrieval failed: {exc}")

    # ── memory.member.history ────────────────────────────────────────

    async def _history(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Get recent conversation history for a member.

        Required kwargs:
            member_id (str): The member's customer_id or member_number.
        Optional kwargs:
            limit (int): Number of recent messages to return (default: 20).
        """
        member_id = kwargs.get("member_id")
        if not member_id:
            return AdapterResult(
                success=False,
                error="Parameter 'member_id' is required for memory.member.history",
                error_code="MISSING_PARAM",
            )

        limit = kwargs.get("limit", 20)

        try:
            db = open_session()
            try:
                # Resolve member to find their chat sessions
                cid_lookup = -1
                mid = str(member_id).strip()
                if mid.isdigit() and int(mid) <= 2147483647:
                    cid_lookup = int(mid)

                member = db.query(StudioMember).filter(
                    StudioMember.tenant_id == tenant_id,
                    (StudioMember.customer_id == cid_lookup) | (StudioMember.member_number == mid)
                ).first()

                if not member:
                    return AdapterResult(
                        success=True,
                        data="Mitglied nicht gefunden.",
                        metadata={"member_id": member_id, "found": False},
                    )

                # Find sessions linked to this member
                sessions = db.query(ChatSession).filter(
                    ChatSession.tenant_id == tenant_id,
                    ChatSession.member_id == str(member.customer_id),
                ).order_by(ChatSession.last_message_at.desc()).limit(5).all()

                if not sessions:
                    return AdapterResult(
                        success=True,
                        data="Keine Chat-Sitzungen für dieses Mitglied gefunden.",
                        metadata={"member_id": member_id, "found": False},
                    )

                session_ids = [str(session.id) for session in sessions]
                messages = db.query(ChatMessage).filter(
                    ChatMessage.session_id.in_(session_ids),
                ).order_by(ChatMessage.timestamp.desc()).limit(limit).all()
            finally:
                db.close()

            history = []
            for msg in reversed(messages):
                history.append({
                    "role": msg.role,
                    "content": msg.content[:500] if msg.content else "",
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                })

            return AdapterResult(
                success=True,
                data=history,
                metadata={
                    "member_id": member_id,
                    "member_name": f"{member.first_name} {member.last_name}".strip(),
                    "message_count": len(history),
                },
            )
        except Exception as exc:
            logger.error("member_memory_adapter.history_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Member history retrieval failed: {exc}")

    # ── memory.member.index ──────────────────────────────────────────

    async def _index(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """Index or re-index a member's memory profile into ChromaDB.

        Required kwargs:
            member_id (str): The member's customer_id.
        Optional kwargs:
            profile_summary (str): Pre-computed summary to index (skips LLM analysis).
        """
        member_id = kwargs.get("member_id")
        if not member_id:
            return AdapterResult(
                success=False,
                error="Parameter 'member_id' is required for memory.member.index",
                error_code="MISSING_PARAM",
            )

        profile_summary = kwargs.get("profile_summary")

        try:
            if profile_summary:
                # Direct indexing with provided summary
                from app.memory.member_memory_analyzer import _index_member_memory
                await _index_member_memory(str(member_id), tenant_id, profile_summary)
                return AdapterResult(
                    success=True,
                    data={"member_id": member_id, "action": "indexed", "source": "provided_summary"},
                )
            else:
                # Read from file and index
                slug = self._resolve_tenant_slug(tenant_id)
                content = self._read_member_file(str(member_id), slug)

                if not content:
                    return AdapterResult(
                        success=False,
                        error=f"No profile file found for member {member_id}",
                        error_code="NOT_FOUND",
                    )

                from app.memory.member_memory_analyzer import _index_member_memory
                await _index_member_memory(str(member_id), tenant_id, content)

                return AdapterResult(
                    success=True,
                    data={"member_id": member_id, "action": "indexed", "source": "profile_file"},
                )
        except Exception as exc:
            logger.error("member_memory_adapter.index_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Member memory indexing failed: {exc}")

    # ── memory.member.list ───────────────────────────────────────────

    async def _list_members(self, tenant_id: int, **kwargs: Any) -> AdapterResult:
        """List all members that have memory profiles.

        Scans the member memory directories for profile files.
        """
        try:
            slug = self._resolve_tenant_slug(tenant_id)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

            possible_dirs = [
                os.path.join(base_dir, "data", "knowledge", "tenants", slug, "members"),
                os.path.join(base_dir, "data", "knowledge", "members"),
            ]

            profiles = []
            seen_ids = set()

            for mem_dir in possible_dirs:
                if not os.path.exists(mem_dir):
                    continue
                for filename in os.listdir(mem_dir):
                    if filename.endswith(".md"):
                        mid = filename.replace(".md", "")
                        if mid not in seen_ids:
                            seen_ids.add(mid)
                            filepath = os.path.join(mem_dir, filename)
                            size = os.path.getsize(filepath)
                            profiles.append({
                                "member_id": mid,
                                "file": filename,
                                "size_bytes": size,
                                "directory": mem_dir,
                            })

            return AdapterResult(
                success=True,
                data=profiles,
                metadata={"total_profiles": len(profiles), "tenant_slug": slug},
            )
        except Exception as exc:
            logger.error("member_memory_adapter.list_failed", error=str(exc))
            return AdapterResult(success=False, error=f"Member listing failed: {exc}")

    # ── Health Check ─────────────────────────────────────────────────

    async def health_check(self, tenant_id: int) -> AdapterResult:
        """Check if the member memory system is accessible."""
        try:
            slug = self._resolve_tenant_slug(tenant_id)
            from app.memory.member_memory_analyzer import member_collection_name_for_slug

            collection_name = member_collection_name_for_slug(slug)

            return AdapterResult(
                success=True,
                data={
                    "status": "HEALTHY",
                    "adapter": self.integration_id,
                    "collection": collection_name,
                    "tenant_slug": slug,
                },
            )
        except Exception as exc:
            logger.warning(
                "member_memory_adapter.health_check_failed",
                error=str(exc),
                tenant_id=tenant_id,
            )
            return AdapterResult(
                success=True,
                data={"status": "NOT_CONFIGURED", "reason": str(exc)},
            )

    # ── Helpers ───────────────────────────────────────────────────────

    def _resolve_tenant_slug(self, tenant_id: int) -> str:
        """Resolve the tenant slug from tenant_id."""
        try:
            db = open_session()
            try:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                return tenant.slug if tenant else "system"
            finally:
                db.close()
        except Exception:
            return "system"

    def _read_member_file(self, member_id: str, tenant_slug: str) -> str | None:
        """Read a member's profile markdown file.

        Searches in tenant-specific and legacy directories.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        possible_dirs = [
            os.path.join(base_dir, "data", "knowledge", "tenants", tenant_slug, "members"),
            os.path.join(base_dir, "data", "knowledge", "members"),
            "/app/data/knowledge/members",
            f"/app/data/knowledge/tenants/{tenant_slug}/members",
        ]

        for mem_dir in possible_dirs:
            filepath = os.path.join(mem_dir, f"{member_id}.md")
            if os.path.exists(filepath):
                logger.debug("member_memory_adapter.file_found", path=filepath)
                with open(filepath, "r", encoding="utf-8") as f:
                    return f.read()

        return None
