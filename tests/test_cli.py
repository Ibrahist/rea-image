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


def test_cli_analyze_formats_and_batch_csv(tmp_path: Path):
    """Test --format json, --format csv, and folder batch_summary.csv generation."""
    img1_path = tmp_path / "img1.png"
    img2_path = tmp_path / "img2.png"
    img = Image.new("RGB", (120, 120), color=(180, 180, 180))
    img.save(img1_path)
    img.save(img2_path)

    # 1. JSON format on single image
    res_json = runner.invoke(app, ["analyze", str(img1_path), "--format", "json"])
    assert res_json.exit_code == 0
    import json
    data = json.loads(res_json.output.strip())
    assert data["image"] == "img1.png"
    assert "verdict" in data

    # 2. CSV format on single image
    res_csv = runner.invoke(app, ["analyze", str(img1_path), "--format", "csv"])
    assert res_csv.exit_code == 0
    assert "image,verdict" in res_csv.output
    assert "img1.png" in res_csv.output

    # 3. Batch folder run generates batch_summary.csv
    batch_out = tmp_path / "batch_out"
    res_folder = runner.invoke(app, ["analyze", str(tmp_path), "--out", str(batch_out)])
    assert res_folder.exit_code == 0
    csv_file = batch_out / "batch_summary.csv"
    assert csv_file.exists()
    content = csv_file.read_text(encoding="utf-8")
    assert "img1.png" in content
    assert "img2.png" in content


def test_calibration_tolerance_check():
    """Test calibration check fails when bins deviate beyond tolerance."""
    from eval.dataset_schema import CalibrationBin
    from eval.runner import check_calibration_tolerance
    from rea_image.judge.engine import compute_confidence_label, CALIBRATION_THRESHOLDS
    from rea_image.schemas import EvidenceItem

    # Check CALIBRATION_THRESHOLDS are used
    assert CALIBRATION_THRESHOLDS["high"] == 0.80
    assert CALIBRATION_THRESHOLDS["medium_high"] == 0.65
    assert CALIBRATION_THRESHOLDS["medium"] == 0.45
    label = compute_confidence_label(0.82, [EvidenceItem(name="sensor_poisson_noise", value={}, direction="real photograph", strength=0.8, explanation="noise")])
    assert label == "high"

    # Calibration bins test
    good_bins = [
        CalibrationBin(bin_name="High (0.80+)", confidence_range="0.80+", sample_count=10, correct_count=9, empirical_accuracy_pct=90.0),
        CalibrationBin(bin_name="Low (<0.45)", confidence_range="<0.45", sample_count=0, correct_count=0, empirical_accuracy_pct=0.0),
    ]
    ok, errs = check_calibration_tolerance(good_bins, tolerance=20.0)
    assert ok
    assert not errs

    bad_bins = [
        CalibrationBin(bin_name="High (0.80+)", confidence_range="0.80+", sample_count=10, correct_count=5, empirical_accuracy_pct=50.0),
    ]
    ok, errs = check_calibration_tolerance(bad_bins, tolerance=20.0)
    assert not ok
    assert len(errs) == 1
    assert "is below tolerance floor" in errs[0]

