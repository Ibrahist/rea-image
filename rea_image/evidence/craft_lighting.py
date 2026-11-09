"""Lighting setup classification: 12 standard lighting rigs, direction, softness, and gear lists."""

from typing import Any, Dict, List, Optional
import numpy as np
from rea_image.schemas import LightingSetupInfo


STANDARD_SETUPS = {
    "rembrandt": {
        "name": "Rembrandt lighting",
        "description": "Directional key light at 45 degrees creating signature shadow triangle on opposite cheek.",
        "gear": ["Key strobe with 90cm octabox (45° angle)", "White reflector fill (opposite side)", "Black flag for contrast control"],
        "ratio": "3:1 to 4:1",
    },
    "butterfly": {
        "name": "Butterfly / Paramount lighting",
        "description": "High frontal key light centered above subject creating symmetrical butterfly shadow below nose.",
        "gear": ["Beauty dish with diffuser sock (overhead on boom arm)", "Silver reflector below chin", "Rim kicker behind subject"],
        "ratio": "2:1",
    },
    "split": {
        "name": "Split lighting",
        "description": "Key light placed 90 degrees to one side, casting one half of the subject into complete shadow.",
        "gear": ["Strip softbox with honeycomb grid at 90°", "Negative fill flag (solid black) opposite key"],
        "ratio": "8:1 (dramatic contrast)",
    },
    "loop": {
        "name": "Loop lighting",
        "description": "Gentle key light placed slightly higher than eye level at 30-40 degrees, small downward loop shadow.",
        "gear": ["Medium octabox or shoot-through umbrella", "Foldable 5-in-1 reflector"],
        "ratio": "2:1",
    },
    "softbox": {
        "name": "Softbox portrait",
        "description": "Large diffused wraparound lighting with gradual transition from highlights into soft shadows.",
        "gear": ["120cm parabolic softbox or 4x6ft diffusion scrim", "Low-power fill bounce", "Hair light"],
        "ratio": "1.5:1",
    },
    "window_light": {
        "name": "Window light",
        "description": "Soft directional natural illumination with gentle one-sided inverse-square falloff.",
        "gear": ["North-facing large window or 600W LED through 6x6 silk frame", "Sheer white curtain diffuser", "White foam core bounce board"],
        "ratio": "2.5:1",
    },
    "ring_light": {
        "name": "Ring light",
        "description": "Flat, virtually shadowless frontal illumination with distinct halo catchlights in pupils.",
        "gear": ["18-inch bi-color LED ring light centered on lens axis", "Tripod camera mount"],
        "ratio": "1:1 (shadowless)",
    },
    "backlit": {
        "name": "Backlit / Rim light",
        "description": "Strong primary light source located behind subject, creating intense rim outline or silhouette.",
        "gear": ["1200W HMI / Strobe behind subject directed forward", "Warm backlight gel", "Optional subtle front bounce fill"],
        "ratio": "1:6 (backlight dominant)",
    },
    "golden_hour": {
        "name": "Golden hour",
        "description": "Low-angle directional warm sunlight (3200K) creating long dramatic shadows and amber glow.",
        "gear": ["Natural setting sun (30-60m before sunset) or warm tungsten spotlight (3000K) placed low", "Gold reflector fill"],
        "ratio": "4:1",
    },
    "hard_flash": {
        "name": "Hard direct flash",
        "description": "Unmodified point-source flash on-axis with camera; harsh edges, high contrast, specular highlights.",
        "gear": ["On-camera speedlight (direct, zero diffusion)", "Manual trigger"],
        "ratio": "1:1 with harsh shadow edges",
    },
    "neon": {
        "name": "Neon / Cyberpunk practicals",
        "description": "High-saturation opposing color sources (e.g. vibrant cyan key paired with vivid magenta rim).",
        "gear": ["2x Astera Titan / Nanlite Pavotube RGB LED tubes", "Black background drape", "Haze / fog machine for volumetric beam"],
        "ratio": "Dual colored keys (1:1 saturated)",
    },
    "overcast": {
        "name": "Overcast / Ambient diffuse",
        "description": "Even, omnidirectional, shadowless illumination from cloud cover or large ceiling bounce.",
        "gear": ["Overcast daylight sky or 8x8 overhead bounce frame with 300W continuous LEDs", "No hard directional fixtures"],
        "ratio": "1:1",
    },
}


class LightingClassifier:
    """Classifies lighting direction, softness, color temperature, and matched standard rig."""

    def classify(self, arr: np.ndarray) -> LightingSetupInfo:
        h, w, _ = arr.shape
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        
        # 1. Light direction (left vs right, top vs bottom)
        left_lum = float(np.mean(lum[:, : w // 2]))
        right_lum = float(np.mean(lum[:, w // 2 :]))
        top_lum = float(np.mean(lum[: h // 2, :]))
        bottom_lum = float(np.mean(lum[h // 2 :, :]))

        lr_ratio = max(left_lum, right_lum) / (min(left_lum, right_lum) + 1e-4)
        direction = "front / centered"
        if lr_ratio > 1.4:
            direction = "side light (left)" if left_lum > right_lum else "side light (right)"
        elif top_lum > bottom_lum * 1.35:
            direction = "high / overhead light"

        # 2. Softness (gradient steepness)
        gy, gx = np.gradient(lum)
        grad_mag = np.hypot(gx, gy)
        steepness = float(np.percentile(grad_mag, 95))
        
        if steepness > 45.0:
            softness = "hard directional light (sharp defined shadows)"
        elif steepness < 18.0:
            softness = "very soft / diffused wrap (no hard shadow lines)"
        else:
            softness = "moderately soft (diffused modifier)"

        # 3. Color temperature estimate
        r_mean = float(np.mean(arr[:, :, 0]))
        b_mean = float(np.mean(arr[:, :, 2]))
        if r_mean > b_mean * 1.3:
            temp = "warm golden (~3000K - 3800K)"
        elif b_mean > r_mean * 1.25:
            temp = "cool daylight / blue hour (~6500K - 7500K)"
        else:
            temp = "neutral daylight (~5200K - 5600K)"

        # 4. Neon / saturated practicals check
        r = arr[:, :, 0].astype(np.float32)
        g = arr[:, :, 1].astype(np.float32)
        b = arr[:, :, 2].astype(np.float32)
        sat = (np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)) / 255.0
        high_sat_pct = float(np.mean(sat > 0.65))

        # Match to 12 setups
        if high_sat_pct > 0.15:
            setup_key = "neon"
        elif "warm" in temp and "hard" in softness and "side" in direction:
            setup_key = "golden_hour"
        elif "hard" in softness and direction == "front / centered":
            setup_key = "hard_flash"
        elif lr_ratio > 2.2:
            setup_key = "split"
        elif lr_ratio > 1.5:
            setup_key = "rembrandt"
        elif "high" in direction and "soft" in softness:
            setup_key = "butterfly"
        elif "very soft" in softness:
            setup_key = "overcast" if "neutral" in temp or "cool" in temp else "window_light"
        elif "side" in direction:
            setup_key = "window_light"
        else:
            setup_key = "softbox"

        setup_spec = STANDARD_SETUPS[setup_key]

        return LightingSetupInfo(
            matched_setup=setup_spec["name"],
            direction=direction,
            softness=softness,
            color_temperature=temp,
            ratio=setup_spec["ratio"],
            suggested_gear=setup_spec["gear"],
        )

