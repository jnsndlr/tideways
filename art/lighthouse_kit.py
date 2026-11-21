"""Run with Blender -b -P art/lighthouse_kit.py from the repository root."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
ART = ROOT / "art"
TAU = math.tau
sin, cos, pi = math.sin, math.cos, math.pi

bpy.ops.wm.read_factory_settings(use_empty=True)
paint = bpy.data.materials.new("Coastal paint")
paint.use_nodes = True
attribute = paint.node_tree.nodes.new("ShaderNodeVertexColor")
attribute.layer_name = "Paint"
shader = paint.node_tree.nodes.get("Principled BSDF")
paint.node_tree.links.new(attribute.outputs["Color"], shader.inputs["Base Color"])

cream, white, red = "e9dcbb", "f5efdf", "af4134"
iron, teal, slate = "303e43", "468579", "515e63"
stone, glass, gold = "aca69a", "426372", "ffd688"
brick, wood = "a25d49", "c9a980"


class Part:
    def __init__(self, name):
        self.name = name
        self.vertices, self.faces, self.colors = [], [], []

    def face(self, points, color):
        start = len(self.vertices)
        self.vertices.extend(points)
        self.faces.append(tuple(range(start, len(self.vertices))))
        self.colors.append(color)

    def ring(self, z, top, r, rt, sides, color, phase=0, center=(0, 0)):
        rings = [[(center[0] + radius*cos(phase+i*TAU/sides),
                   center[1] + radius*sin(phase+i*TAU/sides), h)
                  for i in range(sides)] for h, radius in [(z, r), (top, rt)]]
        for i in range(sides):
            j = (i+1) % sides
            self.face([rings[0][i], rings[0][j], rings[1][j], rings[1][i]], color)
        self.face(rings[0][::-1], color)
        self.face(rings[1], color)

    def box(self, x, y, z, w, d, h, color):
        pts = [(x+a*w/2, y+b*d/2, z+c*h/2) for c in (-1,1)
               for a,b in [(-1,-1),(1,-1),(1,1),(-1,1)]]
        for f in [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            self.face([pts[i] for i in f], color)

    def rod(self, a, b, radius, color, sides=6):
        a, b = Vector(a), Vector(b)
        axis = (b-a).normalized()
        u = axis.cross(Vector((0,1,0)))
        if u.length < 0.01:
            u = axis.cross(Vector((1,0,0)))
        u.normalize()
        v = axis.cross(u)
        rim = [radius*(u*cos(i*TAU/sides)+v*sin(i*TAU/sides)) for i in range(sides)]
        for i in range(sides):
            j = (i+1) % sides
            self.face([a+rim[i], a+rim[j], b+rim[j], b+rim[i]], color)
        self.face([a+p for p in reversed(rim)], color)
        self.face([b+p for p in rim], color)

    def finish(self):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.materials.append(paint)
        colors = mesh.color_attributes.new(name="Paint", type="BYTE_COLOR", domain="CORNER")
        for poly, hex_color in zip(mesh.polygons, self.colors):
            rgb = [int(hex_color[i:i+2], 16)/255 for i in (0,2,4)]
            for i in poly.loop_indices:
                colors.data[i].color_srgb = (*rgb, 1)
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def sash(p, x, y, z, w=1, h=1.6):
    p.box(x,y,z,w+.24,.25,h+.28,cream)
    p.box(x,y-.15,z,w,.11,h,glass)
    p.box(x,y-.22,z,.08,.08,h,white)
    p.box(x,y-.22,z,w,.08,.09,white)
    p.box(x,y-.08,z-h/2-.17,w+.4,.44,.15,stone)


def masonry(name, h, n, pattern):
    p = Part(name)
    phase = -pi/2 + pi/n
    def radius(t):
        return 3.85 - 1.65*t
    p.ring(-3,.48,4.26,4.1,n,stone,phase)
    courses = 24
    for j in range(courses):
        t, u = j/courses, (j+1)/courses
        color = cream
        if pattern == "band" and (6 <= j < 10 or 16 <= j < 20):
            color = red
        if pattern == "timber":
            color = white
        if pattern == "brick":
            color = [brick,"ac6952","aa624e","a45f4b"][j%4]
        p.ring(.48+t*(h-.48),.48+u*(h-.48),radius(t),radius(u),n,color,phase)
        if pattern == "timber" and j%2 == 0:
            z = .48+t*(h-.48)
            p.ring(z,z+.09,radius(t)+.045,radius(t)+.045,n,cream,phase)
    if pattern == "timber":
        for i in range(n):
            angle = phase+i*TAU/n
            p.rod((3.85*cos(angle),3.85*sin(angle),.48),
                  (2.2*cos(angle),2.2*sin(angle),h),.16,teal)
    for fraction in [.36,.66,.87]:
        sash(p,0,-radius(fraction)*cos(pi/n),h*fraction,.83,1.4)
    y = -radius(.05)*cos(pi/n)
    p.box(0,y,1.52,1.75,.55,2.9,cream)
    p.box(0,y-.3,1.42,1.35,.18,2.56,teal if pattern=="timber" else iron)
    for i in range(3):
        p.box(0,y-1.35+i*.36,.10+i*.13,2.12,.46,.3+i*.20,stone)
    p.ring(h-.65,h,2.3,2.8,n,cream,phase)
    return p.finish()


def skeleton():
    p = Part("Ironwork")
    sections = [(-2,3.5),(5,2.85),(11,2.18),(17,1.65)]
    def corner(i, r, z):
        return (r*cos(pi/4+i*pi/2),r*sin(pi/4+i*pi/2),z)
    for i in range(4):
        x,y,_ = corner(i,3.5,0)
        p.ring(-3,.5,.83,.72,8,stone,center=(x,y))
        for (z,r),(zz,rr) in zip(sections,sections[1:]):
            a,b = corner(i,r,z),corner(i+1,r,z)
            c,d = corner(i,rr,zz),corner(i+1,rr,zz)
            p.rod(a,c,.18,iron)
            p.rod(a,d,.10,teal)
            p.rod(b,c,.10,teal)
            p.rod(c,d,.15,iron)
    p.ring(-1,17,.78,.78,12,cream)
    p.ring(15.5,17,1.65,2.8,8,iron)
    return p.finish()


def lantern():
    p = Part("Gallery")
    p.ring(-.18,.28,2.75,3.25,16,iron)
    p.ring(.28,.43,3.25,3.25,16,cream)
    for i in range(16):
        a,b = TAU*i/16, TAU*(i+1)/16
        x,y = 3.07*cos(a),3.07*sin(a)
        p.rod((x,y,.43),(x,y,1.53),.063,iron)
        for z in [.94,1.53]:
            p.rod((x,y,z),(3.07*cos(b),3.07*sin(b),z),.055,iron)
    p.ring(.43,1.05,1.94,1.94,12,teal)
    p.ring(1.05,1.17,2,2,12,cream)
    # Open lantern with an amber stepped optic, central spindle and diagonal glazing bars.
    p.ring(1.17,1.7,.36,.36,12,iron)
    for i,r in enumerate([.46,.64,.75,.8,.75,.64,.46]):
        z = 1.52+i*.16
        p.ring(z,z+.105,r,r+.05,16,gold)
        p.ring(z+.105,z+.16,r+.05,r-.03,16,"eeb468")
    for i in range(12):
        a,b = TAU*i/12,TAU*(i+1)/12
        x,y = 1.83*cos(a),1.83*sin(a)
        p.rod((x,y,1.14),(x,y,3.14),.075,iron)
        p.rod((x,y,1.15),(1.83*cos(b),1.83*sin(b),3.14),.035,teal)
    p.ring(3.08,3.23,1.98,2.03,12,iron)
    return p.finish()


def cap(name,color,profile):
    p = Part(name)
    for (z,r),(zz,rr) in zip(profile,profile[1:]):
        p.ring(z,zz,r,rr,12,color)
    z = profile[-1][0]
    p.ring(z,z+.24,.20,.20,10,iron)
    p.ring(z+.24,z+.54,.20,.035,10,gold)
    return p.finish()


def house_window(p, x, y, z, angle=0, w=.95, h=1.23):
    # Turn the complete sash, including the projecting sill, onto its wall.
    start = len(p.vertices)
    sash(p, 0, 0, z, w, h)
    for i in range(start, len(p.vertices)):
        u, v, height = p.vertices[i]
        p.vertices[i] = (x+u*cos(angle)-v*sin(angle), y+u*sin(angle)+v*cos(angle), height)


def cottage(name, width, depth, eaves, rise, siding, roof, hip=0, porch=False):
    p = Part(name)
    x, y = width/2, depth/2
    p.box(0,0,-.9,width+.18,depth+.18,2.8,stone)
    p.box(0,0,(eaves+.42)/2,width,depth,eaves-.42,siding)
    for end in [-1,1]:
        for side in [-1,1]:
            p.box(end*(x-.08),side*(y-.08),(eaves+.42)/2,.22,.22,eaves-.42,white)
        house_window(p,end*(x+.04),0,2.04,end*pi/2)
        for side in [-1,1]:
            house_window(p,end*(x-1.03),side*(y+.04),2.04,pi if side>0 else 0)
    p.box(0,-y-.06,1.57,1.36,.21,2.38,white)
    p.box(0,-y-.21,1.53,1.09,.14,2.19,teal)
    for step in range(3):
        p.box(0,-y-1.25+.34*step,.065*(step+1),1.75,.4,.13*(step+1),stone)
    rx, ry = x+.35, y+.34
    ridge = rx-hip
    peak = eaves+rise
    for sign in [-1,1]:
        pts = [(-ridge,0,peak),(-rx,sign*ry,eaves),(rx,sign*ry,eaves),(ridge,0,peak)]
        p.face(pts if sign<0 else pts[::-1],roof)
        p.box(0,sign*ry,eaves-.065,2*rx,.15,.16,white)
        if hip:
            pts = [(sign*rx,-ry,eaves),(sign*rx,ry,eaves),(sign*ridge,0,peak)]
            p.face(pts if sign>0 else pts[::-1],roof)
            p.box(sign*rx,0,eaves-.065,.15,2*ry,.16,white)
        else:
            # Fit the wall gable under the roof slope at the wall line.
            pts = [(sign*x,-y,eaves),(sign*x,y,eaves),(sign*x,0,peak)]
            p.face(pts if sign>0 else pts[::-1],siding)
            for side in [-1,1]:
                p.rod((sign*rx,0,peak),(sign*rx,side*ry,eaves),.09,white)
    if porch:
        p.box(0,-y-.9,.32,width-.4,1.8,.36,wood)
        for post in [-x+.4,x-.4]:
            p.box(post,-y-1.65,1.65,.15,.15,2.65,white)
        p.face([(-x,-y-1.87,2.99),(x,-y-1.87,2.99),(x,-y,3.45),(-x,-y,3.45)],roof)
        p.box(0,-y-1.87,2.9,width,.13,.18,white)
    if eaves>5:
        for wx in [-x+1.03,0,x-1.03]:
            house_window(p,wx,-y-.04,4.62,w=.82,h=1.08)
    chimney = peak+.36
    p.box(x*.55,.55,chimney-1,.68,.68,2,brick)
    p.box(x*.55,.55,chimney,.86,.86,.19,iron)
    return p.finish()


towers = [masonry("DoubleBand",21,20,"band"), masonry("Timber",13,4,"timber"),
          skeleton(), masonry("Brick",18,8,"brick")]
gallery = lantern()
roofs = [cap("Oxblood",red,[(0,2.26),(.18,2.3),(1.55,.25)]),
         cap("Copper",teal,[(0,2.28),(.19,2.3),(.52,1.78),(1.28,1.15),(1.72,.25)]),
         cap("Graphite",iron,[(0,2.22),(.16,2.28),(.44,1.73),(.92,1.36),(1.33,.78),(1.48,.25)])]
houses = [
    cottage("KeepersHouse",6.25,4.5,3.65,1.88,cream,slate),
    cottage("PorchBungalow",7.5,4.9,3.65,1.65,"a9c2b4",iron,hip=2.15,porch=True),
    cottage("BrickQuarters",5.6,5.0,5.7,2.05,brick,"53696e"),
]
kit = towers+[gallery]+roofs+houses
bpy.ops.object.select_all(action="DESELECT")
for obj in kit:
    obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets/models/lighthouse_kit.glb"),use_selection=True,
                          export_materials="EXPORT",export_yup=True)

# Four editable assemblies in the source file, sharing gallery, cottage and roof meshes.
def place(obj, xyz, collection):
    instance = obj.copy()
    collection.objects.link(instance)
    instance.location = xyz
    return instance

for i,(shaft,h) in enumerate(zip(towers,[21,13,17,18])):
    collection = bpy.data.collections.new(["Headland","Harbor","Shoal","Fort Point"][i])
    bpy.context.scene.collection.children.link(collection)
    x = (i-1.5)*21
    place(shaft,(x,0,0),collection)
    place(gallery,(x,0,h),collection)
    place(roofs[[0,1,2,1][i]],(x,0,h+3.23),collection)
    if i != 2:
        place(houses[[0,1,0,2][i]],(x+10,-3,0),collection)
for obj in kit:
    bpy.data.objects.remove(obj,do_unlink=True)

scene = bpy.context.scene
scene.world = bpy.data.worlds.new("Marine overcast")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.62,.74,.8,1)
bpy.ops.mesh.primitive_plane_add(size=2000)
floor = bpy.context.object
floor.name = "Studio ground"
floor.location.z = -.02
mat = bpy.data.materials.new("Sea mist")
mat.diffuse_color = (.30,.42,.44,1)
floor.data.materials.append(mat)
bpy.ops.object.light_add(type="SUN", rotation=(.56,-.5,-.35))
bpy.context.object.data.energy = 2.7
bpy.context.object.data.angle = .21
target = Vector((4,0,9.8))
bpy.ops.object.camera_add(location=target+Vector((15,-83,26)))
cam = bpy.context.object
cam.rotation_euler = (target-cam.location).to_track_quat("-Z","Y").to_euler()
cam.data.type = "ORTHO"
cam.data.ortho_scale = 85
scene.camera = cam
scene.render.engine = "CYCLES"
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x,scene.render.resolution_y = 1860,785
scene.render.resolution_percentage = 100
for area in bpy.context.screen.areas:
    if area.type=="VIEW_3D":
        area.spaces.active.region_3d.view_perspective="CAMERA"
        area.spaces.active.shading.color_type="VERTEX"
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.object.select_all(action="DESELECT")
bpy.ops.wm.save_as_mainfile(filepath=str(ART/"lighthouse_kit.blend"))
scene.render.filepath = str(ART/"lighthouse_kit_preview.png")
bpy.ops.render.render(write_still=True)
