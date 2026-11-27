"""Build four individual Godot props and an editable Blender kit."""
from math import atan2, cos, pi, sin, tau
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/airfield_buildings"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def paint(name, hex_color):
    mat = bpy.data.materials.new(name)
    rgb = [int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    mat.diffuse_color = (*[((v + .055) / 1.055) ** 2.4 for v in rgb], 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = .74
    return mat


ivory = paint('Canvas enamel', 'e9ddc4')
spruce = paint('Deep spruce', '294d4d')
green = paint('Patinated roof', '458782')
rib = paint('Folded seam', '69a59a')
red = paint('Oxide red', 'ac5141')
dark = paint('Graphite', '374750')
slate = paint('Blue zinc', '657882')
glass = paint('Harbour glass', '528592')
pale = paint('Sky glass', '80acb3')
cedar = paint('Honey cedar', 'b88557')
cement = paint('Apron concrete', 'aeaa9b')
yellow = paint('Safety ochre', 'edb849')


def box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def beam(name, a, b, width, mat):
    d = Vector(b) - Vector(a)
    obj = box(name, (Vector(a)+Vector(b))/2, (width, width, d.length), mat)
    obj.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()


def sign(body, x, y, z, height, mat):
    bpy.ops.object.text_add(location=(x, y, z), rotation=(pi/2, 0, 0))
    obj = bpy.context.object
    obj.data.body = body
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.size = height
    obj.data.space_character = 1.12
    obj.data.materials.append(mat)
    bpy.ops.object.convert(target='MESH')
    obj.name = body


def roof(name, x1, z1, x2, z2, depth, mat, trim):
    slope = atan2(z2-z1, x2-x1)
    span = ((x2-x1)**2 + (z2-z1)**2)**.5
    for y, d, thickness, color in [(0, depth, .16, mat), (-depth/2, .12, .26, trim),
                                   (depth/2, .12, .26, trim)]:
        obj = box(name, ((x1+x2)/2, y, (z1+z2)/2), (span, d, thickness), color)
        obj.rotation_euler.y = -slope
    count = max(2, round(span / 1.3))
    for i in range(1, count):
        t = i/count
        box('Standing seam', (x1+(x2-x1)*t, 0, z1+(z2-z1)*t+.10), (.06, depth, .09), trim)


def front_window(x, y, z, w, h):
    box('Window frame', (x, y, z), (w, .14, h), spruce)
    box('Glazing', (x, y-.08, z), (w-.14, .05, h-.13), glass)
    box('Mullion', (x, y-.12, z), (.08, .06, h), ivory)


def slab(w, d):
    box('Concrete foundation', (0, 0, .12), (w, d, .24), cement)


def open_hangar():
    slab(19, 15)
    for x in (-8.5, 8.5):
        box('Side wall', (x, .1, 2.58), (.25, 12.4, 4.7), ivory)
        for y in (-5.9, -3, 0, 3, 6):
            box('Portal column', (x, y, 2.58), (.38, .22, 4.7), green)
    box('Rear wall', (0, 6.2, 2.6), (17, .24, 4.75), ivory)
    for y in (-6.2, 0, 6.2):
        beam('Truss tie', (-8.5,y,4.95), (8.5,y,4.95), .16, spruce)
        for s in (-1,1):
            beam('Rafter', (s*8.5,y,4.95), (0,y,7.2), .20, spruce)
            beam('Truss web', (s*4.2,y,4.95), (0,y,7.2), .13, spruce)
        beam('King post', (0,y,4.95), (0,y,7.2), .13, spruce)
    roof('Gable west', -9, 4.98, 0, 7.36, 13.6, green, rib)
    roof('Gable east', 0, 7.36, 9, 4.98, 13.6, green, rib)
    for s in (-1, 1):
        box('Parked door leaf', (s*7.65,-6.32,2.56), (1.65,.22,4.62), green)
        for dx in (-.6,0,.6):
            box('Door flute', (s*7.65+dx,-6.45,2.56), (.065,.06,4.45), rib)
    box('Bay plate', (0,-6.37,5.48), (2.25,.13,.87), spruce)
    sign('01', 0,-6.45,5.48,.8,ivory)


def workshop():
    slab(18.3, 14)
    box('Workshop shell', (0,0,2.71), (17,12,4.95), red)
    for i in range(2):
        start = -8.65+8.65*i
        roof('Sawtooth shed', start,5.25,start+8.65,6.8,12.7,slate,dark)
        # Wedge under each roof, with clerestory panes on its high side.
        v = [(x,y,z) for y in (-6,6) for x,z in ((start,5.15),(start+8.65,5.15),(start+8.65,6.76))]
        mesh = bpy.data.meshes.new('Clerestory wedge')
        mesh.from_pydata(v, [], [(0,1,2),(5,4,3),(0,3,4,1),(1,4,5,2),(2,5,3,0)])
        obj = bpy.data.objects.new(mesh.name, mesh)
        scene.collection.objects.link(obj)
        mesh.materials.append(red)
        for y in (-4.5,-1.5,1.5,4.5):
            box('Clerestory glass',(start+8.67,y,6.05),(.07,2.77,.92),pale)
    box('Door jamb',(-.8,-6.04,2.43),(13.5,.16,4.4),dark)
    for i in range(6):
        x = -6.3+i*2.2
        box('Folding door leaf',(x,-6.16,2.42),(2.15,.14,4.24),ivory)
        front_window(x,-6.25,3.33,1.68,.71)
    box('Service door',(7,-6.1,1.36),(1.25,.18,2.24),dark)
    sign('02',7,-6.14,3.76,1.0,ivory)
    for y in (-4,-1,2,5):
        box('Siding rib',(8.53,y,2.71),(.09,.11,4.95),red)


def office():
    slab(12.4,8.9)
    box('Dispatch office',(0,0,1.85),(11.5,7,3.24),cedar)
    for x in range(-5,6):
        box('Board and batten',(x,-3.54,1.85),(.06,.07,3.22),ivory)
    roof('Office shed roof',-6.05,3.54,6.05,4.21,7.8,green,rib)
    # Fill the triangular strip between the wall plate and the sloping roof.
    for side in (-1,1):
        v = [(-5.75,side*3.5,3.44),(5.75,side*3.5,3.44),(5.75,side*3.5,4.12)]
        m = bpy.data.meshes.new('Gable trim')
        m.from_pydata(v,[],[(0,1,2) if side==-1 else (2,1,0)])
        m.materials.append(cedar)
        scene.collection.objects.link(bpy.data.objects.new(m.name,m))
    box('High side trim',(5.72,0,3.74),(.1,7,.72),cedar)
    for x in (-3.8,-1.6,3.8):
        front_window(x,-3.63,1.86,1.86,1.4)
    box('Entry',(1.25,-3.65,1.43),(1.38,.16,2.4),spruce)
    box('Door glass',(1.25,-3.75,1.77),(1.04,.05,1.22),pale)
    box('Entry canopy',(1.25,-4.15,2.91),(3.15,1.43,.17),green)
    box('Dispatch sign',(-2.68,-3.64,2.94),(4.95,.16,.62),spruce)
    sign('FLIGHT  OFFICE',-2.68,-3.74,2.94,.46,ivory)
    box('Bench seat',(-3.15,-4.05,.73),(3.85,.54,.16),cedar)
    for x in (-4.65,-1.65):
        box('Bench leg',(x,-4.05,.47),(.16,.45,.47),spruce)


def ring(name, bottom, top, z0, z1, mat):
    points = [(cos(tau*(i+.5)/8),sin(tau*(i+.5)/8)) for i in range(8)]
    verts = [(x*r,y*r,z) for r,z in ((bottom,z0),(top,z1)) for x,y in points]
    faces = [tuple(reversed(range(8))), tuple(range(8,16))]
    faces += [(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.materials.append(mat)
    scene.collection.objects.link(bpy.data.objects.new(name,mesh))


def tower():
    slab(6.9,6.9)
    box('Watch tower shaft',(0,0,3.85),(4.55,4.55,7.24),ivory)
    box('Painted plinth',(0,0,.78),(4.62,4.62,1.1),spruce)
    box('Entry door',(0,-2.34,1.49),(1.32,.17,2.5),green)
    for z in (3.85,5.65):
        front_window(0,-2.32,z,1.68,.85)
    ring('Cantilever',2.65,3.8,7.37,7.97,spruce)
    ring('Gallery deck',4.05,4.05,7.94,8.16,slate)
    ring('Cab sill',2.81,2.9,8.14,8.75,red)
    ring('Sloping cab windows',2.9,3.38,8.75,10.64,glass)
    for i in range(8):
        angle = tau*(i+.5)/8
        x,y = cos(angle),sin(angle)
        beam('Cab mullion',(2.9*x,2.9*y,8.75),(3.38*x,3.38*y,10.66),.15,ivory)
        end = tau*(i+1.5)/8
        for z in (8.62,9.06):
            beam('Gallery rail',(3.94*x,3.94*y,z),(3.94*cos(end),3.94*sin(end),z),.07,ivory)
        beam('Stanchion',(3.94*x,3.94*y,8.1),(3.94*x,3.94*y,9.07),.085,ivory)
    ring('Roof fascia',3.65,3.68,10.62,10.91,spruce)
    ring('Cab roof',3.68,.53,10.91,11.62,green)
    beam('Aerial',(0,0,11.6),(0,0,13.3),.1,dark)
    box('Beacon',(0,0,12.01),(.37,.37,.35),yellow)


def build(name, make, position):
    before = set(scene.objects)
    make()
    pieces = list(set(scene.objects)-before)
    group = bpy.data.collections.new(name)
    scene.collection.children.link(group)
    for obj in pieces:
        for coll in list(obj.users_collection):
            coll.objects.unlink(obj)
        group.objects.link(obj)
    # Join temporary copies into one draw mesh, preserving editable source pieces.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in pieces:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = min(pieces,key=lambda o:o.name)
    bpy.ops.object.duplicate()
    bpy.ops.object.join()
    prop = bpy.context.object
    prop.name = name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True)
    bpy.data.objects.remove(prop,do_unlink=True)
    group.instance_offset = (*position,0)
    for obj in pieces:
        obj.location += Vector((*position,0))


build('open_gable_hangar',open_hangar,(-12,-9))
build('sawtooth_workshop_hangar',workshop,(-12,12))
build('flight_office',office,(9,-9))
build('control_tower',tower,(10,10))

direction = Vector((32,-64,35))
rotation = (-direction).to_track_quat('-Z','Y')
target = Vector((-2,1,2.8))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 62
        space.shading.color_type = 'MATERIAL'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/airfield_buildings.blend'))

box('Preview ground',(0,0,-.17),(500,500,.32),paint('Coastal turf','88937c'))
bpy.ops.object.camera_add(location=target+direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 56
scene.camera = camera
scene.world = bpy.data.worlds.new('Coastal daylight')
scene.world.color = (.64,.72,.82)
bpy.ops.object.light_add(type='SUN')
bpy.context.object.rotation_euler = (.49,-.6,-.35)
bpy.context.object.data.energy = 3.5
bpy.context.object.data.angle = .15
scene.render.engine = 'CYCLES'
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x = 1440
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT/'art/airfield_buildings_preview.png')
bpy.ops.render.render(write_still=True)
