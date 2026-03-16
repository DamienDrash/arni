"""ARIIA v2.0 – MinIO Object Storage Client.

Async wrapper around the synchronous minio-py library.
Sync calls are dispatched via run_in_executor to avoid blocking the event loop.

Key schema:
  raw:       {tenant_slug}/uploads/raw/{job_id}_{filename}
  processed: {tenant_slug}/uploads/processed/{job_id}_{filename}
"""
from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path
from typing import BinaryIO

import structlog
from minio import Minio
from minio.error import S3Error

from config.settings import get_settings

logger = structlog.get_logger()

# ── Module-level singleton ─────────────────────────────────────────────────────
_client: "StorageClient | None" = None


def get_storage_client() -> "StorageClient":
    """Return (or lazily create) the module-level StorageClient singleton."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = StorageClient(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


class StorageClient:
    """Async-friendly wrapper around the synchronous Minio client.

    All blocking calls are executed in the default ThreadPoolExecutor via
    ``asyncio.get_event_loop().run_in_executor(None, ...)``.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
    ) -> None:
        self._minio = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def _run(self, func, *args, **kwargs):
        """Run a blocking callable in the thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _bucket_name(self, tenant_slug: str) -> str:
        return f"ariia-{tenant_slug}"

    def _ensure_bucket(self, bucket: str) -> None:
        """Create bucket if it does not already exist (sync, called from executor)."""
        if not self._minio.bucket_exists(bucket):
            self._minio.make_bucket(bucket)
            logger.info("storage.bucket_created", bucket=bucket)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def upload_stream(
        self,
        tenant_slug: str,
        job_id: str,
        filename: str,
        data: BinaryIO,
        size: int,
        content_type: str,
    ) -> str:
        """Upload a binary stream to MinIO under the raw key schema.

        Args:
            tenant_slug: Tenant identifier used for the bucket name and key prefix.
            job_id: Unique job UUID prefix for the object name.
            filename: Original filename (included in the key).
            data: File-like object opened for reading.
            size: Total byte length of ``data``.
            content_type: MIME type of the object.

        Returns:
            The full S3 key string for the newly uploaded object.
        """
        bucket = self._bucket_name(tenant_slug)
        s3_key = f"{tenant_slug}/uploads/raw/{job_id}_{filename}"

        def _upload():
            self._ensure_bucket(bucket)
            self._minio.put_object(
                bucket,
                s3_key,
                data,
                size,
                content_type=content_type,
            )

        await self._run(_upload)
        logger.info("storage.upload_complete", bucket=bucket, key=s3_key, size=size)
        return s3_key

    async def download_to_tempfile(self, s3_key: str) -> Path:
        """Download an object to a temporary file and return the path.

        The caller is responsible for deleting the temporary file after use.

        Args:
            s3_key: Full S3 key in the form ``{tenant_slug}/uploads/{subpath}``.

        Returns:
            Path to the downloaded temporary file.
        """
        # Derive bucket from the key prefix (first path segment)
        parts = s3_key.split("/", 1)
        bucket = self._bucket_name(parts[0])

        def _download() -> Path:
            response = self._minio.get_object(bucket, s3_key)
            try:
                suffix = Path(s3_key).suffix or ".tmp"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    for chunk in response.stream(amt=65536):
                        tmp.write(chunk)
                    return Path(tmp.name)
            finally:
                response.close()
                response.release_conn()

        path = await self._run(_download)
        logger.info("storage.download_complete", key=s3_key, tmp_path=str(path))
        return path

    async def move_to_processed(self, s3_key: str) -> str:
        """Move an object from the raw/ prefix to the processed/ prefix.

        Performs a server-side copy followed by deletion of the source object.

        Args:
            s3_key: Current key (must contain ``/uploads/raw/``).

        Returns:
            The new processed key.

        Raises:
            ValueError: If the key does not contain the expected raw prefix.
        """
        if "/uploads/raw/" not in s3_key:
            raise ValueError(f"s3_key does not contain '/uploads/raw/': {s3_key!r}")

        new_key = s3_key.replace("/uploads/raw/", "/uploads/processed/", 1)
        parts = s3_key.split("/", 1)
        bucket = self._bucket_name(parts[0])

        def _move():
            from minio.commonconfig import CopySource
            self._minio.copy_object(
                bucket,
                new_key,
                CopySource(bucket, s3_key),
            )
            self._minio.remove_object(bucket, s3_key)

        await self._run(_move)
        logger.info("storage.move_to_processed", old_key=s3_key, new_key=new_key)
        return new_key

    async def delete_object(self, s3_key: str) -> None:
        """Permanently delete an object from MinIO.

        Args:
            s3_key: Full S3 key to delete.
        """
        parts = s3_key.split("/", 1)
        bucket = self._bucket_name(parts[0])

        def _delete():
            self._minio.remove_object(bucket, s3_key)

        await self._run(_delete)
        logger.info("storage.delete_complete", key=s3_key)
