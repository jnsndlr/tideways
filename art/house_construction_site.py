"""Build a compact residential house construction site for Tideways (no crane).

Smaller, cozy counterpart to art/construction_site.py (13.6m x 10.4m lot vs 22m x 16m,
6.0m x 4.4m coastal cottage footprint vs 8.4m x 6.0m, no tower crane).

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/house_construction_site.py

Outputs:
    art/house_construction_site.blend
    assets/models/house_construction_site.glb
    art/house_construction_site_preview.png
    art/house_construction_site_stages_preview.png

Hierarchy (ready for Godot visibility / animation control):
    HouseConstructionSite
      SiteBase
        LotPad
        SitePerimeter
        SiteProps
      Materials
        Pile_ConcreteBags
        Pile_LumberStack
        Pile_PlywoodSheets
        Pile_RoofLumber
      Equipment
        WorkTruck
          Truck_Body
          Truck_LumberLoad
        CementMixer
          Mixer_Frame
          Mixer_Tilt
            Mixer_Drum
        Wheelbarrow
          Wheelbarrow_Body
          Wheelbarrow_Concrete
        Stepladder
        Scaffold
      Workers
        Worker_1
          Worker_1_Body
          Worker_1_ArmL
          Worker_1_ArmR
        Worker_2
          Worker_2_Body
          Worker_2_ArmL
          Worker_2_ArmR
      BuildingStages
        Stage1_Foundation
        Stage2_FloorDeck
        Stage3_Walls
          Wall_Back          (pivots at bottom edge for tilt-up framing)
          Wall_Left          (pivots at bottom edge for tilt-up framing)
          Wall_Right         (pivots at bottom edge for tilt-up framing)
          Wall_Front         (pivots at bottom edge for tilt-up framing)
          Wall_InteriorAndPorch
        Stage4_UpperFrameAndGables
        Stage5_Roof
          Stage5a_TrussesLeft
          Stage5b_TrussesRight
          Stage5c_PorchRoof
"""

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "art" / "house_construction_site.blend"
GLB_PATH = ROOT / "assets" / "models" / "house_construction_site.glb"
HERO_PREVIEW_PATH = ROOT / "art" / "house_construction_site_preview.png"
STAGES_PREVIEW_PATH = ROOT / "art" / "house_construction_site_stages_preview.png"


# ---------------------------------------------------------------------------
# Color & material helpers (matching Tideways construction_site.py palette)
# ---------------------------------------------------------------------------

