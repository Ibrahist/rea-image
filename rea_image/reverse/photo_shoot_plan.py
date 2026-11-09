"""Photographic shoot planner with ASCII lighting diagrams, gear lists, and post-processing steps."""

from typing import Any, Dict, List, Optional


ASCII_LIGHTING_DIAGRAMS = {
    "Rembrandt lighting": """
           [ Background / Backdrop ]
                      |
                      v
                (  Subject  )
                   /     \\
      [Reflector]         [Key Softbox 45°]
                              \\
                               v
                         [  Camera  ]
    """,
    "Butterfly / Paramount lighting": """
           [ Background / Backdrop ]
                      |
                      v
                (  Subject  )
                      ^
                      |
               [Under-chin Reflector]
                      ^
                      |
               [Overhead Beauty Dish]
                      ^
                      |
                 [ Camera ]
    """,
    "Split lighting": """
           [ Background / Backdrop ]
                      |
                      v
  [Black Flag]  (  Subject  )  <-- [Key Stripbox 90°]
                      ^
                      |
                 [ Camera ]
    """,
    "Window light": """
           [ Background / Backdrop ]
                      |
                      v
 [Bounce Board] (  Subject  )  <-- [Large Window / Scrim]
                      ^
                      |
                 [ Camera ]
    """,
    "default": """
           [ Background / Backdrop ]
                      |
                      v
 [Fill Light]   (  Subject  )   [Key Light]
                      ^
                      |
                 [ Camera ]
    """,
}


class PhotoShootPlanner:
    """Generates practical physical shoot instructions and post-production recipe."""

    def plan(
        self,
        camera_info: Dict[str, Any],
        lighting_info: Dict[str, Any],
        color_info: Dict[str, Any],
        aspect_ratio: str = "3:2",
    ) -> Dict[str, Any]:
        setup_name = lighting_info.get("matched_setup", "Softbox portrait")
        diagram = ASCII_LIGHTING_DIAGRAMS.get(setup_name, ASCII_LIGHTING_DIAGRAMS["default"])

        # Determine camera settings
        focal = camera_info.get("estimated_focal_length", "50mm f/1.8")
        aperture = camera_info.get("estimated_aperture", "f/2.8")
        iso = "ISO 100 - 400"
        shutter = "1/160s (sync speed)"

        # Post-processing pipeline
        split_toning = color_info.get("split_toning", "neutral")
        post_processing = [
            f"1. Crop to target aspect ratio: {aspect_ratio}.",
            f"2. Set White Balance based on lighting temperature: {lighting_info.get('color_temperature', '5500K')}.",
            "3. Exposure compensation: balance highlights and shadow detail in RAW converter.",
            f"4. Color grading: apply tone curves to match {split_toning}.",
            "5. Frequency separation: subtle skin texture retouching without blurring pores.",
            "6. Output sharpening: high-pass filter radius 1.2px for web export.",
        ]

        gear_list = list(lighting_info.get("suggested_gear", []))
        gear_list.extend([
            f"Full-frame or APS-C camera body with {focal}",
            "Sturdy tripod and wireless flash trigger",
            "ColorChecker Passport for accurate color profiling",
        ])

        return {
            "location": "Photo Studio with seamless backdrop or controlled indoor space",
            "camera_settings": {
                "lens": focal,
                "aperture": aperture,
                "shutter_speed": shutter,
                "iso": iso,
            },
            "lighting_diagram": diagram.strip(),
            "gear_list": gear_list,
            "wardrobe_props": "Non-reflective solid colors tailored to the scene palette",
            "post_processing_steps": post_processing,
        }

