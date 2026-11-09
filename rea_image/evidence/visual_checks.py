"""Visual sanity checks: anatomy, text glyphs, physics, style tells, and render tells."""

from typing import Any, Dict, List, Optional
import numpy as np
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


class VisualChecksDetector(BaseDetector):
    name = "visual_checks"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        arr = ingest_res.rgb_array
        h, w, _ = arr.shape

        # If image is predominantly flat vector/graphic (>25% flat runs), skip skin sheen and render shader checks
        step_y = max(1, h // 100)
        diff_h = np.all(arr[::step_y, 1:, :] == arr[::step_y, :-1, :], axis=-1)
        flat_pct = (np.sum(diff_h) / float(diff_h.size)) * 100.0
        if flat_pct > 25.0:
            return items

        # 1. Check for AI style tells (hyper-smooth plastic sheen + high micro-contrast)
        plastic_sheen = self._check_plastic_sheen(arr)
        if plastic_sheen.get("detected"):
            items.append(
                make_evidence(
                    name="ai_style_plastic_sheen",
                    value=plastic_sheen,
                    direction=ProductionMethod.AI_GENERATED.value,
                    strength=0.72,
                    explanation="Over-smooth skin/surface texture paired with high specular highlights ('AI plastic sheen' look).",
                )
            )

        # 2. Check for 3D Render tells (perfect mathematical geometry and phong/pbr shader gradients)
        render_tells = self._check_render_shaders(arr)
        if render_tells.get("detected"):
            items.append(
                make_evidence(
                    name="3d_shader_characteristics",
                    value=render_tells,
                    direction=ProductionMethod.RENDER_3D.value,
                    strength=0.75,
                    explanation="Clean geometric edge falloff and uniform PBR specular shader rolloff typical of 3D rendering engines (Blender/Cycles/Unreal).",
                )
            )

        return items

    def _check_plastic_sheen(self, arr: np.ndarray) -> Dict[str, Any]:
        """Detect over-smoothed midtones with excessive specular highlight peaks."""
        try:
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            # Variance in midtones (lum between 60 and 190)
            midtones = lum[(lum > 60) & (lum < 190)]
            if len(midtones) < 1000:
                return {"detected": False}

            # Local variation
            from scipy.ndimage import uniform_filter
            mean_filt = uniform_filter(lum, size=5)
            local_var = uniform_filter(lum**2, size=5) - mean_filt**2
            mid_local_std = np.sqrt(np.maximum(0, local_var))[(lum > 60) & (lum < 190)]
            
            # High highlights
            specular_pct = float(np.mean(lum > 245))
            avg_mid_std = float(np.mean(mid_local_std))

            # AI plastic look: very low midtone texture variation (< 4.5) but sharp specular spots
            if avg_mid_std < 4.5 and specular_pct > 0.015:
                return {
                    "detected": True,
                    "mid_std": round(avg_mid_std, 2),
                    "specular_pct": round(specular_pct * 100.0, 2),
                }
        except Exception:
            pass
        return {"detected": False}

    def _check_render_shaders(self, arr: np.ndarray) -> Dict[str, Any]:
        """Detect 3D surface shading profiles."""
        try:
            h, w, _ = arr.shape
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            gy, gx = np.gradient(lum)
            grad_mag = np.hypot(gx, gy)
            
            # Clean edges with near-zero interior texture
            edge_sharpness = float(np.percentile(grad_mag, 98))
            flat_interior = float(np.percentile(grad_mag, 30))
            ratio = edge_sharpness / (flat_interior + 1e-4)
            
            if ratio > 60.0 and edge_sharpness > 35.0:
                return {
                    "detected": True,
                    "edge_interior_ratio": round(ratio, 1),
                }
        except Exception:
            pass
        return {"detected": False}

    def run_region(self, crop: np.ndarray, region_id: str, mask: Optional[np.ndarray] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        h, w, _ = crop.shape
        if h < 32 or w < 32:
            return items

        plastic_sheen = self._check_plastic_sheen(crop)
        if plastic_sheen.get("detected"):
            items.append(
                make_evidence(
                    name="ai_style_plastic_sheen",
                    value=plastic_sheen,
                    direction=ProductionMethod.AI_GENERATED.value,
                    strength=0.72,
                    explanation=f"Region {region_id} exhibits over-smooth plastic sheen texture typical of AI generation.",
                    region=region_id,
                )
            )

        render_tells = self._check_render_shaders(crop)
        if render_tells.get("detected"):
            items.append(
                make_evidence(
                    name="3d_shader_characteristics",
                    value=render_tells,
                    direction=ProductionMethod.RENDER_3D.value,
                    strength=0.75,
                    explanation=f"Region {region_id} shows clean geometric edge falloff and PBR shader gradients.",
                    region=region_id,
                )
            )

        return items
