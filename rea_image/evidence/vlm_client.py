"""Opt-in Vision-Language Model client with graceful offline degradation."""

import base64
import io
import json
import logging
from typing import Any, Dict, Optional
from PIL import Image
import httpx
from rea_image.config import settings

logger = logging.getLogger(__name__)


class VLMClient:
    """Handles opt-in vision model API calls for visual sanity checks and labeling."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        offline: bool = True,
    ):
        self.offline = offline or settings.offline
        self.provider = provider or settings.vlm_provider or "openai"
        self.model = model or settings.vlm_model or "gpt-4o"
        self.endpoint = endpoint or settings.vlm_endpoint
        self.api_key = api_key or settings.vlm_api_key

    def is_available(self) -> bool:
        """True only if offline mode is disabled and an API key/endpoint is configured."""
        if self.offline:
            return False
        return bool(self.api_key or self.endpoint)

    def analyze_visual_semantics(self, img: Image.Image) -> Optional[Dict[str, Any]]:
        """Query VLM for anatomy, text correctness, lighting, and style sanity checks.
        
        Returns parsed dictionary or None on offline / failure. Never logs or leaks API keys.
        """
        if not self.is_available():
            return None

        # Build prompt
        system_prompt = (
            "You are an expert image forensic analyst. Analyze this image and return a JSON object with: "
            "1. 'anatomy_flaws': bool (are there distorted hands, extra fingers, malformed ears/eyes?)\n"
            "2. 'text_gibberish': bool (are there pseudo-glyphs or misspelled text?)\n"
            "3. 'physics_violations': bool (impossible reflections or perspective?)\n"
            "4. 'style_impression': string ('real photo', 'AI diffusion', '3D render', 'graphic design')\n"
            "5. 'visual_summary': string\n"
            "Output strictly valid JSON."
        )

        try:
            # Encode image to base64 JPEG
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            # Default endpoint handling (OpenAI-compatible format)
            target_url = self.endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze the forensic visual attributes of this image."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                            },
                        ],
                    },
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 500,
            }

            logger.info("Dispatching opt-in VLM semantic inspection call...")
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(target_url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return json.loads(content)
                else:
                    logger.warning(f"VLM endpoint returned status {resp.status_code}; continuing offline.")
        except Exception as e:
            logger.warning(f"VLM call failed ({e.__class__.__name__}); gracefully degrading to offline forensics.")

        return None

