"""Tests for camera hardware detection and optical forensics."""

from pathlib import Path
import numpy as np
from PIL import Image, ExifTags
from typer.testing import CliRunner
from rea_image.cli import app
from rea_image.evidence.camera_detector import (
    CameraDetector,
    classify_camera_device,
    _format_lens_specification,
)
from rea_image.report.orchestrator import run_analysis_pipeline

runner = CliRunner()


def test_classify_camera_device_catalog():
    """Test device categorization, sensor formats, and crop factors across brands."""
    # Smartphones
    iphone = classify_camera_device("Apple", "iPhone 15 Pro Max")
    assert iphone["device_type"] == "smartphone"
    assert iphone["canonical_make"] == "Apple"
    assert iphone["sensor_format"] == "smartphone_large_sensor"
    assert iphone["sensor_crop_factor"] == 3.2

    pixel = classify_camera_device("Google", "Pixel 8 Pro")
    assert pixel["device_type"] == "smartphone"
    assert pixel["canonical_make"] == "Google"

    samsung = classify_camera_device("samsung", "SM-S928B")
    assert samsung["device_type"] == "smartphone"
    assert samsung["canonical_make"] == "Samsung"

    # Sony mirrorless
    sony_ff = classify_camera_device("Sony", "ILCE-7M4")
    assert sony_ff["device_type"] == "mirrorless"
    assert sony_ff["sensor_format"] == "full_frame"
    assert sony_ff["sensor_crop_factor"] == 1.0

    sony_apsc = classify_camera_device("Sony", "ILCE-6700")
    assert sony_apsc["device_type"] == "mirrorless"
    assert sony_apsc["sensor_format"] == "aps_c"
    assert sony_apsc["sensor_crop_factor"] == 1.5

    # Canon mirrorless & DSLR
    canon_r5 = classify_camera_device("Canon", "Canon EOS R5")
    assert canon_r5["device_type"] == "mirrorless"
    assert canon_r5["sensor_format"] == "full_frame"

    canon_5d = classify_camera_device("Canon", "Canon EOS 5D Mark IV")
    assert canon_5d["device_type"] == "dslr"
    assert canon_5d["sensor_format"] == "full_frame"

    canon_rebel = classify_camera_device("Canon", "Canon EOS Rebel T7i")
    assert canon_rebel["device_type"] == "dslr"
    assert canon_rebel["sensor_format"] == "aps_c"

    # Nikon mirrorless & DSLR
    nikon_z = classify_camera_device("NIKON CORPORATION", "NIKON Z 8")
    assert nikon_z["device_type"] == "mirrorless"
    assert nikon_z["sensor_format"] == "full_frame"

    nikon_d = classify_camera_device("NIKON CORPORATION", "NIKON D850")
    assert nikon_d["device_type"] == "dslr"
    assert nikon_d["sensor_format"] == "full_frame"

    # Drones & Action cams
    dji = classify_camera_device("DJI", "FC3582")
    assert dji["device_type"] == "drone"

    gopro = classify_camera_device("GoPro", "HERO11 Black")
    assert gopro["device_type"] == "action_cam"

    # Medium format
    fuji_gfx = classify_camera_device("FUJIFILM", "GFX 100 II")
    assert fuji_gfx["device_type"] == "medium_format"
    assert fuji_gfx["sensor_crop_factor"] == 0.79


