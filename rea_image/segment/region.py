"""Region definition, crop generation, and mask management."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image


@dataclass
class SegmentRegion:
    id: str
    label: str
    bbox: List[int]  # [x, y, width, height]
    mask: np.ndarray  # 2D boolean array (H, W)
    area_pct: float  # Percentage of image area (0.0 to 100.0)
    crop_image: Optional[Image.Image] = None

    def save_mask_and_crop(self, out_dir: Path, base_img: Image.Image) -> Tuple[Path, Path]:
        """Save binary mask PNG and cropped region PNG to out_dir."""
        out_dir.mkdir(parents=True, exist_ok=True)
        mask_path = out_dir / f"{self.id}_mask.png"
        crop_path = out_dir / f"{self.id}_crop.png"

        # Save mask as 8-bit grayscale
        mask_uint8 = (self.mask.astype(np.uint8)) * 255
        mask_img = Image.fromarray(mask_uint8, mode="L")
        mask_img.save(mask_path, format="PNG")

        # Crop image to bounding box
        x, y, w, h = self.bbox
        w = max(1, w)
        h = max(1, h)
        cropped = base_img.crop((x, y, x + w, y + h))
        cropped.save(crop_path, format="PNG")

        return mask_path, crop_path

