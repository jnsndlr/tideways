"""Build the navy harbor tug. Run with Blender -b -P art/navy_tug_mid.py."""
from pathlib import Path
import math
import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
def paint(name, rgb, metallic=0, rough=.58):
    m = bpy.data.materials.new(name)
    values = [((int(rgb[i:i+2],16)/255+.055)/1.055)**2.4 for i in (0,2,4)]
    m.diffuse_color = (*values,1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*values,1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = rough
    return m
hull=paint("Graphite hull","272c33")
red=paint("Oxide waterline","763f34")
deck=paint("Nonskid deck","777d7e")
steel=paint("Machinery enamel","404a50")
gray=paint("Haze gray","abb3b5")
white=paint("Bridge ivory","eeeae1")
rubber=paint("Ivory rubbing rubber","d3cfc2")
glass=paint("Petrol blue glazing","244451",.45,.2)
metal=paint("Brushed exhaust steel","97918a",.7)
orange=paint("Rescue orange","ef641f")
brass=paint("Propeller brass","b69556",.4)
rope=paint("Tow wire","7b7465")
signal=paint("Signal red","b63e35")
def mesh(name,verts,faces,m):
    d=bpy.data.meshes.new(name)
    d.from_pydata(verts,[],faces)
    d.update()
    o=bpy.data.objects.new(name,d)
    sc.collection.objects.link(o)
    d.materials.append(m)
    return o
def box(name,loc,size,m):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object
    o.name=name
    o.dimensions=size
    o.data.materials.append(m)
    return o
def tube(name,a,b,r,m,n=6,r2=None):
    a,b=Vector(a),Vector(b)
    axis=(b-a).normalized()
    u=axis.cross(Vector((0,0,1)) if abs(axis.z)<.95 else Vector((0,1,0))).normalized()
    v=axis.cross(u)
    rings=[[p+radius*(u*math.cos(i*math.tau/n)+v*math.sin(i*math.tau/n)) for i in range(n)] for p,radius in [(a,r),(b,r if r2 is None else r2)]]
    return loft(name,rings,m)
def loft(name,rings,m):
    n=len(rings[0])
    faces=[tuple(reversed(range(n)))]
    for j in range(len(rings)-1):
        for i in range(n):
            k=j*n+i
            q=j*n+(i+1)%n
            faces.append((k,q,q+n,k+n))
    faces.append(tuple(range((len(rings)-1)*n,len(rings)*n)))
    return mesh(name,[p for ring in rings for p in ring],faces,m)
def rail(name,path,m=white,r=.032):
    for a,b in zip(path,path[1:]):
        tube(name,a,b,r,m)
def outline(scale,height):
    pts=[]
    for i in range(64):
        a=i*math.tau/64
        c,s=math.cos(a),math.sin(a)
        x=13.4*math.copysign(abs(c)**.72,c)
        y=4.65*math.copysign(abs(s)**.72,s)*(1-.12*max(x/13.4,0)**2)
        pts.append(Vector((scale*x,scale*y,height+.40*(abs(x)/13.4)**3)))
    return pts
loft("Antifouling and keel",[outline(.65,-2),outline(.89,-.58),outline(.95,.04)],red)
loft("Welded shell",[outline(.95,.04),outline(1,.83),outline(1.005,1.65)],hull)
loft("Weather deck",[outline(.995,1.63),outline(.995,1.69)],deck)
rim=outline(1,1.66)
for i,a in enumerate(rim):
    b=rim[(i+1)%64]
    def wall(p):
        x=abs(p.x)
        return .38+.49*min(1,max(0,(x-8.2)/1.3)) if 6.1<x<8.6 else .87
    topa=a+Vector((0,0,wall(a)))
    topb=b+Vector((0,0,wall(b)))
    mesh("Bulwark plate",[a,b,topb,topa],[(0,1,2,3)],hull)
    tube("Round gunwale",topa,topb,.055,steel)
    if i%3==0:
        tube("Bulwark knee",a*.995,topa*.994,.052,steel)
def swept(name,path,r,mat,sides=8,closed=False):
    rings=[]
    for j,p in enumerate(path):
        prev=path[j-1] if closed or j else p
        nxt=path[(j+1)%len(path)] if closed or j+1<len(path) else p
        tangent=(nxt-prev).normalized()
        u=tangent.cross(Vector((0,0,1))).normalized()
        v=tangent.cross(u)
        rings.append([p+r*(u*math.cos(k*math.tau/sides)+v*math.sin(k*math.tau/sides)) for k in range(sides)])
    faces=[]
    for j in range(len(path) if closed else len(path)-1):
        for k in range(sides):
            n=(j+1)%len(path)
            h=(k+1)%sides
            faces.append((j*sides+k,j*sides+h,n*sides+h,n*sides+k))
    if not closed:
        faces.extend([tuple(reversed(range(sides))),tuple(range((len(path)-1)*sides,len(path)*sides))])
    ob=mesh(name,[v for ring in rings for v in ring],faces,mat)
    for f in ob.data.polygons: f.use_smooth=len(f.vertices)==4
for z,r,extent in [(1.49,.16,0),(1.94,.27,8.0),(2.43,.25,8.7)]:
    path=outline(1.022,z)
    section=[p for p in path if not extent or p.x < -extent]
    swept("Continuous ivory fender",section,r,rubber,8,not extent)
    for i in range(2,len(section)-1,8):
        tube("Rubber binding",section[i],section[i].lerp(section[i+1],.12),r+.009,gray,8)
def chamfer(x,y,z,c,cx=0):
    return [Vector((cx+a,b,z)) for a,b in [(x,-y+c),(x,y-c),(x-c,y),(-x+c,y),(-x,y-c),(-x,-y+c),(-x+c,-y),(x-c,-y)]]
loft("Engine casing",[chamfer(5.35,2.87,1.71,.68),chamfer(5.35,2.87,3.89,.68),chamfer(4.57,2.43,4.84,.60)],gray)
loft("Bridge coaming",[chamfer(2.12,1.86,4.77,.63,-.22),chamfer(2.22,2.05,5.78,.73,-.22)],white)
bottom=chamfer(2.22,2.05,5.73,.73,-.22)
top=chamfer(2.73,2.57,7.52,1.06,-.22)
loft("Outward raked pilothouse",[bottom,top],white)
def pane(a,b,c,d,l,r,low,high,m,name):
    normal=(b-a).cross(d-a).normalized()*.015
    def pos(u,v):return a.lerp(b,u).lerp(d.lerp(c,u),v)+normal
    mesh(name,[pos(l,low),pos(r,low),pos(r,high),pos(l,high)],[(0,1,2,3)],m)
roof=chamfer(2.89,2.72,7.63,1.1,-.22)
crown=chamfer(2.12,1.95,8.17,.75,-.22)
loft("Eyebrow and clerestory",[top,roof,crown],white)
for i in range(8):
    j=(i+1)%8
    count=3 if i in (2,6) else 2 if i in (0,4) else 1
    for k in range(count):
        if i in (2,6) and k==1:
            pane(bottom[i],bottom[j],top[j],top[i],.395,.605,.43,.9,glass,"Door light")
            continue
        pane(bottom[i],bottom[j],top[j],top[i],(k+.06)/count,(k+.94)/count,.075,.935,glass,"Bridge window")
    pane(roof[i],roof[j],crown[j],crown[i],.09,.91,.12,.85,glass,"Upper light")
def railing(path):
    for p in path: tube("Stanchion",p,p+Vector((0,0,.72)),.034,white)
    for h in (.36,.72):rail("Guard rail",[p+Vector((0,0,h)) for p in path])
railing(crown+[crown[0]])
def label(body,loc,size,m,side):
    d=bpy.data.curves.new(body,'FONT')
    d.body=body
    d.align_x='CENTER'
    d.align_y='CENTER'
    d.size=size
    o=bpy.data.objects.new(body,d)
    sc.collection.objects.link(o)
    o.location=loc
    o.rotation_euler=(math.pi/2,0,0 if side<0 else math.pi)
    d.materials.append(m)
    bpy.context.view_layer.objects.active=o
    o.select_set(True)
    bpy.ops.object.convert(target='MESH')
    o.select_set(False)
for s in (-1,1):
    for x in (-3.7,-2.15,-.6,.95,2.5):
        tube("Port rim",(x,s*2.85,3.37),(x,s*2.93,3.37),.266,white,16)
        tube("Port glass",(x,s*2.92,3.37),(x,s*2.95,3.37),.218,glass,16)
    label("YT-805",(-2,s*4.66,2.12),.56,white,s)
    box("Bridge wing",(1.8,s*2.43,5.82),(3.35,1.04,.14),gray)
    railing([Vector((x,s*2.92,5.88)) for x in (.15,1.26,2.38,3.45)])
    # Two levels of access: forecastle to boat deck, then up to the bridge wing.
    for start,end,y in [((-6.98,1.82),(-4.48,4.82),2.05),((-2.02,4.82),(.22,5.82),2.59)]:
        x0,z0=start
        x1,z1=end
        steps=12 if z1-z0>2 else 5
        for k in range(steps):
            t=(k+.5)/steps
            box("Grated stair",(x0+(x1-x0)*t,s*y,z0+(z1-z0)*t),((x1-x0)/steps+.05,.62,.07),gray)
        for edge in (y-.31,y+.31):
            for dz,r,mat in [(0,.06,steel),(.79,.033,white),(.42,.024,white)]:
                rail("Stair rail",[(x0,s*edge,z0+dz),(x1,s*edge,z1+dz)],mat,r)
            for t in (0,.5,1):
                x=x0+(x1-x0)*t
                z=z0+(z1-z0)*t
                tube("Newel",(x,s*edge,z),(x,s*edge,z+.79),.03,white)
    box("Forecastle landing",(-3.49,s*2.06,4.81),(2.17,1.19,.12),gray)
    railing([Vector((x,s*2.62,4.87)) for x in (-4.55,-3.4,-2.44)])
    # Angular uptake enclosure rises from the lower house to the bridge wing.
    profile=[(-.65,3.88),(4.57,3.88),(3.83,5.77),(.63,5.77)]
    loft("Sloped funnel casing",[[Vector((x,s*y,z)) for x,z in profile] for y in (1.25,2.84)],gray)
    for x,z,width,height in [(3.82,2.83,.79,2.03),(-2.23,3.19,.56,1.18)]:
        box("Watertight door frame",(x,s*2.895,z),(width+.12,.08,height+.09),steel)
        box("Inset steel door",(x,s*2.95,z),(width,.05,height),gray)
        box("Door dog",(x+.17,s*3.0,z),(.18,.06,.04),steel)
    box("Fire locker",(.98,s*3.0,2.48),(.61,.28,.74),signal)
    pipe=[(-5.39,s*2.18,2.09),(-5.39,s*2.18,3.87),(-4.53,s*2.18,4.82),(-4.53,s*2.18,5.57)]
    rail("Fire main",pipe,signal,.092)
    rail("Fire monitor",[pipe[-1],(-4.53,s*2.18,5.76),(-4.91,s*2.18,5.89)],signal,.081)
    for x in (-4.3,-3.25,-2.2,-1.15,-.1):
        y=abs(outline(1,0)[16].y)*(1-(abs(x)/13.4)**(2/.72))**(.72/2)
        box("Freeing port",(x,s*(y+.014),1.87),(.76,.035,.17),steel)
    for x,r,h in [(3.72,.225,8.36),(4.39,.11,6.83)]:
        y=s*1.51
        tube("Exhaust flange",(x,y,4.83),(x,y,5),r*1.45,steel)
        tube("Exhaust trunk",(x,y,4.96),(x+.05,y,5.83),r,metal,12)
        end=Vector((x+.67,y,h))
        start=Vector((x+.05,y,5.83))
        tube("Swept uptake",start,end,r,metal,12,r*.82)
        tube("Blackened mouth",end,end+(end-start).normalized()*.015,r*.7,hull,12)
    box("Vent housing",(3.5,s*2.86,4.83),(1.27,.09,.91),steel)
    for k in range(7):box("Vent louver",(3.5,s*2.93,4.44+k*.12),(1.2,.1,.048),gray)
    def ring(x,y,z,r):
        pts=[Vector((x+r*math.cos(k*math.tau/24),y,z+r*math.sin(k*math.tau/24))) for k in range(24)]
        for k,p in enumerate(pts):tube("Lifebuoy",p,pts[(k+1)%24],.102,white if k%6==0 else orange)
    ring(-1.99,s*2.99,2.97,.33)
    ring(.83,s*3.0,6.30,.30)
    tube("Liferaft canister",(-4.1,s*1.57,5.19),(-2.63,s*1.57,5.19),.34,white,12)
    for x in (-3.95,-2.8):
        tube("Canister straps",(x,s*1.57,5.19),(x+.065,s*1.57,5.19),.351,gray,12)
    for x in (-8.0,8.25):
        for dx in (-.31,.31):
            tube("Mooring bitt",(x+dx,s*2.79,1.78),(x+dx,s*2.79,2.7),.14,steel)
        tube("Bitt horns",(x-.65,s*2.79,2.53),(x+.65,s*2.79,2.53),.105,steel)
# Tow drum and wire turns on the open working deck.
box("Winch foundation",(-7.7,0,1.87),(2.18,3.36,.22),steel)
for y in (-1.4,1.4):
    box("Bearing stool",(-7.7,y,2.28),(1.23,.29,.82),steel)
    tube("Winch cheek",(-7.7,y-.08,2.69),(-7.7,y+.08,2.69),.91,hull,24)
tube("Tow reel",(-7.7,-1.34,2.69),(-7.7,1.34,2.69),.63,rope,24)
for k in range(17):
    y=-1.24+k*.15
    tube("Wound hawser",(-7.7,y,2.69),(-7.7,y+.081,2.69),.666,rope,20)
for x in (7.1,9.1):
    tube("Deck capstan",(x,0,1.8),(x,0,2.55),.33,steel,16)
    tube("Capstan head",(x,0,2.55),(x,0,2.68),.43,gray,16)
tube("Signal mast",(-.32,0,8.16),(.12,0,14.04),.19,hull,12,.077)
for z,w in [(9.13,1.86),(10.83,1.52),(12.63,1.23),(13.72,.97)]:
    x=-.32+.44*(z-8.16)/5.88
    tube("Signal yard",(x,-w/2,z),(x,w/2,z),.064,hull)
    for y in (-w/2,w/2):
        tube("Yard brace",(x,0,z-.36),(x,y,z),.034,hull)
        tube("Navigation lantern",(x,y,z+.04),(x,y,z+.19),.068,rubber)
for x,y,h in [(-1.67,-1.15,2.12),(1.02,1.34,1.93)]:
    tube("Radio whip",(x,y,8.16),(x+.14,y,8.16+h),.035,white,6,.012)
box("Radar pedestal",(-1.46,0,8.54),(.34,.32,.74),gray)
box("Radar scanner",(-1.46,0,8.99),(.21,2.21,.17),white)
# Two stern azimuth drives. Each nozzle is an open annulus with a shared lip.
drive_parts=[]
for side in (-1,1):
    x,y,z=8.77,side*1.96,-2.52
    def drive_ring(dx,r,n):
        return [(x+dx,y+r*math.cos(k*math.tau/n),z+r*math.sin(k*math.tau/n)) for k in range(n)]
    n=12
    rings=[drive_ring(dx,r,n) for dx,r in [(.84,.95),(.16,.96),(.16,.78),(.84,.84)]]
    faces=[(i*n+k,((i+1)%4)*n+k,((i+1)%4)*n+(k+1)%n,i*n+(k+1)%n) for i in range(4) for k in range(n)]
    nozzle=mesh("Kort nozzle",sum(rings,[]),faces,red)
    for face in nozzle.data.polygons:face.use_smooth=face.index//n in (0,2)
    drive_parts.append(nozzle)
    drive_parts.append(tube("Steering leg",(x,y,z),(x,y,-.89),.30,red,8,.41))
    drive_parts.append(loft("Gearcase and spinner",[drive_ring(dx,r,8) for dx,r in [(-.77,.08),(-.41,.29),(.42,.24),(.72,.08)]],red))
    for blade in range(4):
        angle=blade*math.pi/2
        verts=[]
        for dx,r,skew in [(.41,.18,-.35),(.56,.18,.35),(.52,.66,.64),(.40,.765,.49),(.30,.64,.17)]:
            verts.append((x+dx,y+r*math.cos(angle+skew),z+r*math.sin(angle+skew)))
        drive_parts.append(mesh("Swept bronze blade",verts,[(0,1,2),(0,2,4),(4,2,3)],brass))
print("Twin drive triangles:",sum(sum(len(f.vertices)-2 for f in o.data.polygons) for o in drive_parts))
# Consolidate by material for export while retaining separate editable components.
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active=next(o for o in sc.objects if o.name.startswith("Antifouling"))
bpy.ops.object.join()
boat=bpy.context.object
boat.name="Navy tug YT-805"
boat.rotation_euler.z=math.pi/2
bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
bpy.ops.export_scene.gltf(filepath=str(root/"assets/models/navy_tug_mid.glb"),use_selection=True)
# Camera axes follow the same rotation as the exported vessel.
def world(x,y,z):return Vector((-y,x,z))
target=world(0,0,5.25)
camera=bpy.data.cameras.new("Portrait")
cam=bpy.data.objects.new("Portrait",camera)
sc.collection.objects.link(cam)
cam.location=world(-14,-46,14)
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camera.type='ORTHO'
camera.ortho_scale=32.2
sc.camera=cam
sc.render.engine='CYCLES'
sc.cycles.samples=12
sc.cycles.use_denoising=True
sc.world=bpy.data.worlds.new("Studio sky")
sc.world.use_nodes=True
bg=sc.world.node_tree.nodes.get('Background')
bg.inputs[0].default_value=(.48,.61,.70,1)
bg.inputs[1].default_value=.7
for pos,power,size in [((-12,-16,24),12500,14),((10,8,18),8800,10)]:
    light=bpy.data.lights.new("Softbox",'AREA')
    light.energy=power
    light.shape='DISK'
    light.size=size
    ob=bpy.data.objects.new("Softbox",light)
    sc.collection.objects.link(ob)
    ob.location=world(*pos)
    ob.rotation_euler=(target-ob.location).to_track_quat('-Z','Y').to_euler()
sc.render.resolution_x,sc.render.resolution_y=1250,780
sc.render.resolution_percentage=100
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'
        area.spaces.active.shading.color_type='MATERIAL'
sc.render.filepath="//navy_tug_mid_preview.png"
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(root/"art/navy_tug_mid.blend"))
bpy.ops.render.render(write_still=True)

# A stern-quarter inspection view shows the blade sweep through both nozzles.
target=world(8.5,0,-1.8)
cam.location=world(29,-9,-7.2)
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camera.ortho_scale=12.8
sc.render.filepath="//navy_tug_mid_drives.png"
bpy.ops.render.render(write_still=True)
