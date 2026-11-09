"""Area-weighted whole-image judgment aggregator and verdict summary generator."""

from collections import defaultdict
from typing import Dict, List, Optional
from rea_image.schemas import MethodBreakdownItem, ProductionMethod, RegionAnalysis, Verdict
from rea_image.judge.style_matcher import estimate_ai_model_family


class VerdictAggregator:
    """Aggregates per-region judgments into a unified whole-image verdict."""

    def aggregate(
        self,
        regions: List[RegionAnalysis],
        global_evidence: list,
        aspect_ratio: str,
        width: int,
        height: int,
        color_grade: Optional[dict] = None,
    ) -> Tuple[Verdict, str]:
        """Aggregate regional classifications weighted by area percentage.
        
        Returns (Verdict, what_would_change_verdict_string).
        """
        area_by_method: Dict[str, float] = defaultdict(float)

        for r in regions:
            area_by_method[r.method] += r.area_pct

        # Sort methods by area percentage descending
        sorted_methods = sorted(area_by_method.items(), key=lambda x: x[1], reverse=True)
        breakdown = [
            MethodBreakdownItem(method=m, area_pct=round(pct, 1))
            for m, pct in sorted_methods
            if pct > 0.05
        ]

        if not breakdown:
            breakdown = [MethodBreakdownItem(method=ProductionMethod.REAL_PHOTO.value, area_pct=100.0)]

        # Determine composite status
        dominant_method, dominant_pct = sorted_methods[0]
        has_secondary = len(sorted_methods) > 1 and sorted_methods[1][1] >= 15.0

        # Style family for AI components
        has_ai = any("ai-generated" in m.lower() for m, _ in sorted_methods if _ >= 10.0)
        ai_style = ""
        if has_ai:
            style_info = estimate_ai_model_family(global_evidence, width, height, color_grade)
            ai_style = f"{style_info['family']}; "

        # Summary line
        if has_secondary:
            sec_method, sec_pct = sorted_methods[1]
            summary = (
                f"{dominant_method} {dominant_pct:.0f}% + {sec_method} {sec_pct:.0f}%; "
                f"{ai_style}{aspect_ratio}; confidence {regions[0].confidence}"
            )
        else:
            summary = f"{dominant_method} {dominant_pct:.0f}%; {ai_style}{aspect_ratio}; confidence {regions[0].confidence}"

        # What evidence would change the verdict
        if "ai-generated" in dominant_method.lower():
            change_statement = (
                "What would change this verdict: A cryptographically signed C2PA camera manifest, "
                "original camera RAW (CR3/NEF/ARW/DNG) files with full continuous Bayer sensor noise, "
                "or verifiable in-camera EXIF timestamps would refute the AI-generated finding."
            )
        elif "real photograph" in dominant_method.lower():
            change_statement = (
                "What would change this verdict: Discovery of latent diffusion frequency spikes, "
                "generative AI PNG text chunks (A1111/ComfyUI), or anatomical/perspective inconsistencies "
                "would reclassify this image as AI-generated."
            )
        else:
            change_statement = (
                "What would change this verdict: Presence of continuous camera sensor noise or "
                "photographic EXIF metadata would alter the graphic/render classification."
            )

        verdict = Verdict(
            summary=summary,
            confidence=regions[0].confidence if regions else "medium",
            method_breakdown=breakdown,
        )

        return verdict, change_statement

