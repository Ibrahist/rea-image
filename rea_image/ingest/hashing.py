"""Hashing utilities for caching, deduplication, and perceptual identification."""

import hashlib
from pathlib import Path
from typing import Union
import numpy as np
from PIL import Image


def compute_sha256(file_path_or_bytes: Union[str, Path, bytes]) -> str:
    """Compute SHA-256 hash of file content or bytes."""
    hasher = hashlib.sha256()
    if isinstance(file_path_or_bytes, bytes):
        hasher.update(file_path_or_bytes)
    else:
        path = Path(file_path_or_bytes)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


def compute_dhash(img: Image.Image, hash_size: int = 8) -> str:
    """Compute difference hash (dHash) of an image.
    
    Resizes image to (hash_size + 1, hash_size), converts to grayscale,
    and compares adjacent pixels.
    """
    gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.int16)
    diff = arr[:, 1:] > arr[:, :-1]
    
    # Pack boolean bits into hex string
    bits = diff.flatten()
    val = 0
    for bit in bits:
        val = (val << 1) | int(bit)
    hex_len = (hash_size * hash_size) // 4
    return f"{val:0{hex_len}x}"


def compute_phash(img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """Compute perceptual hash (pHash) using discrete cosine transform (DCT)."""
    try:
        from scipy.fft import dct
        
        img_size = hash_size * highfreq_factor
        gray = img.convert("L").resize((img_size, img_size), Image.Resampling.LANCZOS)
        arr = np.asarray(gray, dtype=np.float32)
        
        # 2D DCT
        dct_rows = dct(arr, axis=0, norm="ortho")
        dct_2d = dct(dct_rows, axis=1, norm="ortho")
        
        # Extract low frequencies, exclude DC term at (0, 0)
        low_freq = dct_2d[:hash_size, :hash_size]
        median_val = np.median(low_freq[1:, 1:])
        diff = low_freq > median_val
        
        bits = diff.flatten()
        val = 0
        for bit in bits:
            val = (val << 1) | int(bit)
        hex_len = (hash_size * hash_size) // 4
        return f"{val:0{hex_len}x}"
    except Exception:
        # Fallback to dHash if DCT fails
        return compute_dhash(img, hash_size)

