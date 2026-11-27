"""Editable Coast Guard radar tower. Run with Blender --background --python."""
from math import cos, pi, sin
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/coast_guard_station"
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def paint(name, hex_color, roughness=0.74, metallic=0.0, emission=0.0):
    mat = bpy.data.materials.new(name)
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    mat.diffuse_color = (*lin, 1.0)
    mat.use_nodes = True
    shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*lin, 1.0)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    if emission > 0:
        if 'Emission Color' in shader.inputs:
            shader.inputs['Emission Color'].default_value = (*lin, 1.0)
            shader.inputs['Emission Strength'].default_value = emission
        elif 'Emission' in shader.inputs:
            shader.inputs['Emission'].default_value = (*lin, 1.0)
    return mat


def box(name, center, size, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def cyl(name, center, radius, depth, mat, verts=16, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=center, rotation=rot
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def sphere(name, center, radius, mat, segs=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segs, ring_count=rings, radius=radius, location=center
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def beam(name, a, b, width, mat):
    va, vb = Vector(a), Vector(b)
    d = vb - va
    if d.length < 1e-5:
        return None
    obj = box(name, (va + vb) / 2, (width, width, d.length), mat)
    obj.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return obj


# Coast Guard station palette
cream = paint('Salt white siding', 'f0e8d3')
white = paint('White enamel trim', 'fff9e7', roughness=0.55)
roof = paint('Lifeboat red metal', 'aa4035', roughness=0.62)
navy = paint('Marine blue', '233f51', roughness=0.6)
dark_steel = paint('Galvanized steel', '4e5c63', roughness=0.45, metallic=0.35)
base = paint('Weathered concrete', 'aea99a', roughness=0.85)
orange = paint('Rescue orange', 'ed6338', roughness=0.5)
beacon_red = paint('Obstruction beacon', 'ff3322', roughness=0.2, emission=4.0)


def corner_xy(z, h_top=12.4, r_bot=2.15, r_top=0.82):
    t = max(0.0, min(1.0, z / h_top))
    r = r_bot + (r_top - r_bot) * t
    return [(-r, -r), (r, -r), (r, r), (-r, r)]


def make_platform(name_prefix, z, size, has_knees=True, knee_z_drop=1.1, r_inner=0.85):
    half = size / 2.0
    box(f'{name_prefix} deck', (0, 0, z), (size, size, 0.22), navy)
    box(f'{name_prefix} trim', (0, 0, z - 0.02), (size + 0.08, size + 0.08, 0.14), white)

    if has_knees:
        for sx in (-1, 1):
            for sy in (-1, 1):
                beam(
                    f'{name_prefix} knee',
                    (sx * r_inner, sy * r_inner, z - knee_z_drop),
                    (sx * (half - 0.12), sy * (half - 0.12), z - 0.1),
                    0.12,
                    white,
                )

    rail_r = half - 0.08
    for s in (-1, 1):
        for k in (-rail_r, 0.0, rail_r):
            box(f'{name_prefix} post', (k, s * rail_r, z + 0.58), (0.07, 0.07, 0.96), white)
            if abs(k) < rail_r - 0.01:
                box(f'{name_prefix} post', (s * rail_r, k, z + 0.58), (0.07, 0.07, 0.96), white)
        for rz in (z + 0.56, z + 1.02):
            box(f'{name_prefix} rail', (0, s * rail_r, rz), (size - 0.1, 0.06, 0.06), white)
            box(f'{name_prefix} rail', (s * rail_r, 0, rz), (0.06, size - 0.1, 0.06), white)


def radar_tower():
    # 1. Concrete foundation pad & 4 corner pedestals
    box('Foundation pad', (0, 0, 0.16), (5.4, 5.4, 0.32), base)
    for cx, cy in corner_xy(0.0):
        box('Leg footing', (cx, cy, 0.44), (0.72, 0.72, 0.56), base)
        box('Base plate', (cx, cy, 0.75), (0.48, 0.48, 0.08), dark_steel)

    # 2. Compact equipment & generator shelter nested at the base
    box('Equipment shelter', (0, 0.15, 1.38), (2.45, 2.2, 2.16), cream)
    box('Shelter roof', (0, 0.15, 2.52), (2.68, 2.42, 0.14), roof)
    box('Shelter door frame', (0, -0.96, 1.24), (1.02, 0.12, 1.84), white)
    box('Shelter door', (0, -1.01, 1.22), (0.86, 0.08, 1.72), navy)
    box('Shelter stripe', (0, -1.06, 1.52), (0.86, 0.03, 0.16), orange)
    # Side vent louvers
    for i in range(4):
        box('Shelter vent', (1.24, 0.15, 1.45 + i * 0.14), (0.06, 0.72, 0.07), navy)

    # 3. Tapered 4-leg steel lattice mast (4 alternating red/white bays)
    bay_z = [0.75, 3.65, 6.55, 9.45, 12.35]
    bay_mats = [roof, white, roof, white]

    for i in range(len(bay_z) - 1):
        z0, z1 = bay_z[i], bay_z[i + 1]
        mat = bay_mats[i]
        p0 = corner_xy(z0)
        p1 = corner_xy(z1)

        # 4 corner legs
        for c in range(4):
            beam(f'Tower leg {i}', (*p0[c], z0), (*p1[c], z1), 0.15, mat)

        # Horizontal girts at top of bay (and mid-girt on lower bays)
        for c in range(4):
            nc = (c + 1) % 4
            beam(f'Girt top {i}', (*p1[c], z1), (*p1[nc], z1), 0.095, mat)
            # X-bracing on each face
            beam(f'Brace A {i}', (*p0[c], z0), (*p1[nc], z1), 0.075, mat)
            beam(f'Brace B {i}', (*p0[nc], z0), (*p1[c], z1), 0.075, mat)

        # Mid horizontal girt on bottom two bays for crispness
        if i < 2:
            zm = (z0 + z1) / 2.0
            pm = corner_xy(zm)
            for c in range(4):
                nc = (c + 1) % 4
                beam(f'Mid girt {i}', (*pm[c], zm), (*pm[nc], zm), 0.08, mat)

    # 4. Internal access ladder + cable conduit running up the rear/center
    ladder_y = 0.58
    for sx in (-0.2, 0.2):
        beam('Ladder rail', (sx, ladder_y, 2.55), (sx, ladder_y, 12.45), 0.045, dark_steel)
    z_rung = 2.85
    while z_rung < 12.3:
        beam('Ladder rung', (-0.2, ladder_y, z_rung), (0.2, ladder_y, z_rung), 0.03, dark_steel)
        z_rung += 0.38
    # Cable tray beside ladder
    beam('Cable conduit', (-0.42, ladder_y, 2.5), (-0.42, ladder_y, 12.4), 0.09, navy)

    # 5. Mid-level service platform at z = 6.6
    make_platform('Mid', 6.6, size=3.3, has_knees=False)
    # Side microwave dish on mid-level
    beam('Dish mount', (1.58, -0.5, 7.25), (1.92, -0.5, 7.25), 0.08, dark_steel)
    cyl('Microwave dish', (2.0, -0.5, 7.25), 0.55, 0.14, white, verts=20, rot=(0, pi / 2, 0))
    cyl('Dish rim', (2.06, -0.5, 7.25), 0.57, 0.06, navy, verts=20, rot=(0, pi / 2, 0))
    cyl('Dish feed', (2.22, -0.5, 7.25), 0.08, 0.28, orange, verts=12, rot=(0, pi / 2, 0))

    # 6. Upper radar gallery deck at z = 12.45
    make_platform('Radar', 12.45, size=3.8, has_knees=True, knee_z_drop=1.25, r_inner=0.88)

    # Corner red obstruction lights on upper deck
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = sx * 1.82, sy * 1.82
            cyl('Beacon post', (px, py, 13.62), 0.035, 0.24, dark_steel, verts=8)
            sphere('Obstruction light', (px, py, 13.78), 0.095, beacon_red, segs=12, rings=8)

    # 7. Central radar pedestal (static; rotating scanner mounts at z = 14.45)
    cyl('Pedestal base', (0, 0, 12.78), 0.62, 0.44, navy, verts=16)
    cyl('Pedestal column', (0, 0, 13.65), 0.42, 1.35, white, verts=16)
    cyl('Pedestal collar', (0, 0, 14.38), 0.48, 0.14, navy, verts=16)

    # 8. Secondary white radome + VHF whip antennas on the upper deck
    cyl('Radome stand', (-1.18, 1.05, 12.92), 0.24, 0.72, dark_steel, verts=12)
    sphere('Weather radome', (-1.18, 1.05, 13.65), 0.58, white, segs=20, rings=12)
    cyl('Radome band', (-1.18, 1.05, 13.65), 0.59, 0.07, navy, verts=20)

    # Tall lightning/VHF mast on a cantilevered outrigger beam off the upper deck corner
    mx, my = 2.35, 2.35
    beam('Antenna outrigger', (1.72, 1.72, 12.45), (mx, my, 12.45), 0.11, white)
    beam('Antenna brace', (1.62, 1.62, 11.85), (mx, my, 12.42), 0.08, white)
    cyl('Antenna mount', (mx, my, 12.48), 0.11, 0.14, navy, verts=12)
    cyl('Antenna mast', (mx, my, 14.95), 0.055, 4.8, white, verts=10)
    cyl('Antenna mast band', (mx, my, 16.2), 0.06, 0.7, orange, verts=10)
    sphere('Top beacon', (mx, my, 17.45), 0.13, beacon_red, segs=14, rings=10)
    # Crossbar with VHF whips
    beam('VHF crossbar', (mx - 0.55, my, 16.4), (mx + 0.55, my, 16.4), 0.04, dark_steel)
    for dx in (-0.52, 0.52):
        cyl('VHF whip', (mx + dx, my, 16.95), 0.02, 1.35, dark_steel, verts=8)


SCANNER_PIVOT_Z = 14.45


def radar_scanner():
    """Rotating gearbox + open-array slotted waveguide radar bar, centered at origin."""
    box('Radar gearbox', (0, 0, 0.27), (0.92, 0.68, 0.56), navy)
    box('Gearbox cap', (0, 0, 0.59), (0.76, 0.56, 0.12), white)
    box('Radar array main', (0, 0, 0.87), (3.9, 0.36, 0.34), white)
    box('Radar array slot', (0, 0, 0.87), (3.6, 0.40, 0.13), navy)
    for s in (-1, 1):
        box('Radar tip', (s * 1.95, 0, 0.87), (0.32, 0.40, 0.38), orange)


def build(name, make, pivot_z=0.0, preview_yaw=0.0):
    before = set(scene.objects)
    make()
    pieces = list(set(scene.objects) - before)
    group = bpy.data.collections.new(name)
    scene.collection.children.link(group)
    for obj in pieces:
        for coll in list(obj.users_collection):
            coll.objects.unlink(obj)
        group.objects.link(obj)

    # Export a single joined GLB while keeping editable pieces in the .blend
    bpy.ops.object.select_all(action='DESELECT')
    for obj in pieces:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = min(pieces, key=lambda o: o.name)
    bpy.ops.object.duplicate()
    bpy.ops.object.join()
    prop = bpy.context.object
    prop.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / f'{name}.glb'),
        export_format='GLB',
        use_selection=True,
    )
    bpy.data.objects.remove(prop, do_unlink=True)

    if pivot_z != 0.0:
        pivot = bpy.data.objects.new(f'{name}_pivot', None)
        pivot.location = (0, 0, pivot_z)
        group.objects.link(pivot)
        for obj in pieces:
            obj.parent = pivot
        # Add looping 360-degree spin animation in the .blend
        scene.frame_start = 1
        scene.frame_end = 120
        pivot.rotation_euler = (0, 0, preview_yaw)
        pivot.keyframe_insert(data_path='rotation_euler', index=2, frame=1)
        pivot.rotation_euler = (0, 0, preview_yaw + 2 * pi)
        pivot.keyframe_insert(data_path='rotation_euler', index=2, frame=121)
        pivot.rotation_euler = (0, 0, preview_yaw)


build('radar_tower', radar_tower)
build('radar_tower_scanner', radar_scanner, pivot_z=SCANNER_PIVOT_Z, preview_yaw=0.45)

# Save editable .blend
direction = Vector((18, -28, 16))
rotation = (-direction).to_track_quat('-Z', 'Y')
target = Vector((0, 0, 8.6))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 36
        space.shading.color_type = 'MATERIAL'

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'art/coast_guard_radar_tower.blend'))

# Preview render (matching coast_guard_station_preview.png lighting & ground)
quay = paint('Quayside aggregate', 'a59d88')
box('Quayside', (0, 0, -0.2), (80, 80, 0.4), quay)

bpy.ops.object.camera_add(location=target + direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 23.0
scene.camera = camera

scene.world = bpy.data.worlds.new('Coastal daylight')
scene.world.color = (0.64, 0.72, 0.82)
bpy.ops.object.light_add(type='SUN')
bpy.context.object.rotation_euler = (0.49, -0.6, -0.35)
bpy.context.object.data.energy = 3.5
bpy.context.object.data.angle = 0.15

scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = 1024
scene.render.resolution_y = 1280
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT / 'art/coast_guard_radar_tower_preview.png')
bpy.ops.render.render(write_still=True)
