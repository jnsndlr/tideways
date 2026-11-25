"""Build a modular low-poly construction site for Tideways.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/construction_site.py

Outputs:
    art/construction_site.blend
    assets/models/construction_site.glb
    art/construction_site_preview.png
    art/construction_site_stages_preview.png

Hierarchy (ready for Godot visibility / animation control):
    ConstructionSite
      SiteBase
        LotPad
        SitePerimeter
        SiteProps
      Materials
        Pile_LumberStack_1
        Pile_LumberStack_2
        Pile_PlywoodSheets
        Pile_PrefabFrames
        Pile_ConcreteBlocks
        Pile_GravelMound
      Crane
        Crane_Base
        Crane_Jib          (rotates around local Z at slewing ring)
          Crane_Trolley    (slides along local X from 2.2m to 11.4m)
            Crane_Cable    (origin at trolley sheave; scale Z to hoist)
            Crane_Hook     (translates along local Z)
              Crane_Payload_Frame  (toggleable lifted wall frame / truss)
      BuildingStages
        Stage1_Foundation
        Stage2_FloorDeck
        Stage3_FirstFloorWalls
        Stage4_UpperFrameAndGables
        Stage5_RoofTrusses
"""

import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BLEND_PATH = ROOT / "art" / "construction_site.blend"
GLB_PATH = ROOT / "assets" / "models" / "construction_site.glb"
HERO_PREVIEW_PATH = ROOT / "art" / "construction_site_preview.png"
STAGES_PREVIEW_PATH = ROOT / "art" / "construction_site_stages_preview.png"


# ---------------------------------------------------------------------------
# Color & material helpers
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
        self.gravel_mound = make_material("GravelMound", "8f8e88", roughness=0.92)
        self.concrete = make_material("ConcreteSlab", "b5b6b0", roughness=0.84)
        self.concrete_dark = make_material("ConcreteBlock", "8d8f8a", roughness=0.88)
        self.lumber_light = make_material("LumberFresh", "e0ba7e", roughness=0.76)
        self.lumber_mid = make_material("LumberBeam", "c99859", roughness=0.78)
        self.lumber_dark = make_material("LumberTreated", "95673b", roughness=0.80)
        self.plywood = make_material("PlywoodSheet", "d5ae6f", roughness=0.78)
        self.crane_gold = make_material("CraneGold", "e3a535", roughness=0.52, metallic=0.15)
        self.crane_gold_lt = make_material("CraneGoldLight", "f3be52", roughness=0.48, metallic=0.10)
        self.crane_green = make_material("CraneGreen", "365950", roughness=0.58, metallic=0.12)
        self.crane_trim = make_material("CraneTrim", "e3dfc6", roughness=0.55)
        self.glass = make_material("CabGlass", "345460", roughness=0.22, metallic=0.10)
        self.iron = make_material("DarkIron", "434b49", roughness=0.55, metallic=0.45)
        self.safety = make_material("SafetyOrange", "d65f35", roughness=0.62)
        self.tarp = make_material("TarpTeal", "467977", roughness=0.78)
        self.sign_white = make_material("SignBoard", "e8e4d8", roughness=0.68)


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
        verts = res["verts"]
        faces = list({f for v in verts for f in v.link_faces})
        self._apply_mat(faces, mat)

    def box_min_max(self, x0, x1, y0, y1, z0, z1, mat):
        self.box(
            ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5),
            (abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)),
            mat,
        )

    def strut(self, a, b, width, mat, depth=None):
        """Low-poly rectangular beam from point a to point b."""
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

    def cylinder(self, a, b, r_bot, r_top, mat, segments=6):
        """Low-poly prism/cylinder from a to b."""
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
        """Octagonal chamfered slab matching Tideways coastal lot pads."""
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

    def mound(self, center, rx, ry, height, mat, sides=8):
        """Low-poly faceted gravel/dirt pile with slightly irregular ridge."""
        cx, cy, cz = self._shift(center)
        base = []
        mid = []
        for i in range(sides):
            ang = 2.0 * math.pi * i / sides
            jitter = 1.0 + 0.10 * math.sin(i * 2.3)
            bx = cx + rx * jitter * math.cos(ang)
            by = cy + ry * jitter * math.sin(ang)
            base.append(self.bm.verts.new((bx, by, cz)))
            mx = cx + rx * 0.52 * math.cos(ang + 0.18)
            my = cy + ry * 0.52 * math.sin(ang + 0.18)
            mz = cz + height * (0.62 + 0.08 * math.cos(i * 1.7))
            mid.append(self.bm.verts.new((mx, my, mz)))
        apex = self.bm.verts.new((cx + rx * 0.08, cy - ry * 0.06, cz + height))
        faces = []
        for i in range(sides):
            j = (i + 1) % sides
            faces.append(self.bm.faces.new((base[i], base[j], mid[j], mid[i])))
            faces.append(self.bm.faces.new((mid[i], mid[j], apex)))
        faces.append(self.bm.faces.new(list(reversed(base))))
        self._apply_mat(faces, mat)

    def finish(self, collection, parent=None, local_location=None):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        for mat in self.materials:
            mesh.materials.append(mat)
        # Keep crisp low-poly flat shading
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
    obj.empty_display_size = 0.5
    collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    obj.location = Vector(location)
    return obj


# ---------------------------------------------------------------------------
# Site layout constants (meters, Blender Z-up, ground Z = 0)
# ---------------------------------------------------------------------------

PAD_TOP = 0.18

# Building footprint centered at (2.2, 1.0): 8.4m (X) x 6.0m (Y)
BLD_CX, BLD_CY = 2.2, 1.0
BLD_W, BLD_D = 8.4, 6.0
BLD_X0, BLD_X1 = BLD_CX - BLD_W * 0.5, BLD_CX + BLD_W * 0.5   # -2.0 .. 6.4
BLD_Y0, BLD_Y1 = BLD_CY - BLD_D * 0.5, BLD_CY + BLD_D * 0.5   # -2.0 .. 4.0

# Crane mast center at (-3.6, 2.2) — reaches both material yard and all of building
CRANE_X, CRANE_Y = -3.6, 2.2
CRANE_SLEW_Z = PAD_TOP + 10.6   # 10.78m mast height


# ---------------------------------------------------------------------------
# 1. Site Base (Lot pad, perimeter fencing, job-site props)
# ---------------------------------------------------------------------------

