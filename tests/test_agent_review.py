"""Tests for exporting agent review tasks and applying review decisions."""

import json
from pathlib import Path
from PIL import Image
import pytest
from rea_image.schemas import NeedsReviewItem, ProductionMethod
from rea_image.report.orchestrator import run_analysis_pipeline
from rea_image.report.agent_review import export_agent_review_tasks, apply_agent_review


def test_agent_review_export_and_apply(tmp_path: Path):
    """Test exporting review_tasks.json and applying the resolved verdict."""
    img_path = tmp_path / "review_sample.png"
    img = Image.new("RGB", (250, 250), color=(120, 140, 160))
    img.save(img_path)

    out_dir = tmp_path / "out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir)

    # Force a mock conflict
    report.needs_review = [
        NeedsReviewItem(
            region_id="region_0",
            reason="Ambiguous photographic vs AI skin texture",
            question_for_agent="Inspect pores to determine authenticity.",
        )
    ]

    # 1. Export review tasks
    tasks_path = export_agent_review_tasks(report, out_dir)
    assert tasks_path is not None
    assert tasks_path.exists()

    with open(tasks_path, "r", encoding="utf-8") as f:
        tasks = json.load(f)
    assert len(tasks) == 1
    assert tasks[0]["region_id"] == "region_0"

    # 2. Simulate agent filling in decision
    tasks[0]["agent_verdict"] = ProductionMethod.REAL_PHOTO.value
    tasks[0]["agent_explanation"] = "Natural continuous pore structure confirmed."
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

    # 3. Apply agent review
    updated = apply_agent_review(out_dir=out_dir, answers_file=tasks_path)
    assert updated.regions[0].method == ProductionMethod.REAL_PHOTO.value
    assert updated.regions[0].confidence == "high"
    assert len(updated.needs_review) == 0

    verdict_text = (out_dir / "verdict.txt").read_text(encoding="utf-8")
    assert "real photograph" in verdict_text