def hex_to_linear(hex_str):
    srgb = tuple(int(hex_str[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return tuple(
        ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
        for c in srgb
    )


def make_material(name, hex_str, roughness=0.72, metallic=0.0):
    mat = bpy.data.materials.new(name)
    lin = hex_to_linear(hex_str)
    mat.diffuse_color = (*lin, 1.0)
    if not mat.node_tree:
        mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


class Palette:
    def __init__(self):
        self.dirt = make_material("DirtLot", "a49279", roughness=0.92)
        self.dirt_dark = make_material("DirtExcavated", "88755d", roughness=0.94)
        self.gravel = make_material("GravelApron", "9c9b95", roughness=0.90)
        self.concrete = make_material("ConcreteSlab", "b5b6b0", roughness=0.84)
        self.concrete_dark = make_material("ConcreteBlock", "8d8f8a", roughness=0.88)
        self.concrete_wet = make_material("ConcreteWet", "999b94", roughness=0.62)
        self.lumber_light = make_material("LumberFresh", "e0ba7e", roughness=0.76)
        self.lumber_mid = make_material("LumberBeam", "c99859", roughness=0.78)
        self.lumber_dark = make_material("LumberTreated", "95673b", roughness=0.80)
        self.plywood = make_material("PlywoodSheet", "d5ae6f", roughness=0.78)
        self.equip_gold = make_material("EquipGold", "e3a535", roughness=0.52, metallic=0.15)
        self.equip_green = make_material("EquipGreen", "365950", roughness=0.58, metallic=0.12)
        self.truck_blue = make_material("TruckTeal", "4c7378", roughness=0.45, metallic=0.18)
        self.truck_trim = make_material("TruckTrim", "e3dfc6", roughness=0.55)
        self.glass = make_material("CabGlass", "345460", roughness=0.22, metallic=0.10)
        self.iron = make_material("DarkIron", "434b49", roughness=0.55, metallic=0.45)
        self.rubber = make_material("TireRubber", "2d3030", roughness=0.88)
        self.safety = make_material("SafetyOrange", "d65f35", roughness=0.62)
        self.vest_lime = make_material("VestLime", "b7cc49", roughness=0.68)
        self.tarp = make_material("TarpTeal", "467977", roughness=0.78)
        self.sign_white = make_material("SignBoard", "e8e4d8", roughness=0.68)
        self.bag_kraft = make_material("CementBag", "c8b89b", roughness=0.86)
        self.skin = make_material("WorkerSkin", "e6a777", roughness=0.75)
        self.pants = make_material("WorkerPants", "353b42", roughness=0.82)
        self.boots = make_material("WorkerBoots", "5a402c", roughness=0.84)
        self.shirt_red = make_material("ShirtFlannel", "a8483c", roughness=0.82)
        self.shirt_navy = make_material("ShirtNavy", "3a5268", roughness=0.82)
        self.scaffold_blue = make_material("ScaffoldBlue", "4d748f", roughness=0.55, metallic=0.25)


# ---------------------------------------------------------------------------
# Low-poly BMesh builder
# ---------------------------------------------------------------------------

class LowPolyPart:
    """Accumulates low-poly primitives with per-face material slots into one Mesh."""

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

    def _apply_mat(self, geom, mat):
        slot = self._slot(mat)
        for el in geom:
            if isinstance(el, bmesh.types.BMFace):
                el.material_index = slot

    def _shift(self, pos):
        return Vector(pos) - self.origin

    def box(self, center, size, mat, rot_euler=(0.0, 0.0, 0.0)):
        sx, sy, sz = size
        if sx <= 0 or sy <= 0 or sz <= 0:
            return
        mat_rot = Matrix.Identity(4)
        if any(rot_euler):
            mat_rot = (
                Matrix.Rotation(rot_euler[2], 4, "Z")
                @ Matrix.Rotation(rot_euler[1], 4, "Y")
                @ Matrix.Rotation(rot_euler[0], 4, "X")
            )
        xf = (
            Matrix.Translation(self._shift(center))
            @ mat_rot
            @ Matrix.Diagonal((sx, sy, sz, 1.0))
        )
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=xf)
        faces = list({f for v in res["verts"] for f in v.link_faces})
        self._apply_mat(faces, mat)

    def strut(self, a, b, width, mat, depth=None):
        va = Vector(a)
        vb = Vector(b)
        delta = vb - va
        length = delta.length
        if length < 1e-5:
            return
        d = width if depth is None else depth
        mid = (va + vb) * 0.5
        quat = delta.to_track_quat("Z", "Y")
        xf = (
            Matrix.Translation(self._shift(mid))
            @ quat.to_matrix().to_4x4()
            @ Matrix.Diagonal((width, d, length, 1.0))
        )
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=xf)
        faces = list({f for v in res["verts"] for f in v.link_faces})
        self._apply_mat(faces, mat)

    def cylinder(self, a, b, r_bot, r_top, mat, segments=8):
        va = Vector(a)
        vb = Vector(b)
        delta = vb - va
        length = delta.length
        if length < 1e-5:
            return
        mid = (va + vb) * 0.5
        quat = delta.to_track_quat("Z", "Y")
        xf = Matrix.Translation(self._shift(mid)) @ quat.to_matrix().to_4x4()
        res = bmesh.ops.create_cone(
            self.bm,
            cap_ends=True,
            cap_tris=False,
            segments=segments,
            radius1=r_bot,
            radius2=r_top,
            depth=length,
            matrix=xf,
        )
        faces = list({f for v in res["verts"] for f in v.link_faces})
        self._apply_mat(faces, mat)

    def chamfered_pad(self, center, sx, sy, sz, chamfer, mat):
        cx, cy, cz = self._shift(center)
        hx, hy = sx * 0.5, sy * 0.5
        c = min(chamfer, hx * 0.4, hy * 0.4)
        ring = [
            (cx - hx + c, cy - hy),
            (cx + hx - c, cy - hy),
            (cx + hx, cy - hy + c),
            (cx + hx, cy + hy - c),
            (cx + hx - c, cy + hy),
            (cx - hx + c, cy + hy),
            (cx - hx, cy + hy - c),
            (cx - hx, cy - hy + c),
        ]
        z0 = cz - sz * 0.5
        z1 = cz + sz * 0.5
        bot = [self.bm.verts.new((x, y, z0)) for x, y in ring]
        top = [self.bm.verts.new((x, y, z1)) for x, y in ring]
        faces = []
        n = len(ring)
        for i in range(n):
            j = (i + 1) % n
            faces.append(self.bm.faces.new((bot[i], bot[j], top[j], top[i])))
        faces.append(self.bm.faces.new(list(reversed(bot))))
        faces.append(self.bm.faces.new(top))
        self._apply_mat(faces, mat)

    def finish(self, collection, parent=None, local_location=None):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mat in self.materials:
            mesh.materials.append(mat)
        mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
        mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(obj)
        if parent is not None:
            obj.parent = parent
        if local_location is not None:
            obj.location = Vector(local_location)
        else:
            obj.location = self.origin
        return obj


def make_empty(name, collection, parent=None, location=(0.0, 0.0, 0.0)):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.4
    collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    obj.location = Vector(location)
    return obj


# ---------------------------------------------------------------------------
# Compact residential site layout constants (meters, Blender Z-up)
# ---------------------------------------------------------------------------

PAD_TOP = 0.16

# Small coastal cottage footprint: 6.0m (X) x 4.4m (Y) centered at (0.3, 0.8)
BLD_CX, BLD_CY = 0.3, 0.8
BLD_W, BLD_D = 6.0, 4.4
BLD_X0, BLD_X1 = BLD_CX - BLD_W * 0.5, BLD_CX + BLD_W * 0.5   # -2.7 .. 3.3
BLD_Y0, BLD_Y1 = BLD_CY - BLD_D * 0.5, BLD_CY + BLD_D * 0.5   # -1.4 .. 3.0

Z_PAD = PAD_TOP
Z_FND_TOP = Z_PAD + 0.36          # 0.52m top of concrete stem/slab
Z_DECK_TOP = Z_FND_TOP + 0.24     # 0.76m top of plywood subfloor
WALL_H = 2.40
Z_WALL_TOP = Z_DECK_TOP + WALL_H  # 3.16m top of double top plate
Z_UPPER_DECK = Z_WALL_TOP + 0.20  # 3.36m top of ceiling joists
ROOF_RISE = 1.75
Z_RIDGE = Z_UPPER_DECK + ROOF_RISE  # 5.11m roof ridge


# ---------------------------------------------------------------------------
# 1. Site Base (Compact lot pad, perimeter fence, sawhorses & permit sign)
# ---------------------------------------------------------------------------

def build_site_base(pal, col, parent):
    group = make_empty("SiteBase", col, parent)

    # -- LotPad: compact 13.6m x 10.4m chamfered residential lot --
    lot = LowPolyPart("LotPad")
    lot.chamfered_pad((0.0, 0.0, PAD_TOP * 0.5), 13.6, 10.4, PAD_TOP, 0.65, pal.dirt)
    # Compact gravel driveway apron on front-right (non-overlapping)
    lot.chamfered_pad((3.8, -3.4, PAD_TOP + 0.014), 5.2, 3.0, 0.028, 0.30, pal.gravel)
    lot.chamfered_pad((5.15, 0.3, PAD_TOP + 0.012), 2.5, 4.4, 0.024, 0.25, pal.gravel)
    # Darker excavated earth pad under the cottage footprint
    lot.chamfered_pad((BLD_CX, BLD_CY, PAD_TOP + 0.014), BLD_W + 0.9, BLD_D + 0.9, 0.028, 0.20, pal.dirt_dark)
    # Gravel material staging strip along the left edge
    lot.chamfered_pad((-4.85, 0.2, PAD_TOP + 0.012), 2.8, 7.6, 0.024, 0.25, pal.gravel)
    lot.finish(col, group)

    # -- SitePerimeter: low residential safety fence with driveway opening --
    fence = LowPolyPart("SitePerimeter")

    def fence_run(p0, p1, panels, skip_start=False, skip_end=False):
        v0 = Vector((p0[0], p0[1], PAD_TOP))
        v1 = Vector((p1[0], p1[1], PAD_TOP))
        for i in range(panels + 1):
            if (i == 0 and skip_start) or (i == panels and skip_end):
                continue
            p = v0.lerp(v1, i / panels)
            fence.box((p.x, p.y, PAD_TOP + 0.54), (0.08, 0.08, 1.08), pal.lumber_dark)
        for i in range(panels):
            pa = v0.lerp(v1, i / panels)
            pb = v0.lerp(v1, (i + 1) / panels)
            fence.strut((pa.x, pa.y, PAD_TOP + 0.95), (pb.x, pb.y, PAD_TOP + 0.95), 0.045, pal.lumber_mid)
            fence.strut((pa.x, pa.y, PAD_TOP + 0.26), (pb.x, pb.y, PAD_TOP + 0.26), 0.045, pal.lumber_mid)
            mid = (pa + pb) * 0.5
            seg_len = (pb - pa).length - 0.10
            ang = math.atan2(pb.y - pa.y, pb.x - pa.x)
            fence.box(
                (mid.x, mid.y, PAD_TOP + 0.60),
                (seg_len, 0.025, 0.54),
                pal.safety,
                rot_euler=(0.0, 0.0, ang),
            )

    fence_run((-6.35, 4.75), (6.35, 4.75), 6)
    fence_run((-6.35, -4.75), (-6.35, 4.75), 5, skip_end=True)
    fence_run((6.35, -1.0), (6.35, 4.75), 3, skip_end=True)
    fence_run((-6.35, -4.75), (-1.4, -4.75), 3, skip_start=True)

    # Small safety cones flanking the driveway
    for cx, cy in [(-0.95, -4.55), (6.0, -4.55), (6.0, -1.45)]:
        fence.box((cx, cy, PAD_TOP + 0.022), (0.30, 0.30, 0.044), pal.iron)
        fence.cylinder((cx, cy, PAD_TOP + 0.044), (cx, cy, PAD_TOP + 0.54), 0.11, 0.03, pal.safety, segments=6)
        fence.cylinder((cx, cy, PAD_TOP + 0.30), (cx, cy, PAD_TOP + 0.40), 0.078, 0.060, pal.sign_white, segments=6)

    # Small residential building permit / notice board
    sx, sy = -1.85, -4.15
    for dx in (-0.36, 0.36):
        fence.box((sx + dx, sy, PAD_TOP + 0.72), (0.075, 0.075, 1.44), pal.lumber_dark)
    fence.box((sx, sy, PAD_TOP + 1.18), (0.98, 0.06, 0.64), pal.lumber_dark)
    fence.box((sx, sy - 0.025, PAD_TOP + 1.18), (0.88, 0.025, 0.54), pal.sign_white)
    fence.box((sx, sy - 0.04, PAD_TOP + 1.35), (0.82, 0.02, 0.11), pal.truck_blue)
    fence.finish(col, group)

    # -- SiteProps: sawhorses with plank, toolbox, corner batter stakes --
    props = LowPolyPart("SiteProps")

    def sawhorse(cx, cy, yaw=0.0):
        ca, sa = math.cos(yaw), math.sin(yaw)

        def pt(lx, ly, lz):
            return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, PAD_TOP + lz)

        props.strut(pt(-0.46, 0.0, 0.70), pt(0.46, 0.0, 0.70), 0.08, pal.lumber_mid, 0.06)
        for sx_e in (-0.35, 0.35):
            for sy_l in (-0.24, 0.24):
                props.strut(pt(sx_e, 0.0, 0.68), pt(sx_e, sy_l, 0.0), 0.05, pal.lumber_light)

    sawhorse(-2.9, -3.45, yaw=0.12)
    sawhorse(-1.85, -3.55, yaw=0.06)
    props.strut((-3.15, -3.42, PAD_TOP + 0.75), (-1.55, -3.58, PAD_TOP + 0.75), 0.20, pal.lumber_light, 0.045)

    # Compact green job toolbox
    props.box((-3.85, -3.95, PAD_TOP + 0.28), (0.88, 0.48, 0.52), pal.equip_green, rot_euler=(0, 0, 0.08))
    props.box((-3.85, -3.95, PAD_TOP + 0.56), (0.92, 0.52, 0.07), pal.equip_gold, rot_euler=(0, 0, 0.08))

    # Corner survey stakes
    for sx_c in (BLD_X0 - 0.35, BLD_X1 + 0.35):
        for sy_c in (BLD_Y0 - 0.35, BLD_Y1 + 0.35):
            props.box((sx_c, sy_c, PAD_TOP + 0.20), (0.05, 0.05, 0.40), pal.lumber_dark)
            props.box((sx_c, sy_c, PAD_TOP + 0.36), (0.06, 0.06, 0.09), pal.safety)

    props.finish(col, group)
    return group


