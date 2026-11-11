"""Data schemas and types for rea-image according to specification."""

import math
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


def format_rational(val: Any) -> Optional[float]:
    """Convert rational (IFDRational, Fraction, tuple, str, float) to float, handling zero denominators safely."""
    if val is None:
        return None
    try:
        if isinstance(val, (bool, str)):
            if isinstance(val, str):
                if "/" in val:
                    n, d = val.split("/", 1)
                    return float(n) / float(d) if float(d) != 0 else None
                return float(val)
            return None
        if hasattr(val, "item") and not isinstance(val, (int, float)):
            try:
                val = val.item()
            except Exception:
                pass
        if isinstance(val, (int, float)):
            return float(val)
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            num = getattr(val, "numerator")
            den = getattr(val, "denominator")
            return float(num) / float(den) if den != 0 else None
        if isinstance(val, (tuple, list)):
            if len(val) == 1:
                return format_rational(val[0])
            if len(val) >= 2:
                num = format_rational(val[0])
                den = format_rational(val[1])
                if num is not None and den is not None and den != 0:
                    return num / den
    except Exception:
        pass
    return None


def clean_json_value(val: Any) -> Any:
    """Recursively convert unknown objects (IFDRational, bytes, numpy scalars, etc.) to JSON-safe values."""
    if val is None:
        return None
    if isinstance(val, (bool, str)):
        return val
    # Numpy scalars / arrays
    if hasattr(val, "item") and not isinstance(val, (int, float, bool, str)):
        try:
            val = val.item()
            if isinstance(val, (bool, str, int)):
                return val
            if isinstance(val, float):
                if math.isnan(val) or math.isinf(val):
                    return None
                return val
        except Exception:
            pass
    if hasattr(val, "tolist") and not isinstance(val, (list, tuple)):
        try:
            return clean_json_value(val.tolist())
        except Exception:
            pass
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    # IFDRational, Fraction, or any object with numerator/denominator
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        try:
            num = getattr(val, "numerator")
            den = getattr(val, "denominator")
            if den == 0:
                return None
            return float(num) / float(den)
        except Exception:
            return None
    # Bytes
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8", errors="replace").strip("\x00")
        except Exception:
            return repr(val)
    # Sequences (tuples, sets, lists) -> list
    if isinstance(val, (list, tuple, set)):
        return [clean_json_value(x) for x in val]
    # Mappings
    if isinstance(val, dict):
        return {str(k): clean_json_value(v) for k, v in val.items()}
    # Fallback to string
    return str(val)


class ProductionMethod(str, Enum):
    REAL_PHOTO = "real photograph"
    AI_GENERATED = "AI-generated"
    RENDER_3D = "3D render"
    GRAPHIC_DESIGN = "vector or graphic design"
    UI_SCREENSHOT = "UI or screenshot"
    ILLUSTRATION = "illustration or painting"
    COMPOSITE = "composite"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM_LOW = "medium-low"
    MEDIUM = "medium"
    MEDIUM_HIGH = "medium-high"
    HIGH = "high"


class ImageMetadata(BaseModel):
    path: str
    sha256: str
    width: int
    height: int
    format: str
    aspect_ratio: str
    bit_depth: Optional[int] = 8
    color_mode: Optional[str] = "RGB"
    icc_profile: Optional[str] = None
    dpi: Optional[tuple[float, float]] = None
    perceptual_hash: Optional[str] = None


class EvidenceItem(BaseModel):
    name: str = Field(..., description="Name of the signal or detector")
    value: Any = Field(..., description="Observed value or metric")
    region: str = Field(default="global", description="Region id or 'global'")
    direction: str = Field(..., description="Which method this evidence supports (or opposes)")
    strength: float = Field(..., ge=0.0, le=1.0, description="Confidence strength between 0.0 and 1.0")
    explanation: str = Field(..., description="Plain-language interpretation")

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, v: Any) -> Any:
        return clean_json_value(v)

    @field_serializer("value", mode="plain")
    def serialize_value(self, v: Any) -> Any:
        return clean_json_value(v)


class MethodBreakdownItem(BaseModel):
    method: str
    area_pct: float = Field(..., ge=0.0, le=100.0)


