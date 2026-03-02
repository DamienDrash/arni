"""Memory Writer Service – transactional writes to graph + vector stores.

Consumes EnrichmentResults from the event bus and writes the enriched
entities, facts and relationships to both the Knowledge Graph (Neo4j)
and the Vector Store (Qdrant/ChromaDB) in a coordinated manner.

This is the ONLY service with write access to the persistent stores,
ensuring data consistency and a single point of control for all mutations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.memory_platform.config import get_config
from app.memory_platform.event_bus import get_event_bus
from app.memory_platform.models import (
    EnrichmentResult,
    ExtractedEntity,
    ExtractedFact,
    ExtractedRelationship,
    MemoryEvent,
)
from app.memory_platform.models.graph_store import get_graph_store
from app.memory_platform.models.vector_store import get_vector_store

logger = structlog.get_logger()


class MemoryWriterService:
    """Writes enriched data to the Knowledge Graph and Vector Store."""

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        self._graph = get_graph_store()
        self._vector = get_vector_store()
        self._initialised: bool = False
        self._write_count: int = 0

    async def initialise(self) -> None:
        """Initialise stores and subscribe to events."""
        if self._initialised:
            return

        await self._graph.initialise()
        await self._vector.initialise()

        # Subscribe to enrichment events
        self._event_bus.subscribe("memory.enriched", self._handle_enrichment_event)
        self._initialised = True
        logger.info("writer.service_initialised")

    async def _handle_enrichment_event(self, event: MemoryEvent) -> None:
        """Handle an incoming enrichment event."""
        if not isinstance(event, EnrichmentResult):
            return

        logger.info(
            "writer.processing",
            event_id=event.event_id,
            entities=len(event.entities),
            facts=len(event.facts),
            relationships=len(event.relationships),
        )

        now = datetime.now(timezone.utc).isoformat()

        # 1. Ensure tenant node exists
        await self._graph.upsert_node(
            label="Tenant",
            key_field="tenant_id",
            key_value=str(event.tenant_id),
            properties={"tenant_id": event.tenant_id, "updated_at": now},
        )

        # 2. Write entities to graph
        entity_ids: dict[str, str] = {}
        for entity in event.entities:
            await self._graph.upsert_node(
                label="Entity",
                key_field="entity_id",
                key_value=entity.entity_id,
                properties={
                    "entity_id": entity.entity_id,
                    "tenant_id": event.tenant_id,
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "confidence": entity.confidence,
                    "updated_at": now,
                    **{k: str(v) for k, v in entity.attributes.items()},
                },
            )
            entity_ids[entity.name.lower()] = entity.entity_id

            # Link entity to tenant
            await self._graph.create_relationship(
                source_label="Entity",
                source_key="entity_id",
                source_value=entity.entity_id,
                target_label="Tenant",
                target_key="tenant_id",
                target_value=str(event.tenant_id),
                rel_type="BELONGS_TO",
            )

        # 3. Write facts to graph and vector store
        fact_texts: list[str] = []
        fact_ids: list[str] = []
        fact_metadatas: list[dict[str, Any]] = []

        for fact in event.facts:
            # Write fact to graph
            await self._graph.upsert_node(
                label="Fact",
                key_field="fact_id",
                key_value=fact.fact_id,
                properties={
                    "fact_id": fact.fact_id,
                    "tenant_id": event.tenant_id,
                    "fact_type": fact.fact_type.value,
                    "subject": fact.subject,
                    "predicate": fact.predicate,
                    "value": fact.value,
                    "confidence": fact.confidence,
                    "member_id": fact.member_id or "",
                    "source_chunk_id": fact.source_chunk_id,
                    "created_at": now,
                    "updated_at": now,
                    "access_count": 0,
                    "decay_score": 1.0,
                },
            )

            # Link fact to tenant
            await self._graph.create_relationship(
                source_label="Fact",
                source_key="fact_id",
                source_value=fact.fact_id,
                target_label="Tenant",
                target_key="tenant_id",
                target_value=str(event.tenant_id),
                rel_type="BELONGS_TO",
            )

            # Link fact to member if applicable
            if fact.member_id:
                await self._graph.upsert_node(
                    label="Member",
                    key_field="member_id",
                    key_value=fact.member_id,
                    properties={
                        "member_id": fact.member_id,
                        "tenant_id": event.tenant_id,
                        "updated_at": now,
                    },
                )
                await self._graph.create_relationship(
                    source_label="Fact",
                    source_key="fact_id",
                    source_value=fact.fact_id,
                    target_label="Member",
                    target_key="member_id",
                    target_value=fact.member_id,
                    rel_type="APPLIES_TO",
                )

            # Prepare for vector store
            fact_text = f"{fact.subject} {fact.predicate} {fact.value}"
            fact_texts.append(fact_text)
            fact_ids.append(fact.fact_id)
            fact_metadatas.append({
                "fact_type": fact.fact_type.value,
                "subject": fact.subject,
                "predicate": fact.predicate,
                "member_id": fact.member_id or "",
                "confidence": fact.confidence,
                "tenant_id": event.tenant_id,
            })

        # Batch upsert facts to vector store
        if fact_texts:
            await self._vector.upsert(
                tenant_id=event.tenant_id,
                documents=fact_texts,
                ids=fact_ids,
                metadatas=fact_metadatas,
                namespace="facts",
            )

        # 4. Write relationships to graph
        for rel in event.relationships:
            source_id = entity_ids.get(rel.source_entity.lower())
            target_id = entity_ids.get(rel.target_entity.lower())
            if source_id and target_id:
                await self._graph.create_relationship(
                    source_label="Entity",
                    source_key="entity_id",
                    source_value=source_id,
                    target_label="Entity",
                    target_key="entity_id",
                    target_value=target_id,
                    rel_type=rel.relationship_type.upper().replace(" ", "_"),
                    properties={
                        "confidence": rel.confidence,
                        "created_at": now,
                    },
                )

        # 5. Write knowledge chunks to vector store (from document metadata)
        document_id = event.metadata.get("document_id")
        if document_id:
            await self._graph.upsert_node(
                label="Document",
                key_field="document_id",
                key_value=document_id,
                properties={
                    "document_id": document_id,
                    "tenant_id": event.tenant_id,
                    "source_type": event.metadata.get("source_type", ""),
                    "updated_at": now,
                },
            )

        self._write_count += 1

        # Publish completion event
        from app.memory_platform.models import MemoryEvent as ME
        completion_event = ME(
            event_type="memory.written",
            tenant_id=event.tenant_id,
            metadata={
                "source_event_id": event.event_id,
                "entities_written": len(event.entities),
                "facts_written": len(event.facts),
                "relationships_written": len(event.relationships),
            },
        )
        await self._event_bus.publish(completion_event)

        logger.info(
            "writer.completed",
            event_id=event.event_id,
            entities=len(event.entities),
            facts=len(event.facts),
            relationships=len(event.relationships),
        )

    # ── Direct Write API ─────────────────────────────────────────────

    async def write_fact(
        self,
        tenant_id: int,
        fact: ExtractedFact,
    ) -> bool:
        """Write a single fact directly (for API use)."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            await self._graph.upsert_node(
                label="Fact",
                key_field="fact_id",
                key_value=fact.fact_id,
                properties={
                    "fact_id": fact.fact_id,
                    "tenant_id": tenant_id,
                    "fact_type": fact.fact_type.value,
                    "subject": fact.subject,
                    "predicate": fact.predicate,
                    "value": fact.value,
                    "confidence": fact.confidence,
                    "member_id": fact.member_id or "",
                    "created_at": now,
                    "updated_at": now,
                    "access_count": 0,
                    "decay_score": 1.0,
                },
            )

            fact_text = f"{fact.subject} {fact.predicate} {fact.value}"
            await self._vector.upsert(
                tenant_id=tenant_id,
                documents=[fact_text],
                ids=[fact.fact_id],
                metadatas=[{
                    "fact_type": fact.fact_type.value,
                    "subject": fact.subject,
                    "member_id": fact.member_id or "",
                }],
                namespace="facts",
            )
            return True
        except Exception as exc:
            logger.error("writer.write_fact_error", error=str(exc))
            return False

    async def delete_member_data(self, tenant_id: int, member_id: str) -> int:
        """Delete all data for a member (GDPR right to be forgotten)."""
        deleted = 0
        try:
            # Get all facts for this member
            facts = await self._graph.get_member_facts(tenant_id, member_id)
            fact_ids = [f.get("fact_id", "") for f in facts if f.get("fact_id")]

            # Delete from vector store
            if fact_ids:
                await self._vector.delete(tenant_id, fact_ids, namespace="facts")

            # Delete fact nodes from graph
            for fact_id in fact_ids:
                await self._graph.delete_node("Fact", "fact_id", fact_id)
                deleted += 1

            # Delete member node
            await self._graph.delete_node("Member", "member_id", member_id)

            logger.info(
                "writer.member_data_deleted",
                tenant_id=tenant_id,
                member_id=member_id,
                facts_deleted=deleted,
            )
        except Exception as exc:
            logger.error("writer.delete_member_error", error=str(exc))

        return deleted

    @property
    def write_count(self) -> int:
        return self._write_count


# ── Singleton ────────────────────────────────────────────────────────

_service: MemoryWriterService | None = None


def get_writer_service() -> MemoryWriterService:
    """Return the singleton writer service."""
    global _service
    if _service is None:
        _service = MemoryWriterService()
    return _service
