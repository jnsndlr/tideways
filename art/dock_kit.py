"""Run Blender in background with -P art/dock_kit.py to rebuild the dock modules."""
from pathlib import Path
import math
import random
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pier_wood import BOARD_COLORS, TIMBER_COLOR, grain

wood_rng = random.Random(413)


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


boards = [material("Weathered fir " + str(i), rgb) for i, rgb in enumerate(BOARD_COLORS)]
timber = material("Pier timber", TIMBER_COLOR)
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
    if mat in boards or mat == timber:
        grain(obj, wood_rng)
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


# One white material carries the fir, stringer and rubbing-strip colours.
deck_mat = material("Dock vertex colour", (1, 1, 1))
colour_node = deck_mat.node_tree.nodes.new("ShaderNodeVertexColor")
colour_node.layer_name = "Dock colour"
deck_mat.node_tree.links.new(colour_node.outputs["Color"],
                             deck_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])


def part(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return obj


def panel(name, center, size, faces, rgb, shades=None):
    # Lower and upper corners each run counterclockwise from (-x, -y).
    vertices = [(center[0] + x*size[0]/2, center[1] + y*size[1]/2,
                 center[2] + z*size[2]/2)
                for z in (-1, 1) for x, y in ((-1,-1), (1,-1), (1,1), (-1,1))]
    obj = part(name, vertices, faces, deck_mat)
    colours = obj.data.color_attributes.new(name="Dock colour", type="FLOAT_COLOR", domain="POINT")
    for i, value in enumerate(colours.data):
        shade = shades[i % 4] if shades else 1.0
        value.color = (*(c*shade for c in rgb), 1)


top = (4,5,6,7)
bottom = (3,2,1,0)
front, back = (0,1,5,4), (2,3,7,6)
left, right = (3,0,4,7), (1,2,6,5)

finished = set()
for row, (kind, w) in enumerate([("main", 4), ("finger", 2)]):
    for col, ramp in enumerate([False, True]):
        for i in range(30):
            # Vary colour across the narrow axis to suggest grain along the board.
            rng = random.Random(413+i)
            shades = [rng.uniform(.78,.88), rng.uniform(.78,.88),
                      rng.uniform(.98,1.08), rng.uniform(.98,1.08)]
            panel("Plank", (0,(i+.5)/5,-.045), (w,.196,.09), (top,front,back),
                  BOARD_COLORS[(i*7 + i//3) % 4], shades)
        for sign in [-1, 1]:
            x = sign*(w/2-.11)
            panel("Stringer", (x,3,-.19), (.18,6,.22), (bottom,left,right,front,back),
                  steel.diffuse_color[:3] if ramp else TIMBER_COLOR)
            if ramp:
                for y in [.06, 2, 4, 5.94]:
                    box("Stanchion", (x, y, .43), (.055,.055,.86), steel, 0)
                for z in [.48,.88]:
                    box("Handrail", (x, 3, z), (.064,5.94,.055), steel, 0)
                for y in [.10,5.90]:
                    box("Threshold stripe", (sign*w/4,y,.002), (w/2-.14,.065,.004), paint, 0)
            else:
                for y in [1.5, 4.5]:
                    panel("Hull rub strip", (sign*(w/2-.03),y,-.13), (.06,2.76,.14),
                          (top,bottom,front,back,right if sign > 0 else left), rubber.diffuse_color[:3])
        finish(kind + ("_ramp" if ramp else "_deck"), (col*5,row*8,0))
    for sign in [-1, 1]:
        x = sign*(w/2-.44)
        box("Sealed float", (x,3,-.56), (.71,5.65,.62), float_mat,0)
        for y in [.85,3,5.15]:
            box("Float band", (x,y,-.56), (.73,.09,.64), rubber,0)
    finish(kind+"_floats", (10,row*8,0))
    for y in [.6,5.4]:
        panel("Pile cap beam", (0,y,-.36), (w-.16,.23,.23),
              (top,bottom,front,back,left,right), TIMBER_COLOR)
        for sign in [-1, 1]:
            bpy.ops.mesh.primitive_cylinder_add(vertices=8,end_fill_type="NOTHING",radius=.16,depth=5,
                location=(sign*(w/2-.32),y,-2.965))
            bpy.context.object.data.materials.append(timber)
            # The cap beam covers the pile head and the lower end is submerged.
    finish(kind+"_piles", (15,row*8,0))

# A cast two-horn cleat, with open space for a line under each horn.
iron = material("Graphite cast iron", (.052, .065, .071))
box("Mounting foot", (0, 0, .016), (.16, .34, .032), iron, 0)
for sign in (-1, 1):
    leg = box("Cleat leg", (0, sign*.084, .077), (.074,.060,.115), iron, 0)
    leg.rotation_euler.x = -sign*.18
# Diamond sections taper from the broad centre to the raised tips.
rings = [(-.26,.168,.013), (0,.14,.040), (.26,.168,.013)]
vertices = [(r*math.cos(i*math.tau/4), y, z+r*.76*math.sin(i*math.tau/4))
            for y,z,r in rings for i in range(4)]
faces = [(0,1,2,3), (11,10,9,8)]
for k in range(len(rings)-1):
    for i in range(4):
        a, b = 4*k+i, 4*k+(i+1)%4
        faces.append((a, a+4, b+4, b))
part("Cleat horns", vertices, faces, iron)
finish("cleat", (-3, 0, 0))

ivory = material("Salt-worn fiberglass", (.78, .80, .71))
navy = material("Marine blue", (.032, .115, .18))
rope = material("Manila line", (.52, .35, .16))
wire = material("Vinyl-coated pot wire", (.058, .12, .095))


def rod(name, start, end, radius, mat, sides=8):
    start, end = Vector(start), Vector(end)
    axis = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides, radius=radius,
                                        depth=axis.length, location=(start+end)/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)


# Weatherproof locker with an overhanging lid, gasket and paired draw latches.
box("Locker", (0, 0, .30), (1.38, .66, .60), ivory, .06)
box("Gasket", (0, 0, .60), (1.39, .67, .035), rubber)
box("Moulded lid", (0, 0, .655), (1.46, .72, .10), ivory, .045)
for x in (-.42, .42):
    box("Latch", (x, -.34, .57), (.08, .04, .15), steel)
finish("dock_box", (-3, 2, 0))

box("Bolt flange", (0, 0, .04), (.43, .39, .08), steel)
box("Pedestal", (0, 0, .55), (.31, .28, 1.03), ivory, .035)
box("Lamp lens", (0, 0, 1.095), (.32, .29, .10), paint)
box("Weather cap", (0, 0, 1.17), (.38, .34, .064), navy)
for z in (.59, .85):
    rod("Outlet collar", (0, -.13, z), (0, -.17, z), .084, rubber, 12)
    rod("Hinged socket cover", (0, -.17, z), (0, -.19, z), .072, navy, 12)
    box("Cover hinge", (0, -.18, z+.061), (.12, .04, .033), steel)
finish("power_pedestal", (-3, 3, 0))

# Deck edge at the origin. Positive Blender Y points out over the water.
box("Eye plate", (0, -.065, .015), (.12, .14, .03), steel)
rod("Fender line", (0, -.065, .03), (0, .132, -.13), .016, rope)
for z, radius, depth, mat in [(-.16,.044,.09,navy), (-.225,.088,.07,navy),
                              (-.43,.115,.36,ivory), (-.635,.089,.06,navy)]:
    rod("Fender", (0,.132,z-depth/2), (0,.132,z+depth/2), radius, mat, 16)
finish("fender", (-3, 4, 0))

# Open slatted fish crate with corner posts and a plank floor.
for x in (-.34, .34):
    for y in (-.23, .23):
        box("Corner post", (x,y,.21), (.055,.055,.42), timber)
for i in range(3):
    box("Floor plank", (0,(i-1)*.15,.032), (.70,.145,.064), boards[i])
    z = .075 + i*.138
    for side in (-1, 1):
        box("Long slat", (0,side*.265,z), (.77,.035,.113), boards[i])
        box("End slat", (side*.377,0,z), (.035,.50,.113), boards[3-i])
finish("fish_crate", (-3, 5, 0))

# Round wire pot with a recessed top-entry funnel and a weighted lower hoop.
def hoop(radius, z, thickness):
    bpy.ops.mesh.primitive_torus_add(major_segments=24, minor_segments=6,
                                     major_radius=radius, minor_radius=thickness,
                                     location=(0,0,z))
    bpy.context.object.data.materials.append(wire)


for z in (.021, .15, .28, .41):
    hoop(.50, z, .019 if z in (.021, .41) else .009)
hoop(.31, .41, .009)
hoop(.14, .24, .014)
for i in range(24):
    angle = math.tau*i/24
    x, y = math.cos(angle), math.sin(angle)
    rod("Cage upright", (.5*x,.5*y,.02), (.5*x,.5*y,.41), .009, wire, 6)
    if i % 2 == 0:
        rod("Lid spoke", (.50*x,.50*y,.41), (.31*x,.31*y,.41), .009, wire, 6)
        rod("Funnel", (.31*x,.31*y,.41), (.14*x,.14*y,.24), .009, wire, 6)
for i in range(-3, 4):
    offset = i*.125
    span = math.sqrt(.50**2-offset**2)
    rod("Base grid", (-span,offset,.02), (span,offset,.02), .009, wire, 6)
    rod("Base grid", (offset,-span,.02), (offset,span,.02), .009, wire, 6)
finish("crab_pot", (-3, 6.5, 0))

bpy.ops.object.select_all(action="DESELECT")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "art/dock_kit.blend"))