def test_camera_catalog_table_driven():
    """Exhaustive table-driven test verifying >= 60 make/model pairs and edge cases."""
    test_cases = [
        # (Make, Model, Expected Device Type, Expected Sensor Format, Expected Crop Factor)
        # Nikon DX
        ("Nikon", "D3500", "dslr", "aps_c", 1.5),
        ("Nikon", "D5600", "dslr", "aps_c", 1.5),
        ("Nikon", "D7500", "dslr", "aps_c", 1.5),
        ("Nikon", "D500", "dslr", "aps_c", 1.5),
        ("Nikon", "D300s", "dslr", "aps_c", 1.5),
        ("Nikon", "D90", "dslr", "aps_c", 1.5),
        ("Nikon", "Z 50", "mirrorless", "aps_c", 1.5),
        ("Nikon", "Z fc", "mirrorless", "aps_c", 1.5),
        ("Nikon", "Z 30", "mirrorless", "aps_c", 1.5),
        # Nikon FX
        ("NIKON CORPORATION", "NIKON D850", "dslr", "full_frame", 1.0),
        ("Nikon", "D810", "dslr", "full_frame", 1.0),
        ("Nikon", "D780", "dslr", "full_frame", 1.0),
        ("Nikon", "D750", "dslr", "full_frame", 1.0),
        ("Nikon", "D6", "dslr", "full_frame", 1.0),
        ("Nikon", "D5", "dslr", "full_frame", 1.0),
        ("Nikon", "Df", "dslr", "full_frame", 1.0),
        ("Nikon", "Z 8", "mirrorless", "full_frame", 1.0),
        ("Nikon", "Z 6_2", "mirrorless", "full_frame", 1.0),
        ("Nikon", "Z f", "mirrorless", "full_frame", 1.0),
        ("Nikon", "Nikon 1 J5", "mirrorless", "one_inch", 2.7),
        ("Nikon", "COOLPIX P1000", "compact", "1/2.3_inch", 5.6),
        # Canon Compact
        ("Canon", "IXUS 185", "compact", "1/2.3_inch", 5.6),
        ("Canon", "IXY 650", "compact", "1/2.3_inch", 5.6),
        ("Canon", "PowerShot G7 X Mark III", "compact", "one_inch", 2.7),
        ("Canon", "PowerShot SX740 HS", "compact", "1/2.3_inch", 5.6),
        # Canon Mirrorless & DSLR Full-Frame
        ("Canon", "EOS R5", "mirrorless", "full_frame", 1.0),
        ("Canon", "EOS R6 Mark II", "mirrorless", "full_frame", 1.0),
        ("Canon", "EOS RP", "mirrorless", "full_frame", 1.0),
        ("Canon", "EOS 5D Mark IV", "dslr", "full_frame", 1.0),
        ("Canon", "EOS 6D", "dslr", "full_frame", 1.0),
        ("Canon", "EOS-1D X Mark III", "dslr", "full_frame", 1.0),
        # Canon Mirrorless & DSLR APS-C
        ("Canon", "EOS R7", "mirrorless", "aps_c", 1.6),
        ("Canon", "EOS R10", "mirrorless", "aps_c", 1.6),
        ("Canon", "EOS R50", "mirrorless", "aps_c", 1.6),
        ("Canon", "EOS M50 Mark II", "mirrorless", "aps_c", 1.6),
        ("Canon", "EOS 7D Mark II", "dslr", "aps_c", 1.6),
        ("Canon", "EOS 90D", "dslr", "aps_c", 1.6),
        ("Canon", "EOS Rebel T7i", "dslr", "aps_c", 1.6),
        ("Canon", "EOS 850D", "dslr", "aps_c", 1.6),
        # Sony Compact
        ("Sony", "DSC-W830", "compact", "1/2.3_inch", 5.6),
        ("Sony", "DSC-HX400V", "compact", "1/2.3_inch", 5.6),
        ("Sony", "DSC-RX100M7", "compact", "one_inch", 2.7),
        ("Sony", "ZV-1", "compact", "one_inch", 2.7),
        ("Sony", "DSC-RX1R", "compact", "full_frame", 1.0),
        # Sony Phone
        ("Sony", "XQ-BC52", "smartphone", "smartphone_small", 4.0),
        ("Sony", "Xperia 1 V", "smartphone", "smartphone_small", 4.0),
        # Sony Mirrorless APS-C
        ("Sony", "ILCE-6700", "mirrorless", "aps_c", 1.5),
        ("Sony", "ILCE-6400", "mirrorless", "aps_c", 1.5),
        ("Sony", "ZV-E10", "mirrorless", "aps_c", 1.5),
        ("Sony", "NEX-5N", "mirrorless", "aps_c", 1.5),
        # Sony Mirrorless Full-Frame
        ("Sony", "ILCE-7M4", "mirrorless", "full_frame", 1.0),
        ("Sony", "ILCE-7RM5", "mirrorless", "full_frame", 1.0),
        ("Sony", "ILCE-1", "mirrorless", "full_frame", 1.0),
        ("Sony", "FX3", "mirrorless", "full_frame", 1.0),
        ("Sony", "ZV-E1", "mirrorless", "full_frame", 1.0),
        # Leica
        ("Leica", "CL", "mirrorless", "aps_c", 1.5),
        ("Leica", "TL2", "mirrorless", "aps_c", 1.5),
        ("Leica", "D-LUX 7", "compact", "micro_four_thirds", 2.0),
        ("Leica", "Q3", "mirrorless", "full_frame", 1.0),
        ("Leica", "SL2", "mirrorless", "full_frame", 1.0),
        ("Leica", "M11", "mirrorless", "full_frame", 1.0),
        ("Leica", "S3", "dslr", "medium_format", 0.79),
        # Panasonic
        ("Panasonic", "DC-S5", "mirrorless", "full_frame", 1.0),
        ("Panasonic", "DC-S1H", "mirrorless", "full_frame", 1.0),
        ("Panasonic", "DMC-FZ1000", "compact", "one_inch", 2.7),
        ("Panasonic", "DC-GH6", "mirrorless", "micro_four_thirds", 2.0),
        ("Panasonic", "DC-G9", "mirrorless", "micro_four_thirds", 2.0),
        # Pentax
        ("Pentax", "K-1", "dslr", "full_frame", 1.0),
        ("Pentax", "K-3 Mark III", "dslr", "aps_c", 1.5),
        ("Pentax", "K-70", "dslr", "aps_c", 1.5),
        ("Pentax", "645Z", "dslr", "medium_format", 0.79),
        # Sigma
        ("Sigma", "fp", "mirrorless", "full_frame", 1.0),
        ("Sigma", "fp L", "mirrorless", "full_frame", 1.0),
        ("Sigma", "sd Quattro", "mirrorless", "aps_c", 1.5),
        # Fujifilm
        ("Fujifilm", "FinePix S5700", "compact", "1/2.5_inch", 6.0),
        ("Fujifilm", "X100V", "compact", "aps_c", 1.5),
        ("Fujifilm", "X-T5", "mirrorless", "aps_c", 1.5),
        ("Fujifilm", "GFX 100 II", "medium_format", "medium_format", 0.79),
        # DJI
        ("DJI", "FC2103", "drone", "one_inch", 2.7),
        ("DJI", "Osmo Pocket 3", "action_cam", "one_inch", 2.7),
        ("DJI", "FC3582", "drone", "micro_four_thirds", 2.0),
        ("DJI", "Mini 4 Pro", "drone", "1/1.3_inch", 3.2),
        # Hasselblad
        ("Hasselblad", "L1D-20c", "drone", "one_inch", 2.7),
        ("Hasselblad", "X2D 100C", "medium_format", "medium_format", 0.79),
        # Apple
        ("Apple", "iPad Pro", "tablet", "smartphone_small", 4.0),
        ("Apple", "iPhone 15 Pro Max", "smartphone", "smartphone_large_sensor", 3.2),
        ("Apple", "iPhone 13", "smartphone", "smartphone_small", 4.0),
        # Samsung
        ("Samsung", "SM-S918B", "smartphone", "smartphone_large_sensor", 3.2),
        ("Samsung", "SM-S928B", "smartphone", "smartphone_large_sensor", 3.2),
        ("Samsung", "SM-A546B", "smartphone", "smartphone_small", 4.0),
        # Google
        ("Google", "Pixel 8 Pro", "smartphone", "smartphone_large_sensor", 3.2),
        ("Google", "Pixel 7a", "smartphone", "smartphone_small", 4.0),
        # African & Budget Smartphones
        ("Tecno", "CK7n", "smartphone", "smartphone_small", 4.0),
        ("Infinix", "X6816", "smartphone", "smartphone_small", 4.0),
        ("itel", "A662LM", "smartphone", "smartphone_small", 4.0),
        ("realme", "RMX3363", "smartphone", "smartphone_small", 4.0),
        ("Nokia", "G20", "smartphone", "smartphone_small", 4.0),
        ("Nokia", "TA-1336", "smartphone", "smartphone_small", 4.0),
        # Unknown cases (MUST yield unknown, never confident hallucinations)
        ("Acme", "SuperCam 9000", "unknown", "unknown", None),
        ("Canon", "NonExistentModelXYZ", "unknown", "unknown", None),
        ("Sony", "RandomGizmo123", "unknown", "unknown", None),
        ("TotallyUnknownMake", "Unknown123", "unknown", "unknown", None),
    ]

    assert len(test_cases) >= 60, f"Expected >= 60 test cases, got {len(test_cases)}"

    for make, model, exp_type, exp_format, exp_crop in test_cases:
        res = classify_camera_device(make, model)
        assert res["device_type"] == exp_type, f"Failed type for {make} {model}: got {res['device_type']}, expected {exp_type}"
        assert res["sensor_format"] == exp_format, f"Failed sensor for {make} {model}: got {res['sensor_format']}, expected {exp_format}"
        assert res["sensor_crop_factor"] == exp_crop, f"Failed crop for {make} {model}: got {res['sensor_crop_factor']}, expected {exp_crop}"