def build_site_base(pal, col, parent):
    group = make_empty("SiteBase", col, parent)

    # -- LotPad --
    lot = LowPolyPart("LotPad")
    # Main chamfered graded dirt lot: 22m x 16m
    lot.chamfered_pad((0.0, 0.0, PAD_TOP * 0.5), 22.0, 16.0, PAD_TOP, 0.85, pal.dirt)
    # Compacted gravel vehicle apron on front & right (non-overlapping to prevent Z-fighting)
    lot.chamfered_pad((4.2, -5.0, PAD_TOP + 0.015), 11.4, 5.2, 0.03, 0.4, pal.gravel)
    lot.chamfered_pad((8.8, 1.6, PAD_TOP + 0.012), 3.4, 7.8, 0.024, 0.35, pal.gravel)
    # Leveled darker earth excavation bed under building footprint
    lot.chamfered_pad((BLD_CX, BLD_CY, PAD_TOP + 0.014), BLD_W + 1.1, BLD_D + 1.1, 0.028, 0.25, pal.dirt_dark)
    # Compacted gravel staging strip under material piles
    lot.chamfered_pad((-7.0, 0.5, PAD_TOP + 0.012), 5.6, 12.2, 0.024, 0.35, pal.gravel)
    lot.finish(col, group)

    # -- SitePerimeter (fencing with wide driveway opening at front-right for vehicles) --
    fence = LowPolyPart("SitePerimeter")

    def fence_run(p0, p1, panels, skip_start_post=False, skip_end_post=False):
        v0 = Vector((p0[0], p0[1], PAD_TOP))
        v1 = Vector((p1[0], p1[1], PAD_TOP))
        for i in range(panels + 1):
            if i == 0 and skip_start_post:
                continue
            if i == panels and skip_end_post:
                continue
            t = i / panels
            p = v0.lerp(v1, t)
            fence.box((p.x, p.y, PAD_TOP + 0.62), (0.09, 0.09, 1.24), pal.lumber_dark)
        for i in range(panels):
            pa = v0.lerp(v1, i / panels)
            pb = v0.lerp(v1, (i + 1) / panels)
            # Top & bottom horizontal wood rails
            fence.strut((pa.x, pa.y, PAD_TOP + 1.08), (pb.x, pb.y, PAD_TOP + 1.08), 0.05, pal.lumber_mid)
            fence.strut((pa.x, pa.y, PAD_TOP + 0.30), (pb.x, pb.y, PAD_TOP + 0.30), 0.05, pal.lumber_mid)
            # Orange safety barrier band in the middle
            mid = (pa + pb) * 0.5
            seg_len = (pb - pa).length - 0.12
            ang = math.atan2(pb.y - pa.y, pb.x - pa.x)
            fence.box(
                (mid.x, mid.y, PAD_TOP + 0.70),
                (seg_len, 0.03, 0.62),
                pal.safety,
                rot_euler=(0.0, 0.0, ang),
            )

    # Back fence (-10.3..10.3, y=7.4), Left fence (x=-10.3), Right fence (x=10.3, partial)
    fence_run((-10.3, 7.4), (10.3, 7.4), 8)
    fence_run((-10.3, -7.4), (-10.3, 7.4), 6, skip_end_post=True)
    fence_run((10.3, -1.6), (10.3, 7.4), 4, skip_end_post=True)
    # Front-left fence up to driveway entrance
    fence_run((-10.3, -7.4), (-1.2, -7.4), 4, skip_start_post=True)

    # Safety cones marking the open truck/backhoe driveway entrance
    for cx, cy in [(-0.7, -7.2), (9.8, -7.2), (9.8, -2.2), (2.8, -3.3)]:
        fence.box((cx, cy, PAD_TOP + 0.025), (0.34, 0.34, 0.05), pal.iron)
        fence.cylinder((cx, cy, PAD_TOP + 0.05), (cx, cy, PAD_TOP + 0.62), 0.13, 0.035, pal.safety, segments=6)
        fence.cylinder((cx, cy, PAD_TOP + 0.35), (cx, cy, PAD_TOP + 0.47), 0.088, 0.068, pal.sign_white, segments=6)

    # Job-site plan/notice board near the entrance
    sx, sy = -1.7, -6.5
    for dx in (-0.52, 0.52):
        fence.box((sx + dx, sy, PAD_TOP + 0.85), (0.09, 0.09, 1.70), pal.lumber_dark)
    fence.box((sx, sy, PAD_TOP + 1.38), (1.35, 0.07, 0.82), pal.lumber_dark)
    fence.box((sx, sy - 0.03, PAD_TOP + 1.38), (1.22, 0.03, 0.70), pal.sign_white)
    # Small header stripe on sign
    fence.box((sx, sy - 0.05, PAD_TOP + 1.60), (1.16, 0.02, 0.14), pal.crane_green)
    fence.finish(col, group)

    # -- SiteProps (sawhorses, toolbox, batter boards) --
    props = LowPolyPart("SiteProps")

    def sawhorse(cx, cy, yaw=0.0):
        # Simple low-poly carpenter sawhorse
        ca, sa = math.cos(yaw), math.sin(yaw)

        def pt(lx, ly, lz):
            return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, PAD_TOP + lz)

        props.strut(pt(-0.55, 0.0, 0.76), pt(0.55, 0.0, 0.76), 0.09, pal.lumber_mid, 0.07)
        for sx_end in (-0.42, 0.42):
            for sy_leg in (-0.28, 0.28):
                props.strut(pt(sx_end, 0.0, 0.74), pt(sx_end, sy_leg, 0.0), 0.055, pal.lumber_light)

    sawhorse(-2.6, -5.0, yaw=0.18)
    sawhorse(-1.3, -5.2, yaw=0.12)
    # Plank resting across the two sawhorses
    props.strut((-2.9, -4.95, PAD_TOP + 0.82), (-1.0, -5.25, PAD_TOP + 0.82), 0.22, pal.lumber_light, 0.05)

    # Metal job-site gang box / tool chest
    props.box((-3.8, -5.6, PAD_TOP + 0.42), (1.25, 0.65, 0.76), pal.crane_green, rot_euler=(0, 0, 0.08))
    props.box((-3.8, -5.6, PAD_TOP + 0.83), (1.30, 0.69, 0.08), pal.crane_gold, rot_euler=(0, 0, 0.08))

    # Corner survey stakes around the building pad
    for sx_c in (BLD_X0 - 0.45, BLD_X1 + 0.45):
        for sy_c in (BLD_Y0 - 0.45, BLD_Y1 + 0.45):
            props.box((sx_c, sy_c, PAD_TOP + 0.24), (0.06, 0.06, 0.48), pal.lumber_dark)
            props.box((sx_c, sy_c, PAD_TOP + 0.44), (0.07, 0.07, 0.10), pal.safety)

    props.finish(col, group)
    return group


# ---------------------------------------------------------------------------
# 2. Material Piles (individually toggleable so piles can deplete!)
# ---------------------------------------------------------------------------

