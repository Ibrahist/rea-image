"""Segmentation package: classical fallback, OCR merger, and region management."""

from rea_image.segment.region import SegmentRegion
from rea_image.segment.classical import ClassicalSegmenter
from rea_image.segment.ocr_merger import OCRTextDetector
from rea_image.segment.model_hook import segment_image

__all__ = [
    "SegmentRegion",
    "ClassicalSegmenter",
    "OCRTextDetector",
    "segment_image",
]

