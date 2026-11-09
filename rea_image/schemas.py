"""Data schemas and types for rea-image according to specification."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


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


class MethodBreakdownItem(BaseModel):
    method: str
    area_pct: float = Field(..., ge=0.0, le=100.0)


class Verdict(BaseModel):
    summary: str
    confidence: str
    method_breakdown: List[MethodBreakdownItem] = Field(default_factory=list)


class PaletteColor(BaseModel):
    hex: str
    rgb: list[int]
    role: str = Field(..., description="background, subject, accent, or text")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class TypographyInfo(BaseModel):
    font_family_candidates: List[str] = Field(default_factory=list)
    weight: Optional[str] = None
    size_hierarchy: Optional[str] = None
    line_spacing: Optional[float] = None
    tracking: Optional[float] = None
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


class ReportSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    image: ImageMetadata
    verdict: Verdict
    regions: List[RegionAnalysis] = Field(default_factory=list)
    global_analysis: GlobalAnalysis = Field(..., alias="global")
    needs_review: List[NeedsReviewItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

