"""Rebuild the two fishing wharves with Blender -b -P art/crabbing_wharves.py."""
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rng = random.Random(36)


def paint(name, hexcolor):
    rgb = [int(hexcolor[i:i+2], 16) / 255 for i in (0, 2, 4)]
    color = tuple(((v+.055)/1.055)**2.4 if v > .04045 else v/12.92 for v in rgb) + (1,)
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    m.use_nodes = True
    shader = m.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Roughness"].default_value = .8
    return m


def palette(name, colors):
    return [paint(f"{name} {i+1}", c) for i, c in enumerate(colors.split())]


wood = palette("Weathered fir", "bd8451 b88050 ca935b ac764a d39a63")
piles = palette("Tide-marked pilings", "816043 79553c 916749")
blue = palette("Petrol blue paint", "27747b 2c7981 307c82 296f76")
red = palette("Vermilion paint", "ac4233 b74a37 c0523e b44736")
roof = palette("Cedar shakes", "615550 72615a 695b56 786861 635653 695f59")
cream, dark, glass, brass, net, iron, orange, chalk = [
    paint(n,c) for n,c in zip(("Buff trim","Shadow","Harbor glass","Pot bindings","Green wire",
    "Wrought iron","Float vermilion","Float ivory"),"efd29a 383632 305863 e9ad39 23745a 423d39 e55a31 f5e3ba".split())]


class Part:
    def __init__(self, name):
        self.name = name
        self.v, self.f, self.indices, self.mats = [], [], [], []

    def solid(self, verts, faces, mat):
        off = len(self.v)
        self.v.extend(verts)
        if mat not in self.mats:
            self.mats.append(mat)
        self.f.extend(tuple(off+i for i in face) for face in faces)
        self.indices.extend([self.mats.index(mat)] * len(faces))

    def finish(self, collection):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.v, [], self.f)
        mesh.update()
        for m in self.mats:
            mesh.materials.append(m)
        mesh.polygons.foreach_set("material_index", self.indices)
        obj = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(obj)


def rod(a, b, r, mat, sides=8, end=None):
    a,b = Vector(a),Vector(b)
    axis = (b-a).normalized()
    u = axis.cross(Vector((1,0,0)) if abs(axis.x)<.85 else Vector((0,1,0))).normalized()
    v = axis.cross(u)
    ring = [u*math.cos(i*math.tau/sides)+v*math.sin(i*math.tau/sides) for i in range(sides)]
    part.solid([p+d*s for p,s in ((a,r),(b,end if end is not None else r)) for d in ring],
               [tuple(reversed(range(sides))),tuple(range(sides,2*sides))]+
               [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)],mat)


def board(pos, size, mat, pitch=0):
    x,y,z=pos
    w,d,h=[i/2 for i in size]
    c,s=math.cos(pitch),math.sin(pitch)
    verts=[(x+i*c+k*s,y+j,z-i*s+k*c) for k in (-h,h) for j in (-d,d) for i in (-w,w)]
    part.solid(verts,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],mat)


def window(x,y,z,w,h,side=False):
    def trim(dx,dy,dz,a,b,c,mat):
        board((x+dy if side else x+dx,y+dx if side else y+dy,z+dz),
              (b,a,c) if side else (a,b,c),mat)
    trim(0,0,0,w,.1,h,glass)
    for i in (-1,1):
        trim(i*w/2,-.06,0,.075,.11,h+.1,cream)
        trim(0,-.075,i*h/2,w+.19,.15,.08,cream)
    trim(0,-.057,.08,w,.065,.046,cream)
    trim(0,-.057,0,.046,.065,h,cream)


def crabpot(x,y,z):
    # Sloping shoulders, yellow lashings and a circular inward-tapered entrance.
    profile=[(-.47,0),(.47,0),(.47,.34),(.37,.58),(-.37,.58),(-.47,.34)]
    def point(i,depth):
        a,b=profile[i]
        return Vector((x+a,y+depth,z+b+.025))
    for i in range(6):
        j=(i+1)%6
        rod(point(i,-.34),point(i,.34),.023,brass)
        for k in range(11):
            dep=-.34+.068*k
            rod(point(i,dep),point(j,dep),.022 if k in (0,10) else .009,
                brass if k in (0,10) else net,6)
        for k in range(1,math.ceil((point(i,0)-point(j,0)).length/.075)):
            t=k/math.ceil((point(i,0)-point(j,0)).length/.075)
            rod(point(i,-.34).lerp(point(j,-.34),t),point(i,.34).lerp(point(j,.34),t),.009,net,6)
    for dep in (-.34,.34):
        last=[]
        for i in range(32):
            ang=i*math.tau/32
            dx,dz=math.cos(ang),math.sin(ang)
            reach=min(.46/max(abs(dx),.001),.285/max(abs(dz),.001))
            if dz>0:
                reach=min(reach,.50/(abs(dx)+.42*dz))
            rings=[(x+dx*r,y+depth,z+.31+dz*r) for r,depth in
                   ((reach,dep),(.15,dep),(.10,dep*.45))]
            for a,b in zip(rings,rings[1:]):
                rod(a,b,.008,net,5)
            last.append(rings)
        for i in range(32):
            for level in (1,2):
                rod(last[i][level],last[i-1][level],.013,brass if level==1 else net,6)


