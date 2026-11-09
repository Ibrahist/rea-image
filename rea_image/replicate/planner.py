"""Cheapest viable path replication planner and batching coordinator."""

from typing import Any, Dict, List, Optional
from rea_image.schemas import ProductionMethod, RecreatePlan, RegionAnalysis
from rea_image.capabilities.loader import CapabilitiesRegistry


class ReplicationPlanner:
    """Plans the most cost-effective and controllable recreation route per region and whole image."""

    def __init__(self, registry: Optional[CapabilitiesRegistry] = None):
        self.registry = registry or CapabilitiesRegistry()

    def plan_region(self, region: RegionAnalysis, aspect_ratio: str = "1:1") -> RecreatePlan:
        method = region.method
        label = region.label

        # 1. Text blocks, UI elements, or logos -> always route to DESIGN
        if label in ("text_block", "ui_element", "logo_watermark") or method == ProductionMethod.GRAPHIC_DESIGN.value:
            return RecreatePlan(
                path="design",
                steps=[
                    "1. Open Figma, Penpot, or Adobe Illustrator with canvas matching image bounds.",
                    "2. Import extracted SVG scaffold (scaffold.svg) and extract typography specifications.",
                    "3. Apply exact hex color tokens from the extracted palette.",
                    "4. Export as transparent PNG / SVG asset to composite over visual layers.",
                ],
                tools=["Figma", "Penpot", "Adobe Illustrator", "Inkscape"],
                est_cost="$0.00",
                est_time="15m",
                starter_files=["scaffold.svg", "typography_spec.json"],
            )

        # 2. UI Screenshot -> route to DESIGN / CODE
        if method == ProductionMethod.UI_SCREENSHOT.value:
            return RecreatePlan(
                path="design",
                steps=[
                    "1. Open scaffold.html in browser or VS Code.",
                    "2. Adjust CSS custom properties for palette and typography scale.",
                    "3. Replace dummy cards with real production content / screenshots.",
                ],
                tools=["HTML/CSS", "Tailwind CSS", "Browser"],
                est_cost="$0.00",
                est_time="20m",
                starter_files=["scaffold.html"],
            )

        # 3. 3D Render -> evaluate GENERATE vs RENDER
        if method == ProductionMethod.RENDER_3D.value:
            return RecreatePlan(
                path="render",
                steps=[
                    "1. Launch Blender and run starter_scene.py in the Scripting workspace.",
                    "2. Adjust object geometry to match the reference bounding silhouette.",
                    "3. Set Cycles samples to 256 with OptiX / OpenImageDenoise.",
                    "4. Render F12 and export 16-bit PNG.",
                ],
                tools=["Blender 4.x (Cycles)", "Three.js"],
                est_cost="$0.00",
                est_time="45m",
                starter_files=["starter_scene.py"],
            )

        # 4. Real photograph -> evaluate SHOOT vs GENERATE trade-off
        if method == ProductionMethod.REAL_PHOTO.value:
            # If high-budget physical fidelity needed: shoot; if rapid low-cost: AI prompt
            return RecreatePlan(
                path="shoot",
                steps=[
                    "1. Setup studio camera with prime lens matching estimated focal length.",
                    "2. Assemble lighting rig following the generated ASCII lighting diagram.",
                    "3. Capture bracketed exposures at base ISO.",
                    "4. Apply color grading LUT and exposure curves in post-processing.",
                ],
                tools=["DSLR / Mirrorless Camera", "50mm Prime Lens", "Studio Lighting Rig"],
                est_cost="$0.00 (with gear) / $150 (day rental)",
                est_time="2h",
                starter_files=["shoot_plan.md"],
            )

        # 5. Default / AI-Generated -> route to GENERATE
        model = self.registry.recommend_model(preferred_aspect=aspect_ratio)
        return RecreatePlan(
            path="generate",
            steps=[
                f"1. Submit layered prompt to {model.name}.",
                "2. Generate 4 initial candidates at recommended seed and aspect ratio.",
                "3. Inpaint any anatomical defects or artifacts using regional mask.",
                "4. Upscale using 2x/4x latent or clarity upscaler.",
            ],
            tools=[model.name, f"{model.provider} API"],
            est_cost=model.est_cost_per_image,
            est_time="2m",
            starter_files=["prompt.txt"],
        )

    def plan_batching(self, regions: List[RegionAnalysis]) -> Dict[str, Any]:
        """Group regions that can be generated together vs what must be isolated."""
        gen_batch = []
        design_batch = []
        manual_batch = []

        for r in regions:
            if r.label in ("text_block", "ui_element", "logo_watermark"):
                design_batch.append(r.id)
            elif r.recreate.path == "generate":
                gen_batch.append(r.id)
            else:
                manual_batch.append(r.id)

        explanation = (
            "Batching Strategy: Background and visual subjects are generated together in one AI pass. "
            "Typography and graphic text layers MUST be overlaid separately in a vector/design tool "
            "because text generation in raster diffusion models is prone to spelling errors and lack of font control."
        )

        return {
            "ai_generation_batch": gen_batch,
            "vector_design_batch": design_batch,
            "manual_or_shoot_batch": manual_batch,
            "strategy_rationale": explanation,
        }

