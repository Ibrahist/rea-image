"""Export traces detector: Photoshop/Canva/Figma signatures and JPEG quantization tables."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


# Canonical Standard JPEG Quantization Table (IJG 50% luminance base)
IJG_LUM_50 = np.array([
    [16, 11, 10, 16, 24, 40, 51, 61],
    [12, 12, 14, 19, 26, 58, 60, 55],
    [14, 13, 16, 24, 40, 57, 69, 56],
    [14, 17, 22, 29, 51, 87, 80, 62],
    [18, 22, 37, 56, 68, 109, 103, 77],
    [24, 35, 55, 64, 81, 104, 113, 92],
    [49, 64, 78, 87, 103, 121, 120, 101],
    [72, 92, 95, 98, 112, 100, 103, 99],
], dtype=np.int32)

# Adobe Photoshop Save For Web Quality 12 Luminance Table
PHOTOSHOP_Q12_LUM = np.array([
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1],
], dtype=np.int32)


class ExportTracesDetector(BaseDetector):
    name = "export_traces"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        raw_info = ingest_res.raw_info
        img = ingest_res.rgb_image

        # 1. Inspect software export signatures in info / PNG / XMP
        tool_match = self._find_export_software(raw_info, ingest_res.path)
        if tool_match:
            tool_name = tool_match["tool"]
            category = tool_match["category"]
            target_method = (
                ProductionMethod.GRAPHIC_DESIGN.value
                if category in ("graphic", "screenshot")
                else ProductionMethod.REAL_PHOTO.value
            )
            items.append(
                make_evidence(
                    name="export_software_signature",
                    value=tool_match,
                    direction=target_method,
                    strength=0.82,
                    explanation=f"Export signature identified: '{tool_name}' ({category} software fingerprint).",
                )
            )

        # 2. Color profile quirks (e.g. Display P3 screenshot profile)
        icc = ingest_res.metadata.icc_profile
        if icc:
            icc_lower = icc.lower()
            if "display p3" in icc_lower or "p3" in icc_lower:
                items.append(
                    make_evidence(
                        name="color_profile_quirk",
                        value=icc,
                        direction=ProductionMethod.UI_SCREENSHOT.value,
                        strength=0.65,
                        explanation="Display P3 color profile embedded; commonly produced by Apple display/iOS screenshots.",
                    )
                )

        # 3. JPEG Quantization Table analysis
        if ingest_res.metadata.format.upper() in ("JPEG", "JPG"):
            q_info = self._analyze_quantization_tables(img)
            if q_info.get("found"):
                matched_source = q_info.get("matched_source")
                if matched_source:
                    items.append(
                        make_evidence(
                            name="jpeg_quantization_table",
                            value=q_info,
                            direction=(
                                ProductionMethod.GRAPHIC_DESIGN.value
                                if "Photoshop" in matched_source or "Canva" in matched_source
                                else ProductionMethod.REAL_PHOTO.value
                            ),
                            strength=0.75,
                            explanation=f"JPEG Quantization table matches known encoder: {matched_source}.",
                        )
                    )

        return items

    def _find_export_software(self, raw_info: dict, path: Path) -> Optional[Dict[str, str]]:
        # Common text keys in PNG and metadata
        combined_text = ""
        for k in ("Software", "Software:Text", "Title", "Comment", "xmp", "XML:com.adobe.xmp"):
            val = raw_info.get(k)
            if isinstance(val, bytes):
                val = val.decode("utf-8", errors="ignore")
            if isinstance(val, str):
                combined_text += " " + val

        # Also search raw file header for signatures
        try:
            with open(path, "rb") as f:
                header = f.read(16384).decode("utf-8", errors="ignore")
                combined_text += " " + header
        except Exception:
            pass

        t_lower = combined_text.lower()
        if "photoshop" in t_lower:
            return {"tool": "Adobe Photoshop", "category": "graphic"}
        if "figma" in t_lower:
            return {"tool": "Figma", "category": "graphic"}
        if "canva" in t_lower:
            return {"tool": "Canva", "category": "graphic"}
        if "illustrator" in t_lower:
            return {"tool": "Adobe Illustrator", "category": "graphic"}
        if "lightroom" in t_lower:
            return {"tool": "Adobe Lightroom", "category": "photo"}
        if "blender" in t_lower:
            return {"tool": "Blender", "category": "3d"}
        if "screencapture" in t_lower or "snipping tool" in t_lower or "snip & sketch" in t_lower:
            return {"tool": "OS Screen Capture", "category": "screenshot"}

        return None

    def _analyze_quantization_tables(self, img: Image.Image) -> Dict[str, Any]:
        result = {"found": False}
        qt = getattr(img, "quantization", None)
        if not qt or not isinstance(qt, dict):
            return result

        result["found"] = True
        lum_table = qt.get(0)
        if lum_table and len(lum_table) == 64:
            table_arr = np.array(lum_table, dtype=np.int32).reshape((8, 8))
            result["lum_top_left"] = int(table_arr[0, 0])
            
            # Check for Photoshop Save For Web
            diff_ps = np.mean(np.abs(table_arr - PHOTOSHOP_Q12_LUM))
            if diff_ps < 2.0:
                result["matched_source"] = "Adobe Photoshop Save For Web (High/Max quality)"
                return result

            # Check for standard IJG base
            ratio = table_arr[0, 0] / float(IJG_LUM_50[0, 0])
            if 0.1 <= ratio <= 3.0:
                diff_ijg = np.mean(np.abs(table_arr - (IJG_LUM_50 * ratio)))
                if diff_ijg < 4.0:
                    result["matched_source"] = f"Standard libjpeg encoder (est. scale factor {ratio:.2f})"
                    return result

            result["matched_source"] = "Custom / Camera firmware quantization table"

        return result

