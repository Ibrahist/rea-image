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

