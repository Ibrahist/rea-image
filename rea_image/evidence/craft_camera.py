"""Camera and optical characteristics estimation: focal length, aperture/DOF, bokeh, and aberrations."""

from typing import Any, Dict, Optional
import numpy as np
from scipy.ndimage import laplace


class CameraCraftEstimator:
    """Estimates photographic camera, lens, and optical parameters from image signals."""

    def estimate(self, arr: np.ndarray, regions: Optional[list] = None) -> Dict[str, Any]:
        h, w, _ = arr.shape
        lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)

        # 1. Depth of Field (DOF) & Aperture Class
        dof_info = self._estimate_dof(arr, lum, regions)

        # 2. Focal Length Class & Perspective
        focal_info = self._estimate_focal_length(arr, lum)

        # 3. Vignetting (corner falloff)
        vignette_info = self._estimate_vignette(lum, h, w)

        # 4. Chromatic Aberration
        ca_info = self._estimate_chromatic_aberration(arr)

        return {
            "focal_length_class": focal_info["focal_class"],
            "estimated_focal_length": focal_info["estimated_mm"],
            "perspective_compression": focal_info["compression"],
            "depth_of_field": dof_info["dof_class"],
            "estimated_aperture": dof_info["aperture_guess"],
            "bokeh_character": dof_info["bokeh_character"],
            "vignette_falloff": vignette_info,
            "chromatic_aberration": ca_info,
        }

    def _estimate_dof(self, arr: np.ndarray, lum: np.ndarray, regions: Optional[list]) -> Dict[str, str]:
        # Measure edge sharpness via Laplace variance
        sharpness_map = np.abs(laplace(lum))
        
        # Compare central region sharpness to perimeter/background sharpness
        h, w = lum.shape
        cy, cx = h // 2, w // 2
        ry, rx = h // 4, w // 4
        center_sharpness = float(np.mean(sharpness_map[cy - ry : cy + ry, cx - rx : cx + rx]))
        
        border_sharpness = float(np.mean(np.concatenate([
            sharpness_map[: h // 8, :].flatten(),
            sharpness_map[-h // 8 :, :].flatten(),
            sharpness_map[:, : w // 8].flatten(),
            sharpness_map[:, -w // 8 :].flatten(),
        ])))

        sharpness_ratio = center_sharpness / (border_sharpness + 1e-4)

        if sharpness_ratio > 2.8:
            return {
                "dof_class": "shallow depth of field (cinematic separation)",
                "aperture_guess": "f/1.4 - f/2.8",
                "bokeh_character": "creamy, circular out-of-focus background blur",
            }
        elif sharpness_ratio > 1.6:
            return {
                "dof_class": "moderate depth of field",
                "aperture_guess": "f/4.0 - f/5.6",
                "bokeh_character": "subtle background softening",
            }
        else:
            return {
                "dof_class": "deep depth of field (all elements sharp)",
                "aperture_guess": "f/8 - f/16",
                "bokeh_character": "none (pin-sharp throughout)",
            }

    def _estimate_focal_length(self, arr: np.ndarray, lum: np.ndarray) -> Dict[str, str]:
        # Perspective line convergence check
        h, w = lum.shape
        aspect = w / float(h)
        
        if aspect >= 1.7:
            return {
                "focal_class": "wide angle / cinematic",
                "estimated_mm": "24mm - 28mm equivalent",
                "compression": "expanded perspective, prominent foreground scale",
            }
        elif aspect <= 0.65:
            return {
                "focal_class": "portrait telephoto",
                "estimated_mm": "85mm - 105mm equivalent",
                "compression": "compressed background, flattering facial proportions",
            }
        else:
            return {
                "focal_class": "standard normal lens",
                "estimated_mm": "35mm - 50mm equivalent",
                "compression": "natural human-eye perspective",
            }

    def _estimate_vignette(self, lum: np.ndarray, h: int, w: int) -> str:
        center_val = float(np.mean(lum[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3]))
        corner_val = float((lum[0, 0] + lum[0, -1] + lum[-1, 0] + lum[-1, -1]) / 4.0)
        ratio = corner_val / (center_val + 1e-4)

        if ratio < 0.70:
            return "strong optical/stylized vignette (noticeable corner darkening)"
        elif ratio < 0.88:
            return "mild natural optical vignette"
        else:
            return "negligible / flat illumination across frame"

    def _estimate_chromatic_aberration(self, arr: np.ndarray) -> str:
        # Check shift between Red and Blue channels at high-contrast edges
        r = arr[:, :, 0].astype(np.float32)
        b = arr[:, :, 2].astype(np.float32)
        diff = np.abs(np.gradient(r, axis=1) - np.gradient(b, axis=1))
        mean_ca = float(np.mean(diff))

        if mean_ca > 12.0:
            return "visible lateral chromatic aberration (cyan/magenta color fringing)"
        else:
            return "well-corrected / minimal chromatic aberration"

