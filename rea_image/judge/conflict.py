"""Conflict detector and agent review task generator."""

from typing import List, Tuple
from rea_image.schemas import EvidenceItem, NeedsReviewItem, ProductionMethod


class ConflictDetector:
    """Identifies contradictory signals and formulates questions for agent review."""

    def find_conflicts(
        self,
        evidence_list: List[EvidenceItem],
        region_id: str = "global",
    ) -> Tuple[List[str], List[NeedsReviewItem]]:
        contradictions: List[str] = []
        review_items: List[NeedsReviewItem] = []

        has_camera_exif = any(ev.name == "camera_exif" for ev in evidence_list)
        has_ai_metadata = any(ev.name == "ai_generator_metadata" for ev in evidence_list)
        has_ai_forensics = any(ev.name in ("spectral_peaks_upscaler", "ai_style_plastic_sheen") for ev in evidence_list)
        has_flat_graphic = any(ev.name == "flat_color_runs" for ev in evidence_list)
        has_noise_composite = any(ev.name in ("noise_inconsistency_composite", "jpeg_grid_misalignment") for ev in evidence_list)

        # Conflict 1: Camera EXIF present, but AI metadata or AI forensics detected
        if has_camera_exif and (has_ai_metadata or has_ai_forensics):
            msg = "Conflict: Camera hardware EXIF is present, but AI synthetic indicators were also detected."
            contradictions.append(msg)
            review_items.append(
                NeedsReviewItem(
                    region_id=region_id,
                    reason="EXIF vs. Synthetic artifacts mismatch",
                    question_for_agent=(
                        "Inspect image boundaries, fine details (fingers, pupils, text), and noise texture. "
                        "Determine if camera EXIF is authentic with AI post-processing/inpainting, or if EXIF was spoofed/copied onto an AI generation."
                    ),
                )
            )

        # Conflict 2: Severe regional noise / compression inconsistency
        if has_noise_composite:
            msg = "Conflict: Splicing / composite signals detected across regions."
            contradictions.append(msg)
            review_items.append(
                NeedsReviewItem(
                    region_id=region_id,
                    reason="Spatial noise / JPEG grid discontinuity",
                    question_for_agent=(
                        "Examine the boundary between the main subject and background. "
                        "Is there evidence of edge feathering, cutout halos, or divergent lighting angles typical of a composite collage?"
                    ),
                )
            )

        # Conflict 3: Real photo indicators mixed with pure flat vector runs
        if has_camera_exif and has_flat_graphic:
            msg = "Conflict: Photographic camera capture combined with exact vector graphic flat runs."
            contradictions.append(msg)
            review_items.append(
                NeedsReviewItem(
                    region_id=region_id,
                    reason="Mixed photo and graphic layers",
                    question_for_agent=(
                        "Verify whether text banners, logos, or UI badges were digitally overlaid onto a real photograph."
                    ),
                )
            )

        return contradictions, review_items

