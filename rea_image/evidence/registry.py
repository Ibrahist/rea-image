"""Detector plugin registry and entry-point discovery."""

import importlib.metadata
from typing import Any, Dict, List, Optional, Type
from rea_image.evidence.provenance import ProvenanceDetector
from rea_image.evidence.generator_traces import GeneratorTracesDetector
from rea_image.evidence.export_traces import ExportTracesDetector
from rea_image.evidence.forensics_noise import ForensicsNoiseDetector
from rea_image.evidence.forensics_jpeg import ForensicsJpegDetector
from rea_image.evidence.forensics_frequency import ForensicsFrequencyDetector
from rea_image.evidence.forensics_flat import ForensicsFlatDetector
from rea_image.evidence.visual_checks import VisualChecksDetector

# Built-in detector registry
DETECTORS: Dict[str, Type] = {
    "provenance": ProvenanceDetector,
    "generator_traces": GeneratorTracesDetector,
    "export_traces": ExportTracesDetector,
    "noise": ForensicsNoiseDetector,
    "jpeg": ForensicsJpegDetector,
    "frequency": ForensicsFrequencyDetector,
    "flat": ForensicsFlatDetector,
    "visual_checks": VisualChecksDetector,
}


def register_detector(name: str, detector_cls: Type) -> None:
    """Register a detector class dynamically."""
    DETECTORS[name.lower()] = detector_cls


def get_detector_registry() -> Dict[str, Type]:
    """Return all registered detectors, including third-party entry points."""
    try:
        eps = importlib.metadata.entry_points(group="rea_image.detectors")
        for ep in eps:
            if ep.name not in DETECTORS:
                try:
                    DETECTORS[ep.name] = ep.load()
                except Exception:
                    pass
    except Exception:
        pass
    return dict(DETECTORS)


def get_active_detectors(disabled: Optional[List[str]] = None) -> List[Any]:
    """Instantiate and return active detectors, excluding any disabled ones."""
    registry = get_detector_registry()
    disabled_set = {d.lower().strip() for d in (disabled or []) if d}

    instances = []
    for name, cls in registry.items():
        if name in disabled_set:
            continue
        try:
            instances.append(cls())
        except Exception:
            pass
    return instances
