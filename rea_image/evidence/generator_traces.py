"""AI generator traces: PNG text chunks, ComfyUI/A1111/Invoke parameters, watermarks."""

import json
import re
from typing import Any, Dict, List, Optional
from PIL import Image
from rea_image.evidence.base import BaseDetector, make_evidence
from rea_image.ingest.loader import IngestResult
from rea_image.schemas import EvidenceItem, ProductionMethod


class GeneratorTracesDetector(BaseDetector):
    name = "generator_traces"

    def run(self, ingest_res: IngestResult, regions: Optional[list] = None) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        raw_info = ingest_res.raw_info
        img = ingest_res.rgb_image

        traces = self._extract_generator_chunks(raw_info, img)

        if traces.get("found"):
            generator_type = traces.get("generator", "AI Generator")
            prompt = traces.get("prompt")
            params = traces.get("parameters", {})
            
            explanation_parts = [f"Found embedded generation metadata from {generator_type}"]
            if prompt:
                short_p = (prompt[:120] + "...") if len(prompt) > 120 else prompt
                explanation_parts.append(f"Prompt: \"{short_p}\"")
            if params.get("seed"):
                explanation_parts.append(f"Seed: {params['seed']}")
            if params.get("model"):
                explanation_parts.append(f"Model: {params['model']}")

            items.append(
                make_evidence(
                    name="ai_generator_metadata",
                    value=traces,
                    direction=ProductionMethod.AI_GENERATED.value,
                    strength=0.99,
                    explanation=" | ".join(explanation_parts),
                )
            )

        # Check for invisible-watermark markers (e.g. SD watermark frequency fingerprint)
        wm = self._check_invisible_watermark(ingest_res.rgb_array)
        if wm.get("detected"):
            items.append(
                make_evidence(
                    name="invisible_watermark",
                    value=wm,
                    direction=ProductionMethod.AI_GENERATED.value,
                    strength=0.88,
                    explanation=f"Detected invisible synthetic media watermark ({wm.get('signature')}).",
                )
            )

        return items

    def _extract_generator_chunks(self, raw_info: dict, img: Image.Image) -> Dict[str, Any]:
        result = {"found": False, "parameters": {}}

        # 1. Automatic1111 / Stable Diffusion WebUI "parameters" chunk
        if "parameters" in raw_info:
            param_str = raw_info["parameters"]
            if isinstance(param_str, bytes):
                param_str = param_str.decode("utf-8", errors="ignore")
            result["found"] = True
            result["generator"] = "Stable Diffusion / A1111"
            parsed = self._parse_a1111_parameters(param_str)
            result.update(parsed)
            return result

        # 2. ComfyUI workflow / prompt chunks
        if "prompt" in raw_info or "workflow" in raw_info:
            try:
                raw_prompt = raw_info.get("prompt")
                if isinstance(raw_prompt, str):
                    prompt_data = json.loads(raw_prompt)
                elif isinstance(raw_prompt, dict):
                    prompt_data = raw_prompt
                else:
                    prompt_data = {}

                # Look for KSampler and CLIP positive text
                positive_text = ""
                model_name = ""
                steps = None
                cfg = None
                seed = None

                for node_id, node in prompt_data.items():
                    class_type = node.get("class_type", "")
                    inputs = node.get("inputs", {})
                    if "CLIPTextEncode" in class_type or "Positive" in class_type:
                        text = inputs.get("text", "")
                        if text and len(text) > len(positive_text):
                            positive_text = text
                    elif "KSampler" in class_type:
                        steps = inputs.get("steps")
                        cfg = inputs.get("cfg")
                        seed = inputs.get("seed")
                    elif "CheckpointLoader" in class_type:
                        model_name = inputs.get("ckpt_name", "")

                result["found"] = True
                result["generator"] = "ComfyUI"
                result["prompt"] = positive_text
                result["parameters"] = {
                    "steps": steps,
                    "cfg": cfg,
                    "seed": seed,
                    "model": model_name,
                }
                return result
            except Exception:
                pass

        # 3. NovelAI "Comment" JSON chunk
        if "Comment" in raw_info:
            try:
                comment_str = raw_info["Comment"]
                data = json.loads(comment_str)
                result["found"] = True
                result["generator"] = "NovelAI"
                result["prompt"] = data.get("prompt", "")
                result["negative_prompt"] = data.get("uc", "")
                result["parameters"] = {
                    "steps": data.get("steps"),
                    "scale": data.get("scale"),
                    "seed": data.get("seed"),
                }
                return result
            except Exception:
                pass

        # 4. InvokeAI metadata
        for k in ("sd-metadata", "invokeai_metadata"):
            if k in raw_info:
                try:
                    val = json.loads(raw_info[k])
                    result["found"] = True
                    result["generator"] = "InvokeAI"
                    result["prompt"] = val.get("image", {}).get("prompt", "")
                    result["parameters"] = val.get("image", {})
                    return result
                except Exception:
                    pass

        # 5. Midjourney tags in EXIF or PNG chunks
        for k in ("Description", "UserComment", "ImageDescription", "Comment"):
            val = raw_info.get(k)
            if not val:
                try:
                    exif = img.getexif()
                    if exif:
                        val = exif.get(0x010E) or exif.get(0x9286)
                except Exception:
                    pass
            if val and isinstance(val, (str, bytes)):
                val_str = val.decode("utf-8", errors="ignore") if isinstance(val, bytes) else val
                if any(tag in val_str for tag in ("--v ", "--ar ", "--stylize ", "Midjourney")):
                    result["found"] = True
                    result["generator"] = "Midjourney"
                    result["prompt"] = val_str
                    # Extract Midjourney flags
                    ar_m = re.search(r"--ar\s+(\d+:\d+)", val_str)
                    v_m = re.search(r"--v\s+([0-9.]+)", val_str)
                    s_m = re.search(r"--stylize\s+(\d+)", val_str)
                    result["parameters"] = {
                        "aspect_ratio": ar_m.group(1) if ar_m else None,
                        "version": v_m.group(1) if v_m else None,
                        "stylize": s_m.group(1) if s_m else None,
                    }
                    return result

        return result

    def _parse_a1111_parameters(self, text: str) -> Dict[str, Any]:
        """Parse Automatic1111 parameters text chunk into prompt, negative, and settings."""
        res = {"prompt": "", "negative_prompt": "", "parameters": {}}
        lines = text.strip().split("\n")
        
        prompt_lines = []
        neg_lines = []
        setting_line = ""
        is_neg = False

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("Negative prompt:"):
                is_neg = True
                neg_lines.append(line_str[len("Negative prompt:"):].strip())
            elif line_str.startswith("Steps:") and "Sampler:" in line_str:
                setting_line = line_str
            else:
                if is_neg:
                    neg_lines.append(line_str)
                else:
                    prompt_lines.append(line_str)

        res["prompt"] = " ".join(prompt_lines).strip()
        res["negative_prompt"] = " ".join(neg_lines).strip()

        # Parse key-values in settings line
        if setting_line:
            parts = [p.strip() for p in setting_line.split(",") if ":" in p]
            for part in parts:
                k, v = part.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if k == "steps":
                    res["parameters"]["steps"] = int(v) if v.isdigit() else v
                elif k == "sampler":
                    res["parameters"]["sampler"] = v
                elif k == "cfg scale":
                    res["parameters"]["cfg"] = float(v) if v.replace(".", "", 1).isdigit() else v
                elif k == "seed":
                    res["parameters"]["seed"] = int(v) if v.isdigit() else v
                elif k == "size":
                    res["parameters"]["size"] = v
                elif k == "model":
                    res["parameters"]["model"] = v
                elif k == "model hash":
                    res["parameters"]["model_hash"] = v

        return res

    def _check_invisible_watermark(self, arr) -> Dict[str, Any]:
        """Check for high-frequency watermarking signatures."""
        # Detect Stable Diffusion / DwtDct watermark signature in 48x48 corner frequency band
        import numpy as np
        try:
            h, w, _ = arr.shape
            if h < 64 or w < 64:
                return {"detected": False}
            corner = arr[:64, :64, 0].astype(np.float32)
            # DwtDct watermark places energy in high-frequency band
            fft = np.fft.fft2(corner)
            fft_shift = np.abs(np.fft.fftshift(fft))
            # Ratio of high-frequency diagonal peak
            diag = np.diag(fft_shift)
            peak_ratio = float(np.max(diag[40:]) / (np.mean(fft_shift) + 1e-6))
            if peak_ratio > 35.0:
                return {"detected": True, "signature": "DwtDct / Latent Diffusion high-freq watermark"}
        except Exception:
            pass
        return {"detected": False}

