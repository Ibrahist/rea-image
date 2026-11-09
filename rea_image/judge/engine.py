"""Weighted evidence judgment engine, calibration, and per-region scoring."""

from typing import Dict, List, Tuple
from rea_image.schemas import ConfidenceLevel, EvidenceItem, ProductionMethod, RegionAnalysis
from rea_image.judge.conflict import ConflictDetector


# Category multipliers: Hard provenance > Forensics > Visuals
DETECTOR_CATEGORY_WEIGHTS = {
    # Hard Provenance (weight 3.0)
    "c2pa_assertion": 3.0,
    "ai_generator_metadata": 3.0,
    "camera_exif": 2.8,
    "iptc_digital_source_type": 2.8,
    "rendering_software": 2.5,
    "export_software_signature": 2.0,
    # Forensics (weight 1.8)
    "natural_frequency_falloff": 1.8,
    "flat_color_runs": 1.8,
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


def compute_confidence_label(score: float, top_supporting: List[EvidenceItem]) -> str:
    """Map numeric calibrated score and supporting signals to human confidence level."""
    # If top supporting includes cryptographically verified C2PA or exact prompt chunk
    has_hard_proof = any(ev.name in ("c2pa_assertion", "ai_generator_metadata") for ev in top_supporting)
    if has_hard_proof:
        if score >= 0.75:
            return ConfidenceLevel.HIGH.value
        elif score >= 0.50:
            return ConfidenceLevel.MEDIUM_HIGH.value
        else:
            return ConfidenceLevel.MEDIUM.value

    if score >= 0.75:
        return ConfidenceLevel.HIGH.value
    elif score >= 0.60:
        return ConfidenceLevel.MEDIUM_HIGH.value
    elif score >= 0.45:
        return ConfidenceLevel.MEDIUM.value
    elif score >= 0.30:
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
        # Initialize scores for all production methods
        scores: Dict[str, float] = {m.value: 0.05 for m in ProductionMethod}

        # If label is explicitly "text_block", add baseline prior for graphic design
        if label == "text_block":
            scores[ProductionMethod.GRAPHIC_DESIGN.value] += 1.2
        elif label == "ui_element":
            scores[ProductionMethod.UI_SCREENSHOT.value] += 1.2

        # Accumulate weighted evidence
        for ev in evidence_list:
            weight = DETECTOR_CATEGORY_WEIGHTS.get(ev.name, 1.0) * ev.strength
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
        supporting = [ev for ev in evidence_list if ev.direction == winner_method]
        supporting.sort(
            key=lambda ev: DETECTOR_CATEGORY_WEIGHTS.get(ev.name, 1.0) * ev.strength,
            reverse=True,
        )
        top_supporting = supporting[:3]

        # Top 1-2 contradicting evidence items
        contradicting = [ev for ev in evidence_list if ev.direction != winner_method and ev.direction != "neutral"]
        contradicting.sort(
            key=lambda ev: DETECTOR_CATEGORY_WEIGHTS.get(ev.name, 1.0) * ev.strength,
            reverse=True,
        )
        top_contradicting = contradicting[:2]

        # Check contradictions and agent review needs
        contradictions, review_items = self.conflict_detector.find_conflicts(evidence_list, region_id=region_id)

        # Confidence level
        confidence = compute_confidence_label(winner_prob, top_supporting)

        region_analysis = RegionAnalysis(
            id=region_id,
            label=label,
            bbox=bbox,
            area_pct=area_pct,
            method=winner_method,
            confidence=confidence,
            evidence=evidence_list,
            contradictions=contradictions,
        )

        return region_analysis, contradictions, review_items