def test_hardware_exif_camera_detection(tmp_path: Path):
    """Test extracting camera specs from an image with genuine EXIF data."""
    img_path = tmp_path / "sony_photo.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 15, (200, 300, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Sony"
    exif[ExifTags.Base.Model] = "ILCE-7M4"
    exif[ExifTags.Base.Software] = "ILCE-7M4 v2.00"
    exif[ExifTags.Base.DateTime] = "2024:06:15 14:30:00"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.LensModel] = "FE 24-70mm F2.8 GM II"
    exif_ifd[ExifTags.Base.FocalLength] = (50, 1)
    exif_ifd[ExifTags.Base.FocalLengthIn35mmFilm] = 50
    exif_ifd[ExifTags.Base.FNumber] = (28, 10)
    exif_ifd[ExifTags.Base.ExposureTime] = (1, 250)
    exif_ifd[ExifTags.Base.ISOSpeedRatings] = 100

    img.save(img_path, "JPEG", exif=exif)

    detector = CameraDetector()
    with Image.open(img_path) as loaded_img:
        hw_cam = detector.extract_hardware_exif(img=loaded_img, path=img_path)

    assert hw_cam is not None
    assert hw_cam["detected"] is True
    assert hw_cam["source"] == "exif_metadata"
    assert hw_cam["confidence"] == "medium"
    assert hw_cam["make"] == "Sony"
    assert hw_cam["model"] == "ILCE-7M4"
    assert hw_cam["device_type"] == "mirrorless"
    assert hw_cam["sensor_format"] == "full_frame"
    assert hw_cam["sensor_crop_factor"] == 1.0
    assert hw_cam["lens"] == "FE 24-70mm F2.8 GM II"
    assert hw_cam["focal_length"] == "50.0mm"
    assert hw_cam["focal_length_35mm"] == "50mm"
    assert hw_cam["aperture"] == "f/2.8"
    assert hw_cam["shutter_speed"] == "1/250s"
    assert hw_cam["iso"] == "100"
    assert "Sony ILCE-7M4" in hw_cam["summary"]

    # When corroborated through detect() with matching 3:2 aspect, focal ratio, and noise
    with Image.open(img_path) as loaded_img:
        corroborated = detector.detect(
            arr=np.array(loaded_img),
            aspect_ratio="3:2",
            optical_craft={},
            img=loaded_img,
            path=img_path,
            is_photograph=True,
        )
    assert corroborated["confidence"] == "high"
    assert len(corroborated["why_believed"]) >= 2
    assert not corroborated["why_doubted"]


def test_inferred_optical_camera_detection():
    """Test camera type inference when EXIF is stripped."""
    detector = CameraDetector()

    # Case 1: Native 4:3 aspect ratio with deep DoF
    arr_4_3 = np.zeros((1200, 1600, 3), dtype=np.uint8)
    arr_4_3[:, :] = [120, 150, 180]
    optical_craft_4_3 = {
        "depth_of_field": "deep depth of field (all elements sharp)",
        "estimated_aperture": "f/1.8",
        "estimated_focal_length": "26mm equivalent",
    }
    res_phone = detector.infer_from_optics(arr_4_3, aspect_ratio="4:3", optical_craft=optical_craft_4_3, is_photograph=True)
    assert res_phone["detected"] is True
    assert res_phone["source"] == "optical_forensics"
    assert res_phone["device_type"] == "smartphone"
    assert res_phone["sensor_format"] == "smartphone_small"
    assert res_phone["candidates"][0]["class"] == "smartphone"
    assert res_phone["candidates"][0]["probability"] > 0.5

    # Case 2: Native 3:2 aspect ratio with shallow DoF
    arr_3_2 = np.zeros((1024, 1536, 3), dtype=np.uint8)
    arr_3_2[:, :] = [100, 120, 140]
    optical_craft_3_2 = {
        "depth_of_field": "shallow depth of field (cinematic separation)",
        "estimated_aperture": "f/1.4",
        "estimated_focal_length": "85mm portrait telephoto",
    }
    res_dslr = detector.infer_from_optics(arr_3_2, aspect_ratio="3:2", optical_craft=optical_craft_3_2, is_photograph=True)
    assert res_dslr["detected"] is True
    assert res_dslr["device_type"] == "mirrorless_or_dslr"
    assert res_dslr["sensor_format"] == "aps_c_or_full_frame"
    assert res_dslr["candidates"][0]["class"] == "dedicated_camera"
    assert res_dslr["candidates"][0]["probability"] > 0.5

    # Case 3: Resized non-native dimensions -> Ambiguous camera profile
    arr_resized = np.zeros((300, 400, 3), dtype=np.uint8)
    res_ambiguous = detector.infer_from_optics(arr_resized, aspect_ratio="4:3", optical_craft=optical_craft_4_3, is_photograph=True)
    assert res_ambiguous["display_name"] == "Inferred: Ambiguous Camera Profile"
    assert res_ambiguous["confidence"] == "low"
    assert len(res_ambiguous["candidates"]) == 2

    # Case 4: Non-photographic image
    res_non_photo = detector.infer_from_optics(arr_3_2, aspect_ratio="3:2", optical_craft=optical_craft_3_2, is_photograph=False)
    assert res_non_photo["detected"] is False
    assert res_non_photo["source"] == "none"


