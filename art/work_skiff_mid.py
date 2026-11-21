"""Build the aluminum work skiff. Run blender -b -P art/work_skiff_mid.py."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pusher_mid import ROOT, Part, annulus, block, pipe, rect

ALLOY, EDGE, FLOOR = "a1a6a4", "cbd0ca", "777d78"
DARK, RUBBER, SEAM = "272f33", "232729", "727c7c"
RED, WHITE = "bb4333", "e6e5da"

# Station values are longitudinal position, half-beam, sheer height, keel height
# and the rake of the bottom aft of the stem. All dimensions are in metres.
STATIONS = [(-3.12, 1.00, 0.98, -0.32, 0.24),
            (-2.74, 1.04, 0.72, -0.35, 0.03),
            (-1.55, 1.07, 0.67, -0.38, 0.00),
            (0.20, 1.09, 0.67, -0.39, 0.00),
            (1.53, 1.07, 0.71, -0.37, -0.05),
            (2.47, 0.98, 0.82, -0.30, -0.20),
            (3.21, 0.74, 0.93, -0.06, -0.48)]


def tapered_plate(part, profile, y, thickness, color):
    # CCW in the x,z plane faces -y.
    part.loft([[(x, v, z) for x, z in reversed(profile)]
               for v in (y-thickness/2, y+thickness/2)], color)


def skiff_hull():
    hull = Part("Welded hull")
    soft = Part("Rub rails and nonskid")
    rings = []
    gunwales = []
    strakes = []
    for x, w, sheer, keel, rake in STATIONS:
        floor = max(0.15, keel+0.35)
        chine = (x+rake, w*0.83, keel+0.20)
        boot = (x+rake*0.74, w*0.90, max(0.14, keel+0.25))
        rail = (x, w, sheer)
        side = [chine, boot, rail, (x, w-0.11, sheer-0.015),
                (x+rake*0.50, w*0.78, floor)]
        rings.append([(x+rake, 0, keel)] + side + [(a,-b,c) for a,b,c in reversed(side)])
        gunwales.append(rail)
        strakes.append(Vector(boot).lerp(Vector(rail), 0.41))
    # Close each end, including the recessed cockpit floor.
    hull.loft(rings, lambda row,i: [DARK, DARK, ALLOY, EDGE, "8b9391", FLOOR,
                                   "8b9391", EDGE, ALLOY, DARK, DARK][i], top=ALLOY)
    for side in (-1, 1):
        for points, part, r, code in [(gunwales, soft, 0.056, RUBBER),
                                      (strakes, hull, 0.025, EDGE)]:
            curve = [(x, side*y, z) for x,y,z in points]
            for a,b in zip(curve, curve[1:]):
                pipe(part, a, b, r, code, 10)
        # Inside face of the welded frames is visible down the open cockpit.
        for x,w,h,_,_ in STATIONS[2:6]:
            pipe(hull, (x, side*w*0.80, 0.18), (x, side*(w-0.11), h-0.03), 0.028, SEAM, 5)
    # Fore and aft decks bridge the cockpit, with a low central engine transom.
    hull.loft([rect(2.82,0,0.29,0.69,1.49,0.05), rect(2.85,0,0.74,0.70,1.55,0.05)], ALLOY, top=FLOOR)
    block(hull,-2.83,0,0.19,0.57,1.77,0.40,ALLOY,0.07)
    # Raised stern quarters to either side of the motor well.
    for side in (-1,1):
        tapered_plate(hull, [(-3.15,0.51),(-2.63,0.50),(-2.72,0.68),(-3.22,0.98)],
                      side*0.91, 0.17, ALLOY)
        # Bow pusher knees with tapered steel cheeks and blunt rubber pads.
        tapered_plate(hull, [(2.76,0.26),(3.36,0.22),(3.36,1.19),(3.21,1.19),(3.07,0.88)],
                      side*0.62, 0.14, ALLOY)
        block(soft,3.39,side*0.62,0.19,0.12,0.21,1.03,RUBBER,0.023)
        for z in (0.34,1.10):
            pipe(hull,(3.27,side*0.692,z),(3.27,side*0.705,z),0.032,EDGE,8)
    # Folded bow plate follows the rake from the cockpit sole to the transverse rub rail.
    hull.loft([rect(2.98,0,0.29,0.10,1.17),rect(3.16,0,0.87,0.10,1.49),
               rect(3.16,0,0.92,0.10,1.49)], ALLOY, top=EDGE)
    annulus(hull,(3.23,0,0.66),(0,1,0),0.080,0.046,0.045,SEAM,count=12)
    pipe(soft, (3.207,-0.73,0.92),(3.207,0.73,0.92),0.057,RUBBER,10)
    # Removable sole panels with dark seams and recessed pull handles.
    for x in (0.70,1.78):
        block(soft,x,0,0.151,1.02,1.28,0.024,SEAM,0.05)
        block(soft,x,0,0.175,0.98,1.24,0.014,"929892",0.04)
        block(soft,x+0.33,0,0.190,0.055,0.15,0.006,DARK,0.016)
    return hull, soft


def pilothouse():
    frame, glass, fittings = Part("Aluminum helm shelter"), Part("Windshield glazing"), Part("Helm and fittings")
    # Short three-sided wheelhouse is open aft under a much longer canopy.
    block(frame,-0.40,0,0.15,0.83,1.04,0.73,ALLOY,0.05)
    block(frame,0,0,0.87,0.068,1.02,0.15,ALLOY)
    for side in (-1,1):
        tapered_plate(frame,[(-0.83,0.80),(0.04,0.80),(0.04,1.11),(-0.77,1.06)],
                      side*0.49,0.085,ALLOY)
    corners = [(0.00,-0.49),(0.00,0.49),(-0.80,0.49),(-0.80,-0.49)]
    def window_ring(z):
        return [(x+(z-1)*0.034 if x==0 else x, y,z) for x,y in corners]
    lo, hi = window_ring(1.01), window_ring(1.94)
    for i,j in [(0,1),(1,2),(3,0)]:
        # Broad plates around the rubber-gasketed, clipped-corner glazing.
        a,b,c,d = [Vector(p) for p in (lo[i],lo[j],hi[j],hi[i])]
        def point(u,v):
            return a.lerp(d,v).lerp(b.lerp(c,v),u)
        cut = [(0.12,0.11),(0.88,0.11),(0.925,0.16),(0.925,0.83),
               (0.88,0.88),(0.12,0.88),(0.075,0.83),(0.075,0.16)]
        edges = [(0,0),(1,0),(1,0),(1,1),(1,1),(0,1),(0,1),(0,0)]
        outline = [point(u,v) for u,v in cut]
        for k in range(8):
            n=(k+1)%8
            face=[point(*edges[k]),point(*edges[n]),outline[n],outline[k]]
            if edges[k]==edges[n]:
                face.pop(1)
            frame.face([frame.vertex(p) for p in face], ALLOY)
            pipe(fittings,outline[k],outline[n],0.017,RUBBER,8)
        glass.face([glass.vertex(p) for p in outline], "adbfbf")
    # External wiper on the front pane.
    pipe(fittings,(0.045,0.36,1.79),(0.026,0.01,1.25),0.010,DARK,6)
    pipe(fittings,(0.026,-0.18,1.24),(0.026,0.17,1.29),0.013,RUBBER,6)
    for a,b in zip(lo,hi):
        pipe(frame,a,b,0.029,EDGE,8)
    # Crown the sheet roof and fold its edges down into a dark drip lip.
    frame.loft([rect(-0.97,0,1.93,2.46,1.50,0.19),rect(-0.97,0,1.97,2.52,1.55,0.19),
                rect(-0.97,0,2.08,2.45,1.49,0.18),rect(-0.96,0,2.14,2.22,1.22,0.16)],
               lambda row,i: [DARK,ALLOY,EDGE][row],top="ccd0c8")
    for side in (-1,1):
        y=side*0.62
        pipe(frame,(-2.10,y,0.18),(-2.10,y,1.97),0.033,EDGE)
        pipe(frame,(-2.09,y,1.49),(-1.46,y,0.67),0.027,ALLOY)
        pipe(frame,(-2.10,y,0.57),(-0.82,side*0.51,1.50),0.025,ALLOY)
    pipe(frame,(-0.03,0,2.11),(-0.03,0,2.37),0.035,ALLOY)
    pipe(fittings,(-0.03,0,2.32),(-0.03,0,2.42),0.064,WHITE,12)
    for side,color in [(-1,"488568"),(1,"bd4534")]:
        block(fittings,-0.24,side*0.75,1.974,0.14,0.055,0.07,color,0.019)
    block(fittings,0.27,0,1.972,0.047,0.60,0.09,DARK,0.014)
    block(fittings,0.296,0,1.994,0.012,0.53,0.04,WHITE)
    # Bench, dash, gauges, throttle and wheel can be seen through the glass.
    block(frame,-0.69,0,0.85,0.41,0.90,0.18,ALLOY,0.035)
    pipe(frame,(-1.21,0,0.15),(-1.21,0,0.64),0.068,ALLOY)
    block(fittings,-1.22,0,0.64,0.49,0.60,0.12,DARK,0.08)
    block(fittings,-1.46,0,0.73,0.11,0.60,0.42,DARK,0.05)
    hub=Vector((-0.99,0.04,1.10))
    axis=Vector((-0.86,0,0.50)).normalized()
    pipe(frame,hub-axis*0.21,hub,0.04,SEAM)
    annulus(fittings,hub,axis,0.165,0.143,0.038,RUBBER,count=16)
    for angle in (90,210,330):
        theta=math.radians(angle)
        spoke=Vector((0,1,0))*math.cos(theta)+axis.cross(Vector((0,1,0)))*math.sin(theta)
        pipe(frame,hub,hub+spoke*0.151,0.012,ALLOY,6)
    for y in (-0.23,-0.08):
        pipe(fittings,(-0.77,y,1.03),(-0.77,y,1.053),0.056,DARK,12)
    pipe(frame,(-0.70,-0.34,1.03),(-0.78,-0.34,1.20),0.014,ALLOY)
    pipe(fittings,(-0.79,-0.37,1.20),(-0.79,-0.31,1.20),0.029,DARK)
    # Ring buoy with four white grab bands hangs on the aft canopy frame.
    center=Vector((-1.95,0.47,0.85))
    axis=Vector((0,1,0))
    annulus(fittings,center,axis,0.28,0.165,0.087,"d4582c",count=24)
    for i in range(4):
        angle=math.radians(45+90*i)
        offset=Vector((math.cos(angle),0,math.sin(angle)))
        pipe(fittings,center+offset*0.167,center+offset*0.278,0.052,WHITE,8)
    return frame, glass, fittings


def motors():
    metal, cowl = Part("Twin outboard legs"), Part("Outboard cowlings")
    for y in (-0.45,0.45):
        block(metal,-3.12,y,0.12,0.27,0.25,0.43,SEAM,0.04)
        pipe(metal,(-3.16,y,0.39),(-3.38,y,0.22),0.075,DARK)
        metal.loft([rect(-3.39,y,-0.47,0.23,0.10,0.035),
                    rect(-3.37,y,0.12,0.25,0.17,0.04),rect(-3.34,y,0.36,0.36,0.27,0.055)],DARK)
        block(metal,-3.42,y,-0.35,0.50,0.27,0.03,SEAM,0.03)
        pipe(metal,(-3.30,y,-0.46),(-3.68,y,-0.46),0.072,DARK,10)
        for i in range(3):
            a=math.tau*i/3
            tip=Vector((-3.63,y+0.116*math.cos(a),-0.46+0.116*math.sin(a)))
            pipe(metal,(-3.61,y,-0.46),tip,0.040,ALLOY,6,0.021)
        cowl.loft([rect(-3.32,y,0.30,0.50,0.35,0.07),rect(-3.33,y,0.43,0.63,0.41,0.09),
                   rect(-3.35,y,0.70,0.63,0.43,0.10),rect(-3.37,y,0.87,0.52,0.38,0.095),
                   rect(-3.37,y,0.91,0.40,0.29,0.09)],
                  lambda row,i: ["343e43","252c33","30373d","444c50"][row],top="444c50")
        for s in (-1,1):
            tapered_plate(cowl,[(-3.54,0.54),(-3.13,0.60),(-3.12,0.63),(-3.50,0.59)],
                          y+s*0.212,0.009,"bfc4be")
    return metal,cowl


def deck_gear():
    gear=Part("Mooring gear")
    # A compact red line drum stands out against the alloy foredeck.
    for y in (-0.17,0.17):
        block(gear,2.80,y,0.74,0.31,0.052,0.16,RED,0.02)
        pipe(gear,(2.80,y-0.024,0.88),(2.80,y+0.024,0.88),0.137,RED,16)
    pipe(gear,(2.80,-0.15,0.88),(2.80,0.15,0.88),0.083,"7e755c",14)
    for i in range(6):
        annulus(gear,(2.80,-0.125+i*0.05,0.88),(0,1,0),0.091,0.081,0.031,"a99c78",count=12)
    for x,w,z in [(2.44,0.92,0.81),(-2.58,0.98,0.72)]:
        for side in (-1,1):
            y=side*w
            for dx in (-0.061,0.061):
                pipe(gear,(x+dx,y,z),(x+dx,y,z+0.087),0.025,SEAM)
            pipe(gear,(x-0.14,y,z+0.086),(x+0.14,y,z+0.086),0.029,ALLOY)
    return gear


def make_palette(parts):
    swatches = sorted({color for part in parts for color in part.colors})
    image = bpy.data.images.new("Skiff paint", width=len(swatches), height=1, alpha=False)
    image.pixels[:] = [channel for code in swatches
                       for channel in (*[c / 255 for c in bytes.fromhex(code)], 1.0)]
    image.pack()
    return image, {code: (i+0.5)/len(swatches) for i,code in enumerate(swatches)}


def finish(material_name, parts, palette, metal, roughness, opacity=1.0):
    mat=bpy.data.materials.new(material_name)
    mat.use_nodes=True
    image, swatches = palette
    paint=mat.node_tree.nodes.new("ShaderNodeTexImage")
    paint.image=image
    paint.interpolation="Closest"
    shader=mat.node_tree.nodes.get("Principled BSDF")
    mat.node_tree.links.new(paint.outputs["Color"],shader.inputs["Base Color"])
    shader.inputs["Metallic"].default_value=metal
    shader.inputs["Roughness"].default_value=roughness
    shader.inputs["Alpha"].default_value=opacity
    if opacity < 1:
        mat.surface_render_method="BLENDED"
        mat.use_backface_culling=False
    objects=[]
    for part in parts:
        obj=part.finish(bpy.context.scene.collection,mat)
        uv=obj.data.uv_layers.new(name="Paint")
        for face,code in zip(obj.data.polygons,part.colors):
            for corner in face.loop_indices:
                uv.uv[corner].vector=(swatches[code],0.5)
        objects.append(obj)
    return objects


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    shell, rubber=skiff_hull()
    shelter,glass,helm=pilothouse()
    legs,cowls=motors()
    hardware=[rubber,helm,cowls,deck_gear()]
    aluminum=[shell,shelter,legs]
    palette=make_palette(aluminum+hardware+[glass])
    hull,*rest=finish("Satin marine aluminum",aluminum,palette,0.55,0.40)
    rest+=finish("Marine fittings",hardware,palette,0.14,0.51)
    rest+=finish("Tinted safety glass",[glass],palette,0.08,0.16,0.32)
    for obj in rest:
        obj.parent=hull
    bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets/models/work_skiff_mid.glb"),
                              export_format="GLB",export_vertex_color="NONE")

    # Photograph both construction boats on the same studio water.
    with bpy.data.libraries.load(str(ROOT/"art/barge_construction.blend")) as (src,dst):
        dst.collections=["Preview studio"]
        dst.worlds=["Overcast sky"]
    studio=dst.collections[0]
    scene.collection.children.link(studio)
    scene.world=dst.worlds[0]
    camera=next(o for o in studio.objects if o.type=="CAMERA")
    key=next(o for o in studio.objects if o.type=="LIGHT")
    target=Vector((0,0.08,0.90))
    camera.location=target+Vector((10,-5.9,3.8))
    camera.rotation_euler=(target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.ortho_scale=8.9
    scene.camera=camera
    key.location=(4, -4, 7)
    key.rotation_euler=(-key.location).to_track_quat("-Z","Y").to_euler()
    key.data.energy=980
    key.data.size=5
    for obj in studio.objects:
        obj.hide_set(True)
    scene.render.engine="CYCLES"
    scene.cycles.samples=36
    scene.cycles.use_denoising=True
    scene.render.resolution_x,scene.render.resolution_y=1400,900
    scene.render.resolution_percentage=100
    scene.render.filepath="//work_skiff_preview.png"
    for area in bpy.context.screen.areas:
        if area.type=="VIEW_3D":
            view=area.spaces.active
            view.shading.color_type="VERTEX"
            view.overlay.show_overlays=False
            view.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
            view.region_3d.view_location=target
            view.region_3d.view_distance=8.4
            view.region_3d.view_perspective="ORTHO"
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art/work_skiff.blend"),compress=True)
    bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    build()
