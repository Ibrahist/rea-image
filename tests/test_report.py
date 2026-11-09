"""Tests for report generation, bundle assets, and HTML rebuild (M8)."""

import json
from pathlib import Path
from PIL import Image, ImageDraw
from rea_image.report.orchestrator import run_analysis_pipeline, rebuild_html_from_json
from rea_image.schemas import ReportSchema


def test_full_pipeline_and_bundle_export(tmp_path: Path):
    """Test running full analysis pipeline and exporting all required bundle files."""
    img_path = tmp_path / "test_target.png"
    img = Image.new("RGB", (400, 300), color=(220, 230, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 250, 200], fill=(200, 50, 50))
    draw.text((60, 60), "Headline", fill=(255, 255, 255))
    img.save(img_path, format="PNG")

    out_dir = tmp_path / "rea_output"
    report = run_analysis_pipeline(
        image_path=img_path,
        out_dir=out_dir,
        offline=True,
    )

    # 1. Check verdict.txt
    verdict_file = out_dir / "verdict.txt"
    assert verdict_file.exists()
    verdict_content = verdict_file.read_text(encoding="utf-8").strip()
    assert len(verdict_content) > 10
    assert report.verdict.confidence in verdict_content

    # 2. Check report.json
    json_file = out_dir / "report.json"
    assert json_file.exists()
    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Validate against Section 7 schema keys
    assert "image" in json_data
    assert "verdict" in json_data
    assert "regions" in json_data
    assert "global" in json_data
    assert "needs_review" in json_data
    assert "limitations" in json_data

    # Validate Pydantic parsing
    validated = ReportSchema(**json_data)
    assert validated.image.width == 400
    assert validated.image.height == 300

    # 3. Check report.html
    html_file = out_dir / "report.html"
    assert html_file.exists()
    html_text = html_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_text
    assert "rea-image Report" in html_text
    assert "VERDICT & CLASSIFICATION" in html_text

    # 4. Check layers/ directory
    layers_dir = out_dir / "layers"
    assert layers_dir.exists()
    layer_files = list(layers_dir.glob("*.png"))
    assert len(layer_files) >= 2  # At least mask and crop

    # 5. Check recreate/ directory
    recreate_dir = out_dir / "recreate"
    assert recreate_dir.exists()
    prompt_file = recreate_dir / "prompt.txt"
    assert prompt_file.exists()
    assert len(prompt_file.read_text(encoding="utf-8")) > 20

    # 6. Test rebuild_html_from_json
    html_file.unlink()  # Remove existing html
    assert not html_file.exists()
    rebuilt_path = rebuild_html_from_json(out_dir)
    assert rebuilt_path.exists()
    assert html_file.exists()

