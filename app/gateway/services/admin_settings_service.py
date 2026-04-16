from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from fastapi import HTTPException
from fastapi.responses import Response

from app.core.auth import AuthContext
from app.gateway.admin_shared import REDACTED_SECRET_VALUE, safe_tenant_slug, write_admin_audit
from app.gateway.persistence import persistence

logger = structlog.get_logger()


class AdminSettingsService:
    def get_prompt_config(self, user: AuthContext) -> dict[str, Any]:
        from app.core.prompt_builder import PROMPT_SETTINGS_DEFAULTS, PROMPT_SETTINGS_KEYS

        result: dict[str, Any] = {}
        for key in PROMPT_SETTINGS_KEYS:
            value = persistence.get_setting(key, None, tenant_id=user.tenant_id)
            result[key] = value if value is not None else PROMPT_SETTINGS_DEFAULTS.get(key, "")
        return result

    def update_prompt_config(self, user: AuthContext, payload: dict[str, Any]) -> dict[str, str]:
        from app.core.prompt_builder import PROMPT_SETTINGS_KEYS

        for key, value in payload.items():
            if key in PROMPT_SETTINGS_KEYS:
                persistence.upsert_setting(key, str(value), tenant_id=user.tenant_id)

        write_admin_audit(
            actor=user,
            action="prompt_config.update",
            category="settings",
            target_type="tenant",
            target_id=str(user.tenant_id),
            details={"changed_keys": sorted(payload.keys())},
        )
        return {"status": "ok", "updated": str(len(payload))}

    def get_prompt_config_schema(self) -> dict[str, Any]:
        from app.core.prompt_builder import PROMPT_SETTINGS_SCHEMA, VARIABLE_CATEGORIES

        return {
            "categories": VARIABLE_CATEGORIES,
            "variables": PROMPT_SETTINGS_SCHEMA,
        }

    async def test_platform_email(self, user: AuthContext, body: Any) -> dict[str, Any]:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        effective_pass = body.pass_
        if effective_pass == REDACTED_SECRET_VALUE:
            effective_pass = persistence.get_setting("platform_email_smtp_pass", tenant_id=user.tenant_id)

        if not effective_pass:
            return {"status": "error", "error": "No SMTP password provided"}

        try:
            msg = MIMEMultipart()
            msg["From"] = f"{body.from_name} <{body.from_addr}>"
            msg["To"] = body.recipient
            msg["Subject"] = "ARIIA Platform SMTP Test"

            content = (
                "Dies ist ein Test der ARIIA SaaS Plattform SMTP-Konfiguration.\n\n"
                f"Zeitstempel: {datetime.now(timezone.utc).isoformat()}\n"
                f"Host: {body.host}\n"
                f"User: {body.user}"
            )
            msg.attach(MIMEText(content, "plain"))

            def _send() -> None:
                with smtplib.SMTP(body.host, body.port, timeout=15) as server:
                    server.starttls()
                    server.login(body.user, effective_pass)
                    server.send_message(msg)

            await asyncio.to_thread(_send)
            return {"status": "ok", "message": f"Test-Mail erfolgreich an {body.recipient} gesendet."}
        except Exception as exc:
            logger.error("admin.smtp_test_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}

    def get_whatsapp_qr(self, user: AuthContext) -> dict[str, Any]:
        bridge_url = persistence.get_setting("bridge_qr_url", tenant_id=user.tenant_id) or "http://localhost:3000/qr"
        return {
            "status": "ok",
            "qr_url": bridge_url,
            "tenant_slug": safe_tenant_slug(user),
        }

    async def get_whatsapp_qr_image(self, user: AuthContext) -> Response:
        slug = safe_tenant_slug(user)
        waha_url = persistence.get_setting("waha_api_url", tenant_id=user.tenant_id) or "http://ariia-whatsapp-bridge:3000"
        waha_key = persistence.get_setting("waha_api_key", tenant_id=user.tenant_id) or "ariia-waha-secret"
        session_name = slug or "default"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                sessions_resp = await client.get(
                    f"{waha_url}/api/sessions",
                    headers={"X-Api-Key": waha_key},
                )
                if sessions_resp.status_code == 200:
                    sessions = sessions_resp.json()
                    current_session = next((s for s in sessions if s["name"] == session_name), None)

                    if not current_session or current_session.get("status") in {"STOPPED", "FAILED"}:
                        if current_session and current_session.get("status") == "FAILED":
                            logger.warning("admin.whatsapp.session_failed_reset", tenant=slug)
                            await client.post(
                                f"{waha_url}/api/sessions/stop",
                                json={"name": session_name},
                                headers={"X-Api-Key": waha_key},
                            )
                            await asyncio.sleep(2)
                            raise HTTPException(status_code=404, detail="RESTARTING")

                        webhook_url = f"http://ariia-core:8000/webhook/waha/{slug}"
                        await client.post(
                            f"{waha_url}/api/sessions/start",
                            headers={"X-Api-Key": waha_key, "Content-Type": "application/json"},
                            json={
                                "name": session_name,
                                "displayName": "Ariia",
                                "config": {
                                    "webhooks": [
                                        {
                                            "url": webhook_url,
                                            "events": ["message", "session.status"],
                                            "hmac": waha_key,
                                        }
                                    ]
                                },
                            },
                        )
                        raise HTTPException(status_code=404, detail="STARTING")

                    if current_session.get("status") == "WORKING":
                        raise HTTPException(status_code=404, detail="CONNECTED")

                    webhook_url = f"http://ariia-core:8000/webhook/waha/{slug}"
                    try:
                        await client.post(
                            f"{waha_url}/api/sessions/{session_name}/webhooks",
                            headers={"X-Api-Key": waha_key, "Content-Type": "application/json"},
                            json={
                                "webhooks": [
                                    {
                                        "url": webhook_url,
                                        "events": ["message", "session.status"],
                                        "hmac": waha_key,
                                    }
                                ]
                            },
                        )
                    except Exception:
                        pass

                qr_resp = None
                for _ in range(2):
                    qr_resp = await client.get(
                        f"{waha_url}/api/{session_name}/auth/qr",
                        headers={"X-Api-Key": waha_key, "Accept": "image/png"},
                    )
                    if qr_resp.status_code == 200 and qr_resp.headers.get("content-type", "").startswith("image/"):
                        break
                    await asyncio.sleep(2)

                if qr_resp and qr_resp.status_code == 200 and qr_resp.headers.get("content-type", "").startswith("image/"):
                    return Response(content=qr_resp.content, media_type="image/png")
                if qr_resp and (qr_resp.status_code == 404 or b"QR code" not in qr_resp.content):
                    raise HTTPException(status_code=404, detail="NO_QR_FOUND")
                raise HTTPException(status_code=502, detail="QR-Code konnte nicht geladen werden")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("admin.qr_proxy_failed", error=str(exc))
            raise HTTPException(status_code=502, detail="WhatsApp Bridge Fehler")

    async def reset_whatsapp_session(self, user: AuthContext) -> dict[str, str]:
        waha_url = persistence.get_setting("waha_api_url", tenant_id=user.tenant_id) or "http://ariia-whatsapp-bridge:3000"
        waha_key = persistence.get_setting("waha_api_key", tenant_id=user.tenant_id) or "ariia-waha-secret"
        session_name = safe_tenant_slug(user) or "default"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{waha_url}/api/sessions/stop",
                    headers={"X-Api-Key": waha_key, "Content-Type": "application/json"},
                    json={"name": session_name, "logout": True},
                )
                await asyncio.sleep(2)
            return {"status": "ok", "message": "WhatsApp Sitzung zurückgesetzt. Bitte QR-Code neu laden."}
        except Exception as exc:
            logger.error("admin.whatsapp.reset_failed", error=str(exc))
            return {"status": "ok", "message": "Reset-Anfrage an Bridge gesendet."}


service = AdminSettingsService()
