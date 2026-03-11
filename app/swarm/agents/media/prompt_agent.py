"""ImagePromptAgent: enriches user image prompts with tenant brand context."""
from __future__ import annotations
from typing import Optional
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()


class ImagePromptAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "image_prompt"

    @property
    def description(self) -> str:
        return "Image Prompt Agent – Enriches prompts with tenant brand context"

    async def handle(self, message):
        return None

    async def enrich(
        self,
        *,
        user_prompt: str,
        tenant_id: int,
        channel: str = "email",
        tone: str = "professional",
        campaign_name: str = "",
        db=None,
    ) -> str:
        """Enrich a raw user prompt with tenant brand context and channel requirements."""
        brand_context = ""
        reference_context = ""
        try:
            if db:
                from app.core.models import Tenant
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant:
                    color = getattr(tenant, "primary_color", None) or getattr(tenant, "tenant_primary_color", None)
                    if color:
                        brand_context += f" Brand accent color: {color}."

                # Load brand reference images and inject their visual context
                try:
                    from app.core.media_models import TenantBrandReference, MediaAsset
                    refs = db.query(TenantBrandReference).filter(
                        TenantBrandReference.tenant_id == tenant_id
                    ).limit(3).all()
                    ref_parts = []
                    for ref in refs:
                        if ref.asset_id:
                            asset = db.query(MediaAsset).filter(MediaAsset.id == ref.asset_id).first()
                            if asset:
                                ref_desc = []
                                if asset.description:
                                    ref_desc.append(asset.description)
                                if asset.tags:
                                    tags = asset.tags if isinstance(asset.tags, list) else []
                                    if tags:
                                        ref_desc.append(f"visual elements: {', '.join(tags[:8])}")
                                if asset.dominant_colors:
                                    colors = asset.dominant_colors if isinstance(asset.dominant_colors, list) else []
                                    if colors:
                                        ref_desc.append(f"color palette: {', '.join(colors[:4])}")
                                if asset.alt_text and not ref_desc:
                                    ref_desc.append(asset.alt_text)
                                label = ref.label or "Reference image"
                                if ref_desc:
                                    ref_parts.append(f"{label}: {'. '.join(ref_desc)}")
                    if ref_parts:
                        reference_context = "Visual reference style — " + " | ".join(ref_parts) + "."
                        logger.info("image_prompt_agent.references_loaded", tenant_id=tenant_id, count=len(ref_parts))
                except Exception as e:
                    logger.warning("image_prompt_agent.references_failed", error=str(e))
        except Exception as e:
            logger.warning("image_prompt_agent.brand_context_failed", error=str(e))

        channel_hints = {
            "email": "Wide format (16:9 or wider), photorealistic, high contrast for email rendering, no text overlays.",
            "whatsapp": "Square format (1:1), vibrant colors, eye-catching.",
            "sms": "Simple, clean, minimal.",
            "social": "Square or portrait format, bold visuals, lifestyle photography style.",
        }
        channel_hint = channel_hints.get(channel, channel_hints["email"])

        tone_hints = {
            "professional": "Clean, modern, professional photography style.",
            "casual": "Friendly, warm, approachable atmosphere.",
            "motivational": "Energetic, dynamic, action-oriented, bright lighting.",
            "urgent": "Bold, high-contrast, attention-grabbing.",
        }
        tone_hint = tone_hints.get(tone, tone_hints["professional"])

        context_parts = [user_prompt.strip()]
        if reference_context:
            context_parts.append(reference_context)
        context_parts.append(f"Style: {tone_hint}")
        context_parts.append(f"Format requirements: {channel_hint}")
        context_parts.append("Industry: fitness studio, health and wellness.")
        if brand_context:
            context_parts.append(brand_context)
        if campaign_name:
            context_parts.append(f"Campaign: {campaign_name}.")
        context_parts.append("Photorealistic, high quality, no watermarks, no text.")

        enriched = " ".join(context_parts)
        logger.info("image_prompt_agent.enriched", tenant_id=tenant_id, original_len=len(user_prompt), enriched_len=len(enriched))
        return enriched
