"""Editable Fire Station & Small Fire Truck kit.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python art/fire_station_kit.py

Exports individual GLB assets to assets/models/fire_station_kit/:
  - fire_station.glb  (2-bay station with animated overhead doors & exterior warning beacons)
  - fire_truck.glb    (compact pumper truck with animated lightbar/flashers & aimable deck hose)
  - fire_hydrant.glb  (classic street hydrant)
  - hose_reel.glb     (free-standing hose reel prop)
  - traffic_cone.glb  (safety cone prop)

Also saves art/fire_station_kit.blend and renders art/fire_station_kit_preview.png.
"""
from math import atan2, cos, hypot, pi, radians, sin
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/fire_station_kit"
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 96


def paint(name, hex_color, roughness=0.72, metallic=0.0, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    rgb = [int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    mat.diffuse_color = (*lin, 1.0)
    mat.use_nodes = True
    shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*lin, 1.0)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    if emission_strength > 0.0:
        if 'Emission Color' in shader.inputs:
            shader.inputs['Emission Color'].default_value = (*lin, 1.0)
            shader.inputs['Emission Strength'].default_value = emission_strength
        elif 'Emission' in shader.inputs:
            shader.inputs['Emission'].default_value = (*lin, 1.0)
    return mat


# Shared Tideways-harmonized firehouse palette
brick = paint('Firehouse brick', '9e3b33', roughness=0.82)
brick_dark = paint('Brick trim', '782a25', roughness=0.84)
cream = paint('Salt white stucco', 'efe7d2', roughness=0.76)
white = paint('White enamel trim', 'fff9ea', roughness=0.58)
roof_slate = paint('Slate roof', '3a4954', roughness=0.74)
roof_seam = paint('Roof seam', '526572', roughness=0.68)
navy = paint('Deep navy', '223847', roughness=0.65)
concrete = paint('Apron concrete', 'aba698', roughness=0.88)
interior_dark = paint('Bay interior', '2a2e33', roughness=0.92)
glass = paint('Harbour glass', '5e8b97', roughness=0.22)
truck_red = paint('Fire engine red', 'cc241d', roughness=0.35)
truck_red_dark = paint('Engine deep red', '941914', roughness=0.45)
chrome = paint('Brushed chrome', 'd5dce0', roughness=0.25, metallic=0.88)
steel = paint('Painted steel', '5d6b73', roughness=0.50, metallic=0.45)
rubber = paint('Tire rubber', '222528', roughness=0.86)
brass = paint('Polished brass', 'd9a441', roughness=0.30, metallic=0.85)
yellow_stripe = paint('Safety yellow', 'f2c12e', roughness=0.48)
cone_orange = paint('Safety orange', 'f05d23', roughness=0.55)
hose_canvas = paint('Canvas hose', 'd8ceb8', roughness=0.82)

# Emissive light materials (distinct so Godot can also drive emission independently)
glow_red_a = paint('Beacon red A', 'ff2418', roughness=0.18, emission_strength=6.0)
glow_red_b = paint('Beacon red B', 'ff2418', roughness=0.18, emission_strength=6.0)
glow_blue = paint('Beacon blue', '1e88ff', roughness=0.18, emission_strength=6.0)
glow_amber = paint('Beacon amber', 'ff9d14', roughness=0.18, emission_strength=5.5)
glow_white = paint('Headlight white', 'fff6d6', roughness=0.15, emission_strength=4.5)
glow_station = paint('Station alarm red', 'ff2a1a', roughness=0.18, emission_strength=6.5)


def link_obj(obj, parent=None):
    if obj.name not in scene.collection.objects:
        scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, location=(0, 0, 0), parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = 0.4
    obj.location = location
    return link_obj(obj, parent)


def box(name, center, size, mat, parent=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = rot
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    return obj


def cyl(name, center, radius, depth, mat, verts=16, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=center, rotation=rot
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    return obj


def sphere(name, center, radius, mat, segs=12, rings=8, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segs, ring_count=rings, radius=radius, location=center
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    return obj


def cone(name, center, r1, r2, depth, mat, verts=14, rot=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cone_add(
        vertices=verts, radius1=r1, radius2=r2, depth=depth, location=center, rotation=rot
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    return obj


def beam(name, a, b, width, mat, parent=None):
    d = Vector(b) - Vector(a)
    obj = box(name, (Vector(a) + Vector(b)) / 2, (width, width, d.length), mat, parent=parent)
    obj.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return obj


def sign(body, x, y, z, height, mat, parent=None):
    bpy.ops.object.text_add(location=(x, y, z), rotation=(pi / 2, 0, 0))
    obj = bpy.context.object
    obj.data.body = body
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.size = height
    obj.data.space_character = 1.12
    obj.data.extrude = 0.02
    obj.data.materials.append(mat)
    bpy.ops.object.convert(target='MESH')
    obj.name = body
    if parent is not None:
        obj.parent = parent
    return obj


def window(x, y, z, w=1.4, h=1.5, side=False, parent=None):
    for name, offset, width, height, mat in [
        ('WinCasing', 0.0, w, h, white),
        ('WinSash', 0.06, w - 0.16, h - 0.16, navy),
        ('WinGlass', 0.095, w - 0.28, h - 0.28, glass),
        ('WinMullion', 0.13, 0.06, h - 0.16, white),
        ('WinRail', 0.14, w - 0.16, 0.07, white),
    ]:
        pos = (x + offset, y, z) if side else (x, y - offset, z)
        dims = (0.10, width, height) if side else (width, 0.10, height)
        box(name, pos, dims, mat, parent=parent)


def gable(x, y, w, d, eave, rise, wall_mat, roof_mat, seam_mat, parent=None):
    verts = [
        (x + dx, y + dy, eave + h)
        for dy in (-d / 2, d / 2)
        for dx, h in ((-w / 2, 0), (w / 2, 0), (0, rise))
    ]
    mesh = bpy.data.meshes.new('GableInfill')
    mesh.from_pydata(verts, [], [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
    obj = bpy.data.objects.new('GableInfill', mesh)
    link_obj(obj, parent)
    mesh.materials.append(wall_mat)
    for s in (-1, 1):
        span = w / 2 + 0.36
        drop = rise * span / (w / 2)
        panel = box(
            'RoofPlane',
            (x + s * span / 2, y, eave + rise - drop / 2 + 0.09),
            (hypot(span, drop), d + 0.65, 0.18),
            roof_mat,
            parent=parent,
        )
        panel.rotation_euler.y = s * atan2(drop, span)
        steps = max(2, round(d / 1.4))
        for i in range(steps + 1):
            yp = y - d / 2 + i * d / steps
            beam(
                'RoofSeam',
                (x, yp, eave + rise + 0.19),
                (x + s * span, yp, eave + rise - drop + 0.19),
                0.055,
                seam_mat,
                parent=parent,
            )


def key_flash(obj, start_frame, end_frame, period=8, phase=0, active_scale=1.0, off_scale=0.05):
    """Keyframe a beacon glow bulb to flash on/off during [start_frame, end_frame]."""
    obj.scale = (off_scale, off_scale, off_scale)
    obj.keyframe_insert(data_path='scale', frame=1)
    if start_frame > 2:
        obj.keyframe_insert(data_path='scale', frame=start_frame - 1)
    f = start_frame
    while f <= end_frame:
        on = ((f - start_frame + phase) // (period // 2)) % 2 == 0
        s = active_scale if on else off_scale
        obj.scale = (s, s, s)
        obj.keyframe_insert(data_path='scale', frame=f)
        f += period // 2
    if end_frame < scene.frame_end:
        obj.scale = (off_scale, off_scale, off_scale)
        obj.keyframe_insert(data_path='scale', frame=min(scene.frame_end, end_frame + 2))
        obj.keyframe_insert(data_path='scale', frame=scene.frame_end)


# ---------------------------------------------------------------------------
# 1. FIRE STATION (compact 1-story 2-bay firehouse + bell cupola + doors & lights)
# ---------------------------------------------------------------------------
def make_fire_station():
    root = empty('FireStationRoot', (0, 0, 0))
    static = empty('StationStructure', (0, 0, 0), parent=root)

    # Concrete apron & foundation
    box('ApronSlab', (0, -1.8, 0.10), (13.4, 13.6, 0.20), concrete, parent=static)
    box('ApronStripeL', (-2.15, -7.0, 0.205), (0.14, 3.2, 0.015), yellow_stripe, parent=static)
    box('ApronStripeR', (2.15, -7.0, 0.205), (0.14, 3.2, 0.015), yellow_stripe, parent=static)

    # Compact 1-story firehouse shell (W=10.6, D=8.8, H=4.15) with real recessed apparatus bays
    box('WallRear', (0, 4.25, 2.18), (10.6, 0.30, 3.96), brick, parent=static)
    box('WallLeft', (-5.15, 0, 2.18), (0.30, 8.8, 3.96), brick, parent=static)
    box('WallRight', (5.15, 0, 2.18), (0.30, 8.8, 3.96), brick, parent=static)
    box('BayFloor', (0, 0.15, 0.21), (10.0, 8.2, 0.04), interior_dark, parent=static)
    box('BayCeiling', (0, 0.15, 3.75), (10.0, 8.2, 0.16), interior_dark, parent=static)

    # Front piers framing two 3.2m-wide x 3.1m-high apparatus bays (centered at x = -2.15, +2.15)
    box('FrontPierLeft', (-4.52, -4.25, 1.80), (1.56, 0.36, 3.20), brick, parent=static)
    box('FrontPierCenter', (0.0, -4.25, 1.80), (1.10, 0.36, 3.20), brick, parent=static)
    box('FrontPierRight', (4.52, -4.25, 1.80), (1.56, 0.36, 3.20), brick, parent=static)
    # Front header band above doors
    box('FrontHeaderWall', (0, -4.25, 3.78), (10.6, 0.36, 0.78), brick, parent=static)

    # Cornice & corner quoins
    box('CorniceFront', (0, -4.40, 4.10), (11.0, 0.32, 0.22), white, parent=static)
    for x in (-5.22, 5.22):
        for y in (-4.32, 4.32):
            box('CornerQuoin', (x, y, 2.18), (0.26, 0.26, 3.96), cream, parent=static)

    # Gable roof over 1-story station
    gable(0, 0, 10.6, 8.8, 4.15, 2.05, brick, roof_slate, roof_seam, parent=static)

    # Side ground-floor windows
    for y in (-2.0, 1.6):
        window(5.30, y, 2.10, 1.35, 1.30, side=True, parent=static)

    # Signboard centered in the front gable above the bays
    box('SignBoard', (0, -4.46, 4.82), (5.6, 0.16, 0.62), navy, parent=static)
    sign('FIRE STATION', 0, -4.55, 4.82, 0.37, white, parent=static)
    for bx, label in ((-2.15, 'BAY 1'), (2.15, 'BAY 2')):
        box('BayPlate', (bx, -4.45, 3.66), (1.18, 0.12, 0.28), navy, parent=static)
        sign(label, bx, -4.52, 3.66, 0.17, white, parent=static)

    # Compact rooftop bell cupola on the ridge
    cx, cy = 0.0, 0.4
    box('CupolaBase', (cx, cy, 6.22), (1.95, 1.95, 0.55), white, parent=static)
    for sx in (-0.78, 0.78):
        for sy in (-0.78, 0.78):
            box('CupolaPost', (cx + sx, cy + sy, 6.98), (0.16, 0.16, 1.05), white, parent=static)
    cone('FireBell', (cx, cy, 6.96), 0.34, 0.14, 0.48, brass, verts=16, parent=static)
    sphere('BellClapper', (cx, cy, 6.70), 0.08, brass, parent=static)
    cone(
        'CupolaSpire',
        (cx, cy, 8.05),
        1.55,
        0.0,
        1.15,
        roof_slate,
        verts=4,
        rot=(0, 0, pi / 4),
        parent=static,
    )

    # Bay door frames & animated overhead doors (pivot at top header z=3.30, y=-4.16)
    door_pivots = []
    for side_name, bx in (('BayDoorLeft', -2.15), ('BayDoorRight', 2.15)):
        # Frame jambs
        box(f'{side_name}JambL', (bx - 1.60, -4.34, 1.75), (0.15, 0.24, 3.12), white, parent=static)
        box(f'{side_name}JambR', (bx + 1.60, -4.34, 1.75), (0.15, 0.24, 3.12), white, parent=static)
        box(f'{side_name}Header', (bx, -4.34, 3.36), (3.35, 0.24, 0.16), white, parent=static)

        # Pivot at top of doorway so rotating +86 deg around X swings it cleanly up & inside
        pivot = empty(side_name, (bx, -4.15, 3.28), parent=root)
        # Door panel hangs down from z=0 to z=-3.06 in local space
        box(f'{side_name}Panel', (0, 0, -1.53), (3.06, 0.12, 3.06), truck_red, parent=pivot)
        for iz in (-2.75, -2.00, -1.25, -0.50):
            box(f'{side_name}Stile', (0, -0.07, iz), (3.00, 0.04, 0.07), white, parent=pivot)
        for wx in (-1.02, -0.34, 0.34, 1.02):
            box(f'{side_name}Glass', (wx, -0.07, -0.88), (0.54, 0.05, 0.50), glass, parent=pivot)
        box(f'{side_name}Handle', (0, -0.10, -2.68), (0.32, 0.06, 0.07), chrome, parent=pivot)

        # Animate door: closed (1..12) -> opens (12..36) -> stays open (36..72) -> closes (72..92)
        pivot.rotation_euler = (0.0, 0.0, 0.0)
        pivot.keyframe_insert(data_path='rotation_euler', frame=1)
        pivot.keyframe_insert(data_path='rotation_euler', frame=12)
        pivot.rotation_euler = (radians(86.0), 0.0, 0.0)
        pivot.keyframe_insert(data_path='rotation_euler', frame=36)
        pivot.keyframe_insert(data_path='rotation_euler', frame=72)
        pivot.rotation_euler = (0.0, 0.0, 0.0)
        pivot.keyframe_insert(data_path='rotation_euler', frame=92)
        pivot.keyframe_insert(data_path='rotation_euler', frame=96)
        door_pivots.append(pivot)

    # Exterior Warning Beacons that go off (flash) as the doors open!
    beacon_specs = [
        ('StationBeaconLeft', -4.05, -4.52, 3.32, 0),
        ('StationBeaconCenter', 0.0, -4.52, 3.32, 4),
        ('StationBeaconRight', 4.05, -4.52, 3.32, 0),
    ]
    for bname, bx, by, bz, phase in beacon_specs:
        mount = empty(bname, (bx, by, bz), parent=root)
        box(f'{bname}Bracket', (0, 0.08, 0), (0.24, 0.22, 0.20), steel, parent=mount)
        cyl(f'{bname}Housing', (0, -0.04, 0.13), 0.11, 0.11, steel, verts=12, parent=mount)
        lens = sphere(f'{bname}Lens', (0, -0.04, 0.25), 0.13, glow_station, segs=12, rings=8, parent=mount)
        key_flash(lens, start_frame=10, end_frame=88, period=8, phase=phase, active_scale=1.18, off_scale=0.35)

    return root


# ---------------------------------------------------------------------------
# 2. SMALL FIRE TRUCK (compact pumper + animated lights + aimable deck hose)
# ---------------------------------------------------------------------------
def make_fire_truck():
    root = empty('FireTruckRoot', (0, 0, 0))
    body = empty('TruckBody', (0, 0, 0), parent=root)

    # Chassis & bumpers (Truck faces -Y, width ~2.05m, length ~5.6m, height ~2.6m)
    box('ChassisFrame', (0, 0.0, 0.56), (1.72, 5.2, 0.26), steel, parent=body)
    box('FrontBumper', (0, -2.76, 0.58), (2.06, 0.26, 0.30), chrome, parent=body)
    box('RearStep', (0, 2.74, 0.54), (2.02, 0.36, 0.18), chrome, parent=body)

    # Cab (front)
    box('CabLower', (0, -1.65, 1.12), (1.96, 1.95, 0.92), truck_red, parent=body)
    box('CabUpper', (0, -1.52, 1.96), (1.90, 1.65, 0.78), truck_red, parent=body)
    box('CabRoof', (0, -1.52, 2.38), (1.84, 1.58, 0.08), white, parent=body)
    # Windshield & side windows
    box('Windshield', (0, -2.36, 1.96), (1.68, 0.08, 0.58), glass, parent=body)
    for sx in (-0.96, 0.96):
        box('CabWindow', (sx, -1.56, 1.96), (0.06, 1.15, 0.54), glass, parent=body)
        box('MirrorArm', (sx * 1.10, -2.18, 1.84), (0.20, 0.06, 0.06), chrome, parent=body)
        box('MirrorHead', (sx * 1.18, -2.18, 1.90), (0.06, 0.12, 0.28), chrome, parent=body)

    # Front grille & headlights
    box('GrilleFrame', (0, -2.64, 1.12), (1.24, 0.08, 0.62), chrome, parent=body)
    for gz in (0.94, 1.06, 1.18, 1.30):
        box('GrilleBar', (0, -2.68, gz), (1.10, 0.05, 0.04), steel, parent=body)
    for sx in (-0.76, 0.76):
        box('HeadlightBezel', (sx, -2.64, 0.98), (0.26, 0.08, 0.22), chrome, parent=body)
        box('HeadlightLens', (sx, -2.69, 0.98), (0.20, 0.04, 0.16), glow_white, parent=body)

    # Rear pumper body & equipment lockers
    box('PumperBody', (0, 0.92, 1.42), (2.02, 3.18, 1.50), truck_red, parent=body)
    box('StripeBandL', (-1.02, 0.15, 1.08), (0.04, 4.90, 0.14), yellow_stripe, parent=body)
    box('StripeBandR', (1.02, 0.15, 1.08), (0.04, 4.90, 0.14), yellow_stripe, parent=body)
    # Roll-up aluminum equipment compartment doors on both sides
    for sx in (-1.02, 1.02):
        for cy, cw in ((-0.12, 0.86), (0.96, 1.05), (2.02, 0.80)):
            box('LockerDoor', (sx, cy, 1.46), (0.06, cw, 0.96), chrome, parent=body)
    # Top hose bed rim & folded canvas hoses
    box('HoseBed', (0, 1.35, 2.22), (1.68, 2.15, 0.14), truck_red_dark, parent=body)
    for hx in (-0.42, 0.0, 0.42):
        box('FoldedHose', (hx, 1.38, 2.34), (0.28, 1.92, 0.16), hose_canvas, parent=body)

    # Side-mounted extension ladder on right side
    for lz in (1.76, 2.08):
        box('LadderRail', (1.12, 1.02, lz), (0.06, 3.05, 0.06), chrome, parent=body)
    for i in range(9):
        ly = -0.30 + i * 0.33
        box('LadderRung', (1.12, ly, 1.92), (0.05, 0.05, 0.30), chrome, parent=body)

    # 4 Wheels (separate nodes with centered pivots so they can spin!)
    wheel_positions = [
        ('WheelFL', -0.96, -1.62, 0.44),
        ('WheelFR', 0.96, -1.62, 0.44),
        ('WheelRL', -0.96, 1.48, 0.44),
        ('WheelRR', 0.96, 1.48, 0.44),
    ]
    for wname, wx, wy, wz in wheel_positions:
        w = empty(wname, (wx, wy, wz), parent=root)
        cyl(f'{wname}Tire', (0, 0, 0), 0.44, 0.32, rubber, verts=18, rot=(0, pi / 2, 0), parent=w)
        cyl(f'{wname}Rim', (0, 0, 0), 0.24, 0.34, chrome, verts=12, rot=(0, pi / 2, 0), parent=w)

    # Animated Roof Lightbar + Grille Flashers + Rear Flashers
    lightbar = empty('TruckLightbar', (0, -1.78, 2.48), parent=root)
    box('LightbarBase', (0, 0, 0), (1.46, 0.30, 0.10), steel, parent=lightbar)
    lb_red_l = box('LightbarRedL', (-0.50, 0, 0.11), (0.42, 0.26, 0.16), glow_red_a, parent=lightbar)
    lb_white_c = box('LightbarWhiteC', (0.0, 0, 0.11), (0.36, 0.24, 0.14), glow_white, parent=lightbar)
    lb_blue_r = box('LightbarBlueR', (0.50, 0, 0.11), (0.42, 0.26, 0.16), glow_blue, parent=lightbar)

    grille_l = box('GrilleFlashL', (-0.42, -2.69, 1.36), (0.20, 0.06, 0.12), glow_red_a, parent=root)
    grille_r = box('GrilleFlashR', (0.42, -2.69, 1.36), (0.20, 0.06, 0.12), glow_blue, parent=root)
    rear_l = box('RearFlashL', (-0.78, 2.54, 2.08), (0.20, 0.08, 0.16), glow_amber, parent=root)
    rear_r = box('RearFlashR', (0.78, 2.54, 2.08), (0.20, 0.08, 0.16), glow_red_b, parent=root)

    # Alternating emergency flash keyframes across the full 96-frame loop
    key_flash(lb_red_l, 1, 96, period=8, phase=0, active_scale=1.15, off_scale=0.55)
    key_flash(lb_blue_r, 1, 96, period=8, phase=4, active_scale=1.15, off_scale=0.55)
    key_flash(lb_white_c, 1, 96, period=12, phase=2, active_scale=1.12, off_scale=0.55)
    key_flash(grille_l, 1, 96, period=8, phase=0, active_scale=1.20, off_scale=0.45)
    key_flash(grille_r, 1, 96, period=8, phase=4, active_scale=1.20, off_scale=0.45)
    key_flash(rear_l, 1, 96, period=10, phase=0, active_scale=1.18, off_scale=0.45)
    key_flash(rear_r, 1, 96, period=10, phase=5, active_scale=1.18, off_scale=0.45)

    # Aimable Deck Hose / Water Monitor (2-axis gimbal: Yaw -> Pitch -> Nozzle + NozzleTip)
    cyl('MonitorPedestal', (0, -0.05, 2.34), 0.14, 0.34, steel, verts=14, parent=body)
    turret_yaw = empty('HoseTurretYaw', (0, -0.05, 2.52), parent=root)
    cyl('TurretSwivel', (0, 0, 0.08), 0.12, 0.18, brass, verts=14, parent=turret_yaw)
    box('TurretYokeL', (-0.11, 0, 0.22), (0.05, 0.12, 0.22), brass, parent=turret_yaw)
    box('TurretYokeR', (0.11, 0, 0.22), (0.05, 0.12, 0.22), brass, parent=turret_yaw)

    turret_pitch = empty('HoseTurretPitch', (0, 0, 0.28), parent=turret_yaw)
    # Barrel points along -Y (forward) in local space
    cyl(
        'HoseBarrel',
        (0, -0.26, 0),
        0.075,
        0.64,
        chrome,
        verts=14,
        rot=(pi / 2, 0, 0),
        parent=turret_pitch,
    )
    cone(
        'HoseNozzle',
        (0, -0.68, 0),
        0.085,
        0.042,
        0.24,
        brass,
        verts=14,
        rot=(-pi / 2, 0, 0),
        parent=turret_pitch,
    )
    empty('NozzleTip', (0, -0.82, 0), parent=turret_pitch)

    # Smooth aiming sweep animation (pans left/right and pitches up/down)
    yaw_keys = [(1, 0), (24, -40), (48, 0), (72, 42), (96, 0)]
    pitch_keys = [(1, 10), (24, 28), (48, 18), (72, 32), (96, 10)]
    for f, deg in yaw_keys:
        turret_yaw.rotation_euler = (0.0, 0.0, radians(deg))
        turret_yaw.keyframe_insert(data_path='rotation_euler', frame=f)
    for f, deg in pitch_keys:
        turret_pitch.rotation_euler = (radians(deg), 0.0, 0.0)
        turret_pitch.keyframe_insert(data_path='rotation_euler', frame=f)

    return root


# ---------------------------------------------------------------------------
# 3. KIT PROPS (Fire Hydrant, Hose Reel, Traffic Cone)
# ---------------------------------------------------------------------------
def make_fire_hydrant():
    root = empty('FireHydrantRoot', (0, 0, 0))
    cyl('HydrantBase', (0, 0, 0.06), 0.20, 0.12, truck_red_dark, verts=14, parent=root)
    cyl('HydrantBody', (0, 0, 0.42), 0.14, 0.64, truck_red, verts=14, parent=root)
    cyl('HydrantCollar', (0, 0, 0.72), 0.165, 0.08, chrome, verts=14, parent=root)
    sphere('HydrantDome', (0, 0, 0.78), 0.14, truck_red, segs=14, rings=8, parent=root)
    cyl('HydrantNut', (0, 0, 0.94), 0.045, 0.08, chrome, verts=6, parent=root)
    cyl('SideNozzles', (0, 0, 0.56), 0.06, 0.40, chrome, verts=10, rot=(0, pi / 2, 0), parent=root)
    cyl('FrontNozzle', (0, -0.15, 0.44), 0.075, 0.12, chrome, verts=10, rot=(pi / 2, 0, 0), parent=root)
    return root


def make_hose_reel():
    root = empty('HoseReelRoot', (0, 0, 0))
    box('ReelStandBase', (0, 0, 0.04), (0.68, 0.50, 0.08), steel, parent=root)
    for sx in (-0.28, 0.28):
        box('ReelLeg', (sx, 0, 0.42), (0.06, 0.08, 0.72), steel, parent=root)
    cyl('ReelAxle', (0, 0, 0.68), 0.04, 0.64, chrome, verts=10, rot=(0, pi / 2, 0), parent=root)
    for sx in (-0.20, 0.20):
        cyl('ReelFlange', (sx, 0, 0.68), 0.34, 0.03, truck_red, verts=18, rot=(0, pi / 2, 0), parent=root)
    cyl('CoiledHose', (0, 0, 0.68), 0.28, 0.36, hose_canvas, verts=18, rot=(0, pi / 2, 0), parent=root)
    cone('ReelNozzle', (0.0, -0.30, 0.46), 0.045, 0.02, 0.18, brass, verts=10, rot=(pi / 4, 0, 0), parent=root)
    return root


def make_traffic_cone():
    root = empty('TrafficConeRoot', (0, 0, 0))
    box('ConeBase', (0, 0, 0.025), (0.38, 0.38, 0.05), rubber, parent=root)
    cone('ConeBody', (0, 0, 0.36), 0.14, 0.032, 0.64, cone_orange, verts=14, parent=root)
    cone('ConeStripe', (0, 0, 0.44), 0.105, 0.072, 0.16, white, verts=14, parent=root)
    return root


# ---------------------------------------------------------------------------
# Export each kit piece as a clean GLB (preserving hierarchy & animations!),
# then arrange them into a nice diorama layout for the .blend & preview PNG.
# ---------------------------------------------------------------------------
def build_asset(name, make_fn, layout_pos, layout_rot_z=0.0):
    before = set(scene.objects)
    root_obj = make_fn()
    pieces = list(set(scene.objects) - before)

    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    for obj in pieces:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in pieces:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = root_obj
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / f'{name}.glb'),
        export_format='GLB',
        use_selection=True,
        export_animations=True,
    )

    # Position for the .blend kit overview & preview render
    root_obj.location = Vector(layout_pos)
    root_obj.rotation_euler.z = radians(layout_rot_z)
    return root_obj


build_asset('fire_station', make_fire_station, (0.0, 1.5, 0.0), 0.0)
build_asset('fire_truck', make_fire_truck, (-2.15, -6.5, 0.20), -18.0)
build_asset('fire_hydrant', make_fire_hydrant, (5.5, -5.0, 0.20), 0.0)
build_asset('hose_reel', make_hose_reel, (4.2, -3.9, 0.20), 12.0)
build_asset('traffic_cone', make_traffic_cone, (1.2, -6.4, 0.20), 0.0)

# Set frame to 42 so the preview shows the bay doors OPEN, beacons ON, and deck hose aimed!
scene.frame_set(42)

# Save editable .blend
direction = Vector((14.5, -25.0, 14.0))
rotation = (-direction).to_track_quat('-Z', 'Y')
target = Vector((-0.2, -1.0, 2.5))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 28
        space.shading.color_type = 'MATERIAL'

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'art/fire_station_kit.blend'))

# Render preview PNG
box('PreviewGround', (0, 0, -0.16), (220, 220, 0.32), paint('Coastal turf', '7f8d74'))
bpy.ops.object.camera_add(location=target + direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 23.0
scene.camera = camera

scene.world = bpy.data.worlds.new('Coastal daylight')
scene.world.use_nodes = True
bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Color'].default_value = (0.52, 0.64, 0.78, 1.0)
bg.inputs['Strength'].default_value = 0.85

bpy.ops.object.light_add(type='SUN')
sun = bpy.context.object
sun.rotation_euler = (0.52, -0.58, -0.35)
sun.data.energy = 3.2
sun.data.angle = 0.14

scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = 1440
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT / 'art/fire_station_kit_preview.png')
bpy.ops.render.render(write_still=True)

print("Built fire_station_kit successfully.")