class Verdict(BaseModel):
    summary: str
    confidence: str
    method_breakdown: List[MethodBreakdownItem] = Field(default_factory=list)

    @property
    def dominant_method(self) -> str:
        return self.method_breakdown[0].method if self.method_breakdown else ProductionMethod.REAL_PHOTO.value


class PaletteColor(BaseModel):
    hex: str
    rgb: list[int]
    role: str = Field(..., description="background, subject, accent, or text")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class TypographyInfo(BaseModel):
    font_family_candidates: List[str] = Field(default_factory=list)
    weight: Optional[str] = None
    size_hierarchy: Optional[str] = None
    line_spacing: Optional[Union[float, str]] = None
    tracking: Optional[Union[float, str]] = None
    alignment: Optional[str] = None
    text_styling: List[str] = Field(default_factory=list)
    extracted_text: Optional[str] = None


class CompositionInfo(BaseModel):
    aspect_ratio: str
    rule_of_thirds: Optional[Dict[str, Any]] = None
    golden_ratio: Optional[Dict[str, Any]] = None
    leading_lines: Optional[List[Dict[str, Any]]] = None
    framing: Optional[str] = None
    negative_space_pct: Optional[float] = None
    subject_scale_pct: Optional[float] = None
    focal_hierarchy: Optional[List[str]] = None


class LightingSetupInfo(BaseModel):
    matched_setup: str = Field(default="ambient", description="One of 12 standard lighting setups")
    direction: Optional[str] = None
    softness: Optional[str] = None
    color_temperature: Optional[str] = None
    ratio: Optional[str] = None
    suggested_gear: List[str] = Field(default_factory=list)


class CraftInfo(BaseModel):
    camera_lens: Optional[Dict[str, Any]] = Field(default_factory=dict)
    lighting: Optional[LightingSetupInfo] = None
    color_grade: Optional[Dict[str, Any]] = Field(default_factory=dict)
    scene_description: Optional[str] = None


class ReverseInfo(BaseModel):
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    variants: Dict[str, str] = Field(
        default_factory=lambda: {
            "faithful": "",
            "simplified": "",
            "style_transfer": "",
        }
    )
    suggested_workflow: Optional[str] = None


class RecreatePlan(BaseModel):
    path: str = Field(..., description="shoot, generate, render, or design")
    steps: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    est_cost: str = Field(default="$0.00")
    est_time: str = Field(default="10m")
    starter_files: List[str] = Field(default_factory=list)


class RegionAnalysis(BaseModel):
    id: str
    label: str
    bbox: List[int] = Field(..., description="[x, y, width, height]")
    mask_path: Optional[str] = None
    crop_path: Optional[str] = None
    area_pct: float = Field(..., ge=0.0, le=100.0)
    method: str
    confidence: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    top_contradicting: List[EvidenceItem] = Field(default_factory=list)
    typography: Dict[str, Any] = Field(default_factory=dict)
    palette: List[PaletteColor] = Field(default_factory=list)
    composition: Dict[str, Any] = Field(default_factory=dict)
    craft: Dict[str, Any] = Field(default_factory=dict)
    reverse: ReverseInfo = Field(default_factory=ReverseInfo)
    recreate: RecreatePlan = Field(default_factory=lambda: RecreatePlan(path="design"))


class NeedsReviewItem(BaseModel):
    region_id: str
    reason: str
    question_for_agent: str


class GlobalAnalysis(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    forensics: Dict[str, Any] = Field(default_factory=dict)
    palette: List[PaletteColor] = Field(default_factory=list)
    composition: Dict[str, Any] = Field(default_factory=dict)
    lighting: Dict[str, Any] = Field(default_factory=dict)
    color_grade: Dict[str, Any] = Field(default_factory=dict)
    typography: Dict[str, Any] = Field(default_factory=dict)
    layout_grid: Dict[str, Any] = Field(default_factory=dict)
    camera: Dict[str, Any] = Field(default_factory=dict)


class ReportSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    image: ImageMetadata
    verdict: Verdict
    regions: List[RegionAnalysis] = Field(default_factory=list)
    global_analysis: GlobalAnalysis = Field(..., alias="global")
    needs_review: List[NeedsReviewItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

