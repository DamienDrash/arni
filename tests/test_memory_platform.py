"""
Umfassende Tests für die Memory Platform.

Alle Tests sind an die tatsächlichen Modul-APIs angepasst.
"""

import asyncio
import json
import os
import tempfile
import pytest
from datetime import datetime, timedelta


# ── Event Bus Tests ───────────────────────────────────────────────────

class TestEventBus:
    """Tests für den internen Event Bus (InternalEventBus)."""

    def test_import(self):
        from app.memory_platform.event_bus import InternalEventBus
        bus = InternalEventBus()
        assert bus is not None

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        from app.memory_platform.event_bus import InternalEventBus
        from app.memory_platform.models import MemoryEvent
        bus = InternalEventBus()
        await bus.start()

        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("test.event", handler)
        event = MemoryEvent(event_type="test.event", tenant_id=1, metadata={"key": "value"})
        await bus.publish(event)

        await asyncio.sleep(0.3)
        await bus.stop()
        assert len(received) >= 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        from app.memory_platform.event_bus import InternalEventBus
        from app.memory_platform.models import MemoryEvent
        bus = InternalEventBus()
        await bus.start()

        count = {"a": 0, "b": 0}

        async def handler_a(event):
            count["a"] += 1

        async def handler_b(event):
            count["b"] += 1

        bus.subscribe("multi.event", handler_a)
        bus.subscribe("multi.event", handler_b)
        event = MemoryEvent(event_type="multi.event", tenant_id=1)
        await bus.publish(event)

        await asyncio.sleep(0.3)
        await bus.stop()
        assert count["a"] >= 1
        assert count["b"] >= 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        from app.memory_platform.event_bus import InternalEventBus
        from app.memory_platform.models import MemoryEvent
        bus = InternalEventBus()
        await bus.start()

        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("unsub.event", handler)
        bus.unsubscribe("unsub.event", handler)
        event = MemoryEvent(event_type="unsub.event", tenant_id=1)
        await bus.publish(event)

        await asyncio.sleep(0.3)
        await bus.stop()
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_no_subscribers(self):
        from app.memory_platform.event_bus import InternalEventBus
        from app.memory_platform.models import MemoryEvent
        bus = InternalEventBus()
        await bus.start()
        event = MemoryEvent(event_type="no.subscribers", tenant_id=1)
        await bus.publish(event)
        await bus.stop()

    def test_subscriber_count_dict(self):
        from app.memory_platform.event_bus import InternalEventBus
        bus = InternalEventBus()

        async def handler(event):
            pass

        bus.subscribe("count.event", handler)
        assert isinstance(bus.subscriber_count, dict)
        assert bus.subscriber_count.get("count.event", 0) >= 1


# ── Parser Registry Tests ─────────────────────────────────────────────

