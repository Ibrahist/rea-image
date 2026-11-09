"""Schema for evaluation benchmark dataset items and evaluation metrics."""

from typing import List, Optional
from pydantic import BaseModel, Field


class LabeledRegion(BaseModel):
    id: str
    expected_method: str
    area_pct: float
    bbox: Optional[List[int]] = None


class EvalItem(BaseModel):
    id: str
    image_path: str
    split: str = Field(..., description="'tuning' or 'held_out'")
    condition: str = Field(..., description="'original', 'compressed', or 'screenshot'")
    expected_dominant_method: str
    expected_regions: List[LabeledRegion] = Field(default_factory=list)


class CalibrationBin(BaseModel):
    bin_name: str
    confidence_range: str
    sample_count: int
    correct_count: int
    empirical_accuracy_pct: float


class EvalSummary(BaseModel):
    total_images: int
    tuning_accuracy_pct: float
    held_out_accuracy_pct: float
    original_accuracy_pct: float
    compressed_accuracy_pct: float
    screenshot_accuracy_pct: float
    calibration_bins: List[CalibrationBin] = Field(default_factory=list)
    is_calibrated: bool = Field(default=True)
    calibration_errors: List[str] = Field(default_factory=list)