def build_materials(pal, col, parent):
    group = make_empty("Materials", col, parent)

    # 2a. Stacked framing lumber bundle #1 (2x4 / 2x6 studs)
    p1 = LowPolyPart("Pile_LumberStack_1", origin=(-7.4, 2.4, PAD_TOP))
    # Dunnage sleepers
    for dy in (-1.4, 0.0, 1.4):
        p1.box((-7.4, 2.4 + dy, PAD_TOP + 0.06), (1.55, 0.14, 0.12), pal.lumber_dark)
    # 5 layers of individual timber planks (low-poly grouped rows)
    for layer in range(5):
        z = PAD_TOP + 0.18 + layer * 0.13
        n_boards = 6 if layer < 4 else 4
        for i in range(n_boards):
            bx = -7.4 - (n_boards - 1) * 0.115 + i * 0.23
            mat = pal.lumber_light if (i + layer) % 2 == 0 else pal.lumber_mid
            length = 3.9 - (i % 2) * 0.18
            p1.box((bx, 2.4, z), (0.20, length, 0.11), mat)
    # Orange tie straps around bundle
    for dy in (-1.1, 1.1):
        p1.box((-7.4, 2.4 + dy, PAD_TOP + 0.45), (1.42, 0.06, 0.66), pal.safety)
    p1.finish(col, group)

    # 2b. Stacked heavy timber beams / joists #2
    p2 = LowPolyPart("Pile_LumberStack_2", origin=(-7.6, -2.5, PAD_TOP))
    for dy in (-1.3, 1.3):
        p2.box((-7.6, -2.5 + dy, PAD_TOP + 0.06), (1.35, 0.16, 0.12), pal.lumber_dark)
    for layer in range(3):
        z = PAD_TOP + 0.21 + layer * 0.19
        cols_n = 4 - (layer // 2)
        for i in range(cols_n):
            bx = -7.6 - (cols_n - 1) * 0.15 + i * 0.30
            p2.box((bx, -2.5, z), (0.25, 3.6, 0.17), pal.lumber_mid if layer % 2 == 0 else pal.lumber_light)
    for dy in (-0.95, 0.95):
        p2.box((-7.6, -2.5 + dy, PAD_TOP + 0.39), (1.26, 0.06, 0.56), pal.safety)
    p2.finish(col, group)

    # 2c. Stacked plywood / OSB sheets on pallet + folded teal tarp
    p3 = LowPolyPart("Pile_PlywoodSheets", origin=(-7.0, 5.4, PAD_TOP))
    # Pallet runners & deck
    for dx in (-0.95, 0.0, 0.95):
        p3.box((-7.0 + dx, 5.4, PAD_TOP + 0.06), (0.12, 1.35, 0.12), pal.lumber_dark)
    p3.box((-7.0, 5.4, PAD_TOP + 0.14), (2.45, 1.35, 0.04), pal.lumber_dark)
    # Plywood sheets stack
    for layer in range(8):
        z = PAD_TOP + 0.19 + layer * 0.06
        dx_jit = 0.02 * ((layer % 3) - 1)
        p3.box((-7.0 + dx_jit, 5.4, z), (2.44, 1.24, 0.05), pal.plywood if layer % 2 == 0 else pal.lumber_light)
    # Folded teal tarp draped over one end of the plywood stack
    p3.box((-7.72, 5.4, PAD_TOP + 0.67), (1.08, 1.30, 0.06), pal.tarp)
    p3.box((-8.24, 5.4, PAD_TOP + 0.42), (0.06, 1.30, 0.54), pal.tarp)
    p3.finish(col, group)

    # 2d. Pre-assembled wood wall frames & trusses leaning on an A-frame rack
    #     (Right inside the crane's swing radius at (-5.6, -1.6))
    p4 = LowPolyPart("Pile_PrefabFrames", origin=(-5.2, -1.6, PAD_TOP))
    # A-frame rack base & uprights
    for dy in (-1.2, 1.2):
        p4.box((-5.2, -1.6 + dy, PAD_TOP + 0.06), (1.5, 0.14, 0.12), pal.lumber_dark)
        p4.strut((-5.8, -1.6 + dy, PAD_TOP + 0.12), (-5.2, -1.6 + dy, PAD_TOP + 2.15), 0.10, pal.lumber_dark)
        p4.strut((-4.6, -1.6 + dy, PAD_TOP + 0.12), (-5.2, -1.6 + dy, PAD_TOP + 2.15), 0.10, pal.lumber_dark)
    p4.strut((-5.2, -2.9, PAD_TOP + 2.10), (-5.2, -0.3, PAD_TOP + 2.10), 0.10, pal.lumber_dark)

    # 2 prefab stud wall panels leaning on the +X side of the A-frame
    for idx in range(2):
        tilt = -0.22
        offset_x = -4.85 + idx * 0.18
        # Build panel in local coords, rotated around Y
        cy = -1.6
        w_len = 2.8
        h_pan = 2.15
        # Bottom & top plates
        for hz in (0.14, h_pan):
            px = offset_x + hz * math.sin(tilt)
            pz = PAD_TOP + 0.10 + hz * math.cos(tilt)
            p4.box((px, cy, pz), (0.10, w_len, 0.09), pal.lumber_mid, rot_euler=(0, tilt, 0))
        # Studs
        for s in range(6):
            sy = cy - w_len * 0.5 + 0.06 + s * (w_len - 0.12) / 5.0
            hz = (0.14 + h_pan) * 0.5
            px = offset_x + hz * math.sin(tilt)
            pz = PAD_TOP + 0.10 + hz * math.cos(tilt)
            p4.box((px, sy, pz), (0.09, 0.08, h_pan - 0.16), pal.lumber_light, rot_euler=(0, tilt, 0))

    # 2 prefab triangular roof trusses leaning on the -X side of the A-frame
    for idx in range(2):
        ox = -5.65 - idx * 0.18
        base_z = PAD_TOP + 0.14
        half_span = 1.65
        rise = 1.55
        a = (ox, -1.6 - half_span, base_z)
        b = (ox, -1.6 + half_span, base_z)
        peak = (ox + 0.25, -1.6, base_z + rise)
        mid_b = (ox, -1.6, base_z)
        p4.strut(a, b, 0.09, pal.lumber_light)
        p4.strut(a, peak, 0.09, pal.lumber_light)
        p4.strut(b, peak, 0.09, pal.lumber_light)
        p4.strut(mid_b, peak, 0.08, pal.lumber_mid)
    p4.finish(col, group)

    # 2e. Concrete cinder blocks on pallet (front-left)
    p5 = LowPolyPart("Pile_ConcreteBlocks", origin=(-5.4, -5.2, PAD_TOP))
    p5.box((-5.4, -5.2, PAD_TOP + 0.07), (1.55, 1.35, 0.14), pal.lumber_dark)
    for layer in range(3):
        z = PAD_TOP + 0.26 + layer * 0.24
        for ix in range(3):
            for iy in range(4):
                if layer == 2 and ix == 2 and iy >= 2:
                    continue
                bx = -5.85 + ix * 0.45
                by = -5.65 + iy * 0.30
                mat = pal.concrete if (ix + iy + layer) % 2 == 0 else pal.concrete_dark
                p5.box((bx, by, z), (0.40, 0.25, 0.21), mat)
    p5.finish(col, group)

    # 2f. Gravel mound near the vehicle apron (great spot for a backhoe/dump truck)
    p6 = LowPolyPart("Pile_GravelMound", origin=(7.6, -5.4, PAD_TOP))
    p6.mound((7.6, -5.4, PAD_TOP), 1.85, 1.55, 1.15, pal.gravel_mound, sides=8)
    p6.mound((8.6, -4.5, PAD_TOP), 1.05, 0.95, 0.62, pal.dirt_dark, sides=7)
    p6.finish(col, group)

    return group


# ---------------------------------------------------------------------------
# 3. Articulated Low-Poly Construction Tower Crane
# ---------------------------------------------------------------------------

def build_crane(pal, col, parent):
    """Build a slewing tower crane with clean hierarchical pivots for animation."""
    crane_root = make_empty("Crane", col, parent, location=(CRANE_X, CRANE_Y, PAD_TOP))

    # -- 3a. Crane_Base (concrete ballast + lattice mast tower + slewing ring) --
    # Built in Crane-local coordinates (origin at ground center of mast)
    base = LowPolyPart("Crane_Base", origin=(0.0, 0.0, 0.0))
    # Heavy concrete ballast cross-base
    base.chamfered_pad((0.0, 0.0, 0.24), 2.9, 2.9, 0.48, 0.35, pal.concrete)
    for dx in (-0.85, 0.85):
        for dy in (-0.85, 0.85):
            base.box((dx, dy, 0.68), (0.95, 0.95, 0.42), pal.concrete_dark)
    # Steel base collar
    base.box((0.0, 0.0, 0.98), (1.35, 1.35, 0.22), pal.crane_green)

    # Lattice mast tower: 0.95m square section, 7 bays up to Z = 10.2m
    mast_h0 = 1.05
    mast_h1 = 10.20
    half_m = 0.46
    bays = 7
    bay_h = (mast_h1 - mast_h0) / bays
    # 4 vertical corner chords
    for sx in (-half_m, half_m):
        for sy in (-half_m, half_m):
            base.strut((sx, sy, mast_h0), (sx, sy, mast_h1), 0.095, pal.crane_gold)
    # Horizontal & diagonal lattice bracing on all 4 faces
    for b in range(bays):
        z0 = mast_h0 + b * bay_h
        z1 = z0 + bay_h
        corners = [
            (-half_m, -half_m),
            (half_m, -half_m),
            (half_m, half_m),
            (-half_m, half_m),
        ]
        for i in range(4):
            a = corners[i]
            c = corners[(i + 1) % 4]
            base.strut((a[0], a[1], z1), (c[0], c[1], z1), 0.055, pal.crane_gold)
            # Alternating diagonal
            if (b + i) % 2 == 0:
                base.strut((a[0], a[1], z0), (c[0], c[1], z1), 0.050, pal.crane_gold_lt)
            else:
                base.strut((c[0], c[1], z0), (a[0], a[1], z1), 0.050, pal.crane_gold_lt)

    # Top slewing platform & ring bearing
    base.box((0.0, 0.0, 10.34), (1.28, 1.28, 0.26), pal.crane_green)
    base.cylinder((0.0, 0.0, 10.47), (0.0, 0.0, 10.62), 0.56, 0.56, pal.iron, segments=10)
    base_obj = base.finish(col, crane_root, local_location=(0.0, 0.0, 0.0))

    # -- 3b. Crane_Jib (slews around Z at (0, 0, 10.60) in Crane-local space) --
    jib = LowPolyPart("Crane_Jib", origin=(0.0, 0.0, 0.0))
    # Turntable hub
    jib.box((0.0, 0.0, 0.16), (1.26, 1.26, 0.28), pal.crane_gold)

    # Operator cab cantilevered on the right (-Y) side of the slewing hub
    jib.box((0.35, -1.05, 0.52), (1.55, 0.92, 0.42), pal.crane_gold)
    jib.box((0.40, -1.05, 1.05), (1.46, 0.86, 0.68), pal.glass)
    # Cab corner pillars & trim roof
    for dx in (-0.30, 1.08):
        for dy in (-1.46, -0.64):
            jib.strut((dx, dy, 0.72), (dx, dy, 1.40), 0.055, pal.crane_trim)
    jib.box((0.40, -1.05, 1.44), (1.66, 1.02, 0.10), pal.crane_trim)
    # Cab mount bracket
    jib.box((0.10, -0.60, 0.22), (0.90, 0.40, 0.22), pal.crane_green)

    # Apex / cathead tower rising above the slewing hub
    apex_z = 3.15
    for sx in (-0.42, 0.42):
        for sy in (-0.42, 0.42):
            jib.strut((sx, sy, 0.30), (0.0, 0.0, apex_z), 0.08, pal.crane_gold)
    jib.box((0.0, 0.0, apex_z + 0.06), (0.36, 0.36, 0.26), pal.safety)

    # Main horizontal triangular lattice jib (+X from 0.0 to 12.2m)
    jib_len = 12.2
    jib_bays = 10
    jib_w = 0.40   # half-width of bottom chords
    jib_h = 0.85   # height of top apex chord
    jib_z0 = 0.32
    jib_z1 = jib_z0 + jib_h

    # 3 longitudinal chords (2 bottom, 1 top)
    jib.strut((-0.4, -jib_w, jib_z0), (jib_len, -jib_w, jib_z0), 0.075, pal.crane_gold)
    jib.strut((-0.4, jib_w, jib_z0), (jib_len, jib_w, jib_z0), 0.075, pal.crane_gold)
    jib.strut((0.0, 0.0, jib_z1), (jib_len - 0.5, 0.0, jib_z1), 0.080, pal.crane_gold)
    # Nose tip cap (safety orange + white stripe like Tideways barge crane)
    jib.strut((jib_len - 0.5, 0.0, jib_z1), (jib_len, -jib_w, jib_z0), 0.07, pal.safety)
    jib.strut((jib_len - 0.5, 0.0, jib_z1), (jib_len, jib_w, jib_z0), 0.07, pal.safety)
    jib.box((jib_len, 0.0, jib_z0), (0.16, jib_w * 2.1, 0.16), pal.safety)

    dx_bay = (jib_len - 0.5) / jib_bays
    for b in range(jib_bays):
        x0 = b * dx_bay
        x1 = (b + 1) * dx_bay
        xm = (x0 + x1) * 0.5
        mat_br = pal.safety if b == jib_bays - 1 else (pal.crane_trim if b == jib_bays - 2 else pal.crane_gold_lt)
        # Bottom cross tie
        jib.strut((x1, -jib_w, jib_z0), (x1, jib_w, jib_z0), 0.045, mat_br)
        # Side triangular web diagonals
        for side in (-1, 1):
            y_b = side * jib_w
            jib.strut((x0, y_b, jib_z0), (xm, 0.0, jib_z1), 0.045, mat_br)
            jib.strut((xm, 0.0, jib_z1), (x1, y_b, jib_z0), 0.045, mat_br)

    # Counter-jib (-X from 0.0 to -4.6m) with concrete counterweights
    cj_len = -4.6
    for sy in (-0.42, 0.42):
        jib.strut((0.0, sy, jib_z0), (cj_len, sy, jib_z0), 0.085, pal.crane_gold)
    for cx in (-1.2, -2.4, -3.6, -4.55):
        jib.strut((cx, -0.42, jib_z0), (cx, 0.42, jib_z0), 0.06, pal.crane_gold)
    # Winch motor housing on counter-jib
    jib.box((-1.5, 0.0, jib_z0 + 0.34), (1.15, 0.78, 0.58), pal.crane_green)
    # 3 stacked concrete counterweight slabs at tail
    for i in range(3):
        jib.box((-3.25 - i * 0.42, 0.0, jib_z0 + 0.52), (0.34, 1.32, 1.04), pal.concrete if i % 2 == 0 else pal.concrete_dark)

    # Pendant tension cables from apex to main jib & counter-jib
    jib.strut((0.0, 0.0, apex_z), (6.5, 0.0, jib_z1), 0.036, pal.iron)
    jib.strut((0.0, 0.0, apex_z), (11.2, 0.0, jib_z1), 0.036, pal.iron)
    jib.strut((0.0, 0.0, apex_z), (-4.4, -0.35, jib_z0 + 0.08), 0.036, pal.iron)
    jib.strut((0.0, 0.0, apex_z), (-4.4, 0.35, jib_z0 + 0.08), 0.036, pal.iron)

    jib_obj = jib.finish(col, crane_root, local_location=(0.0, 0.0, 10.60))

    # -- 3c. Crane_Trolley (parented to Crane_Jib, slides along X) --
    trolley = LowPolyPart("Crane_Trolley", origin=(0.0, 0.0, 0.0))
    trolley.box((0.0, 0.0, 0.0), (0.72, 0.96, 0.22), pal.crane_green)
    trolley.box((0.0, 0.0, -0.14), (0.48, 0.42, 0.14), pal.iron)
    trolley_obj = trolley.finish(col, jib_obj, local_location=(6.8, 0.0, 0.22))

    # -- 3d. Crane_Cable (origin at trolley sheave, length = 1.0m unit so scale.z = drop distance!) --
    cable = LowPolyPart("Crane_Cable", origin=(0.0, 0.0, 0.0))
    # Twin hoist cables descending 1.0m along -Z
    for dy in (-0.10, 0.10):
        cable.cylinder((0.0, dy, 0.0), (0.0, dy, -1.0), 0.022, 0.022, pal.iron, segments=5)
    cable_obj = cable.finish(col, trolley_obj, local_location=(0.0, 0.0, -0.16))
    cable_obj.scale = (1.0, 1.0, 4.4)

    # -- 3e. Crane_Hook (parented to Crane_Trolley, Z = -0.16 - drop) --
    hook = LowPolyPart("Crane_Hook", origin=(0.0, 0.0, 0.0))
    # Yellow & dark iron sheave block
    hook.box((0.0, 0.0, -0.18), (0.34, 0.38, 0.36), pal.crane_gold)
    hook.box((0.0, 0.0, -0.18), (0.36, 0.40, 0.10), pal.iron)
    # Hook shank & J-hook
    hook.cylinder((0.0, 0.0, -0.36), (0.0, 0.0, -0.56), 0.045, 0.045, pal.iron, segments=6)
    hook.strut((0.0, 0.0, -0.56), (0.14, 0.0, -0.72), 0.065, pal.iron)
    hook.strut((0.14, 0.0, -0.72), (-0.02, 0.0, -0.86), 0.065, pal.iron)
    hook.strut((-0.02, 0.0, -0.86), (-0.14, 0.0, -0.76), 0.055, pal.iron)
    hook_obj = hook.finish(col, trolley_obj, local_location=(0.0, 0.0, -4.56))

    # -- 3f. Crane_Payload_Frame (a framed wood wall section hanging in a sling) --
    payload = LowPolyPart("Crane_Payload_Frame", origin=(0.0, 0.0, 0.0))
    # Spreader bar + 2 orange lifting slings from hook at (0,0,-0.80)
    payload.strut((-0.95, 0.0, -1.45), (0.95, 0.0, -1.45), 0.07, pal.crane_gold)
    payload.strut((0.0, 0.0, -0.80), (-0.90, 0.0, -1.45), 0.032, pal.safety)
    payload.strut((0.0, 0.0, -0.80), (0.90, 0.0, -1.45), 0.032, pal.safety)
    payload.strut((-0.90, 0.0, -1.45), (-1.15, 0.0, -1.95), 0.030, pal.safety)
    payload.strut((0.90, 0.0, -1.45), (1.15, 0.0, -1.95), 0.030, pal.safety)

    # Wood-framed wall panel (2.8m wide x 2.2m tall, with window opening!)
    fw, fh = 2.8, 2.2
    top_z = -1.95
    bot_z = top_z - fh
    # Top double plate & bottom sole plate
    payload.box((0.0, 0.0, top_z), (fw, 0.13, 0.11), pal.lumber_mid)
    payload.box((0.0, 0.0, bot_z), (fw, 0.13, 0.09), pal.lumber_mid)
    # Outer & inner studs
    for sx in (-1.35, -0.90, -0.55, 0.55, 0.90, 1.35):
        payload.box((sx, 0.0, (top_z + bot_z) * 0.5), (0.09, 0.12, fh - 0.10), pal.lumber_light)
    # Window header & sill inside the lifted frame
    payload.box((0.0, 0.0, top_z - 0.36), (1.10, 0.13, 0.14), pal.lumber_mid)
    payload.box((0.0, 0.0, bot_z + 0.72), (1.10, 0.12, 0.09), pal.lumber_mid)
    # Cripple studs above header / below sill
    for sx in (-0.22, 0.22):
        payload.box((sx, 0.0, top_z - 0.18), (0.08, 0.11, 0.24), pal.lumber_light)
        payload.box((sx, 0.0, bot_z + 0.36), (0.08, 0.11, 0.64), pal.lumber_light)
    # Diagonal temporary brace across frame
    payload.strut((-1.32, 0.08, bot_z + 0.08), (-0.56, 0.08, top_z - 0.08), 0.055, pal.lumber_dark)
    payload_obj = payload.finish(col, hook_obj, local_location=(0.0, 0.0, 0.0))

    # Default hero pose: jib angled toward the building (-16 deg)
    jib_obj.rotation_euler.z = math.radians(-16.0)

    return {
        "root": crane_root,
        "base": base_obj,
        "jib": jib_obj,
        "trolley": trolley_obj,
        "cable": cable_obj,
        "hook": hook_obj,
        "payload": payload_obj,
    }


# ---------------------------------------------------------------------------
# 4. Staged Wood-Framed Building (Stage 1 -> Stage 5)
# ---------------------------------------------------------------------------

def build_building_stages(pal, col, parent):
    group = make_empty("BuildingStages", col, parent)

    z_pad = PAD_TOP
    z_fnd_top = z_pad + 0.42          # 0.60m top of concrete stem/slab
    z_deck_top = z_fnd_top + 0.28     # 0.88m top of plywood subfloor
    wall_h = 2.65
    z_wall_top = z_deck_top + wall_h  # 3.53m top of 1st-floor double top plate
    z_upper_deck = z_wall_top + 0.24  # 3.77m top of 2nd-floor/attic joists
    roof_rise = 2.35
    z_ridge = z_upper_deck + roof_rise  # 6.12m roof peak

    # -- Stage 1: Concrete Foundation & Form Boards --
    s1 = LowPolyPart("Stage1_Foundation", origin=(BLD_CX, BLD_CY, z_pad))
    # Stepped concrete footing
    s1.box((BLD_CX, BLD_CY, z_pad + 0.10), (BLD_W + 0.36, BLD_D + 0.36, 0.20), pal.concrete_dark)
    # Main concrete slab / stem wall
    s1.box((BLD_CX, BLD_CY, z_pad + 0.29), (BLD_W, BLD_D, 0.26), pal.concrete)
    # Front entry concrete porch footing pad
    s1.box((BLD_CX - 1.1, BLD_Y0 - 0.65, z_pad + 0.18), (2.2, 1.3, 0.36), pal.concrete)
    # Wooden form boards along two edges for authentic construction detail
    s1.box((BLD_CX, BLD_Y0 - 0.05, z_pad + 0.24), (BLD_W + 0.16, 0.06, 0.24), pal.lumber_dark)
    s1.box((BLD_X1 + 0.05, BLD_CY, z_pad + 0.24), (0.06, BLD_D + 0.16, 0.24), pal.lumber_dark)
    s1_obj = s1.finish(col, group)

    # -- Stage 2: Floor Joists & Plywood Subfloor Deck --
    s2 = LowPolyPart("Stage2_FloorDeck", origin=(BLD_CX, BLD_CY, z_fnd_top))
    # Treated sill plates around perimeter
    s2.box((BLD_CX, BLD_Y0 + 0.09, z_fnd_top + 0.04), (BLD_W, 0.18, 0.08), pal.lumber_dark)
    s2.box((BLD_CX, BLD_Y1 - 0.09, z_fnd_top + 0.04), (BLD_W, 0.18, 0.08), pal.lumber_dark)
    s2.box((BLD_X0 + 0.09, BLD_CY, z_fnd_top + 0.04), (0.18, BLD_D - 0.36, 0.08), pal.lumber_dark)
    s2.box((BLD_X1 - 0.09, BLD_CY, z_fnd_top + 0.04), (0.18, BLD_D - 0.36, 0.08), pal.lumber_dark)
    # Rim joists & exposed floor joists
    joist_z = z_fnd_top + 0.16
    s2.box((BLD_CX, BLD_Y0 + 0.05, joist_z), (BLD_W, 0.08, 0.18), pal.lumber_mid)
    s2.box((BLD_CX, BLD_Y1 - 0.05, joist_z), (BLD_W, 0.08, 0.18), pal.lumber_mid)
    for i in range(13):
        jx = BLD_X0 + 0.06 + i * (BLD_W - 0.12) / 12.0
        s2.box((jx, BLD_CY, joist_z), (0.07, BLD_D - 0.16, 0.17), pal.lumber_light)
    # Plywood subfloor deck panels (slightly staggered grid seams)
    for ix in range(4):
        for iy in range(3):
            pw = (BLD_W - 0.08) / 4.0
            pd = (BLD_D - 0.08) / 3.0
            px = BLD_X0 + 0.04 + (ix + 0.5) * pw
            py = BLD_Y0 + 0.04 + (iy + 0.5) * pd
            mat = pal.plywood if (ix + iy) % 2 == 0 else pal.lumber_light
            s2.box((px, py, z_deck_top - 0.025), (pw - 0.03, pd - 0.03, 0.05), mat)
    s2_obj = s2.finish(col, group)

    # -- Stage 3: First-Floor Wood Stud Walls (with framed door & window openings) --
    s3 = LowPolyPart("Stage3_FirstFloorWalls", origin=(BLD_CX, BLD_CY, z_deck_top))

    def framed_wall(x0, y0, x1, y1, z_bot, height, openings, thickness=0.14):
        """Build a real stud-framed wall between (x0,y0) and (x1,y1).
        openings: list of (u_start, u_end, sill_z_rel, head_z_rel) in meters along wall.
        """
        v0 = Vector((x0, y0, 0.0))
        v1 = Vector((x1, y1, 0.0))
        dv = v1 - v0
        length = dv.length
        dir_v = dv / length
        ang = math.atan2(dir_v.y, dir_v.x)

        def wbox(u_mid, u_len, z_mid, z_len, mat, thick=thickness):
            p = v0 + dir_v * u_mid
            s3.box((p.x, p.y, z_mid), (u_len, thick, z_len), mat, rot_euler=(0.0, 0.0, ang))

        # Sole plate (skip door openings where sill_z_rel == 0)
        plate_h = 0.07
        door_spans = sorted((a, b) for a, b, sz, _ in openings if sz <= 0.05)
        cur = 0.0
        for a, b in door_spans:
            if a > cur + 0.05:
                wbox((cur + a) * 0.5, a - cur, z_bot + plate_h * 0.5, plate_h, pal.lumber_mid)
            cur = b
        if cur < length - 0.05:
            wbox((cur + length) * 0.5, length - cur, z_bot + plate_h * 0.5, plate_h, pal.lumber_mid)

        # Double top plate
        wbox(length * 0.5, length, z_bot + height - 0.06, 0.12, pal.lumber_mid)

        # Vertical studs on ~0.65m centers, skipping openings
        stud_w = 0.075
        n_studs = max(2, int(round(length / 0.65)))
        stud_positions = [i * length / n_studs for i in range(n_studs + 1)]
        # Add king/jack studs at each opening edge
        for a, b, sz, hz in openings:
            stud_positions.extend([a, b])
        stud_positions = sorted(set(round(u, 3) for u in stud_positions))

        z_stud_bot = z_bot + plate_h
        z_stud_top = z_bot + height - 0.12

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
                # Cripple below window sill
                if sz > 0.12:
                    c_top = z_bot + sz - 0.04
                    if c_top > z_stud_bot + 0.06:
                        wbox(u, stud_w, (z_stud_bot + c_top) * 0.5, c_top - z_stud_bot, pal.lumber_light)
                # Cripple above header
                c_bot = z_bot + hz + 0.16
                if z_stud_top > c_bot + 0.05:
                    wbox(u, stud_w, (c_bot + z_stud_top) * 0.5, z_stud_top - c_bot, pal.lumber_light)

        # Headers & window sills (slightly inset in thickness to avoid coplanar overlap with king studs)
        for a, b, sz, hz in openings:
            span = b - a
            mid = (a + b) * 0.5
            wbox(mid, span + 0.04, z_bot + hz + 0.08, 0.16, pal.lumber_mid, thick=thickness - 0.008)
            if sz > 0.10:
                wbox(mid, span - 0.02, z_bot + sz, 0.075, pal.lumber_mid, thick=thickness - 0.008)

    # Front wall (Y = BLD_Y0, X from BLD_X0 to BLD_X1): front door + 2 windows
    framed_wall(
        BLD_X0 + 0.07, BLD_Y0 + 0.07, BLD_X1 - 0.07, BLD_Y0 + 0.07,
        z_deck_top, wall_h,
        openings=[
            (2.4, 3.55, 0.0, 2.10),     # Front entry door
            (0.7, 1.85, 0.88, 2.08),    # Left window
            (4.7, 6.25, 0.88, 2.08),    # Right double window
            (6.8, 7.65, 0.88, 2.08),    # Far right window
        ],
    )
    # Back wall (Y = BLD_Y1)
    framed_wall(
        BLD_X0 + 0.07, BLD_Y1 - 0.07, BLD_X1 - 0.07, BLD_Y1 - 0.07,
        z_deck_top, wall_h,
        openings=[
            (1.1, 2.4, 0.88, 2.08),
            (3.6, 4.9, 0.88, 2.08),
            (6.0, 7.2, 0.0, 2.10),      # Back patio door
        ],
    )
    # Left wall (X = BLD_X0)
    framed_wall(
        BLD_X0 + 0.07, BLD_Y0 + 0.14, BLD_X0 + 0.07, BLD_Y1 - 0.14,
        z_deck_top, wall_h,
        openings=[(1.1, 2.3, 0.88, 2.08), (3.4, 4.6, 0.88, 2.08)],
    )
    # Right wall (X = BLD_X1)
    framed_wall(
        BLD_X1 - 0.07, BLD_Y0 + 0.14, BLD_X1 - 0.07, BLD_Y1 - 0.14,
        z_deck_top, wall_h,
        openings=[(1.2, 2.5, 0.88, 2.08), (3.5, 4.6, 0.88, 2.08)],
    )
    # Interior central load-bearing partition wall with doorway
    framed_wall(
        BLD_CX - 0.2, BLD_Y0 + 0.18, BLD_CX - 0.2, BLD_Y1 - 0.18,
        z_deck_top, wall_h,
        openings=[(2.0, 3.3, 0.0, 2.10)],
        thickness=0.11,
    )

    # Diagonal corner wind-bracing struts
    s3.strut((BLD_X0 + 0.14, BLD_Y0 + 0.02, z_deck_top + 0.12), (BLD_X0 + 1.5, BLD_Y0 + 0.02, z_wall_top - 0.16), 0.055, pal.lumber_dark)
    s3.strut((BLD_X1 - 0.02, BLD_Y0 + 0.20, z_deck_top + 0.12), (BLD_X1 - 0.02, BLD_Y0 + 1.6, z_wall_top - 0.16), 0.055, pal.lumber_dark)

    # Front porch wood posts & header beam
    for px in (BLD_CX - 2.05, BLD_CX - 0.15):
        s3.box((px, BLD_Y0 - 1.15, z_pad + 0.36 + 1.35), (0.14, 0.14, 2.70), pal.lumber_mid)
    s3.box((BLD_CX - 1.10, BLD_Y0 - 1.15, z_wall_top - 0.08), (2.20, 0.16, 0.18), pal.lumber_mid)

    s3_obj = s3.finish(col, group)

    # -- Stage 4: Ceiling Joists, Rim Band & Gable End Stud Framing --
    s4 = LowPolyPart("Stage4_UpperFrameAndGables", origin=(BLD_CX, BLD_CY, z_wall_top))
    # Perimeter rim band
    band_z = z_wall_top + 0.12
    s4.box((BLD_CX, BLD_Y0 + 0.06, band_z), (BLD_W, 0.10, 0.22), pal.lumber_mid)
    s4.box((BLD_CX, BLD_Y1 - 0.06, band_z), (BLD_W, 0.10, 0.22), pal.lumber_mid)
    s4.box((BLD_X0 + 0.06, BLD_CY, band_z), (0.10, BLD_D - 0.20, 0.22), pal.lumber_mid)
    s4.box((BLD_X1 - 0.06, BLD_CY, band_z), (0.10, BLD_D - 0.20, 0.22), pal.lumber_mid)
    # Ceiling joists spanning Y across the building
    for i in range(11):
        jx = BLD_X0 + 0.35 + i * (BLD_W - 0.70) / 10.0
        s4.box((jx, BLD_CY, band_z), (0.075, BLD_D - 0.18, 0.20), pal.lumber_light)

    # Gable end triangles (left X=BLD_X0 and right X=BLD_X1) with vertical gable studs
    half_d = BLD_D * 0.5
    for gx in (BLD_X0 + 0.07, BLD_X1 - 0.07):
        # End rafters
        s4.strut((gx, BLD_Y0, z_upper_deck), (gx, BLD_CY, z_ridge), 0.11, pal.lumber_mid)
        s4.strut((gx, BLD_Y1, z_upper_deck), (gx, BLD_CY, z_ridge), 0.11, pal.lumber_mid)
        # Vertical gable studs rising to meet the rafters
        for k in range(-3, 4):
            gy = BLD_CY + k * 0.72
            frac = 1.0 - abs(gy - BLD_CY) / half_d
            h_g = roof_rise * frac - 0.06
            if h_g > 0.18:
                s4.box((gx, gy, z_upper_deck + h_g * 0.5), (0.09, 0.08, h_g), pal.lumber_light)
        # Small attic louver / window framing in gable peak
        s4.box((gx, BLD_CY, z_upper_deck + 1.05), (0.10, 0.85, 0.08), pal.lumber_mid)
        s4.box((gx, BLD_CY, z_upper_deck + 1.72), (0.10, 0.85, 0.09), pal.lumber_mid)

    # Ridge beam running the full length + overhang
    s4.box((BLD_CX, BLD_CY, z_ridge), (BLD_W + 0.70, 0.11, 0.20), pal.lumber_mid)
    s4_obj = s4.finish(col, group)

    # -- Stage 5: Roof Trusses, Overhangs, Purlins & Starter Sheathing --
    s5 = LowPolyPart("Stage5_RoofTrusses", origin=(BLD_CX, BLD_CY, z_upper_deck))
    overhang_y = 0.48
    eave_z = z_upper_deck - overhang_y * (roof_rise / half_d)

    # 9 interior pitched roof trusses with king posts & diagonal web struts
    n_trusses = 9
    for i in range(n_trusses):
        tx = BLD_X0 + 0.72 + i * (BLD_W - 1.44) / (n_trusses - 1)
        p_front = (tx, BLD_Y0 - overhang_y, eave_z)
        p_back = (tx, BLD_Y1 + overhang_y, eave_z)
        p_peak = (tx, BLD_CY, z_ridge)
        p_mid = (tx, BLD_CY, z_upper_deck)
        # Top chords (rafters)
        s5.strut(p_front, p_peak, 0.09, pal.lumber_light)
        s5.strut(p_back, p_peak, 0.09, pal.lumber_light)
        # King post
        s5.strut(p_mid, p_peak, 0.08, pal.lumber_mid)
        # Web diagonals
        s5.strut(p_mid, (tx, BLD_CY - half_d * 0.5, z_upper_deck + roof_rise * 0.5), 0.065, pal.lumber_light)
        s5.strut(p_mid, (tx, BLD_CY + half_d * 0.5, z_upper_deck + roof_rise * 0.5), 0.065, pal.lumber_light)

    # Fascia boards & roof purlins along both slopes
    slope_len = math.hypot(half_d + overhang_y, z_ridge - eave_z)
    pitch = math.atan2(z_ridge - eave_z, half_d + overhang_y)
    for side in (-1, 1):
        # Eave fascia
        ey = BLD_CY + side * (half_d + overhang_y)
        s5.box((BLD_CX, ey, eave_z - 0.03), (BLD_W + 0.70, 0.06, 0.16), pal.lumber_mid)
        # 3 longitudinal purlins / roof battens per slope
        for frac in (0.25, 0.55, 0.82):
            py = BLD_CY + side * (half_d + overhang_y) * frac
            pz = z_ridge - (z_ridge - eave_z) * frac + 0.06
            s5.box(
                (BLD_CX, py, pz),
                (BLD_W + 0.65, 0.08, 0.05),
                pal.lumber_light,
                rot_euler=(-side * pitch, 0.0, 0.0),
            )

    # Clean open wood framing: skip solid roof sheathing so the truss structure reads crisply.

    # Small framed front porch gable roof
    px0, px1 = BLD_CX - 2.15, BLD_CX - 0.05
    p_cx = (px0 + px1) * 0.5
    p_peak_z = z_wall_top + 0.95
    for py in (BLD_Y0 - 1.25, BLD_Y0 - 0.65, BLD_Y0 - 0.05):
        s5.strut((px0, py, z_wall_top - 0.05), (p_cx, py, p_peak_z), 0.08, pal.lumber_light)
        s5.strut((px1, py, z_wall_top - 0.05), (p_cx, py, p_peak_z), 0.08, pal.lumber_light)
    s5.strut((p_cx, BLD_Y0 - 1.32, p_peak_z), (p_cx, BLD_Y0 + 0.15, p_peak_z), 0.09, pal.lumber_mid)

    s5_obj = s5.finish(col, group)

    return [s1_obj, s2_obj, s3_obj, s4_obj, s5_obj]


# ---------------------------------------------------------------------------
# Studio & Preview Rendering
# ---------------------------------------------------------------------------

def setup_studio(scene):
    studio = bpy.data.collections.new("PreviewStudio")
    scene.collection.children.link(studio)

    # Backdrop ground plane
    bpy.ops.mesh.primitive_plane_add(size=180, location=(0.0, 0.0, -0.02))
    floor = bpy.context.object
    floor.name = "StudioFloor"
    fmat = make_material("BackdropFloor", "d4dbd6", roughness=0.95)
    floor.data.materials.append(fmat)

    # Soft daylight world
    world = bpy.data.worlds.new("Daylight")
    if not world.node_tree:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.78, 0.84, 0.91, 1.0)
    bg.inputs[1].default_value = 0.72
    scene.world = world

    # Warm key sun/area light
    bpy.ops.object.light_add(type="AREA", location=(-16.0, -22.0, 30.0))
    key = bpy.context.object
    key.name = "KeyLight"
    key.rotation_euler = (Vector((0, 0, 2)) - key.location).to_track_quat("-Z", "Y").to_euler()
    key.data.energy = 24000
    key.data.shape = "DISK"
    key.data.size = 14.0
    key.data.color = (1.0, 0.97, 0.92)

    # Cool fill light
    bpy.ops.object.light_add(type="AREA", location=(24.0, 16.0, 18.0))
    fill = bpy.context.object
    fill.name = "FillLight"
    fill.rotation_euler = (Vector((0, 0, 2)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    fill.data.energy = 6000
    fill.data.shape = "DISK"
    fill.data.size = 16.0
    fill.data.color = (0.85, 0.92, 1.0)

    # Orthographic three-quarter camera matching Tideways previews
    target = Vector((0.2, 0.0, 4.3))
    bpy.ops.object.camera_add(location=target + Vector((-24.0, -30.0, 22.0)))
    cam = bpy.context.object
    cam.name = "PreviewCamera"
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 29.0
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


def render_stages_grid(scene, stages, materials_group, crane):
    """Render 4 progression stages and stitch them into a 2x2 preview PNG."""
    import tempfile

    piles = {c.name: c for c in materials_group.children}
    configs = [
        # Stage 0: Materials delivered, cleared lot, crane swinging over prefab frames
        {
            "stages": [],
            "hidden_piles": [],
            "jib_deg": -125.0,
            "trolley_x": 4.2,
            "drop": 6.2,
            "payload": False,
        },
        # Stage 1-2: Foundation poured & floor deck built, crane lifting a wall frame
        {
            "stages": [0, 1],
            "hidden_piles": ["Pile_ConcreteBlocks"],
            "jib_deg": -62.0,
            "trolley_x": 5.8,
            "drop": 4.2,
            "payload": True,
        },
        # Stage 3: First-floor stud walls up, crane swinging frame clearly above walls
        {
            "stages": [0, 1, 2],
            "hidden_piles": ["Pile_ConcreteBlocks", "Pile_LumberStack_1"],
            "jib_deg": -26.0,
            "trolley_x": 6.2,
            "drop": 2.4,
            "payload": True,
        },
        # Stage 5: Completed wood-framed building with roof trusses
        {
            "stages": [0, 1, 2, 3, 4],
            "hidden_piles": ["Pile_ConcreteBlocks", "Pile_LumberStack_1", "Pile_PrefabFrames"],
            "jib_deg": 18.0,
            "trolley_x": 7.6,
            "drop": 2.8,
            "payload": False,
        },
    ]

    scene.render.resolution_x = 700
    scene.render.resolution_y = 520
    scene.cycles.samples = 16

    tile_paths = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, cfg in enumerate(configs):
            for i, st in enumerate(stages):
                set_hidden(st, i not in cfg["stages"])
            for pname, pobj in piles.items():
                set_hidden(pobj, pname in cfg["hidden_piles"])
            crane["jib"].rotation_euler.z = math.radians(cfg["jib_deg"])
            crane["trolley"].location.x = cfg["trolley_x"]
            crane["cable"].scale.z = cfg["drop"]
            crane["hook"].location.z = -0.16 - cfg["drop"]
            set_hidden(crane["payload"], not cfg["payload"])

            out_path = Path(tmpdir) / f"stage_{idx}.png"
            scene.render.filepath = str(out_path)
            bpy.ops.render.render(write_still=True)
            tile_paths.append(out_path)

        # Stitch 2x2 using Blender's built-in image API (no PIL dependency needed)
        w, h = 700, 520
        grid = bpy.data.images.new("StagesGrid", width=w * 2, height=h * 2, alpha=True)
        pixels = [0.0] * (w * 2 * h * 2 * 4)
        # Placements: (col, row_from_bottom) -> 0: top-left, 1: top-right, 2: bot-left, 3: bot-right
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

    # Restore full visibility and hero pose (frame suspended cleanly above the lot/roof)
    for st in stages:
        set_hidden(st, False)
    for pobj in piles.values():
        set_hidden(pobj, False)
    crane["jib"].rotation_euler.z = math.radians(-38.0)
    crane["trolley"].location.x = 5.4
    crane["cable"].scale.z = 1.8
    crane["hook"].location.z = -0.16 - 1.8
    set_hidden(crane["payload"], False)


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    pal = Palette()

    asset_col = bpy.data.collections.new("ConstructionSite")
    scene.collection.children.link(asset_col)

    root = make_empty("ConstructionSite", asset_col)
    build_site_base(pal, asset_col, root)
    materials_group = build_materials(pal, asset_col, root)
    crane = build_crane(pal, asset_col, root)
    stages = build_building_stages(pal, asset_col, root)

    # Set hero pose for GLB export (all stages & piles visible; crane holding a frame cleanly in mid-air)
    crane["jib"].rotation_euler.z = math.radians(-38.0)
    crane["trolley"].location.x = 5.4
    crane["cable"].scale.z = 1.8
    crane["hook"].location.z = -0.16 - 1.8

    # Print triangle stats
    total_tris = 0
    for obj in asset_col.objects:
        if obj.type == "MESH":
            tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
            total_tris += tris
            print(f"  {obj.name:28s} {tris:5d} tris")
    print(f"TOTAL: {total_tris} tris")

    # Export clean GLB (only ConstructionSite collection, before adding studio)
    GLB_PATH.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in asset_col.objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(GLB_PATH),
        export_format="GLB",
        use_selection=True,
    )

    # Add studio for preview renders & save .blend
    studio = setup_studio(scene)

    # Render hero preview (1200x860)
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 860
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 24
    scene.render.filepath = str(HERO_PREVIEW_PATH)
    bpy.ops.render.render(write_still=True)

    # Render 2x2 progression grid
    render_stages_grid(scene, stages, materials_group, crane)

    # Hide studio objects in viewport so opening .blend shows the clean model
    for obj in studio.objects:
        obj.hide_viewport = True

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), compress=True)
    print(f"Saved: {BLEND_PATH}")
    print(f"Exported: {GLB_PATH}")
    print(f"Previews: {HERO_PREVIEW_PATH}, {STAGES_PREVIEW_PATH}")


if __name__ == "__main__":
    build()
