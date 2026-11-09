"""Classical offline segmentation engine using color clustering, contours, and edge saliency."""

from typing import List
import numpy as np
from scipy.ndimage import label, find_objects, gaussian_filter
from rea_image.segment.region import SegmentRegion
from rea_image.segment.ocr_merger import OCRTextDetector


class ClassicalSegmenter:
    """Deterministic offline segmenter that splits images into semantic regions."""

    def __init__(self, max_regions: int = 6):
        self.max_regions = max_regions
        self.ocr_detector = OCRTextDetector()
        self.confirmed_text_boxes: List[dict] = []

    def segment(self, arr: np.ndarray) -> List[SegmentRegion]:
        h, w, _ = arr.shape
        total_pixels = h * w
        assigned_mask = np.zeros((h, w), dtype=bool)
        regions: List[SegmentRegion] = []
        region_counter = 0
        self.confirmed_text_boxes = []

        # 1. First extract text boxes from OCR locator (require confirmed OCR text)
        text_boxes = self.ocr_detector.detect_text_boxes(arr)
        # Sort text boxes by area descending
        text_boxes = sorted(text_boxes, key=lambda b: b["bbox"][2] * b["bbox"][3], reverse=True)[:3]

        for tb in text_boxes:
            # Require confirmed OCR text before labeling any region as text_block
            text_str = tb.get("text", "").strip()
            words = tb.get("words", [])
            alnums = [c for c in text_str if c.isalnum()]
            if not text_str or not words or len(alnums) < 3:
                continue

            self.confirmed_text_boxes.append(tb)

            bx, by, bw, bh = tb["bbox"]
            tmask = np.zeros((h, w), dtype=bool)
            tmask[by : by + bh, bx : bx + bw] = True
            # Mask out already assigned
            tmask = tmask & (~assigned_mask)
            box_area = int(np.sum(tmask))
            if box_area > total_pixels * 0.005:  # at least 0.5% of image
                assigned_mask |= tmask
                area_pct = (box_area / float(total_pixels)) * 100.0
                regions.append(
                    SegmentRegion(
                        id=f"region_{region_counter}",
                        label="text_block",
                        bbox=[bx, by, bw, bh],
                        mask=tmask,
                        area_pct=round(area_pct, 2),
                    )
                )
                region_counter += 1

        # 2. Segment remaining image via color quantization & spatial clustering
        # Subsample array for fast color quantization
        smooth = gaussian_filter(arr.astype(np.float32), sigma=(2, 2, 0))
        # Quantize colors to 4 levels per channel (64 color bins)
        quantized = (smooth // 64).astype(np.int32)
        color_idx = quantized[:, :, 0] * 16 + quantized[:, :, 1] * 4 + quantized[:, :, 2]
        
        # Determine background color: most frequent color along the outer 4 border edges
        border_pixels = np.concatenate([
            color_idx[0, :],
            color_idx[-1, :],
            color_idx[:, 0],
            color_idx[:, -1],
        ])
        counts = np.bincount(border_pixels)
        bg_color = int(np.argmax(counts))

        # Background mask
        bg_mask = (color_idx == bg_color) & (~assigned_mask)
        # Also clean up morphological holes in background
        from scipy.ndimage import binary_dilation, binary_erosion
        bg_cleaned = binary_dilation(bg_mask, iterations=2)
        bg_cleaned = binary_erosion(bg_cleaned, iterations=2) & (~assigned_mask)
        
        bg_area = int(np.sum(bg_cleaned))
        if bg_area > total_pixels * 0.05:
            assigned_mask |= bg_cleaned
            # Compute bbox of background
            ys, xs = np.where(bg_cleaned)
            bx, by = int(np.min(xs)), int(np.min(ys))
            bw, bh = int(np.max(xs) - bx + 1), int(np.max(ys) - by + 1)
            area_pct = (bg_area / float(total_pixels)) * 100.0
            regions.append(
                SegmentRegion(
                    id=f"region_{region_counter}",
                    label="background",
                    bbox=[bx, by, bw, bh],
                    mask=bg_cleaned,
                    area_pct=round(area_pct, 2),
                )
            )
            region_counter += 1

        # 3. Connected components on the remaining foreground pixels
        remaining = ~assigned_mask
        labeled, num_features = label(remaining)
        slices = find_objects(labeled)

        # Sort candidate components by pixel area
        comps = []
        for i in range(1, num_features + 1):
            comp_mask = (labeled == i)
            comp_area = int(np.sum(comp_mask))
            if comp_area > total_pixels * 0.015:  # at least 1.5% area
                comps.append((comp_area, comp_mask, slices[i - 1]))

        comps.sort(key=lambda c: c[0], reverse=True)

        # The largest central component is labeled "main_subject"
        for i, (comp_area, comp_mask, slc) in enumerate(comps[: self.max_regions - len(regions)]):
            sy, sx = slc
            bx = int(sx.start)
            by = int(sy.start)
            bw = int(sx.stop - sx.start)
            bh = int(sy.stop - sy.start)

            assigned_mask |= comp_mask
            area_pct = (comp_area / float(total_pixels)) * 100.0
            lbl = "main_subject" if (i == 0 and not any(r.label == "main_subject" for r in regions)) else "foreground_object"

            regions.append(
                SegmentRegion(
                    id=f"region_{region_counter}",
                    label=lbl,
                    bbox=[bx, by, bw, bh],
                    mask=comp_mask,
                    area_pct=round(area_pct, 2),
                )
            )
            region_counter += 1

        # 4. Any leftover unassigned pixels get absorbed into the background or a residual region
        unassigned_area = int(np.sum(~assigned_mask))
        if unassigned_area > 0:
            leftover_mask = ~assigned_mask
            # If background exists, merge into background
            bg_region = next((r for r in regions if r.label == "background"), None)
            if bg_region is not None:
                bg_region.mask |= leftover_mask
                new_area = int(np.sum(bg_region.mask))
                bg_region.area_pct = round((new_area / float(total_pixels)) * 100.0, 2)
                ys, xs = np.where(bg_region.mask)
                bg_region.bbox = [int(np.min(xs)), int(np.min(ys)), int(np.max(xs) - np.min(xs) + 1), int(np.max(ys) - np.min(ys) + 1)]
            else:
                ys, xs = np.where(leftover_mask)
                bx, by = int(np.min(xs)), int(np.min(ys))
                bw, bh = int(np.max(xs) - bx + 1), int(np.max(ys) - by + 1)
                area_pct = (unassigned_area / float(total_pixels)) * 100.0
                regions.append(
                    SegmentRegion(
                        id=f"region_{region_counter}",
                        label="background",
                        bbox=[bx, by, bw, bh],
                        mask=leftover_mask,
                        area_pct=round(area_pct, 2),
                    )
                )

        # Normalize area_pct so sum is exactly 100.0
        total_pct = sum(r.area_pct for r in regions)
        if total_pct > 0:
            for r in regions:
                r.area_pct = round((r.area_pct / total_pct) * 100.0, 2)
            # Adjust rounding difference on largest region
            diff = round(100.0 - sum(r.area_pct for r in regions), 2)
            if diff != 0 and regions:
                regions[0].area_pct = round(regions[0].area_pct + diff, 2)

        return regions

