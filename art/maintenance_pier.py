"""Build the ferry maintenance pier. Run with Blender in background mode."""
import math
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
palette = {}
def paint(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .74
    palette[name] = m
    return name

ivory = paint('Warm enamel', (.82,.80,.68))
trim = paint('Chalk trim', (.94,.91,.79))
roof = paint('Standing seam zinc', (.46,.54,.54))
steel = paint('Galvanized steel', (.32,.41,.42))
dark = paint('Deep marine blue', (.035,.10,.13))
glass = paint('Harbor glass', (.10,.23,.27))
teal = paint('Boatyard green', (.085,.35,.32))
red = paint('Oxide red', (.52,.12,.064))
yellow = paint('Safety ochre', (.92,.57,.12))
deck = paint('Pier concrete', (.42,.43,.39))
wood = paint('Creosoted timber', (.17,.115,.08))
wet = paint('Tidal staining', (.081,.088,.075))
parts = {}
group = 'Pier'
def mesh(v, f, mat):
    verts, faces, mats = parts.setdefault(group, ([], [], []))
    start = len(verts)
    verts.extend(v)
    faces.extend([tuple(start+i for i in face) for face in f])
    mats.extend([mat]*len(f))

def prism(top, bottom, mat):
    n = len(top)
    mesh(bottom+top, [tuple(reversed(range(n))), tuple(range(n,2*n))]+
         [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],mat)

def box(x,y,z,w,d,h,mat, slope=0):
    xy=[(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]
    def layer(offset):
        return [(x+a,y+b,z+offset+b*slope) for a,b in xy]
    prism(layer(h/2),layer(-h/2),mat)

def post(x,y,z,r,h,mat):
    ring=[(x+r*math.cos(i*math.pi/6),y+r*math.sin(i*math.pi/6)) for i in range(12)]
    prism([(a,b,z+h) for a,b in ring],[(a,b,z) for a,b in ring],mat)

def brace(a,b,width,mat):
    a,b=Vector(a),Vector(b)
    rot=(b-a).to_track_quat('Z','Y')
    ring=[rot @ Vector((i*width/2,j*width/2,0)) for i,j in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    prism([tuple(b+p) for p in ring],[tuple(a+p) for p in ring],mat)

# Deck elevation 3.8 m above the waterline, with submerged pile ends.
box(0,0,3.47,78,42,.66,deck)
for x in range(-36,37,9):
    box(x,0,2.82,1,41,.65,wood)
    for y in [-19,-10,0,10,19]:
        post(x,y,-3,.51,5.87,wood)
        post(x,y,-3,.52,3.35,wet)
    if x<36:
        for y in [-19,19]:
            brace((x,y,-.55),(x+9,y,2.64),.34,wood)
            brace((x,y+.18,2.64),(x+9,y+.18,-.55),.34,wood)
for y in [-20.8,20.8]:
    box(0,y,3.17,78,.46,.44,wood)
    for x in range(-36,37,6):
        box(x,y*1.017,1.72,.68,.52,3.48,wood)
        box(x,y*1.017,3.29,.71,.55,.18,steel)
for x in [-38.1,38.1]:
    for y in range(-18,19,3):
        post(x,y,3.8,.062,1.02,steel)
    for z in [4.30,4.81]:
        box(x,0,z,.075,36,.075,steel)
for x in range(-32,33,8):
    post(x,-19.55,3.8,.33,.14,dark)
    post(x,-19.55,3.94,.20,.49,yellow)
    post(x,-19.55,4.39,.29,.12,yellow)

group='Maintenance hall'
box(0,3,8.1,57,23,8.6,ivory)
box(0,3,4.59,57.16,23.16,1.58,deck)
box(0,3,5.43,57.2,23.2,.16,red)
for y,slope in [(-2.8,.052),(8.8,-.052)]:
    box(0,y,12.65,58,11.8,.26,roof,slope)
    for x in range(-28,29,2):
        box(x,y,12.81,.064,11.8,.075,steel,slope)
box(0,5.25,14.74,53,12,5.0,ivory)
for y,slope in [(2.13,.075),(8.37,-.075)]:
    box(0,y,17.54,54.1,6.30,.24,roof,slope)
    for x in range(-26,27,2):
        box(x,y,17.68,.064,6.30,.075,steel,slope)
box(0,5.25,17.93,54.2,.32,.15,trim)
def windows(x,y,z,w,h,side):
    box(x,y,z,w+.22,.15,h+.22,trim)
    box(x,y+.085*side,z,w,.10,h,glass)
    for k in [-1,1]:
        box(x+k*w/6,y+.15*side,z,.095,.065,h,trim)
for side,y in [(-1,-.78),(1,11.28)]:
    for x in range(-24,25,4):
        for z in (14.04,15.97):
            windows(x,y,z,2.85,1.23,side)
for side,y in [(-1,-8.53),(1,14.53)]:
    for x in range(-26,27,4):
        windows(x,y,10.72,2.58,1.3,side)
    for x in range(-28,29,4):
        box(x,y,8.65,.11,.14,6.34,trim)
for side in [-1,1]:
    for y in [-5,0,5,10]:
        box(side*28.53,y,9.4,.19,2.4,1.82,trim)
        box(side*28.64,y,9.4,.08,2.17,1.62,glass)
        box(side*28.70,y,9.4,.07,.1,1.62,trim)

group='Loading apron'
def lettering(body,x,y,z,size,mat):
    curve=bpy.data.curves.new(body,'FONT')
    curve.body=body
    curve.align_x='CENTER'
    curve.align_y='CENTER'
    curve.size=size
    obj=bpy.data.objects.new(body,curve)
    bpy.context.collection.objects.link(obj)
    obj.location=(x,y,z)
    obj.rotation_euler.x=math.pi/2
    curve.materials.append(palette[mat])
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj.select_set(False)

for i,x in enumerate([-21,-12,-3]):
    box(x,-8.65,6.39,6.4,.3,5.17,dark)
    box(x,-8.84,6.37,5.92,.12,4.98,teal)
    for n in range(11):
        box(x,-8.92,4.13+n*.42,5.86,.045,.055,steel)
    box(x,-9.26,9.20,7.1,1.7,.19,roof,.08)
    lettering(f'0{i+1}',x,-8.98,7.46,.86,trim)
    for k in [-1,1]:
        post(x+3.46*k,-9.54,3.8,.13,1.28,yellow)
        box(x+3.46*k,-13.5,3.812,.12,6,.02,yellow)
box(15,-9.4,5.78,17,2,3.96,teal)
box(15,-9.75,7.89,17.6,2.9,.26,roof,.09)
for x in [9.2,13.3,17.4]:
    windows(x,-10.43,6.03,2.78,1.42,-1)
box(21,-10.45,5.05,1.45,.16,2.5,dark)
box(15,-8.68,8.96,17,.19,1.31,dark)
lettering('F E R R Y   W O R K S',15,-8.79,8.97,.84,trim)
# Small roof extractors break the ridge silhouette.
for x in [-18,0,18]:
    post(x,6.65,17.75,.55,.79,steel)
    post(x,6.65,18.48,.78,.19,dark)

for name,(v,f,materials) in parts.items():
    data=bpy.data.meshes.new(name)
    data.from_pydata(v,[],f)
    keys=list(dict.fromkeys(materials))
    for key in keys:
        data.materials.append(palette[key])
    for poly,key in zip(data.polygons,materials):
        poly.material_index=keys.index(key)
    bpy.context.collection.objects.link(bpy.data.objects.new(name,data))
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets/models/maintenance_pier.glb'),export_format='GLB')
# The presentation rig lives only in the preview.
direction=Vector((50,-91,41))
target=Vector((0,0,7))
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        view=area.spaces.active
        view.region_3d.view_rotation=(-direction).to_track_quat('-Z','Y')
        view.region_3d.view_distance=94
        view.region_3d.view_location=target
        view.shading.color_type='MATERIAL'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art/maintenance_pier.blend'))
bpy.ops.mesh.primitive_plane_add(size=2000,location=(0,0,0))
water=bpy.data.materials.new('Sound water')
water.use_nodes=True
nodes=water.node_tree.nodes
bs=nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value=(.065,.19,.22,1)
bs.inputs['Roughness'].default_value=.32
noise=nodes.new('ShaderNodeTexNoise')
tex=nodes.new('ShaderNodeTexCoord')
water.node_tree.links.new(tex.outputs['Object'],noise.inputs['Vector'])
noise.inputs['Scale'].default_value=1.6
bump=nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value=.17
bump.inputs['Distance'].default_value=.10
water.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height'])
water.node_tree.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
bpy.context.object.data.materials.append(water)
bpy.ops.object.camera_add(location=target+direction)
cam=bpy.context.object
cam.rotation_euler=(-direction).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO'
cam.data.ortho_scale=100
scene.camera=cam
scene.world=bpy.data.worlds.new('Maritime daylight')
scene.world.color=(.55,.59,.65)
bpy.ops.object.light_add(type='SUN')
sun=bpy.context.object
sun.rotation_euler=Vector((.45,.65,-1)).to_track_quat('-Z','Y').to_euler()
sun.data.energy=3
sun.data.angle=.12
scene.render.engine='CYCLES'
scene.cycles.samples=8
scene.cycles.use_denoising=True
scene.render.resolution_x=1280
scene.render.resolution_y=800
scene.render.resolution_percentage=100
cam.data.clip_end=2000
scene.render.filepath=str(ROOT/'art/maintenance_pier_preview.png')
bpy.ops.render.render(write_still=True)
