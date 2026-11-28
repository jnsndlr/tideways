"""Build the town fleet garage. Run with Blender --background --python."""
from math import pi
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def paint(name, hex_code):
    mat = bpy.data.materials.new(name)
    rgb = [int(hex_code[i:i+2], 16) / 255 for i in (0, 2, 4)]
    mat.diffuse_color = (*[((v + .055) / 1.055) ** 2.4 for v in rgb], 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = .78
    return mat


def box(name, xyz, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def letters(body, x, y, z, size, mat):
    bpy.ops.object.text_add(location=(x, y, z), rotation=(pi/2, 0, 0))
    obj = bpy.context.object
    obj.data.body = body
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.size = size
    obj.data.materials.append(mat)
    bpy.ops.object.convert(target='MESH')


def join(parts, active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()


sage = paint('Enamel | spruce', '376458')
cream = paint('Enamel | oyster', 'e1decd')
dark = paint('Folded steel | graphite', '344548')
concrete = paint('Precast concrete', 'a5a598')
glass = paint('Wired glass', '779ba0')
yellow = paint('Traffic yellow', 'edb94e')
brick = paint('Utility brick', 'a76e54')
bay_centers = (-7, -1, 5)
# Front faces Blender -Y (Godot +Z). Slab and apron share a flush datum.
floor = box('Slab', (0, 0, -.12), (22, 15, .24), concrete)
box('Apron', (0, -15, -.13), (23, 15, .24), concrete)
for x in (-10, -4, 2, 8):
    box('Lane stripe', (x, -14.8, -.004), (.12, 13.9, .012), yellow)
box('Back wall', (0, 7.38, 3), (22, .24, 6), cream)
for x in (-10.88, 10.88):
    box('Side wall', (x, 0, 3), (.24, 15, 6), cream)
    for y in range(-7, 8):
        box('Pressed wall seam', (x, y, 3), (.29, .05, 6), concrete)
    box('Concrete plinth', (x, 0, .37), (.33, 15, .74), concrete)
    for y in (-4.8, 0, 4.8):
        box('High sash', (x, y, 4.35), (.38, 3.35, 1.23), dark)
        box('High light', (x, y, 4.35), (.40, 3.18, 1.07), glass)
        box('Meeting stile', (x, y, 4.35), (.42, .09, 1.12), dark)
for x, width in ((-10.2, 1.6), (-4, 1.2), (2, 1.2), (9.2, 3.6)):
    box('Brick pier', (x, -7.38, 2.4), (width, .24, 4.8), brick)
box('Front lintel', (0, -7.38, 5.4), (22, .24, 1.2), sage)
box('Fascia stripe', (0, -7.52, 4.93), (22, .04, .09), yellow)
letters('TOWN  PUBLIC  WORKS', -1, -7.53, 5.5, .68, cream)
box('Personnel door frame', (9, -7.53, 1.2), (1.38, .10, 2.4), dark)
box('Personnel door', (9, -7.6, 1.15), (1.21, .08, 2.3), sage)
box('Door lite', (9, -7.65, 1.68), (.85, .04, .71), glass)
box('Lever', (9.38, -7.70, 1.02), (.21, .10, .05), cream)
box('Roof cap', (0, 0, 6.09), (22.65, 15.65, .23), dark)
for x in range(-11, 12):
    box('Standing seam', (x, 0, 6.23), (.05, 15.55, .07), dark)
for x in (-6, 3):
    box('Roof curb', (x, 2, 6.29), (2.6, 1.8, .18), dark)
    box('Exhaust housing', (x, 2, 6.55), (2.4, 1.6, .46), concrete)
    for i in range(7):
        box('Exhaust louver', (x-.9+i*.3, 2, 6.8), (.14, 1.25, .06), dark)
for i, x in enumerate(bay_centers):
    letters('0'+str(i+1), x-2.97, -7.53, 3.85, .47, cream)
    for side in (-1, 1):
        xp = x+side*2.4
        box('Door guide', (xp, -7.12, 2.4), (.10, .15, 4.8), dark)
        box('Overhead track', (xp, -4.35, 5.06), (.10, 4.55, .13), dark)
        box('Bollard', (xp, -8.04, .52), (.17, .17, 1.04), yellow)
        box('Bollard band', (xp, -8.04, .81), (.18, .18, .13), dark)
shell_parts = list(scene.objects)
# One rigid mesh per moving section, with its origin on the track centerline.
for bay, x in enumerate(bay_centers):
    for row in range(8):
        z = (row+.5)*.6
        panel = box('Bay%dPanel%d' % (bay+1, row+1), (x, -7.12, z),
                    (4.76, .12, .596), cream)
        parts = [panel]
        parts.append(box('Formed rib', (x, -7.193, z-.22), (4.68, .04, .044), concrete))
        if row == 4:
            for dx in (-1.7, -.57, .57, 1.7):
                parts.append(box('Gasket', (x+dx, -7.20, z), (.98, .05, .36), dark))
                parts.append(box('Lite', (x+dx, -7.24, z), (.88, .04, .27), glass))
        join(parts, panel)

direction = Vector((20, -42, 21))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = (-direction).to_track_quat('-Z', 'Y')
        space.region_3d.view_location = (0, -4, 2)
        space.region_3d.view_distance = 36
        space.shading.color_type = 'MATERIAL'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/public_works.blend'))
join(shell_parts, floor)
floor.name = 'FleetGarage'
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets/models/public_works.glb'), export_format='GLB')