def test_cli_camera_command(tmp_path: Path):
    """Test 'rea-image camera' CLI subcommand in both Rich table and JSON mode."""
    img_path = tmp_path / "phone_shot.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 25, (300, 400, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Apple"
    exif[ExifTags.Base.Model] = "iPhone 14 Pro"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.LensModel] = "iPhone 14 Pro back triple camera 6.86mm f/1.78"
    exif_ifd[ExifTags.Base.FocalLength] = (686, 100)
    exif_ifd[ExifTags.Base.FocalLengthIn35mmFilm] = 24
    exif_ifd[ExifTags.Base.FNumber] = (178, 100)
    exif_ifd[ExifTags.Base.ExposureTime] = (1, 120)
    exif_ifd[ExifTags.Base.ISOSpeedRatings] = 80

    img.save(img_path, "JPEG", exif=exif)

    # 1. Human-readable card output
    res_card = runner.invoke(app, ["camera", str(img_path)])
    assert res_card.exit_code == 0
    assert "Apple iPhone 14 Pro" in res_card.output
    assert "Smartphone" in res_card.output
    assert "Hardware EXIF" in res_card.output
    assert "f/1.8" in res_card.output or "f/1.78" in res_card.output

    # 2. JSON output
    res_json = runner.invoke(app, ["camera", str(img_path), "--json"])
    assert res_json.exit_code == 0
    assert '"make": "Apple"' in res_json.output
    assert '"model": "iPhone 14 Pro"' in res_json.output
    assert '"device_type": "smartphone"' in res_json.output
    assert '"shutter_speed": "1/120s"' in res_json.output


def test_report_orchestrator_includes_detected_camera(tmp_path: Path):
    """Test full analysis orchestrator populates camera in global analysis and report.html."""
    img_path = tmp_path / "report_cam.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 25, (200, 300, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "Canon EOS R5"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.LensModel] = "RF24-70mm F2.8 L IS USM"
    exif_ifd[ExifTags.Base.FocalLength] = (70, 1)
    exif_ifd[ExifTags.Base.FNumber] = (28, 10)
    exif_ifd[ExifTags.Base.ExposureTime] = (1, 500)
    exif_ifd[ExifTags.Base.ISOSpeedRatings] = 200

    img.save(img_path, "JPEG", exif=exif)

    out_dir = tmp_path / "report_cam_out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir, no_cache=True)

    # Check global analysis contains camera
    assert report.global_analysis.camera is not None
    assert report.global_analysis.camera.get("detected") is True
    assert report.global_analysis.camera.get("make") == "Canon"
    assert report.global_analysis.camera.get("model") == "Canon EOS R5"
    assert report.global_analysis.camera.get("device_type") == "mirrorless"

    # Check HTML report contains camera hardware profile
    html_content = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "Camera Hardware & Optical Profile" in html_content
    assert "Canon EOS R5" in html_content
    assert "RF24-70mm" in html_content

    # Check shoot plan includes detected camera
    shoot_plan = (out_dir / "recreate" / "shoot_plan.md").read_text(encoding="utf-8")
    assert "Canon EOS R5" in shoot_plan


def test_camera_detection_non_photographic(tmp_path: Path):
    """Test non-photographs report 'No physical camera' and omit camera lines from shoot plan."""
    ai_img = Path("eval/benchmark_data/images/ai_original.png")
    if not ai_img.exists():
        return

    out_dir = tmp_path / "ai_cam_out"
    report = run_analysis_pipeline(ai_img, out_dir=out_dir, no_cache=True)

    cam = report.global_analysis.camera
    assert cam.get("detected") is False
    assert cam.get("summary") == "No physical camera (non-photographic image)"
    assert cam.get("display_name") == "No Physical Camera Detected"

    # Verify shoot plan has no camera lines
    shoot_plan = (out_dir / "recreate" / "shoot_plan.md").read_text(encoding="utf-8")
    assert "## Camera Settings" not in shoot_plan
    assert "Camera:" not in shoot_plan


def test_camera_exif_on_ai_image_conflict(tmp_path: Path):
    """Test camera EXIF on an AI-generated image produces a 'claimed by metadata' conflict."""
    from PIL import PngImagePlugin

    img_path = tmp_path / "ai_with_exif.png"
    img = Image.new("RGB", (300, 300), color=(120, 140, 160))

    # Add AI PNG chunk metadata to force AI verdict
    meta = PngImagePlugin.PngInfo()
    meta.add_text("parameters", "A cinematic portrait of an astronaut, masterwork, Unreal Engine 5 render, highly detailed")

    # Add hardware camera EXIF
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Nikon"
    exif[ExifTags.Base.Model] = "NIKON D850"

    img.save(img_path, "PNG", pnginfo=meta, exif=exif)

    out_dir = tmp_path / "ai_exif_out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir, no_cache=True)

    cam = report.global_analysis.camera
    assert cam.get("claimed_by_metadata") is True
    assert cam.get("confidence") == "low"
    assert "claimed by metadata" in cam.get("display_name", "").lower()
    assert "claimed by metadata" in cam.get("summary", "").lower()

    # Verify conflict added to needs_review
    conflict_found = any(
        "metadata claims" in r.reason and "pixels indicate" in r.reason
        for r in report.needs_review
    )
    assert conflict_found, f"Needs review conflict missing from {report.needs_review}"

    # Verify shoot plan omits camera body
    shoot_plan = (out_dir / "recreate" / "shoot_plan.md").read_text(encoding="utf-8")
    assert "## Camera Settings" not in shoot_plan
    assert "Camera: NIKON D850" not in shoot_plan


