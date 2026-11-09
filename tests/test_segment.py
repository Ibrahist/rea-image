"""Tests for segmentation, OCR merger, palette, and composition (M4)."""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pytest
from rea_image.ingest.loader import load_image
from rea_image.segment.classical import ClassicalSegmenter
from rea_image.segment.ocr_merger import OCRTextDetector
from rea_image.evidence.craft_color import extract_dominant_palette, analyze_color_grade
from rea_image.evidence.craft_composition import analyze_composition


def test_classical_segmentation(tmp_path: Path):
    """Test splitting image into regions and area normalization to 100%."""
    img_path = tmp_path / "seg_sample.png"
    img = Image.new("RGB", (400, 400), color=(230, 230, 230))
    draw = ImageDraw.Draw(img)
    # Background is gray, draw a subject in the center
    draw.rectangle([100, 100, 300, 300], fill=(20, 80, 180))
    # Draw a secondary object
    draw.ellipse([320, 50, 380, 110], fill=(220, 50, 50))
    img.save(img_path, format="PNG")

    res = load_image(img_path)
    segmenter = ClassicalSegmenter()
    regions = segmenter.segment(res.rgb_array)

    assert len(regions) >= 2
    total_area = sum(r.area_pct for r in regions)
    assert abs(total_area - 100.0) < 0.1

    labels = [r.label for r in regions]
    assert "background" in labels
    assert "main_subject" in labels or "foreground_object" in labels

    for r in regions:
        assert len(r.bbox) == 4
        assert r.mask.shape == (400, 400)
        assert r.area_pct > 0


def test_palette_extraction(tmp_path: Path):
    """Test extracting dominant palette with roles and valid hex codes."""
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:50, :50] = [255, 0, 0]      # Red
    arr[:50, 50:] = [0, 255, 0]      # Green
    arr[50:, :50] = [0, 0, 255]      # Blue
    arr[50:, 50:] = [255, 255, 0]    # Yellow

    palette = extract_dominant_palette(arr, n_colors=4)
    assert len(palette) == 4
    for p in palette:
        assert p.hex.startswith("#")
        assert len(p.hex) == 7
        assert len(p.rgb) == 3
        assert p.role in ("background", "subject", "accent", "text")
        assert 0.0 <= p.percentage <= 100.0

    # Color grading
    grade = analyze_color_grade(arr)
    assert "contrast" in grade
    assert "saturation_level" in grade
    assert "black_point" in grade
    assert "white_point" in grade


def test_composition_analysis(tmp_path: Path):
    """Test rule of thirds, aspect ratio, and composition analysis."""
    arr = np.zeros((300, 400, 3), dtype=np.uint8)
    comp = analyze_composition(arr)

    assert comp.aspect_ratio == "4:3"
    assert comp.rule_of_thirds is not None
    assert comp.golden_ratio is not None
    assert comp.framing is not None
    assert comp.negative_space_pct is not None

