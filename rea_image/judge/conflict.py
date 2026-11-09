"""Conflict detector and agent review task generator."""

from typing import List, Tuple
from rea_image.schemas import EvidenceItem, NeedsReviewItem


class ConflictDetector:
    """Identifies contradictory signals and formulates questions for agent review."""

    def find_conflicts(
        self,
        evidence_list: List[EvidenceItem],
        region_id: str = "global",
    ) -> Tuple[List[str], List[NeedsReviewItem]]:
        contradictions: List[str] = []
        review_items: List[NeedsReviewItem] = []

        # 1. Real photo signals (hardware EXIF or physical optical/sensor forensics)
        photo_signals = [
            ev for ev in evidence_list
            if ev.direction == "real photograph"
            and ev.name in ("camera_exif", "jpeg_grid_aligned", "natural_frequency_falloff", "sensor_poisson_noise", "continuous_natural_gradients")
            and ev.strength >= 0.4
        ]
        has_camera_exif = any(ev.name == "camera_exif" for ev in photo_signals)
        has_photo_signals = len(photo_signals) > 0

        # 2. AI synthetic signals
        ai_signals = [
            ev for ev in evidence_list
            if ev.direction == "AI-generated"
            and ev.name in ("ai_generator_metadata", "spectral_peaks_upscaler", "ai_style_plastic_sheen")
            and ev.strength >= 0.3
        ]
        has_ai_signals = len(ai_signals) > 0

        # 3. Graphic / vector signals
        graphic_signals = [
            ev for ev in evidence_list
            if ev.direction == "vector or graphic design"
            and ev.name in ("flat_color_runs", "ela_minimal_error")
            and ev.strength >= 0.3
        ]
        has_graphic_signals = len(graphic_signals) > 0

        # 4. Splicing / noise composite signals
        has_noise_composite = any(ev.name in ("noise_inconsistency_composite", "jpeg_grid_misalignment") for ev in evidence_list)

        # Conflict 1: Camera EXIF or optical photo signals coexist with AI synthetic indicators
        has_hard_ai = any(ev.name in ("ai_generator_metadata", "c2pa_assertion") for ev in ai_signals)
        # If hard AI metadata is verified, only hard camera EXIF can genuinely contradict it
        should_flag_photo_ai_conflict = (has_camera_exif or not has_hard_ai) if has_photo_signals else False

        if should_flag_photo_ai_conflict and has_ai_signals:
            photo_names = ", ".join(ev.name for ev in photo_signals)
            ai_names = ", ".join(ev.name for ev in ai_signals)
            msg = f"Conflict: Real photograph signals ({photo_names}) coexist with AI synthetic indicators ({ai_names})."
            contradictions.append(msg)
            reason_str = "EXIF vs. Synthetic artifacts mismatch" if has_camera_exif else "Optical photo vs. AI synthetic conflict"
            review_items.append(
                NeedsReviewItem(
                    region_id=region_id,
                    reason=reason_str,
                    question_for_agent=(
                        f"Inspect image details and noise texture for agent review: optical signals ({photo_names}) contradict AI indicators ({ai_names}). "
                        "Determine if this is an authentic photograph affected by compression/resizing, or generative AI with simulated photographic properties."
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

        # Conflict 3: Real photo indicators mixed with flat vector runs
        if has_photo_signals and has_graphic_signals:
            photo_names = ", ".join(ev.name for ev in photo_signals)
            graphic_names = ", ".join(ev.name for ev in graphic_signals)
            msg = f"Conflict: Photographic signals ({photo_names}) coexist with vector graphic signals ({graphic_names})."
            contradictions.append(msg)
            review_items.append(
                NeedsReviewItem(
                    region_id=region_id,
                    reason="Mixed photo and graphic layers" if has_camera_exif else "Photo vs. Vector graphic conflict",
                    question_for_agent=(
                        f"Photographic signals ({photo_names}) coexist with graphic signals ({graphic_names}). "
                        "Verify whether text banners, logos, or UI elements were digitally overlaid onto a photograph, or if recompression caused false flat runs."
                    ),
                )
            )

        return contradictions, review_items

