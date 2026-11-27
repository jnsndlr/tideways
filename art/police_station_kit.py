"""Editable Small Police Station & Squad Car kit.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python art/police_station_kit.py

Exports individual GLB assets to assets/models/police_station_kit/:
  - police_station.glb   (compact 1-story coastal police station with portico, blue globe lamps & radio mast)
  - squad_car.glb        (compact two-tone police cruiser with animated roof lightbar, grille & rear flashers)
  - police_barricade.glb (striped sawhorse barricade with animated amber warning lamp)
  - parking_bollard.glb  (navy & chrome reflective bollard)
  - notice_board.glb     (community notice & patrol board)

Also saves art/police_station_kit.blend and renders art/police_station_kit_preview.png.
"""
from math import atan2, hypot, pi, radians
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/police_station_kit"
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


# Shared Tideways-harmonized coastal civic / police palette
stucco = paint('Coastal limestone stucco', 'e6dfd0', roughness=0.80)
stone_base = paint('Harbor granite base', '7e8589', roughness=0.86)
white = paint('White enamel trim', 'fff9ea', roughness=0.58)
roof_slate = paint('Slate roof', '334350', roughness=0.74)
roof_seam = paint('Roof seam', '4c5f6e', roughness=0.68)
police_navy = paint('Police navy', '1b2f45', roughness=0.45)
police_navy_gloss = paint('Cruiser navy', '162638', roughness=0.28)
cruiser_white = paint('Cruiser white', 'f4f3ee', roughness=0.30)
concrete = paint('Apron concrete', 'aba698', roughness=0.88)
asphalt = paint('Parking pad', '4b5056', roughness=0.90)
glass = paint('Harbour glass', '5b8694', roughness=0.20)
windshield_glass = paint('Cruiser glass', '2f4b57', roughness=0.16)
chrome = paint('Brushed chrome', 'd5dce0', roughness=0.24, metallic=0.88)
steel = paint('Painted steel', '4e5b63', roughness=0.52, metallic=0.45)
rubber = paint('Tire rubber', '202326', roughness=0.86)
gold_badge = paint('Badge gold', 'dfb03e', roughness=0.28, metallic=0.82)
yellow_stripe = paint('Safety yellow', 'f2c12e', roughness=0.48)
wood_cork = paint('Cork board', 'a67c52', roughness=0.88)
paper_note = paint('Notice paper', 'f7f2e4', roughness=0.82)

# Emissive light materials (distinct so Godot can also drive emission independently)
glow_red = paint('Lightbar red', 'ff2018', roughness=0.16, emission_strength=6.5)
glow_blue = paint('Lightbar blue', '167dff', roughness=0.16, emission_strength=6.5)
glow_white = paint('Strobe white', 'fff6d6', roughness=0.15, emission_strength=5.5)
glow_amber = paint('Warning amber', 'ff9d14', roughness=0.18, emission_strength=5.5)
glow_tail = paint('Taillight red', 'd91e18', roughness=0.22, emission_strength=3.0)
glow_globe = paint('Police globe blue', '2b95ff', roughness=0.18, emission_strength=5.0)


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


def window(x, y, z, w=1.35, h=1.40, side=False, barred=False, parent=None):
    for name, offset, width, height, mat in [
        ('WinCasing', 0.0, w, h, white),
        ('WinSash', 0.06, w - 0.16, h - 0.16, police_navy),
        ('WinGlass', 0.095, w - 0.28, h - 0.28, glass),
        ('WinMullion', 0.13, 0.06, h - 0.16, white),
        ('WinRail', 0.14, w - 0.16, 0.07, white),
    ]:
        pos = (x + offset, y, z) if side else (x, y - offset, z)
        dims = (0.10, width, height) if side else (width, 0.10, height)
        box(name, pos, dims, mat, parent=parent)
    if barred:
        for i in (-2, -1, 0, 1, 2):
            span = (w - 0.34) * (i / 4.5)
            pos = (x + 0.15, y + span, z) if side else (x + span, y - 0.15, z)
            cyl('CellBar', pos, 0.022, h - 0.24, steel, verts=8, parent=parent)


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


