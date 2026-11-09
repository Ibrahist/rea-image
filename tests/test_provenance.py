"""Tests for provenance, generator traces, and export traces detectors (M2)."""

import json
from pathlib import Path
from PIL import Image, PngImagePlugin
from rea_image.ingest.loader import load_image
from rea_image.evidence.provenance import ProvenanceDetector
from rea_image.evidence.generator_traces import GeneratorTracesDetector
from rea_image.evidence.export_traces import ExportTracesDetector
from rea_image.schemas import ProductionMethod


def test_a1111_png_generator_traces(tmp_path: Path):
    """Test extracting Automatic1111 / Stable Diffusion parameters from PNG chunks."""
    img_path = tmp_path / "sd_sample.png"
    img = Image.new("RGB", (256, 256), color=(100, 150, 200))
    
    png_info = PngImagePlugin.PngInfo()
    params = (
        "masterpiece, cinematic portrait of an astronaut on Mars, photorealistic, 8k\n"
        "Negative prompt: low quality, blurry, deformed hands, extra fingers\n"
        "Steps: 28, Sampler: DPM++ 2M Karras, CFG scale: 7.0, Seed: 3829104, Size: 512x512, Model hash: cc6f68ecce, Model: realisticVisionV5"
    )
    png_info.add_text("parameters", params)
    img.save(img_path, format="PNG", pnginfo=png_info)

    res = load_image(img_path)
    detector = GeneratorTracesDetector()
    items = detector.run(res)

    assert len(items) >= 1
    ai_item = next(it for it in items if it.name == "ai_generator_metadata")
    assert ai_item.direction == ProductionMethod.AI_GENERATED.value
    assert ai_item.strength >= 0.95
    assert "cinematic portrait of an astronaut" in ai_item.value["prompt"]
    assert "deformed hands" in ai_item.value["negative_prompt"]
    assert ai_item.value["parameters"]["seed"] == 3829104
    assert ai_item.value["parameters"]["steps"] == 28
    assert ai_item.value["parameters"]["sampler"] == "DPM++ 2M Karras"


def test_comfyui_metadata_traces(tmp_path: Path):
    """Test extracting prompt and model from ComfyUI JSON chunks."""
    img_path = tmp_path / "comfy_sample.png"
    img = Image.new("RGB", (256, 256), color=(20, 20, 20))
    
    comfy_prompt = {
        "3": {
            "class_type": "KSampler",
            "inputs": {"steps": 25, "cfg": 8.0, "seed": 998877}
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "flux1-dev.safetensors"}
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "cyberpunk neon alleyway in Tokyo, rainy reflections"}
        }
    }
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("prompt", json.dumps(comfy_prompt))
    img.save(img_path, format="PNG", pnginfo=png_info)

    res = load_image(img_path)
    detector = GeneratorTracesDetector()
    items = detector.run(res)

    ai_item = next(it for it in items if it.name == "ai_generator_metadata")
    assert ai_item.direction == ProductionMethod.AI_GENERATED.value
    assert "cyberpunk neon alleyway" in ai_item.value["prompt"]
    assert ai_item.value["parameters"]["seed"] == 998877
    assert ai_item.value["parameters"]["model"] == "flux1-dev.safetensors"


def test_photoshop_export_traces(tmp_path: Path):
    """Test identifying Adobe Photoshop export software traces."""
    img_path = tmp_path / "ps_sample.png"
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("Software", "Adobe Photoshop 2024 (Windows)")
    img.save(img_path, format="PNG", pnginfo=png_info)

    res = load_image(img_path)
    detector = ExportTracesDetector()
    items = detector.run(res)

    sw_item = next(it for it in items if it.name == "export_software_signature")
    assert sw_item.direction == ProductionMethod.GRAPHIC_DESIGN.value
    assert sw_item.value["tool"] == "Adobe Photoshop"
    assert sw_item.strength >= 0.70


def test_missing_camera_metadata(sample_png: Path):
    """Test weak neutral evidence when camera EXIF is missing."""
    res = load_image(sample_png)
    detector = ProvenanceDetector()
    items = detector.run(res)

    missing_item = next(it for it in items if it.name == "camera_exif_missing")
    assert missing_item.direction == "neutral"
    assert missing_item.strength <= 0.3

