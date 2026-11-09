"""Flat-region test, vector runs, resolution signatures, and compression degradation penalty."""

from typing import Any, Dict, List, Optional
import numpy as np
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


KNOWN_GENERATOR_RESOLUTIONS = {
    (512, 512): "Stable Diffusion v1.5 base",
    (768, 768): "Stable Diffusion v2 base",
    (1024, 1024): "SDXL / Midjourney / FLUX.1 base 1:1",
    (896, 1152): "SDXL standard bucket (3:4)",
    (1152, 896): "SDXL standard bucket (4:3)",
    (832, 1216): "SDXL standard bucket (9:16 approx)",
    (1216, 832): "SDXL standard bucket (16:9 approx)",
    (1024, 1792): "DALL-E 3 vertical standard",
    (1792, 1024): "DALL-E 3 horizontal standard",
}


class ForensicsFlatDetector(BaseDetector):
    name = "forensics_flat"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        arr = ingest_res.rgb_array
        h, w, c = arr.shape
        metadata = ingest_res.metadata

        # 1. Flat Region & Exact Color Run Analysis (Vector vs Photo test)
        flat_stats = self._analyze_flat_runs(arr)
        flat_pct = flat_stats["flat_pixel_percentage"]
        unique_ratio = flat_stats["unique_color_ratio"]
        unique_colors = flat_stats.get("unique_colors_sampled", 9999)

        is_vector = (flat_pct > 35.0 and unique_ratio < 0.03) or (flat_pct > 15.0 and unique_ratio < 0.01) or (unique_colors < 256)
        if is_vector:
            items.append(
                make_evidence(
                    name="flat_color_runs",
                    value=flat_stats,
                    direction=ProductionMethod.GRAPHIC_DESIGN.value,
                    strength=0.85,
                    explanation=f"High proportion of exact flat color runs ({flat_pct:.1f}% flat pixels) and low unique color entropy; characteristic of vector design, infographic, or UI.",
                )
            )
        elif unique_ratio > 0.02 or flat_pct < 10.0:
            items.append(
                make_evidence(
                    name="continuous_natural_gradients",
                    value=flat_stats,
                    direction=ProductionMethod.REAL_PHOTO.value,
                    strength=0.75,
                    explanation=f"Continuous chromatic variation with rich unique color entropy ({unique_ratio*100:.1f}% unique); consistent with optical photographic capture.",
                )
            )

        # 2. Generator Resolution Signatures
        res_key = (w, h)
        if res_key in KNOWN_GENERATOR_RESOLUTIONS:
            gen_name = KNOWN_GENERATOR_RESOLUTIONS[res_key]
            items.append(
                make_evidence(
                    name="generator_resolution_signature",
                    value={"dimensions": f"{w}x{h}", "matched_bucket": gen_name},
                    direction=ProductionMethod.AI_GENERATED.value,
                    strength=0.75,
                    explanation=f"Exact pixel dimensions ({w}x{h}) match standard AI generator output bucket: {gen_name}.",
                )
            )

        # 3. Compression & Degradation Assessment
        degradation = self._assess_degradation(arr, metadata)
        if degradation["is_degraded"]:
            items.append(
                make_evidence(
                    name="compression_degradation_penalty",
                    value=degradation,
                    direction="neutral",
                    strength=degradation["penalty_score"],
                    explanation=degradation["explanation"],
                )
            )

        return items

    def _analyze_flat_runs(self, arr: np.ndarray) -> Dict[str, float]:
        """Compute horizontal flat runs (consecutive identical RGB pixels)."""
        h, w, _ = arr.shape
        # Subsample rows for performance on large images
        step_y = max(1, h // 200)
        sampled = arr[::step_y, :, :]
        
        # Horizontal diff
        diff_h = np.all(sampled[:, 1:, :] == sampled[:, :-1, :], axis=-1)
        flat_pixels = int(np.sum(diff_h))
        total_tested = int(diff_h.size)
        flat_pct = (flat_pixels / (total_tested + 1e-5)) * 100.0

        # Unique colors in sample
        flat_colors = sampled.reshape(-1, 3)
        # Pack to 24-bit int for fast unique counting
        packed = (flat_colors[:, 0].astype(np.uint32) << 16) | (flat_colors[:, 1].astype(np.uint32) << 8) | flat_colors[:, 2].astype(np.uint32)
        unique_colors = len(np.unique(packed))
        unique_ratio = unique_colors / float(len(packed))

        return {
            "flat_pixel_percentage": float(flat_pct),
            "unique_color_ratio": float(unique_ratio),
            "unique_colors_sampled": int(unique_colors),
        }

    def _assess_degradation(self, arr: np.ndarray, metadata) -> Dict[str, Any]:
        """Determine if image compression/resizing degrades forensic reliability."""
        h, w, _ = arr.shape
        reasons = []
        penalty = 0.0

        if min(h, w) < 480:
            reasons.append("Low resolution (< 480px) restricts fine forensic frequency inspection")
            penalty += 0.35

        # Check for heavy JPEG blocking
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        if w >= 64:
            col_diffs = np.abs(lum[:, 1:] - lum[:, :-1])
            block_boundary_energy = np.mean(col_diffs[:, 7::8])
            non_boundary_energy = np.mean(col_diffs[:, 3::8])
            if non_boundary_energy > 0:
                block_ratio = block_boundary_energy / non_boundary_energy
                if block_ratio > 1.4:
                    reasons.append("Heavy JPEG compression blocking artifacts observed; fine noise signals attenuated")
                    penalty += 0.40

        is_degraded = len(reasons) > 0
        penalty_clamped = min(0.70, penalty)
        explanation = "; ".join(reasons) if reasons else "No severe compression degradation detected."

        return {
            "is_degraded": is_degraded,
            "penalty_score": float(penalty_clamped),
            "reasons": reasons,
            "explanation": explanation,
        }

    def run_region(self, crop: np.ndarray, region_id: str, mask: Optional[np.ndarray] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        if crop.shape[0] < 16 or crop.shape[1] < 16:
            return items

        flat_stats = self._analyze_flat_runs(crop)
        flat_pct = flat_stats["flat_pixel_percentage"]
        unique_ratio = flat_stats["unique_color_ratio"]
        unique_colors = flat_stats.get("unique_colors_sampled", 9999)

        is_vector = (flat_pct > 35.0 and unique_ratio < 0.03) or (flat_pct > 15.0 and unique_ratio < 0.01) or (unique_colors < 256)
        if is_vector:
            items.append(
                make_evidence(
                    name="flat_color_runs",
                    value=flat_stats,
                    direction=ProductionMethod.GRAPHIC_DESIGN.value,
                    strength=0.88,
                    explanation=f"Region {region_id} contains exact flat color runs ({flat_pct:.1f}% flat) and low color entropy; characteristic of vector design.",
                    region=region_id,
                )
            )
        elif unique_ratio > 0.02 or flat_pct < 10.0:
            items.append(
                make_evidence(
                    name="continuous_natural_gradients",
                    value=flat_stats,
                    direction=ProductionMethod.REAL_PHOTO.value,
                    strength=0.78,
                    explanation=f"Region {region_id} shows continuous chromatic variation ({unique_ratio*100:.1f}% unique colors); consistent with optical photo capture.",
                    region=region_id,
                )
            )
        return items
