"""Build the Tideways submarine with Blender in background mode, from the repo root."""
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
# Coordinates below are (beam, bow, height above surfaced waterline), in metres.
def point(x, forward, z):
    return (x, -forward, z)


def color(hex_value):
    channels = [int(hex_value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels) + (1,)


paint = bpy.data.materials.new("Submarine paint")
paint.use_nodes = True
shader = paint.node_tree.nodes.get("Principled BSDF")
attribute = paint.node_tree.nodes.new("ShaderNodeVertexColor")
attribute.layer_name = "Paint"
paint.node_tree.links.new(attribute.outputs["Color"], shader.inputs["Base Color"])
shader.inputs["Roughness"].default_value = .67
slate, rubber, red, deck = "36434b", "26323a", "783e38", "4c595e"
pale, steel, brass = "d2d7ca", "849296", "997d4e"


def mesh(name, vertices, faces, colors):
    data = bpy.data.meshes.new(name)
    data.from_pydata([point(*v) for v in vertices], [], faces)
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    data.materials.append(paint)
    layer = data.color_attributes.new(name="Paint", type="FLOAT_COLOR", domain="CORNER")
    for polygon, tint in zip(data.polygons, colors):
        for index in polygon.loop_indices:
            layer.data[index].color = color(tint)
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    return obj


def loft(name, rings, tint, shade=None):
    n = len(rings[0])
    faces = [tuple(reversed(range(n)))]
    colors = [tint]
    for row in range(len(rings) - 1):
        for i in range(n):
            a, b = row * n + i, row * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
            colors.append(shade(row, i) if shade else tint)
    faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    return mesh(name, sum(rings, []), faces, colors + [tint])


# Keep the shoulders and keel profile, with tighter spacing across the exposed crown.
angles = [math.radians(a) for a in (0, 22.5, 45, 56.25, 67.5, 78.75, 90,
                                    101.25, 112.5, 123.75, 135, 157.5, 180,
                                    202.5, 270, 337.5)]
stations = [(-47,.55), (-42,2.05), (-36,3.35), (-28,4.52),
            (-18,5.02), (19,5.18), (32,5.02), (38,4.65),
            (42,3.94), (45,2.9), (46.7,1.6), (47.2,.45)]
axis = -2.35
rings = [[(r*math.cos(a), f, axis + r*math.sin(a)) for a in angles] for f,r in stations]


def hull_color(row, side):
    end = angles[side + 1] if side + 1 < len(angles) else math.tau
    elevation = math.sin((angles[side] + end) / 2)
    if elevation < -.35:
        return red
    if row >= 10 or elevation < .12:
        return rubber
    return slate


loft("Hull", rings, rubber, hull_color)
# Rounded leading edge, straight flanks, pinched trailing edge.
outline = [(0,6),(.74,5.55),(1,4.3),(1,-2.5),(.68,-4.5),(0,-6),
           (-.68,-4.5),(-1,-2.5),(-1,4.3),(-.74,5.55)]
sail_rings = [[(x*w, 12+y*l, z) for x,y in outline]
              for z,w,l in [(2.35,1.95,1.18),(3.45,1.4,1),(8.8,1.4,1),(9.15,1.18,.95)]]
loft("Sail", sail_rings, slate, lambda row,i: deck if row == 2 else slate)


def disc(name, f, x, rings, sides, tint):
    loft(name, [[(x+r*math.cos(i*math.tau/sides), f+r*math.sin(i*math.tau/sides), z)
                 for i in range(sides)] for z,r in rings], tint)


for f in (-14, 27):
    disc("Deck hatch", f, 0, [(2.53,1.12),(2.88,1.12),(2.99,.92)], 10, deck)
for f,h,r in [(11.6,12.6,.19),(14,11.4,.26)]:
    disc("Mast collar", f, 0, [(9.12,.4),(9.45,.36)], 6, rubber)
    disc("Mast", f, 0, [(9.43,r),(h,r)], 6, steel)
    disc("Scope head", f, 0, [(h-.35,r*1.55),(h+.23,r*1.55)], 6, rubber)


def foil(name, angle, start, end, center, sweep, chord, thickness, tint):
    rings = []
    for radius, shift, scale in [(start,0,1),(end,sweep,.42)]:
        ring = []
        for along, height in [(.5,0),(.13,1),(-.5,.15),(-.5,-.15),(.13,-1)]:
            offset = height*thickness*scale
            ring.append((radius*math.cos(angle)-offset*math.sin(angle),
                         center+shift+along*chord*scale,
                         (5.1 if name == "Sail plane" else axis)+radius*math.sin(angle)+offset*math.cos(angle)))
        rings.append(ring)
    loft(name,rings,tint)


for angle in (0,math.pi):
    foil("Sail plane", angle,1.25,5.2,12,.0,3.7,.25,slate)
for i in range(4):
    foil("Tail plane", i*math.pi/2,1,6,-38,-2.7,8.2,.38,red if i==3 else slate)
for i in range(7):
    foil("Screw blade", i*math.tau/7,.32,2.38,-47.45,-.52,1.8,.19,brass)
hub_angles = [math.tau * i / 8 for i in range(8)]
loft("Screw hub", [[(r*math.cos(a),f,axis+r*math.sin(a)) for a in hub_angles]
                    for f,r in [(-46.85,.55),(-47.9,.55),(-48.65,.13)]], brass)

# Painted 07 identifier on the flat faces of the sail, readable from either beam.
glyphs = [[(0,0),(1,0),(1,1.65),(0,1.65),(0,0)],[(0,1.65),(1,1.65),(.28,0)]]
for side in (-1,1):
    for digit,path in enumerate(glyphs):
        for (u,v),(s,t) in zip(path,path[1:]):
            length = math.hypot(s-u,t-v)
            dy,dz = -.095*(t-v)/length,.095*(s-u)/length
            vertices = [(side*1.413,13.5-side*(digit*1.45+a),6.1+b)
                        for a,b in [(u+dy,v+dz),(s+dy,t+dz),(s-dy,t-dz),(u-dy,v-dz)]]
            mesh("Sail number",vertices,[(0,1,2,3) if side==1 else (3,2,1,0)],[pale])

objects = list(scene.objects)
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = objects[0]
bpy.ops.object.join()
sub = bpy.context.object
sub.name = "Nuclear submarine"
sub.data.calc_loop_triangles()
assert len(sub.data.loop_triangles) <= 1000, len(sub.data.loop_triangles)
print("Model triangles", len(sub.data.loop_triangles))
bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets/models/nuclear_sub_mid.glb"),use_selection=True)
# Studio preview with the entire keel visible.
camera_data = bpy.data.cameras.new("Asset portrait")
camera = bpy.data.objects.new("Asset portrait", camera_data)
scene.collection.objects.link(camera)
camera.location = (87,-44,36)
camera.rotation_euler = (Vector((0,0,.7))-camera.location).to_track_quat('-Z','Y').to_euler()
camera_data.type = 'ORTHO'
camera_data.ortho_scale = 99
camera_data.clip_end = 300
scene.camera = camera
scene.render.engine = 'BLENDER_WORKBENCH'
shading = scene.display.shading
shading.light = 'STUDIO'
shading.color_type = 'VERTEX'
shading.show_shadows = True
shading.show_cavity = True
shading.cavity_type = 'WORLD'
scene.world = bpy.data.worlds.new("Backdrop")
scene.world.color = (.19,.23,.25)
shading.background_type = 'WORLD'
scene.render.resolution_x,scene.render.resolution_y = 1400,610
scene.render.resolution_percentage = 100
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        area.spaces.active.shading.color_type = 'VERTEX'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art/nuclear_sub_mid.blend"))
scene.render.filepath = str(ROOT/"art/nuclear_sub_mid_preview.png")
bpy.ops.render.render(write_still=True)
