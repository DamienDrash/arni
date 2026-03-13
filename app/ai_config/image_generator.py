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
    **kwargs,
) -> GeneratedImageResult:
    """Generate an image via the configured provider."""
    if config.provider_type == "fal_ai":
        return await _generate_fal(config, prompt, size, n)
    elif config.provider_type == "openai_images":
        return await _generate_openai(config, prompt, size, quality, n)
    elif config.provider_type == "stability_ai":
        return await _generate_stability(config, prompt, size, n)
    elif config.provider_type == "fal_ai_schnell":
        return await _generate_fal_schnell(config, prompt, size, n)
    elif config.provider_type == "recraft_v3":
        return await _generate_recraft(config, prompt, size, n, brand_colors=kwargs.get("brand_colors", []))
    elif config.provider_type == "ideogram_v2":
        return await _generate_ideogram(config, prompt, size, n)
    elif config.provider_type == "fal_generic":
        return await _generate_fal_generic(config, prompt, size, n)
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


async def _generate_fal_schnell(config, prompt: str, size: str, n: int) -> GeneratedImageResult:
    """FLUX Schnell — fast preview generation (~1-2s)."""
    fal_size = _FAL_SIZE_MAP.get(size, "square_hd")
    payload = {
        "prompt": prompt,
        "image_size": fal_size,
        "num_inference_steps": 4,   # Schnell uses fewer steps
        "num_images": n,
        "enable_safety_checker": True,
        "output_format": "jpeg",
    }
    url = "https://fal.run/fal-ai/flux/schnell"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Key {config.api_key}"})
        if resp.status_code != 200:
            raise RuntimeError(f"fal.ai Schnell error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
    images = data.get("images", [])
    urls = [img["url"] for img in images if img.get("url")]
    logger.info("fal_ai_schnell.generate.complete", n_images=len(urls))
    return GeneratedImageResult(urls=urls, model="fal-ai/flux/schnell", provider_slug=config.provider_slug, revised_prompt=prompt)


async def _generate_recraft(config, prompt: str, size: str, n: int, brand_colors: list[str] = None) -> GeneratedImageResult:
    """Recraft V3 — brand-consistent generation."""
    # Map size to width/height
    w, h = 1024, 1024
    if "x" in size:
        try:
            w, h = int(size.split("x")[0]), int(size.split("x")[1])
        except (ValueError, IndexError):
            pass

    payload: dict = {
        "prompt": prompt,
        "image_size": {"width": w, "height": h},
        "style": "realistic_image",
        "num_images": n,
    }
    # Inject brand colors as Recraft color palette hints
    if brand_colors:
        payload["colors"] = [{"rgb": _hex_to_rgb(c)} for c in brand_colors[:5] if c]

    url = "https://fal.run/fal-ai/recraft-v3"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Key {config.api_key}"})
        if resp.status_code != 200:
            raise RuntimeError(f"Recraft V3 error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
    images = data.get("images", [])
    urls = [img["url"] for img in images if img.get("url")]
    logger.info("recraft_v3.generate.complete", n_images=len(urls))
    return GeneratedImageResult(urls=urls, model="fal-ai/recraft-v3", provider_slug=config.provider_slug, revised_prompt=prompt)


async def _generate_ideogram(config, prompt: str, size: str, n: int) -> GeneratedImageResult:
    """Ideogram v2 — best for images with text overlays."""
    # Ideogram uses resolution strings
    resolution_map = {
        "1024x1024": "RESOLUTION_1024_1024",
        "1280x720": "RESOLUTION_1280_720",
        "720x1280": "RESOLUTION_720_1280",
        "1024x768": "RESOLUTION_1024_768",
    }
    resolution = resolution_map.get(size, "RESOLUTION_1024_1024")
    payload = {
        "prompt": prompt,
        "resolution": resolution,
        "style_type": "REALISTIC",
        "magic_prompt_option": "AUTO",
        "num_images": n,
    }
    url = "https://fal.run/fal-ai/ideogram/v2"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Key {config.api_key}"})
        if resp.status_code != 200:
            raise RuntimeError(f"Ideogram v2 error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
    images = data.get("images", [])
    urls = [img["url"] if isinstance(img, dict) else img for img in images if img]
    logger.info("ideogram_v2.generate.complete", n_images=len(urls))
    return GeneratedImageResult(urls=urls, model="fal-ai/ideogram/v2", provider_slug=config.provider_slug, revised_prompt=prompt)


async def _generate_fal_generic(config, prompt: str, size: str, n: int) -> GeneratedImageResult:
    """Universal fal.ai dispatcher for any model endpoint with optional extra params."""
    from app.ai_config.image_models_meta import MODELS_BY_SLUG

    # Find metadata by matching the provider_slug to our catalog slug
    meta = MODELS_BY_SLUG.get(config.provider_slug) or {}
    endpoint = meta.get("fal_endpoint") or config.model
    extra_params = meta.get("fal_params") or {}

    fal_size = _FAL_SIZE_MAP.get(size, "square_hd")
    payload: dict = {
        "prompt": prompt,
        "image_size": fal_size,
        "num_images": n,
        **extra_params,
    }

    # Ideogram V3 uses different param names
    if "ideogram/v3" in endpoint:
        resolution_map = {
            "1024x1024": "RESOLUTION_1024_1024",
            "1280x720": "RESOLUTION_1280_720",
            "720x1280": "RESOLUTION_720_1280",
            "1024x768": "RESOLUTION_1024_768",
        }
        payload = {
            "prompt": prompt,
            "resolution": resolution_map.get(size, "RESOLUTION_1024_1024"),
            "style_type": "REALISTIC",
            "magic_prompt_option": "AUTO",
            "num_images": n,
            **extra_params,
        }
    # GPT Image 1.5 via fal.ai — uses OpenAI size string
    elif "gpt-image" in endpoint:
        payload = {
            "prompt": prompt,
            "size": size,
            "n": n,
            **extra_params,
        }
    # Gemini / Imagen 4 / FLUX.2 variants / Nano Banana → aspect_ratio param
    elif any(x in endpoint for x in ("gemini-3", "imagen4", "nano-banana", "flux-pro/v1.1-ultra", "flux-2-pro", "flux-2-max", "flux-2-flex", "flux-2/turbo", "flux-2/klein")):
        w, h = 1024, 1024
        if "x" in size:
            try:
                w, h = int(size.split("x")[0]), int(size.split("x")[1])
            except (ValueError, IndexError):
                pass
        from math import gcd
        d = gcd(w, h)
        payload = {
            "prompt": prompt,
            "aspect_ratio": f"{w // d}:{h // d}",
            "num_images": n,
            **extra_params,
        }
    # Seedream / Recraft V4 use width/height dict
    elif any(x in endpoint for x in ("seedream", "recraft/v4")):
        w, h = 1024, 1024
        if "x" in size:
            try:
                w, h = int(size.split("x")[0]), int(size.split("x")[1])
            except (ValueError, IndexError):
                pass
        payload = {
            "prompt": prompt,
            "image_size": {"width": w, "height": h},
            "num_images": n,
            **extra_params,
        }

    url = f"https://fal.run/{endpoint}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Key {config.api_key}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"fal.ai [{endpoint}] error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()

    # GPT Image 1.5 via fal — try OpenAI-style data[].url first, then fall back to fal-style images[]
    if "gpt-image" in endpoint:
        items = data.get("data", [])
        urls = []
        for item in items:
            if item.get("url"):
                urls.append(item["url"])
            elif item.get("b64_json"):
                urls.append(f"data:image/png;base64,{item['b64_json']}")
        # Fallback: fal may also return standard images[] format for this model
        if not urls:
            images = data.get("images", [])
            urls = [(img["url"] if isinstance(img, dict) else img) for img in images if img]
    else:
        images = data.get("images", [])
        urls = [
            (img["url"] if isinstance(img, dict) else img)
            for img in images if img
        ]

    if not urls:
        # Log the full response structure to diagnose future format mismatches
        logger.warning("fal_generic.empty_response", endpoint=endpoint, response_keys=list(data.keys()))
    logger.info("fal_generic.generate.complete", endpoint=endpoint, n_images=len(urls))
    return GeneratedImageResult(
        urls=urls,
        model=endpoint,
        provider_slug=config.provider_slug,
        revised_prompt=data.get("prompt", prompt),
    )


async def generate_edit_image(
    config,                           # ResolvedImageConfig — provides api_key
    image_url: str,                   # publicly accessible URL of the source image
    prompt: str,
    edit_model_slug: str = "nano_banana2_edit",
    strength: float = 0.75,
) -> GeneratedImageResult:
    """Edit an existing image via the configured img2img provider."""
    from app.ai_config.image_edit_models_meta import EDIT_MODELS_BY_SLUG
    meta = EDIT_MODELS_BY_SLUG.get(edit_model_slug)
    if not meta:
        # Unknown slug — fall back to Nano Banana 2 edit
        meta = EDIT_MODELS_BY_SLUG.get("nano_banana2_edit", {})
    endpoint = meta.get("fal_endpoint", "fal-ai/gemini-3.1-flash-image-preview/edit")
    supports_strength = meta.get("supports_strength", False)
    return await _edit_fal_generic(
        config=config,
        image_url=image_url,
        prompt=prompt,
        endpoint=endpoint,
        supports_strength=supports_strength,
        strength=strength,
    )


async def _edit_fal_generic(
    config,
    image_url: str,
    prompt: str,
    endpoint: str,
    supports_strength: bool,
    strength: float,
    n: int = 1,
) -> GeneratedImageResult:
    """Universal fal.ai img2img dispatcher."""
    # GPT Image edit uses OpenAI-style payload (image_url singular, n)
    if "gpt-image" in endpoint:
        payload: dict = {
            "image_url": image_url,
            "prompt": prompt,
            "n": n,
        }
    # Gemini / Nano Banana edit uses image_urls (array)
    elif "gemini" in endpoint or "nano-banana" in endpoint:
        payload = {
            "image_urls": [image_url],
            "prompt": prompt,
            "num_images": n,
        }
    # FLUX Kontext Pro uses image_url singular + prompt
    elif "kontext" in endpoint:
        payload = {
            "image_url": image_url,
            "prompt": prompt,
            "num_images": n,
        }
    else:
        # Seedream, FLUX.2 flash/turbo edit — image_url singular
        payload = {
            "image_url": image_url,
            "prompt": prompt,
            "num_images": n,
        }
        if supports_strength:
            payload["strength"] = max(0.0, min(1.0, strength))

    url = f"https://fal.run/{endpoint}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Key {config.api_key}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"fal.ai edit [{endpoint}] error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()

    if "gpt-image" in endpoint:
        items = data.get("data", [])
        urls = []
        for item in items:
            if item.get("url"):
                urls.append(item["url"])
            elif item.get("b64_json"):
                urls.append(f"data:image/png;base64,{item['b64_json']}")
    else:
        images = data.get("images", [])
        urls = [img["url"] if isinstance(img, dict) else img for img in images if img]

    logger.info("fal_edit.complete", endpoint=endpoint, n_images=len(urls))
    return GeneratedImageResult(
        urls=urls,
        model=endpoint,
        provider_slug=config.provider_slug,
        revised_prompt=data.get("prompt", prompt),
    )


def _hex_to_rgb(hex_color: str) -> dict:
    """Convert #RRGGBB to {r, g, b} dict."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return {"r": 128, "g": 128, "b": 128}
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}
