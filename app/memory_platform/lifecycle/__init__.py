"""
Memory Lifecycle Management – Decay, Konsolidierung, Archivierung.

Verwaltet den Lebenszyklus von Fakten und Erinnerungen:
- Decay Scoring: Zeitbasierter Verfall von Fakten
- Konsolidierung: Zusammenführung redundanter Fakten
- Archivierung: Verschiebung alter Fakten in Cold Storage
- Reactivation: Wiederbelebung archivierter Fakten bei Relevanz
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── Decay-Funktionen ──────────────────────────────────────────────────

def exponential_decay(
    initial_score: float,
    hours_since_update: float,
    half_life_hours: float = 720.0,  # 30 Tage Standard
    min_score: float = 0.05,
) -> float:
    """
    Berechnet den Decay-Score mit exponentieller Abklingfunktion.
    
    Args:
        initial_score: Ursprünglicher Konfidenz-Score (0.0 - 1.0)
        hours_since_update: Stunden seit letzter Aktualisierung
        half_life_hours: Halbwertszeit in Stunden (Standard: 30 Tage)
        min_score: Minimaler Score, unter den nicht gefallen wird
    
    Returns:
        Aktueller Decay-Score
    """
    if hours_since_update <= 0:
        return initial_score
    
    decay_factor = math.pow(0.5, hours_since_update / half_life_hours)
    score = initial_score * decay_factor
    return max(score, min_score)


def reinforcement_boost(
    current_score: float,
    access_count: int,
    boost_factor: float = 0.1,
    max_score: float = 1.0,
) -> float:
    """
    Erhöht den Score bei wiederholtem Zugriff (Reinforcement).
    
    Args:
        current_score: Aktueller Score
        access_count: Anzahl der Zugriffe seit letztem Decay
        boost_factor: Boost pro Zugriff
        max_score: Maximaler Score
    
    Returns:
        Geboosteter Score
    """
    boosted = current_score + (boost_factor * access_count)
    return min(boosted, max_score)


# ── Fact-Type-spezifische Halbwertszeiten ─────────────────────────────

FACT_TYPE_HALF_LIVES = {
    "attribute": 4320.0,      # 180 Tage – stabile Eigenschaften
    "preference": 2160.0,     # 90 Tage – Präferenzen ändern sich
    "relationship": 8760.0,   # 365 Tage – Beziehungen sind langlebig
    "event": 720.0,           # 30 Tage – Ereignisse verlieren Relevanz
    "sentiment": 168.0,       # 7 Tage – Stimmungen sind kurzlebig
    "interaction": 336.0,     # 14 Tage – Interaktionen sind kurzlebig
    "goal": 1440.0,           # 60 Tage – Ziele sind mittelfristig
    "health": 2160.0,         # 90 Tage – Gesundheitsdaten sind stabil
    "contract": 8760.0,       # 365 Tage – Vertragsdaten sind langlebig
}


def get_half_life(fact_type: str) -> float:
    """Gibt die Halbwertszeit für einen Faktentyp zurück."""
    return FACT_TYPE_HALF_LIVES.get(fact_type, 720.0)


# ── Lifecycle Manager ─────────────────────────────────────────────────

class MemoryLifecycleManager:
    """
    Verwaltet den Lebenszyklus aller Fakten und Erinnerungen.
    """
    
    def __init__(
        self,
        db_session_factory=None,
        archive_threshold: float = 0.1,
        consolidation_similarity: float = 0.85,
        max_facts_per_contact: int = 500,
    ):
        self.db_session_factory = db_session_factory
        self.archive_threshold = archive_threshold
        self.consolidation_similarity = consolidation_similarity
        self.max_facts_per_contact = max_facts_per_contact
    
    async def run_decay_cycle(self, tenant_id: int) -> dict:
        """
        Führt einen vollständigen Decay-Zyklus für einen Mandanten durch.
        
        Returns:
            Statistiken über den Decay-Zyklus
        """
        stats = {
            "facts_processed": 0,
            "facts_decayed": 0,
            "facts_archived": 0,
            "facts_consolidated": 0,
            "errors": 0,
        }
        
        try:
            # 1. Alle aktiven Fakten laden
            facts = await self._load_active_facts(tenant_id)
            stats["facts_processed"] = len(facts)
            
            now = datetime.utcnow()
            
            for fact in facts:
                try:
                    # 2. Decay berechnen
                    hours_since = (now - fact.get("updated_at", now)).total_seconds() / 3600
                    half_life = get_half_life(fact.get("fact_type", ""))
                    
                    new_score = exponential_decay(
                        initial_score=fact.get("confidence", 1.0),
                        hours_since_update=hours_since,
                        half_life_hours=half_life,
                    )
                    
                    # 3. Reinforcement durch Zugriffe
                    access_count = fact.get("access_count_since_decay", 0)
                    if access_count > 0:
                        new_score = reinforcement_boost(new_score, access_count)
                    
                    # 4. Score aktualisieren
                    if abs(new_score - fact.get("decay_score", 1.0)) > 0.01:
                        await self._update_decay_score(fact["fact_id"], new_score)
                        stats["facts_decayed"] += 1
                    
                    # 5. Archivieren wenn unter Schwelle
                    if new_score < self.archive_threshold:
                        await self._archive_fact(fact["fact_id"])
                        stats["facts_archived"] += 1
                        
                except Exception as e:
                    logger.warning(f"Decay error for fact {fact.get('fact_id')}: {e}")
                    stats["errors"] += 1
            
            # 6. Konsolidierung durchführen
            consolidated = await self._consolidate_facts(tenant_id)
            stats["facts_consolidated"] = consolidated
            
            logger.info(
                f"Decay cycle completed for tenant {tenant_id}: "
                f"{stats['facts_processed']} processed, "
                f"{stats['facts_decayed']} decayed, "
                f"{stats['facts_archived']} archived, "
                f"{stats['facts_consolidated']} consolidated"
            )
            
        except Exception as e:
            logger.error(f"Decay cycle failed for tenant {tenant_id}: {e}")
            stats["errors"] += 1
        
        return stats
    
    async def reactivate_fact(self, fact_id: str, new_confidence: float = 0.7) -> bool:
        """
        Reaktiviert einen archivierten Fakt, z.B. wenn er in einem Gespräch
        erneut relevant wird.
        """
        try:
            await self._update_decay_score(fact_id, new_confidence)
            await self._unarchive_fact(fact_id)
            logger.info(f"Reactivated fact {fact_id} with confidence {new_confidence}")
            return True
        except Exception as e:
            logger.error(f"Failed to reactivate fact {fact_id}: {e}")
            return False
    
    async def enforce_limits(self, tenant_id: int, contact_id: str) -> int:
        """
        Stellt sicher, dass die maximale Anzahl Fakten pro Kontakt
        nicht überschritten wird. Archiviert die ältesten/niedrigsten.
        
        Returns:
            Anzahl archivierter Fakten
        """
        facts = await self._load_contact_facts(tenant_id, contact_id)
        
        if len(facts) <= self.max_facts_per_contact:
            return 0
        
        # Sortiere nach Decay-Score (niedrigste zuerst)
        facts.sort(key=lambda f: f.get("decay_score", 0))
        
        to_archive = len(facts) - self.max_facts_per_contact
        archived = 0
        
        for fact in facts[:to_archive]:
            try:
                await self._archive_fact(fact["fact_id"])
                archived += 1
            except Exception as e:
                logger.warning(f"Failed to archive fact {fact.get('fact_id')}: {e}")
        
        logger.info(f"Enforced limits for contact {contact_id}: archived {archived} facts")
        return archived
    
    # ── Private Methoden (DB-Abstraktionen) ───────────────────────────
    
    async def _load_active_facts(self, tenant_id: int) -> list:
        """Lädt alle aktiven (nicht archivierten) Fakten eines Mandanten."""
        if not self.db_session_factory:
            return []
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("""
                        SELECT fact_id, fact_type, confidence, decay_score,
                               updated_at, access_count_since_decay
                        FROM memory_facts
                        WHERE tenant_id = :tid AND archived = false
                    """),
                    {"tid": tenant_id}
                )
                rows = result.fetchall()
                return [dict(r._mapping) for r in rows]
        except Exception as e:
            logger.error(f"Failed to load facts: {e}")
            return []
    
    async def _load_contact_facts(self, tenant_id: int, contact_id: str) -> list:
        """Lädt alle Fakten eines Kontakts."""
        if not self.db_session_factory:
            return []
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("""
                        SELECT fact_id, decay_score
                        FROM memory_facts
                        WHERE tenant_id = :tid AND contact_id = :cid AND archived = false
                        ORDER BY decay_score ASC
                    """),
                    {"tid": tenant_id, "cid": contact_id}
                )
                rows = result.fetchall()
                return [dict(r._mapping) for r in rows]
        except Exception as e:
            logger.error(f"Failed to load contact facts: {e}")
            return []
    
    async def _update_decay_score(self, fact_id: str, score: float):
        """Aktualisiert den Decay-Score eines Fakts."""
        if not self.db_session_factory:
            return
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                await session.execute(
                    text("""
                        UPDATE memory_facts
                        SET decay_score = :score, access_count_since_decay = 0
                        WHERE fact_id = :fid
                    """),
                    {"score": score, "fid": fact_id}
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to update decay score: {e}")
    
    async def _archive_fact(self, fact_id: str):
        """Archiviert einen Fakt."""
        if not self.db_session_factory:
            return
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                await session.execute(
                    text("UPDATE memory_facts SET archived = true, archived_at = NOW() WHERE fact_id = :fid"),
                    {"fid": fact_id}
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to archive fact: {e}")
    
    async def _unarchive_fact(self, fact_id: str):
        """Hebt die Archivierung eines Fakts auf."""
        if not self.db_session_factory:
            return
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                await session.execute(
                    text("UPDATE memory_facts SET archived = false, archived_at = NULL WHERE fact_id = :fid"),
                    {"fid": fact_id}
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to unarchive fact: {e}")
    
    async def _consolidate_facts(self, tenant_id: int) -> int:
        """
        Konsolidiert redundante Fakten desselben Kontakts.
        Fakten mit gleichem Subjekt und Prädikat werden zusammengeführt,
        wobei der höhere Konfidenz-Score beibehalten wird.
        
        Returns:
            Anzahl konsolidierter Fakten
        """
        if not self.db_session_factory:
            return 0
        
        consolidated = 0
        try:
            async with self.db_session_factory() as session:
                from sqlalchemy import text
                # Finde Duplikate (gleicher Kontakt, Subjekt, Prädikat)
                result = await session.execute(
                    text("""
                        SELECT contact_id, subject, predicate,
                               COUNT(*) as cnt,
                               array_agg(fact_id ORDER BY confidence DESC) as fact_ids
                        FROM memory_facts
                        WHERE tenant_id = :tid AND archived = false
                        GROUP BY contact_id, subject, predicate
                        HAVING COUNT(*) > 1
                    """),
                    {"tid": tenant_id}
                )
                
                for row in result.fetchall():
                    mapping = row._mapping
                    fact_ids = mapping["fact_ids"]
                    # Behalte den ersten (höchste Konfidenz), archiviere den Rest
                    for fid in fact_ids[1:]:
                        await self._archive_fact(fid)
                        consolidated += 1
                
                await session.commit()
                
        except Exception as e:
            logger.warning(f"Consolidation error: {e}")
        
        return consolidated


# ── Reranking Service ─────────────────────────────────────────────────

class RetrievalReranker:
    """
    Reranking-Service für Retrieval-Ergebnisse.
    Kombiniert Vektor-Ähnlichkeit, Decay-Score und Kontextrelevanz.
    """
    
    def __init__(
        self,
        vector_weight: float = 0.4,
        decay_weight: float = 0.2,
        recency_weight: float = 0.2,
        type_weight: float = 0.1,
        source_weight: float = 0.1,
    ):
        self.vector_weight = vector_weight
        self.decay_weight = decay_weight
        self.recency_weight = recency_weight
        self.type_weight = type_weight
        self.source_weight = source_weight
    
    def rerank(
        self,
        results: list[dict],
        query_context: Optional[dict] = None,
    ) -> list[dict]:
        """
        Rerankt Retrieval-Ergebnisse basierend auf mehreren Signalen.
        
        Args:
            results: Liste von Retrieval-Ergebnissen mit Scores
            query_context: Optionaler Kontext (z.B. aktuelles Thema, Kontakt-ID)
        
        Returns:
            Neu sortierte Ergebnisse mit kombinierten Scores
        """
        if not results:
            return []
        
        context = query_context or {}
        now = datetime.utcnow()
        
        scored_results = []
        for result in results:
            # 1. Vektor-Ähnlichkeit (normalisiert auf 0-1)
            vector_score = min(max(result.get("similarity", 0), 0), 1)
            
            # 2. Decay-Score
            decay_score = result.get("decay_score", 1.0)
            
            # 3. Recency-Score
            updated_at = result.get("updated_at")
            if isinstance(updated_at, str):
                try:
                    updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    updated_at = None
            
            if updated_at:
                hours_ago = (now - updated_at.replace(tzinfo=None)).total_seconds() / 3600
                recency_score = math.exp(-hours_ago / 720)  # 30-Tage-Fenster
            else:
                recency_score = 0.5
            
            # 4. Type-Relevanz
            type_score = self._type_relevance(
                result.get("fact_type", ""),
                context.get("intent", ""),
            )
            
            # 5. Source-Vertrauenswürdigkeit
            source_score = self._source_trust(result.get("source", ""))
            
            # Kombinierter Score
            combined = (
                self.vector_weight * vector_score +
                self.decay_weight * decay_score +
                self.recency_weight * recency_score +
                self.type_weight * type_score +
                self.source_weight * source_score
            )
            
            result["rerank_score"] = round(combined, 4)
            result["score_breakdown"] = {
                "vector": round(vector_score, 3),
                "decay": round(decay_score, 3),
                "recency": round(recency_score, 3),
                "type": round(type_score, 3),
                "source": round(source_score, 3),
            }
            scored_results.append(result)
        
        # Sortiere nach kombiniertem Score (absteigend)
        scored_results.sort(key=lambda r: r["rerank_score"], reverse=True)
        
        return scored_results
    
    def _type_relevance(self, fact_type: str, intent: str) -> float:
        """Bewertet die Relevanz eines Faktentyps für eine Absicht."""
        relevance_map = {
            "sales": {"preference": 0.9, "contract": 0.8, "goal": 0.8, "sentiment": 0.7, "attribute": 0.5},
            "support": {"attribute": 0.9, "health": 0.8, "event": 0.7, "sentiment": 0.6, "preference": 0.5},
            "campaign": {"preference": 0.9, "attribute": 0.8, "goal": 0.7, "sentiment": 0.6, "event": 0.5},
            "general": {"attribute": 0.7, "preference": 0.7, "relationship": 0.6, "event": 0.5, "sentiment": 0.5},
        }
        
        intent_map = relevance_map.get(intent, relevance_map["general"])
        return intent_map.get(fact_type, 0.3)
    
    def _source_trust(self, source: str) -> float:
        """Bewertet die Vertrauenswürdigkeit einer Quelle."""
        trust_map = {
            "manual": 1.0,       # Manuell eingetragen = höchstes Vertrauen
            "crm": 0.9,          # CRM-Daten
            "magicline": 0.9,    # Magicline-Sync
            "notion": 0.85,      # Notion-Import
            "conversation": 0.7, # Aus Gesprächen extrahiert
            "analysis": 0.6,     # KI-Analyse
            "inferred": 0.4,     # Abgeleitet/vermutet
        }
        return trust_map.get(source, 0.5)
