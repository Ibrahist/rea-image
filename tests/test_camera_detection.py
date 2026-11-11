"""Tests for camera hardware detection and optical forensics."""

from pathlib import Path
import numpy as np
from PIL import Image, ExifTags
from typer.testing import CliRunner
from rea_image.cli import app
from rea_image.evidence.camera_detector import CameraDetector, classify_camera_device
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
    img = Image.new("RGB", (300, 200), color=(180, 140, 100))

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
    assert hw_cam["source"] == "hardware_exif"
    assert hw_cam["confidence"] == "high"
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


def test_inferred_optical_camera_detection():
    """Test camera type inference when EXIF is stripped."""
    detector = CameraDetector()

    # Case 1: 4:3 aspect ratio with deep DoF
    arr_4_3 = np.zeros((300, 400, 3), dtype=np.uint8)
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

    # Case 2: 3:2 aspect ratio with shallow DoF
    arr_3_2 = np.zeros((200, 300, 3), dtype=np.uint8)
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

    # Case 3: Non-photographic image
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