# ---------------------------------------------------------------------------
# 2. Material Piles (compact residential quantities, individually depletable)
# ---------------------------------------------------------------------------

def build_materials(pal, col, parent):
    group = make_empty("Materials", col, parent)

    # 2a. Pallet of concrete bags & cinder blocks (front-left)
    p1 = LowPolyPart("Pile_ConcreteBags", origin=(-4.85, -2.55, PAD_TOP))
    p1.box((-4.85, -2.55, PAD_TOP + 0.06), (1.35, 1.15, 0.12), pal.lumber_dark)
    # Bottom row of cinder blocks
    for ix in range(3):
        for iy in range(3):
            bx = -5.25 + ix * 0.40
            by = -2.90 + iy * 0.34
            p1.box((bx, by, PAD_TOP + 0.22), (0.36, 0.28, 0.19), pal.concrete if (ix + iy) % 2 == 0 else pal.concrete_dark)
    # 2 layers of stacked kraft cement bags on top
    for layer in range(2):
        z = PAD_TOP + 0.38 + layer * 0.14
        for ix in range(2):
            for iy in range(2):
                bx = -5.12 + ix * 0.54
                by = -2.78 + iy * 0.44
                p1.box((bx, by, z), (0.48, 0.36, 0.12), pal.bag_kraft, rot_euler=(0, 0, 0.04 * (layer - 0.5)))
    p1.finish(col, group)

    # 2b. Framing lumber stack (middle-left)
    p2 = LowPolyPart("Pile_LumberStack", origin=(-4.85, -0.35, PAD_TOP))
    for dy in (-1.0, 0.0, 1.0):
        p2.box((-4.85, -0.35 + dy, PAD_TOP + 0.05), (1.25, 0.12, 0.10), pal.lumber_dark)
    for layer in range(4):
        z = PAD_TOP + 0.15 + layer * 0.11
        n_b = 5 if layer < 3 else 3
        for i in range(n_b):
            bx = -4.85 - (n_b - 1) * 0.11 + i * 0.22
            mat = pal.lumber_light if (i + layer) % 2 == 0 else pal.lumber_mid
            p2.box((bx, -0.35, z), (0.18, 2.75 - (i % 2) * 0.14, 0.095), mat)
    for dy in (-0.82, 0.82):
        p2.box((-4.85, -0.35 + dy, PAD_TOP + 0.34), (1.14, 0.05, 0.48), pal.safety)
    p2.finish(col, group)

    # 2c. Plywood sheets on pallet with folded teal tarp (back-left)
    p3 = LowPolyPart("Pile_PlywoodSheets", origin=(-4.85, 2.75, PAD_TOP))
    for dx in (-0.75, 0.0, 0.75):
        p3.box((-4.85 + dx, 2.75, PAD_TOP + 0.05), (0.10, 1.15, 0.10), pal.lumber_dark)
    p3.box((-4.85, 2.75, PAD_TOP + 0.12), (2.05, 1.15, 0.04), pal.lumber_dark)
    for layer in range(6):
        z = PAD_TOP + 0.165 + layer * 0.055
        p3.box((-4.85 + 0.015 * ((layer % 3) - 1), 2.75, z), (2.02, 1.08, 0.045), pal.plywood if layer % 2 == 0 else pal.lumber_light)
    p3.box((-5.42, 2.75, PAD_TOP + 0.51), (0.88, 1.12, 0.05), pal.tarp)
    p3.box((-5.84, 2.75, PAD_TOP + 0.32), (0.05, 1.12, 0.40), pal.tarp)
    p3.finish(col, group)

    # 2d. Stacked roof truss / rafter bundle (between lumber and plywood)
    p4 = LowPolyPart("Pile_RoofLumber", origin=(-4.85, 1.40, PAD_TOP))
    for dx in (-0.7, 0.7):
        p4.box((-4.85 + dx, 1.40, PAD_TOP + 0.05), (0.12, 0.90, 0.10), pal.lumber_dark)
    for layer in range(3):
        z = PAD_TOP + 0.15 + layer * 0.11
        for iy in range(3):
            by = 1.40 - 0.26 + iy * 0.26
            p4.box((-4.85, by, z), (2.15, 0.16, 0.09), pal.lumber_light if (layer + iy) % 2 == 0 else pal.lumber_mid)
    p4.finish(col, group)

    return group


# ---------------------------------------------------------------------------
# 3. Residential Equipment (Work Pickup Truck, Cement Mixer, Wheelbarrow,
#    Stepladder, Rolling Scaffold)
# ---------------------------------------------------------------------------

