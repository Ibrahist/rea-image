"""Basic image metadata extractor for dimensions, color profiles, DPI, and aspect ratios."""

import math
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageCms
from rea_image.schemas import ImageMetadata, format_rational
from rea_image.ingest.hashing import compute_sha256, compute_phash


COMMON_ASPECT_RATIOS = [
    (1, 1, "1:1"),
    (4, 5, "4:5"),
    (5, 4, "5:4"),
    (3, 2, "3:2"),
    (2, 3, "2:3"),
    (4, 3, "4:3"),
    (3, 4, "3:4"),
    (16, 9, "16:9"),
    (9, 16, "9:16"),
    (21, 9, "21:9"),
]


def calculate_aspect_ratio_str(width: int, height: int) -> str:
    """Find closest standard aspect ratio or return simplified fraction."""
    if height == 0:
        return "unknown"
    ratio = width / height
    
    for w, h, label in COMMON_ASPECT_RATIOS:
        std_ratio = w / h
        if abs(ratio - std_ratio) < 0.03:
            return label
            
    gcd_val = math.gcd(width, height)
    simplified_w = width // gcd_val
    simplified_h = height // gcd_val
    if simplified_w < 50 and simplified_h < 50:
        return f"{simplified_w}:{simplified_h}"
    return f"{ratio:.2f}:1"


def extract_icc_profile_name(img: Image.Image) -> Optional[str]:
    """Attempt to parse the ICC profile description."""
    icc_bytes = img.info.get("icc_profile")
    if not icc_bytes:
        return None
    try:
        from io import BytesIO
        profile = ImageCms.getOpenProfile(BytesIO(icc_bytes))
        desc = ImageCms.getProfileDescription(profile)
        if desc:
            return desc.strip()
    except Exception:
        pass
    return "embedded-icc"


def extract_metadata(img: Image.Image, file_path: Path) -> ImageMetadata:
    """Extract standard metadata from the loaded PIL image."""
    w, h = img.size
    aspect_str = calculate_aspect_ratio_str(w, h)
    sha256 = compute_sha256(file_path)
    phash = compute_phash(img)
    
    # DPI extraction
    dpi_raw = img.info.get("dpi")
    dpi: Optional[Tuple[float, float]] = None
    if dpi_raw and isinstance(dpi_raw, (tuple, list)) and len(dpi_raw) >= 2:
        try:
            d0 = format_rational(dpi_raw[0])
            d1 = format_rational(dpi_raw[1])
            if d0 is not None and d1 is not None and d0 > 0 and d1 > 0:
                dpi = (float(d0), float(d1))
        except Exception:
            pass
        
    # Bit depth estimate
    mode = img.mode
    bit_depth = 8
    if mode in ("I", "F"):
        bit_depth = 32
    elif "16" in mode or mode in ("RGBa", "RGBA"):
        bit_depth = 8
    elif mode == "1":
        bit_depth = 1
    elif mode == "L":
        bit_depth = 8
        
    icc_name = extract_icc_profile_name(img)
    fmt = (img.format or file_path.suffix.lstrip(".").upper())

    return ImageMetadata(
        path=str(file_path.resolve()),
        sha256=sha256,
        width=w,
        height=h,
        format=fmt,
        aspect_ratio=aspect_str,
        bit_depth=bit_depth,
        color_mode=mode,
        icc_profile=icc_name,
        dpi=dpi,
        perceptual_hash=phash,
    )

