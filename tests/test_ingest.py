"""Tests for image ingestion, hashing, format checks, and animation rejection."""

import pytest
from pathlib import Path
from PIL import Image
from rea_image.ingest.loader import load_image, IngestError, AnimatedImageError
from rea_image.ingest.hashing import compute_sha256, compute_dhash, compute_phash
from rea_image.ingest.metadata_extractor import calculate_aspect_ratio_str


def test_load_valid_png(sample_png: Path):
    res = load_image(sample_png)
    assert res.path == sample_png
    assert res.metadata.width == 320
    assert res.metadata.height == 240
    assert res.metadata.format.upper() == "PNG"
    assert res.metadata.aspect_ratio == "4:3"
    assert res.rgb_image.mode == "RGB"
    assert res.rgb_array.shape == (240, 320, 3)
    assert len(res.metadata.sha256) == 64
    assert res.metadata.perceptual_hash is not None


def test_load_valid_jpeg(sample_jpeg: Path):
    res = load_image(sample_jpeg)
    assert res.path == sample_jpeg
    assert res.metadata.width == 400
    assert res.metadata.height == 300
    assert res.metadata.format.upper() in ("JPEG", "JPG")
    assert res.metadata.aspect_ratio == "4:3"


def test_animated_gif_rejected(animated_gif: Path):
    with pytest.raises(AnimatedImageError) as exc_info:
        load_image(animated_gif)
    assert "Animated files are out of scope" in str(exc_info.value)
    assert "GIF" in str(exc_info.value)


def test_animated_webp_rejected(animated_webp: Path):
    with pytest.raises(AnimatedImageError) as exc_info:
        load_image(animated_webp)
    assert "Animated files are out of scope" in str(exc_info.value)
    assert "WebP" in str(exc_info.value)


def test_nonexistent_file(tmp_path: Path):
    missing = tmp_path / "does_not_exist.png"
    with pytest.raises(IngestError) as exc_info:
        load_image(missing)
    assert "not found" in str(exc_info.value).lower()


def test_corrupt_file(tmp_path: Path):
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"NOT_A_REAL_IMAGE_DATA")
    with pytest.raises(IngestError) as exc_info:
        load_image(corrupt)
    assert "corrupt" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


def test_perceptual_hashes(sample_png: Path):
    with Image.open(sample_png) as img:
        dhash = compute_dhash(img)
        phash = compute_phash(img)
        assert len(dhash) == 16
        assert len(phash) == 16


def test_aspect_ratio_calculations():
    assert calculate_aspect_ratio_str(1920, 1080) == "16:9"
    assert calculate_aspect_ratio_str(1080, 1920) == "9:16"
    assert calculate_aspect_ratio_str(1080, 1350) == "4:5"
    assert calculate_aspect_ratio_str(1000, 1000) == "1:1"
    assert calculate_aspect_ratio_str(1200, 800) == "3:2"

