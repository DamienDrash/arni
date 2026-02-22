"""ARIIA v1.4 – Agent Ops (The Scheduler).

@BACKEND: Sprint 2 → Sprint 9 (LLM-powered)
Handles bookings, schedules, check-ins.
One-Way-Door: Cancellations require confirmation.
"""

import re
import csv
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Optional, Any

import structlog

from app.gateway.schemas import InboundMessage
from app.gateway.persistence import persistence
from app.swarm.base import AgentResponse, BaseAgent
from app.swarm.tools import magicline

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def _load_magicline_skill_prompt() -> str:
    """Load optional Magicline skill instructions for ops prompting."""
    candidate = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "prompts"
        / "skills"
        / "magicline.md"
    )
    try:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("agent.ops.skill_prompt_load_failed", error=str(e))
    return ""




def _build_profile_block(profile: dict) -> str:
    """Render a compact member profile text block for the system prompt."""
    lines: list[str] = []

    lang_map = {"de": "Deutsch", "en": "Englisch", "tr": "Türkisch", "ar": "Arabisch", "fr": "Französisch"}
    lang = lang_map.get(profile.get("preferred_language") or "", profile.get("preferred_language") or "Unbekannt")
    gender_map = {"MALE": "männlich", "FEMALE": "weiblich", "DIVERSE": "divers"}
    gender = gender_map.get(profile.get("gender") or "", "")

    since = profile.get("member_since") or ""
    paused = profile.get("is_paused")

    lines.append(f"- Sprache: {lang}")
    if gender:
        lines.append(f"- Geschlecht: {gender}")
    if since:
        lines.append(f"- Mitglied seit: {since}")
    if paused:
        lines.append("- Status: PAUSIERT ⚠️")

    # Goals / characteristics from additional_info
    extra = profile.get("additional_info") or {}
    for key, val in list(extra.items())[:5]:
        lines.append(f"- {key}: {val}")

    # Visit / booking stats (from check-ins or booking fallback)
    stats = profile.get("checkin_stats")
    if stats:
        source = stats.get("source", "checkins")
        label = "Check-ins" if source == "checkins" else "Buchungen (abgeschlossen)"
        lines.append(f"- {label} (30 Tage): {stats.get('total_30d', '–')}")
        lines.append(f"- Ø Termine/Woche: {stats.get('avg_per_week', '–')}")
        last = stats.get("last_visit")
        days_since = stats.get("days_since_last")
        if last:
            lines.append(f"- Letzter Termin: {last} (vor {days_since} Tagen)")
        if stats.get("top_category"):
            lines.append(f"- Häufigster Kurs/Termin: {stats['top_category']}")
        lines.append(f"- Aktivitätsstatus: {stats.get('status', '–')}")

    # Recent bookings: handle both dict (new) and list (legacy) format
    raw_bookings = profile.get("recent_bookings") or {}
    if isinstance(raw_bookings, dict):
        upcoming = (raw_bookings.get("upcoming") or [])[:3]
        past = (raw_bookings.get("past") or [])[:3]
    else:
        today_iso = date.today().isoformat()
        upcoming = [b for b in raw_bookings if (b.get("start") or "") >= today_iso][:3]
        past = []

    if upcoming:
        lines.append("- Nächste Termine:")
        for b in upcoming:
            start = (b.get("start") or "")[:16].replace("T", " ")
            lines.append(f"  • {start} – {b.get('title', '?')}")
    if past:
        lines.append("- Letzte abgeschlossene Termine:")
        for b in past:
            start = (b.get("start") or "")[:10]
            lines.append(f"  • {start} – {b.get('title', '?')}")

    return "\n".join(lines)


