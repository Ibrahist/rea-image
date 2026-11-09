"""Capability table loader and models schema."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class ModelCapability(BaseModel):
    id: str
    name: str
    provider: str
    max_resolution: str
    supported_aspect_ratios: List[str]
    reference_image_support: bool
    text_rendering_quality: str
    inpainting_support: bool
    style_control: str
    pricing_tier: str
    est_cost_per_image: str
    last_verified: str


class ToolCapability(BaseModel):
    id: str
    category: str
    name: str
    license: str
    est_cost: str
    controllability: str
    last_verified: str


class CapabilitiesRegistry:
    """Loads and queries capabilities for generation models and production tools."""

    def __init__(self, dir_path: Optional[Path] = None):
        if dir_path is None:
            dir_path = Path(__file__).parent
        self.dir_path = dir_path
        self.models: List[ModelCapability] = []
        self.tools: List[ToolCapability] = []
        self._load()

    def _load(self):
        models_file = self.dir_path / "models.yaml"
        if models_file.exists():
            with open(models_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.models = [ModelCapability(**m) for m in data.get("models", [])]

        tools_file = self.dir_path / "tools.yaml"
        if tools_file.exists():
            with open(tools_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.tools = [ToolCapability(**t) for t in data.get("tools", [])]

    def recommend_model(
        self,
        needs_text: bool = False,
        preferred_aspect: str = "1:1",
        budget: str = "budget",
    ) -> ModelCapability:
        """Find the best matching model given requirements."""
        candidates = self.models
        if needs_text:
            candidates = [m for m in candidates if m.text_rendering_quality in ("excellent", "good")]

        # Match aspect ratio
        matched_ar = [m for m in candidates if preferred_aspect in m.supported_aspect_ratios]
        if matched_ar:
            candidates = matched_ar

        # Match budget
        matched_budget = [m for m in candidates if m.pricing_tier == budget]
        if matched_budget:
            return matched_budget[0]

        return candidates[0] if candidates else self.models[0]

