"""AI model family style estimator: probabilistic style heuristic."""

from typing import Any, Dict, Optional


def estimate_ai_model_family(
    evidence_list: list,
    width: int,
    height: int,
    color_grade: Optional[dict] = None,
) -> Dict[str, Any]:
    """Estimate likely AI generator family as a style guess with low-to-medium confidence.
    
    Returns style guess, estimated confidence (always <= medium-high), and key indicators.
    """
    indicators = []
    
    # 1. Check direct metadata traces
    for ev in evidence_list:
        if ev.name == "ai_generator_metadata":
            gen = ev.value.get("generator", "")
            if "Midjourney" in gen:
                return {
                    "family": "Midjourney-style",
                    "confidence": "medium-high",
                    "indicators": ["Midjourney metadata / parameter flags detected"],
                    "note": "Probabilistic style identification based on embedded tags.",
                }
            elif "ComfyUI" in gen or "Stable Diffusion" in gen:
                model_name = ev.value.get("parameters", {}).get("model", "")
                if "flux" in model_name.lower():
                    return {
                        "family": "FLUX-style",
                        "confidence": "medium-high",
                        "indicators": [f"ComfyUI checkpoint trace: {model_name}"],
                        "note": "Probabilistic style identification based on workflow nodes.",
                    }
                return {
                    "family": "Stable Diffusion / SDXL-style",
                    "confidence": "medium-high",
                    "indicators": ["Stable Diffusion / A1111 parameter chunks detected"],
                    "note": "Probabilistic style identification based on generation parameters.",
                }

    # 2. Heuristic resolution matches
    res_pair = (width, height)
    if res_pair in ((1024, 1792), (1792, 1024)):
        indicators.append(f"DALL-E 3 canonical resolution bucket {width}x{height}")
        family = "DALL-E-style"
        conf = "medium"
    elif res_pair in ((896, 1152), (1152, 896), (832, 1216), (1216, 832)):
        indicators.append(f"SDXL aspect ratio bucket {width}x{height}")
        family = "SDXL / FLUX-style"
        conf = "medium"
    elif color_grade and color_grade.get("split_toning") != "neutral":
        indicators.append("Rich cinematic split-toning and dramatic contrast")
        family = "Midjourney-style"
        conf = "low-medium"
    else:
        indicators.append("Diffusion-style latent texture")
        family = "General diffusion-style"
        conf = "low-medium"

    return {
        "family": family,
        "confidence": conf,
        "indicators": indicators,
        "note": "Heuristic style estimate only; never definitive proof of origin.",
    }