class AgentOps(BaseAgent):
    """Scheduling and booking agent – LLM-powered with Magicline Tools."""

    @property
    def name(self) -> str:
        return "ops"

    @property
    def description(self) -> str:
        return "Scheduling & Booking Agent – Kurs buchen, Termine planen, Check-in"

    async def handle(self, message: InboundMessage) -> AgentResponse:
        """Process booking-related messages via GPT-4o-mini with Tool Loop."""
        from app.prompts.engine import get_engine
        from app.integrations.magicline.member_enrichment import enrich_member, get_member_profile

        # Load Skill Content
        skill_content = _load_magicline_skill_prompt()

        # Resolve session → real user_name + member_id
        session = persistence.get_session_by_user_id(message.user_id, tenant_id=message.tenant_id)
        user_name = (session and session.user_name) or message.user_id
        member_id = (session and session.member_id) or "Unknown"
        session_id = (session and hasattr(session, "session_id") and session.session_id) or str(message.message_id)

        # Build member profile context for prompt
        member_profile_block = ""
        if session and session.member_id:
            try:
                # Resolve numeric customer_id from member_id (may be member_number or customer_id string)
                from app.core.db import SessionLocal
                from app.core.models import StudioMember
                db = SessionLocal()
                try:
                    mid = session.member_id.strip()
                    row = (
                        db.query(StudioMember)
                        .filter(
                            (StudioMember.member_number == mid) |
                            (StudioMember.customer_id == int(mid) if mid.isdigit() else False)
                        )
                        .filter(StudioMember.tenant_id == message.tenant_id)
                        .first()
                    )
                    if row:
                        # Trigger enrichment (cached, non-blocking if fresh)
                        enrich_member(row.customer_id, force=False, tenant_id=message.tenant_id)
                        profile = get_member_profile(row.customer_id, tenant_id=message.tenant_id)
                        if profile:
                            member_profile_block = _build_profile_block(profile)
                finally:
                    db.close()
            except Exception as e:
                logger.warning("agent.ops.member_profile_failed", error=str(e))

        engine = get_engine()
        context = {
            "skill_content": skill_content,
            "current_date": date.today().isoformat(),
            "user_name": user_name,
            "member_id": member_id,
            "session_id": session_id,
            "member_profile": member_profile_block,
        }
        tenant_slug = persistence.get_tenant_slug(message.tenant_id)
        tenant_prompt_path = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "knowledge"
            / "tenants"
            / tenant_slug
            / "prompts"
            / "ops-system.j2"
        )
        if tenant_prompt_path.exists():
            try:
                tenant_prompt_raw = tenant_prompt_path.read_text(encoding="utf-8")
                ops_system_prompt = engine.env.from_string(tenant_prompt_raw).render(**context)
            except Exception as e:
                logger.warning("agent.ops.tenant_prompt_render_failed", error=str(e), tenant=tenant_slug)
                ops_system_prompt = engine.render("ops/system.j2", **context)
        else:
            ops_system_prompt = engine.render("ops/system.j2", **context)

        logger.info("agent.ops.handle", message_id=message.message_id)

        # 1. First Pass: Ask LLM (it might decide to use a TOOL)
        response_1 = await self._chat(
            ops_system_prompt,
            message.content,
            user_id=message.user_id,
            tenant_id=message.tenant_id,
        )
        if not response_1:
            return self._fallback_response()

        # 2. Check for TOOL usage
        tool_call = self._extract_tool_call(response_1)
        if tool_call:
            tool_name, args_str = tool_call
            logger.info("agent.ops.tool_use", tool=tool_name, args=args_str)

            # Execute tool
            tool_result = self._execute_tool(tool_name, args_str, message.user_id, message.tenant_id)
            
            # 3. Second Pass: Feed result back and get final answer
            # We append the tool result to the conversation context
            final_prompt = (
                f"{ops_system_prompt}\n\n"
                f"SYSTEM TOOL OUTPUT:\n{tool_result}\n\n"
                "Antworte dem User jetzt basierend auf diesen Daten. Sei hilfreich und präzise."
            )
            response_2 = await self._chat(
                final_prompt,
                message.content,
                user_id=message.user_id,
                tenant_id=message.tenant_id,
            )
            
            cancel_kw = ["stornieren", "absagen", "cancel", "löschen"]
            req_conf = any(kw in message.content.lower() for kw in cancel_kw) and "bestätig" in (response_2 or "").lower()
            return AgentResponse(content=response_2 or "Entschuldige, ich konnte die Daten nicht verarbeiten.", confidence=0.95, requires_confirmation=req_conf)

        # Safety: never expose raw TOOL commands to users.
        if "TOOL:" in response_1:
            logger.warning("agent.ops.unparsed_tool_response", response=response_1)
            return AgentResponse(
                content="Ich habe den Terminbefehl erkannt, aber die Ausführung war unklar. Sag kurz: 'Welche Termine habe ich heute?'",
                confidence=0.6,
            )

        # No tool used, return direct response
        cancel_kw = ["stornieren", "absagen", "cancel", "löschen"]
        req_conf = any(kw in message.content.lower() for kw in cancel_kw) and "bestätig" in (response_1 or "").lower()
        return AgentResponse(content=response_1, confidence=0.85, requires_confirmation=req_conf)

    def _parse_args(self, args_str: str) -> list[str]:
        if not args_str.strip():
            return []
        parsed = next(csv.reader([args_str], skipinitialspace=True), [])
        return [a.strip().strip("'").strip('"') for a in parsed]

    def _extract_tool_call(self, response: str) -> tuple[str, str] | None:
        cleaned = response.strip().strip("`")
        match = re.search(
            r"TOOL\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    def _execute_tool(self, name: str, args_str: str, user_id: str, tenant_id: int | None = None) -> str:
        """Execute the requested tool safely."""
        try:
            args = self._parse_args(args_str)
            
            if name == "get_class_schedule":
                # Default to today if date parsing fails or empty
                d = args[0] if args else date.today().isoformat()
                return magicline.get_class_schedule(d)
                
            elif name == "get_appointment_slots":
                cat = args[0] if len(args) > 0 else "all"
                days = int(args[1]) if len(args) > 1 else 3
                return magicline.get_appointment_slots(cat, days)
                
            elif name == "get_checkin_history":
                days = int(args[0]) if args else 7
                return magicline.get_checkin_history(days, user_identifier=user_id, tenant_id=tenant_id)
            
            elif name == "class_book":
                slot_id = int(args[0])
                return magicline.class_book(slot_id, user_identifier=user_id, tenant_id=tenant_id)

            elif name == "get_member_bookings":
                date_str = args[0] if args else date.today().isoformat()
                query = args[1] if len(args) > 1 and args[1] else None
                return magicline.get_member_bookings(user_id, date_str, query, tenant_id=tenant_id)

            elif name == "cancel_member_booking":
                date_str = args[0] if args else date.today().isoformat()
                query = args[1] if len(args) > 1 and args[1] else None
                return magicline.cancel_member_booking(user_id, date_str, query, tenant_id=tenant_id)

            elif name == "reschedule_member_booking_to_latest":
                date_str = args[0] if args else date.today().isoformat()
                query = args[1] if len(args) > 1 and args[1] else None
                return magicline.reschedule_member_booking_to_latest(user_id, date_str, query, tenant_id=tenant_id)
                
            return f"Error: Tool '{name}' unknown."
            
        except Exception as e:
            logger.error("agent.ops.tool_exec_error", error=str(e), tool=name)
            return f"Error executing tool: {str(e)}"

    def _fallback_response(self) -> AgentResponse:
        return AgentResponse(
            content="Ich kümmere mich drum! 📅 Was brauchst du – Kurs buchen, Termin checken, oder Check-in?",
            confidence=0.7,
        )
