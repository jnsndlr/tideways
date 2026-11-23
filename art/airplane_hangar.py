"""Build the Tideways island air hangar with Blender in background mode."""
from pathlib import Path
from math import cos, sin, pi, radians
import sys
import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
low = '--low' in sys.argv
asset = 'airplane_hangar_low' if low else 'airplane_hangar'
segments = 12 if low else 24
def paint(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Roughness'].default_value = .7
    return m

green = paint('Patinated steel', (.073,.218,.202))
seam = paint('Folded zinc edges', (.15,.34,.30))
cream = paint('Warm ivory enamel', (.78,.747,.607))
trim = paint('Deep spruce', (.032,.082,.079))
glass = paint('Harbour blue glass', (.12,.32,.38))
cedar = paint('Oiled cedar', (.48,.239,.10))
cement = paint('Apron concrete', (.43,.45,.43))
gold = paint('Taxiway ochre', (.91,.56,.075))
red = paint('Vermilion enamel', (.62,.115,.052))

def box(name, loc, dims, mat):
    if low and name in {'Sky pane', 'Casement mullion', 'Door light'}:
        dx,dy,dz = (v/2 for v in dims)
        if name == 'Door light':
            corners = [(-dx,-dy,-dz),(dx,-dy,-dz),(dx,-dy,dz),(-dx,-dy,dz)]
        else:
            side = 1 if loc[0] > 0 else -1
            corners = [(side*dx,-side*dy,-dz),(side*dx,side*dy,-dz),
                       (side*dx,side*dy,dz),(side*dx,-side*dy,dz)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(corners, [], [(0,1,2,3)])
        mesh.update()
        o = bpy.data.objects.new(name,mesh)
        scene.collection.objects.link(o)
        o.location = loc
        mesh.materials.append(mat)
        return o
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(mat)
    return o

def spar(name,a,b,w,d,mat):
    delta = Vector(b)-Vector(a)
    o = box(name,(Vector(a)+Vector(b))/2,(w,d,delta.length),mat)
    o.rotation_euler = delta.to_track_quat('Z','Y').to_euler()

def lettering(body,loc,size,mat):
    data = bpy.data.curves.new(body,'FONT')
    if low:
        data.resolution_u = 4
    data.body = body
    data.align_x = data.align_y = 'CENTER'
    data.size = size
    data.space_character = 1.14
    o = bpy.data.objects.new(body,data)
    scene.collection.objects.link(o)
    o.rotation_euler.x = pi/2
    o.location = loc
    data.materials.append(mat)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.convert(target='MESH')

# A shallow circular vault with raised transverse seams.
def arch(t,extra=0):
    return ((17.1+extra)*sin(t), -7.45+(17.1+extra)*cos(t))

def vault(name,y1,y2,extra,thickness,mat):
    verts=[]
    faces=[]
    for i in range(segments+1):
        t=radians(-43+86*i/segments)
        for y,r in [(y1,extra),(y2,extra),(y2,extra-thickness),(y1,extra-thickness)]:
            x,z=arch(t,r)
            verts.append((x,y,z))
        if i:
            for j in range(4):
                if low and j == 2 and name == "Raised standing seam":
                    continue  # The roof covers the underside of each seam.
                a=4*(i-1)+j
                b=4*(i-1)+(j+1)%4
                faces.append((a,a+4,b+4,b))
    last = 4*segments
    faces.extend([(0,1,2,3),(last+3,last+2,last+1,last)])
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    o=bpy.data.objects.new(name,mesh)
    scene.collection.objects.link(o)
    mesh.materials.append(mat)

box('Concrete apron and bay floor',(0,-2,.09),(24,22,.18),cement)
box('Taxi lead-in',(0,-8,.19),(.12,9.8,.014),gold)
for x in [-11.25,11.25]:
    box('Enamel side wall',(x,0,2.62),(.25,15,4.89),cream)
    box('Spruce kick plate',(x,0,.62),(.33,15,.88),green)
    for y in [-6,-3,0,3,6]:
        box('Side window surround',(x*1.016,y,3.43),(.1,2.42,1.35),trim)
        box('Sky pane',(x*1.022,y,3.43),(.06,2.24,1.17),glass)
        box('Casement mullion',(x*1.026,y,3.43),(.04,.07,1.2),cream)
box('Rear wall',(0,7.38,2.62),(22.5,.24,4.9),cream)
vault('Barrel roof',-7.85,7.85,0,.16,green)
for y in range(-7,8,2):
    vault('Raised standing seam',y-.045,y+.045,.045,.065,seam)
for y in [-7.65,7.65]:
    # Fill each end with vertical strips trimmed to the arch.
    verts=[]
    faces=[]
    for i in range(segments+1):
        x,z=arch(radians(-43+86*i/segments),-.1)
        verts.extend([(x,y,4.88),(x,y,z)])
        if i:
            j=2*i
            faces.append((j-2,j,j+1,j-1) if y<0 else (j-1,j+1,j,j-2))
    mesh=bpy.data.meshes.new('Vault end')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    end=bpy.data.objects.new('Ivory arch end',mesh)
    scene.collection.objects.link(end)
    mesh.materials.append(cream)
    vault('Rolled perimeter flashing',y-.24,y+.24,.095,.24,seam)
for y in [-6,-2,2,6]:
    box('Interior truss chord',(0,y,5.14),(22.5,.16,.17),cedar)
    for i in range(6 if low else 10):
        x=-10+(3.6 if low else 2)*i
        spar('Interior truss web',(x,y,5.18),(x+1,y,(-7.45+(16.88**2-(x+1)**2)**.5)),.12,.12,cedar)
box('Sliding door rail',(0,-7.83,5.1),(23.2,.36,.37),trim)
for side in [-1,1]:
    for i in range(2):
        x=side*(7.65+i*2.50)
        y=-7.65-i*.14
        box('Sliding door leaf',(x,y,2.60),(2.52,.18,4.78),green)
        for dx in [-.79,0,.79]:
            box('Door light',(x+dx,y-.105,3.77),(.70,.045,.89),glass)
        for dx in [-1.19,1.19]:
            box('Door stile',(x+dx,y-.13,2.60),(.095,.09,4.76),seam)
        spar('Diagonal door brace',(x-1.13,y-.15,.46),(x+1.13,y-.15,3.14),.105,.075,seam)
box('Enamel signboard',(0,-7.75,6.48),(12,.18,1.3),trim)
lettering('I S L A N D   A I R',(0,-7.852,6.48),.96,cream)
for s in [-1,1]:
    for i in range(3):
        box('Wing insignia',(s*(7.05-.21*i),-7.74,6.77-.22*i),(1.64-.38*i,.075,.105),red)
for i in range(5):
    box('Crown vent louvre',(0,-7.73,7.77+.20*i),(2.18-.21*i,.14,.10),green)
lettering('03',(9.75,-7.96,2.77),.82,cream)

bpy.ops.export_scene.gltf(filepath=str(root/'assets/models'/f'{asset}.glb'),export_format='GLB')
def aim(o,target):
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
scene.world=bpy.data.worlds.new('Maritime daylight')
scene.world.color=(.54,.59,.62)
ground=box('Studio ground',(0,0,-.12),(240,240,.2),paint('Studio slate',(.17,.235,.25)))
ground.hide_set(True)
for loc,power,size in [((-14,-20,26),11000,12),((18,-12,18),6800,10),((0,14,23),9000,12)]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    o=bpy.context.object
    o.data.energy=power
    o.data.size=size
    aim(o,(0,0,3))
bpy.ops.object.camera_add(location=(22,-42,19))
cam=bpy.context.object
aim(cam,(0,-1.5,3.5))
cam.data.type='ORTHO'
cam.data.ortho_scale=38
scene.camera=cam
scene.render.engine='CYCLES'
scene.cycles.samples=8
scene.cycles.use_denoising=True
scene.render.resolution_percentage=100
scene.render.resolution_x=1080
scene.render.resolution_y=770
scene.render.filepath=f'//{asset}_preview.png'
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'
        area.spaces.active.shading.color_type='MATERIAL'
        area.spaces.active.overlay.show_overlays=False
bpy.ops.object.select_all(action='DESELECT')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/'art'/f'{asset}.blend'),compress=True)
bpy.ops.render.render(write_still=True)
