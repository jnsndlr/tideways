"""Build a small coastal town school building. Run with Blender --background --python."""
from math import atan2, cos, pi, radians, sin
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


def paint(name, hex_code, roughness=0.76, metallic=0.0):
    mat = bpy.data.materials.new(name)
    rgb = [int(hex_code[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    mat.diffuse_color = (*[((v + 0.055) / 1.055) ** 2.4 for v in rgb], 1)
    mat.use_nodes = True
    shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = mat.diffuse_color
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return mat


def box(name, xyz, size, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def cyl(name, xyz, radius, depth, mat, verts=16, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=xyz, rotation=rot
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def cone(name, xyz, r1, r2, depth, mat, verts=4, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(
        vertices=verts, radius1=r1, radius2=r2, depth=depth, location=xyz, rotation=rot
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def prism_gable(name, width, depth, height, center, mat, axis='X'):
    """Triangular gable prism. axis='X' means ridge runs along X; 'Y' means along Y."""
    hw, hd = width / 2, depth / 2
    if axis == 'X':
        verts = [
            (-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
            (-hw, 0, height), (hw, 0, height),
        ]
        faces = [
            (0, 1, 2, 3), (0, 1, 5, 4), (2, 3, 4, 5),
            (0, 4, 3), (1, 2, 5),
        ]
    else:
        verts = [
            (-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
            (0, -hd, height), (0, hd, height),
        ]
        faces = [
            (0, 1, 2, 3), (0, 3, 5, 4), (1, 2, 5, 4),
            (0, 1, 4), (3, 2, 5),
        ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = center
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def letters(body, x, y, z, size, mat):
    bpy.ops.object.text_add(location=(x, y, z), rotation=(pi / 2, 0, 0))
    obj = bpy.context.object
    obj.data.body = body
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.size = size
    obj.data.space_character = 1.08
    obj.data.extrude = 0.025
    obj.data.materials.append(mat)
    bpy.ops.object.convert(target='MESH')
    obj.name = body
    return obj


def join(parts, active):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()


# Tideways coastal palette
brick = paint('School brick', 'a55a45', roughness=0.84)
cream = paint('Trim oyster', 'e6dfd0', roughness=0.72)
spruce = paint('Roof spruce', '325954', roughness=0.68)
seam = paint('Standing seam', '4b7870', roughness=0.62)
stone = paint('Foundation stone', '9e9b8e', roughness=0.86)
concrete = paint('Walkway concrete', 'b3afa2', roughness=0.84)
dark = paint('Wrought iron', '2f3b40', roughness=0.55, metallic=0.4)
wood = paint('Entry cedar', '8c5535', roughness=0.72)
glass = paint('Classroom glass', '5e8d99', roughness=0.22)
brass = paint('School bell brass', 'cfa044', roughness=0.32, metallic=0.85)
flag_blue = paint('Pennant navy', '2a4c6e', roughness=0.78)
flag_gold = paint('Pennant gold', 'e2b448', roughness=0.78)
leaf = paint('Coastal shrub', '62835c', roughness=0.85)
soil = paint('Planting bed', '594a3c', roughness=0.92)


def window_unit(x, y, z, w, h, facing='-Y'):
    """Recessed multi-pane classroom window with sill, lintel, frame, and mullions."""
    # Facing determines orientation: -Y (front), +Y (back), -X (left), +X (right)
    if facing in ('-Y', '+Y'):
        s = -1 if facing == '-Y' else 1
        # Stone sill & lintel
        box('Window sill', (x, y + s * 0.09, z - h / 2 - 0.07), (w + 0.24, 0.24, 0.14), stone)
        box('Window lintel', (x, y + s * 0.06, z + h / 2 + 0.09), (w + 0.28, 0.18, 0.18), cream)
        # Outer frame
        box('Window frame', (x, y + s * 0.03, z), (w, 0.10, h), cream)
        # Glass pane
        box('Window glass', (x, y + s * 0.09, z), (w - 0.16, 0.04, h - 0.16), glass)
        # Vertical mullion + two horizontal muntins
        box('Mullion V', (x, y + s * 0.115, z), (0.07, 0.04, h - 0.12), cream)
        for dz in (-h * 0.16, h * 0.18):
            box('Muntin H', (x, y + s * 0.115, z + dz), (w - 0.12, 0.04, 0.06), cream)
    else:
        s = -1 if facing == '-X' else 1
        box('Window sill', (x + s * 0.09, y, z - h / 2 - 0.07), (0.24, w + 0.24, 0.14), stone)
        box('Window lintel', (x + s * 0.06, y, z + h / 2 + 0.09), (0.18, w + 0.28, 0.18), cream)
        box('Window frame', (x + s * 0.03, y, z), (0.10, w, h), cream)
        box('Window glass', (x + s * 0.09, y, z), (0.04, w - 0.16, h - 0.16), glass)
        box('Mullion V', (x + s * 0.115, y, z), (0.04, 0.07, h - 0.12), cream)
        for dz in (-h * 0.16, h * 0.18):
            box('Muntin H', (x + s * 0.115, y, z + dz), (0.04, w - 0.12, 0.06), cream)


def build_school():
    # --- 1. Foundation plinth & main brick body ---
    # Main footprint: 18m x 10m, plinth Z: 0..0.60, walls Z: 0.60..4.80
    plinth = box('Foundation plinth', (0, 0, 0.30), (18.3, 10.3, 0.60), stone)
    box('Water table trim', (0, 0, 0.63), (18.42, 10.42, 0.09), cream)
    box('Main walls', (0, 0, 2.70), (18.0, 10.0, 4.20), brick)
    # Corner brick pilasters for architectural crispness
    for sx in (-1, 1):
        for sy in (-1, 1):
            box('Corner pilaster', (sx * 8.95, sy * 4.95, 2.70), (0.42, 0.42, 4.20), brick)
    # Eaves cornice band
    box('Cornice band', (0, 0, 4.78), (18.36, 10.36, 0.22), cream)

    # --- 2. Main gable roof (ridge along X) ---
    gable_h = 2.65
    prism_gable('Main gable infill', 18.0, 10.0, gable_h, (0, 0, 4.80), brick, axis='X')

    eave_y = 5.65
    eave_z = 4.62
    ridge_z = 4.80 + gable_h + 0.12
    slope_len = (eave_y ** 2 + (ridge_z - eave_z) ** 2) ** 0.5
    slope_ang = atan2(ridge_z - eave_z, eave_y)
    roof_len = 19.1

    for sy in (-1, 1):
        mid_y = sy * eave_y / 2
        mid_z = (eave_z + ridge_z) / 2
        box(
            'Main roof slope',
            (0, mid_y, mid_z),
            (roof_len, slope_len, 0.18),
            spruce,
            rot=(-sy * slope_ang, 0, 0),
        )
        # Standing seams along the roof
        for x in range(-9, 10):
            box(
                'Roof seam',
                (x, mid_y, mid_z + 0.10),
                (0.055, slope_len - 0.1, 0.06),
                seam,
                rot=(-sy * slope_ang, 0, 0),
            )
        # Gable rake trim on both ends
        for sx in (-1, 1):
            box(
                'Rake trim',
                (sx * (roof_len / 2 - 0.04), mid_y, mid_z - 0.04),
                (0.14, slope_len + 0.08, 0.24),
                cream,
                rot=(-sy * slope_ang, 0, 0),
            )
    # Ridge cap
    box('Ridge cap', (0, 0, ridge_z + 0.09), (roof_len + 0.08, 0.26, 0.16), seam)

    # --- 3. Front entry vestibule & cross-gable porch ---
    vest_w, vest_d = 5.2, 2.4
    vest_y = -5.0 - vest_d / 2  # -6.2
    box('Vestibule plinth', (0, vest_y, 0.30), (vest_w + 0.25, vest_d + 0.25, 0.60), stone)
    box('Vestibule walls', (0, vest_y, 2.55), (vest_w, vest_d, 3.90), brick)
    box('Vestibule cornice', (0, vest_y, 4.52), (vest_w + 0.32, vest_d + 0.32, 0.20), cream)
    prism_gable('Vestibule gable', vest_w, vest_d + 0.8, 1.55, (0, vest_y + 0.4, 4.55), cream, axis='Y')

    # Cross-gable roof over vestibule
    ve_x = vest_w / 2 + 0.45
    ve_z = 4.42
    vr_z = 4.55 + 1.55 + 0.10
    v_span = (ve_x ** 2 + (vr_z - ve_z) ** 2) ** 0.5
    v_ang = atan2(vr_z - ve_z, ve_x)
    v_depth = vest_d + 2.2
    for sx in (-1, 1):
        box(
            'Vestibule roof',
            (sx * ve_x / 2, vest_y + 0.65, (ve_z + vr_z) / 2),
            (v_span, v_depth, 0.16),
            spruce,
            rot=(0, sx * v_ang, 0),
        )
        box(
            'Vestibule rake',
            (sx * ve_x / 2, -5.0 - vest_d - 0.45, (ve_z + vr_z) / 2 - 0.03),
            (v_span + 0.08, 0.14, 0.22),
            cream,
            rot=(0, sx * v_ang, 0),
        )
    box('Vestibule ridge', (0, vest_y + 0.65, vr_z + 0.07), (0.22, v_depth + 0.05, 0.14), seam)

    # Double entry doors & transom
    front_y = -5.0 - vest_d  # -7.4
    box('Door surround', (0, front_y - 0.05, 2.05), (2.56, 0.16, 2.90), cream)
    for sx in (-1, 1):
        box('Door leaf', (sx * 0.57, front_y - 0.08, 1.72), (1.08, 0.10, 2.24), wood)
        box('Door glass', (sx * 0.57, front_y - 0.12, 2.15), (0.72, 0.04, 0.92), glass)
        box('Door handle', (sx * 0.14, front_y - 0.16, 1.62), (0.05, 0.09, 0.24), brass)
    # Transom above double doors
    box('Transom frame', (0, front_y - 0.08, 3.12), (2.26, 0.10, 0.52), cream)
    box('Transom glass', (0, front_y - 0.11, 3.12), (2.10, 0.04, 0.38), glass)
    for dx in (-0.52, 0, 0.52):
        box('Transom mullion', (dx, front_y - 0.13, 3.12), (0.05, 0.04, 0.40), cream)

    # School signboard & lettering
    box('Signboard', (0, front_y - 0.09, 4.10), (4.25, 0.12, 0.58), spruce)
    box('Signboard frame', (0, front_y - 0.07, 4.10), (4.38, 0.08, 0.70), cream)
    letters('TIDEWAYS SCHOOL', 0, front_y - 0.16, 4.10, 0.34, cream)

    # Entry steps & porch landing
    box('Porch landing', (0, front_y - 0.75, 0.30), (3.4, 1.5, 0.60), stone)
    for i in range(3):
        step_h = 0.60 - (i + 1) * 0.15
        box('Entry step', (0, front_y - 1.5 - (i + 0.5) * 0.36, step_h / 2), (3.2, 0.36, step_h), stone)
    # Cheek walls & iron handrails
    for sx in (-1, 1):
        box('Step cheek', (sx * 1.72, front_y - 1.4, 0.48), (0.28, 2.6, 0.96), brick)
        box('Cheek cap', (sx * 1.72, front_y - 1.4, 0.99), (0.34, 2.68, 0.08), stone)
        box('Porch lamp mount', (sx * 1.65, front_y - 0.10, 2.85), (0.14, 0.14, 0.24), dark)
        box('Porch lamp glass', (sx * 1.65, front_y - 0.18, 2.74), (0.16, 0.16, 0.22), flag_gold)

    # --- 4. Bell cupola / belfry on the main ridge ---
    cup_z = ridge_z - 0.15  # 7.42
    box('Cupola base', (0, 0, cup_z + 0.35), (2.25, 2.25, 0.90), cream)
    box('Cupola plinth trim', (0, 0, cup_z + 0.84), (2.42, 2.42, 0.12), cream)
    # Four corner posts of open belfry
    belfry_z = cup_z + 1.55
    for sx in (-1, 1):
        for sy in (-1, 1):
            box('Belfry post', (sx * 0.88, sy * 0.88, belfry_z), (0.22, 0.22, 1.35), cream)
    # Low balustrade rails around belfry
    for sy in (-1, 1):
        box('Belfry rail Y', (0, sy * 0.88, cup_z + 1.08), (1.76, 0.10, 0.36), cream)
    for sx in (-1, 1):
        box('Belfry rail X', (sx * 0.88, 0, cup_z + 1.08), (0.10, 1.76, 0.36), cream)
    # Hanging brass school bell
    box('Bell yoke', (0, 0, cup_z + 2.02), (1.60, 0.12, 0.12), dark)
    cone('School bell', (0, 0, cup_z + 1.65), 0.36, 0.14, 0.52, brass, verts=16)
    cyl('Bell clapper', (0, 0, cup_z + 1.36), 0.06, 0.14, brass, verts=10)
    # Cupola cornice & pyramidal spire roof
    box('Cupola cornice', (0, 0, cup_z + 2.28), (2.48, 2.48, 0.18), cream)
    cone('Cupola spire', (0, 0, cup_z + 3.22), 1.80, 0.04, 1.72, spruce, verts=4, rot=(0, 0, radians(45)))
    cyl('Finial mast', (0, 0, cup_z + 4.35), 0.045, 0.70, brass, verts=10)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.11, location=(0, 0, cup_z + 4.22))
    orb = bpy.context.object
    orb.name = 'Finial orb'
    orb.data.materials.append(brass)

    # --- 5. Classroom windows & gable vents ---
    # Front facade (two on each side of vestibule)
    for x in (-6.7, -4.2, 4.2, 6.7):
        window_unit(x, -5.0, 2.65, 1.65, 2.35, facing='-Y')
    # Back facade (five evenly spaced)
    for x in (-6.8, -3.4, 0.0, 3.4, 6.8):
        window_unit(x, 5.0, 2.65, 1.65, 2.35, facing='+Y')
    # Side facades (two per side + circular gable vent)
    for sx, face in ((-1, '-X'), (1, '+X')):
        for y in (-2.2, 2.2):
            window_unit(sx * 9.0, y, 2.65, 1.65, 2.35, facing=face)
        # Circular attic vent in gable triangle
        cyl('Gable vent frame', (sx * 9.02, 0, 5.95), 0.58, 0.14, cream, verts=18, rot=(0, pi / 2, 0))
        cyl('Gable vent louver', (sx * 9.06, 0, 5.95), 0.45, 0.10, spruce, verts=18, rot=(0, pi / 2, 0))

    # --- 6. Front walkway, flagpole, shrubs & school bench ---
    box('Front walkway', (0, -10.8, 0.05), (3.1, 4.6, 0.10), concrete)
    # Planting beds flanking the vestibule
    for sx in (-1, 1):
        box('Planting curb', (sx * 5.8, -5.85, 0.14), (5.6, 1.5, 0.28), stone)
        box('Planting soil', (sx * 5.8, -5.85, 0.24), (5.3, 1.25, 0.12), soil)
        for dx, r in ((-1.7, 0.56), (0.0, 0.48), (1.7, 0.58)):
            bpy.ops.mesh.primitive_ico_sphere_add(
                subdivisions=2, radius=r, location=(sx * 5.8 + dx, -5.85, 0.55)
            )
            shrub = bpy.context.object
            shrub.name = 'Coastal shrub'
            shrub.scale = (1.1, 0.95, 0.78)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            shrub.data.materials.append(leaf)

    # Flagpole (front right)
    fx, fy = 5.6, -9.2
    cyl('Flagpole base', (fx, fy, 0.18), 0.48, 0.36, stone, verts=8)
    cyl('Flagpole mast', (fx, fy, 4.68), 0.06, 9.0, cream, verts=12)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=8, radius=0.11, location=(fx, fy, 9.24))
    fin = bpy.context.object
    fin.name = 'Flagpole finial'
    fin.data.materials.append(brass)
    box('Flag body', (fx + 0.78, fy, 8.55), (1.45, 0.04, 0.85), flag_blue)
    box('Flag stripe', (fx + 0.78, fy, 8.55), (1.46, 0.05, 0.22), flag_gold)

    # Wooden bench (front left)
    bx, by = -4.6, -9.2
    box('Bench seat', (bx, by, 0.48), (1.85, 0.46, 0.07), wood)
    box('Bench back', (bx, by + 0.22, 0.82), (1.85, 0.06, 0.34), wood, rot=(radians(-12), 0, 0))
    for dx in (-0.72, 0.72):
        box('Bench leg', (bx + dx, by, 0.24), (0.08, 0.42, 0.48), dark)
        box('Bench post', (bx + dx, by + 0.21, 0.64), (0.07, 0.07, 0.42), dark)

    return plinth


plinth = build_school()

# Configure viewport for editable .blend
direction = Vector((20, -34, 17))
rotation = (-direction).to_track_quat('-Z', 'Y')
target = Vector((0, -2.0, 3.6))
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 34
        space.shading.color_type = 'MATERIAL'

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'art/small_school.blend'))

# Export joined single-mesh GLB for Godot
all_parts = list(scene.objects)
join(all_parts, plinth)
plinth.name = 'SmallSchool'
bpy.ops.export_scene.gltf(
    filepath=str(ROOT / 'assets/models/small_school.glb'),
    export_format='GLB',
)

# Render preview image
box('Preview ground', (0, 0, -0.16), (400, 400, 0.32), paint('Coastal turf', '88937c'))
bpy.ops.object.camera_add(location=target + direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 26
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
scene.render.resolution_x = 1280
scene.render.resolution_y = 860
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT / 'art/small_school_preview.png')
bpy.ops.render.render(write_still=True)
