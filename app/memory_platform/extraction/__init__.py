"""Extraction Service – LLM-powered entity, fact and relationship extraction.

Consumes IngestionEvents from the event bus, uses an LLM to extract
structured information (entities, facts, relationships) from the raw
content chunks, and publishes ExtractionResults for downstream processing.

This service replaces the extraction logic previously embedded in
``app/memory/librarian_v2.py`` and ``app/memory/member_memory_analyzer.py``.
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

from app.memory_platform.config import get_config
from app.memory_platform.event_bus import get_event_bus
from app.memory_platform.models import (
    ContentChunk,
    ExtractionResult,
    ExtractedEntity,
    ExtractedFact,
    ExtractedRelationship,
    FactType,
    IngestionEvent,
    MemoryEvent,
)

logger = structlog.get_logger()

# ── Extraction Prompts ───────────────────────────────────────────────

KNOWLEDGE_EXTRACTION_PROMPT = """Du bist ein Experte für Informationsextraktion. Analysiere den folgenden Text und extrahiere alle relevanten Entitäten, Fakten und Beziehungen.

**Text:**
{content}

**Anweisungen:**
1. Extrahiere alle benannten Entitäten (Personen, Organisationen, Produkte, Orte, Themen).
2. Extrahiere alle atomaren Fakten als Subjekt-Prädikat-Wert-Tripel.
3. Identifiziere Beziehungen zwischen Entitäten.
4. Klassifiziere jeden Fakt in eine der Kategorien: preference, attribute, relationship, event, opinion, goal, behaviour, health, contract, demographic.
5. Bewerte die Konfidenz jeder Extraktion (0.0 bis 1.0).

**Antwortformat (JSON):**
{{
  "entities": [
    {{"name": "...", "entity_type": "person|product|topic|organisation|location", "attributes": {{}}}}
  ],
  "facts": [
    {{"fact_type": "...", "subject": "...", "predicate": "...", "value": "...", "confidence": 0.9}}
  ],
  "relationships": [
    {{"source_entity": "...", "target_entity": "...", "relationship_type": "...", "confidence": 0.8}}
  ]
}}

Antworte NUR mit validem JSON, ohne Erklärungen."""

CONVERSATION_EXTRACTION_PROMPT = """Du bist ein Experte für die Analyse von Kundengesprächen. Analysiere das folgende Gespräch und extrahiere alle relevanten Informationen über den Kunden/das Mitglied.

**Gespräch:**
{content}

**Anweisungen:**
1. Extrahiere persönliche Präferenzen, Interessen und Ziele des Kunden.
2. Identifiziere Beschwerden, Probleme oder Wünsche.
3. Erkenne Verhaltensmuster und Stimmungen.
4. Extrahiere konkrete Fakten (z.B. Vertragsinformationen, Termine, Kaufabsichten).
5. Identifiziere alle erwähnten Personen, Produkte oder Themen.
6. Bewerte die Konfidenz jeder Extraktion.

**Antwortformat (JSON):**
{{
  "entities": [
    {{"name": "...", "entity_type": "person|product|topic|organisation|location", "attributes": {{}}}}
  ],
  "facts": [
    {{"fact_type": "preference|attribute|relationship|event|opinion|goal|behaviour|health|contract|demographic", "subject": "...", "predicate": "...", "value": "...", "confidence": 0.9, "member_id": null}}
  ],
  "relationships": [
    {{"source_entity": "...", "target_entity": "...", "relationship_type": "...", "confidence": 0.8}}
  ]
}}

