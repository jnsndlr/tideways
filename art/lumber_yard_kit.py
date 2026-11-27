"""Build the Tideways lumber yard kit, individual GLBs, and a yard diorama preview.

Run with Blender in background mode and --python art/lumber_yard_kit.py.
Dimensions are metres. Blender -Y is the front of each building and vehicle.
"""
from math import atan2, cos, pi, sin, tau
from pathlib import Path
from random import Random

import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/lumber_yard_kit"
OUT.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rng = Random(4207)

palette = {
    "bark": ("4E3B2E", 0.90, 0.0),
    "bark_dark": ("3A2B22", 0.92, 0.0),
    "endgrain": ("E5C896", 0.84, 0.0),
    "heartwood": ("C99B63", 0.84, 0.0),
    "debarked": ("D8B684", 0.82, 0.0),
    "fresh_wood": ("E6C994", 0.80, 0.0),
    "kiln_wood": ("D4A76A", 0.78, 0.0),
    "cedar": ("A66E46", 0.84, 0.0),
    "timber": ("7D5136", 0.86, 0.0),
    "roof": ("3D4F54", 0.65, 0.2),
    "seam": ("566A6F", 0.60, 0.25),
    "corrugated": ("7B8B8C", 0.55, 0.35),
    "rust": ("9B5238", 0.78, 0.15),
    "steel": ("495358", 0.50, 0.45),
    "steel_light": ("9AA6A3", 0.45, 0.50),
    "blade": ("C8D2D4", 0.25, 0.85),
    "concrete": ("A7A59C", 0.90, 0.0),
    "gravel": ("9E9789", 0.95, 0.0),
    "dirt": ("7D6650", 0.95, 0.0),
    "siding": ("A84938", 0.84, 0.0),
    "office_wall": ("6E8275", 0.84, 0.0),
    "cream": ("F2E4C8", 0.82, 0.0),
    "glass": ("628A96", 0.20, 0.10),
    "shade": ("2E3234", 0.88, 0.0),
    "yellow": ("E0A838", 0.50, 0.15),
    "orange": ("D96E2B", 0.52, 0.15),
    "tire": ("2B3033", 0.90, 0.0),
    "tread": ("3E4548", 0.90, 0.0),
    "sawdust": ("E3C17B", 0.94, 0.0),
    "sawdust_dark": ("C69F58", 0.94, 0.0),
    "strap": ("292D30", 0.45, 0.50),
}

