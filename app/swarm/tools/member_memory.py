"""Tool for searching member-specific long-term memory."""

from __future__ import annotations
import re
import os
import structlog
from app.core.db import SessionLocal
from app.core.models import Tenant, StudioMember
from app.memory.member_memory_analyzer import member_collection_name_for_slug
from app.gateway.persistence import persistence

logger = structlog.get_logger()

def search_member_memory(user_identifier: str, query: str, tenant_id: int | None = None) -> str:
    """Search for specific facts about a member in their long-term memory."""
    try:
        from app.core.knowledge.retriever import HybridRetriever
        
        db_session = SessionLocal()
        slug = "system"
        t = db_session.query(Tenant).filter(Tenant.id == tenant_id).first()
        if t: slug = t.slug
        
        # 1. Resolve identifiers
        m_id = str(user_identifier).strip()
        
        from app.core.models import ChatSession
        session = db_session.query(ChatSession).filter(ChatSession.user_id == m_id, ChatSession.tenant_id == tenant_id).first()
        
        # Candidate ID from session or direct input
        candidate_id = session.member_id if session and session.member_id else m_id
        
        # Resolve to customer_id (int) if numeric
        cid_lookup = -1
        if candidate_id.isdigit() and int(candidate_id) <= 2147483647:
            cid_lookup = int(candidate_id)
            
        # GOLD STANDARD: Multi-factor identification (ID, Member Number, or Email)
        member = db_session.query(StudioMember).filter(StudioMember.tenant_id == tenant_id).filter(
            (StudioMember.customer_id == cid_lookup) |
            (StudioMember.member_number == candidate_id) |
            (StudioMember.email == candidate_id)
        ).first()
        
        if member:
            target_ids = [str(member.customer_id), str(member.member_number)]
        else:
            target_ids = [candidate_id]
            
        db_session.close()
        
        # 2. Retrieval
        collection_name = member_collection_name_for_slug(slug)
        retriever = HybridRetriever(collection_name=collection_name)
        
        # Semantic search
        results = retriever.search(f"Member {target_ids[0]}: {query}", top_n=2)
        
        output = []
        if results:
            for res in results:
                res_mid = str(res.metadata.get("member_id"))
                if res_mid in target_ids:
                    output.append(res.content)

        # 3. GOLD STANDARD FALLBACK: Read physical markdown file
        if not output:
            possible_dirs = [
                "/app/data/knowledge/members",
                "data/knowledge/members",
                "/app/data/knowledge/tenants/getimpulse-berlin/members"
            ]
            for m_dir in possible_dirs:
                for tid in target_ids:
                    f_path = os.path.join(m_dir, f"{tid}.md")
                    if os.path.exists(f_path):
                        logger.info("tool.member_memory.fallback_hit", path=f_path)
                        with open(f_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            if "## Analytische Zusammenfassung" in content:
                                try:
                                    summary = content.split("## Analytische Zusammenfassung")[1].split("##")[0].strip()
                                    output.append(summary)
                                except Exception:
                                    output.append(content[:1000])
                            else:
                                output.append(content[:1000])
                        break
                if output: break

        if not output:
            logger.warning("tool.member_memory.not_found", targets=target_ids)
            return "Keine spezifischen Langzeit-Erinnerungen gefunden."

        return "\n\n".join(output)

    except Exception as e:
        logger.error("tool.member_memory.failed", error=str(e))
        return f"Suche im Langzeitgedächtnis fehlgeschlagen: {e}"