def test_inferred_camera_shoot_plan_class_phrasing(tmp_path: Path):
    """Test camera in shoot plan is phrased as a class for inferred cameras on real photographs."""
    from rea_image.reverse.photo_shoot_plan import PhotoShootPlanner

    planner = PhotoShootPlanner()
    camera_info = {
        "detected_camera": {
            "detected": True,
            "source": "optical_forensics",
            "device_type_label": "Dedicated Mirrorless / DSLR Camera",
            "summary": "Inferred: Likely Dedicated Camera",
        },
        "estimated_focal_length": "50mm normal lens",
        "estimated_aperture": "f/1.8",
    }
    lighting_info = {"matched_setup": "Window light"}
    color_info = {"split_toning": "neutral"}

    plan = planner.plan(
        camera_info=camera_info,
        lighting_info=lighting_info,
        color_info=color_info,
        is_photograph=True,
    )
    assert plan["camera_settings"]["camera"] == "any dedicated camera with 50mm normal lens"
    assert "Camera: any dedicated camera with 50mm normal lens" in plan["gear_list"]


def test_apex_values_conversion(tmp_path: Path):
    """Test converting APEX ApertureValue and ShutterSpeedValue to standard camera notation."""
    detector = CameraDetector()

    # Case 1: Av = 3.0 -> f = 2^(3/2) = 2.828 -> f/2.8
    img_path = tmp_path / "apex_3.jpg"
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Nikon"
    exif[ExifTags.Base.Model] = "Z 6"
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.ApertureValue] = (30, 10)  # APEX Av = 3.0
    exif_ifd[ExifTags.Base.ShutterSpeedValue] = (80, 10)  # APEX Tv = 8.0 -> 2^(-8) = 1/256s
    img.save(img_path, "JPEG", exif=exif)

    with Image.open(img_path) as loaded:
        hw = detector.extract_hardware_exif(img=loaded, path=img_path)
    assert hw is not None
    assert hw["aperture"] == "f/2.8"
    assert hw["shutter_speed"] in ("1/256s", "1/250s")

    # Case 2: Av = 5.0 -> f = 2^(5/2) = 5.657 -> f/5.6
    img_path2 = tmp_path / "apex_5.jpg"
    img2 = Image.new("RGB", (100, 100), color=(100, 100, 100))
    exif2 = img2.getexif()
    exif2[ExifTags.Base.Make] = "Nikon"
    exif2[ExifTags.Base.Model] = "Z 6"
    exif_ifd2 = exif2.get_ifd(ExifTags.IFD.Exif)
    exif_ifd2[ExifTags.Base.ApertureValue] = (50, 10)  # APEX Av = 5.0
    exif_ifd2[ExifTags.Base.ShutterSpeedValue] = (0, 1)  # APEX Tv = 0 -> 1.0s
    img2.save(img_path2, "JPEG", exif=exif2)

    with Image.open(img_path2) as loaded:
        hw2 = detector.extract_hardware_exif(img=loaded, path=img_path2)
    assert hw2 is not None
    assert hw2["aperture"] == "f/5.7" or hw2["aperture"] == "f/5.6"
    assert hw2["shutter_speed"] == "1s"


def test_lens_model_make_and_specification(tmp_path: Path):
    """Test combining LensMake + LensModel and formatting LensSpecification."""
    detector = CameraDetector()

    # Case 1: Combine LensMake + LensModel
    img_path = tmp_path / "lens_combine.jpg"
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "EOS 5D Mark IV"
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.LensMake] = "Canon"
    exif_ifd[ExifTags.Base.LensModel] = "EF 50mm f/1.8 STM"
    img.save(img_path, "JPEG", exif=exif)

    with Image.open(img_path) as loaded:
        hw = detector.extract_hardware_exif(img=loaded, path=img_path)
    assert hw is not None
    assert hw["lens"] == "Canon EF 50mm f/1.8 STM"

    # Case 2: Missing LensModel, format LensSpecification
    assert _format_lens_specification(((24, 1), (70, 1), (28, 10), (28, 10)), "Canon") == "Canon 24-70mm f/2.8"
    assert _format_lens_specification(((50, 1), (50, 1), (18, 10), (18, 10)), None) == "50mm f/1.8"
    assert _format_lens_specification(((18, 1), (55, 1), (35, 10), (56, 10)), "Nikon") == "Nikon 18-55mm f/3.5-5.6"

    # Case 3: Verify extract_hardware_exif formats LensSpecification
    from unittest.mock import MagicMock
    mock_img = MagicMock()
    mock_exif = {
        ExifTags.Base.Make: "Canon",
        ExifTags.Base.Model: "EOS 5D Mark IV",
    }
    mock_ifd = {
        ExifTags.Base.LensMake: "Canon",
        ExifTags.Base.LensSpecification: ((24, 1), (70, 1), (28, 10), (28, 10)),
    }
    mock_exif_obj = MagicMock()
    mock_exif_obj.items.return_value = mock_exif.items()
    mock_exif_obj.get_ifd.return_value = mock_ifd
    mock_img.getexif.return_value = mock_exif_obj

    hw2 = detector.extract_hardware_exif(img=mock_img, path=None)
    assert hw2 is not None
    assert hw2["lens"] == "Canon 24-70mm f/2.8"


