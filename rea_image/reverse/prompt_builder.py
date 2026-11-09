"""Layered reverse prompt generator and setting recommendations."""

from typing import Any, Dict, List, Optional
from rea_image.schemas import ReverseInfo


class PromptBuilder:
    """Builds layered generation prompts, variants, negative prompts, and workflow recommendations."""

    def build(
        self,
        subject_desc: str,
        setting_desc: str,
        style_desc: str,
        camera_lens: Optional[dict] = None,
        lighting_info: Optional[dict] = None,
        color_info: Optional[dict] = None,
        aspect_ratio: str = "1:1",
        model_family: str = "FLUX-style",
    ) -> ReverseInfo:
        # Assemble layered prompt components
        layers: List[str] = []

        # 1. Subject & Action
        layers.append(subject_desc or "a centered high-detail subject")

        # 2. Setting / Background
        if setting_desc:
            layers.append(f"set in {setting_desc}")

        # 3. Medium & Style
        layers.append(style_desc or "photorealistic aesthetic")

        # 4. Camera & Lens
        if camera_lens:
            focal = camera_lens.get("estimated_focal_length", "50mm lens")
            aperture = camera_lens.get("estimated_aperture", "f/2.8")
            layers.append(f"shot on {focal}, {aperture}")

        # 5. Lighting
        if lighting_info:
            setup = lighting_info.get("matched_setup", "soft directional lighting")
            temp = lighting_info.get("color_temperature", "natural daylight")
            layers.append(f"{setup.lower()}, {temp}")

        # 6. Color Grade
        if color_info:
            split = color_info.get("split_toning", "neutral")
            sat = color_info.get("saturation_level", "natural saturation")
            if split != "neutral":
                layers.append(f"{split}, {sat}")

        # 7. Quality & Render details
        layers.append("ultra-detailed, 8k resolution, crisp textures, masterpieces composition")

        faithful_prompt = ", ".join(layers)

        # Simplified prompt
        simplified_prompt = f"{subject_desc}, {setting_desc}, {style_desc}, cinematic lighting"

        # Style transfer prompt (with placeholder subject)
        style_tokens = []
        if style_desc:
            style_tokens.append(style_desc)
        if lighting_info:
            style_tokens.append(lighting_info.get("matched_setup", ""))
        if color_info and color_info.get("split_toning") != "neutral":
            style_tokens.append(color_info.get("split_toning", ""))
        style_transfer_prompt = f"[SUBJECT], {', '.join([s for s in style_tokens if s])}, shot on 50mm f/2.8"

        # Negative prompt
        negative_prompt = (
            "blurry, low resolution, deformed anatomy, distorted fingers, extra limbs, "
            "poorly rendered hands, warped perspective, oversaturated plastic skin, text artifacts, watermark"
        )

        # Recommended settings
        settings = {
            "aspect_ratio": aspect_ratio,
            "steps": 28,
            "guidance_scale": 6.0 if "flux" in model_family.lower() else 7.0,
            "sampler": "Euler a" if "flux" in model_family.lower() else "DPM++ 2M Karras",
            "recommended_model": "FLUX.1 [dev]" if "flux" in model_family.lower() else "Midjourney v6.1",
        }

        # Workflow recommendation
        workflow = (
            "Text-to-Image base generation for subject + environment. "
            "Render typographic text blocks and logos separately in Figma/vector tool to avoid AI glyph distortion."
        )

        return ReverseInfo(
            prompt=faithful_prompt,
            negative_prompt=negative_prompt,
            settings=settings,
            variants={
                "faithful": faithful_prompt,
                "simplified": simplified_prompt,
                "style_transfer": style_transfer_prompt,
            },
            suggested_workflow=workflow,
        )

