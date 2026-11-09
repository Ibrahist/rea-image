"""Evidence collection package: provenance, generator traces, export traces, forensics, and craft analysis."""

from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.evidence.provenance import ProvenanceDetector
from rea_image.evidence.generator_traces import GeneratorTracesDetector
from rea_image.evidence.export_traces import ExportTracesDetector
from rea_image.evidence.forensics_noise import ForensicsNoiseDetector
from rea_image.evidence.forensics_jpeg import ForensicsJpegDetector
from rea_image.evidence.forensics_frequency import ForensicsFrequencyDetector
from rea_image.evidence.forensics_flat import ForensicsFlatDetector
from rea_image.evidence.visual_checks import VisualChecksDetector
from rea_image.evidence.craft_color import extract_dominant_palette, analyze_color_grade
from rea_image.evidence.craft_composition import analyze_composition
from rea_image.evidence.craft_camera import CameraCraftEstimator
from rea_image.evidence.craft_lighting import LightingClassifier
from rea_image.evidence.typography import TypographyAnalyzer, analyze_layout_grid

__all__ = [
    "BaseDetector",
    "make_evidence",
    "ProvenanceDetector",
    "GeneratorTracesDetector",
    "ExportTracesDetector",
    "ForensicsNoiseDetector",
    "ForensicsJpegDetector",
    "ForensicsFrequencyDetector",
    "ForensicsFlatDetector",
    "VisualChecksDetector",
    "extract_dominant_palette",
    "analyze_color_grade",
    "analyze_composition",
    "CameraCraftEstimator",
    "LightingClassifier",
    "TypographyAnalyzer",
    "analyze_layout_grid",
]
