"""Tests for forensic signal detectors (M3)."""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from rea_image.ingest.loader import load_image
from rea_image.evidence.forensics_noise import ForensicsNoiseDetector
from rea_image.evidence.forensics_jpeg import ForensicsJpegDetector
from rea_image.evidence.forensics_frequency import ForensicsFrequencyDetector
from rea_image.evidence.forensics_flat import ForensicsFlatDetector
from rea_image.schemas import ProductionMethod


def test_flat_vector_detection(tmp_path: Path):
    """Test flat-run detection on clean vector/graphic style image."""
    img_path = tmp_path / "flat_graphic.png"
    # Create an image with large flat color patches
    img = Image.new("RGB", (300, 300), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 140, 140], fill=(255, 0, 0))
    draw.rectangle([160, 20, 280, 140], fill=(0, 255, 0))
    draw.rectangle([20, 160, 280, 280], fill=(0, 0, 255))
    img.save(img_path, format="PNG")

    res = load_image(img_path)
    detector = ForensicsFlatDetector()
    items = detector.run(res)

    flat_item = next((it for it in items if it.name == "flat_color_runs"), None)
    assert flat_item is not None
    assert flat_item.direction == ProductionMethod.GRAPHIC_DESIGN.value
    assert flat_item.strength >= 0.85


def test_hypersmooth_noise_detection(tmp_path: Path):
    """Test hypersmooth residual noise detection on flat digital graphic."""
    img_path = tmp_path / "smooth.png"
    img = Image.new("RGB", (200, 200), color=(128, 128, 128))
    img.save(img_path, format="PNG")

    res = load_image(img_path)
    detector = ForensicsNoiseDetector()
    items = detector.run(res)

    smooth_item = next((it for it in items if it.name == "noise_residual_hypersmooth"), None)
    assert smooth_item is not None
    assert smooth_item.direction == ProductionMethod.GRAPHIC_DESIGN.value


def test_frequency_periodic_peaks(tmp_path: Path):
    """Test 2D FFT detection of periodic upsampling/checkerboard peaks."""
    img_path = tmp_path / "periodic_upscale.png"
    # Generate 256x256 image with synthetic 4-pixel checkerboard artifact
    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    y, x = np.ogrid[:256, :256]
    checker = ((x % 8 < 4) ^ (y % 8 < 4)) * 120
    arr[:, :, 0] = checker
    arr[:, :, 1] = checker
    arr[:, :, 2] = checker
    Image.fromarray(arr).save(img_path, format="PNG")

    res = load_image(img_path)
    detector = ForensicsFrequencyDetector()
    items = detector.run(res)

    peak_item = next((it for it in items if it.name == "spectral_peaks_upscaler"), None)
    assert peak_item is not None
    assert peak_item.direction == ProductionMethod.AI_GENERATED.value
    # Uncorroborated periodic peaks must be capped at <= 0.40 to prevent false positives on texture/resizing
    assert peak_item.strength <= 0.40
    assert peak_item.strength >= 0.30


def test_jpeg_ela_analysis(tmp_path: Path):
    """Test Error Level Analysis on JPEG image."""
    img_path = tmp_path / "ela_sample.jpg"
    img = Image.new("RGB", (320, 240), color=(180, 180, 180))
    draw = ImageDraw.Draw(img)
    draw.ellipse([40, 40, 200, 200], fill=(50, 80, 220))
    img.save(img_path, format="JPEG", quality=85)

    res = load_image(img_path)
    detector = ForensicsJpegDetector()
    items = detector.run(res)

    assert isinstance(items, list)


def test_low_res_degradation_penalty(tmp_path: Path):
    """Test degradation penalty triggering on low-resolution image."""
    img_path = tmp_path / "lowres.png"
    img = Image.new("RGB", (120, 120), color=(100, 100, 100))
    img.save(img_path, format="PNG")

    res = load_image(img_path)
    detector = ForensicsFlatDetector()
    items = detector.run(res)

    deg_item = next((it for it in items if it.name == "compression_degradation_penalty"), None)
    assert deg_item is not None
    assert deg_item.value["is_degraded"] is True
    assert deg_item.strength > 0.0


def test_forensics_small_crop_boundaries():
    """Test that regional forensics detectors handle crops <64px and <16px without exceptions."""
    freq_det = ForensicsFrequencyDetector()
    noise_det = ForensicsNoiseDetector()
    flat_det = ForensicsFlatDetector()

    # 1. 32x32 crop: frequency detector returns empty (requires >= 64px), noise & flat process safely
    crop_32 = np.full((32, 32, 3), 120, dtype=np.uint8)
    freq_items_32 = freq_det.run_region(crop_32, "region_32")
    assert freq_items_32 == []  # < 64px FFT boundary returns neutral/empty

    noise_items_32 = noise_det.run_region(crop_32, "region_32")
    assert isinstance(noise_items_32, list)

    flat_items_32 = flat_det.run_region(crop_32, "region_32")
    assert isinstance(flat_items_32, list)

    # 2. 8x8 micro-crop: below all patch thresholds (<64px, <24px, <16px) -> all return empty
    crop_8 = np.full((8, 8, 3), 120, dtype=np.uint8)
    assert freq_det.run_region(crop_8, "region_8") == []
    assert noise_det.run_region(crop_8, "region_8") == []
    assert flat_det.run_region(crop_8, "region_8") == []


