"""Photographic shoot planner with ASCII lighting diagrams, gear lists, and post-processing steps."""

from typing import Any, Dict


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
    "Golden hour": """
               [ Low-Angle Setting Sun ]
                           \\
                            v
   [Reflector / Scrim]  (  Subject  )
                            ^
                            |
                       [  Camera  ]
    """,
    "Overcast": """
            [ Diffused Sky / Cloud Cover ]
                        | | |
                        v v v
                     (  Subject  )
                        /   \\
          [Ambient Light]   [Ambient Light]
                         ^
                         |
                    [  Camera  ]
    """,
    "default": """
           [ Ambient Background ]
                      |
                      v
 [Fill / Bounce] (  Subject  )   [Key Light / Natural Source]
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
        subject_is_human: bool = False,
        is_photograph: bool = True,
    ) -> Dict[str, Any]:
        setup_name = (
            lighting_info.get("matched_setup")
            or lighting_info.get("setup_class")
            or lighting_info.get("name")
            or "Natural ambient"
        )
        
        # Match diagram
        diagram = ASCII_LIGHTING_DIAGRAMS.get(setup_name)
        if not diagram:
            # Fuzzy match
            name_lower = setup_name.lower()
            if "golden" in name_lower:
                diagram = ASCII_LIGHTING_DIAGRAMS["Golden hour"]
            elif "overcast" in name_lower:
                diagram = ASCII_LIGHTING_DIAGRAMS["Overcast"]
            elif "window" in name_lower:
                diagram = ASCII_LIGHTING_DIAGRAMS["Window light"]
            elif "rembrandt" in name_lower:
                diagram = ASCII_LIGHTING_DIAGRAMS["Rembrandt lighting"]
            elif "butterfly" in name_lower:
                diagram = ASCII_LIGHTING_DIAGRAMS["Butterfly / Paramount lighting"]
            elif "split" in name_lower:
                diagram = ASCII_LIGHTING_DIAGRAMS["Split lighting"]
            else:
                diagram = ASCII_LIGHTING_DIAGRAMS["default"]

        name_lower = setup_name.lower()
        is_golden = "golden" in name_lower
        is_overcast = "overcast" in name_lower
        is_window = "window" in name_lower
        is_outdoor = is_golden or is_overcast or "outdoor" in name_lower or "sun" in name_lower
        is_studio = any(s in name_lower for s in ("rembrandt", "butterfly", "split", "loop", "softbox", "ring"))

        # Determine location
        if is_golden:
            location = "Outdoor natural setting (open field, yard, garden, or street) during golden hour (30-60m before sunset)"
        elif is_overcast:
            location = "Outdoor location in open shade or under soft overcast cloud cover"
        elif is_window:
            location = "Indoor location adjacent to a large north-facing natural window"
        elif is_studio:
            location = "Photo studio with seamless paper/cyclorama backdrop"
        else:
            location = "Controlled photography location matching scene ambient illumination"

        # Camera & lens settings
        det_cam = camera_info.get("detected_camera") or {}
        focal = det_cam.get("lens") or camera_info.get("estimated_focal_length") or "50mm normal lens"
        aperture = det_cam.get("aperture") or camera_info.get("estimated_aperture") or "f/2.8"
        focal_class = camera_info.get("focal_length_class", "").lower()
        is_telephoto = "telephoto" in focal_class or "telephoto" in str(focal).lower()

        # Build camera description only if image is a real photograph
        if is_photograph and det_cam.get("detected", False) and not det_cam.get("claimed_by_metadata"):
            if det_cam.get("source") in ("hardware_exif", "exif_metadata"):
                cam_body = det_cam.get("summary") or det_cam.get("display_name") or "Standard DSLR / Mirrorless camera"
            else:
                dev_class = det_cam.get("device_type_label", "").lower()
                if "smartphone" in dev_class:
                    cam_body = f"any smartphone camera with {focal}"
                else:
                    cam_body = f"any dedicated camera with {focal}"
            gear_list = [f"Camera: {cam_body}"]
        elif is_photograph:
            cam_body = f"any dedicated camera with {focal}"
            gear_list = [f"Camera: {cam_body}"]
        else:
            cam_body = None
            gear_list = []

        # Shutter speed suited to the scene (use actual hardware settings if available)
        if det_cam.get("shutter_speed"):
            shutter = det_cam["shutter_speed"]
        elif is_outdoor or is_telephoto or not subject_is_human:
            shutter = "1/500s - 1/1000s (fast shutter to freeze subject motion in ambient light)"
        elif is_overcast:
            shutter = "1/250s - 1/500s (handheld camera stability)"
        elif is_studio:
            shutter = "1/160s (strobe sync speed)"
        else:
            shutter = "1/200s"

        if det_cam.get("iso"):
            iso = f"ISO {det_cam['iso']}"
        elif is_outdoor or is_telephoto or not subject_is_human:
            iso = "ISO 100 - 400"
        elif is_overcast:
            iso = "ISO 200 - 800"
        elif is_studio:
            iso = "ISO 100 base"
        else:
            iso = "ISO 100 - 400"

        # Gear list
        gear_list.extend(lighting_info.get("suggested_gear") or lighting_info.get("gear") or [])
        if is_outdoor:
            if not gear_list and is_photograph:
                gear_list = [
                    "Natural ambient sunlight",
                    "Foldable 5-in-1 reflector (gold or silver/white)",
                    "Lens hood to control direct sun flare",
                ]
            if is_photograph:
                gear_list.append(f"Camera body paired with {focal}")
                gear_list.append("Monopod or handheld camera strap for mobility")
        elif is_studio:
            if not gear_list and is_photograph:
                gear_list = [
                    "Key strobe with softbox or beauty dish",
                    "White bounce reflector fill",
                    "Wireless flash trigger transmitter",
                ]
            if is_photograph:
                gear_list.append(f"Camera body paired with {focal}")
                gear_list.append("Heavy-duty studio tripod and light stands")
        else:
            if is_photograph:
                gear_list.append(f"Camera body paired with {focal}")
                gear_list.append("Handheld stabilization or travel tripod")

        # Post-processing pipeline
        split_toning = color_info.get("split_toning", "neutral")
        color_temp = lighting_info.get("color_temperature", "5500K")
        post_processing = [
            f"1. Crop to target aspect ratio: {aspect_ratio}.",
            f"2. Set White Balance based on lighting temperature: {color_temp}.",
            "3. Exposure compensation: balance highlights and shadow detail in RAW converter.",
            f"4. Color grading: apply tone curves to match {split_toning}.",
        ]

        if subject_is_human:
            post_processing.append("5. Frequency separation: subtle skin texture retouching without blurring pores.")
        else:
            post_processing.append("5. Micro-contrast enhancement: refine subject texture (feathers, fur, foliage, or materials) without halo artifacts.")

        post_processing.append("6. Output sharpening: high-pass filter radius 1.2px for web export.")

        return {
            "location": location,
            "camera_settings": {
                "camera": cam_body,
                "lens": focal if is_photograph else None,
                "aperture": aperture if is_photograph else None,
                "shutter_speed": shutter if is_photograph else None,
                "iso": iso if is_photograph else None,
            },
            "lighting_diagram": diagram.strip(),
            "gear_list": gear_list,
            "wardrobe_props": "Natural styling tailored to the scene palette and environment",
            "post_processing_steps": post_processing,
        }
