"""ImageGenerationAgent: wraps the configured image provider."""
from __future__ import annotations
from typing import Optional
import structlog
from app.swarm.base import BaseAgent

logger = structlog.get_logger()


class ImageGenerationAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "image_generation"

    @property
    def description(self) -> str:
        return "Image Generation Agent – Generates images via configured provider"

    async def handle(self, message):
        return None

    async def generate(
        self,
        *,
        prompt: str,
        tenant_id: int,
        size: str = "1024x1024",
        quality: str = "standard",
        db=None,
        model_slug: Optional[str] = None,
    ) -> tuple[bytes, str, str]:
        """Generate image. Returns (image_bytes, provider_slug, revised_prompt)."""
        import httpx
        import base64
        from app.ai_config.image_service import ImageConfigService
        from app.ai_config.image_generator import generate_image

        svc = ImageConfigService(db)
        if model_slug:
            config = svc.resolve_provider_by_slug(tenant_id, model_slug)
        else:
            config = svc.resolve_image_provider(tenant_id)
        result = await generate_image(config=config, prompt=prompt, size=size, quality=quality)

        # If primary model returned no images, retry once with the reliable fallback (flux2_pro)
        if not result.urls and model_slug and model_slug != "flux2_pro":
            logger.warning("image_generation_agent.fallback", original_slug=model_slug, tenant_id=tenant_id)
            fallback_config = svc.resolve_provider_by_slug(tenant_id, "flux2_pro")
            if fallback_config:
                result = await generate_image(config=fallback_config, prompt=prompt, size=size, quality=quality)
                config = fallback_config

        if not result.urls:
            raise ValueError("Image generation returned no results")

        image_url = result.urls[0]
        if image_url.startswith("data:"):
            b64_data = image_url.split(",", 1)[1]
            image_bytes = base64.b64decode(b64_data)
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_bytes = resp.content

        revised_prompt = result.revised_prompt or prompt
        logger.info("image_generation_agent.complete", tenant_id=tenant_id, provider=config.provider_slug, size=len(image_bytes))
        return image_bytes, config.provider_slug, revised_prompt
