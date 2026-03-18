"""Media file storage utilities with path traversal protection."""
from __future__ import annotations
import uuid
import os
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Document upload support
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt"}
ALLOWED_DOCUMENT_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".txt": "text/plain",
}
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024  # 25MB


def _validate_tenant_slug(tenant_slug: str) -> None:
    """Raise ValueError if tenant_slug contains path traversal characters."""
    if not tenant_slug:
        raise ValueError("tenant_slug must not be empty")
    forbidden = ["..", "/", "\\", "\x00"]
    for char in forbidden:
        if char in tenant_slug:
            raise ValueError(f"Invalid tenant_slug: contains forbidden character '{char}'")


def _get_media_root() -> Path:
    from config.settings import get_settings
    settings = get_settings()
    if settings.media_root_path:
        return Path(settings.media_root_path)
    base = Path(__file__).resolve().parent.parent.parent
    return base / "data" / "media" / "tenants"


def get_media_path(tenant_slug: str, filename: str) -> Path:
    _validate_tenant_slug(tenant_slug)
    return _get_media_root() / tenant_slug / "images" / filename


def get_public_url(tenant_slug: str, filename: str) -> str:
    from config.settings import get_settings
    settings = get_settings()
    base = settings.media_public_base_url or settings.gateway_public_url or ""
    return f"{base}/media/tenants/{tenant_slug}/images/{filename}"


def get_document_path(tenant_slug: str, filename: str) -> Path:
    _validate_tenant_slug(tenant_slug)
    return _get_media_root() / tenant_slug / "documents" / filename


def get_document_public_url(tenant_slug: str, filename: str) -> str:
    from config.settings import get_settings
    settings = get_settings()
    base = settings.media_public_base_url or settings.gateway_public_url or ""
    return f"{base}/media/tenants/{tenant_slug}/documents/{filename}"


async def save_document_bytes(
    data: bytes,
    tenant_slug: str,
    original_filename: str,
) -> tuple[str, int, str]:
    """Save a document upload. Returns (uuid_filename, size_bytes, mime_type).

    Supports: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, TXT. Max 25 MB.
    Files are stored at data/media/tenants/{slug}/documents/ and served
    via the existing StaticFiles mount at /media/tenants/{slug}/documents/.
    """
    _validate_tenant_slug(tenant_slug)

    size = len(data)
    if size > MAX_DOCUMENT_SIZE:
        raise ValueError(f"File too large: {size} bytes (max {MAX_DOCUMENT_SIZE})")

    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError(
            f"Unsupported document type: {ext}. "
            f"Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}"
        )

    mime_type = ALLOWED_DOCUMENT_MIME_TYPES.get(ext, "application/octet-stream")
    uuid_name = f"{uuid.uuid4()}{ext}"
    dest = get_document_path(tenant_slug, uuid_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    logger.info(
        "media.document_saved",
        filename=uuid_name,
        original=original_filename,
        size=size,
        tenant_slug=tenant_slug,
    )
    return uuid_name, size, mime_type


def delete_document(tenant_slug: str, filename: str) -> bool:
    """Delete a document file from disk."""
    try:
        _validate_tenant_slug(tenant_slug)
        path = get_document_path(tenant_slug, filename)
        if path.exists():
            path.unlink()
            return True
    except Exception as e:
        logger.warning("media.document_delete_failed", error=str(e))
    return False


async def save_upload_bytes(data: bytes, tenant_slug: str, original_filename: str) -> tuple[str, int, str]:
    """Save raw bytes from upload. Returns (uuid_filename, size_bytes, mime_type)."""
    _validate_tenant_slug(tenant_slug)

    size = len(data)
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {size} bytes (max {MAX_FILE_SIZE})")

    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    # Detect MIME type
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "application/octet-stream")

    uuid_name = f"{uuid.uuid4()}{ext}"
    dest = get_media_path(tenant_slug, uuid_name)
    dest.parent.mkdir(parents=True, exist_ok=True)

    dest.write_bytes(data)
    logger.info("media.upload_saved", filename=uuid_name, size=size, tenant_slug=tenant_slug)
    return uuid_name, size, mime_type


async def save_bytes(data: bytes, tenant_slug: str, ext: str = ".png") -> tuple[str, int]:
    """Save raw bytes (AI generated). Returns (uuid_filename, size_bytes)."""
    _validate_tenant_slug(tenant_slug)
    uuid_name = f"{uuid.uuid4()}{ext}"
    dest = get_media_path(tenant_slug, uuid_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    logger.info("media.ai_image_saved", filename=uuid_name, size=len(data), tenant_slug=tenant_slug)
    return uuid_name, len(data)


def delete_file(tenant_slug: str, filename: str) -> bool:
    """Delete a file from disk. Returns True if deleted, False if not found."""
    try:
        _validate_tenant_slug(tenant_slug)
        path = get_media_path(tenant_slug, filename)
        if path.exists():
            path.unlink()
            return True
    except Exception as e:
        logger.warning("media.delete_failed", error=str(e))
    return False
