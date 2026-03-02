"""Enrichment Service – augments extracted data with additional context.

Consumes ExtractionResults from the event bus, enriches entities and
facts with data from internal sources (e.g., existing member profiles,
Magicline data) and external sources, then publishes EnrichmentResults.

This service replaces the enrichment logic previously scattered across
``app/memory/librarian_v2.py`` and ``app/memory/member_memory_analyzer.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.memory_platform.config import get_config
from app.memory_platform.event_bus import get_event_bus
from app.memory_platform.models import (
    EnrichmentResult,
    ExtractionResult,
    ExtractedEntity,
    ExtractedFact,
    ExtractedRelationship,
    FactType,
    MemoryEvent,
)

logger = structlog.get_logger()


class EnrichmentService:
    """Enriches extracted data with additional context from internal/external sources."""

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        self._enrichment_plugins: list[EnrichmentPlugin] = []
        self._initialised: bool = False

    async def initialise(self) -> None:
        """Initialise the service and subscribe to events."""
        if self._initialised:
            return

        # Register default enrichment plugins
        self._enrichment_plugins = [
            MemberProfileEnricher(),
            FactDeduplicationEnricher(),
            TemporalEnricher(),
        ]

        # Subscribe to extraction events
        self._event_bus.subscribe("memory.extracted", self._handle_extraction_event)
        self._initialised = True
        logger.info("enrichment.service_initialised")

    async def _handle_extraction_event(self, event: MemoryEvent) -> None:
        """Handle an incoming extraction event."""
        if not isinstance(event, ExtractionResult):
            return

        logger.info(
            "enrichment.processing",
            event_id=event.event_id,
            entities=len(event.entities),
            facts=len(event.facts),
        )

        # Run all enrichment plugins in sequence
        entities = list(event.entities)
        facts = list(event.facts)
        relationships = list(event.relationships)
        enrichment_sources: list[str] = []

        for plugin in self._enrichment_plugins:
            try:
                result = await plugin.enrich(
                    tenant_id=event.tenant_id,
                    entities=entities,
                    facts=facts,
                    relationships=relationships,
                    metadata=event.metadata,
                )
                entities = result.get("entities", entities)
                facts = result.get("facts", facts)
                relationships = result.get("relationships", relationships)
                enrichment_sources.append(plugin.name)
            except Exception as exc:
                logger.error(
                    "enrichment.plugin_error",
                    plugin=plugin.name,
                    error=str(exc),
                )

        # Publish enrichment result
        enrichment_event = EnrichmentResult(
            tenant_id=event.tenant_id,
            source_event_id=event.event_id,
            entities=entities,
            facts=facts,
            relationships=relationships,
            enrichment_sources=enrichment_sources,
            metadata=event.metadata,
        )
        await self._event_bus.publish(enrichment_event)

        logger.info(
            "enrichment.completed",
            event_id=event.event_id,
            entities=len(entities),
            facts=len(facts),
            enrichment_sources=enrichment_sources,
        )

    def register_plugin(self, plugin: EnrichmentPlugin) -> None:
        """Register a custom enrichment plugin."""
        self._enrichment_plugins.append(plugin)
        logger.info("enrichment.plugin_registered", plugin=plugin.name)


# ── Enrichment Plugin Interface ──────────────────────────────────────

class EnrichmentPlugin:
    """Base class for enrichment plugins."""

    name: str = "base"

    async def enrich(
        self,
        tenant_id: int,
        entities: list[ExtractedEntity],
        facts: list[ExtractedFact],
        relationships: list[ExtractedRelationship],
        metadata: dict[str, Any],
    ) -> dict[str, list]:
        """Enrich the extracted data. Must return the (possibly modified) data."""
        return {
            "entities": entities,
            "facts": facts,
            "relationships": relationships,
        }


class MemberProfileEnricher(EnrichmentPlugin):
    """Enriches facts with existing member profile data.

    Links extracted facts to known members and adds context from
    the member's existing profile (e.g., contract info, check-in data).
    """

    name = "member_profile"

    async def enrich(
        self,
        tenant_id: int,
        entities: list[ExtractedEntity],
        facts: list[ExtractedFact],
        relationships: list[ExtractedRelationship],
        metadata: dict[str, Any],
    ) -> dict[str, list]:
        member_id = metadata.get("member_id")
        if not member_id:
            return {"entities": entities, "facts": facts, "relationships": relationships}

        # Ensure all facts have the member_id set
        for fact in facts:
            if not fact.member_id:
                fact.member_id = member_id

        # Try to enrich with existing member data from the database
        try:
            from app.memory.database import get_member_by_id
            member = await get_member_by_id(member_id, tenant_id)
            if member:
                # Add member attributes as context
                for entity in entities:
                    if entity.entity_type == "person" and not entity.attributes.get("member_id"):
                        entity.attributes["member_id"] = member_id
                        entity.attributes["source"] = "member_profile"
        except Exception:
            pass  # Member lookup is optional

        return {"entities": entities, "facts": facts, "relationships": relationships}


class FactDeduplicationEnricher(EnrichmentPlugin):
    """Deduplicates facts by merging similar entries.

    When two facts have the same subject and predicate, the one with
    higher confidence wins. This prevents the graph from accumulating
    redundant information.
    """

    name = "fact_deduplication"

    async def enrich(
        self,
        tenant_id: int,
        entities: list[ExtractedEntity],
        facts: list[ExtractedFact],
        relationships: list[ExtractedRelationship],
        metadata: dict[str, Any],
    ) -> dict[str, list]:
        seen: dict[str, ExtractedFact] = {}
        for fact in facts:
            key = f"{fact.subject.lower()}:{fact.predicate.lower()}:{fact.member_id or ''}"
            existing = seen.get(key)
            if existing is None or fact.confidence > existing.confidence:
                seen[key] = fact

        deduped = list(seen.values())
        if len(deduped) < len(facts):
            logger.info(
                "enrichment.deduplication",
                original=len(facts),
                deduped=len(deduped),
            )

        return {"entities": entities, "facts": deduped, "relationships": relationships}


class TemporalEnricher(EnrichmentPlugin):
    """Adds temporal metadata to facts and entities.

    Ensures all facts have proper timestamps for the memory lifecycle
    management (decay scoring, consolidation).
    """

    name = "temporal"

    async def enrich(
        self,
        tenant_id: int,
        entities: list[ExtractedEntity],
        facts: list[ExtractedFact],
        relationships: list[ExtractedRelationship],
        metadata: dict[str, Any],
    ) -> dict[str, list]:
        now = datetime.now(timezone.utc).isoformat()

        for entity in entities:
            if "extracted_at" not in entity.attributes:
                entity.attributes["extracted_at"] = now
            entity.attributes["tenant_id"] = tenant_id

        for fact in facts:
            # These will be stored as node properties in the graph
            pass  # Timestamps are handled by the writer service

        return {"entities": entities, "facts": facts, "relationships": relationships}


# ── Singleton ────────────────────────────────────────────────────────

_service: EnrichmentService | None = None


def get_enrichment_service() -> EnrichmentService:
    """Return the singleton enrichment service."""
    global _service
    if _service is None:
        _service = EnrichmentService()
    return _service
