from __future__ import annotations

import ast
import json as _json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func

from app.core.auth import AuthContext
from app.domains.identity.models import AuditLog
from app.domains.support.models import ChatMessage, ChatSession, MemberFeedback
from app.gateway.admin_analytics_repository import admin_analytics_repository
from app.shared.db import session_scope

_CHANNEL_NAMES: dict[str, str] = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "email": "E-Mail",
    "sms": "SMS",
    "phone": "Telefon",
}


class AdminAnalyticsService:
    @staticmethod
    def _parse_msg_meta_safe(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return _json.loads(raw)
        except Exception:
            return {}

    @staticmethod
    def _safe_parse_details(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return _json.loads(raw)
        except (_json.JSONDecodeError, TypeError):
            try:
                return ast.literal_eval(raw)
            except Exception:
                return {"_raw": raw}

    @staticmethod
    def _time_ago(ts: datetime) -> str:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - ts
        total_seconds = int(diff.total_seconds())
        if total_seconds < 60:
            return f"vor {total_seconds}s"
        if total_seconds < 3600:
            return f"vor {total_seconds // 60} Min"
        if total_seconds < 86400:
            return f"vor {total_seconds // 3600} Std"
        return f"vor {total_seconds // 86400} Tagen"

    @staticmethod
    def _initials(name: str | None) -> str:
        if not name:
            return "??"
        parts = name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return name[:2].upper()

    def _fetch_window(self, db, tenant_id: int, since: datetime) -> list[dict[str, Any]]:
        rows = admin_analytics_repository.list_assistant_messages_since(
            db,
            tenant_id=tenant_id,
            since=since,
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            meta = self._parse_msg_meta_safe(row.metadata_json)
            conf_raw = meta.get("confidence")
            conf: float | None = None
            if isinstance(conf_raw, (int, float)):
                conf = float(conf_raw)
            elif isinstance(conf_raw, str):
                try:
                    conf = float(conf_raw)
                except ValueError:
                    pass
            result.append({
                "escalated": meta.get("escalated") is True or meta.get("escalated") == "true",
                "confidence": conf,
                "channel": str(meta.get("channel") or "unknown").lower(),
                "ts": row.timestamp,
            })
        return result

    def get_overview(self, user: AuthContext) -> dict[str, Any]:
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        cutoff_24h = (now - timedelta(hours=24)).replace(tzinfo=None)
        cutoff_30d = (now - timedelta(days=30)).replace(tzinfo=None)
        cutoff_60d = (now - timedelta(days=60)).replace(tzinfo=None)

        with session_scope() as db:
            msgs_24h = self._fetch_window(db, user.tenant_id, cutoff_24h)
            msgs_30d = self._fetch_window(db, user.tenant_id, cutoff_30d)
            msgs_60d = self._fetch_window(db, user.tenant_id, cutoff_60d)
            msgs_prev_30d = [msg for msg in msgs_60d if msg["ts"] < cutoff_30d]

            escal_24h = sum(1 for msg in msgs_24h if msg["escalated"])
            total_24h = len(msgs_24h)
            confs = [msg["confidence"] for msg in msgs_24h if msg["confidence"] is not None]
            conf_avg = round((sum(confs) / len(confs)) * 100, 1) if confs else 0.0
            channels_24h: dict[str, int] = {}
            for msg in msgs_24h:
                channels_24h[msg["channel"]] = channels_24h.get(msg["channel"], 0) + 1

            conf_dist = [
                {"range": "90–100%", "count": sum(1 for c in confs if c >= 0.9)},
                {"range": "75–89%", "count": sum(1 for c in confs if 0.75 <= c < 0.9)},
                {"range": "50–74%", "count": sum(1 for c in confs if 0.5 <= c < 0.75)},
                {"range": "<50%", "count": sum(1 for c in confs if c < 0.5)},
            ]
            conf_total = len(confs)
            tickets_30d = len(msgs_30d)
            tickets_prev = len(msgs_prev_30d)
            ai_rate = round(((total_24h - escal_24h) / max(1, total_24h)) * 100, 1)
            month_trend = round(((tickets_30d - tickets_prev) / max(1, tickets_prev)) * 100, 1)
            return {
                "tickets_24h": total_24h,
                "resolved_24h": total_24h - escal_24h,
                "escalated_24h": escal_24h,
                "ai_resolution_rate": ai_rate,
                "escalation_rate": round((escal_24h / max(1, total_24h)) * 100, 1),
                "confidence_avg": conf_avg,
                "confidence_high_pct": round(sum(1 for c in confs if c >= 0.9) / max(1, conf_total) * 100),
                "confidence_low_pct": round(sum(1 for c in confs if c < 0.5) / max(1, conf_total) * 100),
                "confidence_distribution": conf_dist,
                "channels_24h": channels_24h,
                "tickets_30d": tickets_30d,
                "tickets_prev_30d": tickets_prev,
                "month_trend_pct": month_trend,
            }

    def get_satisfaction(self, user: AuthContext) -> dict[str, Any]:
        with session_scope() as db:
            result = admin_analytics_repository.get_feedback_summary(db, tenant_id=user.tenant_id)
            avg_raw = result.avg_rating if result and result.avg_rating else 0.0
            total = result.total_feedback if result and result.total_feedback else 0
            return {"average": round(float(avg_raw), 1), "total": total}

    def get_hourly(self, user: AuthContext) -> list[dict[str, Any]]:
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=24)).replace(tzinfo=None)
        with session_scope() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.tenant_id == user.tenant_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.timestamp >= cutoff,
                )
                .all()
            )
            hourly: dict[int, dict[str, int]] = {hour: {"aiResolved": 0, "escalated": 0} for hour in range(24)}
            for row in rows:
                ts = row.timestamp
                if ts and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                hour = ts.hour if ts else 0
                meta = self._parse_msg_meta_safe(row.metadata_json)
                if meta.get("escalated") is True or meta.get("escalated") == "true":
                    hourly[hour]["escalated"] += 1
                else:
                    hourly[hour]["aiResolved"] += 1
            return [
                {"hour": f"{hour:02d}:00", "aiResolved": hourly[hour]["aiResolved"], "escalated": hourly[hour]["escalated"]}
                for hour in range(24)
            ]

    def get_weekly(self, user: AuthContext) -> list[dict[str, Any]]:
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        with session_scope() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.tenant_id == user.tenant_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.timestamp >= cutoff,
                )
                .all()
            )
            day_labels = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]
            daily: dict[str, dict[str, int]] = {}
            for row in rows:
                ts = row.timestamp
                if ts and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                day_key = ts.strftime("%Y-%m-%d") if ts else ""
                if not day_key:
                    continue
                if day_key not in daily:
                    daily[day_key] = {"tickets": 0, "escalated": 0}
                daily[day_key]["tickets"] += 1
                meta = self._parse_msg_meta_safe(row.metadata_json)
                if meta.get("escalated") is True or meta.get("escalated") == "true":
                    daily[day_key]["escalated"] += 1

            result: list[dict[str, Any]] = []
            for idx in range(7):
                day = now - timedelta(days=6 - idx)
                key = day.strftime("%Y-%m-%d")
                rec = daily.get(key, {"tickets": 0, "escalated": 0})
                result.append({
                    "day": day_labels[day.weekday() % 7],
                    "date": key,
                    "tickets": rec["tickets"],
                    "resolved": rec["tickets"] - rec["escalated"],
                    "escalated": rec["escalated"],
                })
            return result

    def get_intents(self, user: AuthContext) -> list[dict[str, Any]]:
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        with session_scope() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.tenant_id == user.tenant_id,
                    ChatMessage.role == "assistant",
                    ChatMessage.timestamp >= cutoff,
                )
                .all()
            )
            intent_stats: dict[str, dict[str, int]] = {}
            for row in rows:
                meta = self._parse_msg_meta_safe(row.metadata_json)
                intent = str(meta.get("intent") or "unknown").strip() or "unknown"
                if intent not in intent_stats:
                    intent_stats[intent] = {"count": 0, "resolved": 0}
                intent_stats[intent]["count"] += 1
                if not (meta.get("escalated") is True or meta.get("escalated") == "true"):
                    intent_stats[intent]["resolved"] += 1

            sorted_intents = sorted(intent_stats.items(), key=lambda item: item[1]["count"], reverse=True)[:8]
            return [
                {
                    "intent": intent,
                    "label": intent.replace("_", " ").title(),
                    "count": stats["count"],
                    "aiRate": round((stats["resolved"] / max(1, stats["count"])) * 100),
                }
                for intent, stats in sorted_intents
            ]

    def get_channels(self, effective_tid: int, *, days: int) -> list[dict[str, Any]]:
        from collections import defaultdict
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=days)).replace(tzinfo=None)
        with session_scope() as db:
            messages = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.tenant_id == effective_tid,
                    ChatMessage.role == "assistant",
                    ChatMessage.timestamp >= since,
                )
                .all()
            )
            channel_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "resolved": 0})
            for message in messages:
                meta = self._parse_msg_meta_safe(message.metadata_json)
                channel = str(meta.get("channel") or "unknown").lower()
                channel_stats[channel]["count"] += 1
                if not meta.get("escalated"):
                    channel_stats[channel]["resolved"] += 1

            channel_order = ["whatsapp", "telegram", "email", "sms", "phone"]
            result = []
            for channel in channel_order:
                if channel not in channel_stats:
                    continue
                stats = channel_stats[channel]
                total = stats["count"]
                ai_rate = round(stats["resolved"] / max(total, 1) * 100)
                result.append({
                    "ch": channel,
                    "name": _CHANNEL_NAMES.get(channel, channel.capitalize()),
                    "tickets": total,
                    "aiRate": ai_rate,
                    "esc": f"{100 - ai_rate}%",
                })

            for channel, stats in channel_stats.items():
                if channel in channel_order:
                    continue
                total = stats["count"]
                ai_rate = round(stats["resolved"] / max(total, 1) * 100)
                result.append({
                    "ch": channel,
                    "name": _CHANNEL_NAMES.get(channel, channel.capitalize()),
                    "tickets": total,
                    "aiRate": ai_rate,
                    "esc": f"{100 - ai_rate}%",
                })
            return result

    def get_recent_sessions(self, effective_tid: int, *, limit: int) -> list[dict[str, Any]]:
        with session_scope() as db:
            sessions = admin_analytics_repository.list_recent_sessions(
                db,
                tenant_id=effective_tid,
                limit=limit,
            )
            message_rows = admin_analytics_repository.list_messages_for_session_ids(
                db,
                tenant_id=effective_tid,
                session_ids=[session.user_id for session in sessions],
            )
            messages_by_session: dict[str, list[ChatMessage]] = {}
            for row in message_rows:
                messages_by_session.setdefault(row.session_id, []).append(row)
            result = []
            for session in sessions:
                session_messages = messages_by_session.get(session.user_id, [])
                last_msg = next((row for row in session_messages if row.role == "assistant"), None)
                last_user_msg = next((row for row in session_messages if row.role == "user"), None)
                message_count = len(session_messages)

                meta = self._parse_msg_meta_safe(last_msg.metadata_json if last_msg else None)
                channel = meta.get("channel") or (session.platform or "unknown").lower()
                confidence_raw = meta.get("confidence")
                confidence = round(float(confidence_raw) * 100) if confidence_raw is not None else 0
                escalated = meta.get("escalated", False)

                issue_text = (last_user_msg.content or "")[:120] if last_user_msg else ""
                last_active = session.last_message_at
                if last_active and last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)

                member_name = session.user_name or session.email or session.phone_number or f"User {session.user_id[-6:]}"
                result.append({
                    "id": f"T-{session.id:04d}",
                    "channel": channel,
                    "member": member_name,
                    "avatar": self._initials(member_name),
                    "issue": issue_text,
                    "confidence": confidence,
                    "status": "escalated" if escalated else "resolved",
                    "time": self._time_ago(last_active) if last_active else "–",
                    "messages": message_count,
                })
            return result

    def get_audit_logs(self, user: AuthContext, *, limit: int, offset: int) -> dict[str, Any]:
        with session_scope() as db:
            total = admin_analytics_repository.count_audit_logs(db, tenant_id=user.tenant_id)
            rows = admin_analytics_repository.list_audit_logs(
                db,
                tenant_id=user.tenant_id,
                limit=limit,
                offset=offset,
            )
            return {
                "total": total,
                "items": [
                    {
                        "id": row.id,
                        "actor_user_id": row.actor_user_id,
                        "actor_email": row.actor_email,
                        "action": row.action,
                        "category": row.category,
                        "target_type": row.target_type,
                        "target_id": row.target_id,
                        "details": self._safe_parse_details(row.details_json),
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ],
            }


service = AdminAnalyticsService()
