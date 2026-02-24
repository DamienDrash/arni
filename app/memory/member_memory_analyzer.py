import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Final

import structlog

from app.core.db import SessionLocal
from app.core.models import ChatMessage, ChatSession, StudioMember, Tenant
from app.swarm.llm import LLMClient
from config.settings import get_settings
from app.gateway.persistence import persistence
from app.knowledge.store import KnowledgeStore
from app.knowledge.ingest import collection_name_for_slug as get_kb_coll_name

logger = structlog.get_logger()
settings = get_settings()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEGACY_MEMORY_DIR = os.path.join(BASE_DIR, "data", "knowledge", "members")
TENANT_MEMORY_ROOT = os.path.join(BASE_DIR, "data", "knowledge", "tenants")
GLOBAL_INSTRUCTIONS_PATH = os.path.join(BASE_DIR, "data", "knowledge", "member-memory-instructions.md")

def member_collection_name_for_slug(tenant_slug: str) -> str:
    """Return the ChromaDB collection name for member memory."""
    safe = re.sub(r"[^a-z0-9_-]", "_", (tenant_slug or "system").lower())
    return f"ariia_member_memory_{safe}"

async def _index_member_memory(member_id: str, tenant_id: int | None, profile_summary: str):
    """Upsert the member's analytical summary into the vector DB."""
    try:
        db = SessionLocal()
        t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        slug = t.slug if t else "system"
        db.close()
        
        collection_name = member_collection_name_for_slug(slug)
        store = KnowledgeStore(collection_name=collection_name)
        
        # We index the summary as a single document per member
        doc_id = f"member_{member_id}"
        store.upsert_documents(
            documents=[profile_summary],
            metadatas=[{"member_id": member_id, "type": "memory", "updated_at": datetime.now(timezone.utc).isoformat()}],
            ids=[doc_id]
        )
    except Exception as e:
        logger.error("member_memory.indexing_failed", member_id=member_id, error=str(e))

DEFAULT_INSTRUCTIONS: Final[str] = """# Member Memory Extraction Instructions (Gold Standard)

ZIEL:
Extrahiere langlebige, faktische und emotionale Informationen über das Mitglied. Diese Daten dienen als Langzeitgedächtnis für personalisierte Assistenz und Retention.

STRUKTUR-VORGABEN:
- Fokus auf: Trainingsziele, körperliche Einschränkungen, Präferenzen, Motivation, zeitliche Constraints.
- Motivations-Anker: Warum trainiert die Person wirklich? (z.B. "Will für Enkel fit bleiben", "Marathon-Traum").
- Sentiment-Muster: Ist die Person oft unzufrieden? Was sind die Haupt-Frustratoren (z.B. "Duschen", "Sauberkeit")?
- Sprache: Kompaktes, faktisches Deutsch.
- Kennzeichnung: Hypothesen (bei Unsicherheit) klar als solche markieren.

VERBOTE:
- Keine sensiblen PII (Passwörter, Bankdaten).
- Keine flüchtigen Smalltalk-Infos ohne Nutzwert.
- Keine Redundanz zu bereits vorhandenen Fakten.
"""


def _cron_due_utc(expr: str, now: datetime) -> bool:
    # Supports "m h * * *"
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return False
    minute, hour, dom, mon, dow = parts
    if dom != "*" or mon != "*" or dow != "*":
        return False
    try:
        return int(minute) == now.minute and int(hour) == now.hour
    except Exception:
        return False


def _tenant_slug(tenant_id: int | None) -> str:
    if tenant_id is None:
        return "system"
    db = SessionLocal()
    try:
        row = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return (row.slug if row and row.slug else "system").strip().lower()
    finally:
        db.close()


def _member_memory_dir_for_tenant(tenant_id: int | None) -> str:
    slug = _tenant_slug(tenant_id)
    safe = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in slug).strip("-_") or "system"
    if safe == "system":
        os.makedirs(LEGACY_MEMORY_DIR, exist_ok=True)
        return LEGACY_MEMORY_DIR
    path = os.path.join(TENANT_MEMORY_ROOT, safe, "members")
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        os.makedirs(LEGACY_MEMORY_DIR, exist_ok=True)
        return LEGACY_MEMORY_DIR
    return path


