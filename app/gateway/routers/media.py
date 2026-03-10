"""Media upload and AI image generation API endpoints."""
from __future__ import annotations
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.auth import AuthContext, get_current_user
from app.core.media_models import MediaAsset

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/media", tags=["media"])


class AIImageGenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"


@router.post("/upload", status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    alt_text: Optional[str] = None,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload an image file. Supported: PNG, JPG, GIF, WebP. Max 10MB."""
    from app.media.storage import ALLOWED_EXTENSIONS, MAX_FILE_SIZE, save_upload_bytes, get_public_url
    from app.media.service import MediaService
    from app.core.models import Tenant
    from pathlib import Path

    # Get tenant slug
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Read file data first
    data = await file.read()
    size = len(data)

    # Validate before writing to disk
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: PNG, JPG, GIF, WebP")
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large: {size / 1024 / 1024:.1f}MB (max 10MB)")

    # Check storage quota BEFORE writing
    svc = MediaService(db=db, tenant_id=user.tenant_id, tenant_slug=tenant.slug)
    svc.check_storage_quota(bytes_to_add=size)

    # Save to disk
    try:
        filename, saved_size, mime_type = await save_upload_bytes(data, tenant.slug, file.filename or "upload.jpg")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Record in DB
    asset = svc.record_upload(
        filename=filename,
        original_filename=file.filename,
        file_size=saved_size,
        mime_type=mime_type,
        width=None,
        height=None,
        created_by=user.user_id,
        image_data=data,
    )
    if alt_text:
        asset.alt_text = alt_text
        db.commit()

    svc.increment_storage_usage(saved_size)

    url = get_public_url(tenant.slug, filename)
    logger.info("media.upload_complete", asset_id=asset.id, tenant_id=user.tenant_id, size=saved_size)

    return {
        "id": asset.id,
        "url": url,
        "filename": filename,
        "original_filename": file.filename,
        "mime_type": mime_type,
        "file_size": saved_size,
        "source": "upload",
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.post("/ai-generate", status_code=201)
async def ai_generate_image(
    body: AIImageGenerateRequest,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an image using AI (DALL-E 3 or configured provider)."""
    from app.media.service import MediaService
    from app.media.storage import save_bytes, get_public_url
    from app.ai_config.image_service import ImageConfigService
    from app.ai_config.image_generator import generate_image
    from app.core.models import Tenant
    import httpx
    import base64

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    svc = MediaService(db=db, tenant_id=user.tenant_id, tenant_slug=tenant.slug)

    # Check quota BEFORE calling API
    svc.check_image_gen_quota()

    # Resolve provider
    img_svc = ImageConfigService(db)
    config = img_svc.resolve_image_provider(user.tenant_id)

    # Generate image
    try:
        result = await generate_image(config=config, prompt=body.prompt, size=body.size, quality=body.quality)
    except Exception as e:
        logger.error("media.ai_generate_failed", error=str(e), tenant_id=user.tenant_id)
        raise HTTPException(status_code=502, detail=f"Image generation failed: {str(e)}")

    if not result.urls:
        raise HTTPException(status_code=502, detail="Image generation returned no results")

    # Download and save image
    image_url = result.urls[0]
    try:
        if image_url.startswith("data:"):
            # Base64 data URI (Stability AI)
            b64_data = image_url.split(",", 1)[1]
            image_data = base64.b64decode(b64_data)
        else:
            # Remote URL (DALL-E)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(image_url)
                image_data = resp.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download generated image: {str(e)}")

    svc.check_storage_quota(bytes_to_add=len(image_data))
    filename, file_size = await save_bytes(image_data, tenant.slug, ".png")

    asset = svc.record_ai_generated(
        filename=filename,
        file_size=file_size,
        mime_type="image/png",
        prompt=body.prompt,
        provider_slug=config.provider_slug,
        created_by=user.user_id,
        image_data=image_data,
    )

    svc.increment_image_gen_usage()
    svc.increment_storage_usage(file_size)

    url = get_public_url(tenant.slug, filename)
    logger.info("media.ai_generate_complete", asset_id=asset.id, tenant_id=user.tenant_id, provider=config.provider_slug)

    return {
        "id": asset.id,
        "url": url,
        "revised_prompt": result.revised_prompt,
        "provider_slug": config.provider_slug,
        "model": result.model,
        "file_size": file_size,
        "source": "ai_generated",
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.get("")
async def list_media(
    source: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List media assets for the tenant."""
    q = db.query(MediaAsset).filter(MediaAsset.tenant_id == user.tenant_id)
    if source:
        q = q.filter(MediaAsset.source == source)

    total = q.count()
    assets = q.order_by(MediaAsset.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    from app.core.models import Tenant
    from app.media.storage import get_public_url
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    slug = tenant.slug if tenant else "unknown"

    return {
        "items": [_asset_to_dict(a, slug) for a in assets],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.delete("/{asset_id}")
async def delete_media(
    asset_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a media asset."""
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.tenant_id == user.tenant_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    from app.media.storage import delete_file
    from app.media.service import MediaService
    from app.core.models import Tenant

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    slug = tenant.slug if tenant else "unknown"

    file_size = asset.file_size or 0
    delete_file(slug, asset.filename)

    svc = MediaService(db=db, tenant_id=user.tenant_id, tenant_slug=slug)
    svc.decrement_storage_usage(file_size)

    db.delete(asset)
    db.commit()

    logger.info("media.deleted", asset_id=asset_id, tenant_id=user.tenant_id)
    return {"status": "deleted", "id": asset_id}


def _asset_to_dict(asset: MediaAsset, tenant_slug: str) -> dict:
    from app.media.storage import get_public_url
    return {
        "id": asset.id,
        "url": get_public_url(tenant_slug, asset.filename),
        "filename": asset.filename,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "source": asset.source,
        "alt_text": asset.alt_text,
        "generation_prompt": asset.generation_prompt,
        "image_provider_slug": asset.image_provider_slug,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }
