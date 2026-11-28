"""Run with Blender in background mode to rebuild the retail kit and preview."""
from math import pi
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/retail_stores"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def paint(name, hex_rgb):
    mat = bpy.data.materials.new(name)
    rgb = [int(hex_rgb[i:i+2], 16) / 255 for i in (0, 2, 4)]
    mat.diffuse_color = (*[((v + .055) / 1.055) ** 2.4 for v in rgb], 1)
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = mat.diffuse_color
    return mat


cream = paint('Buttercream enamel', 'fff0cc')
green = paint('Produce green', '286958')
mint = paint('Celadon', '9db8a0')
red = paint('Persimmon', 'd65c3e')
wood = paint('Oiled cedar', 'ac7347')
clay = paint('Fired brick', 'aa5745')
sand = paint('Limestone', 'd6c2a1')
blue = paint('Marine blue', '325a83')
gold = paint('Marigold', 'f5ba49')
steel = paint('Galvanized steel', '98a6a8')
dark = paint('Charcoal', '34444b')
glass = paint('Coastal glazing', '6ea5ad')
roof = paint('Roof membrane', '7a8584')


def box(name, loc, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    obj.data.materials.append(mat)
    return obj


def sign(label, x, y, z, size, mat):
    bpy.ops.object.text_add(location=(x, y, z), rotation=(pi/2, 0, 0))
    obj = bpy.context.object
    obj.data.body = label
    obj.data.size = size
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.materials.append(mat)
    bpy.ops.object.convert(target='MESH')
    obj.name = label


def shell(w, d, h, wall, edge):
    box('Entry walk', (0, -1, .12), (w+.7, d+2.7, .24), sand)
    box('Store shell', (0, 0, h/2+.24), (w, d, h), wall)
    box('Roof coping', (0, 0, h+.28), (w+.25, d+.25, .26), edge)
    box('Roof membrane', (0, 0, h+.42), (w-.55, d-.55, .08), roof)
    for x in (-w*.27, w*.27):
        box('Air handler', (x, d*.22, h+.87), (2.8, 1.5, .86), steel)
        for dx in (-.72, .72):
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=.52, depth=.08,
                                               location=(x+dx, d*.22, h+1.34))
            bpy.context.object.name = 'Fan grille'
            bpy.context.object.data.materials.append(dark)
    x = -w*.28
    box('Receiving door', (x, d/2+.06, 1.92), (3.2, .15, 3.36), steel)
    for i in range(7):
        box('Roller seam', (x, d/2+.15, .58+i*.45), (3.1, .04, .05), dark)


def window(x, y, width, entry=False):
    bottom = .25 if entry else .69
    box('Aluminium surround', (x, y, (3.25+bottom)/2), (width, .14, 3.25-bottom), dark)
    for side in (-1, 1):
        box('Door glass' if entry else 'Display glass',
            (x+side*width*.245, y-.09, (3.15+bottom)/2), (width*.47, .06, 3.03-bottom), glass)
        if entry:
            box('Push rail', (x+side*width*.245, y-.15, 1.27), (width*.4, .08, .07), cream)


def grocery():
    shell(15, 10, 4.65, mint, green)
    for x in (-4.9, -.2, 4.65):
        window(x, -5.07, 4.05, entry=x==4.65)
    box('Market signboard', (0, -5.12, 4.55), (12.9, .34, 1.38), green)
    sign('SALTWATER  GROCERY', 0, -5.31, 4.55, .99, cream)
    for i in range(19):
        x = (i-9)*.76
        fabric = cream if i%2 else green
        box('Canvas awning', (x, -5.84, 3.54), (.76, 1.74, .12), fabric).rotation_euler.x = .20
        box('Striped valance', (x, -6.67, 3.28), (.76, .08, .28), fabric)
    for x, produce in [(-5, red), (-3.3, gold), (-1.6, green)]:
        box('Market crate', (x, -6, .77), (1.52, .78, .78), wood)
        for dx in (-.47, 0, .47):
            for dy in (-.19, .19):
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.25,
                                                       location=(x+dx, -6+dy, 1.19))
                bpy.context.object.data.materials.append(produce)


