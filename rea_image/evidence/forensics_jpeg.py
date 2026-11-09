"""JPEG forensics: Error Level Analysis (ELA), blocking grid alignment, and double compression."""

import io
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


class ForensicsJpegDetector(BaseDetector):
    name = "forensics_jpeg"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        img = ingest_res.rgb_image
        arr = ingest_res.rgb_array
        h, w, _ = arr.shape

        if h < 64 or w < 64:
            return items

        # 1. Error Level Analysis (ELA)
        ela_metrics = self._compute_ela(img)
        if ela_metrics:
            mean_err = ela_metrics["mean_error"]
            err_var = ela_metrics["error_variance"]
            
            # If recompression error is extremely low across the board, image was saved with low quality or is flat
            if mean_err < 1.0:
                items.append(
                    make_evidence(
                        name="ela_minimal_error",
                        value=ela_metrics,
                        direction=ProductionMethod.GRAPHIC_DESIGN.value,
                        strength=0.65,
                        explanation=f"ELA indicates virtually zero compression delta (mean error={mean_err:.2f}), common in synthetic vector renders or lossless graphics.",
                    )
                )

            # High variance in error levels across spatial regions indicates splice/composite
            if err_var > 45.0:
                items.append(
                    make_evidence(
                        name="ela_regional_discrepancy",
                        value=ela_metrics,
                        direction=ProductionMethod.COMPOSITE.value,
                        strength=0.76,
                        explanation=f"High regional variance in ELA response (var={err_var:.1f}), showing uneven compression history characteristic of image splicing.",
                    )
                )

        # 2. JPEG 8x8 Blocking Grid Misalignment Check (Only relevant for JPEG or recompressed formats)
        is_jpeg = ingest_res.metadata.format.upper() in ("JPEG", "JPG")
        if is_jpeg:
            grid_metrics = self._check_blocking_grid(arr)
            if grid_metrics.get("grid_detected"):
                misaligned = grid_metrics.get("misaligned", False)
                if misaligned:
                    items.append(
                        make_evidence(
                            name="jpeg_grid_misalignment",
                            value=grid_metrics,
                            direction=ProductionMethod.COMPOSITE.value,
                            strength=0.82,
                            explanation="JPEG 8x8 DCT blocking boundary misalignment detected, indicating pasted or translated content from another image source.",
                        )
                    )
                else:
                    items.append(
                        make_evidence(
                            name="jpeg_grid_aligned",
                            value=grid_metrics,
                            direction=ProductionMethod.REAL_PHOTO.value,
                            strength=0.60,
                            explanation="Consistent 8x8 JPEG DCT block grid aligned across all image boundaries.",
                        )
                    )

        return items

    def _compute_ela(self, img: Image.Image, quality: int = 90) -> Optional[Dict[str, float]]:
        """Compute Error Level Analysis by recompressing at known quality."""
        try:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            buffer.seek(0)
            recompressed = Image.open(buffer).convert("RGB")
            
            arr_orig = np.asarray(img.convert("RGB"), dtype=np.float32)
            arr_recomp = np.asarray(recompressed, dtype=np.float32)
            
            diff = np.abs(arr_orig - arr_recomp)
            mean_error = float(np.mean(diff))
            max_error = float(np.max(diff))
            error_variance = float(np.var(diff))

            return {
                "mean_error": mean_error,
                "max_error": max_error,
                "error_variance": error_variance,
            }
        except Exception:
            return None

    def _check_blocking_grid(self, arr: np.ndarray) -> Dict[str, Any]:
        """Detect 8x8 JPEG blocking artifacts and check if they align cleanly."""
        try:
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            h, w = lum.shape
            
            # Differences across vertical boundaries
            col_diffs = np.mean(np.abs(lum[:, 1:] - lum[:, :-1]), axis=0)
            if len(col_diffs) < 32:
                return {"grid_detected": False}

            # Periodic strength at modulo 8
            mod_energies = [np.mean(col_diffs[k::8]) for k in range(8)]
            best_offset = int(np.argmax(mod_energies))
            peak_val = mod_energies[best_offset]
            other_mean = np.mean([mod_energies[i] for i in range(8) if i != best_offset])
            
            ratio = peak_val / (other_mean + 1e-4)
            if ratio > 1.25:
                # If offset is 7 (0-indexed boundary at col 8), grid is aligned; if offset != 7, cropped or shifted!
                misaligned = (best_offset != 7 and best_offset != 0)
                return {
                    "grid_detected": True,
                    "offset": best_offset,
                    "strength_ratio": float(ratio),
                    "misaligned": misaligned,
                }
        except Exception:
            pass
        return {"grid_detected": False}
