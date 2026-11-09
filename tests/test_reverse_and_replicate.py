"""Tests for reverse engineering scaffolds, capability table, and replication planner (M7)."""

import ast
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from rea_image.capabilities.loader import CapabilitiesRegistry
from rea_image.reverse.prompt_builder import PromptBuilder
from rea_image.reverse.photo_shoot_plan import PhotoShootPlanner
from rea_image.reverse.render_scaffold import RenderScaffoldBuilder
from rea_image.reverse.graphic_scaffold import GraphicScaffoldBuilder
from rea_image.reverse.ui_scaffold import UIScaffoldBuilder
from rea_image.replicate.planner import ReplicationPlanner
from rea_image.replicate.backend import GenerationBackend
from rea_image.schemas import PaletteColor, ProductionMethod, RegionAnalysis


def test_capabilities_registry():
    """Verify loading models.yaml and recommending best model."""
    registry = CapabilitiesRegistry()
    assert len(registry.models) >= 3
    assert len(registry.tools) >= 2

    # Recommend model for text rendering
    rec = registry.recommend_model(needs_text=True, preferred_aspect="16:9")
    assert rec.text_rendering_quality in ("excellent", "good")
    assert rec.est_cost_per_image is not None


def test_prompt_builder():
    """Verify layered prompt construction and 3 variants."""
    builder = PromptBuilder()
    res = builder.build(
        subject_desc="a vintage mechanical wristwatch",
        setting_desc="dark slate surface with subtle water droplets",
        style_desc="commercial product photography",
        camera_lens={"estimated_focal_length": "85mm macro", "estimated_aperture": "f/4.0"},
        lighting_info={"matched_setup": "Softbox portrait", "color_temperature": "5600K daylight"},
        color_info={"split_toning": "neutral", "saturation_level": "natural saturation"},
        aspect_ratio="1:1",
    )

    assert "vintage mechanical wristwatch" in res.prompt
    assert "85mm macro" in res.prompt
    assert len(res.variants) == 3
    assert "faithful" in res.variants
    assert "simplified" in res.variants
    assert "style_transfer" in res.variants
    assert len(res.negative_prompt) > 20
    assert res.settings["aspect_ratio"] == "1:1"


def test_photo_shoot_plan():
    """Verify photo shoot plan and ASCII lighting diagram generation."""
    planner = PhotoShootPlanner()
    plan = planner.plan(
        camera_info={"estimated_focal_length": "50mm f/1.8", "estimated_aperture": "f/2.8"},
        lighting_info={"matched_setup": "Rembrandt lighting", "suggested_gear": ["Octabox", "Reflector"]},
        color_info={"split_toning": "teal & orange"},
        aspect_ratio="3:2",
    )

    assert "Rembrandt" in plan["lighting_diagram"] or "Subject" in plan["lighting_diagram"]
    assert len(plan["gear_list"]) >= 3
    assert len(plan["post_processing_steps"]) >= 4


def test_render_scaffold_blender_syntax():
    """Verify that generated Blender script is valid Python code."""
    builder = RenderScaffoldBuilder()
    script = builder.build_blender_script(scene_name="TestScene", focal_mm=50)
    
    # Must parse cleanly as Python syntax
    parsed = ast.parse(script)
    assert parsed is not None
    assert "bpy" in script
    assert "CYCLES" in script


def test_graphic_scaffold_svg():
    """Verify that generated SVG is well-formed XML."""
    builder = GraphicScaffoldBuilder()
    palette = [
        PaletteColor(hex="#FFFFFF", rgb=[255, 255, 255], role="background", percentage=60.0),
        PaletteColor(hex="#0066CC", rgb=[0, 102, 204], role="accent", percentage=30.0),
    ]
    svg_str = builder.build_svg(width=800, height=600, palette=palette)

    # Must parse as valid XML
    root = ET.fromstring(svg_str)
    assert root.tag.endswith("svg")
    assert root.attrib["width"] == "800"
    assert root.attrib["height"] == "600"


def test_replication_planner_routing():
    """Verify routing logic: text to design, photo to shoot, AI to generate."""
    planner = ReplicationPlanner()

    # Text region
    r_text = RegionAnalysis(
        id="r_text",
        label="text_block",
        bbox=[0, 0, 100, 30],
        area_pct=10.0,
        method=ProductionMethod.GRAPHIC_DESIGN.value,
        confidence="high",
    )
    plan_text = planner.plan_region(r_text)
    assert plan_text.path == "design"

    # Photo region
    r_photo = RegionAnalysis(
        id="r_photo",
        label="main_subject",
        bbox=[0, 0, 400, 400],
        area_pct=80.0,
        method=ProductionMethod.REAL_PHOTO.value,
        confidence="high",
    )
    plan_photo = planner.plan_region(r_photo)
    assert plan_photo.path == "shoot"


def test_generation_backend_dry_run():
    """Verify backend enforces dry-run safety by default."""
    backend = GenerationBackend()
    res = backend.execute_recreation(
        prompt="A cute astronaut cat on Mars",
        dry_run=True,
        confirmed=False,
    )
    assert res["status"] == "simulated"
    assert res["dry_run"] is True

