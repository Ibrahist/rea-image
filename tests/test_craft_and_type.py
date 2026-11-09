"""Tests for camera optics, lighting setups, typography, and visual checks (M5)."""

import numpy as np
from rea_image.evidence.craft_camera import CameraCraftEstimator
from rea_image.evidence.craft_lighting import LightingClassifier
from rea_image.evidence.typography import TypographyAnalyzer, analyze_layout_grid


def test_camera_craft_estimator():
    """Test focal length and aperture estimation on synthetic frame."""
    arr = np.zeros((400, 600, 3), dtype=np.uint8)
    arr[:, :] = [100, 150, 200]
    estimator = CameraCraftEstimator()
    res = estimator.estimate(arr)

    assert "focal_length_class" in res
    assert "estimated_focal_length" in res
    assert "depth_of_field" in res
    assert "estimated_aperture" in res
    assert "vignette_falloff" in res


def test_lighting_classifier():
    """Test standard lighting rig matching."""
    # Test side lit image
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    arr[:, :100] = [240, 240, 240]  # bright left
    arr[:, 100:] = [20, 20, 20]     # dark right

    classifier = LightingClassifier()
    info = classifier.classify(arr)

    assert info.matched_setup in (
        "Split lighting", "Rembrandt lighting", "Window light", "Softbox portrait"
    )
    assert len(info.suggested_gear) >= 2
    assert info.direction is not None
    assert info.softness is not None


def test_typography_analyzer():
    """Test typography font candidates, size hierarchy, and layout grid."""
    arr = np.zeros((300, 500, 3), dtype=np.uint8)
    sample_boxes = [
        {"bbox": [50, 40, 400, 60], "confidence": 0.9, "text": "BIG HEADLINE"},
        {"bbox": [50, 120, 250, 24], "confidence": 0.8, "text": "Subheading line"},
    ]
    analyzer = TypographyAnalyzer()
    res = analyzer.analyze(arr, text_boxes=sample_boxes)

    assert len(res.font_family_candidates) == 3
    assert "Display" in res.size_hierarchy or "Bold" in res.weight
    assert res.alignment in ("left", "center", "right")
    assert res.extracted_text == "BIG HEADLINE Subheading line"
    assert isinstance(res.line_spacing, float)

    grid = analyze_layout_grid(arr)
    assert "margins" in grid
    assert "grid_type" in grid


def test_typography_and_layout_not_measured_when_empty():
    """Verify evidence-first: unmeasured values return 'not measured' instead of canned constants."""
    arr = np.zeros((300, 500, 3), dtype=np.uint8)
    analyzer = TypographyAnalyzer()
    res = analyzer.analyze(arr, text_boxes=[])
    assert res.extracted_text == "not measured"
    assert res.size_hierarchy == "not measured"
    assert res.line_spacing == "not measured"
    assert res.alignment == "not measured"

    grid = analyze_layout_grid(arr, regions=[])
    assert grid["margins"] == "not measured"
    assert grid["grid_type"] == "not measured"

