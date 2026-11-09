"""Forensic noise analysis: residual noise profile, Poisson-Gaussian correlation, and regional uniformity."""

from typing import List, Optional
import numpy as np
from scipy.ndimage import median_filter
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


class ForensicsNoiseDetector(BaseDetector):
    name = "forensics_noise"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        arr = ingest_res.rgb_array
        h, w, c = arr.shape

        if h < 32 or w < 32:
            return items

        # Convert to float luminance
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        
        # Estimate noise residual using local median filtering
        filtered = median_filter(lum, size=3)
        residual = lum - filtered
        
        noise_std = float(np.std(residual))
        noise_var = float(np.var(residual))

        # Check for hyper-smoothness (characteristic of graphic design, UI, or heavy AI smoothing)
        if noise_std < 0.6:
            items.append(
                make_evidence(
                    name="noise_residual_hypersmooth",
                    value={"noise_std": noise_std, "noise_var": noise_var},
                    direction=ProductionMethod.GRAPHIC_DESIGN.value,
                    strength=0.85,
                    explanation=f"Near-zero residual noise (std={noise_std:.2f}); consistent with vector design, digital UI, or flat 3D render.",
                )
            )
        elif noise_std > 8.0:
            items.append(
                make_evidence(
                    name="noise_residual_high",
                    value={"noise_std": noise_std},
                    direction=ProductionMethod.REAL_PHOTO.value,
                    strength=0.70,
                    explanation=f"Substantial sensor-like residual noise detected (std={noise_std:.2f}); typical of physical camera ISO gain.",
                )
            )

        # Regional noise uniformity check (only valid when meaningful noise exists)
        if noise_std >= 2.0:
            mid_h, mid_w = h // 2, w // 2
            q1 = residual[:mid_h, :mid_w]
            q2 = residual[:mid_h, mid_w:]
            q3 = residual[mid_h:, :mid_w]
            q4 = residual[mid_h:, mid_w:]

            stds = [float(np.std(q)) for q in (q1, q2, q3, q4)]
            min_std = min(stds)
            if min_std >= 1.0:
                std_ratio = max(stds) / min_std
                if std_ratio > 3.0:
                    items.append(
                        make_evidence(
                            name="noise_inconsistency_composite",
                            value={"quadrant_stds": stds, "variance_ratio": std_ratio},
                            direction=ProductionMethod.COMPOSITE.value,
                            strength=0.80,
                            explanation=f"Regional noise levels vary sharply across sectors (max/min ratio {std_ratio:.1f}x), indicating possible composite or spliced layers.",
                        )
                    )

        # Physical sensor test: natural camera noise variance correlates positively with signal luminance
        # In contrast, AI generators often exhibit synthetic or non-correlated noise
        correlation = self._lum_noise_correlation(lum, np.abs(residual))
        if correlation is not None:
            if correlation > 0.35 and noise_std >= 1.5:
                items.append(
                    make_evidence(
                        name="sensor_poisson_noise",
                        value={"lum_noise_corr": correlation},
                        direction=ProductionMethod.REAL_PHOTO.value,
                        strength=0.78,
                        explanation=f"Noise amplitude correlates positively with pixel brightness (r={correlation:.2f}), matching physical sensor Poisson-Gaussian physics.",
                    )
                )
            elif correlation < -0.15 and noise_std >= 1.5:
                items.append(
                    make_evidence(
                        name="synthetic_noise_uncorrelated",
                        value={"lum_noise_corr": correlation},
                        direction=ProductionMethod.AI_GENERATED.value,
                        strength=0.68,
                        explanation=f"Noise distribution is decoupled from physical scene luminance (r={correlation:.2f}), typical of synthetic latent diffusion outputs.",
                    )
                )

        return items

    def _lum_noise_correlation(self, lum: np.ndarray, noise_mag: np.ndarray) -> Optional[float]:
        try:
            # Subsample for speed if large
            sub_lum = lum[::4, ::4].flatten()
            sub_noise = noise_mag[::4, ::4].flatten()
            # Remove saturated extremes (pure black/white)
            valid = (sub_lum > 15) & (sub_lum < 240)
            if np.sum(valid) < 500:
                return None
            if np.std(sub_noise[valid]) < 1e-4 or np.std(sub_lum[valid]) < 1e-4:
                return None
            corr = float(np.corrcoef(sub_lum[valid], sub_noise[valid])[0, 1])
            if np.isnan(corr):
                return None
            return corr
        except Exception:
            return None