def build_equipment(pal, col, parent):
    group = make_empty("Equipment", col, parent)

    # -- 3a. Compact Pickup Work Truck (parked on front-right driveway) --
    truck_root = make_empty("WorkTruck", col, group, location=(4.75, -2.55, PAD_TOP))
    truck = LowPolyPart("Truck_Body", origin=(0.0, 0.0, 0.0))
    # Oriented facing +Y (front toward house, bed toward driveway)
    # Chassis & bumpers
    truck.box((0.0, 0.0, 0.44), (1.58, 3.85, 0.24), pal.iron)
    truck.box((0.0, 1.96, 0.46), (1.62, 0.14, 0.20), pal.truck_trim)
    truck.box((0.0, -1.96, 0.46), (1.62, 0.14, 0.20), pal.truck_trim)
    # Lower body & hood (+Y)
    truck.box((0.0, 1.25, 0.80), (1.56, 1.25, 0.50), pal.truck_blue)
    # Cab
    truck.box((0.0, 0.18, 0.82), (1.56, 1.15, 0.52), pal.truck_blue)
    truck.box((0.0, 0.16, 1.32), (1.46, 1.04, 0.52), pal.glass)
    # Cab roof & pillars
    truck.box((0.0, 0.16, 1.62), (1.52, 1.10, 0.10), pal.truck_trim)
    for dx in (-0.70, 0.70):
        for dy in (-0.32, 0.64):
            truck.strut((dx, dy, 1.06), (dx, dy, 1.58), 0.06, pal.truck_blue)
    # Pickup bed (-Y side) with side walls & tailgate
    truck.box((0.0, -1.16, 0.62), (1.54, 1.56, 0.12), pal.iron)
    for dx in (-0.72, 0.72):
        truck.box((dx, -1.16, 0.88), (0.10, 1.56, 0.46), pal.truck_blue)
    truck.box((0.0, -1.90, 0.86), (1.52, 0.09, 0.44), pal.truck_blue)
    # Lumber rack headache bar behind cab
    for dx in (-0.68, 0.68):
        truck.strut((dx, -0.40, 1.08), (dx, -0.40, 1.72), 0.055, pal.iron)
    truck.strut((-0.72, -0.40, 1.72), (0.72, -0.40, 1.72), 0.055, pal.iron)
    # Headlights & grille
    truck.box((0.0, 1.89, 0.80), (0.96, 0.04, 0.24), pal.iron)
    for dx in (-0.58, 0.58):
        truck.box((dx, 1.89, 0.84), (0.22, 0.05, 0.15), pal.sign_white)
    # 4 wheels
    for dx in (-0.78, 0.78):
        for dy in (-1.18, 1.18):
            truck.cylinder((dx - 0.10, dy, 0.34), (dx + 0.10, dy, 0.34), 0.34, 0.34, pal.rubber, segments=10)
            truck.cylinder((dx - 0.11, dy, 0.34), (dx + 0.11, dy, 0.34), 0.18, 0.18, pal.truck_trim, segments=8)
    truck.finish(col, truck_root, local_location=(0.0, 0.0, 0.0))

    # Toggleable lumber load resting in pickup bed (front on bed floor, rear resting over tailgate)
    t_load = LowPolyPart("Truck_LumberLoad", origin=(0.0, 0.0, 0.0))
    for i in range(4):
        bx = -0.36 + i * 0.24
        t_load.box((bx, -1.25, 1.04), (0.16, 1.85, 0.12), pal.lumber_light if i % 2 == 0 else pal.lumber_mid, rot_euler=(-0.18, 0.0, 0.0))
    t_load_obj = t_load.finish(col, truck_root, local_location=(0.0, 0.0, 0.0))

    # -- 3b. Portable Wheeled Concrete Mixer (animated drum spin & tilt!) --
    mixer_root = make_empty("CementMixer", col, group, location=(2.45, -2.95, PAD_TOP))
    m_frame = LowPolyPart("Mixer_Frame", origin=(0.0, 0.0, 0.0))
    # Horizontal axle & tow frame
    m_frame.strut((-0.44, 0.0, 0.24), (0.44, 0.0, 0.24), 0.06, pal.iron)
    m_frame.strut((0.0, -0.58, 0.24), (0.0, 0.56, 0.24), 0.06, pal.iron)
    # Front support foot
    m_frame.strut((0.0, 0.45, 0.24), (0.0, 0.45, 0.0), 0.06, pal.iron)
    m_frame.box((0.0, 0.45, 0.03), (0.28, 0.14, 0.06), pal.iron)
    # 2 rubber wheels
    for dx in (-0.48, 0.48):
        m_frame.cylinder((dx - 0.06, 0.0, 0.24), (dx + 0.06, 0.0, 0.24), 0.24, 0.24, pal.rubber, segments=10)
        m_frame.cylinder((dx - 0.065, 0.0, 0.24), (dx + 0.065, 0.0, 0.24), 0.10, 0.10, pal.equip_gold, segments=8)
    # A-frame yoke uprights supporting the drum pivot at Z = 0.86
    for dx in (-0.36, 0.36):
        m_frame.strut((dx, 0.0, 0.24), (dx, 0.0, 0.88), 0.055, pal.iron)
    # Motor box on side
    m_frame.box((0.46, 0.06, 0.68), (0.26, 0.34, 0.32), pal.equip_green)
    m_frame.finish(col, mixer_root, local_location=(0.0, 0.0, 0.0))

    # Tilt pivot (rotates around X to tip drum toward -Y or +Y)
    mixer_tilt = make_empty("Mixer_Tilt", col, mixer_root, location=(0.0, 0.0, 0.88))
    mixer_tilt.rotation_euler.x = math.radians(-28.0)

    # Spinning drum (rotates around its local Z axis!)
    m_drum = LowPolyPart("Mixer_Drum", origin=(0.0, 0.0, 0.0))
    # Lower bowl + tapered mouth along local +Z
    m_drum.cylinder((0.0, 0.0, -0.32), (0.0, 0.0, 0.12), 0.28, 0.38, pal.equip_gold, segments=10)
    m_drum.cylinder((0.0, 0.0, 0.12), (0.0, 0.0, 0.46), 0.38, 0.22, pal.equip_gold, segments=10)
    # Dark ring band + external mixing ribs so rotation is super readable in animation!
    m_drum.cylinder((0.0, 0.0, 0.08), (0.0, 0.0, 0.16), 0.395, 0.395, pal.iron, segments=10)
    for k in range(4):
        ang = k * math.pi * 0.5
        rx, ry = 0.34 * math.cos(ang), 0.34 * math.sin(ang)
        m_drum.box((rx, ry, -0.06), (0.05, 0.05, 0.34), pal.safety, rot_euler=(0.0, 0.0, ang))
    # Wet concrete visible inside mouth
    m_drum.cylinder((0.0, 0.0, 0.22), (0.0, 0.0, 0.36), 0.24, 0.19, pal.concrete_wet, segments=8)
    m_drum_obj = m_drum.finish(col, mixer_tilt, local_location=(0.0, 0.0, 0.0))

    # -- 3c. Wheelbarrow (rolls between mixer and foundation) --
    wb_root = make_empty("Wheelbarrow", col, group, location=(1.40, -2.90, PAD_TOP))
    wb = LowPolyPart("Wheelbarrow_Body", origin=(0.0, 0.0, 0.0))
    # Tray
    wb.box((0.0, 0.0, 0.46), (0.58, 0.78, 0.28), pal.safety)
    # Front wheel (+Y)
    wb.cylinder((-0.06, 0.54, 0.17), (0.06, 0.54, 0.17), 0.17, 0.17, pal.rubber, segments=8)
    # Handles & rear legs
    for dx in (-0.22, 0.22):
        wb.strut((dx, 0.54, 0.18), (dx, -0.78, 0.42), 0.045, pal.lumber_mid)
        wb.strut((dx, -0.26, 0.32), (dx, -0.30, 0.0), 0.04, pal.iron)
    wb.finish(col, wb_root, local_location=(0.0, 0.0, 0.0))

    wb_conc = LowPolyPart("Wheelbarrow_Concrete", origin=(0.0, 0.0, 0.0))
    wb_conc.box((0.0, 0.0, 0.58), (0.50, 0.68, 0.14), pal.concrete_wet)
    wb_conc_obj = wb_conc.finish(col, wb_root, local_location=(0.0, 0.0, 0.0))

    # -- 3d. Portable Wooden A-Frame Stepladder --
    ladder = LowPolyPart("Stepladder", origin=(0.0, 0.0, 0.0))
    lh = 1.85
    spread = 0.52
    for dx in (-0.22, 0.22):
        ladder.strut((dx, -spread, 0.0), (dx, -0.05, lh), 0.05, pal.lumber_mid)
        ladder.strut((dx, spread, 0.0), (dx, 0.05, lh), 0.045, pal.lumber_dark)
    ladder.box((0.0, 0.0, lh + 0.02), (0.54, 0.22, 0.045), pal.lumber_mid)
    for step in range(1, 5):
        frac = step / 5.0
        sy = -spread * (1.0 - frac) - 0.05 * frac
        sz = lh * frac
        ladder.box((0.0, sy, sz), (0.44, 0.09, 0.035), pal.lumber_light)
    ladder_obj = ladder.finish(col, group, local_location=(-2.85, -1.65, PAD_TOP))

    # -- 3e. Compact Rolling Steel Scaffold (for upper framing & roof trusses) --
    scaf = LowPolyPart("Scaffold", origin=(0.0, 0.0, 0.0))
    sw, sd, sh = 1.65, 0.85, 2.05
    # 4 corner tubular posts + caster wheels
    for sx in (-sw * 0.5, sw * 0.5):
        for sy in (-sd * 0.5, sd * 0.5):
            scaf.cylinder((sx, sy, 0.14), (sx, sy, sh + 0.85), 0.032, 0.032, pal.scaffold_blue, segments=6)
            scaf.cylinder((sx - 0.04, sy, 0.07), (sx + 0.04, sy, 0.07), 0.07, 0.07, pal.rubber, segments=6)
    # Cross braces & guard rails
    for sz in (0.35, sh, sh + 0.82):
        scaf.strut((-sw * 0.5, -sd * 0.5, sz), (sw * 0.5, -sd * 0.5, sz), 0.04, pal.scaffold_blue)
        scaf.strut((-sw * 0.5, sd * 0.5, sz), (sw * 0.5, sd * 0.5, sz), 0.04, pal.scaffold_blue)
        scaf.strut((-sw * 0.5, -sd * 0.5, sz), (-sw * 0.5, sd * 0.5, sz), 0.04, pal.scaffold_blue)
        scaf.strut((sw * 0.5, -sd * 0.5, sz), (sw * 0.5, sd * 0.5, sz), 0.04, pal.scaffold_blue)
    # Diagonal X-brace on front/back
    scaf.strut((-sw * 0.5, -sd * 0.5, 0.35), (sw * 0.5, -sd * 0.5, sh), 0.032, pal.scaffold_blue)
    scaf.strut((sw * 0.5, -sd * 0.5, 0.35), (-sw * 0.5, -sd * 0.5, sh), 0.032, pal.scaffold_blue)
    # Wooden work plank deck
    for dy in (-0.22, 0.0, 0.22):
        scaf.box((0.0, dy, sh + 0.035), (sw - 0.06, 0.20, 0.05), pal.lumber_light)
    scaf_obj = scaf.finish(col, group, local_location=(4.55, 1.65, PAD_TOP))

    return {
        "truck": truck_root,
        "truck_load": t_load_obj,
        "mixer": mixer_root,
        "mixer_tilt": mixer_tilt,
        "mixer_drum": m_drum_obj,
        "wheelbarrow": wb_root,
        "wheelbarrow_concrete": wb_conc_obj,
        "ladder": ladder_obj,
        "scaffold": scaf_obj,
    }


