"""ARIIA Project Titan – The Librarian.

@BACKEND: Infinite Context Layer
Summarizes old sessions into narrative episodes and stores them 
as semantic mid-term memory.
"""

import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from app.core.db import SessionLocal
from app.core.models import ChatMessage, ChatSession
from app.swarm.llm import LLMClient
from app.memory.member_memory_analyzer import _index_member_memory
from config.settings import get_settings

logger = structlog.get_logger()

LIBRARIAN_PROMPT = """
Du bist der Bibliothekar von ARIIA. Deine Aufgabe ist es, einen abgeschlossenen Chat-Verlauf 
in eine kompakte, narrative Zusammenfassung (Episode) zu verwandeln.

KONTEXT:
Mitglied: {member_id}
Chat-Verlauf:
{chat_text}

ZIEL:
Schreibe eine kurze Zusammenfassung in der 3. Person.
Beispiel: "Am 23.02. fragte das Mitglied nach Marathon-Tipps und klagte über Knieprobleme. Der Bot empfahl eine Pause."
"""

class Librarian:
    def __init__(self):
        self._llm = LLMClient(get_settings().openai_api_key)

    async def summarize_session(self, member_id: str, tenant_id: int, messages: list):
        if not messages: return
        
        chat_text = "\n".join([f"{m.role}: {m.content}" for m in messages])
        
        try:
            summary = await self._llm.chat(
                messages=[{"role": "system", "content": LIBRARIAN_PROMPT.format(member_id=member_id, chat_text=chat_text)}],
                model="gpt-4o-mini",
                temperature=0.3
            )
            
            # Store this as an episodic memory in the member's vector collection
            # We prefix it with [EPISODE] so the MasterAgent knows it's a summary
            episodic_fact = f"[EPISODE {datetime.now().strftime('%Y-%m-%d')}]: {summary}"
            await _index_member_memory(member_id, tenant_id, episodic_fact)
            
            logger.info("librarian.session_archived", member_id=member_id, tenant_id=tenant_id)
            return True
        except Exception as e:
            logger.error("librarian.archival_failed", error=str(e))
            return False

    async def run_archival_cycle(self):
        """Scans for sessions older than 24h that haven't been summarized yet."""
        db = SessionLocal()
        try:
            # Simple heuristic: last interaction > 24h ago
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            sessions = db.query(ChatSession).filter(
                ChatSession.last_message_at < cutoff,
                ChatSession.is_active == True # Still marked active but old
            ).all()
            
            for sess in sessions:
                msgs = db.query(ChatMessage).filter(ChatMessage.session_id == sess.user_id).all()
                if msgs:
                    success = await self.summarize_session(sess.member_id or sess.user_id, sess.tenant_id, msgs)
                    if success:
                        sess.is_active = False # Mark as archived
                        db.commit()
        finally:
            db.close()
