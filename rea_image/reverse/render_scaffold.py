"""3D Render scaffold generator: scene notes, shader setups, and Blender Python script."""

from typing import Any, Dict, List


class RenderScaffoldBuilder:
    """Generates 3D scene reconstruction notes and executable Blender Python starter script."""

    def build_blender_script(
        self,
        scene_name: str,
        focal_mm: int = 50,
        palette_colors: List[str] = None,
    ) -> str:
        colors = palette_colors or ["#336699", "#E0E0E0", "#FF6600"]
        # Convert hex to RGB float (0.0 to 1.0)
        def hex_to_rgb_float(h):
            h = h.lstrip("#")
            return [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)] + [1.0]

        mat_color = hex_to_rgb_float(colors[0])

        script = f'''"""Blender 4.x Python Setup Script for {scene_name}
Run inside Blender's Scripting workspace (Text Editor -> Run Script).
"""

import bpy
import math

# Clear existing objects in default scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Setup Scene & Render Engine (Cycles)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 256
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# 2. Add Camera
cam_data = bpy.data.cameras.new("ReaCamera")
cam_data.lens = {focal_mm}
cam_obj = bpy.data.objects.new("ReaCamera", cam_data)
scene.collection.objects.link(cam_obj)
cam_obj.location = (0, -4.0, 1.2)
cam_obj.rotation_euler = (math.radians(75), 0, 0)
scene.camera = cam_obj

# 3. Add Studio Key Light (Area Light)
key_light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
key_light_data.energy = 500.0
key_light_data.size = 1.2
key_light_obj = bpy.data.objects.new(name="KeyLight", object_data=key_light_data)
scene.collection.objects.link(key_light_obj)
key_light_obj.location = (2.5, -2.5, 3.0)
key_light_obj.rotation_euler = (math.radians(45), math.radians(15), math.radians(-30))

# 4. Add Fill Light
fill_light_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_light_data.energy = 150.0
fill_light_data.size = 2.0
fill_light_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light_data)
scene.collection.objects.link(fill_light_obj)
fill_light_obj.location = (-2.5, -2.0, 1.5)

# 5. Create Primary Subject Primitive & PBR Material
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.5))
subject = bpy.context.active_object
subject.name = "SubjectMesh"

# Add Principled BSDF Material
mat = bpy.data.materials.new(name="SubjectMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs['Base Color'].default_value = {mat_color}
    bsdf.inputs['Roughness'].default_value = 0.35
    bsdf.inputs['Metallic'].default_value = 0.05
subject.data.materials.append(mat)

# 6. Add Studio Backdrop Plane
bpy.ops.mesh.primitive_plane_add(size=15.0, location=(0, 2.0, 0))
floor = bpy.context.active_object
floor.name = "BackdropPlane"

print("rea-image: Blender scaffold successfully initialized!")
'''
        return script

