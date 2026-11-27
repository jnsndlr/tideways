"""Build the Tideways farm collection, individual GLBs and a farmyard portrait.

Run with Blender in background mode and --python art/farm_kit.py.
Dimensions are metres. Blender -Y is the front of each building and tractor.
"""
from math import atan2, cos, pi, sin, tau
from pathlib import Path
from random import Random

import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/farm_kit"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rng = Random(813)
palette = {
    "barn": "AF4437", "batten": "C75B45", "cream": "F6E5C1", "roof": "3B5056",
    "seam": "556969", "cedar": "A87048", "wood": "805138", "shade": "423E34",
    "glass": "608995", "sage": "839B83", "yellow": "D6AE67", "metal": "ABB8AD",
    "rim": "728986", "tire": "303639", "tread": "414847", "tractor": "43816F",
    "gold": "E9BB60", "soil": "77503A", "earth": "95684A", "leaf": "577144",
    "sprout": "8BA154", "straw": "D6A651", "wheat": "F1CD77", "turf": "9CA679",
    "lane": "B7A386", "brick": "935A47",
}
materials = {}
for name, hex_value in palette.items():
    color = [int(hex_value[i:i+2], 16) / 255 for i in (0, 2, 4)]
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*[((c+.055)/1.055)**2.4 for c in color], 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = .82
    materials[name] = mat

# Batch disconnected pieces into a single material-indexed mesh per prop.
verts, faces, colors = [], [], []
def add(points, polygons, color):
    start = len(verts)
    verts.extend(points)
    faces.extend(tuple(start+i for i in face) for face in polygons)
    colors.extend([color] * len(polygons))


def box(center, size, color, rotation=(0, 0, 0)):
    matrix = Euler(rotation).to_matrix()
    points = [Vector(center) + matrix @ Vector((x*size[0]/2, y*size[1]/2, z*size[2]/2))
              for z in (-1, 1) for x, y in ((-1,-1),(1,-1),(1,1),(-1,1))]
    add(points, [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)], color)


def cylinder(center, r1, r2, height, color, sides=16, axle=False):
    points = []
    for z, radius in ((-height/2, r1), (height/2, r2)):
        for i in range(sides):
            x, y = radius*cos(i*tau/sides), radius*sin(i*tau/sides)
            points.append(Vector(center) + Vector((z,y,-x) if axle else (x,y,z)))
    add(points, [tuple(reversed(range(sides))), tuple(range(sides,2*sides))] +
        [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)], color)


def finish(name, origin=(0,0,0)):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    slots = list(dict.fromkeys(colors))
    for color in slots:
        mesh.materials.append(materials[color])
    mesh.polygons.foreach_set('material_index', [slots.index(c) for c in colors])
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.location = origin
    verts.clear()
    faces.clear()
    colors.clear()
    return obj


def shell(w, d, h, pitch, siding, gambrel=False):
    profile = [(-w/2,h), (0,h+pitch), (w/2,h)]
    if gambrel:
        profile = [(-w/2,h),(-w*.33,h+pitch*.73),(0,h+pitch),
                   (w*.33,h+pitch*.73),(w/2,h)]
    outline = [(-w/2,0)] + profile + [(w/2,0)]
    n = len(outline)
    add([(x,y,z) for y in (-d/2,d/2) for x,z in outline],
        [tuple(reversed(range(n))),tuple(range(n,2*n))] +
        [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)], siding)
    for (x,z),(xx,zz) in zip(profile,profile[1:]):
        angle = -atan2(zz-z, xx-x)
        span = ((xx-x)**2+(zz-z)**2)**.5
        for y, depth, thick, col in ((0,d+.55,.16,"roof"),(-d/2-.28,.1,.21,"cream"),
                                      (d/2+.28,.1,.21,"cream")):
            box(((x+xx)/2,y,(z+zz)/2+.06),(span+.18,depth,thick),col,(0,angle,0))
        for i in range(round(span/.6)):
            t = (i+.5)/round(span/.6)
            box((x+(xx-x)*t,0,z+(zz-z)*t+.16),(.045,d+.56,.055),"seam",(0,angle,0))
    for x in (-w/2,w/2):
        for y in (-d/2,d/2):
            box((x,y,h/2),(.15,.16,h),"cream")


def window(x,y,z,w=1,h=1):
    box((x,y,z),(w+.18,.14,h+.18),"cream")
    box((x,y-.09,z),(w,.08,h),"glass")
    box((x,y-.14,z),(.07,.04,h),"cream")
    box((x,y-.14,z),(w,.04,.07),"cream")