Antworte NUR mit validem JSON, ohne Erklärungen."""


class ExtractionService:
    """Extracts structured knowledge from raw content using LLMs."""

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        self._client: Any = None
        self._initialised: bool = False

    async def initialise(self) -> None:
        """Initialise the LLM client and subscribe to events."""
        if self._initialised:
            return

        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI()
            logger.info("extraction.llm_client_initialised")
        except Exception as exc:
            logger.warning("extraction.llm_client_failed", error=str(exc))

        # Subscribe to ingestion events
        self._event_bus.subscribe("ingestion.raw", self._handle_ingestion_event)
        self._initialised = True
        logger.info("extraction.service_initialised")

    async def _handle_ingestion_event(self, event: MemoryEvent) -> None:
        """Handle an incoming ingestion event."""
        if not isinstance(event, IngestionEvent):
            return

        logger.info(
            "extraction.processing",
            event_id=event.event_id,
            chunks=len(event.chunks),
        )

        all_entities: list[ExtractedEntity] = []
        all_facts: list[ExtractedFact] = []
        all_relationships: list[ExtractedRelationship] = []

        for chunk in event.chunks:
            try:
                result = await self._extract_from_chunk(
                    chunk=chunk,
                    is_conversation=event.content_type == "conversation",
                    member_id=event.metadata.get("member_id"),
                )
                all_entities.extend(result.get("entities", []))
                all_facts.extend(result.get("facts", []))
                all_relationships.extend(result.get("relationships", []))
            except Exception as exc:
                logger.error(
                    "extraction.chunk_error",
                    chunk_id=chunk.chunk_id,
                    error=str(exc),
                )

        # Deduplicate entities by name
        seen_entities: dict[str, ExtractedEntity] = {}
        for entity in all_entities:
            key = f"{entity.name.lower()}:{entity.entity_type}"
            if key not in seen_entities or entity.confidence > seen_entities[key].confidence:
                seen_entities[key] = entity
        deduped_entities = list(seen_entities.values())

        # Publish extraction result
        extraction_event = ExtractionResult(
            tenant_id=event.tenant_id,
            source_event_id=event.event_id,
            entities=deduped_entities,
            facts=all_facts,
            relationships=all_relationships,
            metadata={
                **event.metadata,
                "source_type": event.source_type.value if hasattr(event.source_type, 'value') else str(event.source_type),
                "chunk_count": len(event.chunks),
            },
        )
        await self._event_bus.publish(extraction_event)

        logger.info(
            "extraction.completed",
            event_id=event.event_id,
            entities=len(deduped_entities),
            facts=len(all_facts),
            relationships=len(all_relationships),
        )

    async def _extract_from_chunk(
        self,
        chunk: ContentChunk,
        is_conversation: bool = False,
        member_id: str | None = None,
    ) -> dict[str, list]:
        """Extract entities, facts and relationships from a single chunk."""
        if not chunk.content.strip():
            return {"entities": [], "facts": [], "relationships": []}

        # Skip very short chunks
        if len(chunk.content.strip()) < 20:
            return {"entities": [], "facts": [], "relationships": []}

        prompt = (
            CONVERSATION_EXTRACTION_PROMPT if is_conversation
            else KNOWLEDGE_EXTRACTION_PROMPT
        ).format(content=chunk.content[:4000])

        cfg = get_config().extraction

        if self._client is None:
            # Fallback: simple rule-based extraction
            return self._rule_based_extraction(chunk, member_id)

        try:
            response = await self._client.chat.completions.create(
                model=cfg.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                return {"entities": [], "facts": [], "relationships": []}

            data = json.loads(content)
            return self._parse_llm_response(data, chunk.chunk_id, member_id)

        except json.JSONDecodeError as exc:
            logger.warning("extraction.json_parse_error", error=str(exc))
            return {"entities": [], "facts": [], "relationships": []}
        except Exception as exc:
            logger.error("extraction.llm_error", error=str(exc))
            return self._rule_based_extraction(chunk, member_id)

    def _parse_llm_response(
        self,
        data: dict[str, Any],
        chunk_id: str,
        member_id: str | None,
    ) -> dict[str, list]:
        """Parse the LLM JSON response into typed models."""
        entities: list[ExtractedEntity] = []
        facts: list[ExtractedFact] = []
        relationships: list[ExtractedRelationship] = []

        for e in data.get("entities", []):
            try:
                entities.append(ExtractedEntity(
                    name=str(e.get("name", "")),
                    entity_type=str(e.get("entity_type", "topic")),
                    attributes=e.get("attributes", {}),
                    confidence=float(e.get("confidence", 0.7)),
                ))
            except Exception:
                continue

        for f in data.get("facts", []):
            try:
                fact_type_str = str(f.get("fact_type", "attribute")).lower()
                try:
                    fact_type = FactType(fact_type_str)
                except ValueError:
                    fact_type = FactType.ATTRIBUTE

                facts.append(ExtractedFact(
                    fact_type=fact_type,
                    subject=str(f.get("subject", "")),
                    predicate=str(f.get("predicate", "")),
                    value=str(f.get("value", "")),
                    confidence=float(f.get("confidence", 0.7)),
                    source_chunk_id=chunk_id,
                    member_id=f.get("member_id") or member_id,
                ))
            except Exception:
                continue

        for r in data.get("relationships", []):
            try:
                relationships.append(ExtractedRelationship(
                    source_entity=str(r.get("source_entity", "")),
                    target_entity=str(r.get("target_entity", "")),
                    relationship_type=str(r.get("relationship_type", "")),
                    confidence=float(r.get("confidence", 0.7)),
                ))
            except Exception:
                continue

        return {"entities": entities, "facts": facts, "relationships": relationships}

    def _rule_based_extraction(
        self,
        chunk: ContentChunk,
        member_id: str | None,
    ) -> dict[str, list]:
        """Simple rule-based fallback extraction when LLM is unavailable."""
        facts: list[ExtractedFact] = []
        content = chunk.content

        # Extract the whole chunk as a single knowledge fact
        if chunk.content_type == "table":
            facts.append(ExtractedFact(
                fact_type=FactType.ATTRIBUTE,
                subject="document",
                predicate="contains_table",
                value=content[:500],
                confidence=0.5,
                source_chunk_id=chunk.chunk_id,
                member_id=member_id,
            ))
        else:
            # Create a summary fact from the first 200 chars
            summary = content[:200].strip()
            if summary:
                facts.append(ExtractedFact(
                    fact_type=FactType.ATTRIBUTE,
                    subject="document",
                    predicate="content_summary",
                    value=summary,
                    confidence=0.3,
                    source_chunk_id=chunk.chunk_id,
                    member_id=member_id,
                ))

        return {"entities": [], "facts": facts, "relationships": []}

    # ── Direct extraction API ────────────────────────────────────────

    async def extract_from_text(
        self,
        text: str,
        tenant_id: int,
        member_id: str | None = None,
        is_conversation: bool = False,
    ) -> dict[str, list]:
        """Extract entities and facts from arbitrary text (API endpoint)."""
        chunk = ContentChunk(content=text, content_type="text")
        return await self._extract_from_chunk(chunk, is_conversation, member_id)


# ── Singleton ────────────────────────────────────────────────────────

_service: ExtractionService | None = None


def get_extraction_service() -> ExtractionService:
    """Return the singleton extraction service."""
    global _service
    if _service is None:
        _service = ExtractionService()
    return _service
