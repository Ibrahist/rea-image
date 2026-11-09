"""Cross-image consistency analyzer for carousels, ad sets, and brand image series."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from rea_image.schemas import ReportSchema, PaletteColor


def analyze_cross_image_consistency(
    reports: List[ReportSchema],
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evaluate style, palette, aspect ratio, and typography uniformity across an image set."""
    if not reports:
        return {}

    n = len(reports)
    filenames = [Path(r.image.path).name for r in reports]

    # 1. Aspect Ratio Uniformity (Essential for carousels)
    aspect_ratios = [r.image.aspect_ratio for r in reports]
    unique_ars = list(set(aspect_ratios))
    ar_consistent = len(unique_ars) == 1
    ar_summary = {
        "is_uniform": ar_consistent,
        "unique_aspect_ratios": unique_ars,
        "dominant_aspect_ratio": max(set(aspect_ratios), key=aspect_ratios.count),
    }

    # 2. Production Medium Consistency
    dominant_methods = [
        r.verdict.method_breakdown[0].method if r.verdict.method_breakdown else "unknown"
        for r in reports
    ]
    unique_methods = list(set(dominant_methods))
    method_consistent = len(unique_methods) == 1
    method_summary = {
        "is_uniform": method_consistent,
        "methods_present": unique_methods,
        "dominant_method": max(set(dominant_methods), key=dominant_methods.count),
    }

    # 3. Brand Color Palette Cohesion
    # Collect all palette colors and find shared dominant brand hues
    all_hexes = []
    all_rgbs = []
    for r in reports:
        for c in r.global_analysis.palette:
            all_hexes.append(c.hex)
            all_rgbs.append(c.rgb)

    # Compute color variance / cohesion across images
    if all_rgbs:
        rgbs_arr = np.array(all_rgbs, dtype=np.float32)
        color_std = float(np.mean(np.std(rgbs_arr, axis=0)))
        palette_cohesion = "high" if color_std < 40.0 else ("medium" if color_std < 75.0 else "diverse")
    else:
        palette_cohesion = "unknown"

    # 4. Lighting & Color Grade Uniformity
    color_temps = [
        r.global_analysis.lighting.get("color_temperature", "neutral")
        for r in reports
    ]
    unique_temps = list(set(color_temps))
    temp_consistent = len(unique_temps) <= 2

    # 5. Overall Series Cohesion Score (0 - 100)
    score = 0
    if ar_consistent:
        score += 30
    elif len(unique_ars) <= 2:
        score += 15

    if method_consistent:
        score += 35
    elif len(unique_methods) <= 2:
        score += 20

    if palette_cohesion == "high":
        score += 25
    elif palette_cohesion == "medium":
        score += 15

    if temp_consistent:
        score += 10

    if score >= 85:
        verdict = "Highly Cohesive Brand Series / Carousel"
    elif score >= 60:
        verdict = "Moderately Cohesive Campaign Set"
    else:
        verdict = "Heterogeneous / Mixed Media Collection"

    summary_data = {
        "total_images": n,
        "image_files": filenames,
        "series_cohesion_score": score,
        "series_verdict": verdict,
        "aspect_ratio_consistency": ar_summary,
        "production_method_consistency": method_summary,
        "palette_cohesion": {
            "level": palette_cohesion,
            "color_variance": round(color_std, 1) if all_rgbs else 0.0,
        },
        "lighting_temperature_consistency": {
            "is_consistent": temp_consistent,
            "temperatures_detected": unique_temps,
        },
        "recommendations": [],
    }

    # Actionable advice for creators
    if not ar_consistent:
        summary_data["recommendations"].append(
            f"Carousel warning: Mismatched aspect ratios ({', '.join(unique_ars)}). Standardize to {ar_summary['dominant_aspect_ratio']} for carousel posts."
        )
    if not method_consistent:
        summary_data["recommendations"].append(
            f"Mixed production media ({', '.join(unique_methods)}). Ensure transition styling bridges photographic and graphic slides smoothly."
        )

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_file = out_dir / "consistency_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

    return summary_data

