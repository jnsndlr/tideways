"""Generate the waterfront depot, its game mesh and a three-quarter art preview."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def paint(name, hexcolor):
    srgb = tuple(int(hexcolor[i:i+2], 16)/255 for i in (0, 2, 4))
    linear = tuple(((v+.055)/1.055)**2.4 if v > .04045 else v/12.92 for v in srgb)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*linear, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*linear, 1)
    shader.inputs["Roughness"].default_value = .64
    return mat


siding = paint("Oyster clapboard", "d8c3a5")
trim = paint("Buttermilk joinery", "f3d6a2")
wood = paint("Honey cedar", "a96b3c")
roof = paint("Patinated sheet metal", "467977")
seam = paint("Folded seams", "67938b")
rail = paint("Harbor teal", "16665f")
glass = paint("Deep inlet glass", "254d52")
amber = paint(" lamplight".strip().title(), "ffc16a")
warm = paint("Warm ground-floor panes", "c88746")
brick = paint("Fired brick", "b35436")
stone = paint("Sandstone paving", "bdab92")
iron = paint("Bronze fittings", "57472e")

# Assemble each architectural element as an editable mesh in the source file.
pieces = []


def box(name, loc, size, mat, tilt=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.rotation_euler.x = tilt
    ob.data.materials.append(mat)
    pieces.append(ob)
    return ob


def beam(name, a, b, width, mat):
    delta = Vector(b) - Vector(a)
    ob = box(name, (Vector(a)+Vector(b))*.5, (width,width,delta.length), mat)
    ob.rotation_euler = delta.to_track_quat("Z","Y").to_euler()


def roof_half(x0,x1,y0,y1,z0,z1):
    angle = math.atan((z1-z0)/(y1-y0))
    length = math.hypot(y1-y0,z1-z0)
    center = ((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
    box("Roof pan",center,(x1-x0,length,.13),roof,angle)
    count = round((x1-x0)/.32)
    for i in range(count+1):
        x = x0+(x1-x0)*i/count
        box("Standing seam",(x,center[1],center[2]+.075),(.034,length,.04),seam,angle)
    for x in [x0,x1]:
        box("Rake board",(x,center[1],center[2]-.035),(.13,length+.1,.20),trim,angle)


def gable(x0,x1,half,eave,rise):
    for side in (-1,1):
        roof_half(x0,x1,0,side*half,eave+rise,eave)
        box("Eave",( (x0+x1)/2,side*half,eave-.04),(x1-x0+.12,.13,.19),trim)
    box("Ridge cap",((x0+x1)/2,0,eave+rise+.06),(x1-x0+.12,.15,.10),seam)


# Ground origin at the centre of the paved apron.
box("Platform footing",(0,0,.13),(13.8,9.5,.26),wood)
for i in range(12):
    for j in range(5):
        box("Platform slab",(-6.325+1.15*i,-3.8+1.9*j,.26),(1.14,1.89,.14),stone)
box("Main volume",(1.9,.55,3.25),(8.3,5.6,5.85),siding)
for i in range(22):
    box("Clapboard lap",(1.9,.55,.53+i*.26),(8.34,5.64,.045),siding)
for x in (-2.25,6.05):
    for y in (-2.25,3.35):
        box("Corner board",(x,y,3.25),(.20,.20,5.85),trim)

# Roof ridges run lengthwise over both the hall and the open end porch.
def centered_gable(x0,x1,half,eave,rise):
    start = len(pieces)
    gable(x0,x1,half,eave,rise)
    for ob in pieces[start:]:
        ob.location.y += .55


for x in (-2.25,6.05):
    mesh = bpy.data.meshes.new("Pediment")
    verts = [(x,-2.25,6.12),(x,3.35,6.12),(x,.55,8.1)]
    mesh.from_pydata(verts,[],[(0,2,1) if x<0 else (0,1,2)])
    ob = bpy.data.objects.new("Gable infill",mesh)
    scene.collection.objects.link(ob)
    mesh.materials.append(siding)
    pieces.append(ob)
    for i in range(-8,9):
        y = .55+i*.30
        h = 1.9*(1-abs(i*.30)/2.8)
        box("Gable batten",(x,y,6.12+h/2),(.075,.045,h),trim)
centered_gable(-2.66,6.46,3.15,6.02,2.22)
centered_gable(-6.65,-2.21,3.04,3.06,1.06)
roof_half(-2.37,6.52,-4.42,-2.18,3.02,3.52)
box("Veranda fascia",(2.08,-4.42,2.98),(9.02,.14,.23),trim)


def window(x,y,z,w,h,end=0,arched=False):
    # Local u follows the wall, positive d faces outwards.
    def layer(name,u,d,v,width,depth,height,mat):
        if end:
            box(name,(x+end*d,y+u,z+v),(depth,width,height),mat)
        else:
            box(name,(x+u,y-d,z+v),(width,depth,height),mat)
    layer("Sash surround",0,.055,0,w+.20,.14,h+.19,trim)
    layer("Recessed sash",0,.135,0,w,.065,h,glass)
    if arched:
        layer("Amber transom glass",0,.174,h*.28,w-.10,.025,h*.32,warm)
        for side in (-1,1):
            # Shaped spandrel corners read as a segmental arch at map scale.
            ob_count = len(pieces)
            layer("Arched sash corner",side*w*.445,.194,h*.43,w*.22,.04,h*.13,trim)
            if not end:
                pieces[ob_count].rotation_euler.y = side*-.48
    layer("Meeting rail",0,.205,h*.12,w,.055,.075,trim)
    layer("Glazing bar",0,.21,0,.07,.06,h,trim)
    layer("Projecting sill",0,.13,-h*.52,w+.29,.27,.105,trim)


for x in (-1.18,.83,2.84,4.85):
    window(x,-2.27,4.80,1.32,1.38)
    window(x,-2.27,1.85,1.38,1.96,arched=True)
for x in (-1.1,1.0,3.1,5.0):
    for z in (1.83,4.80):
        # Rear uses the same sash rotated around its wall centre.
        start = len(pieces)
        window(x,3.35,z,1.18,1.4)
        for ob in pieces[start:]:
            ob.location.y = 6.70-ob.location.y
for x,side in ((-2.27,-1),(6.07,1)):
    for y in (-1.12,2.22):
        for z in (1.75,4.90):
            window(x,y,z,.72,1.18,side)
    window(x,.55,6.78,.65,.79,side)
    box("Entry casing",(x+side*.09,.55,1.57),(.18,1.48,2.48),trim)
    box("Paneled entry",(x+side*.20,.55,1.56),(.10,1.21,2.33),rail)
    box("Entry light",(x+side*.26,.55,2.02),(.045,.89,.87),warm)
    box("Brass latch",(x+side*.29,.12,1.44),(.06,.09,.20),amber)

for x,y in [(-6.35,-2.25),(-6.35,3.35),(-2.18,-4.18),(.65,-4.18),(3.51,-4.18),(6.27,-4.18)]:
    box("Porch column",(x,y,1.70),(.20,.20,2.74),trim)
    box("Painted post boot",(x,y,.70),(.31,.31,.75),rail)
    for dx in (-.48,.48):
        if -6.50 < x+dx < 6.45:
            beam("Knee brace",(x,y,2.47),(x+dx,y,2.97),.13,wood)
for y in (-2.25,3.35):
    beam("End porch bracket",(-6.35,y,2.48),(-6.35,y+(.65 if y<0 else -.65),3.29),.16,wood)
for x in (-6.48,-4.5,-2.52,-.54,1.44,3.42,5.40,6.48):
    box("Promenade stanchion",(x,-4.49,.85),(.15,.15,1.04),rail)
for z in (.67,1.28):
    box("Promenade rail",(0,-4.49,z),(13,.10,.105),rail)
# Open ends provide pedestrian access to the platform.
for y in (-1.04,2.14):
    x = -6.30
    top = 3.06+1.06*(1-abs(y-.55)/3.04)
    beam("Pendant chain",(x,y,top),(x,y,top-.40),.045,iron)
    box("Lantern cap",(x,y,top-.43),(.28,.28,.12),iron)
    box("Lantern glass",(x,y,top-.62),(.21,.21,.29),amber)
    box("Lantern foot",(x,y,top-.79),(.20,.20,.075),iron)
for y in (-1.25,2.30):
    box("Bench seat",(-4.55,y,.84),(1.80,.43,.15),wood)
    for dx in (-.67,.67):
        box("Bench leg",(-4.55+dx,y,.57),(.13,.34,.47),rail)
    box("Bench back",(-4.55,y+.19,1.09),(1.80,.10,.44),wood)

box("Chimney stack",(4.6,.32,8.28),(.86,.83,2.48),brick)
for z,size in ((9.29,1.02),(9.46,1.09)):
    box("Corbelled crown",(4.6,.32,z),(size,size,.15),brick)
box("Flue opening",(4.6,.32,9.54),(.63,.60,.04),iron)

bpy.ops.object.select_all(action="SELECT")
bpy.context.view_layer.objects.active = pieces[0]
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art/waterfront_depot.blend"))
bpy.ops.object.join()
bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
bpy.context.object.name = "Waterfront Depot"
bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets/models/waterfront_depot.glb"),use_selection=True)

box("Studio floor",(0,0,-.09),(200,200,.16),paint("Backdrop","d6ded9"))
scene.world = bpy.data.worlds.new("Daylight")
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.78,.83,.90,1)
scene.world.node_tree.nodes["Background"].inputs[1].default_value = .65
bpy.ops.object.light_add(type="AREA", location=(-8,-13,22))
key = bpy.context.object
key.rotation_euler = (-key.location).to_track_quat("-Z","Y").to_euler()
key.data.energy = 4600
key.data.shape = "DISK"
key.data.size = 9
bpy.ops.object.camera_add(location=(-18,-28,12.0))
cam = bpy.context.object
cam.rotation_euler = (Vector((0,0,4.05))-cam.location).to_track_quat("-Z","Y").to_euler()
cam.data.type = "ORTHO"
cam.data.ortho_scale = 18.9
scene.camera = cam
scene.render.engine = "CYCLES"
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x,scene.render.resolution_y = 900,680
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT/"art/waterfront_depot_preview.png")
bpy.ops.render.render(write_still=True)