def key_flash(obj, start_frame, end_frame, period=8, phase=0, active_scale=1.18, off_scale=0.45):
    """Keyframe an emissive light lens to flash on/off across [start_frame, end_frame]."""
    obj.scale = (off_scale, off_scale, off_scale)
    obj.keyframe_insert(data_path='scale', frame=1)
    if start_frame > 2:
        obj.keyframe_insert(data_path='scale', frame=start_frame - 1)
    f = start_frame
    step = max(1, period // 2)
    while f <= end_frame:
        on = ((f - start_frame + phase) // step) % 2 == 0
        s = active_scale if on else off_scale
        obj.scale = (s, s, s)
        obj.keyframe_insert(data_path='scale', frame=f)
        f += step
    if end_frame < scene.frame_end:
        obj.scale = (off_scale, off_scale, off_scale)
        obj.keyframe_insert(data_path='scale', frame=min(scene.frame_end, end_frame + 2))
        obj.keyframe_insert(data_path='scale', frame=scene.frame_end)


# ---------------------------------------------------------------------------
# 1. SMALL POLICE STATION (compact 1-story coastal station + portico + lamps)
# ---------------------------------------------------------------------------
def make_police_station():
    root = empty('PoliceStationRoot', (0, 0, 0))
    static = empty('StationStructure', (0, 0, 0), parent=root)

    # Concrete plaza & reserved squad-car parking apron
    box('ApronSlab', (0, -1.6, 0.10), (13.6, 12.8, 0.20), concrete, parent=static)
    box('SquadPad', (-3.2, -5.5, 0.205), (5.6, 4.6, 0.02), asphalt, parent=static)
    # Parking stall lines
    for sx in (-5.7, -0.7):
        box('ParkingLine', (sx, -5.5, 0.22), (0.12, 4.1, 0.012), yellow_stripe, parent=static)
    box('ParkingStop', (-3.2, -3.55, 0.26), (2.2, 0.22, 0.12), concrete, parent=static)

    # Main 1-story civic building shell (W=9.8, D=7.2, H=3.95)
    box('WallBase', (0, 0.6, 0.62), (9.96, 7.36, 0.84), stone_base, parent=static)
    box('MainBody', (0, 0.6, 2.48), (9.80, 7.20, 2.94), stucco, parent=static)
    box('CorniceFront', (0, -3.08, 3.92), (10.2, 0.28, 0.22), white, parent=static)
    box('CorniceBack', (0, 4.28, 3.92), (10.2, 0.28, 0.22), white, parent=static)
    for x in (-4.88, 4.88):
        for y in (-2.98, 4.18):
            box('CornerPilaster', (x, y, 2.08), (0.28, 0.28, 3.76), police_navy, parent=static)

    # Gable roof
    gable(0, 0.6, 9.80, 7.20, 3.95, 1.95, stucco, roof_slate, roof_seam, parent=static)

    # Front covered entry portico (centered at x=1.2 so squad car has clear parking on the left)
    px = 1.2
    box('PorticoSteps1', (px, -3.95, 0.26), (3.4, 1.5, 0.14), stone_base, parent=static)
    box('PorticoSteps2', (px, -3.65, 0.40), (3.1, 1.1, 0.14), stone_base, parent=static)
    for sx in (-1.28, 1.28):
        box('PorticoColumn', (px + sx, -4.12, 1.82), (0.22, 0.22, 2.75), white, parent=static)
        box('PorticoBase', (px + sx, -4.12, 0.52), (0.30, 0.30, 0.20), police_navy, parent=static)
    box('PorticoRoof', (px, -3.68, 3.28), (3.4, 1.55, 0.22), roof_slate, parent=static)
    box('PorticoFascia', (px, -4.42, 3.22), (3.5, 0.12, 0.16), white, parent=static)

    # Double entry doors & transom
    box('DoorFrame', (px, -3.02, 1.72), (1.96, 0.18, 2.52), white, parent=static)
    for dx in (-0.44, 0.44):
        box('DoorLeaf', (px + dx, -3.06, 1.50), (0.84, 0.10, 2.04), police_navy, parent=static)
        box('DoorWindow', (px + dx, -3.11, 1.82), (0.52, 0.04, 0.84), glass, parent=static)
        box('DoorHandle', (px + dx * 0.25, -3.14, 1.38), (0.05, 0.08, 0.22), gold_badge, parent=static)
    box('DoorTransom', (px, -3.08, 2.74), (1.72, 0.06, 0.34), glass, parent=static)

    # Classic blue police globe lamps flanking the front entrance
    for side_name, sx in (('StationGlobeL', px - 1.28), ('StationGlobeR', px + 1.28)):
        cyl(f'{side_name}Pedestal', (sx, -4.42, 1.10), 0.10, 1.30, police_navy, verts=12, parent=static)
        cyl(f'{side_name}Collar', (sx, -4.42, 1.78), 0.13, 0.08, chrome, verts=12, parent=static)
        sphere(f'{side_name}Lens', (sx, -4.42, 1.96), 0.18, glow_globe, segs=14, rings=10, parent=static)

    # Front & side windows (barred holding-cell windows on right side)
    window(-2.45, -3.02, 2.15, 1.65, 1.35, side=False, parent=static)
    window(3.75, -3.02, 2.15, 1.25, 1.35, side=False, parent=static)
    for wy in (-1.1, 1.9):
        window(4.92, wy, 2.25, 1.20, 1.05, side=True, barred=True, parent=static)

    # Main POLICE signboard & golden badge shield in the front gable
    box('SignBoard', (0.0, -3.14, 4.65), (4.8, 0.16, 0.68), police_navy, parent=static)
    box('SignTrim', (0.0, -3.12, 4.65), (4.94, 0.10, 0.78), gold_badge, parent=static)
    sign('POLICE', 0.35, -3.24, 4.65, 0.42, white, parent=static)
    # Stylized 6-point badge emblem on left of signboard
    cyl('BadgeDisc', (-1.75, -3.23, 4.65), 0.24, 0.06, gold_badge, verts=6, rot=(pi / 2, 0, 0), parent=static)
    cyl('BadgeCenter', (-1.75, -3.26, 4.65), 0.12, 0.04, police_navy, verts=12, rot=(pi / 2, 0, 0), parent=static)

    # Rooftop dispatch radio mast & antenna
    mx, my = -2.8, 1.8
    box('MastBase', (mx, my, 5.15), (0.65, 0.65, 0.45), steel, parent=static)
    cyl('RadioMast', (mx, my, 6.45), 0.055, 2.40, chrome, verts=10, parent=static)
    for az in (6.85, 7.25):
        box('AntennaBar', (mx, my, az), (0.95, 0.05, 0.05), chrome, parent=static)
    sphere('MastBeacon', (mx, my, 7.68), 0.08, glow_red, segs=10, rings=8, parent=static)

    return root


# ---------------------------------------------------------------------------
# 2. SQUAD CAR (compact two-tone cruiser with animated lightbar & flashers)
# ---------------------------------------------------------------------------
def make_squad_car():
    root = empty('SquadCarRoot', (0, 0, 0))
    body = empty('CarBody', (0, 0, 0), parent=root)

    # Chassis & bumpers (Car faces -Y, width ~1.84m, length ~4.45m, height ~1.62m)
    box('ChassisUnderbody', (0, 0.0, 0.38), (1.62, 4.10, 0.22), steel, parent=body)
    box('FrontBumper', (0, -2.22, 0.46), (1.84, 0.22, 0.24), police_navy_gloss, parent=body)
    box('RearBumper', (0, 2.20, 0.46), (1.84, 0.22, 0.24), police_navy_gloss, parent=body)

    # Push bumper (classic police ram bar on front)
    for sx in (-0.36, 0.36):
        box('PushUpright', (sx, -2.38, 0.68), (0.08, 0.14, 0.50), steel, parent=body)
    box('PushBarTop', (0, -2.42, 0.82), (0.80, 0.07, 0.07), steel, parent=body)
    box('PushBarMid', (0, -2.42, 0.60), (0.80, 0.07, 0.07), steel, parent=body)

    # Lower body: navy front & rear, white center doors (classic black/navy & white cruiser)
    box('FrontFenderBody', (0, -1.42, 0.72), (1.82, 1.48, 0.56), police_navy_gloss, parent=body)
    box('CenterDoorsBody', (0, 0.08, 0.72), (1.84, 1.56, 0.56), cruiser_white, parent=body)
    box('RearTrunkBody', (0, 1.48, 0.72), (1.82, 1.32, 0.56), police_navy_gloss, parent=body)

    # Side gold/navy stripe & door badges
    for sx in (-0.93, 0.93):
        box('SideStripe', (sx, 0.05, 0.70), (0.03, 3.92, 0.10), yellow_stripe, parent=body)
        cyl('DoorBadge', (sx * 1.01, -0.05, 0.76), 0.14, 0.03, gold_badge, verts=6, rot=(0, pi / 2, 0), parent=body)

    # Cabin greenhouse & white roof
    box('CabinCore', (0, 0.14, 1.24), (1.58, 1.88, 0.52), cruiser_white, parent=body)
    box('CabinRoof', (0, 0.14, 1.52), (1.54, 1.76, 0.08), cruiser_white, parent=body)
    # Angled windshield & rear glass
    box('Windshield', (0, -0.84, 1.20), (1.46, 0.08, 0.56), windshield_glass, parent=body, rot=(radians(-24), 0, 0))
    box('RearWindow', (0, 1.10, 1.20), (1.46, 0.08, 0.54), windshield_glass, parent=body, rot=(radians(24), 0, 0))
    for sx in (-0.80, 0.80):
        box('SideWindowF', (sx, -0.26, 1.24), (0.05, 0.68, 0.38), windshield_glass, parent=body)
        box('SideWindowR', (sx, 0.54, 1.24), (0.05, 0.68, 0.38), windshield_glass, parent=body)
        box('MirrorArm', (sx * 1.12, -0.66, 1.06), (0.14, 0.06, 0.05), police_navy_gloss, parent=body)
        box('MirrorHead', (sx * 1.18, -0.66, 1.10), (0.08, 0.12, 0.14), police_navy_gloss, parent=body)

    # Front grille, headlights & taillights
    box('FrontGrille', (0, -2.17, 0.72), (0.94, 0.06, 0.28), chrome, parent=body)
    for sx in (-0.68, 0.68):
        box('HeadlightBezel', (sx, -2.17, 0.74), (0.30, 0.06, 0.18), chrome, parent=body)
        box('HeadlightLens', (sx, -2.20, 0.74), (0.24, 0.04, 0.14), glow_white, parent=body)
        box('TaillightLens', (sx, 2.15, 0.76), (0.34, 0.05, 0.16), glow_tail, parent=body)

    # Trunk radio whip antenna
    cyl('TrunkAntenna', (0.62, 1.78, 1.48), 0.016, 1.05, chrome, verts=8, parent=body)

    # 4 Wheels (separate nodes with centered pivots so they can spin!)
    wheel_positions = [
        ('WheelFL', -0.88, -1.32, 0.34),
        ('WheelFR', 0.88, -1.32, 0.34),
        ('WheelRL', -0.88, 1.32, 0.34),
        ('WheelRR', 0.88, 1.32, 0.34),
    ]
    for wname, wx, wy, wz in wheel_positions:
        w = empty(wname, (wx, wy, wz), parent=root)
        cyl(f'{wname}Tire', (0, 0, 0), 0.34, 0.24, rubber, verts=18, rot=(0, pi / 2, 0), parent=w)
        cyl(f'{wname}Rim', (0, 0, 0), 0.19, 0.26, chrome, verts=12, rot=(0, pi / 2, 0), parent=w)

    # Animated Roof Lightbar + Push-Bumper Grille Flashers + Rear Deck Flashers
    lightbar = empty('SquadLightbar', (0, 0.06, 1.58), parent=root)
    box('LightbarBase', (0, 0, 0), (1.28, 0.26, 0.07), steel, parent=lightbar)
    lb_red_l = box('LightbarRedL', (-0.42, 0, 0.09), (0.40, 0.24, 0.14), glow_red, parent=lightbar)
    lb_white_c = box('LightbarWhiteC', (0.0, 0, 0.09), (0.32, 0.22, 0.12), glow_white, parent=lightbar)
    lb_blue_r = box('LightbarBlueR', (0.42, 0, 0.09), (0.40, 0.24, 0.14), glow_blue, parent=lightbar)

    grille_l = box('GrilleFlashL', (-0.22, -2.44, 0.82), (0.16, 0.06, 0.09), glow_red, parent=root)
    grille_r = box('GrilleFlashR', (0.22, -2.44, 0.82), (0.16, 0.06, 0.09), glow_blue, parent=root)
    rear_l = box('RearFlashL', (-0.46, 1.02, 1.36), (0.20, 0.08, 0.10), glow_blue, parent=root)
    rear_r = box('RearFlashR', (0.46, 1.02, 1.36), (0.20, 0.08, 0.10), glow_red, parent=root)

    # Alternating emergency flash keyframes across the full 96-frame loop
    key_flash(lb_red_l, 1, 96, period=8, phase=0, active_scale=1.18, off_scale=0.52)
    key_flash(lb_blue_r, 1, 96, period=8, phase=4, active_scale=1.18, off_scale=0.52)
    key_flash(lb_white_c, 1, 96, period=12, phase=2, active_scale=1.12, off_scale=0.52)
    key_flash(grille_l, 1, 96, period=8, phase=0, active_scale=1.22, off_scale=0.45)
    key_flash(grille_r, 1, 96, period=8, phase=4, active_scale=1.22, off_scale=0.45)
    key_flash(rear_l, 1, 96, period=8, phase=4, active_scale=1.20, off_scale=0.45)
    key_flash(rear_r, 1, 96, period=8, phase=0, active_scale=1.20, off_scale=0.45)

    return root


# ---------------------------------------------------------------------------
# 3. KIT PROPS (Police Barricade, Parking Bollard, Notice Board)
# ---------------------------------------------------------------------------
def make_police_barricade():
    root = empty('PoliceBarricadeRoot', (0, 0, 0))
    for sx in (-0.65, 0.65):
        beam('BarricadeLegF', (sx, -0.30, 0.0), (sx, -0.04, 0.92), 0.06, steel, parent=root)
        beam('BarricadeLegB', (sx, 0.30, 0.0), (sx, 0.04, 0.92), 0.06, steel, parent=root)
    box('BarricadeBoard', (0, 0, 0.78), (1.62, 0.08, 0.28), cruiser_white, parent=root)
    for bx in (-0.54, -0.18, 0.18, 0.54):
        box('BarricadeStripe', (bx, -0.045, 0.78), (0.18, 0.02, 0.26), police_navy, parent=root)
    box('BarricadeLowerRail', (0, 0, 0.36), (1.42, 0.06, 0.12), police_navy, parent=root)
    # Flashing amber warning lamp mounted on top
    box('LampBase', (0.58, 0, 0.97), (0.14, 0.10, 0.10), steel, parent=root)
    lamp = sphere('BarricadeFlash', (0.58, 0, 1.09), 0.09, glow_amber, segs=10, rings=8, parent=root)
    key_flash(lamp, 1, 96, period=12, phase=0, active_scale=1.18, off_scale=0.48)
    return root


def make_parking_bollard():
    root = empty('ParkingBollardRoot', (0, 0, 0))
    cyl('BollardBase', (0, 0, 0.04), 0.15, 0.08, steel, verts=14, parent=root)
    cyl('BollardPost', (0, 0, 0.46), 0.095, 0.84, police_navy, verts=14, parent=root)
    cyl('BollardBand', (0, 0, 0.72), 0.102, 0.12, yellow_stripe, verts=14, parent=root)
    sphere('BollardCap', (0, 0, 0.88), 0.095, chrome, segs=12, rings=8, parent=root)
    return root


def make_notice_board():
    root = empty('NoticeBoardRoot', (0, 0, 0))
    for sx in (-0.58, 0.58):
        box('BoardPost', (sx, 0, 0.88), (0.09, 0.09, 1.76), police_navy, parent=root)
    box('BoardFrame', (0, 0, 1.38), (1.36, 0.12, 0.92), police_navy, parent=root)
    box('BoardCork', (0, -0.05, 1.38), (1.20, 0.04, 0.76), wood_cork, parent=root)
    for nx, nz, nw, nh in (
        (-0.32, 1.50, 0.26, 0.30),
        (0.05, 1.48, 0.30, 0.26),
        (0.36, 1.44, 0.22, 0.32),
        (-0.18, 1.18, 0.28, 0.22),
    ):
        box('NoticePaper', (nx, -0.075, nz), (nw, 0.015, nh), paper_note, parent=root)
    box('BoardCap', (0, 0, 1.90), (1.52, 0.30, 0.10), roof_slate, parent=root)
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


build_asset('police_station', make_police_station, (0.0, 1.5, 0.0), 0.0)
build_asset('squad_car', make_squad_car, (-3.2, -4.4, 0.22), -16.0)
build_asset('police_barricade', make_police_barricade, (4.3, -4.7, 0.20), 14.0)
build_asset('parking_bollard', make_parking_bollard, (0.4, -5.8, 0.20), 0.0)
build_asset('notice_board', make_notice_board, (4.8, -2.5, 0.20), -18.0)

# Set frame to 1 so the preview shows the red/blue lightbar & flashers actively lit!
scene.frame_set(1)

# Save editable .blend
direction = Vector((14.5, -25.0, 14.0))
rotation = (-direction).to_track_quat('-Z', 'Y')
target = Vector((-0.2, -0.8, 2.2))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 27
        space.shading.color_type = 'MATERIAL'

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'art/police_station_kit.blend'))

# Render preview PNG
box('PreviewGround', (0, 0, -0.16), (220, 220, 0.32), paint('Coastal turf', '7f8d74'))
bpy.ops.object.camera_add(location=target + direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 22.0
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
scene.render.filepath = str(ROOT / 'art/police_station_kit_preview.png')
bpy.ops.render.render(write_still=True)

print("Built police_station_kit successfully.")
