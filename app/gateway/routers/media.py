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
    # Optional campaign context for orchestrator routing
    campaign_name: Optional[str] = None
    channel: Optional[str] = "email"
    tone: Optional[str] = "professional"
    task_context: Optional[str] = "general"
    mode: str = "final"              # "preview" or "final"
    has_text_overlay: bool = False   # routes to Ideogram v2
    use_brand_style: bool = False    # routes to Recraft V3 (Business+ only)
    model_slug: Optional[str] = None  # explicit model override from user selection


class MediaAssetUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    alt_text: Optional[str] = None
    usage_context: Optional[str] = None


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


@router.get("/image-models")
async def list_image_models(user: AuthContext = Depends(get_current_user)):
    """Return the catalog of selectable image generation models with metadata."""
    from app.ai_config.image_models_meta import SELECTABLE_MODELS
    return {"models": SELECTABLE_MODELS}


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

    # If campaign context provided, route through MediaOrchestrator
    if body.campaign_name or body.task_context != "general" or body.channel != "email":
        from app.swarm.agents.media.orchestrator import MediaOrchestrator, MediaGenerationRequest
        from app.swarm.llm import LLMClient
        from config.settings import get_settings
        settings = get_settings()
        llm = LLMClient(openai_api_key=settings.openai_api_key)
        orch = MediaOrchestrator(llm)
        req = MediaGenerationRequest(
            user_prompt=body.prompt,
            tenant_id=user.tenant_id,
            campaign_name=body.campaign_name or "",
            channel=body.channel or "email",
            tone=body.tone or "professional",
            task_context=body.task_context or "general",
            size=body.size,
            quality=body.quality,
            created_by=user.user_id,
            model_slug=body.model_slug,
        )
        result = await orch.run(req, db=db, tenant_slug=tenant.slug)
        if result.error:
            raise HTTPException(status_code=502, detail=result.error)
        return {
            "id": result.asset_id,
            "url": result.url,
            "source": "ai_generated",
            "qa_passed": result.qa_passed,
            "qa_score": result.qa_score,
            "qa_issues": result.qa_issues,
            "qa_suggestions": result.qa_suggestions,
            "pipeline_steps": result.pipeline_steps,
            "retries": result.retries,
            "revised_prompt": result.revised_prompt,
            "created_at": None,
        }

    # Feature gates and quota checks
    from app.core.feature_gates import FeatureGate
    gate = FeatureGate(user.tenant_id)

    if body.use_brand_style:
        gate.require_brand_style()
    if body.has_text_overlay:
        gate.require_text_overlay_images()

    if body.mode == "preview":
        gate.check_image_preview_limit()
    else:
        # Check quota BEFORE calling API
        svc.check_image_gen_quota()
        gate.check_image_generation_limit()

    # Resolve provider based on mode and features
    img_svc = ImageConfigService(db)
    config = img_svc.resolve_provider_for_mode(
        user.tenant_id,
        mode=body.mode,
        has_text_overlay=body.has_text_overlay,
        use_brand_style=body.use_brand_style,
    )

    # Generate image
    try:
        result = await generate_image(
            config=config,
            prompt=body.prompt,
            size=body.size,
            quality=body.quality,
            brand_colors=[],
        )
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

    if body.mode == "preview":
        gate.increment_image_preview_usage()
    else:
        svc.increment_image_gen_usage()
        gate.increment_image_generation_usage()
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
        "mode": body.mode,
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
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    slug = tenant.slug if tenant else "unknown"

    return {
        "items": [_asset_to_dict(a, slug) for a in assets],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/search")
async def search_media(
    q: Optional[str] = None,
    context: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Search media assets by description, tags, and context."""
    from app.core.models import Tenant
    from sqlalchemy import or_, cast, Text

    query = db.query(MediaAsset).filter(MediaAsset.tenant_id == user.tenant_id)

    if q:
        query = query.filter(
            or_(
                MediaAsset.description.ilike(f"%{q}%"),
                MediaAsset.display_name.ilike(f"%{q}%"),
                MediaAsset.alt_text.ilike(f"%{q}%"),
                cast(MediaAsset.tags, Text).ilike(f"%{q}%"),
            )
        )

    if context:
        query = query.filter(MediaAsset.usage_context == context)

    if channel == "email":
        query = query.filter(MediaAsset.mime_type != "image/webp")

    total = query.count()
    assets = query.order_by(MediaAsset.created_at.desc()).limit(limit).all()

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    slug = tenant.slug if tenant else "unknown"

    return {
        "items": [_asset_to_dict(a, slug) for a in assets],
        "total": total,
    }


@router.patch("/{asset_id}")
async def update_media_metadata(
    asset_id: int,
    body: MediaAssetUpdate,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update metadata for a media asset."""
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.tenant_id == user.tenant_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    if body.display_name is not None:
        asset.display_name = body.display_name
    if body.description is not None:
        asset.description = body.description
    if body.tags is not None:
        asset.tags = body.tags
    if body.alt_text is not None:
        asset.alt_text = body.alt_text
    if body.usage_context is not None:
        asset.usage_context = body.usage_context

    db.commit()

    from app.core.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    slug = tenant.slug if tenant else "unknown"
    return _asset_to_dict(asset, slug)


@router.post("/{asset_id}/describe")
async def describe_media(
    asset_id: int,
    user: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Use GPT-4o Vision to auto-generate description, tags, alt_text, usage_context for a media asset."""
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.tenant_id == user.tenant_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")

    from app.core.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    slug = tenant.slug if tenant else "unknown"

    # Read image bytes from disk
    try:
        from app.media.storage import get_media_path
        image_path = get_media_path(slug, asset.filename)
        image_bytes = image_path.read_bytes()
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Image file not found on disk: {e}")

    # Run ImageAnalysisAgent
    try:
        from app.swarm.agents.media.analysis_agent import ImageAnalysisAgent
        from app.swarm.llm import LLMClient
        from config.settings import get_settings
        settings = get_settings()
        llm = LLMClient(openai_api_key=settings.openai_api_key)
        ImageAnalysisAgent.set_llm(llm)
        agent = ImageAnalysisAgent()
        analysis = await agent.describe(image_bytes=image_bytes, tenant_id=user.tenant_id)
    except Exception as e:
        logger.error("media.describe_failed", error=str(e), asset_id=asset_id)
        raise HTTPException(status_code=502, detail=f"Vision analysis failed: {e}")

    if analysis:
        if analysis.get("description"):
            asset.description = analysis["description"]
        if analysis.get("tags"):
            asset.tags = analysis["tags"]
        if analysis.get("alt_text"):
            asset.alt_text = analysis["alt_text"]
        if analysis.get("usage_context"):
            asset.usage_context = analysis["usage_context"]
        if analysis.get("dominant_colors"):
            asset.dominant_colors = analysis["dominant_colors"]
        if analysis.get("brightness"):
            asset.brightness = analysis["brightness"]
        db.commit()

    return _asset_to_dict(asset, slug)


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

    # Protect assets referenced by active campaigns
    from app.core.models import Campaign
    ref = db.query(Campaign).filter(
        Campaign.tenant_id == user.tenant_id,
        Campaign.featured_image_asset_id == asset_id,
        Campaign.status.in_(["draft", "scheduled", "sending"]),
    ).first()
    if ref:
        raise HTTPException(
            status_code=409,
            detail=f"Asset is used by campaign '{ref.name}'. Remove the image from the campaign first.",
        )

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


@router.get("/brand-references")
async def list_brand_references(user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.media_models import TenantBrandReference, MediaAsset
    from app.core.models import Tenant
    from app.media.storage import get_public_url
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    refs = db.query(TenantBrandReference).filter(
        TenantBrandReference.tenant_id == user.tenant_id
    ).order_by(TenantBrandReference.created_at.desc()).all()
    result = []
    for ref in refs:
        asset = db.query(MediaAsset).filter(MediaAsset.id == ref.asset_id).first() if ref.asset_id else None
        url = get_public_url(tenant.slug, asset.filename) if (asset and tenant) else None
        result.append({
            "id": ref.id,
            "label": ref.label,
            "asset_id": ref.asset_id,
            "url": url,
            "created_at": ref.created_at.isoformat() if ref.created_at else None,
        })
    return result


class BrandReferenceCreate(BaseModel):
    asset_id: int
    label: Optional[str] = None


@router.post("/brand-references", status_code=201)
async def create_brand_reference(body: BrandReferenceCreate, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.media_models import TenantBrandReference, MediaAsset
    from app.core.feature_gates import FeatureGate
    from app.core.models import Tenant
    from app.media.storage import get_public_url, get_media_path
    gate = FeatureGate(user.tenant_id)
    gate.require_brand_style()
    asset = db.query(MediaAsset).filter(MediaAsset.id == body.asset_id, MediaAsset.tenant_id == user.tenant_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

    # Auto-analyze if the asset has never been described (so prompt injection has data)
    if not asset.description and tenant:
        try:
            from app.swarm.agents.media.analysis_agent import ImageAnalysisAgent
            from app.swarm.llm import LLMClient
            from config.settings import get_settings
            image_path = get_media_path(tenant.slug, asset.filename)
            image_bytes = image_path.read_bytes()
            settings = get_settings()
            llm = LLMClient(openai_api_key=settings.openai_api_key)
            ImageAnalysisAgent.set_llm(llm)
            agent = ImageAnalysisAgent()
            analysis = await agent.describe(image_bytes=image_bytes, tenant_id=user.tenant_id)
            if analysis:
                asset.description = analysis.get("description") or asset.description
                asset.tags = analysis.get("tags") or asset.tags
                asset.alt_text = analysis.get("alt_text") or asset.alt_text
                asset.usage_context = analysis.get("usage_context") or asset.usage_context
                asset.dominant_colors = analysis.get("dominant_colors") or asset.dominant_colors
                db.commit()
                logger.info("brand_reference.auto_analyzed", asset_id=asset.id, tenant_id=user.tenant_id)
        except Exception as e:
            logger.warning("brand_reference.auto_analyze_failed", asset_id=body.asset_id, error=str(e))

    ref = TenantBrandReference(tenant_id=user.tenant_id, asset_id=body.asset_id, label=body.label)
    db.add(ref)
    db.commit()
    db.refresh(ref)
    url = get_public_url(tenant.slug, asset.filename) if tenant else ""
    return {"id": ref.id, "asset_id": ref.asset_id, "label": ref.label, "url": url,
            "description": asset.description, "tags": asset.tags}


@router.delete("/brand-references/{ref_id}", status_code=204)
async def delete_brand_reference(ref_id: int, user: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.media_models import TenantBrandReference
    ref = db.query(TenantBrandReference).filter(
        TenantBrandReference.id == ref_id,
        TenantBrandReference.tenant_id == user.tenant_id,
    ).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Brand reference not found")
    db.delete(ref)
    db.commit()


def _asset_to_dict(asset: MediaAsset, tenant_slug: str) -> dict:
    from app.media.storage import get_public_url
    return {
        "id": asset.id,
        "url": get_public_url(tenant_slug, asset.filename),
        "filename": asset.filename,
        "original_filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "width": asset.width,
        "height": asset.height,
        "source": asset.source,
        "alt_text": asset.alt_text,
        "display_name": asset.display_name,
        "description": asset.description,
        "tags": asset.tags or [],
        "usage_context": asset.usage_context,
        "dominant_colors": asset.dominant_colors or [],
        "brightness": asset.brightness,
        "orientation": asset.orientation,
        "aspect_ratio": asset.aspect_ratio,
        "generation_prompt": asset.generation_prompt,
        "image_provider_slug": asset.image_provider_slug,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }
