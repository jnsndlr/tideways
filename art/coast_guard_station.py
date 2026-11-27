"""Editable Coast Guard shore station. Run with Blender --background --python."""
from math import atan2, hypot, pi
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/coast_guard_station"
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



cream = paint('Salt white siding', 'f0e8d3')
white = paint('White enamel trim', 'fff9e7')
roof = paint('Lifeboat red metal', 'aa4035')
seam = paint('Raised red seam', 'c35a46')
navy = paint('Marine blue', '233f51')
glass = paint('Sea glass', '638f9b')
base = paint('Weathered concrete', 'aea99a')
wood = paint('Oiled timber', '926b49')
orange = paint('Rescue orange', 'ed6338')


def gable(x, y, w, d, eave, rise):
    verts = [(x+dx, y+dy, eave+h) for dy in (-d/2, d/2)
             for dx, h in ((-w/2, 0), (w/2, 0), (0, rise))]
    mesh = bpy.data.meshes.new('Gable infill')
    mesh.from_pydata(verts, [], [(0,1,2),(5,4,3),(0,3,4,1),(1,4,5,2),(2,5,3,0)])
    scene.collection.objects.link(bpy.data.objects.new(mesh.name, mesh))
    mesh.materials.append(cream)
    for side in (-1, 1):
        span = w/2+.34
        drop = rise*span/(w/2)
        panel = box('Roof plane', (x+side*span/2,y,eave+rise-drop/2+.09),
                    (hypot(span,drop),d+.7,.19), roof)
        panel.rotation_euler.y = side*atan2(drop,span)
        for i in range(round(d)+1):
            yp = y-d/2+i*d/round(d)
            beam('Folded seam',(x,yp,eave+rise+.2),
                 (x+side*span,yp,eave+rise-drop+.2),.055,seam)


def shell(w,d,h):
    box('Footing',(0,0,.14),(w+.45,d+.45,.28),base)
    box('Exterior walls',(0,0,(h+.28)/2),(w,d,h-.28),cream)
    for x in (-w/2,w/2):
        for y in (-d/2,d/2):
            box('Corner board',(x,y,h/2+.14),(.19,.19,h-.28),white)


def window(x,y,z,w=1.55,h=1.55,side=False):
    for name,offset,width,height,mat in [
        ('Casing',0,w,h,white),('Sash',.065,w-.16,h-.16,navy),
        ('Glass',.10,w-.3,h-.3,glass),('Mullion',.14,.065,h-.18,white),
        ('Meeting rail',.15,w-.18,.075,white)]:
        pos = (x+offset,y,z) if side else (x,y-offset,z)
        dims = (.10,width,height) if side else (width,.10,height)
        box(name,pos,dims,mat)


def entry(x,y):
    box('Door frame',(x,y,1.52),(1.48,.18,2.52),white)
    box('Door',(x,y-.11,1.5),(1.25,.12,2.32),navy)
    window(x,y-.20,1.92,.87,.85)
    box('Threshold',(x,y-.44,.15),(1.72,.85,.30),base)


def board(title,x,y,z,w,h):
    box('Letterboard',(x,y,z),(w,.18,h),navy)
    sign(title,x,y-.105,z,h*.63,white)


def station():
    shell(10,12,6.5)
    gable(0,0,10,12,6.5,2.65)
    for x in (-3.25,0,3.25):
        window(x,-6.04,4.95)
        if x:
            window(x,-6.04,1.95)
    for y in (-4,0,4):
        for z in (2,4.95):
            window(5.04,y,z,side=True)
    entry(0,-6.04)
    box('Porch deck',(0,-7.02,.18),(8.7,2.15,.36),base)
    for x in (-4, -1.5,1.5,4):
        box('Porch column',(x,-7.87,1.68),(.2,.2,2.7),white)
    canopy = box('Porch roof',(0,-7.04,3.26),(9,2.55,.2),roof)
    canopy.rotation_euler.x = .16
    board('COAST GUARD',0,-6.1,6.93,6.1,.76)
    box('Chimney',(-2.25,3.3,7.8),(.86,1,2.05),roof)
    box('Chimney cap',(-2.25,3.3,8.9),(1.04,1.16,.18),navy)


def boathouse():
    # The center is an open boat well with a clear entrance at the waterline.
    for s in (-1,1):
        x = s*3.68
        for y in (-7.3,-3.7,0,3.7,7.3):
            box('Timber pile',(x,y,.68),(.45,.45,1.36),wood)
        box('Service walkway',(x,0,1.34),(1.4,16,.32),wood)
        box('Side wall',(s*4.26,0,3.85),(.26,15,4.8),cream)
        if s == 1:
            for y in (-5,0,5):
                window(4.41,y,4.32,2.35,1.2,True)
    box('Rear wall',(0,7.42,3.84),(8.6,.22,4.78),cream)
    for y in (-7.46,0,7.42):
        beam('Truss tie',(-4.2,y,6.05),(4.2,y,6.05),.24,wood)
    gable(0,0,8.7,15,6.24,2.7)
    board('LIFEBOATS',0,-7.62,6.81,4.3,.74)
    for x in (-3.63,3.63):
        box('Bay jamb',(x,-7.5,3.83),(1.35,.28,4.72),cream)
        box('Safety band',(x,-7.66,2.4),(1.34,.05,.29),orange)


def lookout():
    shell(3.9,4.1,6.8)
    entry(0,-2.08)
    window(0,-2.08,4.85,1.15,.98)
    box('Gallery',(0,0,6.88),(6,6,.24),navy)
    for s in (-1,1):
        for t in (-1,1):
            beam('Gallery knee',(s*1.86,t*1.97,5.55),(s*2.85,t*2.85,6.78),.19,white)
        for k in (-2.9,0,2.9):
            box('Rail post',(k,s*2.9,7.45),(.09,.09,.96),white)
            box('Rail post',(s*2.9,k,7.45),(.09,.09,.96),white)
        for z in (7.48,7.91):
            box('Guardrail',(0,s*2.9,z),(5.88,.075,.075),white)
            box('Guardrail',(s*2.9,0,z),(.075,5.88,.075),white)
    box('Watch cabin',(0,0,8.13),(4.38,4.38,2.3),navy)
    for s in (-1,1):
        for k in (-1.42,0,1.42):
            box('Lookout pane',(k,s*2.205,8.28),(1.29,.07,1.58),glass)
            box('Lookout pane',(s*2.205,k,8.28),(.07,1.29,1.58),glass)
    bpy.ops.mesh.primitive_cone_add(vertices=4,radius1=3.76,radius2=0,depth=1.63,
                                    rotation=(0,0,pi/4),location=(0,0,10.06))
    bpy.context.object.data.materials.append(roof)
    beam('Radio whip',(0,0,10.75),(0,0,12.6),.085,navy)


def workshop():
    shell(11,7,3.75)
    gable(0,0,11,7,3.75,1.65)
    for x in (-2.75,1.35):
        box('Roller door surround',(x,-3.55,1.67),(3.72,.15,2.94),navy)
        for i in range(8):
            box('Door section',(x,-3.66,.47+i*.34),(3.44,.10,.32),glass if i==5 else cream)
    entry(4.35,-3.56)
    board('RESCUE EQUIPMENT',0,-3.64,4.07,5.65,.65)
    for y in (-2,1.8):
        window(5.54,y,2.24,2,1.14,True)

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


build('station_house', station, (-10,9))
build('watch_tower', lookout, (7,10))
build('lifeboat_house', boathouse, (-10,-11))
build('equipment_garage', workshop, (8,-8))
direction = Vector((32,-64,35))
rotation = (-direction).to_track_quat('-Z','Y')
target = Vector((-1,-1,3.3))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 62
        space.shading.color_type = 'MATERIAL'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/coast_guard_station.blend'))

water = paint('Harbor water','477e88')
quay = paint('Quayside aggregate','a59d88')
box('Harbor surface',(0,0,-.19),(500,500,.40),water)
box('Quayside',(0,48.7,.20),(150,101,.38),quay)
box('Service apron',(13,-8.05,.20),(28,12.5,.38),quay)
for name in ('station_house','watch_tower','equipment_garage'):
    for obj in bpy.data.collections[name].objects:
        obj.location.z += .39
bpy.ops.object.camera_add(location=target+direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 57
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
scene.render.filepath = str(ROOT/'art/coast_guard_station_preview.png')
bpy.ops.render.render(write_still=True)
