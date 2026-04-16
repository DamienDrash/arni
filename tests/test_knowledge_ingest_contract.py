from __future__ import annotations

import time
from pathlib import Path

from app.core.db import SessionLocal
from app.core.models import Tenant
from app.knowledge import ingest as ingest_module


class _RecordingStore:
    instances: list["_RecordingStore"] = []

    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.documents = []
        self.metadatas = []
        self.ids = []
        self.__class__.instances.append(self)

    def upsert_documents(self, documents, metadatas, ids) -> None:
        self.documents = list(documents)
        self.metadatas = list(metadatas)
        self.ids = list(ids)


def test_ingest_tenant_knowledge_resolves_slug_via_repository(tmp_path, monkeypatch) -> None:
    unique = int(time.time() * 1000)
    tenant_slug = f"ingest-tenant-{unique}"

    db = SessionLocal()
    try:
        tenant = Tenant(slug=tenant_slug, name=f"Ingest Tenant {unique}")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        tenant_id = tenant.id
    finally:
        db.close()

    knowledge_dir = tmp_path / "knowledge"
    tenant_dir = knowledge_dir / "tenants" / tenant_slug
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    (knowledge_dir / "global.md").write_text("# Global\n\nGlobal context.", encoding="utf-8")
    (tenant_dir / "tenant.md").write_text("# Tenant\n\nTenant specific context.", encoding="utf-8")

    _RecordingStore.instances.clear()
    monkeypatch.setattr(ingest_module, "KNOWLEDGE_DIR", str(knowledge_dir))
    monkeypatch.setattr(ingest_module, "TENANT_KNOWLEDGE_DIR", str(knowledge_dir / "tenants"))
    monkeypatch.setattr(ingest_module, "KnowledgeStore", _RecordingStore)

    result = ingest_module.ingest_tenant_knowledge(tenant_id=tenant_id)

    assert result["status"] == "ok"
    assert result["collection"] == ingest_module.collection_name_for_slug(tenant_slug)
    assert result["chunks"] == 2
    store = _RecordingStore.instances[-1]
    assert {meta["type"] for meta in store.metadatas} == {"system", "tenant"}


def test_ingest_all_tenants_only_processes_active_tenants(tmp_path, monkeypatch) -> None:
    unique = int(time.time() * 1000)
    active_slug = f"active-{unique}"
    inactive_slug = f"inactive-{unique}"

    db = SessionLocal()
    try:
        active = Tenant(slug=active_slug, name="Active Tenant", is_active=True)
        inactive = Tenant(slug=inactive_slug, name="Inactive Tenant", is_active=False)
        db.add_all([active, inactive])
        db.commit()
    finally:
        db.close()

    knowledge_dir = tmp_path / "knowledge-all"
    (knowledge_dir / "tenants" / active_slug).mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "global.md").write_text("# Global\n\nGlobal context.", encoding="utf-8")
    ((knowledge_dir / "tenants" / active_slug) / "tenant.md").write_text(
        "# Active\n\nActive tenant context.",
        encoding="utf-8",
    )

    _RecordingStore.instances.clear()
    monkeypatch.setattr(ingest_module, "KNOWLEDGE_DIR", str(knowledge_dir))
    monkeypatch.setattr(ingest_module, "TENANT_KNOWLEDGE_DIR", str(knowledge_dir / "tenants"))
    monkeypatch.setattr(ingest_module, "KnowledgeStore", _RecordingStore)

    result = ingest_module.ingest_all_tenants()

    assert "system" in result
    assert active_slug in result
    assert inactive_slug not in result
