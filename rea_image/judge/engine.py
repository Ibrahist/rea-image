"""Weighted evidence judgment engine, calibration, and per-region scoring."""

from typing import Dict, List, Tuple
from rea_image.schemas import ConfidenceLevel, EvidenceItem, ProductionMethod, RegionAnalysis
from rea_image.judge.conflict import ConflictDetector


# Category multipliers: Hard provenance > Forensics > Visuals
DETECTOR_CATEGORY_WEIGHTS = {
    # Hard Provenance (weight 4.0 - 5.0)
    "c2pa_assertion": 5.0,
    "ai_generator_metadata": 5.0,
    "camera_exif": 3.5,
    "iptc_digital_source_type": 3.5,
    "invisible_watermark": 2.5,
    "rendering_software": 2.5,
    "export_software_signature": 2.0,
    # Forensics (weight 1.8)
    "natural_frequency_falloff": 1.8,
    "flat_color_runs": 1.8,
    "ui_axis_aligned_edges": 1.8,
    "resampled_flat_runs": 1.7,
    "jpeg_grid_misalignment": 1.8,
    "noise_inconsistency_composite": 1.8,
    "sensor_poisson_noise": 1.6,
    "jpeg_grid_aligned": 1.6,
    "continuous_natural_gradients": 1.6,
    "synthetic_noise_uncorrelated": 1.6,
    "noise_residual_hypersmooth": 1.5,
    "generator_resolution_signature": 1.4,
    "ela_regional_discrepancy": 1.4,
    "spectral_peaks_upscaler": 1.2,
    "ela_minimal_error": 0.6,
    "ela_low_error_resave": 0.1,
    # Visuals / Heuristics (weight 1.0)
    "ai_style_plastic_sheen": 1.0,
    "3d_shader_characteristics": 1.0,
    "color_profile_quirk": 0.8,
    "camera_exif_missing": 0.3,
}


# Calibration thresholds derived from benchmark calibration bins
CALIBRATION_THRESHOLDS = {
    "high": 0.80,
    "medium_high": 0.65,
    "medium": 0.45,
    "medium_low": 0.30,
}


def compute_confidence_label(score: float, top_supporting: List[EvidenceItem]) -> str:
    """Map numeric calibrated score and supporting signals to human confidence level."""
    # If top supporting includes cryptographically verified C2PA or exact prompt chunk
    has_hard_proof = any(ev.name in ("c2pa_assertion", "ai_generator_metadata") for ev in top_supporting)
    if has_hard_proof:
        if score >= 0.70:
            return ConfidenceLevel.HIGH.value
        elif score >= 0.45:
            return ConfidenceLevel.MEDIUM_HIGH.value
        else:
            return ConfidenceLevel.MEDIUM.value

    if score >= CALIBRATION_THRESHOLDS["high"]:
        return ConfidenceLevel.HIGH.value
    elif score >= CALIBRATION_THRESHOLDS["medium_high"]:
        return ConfidenceLevel.MEDIUM_HIGH.value
    elif score >= CALIBRATION_THRESHOLDS["medium"]:
        return ConfidenceLevel.MEDIUM.value
    elif score >= CALIBRATION_THRESHOLDS["medium_low"]:
        return ConfidenceLevel.MEDIUM_LOW.value
    else:
        return ConfidenceLevel.LOW.value


class JudgmentEngine:
    """Evaluates evidence per region and resolves production method classifications."""

    def __init__(self):
        self.conflict_detector = ConflictDetector()

    def judge_region(
        self,
        region_id: str,
        label: str,
        bbox: List[int],
        area_pct: float,
        evidence_list: List[EvidenceItem],
    ) -> Tuple[RegionAnalysis, List[str], list]:
        """Classify a region based on weighted evidence sum."""
        # Filter evidence applicable to this region:
        # File-level provenance applies globally, but whole-image pixel heuristics
        # should not pollute regions that have their own localized forensic measurements.
        has_local_evidence = any(ev.region == region_id for ev in evidence_list)
        global_pixel_heuristics = {
            "flat_color_runs",
            "resampled_flat_runs",
            "ui_axis_aligned_edges",
            "noise_residual_hypersmooth",
            "excess_high_frequency_energy",
            "continuous_natural_gradients",
        }

        applicable_evidence = [
            ev for ev in evidence_list
            if ev.region == region_id
            or (ev.region == "global" and (not has_local_evidence or ev.name not in global_pixel_heuristics))
        ]

        # Initialize scores for all production methods
        scores: Dict[str, float] = {m.value: 0.05 for m in ProductionMethod}

        # If label is explicitly "text_block", add baseline prior for graphic design
        if label == "text_block":
            scores[ProductionMethod.GRAPHIC_DESIGN.value] += 1.2
        elif label == "ui_element":
            scores[ProductionMethod.UI_SCREENSHOT.value] += 1.2

        # Accumulate weighted evidence
        for ev in applicable_evidence:
            weight = DETECTOR_CATEGORY_WEIGHTS.get(ev.name, 1.0) * ev.strength
            if ev.region == region_id:
                weight *= 1.5
            target_method = ev.direction
            if target_method in scores:
                scores[target_method] += weight

        # Softmax / normalization
        total_score = sum(scores.values())
        norm_scores = {k: v / total_score for k, v in scores.items()}

        # Identify winner
        sorted_methods = sorted(norm_scores.items(), key=lambda x: x[1], reverse=True)
        winner_method, winner_prob = sorted_methods[0]

        # Top 3 supporting evidence items
        supporting = [ev for ev in applicable_evidence if ev.direction == winner_method]
        supporting.sort(
            key=lambda ev: DETECTOR_CATEGORY_WEIGHTS.get(ev.name, 1.0) * ev.strength * (1.5 if ev.region == region_id else 1.0),
            reverse=True,
        )
        top_supporting = supporting[:3]

        # Top 1-2 contradicting evidence items
        contradicting = [ev for ev in applicable_evidence if ev.direction != winner_method and ev.direction != "neutral"]
        contradicting.sort(
            key=lambda ev: DETECTOR_CATEGORY_WEIGHTS.get(ev.name, 1.0) * ev.strength * (1.5 if ev.region == region_id else 1.0),
            reverse=True,
        )
        top_contradicting = contradicting[:2]

        # Check contradictions and agent review needs
        contradictions, review_items = self.conflict_detector.find_conflicts(applicable_evidence, region_id=region_id)

        # Confidence level
        confidence = compute_confidence_label(winner_prob, top_supporting)

        # If conflicts exist and no hard cryptographic proof overrides it, downgrade confidence
        has_hard_proof = any(ev.name in ("c2pa_assertion", "ai_generator_metadata") for ev in top_supporting)
        if (review_items or contradictions) and not has_hard_proof:
            if confidence in (ConfidenceLevel.HIGH.value, ConfidenceLevel.MEDIUM_HIGH.value):
                confidence = ConfidenceLevel.MEDIUM.value
            elif confidence == ConfidenceLevel.MEDIUM.value:
                confidence = ConfidenceLevel.MEDIUM_LOW.value

        region_analysis = RegionAnalysis(
            id=region_id,
            label=label,
            bbox=bbox,
            area_pct=area_pct,
            method=winner_method,
            confidence=confidence,
            evidence=applicable_evidence,
            contradictions=contradictions,
            top_contradicting=top_contradicting,
        )

        return region_analysis, contradictions, review_items