# ---------------------------------------------------------------------------
# 4. Low-Poly Construction Workers (matching Tideways person_low proportions)
# ---------------------------------------------------------------------------

def build_worker(name, pal, col, parent, location, yaw_deg, shirt_mat, vest_mat, hat_mat, has_hammer=True):
    root = make_empty(name, col, parent, location=location)
    root.rotation_euler.z = math.radians(yaw_deg)

    # Body (legs, boots, torso, vest, head, hard hat)
    body = LowPolyPart(f"{name}_Body", origin=(0.0, 0.0, 0.0))
    # Boots & legs (standing Z = 0..0.72)
    for dx in (-0.11, 0.11):
        body.box((dx, 0.03, 0.07), (0.14, 0.22, 0.14), pal.boots)
        body.box((dx, 0.0, 0.42), (0.15, 0.17, 0.58), pal.pants)
    # Torso & high-vis vest (Z = 0.70..1.26)
    body.box((0.0, 0.0, 0.98), (0.42, 0.24, 0.54), shirt_mat)
    body.box((0.0, 0.0, 0.99), (0.44, 0.26, 0.46), vest_mat)
    # Reflective stripe on vest
    body.box((0.0, 0.0, 0.90), (0.45, 0.27, 0.06), pal.sign_white)
    # Neck & chunky low-poly head (Z = 1.26..1.64)
    body.box((0.0, 0.0, 1.29), (0.14, 0.14, 0.08), pal.skin)
    body.box((0.0, 0.0, 1.46), (0.30, 0.28, 0.30), pal.skin)
    # Simple eyes (+Y is forward)
    for dx in (-0.07, 0.07):
        body.box((dx, 0.145, 1.47), (0.035, 0.02, 0.065), pal.rubber)
    # Hard hat dome + brim
    body.box((0.0, 0.01, 1.63), (0.34, 0.34, 0.13), hat_mat)
    body.box((0.0, 0.06, 1.58), (0.35, 0.40, 0.04), hat_mat)
    body.box((0.0, 0.0, 1.71), (0.10, 0.30, 0.05), hat_mat)
    body.finish(col, root, local_location=(0.0, 0.0, 0.0))

    # Left arm (pivots at shoulder (-0.27, 0.0, 1.18))
    arm_l = LowPolyPart(f"{name}_ArmL", origin=(0.0, 0.0, 0.0))
    arm_l.box((0.0, 0.0, -0.20), (0.13, 0.14, 0.42), shirt_mat)
    arm_l.box((0.0, 0.0, -0.44), (0.11, 0.11, 0.11), pal.skin)
    arm_l_obj = arm_l.finish(col, root, local_location=(-0.28, 0.0, 1.18))

    # Right arm (pivots at shoulder (0.27, 0.0, 1.18)), optionally holding hammer
    arm_r = LowPolyPart(f"{name}_ArmR", origin=(0.0, 0.0, 0.0))
    arm_r.box((0.0, 0.0, -0.20), (0.13, 0.14, 0.42), shirt_mat)
    arm_r.box((0.0, 0.0, -0.44), (0.11, 0.11, 0.11), pal.skin)
    if has_hammer:
        # Carpenter hammer extending forward (+Y) from hand
        arm_r.strut((0.0, 0.0, -0.46), (0.0, 0.30, -0.46), 0.035, pal.lumber_mid)
        arm_r.box((0.0, 0.28, -0.46), (0.05, 0.06, 0.16), pal.iron)
    arm_r_obj = arm_r.finish(col, root, local_location=(0.28, 0.0, 1.18))

    return {"root": root, "arm_l": arm_l_obj, "arm_r": arm_r_obj}


def build_workers(pal, col, parent):
    group = make_empty("Workers", col, parent)
    w1 = build_worker(
        "Worker_1", pal, col, group,
        location=(-0.9, -2.8, PAD_TOP), yaw_deg=20.0,
        shirt_mat=pal.shirt_red, vest_mat=pal.safety, hat_mat=pal.equip_gold,
        has_hammer=True,
    )
    w2 = build_worker(
        "Worker_2", pal, col, group,
        location=(3.45, -1.45, PAD_TOP), yaw_deg=-55.0,
        shirt_mat=pal.shirt_navy, vest_mat=pal.vest_lime, hat_mat=pal.sign_white,
        has_hammer=True,
    )
    return {"w1": w1, "w2": w2}


# ---------------------------------------------------------------------------
# 5. Staged Coastal Cottage Framing (with tilt-up walls!)
# ---------------------------------------------------------------------------

def add_framed_wall(part, pal, x0, y0, x1, y1, z_bot, height, openings, thickness=0.13):
    """Add a low-poly stud-framed wall between (x0,y0) and (x1,y1) onto `part`."""
    v0 = Vector((x0, y0, 0.0))
    v1 = Vector((x1, y1, 0.0))
    dv = v1 - v0
    length = dv.length
    dir_v = dv / length
    ang = math.atan2(dir_v.y, dir_v.x)

    def wbox(u_mid, u_len, z_mid, z_len, mat, thick=thickness):
        p = v0 + dir_v * u_mid
        part.box((p.x, p.y, z_mid), (u_len, thick, z_len), mat, rot_euler=(0.0, 0.0, ang))

    # Sole plate (skip door openings where sill_z_rel == 0)
    plate_h = 0.065
    door_spans = sorted((a, b) for a, b, sz, _ in openings if sz <= 0.05)
    cur = 0.0
    for a, b in door_spans:
        if a > cur + 0.05:
            wbox((cur + a) * 0.5, a - cur, z_bot + plate_h * 0.5, plate_h, pal.lumber_mid)
        cur = b
    if cur < length - 0.05:
        wbox((cur + length) * 0.5, length - cur, z_bot + plate_h * 0.5, plate_h, pal.lumber_mid)

    # Double top plate
    wbox(length * 0.5, length, z_bot + height - 0.055, 0.11, pal.lumber_mid)

    # Studs on ~0.60m centers
    stud_w = 0.07
    n_studs = max(2, int(round(length / 0.60)))
    stud_positions = [i * length / n_studs for i in range(n_studs + 1)]
    for a, b, sz, hz in openings:
        stud_positions.extend([a, b])
    stud_positions = sorted(set(round(u, 3) for u in stud_positions))

    z_stud_bot = z_bot + plate_h
    z_stud_top = z_bot + height - 0.11

    for u in stud_positions:
        inside = None
        for a, b, sz, hz in openings:
            if a + 0.04 < u < b - 0.04:
                inside = (a, b, sz, hz)
                break
        if inside is None:
            wbox(u, stud_w, (z_stud_bot + z_stud_top) * 0.5, z_stud_top - z_stud_bot, pal.lumber_light)
        else:
            _, _, sz, hz = inside
            if sz > 0.12:
                c_top = z_bot + sz - 0.04
                if c_top > z_stud_bot + 0.06:
                    wbox(u, stud_w, (z_stud_bot + c_top) * 0.5, c_top - z_stud_bot, pal.lumber_light)
            c_bot = z_bot + hz + 0.14
            if z_stud_top > c_bot + 0.05:
                wbox(u, stud_w, (c_bot + z_stud_top) * 0.5, z_stud_top - c_bot, pal.lumber_light)

    for a, b, sz, hz in openings:
        span = b - a
        mid = (a + b) * 0.5
        wbox(mid, span + 0.04, z_bot + hz + 0.07, 0.14, pal.lumber_mid, thick=thickness - 0.008)
        if sz > 0.10:
            wbox(mid, span - 0.02, z_bot + sz, 0.07, pal.lumber_mid, thick=thickness - 0.008)


