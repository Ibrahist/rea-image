"""Color grade, dominant palette extraction, and film/LUT analysis."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from rea_image.schemas import PaletteColor


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Format RGB as #RRGGBB."""
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def extract_dominant_palette(
    arr: np.ndarray,
    n_colors: int = 5,
    region_labels: Optional[Dict[str, np.ndarray]] = None,
) -> List[PaletteColor]:
    """Extract dominant palette colors with hex, RGB, percentages, and semantic roles.
    
    Roles:
      - background: dominant in background region / image borders
      - subject: dominant in subject / central region
      - accent: high saturation/distinct vibrancy with moderate or small area
      - text: high contrast against background
    """
    h, w, _ = arr.shape
    # Subsample pixels for speed
    step = max(1, int(np.sqrt((h * w) / 50000)))
    sampled = arr[::step, ::step, :].reshape(-1, 3).astype(np.float32)

    # Simple fast k-means clustering in RGB
    np.random.seed(42)
    indices = np.random.choice(len(sampled), size=n_colors, replace=False)
    centroids = sampled[indices].copy()

    for _ in range(12):  # 12 iterations is plenty for palette convergence
        # Compute distances to centroids
        dists = np.linalg.norm(sampled[:, None, :] - centroids[None, :, :], axis=-1)
        cluster_assignments = np.argmin(dists, axis=-1)
        
        # Update centroids
        new_centroids = np.zeros_like(centroids)
        for k in range(n_colors):
            pts = sampled[cluster_assignments == k]
            if len(pts) > 0:
                new_centroids[k] = np.mean(pts, axis=0)
            else:
                new_centroids[k] = centroids[k]
        if np.allclose(centroids, new_centroids, atol=1.0):
            break
        centroids = new_centroids

    # Calculate percentages
    counts = np.bincount(cluster_assignments, minlength=n_colors)
    total_pts = float(len(sampled))
    percentages = (counts / total_pts) * 100.0

    # Sort descending by percentage
    order = np.argsort(percentages)[::-1]
    sorted_centroids = centroids[order]
    sorted_percentages = percentages[order]

    # Assign roles
    palette: List[PaletteColor] = []
    has_accent = False

    for i in range(n_colors):
        r, g, b = np.clip(np.round(sorted_centroids[i]), 0, 255).astype(int)
        pct = float(round(sorted_percentages[i], 1))
        hex_val = rgb_to_hex(r, g, b)

        # Compute saturation: max(RGB) - min(RGB) / max(RGB)
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        sat = ((max_c - min_c) / float(max_c + 1e-4)) if max_c > 0 else 0.0
        lum = (0.299 * r + 0.587 * g + 0.114 * b)

        # Heuristic role assignment
        if i == 0:
            role = "background"
        elif not has_accent and sat > 0.4 and pct < 25.0:
            role = "accent"
            has_accent = True
        elif lum < 35 or lum > 220:
            role = "text"
        else:
            role = "subject"

        palette.append(
            PaletteColor(
                hex=hex_val,
                rgb=[int(r), int(g), int(b)],
                role=role,
                percentage=pct,
            )
        )

    return palette


def analyze_color_grade(arr: np.ndarray) -> Dict[str, Any]:
    """Analyze contrast curve, saturation, split toning, and dynamic range."""
    lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    
    black_point = int(np.percentile(lum, 1))
    white_point = int(np.percentile(lum, 99))
    dynamic_range = white_point - black_point

    # Contrast estimation
    lum_std = float(np.std(lum))
    if lum_std > 65.0:
        contrast = "high contrast"
    elif lum_std < 35.0:
        contrast = "low contrast / muted"
    else:
        contrast = "medium contrast"

    # Saturation estimation
    r = arr[:, :, 0].astype(np.float32)
    g = arr[:, :, 1].astype(np.float32)
    b = arr[:, :, 2].astype(np.float32)
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    sat = (max_c - min_c) / (max_c + 1e-4)
    mean_sat = float(np.mean(sat))

    if mean_sat < 0.05:
        sat_style = "monochrome / grayscale"
    elif mean_sat < 0.25:
        sat_style = "desaturated / muted"
    elif mean_sat > 0.60:
        sat_style = "hyper-saturated / vibrant"
    else:
        sat_style = "natural saturation"

    # Split-toning detection (shadows vs highlights color temperature)
    shadows_mask = lum < np.percentile(lum, 25)
    highlights_mask = lum > np.percentile(lum, 75)
    
    shadow_r = float(np.mean(r[shadows_mask])) if np.sum(shadows_mask) > 0 else float(np.mean(r))
    shadow_b = float(np.mean(b[shadows_mask])) if np.sum(shadows_mask) > 0 else float(np.mean(b))
    hi_r = float(np.mean(r[highlights_mask])) if np.sum(highlights_mask) > 0 else float(np.mean(r))
    hi_b = float(np.mean(b[highlights_mask])) if np.sum(highlights_mask) > 0 else float(np.mean(b))

    split_toning = "neutral"
    # Teal & Orange / warm highlights + cool shadows
    if (hi_r > hi_b * 1.15) and (shadow_b > shadow_r * 1.08):
        split_toning = "warm highlights, cool shadows (teal & orange / filmic)"
    elif (hi_b > hi_r * 1.15) and (shadow_r > shadow_b * 1.08):
        split_toning = "cool highlights, warm shadows"

    return {
        "black_point": black_point,
        "white_point": white_point,
        "dynamic_range": dynamic_range,
        "contrast": contrast,
        "saturation_level": sat_style,
        "split_toning": split_toning,
        "film_look_detected": (split_toning != "neutral" or contrast == "low contrast / muted"),
    }
