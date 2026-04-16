from app.core.models import IngestionJob, IngestionJobStatus
from app.domains.knowledge.models import IngestionJob as DomainIngestionJob, IngestionJobStatus as DomainIngestionJobStatus


def test_core_models_reexports_knowledge_domain_models() -> None:
    assert IngestionJob is DomainIngestionJob
    assert IngestionJobStatus is DomainIngestionJobStatus


def test_knowledge_models_keep_legacy_contract() -> None:
    assert IngestionJob.__tablename__ == "ingestion_jobs"
    assert IngestionJobStatus.PENDING.value == "pending"