def door(x,y,w,h,braced=False):
    box((x,y,h/2),(w+.22,.15,h+.18),"cream")
    box((x,y-.10,h/2),(w,.12,h),"wood" if braced else "roof")
    if braced:
        for flip in (-1,1):
            box((x,y-.19,h/2),(.12,.09,(w*w+h*h)**.5),"cream",(0,flip*atan2(w,h),0))


def barn():
    shell(8,11,4,3.7,"barn",True)
    for i in range(21):
        x = (i-10)*.37
        box((x,-5.53,2),(.055,.08,4),"batten")
    for i in range(28):
        for x in (-4,4):
            box((x,i*.39-5.25,2),(.09,.06,4),"batten")
    for x in (-1.08,1.08):
        door(x,-5.64,2.08,3.2,True)
    window(0,-5.56,5.2,1.4,1.15)
    box((0,.8,7.9),(1.3,1.3,1.15),"cream")
    for z in (7.75,7.98,8.21):
        box((0,.8,z),(1.34,1.34,.11),"shade")
    cylinder((0,.8,8.76),1.16,.07,.66,"roof",4)


def house(tall):
    h = 4.7 if tall else 2.95
    shell(5.4,6.2,h,1.9,"sage" if tall else "yellow")
    for i in range(1,int(h/.34)):
        box((0,-3.12,i*.34),(5.32,.06,.035),"cream")
    door(0,-3.24,1,2.1)
    for x in (-1.72,1.72):
        window(x,-3.21,1.7)
        if tall:
            window(x,-3.21,3.73)
    for y in (-1.8,.1,1.9):
        for x in (-2.72,2.72):
            box((x,y,1.65),(.14,1.11,1.28),"cream")
            box((x*1.032,y,1.65),(.06,.91,1.08),"glass")
    box((0,-3.83,.14),(5,1.55,.28),"cedar")
    box((0,-3.95,2.56),(5.2,1.85,.15),"roof",(.14,0,0))
    for x in (-2.32,2.32):
        box((x,-4.49,1.26),(.15,.15,2.5),"cream")
    box((1.35,1.8,h+1.25),(.68,.75,2.05),"brick")
    box((1.35,1.8,h+2.3),(.82,.88,.2),"brick")


def stable():
    shell(10,4.8,2.8,1.6,"cedar")
    for x in (-3.25,0,3.25):
        box((x,-2.44,1.25),(2.5,.12,2.5),"shade")
        door(x,-2.54,2.3,1.25,True)
        box((x,-3.05,2.65),(3.23,1.35,.16),"roof",(.14,0,0))
    for x in (-4.85,-1.62,1.62,4.85):
        box((x,-3.55,1.28),(.15,.15,2.56),"cream")


def coop():
    for x in (-1.1,1.1):
        for y in (-1,1):
            box((x,y,.37),(.15,.15,.74),"wood")
    first = len(verts)
    shell(2.55,2.4,1.4,.62,"barn")
    for i in range(first,len(verts)):
        verts[i] = Vector(verts[i])+Vector((0,0,.64))
    box((0,-1.26,1.04),(.64,.1,.78),"shade")
    box((0,-2.12,.34),(.73,1.84,.10),"cedar",(.37,0,0))
    for i in range(6):
        box((0,-2.86+i*.27,.12+i*.105),(.75,.07,.06),"cream")
    box((1.39,0,1.04),(.65,1.52,.64),"cedar")
    box((1.39,0,1.4),(.78,1.66,.10),"roof",(0,.16,0))


def silo(tall):
    r,h = (1.8,7.4) if tall else (2.15,5.3)
    cylinder((0,0,h/2),r,r,h,"metal",32)
    for i in range(int(h/.38)):
        cylinder((0,0,i*.38+.14),r+.045,r+.045,.065,"rim",32)
    cylinder((0,0,h+.62),r+.15,.25,1.24,"rim",32)
    cylinder((0,0,h+1.32),.29,.29,.17,"metal")
    for x in (-.21,.21):
        box((x,-r-.12,h/2),(.06,.08,h),"roof")
    for i in range(1,int(h/.34)):
        box((0,-r-.14,i*.34),(.46,.07,.05),"roof")


