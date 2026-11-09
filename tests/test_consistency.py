"""Tests for cross-image consistency analysis across carousels and image sets."""

from pathlib import Path
from PIL import Image
import pytest
from rea_image.report.orchestrator import run_analysis_pipeline
from rea_image.report.consistency import analyze_cross_image_consistency


def test_cross_image_consistency_analysis(tmp_path: Path):
    """Test evaluating aspect ratio, style, and palette consistency across multiple images."""
    folder = tmp_path / "carousel_set"
    folder.mkdir()

    # Create 3 images in the same aspect ratio (1:1) and shared theme
    reports = []
    for i in range(3):
        img_p = folder / f"slide_{i}.png"
        img = Image.new("RGB", (300, 300), color=(30 + i * 10, 50, 100))
        img.save(img_p)
        r = run_analysis_pipeline(img_p, out_dir=tmp_path / f"out_{i}")
        reports.append(r)

    consistency = analyze_cross_image_consistency(reports, out_dir=tmp_path / "series_out")

    assert consistency["total_images"] == 3
    assert consistency["aspect_ratio_consistency"]["is_uniform"] is True
    assert consistency["series_cohesion_score"] >= 60
    assert (tmp_path / "series_out" / "consistency_summary.json").exists()

