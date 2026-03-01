#!/usr/bin/env python3
"""ARIIA v2.0 – Backup & Recovery Manager.

Provides automated backup and recovery for:
1. PostgreSQL database (pg_dump / pg_restore)
2. ChromaDB vector database (directory snapshot)
3. Redis state (RDB snapshot trigger)

Features:
- Configurable retention policy (default: 7 daily, 4 weekly)
- Compression with gzip
- Backup verification
- Restore from any snapshot
- Scheduled via cron or manual trigger

Usage:
    python scripts/backup_manager.py backup --all
    python scripts/backup_manager.py backup --postgres
    python scripts/backup_manager.py backup --chroma
    python scripts/backup_manager.py list
    python scripts/backup_manager.py restore --id <backup_id>
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import time
import structlog
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = structlog.get_logger()


# ─── Configuration ────────────────────────────────────────────────────────────

DEFAULT_BACKUP_DIR = "/data/backups"
DEFAULT_RETENTION_DAILY = 7
DEFAULT_RETENTION_WEEKLY = 4
CHROMA_DB_PATH = "data/chroma_db"
BACKUP_MANIFEST = "backup_manifest.json"


class BackupType(str, Enum):
    POSTGRES = "postgres"
    CHROMA = "chroma"
    REDIS = "redis"
    FULL = "full"


class BackupStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class BackupRecord:
    """Metadata record for a single backup."""
    backup_id: str
    backup_type: BackupType
    status: BackupStatus
    file_path: str
    size_bytes: int = 0
    created_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "size_human": self._human_size(self.size_bytes),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "metadata": self.metadata,
        }

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# ─── Backup Manager ──────────────────────────────────────────────────────────

class BackupManager:
    """Manages backup and recovery operations.

    Supports PostgreSQL, ChromaDB, and Redis backups with
    configurable retention policies and verification.
    """

    def __init__(
        self,
        backup_dir: str = DEFAULT_BACKUP_DIR,
        retention_daily: int = DEFAULT_RETENTION_DAILY,
        retention_weekly: int = DEFAULT_RETENTION_WEEKLY,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_user: str = "postgres",
        pg_password: str = "",
        pg_database: str = "ariia",
        chroma_path: str = CHROMA_DB_PATH,
        redis_host: str = "localhost",
        redis_port: int = 6379,
    ):
        self._backup_dir = backup_dir
        self._retention_daily = retention_daily
        self._retention_weekly = retention_weekly
        self._pg_host = pg_host
        self._pg_port = pg_port
        self._pg_user = pg_user
        self._pg_password = pg_password
        self._pg_database = pg_database
        self._chroma_path = chroma_path
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._manifest: list[dict] = []

        # Ensure backup directory exists
        os.makedirs(backup_dir, exist_ok=True)
        self._load_manifest()

    # ─── Manifest Management ──────────────────────────────────────────

    def _manifest_path(self) -> str:
        return os.path.join(self._backup_dir, BACKUP_MANIFEST)

    def _load_manifest(self) -> None:
        """Load the backup manifest from disk."""
        path = self._manifest_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self._manifest = json.load(f)
            except Exception:
                self._manifest = []
        else:
            self._manifest = []

    def _save_manifest(self) -> None:
        """Save the backup manifest to disk."""
        with open(self._manifest_path(), "w") as f:
            json.dump(self._manifest, f, indent=2)

    def _add_record(self, record: BackupRecord) -> None:
        """Add a backup record to the manifest."""
        self._manifest.append(record.to_dict())
        self._save_manifest()

    def _update_record(self, backup_id: str, updates: dict) -> None:
        """Update a backup record in the manifest."""
        for entry in self._manifest:
            if entry["backup_id"] == backup_id:
                entry.update(updates)
                break
        self._save_manifest()

    # ─── PostgreSQL Backup ────────────────────────────────────────────

    def backup_postgres(self) -> BackupRecord:
        """Create a compressed PostgreSQL backup using pg_dump.

        Returns:
            BackupRecord with status and file path.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"pg_{timestamp}"
        filename = f"{backup_id}.sql.gz"
        filepath = os.path.join(self._backup_dir, filename)

        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.POSTGRES,
            status=BackupStatus.RUNNING,
            file_path=filepath,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        start_time = time.time()

        try:
            env = os.environ.copy()
            env["PGPASSWORD"] = self._pg_password

            # Run pg_dump and pipe through gzip
            pg_dump_cmd = [
                "pg_dump",
                "-h", self._pg_host,
                "-p", str(self._pg_port),
                "-U", self._pg_user,
                "-d", self._pg_database,
                "--format=plain",
                "--no-owner",
                "--no-privileges",
            ]

            with open(filepath, "wb") as f:
                dump_proc = subprocess.Popen(
                    pg_dump_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
                # Compress on the fly
                with gzip.open(f, "wb") as gz:
                    while True:
                        chunk = dump_proc.stdout.read(8192)
                        if not chunk:
                            break
                        gz.write(chunk)

                dump_proc.wait()

                if dump_proc.returncode != 0:
                    stderr = dump_proc.stderr.read().decode()
                    raise RuntimeError(f"pg_dump failed: {stderr}")

            record.size_bytes = os.path.getsize(filepath)
            record.status = BackupStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_seconds = round(time.time() - start_time, 2)

            logger.info(
                "backup.postgres_completed",
                backup_id=backup_id,
                size=record.size_bytes,
                duration_s=record.duration_seconds,
            )

        except Exception as e:
            record.status = BackupStatus.FAILED
            record.error = str(e)
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_seconds = round(time.time() - start_time, 2)

            logger.error("backup.postgres_failed", error=str(e))

            # Clean up partial file
            if os.path.exists(filepath):
                os.remove(filepath)

        self._add_record(record)
        return record

    # ─── ChromaDB Backup ──────────────────────────────────────────────

    def backup_chroma(self) -> BackupRecord:
        """Create a compressed snapshot of the ChromaDB directory.

        Returns:
            BackupRecord with status and file path.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"chroma_{timestamp}"
        filename = f"{backup_id}.tar.gz"
        filepath = os.path.join(self._backup_dir, filename)

        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.CHROMA,
            status=BackupStatus.RUNNING,
            file_path=filepath,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        start_time = time.time()

        try:
            if not os.path.exists(self._chroma_path):
                raise FileNotFoundError(f"ChromaDB path not found: {self._chroma_path}")

            # Create tar.gz archive
            result = subprocess.run(
                ["tar", "-czf", filepath, "-C", os.path.dirname(self._chroma_path),
                 os.path.basename(self._chroma_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(f"tar failed: {result.stderr}")

            record.size_bytes = os.path.getsize(filepath)
            record.status = BackupStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_seconds = round(time.time() - start_time, 2)

            # Count collections for metadata
            try:
                collections = [
                    d for d in os.listdir(self._chroma_path)
                    if os.path.isdir(os.path.join(self._chroma_path, d))
                ]
                record.metadata["collections"] = len(collections)
            except Exception:
                pass

            logger.info(
                "backup.chroma_completed",
                backup_id=backup_id,
                size=record.size_bytes,
                duration_s=record.duration_seconds,
            )

        except Exception as e:
            record.status = BackupStatus.FAILED
            record.error = str(e)
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_seconds = round(time.time() - start_time, 2)

            logger.error("backup.chroma_failed", error=str(e))

            if os.path.exists(filepath):
                os.remove(filepath)

        self._add_record(record)
        return record

    # ─── Redis Backup ─────────────────────────────────────────────────

    def backup_redis(self) -> BackupRecord:
        """Trigger a Redis BGSAVE and record the snapshot.

        Returns:
            BackupRecord with status.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"redis_{timestamp}"

        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.REDIS,
            status=BackupStatus.RUNNING,
            file_path="",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        start_time = time.time()

        try:
            import redis
            r = redis.Redis(host=self._redis_host, port=self._redis_port)

            # Trigger background save
            r.bgsave()

            # Wait for save to complete (max 60s)
            for _ in range(60):
                info = r.info("persistence")
                if info.get("rdb_bgsave_in_progress", 0) == 0:
                    break
                time.sleep(1)

            # Get the RDB file path
            rdb_dir = r.config_get("dir").get("dir", "/data")
            rdb_file = r.config_get("dbfilename").get("dbfilename", "dump.rdb")
            rdb_path = os.path.join(rdb_dir, rdb_file)

            # Copy RDB to backup directory
            if os.path.exists(rdb_path):
                dest = os.path.join(self._backup_dir, f"{backup_id}.rdb")
                shutil.copy2(rdb_path, dest)
                record.file_path = dest
                record.size_bytes = os.path.getsize(dest)

            record.status = BackupStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_seconds = round(time.time() - start_time, 2)

            logger.info(
                "backup.redis_completed",
                backup_id=backup_id,
                size=record.size_bytes,
            )

        except Exception as e:
            record.status = BackupStatus.FAILED
            record.error = str(e)
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_seconds = round(time.time() - start_time, 2)

            logger.error("backup.redis_failed", error=str(e))

        self._add_record(record)
        return record

    # ─── Full Backup ──────────────────────────────────────────────────

    def backup_all(self) -> list[BackupRecord]:
        """Run all backup types.

        Returns:
            List of BackupRecords for each component.
        """
        results = []
        results.append(self.backup_postgres())
        results.append(self.backup_chroma())
        results.append(self.backup_redis())

        logger.info(
            "backup.full_completed",
            total=len(results),
            successful=sum(1 for r in results if r.status == BackupStatus.COMPLETED),
            failed=sum(1 for r in results if r.status == BackupStatus.FAILED),
        )
        return results

    # ─── Restore ──────────────────────────────────────────────────────

    def restore_postgres(self, backup_id: str) -> bool:
        """Restore PostgreSQL from a backup.

        Args:
            backup_id: The backup ID to restore from.

        Returns:
            True if restore was successful.
        """
        record = self._find_record(backup_id)
        if not record or record.get("backup_type") != "postgres":
            logger.error("backup.restore_not_found", backup_id=backup_id)
            return False

        filepath = record["file_path"]
        if not os.path.exists(filepath):
            logger.error("backup.restore_file_missing", path=filepath)
            return False

        try:
            env = os.environ.copy()
            env["PGPASSWORD"] = self._pg_password

            # Decompress and restore
            with gzip.open(filepath, "rb") as gz:
                result = subprocess.run(
                    [
                        "psql",
                        "-h", self._pg_host,
                        "-p", str(self._pg_port),
                        "-U", self._pg_user,
                        "-d", self._pg_database,
                    ],
                    input=gz.read(),
                    capture_output=True,
                    env=env,
                )

            if result.returncode != 0:
                logger.error("backup.restore_failed", stderr=result.stderr.decode())
                return False

            logger.info("backup.postgres_restored", backup_id=backup_id)
            return True

        except Exception as e:
            logger.error("backup.restore_error", error=str(e))
            return False

    def restore_chroma(self, backup_id: str, target_path: Optional[str] = None) -> bool:
        """Restore ChromaDB from a backup.

        Args:
            backup_id: The backup ID to restore from.
            target_path: Optional custom restore path.

        Returns:
            True if restore was successful.
        """
        record = self._find_record(backup_id)
        if not record or record.get("backup_type") != "chroma":
            logger.error("backup.restore_not_found", backup_id=backup_id)
            return False

        filepath = record["file_path"]
        if not os.path.exists(filepath):
            logger.error("backup.restore_file_missing", path=filepath)
            return False

        target = target_path or self._chroma_path

        try:
            # Remove existing data
            if os.path.exists(target):
                shutil.rmtree(target)

            # Extract archive
            result = subprocess.run(
                ["tar", "-xzf", filepath, "-C", os.path.dirname(target)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(f"tar extract failed: {result.stderr}")

            logger.info("backup.chroma_restored", backup_id=backup_id, path=target)
            return True

        except Exception as e:
            logger.error("backup.restore_error", error=str(e))
            return False

    # ─── Listing & Cleanup ────────────────────────────────────────────

    def list_backups(
        self,
        backup_type: Optional[BackupType] = None,
    ) -> list[dict]:
        """List all backup records, optionally filtered by type."""
        records = self._manifest
        if backup_type:
            records = [r for r in records if r.get("backup_type") == backup_type.value]
        return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)

    def cleanup_old_backups(self) -> int:
        """Remove backups exceeding the retention policy.

        Keeps:
        - Last N daily backups
        - Last M weekly backups (oldest daily of each week)

        Returns:
            Number of backups removed.
        """
        removed = 0
        now = datetime.now(timezone.utc)

        for backup_type in [BackupType.POSTGRES, BackupType.CHROMA]:
            type_records = [
                r for r in self._manifest
                if r.get("backup_type") == backup_type.value
                and r.get("status") in ("completed", "verified")
            ]

            # Sort by creation date (newest first)
            type_records.sort(key=lambda r: r.get("created_at", ""), reverse=True)

            # Keep daily retention
            keep_ids = set()
            daily_kept = 0
            for record in type_records:
                if daily_kept < self._retention_daily:
                    keep_ids.add(record["backup_id"])
                    daily_kept += 1

            # Keep weekly retention (one per week beyond daily)
            weekly_kept = 0
            seen_weeks = set()
            for record in type_records:
                if record["backup_id"] in keep_ids:
                    continue
                try:
                    created = datetime.fromisoformat(record["created_at"])
                    week_key = created.strftime("%Y-W%W")
                    if week_key not in seen_weeks and weekly_kept < self._retention_weekly:
                        keep_ids.add(record["backup_id"])
                        seen_weeks.add(week_key)
                        weekly_kept += 1
                except Exception:
                    pass

            # Remove records not in keep set
            for record in type_records:
                if record["backup_id"] not in keep_ids:
                    filepath = record.get("file_path", "")
                    if filepath and os.path.exists(filepath):
                        os.remove(filepath)
                        removed += 1
                        logger.info(
                            "backup.cleaned",
                            backup_id=record["backup_id"],
                            type=backup_type.value,
                        )

            # Update manifest
            self._manifest = [
                r for r in self._manifest
                if r.get("backup_type") != backup_type.value
                or r["backup_id"] in keep_ids
            ]

        self._save_manifest()
        logger.info("backup.cleanup_complete", removed=removed)
        return removed

    def verify_backup(self, backup_id: str) -> bool:
        """Verify a backup file's integrity.

        Args:
            backup_id: The backup ID to verify.

        Returns:
            True if the backup is valid.
        """
        record = self._find_record(backup_id)
        if not record:
            return False

        filepath = record.get("file_path", "")
        if not filepath or not os.path.exists(filepath):
            return False

        try:
            backup_type = record.get("backup_type")

            if backup_type == "postgres":
                # Verify gzip integrity
                with gzip.open(filepath, "rb") as f:
                    while f.read(8192):
                        pass

            elif backup_type == "chroma":
                # Verify tar.gz integrity
                result = subprocess.run(
                    ["tar", "-tzf", filepath],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return False

            self._update_record(backup_id, {"status": "verified"})
            logger.info("backup.verified", backup_id=backup_id)
            return True

        except Exception as e:
            logger.error("backup.verify_failed", backup_id=backup_id, error=str(e))
            return False

    def _find_record(self, backup_id: str) -> Optional[dict]:
        """Find a backup record by ID."""
        for record in self._manifest:
            if record.get("backup_id") == backup_id:
                return record
        return None

    def get_stats(self) -> dict:
        """Get backup statistics."""
        total = len(self._manifest)
        completed = sum(1 for r in self._manifest if r.get("status") in ("completed", "verified"))
        failed = sum(1 for r in self._manifest if r.get("status") == "failed")
        total_size = sum(r.get("size_bytes", 0) for r in self._manifest)

        return {
            "total_backups": total,
            "completed": completed,
            "failed": failed,
            "total_size_bytes": total_size,
            "total_size_human": BackupRecord._human_size(total_size),
            "backup_dir": self._backup_dir,
            "retention_daily": self._retention_daily,
            "retention_weekly": self._retention_weekly,
        }


# ─── Cron Script Entry Point ─────────────────────────────────────────────────

def create_backup_cron_script(backup_dir: str = DEFAULT_BACKUP_DIR) -> str:
    """Generate a cron-compatible backup script.

    Returns:
        Path to the generated script.
    """
    script_content = f"""#!/bin/bash
# ARIIA Automated Backup Script
# Generated by BackupManager
# Schedule: 0 2 * * * (daily at 2:00 AM)

set -euo pipefail

BACKUP_DIR="{backup_dir}"
LOG_FILE="$BACKUP_DIR/backup.log"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

echo "[$TIMESTAMP] Starting ARIIA backup..." >> "$LOG_FILE"

# Run the Python backup manager
cd /app
python3 -c "
from scripts.backup_manager import BackupManager
import os

manager = BackupManager(
    backup_dir='$BACKUP_DIR',
    pg_host=os.getenv('POSTGRES_HOST', 'postgres'),
    pg_port=int(os.getenv('POSTGRES_PORT', 5432)),
    pg_user=os.getenv('POSTGRES_USER', 'postgres'),
    pg_password=os.getenv('POSTGRES_PASSWORD', ''),
    pg_database=os.getenv('POSTGRES_DB', 'ariia'),
    redis_host=os.getenv('REDIS_HOST', 'redis'),
    redis_port=int(os.getenv('REDIS_PORT', 6379)),
)

# Run full backup
results = manager.backup_all()

# Cleanup old backups
removed = manager.cleanup_old_backups()

# Log results
for r in results:
    print(f'  {{r.backup_type.value}}: {{r.status.value}} ({{r.size_bytes}} bytes)')
print(f'  Cleaned up {{removed}} old backups')
"

echo "[$TIMESTAMP] Backup completed." >> "$LOG_FILE"
"""

    script_path = os.path.join(backup_dir, "run_backup.sh")
    os.makedirs(backup_dir, exist_ok=True)
    with open(script_path, "w") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)

    return script_path


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ARIIA Backup Manager")
    subparsers = parser.add_subparsers(dest="command")

    # backup command
    backup_parser = subparsers.add_parser("backup", help="Create a backup")
    backup_parser.add_argument("--all", action="store_true", help="Backup all components")
    backup_parser.add_argument("--postgres", action="store_true", help="Backup PostgreSQL")
    backup_parser.add_argument("--chroma", action="store_true", help="Backup ChromaDB")
    backup_parser.add_argument("--redis", action="store_true", help="Backup Redis")

    # list command
    subparsers.add_parser("list", help="List all backups")

    # restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("--id", required=True, help="Backup ID to restore")

    # cleanup command
    subparsers.add_parser("cleanup", help="Remove old backups")

    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verify a backup")
    verify_parser.add_argument("--id", required=True, help="Backup ID to verify")

    # stats command
    subparsers.add_parser("stats", help="Show backup statistics")

    args = parser.parse_args()

    manager = BackupManager(
        pg_host=os.getenv("POSTGRES_HOST", "postgres"),
        pg_port=int(os.getenv("POSTGRES_PORT", "5432")),
        pg_user=os.getenv("POSTGRES_USER", "postgres"),
        pg_password=os.getenv("POSTGRES_PASSWORD", ""),
        pg_database=os.getenv("POSTGRES_DB", "ariia"),
        redis_host=os.getenv("REDIS_HOST", "redis"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
    )

    if args.command == "backup":
        if args.all:
            results = manager.backup_all()
            for r in results:
                print(f"  {r.backup_type.value}: {r.status.value} ({r.size_bytes} bytes)")
        elif args.postgres:
            r = manager.backup_postgres()
            print(f"PostgreSQL: {r.status.value} ({r.size_bytes} bytes)")
        elif args.chroma:
            r = manager.backup_chroma()
            print(f"ChromaDB: {r.status.value} ({r.size_bytes} bytes)")
        elif args.redis:
            r = manager.backup_redis()
            print(f"Redis: {r.status.value} ({r.size_bytes} bytes)")

    elif args.command == "list":
        backups = manager.list_backups()
        for b in backups:
            print(f"  {b['backup_id']} | {b['backup_type']} | {b['status']} | {b.get('size_human', 'N/A')}")

    elif args.command == "restore":
        record = manager._find_record(args.id)
        if record:
            btype = record.get("backup_type")
            if btype == "postgres":
                success = manager.restore_postgres(args.id)
            elif btype == "chroma":
                success = manager.restore_chroma(args.id)
            else:
                print(f"Restore not supported for type: {btype}")
                success = False
            print(f"Restore: {'SUCCESS' if success else 'FAILED'}")
        else:
            print(f"Backup not found: {args.id}")

    elif args.command == "cleanup":
        removed = manager.cleanup_old_backups()
        print(f"Removed {removed} old backups")

    elif args.command == "verify":
        valid = manager.verify_backup(args.id)
        print(f"Verification: {'VALID' if valid else 'INVALID'}")

    elif args.command == "stats":
        stats = manager.get_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")