def crate(x,y,z):
    board((x,y,z+.21),(.82,.59,.42),wood[1])
    for i in (-1,1):
        board((x+i*.33,y,z+.21),(.09,.63,.44),wood[3])
    board((x,y-.301,z+.32),(.19,.014,.05),dark)


def build(big):
    global part
    name = "crab_wharf_warehouse" if big else "crab_wharf_shack"
    coll=bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    def start(label):
        return Part(label)
    part=start("Pier • decking, stringers and rail")
    w,d=(11,10.6) if big else (7.4,8.35)
    f=-3.7 if big else -3.0
    pier_mid=f+d/2
    n=round(w/.25)
    for i in range(n):
        board((-w/2+(i+.5)*w/n,pier_mid,-.105),(w/n-.012,d,.21),rng.choice(wood))
    for row in range(4):
        y=f+.12+row*(d-.24)/3
        board((0,y,-.31),(w+.08,.22,.34),wood[3])
        for i in range(7 if big else 5):
            count=6 if big else 4
            x=(i/count-.5)*(w-.34)
            board((x,y,-.85),(.31,.31,1.64),rng.choice(piles))
            if row in (0,3):
                board((x,y,.25),(.17,.17,.58),wood[2])
                rod((x,y-.14,-.30),(x,y-.16,-.30),.046,iron)
    for y in (f+.12,f+d-.12):
        board((0,y,.36),(w-.28,.085,.10),wood[3])
    for x in (-w/2+.17,w/2-.17):
        board((x,pier_mid,.36),(.085,d-.24,.10),wood[3])
        board((x,pier_mid,.23),(.17,.17,.55),wood[2])
    part.finish(coll)
    part=start("Boathouse • siding and joinery")
    width,depth,eave,rise=(6.8,7.65,2.95,1.37) if big else (4.4,6.0,2.75,1.17)
    cx=-.74 if big else .2
    front=-1.365 if big else -.965
    back=front+depth
    color=blue if big else red
    slope=rise/(width/2)
    for y in (front,back):
        count=round(width/.24)
        for i in range(count):
            dx=((i+.5)/count-.5)*width
            h=eave+rise-abs(dx)*slope
            board((cx+dx,y,h/2),(width/count-.007,.13,h),rng.choice(color))
    for x in (cx-width/2,cx+width/2):
        side_boards=round(depth/.23)
        for i in range(side_boards):
            board((x,front+(i+.5)*depth/side_boards,eave/2),(.13,depth/side_boards-.009,eave),rng.choice(color))
        for y in (front,back):
            board((x,y,eave/2),(.17,.18,eave),cream)
        for i in (1,3,5):
            window(x+(-.08 if x<cx else .08),front+depth*i/6,1.55,.48,.72, x<cx) if x<cx else None
    y=front-.12
    door=cx if big else cx-.93
    dw=2.48 if big else .98
    dh=2.32 if big else 2.1
    board((door,y,dh/2),(dw,.13,dh),dark)
    for i in range(10):
        board((door+((i+.5)/10-.5)*dw,y-.08,dh/2),(dw/10-.011,.08,dh-.04),blue[i%4])
    for sign in (-1,1):
        board((door+sign*dw/2,y-.14,dh/2),(.10,.14,dh),cream)
    board((door,y-.15,dh+.07),(dw+.36,.19,.15),cream)
    if big:
        angle=math.atan2(dh-.12,dw-.16)
        for sign in (-1,1):
            board((door,y-.14,dh/2),(math.hypot(dh-.12,dw-.16),.08,.115),wood[2],sign*angle)
        board((door,y-.19,dh/2),(.065,.08,dh),cream)
        for dx in (-2.40,2.40):
            window(cx+dx,y,1.52,.66,.79)
    else:
        for dx in (-.21,.21):
            board((door+dx,y-.14,1.58),(.33,.05,.65),glass)
        rod((door+.32,y-.17,1),(door+.32,y-.23,1),.05,brass)
        for dx,ww in ((.50,.84),(1.64,.53)):
            window(cx+dx,y,1.57,ww,.85)
    window(cx,y,eave+rise*.47,.44,.51)
    part.finish(coll)
    part=start("Roof • staggered split shakes and ridge cap")
    span=width/2+.26
    for sign in (-1,1):
        angle=sign*math.atan(slope)
        for row in range(7):
            t=(row+.5)/7*span
            z=eave+rise-slope*t+(7-row)*.013+.04
            lo,hi=front-.29,back+.29
            a=lo
            while a<hi-.001:
                b=min(hi,a+(.24 if row%2 and a==lo else rng.uniform(.42,.64)))
                board((cx+sign*t,(a+b)/2,z), (span/7/math.cos(angle)+.08,b-a-.009,.085),rng.choice(roof),angle)
                a=b
        for yy in (front-.30,back+.30):
            board((cx+sign*span/2,yy,eave+rise-slope*span/2), (span/math.cos(angle),.14,.15),cream,angle)
    rod((cx,front-.35,eave+rise+.13),(cx,back+.35,eave+rise+.13),.089,wood[2])
    part.finish(coll)
    part=start("Working gear • pots and fish boxes")
    x,y=(-4.67,-2.77) if big else (-2.65,-1.85)
    for dx,dy,dz in ((0,0,0),(.99,0,0),(.04,0,.62),(.70,.74,0)):
        crabpot(x+dx,y+dy,dz)
    for x,y in ([(3.58,-.87),(4.52,-.66),(3.75,.06),(-4.85,front+depth/3)] if big else [(2.85,.2)]):
        for k in range(2 if x < 0 or not big else 3):
            crate(x+.025*k,y,k*.44)
    part.finish(coll)
    if big:
        part=start("Cargo derrick • sheave, hook and marker floats")
        x,y=2.12,-2.56
        board((x,y,1.95),(.27,.28,3.9),wood[2])
        board((x+.83,y,3.84),(2.07,.29,.26),wood[2])
        board((x+.48,y,3.19),(1.62,.21,.18),wood[1],-.86)
        tip=x+1.67
        rod((tip,y-.12,3.68),(tip,y+.12,3.68),.127,iron)
        rod((tip,y,3.67),(tip,y,2.50),.026,dark)
        chain=[(0,2.53),(-.065,2.45),(-.06,2.36),(.025,2.31),(.107,2.37),(.11,2.42)]
        for (a,b),(c,dz) in zip(chain,chain[1:]):
            rod((tip+a,y,b),(tip+c,y,dz),.028,iron)
        for i in range(4):
            xx=-1.65+i*.54
            yy=f-.14
            rod((xx,f+.12,.39),(xx,yy,.03),.018,dark)
            for za,zb,r1,r2,mat in ((.05,-.11,.045,.12,chalk),(-.11,-.23,.12,.13,orange),(-.23,-.34,.13,.115,chalk),(-.34,-.53,.115,.037,orange)):
                rod((xx,yy,za),(xx,yy,zb),r1,mat,12,r2)
        part.finish(coll)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in coll.objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets/models"/(name+".glb")),use_selection=True)
    return coll


