"""Exports verdict.txt, layer masks/crops, and recreate starter files."""

from pathlib import Path
from typing import List, Optional
from PIL import Image
from rea_image.schemas import ReportSchema
from rea_image.segment.region import SegmentRegion


def export_assets_bundle(
    report: ReportSchema,
    segment_regions: List[SegmentRegion],
    base_image: Image.Image,
    out_dir: Path,
    blender_script: Optional[str] = None,
    svg_scaffold: Optional[str] = None,
    html_scaffold: Optional[str] = None,
    shoot_plan_data: Optional[dict] = None,
) -> dict:
    """Exports verdict.txt, layers/ folder, and recreate/ folder."""
    out_dir.mkdir(parents=True, exist_ok=True)
    exported_paths = {}

    # 1. verdict.txt
    verdict_path = out_dir / "verdict.txt"
    verdict_path.write_text(report.verdict.summary.strip() + "\n", encoding="utf-8")
    exported_paths["verdict_txt"] = verdict_path

    # 2. layers/ (masks and crops)
    layers_dir = out_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    
    # Save original preview copy in output root for HTML report
    orig_copy_path = out_dir / "original.png"
    base_image.save(orig_copy_path, format="PNG")
    exported_paths["original_image"] = orig_copy_path

    for r, seg_r in zip(report.regions, segment_regions):
        m_path, c_path = seg_r.save_mask_and_crop(layers_dir, base_image)
        # Store relative paths in report models
        r.mask_path = f"layers/{m_path.name}"
        r.crop_path = f"layers/{c_path.name}"

    exported_paths["layers_dir"] = layers_dir

    # 3. recreate/ starter files
    recreate_dir = out_dir / "recreate"
    recreate_dir.mkdir(parents=True, exist_ok=True)

    # Prompt file
    prompts_text = []
    for r in report.regions:
        if r.reverse and r.reverse.prompt:
            prompts_text.append(f"=== Region {r.id} ({r.label}) ===")
            prompts_text.append(f"Prompt (Faithful):\n{r.reverse.prompt}\n")
            if r.reverse.variants.get("simplified"):
                prompts_text.append(f"Prompt (Simplified):\n{r.reverse.variants['simplified']}\n")
            if r.reverse.variants.get("style_transfer"):
                prompts_text.append(f"Prompt (Style Transfer):\n{r.reverse.variants['style_transfer']}\n")
            if r.reverse.negative_prompt:
                prompts_text.append(f"Negative Prompt:\n{r.reverse.negative_prompt}\n")
            if r.reverse.settings:
                prompts_text.append(f"Recommended Settings: {r.reverse.settings}\n")
            prompts_text.append("-" * 50 + "\n")

    if prompts_text:
        prompt_path = recreate_dir / "prompt.txt"
        prompt_path.write_text("\n".join(prompts_text), encoding="utf-8")
        exported_paths["prompt_txt"] = prompt_path

    # SVG Scaffold
    if svg_scaffold:
        svg_path = recreate_dir / "scaffold.svg"
        svg_path.write_text(svg_scaffold, encoding="utf-8")
        exported_paths["scaffold_svg"] = svg_path

    # HTML/CSS Scaffold
    if html_scaffold:
        html_path = recreate_dir / "scaffold.html"
        html_path.write_text(html_scaffold, encoding="utf-8")
        exported_paths["scaffold_html"] = html_path

    # Blender Python Script
    if blender_script:
        blender_path = recreate_dir / "starter_scene.py"
        blender_path.write_text(blender_script, encoding="utf-8")
        exported_paths["starter_scene_py"] = blender_path

    # Shoot Plan Markdown
    if shoot_plan_data:
        shoot_md_lines = [
            "# Photo Shoot Plan & Production Notes\n",
            f"**Location**: {shoot_plan_data.get('location', 'Studio')}\n",
            "## Camera Settings",
            f"- Lens: {shoot_plan_data.get('camera_settings', {}).get('lens', '50mm')}",
            f"- Aperture: {shoot_plan_data.get('camera_settings', {}).get('aperture', 'f/2.8')}",
            f"- Shutter: {shoot_plan_data.get('camera_settings', {}).get('shutter_speed', '1/160s')}",
            f"- ISO: {shoot_plan_data.get('camera_settings', {}).get('iso', '100')}\n",
            "## ASCII Lighting Diagram",
            "```text",
            shoot_plan_data.get("lighting_diagram", ""),
            "```\n",
            "## Suggested Gear List",
        ]
        for g in shoot_plan_data.get("gear_list", []):
            shoot_md_lines.append(f"- {g}")

        shoot_md_lines.append("\n## Post-Processing Workflow")
        for step in shoot_plan_data.get("post_processing_steps", []):
            shoot_md_lines.append(f"- {step}")

        shoot_path = recreate_dir / "shoot_plan.md"
        shoot_path.write_text("\n".join(shoot_md_lines), encoding="utf-8")
        exported_paths["shoot_plan_md"] = shoot_path

    return exported_paths

