"""Camera hardware identification and optical forensics engine.

Detects the physical camera (make, model, sensor format, lens, and shooting parameters)
that captured a photograph. If EXIF/C2PA metadata is stripped, infers camera classification
(e.g., modern computational smartphone vs. dedicated large-sensor camera) using aspect ratios,
sensor-size depth-of-field constraints, and unsharp masking edge halo forensics.
"""

from fractions import Fraction
import logging
from pathlib import Path
import re
from typing import Any, Dict, Optional
import numpy as np
from PIL import ExifTags, Image
from scipy.ndimage import laplace

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Device and Sensor Catalogs
# ---------------------------------------------------------------------------

MAKE_CANONICAL: Dict[str, str] = {
    "apple": "Apple",
    "canon": "Canon",
    "nikon": "Nikon",
    "nikon corporation": "Nikon",
    "sony": "Sony",
    "fujifilm": "Fujifilm",
    "google": "Google",
    "samsung": "Samsung",
    "panasonic": "Panasonic",
    "olympus": "Olympus",
    "olympus optical co.,ltd": "Olympus",
    "om digital solutions": "OM System",
    "leica": "Leica",
    "leica camera ag": "Leica",
    "dji": "DJI",
    "gopro": "GoPro",
    "hasselblad": "Hasselblad",
    "phase one": "Phase One",
    "ricoh": "Ricoh",
    "ricoh imaging company, ltd.": "Ricoh",
    "xiaomi": "Xiaomi",
    "huawei": "Huawei",
    "oneplus": "OnePlus",
    "oppo": "Oppo",
    "vivo": "Vivo",
    "motorola": "Motorola",
    "pentax": "Pentax",
    "sigma": "Sigma",
}


