"""Tests for CLI subcommands (M8)."""

from pathlib import Path
from PIL import Image, ImageDraw
from typer.testing import CliRunner
from rea_image.cli import app

runner = CliRunner()


def test_cli_analyze_and_report_cycle(tmp_path: Path):
    """Test full CLI analyze, report, palette, and recreate cycle."""
    img_path = tmp_path / "cli_sample.png"
    img = Image.new("RGB", (320, 240), color=(100, 150, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 180, 160], fill=(220, 80, 80))
    img.save(img_path, format="PNG")

    out_dir = tmp_path / "cli_output"

    # 1. rea-image analyze
    res_analyze = runner.invoke(app, ["analyze", str(img_path), "--out", str(out_dir)])
    assert res_analyze.exit_code == 0
    assert "Analysis complete" in res_analyze.output
    assert (out_dir / "report.json").exists()
    assert (out_dir / "report.html").exists()
    assert (out_dir / "verdict.txt").exists()

    # 2. rea-image report (rebuild)
    res_report = runner.invoke(app, ["report", str(out_dir)])
    assert res_report.exit_code == 0
    assert "Successfully rebuilt" in res_report.output

    # 2b. rea-image explain
    res_explain = runner.invoke(app, ["explain", str(out_dir)])
    assert res_explain.exit_code == 0
    assert "Evidence Ledger" in res_explain.output
    assert "Signed Score" in res_explain.output

    # 3. rea-image palette
    res_palette = runner.invoke(app, ["palette", str(img_path)])
    assert res_palette.exit_code == 0
    assert "Dominant Palette" in res_palette.output

    # 4. rea-image provenance
    res_prov = runner.invoke(app, ["provenance", str(img_path)])
    assert res_prov.exit_code == 0
    assert "Provenance & Metadata" in res_prov.output

    # 5. rea-image prompt
    res_prompt = runner.invoke(app, ["prompt", str(img_path)])
    assert res_prompt.exit_code == 0
    assert "Prompt" in res_prompt.output

    # 6. rea-image recreate --dry-run
    res_recreate = runner.invoke(app, ["recreate", str(out_dir), "--dry-run"])
    assert res_recreate.exit_code == 0
    assert "Recreation Simulation" in res_recreate.output or "Dry Run" in res_recreate.output


def test_cli_analyze_failure_exit_code(tmp_path: Path):
    """Test that analyze returns non-zero exit code when ingest fails."""
    corrupt_file = tmp_path / "corrupt.png"
    corrupt_file.write_text("not a real png image content", encoding="utf-8")

    res = runner.invoke(app, ["analyze", str(corrupt_file)])
    assert res.exit_code == 1
    assert "Failed to ingest" in res.output or "Pipeline error" in res.output


def test_cli_analyze_recursive(tmp_path: Path):
    """Test that --recursive searches subdirectories."""
    sub_dir = tmp_path / "subdir" / "nested"
    sub_dir.mkdir(parents=True)
    img = Image.new("RGB", (100, 100), color=(50, 100, 150))
    img.save(sub_dir / "nested_img.png")

    # Non-recursive should find 0 images
    res_non_rec = runner.invoke(app, ["analyze", str(tmp_path)])
    assert res_non_rec.exit_code == 0
    assert "No supported images found" in res_non_rec.output

    # Recursive should find and process the nested image
    out_dir = tmp_path / "rec_out"
    res_rec = runner.invoke(app, ["analyze", str(tmp_path), "--recursive", "--out", str(out_dir)])
    assert res_rec.exit_code == 0
    assert "nested_img.png" in res_rec.output


def test_cli_recreate_missing_path_does_not_crash(tmp_path: Path):
    """Test that recreate handles regions without recreate.path gracefully without crashing."""
    import json
    out_dir = tmp_path / "corrupt_recreate"
    out_dir.mkdir()
    fake_report = {
        "image": {"aspect_ratio": "1:1"},
        "regions": [
            {"id": "r1", "label": "subject", "recreate": None},
            {"id": "r2", "label": "bg", "recreate": {}},
            {"id": "r3", "label": "accent", "recreate": {"path": None}},
        ]
    }
    (out_dir / "report.json").write_text(json.dumps(fake_report), encoding="utf-8")

    res = runner.invoke(app, ["recreate", str(out_dir), "--dry-run"])
    assert res.exit_code == 0
    assert "SKIPPED" in res.output


def test_cli_explain_region_filtering_and_missing(tmp_path: Path):
    """Test explain command with specific region and invalid region."""
    import json
    out_dir = tmp_path / "explain_test"
    out_dir.mkdir()
    fake_report = {
        "verdict": {"summary": "AI-generated 100%"},
        "regions": [
            {
                "id": "region_1",
                "label": "subject",
                "method": "AI-generated",
                "confidence": "high",
                "evidence": [
                    {"name": "ai_generator_metadata", "region": "region_1", "direction": "AI-generated", "strength": 0.9, "explanation": "Prompt metadata"}
                ]
            }
        ]
    }
    (out_dir / "report.json").write_text(json.dumps(fake_report), encoding="utf-8")

    # Specific region
    res_ok = runner.invoke(app, ["explain", str(out_dir), "--region", "region_1"])
    assert res_ok.exit_code == 0
    assert "Region region_1" in res_ok.output
    assert "+4.05" in res_ok.output or "Net Signed Support" in res_ok.output

    # Missing region
    res_err = runner.invoke(app, ["explain", str(out_dir), "--region", "region_missing"])
    assert res_err.exit_code == 1
    assert "Region 'region_missing' not found" in res_err.output

