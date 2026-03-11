"""Credit costs per image generation model slug."""
from __future__ import annotations

# Credits charged per generation/edit by model slug
IMAGE_CREDIT_COSTS: dict[str, int] = {
    # Text-to-image — Budget (1-2 credits)
    "fal_ai_schnell":     1,
    "flux2_turbo":        1,
    "flux2_klein":        2,
    "recraft_v4":         2,
    # Text-to-image — Standard (3 credits)
    "fal_ai":             3,
    "seedream_45":        3,
    "flux2_pro":          3,
    "imagen4_standard":   3,
    "ideogram_v3":        3,
    # Text-to-image — Premium (6 credits)
    "gemini_flash":       6,
    "flux2_max":          6,
    "flux2_flex":         6,
    "imagen4_ultra":      6,
    "recraft_v3":         6,
    "ideogram_v2":        3,
    # Text-to-image — Ultra (10 credits)
    "gemini_pro":         10,
    "gpt_image_15":       10,
    # Image editing — Budget (2 credits)
    "flux2_flash_edit":   2,
    "flux2_turbo_edit":   2,
    # Image editing — Standard (4 credits)
    "seedream_45_edit":   4,
    "flux_kontext_pro":   4,
    "flux2_pro_edit":     4,
    # Image editing — Premium (6 credits)
    "nano_banana2_edit":  6,
    "nano_banana_edit":   6,
    "flux2_max_edit":     6,
    "flux2_flex_edit":    6,
    # Image editing — Ultra (12 credits)
    "nano_banana_pro_edit": 10,
    "gpt_image_15_edit":  12,
}

DEFAULT_CREDIT_COST = 3  # fallback for unknown slugs


def get_credit_cost(model_slug: str) -> int:
    return IMAGE_CREDIT_COSTS.get(model_slug, DEFAULT_CREDIT_COST)