materials = {}
for name, (hex_value, rough, metal) in palette.items():
    color = [int(hex_value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = (*[((c + 0.055) / 1.055) ** 2.4 for c in color], 1.0)
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = linear
    mat.use_nodes = True
    shader = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = linear
    shader.inputs["Roughness"].default_value = rough
    shader.inputs["Metallic"].default_value = metal
    materials[name] = mat

# Batch disconnected pieces into a single material-indexed mesh per prop.
verts, faces, colors = [], [], []


def add(points, polygons, color):
    start = len(verts)
    verts.extend(points)
    faces.extend(tuple(start + i for i in face) for face in polygons)
    colors.extend([color] * len(polygons))


def box(center, size, color, rotation=(0, 0, 0)):
    matrix = Euler(rotation).to_matrix()
    points = [
        Vector(center) + matrix @ Vector((x * size[0] / 2, y * size[1] / 2, z * size[2] / 2))
        for z in (-1, 1)
        for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
    add(
        points,
        [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)],
        color,
    )


def cylinder(center, r1, r2, height, color, sides=16, axis="Z", rotation=(0, 0, 0), cap_color=None):
    matrix = Euler(rotation).to_matrix()
    points = []
    for z, radius in ((-height / 2, r1), (height / 2, r2)):
        for i in range(sides):
            a = i * tau / sides
            x, y = radius * cos(a), radius * sin(a)
            if axis == "X":
                local = Vector((z, y, -x))
            elif axis == "Y":
                local = Vector((x, z, -y))
            else:
                local = Vector((x, y, z))
            points.append(Vector(center) + matrix @ local)
    side_faces = [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides)]
    cap_faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
    if cap_color and cap_color != color:
        start = len(verts)
        verts.extend(points)
        faces.extend(tuple(start + i for i in f) for f in side_faces)
        colors.extend([color] * len(side_faces))
        faces.extend(tuple(start + i for i in f) for f in cap_faces)
        colors.extend([cap_color] * len(cap_faces))
    else:
        add(points, cap_faces + side_faces, color)


def strut(a, b, width, color, depth=None):
    a, b = Vector(a), Vector(b)
    direction = b - a
    if direction.length < 1e-5:
        return
    box(
        (a + b) / 2,
        (width, depth or width, direction.length),
        color,
        direction.to_track_quat("Z", "Y").to_euler(),
    )


def finish(name, origin=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    slots = list(dict.fromkeys(colors))
    for color in slots:
        mesh.materials.append(materials[color])
    mesh.polygons.foreach_set("material_index", [slots.index(c) for c in colors])
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.location = origin
    verts.clear()
    faces.clear()
    colors.clear()
    return obj


def log_piece(center, radius, length, bark_col="bark", end_col="endgrain", axis="X", rot=(0, 0, 0)):
    taper = rng.uniform(0.92, 1.0)
    cylinder(center, radius, radius * taper, length, bark_col, sides=10, axis=axis, rotation=rot, cap_color=end_col)


def gable_roof(cx, cy, z_eave, w, d, pitch, roof_col="roof", seam_col="seam", overhang=0.45):
    profile = [(-w / 2 - overhang, z_eave), (0, z_eave + pitch), (w / 2 + overhang, z_eave)]
    for (x1, z1), (x2, z2) in zip(profile, profile[1:]):
        angle = -atan2(z2 - z1, x2 - x1)
        span = ((x2 - x1) ** 2 + (z2 - z1) ** 2) ** 0.5
        box((cx + (x1 + x2) / 2, cy, (z1 + z2) / 2 + 0.08), (span + 0.14, d + overhang * 2, 0.16), roof_col, (0, angle, 0))
        n_seams = max(2, round(span / 0.7))
        for i in range(n_seams):
            t = (i + 0.5) / n_seams
            box(
                (cx + x1 + (x2 - x1) * t, cy, z1 + (z2 - z1) * t + 0.17),
                (0.05, d + overhang * 2 + 0.02, 0.05),
                seam_col,
                (0, angle, 0),
            )


def window(x, y, z, w=1.0, h=1.0, facing="-Y"):
    if facing == "-Y":
        box((x, y, z), (w + 0.16, 0.14, h + 0.16), "cream")
        box((x, y - 0.08, z), (w, 0.07, h), "glass")
        box((x, y - 0.12, z), (0.06, 0.04, h), "cream")
        box((x, y - 0.12, z), (w, 0.04, 0.06), "cream")
    else:
        sign = 1 if facing == "+X" else -1
        box((x, y, z), (0.14, w + 0.16, h + 0.16), "cream")
        box((x + sign * 0.08, y, z), (0.07, w, h), "glass")
        box((x + sign * 0.12, y, z), (0.04, 0.06, h), "cream")
        box((x + sign * 0.12, y, z), (0.04, w, 0.06), "cream")


# ---------------------------------------------------------------------------
# 1. SAWMILL (Main mill building, headrig saw, infeed/outfeed, cyclone & stack)
# ---------------------------------------------------------------------------
def sawmill():
    # Concrete slab & raised timber deck
    box((0, 0, 0.18), (14.6, 8.6, 0.36), "concrete")
    box((0, 0, 0.42), (14.0, 8.0, 0.12), "timber")

    # Enclosed back wall & partial side walls, open front bay for visibility
    box((0, 3.85, 2.55), (13.6, 0.28, 4.2), "siding")
    for i in range(-16, 17):
        box((i * 0.41, 4.0, 2.55), (0.06, 0.07, 4.1), "rust")

    # End walls with large pass-through openings for log infeed (-X) and lumber outfeed (+X)
    for sx in (-1, 1):
        x = sx * 6.8
        box((x, 2.2, 2.55), (0.26, 3.4, 4.2), "siding")
        box((x, -2.5, 2.55), (0.26, 2.8, 4.2), "siding")
        box((x, -0.3, 3.85), (0.26, 2.4, 1.6), "siding")
        # Gable triangle infill
        add(
            [
                (x - 0.13, -3.9, 4.65), (x - 0.13, 3.9, 4.65), (x - 0.13, 0, 6.85),
                (x + 0.13, -3.9, 4.65), (x + 0.13, 3.9, 4.65), (x + 0.13, 0, 6.85),
            ],
            [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)],
            "siding",
        )

    # Heavy timber columns along open front & interior
    for x in (-6.7, -3.35, 0.0, 3.35, 6.7):
        box((x, -3.85, 2.55), (0.30, 0.30, 4.2), "timber")
        box((x, 3.7, 2.55), (0.28, 0.28, 4.2), "timber")
        # Knee braces
        strut((x, -3.85, 3.55), (x, -2.95, 4.55), 0.16, "cedar")
        if x < 6.7:
            strut((x, -3.85, 3.75), (x + 0.85, -3.85, 4.55), 0.15, "cedar")
        if x > -6.7:
            strut((x, -3.85, 3.75), (x - 0.85, -3.85, 4.55), 0.15, "cedar")
    # Front header beam
    box((0, -3.85, 4.58), (13.9, 0.32, 0.32), "timber")

    # Main gabled roof (ridge runs along X)
    # Build roof slopes along Y using rotated slabs
    for sy in (-1, 1):
        angle = -sy * atan2(2.2, 4.35)
        span = (2.2 ** 2 + 4.35 ** 2) ** 0.5
        box((0, sy * 2.18, 5.78), (15.0, span + 0.25, 0.18), "roof", (angle, 0, 0))
        for ix in range(-10, 11):
            box((ix * 0.72, sy * 2.18, 5.87), (0.06, span + 0.27, 0.05), "seam", (angle, 0, 0))

    # Clerestory / monitor ridge vent
    box((0, 0, 7.15), (9.0, 1.8, 0.95), "corrugated")
    for sy in (-1, 1):
        for ix in range(-4, 5):
            box((ix * 0.95, sy * 0.92, 7.18), (0.65, 0.08, 0.52), "glass")
        box((0, sy * 0.65, 7.75), (9.5, 1.35, 0.14), "roof", (-sy * 0.28, 0, 0))

    # Interior headrig circular saw & carriage
    box((-0.6, -0.3, 1.05), (4.2, 1.5, 0.55), "steel")
    box((-0.4, 0.45, 2.05), (1.7, 0.85, 1.55), "yellow")
    # Big circular saw blade
    cylinder((-0.4, -0.15, 1.85), 0.88, 0.88, 0.06, "blade", sides=24, axis="Y")
    cylinder((-0.4, -0.15, 1.85), 0.18, 0.18, 0.12, "steel", sides=12, axis="Y")
    # Upper blade guard
    box((-0.4, -0.15, 2.42), (1.85, 0.22, 0.58), "orange")

    # Log on the carriage being cut
    log_piece((-2.2, -0.3, 1.62), 0.34, 4.4, "bark", "endgrain", axis="X")
    # Freshly cut planks exiting on the +X side
    for iz in range(3):
        box((2.8, -0.3 + (iz - 1) * 0.22, 1.38 + iz * 0.09), (3.4, 0.26, 0.07), "fresh_wood")

    # Log infeed roller deck (-X)
    box((-8.9, -0.3, 0.95), (4.2, 1.65, 0.16), "steel")
    for x in (-10.8, -9.2, -7.6):
        for sy in (-0.7, 0.7):
            box((x, -0.3 + sy, 0.48), (0.18, 0.18, 0.96), "steel")
    for i in range(6):
        cylinder((-10.6 + i * 0.7, -0.3, 1.12), 0.11, 0.11, 1.45, "steel_light", sides=10, axis="Y")
    # Waiting log on infeed deck
    log_piece((-9.0, -0.3, 1.52), 0.32, 3.8, "bark_dark", "endgrain", axis="X")

    # Outfeed sorting table (+X)
    box((8.8, -0.3, 0.95), (3.8, 2.1, 0.14), "cedar")
    for x in (7.4, 10.4):
        for sy in (-0.9, 0.9):
            box((x, -0.3 + sy, 0.48), (0.16, 0.16, 0.96), "timber")
    for i in range(5):
        box((8.8, -1.0 + i * 0.36, 1.07), (3.5, 0.24, 0.07), "fresh_wood")

    # Cyclone dust collector & tall smokestack on the rear-left
    cylinder((-5.4, 5.1, 4.2), 1.05, 1.05, 2.2, "corrugated", sides=16)
    cylinder((-5.4, 5.1, 2.1), 0.28, 1.05, 2.0, "corrugated", sides=16)
    cylinder((-5.4, 5.1, 5.7), 0.42, 0.42, 1.2, "steel", sides=12)
    for sx in (-0.85, 0.85):
        for sy in (-0.85, 0.85):
            box((-5.4 + sx, 5.1 + sy, 2.2), (0.14, 0.14, 4.4), "steel")
    # Duct pipe from mill roof to cyclone
    strut((-2.0, 2.5, 5.2), (-5.4, 5.1, 4.7), 0.38, "steel_light")

    # Tall smokestack
    cylinder((4.6, 4.9, 4.8), 0.42, 0.32, 9.6, "steel", sides=16)
    cylinder((4.6, 4.9, 9.75), 0.48, 0.36, 0.28, "rust", sides=16)
    box((4.6, 4.9, 0.6), (1.3, 1.3, 1.2), "concrete")


# ---------------------------------------------------------------------------
# 2. LOG PILES OF VARIOUS STATES
# ---------------------------------------------------------------------------
def log_pile_raw():
    """Pyramid of raw bark-covered felled logs with timber skids and chocks."""
    for x in (-1.7, 1.7):
        box((x, 0, 0.11), (0.24, 3.6, 0.22), "timber")
        for sy in (-1.65, 1.65):
            box((x, sy, 0.28), (0.28, 0.26, 0.24), "cedar")

    rows = [5, 4, 3, 2, 1]
    r = 0.29
    for row_idx, count in enumerate(rows):
        z = 0.22 + r + row_idx * (r * 1.72)
        for i in range(count):
            y = (i - (count - 1) / 2) * (r * 2.08) + rng.uniform(-0.03, 0.03)
            rad = r * rng.uniform(0.90, 1.07)
            length = rng.uniform(5.2, 6.1)
            dx = rng.uniform(-0.22, 0.22)
            col = "bark" if (row_idx + i) % 3 else "bark_dark"
            log_piece((dx, y, z), rad, length, col, "endgrain", axis="X", rot=(0, 0, rng.uniform(-0.025, 0.025)))


def log_pile_debarked():
    """Neatly stacked peeled/debarked pale logs inside steel bunk uprights."""
    # Steel bunks
    for x in (-1.8, 1.8):
        box((x, 0, 0.10), (0.20, 3.1, 0.20), "steel")
        for sy in (-1.48, 1.48):
            box((x, sy, 1.05), (0.16, 0.16, 2.0), "steel")
    r = 0.25
    for row_idx in range(3):
        count = 5 if row_idx % 2 == 0 else 4
        z = 0.20 + r + row_idx * (r * 1.78)
        for i in range(count):
            y = (i - (count - 1) / 2) * (r * 2.04)
            length = rng.uniform(5.4, 5.75)
            log_piece((rng.uniform(-0.08, 0.08), y, z), r * rng.uniform(0.95, 1.03), length, "debarked", "endgrain", axis="X")


def lumber_stack_green():
    """Freshly sawn green lumber stacked with drying stickers on timber skids."""
    for x in (-1.8, 0.0, 1.8):
        box((x, 0, 0.10), (0.20, 2.1, 0.20), "timber")
    layers = 8
    for iz in range(layers):
        z_board = 0.26 + iz * 0.19
        # 5 boards across Y
        for iy in range(5):
            y = (iy - 2) * 0.39
            length = 4.6 + rng.uniform(-0.18, 0.18)
            box((rng.uniform(-0.08, 0.08), y, z_board), (length, 0.33, 0.10), "fresh_wood" if (iz + iy) % 2 else "endgrain")
        # Drying stickers between layers
        if iz < layers - 1:
            for x in (-1.8, -0.6, 0.6, 1.8):
                box((x, 0, z_board + 0.085), (0.07, 1.98, 0.05), "cedar")


def lumber_stack_banded():
    """Kiln-dried finished lumber bundles strapped with steel bands, stacked 2 high."""
    for x in (-1.6, 1.6):
        box((x, 0, 0.09), (0.18, 1.65, 0.18), "timber")
    for level in range(2):
        z = 0.54 + level * 0.88
        # Bundle core
        box((0, 0, z), (4.6, 1.45, 0.72), "kiln_wood")
        # Plank seams for visual texture
        for iz in (-0.24, -0.08, 0.08, 0.24):
            box((0, 0, z + iz), (4.62, 1.47, 0.018), "heartwood")
        # Steel straps
        for x in (-1.55, 0.0, 1.55):
            box((x, 0, z), (0.08, 1.50, 0.76), "strap")
        # Spacers between bundles
        if level == 0:
            for x in (-1.5, 1.5):
                box((x, 0, z + 0.44), (0.14, 1.48, 0.14), "timber")


def slab_scrap_pile():
    """Heap of bark edging slabs, offcuts, and scrap timber."""
    box((0, 0, 0.14), (3.4, 2.4, 0.28), "dirt")
    for _ in range(26):
        x = rng.uniform(-1.1, 1.1)
        y = rng.uniform(-0.75, 0.75)
        dist = (x * x + y * y) ** 0.5
        z = max(0.24, 0.85 - dist * 0.42) + rng.uniform(-0.08, 0.12)
        length = rng.uniform(1.1, 2.3)
        w = rng.uniform(0.14, 0.28)
        h = rng.uniform(0.06, 0.13)
        col = rng.choice(["bark", "cedar", "timber", "heartwood", "fresh_wood"])
        rot = (rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(-0.9, 0.9))
        box((x, y, z), (length, w, h), col, rot)


# ---------------------------------------------------------------------------
# 3. OTHER BUILDINGS (Drying Kiln, Lumber Shed, Yard Office + Weighbridge, Sawdust Silo)
# ---------------------------------------------------------------------------
def drying_kiln():
    """Industrial lumber drying kiln with insulated doors and roof steam vents."""
    box((0, 0, 0.15), (9.4, 6.4, 0.30), "concrete")
    box((0, 0, 2.25), (9.0, 6.0, 3.9), "corrugated")
    # Corrugated vertical ribs
    for x in range(-4, 5):
        box((x * 1.0, -3.02, 2.25), (0.08, 0.08, 3.8), "steel_light")
        box((x * 1.0, 3.02, 2.25), (0.08, 0.08, 3.8), "steel_light")
    # Slight shed roof
    box((0, 0, 4.35), (9.6, 6.7, 0.22), "roof", (0.06, 0, 0))
    # Two heavy insulated kiln bays on the front (-Y)
    for sx in (-2.2, 2.2):
        box((sx, -3.06, 1.95), (3.4, 0.18, 3.3), "steel")
        box((sx, -3.14, 1.95), (3.1, 0.12, 3.05), "rust")
        # Locking bars
        for dx in (-0.35, 0.35):
            box((sx + dx, -3.22, 1.95), (0.07, 0.08, 2.8), "steel_light")
    # Roof exhaust stacks / steam vents
    for x in (-2.6, 0.0, 2.6):
        cylinder((x, 0.6, 4.95), 0.36, 0.36, 1.1, "steel", sides=14)
        cylinder((x, 0.6, 5.62), 0.54, 0.12, 0.32, "roof", sides=14)
    # Side boiler/piping unit
    box((5.1, 0.4, 1.35), (1.3, 2.6, 2.1), "steel")
    cylinder((5.1, 1.2, 3.2), 0.22, 0.22, 1.8, "rust", sides=12)


def lumber_shed():
    """Open-front timber storage shed with tiered racks and stacked lumber."""
    box((0, 0, 0.12), (12.4, 5.4, 0.24), "concrete")
    # Back wall
    box((0, 2.48, 2.35), (12.0, 0.22, 4.2), "cedar")
    # Posts along back and front
    for x in (-5.8, -1.95, 1.95, 5.8):
        box((x, 2.35, 2.35), (0.24, 0.24, 4.2), "timber")
        box((x, -2.35, 2.65), (0.26, 0.26, 4.8), "timber")
        # Sloped rafter
        strut((x, 2.35, 4.45), (x, -2.55, 5.05), 0.20, "timber")
    # Sloped metal roof
    box((0, -0.1, 4.88), (12.8, 5.9, 0.18), "roof", (-0.12, 0, 0))
    for i in range(-8, 9):
        box((i * 0.76, -0.1, 4.98), (0.05, 5.92, 0.05), "seam", (-0.12, 0, 0))
    # Tiered rack shelves + lumber bundles inside 3 bays
    for bay_x in (-3.88, 0.0, 3.88):
        for z_rack in (0.45, 1.75, 3.05):
            box((bay_x, 0.4, z_rack), (3.55, 2.4, 0.12), "steel")
            if z_rack < 3.0 or bay_x != 3.88:
                col = "kiln_wood" if z_rack > 1.5 else "fresh_wood"
                box((bay_x, 0.4, z_rack + 0.42), (3.25, 1.85, 0.68), col)
                for dx in (-1.0, 1.0):
                    box((bay_x + dx, 0.4, z_rack + 0.42), (0.07, 1.88, 0.72), "strap")


def yard_office():
    """Small scale house / lumber yard office with porch and awning."""
    box((0, 0, 0.14), (5.6, 4.4, 0.28), "concrete")
    box((0, 0.2, 1.75), (5.2, 3.8, 2.95), "office_wall")
    # Corner trim
    for sx in (-2.6, 2.6):
        for sy in (-1.7, 2.1):
            box((sx, sy, 1.75), (0.16, 0.16, 2.95), "cream")
    gable_roof(0, 0.2, 3.22, 5.2, 3.8, 1.35)
    # Front door & scale-viewing window
    box((-1.25, -1.74, 1.35), (1.05, 0.14, 2.15), "cream")
    box((-1.25, -1.80, 1.35), (0.88, 0.10, 1.98), "timber")
    window(0.95, -1.72, 1.82, 1.7, 1.05, "-Y")
    window(-2.62, 0.2, 1.82, 1.2, 1.05, "-X")
    # Front porch & roof
    box((0, -2.35, 0.18), (5.0, 1.25, 0.26), "cedar")
    box((0, -2.42, 2.75), (5.3, 1.55, 0.14), "roof", (0.14, 0, 0))
    for x in (-2.3, 2.3):
        box((x, -2.85, 1.48), (0.14, 0.14, 2.55), "cream")
    # Signboard on porch fascia
    box((0, -3.18, 2.86), (2.8, 0.12, 0.48), "cream")
    box((0, -3.25, 2.86), (2.6, 0.05, 0.34), "siding")


def weighbridge():
    """Drive-on truck scale platform."""
    box((0, 0, 0.12), (9.6, 3.6, 0.24), "concrete")
    box((0, 0, 0.25), (8.6, 3.0, 0.08), "steel")
    # Ramps at both ends
    for sx in (-1, 1):
        box((sx * 5.2, 0, 0.10), (1.2, 3.4, 0.18), "concrete", (0, sx * 0.15, 0))
    # Yellow safety curbs
    for sy in (-1.62, 1.62):
        box((0, sy, 0.34), (8.8, 0.18, 0.22), "yellow")


def sawdust_silo():
    """Elevated cylindrical sawdust hopper silo on steel legs with discharge chute."""
    r = 1.9
    # 4 steel legs + cross bracing
    leg_pts = [(-1.45, -1.45), (1.45, -1.45), (1.45, 1.45), (-1.45, 1.45)]
    for x, y in leg_pts:
        box((x, y, 0.15), (0.5, 0.5, 0.30), "concrete")
        box((x, y, 1.85), (0.24, 0.24, 3.4), "steel")
    for i in range(4):
        x1, y1 = leg_pts[i]
        x2, y2 = leg_pts[(i + 1) % 4]
        if i != 0:  # Leave front open for truck drive-under
            strut((x1, y1, 0.5), (x2, y2, 2.9), 0.10, "steel")
            strut((x2, y2, 0.5), (x1, y1, 2.9), 0.10, "steel")
        strut((x1, y1, 3.2), (x2, y2, 3.2), 0.16, "steel")

    # Hopper cone & main cylinder
    cylinder((0, 0, 2.45), 0.45, r, 1.7, "steel_light", sides=20)
    cylinder((0, 0, 5.5), r, r, 4.4, "corrugated", sides=20)
    for z in (3.8, 5.0, 6.2, 7.4):
        cylinder((0, 0, z), r + 0.06, r + 0.06, 0.10, "steel", sides=20)
    # Conical roof
    cylinder((0, 0, 8.3), r + 0.14, 0.25, 1.2, "roof", sides=20)
    # Side ladder
    for dx in (-0.22, 0.22):
        box((r + 0.16, dx, 4.1), (0.06, 0.06, 7.2), "steel")
    for z in range(1, 20):
        box((r + 0.18, 0, z * 0.38), (0.05, 0.44, 0.05), "steel")


# ---------------------------------------------------------------------------
# 4. EQUIPMENT & PROPS (Log Loader, Gantry Crane, Wood Chipper, Sawdust Mound)
# ---------------------------------------------------------------------------
def log_loader():
    """Wheeled front-end log loader with hydraulic grapple jaws."""
    # Rear engine hood & counterweight
    box((0, 0.95, 1.25), (1.65, 2.2, 1.15), "yellow")
    box((0, 2.15, 1.05), (1.72, 0.45, 0.85), "steel")
    # Exhaust pipe
    cylinder((0.58, 1.55, 2.25), 0.08, 0.08, 1.05, "shade", sides=10)
    # Operator cab
    box((0, -0.15, 2.05), (1.42, 1.45, 1.35), "shade")
    box((0, -0.15, 2.10), (1.46, 1.15, 0.95), "glass")
    box((0, -0.15, 2.10), (1.15, 1.49, 0.95), "glass")
    box((0, -0.15, 2.78), (1.56, 1.62, 0.14), "yellow")
    # Chassis frame
    box((0, 0.15, 0.72), (1.15, 3.2, 0.42), "steel")

    # Lift arms extending forward (-Y)
    for sx in (-0.62, 0.62):
        strut((sx, -0.35, 1.55), (sx, -2.35, 1.15), 0.18, "yellow", depth=0.22)
        strut((sx, -0.35, 1.10), (sx, -1.95, 1.25), 0.11, "steel_light")
    # Crossbar
    box((0, -2.35, 1.15), (1.55, 0.22, 0.22), "steel")

    # Curved hydraulic log grapple forks
    for sx in (-0.52, 0.52):
        # Lower fork tine
        box((sx, -2.85, 0.62), (0.14, 1.15, 0.14), "orange")
        # Vertical back
        box((sx, -2.38, 1.12), (0.14, 0.18, 1.05), "orange")
        # Upper curved clamp jaw
        strut((sx, -2.38, 1.58), (sx, -2.95, 1.42), 0.12, "orange")
        strut((sx, -2.95, 1.42), (sx, -3.25, 0.98), 0.12, "orange")

    # Carry a log in the grapple!
    log_piece((0, -2.82, 0.98), 0.26, 3.2, "bark", "endgrain", axis="X")

    # 4 heavy off-road tires
    for y in (-1.05, 1.25):
        for sx in (-1, 1):
            r = 0.68
            cylinder((sx * 0.98, y, r), r, r, 0.44, "tire", sides=18, axis="X")
            cylinder((sx * 1.12, y, r), r * 0.56, r * 0.56, 0.18, "yellow", sides=14, axis="X")
            cylinder((sx * 1.18, y, r), r * 0.24, r * 0.24, 0.14, "steel", sides=10, axis="X")
            for i in range(14):
                a = i * tau / 14
                box((sx * 0.98, y - r * sin(a), r + r * cos(a)), (0.46, 0.12, 0.08), "tread", (a, 0, 0))


def gantry_crane():
    """Overhead A-frame yard gantry crane spanning a log/lumber bay."""
    span_x = 9.0
    h = 6.2
    for sx in (-1, 1):
        x = sx * span_x / 2
        # Wheel bogie beam along Y
        box((x, 0, 0.35), (0.55, 4.4, 0.45), "yellow")
        for sy in (-1.7, 1.7):
            cylinder((x, sy, 0.28), 0.28, 0.28, 0.26, "steel", sides=14, axis="X")
            strut((x, sy, 0.55), (x, 0, h), 0.26, "yellow")
        # Mid brace
        box((x, 0, 3.2), (0.20, 2.1, 0.20), "steel")

    # Overhead I-beam bridge
    box((0, 0, h + 0.25), (span_x + 1.8, 0.55, 0.62), "yellow")
    box((0, 0, h + 0.58), (span_x + 1.8, 0.72, 0.10), "steel")
    box((0, 0, h - 0.08), (span_x + 1.8, 0.72, 0.10), "steel")

    # Hoist trolley & spreader bar hanging below
    tx = -1.2
    box((tx, 0, h - 0.35), (1.3, 0.95, 0.55), "orange")
    for dx in (-0.42, 0.42):
        cylinder((tx + dx, 0, h - 1.55), 0.03, 0.03, 2.2, "steel_light", sides=8)
    box((tx, 0, h - 2.68), (2.4, 0.22, 0.22), "orange")
    for dx in (-0.95, 0.95):
        box((tx + dx, 0, h - 2.98), (0.10, 0.12, 0.45), "steel")


def wood_chipper():
    """Towable industrial wood chipper with feed chute and discharge spout."""
    # Trailer frame & tongue
    box((0, 0, 0.55), (1.35, 2.4, 0.20), "steel")
    box((0, -1.75, 0.52), (0.16, 1.3, 0.14), "steel")
    # Wheels
    for sx in (-1, 1):
        cylinder((sx * 0.85, 0.1, 0.42), 0.42, 0.42, 0.26, "tire", sides=16, axis="X")
        cylinder((sx * 0.96, 0.1, 0.42), 0.22, 0.22, 0.10, "yellow", sides=12, axis="X")
    # Engine & flywheel drum housing
    box((0, -0.45, 1.15), (1.15, 1.15, 0.95), "orange")
    cylinder((0, 0.45, 1.25), 0.68, 0.68, 0.52, "yellow", sides=16, axis="X")
    # Wide flared feed chute (+Y)
    box((0, 1.35, 1.22), (1.10, 1.05, 0.78), "orange", (-0.15, 0, 0))
    box((0, 1.85, 1.18), (0.94, 0.12, 0.64), "shade", (-0.15, 0, 0))
    # Angled discharge chute curving up and forward
    strut((0, 0.45, 1.75), (0, -0.15, 2.85), 0.26, "steel_light")
    strut((0, -0.15, 2.85), (0, -0.95, 3.05), 0.24, "yellow")


def sawdust_mound():
    """Conical sawdust / woodchip pile."""
    cylinder((0, 0, 0.85), 2.8, 0.35, 1.7, "sawdust", sides=16)
    cylinder((0.9, 0.5, 0.52), 1.65, 0.28, 1.05, "sawdust_dark", sides=14)
    cylinder((-1.0, -0.4, 0.45), 1.45, 0.25, 0.90, "sawdust", sides=12)


# ---------------------------------------------------------------------------
# EXPORT INDIVIDUAL GLBs & ASSEMBLE YARD DIORAMA
# ---------------------------------------------------------------------------
def asset(name, build, x, y, rot_z=0.0):
    objects = build() or [finish(name)]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / (name + ".glb")),
        use_selection=True,
        export_format="GLB",
    )
    objects[0].location += Vector((x, y, 0))
    objects[0].rotation_euler.z = rot_z
    return objects[0]


