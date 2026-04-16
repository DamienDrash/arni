from __future__ import annotations

import asyncio
import json as _json
import random
from datetime import date, datetime, timezone
from typing import Any

import redis as _redis
import structlog

from app.core.auth import AuthContext
from app.domains.support.models import ChatSession, StudioMember
from app.gateway.admin_operations_repository import admin_operations_repository
from app.core.redis_keys import human_mode_key, token_key, user_token_key
from app.gateway.persistence import persistence
from app.gateway.redis_bus import RedisBus
from app.gateway.schemas import Platform
from app.gateway.utils import send_to_user
from app.shared.db import session_scope
from config.settings import get_settings

from app.integrations.magicline.member_enrichment import enrich_member, get_member_profile
from app.integrations.magicline.members_sync import sync_members_from_magicline

logger = structlog.get_logger()
settings = get_settings()


class AdminOperationsService:
    async def create_redis_bus(self) -> RedisBus:
        bus = RedisBus(redis_url=settings.redis_url)
        await bus.connect()
        return bus

    @staticmethod
    def _legacy_human_mode_key(user_id: str) -> str:
        return f"session:{user_id}:human_mode"

    @staticmethod
    def _legacy_token_key(token: str) -> str:
        return f"token:{token}"

    @staticmethod
    def _legacy_user_token_key(user_id: str) -> str:
        return f"user_token:{user_id}"

    async def _read_active_token(self, bus: RedisBus, tenant_id: int, user_id: str) -> str | None:
        token_value = await bus.client.get(user_token_key(tenant_id, user_id))
        if token_value:
            return token_value.decode("utf-8") if isinstance(token_value, bytes) else str(token_value)
        legacy_value = await bus.client.get(self._legacy_user_token_key(user_id))
        if legacy_value:
            token_str = legacy_value.decode("utf-8") if isinstance(legacy_value, bytes) else str(legacy_value)
            await bus.client.setex(user_token_key(tenant_id, user_id), 86400, token_str)
            await bus.client.delete(self._legacy_user_token_key(user_id))
            return token_str
        return None

    async def _store_active_token(
        self,
        bus: RedisBus,
        tenant_id: int,
        token: str,
        data: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> None:
        await bus.client.setex(token_key(tenant_id, token), 86400, _json.dumps(data))
        if user_id:
            await bus.client.setex(user_token_key(tenant_id, user_id), 86400, token)

    async def _clear_active_token(
        self,
        bus: RedisBus,
        tenant_id: int,
        user_id: str,
        token: str | None,
    ) -> None:
        await bus.client.delete(user_token_key(tenant_id, user_id))
        await bus.client.delete(self._legacy_user_token_key(user_id))
        if token:
            await bus.client.delete(token_key(tenant_id, token))
            await bus.client.delete(self._legacy_token_key(token))

    async def _ensure_active_token(
        self,
        bus: RedisBus,
        tenant_id: int,
        user_id: str,
        *,
        member_id: str | None,
        phone_number: str | None,
        email: str | None,
    ) -> str | None:
        active_token = await self._read_active_token(bus, tenant_id, user_id)
        if member_id:
            await self._clear_active_token(bus, tenant_id, user_id, active_token)
            return None
        if active_token:
            return active_token

        active_token = f"{random.randint(0, 999999):06d}"
        await self._store_active_token(
            bus,
            tenant_id,
            active_token,
            {
                "member_id": member_id,
                "user_id": user_id,
                "phone_number": phone_number,
                "email": email,
            },
            user_id=user_id,
        )
        return active_token

    async def sync_members(self, user: AuthContext) -> dict[str, int]:
        import threading as _threading

        try:
            started_at = datetime.now(timezone.utc).isoformat()
            result = sync_members_from_magicline(tenant_id=user.tenant_id)
            persistence.upsert_setting("magicline_last_sync_at", started_at, tenant_id=user.tenant_id)
            persistence.upsert_setting("magicline_last_sync_status", "ok", tenant_id=user.tenant_id)
            persistence.upsert_setting("magicline_last_sync_error", "", tenant_id=user.tenant_id)

            from app.integrations.magicline.scheduler import _enrich_tenant_members

            _threading.Thread(
                target=_enrich_tenant_members,
                args=(user.tenant_id,),
                daemon=True,
                name=f"manual-enrich-t{user.tenant_id}",
            ).start()
            return result
        except ValueError as exc:
            logger.warning("admin.sync_members.config_error", tenant_id=user.tenant_id, error=str(exc))
            raise

    def get_members_stats(self, user: AuthContext) -> dict[str, Any]:
        with session_scope() as db:
            return admin_operations_repository.get_member_stats(db, tenant_id=user.tenant_id)

    def list_members(self, user: AuthContext, *, limit: int, search: str | None) -> list[dict[str, Any]]:
        with session_scope() as db:
            session_by_member = admin_operations_repository.get_member_chat_summary(
                db,
                tenant_id=user.tenant_id,
            )
            rows = admin_operations_repository.list_members(
                db,
                tenant_id=user.tenant_id,
                limit=limit,
                search=search,
            )
            return [
                {
                    "customer_id": row.customer_id,
                    "member_number": row.member_number,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "date_of_birth": row.date_of_birth.isoformat() if row.date_of_birth else None,
                    "phone_number": row.phone_number,
                    "email": row.email,
                    "gender": row.gender,
                    "preferred_language": row.preferred_language,
                    "member_since": row.member_since.isoformat() if row.member_since else None,
                    "is_paused": row.is_paused,
                    "pause_info": _json.loads(row.pause_info) if row.pause_info else None,
                    "contract_info": _json.loads(row.contract_info) if row.contract_info else None,
                    "enriched_at": row.enriched_at.isoformat() if row.enriched_at else None,
                    "additional_info": _json.loads(row.additional_info) if row.additional_info else None,
                    "checkin_stats": _json.loads(row.checkin_stats) if row.checkin_stats else None,
                    "recent_bookings": _json.loads(row.recent_bookings) if row.recent_bookings else None,
                    "verified": (
                        ((session_by_member.get((row.member_number or "").strip()) or {}).get("chat_sessions") or 0)
                        + ((session_by_member.get(str(row.customer_id)) or {}).get("chat_sessions") or 0)
                    )
                    > 0,
                    "chat_sessions": (
                        ((session_by_member.get((row.member_number or "").strip()) or {}).get("chat_sessions") or 0)
                        + ((session_by_member.get(str(row.customer_id)) or {}).get("chat_sessions") or 0)
                    ),
                    "last_chat_at": (
                        (session_by_member.get((row.member_number or "").strip()) or {}).get("last_chat_at")
                        or (session_by_member.get(str(row.customer_id)) or {}).get("last_chat_at")
                    ),
                }
                for row in rows
            ]

    def get_enrichment_stats(self, user: AuthContext) -> dict[str, Any]:
        with session_scope() as db:
            return admin_operations_repository.get_enrichment_stats(db, tenant_id=user.tenant_id)

    @staticmethod
    def get_member_detail(user: AuthContext, customer_id: int) -> dict[str, Any]:
        profile = get_member_profile(customer_id, tenant_id=user.tenant_id)
        if not profile:
            raise LookupError("Member not found")
        return profile

    def enqueue_enrich_all_members(self, user: AuthContext, *, force: bool) -> dict[str, Any]:
        with session_scope() as db:
            ids = admin_operations_repository.list_member_customer_ids(db, tenant_id=user.tenant_id)

        if not ids:
            return {"enqueued": 0, "estimated_minutes": 0}

        redis_client = _redis.from_url(get_settings().redis_url, decode_responses=True)
        queue_key = f"tenant:{user.tenant_id}:enrich_queue"
        if force:
            redis_client.delete(queue_key)

        chunk_size = 500
        for index in range(0, len(ids), chunk_size):
            redis_client.sadd(queue_key, *ids[index:index + chunk_size])

        enqueued = redis_client.scard(queue_key)
        minutes = (enqueued * 6) // 60
        logger.info("admin.enrich_all.enqueued", total=enqueued, minutes=minutes)
        return {"enqueued": enqueued, "estimated_minutes": minutes}

    async def enrich_member(self, user: AuthContext, customer_id: int, *, force: bool) -> dict[str, Any]:
        return await asyncio.to_thread(enrich_member, customer_id, force, user.tenant_id)

    async def list_active_handoffs(self, user: AuthContext) -> list[dict[str, Any]]:
        bus = await self.create_redis_bus()
        try:
            if user.role == "system_admin":
                keys = await bus.client.keys("session:*:human_mode")
                keys += await bus.client.keys("t*:human_mode:*")
            else:
                keys = await bus.client.keys(human_mode_key(user.tenant_id or 0, "*"))
                keys += await bus.client.keys("session:*:human_mode")

            results = []
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode("utf-8")

                parts = key.split(":")
                user_id = None
                if key.startswith("session:") and len(parts) >= 3:
                    user_id = parts[1]
                elif key.startswith("t") and len(parts) >= 3:
                    user_id = parts[-1]
                if not user_id:
                    continue

                session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
                if user.role != "system_admin" and not session:
                    continue

                active_token = await self._ensure_active_token(
                    bus,
                    user.tenant_id,
                    user_id,
                    member_id=session.member_id if session else None,
                    phone_number=session.phone_number if session else None,
                    email=session.email if session else None,
                )
                results.append({
                    "user_id": user_id,
                    "key": key,
                    "member_id": session.member_id if session else None,
                    "user_name": session.user_name if session else None,
                    "platform": session.platform if session else "unknown",
                    "active_token": active_token,
                })
            return results
        finally:
            await bus.disconnect()

    async def resolve_handoff(self, user: AuthContext, user_id: str) -> dict[str, str]:
        session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
        if user.role != "system_admin" and not session:
            raise LookupError("Handoff not found")

        bus = await self.create_redis_bus()
        try:
            await bus.client.delete(self._legacy_human_mode_key(user_id))
            await bus.client.delete(human_mode_key(user.tenant_id, user_id))
            active_token = await self._read_active_token(bus, user.tenant_id, user_id)
            await self._clear_active_token(bus, user.tenant_id, user_id, active_token)
            logger.info("admin.handoff_resolved", user_id=user_id)
            return {"status": "resolved"}
        finally:
            await bus.disconnect()

    async def generate_verification_token(
        self,
        user: AuthContext,
        *,
        member_id: str,
        user_id: str | None,
        phone_number: str | None,
        email: str | None,
    ) -> dict[str, str]:
        if user.role != "system_admin" and user_id:
            session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
            if not session:
                raise LookupError("User session not found")

        token = f"{random.randint(0, 999999):06d}"
        bus = await self.create_redis_bus()
        try:
            await self._store_active_token(
                bus,
                user.tenant_id,
                token,
                {
                    "member_id": member_id,
                    "user_id": user_id,
                    "phone_number": phone_number,
                    "email": email,
                },
                user_id=user_id,
            )
            logger.info("admin.token_generated", token=token, member_id=member_id)
            return {"token": token}
        finally:
            await bus.disconnect()

    async def get_dashboard_stats(self, user: AuthContext) -> dict[str, Any]:
        db_stats = persistence.get_stats(tenant_id=user.tenant_id)
        bus = await self.create_redis_bus()
        try:
            if user.role == "system_admin":
                keys = await bus.client.keys("session:*:human_mode")
                keys += await bus.client.keys("t*:human_mode:*")
            else:
                keys = await bus.client.keys(human_mode_key(user.tenant_id, "*"))
            active_handoffs = len(keys)
        except Exception as exc:
            logger.error("admin.stats_redis_failed", error=str(exc))
            active_handoffs = 0
        finally:
            await bus.disconnect()
        return {**db_stats, "active_handoffs": active_handoffs}

    async def list_recent_chats(self, user: AuthContext, *, limit: int) -> list[dict[str, Any]]:
        sessions = persistence.get_recent_sessions(tenant_id=user.tenant_id, limit=limit)
        bus = await self.create_redis_bus()
        try:
            results = []
            for session in sessions:
                active_token = await self._ensure_active_token(
                    bus,
                    user.tenant_id,
                    session.user_id,
                    member_id=session.member_id,
                    phone_number=session.phone_number,
                    email=session.email,
                )
                results.append({
                    "user_id": session.user_id,
                    "platform": session.platform,
                    "last_active": session.last_message_at.isoformat() if session.last_message_at else None,
                    "is_active": session.is_active,
                    "user_name": session.user_name,
                    "phone_number": session.phone_number,
                    "email": session.email,
                    "member_id": session.member_id,
                    "active_token": active_token,
                })
            return results
        finally:
            await bus.disconnect()

    @staticmethod
    def get_chat_history(user: AuthContext, user_id: str) -> list[dict[str, Any]]:
        history = persistence.get_chat_history(user_id, tenant_id=user.tenant_id)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "metadata": msg.metadata_json,
            }
            for msg in history
        ]

    async def send_intervention(
        self,
        user: AuthContext,
        *,
        user_id: str,
        content: str,
        platform_value: str | None,
    ) -> dict[str, str]:
        session = persistence.get_session_by_user_id(user_id, tenant_id=user.tenant_id)
        platform_name = (platform_value or (session.platform if session else "") or "telegram").strip().lower()
        platform = Platform(platform_name)
        await send_to_user(
            user_id=user_id,
            platform=platform,
            content=content,
            metadata={"chat_id": user_id},
            tenant_id=user.tenant_id,
        )
        logger.info("admin.intervention.sent", user_id=user_id, platform=platform.value)
        return {"status": "ok"}

    @staticmethod
    def link_member_to_chat(user: AuthContext, user_id: str, member_id: str | None) -> dict[str, Any]:
        ok = persistence.link_session_to_member(user_id=user_id, tenant_id=user.tenant_id, member_id=member_id)
        if not ok:
            raise LookupError("Session not found")
        logger.info("admin.link_member", user_id=user_id, member_id=member_id)
        return {"status": "ok", "user_id": user_id, "member_id": member_id}

    def search_members_for_link(self, user: AuthContext, *, query_text: str) -> list[dict[str, Any]]:
        with session_scope() as db:
            members = admin_operations_repository.search_members_for_link(
                db,
                tenant_id=user.tenant_id,
                query_text=query_text,
            )
            return [
                {
                    "id": member.id,
                    "customer_id": member.customer_id,
                    "member_number": member.member_number,
                    "first_name": member.first_name,
                    "last_name": member.last_name,
                    "email": member.email,
                    "phone_number": member.phone_number,
                }
                for member in members
            ]

    async def reset_chat(
        self,
        user: AuthContext,
        *,
        user_id: str,
        clear_verification: bool,
        clear_contact: bool,
        clear_history: bool,
        clear_handoff: bool,
    ) -> dict[str, Any]:
        reset_result = persistence.reset_chat(
            user_id,
            clear_verification=clear_verification,
            clear_contact=clear_contact,
            clear_history=clear_history,
            tenant_id=user.tenant_id,
        )

        handoff_cleared = False
        if clear_handoff:
            bus = await self.create_redis_bus()
            try:
                cleared = await bus.client.delete(self._legacy_human_mode_key(user_id))
                cleared += await bus.client.delete(human_mode_key(user.tenant_id, user_id))
                handoff_cleared = cleared > 0
            finally:
                await bus.disconnect()

        logger.info(
            "admin.chat_reset",
            user_id=user_id,
            deleted_messages=reset_result["deleted_messages"],
            clear_verification=clear_verification,
            clear_contact=clear_contact,
            clear_handoff=clear_handoff,
        )
        return {
            "status": "ok",
            "user_id": user_id,
            "session_found": reset_result["session_found"],
            "deleted_messages": reset_result["deleted_messages"],
            "verification_cleared": clear_verification,
            "contact_cleared": clear_contact,
            "handoff_cleared": handoff_cleared if clear_handoff else False,
        }


service = AdminOperationsService()
