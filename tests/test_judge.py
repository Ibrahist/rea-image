"""Tests for judgment engine, conflict detection, and verdict aggregation (M6)."""

import pytest
from rea_image.schemas import EvidenceItem, ProductionMethod
from rea_image.judge.engine import JudgmentEngine
from rea_image.judge.conflict import ConflictDetector
from rea_image.judge.aggregator import VerdictAggregator
from rea_image.judge.style_matcher import estimate_ai_model_family


def test_hard_metadata_beats_forensics():
    """Verify that hard provenance (C2PA / AI metadata) outweights forensic indicators."""
    engine = JudgmentEngine()
    
    # 1 strong AI metadata evidence item vs 1 forensic real photo item
    evidence = [
        EvidenceItem(
            name="ai_generator_metadata",
            value={"generator": "Stable Diffusion"},
            region="global",
            direction=ProductionMethod.AI_GENERATED.value,
            strength=0.99,
            explanation="Embedded parameters found",
        ),
        EvidenceItem(
            name="natural_frequency_falloff",
            value={"alpha": 2.0},
            region="global",
            direction=ProductionMethod.REAL_PHOTO.value,
            strength=0.60,
            explanation="Natural frequency spectrum",
        ),
    ]

    region_analysis, contradictions, review_items = engine.judge_region(
        region_id="r0",
        label="main_subject",
        bbox=[0, 0, 100, 100],
        area_pct=100.0,
        evidence_list=evidence,
    )

    assert region_analysis.method == ProductionMethod.AI_GENERATED.value
    assert region_analysis.confidence in ("high", "medium-high")


def test_conflict_detection_creates_review_item():
    """Verify that conflicting signals (Camera EXIF + AI artifacts) trigger an agent review item."""
    conflict_det = ConflictDetector()

    evidence = [
        EvidenceItem(
            name="camera_exif",
            value={"make": "Canon", "model": "EOS R5"},
            region="global",
            direction=ProductionMethod.REAL_PHOTO.value,
            strength=0.90,
            explanation="Hardware camera tag",
        ),
        EvidenceItem(
            name="spectral_peaks_upscaler",
            value={"peaks": 8},
            region="global",
            direction=ProductionMethod.AI_GENERATED.value,
            strength=0.85,
            explanation="Upscaler checkerboard detected",
        ),
    ]

    contradictions, review_items = conflict_det.find_conflicts(evidence, region_id="r0")
    assert len(contradictions) >= 1
    assert len(review_items) >= 1
    assert "EXIF" in review_items[0].reason
    assert "agent" in review_items[0].question_for_agent.lower() or "inspect" in review_items[0].question_for_agent.lower()


def test_verdict_area_aggregation():
    """Verify area-weighted aggregation for a composite image."""
    engine = JudgmentEngine()
    aggregator = VerdictAggregator()

    # Region 1: AI subject (75%)
    r1, _, _ = engine.judge_region(
        region_id="r1",
        label="main_subject",
        bbox=[0, 0, 800, 600],
        area_pct=75.0,
        evidence_list=[
            EvidenceItem(
                name="ai_generator_metadata",
                value={"generator": "Midjourney"},
                region="r1",
                direction=ProductionMethod.AI_GENERATED.value,
                strength=0.95,
                explanation="Midjourney v6 tags",
            )
        ],
    )

    # Region 2: Designed text block (25%)
    r2, _, _ = engine.judge_region(
        region_id="r2",
        label="text_block",
        bbox=[50, 50, 300, 80],
        area_pct=25.0,
        evidence_list=[
            EvidenceItem(
                name="flat_color_runs",
                value={"flat_pixel_percentage": 60.0},
                region="r2",
                direction=ProductionMethod.GRAPHIC_DESIGN.value,
                strength=0.92,
                explanation="Pure flat vector fill",
            )
        ],
    )

    verdict, change_statement = aggregator.aggregate(
        regions=[r1, r2],
        global_evidence=[],
        aspect_ratio="4:3",
        width=800,
        height=600,
    )

    assert len(verdict.method_breakdown) == 2
    assert "AI-generated 75%" in verdict.summary
    assert "vector or graphic design 25%" in verdict.summary
    assert "What would change" in change_statement

