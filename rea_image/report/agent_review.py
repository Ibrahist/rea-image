"""Agent review task export and review answers application."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from rea_image.schemas import ReportSchema, ProductionMethod, EvidenceItem
from rea_image.report.json_exporter import export_report_json
from rea_image.report.html_generator import generate_report_html


def export_agent_review_tasks(report: ReportSchema, out_dir: Path) -> Optional[Path]:
    """Export review_tasks.json for agent inspection when needs_review items exist."""
    if not report.needs_review:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = []

    for item in report.needs_review:
        # Find matching region crop
        matching_region = next((r for r in report.regions if r.id == item.region_id), None)
        crop_rel = matching_region.crop_path if matching_region else ""

        tasks.append({
            "region_id": item.region_id,
            "crop_path": crop_rel,
            "reason": item.reason,
            "question": item.question_for_agent,
            "allowed_verdicts": [
                ProductionMethod.REAL_PHOTO.value,
                ProductionMethod.AI_GENERATED.value,
                ProductionMethod.GRAPHIC_DESIGN.value,
                ProductionMethod.RENDER_3D.value,
                ProductionMethod.COMPOSITE.value,
            ],
            "agent_verdict": None,
            "agent_explanation": "",
        })

    tasks_path = out_dir / "review_tasks.json"
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

    return tasks_path


def apply_agent_review(out_dir: Path, answers_file: Optional[Path] = None) -> ReportSchema:
    """Apply agent review answers to update report.json, verdict.txt, and report.html."""
    json_path = out_dir / "report.json"
    if not json_path.exists():
        raise FileNotFoundError(f"report.json not found in {out_dir}")

    if answers_file is None:
        answers_file = out_dir / "review_tasks.json"
    if not answers_file.exists():
        raise FileNotFoundError(f"Review answers file not found at {answers_file}")

    with open(json_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)
    report = ReportSchema(**report_data)

    with open(answers_file, "r", encoding="utf-8") as f:
        answers = json.load(f)

    # Apply findings to matching regions
    for ans in answers:
        reg_id = ans.get("region_id")
        chosen_method = ans.get("agent_verdict")
        explanation = ans.get("agent_explanation", "Verified via agent vision review.")

        if not chosen_method:
            continue

        for r in report.regions:
            if r.id == reg_id or reg_id == "global":
                r.method = chosen_method
                r.confidence = "high"
                r.evidence.append(
                    EvidenceItem(
                        name="agent_visual_review_resolution",
                        value=chosen_method,
                        region=r.id,
                        direction=chosen_method,
                        strength=0.96,
                        explanation=f"Agent visual review: {explanation}",
                    )
                )

    # Recompute verdict breakdown
    from rea_image.judge.aggregator import VerdictAggregator
    aggregator = VerdictAggregator()
    new_verdict, change_statement = aggregator.aggregate(
        regions=report.regions,
        global_evidence=[],
        aspect_ratio=report.image.aspect_ratio,
        width=report.image.width,
        height=report.image.height,
        color_grade=report.global_analysis.color_grade,
    )
    report.verdict = new_verdict

    # Clear resolved needs_review items
    report.needs_review = []
    report.limitations.append("Agent visual inspection was applied to resolve preliminary conflicts.")

    # Re-export updated bundle
    export_report_json(report, json_path)
    generate_report_html(report, out_dir / "report.html")
    (out_dir / "verdict.txt").write_text(new_verdict.summary.strip() + "\n", encoding="utf-8")

    return report

