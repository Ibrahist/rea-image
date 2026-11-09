"""Base evidence collector interface and evidence item definitions."""

from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
from rea_image.schemas import EvidenceItem
from rea_image.ingest.loader import IngestResult


class BaseDetector(ABC):
    """Abstract base class for all evidence detectors."""

    name: str = "base_detector"

    @abstractmethod
    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        """Extract evidence items from the ingested image and optional regions."""
        pass

    def run_region(self, crop: np.ndarray, region_id: str, mask: Optional[np.ndarray] = None) -> List[EvidenceItem]:
        """Extract evidence items specific to a cropped region and mask."""
        return []


def make_evidence(
    name: str,
    value: any,
    direction: str,
    strength: float,
    explanation: str,
    region: str = "global",
) -> EvidenceItem:
    """Helper factory for EvidenceItem instances."""
    return EvidenceItem(
        name=name,
        value=value,
        region=region,
        direction=direction,
        strength=max(0.0, min(1.0, float(strength))),
        explanation=explanation,
    )