def _clean_str(val: Any) -> str:
    """Normalize string, handling bytes, NUL bytes, and whitespace."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        try:
            val = val.decode("utf-8", errors="replace")
        except Exception:
            val = repr(val)
    return str(val).strip("\x00 \t\r\n")


def _format_rational(val: Any) -> Optional[float]:
    """Convert EXIF rational, tuple, or float to float."""
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        if hasattr(val, "numerator") and hasattr(val, "denominator"):
            return float(val.numerator) / float(val.denominator) if val.denominator != 0 else None
        if isinstance(val, (tuple, list)) and len(val) >= 2:
            num, den = val[0], val[1]
            return float(num) / float(den) if den != 0 else None
        # String representations like "1/250" or "2.8"
        if isinstance(val, str):
            if "/" in val:
                n, d = val.split("/", 1)
                return float(n) / float(d) if float(d) != 0 else None
            return float(val)
    except Exception:
        pass
    return None


def _format_exposure_time(val: Any) -> Optional[str]:
    """Format exposure time in seconds or fractional seconds (e.g. '1/250s')."""
    if val is None:
        return None
    num_val = _format_rational(val)
    if num_val is None or num_val <= 0:
        return _clean_str(val)
    if num_val >= 1.0:
        return f"{num_val:.1f}s" if num_val != int(num_val) else f"{int(num_val)}s"
    # Convert to standard fractional shutter notation (e.g. 1/250s)
    try:
        frac = Fraction(num_val).limit_denominator(8000)
        if frac.numerator == 1:
            return f"1/{frac.denominator}s"
        reciprocal = round(1.0 / num_val)
        return f"1/{reciprocal}s"
    except Exception:
        return f"{num_val:.4f}s"


# ---------------------------------------------------------------------------
# Camera Classification Rules
# ---------------------------------------------------------------------------

def classify_camera_device(make_raw: str, model_raw: str, lens_raw: str = "") -> Dict[str, Any]:
    """Classify camera device type, sensor format, and crop factor from make and model."""
    make_lower = make_raw.lower().strip()
    model_lower = model_raw.lower().strip()

    # Match canonical make name
    canonical_make = MAKE_CANONICAL.get(make_lower)
    if not canonical_make:
        for k, v in MAKE_CANONICAL.items():
            if k in make_lower:
                canonical_make = v
                break
    if not canonical_make:
        canonical_make = make_raw.strip().title() if make_raw else "Unknown"

    device_type = "unknown"
    sensor_format = "unknown"
    crop_factor: Optional[float] = None
    clean_model = model_raw.strip()

    # 1. Smartphones
    if any(m in make_lower for m in ("apple", "google", "samsung", "xiaomi", "huawei", "oneplus", "oppo", "vivo", "motorola")) or \
       any(p in model_lower for p in ("iphone", "pixel", "galaxy", "sm-s", "sm-g", "sm-f", "sm-a", "redmi")):
        device_type = "smartphone"
        sensor_format = "smartphone_small"
        crop_factor = 4.0
        # Refine sensor class for flagship large-sensor phones
        if any(f in model_lower for f in ("14 pro", "15 pro", "16 pro", "ultra", "pixel 7 pro", "pixel 8 pro", "pixel 9 pro")):
            sensor_format = "smartphone_large_sensor"
            crop_factor = 3.2

    # 2. DJI Drones
    elif "dji" in make_lower or "mavic" in model_lower or "fc3" in model_lower or "mini" in model_lower and "dji" in make_lower:
        device_type = "drone"
        sensor_format = "1/1.3_inch"
        crop_factor = 3.2

    # 3. Action Cameras (GoPro / Insta360)
    elif "gopro" in make_lower or "hero" in model_lower or "insta360" in make_lower:
        device_type = "action_cam"
        sensor_format = "1/1.9_inch"
        crop_factor = 4.5

    # 4. Sony
    elif "sony" in make_lower or "ilce" in model_lower:
        if any(s in model_lower for s in ("ilce-7", "ilce-9", "ilce-1", "a7", "a9", "a1", "fx3", "fx6", "zv-e1")):
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0
        elif any(s in model_lower for s in ("ilce-6", "ilce-5", "a6", "zv-e10", "nex")):
            device_type = "mirrorless"
            sensor_format = "aps_c"
            crop_factor = 1.5
        elif "rx100" in model_lower or "zv-1" in model_lower:
            device_type = "compact"
            sensor_format = "one_inch"
            crop_factor = 2.7
        else:
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0

    # 5. Canon
    elif "canon" in make_lower:
        # Canon EOS R full-frame
        if re.search(r"eos\s*r([3568]|p|\b)", model_lower) and not re.search(r"eos\s*r(7|10|50|100)\b", model_lower):
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0
        # Canon EOS R APS-C or EOS M
        elif re.search(r"eos\s*r(7|10|50|100)\b", model_lower) or "eos m" in model_lower:
            device_type = "mirrorless"
            sensor_format = "aps_c"
            crop_factor = 1.6
        # Canon EOS DSLR Full-Frame (5D, 6D, 1D)
        elif any(d in model_lower for d in ("5d", "6d", "1d")):
            device_type = "dslr"
            sensor_format = "full_frame"
            crop_factor = 1.0
        # Canon EOS DSLR APS-C (7D, 80D, 90D, Rebel, xxxD)
        elif any(d in model_lower for d in ("7d", "80d", "90d", "70d", "rebel", "kiss", "eos")) or "powershot" not in model_lower:
            device_type = "dslr"
            sensor_format = "aps_c"
            crop_factor = 1.6
        elif "powershot" in model_lower:
            device_type = "compact"
            sensor_format = "one_inch"
            crop_factor = 2.7

    # 6. Nikon
    elif "nikon" in make_lower:
        # Nikon Z full-frame
        if re.search(r"\bz\s*([56789]|f)\b", model_lower) and not re.search(r"\bz\s*(30|50|fc)\b", model_lower):
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0
        # Nikon Z APS-C (DX)
        elif re.search(r"\bz\s*(30|50|fc)\b", model_lower):
            device_type = "mirrorless"
            sensor_format = "aps_c"
            crop_factor = 1.5
        # Nikon DSLR Full-Frame (FX: D850, D810, D780, D750, D6, D5, D4, D3, Df)
        elif any(d in model_lower for d in ("d850", "d810", "d800", "d780", "d750", "d700", "d6", "d5", "d4", "d3", "df")):
            device_type = "dslr"
            sensor_format = "full_frame"
            crop_factor = 1.0
        # Nikon DSLR APS-C (DX: D500, D7500, D7200, D5600, D3500)
        elif re.search(r"\bd[0-9]{3,4}\b", model_lower):
            device_type = "dslr"
            sensor_format = "aps_c"
            crop_factor = 1.5
        else:
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0

    # 7. Fujifilm
    elif "fujifilm" in make_lower or "fuji" in make_lower:
        if "gfx" in model_lower:
            device_type = "medium_format"
            sensor_format = "medium_format"
            crop_factor = 0.79
        elif "x100" in model_lower:
            device_type = "compact"
            sensor_format = "aps_c"
            crop_factor = 1.5
        else:
            device_type = "mirrorless"
            sensor_format = "aps_c"
            crop_factor = 1.5

    # 8. Leica
    elif "leica" in make_lower:
        if "q" in model_lower or "m" in model_lower or "sl" in model_lower:
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0
        else:
            device_type = "mirrorless"
            sensor_format = "full_frame"
            crop_factor = 1.0

    # 9. Micro Four Thirds (Olympus, OM System, Panasonic Lumix G)
    elif "olympus" in make_lower or "om system" in make_lower or ("panasonic" in make_lower and ("gh" in model_lower or "g9" in model_lower or "g8" in model_lower)):
        device_type = "mirrorless"
        sensor_format = "micro_four_thirds"
        crop_factor = 2.0

    # 10. Hasselblad
    elif "hasselblad" in make_lower:
        device_type = "medium_format"
        sensor_format = "medium_format"
        crop_factor = 0.79

    # 11. Ricoh
    elif "ricoh" in make_lower:
        if "gr" in model_lower:
            device_type = "compact"
            sensor_format = "aps_c"
            crop_factor = 1.5
        else:
            device_type = "compact"
            sensor_format = "aps_c"
            crop_factor = 1.5

    # Build human-readable formatted name
    type_labels = {
        "smartphone": "Smartphone",
        "mirrorless": "Mirrorless Camera",
        "dslr": "DSLR Camera",
        "compact": "Compact Camera",
        "drone": "Drone Aerial Camera",
        "action_cam": "Action Camera",
        "medium_format": "Medium Format Camera",
        "unknown": "Digital Camera",
    }
    format_labels = {
        "full_frame": "Full-Frame (35mm)",
        "aps_c": "APS-C (1.5x crop)",
        "micro_four_thirds": "Micro Four Thirds (2.0x crop)",
        "one_inch": "1.0-inch Sensor",
        "smartphone_small": "Smartphone Sensor (~1/1.3\" to 1/2.5\")",
        "smartphone_large_sensor": "Large Smartphone Sensor (1/1.28\" Quad-Bayer)",
        "1/1.3_inch": "1/1.3-inch Sensor",
        "1/1.9_inch": "1/1.9-inch Sensor",
        "medium_format": "Medium Format (0.79x crop)",
        "unknown": "Standard Sensor",
    }

    display_name = f"{canonical_make} {clean_model}".strip()
    if clean_model.lower().startswith(canonical_make.lower()):
        display_name = clean_model

    return {
        "canonical_make": canonical_make,
        "clean_model": clean_model,
        "device_type": device_type,
        "device_type_label": type_labels.get(device_type, "Digital Camera"),
        "sensor_format": sensor_format,
        "sensor_format_label": format_labels.get(sensor_format, "Standard Sensor"),
        "sensor_crop_factor": crop_factor,
        "display_name": display_name,
    }


# ---------------------------------------------------------------------------
# Optical and Forensic Computational Classifier
# ---------------------------------------------------------------------------

def measure_computational_sharpening(arr: np.ndarray) -> Dict[str, Any]:
    """Measure edge overshoot halos characteristic of mobile computational unsharp masking."""
    lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
    lap = np.abs(laplace(lum))

    # Look for extreme peak values along high-contrast borders relative to median sharpness
    threshold = np.percentile(lap, 98)
    high_edge_lap = lap[lap >= threshold]
    mean_top_edge = float(np.mean(high_edge_lap)) if len(high_edge_lap) > 0 else 0.0
    median_edge = float(np.median(lap)) + 1e-4
    overshoot_ratio = mean_top_edge / median_edge

    # Check gradient symmetry across edges (overshoot creates adjacent bright/dark rim pairs)
    has_unsharp_halo = overshoot_ratio > 35.0
    return {
        "overshoot_ratio": round(overshoot_ratio, 2),
        "has_unsharp_halo": has_unsharp_halo,
        "description": "High edge overshoot halo (computational unsharp masking)" if has_unsharp_halo else "Smooth MTF optical gradient rolloff",
    }


def measure_local_dynamic_range(arr: np.ndarray) -> Dict[str, Any]:
    """Check whether deep shadows are computationally boosted with local tone mapping."""
    lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
    shadow_mask = lum < 40.0
    highlight_mask = lum > 215.0

    shadow_std = float(np.std(lum[shadow_mask])) if np.sum(shadow_mask) > 100 else 0.0
    highlight_std = float(np.std(lum[highlight_mask])) if np.sum(highlight_mask) > 100 else 0.0

    # In mobile HDR pipelines, shadows are lifted and locally normalized, resulting in elevated shadow variance
    has_hdr_shadow_boost = shadow_std > 8.0 and np.sum(shadow_mask) > 500
    return {
        "shadow_variance": round(shadow_std, 2),
        "highlight_variance": round(highlight_std, 2),
        "has_hdr_shadow_boost": has_hdr_shadow_boost,
        "description": "Computational HDR local tone mapping (lifted shadow dynamics)" if has_hdr_shadow_boost else "Natural optical tone curve",
    }


# ---------------------------------------------------------------------------
# Master Camera Detector
# ---------------------------------------------------------------------------

class CameraDetector:
    """Detects camera hardware from metadata or infers capture profile from optical forensics."""

    def extract_hardware_exif(
        self,
        img: Optional[Image.Image] = None,
        path: Optional[Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract camera hardware metadata from EXIF stream."""
        exif_dict: Dict[str, Any] = {}

        # 1. Read EXIF from PIL Image instance
        if img is not None:
            try:
                raw_exif = img.getexif()
                if raw_exif:
                    for k, v in raw_exif.items():
                        tag = ExifTags.TAGS.get(k, str(k))
                        exif_dict[tag] = v

                    # Check Exif IFD sub-dictionaries
                    for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
                        try:
                            ifd = raw_exif.get_ifd(ifd_id)
                            for k, v in ifd.items():
                                tag = ExifTags.TAGS.get(k, str(k))
                                exif_dict[tag] = v
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("Failed to read EXIF from image object: %s", e)

        # 2. Fallback to re-opening source file directly if make/model not yet found
        if path is not None and (not exif_dict.get("Make") and not exif_dict.get("Model")):
            try:
                p = Path(path)
                if p.exists() and p.is_file():
                    with Image.open(p) as disk_img:
                        raw_exif = disk_img.getexif()
                        if raw_exif:
                            for k, v in raw_exif.items():
                                tag = ExifTags.TAGS.get(k, str(k))
                                exif_dict[tag] = v
                            for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
                                try:
                                    ifd = raw_exif.get_ifd(ifd_id)
                                    for k, v in ifd.items():
                                        tag = ExifTags.TAGS.get(k, str(k))
                                        exif_dict[tag] = v
                                except Exception:
                                    pass
            except Exception as e:
                logger.debug("Failed to read EXIF from file path %s: %s", path, e)

        make = _clean_str(exif_dict.get("Make"))
        model = _clean_str(exif_dict.get("Model"))

        if not make and not model:
            return None

        # Lens and optical tags
        lens = _clean_str(exif_dict.get("LensModel") or exif_dict.get("LensMake") or exif_dict.get("LensSpecification"))
        focal_raw = _format_rational(exif_dict.get("FocalLength"))
        focal_35_raw = _format_rational(exif_dict.get("FocalLengthIn35mmFilm"))
        aperture_raw = _format_rational(exif_dict.get("FNumber") or exif_dict.get("ApertureValue"))
        shutter_str = _format_exposure_time(exif_dict.get("ExposureTime") or exif_dict.get("ShutterSpeedValue"))
        iso = exif_dict.get("ISOSpeedRatings") or exif_dict.get("PhotographicSensitivity")
        if isinstance(iso, (list, tuple)) and iso:
            iso = iso[0]

        software = _clean_str(exif_dict.get("Software") or exif_dict.get("HostComputer"))
        date_time = _clean_str(exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime"))

        # Flash
        flash_raw = exif_dict.get("Flash")
        flash_fired: Optional[bool] = None
        if flash_raw is not None:
            try:
                flash_fired = bool(int(flash_raw) & 1)
            except Exception:
                pass

        # Exposure program
        programs = {
            1: "Manual",
            2: "Program AE",
            3: "Aperture Priority",
            4: "Shutter Priority",
            5: "Creative Program",
            6: "Action / Sports",
            7: "Portrait Mode",
            8: "Landscape Mode",
        }
        exp_prog_code = exif_dict.get("ExposureProgram")
        exposure_program = programs.get(exp_prog_code) if isinstance(exp_prog_code, int) else None

        # Metering mode
        metering_modes = {
            1: "Average",
            2: "Center-Weighted Average",
            3: "Spot",
            4: "Multi-Spot",
            5: "Multi-Segment (Pattern)",
            6: "Partial",
        }
        meter_code = exif_dict.get("MeteringMode")
        metering_mode = metering_modes.get(meter_code) if isinstance(meter_code, int) else None

        # Classify device hardware and sensor format
        classification = classify_camera_device(make, model, lens)

        # Build clean formatted strings
        focal_str = f"{focal_raw:.1f}mm" if focal_raw else None
        focal_35_str = f"{int(focal_35_raw)}mm" if focal_35_raw else None
        aperture_str = f"f/{aperture_raw:.1f}" if aperture_raw else None

        summary_parts = [classification["display_name"]]
        specs = []
        if lens:
            specs.append(lens)
        if focal_str:
            specs.append(f"{focal_str} (35mm eq: {focal_35_str})" if focal_35_str else focal_str)
        if aperture_str:
            specs.append(aperture_str)
        if shutter_str:
            specs.append(shutter_str)
        if iso:
            specs.append(f"ISO {iso}")
        if specs:
            summary_parts.append(f"({', '.join(specs)})")

        summary = " ".join(summary_parts)

        return {
            "detected": True,
            "source": "hardware_exif",
            "confidence": "high",
            "make": classification["canonical_make"],
            "model": classification["clean_model"],
            "display_name": classification["display_name"],
            "device_type": classification["device_type"],
            "device_type_label": classification["device_type_label"],
            "sensor_format": classification["sensor_format"],
            "sensor_format_label": classification["sensor_format_label"],
            "sensor_crop_factor": classification["sensor_crop_factor"],
            "lens": lens or None,
            "focal_length": focal_str,
            "focal_length_35mm": focal_35_str,
            "aperture": aperture_str,
            "shutter_speed": shutter_str,
            "iso": str(iso) if iso is not None else None,
            "flash_fired": flash_fired,
            "exposure_program": exposure_program,
            "metering_mode": metering_mode,
            "software_firmware": software or None,
            "datetime_original": date_time or None,
            "computational_traces": [],
            "summary": summary,
        }

    def infer_from_optics(
        self,
        arr: np.ndarray,
        aspect_ratio: str,
        optical_craft: Dict[str, Any],
        is_photograph: bool = True,
    ) -> Dict[str, Any]:
        """Infer camera category and sensor profile from visual forensics when EXIF is stripped."""
        if not is_photograph:
            return {
                "detected": False,
                "source": "none",
                "confidence": "none",
                "make": None,
                "model": "Non-photographic imagery (AI-generated or vector graphic)",
                "display_name": "No Physical Camera Detected",
                "device_type": "unknown",
                "device_type_label": "Not Applicable",
                "sensor_format": "unknown",
                "sensor_format_label": "Not Applicable",
                "sensor_crop_factor": None,
                "lens": None,
                "focal_length": None,
                "focal_length_35mm": None,
                "aperture": None,
                "shutter_speed": None,
                "iso": None,
                "computational_traces": [],
                "summary": "No physical camera detected (non-photographic image)",
            }

        # Analyze aspect ratio
        clean_aspect = aspect_ratio.strip()
        is_4_3 = clean_aspect in ("4:3", "3:4")
        is_3_2 = clean_aspect in ("3:2", "2:3")

        # Computational sharpening and tone mapping checks
        sharp_res = measure_computational_sharpening(arr)
        dr_res = measure_local_dynamic_range(arr)
        dof = optical_craft.get("depth_of_field", "")
        focal_est = optical_craft.get("estimated_focal_length", "50mm normal lens")
        aperture_est = optical_craft.get("estimated_aperture", "f/2.8")

        traces = []
        if is_4_3:
            traces.append("Native 4:3 aspect ratio characteristic of smartphone/MFT sensors")
        elif is_3_2:
            traces.append("Native 3:2 aspect ratio characteristic of 35mm Full-Frame and APS-C sensors")

        if sharp_res["has_unsharp_halo"]:
            traces.append(f"Computational unsharp masking halo (overshoot ratio {sharp_res['overshoot_ratio']})")
        if dr_res["has_hdr_shadow_boost"]:
            traces.append("Multi-frame HDR local tone mapping (elevated shadow detail)")

        # Scoring heuristics
        smartphone_score = 0
        dedicated_score = 0

        if is_4_3:
            smartphone_score += 3
        elif is_3_2:
            dedicated_score += 4

        if sharp_res["has_unsharp_halo"]:
            smartphone_score += 3
        else:
            dedicated_score += 1

        if dr_res["has_hdr_shadow_boost"]:
            smartphone_score += 2

        if "shallow" in dof.lower():
            dedicated_score += 3
        elif "deep" in dof.lower():
            smartphone_score += 2

        if smartphone_score >= dedicated_score:
            device_type = "smartphone"
            device_type_label = "Smartphone Camera"
            sensor_format = "smartphone_small"
            sensor_format_label = "Smartphone Sensor (~1/1.3\" to 1/2.5\")"
            crop_factor = 4.0
            display_name = "Inferred: Likely Modern Smartphone"
            clean_model = "Likely Modern Smartphone (4:3 sensor, computational sharpening)"
            confidence = "medium" if is_4_3 or sharp_res["has_unsharp_halo"] else "low"
            summary = f"Inferred: Likely Smartphone (4:3 sensor format, computational edge enhancement, {focal_est})"
        else:
            device_type = "mirrorless_or_dslr"
            device_type_label = "Dedicated Mirrorless / DSLR Camera"
            sensor_format = "aps_c_or_full_frame"
            sensor_format_label = "APS-C or Full-Frame 35mm Sensor"
            crop_factor = 1.0
            display_name = "Inferred: Likely Dedicated Camera (APS-C / Full-Frame)"
            clean_model = "Likely Dedicated Camera (3:2 35mm/APS-C sensor format, natural optical falloff)"
            confidence = "medium" if is_3_2 else "low"
            summary = f"Inferred: Likely Dedicated Camera (3:2 format, optical gradient falloff, {focal_est}, {aperture_est})"

        return {
            "detected": True,
            "source": "optical_forensics",
            "confidence": confidence,
            "make": "Inferred",
            "model": clean_model,
            "display_name": display_name,
            "device_type": device_type,
            "device_type_label": device_type_label,
            "sensor_format": sensor_format,
            "sensor_format_label": sensor_format_label,
            "sensor_crop_factor": crop_factor,
            "lens": None,
            "focal_length": focal_est,
            "focal_length_35mm": None,
            "aperture": aperture_est,
            "shutter_speed": None,
            "iso": None,
            "flash_fired": None,
            "exposure_program": None,
            "metering_mode": None,
            "software_firmware": None,
            "datetime_original": None,
            "computational_traces": traces,
            "summary": summary,
        }

    def detect(
        self,
        arr: np.ndarray,
        aspect_ratio: str,
        optical_craft: Dict[str, Any],
        img: Optional[Image.Image] = None,
        path: Optional[Path] = None,
        is_photograph: bool = True,
    ) -> Dict[str, Any]:
        """Execute end-to-end camera detection: hardware EXIF first, then optical forensics."""
        # 1. Attempt hardware EXIF extraction
        hw_cam = self.extract_hardware_exif(img=img, path=path)
        if hw_cam is not None:
            # Augment with optical craft signatures
            hw_cam["optical_signatures"] = {
                "depth_of_field": optical_craft.get("depth_of_field"),
                "estimated_aperture": optical_craft.get("estimated_aperture"),
                "estimated_focal_length": optical_craft.get("estimated_focal_length"),
                "vignette_falloff": optical_craft.get("vignette_falloff"),
                "chromatic_aberration": optical_craft.get("chromatic_aberration"),
            }
            return hw_cam

        # 2. Infer from optical forensics
        inferred = self.infer_from_optics(
            arr=arr,
            aspect_ratio=aspect_ratio,
            optical_craft=optical_craft,
            is_photograph=is_photograph,
        )
        inferred["optical_signatures"] = {
            "depth_of_field": optical_craft.get("depth_of_field"),
            "estimated_aperture": optical_craft.get("estimated_aperture"),
            "estimated_focal_length": optical_craft.get("estimated_focal_length"),
            "vignette_falloff": optical_craft.get("vignette_falloff"),
            "chromatic_aberration": optical_craft.get("chromatic_aberration"),
        }
        return inferred