def _write_text_safe(path: str, content: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return
    except PermissionError:
        # If file ownership is stale, replacing the inode can still work when dir is writable.
        try:
            if os.path.exists(path):
                os.remove(path)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return
        except Exception:
            fallback_dir = os.path.join(BASE_DIR, "data", "knowledge", "members-fallback")
            os.makedirs(fallback_dir, exist_ok=True)
            fallback_path = os.path.join(fallback_dir, os.path.basename(path))
            with open(fallback_path, "w", encoding="utf-8") as f:
                f.write(content)


def _instructions_path_for_tenant(tenant_id: int | None) -> str:
    slug = _tenant_slug(tenant_id)
    safe = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "-" for ch in slug).strip("-_") or "system"
    if safe == "system":
        return GLOBAL_INSTRUCTIONS_PATH
    return os.path.join(TENANT_MEMORY_ROOT, safe, "prompts", "member-memory-instructions.md")


def _load_instructions(tenant_id: int | None) -> str:
    tenant_path = _instructions_path_for_tenant(tenant_id)
    if os.path.exists(tenant_path):
        with open(tenant_path, "r", encoding="utf-8") as f:
            return f.read()
    if os.path.exists(GLOBAL_INSTRUCTIONS_PATH):
        with open(GLOBAL_INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
            return f.read()
    try:
        os.makedirs(os.path.dirname(GLOBAL_INSTRUCTIONS_PATH), exist_ok=True)
        with open(GLOBAL_INSTRUCTIONS_PATH, "w", encoding="utf-8") as f:
            f.write(DEFAULT_INSTRUCTIONS)
    except PermissionError:
        return DEFAULT_INSTRUCTIONS
    return DEFAULT_INSTRUCTIONS


def _chat_summary_for_member(member_id: str, tenant_id: int | None, max_messages: int = 80) -> str:
    db = SessionLocal()
    try:
        q = db.query(ChatSession).filter(ChatSession.member_id == member_id)
        if tenant_id is not None:
            q = q.filter(ChatSession.tenant_id == tenant_id)
        session = q.order_by(ChatSession.last_message_at.desc()).first()
        if not session:
            return ""
        qmsg = db.query(ChatMessage).filter(ChatMessage.session_id == session.user_id)
        if tenant_id is not None:
            qmsg = qmsg.filter(ChatMessage.tenant_id == tenant_id)
        rows = qmsg.order_by(ChatMessage.timestamp.desc()).limit(max_messages).all()
        rows.reverse()
        snippets = []
        for row in rows:
            role = row.role or "unknown"
            content = (row.content or "").strip().replace("\n", " ")
            if content:
                snippets.append(f"- {role}: {content[:240]}")
        return "\n".join(snippets)
    finally:
        db.close()


def _heuristic_profile_summary(chat_summary: str, max_points: int = 8) -> str:
    lines = [line for line in chat_summary.splitlines() if line.strip()]
    user_lines = [line for line in lines if line.lower().startswith("- user:")]
    recent = user_lines[-max_points:] if user_lines else lines[-max_points:]
    if not recent:
        return "- Keine belastbaren Signale aus Chatverlauf."
    bullets = []
    for line in recent:
        text = line.split(":", 1)[1].strip() if ":" in line else line.strip()
        if text:
            bullets.append(f"- {text[:180]}")
    return "\n".join(bullets[:max_points]) if bullets else "- Keine belastbaren Signale aus Chatverlauf."


def _extract_first_json_object(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None
    # Accept plain JSON or JSON wrapped in markdown/code fences.
    fence = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not fence:
        return None
    try:
        data = json.loads(fence.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _format_llm_profile(data: dict) -> str:
    summary = (data.get("summary") or "").strip()
    goals = data.get("goals") or []
    preferences = data.get("preferences") or []
    constraints = data.get("constraints") or []
    risks = data.get("risks") or []
    motivation = (data.get("motivation") or "").strip()
    next_actions = data.get("next_actions") or []
    confidence = data.get("confidence")

    lines: list[str] = []
    if summary:
        lines.append(f"- Zusammenfassung: {summary}")
    if goals:
        lines.append(f"- Ziele: {', '.join(str(x) for x in goals[:4])}")
    if preferences:
        lines.append(f"- Präferenzen: {', '.join(str(x) for x in preferences[:4])}")
    if constraints:
        lines.append(f"- Constraints: {', '.join(str(x) for x in constraints[:4])}")
    if risks:
        lines.append(f"- Risiken/Hinweise: {', '.join(str(x) for x in risks[:4])}")
    if motivation:
        lines.append(f"- Motivation: {motivation}")
    if next_actions:
        lines.append(f"- Nächste sinnvolle Schritte: {', '.join(str(x) for x in next_actions[:4])}")
    if isinstance(confidence, (float, int)):
        lines.append(f"- Konfidenz: {float(confidence):.2f}")
    return "\n".join(lines) if lines else "- Keine belastbaren Signale aus Chatverlauf."


async def _extract_profile_with_llm_async(
    *,
    member_id: str,
    tenant_id: int | None,
    instructions: str,
    magic_summary: str,
    chat_summary: str,
) -> str | None:
    if not settings.openai_api_key:
        return None
    llm_enabled = (
        persistence.get_setting("member_memory_llm_enabled", "true", tenant_id=tenant_id) or "true"
    ).lower() == "true"
    if not llm_enabled:
        return None
    model = persistence.get_setting("member_memory_llm_model", "gpt-4o-mini", tenant_id=tenant_id) or "gpt-4o-mini"

    llm = LLMClient(openai_api_key=settings.openai_api_key)
    system = (
        "Du bist der 'Memory Analyzer' von ARIIA. Deine Aufgabe ist es, aus Chat-Verläufen und CRM-Daten "
        "langlebige, faktische Informationen über ein Mitglied zu extrahieren.\n\n"
        "FOKUS:\n"
        "- Trainingsziele (z.B. Abnehmen, Marathon-Vorbereitung)\n"
        "- Körperliche Einschränkungen/Risiken (z.B. Knieprobleme, Blutdruck)\n"
        "- Präferenzen (z.B. trainiert am liebsten morgens, mag keine Kurse)\n"
        "- Persönlichkeit (z.B. braucht viel Motivation, ist sehr sachlich)\n\n"
        "ANTWORTE AUSSCHLIESSLICH als JSON-Objekt mit diesen Feldern:\n"
        "summary (1-2 Sätze), goals (string[]), preferences (string[]), constraints (string[]), "
        "risks (string[]), motivation (string), next_actions (string[]), confidence (0..1)."
    )
    user = (
        f"Mitglied: {member_id}\n\n"
        f"Anweisung:\n{instructions.strip()}\n\n"
        f"CRM-Daten:\n{magic_summary or '- keine Daten -'}\n\n"
        f"Letzte Chats:\n{chat_summary or '- keine Chat-Historie -'}\n"
    )
    response = await llm.chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
        temperature=0.1,
        max_tokens=600,
    )
    payload = _extract_first_json_object(response)
    if not payload:
        return None
    return _format_llm_profile(payload)


def _magicline_summary(member_id: str, tenant_id: int | None) -> str:
    db = SessionLocal()
    try:
        m_id = str(member_id).strip()
        q = db.query(StudioMember).filter(StudioMember.tenant_id == tenant_id)
        
        if m_id.isdigit():
            cid = int(m_id)
            q = q.filter((StudioMember.member_number == m_id) | (StudioMember.customer_id == cid))
        else:
            q = q.filter(StudioMember.member_number == m_id)
            
        row = q.first()
        if not row:
            return ""
        
        info_lines = [
            f"- Name: {row.first_name} {row.last_name}",
            f"- E-Mail: {row.email or '-'}",
            f"- Telefon: {row.phone_number or '-'}",
            f"- Sprache: {row.preferred_language or '-'}",
            f"- Pausiert: {'ja' if row.is_paused else 'nein'}",
        ]
        
        if row.additional_info:
            try:
                extra = json.loads(row.additional_info)
                for k, v in extra.items():
                    info_lines.append(f"- {k}: {v}")
            except Exception:
                pass
                
        return "\n".join(info_lines)
    except Exception:
        return ""
    finally:
        db.close()


def analyze_member(member_id: str, tenant_id: int | None) -> None:
    memory_dir = _member_memory_dir_for_tenant(tenant_id)
    chat = _chat_summary_for_member(member_id, tenant_id)
    magic = _magicline_summary(member_id, tenant_id)
    instructions = _load_instructions(tenant_id)
    profile_summary = None
    try:
        profile_summary = asyncio.run(
            _extract_profile_with_llm_async(
                member_id=member_id,
                tenant_id=tenant_id,
                instructions=instructions,
                magic_summary=magic,
                chat_summary=chat,
            )
        )
        if profile_summary:
            # GOLD STANDARD: Index into Vector DB
            asyncio.run(_index_member_memory(member_id, tenant_id, profile_summary))
            
    except Exception as exc:
        logger.warning("member_memory.llm_extract_failed", member_id=member_id, tenant_id=tenant_id, error=str(exc))
    
    if not profile_summary:
        profile_summary = _heuristic_profile_summary(chat)
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Gold Standard Markdown Structure
    content = [
        f"# Member Memory: {member_id}",
        "",
        f"> SCOPE: Member / {member_id}",
        f"> DOMAIN: Personal Context",
        f"> LAST_ANALYZE: {now}",
        f"> VERSION: 1.4",
        "",
        "## Analytische Zusammenfassung",
        profile_summary,
        "",
        "## Magicline Kontext",
        magic or "- keine Daten -",
        "",
        "## Relevante Chat-Informationen",
        chat or "- keine Chat-Historie -",
    ]
    
    _write_text_safe(os.path.join(memory_dir, f"{member_id}.md"), "\n".join(content))


def analyze_all_members(tenant_id: int | None = None) -> dict[str, int]:
    db = SessionLocal()
    try:
        query = db.query(ChatSession.tenant_id, ChatSession.member_id).filter(ChatSession.member_id.isnot(None))
        if tenant_id is not None:
            query = query.filter(ChatSession.tenant_id == tenant_id)
        pairs = [(row.tenant_id, row.member_id) for row in query.distinct().all() if row.member_id]
    finally:
        db.close()

    ok = 0
    err = 0
    for tenant_id, member_id in pairs:
        try:
            analyze_member(str(member_id), tenant_id)
            ok += 1
        except Exception as exc:
            err += 1
            logger.error("member_memory.analyze_member_failed", tenant_id=tenant_id, member_id=member_id, error=str(exc))
    return {"total": len(pairs), "ok": ok, "err": err}


async def scheduler_loop() -> None:
    logger.info("member_memory.scheduler_started")
    last_slot = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            slot = f"{now:%Y-%m-%d %H:%M}"
            if slot != last_slot:
                last_slot = slot
                db = SessionLocal()
                tenant_ids: set[int] = set()
                try:
                    system_tid = persistence.get_system_tenant_id()
                    tenant_ids.add(system_tid)
                    rows = db.query(ChatSession.tenant_id).filter(ChatSession.tenant_id.isnot(None)).distinct().all()
                    tenant_ids.update(int(row.tenant_id) for row in rows)
                finally:
                    db.close()

                for tenant_id in tenant_ids:
                    enabled = (
                        persistence.get_setting("member_memory_cron_enabled", "true", tenant_id=tenant_id) or "true"
                    ).lower() == "true"
                    cron = persistence.get_setting("member_memory_cron", "0 2 * * *", tenant_id=tenant_id) or "0 2 * * *"
                    if not enabled or not _cron_due_utc(cron, now):
                        continue
                    result = await asyncio.to_thread(analyze_all_members, tenant_id)
                    persistence.upsert_setting("member_memory_last_run_at", now.isoformat(), tenant_id=tenant_id)
                    status = "ok" if result["err"] == 0 else f"error:{result['err']}"
                    persistence.upsert_setting("member_memory_last_run_status", status, tenant_id=tenant_id)
                    logger.info(
                        "member_memory.scheduler_run",
                        tenant_id=tenant_id,
                        **result,
                        status=status,
                    )
        except Exception as exc:
            now = datetime.now(timezone.utc).isoformat()
            system_tid = persistence.get_system_tenant_id()
            persistence.upsert_setting("member_memory_last_run_at", now, tenant_id=system_tid)
            persistence.upsert_setting(
                "member_memory_last_run_status",
                f"error:{str(exc)[:120]}",
                tenant_id=system_tid,
            )
            logger.error("member_memory.scheduler_error", error=str(exc))
        await asyncio.sleep(30)
