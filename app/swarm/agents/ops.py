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
from app.swarm.tools import magicline, member_memory
from app.swarm.tools.knowledge_base import search_knowledge_base
from app.knowledge.ingest import collection_name_for_slug

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
        upcoming = (raw_bookings.get("upcoming") or [])[:10]
        past = (raw_bookings.get("past") or [])[:10]
    else:
        today_iso = date.today().isoformat()
        upcoming = [b for b in raw_bookings if (b.get("start") or "") >= today_iso][:10]
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

        # 1. Start Tool Loop (ReAct Pattern)
        # Load history for context (slots offered etc.)
        history_msgs = []
        try:
            raw_history = persistence.get_chat_history(str(message.user_id), limit=10, tenant_id=message.tenant_id)
            for item in raw_history:
                if item.role in {"user", "assistant"}:
                    history_msgs.append({"role": item.role, "content": item.content})
        except Exception:
            pass

        messages = [{"role": "system", "content": ops_system_prompt}]
        messages.extend(history_msgs)
        messages.append({"role": "user", "content": message.content})
        
        max_turns = 5
        previous_tool_calls = set()
        
        for turn in range(max_turns):
            response = await self._chat_with_messages(messages, tenant_id=message.tenant_id)
            
            if not response:
                return self._fallback_response()
            
            # Check for TOOL usage
            tool_call = self._extract_tool_call(response)
            if not tool_call:
                # Final answer reached
                return AgentResponse(content=response, confidence=0.9)
            
            tool_name, args_str = tool_call
            call_id = f"{tool_name}({args_str})"
            
            # Prevent infinite repetition
            if call_id in previous_tool_calls:
                logger.warning("agent.ops.loop_detected", call=call_id)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "Du wiederholst dich. Nutze die bereits erhaltenen Daten für eine finale Antwort!"})
                continue

            previous_tool_calls.add(call_id)
            logger.info("agent.ops.tool_use", tool=tool_name, args=args_str, turn=turn+1)
            
            # Execute tool
            tool_result = self._execute_tool(tool_name, args_str, message.user_id, message.tenant_id)
            
            # Add to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"OBSERVATION: {tool_result}"})

        return AgentResponse(content="Ich konnte die passende Info gerade nicht abrufen. Bitte versuche es später noch einmal.", confidence=0.5)

    def _parse_args(self, args_str: str) -> list[str]:
        if not args_str.strip():
            return []
        parsed = next(csv.reader([args_str], skipinitialspace=True), [])
        return [a.strip().strip("'").strip('"') for a in parsed]

    def _extract_tool_call(self, response: str) -> tuple[str, str] | None:
        cleaned = response.strip().strip("`").strip()
        # Look for TOOL: name(...) or just TOOL:name(...)
        match = re.search(
            r"TOOL\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            # Fallback for LLMs that just return the tool call line
            match = re.search(r"(\w+)\((.*)\)", cleaned)
            if match and match.group(1) in ("get_class_schedule", "get_appointment_slots", "get_member_bookings", "cancel_member_booking", "reschedule_member_booking_to_latest", "get_checkin_history", "class_book", "search_knowledge_base", "search_member_memory"):
                return match.group(1), match.group(2).strip()
            return None
        return match.group(1), match.group(2).strip()

    def _execute_tool(self, name: str, args_str: str, user_id: str, tenant_id: int | None = None) -> str:
        """Execute the requested tool safely."""
        try:
            args = self._parse_args(args_str)
            logger.info("agent.ops.executing", tool=name, args=args)
            
            if name == "get_class_schedule":
                # Default to today if date parsing fails or empty
                d = args[0] if args else date.today().isoformat()
                return magicline.get_class_schedule(d, tenant_id=tenant_id)
                
            elif name == "get_appointment_slots":
                cat = args[0] if len(args) > 0 else "all"
                days = int(args[1]) if len(args) > 1 else 3
                return magicline.get_appointment_slots(cat, days, tenant_id=tenant_id)
                
            elif name == "get_checkin_history":
                days = int(args[0]) if args else 7
                return magicline.get_checkin_history(days, user_identifier=user_id, tenant_id=tenant_id)
            
            elif name == "class_book":
                slot_id = int(args[0])
                return magicline.class_book(slot_id, user_identifier=user_id, tenant_id=tenant_id)

            elif name == "search_member_memory":
                q = args[0] if args else ""
                return member_memory.search_member_memory(user_id, q, tenant_id=tenant_id)

            elif name == "search_knowledge_base":
                q = args[0] if args else ""
                slug = persistence.get_tenant_slug(tenant_id)
                coll = collection_name_for_slug(slug)
                return search_knowledge_base(q, collection_name=coll)

            elif name == "get_member_bookings":
                raw_date = args[0] if args else date.today().isoformat()
                # Handle LLM sending "None" or "null" as string
                d_val = None if str(raw_date).lower() in ("none", "null", "") else raw_date
                query = args[1] if len(args) > 1 and args[1] else None
                return magicline.get_member_bookings(user_id, d_val, query, tenant_id=tenant_id)

            elif name == "book_appointment_by_time":
                # args expected from LLM: category, date, time
                if len(args) < 3:
                    return "Error: Missing arguments for booking (category, date, time needed)."
                return magicline.book_appointment_by_time(
                    user_identifier=user_id,
                    time_str=args[2],
                    date_str=args[1],
                    category=args[0],
                    tenant_id=tenant_id
                )

            elif name == "cancel_member_booking":
                # args expected: date, query
                raw_arg1 = args[0] if args else date.today().isoformat()
                raw_arg2 = args[1] if len(args) > 1 else None
                
                # Robustness: if arg1 looks like a time or search query (not YYYY-MM-DD), 
                # it's likely the query and user meant today.
                if raw_arg1 and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(raw_arg1)):
                    date_val = date.today().isoformat()
                    query_val = raw_arg1
                else:
                    date_val = raw_arg1
                    query_val = raw_arg2
                    
                return magicline.cancel_member_booking(user_id, date_val, query_val, tenant_id=tenant_id)

            elif name == "reschedule_member_booking_to_latest":
                raw_arg1 = args[0] if args else date.today().isoformat()
                raw_arg2 = args[1] if len(args) > 1 else None
                
                if raw_arg1 and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(raw_arg1)):
                    date_val = date.today().isoformat()
                    query_val = raw_arg1
                else:
                    date_val = raw_arg1
                    query_val = raw_arg2
                    
                return magicline.reschedule_member_booking_to_latest(user_id, date_val, query_val, tenant_id=tenant_id)
                
            return f"Error: Tool '{name}' unknown."
            
        except Exception as e:
            logger.error("agent.ops.tool_exec_error", error=str(e), tool=name)
            return f"Error executing tool: {str(e)}"

    def _fallback_response(self) -> AgentResponse:
        return AgentResponse(
            content="Ich kümmere mich drum! 📅 Was brauchst du – Kurs buchen, Termin checken, oder Check-in?",
            confidence=0.7,
        )