def test_privacy_serial_number_filtering(tmp_path: Path):
    """Test device serial numbers and owner names are stripped from hardware EXIF."""
    detector = CameraDetector()

    img_path = tmp_path / "privacy.jpg"
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Sony"
    exif[ExifTags.Base.Model] = "ILCE-7M4"
    exif[ExifTags.Base.Artist] = "John Doe Photographer"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.BodySerialNumber] = "SN-987654321"
    exif_ifd[ExifTags.Base.LensSerialNumber] = "LENS-123456"
    exif_ifd[ExifTags.Base.CameraOwnerName] = "Private User"
    img.save(img_path, "JPEG", exif=exif)

    with Image.open(img_path) as loaded:
        hw = detector.extract_hardware_exif(img=loaded, path=img_path)
    assert hw is not None
    # Verify no serial numbers or names appear in any key or summary string
    for val in hw.values():
        val_str = str(val)
        assert "987654321" not in val_str
        assert "LENS-123456" not in val_str
        assert "John Doe" not in val_str
        assert "Private User" not in val_str


def test_cli_redact_metadata_flag(tmp_path: Path):
    """Test --redact-metadata flag strips capture timestamps."""
    img_path = tmp_path / "timestamp_shot.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 25, (200, 300, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Sony"
    exif[ExifTags.Base.Model] = "ILCE-7M4"
    exif[ExifTags.Base.DateTime] = "2024:06:15 14:30:00"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.DateTimeOriginal] = "2024:06:15 14:30:00"
    img.save(img_path, "JPEG", exif=exif)

    # 1. Normal run has capture timestamp
    res_normal = runner.invoke(app, ["camera", str(img_path)])
    assert res_normal.exit_code == 0
    assert "2024:06:15 14:30:00" in res_normal.output

    # 2. Redacted run has no capture timestamp
    res_redacted = runner.invoke(app, ["camera", str(img_path), "--redact-metadata"])
    assert res_redacted.exit_code == 0
    assert "2024:06:15 14:30:00" not in res_redacted.output
    assert "Capture Timestamp" not in res_redacted.output


def test_corroborate_exif_editor_downgrade(tmp_path: Path):
    """Test editing software in EXIF downgrades confidence to low and documents in why_doubted."""
    img_path = tmp_path / "photoshop_edited.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 20, (200, 300, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Nikon"
    exif[ExifTags.Base.Model] = "Z 8"
    exif[ExifTags.Base.Software] = "Adobe Photoshop 2024"
    img.save(img_path, "JPEG", exif=exif)

    detector = CameraDetector()
    with Image.open(img_path) as loaded:
        res = detector.detect(arr=arr, aspect_ratio="3:2", optical_craft={}, img=loaded, path=img_path)
    assert res["confidence"] == "low"
    assert any("editor" in d for d in res["why_doubted"])


def test_corroborate_exif_ai_tool_downgrade(tmp_path: Path):
    """Test AI generative software tag in EXIF triggers doubt and confidence low."""
    img_path = tmp_path / "midjourney_exif.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 20, (200, 300, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "EOS R5"
    exif[ExifTags.Base.Software] = "Midjourney v6"
    img.save(img_path, "JPEG", exif=exif)

    detector = CameraDetector()
    with Image.open(img_path) as loaded:
        res = detector.detect(arr=arr, aspect_ratio="3:2", optical_craft={}, img=loaded, path=img_path)
    assert res["confidence"] == "low"
    assert any("AI generative tool" in d for d in res["why_doubted"])


def test_corroborate_exif_focal_crop_mismatch(tmp_path: Path):
    """Test conflicting focal length to 35mm crop factor ratio lowers confidence."""
    img_path = tmp_path / "focal_mismatch.jpg"
    rng = np.random.default_rng(42)
    arr = rng.normal(128, 20, (200, 300, 3)).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Sony"
    exif[ExifTags.Base.Model] = "ILCE-7M4"  # Full frame, crop factor 1.0

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.FocalLength] = (24, 1)
    exif_ifd[ExifTags.Base.FocalLengthIn35mmFilm] = 72  # 3.0x ratio vs expected 1.0
    img.save(img_path, "JPEG", exif=exif)

    detector = CameraDetector()
    with Image.open(img_path) as loaded:
        res = detector.detect(arr=arr, aspect_ratio="3:2", optical_craft={}, img=loaded, path=img_path)
    assert res["confidence"] == "low"
    assert any("conflicts with sensor crop factor" in d for d in res["why_doubted"])


def test_corroborate_exif_hypersmooth_pixels(tmp_path: Path):
    """Test zero-noise pixel profile contradicts camera sensor expectation."""
    img_path = tmp_path / "flat_sensor.jpg"
    arr = np.full((200, 300, 3), 128, dtype=np.uint8)
    img = Image.fromarray(arr)

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "EOS 5D Mark IV"
    img.save(img_path, "JPEG", exif=exif)

    detector = CameraDetector()
    with Image.open(img_path) as loaded:
        res = detector.detect(arr=arr, aspect_ratio="3:2", optical_craft={}, img=loaded, path=img_path)
    assert res["confidence"] == "low"
    assert any("Pixel noise profile is near-zero" in d for d in res["why_doubted"])


def test_cli_camera_format_flag_and_missing_file(tmp_path: Path):
    """Test camera CLI subcommand supports --format json and exits with 1 on missing file."""
    # 1. Missing file -> exit code 1
    res_missing = runner.invoke(app, ["camera", str(tmp_path / "nonexistent.png")])
    assert res_missing.exit_code == 1
    assert "File not found" in res_missing.output

    # 2. --format json flag
    img_path = tmp_path / "test_format.jpg"
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    Image.fromarray(arr).save(img_path)

    res_json = runner.invoke(app, ["camera", str(img_path), "--format", "json"])
    assert res_json.exit_code == 0
    import json
    data = json.loads(res_json.output)
    assert "display_name" in data


