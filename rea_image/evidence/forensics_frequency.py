"""Frequency domain forensics: 2D FFT spectral peaks, upsampler artifacts, and radial falloff."""

from typing import Any, Dict, List, Optional
import numpy as np
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


class ForensicsFrequencyDetector(BaseDetector):
    name = "forensics_frequency"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        img = ingest_res.rgb_image
        arr = ingest_res.rgb_array
        h, w, _ = arr.shape

        if h < 64 or w < 64:
            return items

        # Convert to grayscale float
        gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
        
        # Center crop to power of 2 for clean FFT
        crop_size = min(512, 1 << int(np.log2(min(h, w))))
        start_y = (h - crop_size) // 2
        start_x = (w - crop_size) // 2
        cropped = gray[start_y : start_y + crop_size, start_x : start_x + crop_size]

        # Apply Hanning window to prevent edge boundary spectral leakage
        win_y = np.hanning(crop_size)
        win_x = np.hanning(crop_size)
        window_2d = np.outer(win_y, win_x)
        windowed = (cropped - np.mean(cropped)) * window_2d

        # 2D FFT
        fft = np.fft.fft2(windowed)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)

        # 1. Detect periodic spectral peaks (artifacts of transposed conv / neural upscalers)
        peaks = self._detect_spectral_peaks(magnitude, crop_size)
        if peaks.get("has_regular_peaks"):
            peak_count = peaks.get("peak_count", 0)
            peak_ratio = peaks.get("max_peak_ratio", 0.0)
            
            # Check for corroborating generator metadata or chunks in image info
            info_str = str(getattr(img, "info", {})).lower()
            is_corroborated = any(k in info_str for k in ("parameters", "prompt", "workflow", "comfyui", "c2pa", "midjourney"))

            # Cap strength at <= 0.4 unless corroborated by hard traces
            strength = 0.75 if is_corroborated else 0.35

            items.append(
                make_evidence(
                    name="spectral_peaks_upscaler",
                    value=peaks,
                    direction=ProductionMethod.AI_GENERATED.value,
                    strength=strength,
                    explanation=(
                        f"2D FFT shows periodic spectral peaks ({peak_count} harmonic spikes, ratio={peak_ratio:.1f}). "
                        f"{'Corroborated by generative metadata.' if is_corroborated else 'Uncorroborated signal; may stem from resizing or compression ringing.'}"
                    ),
                )
            )

        # 2. Radial frequency falloff slope (natural images obey 1/f^alpha, alpha ~ 2.0)
        alpha = self._compute_radial_falloff(magnitude, crop_size)
        if alpha is not None:
            if 1.6 <= alpha <= 2.3:
                items.append(
                    make_evidence(
                        name="natural_frequency_falloff",
                        value={"alpha": alpha},
                        direction=ProductionMethod.REAL_PHOTO.value,
                        strength=0.75,
                        explanation=f"Radial frequency power spectrum follows natural scene statistics (1/f^{alpha:.2f}), strongly characteristic of optical photographic capture.",
                    )
                )
            elif alpha < 1.3:
                items.append(
                    make_evidence(
                        name="excess_high_frequency_energy",
                        value={"alpha": alpha},
                        direction=ProductionMethod.GRAPHIC_DESIGN.value,
                        strength=0.74,
                        explanation=f"Shallow spectral slope (alpha={alpha:.2f}) indicates excess high-frequency energy typical of vector sharp edges or digital UI.",
                    )
                )

        return items

    def _detect_spectral_peaks(self, magnitude: np.ndarray, size: int) -> Dict[str, Any]:
        """Look for isolated sharp peaks in the middle-to-high frequency bands."""
        center = size // 2
        # Exclude low frequency DC circle (radius 16)
        y, x = np.ogrid[:size, :size]
        r = np.hypot(x - center, y - center)
        mask = (r >= 20) & (r < center - 10)

        band_vals = magnitude[mask]
        mean_val = np.mean(band_vals)
        std_val = np.std(band_vals)

        # Peaks exceeding 8 standard deviations with high peak-to-mean ratio
        threshold = mean_val + 8.0 * std_val
        peaks = np.argwhere((magnitude > threshold) & mask)

        peak_count = len(peaks)
        max_ratio = float(np.max(band_vals) / (mean_val + 1e-5))
        # Periodic upsamplers produce harmonic peaks (e.g. 4 to 250 peaks) with high peak-to-mean ratio.
        # Massive peak counts (e.g. > 350 peaks like the 574 in textured hen photos) or low ratio
        # stem from broadband texture noise or general JPEG compression ringing rather than generator upsamplers.
        has_regular = bool(4 <= peak_count <= 250 and max_ratio >= 10.0)

        return {
            "has_regular_peaks": has_regular,
            "peak_count": peak_count,
            "max_peak_ratio": max_ratio,
        }

    def _compute_radial_falloff(self, magnitude: np.ndarray, size: int) -> Optional[float]:
        """Compute the power-law exponent alpha from radial average of FFT."""
        try:
            center = size // 2
            y, x = np.ogrid[:size, :size]
            r = np.hypot(x - center, y - center).astype(np.int32)
            max_r = center - 5

            # Compute radial average for r in [5, max_r]
            radial_profile = []
            frequencies = []
            for radius in range(5, max_r):
                vals = magnitude[r == radius]
                if len(vals) > 0:
                    radial_profile.append(float(np.mean(vals)))
                    frequencies.append(radius)

            if len(frequencies) < 20:
                return None

            log_f = np.log(np.array(frequencies, dtype=np.float32))
            log_p = np.log(np.array(radial_profile, dtype=np.float32) + 1e-6)

            # Fit line: log_p = -alpha * log_f + c
            poly = np.polyfit(log_f, log_p, 1)
            alpha = float(-poly[0])
            return alpha
        except Exception:
            return None

    def run_region(self, crop: np.ndarray, region_id: str, mask: Optional[np.ndarray] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        h, w, _ = crop.shape
        if min(h, w) < 64:
            return items

        gray = (0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]).astype(np.float32)
        crop_size = min(256, 1 << int(np.log2(min(h, w))))
        start_y = (h - crop_size) // 2
        start_x = (w - crop_size) // 2
        c_gray = gray[start_y : start_y + crop_size, start_x : start_x + crop_size]

        win_y = np.hanning(crop_size)
        win_x = np.hanning(crop_size)
        windowed = (c_gray - np.mean(c_gray)) * np.outer(win_y, win_x)

        fft = np.fft.fftshift(np.fft.fft2(windowed))
        mag = np.abs(fft)

        alpha = self._compute_radial_falloff(mag, crop_size)
        if alpha is not None:
            if 1.6 <= alpha <= 2.3:
                items.append(
                    make_evidence(
                        name="natural_frequency_falloff",
                        value={"alpha": alpha},
                        direction=ProductionMethod.REAL_PHOTO.value,
                        strength=0.75,
                        explanation=f"Region {region_id} power spectrum follows natural scene statistics (1/f^{alpha:.2f}).",
                        region=region_id,
                    )
                )
            elif alpha < 1.3:
                items.append(
                    make_evidence(
                        name="excess_high_frequency_energy",
                        value={"alpha": alpha},
                        direction=ProductionMethod.GRAPHIC_DESIGN.value,
                        strength=0.74,
                        explanation=f"Region {region_id} shallow spectral slope (alpha={alpha:.2f}) indicates excess high-frequency energy typical of vector sharp edges.",
                        region=region_id,
                    )
                )
        return items
