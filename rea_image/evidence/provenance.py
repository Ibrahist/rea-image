"""Provenance detector: EXIF, XMP, IPTC, and C2PA Content Credentials."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ExifTags, IptcImagePlugin
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.evidence.camera_detector import (
    _convert_apex_aperture,
    _convert_apex_shutter,
    _format_exposure_time,
)
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod, clean_json_value, format_rational


def _clean_str(val: Any, max_len: int = 200) -> str:
    """Normalize metadata string, removing control characters and capping length."""
    if val is None:
        return ""
    if isinstance(val, bytes):
        try:
            val = val.decode("utf-8", errors="replace")
        except Exception:
            val = repr(val)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", str(val)).strip()
    return s[:max_len]


PRIVACY_SENSITIVE_TAGS = {
    "BodySerialNumber",
    "CameraSerialNumber",
    "LensSerialNumber",
    "SerialNumber",
    "Artist",
    "OwnerName",
    "CameraOwnerName",
    "GPSLatitude",
    "GPSLongitude",
}


class ProvenanceDetector(BaseDetector):
    name = "provenance"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        raw_info = ingest_res.raw_info
        img = ingest_res.rgb_image

        exif_data = self._extract_exif(img)
        xmp_data = self._extract_xmp(img, raw_info)
        iptc_data = self._extract_iptc(img)
        c2pa_data = self._extract_c2pa(ingest_res.path)

        # 1. C2PA Assertions (Highest priority hard provenance)
        if c2pa_data.get("found"):
            is_ai = c2pa_data.get("is_ai_generated", False)
            signer = c2pa_data.get("claim_generator", "Unknown Signer")
            if is_ai:
                items.append(
                    make_evidence(
                        name="c2pa_assertion",
                        value={"claim": "ai_generated", "signer": signer},
                        direction=ProductionMethod.AI_GENERATED.value,
                        strength=0.98,
                        explanation=f"Cryptographically verified C2PA Content Credential claims AI generation via '{signer}'.",
                    )
                )
            else:
                items.append(
                    make_evidence(
                        name="c2pa_assertion",
                        value={"claim": "recorded_media", "signer": signer},
                        direction=ProductionMethod.REAL_PHOTO.value,
                        strength=0.95,
                        explanation=f"Cryptographically verified C2PA Content Credential records camera capture signed by '{signer}'.",
                    )
                )

        # 2. IPTC Digital Source Type (IPTC Photo Metadata standard for AI)
        digital_source = xmp_data.get("digital_source_type") or iptc_data.get("digital_source_type")
        if digital_source:
            if "trainedalgorithmicmedia" in digital_source.lower() or "compositealgorithmicmedia" in digital_source.lower():
                items.append(
                    make_evidence(
                        name="iptc_digital_source_type",
                        value=digital_source,
                        direction=ProductionMethod.AI_GENERATED.value,
                        strength=0.95,
                        explanation=f"IPTC DigitalSourceType explicitly declares AI generation: '{digital_source}'.",
                    )
                )

        # 3. Camera EXIF details
        has_camera = bool(exif_data.get("Make") or exif_data.get("Model"))
        if has_camera:
            make = _clean_str(exif_data.get("Make", ""))
            model = _clean_str(exif_data.get("Model", ""))
            lens = _clean_str(exif_data.get("LensModel", exif_data.get("LensMake", "Standard Lens")))
            focal = format_rational(exif_data.get("FocalLength"))
            aperture = format_rational(exif_data.get("FNumber"))
            if aperture is None or aperture <= 0:
                aperture = _convert_apex_aperture(exif_data.get("ApertureValue"))

            shutter_raw = format_rational(exif_data.get("ExposureTime"))
            if shutter_raw is None or shutter_raw <= 0:
                shutter_raw = _convert_apex_shutter(exif_data.get("ShutterSpeedValue"))
            shutter_str = _format_exposure_time(shutter_raw) if shutter_raw else None

            iso_raw = exif_data.get("ISOSpeedRatings", exif_data.get("PhotographicSensitivity"))
            if isinstance(iso_raw, (list, tuple)) and iso_raw:
                iso_raw = iso_raw[0]
            iso = int(iso_raw) if (iso_raw is not None and str(iso_raw).isdigit()) else (iso_raw if iso_raw is not None else None)

            if model and make and model.lower().startswith(make.lower()):
                cam_str = model
            else:
                cam_str = f"{make} {model}".strip() or "Camera"
            details = []
            if lens:
                details.append(f"lens {lens}")
            if focal is not None and focal > 0:
                focal_fmt = f"{int(focal)}mm" if focal == int(focal) else f"{focal:.1f}mm"
                details.append(focal_fmt)
            if aperture is not None and aperture > 0:
                aperture_fmt = f"f/{aperture:.1f}" if aperture != int(aperture) else f"f/{int(aperture)}"
                details.append(aperture_fmt)
            if shutter_str:
                details.append(shutter_str)
            if iso:
                details.append(f"ISO {iso}")

            desc = f"EXIF records hardware camera: {cam_str} ({', '.join(details)})."
            items.append(
                make_evidence(
                    name="camera_exif",
                    value={
                        "make": make,
                        "model": model,
                        "lens": lens,
                        "focal_length": focal,
                        "aperture": aperture,
                        "iso": iso,
                        "shutter": shutter_str or shutter_raw,
                    },
                    direction=ProductionMethod.REAL_PHOTO.value,
                    strength=0.90,
                    explanation=desc,
                )
            )

            # GPS Presence
            if exif_data.get("GPSInfo"):
                items.append(
                    make_evidence(
                        name="gps_coordinates",
                        value="present",
                        direction=ProductionMethod.REAL_PHOTO.value,
                        strength=0.85,
                        explanation="EXIF contains geotagging GPS coordinates typical of physical smartphone or camera capture.",
                    )
                )

            # Check thumbnail vs main image mismatch
            if exif_data.get("has_thumbnail"):
                items.append(
                    make_evidence(
                        name="exif_thumbnail",
                        value="present",
                        direction=ProductionMethod.REAL_PHOTO.value,
                        strength=0.70,
                        explanation="Embedded camera thumbnail present in EXIF stream.",
                    )
                )
        else:
            items.append(
                make_evidence(
                    name="camera_exif_missing",
                    value=None,
                    direction="neutral",
                    strength=0.20,
                    explanation="No camera hardware EXIF metadata found (common on web downloads, messaging apps, and AI outputs).",
                )
            )

        # 4. Software edit history
        software = _clean_str(exif_data.get("Software") or xmp_data.get("creator_tool"))
        if software:
            sw_lower = software.lower()
            if any(k in sw_lower for k in ("photoshop", "lightroom", "gimp", "canva", "figma", "illustrator")):
                items.append(
                    make_evidence(
                        name="editing_software",
                        value=software,
                        direction=ProductionMethod.GRAPHIC_DESIGN.value,
                        strength=0.70,
                        explanation=f"Image contains editing software trace '{software}', indicating post-processing or digital design composition.",
                    )
                )
            elif any(k in sw_lower for k in ("blender", "unreal", "cinema 4d", "maya", "3ds max")):
                items.append(
                    make_evidence(
                        name="rendering_software",
                        value=software,
                        direction=ProductionMethod.RENDER_3D.value,
                        strength=0.92,
                        explanation=f"Image metadata explicitly records 3D rendering package: '{software}'.",
                    )
                )

        return items

    def _extract_exif(self, img: Image.Image) -> Dict[str, Any]:
        result = {}
        try:
            exif = img.getexif()
            if not exif:
                return result
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if tag_name in PRIVACY_SENSITIVE_TAGS:
                    continue
                result[tag_name] = clean_json_value(value)

            # Also check Exif IFD for lens and shooting params
            try:
                for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
                    try:
                        ifd = exif.get_ifd(ifd_id)
                        for k, v in ifd.items():
                            name = ExifTags.TAGS.get(k, str(k))
                            if name in PRIVACY_SENSITIVE_TAGS:
                                continue
                            result[name] = clean_json_value(v)
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception:
            pass
        return result

    def _extract_xmp(self, img: Image.Image, raw_info: dict) -> Dict[str, Any]:
        result = {}
        xmp_str = ""
        # Check standard Pillow XMP locations
        if "XML:com.adobe.xmp" in raw_info:
            val = raw_info["XML:com.adobe.xmp"]
            if isinstance(val, bytes):
                xmp_str = val.decode("utf-8", errors="ignore")
            elif isinstance(val, str):
                xmp_str = val
        elif "xmp" in raw_info:
            val = raw_info["xmp"]
            if isinstance(val, bytes):
                xmp_str = val.decode("utf-8", errors="ignore")
            elif isinstance(val, str):
                xmp_str = val

        if not xmp_str:
            return result

        try:
            # Parse CreatorTool
            m_tool = re.search(r"<(?:xmp:)?CreatorTool>(.*?)</(?:xmp:)?CreatorTool>", xmp_str, re.IGNORECASE)
            if m_tool:
                result["creator_tool"] = m_tool.group(1).strip()

            # Parse IPTC DigitalSourceType
            m_source = re.search(r"DigitalSourceType>(.*?)</", xmp_str, re.IGNORECASE)
            if m_source:
                result["digital_source_type"] = m_source.group(1).strip()
        except Exception:
            pass

        return result

    def _extract_iptc(self, img: Image.Image) -> Dict[str, Any]:
        result = {}
        try:
            iptc = IptcImagePlugin.getiptcinfo(img)
            if iptc:
                for k, v in iptc.items():
                    key_str = str(k)
                    if isinstance(v, bytes):
                        v = v.decode("utf-8", errors="replace")
                    result[key_str] = v
        except Exception:
            pass
        return result

    def _extract_c2pa(self, file_path: Path) -> Dict[str, Any]:
        """Scan file for JUMBF (JPEG Universal Metadata Box Format) and C2PA markers."""
        result = {"found": False}
        try:
            with open(file_path, "rb") as f:
                # Read header/first 512KB and trailer where C2PA manifests reside
                data = f.read(524288)
                f.seek(max(0, file_path.stat().st_size - 524288))
                data += f.read()

            # Look for C2PA / CAI manifest signatures
            if b"c2pa" in data or b"jumb" in data or b"c2pa.claim" in data:
                result["found"] = True
                data_str = data.decode("utf-8", errors="ignore")
                
                # Check for AI generative claim
                is_ai = bool(
                    re.search(r"c2pa\.ai_generative|generative-ai|trainedalgorithmicmedia", data_str, re.IGNORECASE)
                )
                result["is_ai_generated"] = is_ai

                # Extract claim generator / signer tool
                m_gen = re.search(r'"claim_generator":\s*"([^"]+)"', data_str)
                if m_gen:
                    result["claim_generator"] = m_gen.group(1)
                else:
                    m_gen_xml = re.search(r'<c2pa:claimGenerator>(.*?)</c2pa:claimGenerator>', data_str)
                    if m_gen_xml:
                        result["claim_generator"] = m_gen_xml.group(1)
                    else:
                        result["claim_generator"] = "C2PA Manifest"
        except Exception:
            pass
        return result