def test_camera_malformed_exif_zero_denominator_and_negative(tmp_path: Path):
    """Test malformed EXIF with zero denominators, negative values, and raw bytes doesn't crash."""
    detector = CameraDetector()

    from unittest.mock import MagicMock
    mock_img = MagicMock()
    mock_exif = {
        ExifTags.Base.Make: b"Canon\x00\x01",
        ExifTags.Base.Model: b"EOS R5\x00",
    }
    mock_ifd = {
        ExifTags.Base.FNumber: (1, 0),  # Zero denominator
        ExifTags.Base.ExposureTime: (-1, 500),  # Negative value
        ExifTags.Base.FocalLength: (0, 0),  # Zero denominator
        ExifTags.Base.LensModel: b"RF24-70mm\x00",
    }
    mock_exif_obj = MagicMock()
    mock_exif_obj.items.return_value = mock_exif.items()
    mock_exif_obj.get_ifd.return_value = mock_ifd
    mock_img.getexif.return_value = mock_exif_obj

    hw = detector.extract_hardware_exif(img=mock_img, path=None)
    assert hw is not None
    assert hw["make"] == "Canon"
    assert hw["model"] == "EOS R5"
    assert hw["aperture"] is None
    assert hw["shutter_speed"] is None
    assert hw["focal_length"] is None


def test_camera_detection_png_with_exif(tmp_path: Path):
    """Test extracting camera hardware from a PNG file containing EXIF."""
    img_path = tmp_path / "exif_photo.png"
    img = Image.new("RGB", (200, 300), color=(140, 120, 100))

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Nikon"
    exif[ExifTags.Base.Model] = "Z 8"
    img.save(img_path, "PNG", exif=exif)

    detector = CameraDetector()
    with Image.open(img_path) as loaded:
        hw = detector.extract_hardware_exif(img=loaded, path=img_path)
    assert hw is not None
    assert hw["make"] == "Nikon"
    assert hw["model"] == "Z 8"
    assert hw["sensor_format"] == "full_frame"


def test_camera_cli_pure_pixel_ai_image():
    """Test camera CLI command on AI image without PNG chunks does not crash."""
    ai_img = Path("eval/benchmark_data/images/ai_heldout_ss.png")
    if not ai_img.exists():
        return

    res = runner.invoke(app, ["camera", str(ai_img), "--format", "json"])
    assert res.exit_code == 0
    import json
    data = json.loads(res.output)
    assert "display_name" in data


def test_full_rational_exif_jpeg_pipeline(tmp_path: Path):
    """Test JPEG with full IFDRational EXIF succeeds across pipeline and CLI without serialization errors."""
    import json
    from PIL.TiffImagePlugin import IFDRational

    img_path = tmp_path / "photo_rational.jpg"
    img = Image.new("RGB", (300, 300), color=(110, 130, 150))

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "Canon EOS R6"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.ExposureTime] = IFDRational(1, 250)
    exif_ifd[ExifTags.Base.FNumber] = IFDRational(28, 10)
    exif_ifd[ExifTags.Base.FocalLength] = IFDRational(50, 1)
    exif_ifd[ExifTags.Base.ISOSpeedRatings] = 400
    exif_ifd[ExifTags.Base.LensModel] = "RF24-70mm F2.8 L IS USM"

    img.save(img_path, "JPEG", exif=exif)

    # 1. run_analysis_pipeline
    out_dir = tmp_path / "pipeline_out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir, no_cache=True)
    assert report is not None

    report_json_path = out_dir / "report.json"
    assert report_json_path.exists()
    with open(report_json_path, "r", encoding="utf-8") as f:
        json_content = f.read()
        json_data = json.loads(json_content)

    assert json_data["image"]["format"].lower() in ("jpeg", "jpg")
    assert "Canon EOS R6" in json_content
    assert "f/2.8" in json_content
    assert "1/250s" in json_content

    report_html_path = out_dir / "report.html"
    assert report_html_path.exists()
    html_content = report_html_path.read_text(encoding="utf-8")
    assert "Canon EOS R6" in html_content
    assert "f/2.8" in html_content
    assert "1/250s" in html_content

    # 2. rea-image analyze CLI
    analyze_out = tmp_path / "analyze_cli_out"
    res_analyze = runner.invoke(app, ["analyze", str(img_path), "--out", str(analyze_out)])
    assert res_analyze.exit_code == 0

    # 3. rea-image camera CLI
    res_camera = runner.invoke(app, ["camera", str(img_path)])
    assert res_camera.exit_code == 0
    assert "EOS R6" in res_camera.output
    assert "f/2.8" in res_camera.output
    assert "1/250s" in res_camera.output

    # 4. rea-image camera --json CLI
    res_camera_json = runner.invoke(app, ["camera", str(img_path), "--json"])
    assert res_camera_json.exit_code == 0
    cam_json = json.loads(res_camera_json.output)
    assert "EOS R6" in cam_json["display_name"]
    assert cam_json["aperture"] == "f/2.8"
    assert cam_json["shutter_speed"] == "1/250s"


def test_apex_only_tags_pipeline(tmp_path: Path):
    """Test JPEG with APEX tags only (ApertureValue, ShutterSpeedValue) succeeds and formats correctly."""
    from PIL.TiffImagePlugin import IFDRational

    img_path = tmp_path / "apex_photo.jpg"
    img = Image.new("RGB", (200, 200), color=(100, 120, 140))

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "EOS R6"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    # Av = 3.0 -> f = 2^(1.5) = 2.828 -> f/2.8
    exif_ifd[ExifTags.Base.ApertureValue] = IFDRational(30, 10)
    # Tv = 7.965784 -> t = 2^(-7.965784) = 0.004 -> 1/250s
    exif_ifd[ExifTags.Base.ShutterSpeedValue] = IFDRational(7965784, 1000000)
    exif_ifd[ExifTags.Base.FocalLength] = IFDRational(50, 1)

    img.save(img_path, "JPEG", exif=exif)

    out_dir = tmp_path / "apex_out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir, no_cache=True)
    assert report is not None

    with open(out_dir / "report.json", "r", encoding="utf-8") as f:
        json_content = f.read()
    assert "f/2.8" in json_content
    assert "1/250s" in json_content


