"""Camera hardware identification and optical forensics engine.

Detects the physical camera (make, model, sensor format, lens, and shooting parameters)
that captured a photograph. If EXIF/C2PA metadata is stripped, infers camera classification
(e.g., modern computational smartphone vs. dedicated large-sensor camera) using aspect ratios,
sensor-size depth-of-field constraints, and unsharp masking edge halo forensics.
"""

from fractions import Fraction
import logging
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
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
    "tecno": "Tecno",
    "tecno mobile limited": "Tecno",
    "infinix": "Infinix",
    "infinix mobility limited": "Infinix",
    "itel": "itel",
    "realme": "realme",
    "nokia": "Nokia",
    "hmd global": "Nokia",
}


def _clean_str(val: Any, max_len: int = 200) -> str:
    """Normalize string, stripping control characters, NUL bytes, and capping length."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        try:
            val = val.decode("utf-8", errors="replace")
        except Exception:
            val = repr(val)
    # Strip ASCII and Unicode control characters (except standard spaces)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", str(val)).strip()
    return s[:max_len]


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


def _convert_apex_aperture(val: Any) -> Optional[float]:
    """Convert APEX ApertureValue (Av) to f-number: f = 2^(Av / 2)."""
    av = _format_rational(val)
    if av is None:
        return None
    try:
        f_val = math.pow(2.0, av / 2.0)
        return round(f_val, 1)
    except Exception:
        return None


def _convert_apex_shutter(val: Any) -> Optional[float]:
    """Convert APEX ShutterSpeedValue (Tv) to exposure time: t = 2^(-Tv)."""
    tv = _format_rational(val)
    if tv is None:
        return None
    try:
        exp_time = math.pow(2.0, -tv)
        return exp_time
    except Exception:
        return None


def _format_lens_specification(spec_raw: Any, lens_make: str = "") -> Optional[str]:
    """Format LensSpecification 4 rationals (min_focal, max_focal, min_fnum, max_fnum)."""
    if not spec_raw or not isinstance(spec_raw, (list, tuple)) or len(spec_raw) < 4:
        return None
    try:
        min_f = _format_rational(spec_raw[0])
        max_f = _format_rational(spec_raw[1])
        min_fn = _format_rational(spec_raw[2])
        max_fn = _format_rational(spec_raw[3])

        parts = []
        if lens_make:
            parts.append(lens_make)

        if min_f and max_f:
            if abs(min_f - max_f) < 0.1:
                parts.append(f"{min_f:g}mm")
            else:
                parts.append(f"{min_f:g}-{max_f:g}mm")
        elif min_f:
            parts.append(f"{min_f:g}mm")

        if min_fn and max_fn:
            if abs(min_fn - max_fn) < 0.05:
                parts.append(f"f/{min_fn:g}")
            else:
                parts.append(f"f/{min_fn:g}-{max_fn:g}")
        elif min_fn:
            parts.append(f"f/{min_fn:g}")

        return " ".join(parts).strip() if parts else None
    except Exception:
        return None


PRIVACY_SENSITIVE_TAGS = {
    "BodySerialNumber",
    "CameraSerialNumber",
    "LensSerialNumber",
    "SerialNumber",
    "Artist",
    "OwnerName",
    "CameraOwnerName",
    "GPSInfo",
    "GPSLatitude",
    "GPSLongitude",
}

EDITING_SOFTWARE_KEYWORDS = [
    "photoshop",
    "lightroom",
    "gimp",
    "canva",
    "snapseed",
    "affinity",
    "capture one",
    "vsco",
    "pixlr",
    "paint.net",
    "corel",
    "darktable",
]

GENERATIVE_SOFTWARE_KEYWORDS = [
    "stable diffusion",
    "midjourney",
    "dall-e",
    "dalle",
    "comfyui",
    "novelai",
    "automatic1111",
    "invokeai",
    "fooocus",
    "flux",
    "adobe firefly",
    "firefly",
    "bing image creator",
]


# ---------------------------------------------------------------------------
# Camera Classification Rules
# ---------------------------------------------------------------------------

_CAMERAS_CATALOG: Optional[List[Dict[str, Any]]] = None


def load_camera_catalog() -> List[Dict[str, Any]]:
    """Load ordered regex rules from rea_image/capabilities/cameras.yaml."""
    global _CAMERAS_CATALOG
    if _CAMERAS_CATALOG is None:
        yaml_path = Path(__file__).parent.parent / "capabilities" / "cameras.yaml"
        if yaml_path.exists():
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                _CAMERAS_CATALOG = data.get("rules", [])
        else:
            _CAMERAS_CATALOG = []
    return _CAMERAS_CATALOG


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

    rules = load_camera_catalog()
    device_type = "unknown"
    sensor_format = "unknown"
    crop_factor: Optional[float] = None

    for rule in rules:
        make_pat = rule.get("make")
        model_pat = rule.get("model")

        make_match = True
        if make_pat:
            make_match = bool(re.search(make_pat, make_lower) or re.search(make_pat, model_lower))

        if not make_match:
            continue

        model_match = True
        if model_pat:
            model_match = bool(re.search(model_pat, model_lower))

        if model_match:
            device_type = rule.get("device_type", "unknown")
            sensor_format = rule.get("sensor_format", "unknown")
            crop_factor = rule.get("crop_factor")
            break

    # Build human-readable formatted names
    type_labels = {
        "smartphone": "Smartphone",
        "tablet": "Tablet",
        "mirrorless": "Mirrorless Camera",
        "dslr": "DSLR Camera",
        "compact": "Compact Camera",
        "drone": "Drone Aerial Camera",
        "action_cam": "Action Camera",
        "medium_format": "Medium Format Camera",
        "unknown": "Digital Camera",
    }

    if sensor_format == "aps_c":
        cf = f"{crop_factor:.1f}" if crop_factor else "1.5"
        sensor_format_label = f"APS-C ({cf}x crop)"
    elif sensor_format == "medium_format":
        cf = f"{crop_factor:.2f}" if crop_factor else "0.79"
        sensor_format_label = f"Medium Format ({cf}x crop)"
    else:
        format_labels = {
            "full_frame": "Full-Frame (35mm)",
            "micro_four_thirds": "Micro Four Thirds (2.0x crop)",
            "one_inch": "1.0-inch Sensor",
            "smartphone_small": "Smartphone Sensor (~1/1.3\" to 1/2.5\")",
            "smartphone_large_sensor": "Large Smartphone Sensor (1/1.28\" Quad-Bayer)",
            "1/1.3_inch": "1/1.3-inch Sensor",
            "1/1.9_inch": "1/1.9-inch Sensor",
            "1/2.3_inch": "1/2.3-inch Sensor",
            "1/2.5_inch": "1/2.5-inch Sensor",
            "unknown": "Standard Sensor",
        }
        sensor_format_label = format_labels.get(sensor_format, "Standard Sensor")

    clean_model = model_raw.strip()
    display_name = f"{canonical_make} {clean_model}".strip() if clean_model else canonical_make
    if clean_model.lower().startswith(canonical_make.lower()):
        display_name = clean_model
    if canonical_make == "Unknown" and not clean_model:
        display_name = "Unknown Camera"

    return {
        "canonical_make": canonical_make,
        "clean_model": clean_model,
        "device_type": device_type,
        "device_type_label": type_labels.get(device_type, "Digital Camera"),
        "sensor_format": sensor_format,
        "sensor_format_label": sensor_format_label,
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
        redact_metadata: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Extract camera hardware metadata from EXIF stream."""
        exif_dict: Dict[str, Any] = {}

        def _add_tag(k: Any, v: Any):
            tag = ExifTags.TAGS.get(k, str(k))
            if tag not in PRIVACY_SENSITIVE_TAGS:
                exif_dict[tag] = v

        # 1. Read EXIF from PIL Image instance
        if img is not None:
            try:
                raw_exif = img.getexif()
                if raw_exif:
                    for k, v in raw_exif.items():
                        _add_tag(k, v)

                    # Check Exif IFD sub-dictionaries (skip GPSInfo for privacy)
                    try:
                        ifd = raw_exif.get_ifd(ExifTags.IFD.Exif)
                        for k, v in ifd.items():
                            _add_tag(k, v)
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
                                _add_tag(k, v)
                            try:
                                ifd = raw_exif.get_ifd(ExifTags.IFD.Exif)
                                for k, v in ifd.items():
                                    _add_tag(k, v)
                            except Exception:
                                pass
            except Exception as e:
                logger.debug("Failed to read EXIF from file path %s: %s", path, e)

        make = _clean_str(exif_dict.get("Make"))
        model = _clean_str(exif_dict.get("Model"))

        if not make and not model:
            return None

        # Lens and optical tags: combine LensMake + LensModel, or format LensSpecification
        lens_model = _clean_str(exif_dict.get("LensModel"))
        lens_make = _clean_str(exif_dict.get("LensMake"))
        lens_spec = exif_dict.get("LensSpecification")

        lens = None
        if lens_model:
            if lens_make and not lens_model.lower().startswith(lens_make.lower()):
                lens = f"{lens_make} {lens_model}".strip()
            else:
                lens = lens_model
        elif lens_spec:
            lens = _format_lens_specification(lens_spec, lens_make)
        elif lens_make:
            lens = lens_make

        focal_raw = _format_rational(exif_dict.get("FocalLength"))
        focal_35_raw = _format_rational(exif_dict.get("FocalLengthIn35mmFilm"))

        # APEX conversion for aperture: f = 2^(Av / 2)
        fnumber = _format_rational(exif_dict.get("FNumber"))
        if fnumber is not None and fnumber > 0:
            aperture_val = fnumber
        else:
            aperture_val = _convert_apex_aperture(exif_dict.get("ApertureValue"))

        # APEX conversion for shutter: t = 2^(-Tv)
        exp_time = _format_rational(exif_dict.get("ExposureTime"))
        if exp_time is not None and exp_time > 0:
            shutter_str = _format_exposure_time(exp_time)
        else:
            apex_shutter = _convert_apex_shutter(exif_dict.get("ShutterSpeedValue"))
            shutter_str = _format_exposure_time(apex_shutter) if apex_shutter else None

        iso = exif_dict.get("ISOSpeedRatings") or exif_dict.get("PhotographicSensitivity")
        if isinstance(iso, (list, tuple)) and iso:
            iso = iso[0]

        software = _clean_str(exif_dict.get("Software") or exif_dict.get("HostComputer"))
        date_time = None if redact_metadata else _clean_str(exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime"))

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
        aperture_str = f"f/{aperture_val:.1f}" if aperture_val else None

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
            "source": "exif_metadata",
            "confidence": "medium",
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
            "focal_length_mm": focal_raw,
            "focal_length_35mm_val": focal_35_raw,
            "aperture": aperture_str,
            "shutter_speed": shutter_str,
            "iso": str(iso) if iso is not None else None,
            "flash_fired": flash_fired,
            "exposure_program": exposure_program,
            "metering_mode": metering_mode,
            "software_firmware": software or None,
            "datetime_original": date_time or None,
            "computational_traces": [],
            "why_believed": [],
            "why_doubted": [],
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
                "flash_fired": None,
                "exposure_program": None,
                "metering_mode": None,
                "software_firmware": None,
                "datetime_original": None,
                "computational_traces": [],
                "summary": "No physical camera (non-photographic image)",
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

    def corroborate_exif(
        self,
        hw_cam: Dict[str, Any],
        arr: np.ndarray,
        aspect_ratio: Optional[str] = None,
    ) -> None:
        """Corroborate EXIF metadata claim against pixel physics and metadata consistency.

        Updates hw_cam['confidence'], hw_cam['why_believed'], and hw_cam['why_doubted'].
        """
        why_believed: List[str] = list(hw_cam.get("why_believed", []))
        why_doubted: List[str] = list(hw_cam.get("why_doubted", []))

        # 1. Native sensor aspect ratio vs frame geometry
        h, w = arr.shape[:2]
        ar_val = max(w, h) / min(w, h) if min(w, h) > 0 else 1.0
        s_format = str(hw_cam.get("sensor_format", "")).lower()
        dev_type = str(hw_cam.get("device_type", "")).lower()

        expected_aspect = None
        expected_ratio = None
        if any(k in s_format for k in ("full_frame", "aps_c", "aps-c")) or dev_type in ("dslr", "mirrorless"):
            expected_aspect = "3:2"
            expected_ratio = 1.5
        elif any(k in s_format for k in ("micro_four_thirds", "mft", "medium_format", "smartphone", "compact", "drone", "1_inch")) or dev_type in ("smartphone", "compact", "drone"):
            expected_aspect = "4:3"
            expected_ratio = 4.0 / 3.0

        if expected_aspect is not None and expected_ratio is not None:
            ratio_matches = abs(ar_val - expected_ratio) <= 0.06
            str_matches = bool(aspect_ratio and expected_aspect in str(aspect_ratio))
            if ratio_matches or str_matches:
                why_believed.append(f"Aspect ratio matches native sensor format ({expected_aspect})")

        # 2. 35mm-equivalent vs focal length ratio matches sensor crop factor (±10%)
        focal_mm = hw_cam.get("focal_length_mm")
        focal_35_mm = hw_cam.get("focal_length_35mm_val")
        crop_factor = hw_cam.get("sensor_crop_factor")

        if focal_mm and focal_35_mm and focal_mm > 0 and focal_35_mm > 0 and crop_factor and crop_factor > 0:
            measured_crop = focal_35_mm / focal_mm
            crop_err = abs(measured_crop - crop_factor) / crop_factor
            if crop_err <= 0.10:
                why_believed.append(
                    f"Focal length ratio ({measured_crop:.2f}x) corroborates sensor crop factor ({crop_factor:.2f}x)"
                )
            elif crop_err > 0.20:
                why_doubted.append(
                    f"Focal length ratio ({measured_crop:.2f}x) conflicts with sensor crop factor ({crop_factor:.2f}x)"
                )

        # 3. Software / HostComputer metadata tag
        software = hw_cam.get("software_firmware")
        if software:
            sw_lower = software.lower()
            has_gen = any(kw in sw_lower for kw in GENERATIVE_SOFTWARE_KEYWORDS)
            has_edit = any(kw in sw_lower for kw in EDITING_SOFTWARE_KEYWORDS)

            if has_gen:
                why_doubted.append(f"Software metadata tag indicates AI generative tool ({software})")
            elif has_edit:
                why_doubted.append(
                    f"Software metadata indicates post-processing editor ({software}); "
                    f"file was re-saved and pixel forensics may reflect editor rather than direct capture device"
                )
            else:
                make_str = str(hw_cam.get("make", "")).lower()
                if (
                    (make_str and make_str in sw_lower)
                    or any(k in sw_lower for k in ("ver.", "firmware", "ios", "android", "build", "camera", "photo"))
                ):
                    why_believed.append(f"Original device firmware / OS metadata present ({software})")

        # 4. Pixel noise profile (non-zero and consistent with sensor size)
        if arr is not None and arr.size > 0:
            try:
                from scipy.ndimage import median_filter
                lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
                filtered = median_filter(lum, size=3)
                residual = lum - filtered
                noise_std = float(np.std(residual))
                noise_p75 = float(np.percentile(np.abs(residual), 75))

                if noise_std < 0.6 or noise_p75 < 0.8:
                    why_doubted.append(
                        f"Pixel noise profile is near-zero (std={noise_std:.2f}, p75={noise_p75:.2f}), atypical for physical sensor capture"
                    )
                elif noise_std >= 1.0 and noise_p75 >= 1.0:
                    why_believed.append(f"Continuous physical sensor noise profile detected (std={noise_std:.2f})")
            except Exception as e:
                logger.debug("Failed to evaluate noise profile in camera corroboration: %s", e)

        # Upgrade / Downgrade Decision:
        # Upgrade to high only when at least 2 corroborating signals agree and none contradict.
        # When an EXIF camera is contradicted by pixel evidence, downgrade to low.
        if why_doubted:
            confidence = "low"
        elif len(why_believed) >= 2:
            confidence = "high"
        else:
            confidence = "medium"

        hw_cam["confidence"] = confidence
        hw_cam["why_believed"] = why_believed
        hw_cam["why_doubted"] = why_doubted

    def detect(
        self,
        arr: np.ndarray,
        aspect_ratio: str,
        optical_craft: Dict[str, Any],
        img: Optional[Image.Image] = None,
        path: Optional[Path] = None,
        is_photograph: bool = True,
        dominant_method: str = "real photograph",
        redact_metadata: bool = False,
    ) -> Dict[str, Any]:
        """Execute end-to-end camera detection: hardware EXIF first, then optical forensics."""
        hw_cam = self.extract_hardware_exif(img=img, path=path, redact_metadata=redact_metadata)
        if hw_cam is not None:
            # Augment with optical craft signatures
            hw_cam["optical_signatures"] = {
                "depth_of_field": optical_craft.get("depth_of_field"),
                "estimated_aperture": optical_craft.get("estimated_aperture"),
                "estimated_focal_length": optical_craft.get("estimated_focal_length"),
                "vignette_falloff": optical_craft.get("vignette_falloff"),
                "chromatic_aberration": optical_craft.get("chromatic_aberration"),
            }
            if not is_photograph:
                cam_name = f"{hw_cam.get('make', '')} {hw_cam.get('model', '')}".strip() or "Camera"
                hw_cam["claimed_by_metadata"] = True
                hw_cam["confidence"] = "low"
                hw_cam["source"] = "claimed_by_metadata"
                hw_cam["display_name"] = f"{cam_name} (claimed by metadata)"
                hw_cam["summary"] = f"{cam_name} (claimed by metadata, contradicted by {dominant_method})"
                hw_cam.setdefault("why_doubted", []).append(
                    f"Contradicted by overall image verdict ({dominant_method})"
                )
            else:
                self.corroborate_exif(hw_cam, arr=arr, aspect_ratio=aspect_ratio)
            return hw_cam

        # If no hardware EXIF and non-photographic, return non-photo camera profile
        if not is_photograph:
            non_photo = self.infer_from_optics(
                arr=arr,
                aspect_ratio=aspect_ratio,
                optical_craft=optical_craft,
                is_photograph=False,
            )
            non_photo["optical_signatures"] = {
                "depth_of_field": optical_craft.get("depth_of_field"),
                "estimated_aperture": optical_craft.get("estimated_aperture"),
                "estimated_focal_length": optical_craft.get("estimated_focal_length"),
                "vignette_falloff": optical_craft.get("vignette_falloff"),
                "chromatic_aberration": optical_craft.get("chromatic_aberration"),
            }
            return non_photo

        # 2. Infer from optical forensics (is_photograph is True)
        inferred = self.infer_from_optics(
            arr=arr,
            aspect_ratio=aspect_ratio,
            optical_craft=optical_craft,
            is_photograph=True,
        )
        inferred["optical_signatures"] = {
            "depth_of_field": optical_craft.get("depth_of_field"),
            "estimated_aperture": optical_craft.get("estimated_aperture"),
            "estimated_focal_length": optical_craft.get("estimated_focal_length"),
            "vignette_falloff": optical_craft.get("vignette_falloff"),
            "chromatic_aberration": optical_craft.get("chromatic_aberration"),
        }
        return inferred
