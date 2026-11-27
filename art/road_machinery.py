"""Build low-poly road construction machinery for Tideways:
  1. Steam Roller (vibratory road roller)
  2. Wheel Loader (front-end loader with articulated bucket)
  3. Paving Machine (tracked asphalt paver with hopper & screed)

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/road_machinery.py

Outputs:
    art/road_machinery.blend
    assets/models/steam_roller.glb
    assets/models/wheel_loader.glb
    assets/models/paving_machine.glb
    art/road_machinery_preview.png

Coordinate convention:
    Blender: +X right, -Y forward, +Z up, ground at Z = 0.
    glTF/Godot export maps this to +X right, +Z forward, +Y up, ground at Y = 0.
"""

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "art" / "road_machinery.blend"
MODELS_DIR = ROOT / "assets" / "models"
PREVIEW_PATH = ROOT / "art" / "road_machinery_preview.png"


# ---------------------------------------------------------------------------
# Color & material helpers (matches Tideways construction_site.py palette)
# ---------------------------------------------------------------------------

def hex_to_linear(hex_str):
    srgb = tuple(int(hex_str[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(
        ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
        for c in srgb
    )


def make_material(name, hex_str, roughness=0.65, metallic=0.0, emission=0.0):
    mat = bpy.data.materials.new(name)
    lin = hex_to_linear(hex_str)
    mat.diffuse_color = (*lin, 1.0)
    if not mat.node_tree:
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if emission > 0.0 and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*lin, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


class Palette:
    def __init__(self):
        self.yellow = make_material("MachineryYellow", "e5a62e", roughness=0.48, metallic=0.14)
        self.yellow_lt = make_material("MachineryYellowLight", "f2be4e", roughness=0.45, metallic=0.10)
        self.orange = make_material("SafetyOrange", "d85d2e", roughness=0.55, metallic=0.08)
        self.iron = make_material("DarkIron", "383e40", roughness=0.52, metallic=0.48)
        self.iron_lt = make_material("SteelMid", "646c70", roughness=0.44, metallic=0.55)
        self.drum_steel = make_material("DrumSteel", "8d969a", roughness=0.35, metallic=0.72)
        self.chrome = make_material("HydraulicChrome", "cfd6da", roughness=0.22, metallic=0.88)
        self.rubber = make_material("TireRubber", "222426", roughness=0.86, metallic=0.02)
        self.rubber_tread = make_material("TireTread", "181a1c", roughness=0.90, metallic=0.0)
        self.glass = make_material("CabGlass", "304f5c", roughness=0.18, metallic=0.12)
        self.seat = make_material("SeatVinyl", "2c2d30", roughness=0.78, metallic=0.0)
        self.asphalt = make_material("HotAsphalt", "2a2b2d", roughness=0.92, metallic=0.0)
        self.beacon = make_material("AmberBeacon", "f5a018", roughness=0.25, metallic=0.0, emission=1.2)
        self.headlight = make_material("WorkLight", "f7f2d4", roughness=0.20, metallic=0.0, emission=0.8)
        self.taillight = make_material("TailLight", "c82820", roughness=0.30, metallic=0.0, emission=0.4)
        self.stripe_white = make_material("StripeWhite", "eceae2", roughness=0.55, metallic=0.0)


# ---------------------------------------------------------------------------
# Low-poly BMesh builder
# ---------------------------------------------------------------------------

class LowPolyPart:
    """Accumulates flat-shaded low-poly primitives with per-face material slots."""

    def __init__(self, name, origin=(0.0, 0.0, 0.0)):
        self.name = name
        self.origin = Vector(origin)
        self.bm = bmesh.new()
        self.materials = []
        self._mat_index = {}

    def _slot(self, mat):
        idx = self._mat_index.get(mat)
        if idx is None:
            idx = len(self.materials)
            self.materials.append(mat)
            self._mat_index[mat] = idx
        return idx

    def _assign_mat(self, geom, mat):
        slot = self._slot(mat)
        for item in geom:
            if isinstance(item, bmesh.types.BMFace):
                item.material_index = slot
                item.smooth = False

    def box(self, center, size, mat, rot=(0.0, 0.0, 0.0)):
        """Box centered at world `center` with dimensions `size=(sx, sy, sz)`."""
        sx, sy, sz = size
        m = (
            Matrix.Translation(Vector(center) - self.origin)
            @ Matrix.Rotation(rot[2], 4, "Z")
            @ Matrix.Rotation(rot[1], 4, "Y")
            @ Matrix.Rotation(rot[0], 4, "X")
            @ Matrix.Diagonal((sx, sy, sz, 1.0))
        )
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        verts = set(res["verts"])
        faces = [f for f in self.bm.faces if all(v in verts for v in f.verts)]
        self._assign_mat(faces, mat)

    def tapered_box(self, center, size_bot, size_top, height, mat, rot_z=0.0, shift_top=(0.0, 0.0)):
        """Frustum/tapered box with base at center.z - height/2 and top at center.z + height/2."""
        cx, cy, cz = Vector(center) - self.origin
        bx, by = size_bot[0] * 0.5, size_bot[1] * 0.5
        tx, ty = size_top[0] * 0.5, size_top[1] * 0.5
        hz = height * 0.5
        sx, sy = shift_top
        local_pts = [
            Vector((-bx, -by, -hz)), Vector((bx, -by, -hz)),
            Vector((bx, by, -hz)), Vector((-bx, by, -hz)),
            Vector((-tx + sx, -ty + sy, hz)), Vector((tx + sx, -ty + sy, hz)),
            Vector((tx + sx, ty + sy, hz)), Vector((-tx + sx, ty + sy, hz)),
        ]
        rot_m = Matrix.Rotation(rot_z, 4, "Z")
        t_m = Matrix.Translation((cx, cy, cz)) @ rot_m
        vs = [self.bm.verts.new(t_m @ p) for p in local_pts]
        quads = [
            (0, 3, 2, 1), (4, 5, 6, 7),
            (0, 1, 5, 4), (1, 2, 6, 5),
            (2, 3, 7, 6), (3, 0, 4, 7),
        ]
        faces = []
        for q in quads:
            try:
                faces.append(self.bm.faces.new([vs[i] for i in q]))
            except ValueError:
                pass
        self._assign_mat(faces, mat)

    def cylinder(self, center, radius, depth, mat, segments=16, axis="Z", radius2=None):
        """Cylinder centered at world `center` aligned along `axis` ('X', 'Y', or 'Z')."""
        r2 = radius if radius2 is None else radius2
        rot = Matrix.Identity(4)
        if axis == "X":
            rot = Matrix.Rotation(math.pi * 0.5, 4, "Y")
        elif axis == "Y":
            rot = Matrix.Rotation(math.pi * 0.5, 4, "X")
        m = Matrix.Translation(Vector(center) - self.origin) @ rot
        res = bmesh.ops.create_cone(
            self.bm,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=radius,
            radius2=r2,
            depth=depth,
            matrix=m,
        )
        verts = set(res["verts"])
        faces = [f for f in self.bm.faces if all(v in verts for v in f.verts)]
        self._assign_mat(faces, mat)

    def tube(self, p0, p1, radius, mat, segments=6, radius2=None):
        """Cylinder from world point p0 to world point p1."""
        v0, v1 = Vector(p0), Vector(p1)
        d = v1 - v0
        length = d.length
        if length < 1e-5:
            return
        mid = (v0 + v1) * 0.5
        quat = Vector((0.0, 0.0, 1.0)).rotation_difference(d.normalized())
        m = Matrix.Translation(mid - self.origin) @ quat.to_matrix().to_4x4()
        r2 = radius if radius2 is None else radius2
        res = bmesh.ops.create_cone(
            self.bm,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=radius,
            radius2=r2,
            depth=length,
            matrix=m,
        )
        verts = set(res["verts"])
        faces = [f for f in self.bm.faces if all(v in verts for v in f.verts)]
        self._assign_mat(faces, mat)

    def hydraulic(self, p0, p1, barrel_r, rod_r, mat_barrel, mat_rod, barrel_frac=0.58):
        """Hydraulic cylinder: dark barrel from p0 to mid, chrome piston rod from mid to p1."""
        v0, v1 = Vector(p0), Vector(p1)
        vm = v0.lerp(v1, barrel_frac)
        self.tube(v0, vm, barrel_r, mat_barrel, segments=6)
        self.tube(vm, v1, rod_r, mat_rod, segments=6)

    def wheel(self, center, radius, width, pal, segments=12, lug_count=8):
        """Heavy off-road construction wheel with tread lugs, rim, and hub."""
        cx, cy, cz = center
        # Main rubber tire
        self.cylinder((cx, cy, cz), radius * 0.96, width, pal.rubber, segments=segments, axis="X")
        # Tread lugs around circumference
        for i in range(lug_count):
            ang = math.tau * i / lug_count
            ly = cy + math.cos(ang) * (radius * 0.965)
            lz = cz + math.sin(ang) * (radius * 0.965)
            self.box((cx, ly, lz), (width * 0.92, radius * 0.16, radius * 0.08), pal.rubber_tread, rot=(ang, 0.0, 0.0))
        # Yellow steel rim (proud of sidewall so it reads cleanly)
        self.cylinder((cx, cy, cz), radius * 0.56, width * 1.04, pal.yellow, segments=10, axis="X")
        # Outer planetary hub
        sx = 1.0 if cx >= 0 else -1.0
        self.cylinder((cx + sx * width * 0.48, cy, cz), radius * 0.28, width * 0.16, pal.iron, segments=8, axis="X")

    def build(self, col, parent=None):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mat in self.materials:
            mesh.materials.append(mat)
        obj = bpy.data.objects.new(self.name, mesh)
        obj.location = self.origin
        col.objects.link(obj)
        if parent is not None:
            obj.parent = parent
        return obj


def make_empty(name, col, location=(0.0, 0.0, 0.0), parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.5
    obj.location = Vector(location)
    col.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


# ---------------------------------------------------------------------------
# 1. Steam Roller / Vibratory Road Roller
#    Forward = -Y, Length ~4.8m, Width ~2.1m, Height ~2.85m
# ---------------------------------------------------------------------------

def build_steam_roller(pal, col, offset=(0.0, 0.0, 0.0)):
    root = make_empty("SteamRoller", col, location=offset)

    # --- Front steel compaction drum (separate child for rolling animation) ---
    drum_y = -1.48
    drum_r = 0.66
    drum_w = 1.88
    drum = LowPolyPart("Roller_FrontDrum", origin=(0.0, drum_y, drum_r))
    # Main polished steel drum shell
    drum.cylinder((0.0, drum_y, drum_r), drum_r, drum_w, pal.drum_steel, segments=16, axis="X")
    # Recessed dark-iron inner end plates
    for sx in (-1.0, 1.0):
        drum.cylinder((sx * (drum_w * 0.5 - 0.02), drum_y, drum_r), drum_r * 0.86, 0.06, pal.iron, segments=14, axis="X")
        drum.cylinder((sx * (drum_w * 0.5 + 0.03), drum_y, drum_r), drum_r * 0.34, 0.10, pal.yellow, segments=8, axis="X")
    drum.build(col, parent=root)

    # --- Main chassis, yoke, engine hood, cab, and rear wheels ---
    body = LowPolyPart("Roller_Body", origin=(0.0, 0.0, 0.0))

    # Front drum yoke & bumper frame
    yoke_x = drum_w * 0.5 + 0.11
    for sx in (-1.0, 1.0):
        # Side yoke arms wrapping the drum
        body.box((sx * yoke_x, drum_y, drum_r + 0.06), (0.12, 1.48, 0.28), pal.yellow)
        body.box((sx * yoke_x, drum_y + 0.52, drum_r + 0.22), (0.14, 0.55, 0.32), pal.yellow)
    # Front heavy crossbeam & scraper bar
    body.box((0.0, drum_y - 0.78, drum_r + 0.08), (drum_w + 0.32, 0.20, 0.24), pal.yellow)
    body.box((0.0, drum_y - 0.72, drum_r - 0.16), (drum_w + 0.04, 0.08, 0.08), pal.iron)
    # Rear crossbeam behind drum
    body.box((0.0, drum_y + 0.78, drum_r + 0.18), (drum_w + 0.28, 0.24, 0.30), pal.yellow)
    # Front headlights on yoke
    for sx in (-0.72, 0.72):
        body.box((sx, drum_y - 0.89, drum_r + 0.14), (0.18, 0.06, 0.12), pal.headlight)

    # Articulated center pivot & hydraulic steering cylinders
    body.cylinder((0.0, -0.35, 0.86), 0.20, 0.52, pal.iron, segments=12, axis="Z")
    body.box((0.0, -0.35, 0.86), (0.58, 0.56, 0.34), pal.iron)
    for sx in (-1.0, 1.0):
        body.hydraulic((sx * 0.42, -0.78, 0.84), (sx * 0.36, 0.12, 0.84), 0.055, 0.032, pal.iron, pal.chrome)

    # Rear chassis frame
    body.box((0.0, 0.95, 0.78), (1.16, 2.35, 0.42), pal.iron)
    # Rear wheels
    rear_y = 1.18
    rear_r = 0.62
    for sx in (-1.0, 1.0):
        body.wheel((sx * 0.82, rear_y, rear_r), rear_r, 0.46, pal, segments=12, lug_count=8)

    # Operator platform deck
    body.box((0.0, 0.28, 1.18), (1.38, 1.08, 0.14), pal.iron)
    # Side access steps
    for sx in (-1.0, 1.0):
        body.box((sx * 0.74, 0.22, 0.84), (0.18, 0.44, 0.06), pal.iron_lt)
        body.box((sx * 0.74, 0.22, 0.54), (0.18, 0.44, 0.06), pal.iron_lt)
        body.tube((sx * 0.78, 0.02, 0.54), (sx * 0.78, 0.02, 1.24), 0.025, pal.iron)
        body.tube((sx * 0.78, 0.42, 0.54), (sx * 0.78, 0.42, 1.24), 0.025, pal.iron)

    # Rear engine hood (sloped classic roller profile)
    body.tapered_box((0.0, 1.48, 1.42), (1.36, 1.46), (1.18, 1.26), 0.82, pal.yellow, shift_top=(0.0, -0.08))
    # Dark engine side louver panels
    for sx in (-1.0, 1.0):
        body.box((sx * 0.65, 1.50, 1.42), (0.04, 0.96, 0.42), pal.iron)
    # Rear radiator grille & counterweight bumper
    body.box((0.0, 2.18, 1.38), (1.06, 0.08, 0.56), pal.iron)
    body.box((0.0, 2.16, 0.88), (1.42, 0.26, 0.34), pal.yellow)
    for sx in (-0.52, 0.52):
        body.box((sx, 2.30, 0.92), (0.18, 0.05, 0.10), pal.taillight)

    # Exhaust stack on right side of hood
    body.tube((0.52, 1.28, 1.80), (0.52, 1.28, 2.52), 0.055, pal.iron, segments=10)
    body.tube((0.52, 1.28, 2.50), (0.56, 1.38, 2.62), 0.052, pal.iron, segments=8)

    # Operator seat, steering column, and control console
    body.box((0.0, 0.48, 1.44), (0.48, 0.46, 0.14), pal.seat)
    body.box((0.0, 0.68, 1.72), (0.46, 0.12, 0.48), pal.seat)
    body.box((0.0, -0.06, 1.52), (0.56, 0.26, 0.56), pal.iron)
    body.tube((0.0, -0.04, 1.76), (0.0, 0.08, 1.98), 0.035, pal.iron)
    body.cylinder((0.0, 0.10, 2.00), 0.19, 0.04, pal.rubber, segments=8, axis="Z")

    # ROPS Rollbar & Canopy Roof
    for sx in (-0.64, 0.64):
        body.tube((sx, 0.82, 1.22), (sx, 0.72, 2.66), 0.055, pal.iron, segments=6)
        body.tube((sx, -0.18, 1.22), (sx, -0.12, 2.66), 0.045, pal.iron, segments=6)
        body.tube((sx, -0.12, 2.64), (sx, 0.72, 2.64), 0.045, pal.iron, segments=6)
    # Sloped canopy roof
    body.tapered_box((0.0, 0.28, 2.74), (1.48, 1.26), (1.34, 1.12), 0.14, pal.yellow)
    # Amber rotating beacon on roof
    body.cylinder((0.0, 0.35, 2.88), 0.08, 0.14, pal.beacon, segments=8, axis="Z")
    # Roof work lights
    for sx in (-0.48, 0.48):
        body.box((sx, -0.34, 2.72), (0.14, 0.08, 0.10), pal.headlight)

    body.build(col, parent=root)
    return root


# ---------------------------------------------------------------------------
# 2. Wheel Loader (Front-End Loader)
#    Forward = -Y, Length ~6.5m (with bucket), Width ~2.45m, Height ~3.15m
# ---------------------------------------------------------------------------

def build_wheel_loader(pal, col, offset=(0.0, 0.0, 0.0)):
    root = make_empty("WheelLoader", col, location=offset)

    # --- Main chassis, cab, engine bay, and 4 large off-road wheels ---
    body = LowPolyPart("Loader_Body", origin=(0.0, 0.0, 0.0))

    wheel_r = 0.72
    wheel_w = 0.52
    front_y = -1.10
    rear_y = 1.48
    track_x = 0.94

    for wy in (front_y, rear_y):
        for sx in (-1.0, 1.0):
            body.wheel((sx * track_x, wy, wheel_r), wheel_r, wheel_w, pal, segments=12, lug_count=8)

    # Front & rear heavy frames with center articulation joint
    body.box((0.0, -0.78, 0.92), (1.28, 1.45, 0.52), pal.iron)
    body.box((0.0, 1.32, 0.96), (1.36, 2.20, 0.56), pal.iron)
    body.cylinder((0.0, 0.16, 0.94), 0.22, 0.58, pal.iron, segments=12, axis="Z")
    # Front lift tower (supports the boom pivots)
    body.tapered_box((0.0, -0.82, 1.56), (1.22, 0.96), (1.06, 0.68), 0.84, pal.yellow)

    # Wheel fenders
    for sx in (-1.0, 1.0):
        body.box((sx * 0.94, rear_y, 1.54), (0.54, 1.24, 0.08), pal.iron)
        body.box((sx * 0.94, front_y + 0.16, 1.52), (0.52, 0.86, 0.08), pal.iron)

    # Rear engine hood & heavy counterweight
    body.tapered_box((0.0, 1.58, 1.66), (1.46, 1.78), (1.26, 1.54), 0.92, pal.yellow, shift_top=(0.0, -0.06))
    for sx in (-1.0, 1.0):
        body.box((sx * 0.71, 1.62, 1.66), (0.04, 1.18, 0.44), pal.iron)
    # Rear counterweight & radiator grille
    body.tapered_box((0.0, 2.48, 1.12), (1.76, 0.46), (1.62, 0.36), 0.68, pal.yellow)
    body.box((0.0, 2.46, 1.72), (1.08, 0.08, 0.58), pal.iron)
    for sx in (-0.62, 0.62):
        body.box((sx, 2.71, 1.18), (0.20, 0.05, 0.12), pal.taillight)
    # Exhaust pipe & air intake
    body.tube((0.52, 1.62, 2.10), (0.52, 1.62, 2.78), 0.06, pal.iron, segments=10)
    body.tube((0.52, 1.62, 2.76), (0.56, 1.72, 2.88), 0.055, pal.iron, segments=8)
    body.cylinder((-0.46, 1.58, 2.24), 0.11, 0.24, pal.iron, segments=10, axis="Z")

    # Enclosed modern operator cab (centered over articulation / rear)
    cab_y = 0.26
    # Lower cab base
    body.box((0.0, cab_y, 1.54), (1.38, 1.38, 0.52), pal.yellow)
    # Glass greenhouse
    body.tapered_box((0.0, cab_y, 2.32), (1.32, 1.30), (1.22, 1.18), 1.06, pal.glass)
    # Dark corner pillars
    for sx in (-0.61, 0.61):
        for sy in (-0.59, 0.59):
            body.tube((sx, cab_y + sy, 1.78), (sx * 0.94, cab_y + sy * 0.92, 2.86), 0.048, pal.iron, segments=6)
    # Cab roof + amber beacon + front work lights
    body.tapered_box((0.0, cab_y, 2.94), (1.36, 1.34), (1.26, 1.24), 0.16, pal.yellow)
    body.cylinder((0.0, cab_y + 0.34, 3.09), 0.085, 0.15, pal.beacon, segments=10, axis="Z")
    for sx in (-0.46, 0.46):
        body.box((sx, cab_y - 0.68, 2.92), (0.16, 0.08, 0.11), pal.headlight)
        body.box((sx, cab_y + 0.68, 2.92), (0.14, 0.08, 0.10), pal.headlight)

    # Side access ladder steps
    for sx in (-1.0, 1.0):
        for sz in (0.64, 0.96, 1.28):
            body.box((sx * 0.74, 0.26, sz), (0.20, 0.42, 0.05), pal.iron_lt)

    body.build(col, parent=root)

    # --- Lift Boom & Hydraulics (separate child for animation) ---
    boom_pivot = (0.0, -0.82, 1.76)
    boom = LowPolyPart("Loader_Boom", origin=boom_pivot)
    for sx in (-0.54, 0.54):
        # Heavy angled Z-bar lift arm
        boom.tube((sx, -0.82, 1.76), (sx, -1.68, 1.34), 0.12, pal.yellow, segments=8)
        boom.tube((sx, -1.68, 1.34), (sx, -2.42, 0.54), 0.11, pal.yellow, segments=8)
        # Lift hydraulic cylinder from front frame up to arm elbow
        boom.hydraulic((sx, -0.78, 1.04), (sx, -1.64, 1.30), 0.075, 0.045, pal.iron, pal.chrome)
    # Crossbar stiffening tube between arms
    boom.tube((-0.54, -1.64, 1.32), (0.54, -1.64, 1.32), 0.10, pal.yellow, segments=10)
    # Center tilt bellcrank & tilt hydraulic cylinder
    boom.tube((0.0, -1.64, 1.32), (0.0, -1.52, 1.92), 0.085, pal.iron, segments=8)
    boom.hydraulic((0.0, -0.74, 1.94), (0.0, -1.52, 1.92), 0.075, 0.045, pal.iron, pal.chrome)
    boom.tube((0.0, -1.62, 1.32), (0.0, -2.38, 1.02), 0.065, pal.iron, segments=8)
    boom.build(col, parent=root)

    # --- Front Bucket with Digging Teeth (separate child for curling animation) ---
    bucket_pivot = (0.0, -2.42, 0.54)
    bucket = LowPolyPart("Loader_Bucket", origin=bucket_pivot)
    bw = 2.38
    # Bottom floor plate
    bucket.box((0.0, -2.86, 0.12), (bw, 0.96, 0.10), pal.iron)
    # Angled back scoop wall
    bucket.box((0.0, -2.44, 0.56), (bw, 0.12, 0.94), pal.iron, rot=(math.radians(14.0), 0.0, 0.0))
    # Top spill guard lip
    bucket.box((0.0, -2.34, 1.04), (bw, 0.24, 0.10), pal.yellow)
    # Side cheek plates
    for sx in (-1.0, 1.0):
        bucket.box((sx * (bw * 0.5 - 0.04), -2.72, 0.52), (0.08, 0.78, 0.86), pal.iron)
    # Heavy cutting edge + 6 digging teeth
    bucket.box((0.0, -3.34, 0.11), (bw + 0.04, 0.14, 0.09), pal.iron_lt)
    for i in range(6):
        tx = -0.96 + i * (1.92 / 5.0)
        bucket.tapered_box((tx, -3.48, 0.11), (0.12, 0.24), (0.05, 0.08), 0.09, pal.iron_lt)
    bucket.build(col, parent=root)

    return root


# ---------------------------------------------------------------------------
# 3. Asphalt Paving Machine
#    Forward = -Y, Length ~6.2m, Width ~2.85m (screed), Height ~2.95m
# ---------------------------------------------------------------------------

def build_paving_machine(pal, col, offset=(0.0, 0.0, 0.0)):
    root = make_empty("PavingMachine", col, location=offset)

    # --- Main tracked body, front hopper, engine deck, operator platform ---
    body = LowPolyPart("Paver_Body", origin=(0.0, 0.0, 0.0))

    # Twin crawler tracks (left & right)
    for sx in (-0.98, 0.98):
        # Track belt main body
        body.box((sx, 0.12, 0.34), (0.44, 2.55, 0.64), pal.rubber)
        # Rounded front idler & rear drive sprocket
        body.cylinder((sx, -1.16, 0.34), 0.32, 0.44, pal.rubber, segments=10, axis="X")
        body.cylinder((sx, 1.40, 0.34), 0.32, 0.44, pal.rubber, segments=10, axis="X")
        # Inner steel track frame & rollers
        body.box((sx, 0.12, 0.34), (0.48, 2.22, 0.34), pal.iron)
        for ry in (-0.75, -0.15, 0.45, 1.05):
            body.cylinder((sx, ry, 0.24), 0.14, 0.49, pal.iron_lt, segments=8, axis="X")
        # Track grouser pads along top & bottom
        for i in range(6):
            ty = -0.95 + i * 0.42
            body.box((sx, ty, 0.03), (0.46, 0.14, 0.05), pal.rubber_tread)
            body.box((sx, ty, 0.66), (0.46, 0.14, 0.05), pal.rubber_tread)

    # Lower central chassis & conveyor tunnel
    body.box((0.0, 0.18, 0.78), (1.68, 3.45, 0.48), pal.iron)

    # Front Material Hopper (wide open V-shaped bin for hot asphalt)
    hopper_y = -1.86
    # Hopper floor
    body.box((0.0, hopper_y, 0.64), (1.76, 1.72, 0.16), pal.iron)
    # Sloped left & right hopper wings
    for sx in (-1.0, 1.0):
        body.box(
            (sx * 1.14, hopper_y, 0.98),
            (0.14, 1.76, 0.78),
            pal.yellow,
            rot=(0.0, sx * math.radians(26.0), 0.0),
        )
    # Front low lip + dump-truck push rollers
    body.box((0.0, hopper_y - 0.88, 0.74), (2.28, 0.10, 0.28), pal.iron)
    body.box((0.0, hopper_y - 1.06, 0.56), (2.14, 0.14, 0.14), pal.iron)
    for sx in (-0.78, 0.78):
        body.cylinder((sx, hopper_y - 1.14, 0.56), 0.13, 0.42, pal.drum_steel, segments=8, axis="X")
    # Mound of hot black asphalt inside the hopper
    body.tapered_box((0.0, hopper_y + 0.05, 0.96), (1.84, 1.52), (1.12, 0.98), 0.46, pal.asphalt)

    # Mid-mounted Engine Housing
    body.tapered_box((0.0, 0.02, 1.44), (1.72, 1.56), (1.58, 1.42), 0.88, pal.yellow)
    for sx in (-1.0, 1.0):
        body.box((sx * 0.84, 0.02, 1.46), (0.04, 1.12, 0.46), pal.iron)
    # Vertical exhaust stack
    body.tube((0.58, -0.36, 1.86), (0.58, -0.36, 2.74), 0.06, pal.iron, segments=10)
    body.tube((0.58, -0.36, 2.72), (0.62, -0.26, 2.84), 0.055, pal.iron, segments=8)

    # Elevated Rear Operator Platform
    body.box((0.0, 1.24, 1.38), (2.06, 1.02, 0.14), pal.iron)
    # Dual operator seats (left & right) + control consoles
    for sx in (-0.64, 0.64):
        body.box((sx, 1.34, 1.62), (0.44, 0.42, 0.12), pal.seat)
        body.box((sx, 1.52, 1.88), (0.42, 0.10, 0.44), pal.seat)
        body.box((sx, 0.90, 1.72), (0.46, 0.24, 0.56), pal.iron)
    # Safety handrails around platform
    for sx in (-1.00, 1.00):
        body.tube((sx, 0.78, 1.42), (sx, 0.78, 2.18), 0.03, pal.iron, segments=4)
        body.tube((sx, 1.70, 1.42), (sx, 1.70, 2.18), 0.03, pal.iron, segments=4)
        body.tube((sx, 0.78, 2.16), (sx, 1.70, 2.16), 0.03, pal.iron, segments=4)

    # Overhead Canopy Roof & Amber Beacon
    for sx in (-0.92, 0.92):
        body.tube((sx, 0.86, 1.44), (sx, 0.86, 2.76), 0.045, pal.iron, segments=4)
        body.tube((sx, 1.62, 1.44), (sx, 1.62, 2.76), 0.045, pal.iron, segments=4)
    body.tapered_box((0.0, 1.24, 2.82), (2.12, 1.28), (1.96, 1.14), 0.12, pal.yellow)
    body.cylinder((0.0, 1.24, 2.95), 0.085, 0.15, pal.beacon, segments=8, axis="Z")
    for sx in (-0.72, 0.72):
        body.box((sx, 0.60, 2.80), (0.16, 0.08, 0.10), pal.headlight)

    body.build(col, parent=root)

    # --- Rear Asphalt Screed Assembly (separate child for height/extension) ---
    screed = LowPolyPart("Paver_Screed", origin=(0.0, 2.38, 0.36))
    sw = 2.88
    # Twin heavy tow arms connecting mid-chassis to screed
    for sx in (-1.18, 1.18):
        screed.tube((sx, 0.10, 0.58), (sx, 2.32, 0.42), 0.085, pal.yellow, segments=8)
    # Transverse auger screw shaft (spreads hot asphalt ahead of screed)
    screed.cylinder((0.0, 1.98, 0.34), 0.14, sw - 0.16, pal.iron, segments=8, axis="X")
    # Main wide screed ironing plate & heated housing
    screed.box((0.0, 2.42, 0.12), (sw, 0.68, 0.16), pal.iron_lt)
    screed.tapered_box((0.0, 2.42, 0.42), (sw, 0.64), (sw - 0.16, 0.48), 0.44, pal.yellow)
    # Screed side end-gates
    for sx in (-1.0, 1.0):
        screed.box((sx * (sw * 0.5 + 0.04), 2.30, 0.30), (0.08, 0.96, 0.52), pal.iron)
    # Rear walkboard & thickness-adjust handwheels
    screed.box((0.0, 2.86, 0.38), (sw - 0.24, 0.34, 0.07), pal.iron)
    for sx in (-0.98, 0.98):
        screed.tube((sx, 2.62, 0.60), (sx, 2.62, 1.24), 0.032, pal.chrome, segments=6)
        screed.cylinder((sx, 2.62, 1.26), 0.14, 0.04, pal.orange, segments=8, axis="Z")
        screed.box((sx, 2.75, 0.52), (0.18, 0.05, 0.10), pal.taillight)
    screed.build(col, parent=root)

    return root


# ---------------------------------------------------------------------------
# Studio & Preview Rendering
# ---------------------------------------------------------------------------

def setup_studio(scene):
    studio = bpy.data.collections.new("Studio")
    scene.collection.children.link(studio)

    # Clean warm ground plane
    ground_mat = make_material("StudioGround", "d8d4c8", roughness=0.90)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=32.0)
    mesh = bpy.data.meshes.new("StudioGround")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(ground_mat)
    ground = bpy.data.objects.new("StudioGround", mesh)
    ground.location = (0.0, 0.0, -0.005)
    studio.objects.link(ground)

    # World sky lighting
    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*hex_to_linear("dce6ee"), 1.0)
    bg.inputs["Strength"].default_value = 0.85

    # Warm sun key light
    sun_data = bpy.data.lights.new("SunKey", type="SUN")
    sun_data.energy = 3.2
    sun_data.color = (1.0, 0.96, 0.88)
    sun_data.angle = math.radians(2.5)
    sun = bpy.data.objects.new("SunKey", sun_data)
    sun.rotation_euler = (math.radians(52.0), math.radians(14.0), math.radians(-38.0))
    studio.objects.link(sun)

    # Soft fill light
    fill_data = bpy.data.lights.new("FillArea", type="AREA")
    fill_data.energy = 260.0
    fill_data.size = 10.0
    fill_data.color = (0.85, 0.92, 1.0)
    fill = bpy.data.objects.new("FillArea", fill_data)
    fill.location = (8.0, -10.0, 8.0)
    direction = Vector((0.0, 0.0, 1.2)) - fill.location
    fill.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    studio.objects.link(fill)

    # Hero 3/4 camera framing all 3 machines
    cam_data = bpy.data.cameras.new("HeroCam")
    cam_data.lens = 42.0
    cam = bpy.data.objects.new("HeroCam", cam_data)
    cam.location = (-8.2, -13.2, 6.2)
    target = Vector((0.0, -0.2, 1.15))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    studio.objects.link(cam)
    scene.camera = cam

    # Render settings
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 820
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    return studio


def export_hierarchy(root_obj, filepath):
    """Export a single machine hierarchy centered at world origin to GLB."""
    saved_loc = root_obj.location.copy()
    root_obj.location = Vector((0.0, 0.0, 0.0))
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    stack = [root_obj]
    while stack:
        o = stack.pop()
        o.select_set(True)
        stack.extend(o.children)

    filepath.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(filepath),
        export_format="GLB",
        use_selection=True,
    )

    root_obj.location = saved_loc
    bpy.context.view_layer.update()


def count_tris(root_obj):
    total = 0
    stack = [root_obj]
    while stack:
        o = stack.pop()
        if o.type == "MESH":
            total += sum(len(p.vertices) - 2 for p in o.data.polygons)
        stack.extend(o.children)
    return total


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    pal = Palette()

    col = bpy.data.collections.new("RoadMachinery")
    scene.collection.children.link(col)

    # Line up the three machines for the .blend and preview render
    roller = build_steam_roller(pal, col, offset=(-4.6, 0.0, 0.0))
    loader = build_wheel_loader(pal, col, offset=(0.0, 0.3, 0.0))
    paver = build_paving_machine(pal, col, offset=(4.8, 0.0, 0.0))

    for name, obj, glb_name in [
        ("SteamRoller", roller, "steam_roller.glb"),
        ("WheelLoader", loader, "wheel_loader.glb"),
        ("PavingMachine", paver, "paving_machine.glb"),
    ]:
        tris = count_tris(obj)
        print(f"  {name:16s} {tris:5d} tris")
        export_hierarchy(obj, MODELS_DIR / glb_name)

    studio = setup_studio(scene)
    scene.render.filepath = str(PREVIEW_PATH)
    bpy.ops.render.render(write_still=True)

    # Hide studio objects in viewport so opening .blend shows the clean models
    for obj in studio.objects:
        obj.hide_viewport = True

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)
    print(f"Saved:    {BLEND_PATH}")
    print(f"Exported: {MODELS_DIR / 'steam_roller.glb'}, wheel_loader.glb, paving_machine.glb")
    print(f"Preview:  {PREVIEW_PATH}")


if __name__ == "__main__":
    build()
