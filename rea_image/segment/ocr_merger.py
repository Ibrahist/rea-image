"""OCR detection and text region extraction."""

from typing import List, Dict, Any
import numpy as np
from scipy.ndimage import uniform_filter, label, find_objects


class OCRTextDetector:
    """Detects text bounding boxes and extracts text content where available."""

    def detect_text_boxes(self, arr: np.ndarray) -> List[Dict[str, Any]]:
        """Detect text bounding boxes using morphological stroke density and edge contrast."""
        h, w, _ = arr.shape
        if h < 32 or w < 32:
            return []

        # Convert to grayscale luminance
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        
        # High-pass horizontal gradient to highlight character vertical strokes
        grad_x = np.abs(gray[:, 1:] - gray[:, :-1])
        grad_padded = np.pad(grad_x, ((0, 0), (0, 1)), mode="edge")

        # Local stroke variance filter (characters have high local variance)
        mean_filt = uniform_filter(grad_padded, size=(3, 7))
        var_filt = uniform_filter(grad_padded**2, size=(3, 7)) - mean_filt**2
        std_filt = np.sqrt(np.maximum(0, var_filt))

        # Threshold for text stroke candidates
        threshold = np.mean(std_filt) + 1.2 * np.std(std_filt)
        text_mask = std_filt > threshold

        # Morphological dilation: connect letters horizontally into word boxes
        from scipy.ndimage import binary_dilation
        struct = np.ones((3, 9), dtype=bool)
        dilated = binary_dilation(text_mask, structure=struct)

        # Connected component analysis
        labeled, num_features = label(dilated)
        slices = find_objects(labeled)

        text_boxes = []
        for i, slc in enumerate(slices):
            if slc is None:
                continue
            sy, sx = slc
            bx = int(sx.start)
            by = int(sy.start)
            bw = int(sx.stop - sx.start)
            bh = int(sy.stop - sy.start)

            area = bw * bh
            aspect = bw / float(bh + 1e-4)

            # Filter non-text shapes (text lines are usually wider than tall and compact)
            if 8 <= bh <= h * 0.4 and bw >= 16 and aspect >= 0.8:
                # Density check within box
                box_mask = text_mask[sy, sx]
                density = np.mean(box_mask)
                if density > 0.15:
                    text_boxes.append({
                        "bbox": [bx, by, bw, bh],
                        "confidence": float(min(0.95, density * 2.0)),
                        "text": "",  # Populated if OCR engine installed
                    })

        return text_boxes