def build_building_stages(pal, col, parent):
    group = make_empty("BuildingStages", col, parent)

    # -- Stage 1: Compact Concrete Foundation & Porch Pad --
    s1 = LowPolyPart("Stage1_Foundation", origin=(BLD_CX, BLD_CY, Z_PAD))
    s1.box((BLD_CX, BLD_CY, Z_PAD + 0.08), (BLD_W + 0.30, BLD_D + 0.30, 0.16), pal.concrete_dark)
    s1.box((BLD_CX, BLD_CY, Z_PAD + 0.25), (BLD_W, BLD_D, 0.22), pal.concrete)
    # Front porch footing pad (matches Tideways coastal cottage porch)
    porch_cx = BLD_CX - 0.90
    s1.box((porch_cx, BLD_Y0 - 0.55, Z_PAD + 0.15), (2.0, 1.10, 0.30), pal.concrete)
    # Concrete steps base
    s1.box((porch_cx, BLD_Y0 - 1.25, Z_PAD + 0.08), (1.15, 0.36, 0.16), pal.concrete_dark)
    # Wood form boards along front & right edge
    s1.box((BLD_CX, BLD_Y0 - 0.045, Z_PAD + 0.20), (BLD_W + 0.14, 0.05, 0.20), pal.lumber_dark)
    s1.box((BLD_X1 + 0.045, BLD_CY, Z_PAD + 0.20), (0.05, BLD_D + 0.14, 0.20), pal.lumber_dark)
    s1_obj = s1.finish(col, group)

    # -- Stage 2: Floor Joists & Plywood Subfloor Deck --
    s2 = LowPolyPart("Stage2_FloorDeck", origin=(BLD_CX, BLD_CY, Z_FND_TOP))
    # Treated sill plates
    s2.box((BLD_CX, BLD_Y0 + 0.08, Z_FND_TOP + 0.035), (BLD_W, 0.16, 0.07), pal.lumber_dark)
    s2.box((BLD_CX, BLD_Y1 - 0.08, Z_FND_TOP + 0.035), (BLD_W, 0.16, 0.07), pal.lumber_dark)
    s2.box((BLD_X0 + 0.08, BLD_CY, Z_FND_TOP + 0.035), (0.16, BLD_D - 0.32, 0.07), pal.lumber_dark)
    s2.box((BLD_X1 - 0.08, BLD_CY, Z_FND_TOP + 0.035), (0.16, BLD_D - 0.32, 0.07), pal.lumber_dark)
    # Joists
    joist_z = Z_FND_TOP + 0.135
    s2.box((BLD_CX, BLD_Y0 + 0.04, joist_z), (BLD_W, 0.07, 0.15), pal.lumber_mid)
    s2.box((BLD_CX, BLD_Y1 - 0.04, joist_z), (BLD_W, 0.07, 0.15), pal.lumber_mid)
    for i in range(10):
        jx = BLD_X0 + 0.06 + i * (BLD_W - 0.12) / 9.0
        s2.box((jx, BLD_CY, joist_z), (0.065, BLD_D - 0.14, 0.14), pal.lumber_light)
    # Plywood subfloor panels
    for ix in range(3):
        for iy in range(2):
            pw = (BLD_W - 0.06) / 3.0
            pd = (BLD_D - 0.06) / 2.0
            px = BLD_X0 + 0.03 + (ix + 0.5) * pw
            py = BLD_Y0 + 0.03 + (iy + 0.5) * pd
            mat = pal.plywood if (ix + iy) % 2 == 0 else pal.lumber_light
            s2.box((px, py, Z_DECK_TOP - 0.022), (pw - 0.025, pd - 0.025, 0.044), mat)
    # Front porch wood deck planks & 2 steps
    for iy in range(5):
        py = BLD_Y0 - 0.12 - iy * 0.21
        s2.box((porch_cx, py, Z_FND_TOP + 0.04), (1.96, 0.18, 0.045), pal.lumber_mid if iy % 2 == 0 else pal.lumber_light)
    s2.box((porch_cx, BLD_Y0 - 1.24, Z_PAD + 0.22), (1.10, 0.24, 0.05), pal.lumber_light)
    s2_obj = s2.finish(col, group)

    # -- Stage 3: Pivoted Tilt-Up Stud Walls + Interior & Porch Posts --
    s3_group = make_empty("Stage3_Walls", col, group)

    # 3a. Back wall (pivots along bottom edge at Y = BLD_Y1 - 0.065)
    w_back = LowPolyPart("Wall_Back", origin=(BLD_CX, BLD_Y1 - 0.065, Z_DECK_TOP))
    add_framed_wall(
        w_back, pal,
        BLD_X0 + 0.065, BLD_Y1 - 0.065, BLD_X1 - 0.065, BLD_Y1 - 0.065,
        Z_DECK_TOP, WALL_H,
        openings=[(0.9, 2.05, 0.80, 1.90), (3.4, 4.7, 0.80, 1.90)],
    )
    w_back_obj = w_back.finish(col, s3_group)

    # 3b. Left wall (pivots along bottom edge at X = BLD_X0 + 0.065)
    w_left = LowPolyPart("Wall_Left", origin=(BLD_X0 + 0.065, BLD_CY, Z_DECK_TOP))
    add_framed_wall(
        w_left, pal,
        BLD_X0 + 0.065, BLD_Y0 + 0.13, BLD_X0 + 0.065, BLD_Y1 - 0.13,
        Z_DECK_TOP, WALL_H,
        openings=[(0.85, 1.90, 0.80, 1.90), (2.45, 3.45, 0.80, 1.90)],
    )
    w_left_obj = w_left.finish(col, s3_group)

    # 3c. Right wall (pivots along bottom edge at X = BLD_X1 - 0.065)
    w_right = LowPolyPart("Wall_Right", origin=(BLD_X1 - 0.065, BLD_CY, Z_DECK_TOP))
    add_framed_wall(
        w_right, pal,
        BLD_X1 - 0.065, BLD_Y0 + 0.13, BLD_X1 - 0.065, BLD_Y1 - 0.13,
        Z_DECK_TOP, WALL_H,
        openings=[(0.85, 1.90, 0.80, 1.90), (2.45, 3.45, 0.80, 1.90)],
    )
    w_right_obj = w_right.finish(col, s3_group)

    # 3d. Front wall (pivots along bottom edge at Y = BLD_Y0 + 0.065)
    w_front = LowPolyPart("Wall_Front", origin=(BLD_CX, BLD_Y0 + 0.065, Z_DECK_TOP))
    add_framed_wall(
        w_front, pal,
        BLD_X0 + 0.065, BLD_Y0 + 0.065, BLD_X1 - 0.065, BLD_Y0 + 0.065,
        Z_DECK_TOP, WALL_H,
        openings=[
            (1.55, 2.55, 0.0, 1.98),    # Cottage front door (aligns with porch!)
            (0.45, 1.25, 0.80, 1.90),   # Left window
            (3.45, 4.95, 0.80, 1.90),   # Right double cottage window
        ],
    )
    w_front_obj = w_front.finish(col, s3_group)

    # 3e. Interior partition, wind braces & front porch posts/beam
    w_int = LowPolyPart("Wall_InteriorAndPorch", origin=(BLD_CX, BLD_CY, Z_DECK_TOP))
    add_framed_wall(
        w_int, pal,
        BLD_CX + 0.15, BLD_Y0 + 0.16, BLD_CX + 0.15, BLD_Y1 - 0.16,
        Z_DECK_TOP, WALL_H,
        openings=[(1.35, 2.45, 0.0, 1.96)],
        thickness=0.10,
    )
    # Corner wind bracing
    w_int.strut((BLD_X0 + 0.12, BLD_Y0 + 0.01, Z_DECK_TOP + 0.10), (BLD_X0 + 1.25, BLD_Y0 + 0.01, Z_WALL_TOP - 0.14), 0.05, pal.lumber_dark)
    w_int.strut((BLD_X1 - 0.01, BLD_Y0 + 0.18, Z_DECK_TOP + 0.10), (BLD_X1 - 0.01, BLD_Y0 + 1.35, Z_WALL_TOP - 0.14), 0.05, pal.lumber_dark)
    # Front porch posts & header beam
    for px in (porch_cx - 0.88, porch_cx + 0.88):
        w_int.box((px, BLD_Y0 - 0.98, Z_FND_TOP + 0.06 + 1.28), (0.12, 0.12, 2.56), pal.lumber_mid)
    w_int.box((porch_cx, BLD_Y0 - 0.98, Z_WALL_TOP - 0.08), (1.96, 0.14, 0.16), pal.lumber_mid)
    w_int_obj = w_int.finish(col, s3_group)

    # -- Stage 4: Ceiling Joists, Rim Band, Gable Ends & Ridge Beam --
    s4 = LowPolyPart("Stage4_UpperFrameAndGables", origin=(BLD_CX, BLD_CY, Z_WALL_TOP))
    band_z = Z_WALL_TOP + 0.10
    s4.box((BLD_CX, BLD_Y0 + 0.055, band_z), (BLD_W, 0.09, 0.19), pal.lumber_mid)
    s4.box((BLD_CX, BLD_Y1 - 0.055, band_z), (BLD_W, 0.09, 0.19), pal.lumber_mid)
    s4.box((BLD_X0 + 0.055, BLD_CY, band_z), (0.09, BLD_D - 0.18, 0.19), pal.lumber_mid)
    s4.box((BLD_X1 - 0.055, BLD_CY, band_z), (0.09, BLD_D - 0.18, 0.19), pal.lumber_mid)
    for i in range(9):
        jx = BLD_X0 + 0.30 + i * (BLD_W - 0.60) / 8.0
        s4.box((jx, BLD_CY, band_z), (0.065, BLD_D - 0.16, 0.17), pal.lumber_light)

    half_d = BLD_D * 0.5
    for gx in (BLD_X0 + 0.065, BLD_X1 - 0.065):
        s4.strut((gx, BLD_Y0, Z_UPPER_DECK), (gx, BLD_CY, Z_RIDGE), 0.095, pal.lumber_mid)
        s4.strut((gx, BLD_Y1, Z_UPPER_DECK), (gx, BLD_CY, Z_RIDGE), 0.095, pal.lumber_mid)
        for k in range(-2, 3):
            gy = BLD_CY + k * 0.64
            frac = 1.0 - abs(gy - BLD_CY) / half_d
            h_g = ROOF_RISE * frac - 0.05
            if h_g > 0.16:
                s4.box((gx, gy, Z_UPPER_DECK + h_g * 0.5), (0.08, 0.07, h_g), pal.lumber_light)
        # Small gable attic window frame
        s4.box((gx, BLD_CY, Z_UPPER_DECK + 0.78), (0.09, 0.64, 0.07), pal.lumber_mid)
        s4.box((gx, BLD_CY, Z_UPPER_DECK + 1.28), (0.09, 0.64, 0.075), pal.lumber_mid)

    # Ridge beam
    s4.box((BLD_CX, BLD_CY, Z_RIDGE), (BLD_W + 0.56, 0.095, 0.17), pal.lumber_mid)
    s4_obj = s4.finish(col, group)

    # -- Stage 5: Roof Trusses (split into 3 animated parts for sequential build!) --
    s5_group = make_empty("Stage5_Roof", col, group)
    overhang_y = 0.38
    eave_z = Z_UPPER_DECK - overhang_y * (ROOF_RISE / half_d)
    pitch = math.atan2(Z_RIDGE - eave_z, half_d + overhang_y)

    n_trusses = 7
    truss_xs = [BLD_X0 + 0.60 + i * (BLD_W - 1.20) / (n_trusses - 1) for i in range(n_trusses)]

    def add_truss(part, tx):
        p_front = (tx, BLD_Y0 - overhang_y, eave_z)
        p_back = (tx, BLD_Y1 + overhang_y, eave_z)
        p_peak = (tx, BLD_CY, Z_RIDGE)
        p_mid = (tx, BLD_CY, Z_UPPER_DECK)
        part.strut(p_front, p_peak, 0.08, pal.lumber_light)
        part.strut(p_back, p_peak, 0.08, pal.lumber_light)
        part.strut(p_mid, p_peak, 0.07, pal.lumber_mid)
        part.strut(p_mid, (tx, BLD_CY - half_d * 0.5, Z_UPPER_DECK + ROOF_RISE * 0.5), 0.055, pal.lumber_light)
        part.strut(p_mid, (tx, BLD_CY + half_d * 0.5, Z_UPPER_DECK + ROOF_RISE * 0.5), 0.055, pal.lumber_light)

    s5a = LowPolyPart("Stage5a_TrussesLeft", origin=(BLD_CX, BLD_CY, Z_UPPER_DECK))
    for tx in truss_xs[:4]:
        add_truss(s5a, tx)
    s5a_obj = s5a.finish(col, s5_group)

    s5b = LowPolyPart("Stage5b_TrussesRight", origin=(BLD_CX, BLD_CY, Z_UPPER_DECK))
    for tx in truss_xs[4:]:
        add_truss(s5b, tx)
    # Eave fascia & purlins along both slopes
    for side in (-1, 1):
        ey = BLD_CY + side * (half_d + overhang_y)
        s5b.box((BLD_CX, ey, eave_z - 0.025), (BLD_W + 0.56, 0.055, 0.14), pal.lumber_mid)
        for frac in (0.28, 0.62):
            py = BLD_CY + side * (half_d + overhang_y) * frac
            pz = Z_RIDGE - (Z_RIDGE - eave_z) * frac + 0.05
            s5b.box(
                (BLD_CX, py, pz),
                (BLD_W + 0.52, 0.07, 0.045),
                pal.lumber_light,
                rot_euler=(-side * pitch, 0.0, 0.0),
            )
    s5b_obj = s5b.finish(col, s5_group)

    # Charming little cottage porch gable roof
    s5c = LowPolyPart("Stage5c_PorchRoof", origin=(porch_cx, BLD_Y0 - 0.55, Z_WALL_TOP))
    px0, px1 = porch_cx - 1.02, porch_cx + 1.02
    p_peak_z = Z_WALL_TOP + 0.78
    for py in (BLD_Y0 - 1.08, BLD_Y0 - 0.56, BLD_Y0 - 0.04):
        s5c.strut((px0, py, Z_WALL_TOP - 0.04), (porch_cx, py, p_peak_z), 0.07, pal.lumber_light)
        s5c.strut((px1, py, Z_WALL_TOP - 0.04), (porch_cx, py, p_peak_z), 0.07, pal.lumber_light)
    s5c.strut((porch_cx, BLD_Y0 - 1.15, p_peak_z), (porch_cx, BLD_Y0 + 0.12, p_peak_z), 0.08, pal.lumber_mid)
    s5c_obj = s5c.finish(col, s5_group)

    return {
        "s1": s1_obj,
        "s2": s2_obj,
        "w_back": w_back_obj,
        "w_left": w_left_obj,
        "w_right": w_right_obj,
        "w_front": w_front_obj,
        "w_int": w_int_obj,
        "s4": s4_obj,
        "s5a": s5a_obj,
        "s5b": s5b_obj,
        "s5c": s5c_obj,
    }