# Buildings
asset("sawmill", sawmill, -2.5, 9.5)
asset("drying_kiln", drying_kiln, 14.5, 10.0)
asset("lumber_shed", lumber_shed, 12.5, -11.5, 0.0)
asset("yard_office", yard_office, -17.5, -9.5)
asset("weighbridge", weighbridge, -17.5, -15.5)
asset("sawdust_silo", sawdust_silo, -15.5, 10.5)

# Log piles & lumber stacks in various states
asset("log_pile_raw", log_pile_raw, -16.5, 0.5)
asset("log_pile_debarked", log_pile_debarked, -8.5, 0.5)
asset("lumber_stack_green", lumber_stack_green, 8.5, 0.8)
asset("lumber_stack_banded", lumber_stack_banded, 15.5, 0.8)
asset("slab_scrap_pile", slab_scrap_pile, -20.5, 6.2)

# Equipment & props
asset("gantry_crane", gantry_crane, -16.5, 0.5)
asset("log_loader", log_loader, -1.5, -4.5, -0.55)
asset("wood_chipper", wood_chipper, -11.5, 6.8, 0.45)
asset("sawdust_mound", sawdust_mound, -15.5, 15.2)

# Yard ground, gravel pad, compacted dirt lanes, and perimeter fence
box((0, 0, -0.35), (52, 40, 0.70), "gravel")
box((0, -4.8, 0.015), (46, 5.2, 0.03), "dirt")
box((-4.5, 2.0, 0.017), (4.8, 16.0, 0.034), "dirt")
# Perimeter timber fence along back and sides
for a, b, y in [(-24.5, 24.5, 18.5), (-24.5, -22.0, -18.5), (1.0, 24.5, -18.5)]:
    count = max(2, round((b - a) / 2.8))
    for i in range(count + 1):
        box((a + i * (b - a) / count, y, 0.72), (0.16, 0.16, 1.44), "timber")
    for z in (0.48, 1.05):
        box(((a + b) / 2, y, z), (b - a, 0.09, 0.12), "cedar")
asset("lumber_yard_ground", lambda: None, 0, 0)

# Camera, lighting, and preview render
target = Vector((-1.0, 0.5, 1.5))
direction = Vector((26, -58, 42))
rotation = (-direction).to_track_quat("-Z", "Y")
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = target
        space.region_3d.view_distance = 62
        space.shading.color_type = "MATERIAL"

bpy.ops.object.camera_add(location=target + direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 54
scene.camera = camera

scene.world = bpy.data.worlds.new("Overcast sky")
scene.world.color = (0.55, 0.64, 0.75)

bpy.ops.object.light_add(type="SUN")
bpy.context.object.rotation_euler = (0.52, -0.55, -0.35)
bpy.context.object.data.energy = 3.5
bpy.context.object.data.angle = 0.15

scene.render.engine = "CYCLES"
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x = 1440
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.filepath = str(ROOT / "art/lumber_yard_kit_preview.png")

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "art/lumber_yard_kit.blend"))
bpy.ops.render.render(write_still=True)
print("Lumber yard kit exported to", OUT)
