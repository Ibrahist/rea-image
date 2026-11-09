"""Configuration management for rea-image."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # Execution mode
    offline: bool = Field(default=True, description="Run purely offline with zero network calls.")
    agent_review: bool = Field(default=False, description="Enable agent-review mode to export review tasks.")
    
    # Caching
    cache_enabled: bool = Field(default=True, description="Enable SHA256-based caching for expensive operations.")
    cache_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("REA_IMAGE_CACHE_DIR", Path.home() / ".cache" / "rea_image"))
    )

    # Ingest limits
    max_image_pixels: int = Field(default=100_000_000, description="Max pixel count before tile processing.")
    preview_max_dim: int = Field(default=1280, description="Max dimension for model/preview downscaling.")
    
    # Supported extensions
    supported_extensions: set[str] = {
        ".jpg", ".jpeg", ".png", ".webp", ".heic", ".tiff", ".tif", ".bmp", ".avif"
    }

    # VLM Configuration (Optional, opt-in only)
    vlm_provider: Optional[str] = Field(default=None, description="VLM provider: openai, gemini, anthropic, or custom")
    vlm_model: Optional[str] = Field(default=None, description="VLM model identifier")
    vlm_endpoint: Optional[str] = Field(default=None, description="Custom OpenAI-compatible endpoint")
    vlm_api_key: Optional[str] = Field(default=None, description="API Key for VLM (loaded from env)")

    # Output defaults
    default_output_dir: Path = Field(default_factory=lambda: Path("./rea_output"))

    @classmethod
    def from_env(cls, offline: Optional[bool] = None, agent_review: Optional[bool] = None) -> "Settings":
        env_offline = os.getenv("REA_IMAGE_OFFLINE", "true").lower() in ("1", "true", "yes")
        if offline is not None:
            env_offline = offline

        vlm_key = (
            os.getenv("REA_IMAGE_VLM_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
        )
        
        return cls(
            offline=env_offline,
            agent_review=agent_review if agent_review is not None else False,
            vlm_provider=os.getenv("REA_IMAGE_VLM_PROVIDER"),
            vlm_model=os.getenv("REA_IMAGE_VLM_MODEL"),
            vlm_endpoint=os.getenv("REA_IMAGE_VLM_ENDPOINT"),
            vlm_api_key=vlm_key,
        )


settings = Settings.from_env()