def test_camera_detection_png_with_rational_exif(tmp_path: Path):
    """Test PNG containing rational EXIF succeeds across pipeline and camera CLI."""
    import json
    from PIL.TiffImagePlugin import IFDRational

    img_path = tmp_path / "photo_rational.png"
    img = Image.new("RGB", (200, 200), color=(80, 100, 120))

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Sony"
    exif[ExifTags.Base.Model] = "ILCE-7M4"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.ExposureTime] = IFDRational(1, 250)
    exif_ifd[ExifTags.Base.FNumber] = IFDRational(28, 10)
    exif_ifd[ExifTags.Base.FocalLength] = IFDRational(85, 1)

    img.save(img_path, "PNG", exif=exif)

    out_dir = tmp_path / "png_rational_out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir, no_cache=True)
    assert report is not None

    with open(out_dir / "report.json", "r", encoding="utf-8") as f:
        json_content = f.read()
    assert "Sony" in json_content
    assert "ILCE-7M4" in json_content

    res_json = runner.invoke(app, ["camera", str(img_path), "--json"])
    assert res_json.exit_code == 0
    cam_json = json.loads(res_json.output)
    assert cam_json["make"] == "Sony"


def test_malformed_exif_zero_denominator_and_bytes(tmp_path: Path):
    """Test that malformed EXIF (zero denominators, byte blobs) does not crash pipeline or camera CLI."""
    from PIL.TiffImagePlugin import IFDRational

    img_path = tmp_path / "malformed_exif.jpg"
    img = Image.new("RGB", (200, 200), color=(90, 110, 130))

    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Nikon"
    exif[ExifTags.Base.Model] = "Z 6"

    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    exif_ifd[ExifTags.Base.FNumber] = IFDRational(28, 0)
    exif_ifd[ExifTags.Base.ExposureTime] = IFDRational(1, 0)
    exif_ifd[ExifTags.Base.FocalLength] = b"\x00\x01\x02\xff"

    img.save(img_path, "JPEG", exif=exif)

    out_dir = tmp_path / "malformed_out"
    report = run_analysis_pipeline(img_path, out_dir=out_dir, no_cache=True)
    assert report is not None
    assert (out_dir / "report.json").exists()

    res = runner.invoke(app, ["camera", str(img_path)])
    assert res.exit_code == 0

    res_json = runner.invoke(app, ["camera", str(img_path), "--json"])
    assert res_json.exit_code == 0


def test_evidence_item_safe_by_default():
    """Test EvidenceItem pydantic validator and serializer convert unknown objects safely."""
    from PIL.TiffImagePlugin import IFDRational
    from rea_image.schemas import EvidenceItem

    item = EvidenceItem(
        name="test_signal",
        value={
            "rat": IFDRational(1, 250),
            "bad_rat": IFDRational(5, 0),
            "bytes": b"clean_bytes\x00",
            "np_scalar": np.float64(2.8),
            "np_int": np.int32(100),
            "tuple_rat": (IFDRational(50, 1), 10),
        },
        direction="real photograph",
        strength=0.9,
        explanation="Testing safe serialization",
    )

    dumped = item.model_dump(mode="json")
    assert dumped["value"]["rat"] == 0.004
    assert dumped["value"]["bad_rat"] is None
    assert dumped["value"]["bytes"] == "clean_bytes"
    assert dumped["value"]["np_scalar"] == 2.8
    assert dumped["value"]["np_int"] == 100
    assert dumped["value"]["tuple_rat"] == [50.0, 10]

    # Test direct mutation
    item.value = {"mutated_rat": IFDRational(1, 1000)}
    dumped2 = item.model_dump(mode="json")
    assert dumped2["value"]["mutated_rat"] == 0.001


def test_camera_display_name_no_repeated_make(tmp_path: Path):
    """Test that models already starting with make don't duplicate make in display_name or metadata claims."""
    # 1. Direct classification
    canon_cam = classify_camera_device("Canon", "Canon EOS R6")
    assert canon_cam["display_name"] == "Canon EOS R6"
    assert "Canon Canon" not in canon_cam["display_name"]

    nikon_cam = classify_camera_device("Nikon", "NIKON D850")
    assert nikon_cam["display_name"] == "NIKON D850"
    assert "Nikon NIKON" not in nikon_cam["display_name"]

    # 2. CameraDetector metadata-claim path (non-photograph)
    detector = CameraDetector()
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "Canon EOS R6"

    synthetic_arr = np.full((200, 200, 3), 128, dtype=np.uint8)
    detected = detector.detect(
        arr=synthetic_arr,
        aspect_ratio="1:1",
        optical_craft={},
        img=img,
        path=None,
        is_photograph=False,
        dominant_method="vector or graphic design",
    )
    assert detected["claimed_by_metadata"] is True
    assert detected["display_name"] == "Canon EOS R6 (claimed by metadata)"
    assert "Canon Canon" not in detected["display_name"]
    assert "Canon Canon" not in detected["summary"]

    # 3. Full pipeline run on an AI-marked image with Canon EOS R6
    from PIL import PngImagePlugin

    png_path = tmp_path / "ai_canon_test.png"
    meta = PngImagePlugin.PngInfo()
    meta.add_text("parameters", "Cyberpunk street, Unreal Engine 5 render, highly detailed")
    img.save(png_path, "PNG", pnginfo=meta, exif=exif)

    out_dir = tmp_path / "ai_canon_out"
    report = run_analysis_pipeline(png_path, out_dir=out_dir, no_cache=True)
    cam = report.global_analysis.camera

    assert cam["display_name"] == "Canon EOS R6 (claimed by metadata)"
    assert "Canon Canon" not in cam["display_name"]
    assert "Canon Canon" not in cam["summary"]

    # Verify needs_review doesn't repeat make
    claim_review = next(
        (r for r in report.needs_review if "metadata claims" in r.reason),
        None,
    )
    assert claim_review is not None
    assert "Canon EOS R6" in claim_review.reason
    assert "Canon Canon" not in claim_review.reason

    # Verify report.html doesn't contain repeated make
    html_text = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "Canon Canon" not in html_text
