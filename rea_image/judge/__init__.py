"""Judgment package: weighted evidence fusion, conflict detection, and verdict aggregation."""

from rea_image.judge.engine import JudgmentEngine
from rea_image.judge.conflict import ConflictDetector
from rea_image.judge.aggregator import VerdictAggregator
from rea_image.judge.style_matcher import estimate_ai_model_family

__all__ = [
    "JudgmentEngine",
    "ConflictDetector",
    "VerdictAggregator",
    "estimate_ai_model_family",
]

