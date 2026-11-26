"""Rebuild both dock-kit shelters with Blender -b -P art/boathouses.py."""
from pathlib import Path
import math
import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parents[1] / "assets/models/dock_kit"
bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, color, metal=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = .68
    return mat


fir = material("Salt-worn fir", (.30, .195, .107))
zinc = material("Galvanized sheet", (.56, .62, .63), .35)
flashing = material("Folded zinc trim", (.73, .76, .71), .4)
cedar = material("Faded harbour blue", (.15, .28, .31))
glass = material("Clerestory glass", (.08, .155, .18), .35)
cream = material("Linen paint", (.77, .73, .59))
iron = material("Pile shoe", (.105, .13, .13), .4)


def box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def beam(name, a, b, width, depth, mat):
    span = Vector(b) - Vector(a)
    obj = box(name, (Vector(a) + Vector(b)) / 2, (width, depth, span.length), mat)
    obj.rotation_euler = span.to_track_quat("Z", "Y").to_euler()


def build(enclosed):
    # Deck height is zero. Local +Y runs from the head float toward open water.
    eave, ridge = 3.35, 4.40
    for side in (-1, 1):
        x = side * 2.72
        for y in (.32, 6, 11.68):
            box("Post", (x, y, eave/2), (.16, .18, eave), fir)
            box("Galvanized foot", (x, y, .12), (.19, .21, .24), iron)
            for sense in (-1, 1):
                if 0 < y + sense * .68 < 12:
                    beam("Knee brace", (x, y, 2.56), (x, y + sense*.68, 3.22), .10, .12, fir)
            beam("Principal rafter", (x, y, eave-.09), (0, y, ridge-.09), .14, .16, fir)
        box("Eave plate", (x, 6, 3.25), (.19, 11.95, .20), fir)
        pitch = math.atan2(ridge-eave, 2.97)
        roof = box("Standing seam pan", (side*1.485, 6, (eave+ridge)/2),
                   (2.97/math.cos(pitch), 12.12, .065), zinc)
        roof.rotation_euler.y = side*pitch
        for i in range(27):
            y = i*.46 + .02
            beam("Raised seam", (side*2.97, y, eave+.045), (0, y, ridge+.045), .035, .04, flashing)
        box("Drip flashing", (side*2.96, 6, eave-.035), (.06, 12.12, .11), flashing)
        if enclosed:
            for row in range(12):
                box("Lap siding", (x+side*(.095+.002*(row%2)), 6, .23+row*.19),
                    (.075, 11.9, .185), cedar)
            box("Window ribbon", (x, 6, 2.75), (.07, 11.8, .65), glass)
            for z in (2.39, 3.10):
                box("Sash rail", (x, 6, z), (.16, 11.94, .085), cream)
            for j in range(9):
                box("Mullion", (x, .12+j*1.47, 2.75), (.14, .075, .65), cream)
    for y in (.32, 6, 11.68):
        box("Tie beam", (0, y, 3.23), (5.6, .17, .17), fir)
        beam("King post", (0, y, 3.23), (0, y, ridge-.1), .12, .14, fir)
    box("Ridge flashing", (0, 6, ridge+.035), (.17, 12.14, .07), flashing)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    obj.name = "boathouse_" + ("enclosed" if enclosed else "open")
    bpy.ops.export_scene.gltf(filepath=str(OUT / (obj.name + ".glb")), use_selection=True)
    bpy.data.objects.remove(obj, do_unlink=True)


for enclosed in (False, True):
    build(enclosed)
