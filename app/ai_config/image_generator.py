"""Async image generation via fal.ai (FLUX), OpenAI DALL-E, and Stability AI."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class GeneratedImageResult:
    urls: list[str] = field(default_factory=list)
    model: str = ""
    provider_slug: str = ""
    revised_prompt: str = ""


# fal.ai size mapping: "WxH" → fal named size or custom dict
_FAL_SIZE_MAP = {
    "1024x1024": "square_hd",
    "1024x768":  "landscape_4_3",
    "768x1024":  "portrait_4_3",
    "1280x720":  "landscape_16_9",
    "720x1280":  "portrait_16_9",
    "1920x1080": "landscape_16_9",
}


async def generate_image(
    config,  # ResolvedImageConfig
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
) -> GeneratedImageResult:
    """Generate an image via the configured provider."""
    if config.provider_type == "fal_ai":
        return await _generate_fal(config, prompt, size, n)
    elif config.provider_type == "openai_images":
        return await _generate_openai(config, prompt, size, quality, n)
    elif config.provider_type == "stability_ai":
        return await _generate_stability(config, prompt, size, n)
    else:
        raise ValueError(f"Unsupported provider type: {config.provider_type}")


async def _generate_openai(config, prompt: str, size: str, quality: str, n: int) -> GeneratedImageResult:
    url = f"{config.api_base_url}/images/generations"
    payload = {
        "model": config.model,
        "prompt": prompt,
        "n": n,
        "size": size,
    }
    if config.model == "dall-e-3":
        payload["quality"] = quality

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {config.api_key}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI Images API error {resp.status_code}: {resp.text}")
        data = resp.json()

    images = data.get("data", [])
    urls = [img["url"] for img in images if img.get("url")]
    revised = images[0].get("revised_prompt", prompt) if images else prompt

    return GeneratedImageResult(
        urls=urls,
        model=config.model,
        provider_slug=config.provider_slug,
        revised_prompt=revised,
    )


async def _generate_fal(config, prompt: str, size: str, n: int) -> GeneratedImageResult:
    """Generate image via fal.ai (FLUX 1.1 Pro by default)."""
    fal_size = _FAL_SIZE_MAP.get(size, "square_hd")

    payload = {
        "prompt": prompt,
        "image_size": fal_size,
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": n,
        "enable_safety_checker": True,
        "output_format": "jpeg",
    }

    model_endpoint = config.model or "fal-ai/flux-pro/v1.1"
    url = f"https://fal.run/{model_endpoint}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Key {config.api_key}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"fal.ai error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()

    images = data.get("images", [])
    urls = [img["url"] for img in images if img.get("url")]
    revised = data.get("prompt", prompt)

    logger.info("fal_ai.generate.complete", model=model_endpoint, n_images=len(urls))
    return GeneratedImageResult(
        urls=urls,
        model=model_endpoint,
        provider_slug=config.provider_slug,
        revised_prompt=revised,
    )


async def _generate_stability(config, prompt: str, size: str, n: int) -> GeneratedImageResult:
    width, height = 1024, 1024
    if "x" in size:
        parts = size.split("x")
        try:
            width, height = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            pass

    url = f"{config.api_base_url}/v1/generation/{config.model}/text-to-image"
    payload = {
        "text_prompts": [{"text": prompt, "weight": 1.0}],
        "width": width,
        "height": height,
        "samples": n,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {config.api_key}", "Accept": "application/json"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Stability AI error {resp.status_code}: {resp.text}")
        data = resp.json()

    # Stability returns base64; caller must decode and save to disk
    artifacts = data.get("artifacts", [])
    # Return base64 data URIs so caller can handle saving
    b64_urls = [f"data:image/png;base64,{a['base64']}" for a in artifacts if a.get("base64")]

    return GeneratedImageResult(
        urls=b64_urls,
        model=config.model,
        provider_slug=config.provider_slug,
        revised_prompt=prompt,
    )
