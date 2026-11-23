"""Run Blender in background with -P art/dock_kit.py to rebuild the dock modules."""
from pathlib import Path
import math
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/dock_kit"
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = .8
    return m


boards = [material("Weathered fir " + str(i), rgb) for i, rgb in enumerate([
    (.34, .225, .135), (.41, .285, .178), (.37, .262, .17), (.30, .212, .148)])]
timber = material("Creosoted timber", (.105, .069, .045))
steel = material("Galvanized zinc", (.32, .39, .40))
rubber = material("Rubber rubbing strip", (.037, .043, .042))
float_mat = material("Pontoon shell", (.065, .106, .104))
paint = material("Ochre end markings", (.80, .435, .085))


def box(name, center, size, mat, bevel=.012):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Eased edges", "BEVEL")
        mod.width = bevel
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.append(mat)
    return obj


def finish(name, offset):
    bpy.ops.object.select_all(action="DESELECT")
    parts = [o for o in scene.objects if o.name not in finished]
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    obj.name = name
    bpy.ops.export_scene.gltf(filepath=str(OUT / (name + ".glb")), use_selection=True)
    finished.add(name)
    obj.location = offset


finished = set()
for row, (kind, w) in enumerate([("main", 4), ("finger", 2)]):
    for col, ramp in enumerate([False, True]):
        for i in range(30):
            box("Plank", (0, (i+.5)/5, -.045), (w, .196, .09),
                boards[(i*7 + i//3) % 4], .004)
        for sign in [-1, 1]:
            x = sign*(w/2-.11)
            box("Stringer", (x, 3, -.19), (.18, 6, .22), steel if ramp else timber)
            if ramp:
                for y in [.06, 2, 4, 5.94]:
                    box("Stanchion", (x, y, .43), (.055,.055,.86), steel)
                for z in [.48,.88]:
                    box("Handrail", (x, 3, z), (.064,5.94,.055), steel)
                for y in [.10,5.90]:
                    box("Threshold stripe", (sign*w/4,y,.002), (w/2-.14,.065,.004), paint, 0)
            else:
                for y in [1.5, 4.5]:
                    box("Hull rub strip", (sign*(w/2-.03), y, -.13), (.06,2.76,.14), rubber)
        finish(kind + ("_ramp" if ramp else "_deck"), (col*5,row*8,0))
    for sign in [-1, 1]:
        x = sign*(w/2-.44)
        box("Sealed float", (x,3,-.56), (.71,5.65,.62), float_mat,.08)
        for y in [.85,3,5.15]:
            box("Float band", (x,y,-.56), (.73,.09,.64), rubber,.05)
    finish(kind+"_floats", (10,row*8,0))
    for y in [.6,5.4]:
        box("Pile cap beam",(0,y,-.36),(w-.16,.23,.23), timber)
        for sign in [-1, 1]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=.16,depth=5,
                location=(sign*(w/2-.32),y,-2.965))
            bpy.context.object.data.materials.append(timber)
    finish(kind+"_piles", (15,row*8,0))

# A cast two-horn cleat, with open space for a line under each horn.
iron = material("Graphite cast iron", (.052, .065, .071))
box("Mounting foot", (0, 0, .016), (.16, .34, .032), iron)
for sign in (-1, 1):
    leg = box("Cleat leg", (0, sign*.084, .077), (.074,.060,.115), iron)
    leg.rotation_euler.x = -sign*.18
    for x in (-.054, .054):
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=.013, depth=.014,
                                            location=(x, sign*.137, .039))
        bpy.context.object.data.materials.append(steel)
# Loft an elliptical crossbar, tapering and lifting both horn tips.
rings = [(-.26,.168,.013), (-.235,.162,.022), (-.13,.14,.035),
         (0,.14,.040), (.13,.14,.035), (.235,.162,.022), (.26,.168,.013)]
vertices = [(r*math.cos(i*math.tau/8), y, z+r*.76*math.sin(i*math.tau/8))
            for y,z,r in rings for i in range(8)]
faces = [tuple(range(8)), tuple(reversed(range(len(vertices)-8, len(vertices))))]
for k in range(len(rings)-1):
    for i in range(8):
        a, b = 8*k+i, 8*k+(i+1)%8
        faces.append((a, a+8, b+8, b))
mesh = bpy.data.meshes.new("Cleat horns")
mesh.from_pydata(vertices, [], faces)
horns = bpy.data.objects.new("Cleat horns", mesh)
scene.collection.objects.link(horns)
mesh.materials.append(iron)
finish("cleat", (-3, 0, 0))

bpy.ops.object.select_all(action="DESELECT")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "art/dock_kit.blend"))
