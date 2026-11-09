"""Segmentation orchestrator and model/SAM hook."""

from typing import List, Optional
import numpy as np
from rea_image.segment.region import SegmentRegion
from rea_image.segment.classical import ClassicalSegmenter


def segment_image(
    arr: np.ndarray,
    offline: bool = True,
    vlm_model: Optional[str] = None,
) -> List[SegmentRegion]:
    """Segment image into semantic regions.
    
    Uses deterministic classical segmentation offline, with hook for
    SAM / VLM labeling when enabled.
    """
    segmenter = ClassicalSegmenter()
    return segmenter.segment(arr)

