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
    img = Image.new("RGB", (400, 300), color=(150, 180, 200))

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
    img = Image.new("RGB", (300, 200), color=(140, 160, 120))

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