class TestParserRegistry:
    """Tests für die Parser Registry."""

    def test_import(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        assert registry is not None

    def test_supported_extensions(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        supported = registry.supported_extensions
        assert ".md" in supported
        assert ".txt" in supported
        assert ".pdf" in supported
        assert ".csv" in supported
        assert ".json" in supported

    @pytest.mark.asyncio
    async def test_markdown_parser(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Test\n\nDies ist ein Test-Dokument.\n\n## Abschnitt 2\n\nMehr Inhalt hier.")
            f.flush()
            result = await registry.parse(f.name)
            assert result is not None
            assert isinstance(result, list)
            assert len(result) > 0
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_text_parser(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("Einfacher Textinhalt für den Test.")
            f.flush()
            result = await registry.parse(f.name)
            assert result is not None
            assert isinstance(result, list)
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_json_parser(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"name": "Test", "data": [1, 2, 3]}, f)
            f.flush()
            result = await registry.parse(f.name)
            assert result is not None
            assert isinstance(result, list)
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_csv_parser(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
            f.write("Name,Alter,Stadt\nMax,30,Berlin\nAnna,25,München\n")
            f.flush()
            result = await registry.parse(f.name)
            assert result is not None
            assert isinstance(result, list)
            os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_html_parser(self):
        from app.memory_platform.ingestion.parsers import ParserRegistry
        registry = ParserRegistry()
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write("<html><body><h1>Titel</h1><p>Absatz mit <b>fettem</b> Text.</p></body></html>")
            f.flush()
            result = await registry.parse(f.name)
            assert result is not None
            assert isinstance(result, list)
            os.unlink(f.name)


# ── Ingestion Service Tests ───────────────────────────────────────────

class TestIngestionService:
    """Tests für den Ingestion Service."""

    def test_import(self):
        from app.memory_platform.ingestion import IngestionService
        service = IngestionService()
        assert service is not None

    def test_supported_extensions_property(self):
        from app.memory_platform.ingestion import IngestionService
        service = IngestionService()
        supported = service.supported_extensions
        assert isinstance(supported, list)
        assert ".md" in supported
        assert ".pdf" in supported

    @pytest.mark.asyncio
    async def test_ingest_text(self):
        from app.memory_platform.ingestion import IngestionService
        service = IngestionService()
        result = await service.ingest_text(
            tenant_id=1,
            content="# Wissensdokument\n\nDies ist ein Test.",
            title="Test-Dokument",
        )
        assert result is not None
        assert hasattr(result, "document_id")
        assert result.tenant_id == 1

    @pytest.mark.asyncio
    async def test_ingest_file(self):
        from app.memory_platform.ingestion import IngestionService
        service = IngestionService()
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Test-Datei\n\nInhalt für den Ingestion-Test.")
            f.flush()
            result = await service.ingest_file(
                tenant_id=1,
                file_path=f.name,
                original_filename="test.md",
            )
            assert result is not None
            assert hasattr(result, "document_id")
            os.unlink(f.name)


# ── Extraction Service Tests ──────────────────────────────────────────

class TestExtractionService:
    """Tests für den Extraction Service."""

    def test_import(self):
        from app.memory_platform.extraction import ExtractionService
        service = ExtractionService()
        assert service is not None

    @pytest.mark.asyncio
    async def test_extract_from_text(self):
        from app.memory_platform.extraction import ExtractionService
        service = ExtractionService()
        text = "Max Müller ist 35 Jahre alt und wohnt in Berlin."
        result = await service.extract_from_text(text=text, tenant_id=1, member_id="m-1")
        assert isinstance(result, dict)


# ── Enrichment Service Tests ──────────────────────────────────────────

class TestEnrichmentService:
    """Tests für den Enrichment Service."""

    def test_import(self):
        from app.memory_platform.enrichment import EnrichmentService
        service = EnrichmentService()
        assert service is not None

    def test_has_initialise(self):
        from app.memory_platform.enrichment import EnrichmentService
        service = EnrichmentService()
        assert hasattr(service, "initialise")

    def test_has_register_plugin(self):
        from app.memory_platform.enrichment import EnrichmentService
        service = EnrichmentService()
        assert hasattr(service, "register_plugin")


# ── Consent Management Tests ──────────────────────────────────────────

class TestConsentManagement:
    """Tests für das Consent Management."""

    def test_import(self):
        from app.memory_platform.consent import ConsentService
        manager = ConsentService()
        assert manager is not None

    def test_consent_status_enum(self):
        from app.memory_platform.consent import ConsentStatus
        assert ConsentStatus.GRANTED.value == "granted"
        assert ConsentStatus.DENIED.value == "denied"
        assert ConsentStatus.WITHDRAWN.value == "withdrawn"
        assert ConsentStatus.NOT_REQUESTED.value == "not_requested"

    def test_consent_service_methods(self):
        from app.memory_platform.consent import ConsentService
        manager = ConsentService()
        assert hasattr(manager, "grant_consent")
        assert hasattr(manager, "check_consent")
        assert hasattr(manager, "withdraw_consent")
        assert hasattr(manager, "get_all_consents")
        assert hasattr(manager, "get_audit_log")


# ── Lifecycle Management Tests ────────────────────────────────────────

class TestLifecycleManagement:
    """Tests für das Lifecycle Management."""

    def test_exponential_decay(self):
        from app.memory_platform.lifecycle import exponential_decay
        assert exponential_decay(1.0, 0) == 1.0
        score = exponential_decay(1.0, 720, half_life_hours=720)
        assert abs(score - 0.5) < 0.01
        score = exponential_decay(1.0, 1440, half_life_hours=720)
        assert abs(score - 0.25) < 0.01
        score = exponential_decay(1.0, 100000, half_life_hours=720, min_score=0.05)
        assert score >= 0.05

    def test_reinforcement_boost(self):
        from app.memory_platform.lifecycle import reinforcement_boost
        assert reinforcement_boost(0.5, access_count=3, boost_factor=0.1) == 0.8
        assert reinforcement_boost(0.9, access_count=5, boost_factor=0.1) == 1.0

    def test_fact_type_half_lives(self):
        from app.memory_platform.lifecycle import get_half_life
        assert get_half_life("attribute") > get_half_life("sentiment")
        assert get_half_life("relationship") >= get_half_life("attribute")
        assert get_half_life("unknown") == 720.0

    def test_lifecycle_manager_init(self):
        from app.memory_platform.lifecycle import MemoryLifecycleManager
        manager = MemoryLifecycleManager(archive_threshold=0.1, max_facts_per_contact=500)
        assert manager.archive_threshold == 0.1
        assert manager.max_facts_per_contact == 500


# ── Reranking Tests ───────────────────────────────────────────────────

class TestReranking:
    """Tests für den Reranking Service."""

    def test_import(self):
        from app.memory_platform.lifecycle import RetrievalReranker
        reranker = RetrievalReranker()
        assert reranker is not None

    def test_rerank_empty(self):
        from app.memory_platform.lifecycle import RetrievalReranker
        assert RetrievalReranker().rerank([]) == []

    def test_rerank_basic(self):
        from app.memory_platform.lifecycle import RetrievalReranker
        reranker = RetrievalReranker()
        results = [
            {"text": "A", "similarity": 0.5, "decay_score": 0.9, "fact_type": "attribute", "source": "manual"},
            {"text": "B", "similarity": 0.9, "decay_score": 0.3, "fact_type": "sentiment", "source": "analysis"},
            {"text": "C", "similarity": 0.7, "decay_score": 0.7, "fact_type": "preference", "source": "conversation"},
        ]
        reranked = reranker.rerank(results)
        assert len(reranked) == 3
        assert all("rerank_score" in r for r in reranked)
        scores = [r["rerank_score"] for r in reranked]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_with_context(self):
        from app.memory_platform.lifecycle import RetrievalReranker
        reranked = RetrievalReranker().rerank(
            [{"text": "A", "similarity": 0.6, "decay_score": 0.8, "fact_type": "contract", "source": "crm"}],
            query_context={"intent": "sales"},
        )
        assert len(reranked) == 1
        assert "rerank_score" in reranked[0]

    def test_source_trust_scores(self):
        from app.memory_platform.lifecycle import RetrievalReranker
        r = RetrievalReranker()
        assert r._source_trust("manual") > r._source_trust("analysis")
        assert r._source_trust("crm") > r._source_trust("inferred")


# ── Notion Connector Tests ────────────────────────────────────────────

class TestNotionConnector:
    """Tests für den Notion Connector."""

    def test_import(self):
        from app.memory_platform.connectors.notion import NotionConnector
        connector = NotionConnector()
        assert connector is not None

    def test_build_auth_url(self):
        from app.memory_platform.connectors.notion import NotionConnector
        connector = NotionConnector()
        url = connector.get_oauth_url(redirect_uri="http://localhost/callback", state="test_state")
        assert "api.notion.com" in url
        assert "test_state" in url

    def test_connector_properties(self):
        from app.memory_platform.connectors.notion import NotionConnector
        c = NotionConnector()
        assert hasattr(c, "connector_name")
        assert hasattr(c, "connector_type")
        assert hasattr(c, "is_connected")

    def test_connector_methods(self):
        from app.memory_platform.connectors.notion import NotionConnector
        c = NotionConnector()
        for method in ["connect", "disconnect", "sync", "incremental_sync",
                       "handle_webhook", "list_pages", "get_status"]:
            assert hasattr(c, method), f"Missing method: {method}"


# ── Data Models Tests ─────────────────────────────────────────────────

class TestDataModels:
    """Tests für die Datenmodelle."""

    def test_memory_event_model(self):
        from app.memory_platform.models import MemoryEvent
        event = MemoryEvent(event_type="document.ingested", tenant_id=1, metadata={"chunks": 5})
        assert event.event_type == "document.ingested"
        assert event.tenant_id == 1
        assert event.metadata["chunks"] == 5
        assert event.event_id is not None

    def test_knowledge_document_model(self):
        from app.memory_platform.models import KnowledgeDocument
        doc = KnowledgeDocument(
            tenant_id=1, filename="test.pdf",
            original_filename="test.pdf",
            source_type="file_upload", content_type="application/pdf",
        )
        assert doc.tenant_id == 1
        assert doc.document_id is not None

    def test_content_chunk_model(self):
        from app.memory_platform.models import ContentChunk
        chunk = ContentChunk(content="Dies ist ein Test-Chunk.", content_type="text/plain")
        assert chunk.content == "Dies ist ein Test-Chunk."
        assert chunk.chunk_id is not None

    def test_extracted_fact_model(self):
        from app.memory_platform.models import ExtractedFact
        fact = ExtractedFact(
            subject="Max Müller", predicate="wohnt_in", value="Berlin",
            confidence=0.85, fact_type="attribute",
        )
        assert fact.subject == "Max Müller"
        assert fact.confidence == 0.85

    def test_extracted_entity_model(self):
        from app.memory_platform.models import ExtractedEntity
        entity = ExtractedEntity(name="Max Müller", entity_type="person", confidence=0.9)
        assert entity.name == "Max Müller"

    def test_consent_record_model(self):
        from app.memory_platform.models import ConsentRecord
        record = ConsentRecord(
            tenant_id=1, member_id="contact-456",
            consent_type="memory_storage", status="granted",
        )
        assert record.tenant_id == 1
        assert record.status == "granted"

    def test_document_source_type_enum(self):
        from app.memory_platform.models import DocumentSourceType
        assert hasattr(DocumentSourceType, "FILE_UPLOAD")
        assert hasattr(DocumentSourceType, "MANUAL_EDITOR")

    def test_fact_type_enum(self):
        from app.memory_platform.models import FactType
        assert hasattr(FactType, "ATTRIBUTE")
        assert hasattr(FactType, "PREFERENCE")

    def test_search_query_model(self):
        from app.memory_platform.models import SearchQuery
        query = SearchQuery(query="Kraftsport Training", tenant_id=1)
        assert query.query == "Kraftsport Training"

    def test_notion_connection_model(self):
        from app.memory_platform.models import NotionConnection
        conn = NotionConnection(tenant_id=1, workspace_name="Test Workspace")
        assert conn.workspace_name == "Test Workspace"


# ── Config Tests ──────────────────────────────────────────────────────

class TestConfig:
    """Tests für die Konfiguration."""

    def test_import(self):
        from app.memory_platform.config import MemoryPlatformConfig
        assert MemoryPlatformConfig() is not None

    def test_get_config(self):
        from app.memory_platform.config import get_config
        assert get_config() is not None

    def test_has_subconfigs(self):
        from app.memory_platform.config import get_config
        config = get_config()
        for attr in ["ingestion", "extraction", "retrieval", "notion"]:
            assert hasattr(config, attr), f"Missing subconfig: {attr}"

    def test_ingestion_config(self):
        from app.memory_platform.config import IngestionConfig
        assert IngestionConfig() is not None

    def test_retrieval_config(self):
        from app.memory_platform.config import RetrievalConfig
        assert RetrievalConfig() is not None

    def test_notion_config(self):
        from app.memory_platform.config import NotionConfig
        assert NotionConfig() is not None


# ── Graph Store Tests ─────────────────────────────────────────────────

class TestGraphStore:
    def test_import(self):
        from app.memory_platform.models.graph_store import GraphStore
        assert GraphStore is not None

    def test_instantiation(self):
        from app.memory_platform.models.graph_store import GraphStore
        assert GraphStore() is not None


# ── Vector Store Tests ────────────────────────────────────────────────

class TestVectorStore:
    def test_import(self):
        from app.memory_platform.models.vector_store import VectorStore
        assert VectorStore is not None

    def test_instantiation(self):
        from app.memory_platform.models.vector_store import VectorStore
        assert VectorStore() is not None


# ── Writer Tests ──────────────────────────────────────────────────────

class TestWriter:
    def test_import(self):
        from app.memory_platform.writer import MemoryWriterService
        assert MemoryWriterService is not None

    def test_instantiation(self):
        from app.memory_platform.writer import MemoryWriterService
        assert MemoryWriterService() is not None


# ── Retrieval Service Tests ───────────────────────────────────────────

class TestRetrievalService:
    def test_import(self):
        from app.memory_platform.retrieval import RetrievalService
        assert RetrievalService is not None

    def test_instantiation(self):
        from app.memory_platform.retrieval import RetrievalService
        assert RetrievalService() is not None


# ── Prefetcher Tests ──────────────────────────────────────────────────

class TestPrefetcher:
    def test_import(self):
        from app.memory_platform.prefetcher import ContextPrefetcher
        assert ContextPrefetcher is not None

    def test_instantiation(self):
        from app.memory_platform.prefetcher import ContextPrefetcher
        assert ContextPrefetcher() is not None


# ── Migration Tests ───────────────────────────────────────────────────

class TestMigration:
    def test_import(self):
        from app.memory_platform.migration import DataMigration
        assert DataMigration is not None

    def test_instantiation(self):
        from app.memory_platform.migration import DataMigration
        assert DataMigration() is not None


# ── API Router Tests ──────────────────────────────────────────────────

class TestAPIRouter:
    def test_import(self):
        from app.memory_platform.api import router
        assert router is not None

    def test_router_has_routes(self):
        from app.memory_platform.api import router
        assert len(router.routes) > 0


# ── Integration Bridge Tests ─────────────────────────────────────────

class TestIntegrationBridge:
    def test_import(self):
        from app.memory_platform.integration import MemoryPlatformBridge
        assert MemoryPlatformBridge is not None


# ── Orchestrator Patch Tests ──────────────────────────────────────────

class TestOrchestratorPatch:
    def test_import(self):
        from app.memory_platform.integration.orchestrator_patch import apply_all_patches
        assert apply_all_patches is not None


# ── Full Integration Tests ────────────────────────────────────────────

class TestFullIntegration:
    """Integrationstests für das Zusammenspiel der Module."""

    def test_all_modules_importable(self):
        from app.memory_platform.config import MemoryPlatformConfig, get_config
        from app.memory_platform.event_bus import InternalEventBus, get_event_bus
        from app.memory_platform.models import (
            MemoryEvent, KnowledgeDocument, ContentChunk,
            ExtractedFact, ExtractedEntity, ConsentRecord,
            DocumentSourceType, FactType, SearchQuery, NotionConnection,
        )
        from app.memory_platform.ingestion import IngestionService
        from app.memory_platform.ingestion.parsers import ParserRegistry
        from app.memory_platform.extraction import ExtractionService
        from app.memory_platform.enrichment import EnrichmentService
        from app.memory_platform.writer import MemoryWriterService
        from app.memory_platform.retrieval import RetrievalService
        from app.memory_platform.consent import ConsentService
        from app.memory_platform.lifecycle import (
            MemoryLifecycleManager, RetrievalReranker,
            exponential_decay, reinforcement_boost, get_half_life,
        )
        from app.memory_platform.connectors.notion import NotionConnector
        from app.memory_platform.prefetcher import ContextPrefetcher
        from app.memory_platform.migration import DataMigration
        from app.memory_platform.api import router
        from app.memory_platform.integration import MemoryPlatformBridge
        from app.memory_platform.integration.orchestrator_patch import apply_all_patches
        from app.memory_platform.models.graph_store import GraphStore
        from app.memory_platform.models.vector_store import VectorStore
        assert True

    @pytest.mark.asyncio
    async def test_event_driven_pipeline(self):
        from app.memory_platform.event_bus import InternalEventBus
        from app.memory_platform.models import MemoryEvent
        bus = InternalEventBus()
        await bus.start()
        pipeline_log = []

        async def on_ingested(event):
            pipeline_log.append("ingested")

        async def on_extracted(event):
            pipeline_log.append("extracted")

        async def on_written(event):
            pipeline_log.append("written")

        bus.subscribe("document.ingested", on_ingested)
        bus.subscribe("facts.extracted", on_extracted)
        bus.subscribe("memory.written", on_written)

        for etype in ["document.ingested", "facts.extracted", "memory.written"]:
            await bus.publish(MemoryEvent(event_type=etype, tenant_id=1, metadata={"doc_id": "test-1"}))

        await asyncio.sleep(0.5)
        await bus.stop()
        assert len(pipeline_log) == 3

    @pytest.mark.asyncio
    async def test_ingestion_to_extraction_flow(self):
        from app.memory_platform.ingestion import IngestionService
        from app.memory_platform.extraction import ExtractionService

        doc = await IngestionService().ingest_text(
            tenant_id=1, content="Max Müller trainiert Kraftsport in Berlin.", title="Test",
        )
        assert doc is not None

        result = await ExtractionService().extract_from_text(
            text="Max Müller trainiert Kraftsport in Berlin.", tenant_id=1, member_id="m-1",
        )
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
