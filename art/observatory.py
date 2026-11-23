"""Rebuild the Tideways observatory with Blender in background mode."""
import bpy
import math
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rad = math.radians

def material(name, color, metal=0, rough=.5):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    return m

patina = [material('Verdigris '+str(i), c, .48) for i,c in enumerate([
    (.095,.36,.34), (.083,.315,.305), (.11,.38,.35), (.075,.30,.285)])]
iron = material('Deep petrol enamel', (.023,.067,.082), .5)
brass = material('Brushed bronze', (.65,.37,.12), .62)
stone = material('Limestone', (.63,.57,.44))
wood = material('Oiled cedar', (.35,.125,.056))
cream = material('Ivory instrument enamel', (.84,.79,.61), .32)
glass = material('Blue objective coating', (.018,.14,.29), .75,.17)
window = material('Sea glass', (.15,.37,.39), .37,.25)
dark = material('Graphite', (.018,.027,.035), .38)

def finish(name, m):
    o = bpy.context.object
    o.name = name
    o.data.materials.append(m)
    return o

def box(name, loc, size, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = finish(name,m)
    o.dimensions = size
    return o

def cylinder(name,a,b,r,m,n=48,r2=None):
    a,b=Vector(a),Vector(b)
    bpy.ops.mesh.primitive_cone_add(vertices=n,radius1=r,radius2=r if r2 is None else r2,
        depth=(b-a).length,location=(a+b)/2)
    o=finish(name,m)
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return o

def disk(name,z,h,r,m):
    return cylinder(name,(0,0,z),(0,0,z+h),r,m,96)

def radial(name,angle,r,z,width,depth,height,m):
    a=rad(angle)
    o=box(name,(r*math.sin(a),-r*math.cos(a),z),(width,depth,height),m)
    o.rotation_euler.z=a
    return o

disk('Stepped stone footing',0,.22,4.65,stone)
disk('Shadow course',.22,.14,4.53,iron)
disk('Cedar rotunda',.36,2.48,4.39,wood)
for i in range(96):
    radial('Cedar batten',i*3.75,4.386,1.38,.048,.055,2.02,wood)
for i in range(24):
    a=i*15
    radial('Clerestory frame',a,4.36,2.48,1.14,.13,.62,iron)
    radial('Clerestory glazing',a,4.438,2.48,.97,.02,.43,window)
    radial('Bronze mullion',a,4.46,2.48,.036,.025,.46,brass)
disk('Observing deck',2.80,.16,4.54,iron)
disk('Azimuth bearing',2.96,.09,4.48,brass)
disk('Interior floor',3.05,.06,4.34,dark)

def roof_panel(name,start,end,r,m,parent=None):
    verts=[]
    faces=[]
    for j in range(15):
        lat=rad(89.92*j/14)
        for k in range(7):
            a=rad(start+(end-start)*k/6)
            verts.append((r*math.cos(lat)*math.sin(a),-r*math.cos(lat)*math.cos(a),3.1+r*math.sin(lat)))
    for j in range(14):
        for k in range(6):
            i=j*7+k
            faces.append((i,i+1,i+8,i+7))
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    o=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(o)
    o.data.materials.append(m)
    o.parent=parent
    return o

# Move each leaf around the vertical drum axis, just inside the fixed skin.
for start,end,r,parent in [(58,302,4.4,None),(-58,0,4.29,'West shutter'),(0,58,4.29,'East shutter')]:
    pivot=None
    if parent:
        pivot=bpy.data.objects.new(parent,None)
        scene.collection.objects.link(pivot)
        for frame,amount in [(1,0),(72,62 if start==0 else -62)]:
            pivot.rotation_euler.z=rad(amount)
            pivot.keyframe_insert(data_path='rotation_euler',frame=frame)
        pivot.animation_data.action.name=parent+' travel'
        track=pivot.animation_data.nla_tracks.new()
        track.name='Open_Roof'
        track.strips.new('Open_Roof',1,pivot.animation_data.action)
        pivot.animation_data.action=None
    count=12 if pivot is None else 3
    for j in range(count):
        a=start+(end-start)*j/count
        b=start+(end-start)*(j+1)/count
        roof_panel('Radial copper pan',a,b,r,patina[j%4],pivot)
        roof_panel('Raised standing seam',a,a+.75,r+.032,iron,pivot)
    for edge in (start,end):
        roof_panel('Shutter flashing',edge-.55,edge+.55,r+.047,brass,pivot)
disk('Zenith boss',7.45,.10,.30,brass)

# Twin trunnions and separate optics aligned down one optical axis.
disk('Pier foot',3.11,.20,.99,brass)
cylinder('Cast pier',(0,.18,3.31),(0,.18,4.12),.74,iron,r2=.56)
cylinder('Azimuth table',(0,.18,4.12),(0,.18,4.37),.94,brass)
center=Vector((0,.15,4.99))
axis=Vector((-.47,-.71,.525)).normalized()
for s in (-1,1):
    cylinder('Fork cheek',(s*.66,.19,4.29),(s*.87,.15,4.99),.18,iron)
    cylinder('Trunnion',(s*.68,.15,4.99),(s*1.02,.15,4.99),.28,brass)
def tube(name,lo,hi,r,m,r2=None):
    return cylinder(name,center+axis*lo,center+axis*hi,r,m,64,r2)
tube('Rear cell',-1.75,-1.43,.57,iron)
tube('Optical tube',-1.43,1.27,.59,cream,.74)
for t,r in [(-1.35,.62),(-.63,.67),(.58,.73),(1.24,.78)]:
    tube('Instrument collar',t,t+.09,r,brass)
# Lathed open dew shield and convex glass catch different parts of the sky.
def optical_surface(name, profile, mat):
    normal = axis.cross(Vector((0,0,1))).normalized()
    tangent = axis.cross(normal)
    points = []
    faces = []
    for t,r in profile:
        for i in range(64):
            angle = 2*math.pi*i/64
            points.append(center+axis*t+r*(math.cos(angle)*normal+math.sin(angle)*tangent))
    for j in range(len(profile)-1):
        for i in range(64):
            k=(i+1)%64
            faces.append((j*64+i,j*64+k,(j+1)*64+k,(j+1)*64+i))
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(points,[],faces)
    mesh.update()
    o=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(o)
    o.data.materials.append(mat)
    for face in mesh.polygons:
        face.use_smooth=True

optical_surface('Objective hood',[(1.29,.79),(1.89,.87)],iron)
optical_surface('Rolled bronze lip',[(1.84,.87),(1.90,.88),(1.92,.86),(1.92,.80),(1.88,.79)],brass)
optical_surface('Flocked hood lining',[(1.89,.798),(1.47,.706)],dark)
optical_surface('Convex blue objective',[(1.47,.708),(1.51,.61),(1.55,.46),(1.58,.27),(1.59,.001)],glass)
for t in (-.75,.56):
    p=center+axis*t
    cylinder('Finder bracket',p+Vector((.50,0,.22)),p+Vector((.70,0,.53)),.075,brass)
p=center+Vector((.70,0,.53))
cylinder('Guide scope',p-axis*1.04,p+axis*.95,.13,iron)
cylinder('Finder dewshield',p+axis*.74,p+axis*1.03,.17,brass)

# Low masonry entrance wing, stepped portal and engraved lintel.
box('Vestibule footing',(4.15,-.85,.19),(2.6,3.9,.38),stone)
box('Vestibule',(4.15,-.85,1.40),(2.45,3.78,2.08),wood)
box('Entrance fascia',(4.15,-.85,2.49),(2.70,4.04,.20),iron)
box('Copper canopy',(4.15,-.85,2.61),(2.76,4.10,.07),patina[1])
for i in range(3):
    box('Threshold step',(4.18,-3.36+i*.23,.065*(i+1)),(1.79, .47,.13*(i+1)),stone)
box('Portal trim',(4.18,-2.77,1.30),(1.51,.14,1.92),brass)
box('Enamel door',(4.18,-2.86,1.29),(1.35,.07,1.81),iron)
box('Door glazing',(4.18,-2.904,1.57),(1.07,.035,.73),window)
box('Push bar',(4.18,-2.94,1.05),(.84,.065,.055),brass)
for y in (-1.93,-.83,.27):
    box('Side casement',(5.39,y,1.52),(.06,.91,1.10),iron)
    box('Side glazing',(5.43,y,1.52),(.03,.77,.95),window)

# Consolidate static surfaces by material, preserving shutter pivots.
for parent in [None,bpy.data.objects['West shutter'],bpy.data.objects['East shutter']]:
    for mat in list(bpy.data.materials):
        group=[o for o in scene.objects if o.type=='MESH' and o.parent==parent and o.data.materials[0]==mat]
        if not group: continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in group: o.select_set(True)
        bpy.context.view_layer.objects.active=group[0]
        if len(group)>1: bpy.ops.object.join()
        group[0].name=(parent.name if parent else 'Rotunda')+' · '+mat.name

scene.frame_end=72
scene.frame_set(72)
bpy.ops.export_scene.gltf(filepath=str(root/'assets/models/observatory.glb'),export_format='GLB',export_animation_mode='NLA_TRACKS')
# Warm-neutral studio with soft evening shadows.
scene.world=bpy.data.worlds.new('Harbour sky')
scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.61,.73,.81,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.48
ground=box('Studio backdrop',(0,0,-.105),(200,200,.2),material('Slate backdrop',(.18,.245,.27)))
def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
for loc,power,size in [((-6,-9,14),2300,8),((9,-2,10),1250,7),((0,6,12),1800,6)]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    lamp=bpy.context.object
    lamp.data.energy=power
    lamp.data.shape='DISK'
    lamp.data.size=size
    aim(lamp,(0,0,3))
bpy.ops.object.camera_add(location=(7,-18,11))
cam=bpy.context.object
aim(cam,(.44,0,3.28))
cam.data.type='ORTHO'
cam.data.ortho_scale=13.5
scene.camera=cam
scene.render.engine='CYCLES'
scene.cycles.samples=12
scene.cycles.use_denoising=True
scene.render.resolution_percentage=100
scene.render.resolution_x=1000
scene.render.resolution_y=840
scene.render.filepath=str(root/'art/observatory_preview.png')
scene.timeline_markers.new('Weather sealed',frame=1)
scene.timeline_markers.new('Ready to observe',frame=72)
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'
        area.spaces.active.shading.color_type='MATERIAL'
ground.hide_set(True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/'art/observatory.blend'),compress=True)
bpy.ops.render.render(write_still=True)
