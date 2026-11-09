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

            # Alignment estimate: average horizontal center or shared left edge
            centers_x = [b["bbox"][0] + b["bbox"][2] / 2.0 for b in boxes]
            avg_center = float(np.mean(centers_x))
            lefts = [b["bbox"][0] for b in boxes]
            if len(boxes) >= 2 and np.std(lefts) < 15:
                alignment = "left"
            elif abs(avg_center - w / 2.0) < w * 0.12:
                alignment = "center"
            elif avg_center < w * 0.45:
                alignment = "left"
            else:
                alignment = "right"

            # Line spacing calculation from geometry if multiple lines
            if len(boxes) >= 2:
                sorted_boxes = sorted(boxes, key=lambda b: b["bbox"][1])
                ratios = []
                for i in range(len(sorted_boxes) - 1):
                    y1, h1 = sorted_boxes[i]["bbox"][1], sorted_boxes[i]["bbox"][3]
                    y2 = sorted_boxes[i + 1]["bbox"][1]
                    if y2 > y1 and h1 > 0:
                        ratio = (y2 - y1) / float(h1)
                        if 0.8 <= ratio <= 3.5:
                            ratios.append(ratio)
                line_spacing: Optional[Union[float, str]] = round(float(np.mean(ratios)), 2) if ratios else "not measured"
            else:
                line_spacing = "not measured"

            extracted_text = " ".join(b.get("text", "").strip() for b in boxes if b.get("text", "").strip())
            if not extracted_text:
                extracted_text = "not measured"
            tracking: Optional[Union[float, str]] = "not measured"

            # Text styling detection (shadow, stroke, high contrast)
            text_styling = ["solid fill"]
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            gy, gx = np.gradient(lum)
            grad_mag = np.hypot(gx, gy)
            if np.percentile(grad_mag, 98) > 70.0:
                text_styling.append("high-contrast edge")
        else:
            hierarchy = "not measured"
            weight = "not measured"
            alignment = "not measured"
            line_spacing = "not measured"
            tracking = "not measured"
            extracted_text = "not measured"
            font_candidates = []
            text_styling = []

        return TypographyInfo(
            font_family_candidates=font_candidates,
            weight=weight,
            size_hierarchy=hierarchy,
            line_spacing=line_spacing,
            tracking=tracking,
            alignment=alignment,
            text_styling=text_styling,
            extracted_text=extracted_text,
        )


def analyze_layout_grid(arr: np.ndarray, regions: Optional[list] = None) -> Dict[str, Any]:
    """Extract design tokens, margins, column alignment, and card patterns from region geometry."""
    h, w, _ = arr.shape
    regs = regions or []
    non_bg = [r for r in regs if getattr(r, "label", "") != "background"]

    if non_bg:
        min_x = min(r.bbox[0] for r in non_bg)
        min_y = min(r.bbox[1] for r in non_bg)
        max_x = max(r.bbox[0] + r.bbox[2] for r in non_bg)
        max_y = max(r.bbox[1] + r.bbox[3] for r in non_bg)
        margins: Any = {
            "top": int(min_y),
            "bottom": int(max(0, h - max_y)),
            "left": int(min_x),
            "right": int(max(0, w - max_x)),
        }
    else:
        margins = "not measured"

    if len(non_bg) >= 2:
        xs = [r.bbox[0] for r in non_bg]
        ys = [r.bbox[1] for r in non_bg]
        x_spread = max(xs) - min(xs)
        y_spread = max(ys) - min(ys)
        if x_spread > w * 0.2:
            grid_type = f"Multi-column grid ({len(non_bg)} elements across {w}px)"
        elif y_spread > h * 0.2:
            grid_type = f"Vertical stack layout ({len(non_bg)} stacked elements)"
        else:
            grid_type = "Single-container centered layout"
        alignment_axes = "left-aligned" if np.std(xs) < 15 else ("centered" if abs(float(np.mean(xs)) - w / 2.0) < w * 0.15 else "custom grid alignment")
    elif len(non_bg) == 1:
        grid_type = "Single central focal element"
        alignment_axes = "centered"
    else:
        grid_type = "not measured"
        alignment_axes = "not measured"

    container_padding = f"{margins['left']}px / {margins['top']}px" if isinstance(margins, dict) else "not measured"
    corner_radii = "not measured"
    card_patterns = "segmented regions" if len(non_bg) > 0 else "not measured"

    return {
        "margins": margins,
        "grid_type": grid_type,
        "container_padding": container_padding,
        "corner_radii": corner_radii,
        "card_patterns": card_patterns,
        "alignment_axes": alignment_axes,
    }

