"""Build the Tideways coastal airstrip with Blender in background mode."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def material(name, rgb, glow=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = mat.diffuse_color
    bs.inputs['Roughness'].default_value = .9
    if glow:
        bs.inputs['Emission Color'].default_value = mat.diffuse_color
        bs.inputs['Emission Strength'].default_value = glow
    return mat


asphalt = material('Weathered charcoal asphalt', (.085, .104, .109))
gravel = material('Gravel verge', (.28, .27, .215))
white = material('Ivory runway paint', (.9, .89, .78))
yellow = material('Taxiway yellow', (.95, .59, .055))
metal = material('Galvanised steel', (.29, .35, .36))
lamp = material('Edge light glass', (.97, .87, .59), .6)


def box(name, pos, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


box('Gravel bed', (0, 0, -.15), (486, 27, .3), gravel)
box('Runway pavement', (0, 0, .045), (480, 22, .09), asphalt)
for side in (-1, 1):
    box('Edge stripe', (0, side*10.45, .099), (478, .24, .016), white)
    for x in range(-230, 231, 46):
        box('Light plinth', (x, side*11.8, .13), (.5, .5, .26), metal)
        box('Light lens', (x, side*11.8, .34), (.32, .32, .17), lamp)
for x in range(-168, 169, 24):
    box('Centerline', (x, 0, .099), (11, .35, .016), white)

for side, number in ((-1, '09'), (1, '27')):
    for y in (-8, -6, -4, -2, 2, 4, 6, 8):
        box('Threshold bar', (side*228, y, .099), (16, 1.1, .016), white)
    bpy.ops.object.text_add(location=(side*204, 0, .111))
    obj = bpy.context.object
    obj.name = 'Runway ' + number
    obj.data.body = number
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.materials.append(white)
    bpy.ops.object.convert(target='MESH')
    width, height, _ = obj.dimensions
    obj.scale = (8.2 / width, 13 / height, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.z = side*math.pi/2

# An exit stub with a curved lead-off stripe, terminating at the asset boundary.
box('Exit shoulder', (-141, 21, -.09), (19, 23, .18), gravel)
box('Taxiway exit', (-141, 20.5, .034), (15, 24, .068), asphalt)
# Leave a break in the runway edge stripe at the taxiway mouth.
edge = next(o for o in scene.objects if o.name.startswith('Edge stripe') and o.location.y > 0)
bpy.data.objects.remove(edge, do_unlink=True)
for a, b in ((-239, -148.5), (-133.5, 239)):
    box('Edge stripe', ((a+b)/2, 10.45, .099), (b-a, .24, .016), white)
verts = []
for i in range(17):
    t = math.pi/2*i/16
    for r in (11.87, 12.13):
        verts.append((-153+r*math.sin(t), 12-r*math.cos(t), .114))
verts.extend([(-141.13, 32.4, .114), (-140.87, 32.4, .114)])
mesh = bpy.data.meshes.new('Curved taxi line')
mesh.from_pydata(verts, [], [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(17)])
mesh.materials.append(yellow)
scene.collection.objects.link(bpy.data.objects.new(mesh.name, mesh))

# Batch repeated details by material for the game export.
for mat in list(bpy.data.materials):
    objects = [o for o in scene.objects if len(o.material_slots)==1 and o.active_material == mat]
    if objects:
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.object.join()
        bpy.context.object.name = mat.name
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
direction = Vector((-315, -200, 200))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.clip_end = 3000
        space.region_3d.view_rotation = (-direction).to_track_quat('-Z', 'Y')
        space.region_3d.view_distance = 385
        space.shading.color_type = 'MATERIAL'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/airport_runway.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets/models/airport_runway.glb'), export_format='GLB')

# Studio ground and camera only contribute to the preview.
box('Ground', (0, 0, -.43), (3000, 3000, .24), material('Coastal turf', (.235, .31, .17)))
bpy.ops.object.camera_add(location=direction)
camera = bpy.context.object
camera.rotation_euler = (-direction).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 348
camera.data.clip_end = 3000
scene.camera = camera
scene.world = bpy.data.worlds.new('Overcast daylight')
scene.world.color = (.55, .62, .7)
bpy.ops.object.light_add(type='SUN')
bpy.context.object.rotation_euler = (.48, -.59, -.4)
bpy.context.object.data.energy = 3
scene.render.engine = 'CYCLES'
scene.cycles.samples = 4
scene.render.resolution_x = 1400
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT/'art/airport_runway_preview.png')
bpy.ops.render.render(write_still=True)