def field(kind):
    box((0,0,.085),(8,11,.17),"soil")
    for j in range(8):
        x = j-.5*7
        box((x,0,.19),(.59,10.65,.17),"earth")
        if kind == "furrows":
            continue
        if kind == "wheat":
            for stem in range(110):
                xx = x+rng.uniform(-.28,.28)
                yy = -5.16+stem*.095+rng.uniform(-.06,.06)
                tip = rng.uniform(.91,1.22)
                cylinder((xx,yy,(tip+.24)/2),.025,.021,tip-.24,"straw",4)
                cylinder((xx,yy,tip),.062,.031,.23,"wheat",5)
                cylinder((xx,yy,tip+.16),.032,.003,.10,"straw",4)
            continue
        for i in range(16):
            y = -5+i*10/15
            dx = rng.uniform(-.09,.09)
            if kind == "cabbage":
                cylinder((x+dx,y,.42),.19,.34,.30,"leaf",7)
                cylinder((x+dx,y,.66),.31,.14,.18,"sprout",7)
            else:
                cylinder((x,y,.86),.06,.035,1.35,"sprout",6)
                for k in range(4):
                    angle = k*pi/2+i
                    box((x+.14*cos(angle),y+.14*sin(angle),.60+k*.18),
                        (.48,.15,.055),"leaf" if k%2 else "sprout",(0,-.55,angle))
                cylinder((x,y,1.59),.06,.015,.24,"wheat",5)


def tractor(color):
    box((0,0,.75),(1.04,2.9,.38),"shade")
    box((0,-.62,1.25),(1.05,1.66,.74),color)
    box((0,-1.48,1.25),(.78,.09,.5),"roof")
    for i in range(7):
        box(((i-3)*.097,-1.54,1.25),(.035,.04,.43),"metal")
    for x in (-.44,.44):
        box((x,-1.49,1.58),(.19,.12,.15),"cream")
        box((x*1.65,.86,1.59),(.45,1.31,.12),color)
        box((x,.99,1.93),(.08,.08,1.48),"roof")
    box((0,.65,1.25),(.67,.53,.14),"shade")
    box((0,.91,1.48),(.67,.14,.5),"shade")
    cylinder((0,.10,1.42),.05,.05,.40,"roof")
    cylinder((0,.10,1.65),.23,.23,.055,"shade")
    cylinder((.33,-.72,1.99),.07,.07,.85,"shade")
    box((0,.64,2.65),(1.65,1.58,.15),color)
    body = finish("Chassis")
    pieces = [body]
    for front in (False,True):
        radius = .53 if front else .80
        for side in (-1,1):
            cylinder((0,0,0),radius,radius,.34,"tire",20,True)
            cylinder((side*.18,0,0),radius*.61,radius*.61,.07,"gold",16,True)
            cylinder((side*.23,0,0),radius*.29,radius*.29,.08,color,12,True)
            for i in range(16):
                a = i*tau/16
                box((0,-radius*sin(a),radius*cos(a)),(.37,.13,.075),"tread",(a,0,0))
            wheel = finish(("Front" if front else "Rear")+("Left" if side<0 else "Right"),
                           (side*.77,-1.04 if front else .86,radius+.025))
            wheel.parent = body
            pieces.append(wheel)
    return pieces