# ---------------------------------------------------------------------------
# Studio & Preview Rendering
# ---------------------------------------------------------------------------

def setup_studio(scene):
    studio = bpy.data.collections.new("PreviewStudio")
    scene.collection.children.link(studio)

    bpy.ops.mesh.primitive_plane_add(size=160, location=(0.0, 0.0, -0.02))
    floor = bpy.context.object
    floor.name = "StudioFloor"
    fmat = make_material("BackdropFloor", "d4dbd6", roughness=0.95)
    floor.data.materials.append(fmat)

    world = bpy.data.worlds.new("Daylight")
    if not world.node_tree:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.78, 0.84, 0.91, 1.0)
    bg.inputs[1].default_value = 0.72
    scene.world = world

    bpy.ops.object.light_add(type="AREA", location=(-14.0, -18.0, 26.0))
    key = bpy.context.object
    key.name = "KeyLight"
    key.rotation_euler = (Vector((0, 0, 1.5)) - key.location).to_track_quat("-Z", "Y").to_euler()
    key.data.energy = 19000
    key.data.shape = "DISK"
    key.data.size = 12.0
    key.data.color = (1.0, 0.97, 0.92)

    bpy.ops.object.light_add(type="AREA", location=(20.0, 14.0, 16.0))
    fill = bpy.context.object
    fill.name = "FillLight"
    fill.rotation_euler = (Vector((0, 0, 1.5)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    fill.data.energy = 5000
    fill.data.shape = "DISK"
    fill.data.size = 14.0
    fill.data.color = (0.85, 0.92, 1.0)

    # Orthographic three-quarter camera matching Tideways previews, tighter for compact house lot
    target = Vector((0.0, 0.1, 1.9))
    bpy.ops.object.camera_add(location=target + Vector((-18.0, -22.5, 16.5)))
    cam = bpy.context.object
    cam.name = "PreviewCamera"
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 18.2
    scene.camera = cam

    for obj in (floor, key, fill, cam):
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        studio.objects.link(obj)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:
        pass
    scene.render.image_settings.file_format = "PNG"
    return studio


def set_hidden(obj, hide):
    obj.hide_viewport = hide
    obj.hide_render = hide


def render_stages_grid(scene, stages, materials_group, equip, workers):
    """Render 4 progression stages and stitch into a 2x2 preview PNG."""
    import tempfile

    piles = {c.name: c for c in materials_group.children}
    all_stage_keys = ["s1", "s2", "w_back", "w_left", "w_right", "w_front", "w_int", "s4", "s5a", "s5b", "s5c"]

    configs = [
        # 0: Cleared lot + cement mixer pouring foundation
        {
            "visible": ["s1"],
            "hidden_piles": [],
            "front_tilt": 0.0,
            "w1_loc": (1.0, -2.55, PAD_TOP),
            "w2_loc": (3.1, -2.35, PAD_TOP),
            "scaf_loc": (4.35, 1.35, PAD_TOP),
            "truck_load": True,
        },
        # 1: Subfloor deck down + back & side walls up, front wall mid-tilt!
        {
            "visible": ["s1", "s2", "w_back", "w_left", "w_right", "w_front"],
            "hidden_piles": ["Pile_ConcreteBags", "Pile_PlywoodSheets"],
            "front_tilt": -42.0,
            "w1_loc": (-0.6, -0.45, Z_DECK_TOP),
            "w2_loc": (1.4, -0.45, Z_DECK_TOP),
            "scaf_loc": (4.35, 1.35, PAD_TOP),
            "truck_load": True,
        },
        # 2: All walls & gables framed, rolling scaffold pulled up beside house
        {
            "visible": ["s1", "s2", "w_back", "w_left", "w_right", "w_front", "w_int", "s4", "s5a"],
            "hidden_piles": ["Pile_ConcreteBags", "Pile_PlywoodSheets", "Pile_LumberStack"],
            "front_tilt": 0.0,
            "w1_loc": (-1.5, -2.35, PAD_TOP),
            "w2_loc": (3.85, 0.85, PAD_TOP + 2.08),
            "scaf_loc": (3.85, 0.85, PAD_TOP),
            "truck_load": False,
        },
        # 3: Completed cottage wood framing + porch gable
        {
            "visible": all_stage_keys,
            "hidden_piles": ["Pile_ConcreteBags", "Pile_PlywoodSheets", "Pile_LumberStack", "Pile_RoofLumber"],
            "front_tilt": 0.0,
            "w1_loc": (-0.9, -2.8, PAD_TOP),
            "w2_loc": (3.55, -0.6, PAD_TOP),
            "scaf_loc": (4.35, 1.35, PAD_TOP),
            "truck_load": False,
        },
    ]

    scene.render.resolution_x = 700
    scene.render.resolution_y = 520
    scene.cycles.samples = 16

    tile_paths = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, cfg in enumerate(configs):
            for k in all_stage_keys:
                set_hidden(stages[k], k not in cfg["visible"])
            for pname, pobj in piles.items():
                set_hidden(pobj, pname in cfg["hidden_piles"])
            stages["w_front"].rotation_euler.x = math.radians(cfg["front_tilt"])
            workers["w1"]["root"].location = Vector(cfg["w1_loc"])
            workers["w2"]["root"].location = Vector(cfg["w2_loc"])
            equip["scaffold"].location = Vector(cfg["scaf_loc"])
            set_hidden(equip["truck_load"], not cfg["truck_load"])

            out_path = Path(tmpdir) / f"stage_{idx}.png"
            scene.render.filepath = str(out_path)
            bpy.ops.render.render(write_still=True)
            tile_paths.append(out_path)

        w, h = 700, 520
        grid = bpy.data.images.new("StagesGrid", width=w * 2, height=h * 2, alpha=True)
        pixels = [0.0] * (w * 2 * h * 2 * 4)
        coords = [(0, 1), (1, 1), (0, 0), (1, 0)]
        for idx, tp in enumerate(tile_paths):
            img = bpy.data.images.load(str(tp))
            src = list(img.pixels)
            ox, oy = coords[idx]
            for row in range(h):
                src_start = row * w * 4
                dst_row = oy * h + row
                dst_start = (dst_row * (w * 2) + ox * w) * 4
                pixels[dst_start:dst_start + w * 4] = src[src_start:src_start + w * 4]
            bpy.data.images.remove(img)
        grid.pixels.foreach_set(pixels)
        grid.filepath_raw = str(STAGES_PREVIEW_PATH)
        grid.file_format = "PNG"
        grid.save()
        bpy.data.images.remove(grid)

    # Restore hero pose
    for k in all_stage_keys:
        set_hidden(stages[k], False)
    for pobj in piles.values():
        set_hidden(pobj, False)
    stages["w_front"].rotation_euler.x = 0.0
    workers["w1"]["root"].location = Vector((-0.9, -2.8, PAD_TOP))
    workers["w2"]["root"].location = Vector((3.45, -1.45, PAD_TOP))
    equip["scaffold"].location = Vector((4.55, 1.65, PAD_TOP))
    set_hidden(equip["truck_load"], False)


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    pal = Palette()

    asset_col = bpy.data.collections.new("HouseConstructionSite")
    scene.collection.children.link(asset_col)

    root = make_empty("HouseConstructionSite", asset_col)
    build_site_base(pal, asset_col, root)
    materials_group = build_materials(pal, asset_col, root)
    equip = build_equipment(pal, asset_col, root)
    workers = build_workers(pal, asset_col, root)
    stages = build_building_stages(pal, asset_col, root)

    # Print triangle stats
    total_tris = 0
    for obj in asset_col.objects:
        if obj.type == "MESH":
            tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            total_tris += tris
            print(f"  {obj.name:28s} {tris:5d} tris")
    print(f"TOTAL: {total_tris} tris")

    # Export clean GLB
    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in asset_col.objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_PATH),
        export_format="GLB",
        use_selection=True,
    )

    # Add studio for previews & save .blend
    studio = setup_studio(scene)

    scene.render.resolution_x = 1200
    scene.render.resolution_y = 860
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 24
    scene.render.filepath = str(HERO_PREVIEW_PATH)
    bpy.ops.render.render(write_still=True)

    render_stages_grid(scene, stages, materials_group, equip, workers)

    for obj in studio.objects:
        obj.hide_viewport = True

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)
    print(f"Saved: {BLEND_PATH}")
    print(f"Exported: {GLB_PATH}")
    print(f"Previews: {HERO_PREVIEW_PATH}, {STAGES_PREVIEW_PATH}")


if __name__ == "__main__":
    build()
