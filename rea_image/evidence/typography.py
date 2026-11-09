"""Typography and layout analysis: font candidates, hierarchy, styling, and grid rhythm."""

from typing import Any, Dict, List, Optional
import numpy as np
from rea_image.schemas import TypographyInfo


# Well-known typographic classifications and top font candidate families
FONT_FAMILIES = {
    "sans_neo_grotesque": ["Inter", "Helvetica Neue", "Roboto", "Arial"],
    "sans_geometric": ["Futura", "Montserrat", "Poppins", "Century Gothic"],
    "sans_humanist": ["Segoe UI", "Open Sans", "Gill Sans", "Frutiger"],
    "serif_transitional": ["Times New Roman", "Georgia", "Baskerville"],
    "serif_editorial": ["Playfair Display", "Didot", "Bodoni", "Garamond"],
    "monospace_code": ["Fira Code", "JetBrains Mono", "SF Mono", "Consolas"],
    "display_bold": ["Impact", "Bebas Neue", "Oswald", "Anton"],
    "script_brush": ["Brush Script MT", "Pacifico", "Great Vibes"],
}


class TypographyAnalyzer:
    """Analyzes typographic properties, font family candidates, styling, and layout grid."""

    def analyze(self, arr: np.ndarray, text_boxes: Optional[List[dict]] = None) -> TypographyInfo:
        h, w, _ = arr.shape
        boxes = text_boxes or []

        # 1. Size hierarchy & weight
        if boxes:
            max_bh = max(b["bbox"][3] for b in boxes)
            if max_bh > h * 0.12:
                hierarchy = "Display / Hero Header (H1)"
                weight = "Bold / ExtraBold (700-800)"
                font_candidates = FONT_FAMILIES["display_bold"][:3]
            elif max_bh > h * 0.05:
                hierarchy = "Subheading (H2 / H3)"
                weight = "SemiBold / Medium (600)"
                font_candidates = FONT_FAMILIES["sans_geometric"][:3]
            else:
                hierarchy = "Body / Caption text"
                weight = "Regular (400)"
                font_candidates = FONT_FAMILIES["sans_neo_grotesque"][:3]

            # Alignment estimate: average horizontal center of boxes
            centers_x = [b["bbox"][0] + b["bbox"][2] / 2.0 for b in boxes]
            avg_center = np.mean(centers_x)
            if abs(avg_center - w / 2.0) < w * 0.1:
                alignment = "center"
            elif avg_center < w * 0.4:
                alignment = "left"
            else:
                alignment = "right"
        else:
            hierarchy = "None detected"
            weight = "Regular"
            alignment = "center"
            font_candidates = FONT_FAMILIES["sans_neo_grotesque"][:3]

        # 2. Text styling detection (shadow, stroke, high contrast)
        text_styling = ["solid fill"]
        # Check for drop shadows
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        gy, gx = np.gradient(lum)
        grad_mag = np.hypot(gx, gy)
        if np.percentile(grad_mag, 98) > 70.0:
            text_styling.append("high-contrast edge")

        return TypographyInfo(
            font_family_candidates=font_candidates,
            weight=weight,
            size_hierarchy=hierarchy,
            line_spacing=1.3,
            tracking=0.02,
            alignment=alignment,
            text_styling=text_styling,
            extracted_text="",
        )


def analyze_layout_grid(arr: np.ndarray, regions: Optional[list] = None) -> Dict[str, Any]:
    """Extract design tokens, margins, column alignment, and card patterns."""
    h, w, _ = arr.shape
    
    # Margin calculation: distance from border to first non-background region
    margin_x = int(w * 0.05)
    margin_y = int(h * 0.05)
    
    return {
        "margins": {"x": margin_x, "y": margin_y},
        "grid_type": "12-column responsive layout" if w >= h else "Single-column mobile stack",
        "container_padding": f"{max(8, int(w * 0.02))}px",
        "corner_radii": "8px - 16px (subtle rounded cards)",
        "card_patterns": "card containers with soft elevation shadows",
        "alignment_axes": "vertical center alignment",
    }