def windmill():
    def strut(a, b, width, color):
        a, b = Vector(a), Vector(b)
        direction = b - a
        box((a+b)/2, (width,width,direction.length), color,
            direction.to_track_quat('Z','Y').to_euler())

    # Four tapered legs with crossed braces on every face.
    corners = [(-1,-1),(1,-1),(1,1),(-1,1)]
    levels = [(0,1.35),(2.6,1.03),(5.2,.71),(7.8,.39)]
    for i,(sx,sy) in enumerate(corners):
        nx,ny = corners[(i+1)%4]
        box((sx*1.35,sy*1.35,.13),(.45,.45,.26),"rim")
        strut((sx*1.35,sy*1.35,0),(sx*.39,sy*.39,7.8),.16,"wood")
        for (low,w),(high,v) in zip(levels,levels[1:]):
            strut((sx*w,sy*w,low),(nx*v,ny*v,high),.085,"cedar")
            strut((nx*w,ny*w,low),(sx*v,sy*v,high),.085,"cedar")
            strut((sx*v,sy*v,high),(nx*v,ny*v,high),.12,"wood")
    box((0,0,7.83),(1.45,1.45,.18),"cedar")
    cylinder((0,0,8.31),.19,.19,.84,"roof")
    tower = finish("WindmillTower")

    box((0,-.29,0),(.4,1.0,.39),"roof")
    cylinder((0,0,1.53),.067,.052,3.1,"roof")
    # Feathered arrow and a cut-metal rooster in profile, seen above the wheel.
    def cutout(profile,color):
        count = len(profile)
        add([(x,y,z) for y in (-.055,.055) for x,z in profile],
            [tuple(range(count)),tuple(reversed(range(count,2*count)))] +
            [(i,i+count,(i+1)%count+count,(i+1)%count) for i in range(count)],color)

    box((0,0,2.9),(2.91,.13,.105),"gold")
    cutout([(-1.88,2.90),(-1.17,2.59),(-1.17,3.21)],"gold")
    cutout([(.77,2.9),(1.14,2.61),(1.68,2.61),(1.43,2.9),
            (1.68,3.19),(1.14,3.19)],"gold")
    cutout([(-.47,3.02),(-.22,3.02),(-.16,3.21),(.08,3.17),
            (.36,3.29),(.65,3.19),(.5,3.48),(.73,3.41),(.57,3.70),
            (.31,3.78),(.44,3.54),(.16,3.58),(-.03,3.53),(-.21,3.86),
            (-.23,4.00),(-.34,3.92),(-.42,4.04),(-.50,3.89),
            (-.70,3.76),(-.48,3.72),(-.55,3.58),(-.45,3.59),
            (-.42,3.37),(-.28,3.21)],"batten")
    head = finish("VaneHead",(0,0,8.72))
    head.parent = tower

    # Shallow folded sails flare towards their tips around a pair of steel hoops.
    for i in range(14):
        a = tau*i/14
        def point(r,angle,depth):
            return (r*cos(angle),depth,r*sin(angle))
        strut((0,0,0),point(1.98,a,0),.062,"rim")
        for r in (1.05,1.98):
            strut(point(r,a,0),point(r,a+tau/14,0),.047,"rim")
        for inner,outer,color in ((.92,1.86,"metal"),(1.86,2.12,"batten")):
            face = [point(inner,a-.14,.09),point(outer,a-.14,.09),
                    point(outer,a+.17,-.12),point(inner,a+.17,-.12)]
            add(face + [(x,y+.045,z) for x,y,z in face],
                [(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],color)
    box((0,-.04,0),(.39,.32,.39),"gold")
    rotor = finish("WindWheel",(0,-.85,0))
    rotor.parent = head
    return [tower,head,rotor]


def asset(name, build, x, y):
    objects = build() or [finish(name)]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+".glb")), use_selection=True, export_format="GLB")
    objects[0].location += Vector((x,y,0))
    return objects[0]


asset("farm_windmill",windmill,-3.0,14)
asset("red_barn",barn,-9,9)
asset("horse_barn",stable,3,8)
asset("farmhouse",lambda: house(True),14,11)
asset("farm_cottage",lambda: house(False),21,7)
coop_obj = asset("chicken_coop",coop,9,4.5)
second = coop_obj.copy()
scene.collection.objects.link(second)
second.location.x += 4.1
asset("tower_silo",lambda: silo(True),-17,11)
asset("grain_bin",lambda: silo(False),-21,7)
for x,kind in zip((-15,-5,5,15),("wheat","cabbage","corn","furrows")):
    asset("field_"+kind,lambda k=kind: field(k),x,-8)
asset("jade_tractor",lambda: tractor("tractor"),-14,0).rotation_euler.z = pi/2
asset("ochre_tractor",lambda: tractor("yellow"),13,-16).rotation_euler.z = -pi/2

# Headlands connect at each end of the fields. The tractors follow their centreline.
box((0,0,-.37),(54,42,.74),"turf")
for y in (0,-16):
    box((0,y,.015),(46,3.8,.03),"lane")
for x in (-21,21):
    box((x,-8,.018),(3.8,16,.036),"lane")
for a,b,y in [(-25,-12,16.7),(1,24,16.7),(-25,24,-18.9)]:
    count = round((b-a)/2.8)
    for i in range(count+1):
        box((a+i*(b-a)/count,y,.61),(.16,.18,1.22),"cedar")
    for z in (.43,.91):
        box(((a+b)/2,y,z),(b-a,.1,.13),"wood")
asset("farmyard",lambda: None,0,0)

target = Vector((0,-.8,1))
direction = Vector((23,-62,44))
rotation = (-direction).to_track_quat('-Z','Y')
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 65
        space.shading.color_type = 'MATERIAL'
bpy.ops.object.camera_add(location=target+direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 66
scene.camera = camera
scene.world = bpy.data.worlds.new('Overcast sky')
scene.world.color = (.55,.64,.75)
bpy.ops.object.light_add(type='SUN')
bpy.context.object.rotation_euler = (.49,-.58,-.3)
bpy.context.object.data.energy = 3.4
bpy.context.object.data.angle = .15
scene.render.engine = 'CYCLES'
scene.cycles.samples = 10
scene.cycles.use_denoising = True
scene.render.resolution_x = 1440
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT/"art/farm_kit_preview.png")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art/farm_kit.blend"))
bpy.ops.render.render(write_still=True)