large,small=build(True),build(False)
for coll,offset in ((large,(-4.8,2,0)),(small,(5.65,-2.5,0))):
    for obj in coll.objects:
        obj.location=offset

def aim(obj, point):
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat("-Z","Y").to_euler()

bpy.ops.object.camera_add(location=(-12,-30,12))
cam=bpy.context.object
aim(cam,(-.5,.7,1.2))
cam.data.type="ORTHO"
cam.data.ortho_scale=26.5
scene.camera=cam
# Neutral studio setting for the reference view.
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-1.68))
bpy.context.object.name="Studio floor"
bpy.context.object.data.materials.append(paint("Backdrop","e9e2d4"))
bpy.ops.object.light_add(type="AREA",location=(-7,-10,16))
bpy.context.object.data.energy=4200
bpy.context.object.data.shape="DISK"
bpy.context.object.data.size=9
aim(bpy.context.object,(0,0,0))
scene.world=bpy.data.worlds.new("Overcast harbor")
scene.world.use_nodes=True
scene.world.node_tree.nodes["Background"].inputs[0].default_value=(.8,.87,1,1)
scene.world.node_tree.nodes["Background"].inputs[1].default_value=.65
scene.render.engine="CYCLES"
scene.cycles.samples=12
scene.cycles.use_denoising=True
scene.render.resolution_x,scene.render.resolution_y=1500,660
scene.render.resolution_percentage=100
for area in bpy.context.screen.areas:
    if area.type=="VIEW_3D":
        area.spaces.active.region_3d.view_perspective="CAMERA"
        area.spaces.active.shading.color_type="MATERIAL"
bpy.ops.object.select_all(action="DESELECT")
scene.render.filepath="//crabbing_wharves_preview.png"
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art/crabbing_wharves.blend"))
bpy.ops.render.render(write_still=True)
