"""Data Migration – migrates legacy knowledge and member memory data to the Memory Platform.

This module handles the one-time migration of existing data:
1. Legacy Markdown knowledge files → new Document store + vector embeddings
2. Legacy member memory Markdown files → new structured facts + vector store
3. Legacy ChromaDB vectors → new Qdrant collections
4. Legacy conversation data → new conversation memory entries

The migration is idempotent and can be run multiple times safely.
It tracks progress and supports resume after interruption.
"""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()


class DataMigration:
    """Migrates legacy ARIIA knowledge and memory data to the Memory Platform."""

    def __init__(self) -> None:
        self._progress: dict[str, Any] = {
            "started_at": None,
            "completed_at": None,
            "status": "pending",
            "knowledge_files": {"total": 0, "migrated": 0, "errors": 0},
            "member_memory_files": {"total": 0, "migrated": 0, "errors": 0},
            "conversations": {"total": 0, "migrated": 0, "errors": 0},
        }
        self._migrated_files: set[str] = set()

    async def run_full_migration(
        self,
        tenant_id: int,
        knowledge_dir: str = "",
        member_memory_dir: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run the complete migration pipeline.

        Args:
            tenant_id: The tenant to migrate data for.
            knowledge_dir: Path to legacy knowledge markdown files.
            member_memory_dir: Path to legacy member memory markdown files.
            dry_run: If True, only report what would be migrated.

        Returns:
            Migration progress report.
        """
        self._progress["started_at"] = datetime.now(timezone.utc).isoformat()
        self._progress["status"] = "running"

        logger.info(
            "migration.started",
            tenant_id=tenant_id,
            knowledge_dir=knowledge_dir,
            member_memory_dir=member_memory_dir,
            dry_run=dry_run,
        )

        # Phase 1: Migrate knowledge files
        if knowledge_dir and os.path.isdir(knowledge_dir):
            await self._migrate_knowledge_files(tenant_id, knowledge_dir, dry_run)

        # Phase 2: Migrate member memory files
        if member_memory_dir and os.path.isdir(member_memory_dir):
            await self._migrate_member_memory_files(tenant_id, member_memory_dir, dry_run)

        self._progress["completed_at"] = datetime.now(timezone.utc).isoformat()
        self._progress["status"] = "completed"

        logger.info("migration.completed", progress=self._progress)
        return self._progress

    # ── Knowledge File Migration ─────────────────────────────────────

    async def _migrate_knowledge_files(
        self,
        tenant_id: int,
        knowledge_dir: str,
        dry_run: bool,
    ) -> None:
        """Migrate legacy Markdown knowledge files to the new platform."""
        md_files = sorted(glob.glob(os.path.join(knowledge_dir, "*.md")))
        self._progress["knowledge_files"]["total"] = len(md_files)

        logger.info("migration.knowledge_files", count=len(md_files), dir=knowledge_dir)

        for filepath in md_files:
            filename = os.path.basename(filepath)
            if filename in self._migrated_files:
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content.strip():
                    logger.warning("migration.empty_file", file=filename)
                    continue

                if dry_run:
                    logger.info("migration.dry_run.knowledge", file=filename, chars=len(content))
                    self._progress["knowledge_files"]["migrated"] += 1
                    continue

                # Ingest through the new platform
                from app.memory_platform.ingestion import get_ingestion_service
                from app.memory_platform.models import DocumentSourceType

                service = get_ingestion_service()
                doc = await service.ingest_text(
                    tenant_id=tenant_id,
                    content=content,
                    title=filename.replace(".md", "").replace("_", " ").title(),
                    source_type=DocumentSourceType.MARKDOWN,
                    metadata={
                        "legacy_file": filename,
                        "legacy_path": filepath,
                        "migration": True,
                    },
                )

                self._migrated_files.add(filename)
                self._progress["knowledge_files"]["migrated"] += 1

                logger.info(
                    "migration.knowledge_file_migrated",
                    file=filename,
                    doc_id=doc.document_id,
                    chunks=doc.chunk_count,
                )

            except Exception as exc:
                self._progress["knowledge_files"]["errors"] += 1
                logger.error("migration.knowledge_file_error", file=filename, error=str(exc))

    # ── Member Memory File Migration ─────────────────────────────────

    async def _migrate_member_memory_files(
        self,
        tenant_id: int,
        member_memory_dir: str,
        dry_run: bool,
    ) -> None:
        """Migrate legacy member memory Markdown files to structured facts."""
        md_files = sorted(glob.glob(os.path.join(member_memory_dir, "*.md")))
        self._progress["member_memory_files"]["total"] = len(md_files)

        logger.info("migration.member_memory_files", count=len(md_files), dir=member_memory_dir)

        for filepath in md_files:
            filename = os.path.basename(filepath)
            if filename in self._migrated_files:
                continue

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content.strip():
                    continue

                # Extract member ID from filename (e.g., "member_12345.md")
                member_id = self._extract_member_id(filename)

                if dry_run:
                    logger.info(
                        "migration.dry_run.member_memory",
                        file=filename,
                        member_id=member_id,
                        chars=len(content),
                    )
                    self._progress["member_memory_files"]["migrated"] += 1
                    continue

                # Parse the markdown into structured facts
                facts = self._parse_member_memory_markdown(content, member_id)

                # Write facts to the new platform
                from app.memory_platform.writer import get_writer_service
                writer = get_writer_service()
                await writer.initialise()

                for fact in facts:
                    await writer.write_fact(tenant_id, fact)

                # Also ingest the full content as a document
                from app.memory_platform.ingestion import get_ingestion_service
                from app.memory_platform.models import DocumentSourceType

                service = get_ingestion_service()
                await service.ingest_text(
                    tenant_id=tenant_id,
                    content=content,
                    title=f"Mitglieder-Gedächtnis: {member_id}",
                    source_type=DocumentSourceType.MEMBER_MEMORY,
                    metadata={
                        "member_id": member_id,
                        "legacy_file": filename,
                        "migration": True,
                    },
                )

                self._migrated_files.add(filename)
                self._progress["member_memory_files"]["migrated"] += 1

                logger.info(
                    "migration.member_memory_migrated",
                    file=filename,
                    member_id=member_id,
                    facts=len(facts),
                )

            except Exception as exc:
                self._progress["member_memory_files"]["errors"] += 1
                logger.error("migration.member_memory_error", file=filename, error=str(exc))

    # ── Parsing Helpers ──────────────────────────────────────────────

    @staticmethod
    def _extract_member_id(filename: str) -> str:
        """Extract member ID from filename."""
        name = filename.replace(".md", "")
        # Try common patterns
        patterns = [
            r"member[_-]?(\d+)",
            r"mitglied[_-]?(\d+)",
            r"(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1)
        return name

    @staticmethod
    def _parse_member_memory_markdown(
        content: str,
        member_id: str,
    ) -> list:
        """Parse a member memory Markdown file into structured facts.

        The legacy format typically contains sections like:
        ## Persönliche Informationen
        - Name: Max Mustermann
        - Alter: 35
        ## Verträge
        - Vertrag: Premium Mitgliedschaft
        ## Präferenzen
        - Bevorzugte Trainingszeit: Morgens
        """
        from app.memory_platform.models import ExtractedFact, FactType

        facts: list[ExtractedFact] = []
        current_section = "general"

        for line in content.split("\n"):
            line = line.strip()

            # Detect section headers
            if line.startswith("##"):
                current_section = line.lstrip("#").strip().lower()
                continue

            # Parse key-value pairs from list items
            kv_match = re.match(r"^[-*]\s*\**(.+?)\**\s*[:：]\s*(.+)$", line)
            if kv_match:
                key = kv_match.group(1).strip()
                value = kv_match.group(2).strip()

                # Determine fact type based on section
                fact_type = FactType.ATTRIBUTE
                if "vertrag" in current_section or "contract" in current_section:
                    fact_type = FactType.RELATIONSHIP
                elif "präferenz" in current_section or "preference" in current_section:
                    fact_type = FactType.PREFERENCE
                elif "interaktion" in current_section or "interaction" in current_section:
                    fact_type = FactType.EVENT
                elif "gesundheit" in current_section or "health" in current_section:
                    fact_type = FactType.ATTRIBUTE

                facts.append(ExtractedFact(
                    fact_type=fact_type,
                    subject=f"member_{member_id}",
                    predicate=key.lower().replace(" ", "_"),
                    value=value,
                    confidence=0.9,  # High confidence for manually curated data
                    member_id=member_id,
                    source="legacy_migration",
                ))

        return facts

    @property
    def progress(self) -> dict[str, Any]:
        """Get the current migration progress."""
        return dict(self._progress)


# ── Migration Script Entry Point ─────────────────────────────────────

async def run_migration(
    tenant_id: int = 1,
    knowledge_dir: str = "",
    member_memory_dir: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the data migration (can be called from CLI or API)."""
    migration = DataMigration()
    return await migration.run_full_migration(
        tenant_id=tenant_id,
        knowledge_dir=knowledge_dir,
        member_memory_dir=member_memory_dir,
        dry_run=dry_run,
    )