def showroom():
    shell(26, 17, 5.4, clay, sand)
    for x in (-9.7, -5.1, 5.1, 9.7):
        window(x, -8.59, 3.8)
        box('Display sunshade', (x, -9.01, 3.52), (4.18, 1.12, .19), wood)
    window(0, -8.59, 3.65, entry=True)
    # Deep timber portal with a house-shaped sign at its peak.
    for side in (-1, 1):
        box('Porch post', (side*3.08, -10.1, 2.42), (.42, .44, 4.36), wood)
        start = Vector((side*3.5, -9.53, 4.44))
        end = Vector((0, -9.53, 6.91))
        rafter = box('Gable roof', (start+end)/2, ((end-start).length, 2.55, .32), dark)
        rafter.rotation_euler.y = side * .615
    box('Shop name fascia', (0, -10.66, 4.22), (7.54, .29, 1.1), cream)
    sign('HEARTH & HOME', 0, -10.82, 4.23, .74, clay)
    box('Gable king post', (0, -10.48, 5.55), (.23, .21, 2.29), wood)
    sign('HOME GOODS', 7.79, -8.54, 4.54, .76, cream)


def megamart():
    shell(38, 24, 6.6, sand, blue)
    for x in (-14, -9.5, -5, 8.9, 14):
        window(x, -12.08, 4)
    box('Blue entry tower', (1.8, -12.24, 4.08), (12.5, 1.05, 7.68), blue)
    sign('MEGA MART', 1.8, -12.79, 6.55, 1.72, cream)
    box('Gold entry stripe', (1.8, -12.81, 5.36), (12.48, .11, .18), gold)
    for x in (-.7, 4.3):
        window(x, -12.84, 4.29, entry=True)
    box('Pickup canopy', (1.8, -13.28, 3.72), (13.4, 2.26, .38), gold)
    for x in (-4.36, 7.96):
        box('Canopy post', (x, -14.22, 1.88), (.22, .22, 3.3), blue)
    for y in (-8, -3, 2, 7):
        box('Side panel joint', (19.01, y, 3.52), (.08, .12, 6.55), steel)
    box('Wraparound belt', (0, 0, 4.85), (38.14, 24.15, .36), blue)


def export_model(name, build, offset):
    before = set(scene.objects)
    build()
    parts = sorted(set(scene.objects)-before, key=lambda obj: obj.name)
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.users_collection[0].objects.unlink(obj)
        collection.objects.link(obj)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.duplicate()
    bpy.ops.object.join()
    baked = bpy.context.object
    baked.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')), use_selection=True)
    bpy.data.objects.remove(baked, do_unlink=True)
    collection.instance_offset = (*offset, 0)
    for obj in parts:
        obj.location += Vector((*offset, 0))


def preview(kit, target, direction, scale, height):
    rotation = (-direction).to_track_quat('-Z', 'Y')
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            view = area.spaces.active
            view.region_3d.view_location = target
            view.region_3d.view_rotation = rotation
            view.region_3d.view_distance = scale
            view.shading.color_type = 'MATERIAL'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art'/f'{kit}.blend'), compress=True)
    box('Preview ground', (0, 0, -.17), (500, 500, .34), paint('Coastal turf', '98a18c'))
    bpy.ops.object.camera_add(location=target+direction)
    scene.camera = bpy.context.object
    scene.camera.rotation_euler = rotation.to_euler()
    scene.camera.data.type = 'ORTHO'
    scene.camera.data.ortho_scale = scale
    scene.camera.data.clip_end = 400
    scene.world = bpy.data.worlds.new('Coastal daylight')
    scene.world.color = (.55, .61, .68)
    bpy.ops.object.light_add(type='SUN')
    bpy.context.object.rotation_euler = (.52, -.55, -.3)
    bpy.context.object.data.energy = 3.2
    bpy.context.object.data.angle = .14
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 8
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1800
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(ROOT/'art'/f'{kit}_preview.png')
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    stores = [('saltwater_grocery', grocery, (-29, -10)),
              ('hearth_and_home', showroom, (-4, -1)),
              ('mega_mart', megamart, (33, 11))]
    for item in stores:
        export_model(*item)
    preview("retail_stores", Vector((6, 1, 2)), Vector((33, -83, 44)), 110, 640)
