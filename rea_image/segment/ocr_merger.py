"""OCR detection and text region extraction."""

from typing import List, Dict, Any
import numpy as np
from scipy.ndimage import uniform_filter, label, find_objects


class OCRTextDetector:
    """Detects text bounding boxes and extracts verified text content where available."""

    def detect_text_boxes(self, arr: np.ndarray) -> List[Dict[str, Any]]:
        """Detect text bounding boxes using morphological stroke density, edge coherence, and OCR validation."""
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

        # If image has massive noisy components (> 50), it is high-frequency texture, not clean text lines
        is_high_texture = num_features > 40

        candidate_boxes = []
        for slc in slices:
            if slc is None:
                continue
            sy, sx = slc
            bx = int(sx.start)
            by = int(sy.start)
            bw = int(sx.stop - sx.start)
            bh = int(sy.stop - sy.start)

            aspect = bw / float(bh + 1e-4)

            # Filter non-text shapes (text lines are usually wider than tall and compact)
            min_aspect = 1.2 if is_high_texture else 0.8
            if 8 <= bh <= h * 0.4 and bw >= 16 and aspect >= min_aspect:
                # Density check within box
                box_mask = text_mask[sy, sx]
                density = float(np.mean(box_mask))
                if density > 0.18:
                    # Check edge orientation coherence in patch
                    patch_gray = gray[sy, sx]
                    gy, gx = np.gradient(patch_gray)
                    gx_energy = float(np.sum(np.abs(gx)))
                    gy_energy = float(np.sum(np.abs(gy)))
                    # Text character strokes exhibit strong horizontal gradient energy from vertical stems
                    coherence = abs(gx_energy - gy_energy) / (gx_energy + gy_energy + 1e-5)
                    
                    # In high-texture images, reject isotropic/low-coherence patches (noise, feathers)
                    if is_high_texture and coherence < 0.15:
                        continue

                    candidate_boxes.append({
                        "bbox": [bx, by, bw, bh],
                        "confidence": float(min(0.95, density * 2.0)),
                        "coherence": coherence,
                        "text": "",
                        "words": [],
                    })

        # Cap candidate boxes to top 10 most plausible candidates
        candidate_boxes = sorted(
            candidate_boxes,
            key=lambda b: (b["confidence"] * (b["bbox"][2] / (b["bbox"][3] + 1e-4))),
            reverse=True,
        )[:10]

        # Attempt OCR text extraction if pytesseract is available
        confirmed_boxes = []
        has_ocr_engine = False
        try:
            import pytesseract
            from PIL import Image
            from pytesseract import Output
            pil_img = Image.fromarray(arr)

            for box in candidate_boxes:
                bx, by, bw, bh = box["bbox"]
                crop = pil_img.crop((bx, by, bx + bw, by + bh))

                # Use image_to_data to inspect confidence and word-level criteria
                data = pytesseract.image_to_data(crop, output_type=Output.DICT, config="--psm 6")
                has_ocr_engine = True

                valid_words = []
                for word, conf in zip(data.get("text", []), data.get("conf", [])):
                    word_str = str(word).strip()
                    if not word_str:
                        continue
                    try:
                        c_val = float(conf)
                    except (ValueError, TypeError):
                        c_val = -1.0

                    # Stricter confidence threshold: >= 60
                    if c_val < 60.0:
                        continue

                    # Require at least 3 alphanumeric characters
                    alnums = [c for c in word_str if c.isalnum()]
                    if len(alnums) < 3:
                        continue

                    # Require dictionary-like letter ratio (avoid random punctuation noise like "/-")
                    letters = [c for c in word_str if c.isalpha()]
                    if len(letters) / float(len(word_str)) < 0.6:
                        continue

                    valid_words.append(word_str)

                if valid_words:
                    box["text"] = " ".join(valid_words)
                    box["words"] = valid_words
                    confirmed_boxes.append(box)

        except Exception:
            # Pytesseract not installed or tesseract binary unavailable
            has_ocr_engine = False

        if has_ocr_engine:
            return confirmed_boxes

        # If no OCR engine is available, return candidates with empty text/words
        return candidate_boxes
