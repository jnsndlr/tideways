# Builds an ultra-low-poly (< 450 tris) stylized well-dressed woman traveler with hair bun,
# gold square earrings, navy blazer, cream collared blouse, wide-leg navy trousers, dark low-heeled
# pumps, beige tote purse with brown leather strap, and rolling dark-grey suitcase in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_traveler.py)
# Saves art/person_traveler.blend, exports assets/models/person_traveler.glb (rigged + Walk & Idle cycles),
# renders art/person_traveler_preview.png, art/person_traveler_walk_preview.png, art/person_traveler_idle_preview.png,
# and outputs rendered videos art/person_traveler_walk.mp4 and art/person_traveler_idle.mp4.
#
# Strict triangle budget: < 450 triangles.
# Game frame: +Z forward, +Y up, +X left, feet & suitcase wheels on ground at y = 0, ~1.70 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import subprocess
import sys
import tempfile
import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_traveler.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_traveler.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_traveler_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_traveler_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_traveler_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_traveler_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_traveler_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN           = col_srgb(0.87, 0.65, 0.46)
SKIN_SHADE     = col_srgb(0.75, 0.53, 0.35)
EYE            = col_srgb(0.11, 0.10, 0.11)

HAIR           = col_srgb(0.35, 0.26, 0.22)
HAIR_SHADE     = col_srgb(0.26, 0.19, 0.16)

GOLD           = col_srgb(0.96, 0.79, 0.30)
GOLD_SHADE     = col_srgb(0.76, 0.56, 0.16)

BLOUSE         = col_srgb(0.96, 0.93, 0.87)
BLOUSE_SHADE   = col_srgb(0.87, 0.82, 0.75)

BLAZER         = col_srgb(0.30, 0.35, 0.45)
BLAZER_SHADE   = col_srgb(0.22, 0.26, 0.35)
BLAZER_LAPEL   = col_srgb(0.35, 0.40, 0.51)

PANTS          = col_srgb(0.27, 0.31, 0.41)
PANTS_SHADE    = col_srgb(0.19, 0.22, 0.31)

SHOE           = col_srgb(0.23, 0.22, 0.24)
SHOE_SHADE     = col_srgb(0.14, 0.13, 0.15)

PURSE          = col_srgb(0.92, 0.86, 0.77)
PURSE_SHADE    = col_srgb(0.81, 0.74, 0.64)
PURSE_POCKET   = col_srgb(0.87, 0.80, 0.70)
PURSE_STRAP    = col_srgb(0.58, 0.42, 0.30)

CASE           = col_srgb(0.44, 0.44, 0.47)
CASE_SHADE     = col_srgb(0.34, 0.34, 0.37)
CASE_RIB       = col_srgb(0.52, 0.52, 0.55)
CASE_HANDLE    = col_srgb(0.20, 0.20, 0.22)
CASE_WHEEL     = col_srgb(0.16, 0.16, 0.18)

# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_SHADE],
    "top": [BLAZER, BLAZER_SHADE, BLAZER_LAPEL],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [PURSE, PURSE_SHADE, PURSE_POCKET],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared structural anchors so right hand and rolling suitcase handle align seamlessly
ROOT_Y      = 0.585
TORSO_Y     = 0.650
SHOULDER_Y  = 1.074
SHOULDER_Z  = 0.004
SHOULDER_X  = 0.174

HAND_R_POS  = V(-0.318, 0.568, -0.228)
WHEEL_R     = 0.044
CASE_X      = HAND_R_POS.x
WHEEL_Z     = -0.502
CASE_AXIS_Y = HAND_R_POS.y - WHEEL_R
CASE_AXIS_Z = HAND_R_POS.z - WHEEL_Z
CASE_LEN    = math.hypot(CASE_AXIS_Y, CASE_AXIS_Z)
CASE_TILT   = math.atan2(CASE_AXIS_Z, CASE_AXIS_Y)


class MeshBuilder:
    def __init__(self):
        self.bm = bmesh.new()
        self.cl = self.bm.loops.layers.color.new("Col")
        self.part_tris = {}
        self.current_part = "misc"
        self.current_bone = "Root"
        self.vert_bones = []

    def set_part(self, name, bone=None):
        self.current_part = name
        self.part_tris.setdefault(name, 0)
        if bone is not None:
            self.current_bone = bone

    def set_bone(self, bone):
        self.current_bone = bone

    def face(self, pts, color, out=None):
        pts = [Vector(p) for p in pts]
        if len(pts) < 3:
            return None
        if out is not None:
            out_v = Vector(out)
            n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if n.length < 1e-12 and len(pts) > 3:
                n = (pts[2] - pts[0]).cross(pts[3] - pts[0])
            if n.dot(out_v) < 0:
                pts.reverse()
        vs = [self.bm.verts.new(G(p)) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            for v in vs:
                self.bm.verts.remove(v)
            return None
        for _ in vs:
            self.vert_bones.append(self.current_bone)
        f.smooth = False
        for loop in f.loops:
            loop[self.cl] = color
        self.part_tris[self.current_part] = self.part_tris.get(self.current_part, 0) + (len(pts) - 2)
        return f

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None, skip_k=()):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            for k in range(n):
                if k in skip_k:
                    continue
                kn = (k + 1) % n
                p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
                col = colors(i, k) if callable(colors) else colors
                mid = (p0 + p1 + p2 + p3) * 0.25
                self.face([p0, p1, p2, p3], col, out=(mid - cmid))
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            if n <= 4:
                self.face(r0, col, out=out_dir)
            elif n == 5:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir)
                self.face([r0[0], r0[3], r0[4]], col, out=out_dir)
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir)
            else:
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            if n <= 4:
                self.face(rt, col, out=out_dir)
            elif n == 5:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir)
                self.face([rt[0], rt[3], rt[4]], col, out=out_dir)
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir)
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir)

    def box(self, x0, x1, y0, y1, z0, z1, color, skip=()):
        p000 = V(x0, y0, z0); p100 = V(x1, y0, z0)
        p101 = V(x1, y0, z1); p001 = V(x0, y0, z1)
        p010 = V(x0, y1, z0); p110 = V(x1, y1, z0)
        p111 = V(x1, y1, z1); p011 = V(x0, y1, z1)
        c = color if isinstance(color, dict) else {}

        def gc(side):
            return c.get(side, color if not isinstance(color, dict) else c.get("default"))

        if "front"  not in skip: self.face([p001, p101, p111, p011], gc("front"),  out=(0, 0, 1))
        if "back"   not in skip: self.face([p100, p000, p010, p110], gc("back"),   out=(0, 0, -1))
        if "right"  not in skip: self.face([p101, p100, p110, p111], gc("right"),  out=(1, 0, 0))
        if "left"   not in skip: self.face([p000, p001, p011, p010], gc("left"),   out=(-1, 0, 0))
        if "top"    not in skip: self.face([p011, p111, p110, p010], gc("top"),    out=(0, 1, 0))
        if "bottom" not in skip: self.face([p000, p100, p101, p001], gc("bottom"), out=(0, -1, 0))

    def ribbon_path(self, centers, normals, half_w, half_t, color, cap_start=False, cap_end=False):
        """Sweep a rectangular strap along 3D centers with given outward normals."""
        rings = []
        for i, c in enumerate(centers):
            if i == 0:
                t = (centers[1] - centers[0]).normalized()
            elif i == len(centers) - 1:
                t = (centers[-1] - centers[-2]).normalized()
            else:
                t1 = (centers[i] - centers[i - 1]).normalized()
                t2 = (centers[i + 1] - centers[i]).normalized()
                t = t1 + t2
                t = t.normalized() if t.length > 1e-6 else t1
            n = normals[i].normalized()
            b = t.cross(n)
            if b.length < 1e-6:
                b = t.cross(V(0, 1, 0))
            b = b.normalized()
            n = b.cross(t).normalized()
            rings.append([
                c - b * half_w + n * half_t,
                c + b * half_w + n * half_t,
                c + b * half_w - n * half_t,
                c - b * half_w - n * half_t,
            ])
        self.loft(rings, color, cap_bottom=cap_start, cap_top=cap_end, bot_color=color, top_color=color)


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + SLEEK PULLED-BACK HAIR (6-sided low-poly head, y = 1.18 .. 1.69)
    # =========================================================================
    mb.set_part("head_and_hair", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.184,  0.012, 0.148, 0.142),  # 0: chin/jaw base
        (1.270,  0.016, 0.214, 0.200),  # 1: lower cheek
        (1.482,  0.010, 0.216, 0.206),  # 2: brow / forehead top
        (1.602, -0.002, 0.194, 0.198),  # 3: upper crown
        (1.682, -0.012, 0.106, 0.108),  # 4: top cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # Subtle hair volume lift on upper/back rings
    for i in (2, 3, 4):
        for k in range(6):
            if i >= 3 or k in (1, 2, 3, 4):
                p = head_rings[i][k]
                head_rings[i][k] = V(p.x * 1.045, p.y, p.z * 1.045)

    def head_color(i, k):
        if i >= 2:
            return HAIR
        if i == 1:
            return SKIN if k in (4, 5, 0) else HAIR
        return HAIR if k in (1, 2, 3) else SKIN

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 2 and k == 5:
                part_apex = (p2 + p3) * 0.5
                mb.face([p0, p1, part_apex], SKIN, out=(0, 0, 1))
                mb.face([p0, part_apex, p3], HAIR, out=(0, 0, 1))
                mb.face([p1, p2, part_apex], HAIR, out=(0, 0, 1))
            elif i == 1 and k == 0:
                p_temple = p1.lerp(p2, 0.36)
                mb.face([p0, p1, p_temple, p3], SKIN, out=(mid - cmid))
                mb.face([p_temple, p2, p3], HAIR, out=(mid - cmid))
            elif i == 1 and k == 4:
                p_temple = p0.lerp(p3, 0.36)
                mb.face([p0, p1, p2, p_temple], SKIN, out=(mid - cmid))
                mb.face([p_temple, p2, p3], HAIR, out=(mid - cmid))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    rt = head_rings[-1]
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR, out=(0, 1, 0))
    mb.face([rt[3], rt[4], rt[5], rt[0]], HAIR, out=(0, 1, 0))

    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. HIGH CHIGNON HAIR BUN (5-sided chunky faceted low-poly bun = 23 tris)
    # =========================================================================
    mb.set_part("hair_bun", bone="Head")
    bun_axis = V(0.0, 0.26, -0.966).normalized()
    bun_u = V(1.0, 0.0, 0.0)
    bun_v = bun_axis.cross(bun_u).normalized()
    bun_base = V(0.0, 1.495, -0.155)
    bun_stations = [
        (0.000, 0.095, 0.092),  # tucked root inside back of hair
        (0.115, 0.162, 0.156),  # chunky wide faceted belly
        (0.228, 0.092, 0.088),  # faceted crown of bun
    ]
    bun_rings = []
    for (d, rx, ry) in bun_stations:
        c = bun_base + bun_axis * d
        ring = []
        for k in range(5):
            a = 2.0 * math.pi * k / 5.0 + math.pi / 5.0
            ring.append(c + bun_u * (rx * math.sin(a)) + bun_v * (ry * math.cos(a)))
        bun_rings.append(ring)

    def bun_col(i, k):
        return HAIR_SHADE if i == 0 else HAIR

    mb.loft(bun_rings, bun_col, cap_bottom=False, cap_top=True, top_color=HAIR)

    # =========================================================================
    # 3. EARS + ICONIC GOLD SQUARE EARRINGS (with darker center accent)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.200
        x_out = side * 0.242
        y0, y1 = 1.305, 1.396
        z0, z1 = -0.020, 0.044
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.012, zm)
        p_ot = V(x_out, y1 - 0.012, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    mb.set_part("earrings", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.224
        x_out = side * 0.248
        xa, xb = min(x_in, x_out), max(x_in, x_out)
        cy = 1.280
        cz = 0.012
        r = 0.032
        skip_in = "left" if side > 0 else "right"
        mb.box(xa, xb, cy - r, cy + r, cz - r, cz + r,
               {"default": GOLD, "bottom": GOLD_SHADE, "back": GOLD_SHADE},
               skip=(skip_in, "top"))
        x_dot = side * 0.250
        rd = 0.010
        mb.face([
            V(x_dot, cy - rd, cz - rd),
            V(x_dot, cy - rd, cz + rd),
            V(x_dot, cy + rd, cz + rd),
            V(x_dot, cy + rd, cz - rd),
        ], GOLD_SHADE, out=(side, 0, 0))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons on flat front face)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.196
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.386
        rx = 0.018
        ry = 0.046
        pts = [
            V(cx,      cy + ry,        z_eye),
            V(cx + rx, cy + ry * 0.58, z_eye),
            V(cx + rx, cy - ry * 0.58, z_eye),
            V(cx,      cy - ry,        z_eye),
            V(cx - rx, cy - ry * 0.58, z_eye),
            V(cx - rx, cy + ry * 0.58, z_eye),
        ]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. NECK (4-sided tapered warm skin column)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.098, 0.006, 0.070, 0.064, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.196, 0.010, 0.066, 0.060, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 6. CREAM COLLARED BLOUSE + V-NECK SKIN
    # =========================================================================
    mb.set_part("blouse", bone="Torso")
    sx = 0.145
    sz_f = 0.104
    v_top_x = 0.062
    v_bot_y = 1.005
    v_top_y = 1.132

    mb.face([V(-sx, 0.680, sz_f), V(sx, 0.680, sz_f),
             V(sx, v_bot_y, sz_f), V(-sx, v_bot_y, sz_f)], BLOUSE, out=(0, 0, 1))
    mb.face([V(-sx, v_bot_y, sz_f), V(0.0, v_bot_y, sz_f),
             V(-v_top_x, v_top_y, sz_f), V(-sx, v_top_y, sz_f)], BLOUSE, out=(0, 0, 1))
    mb.face([V(0.0, v_bot_y, sz_f), V(sx, v_bot_y, sz_f),
             V(sx, v_top_y, sz_f), V(v_top_x, v_top_y, sz_f)], BLOUSE, out=(0, 0, 1))
    mb.face([V(0.0, v_bot_y, sz_f + 0.002), V(v_top_x, v_top_y, sz_f + 0.002),
             V(-v_top_x, v_top_y, sz_f + 0.002)], SKIN, out=(0, 0, 1))
    for side in (-1, 1):
        p_neck = V(side * 0.062, 1.132, 0.094)
        p_tip  = V(side * 0.012, 1.024, sz_f + 0.014)
        p_out  = V(side * 0.088, 1.058, sz_f + 0.016)
        p_top  = V(side * 0.090, 1.132, 0.102)
        mb.face([p_tip, p_out, p_top, p_neck], BLOUSE_SHADE, out=(0, 0.1, 1))

    # =========================================================================
    # 7. TAILORED SLATE-NAVY BLAZER (open front, notched lapels, structured hem)
    # =========================================================================
    mb.set_part("blazer", bone="Torso")
    jy0, jy1 = 0.642, 1.138
    jy_sh = 1.120  # gentle tailored shoulder slope seamlessly meeting sleeves
    j_open_bot = 0.068
    j_open_top = 0.062
    jx_bot = 0.208
    jx_top = 0.194
    jz_fb = 0.128
    jz_ft = 0.118
    jz_bb = -0.122
    jz_bt = -0.112

    mb.face([V(jx_bot, jy0, jz_bb), V(-jx_bot, jy0, jz_bb),
             V(-jx_top, jy_sh, jz_bt), V(jx_top, jy_sh, jz_bt)], BLAZER, out=(0, 0, -1))
    # Sleek back collar stand (back + top = 4 tris) + top neck fill (2 tris)
    mb.face([V(0.082, jy_sh, jz_bt), V(-0.082, jy_sh, jz_bt),
             V(-0.082, 1.162, jz_bt), V(0.082, 1.162, jz_bt)], BLAZER_SHADE, out=(0, 0, -1))
    mb.face([V(-0.082, 1.162, jz_bt), V(0.082, 1.162, jz_bt),
             V(0.072, 1.146, -0.058), V(-0.072, 1.146, -0.058)], BLAZER_SHADE, out=(0, 1, 0))
    mb.face([V(-j_open_top, jy1, -0.062), V(j_open_top, jy1, -0.062),
             V(j_open_top, jy1, 0.095),   V(-j_open_top, jy1, 0.095)], BLAZER_SHADE, out=(0, 1, 0))

    for side in (-1, 1):
        xo_b, xo_t = side * jx_bot, side * jx_top
        xi_b, xi_t = side * j_open_bot, side * j_open_top
        mb.face([V(xo_b, jy0, jz_fb), V(xo_b, jy0, jz_bb),
                 V(xo_t, jy_sh, jz_bt), V(xo_t, jy_sh, jz_ft)], BLAZER, out=(side, 0, 0))
        mb.face([V(xi_b, jy0, jz_fb), V(xo_b, jy0, jz_fb),
                 V(xo_t, jy_sh, jz_ft), V(xi_t, jy1, jz_ft)], BLAZER, out=(0, 0, 1))
        mb.face([V(xi_b, jy0, sz_f), V(xi_b, jy0, jz_fb),
                 V(xi_t, jy1, jz_ft), V(xi_t, jy1, sz_f)], BLAZER_SHADE, out=(-side, 0, 0))
        mb.face([V(xi_t, jy1, jz_ft), V(xo_t, jy_sh, jz_ft),
                 V(xo_t, jy_sh, jz_bt), V(xi_t, jy1, jz_bt)], BLAZER, out=(0, 1, 0))
        mb.face([V(xi_b, jy0, jz_bb), V(xo_b, jy0, jz_bb),
                 V(xo_b, jy0, jz_fb), V(xi_b, jy0, jz_fb)], BLAZER_SHADE, out=(0, -1, 0))
        lp_b  = V(side * 0.068, 0.800, jz_fb + 0.008)
        lp_o  = V(side * 0.126, 0.992, jz_ft + 0.014)
        lp_t  = V(side * 0.094, 1.134, jz_ft + 0.006)
        lp_in = V(side * 0.062, 1.138, jz_ft + 0.004)
        mb.face([lp_b, lp_o, lp_t, lp_in], BLAZER_LAPEL, out=(0, 0, 1))

    # =========================================================================
    # 8. SLEEVES + CRISP WHITE SHIRT CUFFS + HANDS
    # =========================================================================
    def build_arm(p_sh, p_wr, p_tip, bone_name, is_right=False):
        ax = (p_wr - p_sh).normalized()
        side_x = V(1.0, 0.0, 0.0)
        u = (side_x - ax * side_x.dot(ax)).normalized()
        v = ax.cross(u).normalized()

        def ring(ctr, ru, rv):
            return [
                ctr - u * ru + v * rv,
                ctr + u * ru + v * rv,
                ctr + u * ru - v * rv,
                ctr - u * ru - v * rv,
            ]

        p_cuf0 = p_sh.lerp(p_wr, 0.925)
        mb.set_part("sleeves", bone=bone_name)
        r_sh = ring(p_sh,   0.066, 0.074)
        r_wr = ring(p_cuf0, 0.064, 0.070)
        mb.loft([r_sh, r_wr], BLAZER, cap_bottom=False, cap_top=False)

        # Crisp cream blouse cuff peeking out from under the blazer sleeve
        mb.set_part("cuffs", bone=bone_name)
        r_c0 = ring(p_cuf0, 0.056, 0.060)
        r_c1 = ring(p_wr,   0.054, 0.058)
        mb.loft([r_c0, r_c1], BLOUSE, cap_bottom=False, cap_top=False)

        # Chunky stylized hand / fist
        mb.set_part("hands", bone=bone_name)
        h_ax = (p_tip - p_wr).normalized()
        hu = (side_x - h_ax * side_x.dot(h_ax)).normalized()
        hv = h_ax.cross(hu).normalized()

        def hring(ctr, ru, rv):
            return [
                ctr - hu * ru + hv * rv,
                ctr + hu * ru + hv * rv,
                ctr + hu * ru - hv * rv,
                ctr - hu * ru - hv * rv,
            ]

        r_h0 = hring(p_wr, 0.044, 0.046)
        r_h1 = hring(p_tip, 0.048 if is_right else 0.042, 0.052 if is_right else 0.044)
        mb.loft([r_h0, r_h1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # Left arm (+X): tucked seamlessly into blazer shoulder, hanging at confident angle
    p_l_sh  = V( 0.162, 1.076, 0.004)
    p_l_wr  = V( 0.256, 0.672, 0.045)
    p_l_tip = V( 0.262, 0.580, 0.062)
    build_arm(p_l_sh, p_l_wr, p_l_tip, "Arm_L", is_right=False)

    # Right arm (-X): tucked seamlessly into blazer shoulder, reaching down-back to grip suitcase!
    p_r_sh  = V(-0.162, 1.076, 0.004)
    r_dir   = (HAND_R_POS - p_r_sh).normalized()
    p_r_wr  = HAND_R_POS - r_dir * 0.058
    p_r_tip = HAND_R_POS + r_dir * 0.042
    build_arm(p_r_sh, p_r_wr, p_r_tip, "Arm_R", is_right=True)

    # =========================================================================
    # 9. BEIGE TOTE PURSE + BROWN LEATHER SHOULDER STRAP (right side -X)
    # =========================================================================
    mb.set_part("purse", bone="Purse")
    # Chic structured tote tucked cleanly beside right hip, forward of angled-back Arm_R
    tx_in  = -0.194
    tx_out = -0.268
    ty_bot =  0.562
    ty_top =  0.822
    tz_b0, tz_f0 = -0.028, 0.158
    tz_b1, tz_f1 = -0.042, 0.174

    r_bag_bot = [
        V(tx_out, ty_bot, tz_b0),
        V(tx_in,  ty_bot, tz_b0),
        V(tx_in,  ty_bot, tz_f0),
        V(tx_out, ty_bot, tz_f0),
    ]
    r_bag_top = [
        V(tx_out - 0.006, ty_top, tz_b1),
        V(tx_in,          ty_top, tz_b1),
        V(tx_in,          ty_top, tz_f1),
        V(tx_out - 0.006, ty_top, tz_f1),
    ]

    def bag_col(i, k):
        return PURSE_SHADE if k in (0, 1) else PURSE

    mb.loft([r_bag_bot, r_bag_top], bag_col, cap_bottom=True, cap_top=True,
            bot_color=PURSE_SHADE, top_color=PURSE_SHADE)

    # Subtle patch pocket detail on outer face of tote (1 quad = 2 tris)
    x_pk = tx_out - 0.008
    mb.face([
        V(x_pk, 0.652, 0.020),
        V(x_pk, 0.652, 0.112),
        V(x_pk, 0.736, 0.112),
        V(x_pk, 0.736, 0.020),
    ], PURSE_POCKET, out=(-1, 0, 0))

    # Warm brown leather shoulder strap (3 segments = 24 tris) hugging right shoulder cleanly
    mb.set_part("purse_strap", bone="Purse")
    strap_pts = [
        V(-0.232, 0.816,  0.128),  # tote top front
        V(-0.184, 1.135,  0.048),  # right shoulder crest front
        V(-0.184, 1.132, -0.018),  # right shoulder crest mid
        V(-0.228, 0.816, -0.006),  # tote top back (cleanly forward of Arm_R!)
    ]
    strap_norms = [
        V(-0.85, 0.0,  0.5),
        V(-0.20, 0.95, 0.25),
        V(-0.20, 0.98, -0.10),
        V(-0.85, 0.0, -0.5),
    ]
    mb.ribbon_path(strap_pts, strap_norms, half_w=0.020, half_t=0.008, color=PURSE_STRAP)

    # =========================================================================
    # 10. WIDE-LEG SLATE-NAVY SUIT TROUSERS + BARE ANKLES
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.184, 0.184, 0.556, 0.688, -0.102, 0.106,
           {"default": PANTS, "bottom": PANTS_SHADE}, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t  = side * 0.012
        x_out_t = side * 0.184
        x_in_b  = side * 0.056
        x_out_b = side * 0.226
        rz_t = 0.096
        rz_b = 0.094
        r_top = [
            V(min(x_in_t, x_out_t), 0.588,  rz_t),
            V(max(x_in_t, x_out_t), 0.588,  rz_t),
            V(max(x_in_t, x_out_t), 0.588, -rz_t),
            V(min(x_in_t, x_out_t), 0.588, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.195,  rz_b),
            V(max(x_in_b, x_out_b), 0.195,  rz_b),
            V(max(x_in_b, x_out_b), 0.195, -rz_b),
            V(min(x_in_b, x_out_b), 0.195, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        mb.box(cx - 0.042, cx + 0.042, 0.092, 0.205, -0.044, 0.044, SKIN, skip=("top", "bottom"))

    # =========================================================================
    # 11. DARK LOW-HEELED PUMPS WITH VISIBLE SKIN INSTEP (22 tris per shoe = 44 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        w_h = 0.052
        w_m = 0.058
        w_t = 0.036
        z_heel = -0.088
        z_arch = -0.015
        z_vamp =  0.082
        z_toe  =  0.168
        y0 = 0.000
        y_arch = 0.022
        y_collar = 0.098
        y_vamp   = 0.056
        y_toe    = 0.036

        # Grounded block heel & rear counter (5 faces = 10 tris)
        mb.box(cx - w_h, cx + w_h, y0, y_collar, z_heel, z_arch,
               {"default": SHOE, "bottom": SHOE_SHADE, "front": SHOE_SHADE},
               skip=("top",))

        p_al = V(cx - w_m, y_arch, z_arch)
        p_ar = V(cx + w_m, y_arch, z_arch)
        p_fl = V(cx - w_m, y0,     z_vamp)
        p_fr = V(cx + w_m, y0,     z_vamp)
        p_tl = V(cx - w_t, y0,     z_toe)
        p_tr = V(cx + w_t, y0,     z_toe)

        p_ul = V(cx - w_m * 0.90, y_vamp, z_vamp)
        p_ur = V(cx + w_m * 0.90, y_vamp, z_vamp)
        p_cl = V(cx - w_h, y_collar, z_arch)
        p_cr = V(cx + w_h, y_collar, z_arch)

        # Sole underside (1 continuous arch-to-toe quad = 2 tris)
        mb.face([p_al, p_ar, p_tr, p_tl], SHOE_SHADE, out=(0, -1, 0))
        # Sleek tapered toe vamp sloping cleanly down to tip (2 tris)
        mb.face([p_ul, p_ur, p_tr, p_tl], SHOE, out=(0, 1, 0.5))
        # Left & right side walls bridging heel to pointed toe (3 tris each = 6 tris)
        mb.face([p_al, p_fl, p_ul, p_cl], SHOE, out=(-1, 0, 0))
        mb.face([p_fl, p_tl, p_ul], SHOE, out=(-1, 0, 0))
        mb.face([p_ar, p_cr, p_ur, p_fr], SHOE, out=( 1, 0, 0))
        mb.face([p_fr, p_ur, p_tr], SHOE, out=( 1, 0, 0))
        # Bare warm-brown skin instep visible inside low-cut pump opening (2 tris)
        mb.face([p_cl, p_cr, p_ur, p_ul], SKIN, out=(0, 1, 0.4))

    # =========================================================================
    # 12. ROLLING DARK-GREY HARD-SHELL SUITCASE (bone Suitcase + Case_Wheels)
    # =========================================================================
    mb.set_part("suitcase", bone="Suitcase")
    ct = math.cos(CASE_TILT)
    st = math.sin(CASE_TILT)
    case_orig = V(CASE_X, WHEEL_R, WHEEL_Z)

    def case_pt(lx, ly, lz):
        wy = ly * ct - lz * st
        wz = ly * st + lz * ct
        return V(case_orig.x + lx, case_orig.y + wy, case_orig.z + wz)

    # Chunky square carry-on hard-shell with chamfered top shoulder (20 tris)
    case_stations = [
        # (ly,    hx,    hz)
        (0.044, 0.122, 0.102),  # bottom base clearing wheels & ground cleanly
        (0.332, 0.122, 0.102),  # main boxy carry-on body
        (0.368, 0.098, 0.078),  # sleek chamfered top shoulder
    ]
    case_rings = []
    for (ly, hx, hz) in case_stations:
        case_rings.append([
            case_pt(-hx, ly, -hz),
            case_pt( hx, ly, -hz),
            case_pt( hx, ly,  hz),
            case_pt(-hx, ly,  hz),
        ])

    def case_col(i, k):
        if i == 1:
            return CASE_SHADE
        return CASE_SHADE if k in (1, 3) else CASE

    mb.loft(case_rings, case_col, cap_bottom=True, cap_top=True,
            bot_color=CASE_SHADE, top_color=CASE_SHADE)

    # Crisp vertical hard-shell molding ribs on outer side (-X) & back (-Z) (8 tris)
    for rz_rib in (-0.040, 0.040):
        mb.face([
            case_pt(-0.125, 0.078, rz_rib - 0.012),
            case_pt(-0.125, 0.078, rz_rib + 0.012),
            case_pt(-0.125, 0.296, rz_rib + 0.012),
            case_pt(-0.125, 0.296, rz_rib - 0.012),
        ], CASE_RIB, out=(-1, 0, 0))
    for rx_rib in (-0.046, 0.046):
        mb.face([
            case_pt(rx_rib - 0.013, 0.078, -0.105),
            case_pt(rx_rib + 0.013, 0.078, -0.105),
            case_pt(rx_rib + 0.013, 0.296, -0.105),
            case_pt(rx_rib - 0.013, 0.296, -0.105),
        ], CASE_RIB, out=(0, -st, -ct))

    # Telescopic twin-post handle rising straight to HAND_R_POS (12 + 8 = 20 tris)
    mb.set_part("suitcase_handle", bone="Suitcase")
    rod_y0 = 0.354
    rod_y1 = CASE_LEN - 0.010
    for rod_x in (-0.060, 0.060):
        r0 = []
        r1 = []
        for k in range(3):
            a = 2.0 * math.pi * k / 3.0 + math.pi / 6.0
            dx = 0.013 * math.sin(a)
            dz = 0.013 * math.cos(a)
            r0.append(case_pt(rod_x + dx, rod_y0, dz))
            r1.append(case_pt(rod_x + dx, rod_y1, dz))
        mb.loft([r0, r1], CASE_HANDLE, cap_bottom=False, cap_top=False)

    # Horizontal top grip bar right through HAND_R_POS (3-sided prism = 8 tris)
    g_hx = 0.078
    g_r = 0.020
    r_grip_l = []
    r_grip_r = []
    for k in range(3):
        a = 2.0 * math.pi * k / 3.0
        dy = g_r * math.cos(a)
        dz = g_r * math.sin(a)
        r_grip_l.append(case_pt(-g_hx, CASE_LEN + dy, dz))
        r_grip_r.append(case_pt( g_hx, CASE_LEN + dy, dz))
    mb.loft([r_grip_l, r_grip_r], CASE_HANDLE, cap_bottom=True, cap_top=True,
            bot_color=CASE_HANDLE, top_color=CASE_HANDLE)

    # 2 chunky 5-sided rolling wheels resting squarely at y = 0.000 (32 tris)
    mb.set_part("suitcase_wheels", bone="Case_Wheels")
    for wx_off in (-0.082, 0.082):
        wx_c = CASE_X + wx_off
        hw = 0.023
        r_wl = []
        r_wr = []
        for k in range(5):
            a = 2.0 * math.pi * k / 5.0
            wy = WHEEL_R + WHEEL_R * math.cos(a)
            wz = WHEEL_Z + WHEEL_R * math.sin(a)
            r_wl.append(V(wx_c - hw, wy, wz))
            r_wr.append(V(wx_c + hw, wy, wz))
        mb.loft([r_wl, r_wr], CASE_WHEEL, cap_bottom=True, cap_top=True,
                bot_color=CASE_WHEEL, top_color=CASE_WHEEL)

    return mb


def setup_material():
    mat = bpy.data.materials.get("VertexColour") or bpy.data.materials.new("VertexColour")
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = next((n for n in nt.nodes if n.type == "VERTEX_COLOR"), None)
    if attr is None:
        attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.name = "Attr"
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.22
    return mat


def _reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _pose_mat(head_g, loc, rot_xyz):
    """4x4 world-offset transform contributed by a bone whose local frame matches Game (X, Y, Z)."""
    h = Vector(head_g)
    return (
        Matrix.Translation(h + Vector(loc))
        @ Euler(rot_xyz, "XYZ").to_matrix().to_4x4()
        @ Matrix.Translation(-h)
    )


def _solve_suitcase_grounded_lock(root_loc, root_rot, torso_rot, arm_r_rot):
    """Compute exact local (location, rotation_euler) for Suitcase (child of Root)
    so BOTH wheels stay glued to y = 0 AND the top grip stays locked inside her right hand!"""
    root_head = Vector((0.0, ROOT_Y, 0.0))
    torso_head = Vector((0.0, TORSO_Y, 0.0))
    arm_r_head = Vector((-SHOULDER_X, SHOULDER_Y, SHOULDER_Z))
    case_head = Vector((CASE_X, WHEEL_R, WHEEL_Z))

    m_root = _pose_mat(root_head, root_loc, root_rot)
    m_torso = _pose_mat(torso_head, (0.0, 0.0, 0.0), torso_rot)
    m_arm_r = _pose_mat(arm_r_head, (0.0, 0.0, 0.0), arm_r_rot)

    hand_w = m_root @ m_torso @ m_arm_r @ HAND_R_POS

    cos_a = max(-0.98, min(0.98, (hand_w.y - WHEEL_R) / CASE_LEN))
    alpha = math.acos(cos_a)
    delta_pitch = alpha - CASE_TILT

    wheel_w = Vector((hand_w.x, WHEEL_R, hand_w.z - CASE_LEN * math.sin(alpha)))
    m_case_world = (
        Matrix.Translation(wheel_w)
        @ Euler((delta_pitch, 0.0, 0.0), "XYZ").to_matrix().to_4x4()
        @ Matrix.Translation(-case_head)
    )

    m_local = (
        Matrix.Translation(-case_head)
        @ m_root.inverted()
        @ m_case_world
        @ Matrix.Translation(case_head)
    )
    loc, quat, _ = m_local.decompose()
    return loc, quat.to_euler("XYZ"), wheel_w.z - WHEEL_Z


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: poised stride, free left arm swing, grounded rolling suitcase locked in right hand."""
    action = bpy.data.actions.new(name="Walk")
    rig.animation_data.action = action
    _reset_pose(rig)

    cycle_len = 24
    for frame in range(1, cycle_len + 2, 2):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        c1 = math.cos(phi)
        c2 = math.cos(2.0 * phi)

        bob = -0.022 * (1.0 - c2) * 0.5
        root_loc = (0.0, bob, 0.0)
        root_rot = (0.036, -0.055 * s1, 0.030 * c1)
        pb_root = rig.pose.bones["Root"]
        pb_root.location = root_loc
        pb_root.rotation_euler = root_rot
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_rot = (0.016 * c2, 0.082 * s1, -0.018 * c1)
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = torso_rot
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.032 + 0.022 * c2, -0.036 * s1, -0.012 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.42 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.034, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.42 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.034, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.34 * s1, 0.0, 0.020 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        arm_r_rot = (-0.055 * s1, 0.0, 0.0)
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = arm_r_rot
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_purse = rig.pose.bones["Purse"]
        pb_purse.rotation_euler = (0.050 * math.sin(phi - 0.55), 0.0, 0.020 * c1)
        pb_purse.keyframe_insert(data_path="rotation_euler", frame=frame)

        c_loc, c_rot, _ = _solve_suitcase_grounded_lock(root_loc, root_rot, torso_rot, arm_r_rot)
        pb_case = rig.pose.bones["Suitcase"]
        pb_case.location = c_loc
        pb_case.rotation_euler = c_rot
        pb_case.keyframe_insert(data_path="location", frame=frame)
        pb_case.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_w = rig.pose.bones["Case_Wheels"]
        pb_w.rotation_euler = (2.0 * phi, 0.0, 0.0)
        pb_w.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: poised dock wait, calm breathing, glance around, grounded suitcase settle."""
    action = bpy.data.actions.new(name="Idle")
    rig.animation_data.action = action
    _reset_pose(rig)

    cycle_len = 48
    for frame in range(1, cycle_len + 2, 4):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        s2 = math.sin(2.0 * phi)
        c1 = math.cos(phi)

        bob = -0.007 * (1.0 - c1) * 0.5
        root_loc = (0.0, bob, 0.0)
        root_rot = (0.008, 0.020 * s1, 0.015 * s1)
        pb_root = rig.pose.bones["Root"]
        pb_root.location = root_loc
        pb_root.rotation_euler = root_rot
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_rot = (0.018 * s2, 0.026 * s1, -0.014 * s1)
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = torso_rot
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.028 * s2, 0.20 * s1, 0.024 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (-0.045 * s1, 0.0, 0.016 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        arm_r_rot = (0.032 * s1, 0.0, 0.0)
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = arm_r_rot
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_purse = rig.pose.bones["Purse"]
        pb_purse.rotation_euler = (0.018 * s2, 0.0, -0.016 * s1)
        pb_purse.keyframe_insert(data_path="rotation_euler", frame=frame)

        c_loc, c_rot, wheel_dz = _solve_suitcase_grounded_lock(root_loc, root_rot, torso_rot, arm_r_rot)
        pb_case = rig.pose.bones["Suitcase"]
        pb_case.location = c_loc
        pb_case.rotation_euler = c_rot
        pb_case.keyframe_insert(data_path="location", frame=frame)
        pb_case.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_w = rig.pose.bones["Case_Wheels"]
        pb_w.rotation_euler = (wheel_dz / WHEEL_R, 0.0, 0.0)
        pb_w.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 10-bone rig (7 standard passenger bones + Purse, Suitcase, Case_Wheels) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonTravelerRig")
    rig = bpy.data.objects.new("PersonTravelerRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",        None,       ( 0.000, ROOT_Y,     0.000),      ( 0.000, ROOT_Y + 0.12,     0.000)),
        ("Torso",       "Root",     ( 0.000, TORSO_Y,    0.000),      ( 0.000, 1.120,             0.000)),
        ("Head",        "Torso",    ( 0.000, 1.150,      0.000),      ( 0.000, 1.460,             0.000)),
        ("Arm_L",       "Torso",    ( SHOULDER_X, SHOULDER_Y, SHOULDER_Z), ( SHOULDER_X, SHOULDER_Y + 0.16, SHOULDER_Z)),
        ("Arm_R",       "Torso",    (-SHOULDER_X, SHOULDER_Y, SHOULDER_Z), (-SHOULDER_X, SHOULDER_Y + 0.16, SHOULDER_Z)),
        ("Purse",       "Torso",    (-0.188, 1.140,      0.025),      (-0.188, 1.300,             0.025)),
        ("Leg_L",       "Root",     ( 0.102, 0.575,      0.000),      ( 0.102, 0.735,             0.000)),
        ("Leg_R",       "Root",     (-0.102, 0.575,      0.000),      (-0.102, 0.735,             0.000)),
        ("Suitcase",    "Root",     ( CASE_X, WHEEL_R,   WHEEL_Z),    ( CASE_X, WHEEL_R + 0.22,   WHEEL_Z)),
        ("Case_Wheels", "Suitcase", ( CASE_X, WHEEL_R,   WHEEL_Z),    ( CASE_X, WHEEL_R + 0.12,   WHEEL_Z)),
    ]

    ebones = {}
    for (bname, parent, h_g, t_g) in bone_defs:
        eb = arm_data.edit_bones.new(bname)
        eb.head = G(h_g)
        eb.tail = G(t_g)
        eb.roll = 0.0
        if parent is not None:
            eb.parent = ebones[parent]
            eb.use_connect = False
        ebones[bname] = eb

    bpy.ops.object.mode_set(mode="OBJECT")

    vgroups = {}
    for (bname, _, _, _) in bone_defs:
        vgroups[bname] = ob.vertex_groups.new(name=bname)
    for v_idx, bname in enumerate(mb.vert_bones):
        vgroups[bname].add([v_idx], 1.0, "REPLACE")

    ob.parent = rig
    mod = ob.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = rig

    scene = bpy.context.scene
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 24

    rig.animation_data_create()
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")

    walk_action = _create_walk_action(rig, scene)
    idle_action = _create_idle_action(rig, scene)

    bpy.ops.object.mode_set(mode="OBJECT")

    for act, end_f in ((walk_action, 25), (idle_action, 49)):
        track = rig.animation_data.nla_tracks.new()
        track.name = act.name
        strip = track.strips.new(act.name, 1, act)
        strip.action_frame_start = 1
        strip.action_frame_end = end_f
        track.mute = True

    rig.animation_data.action = walk_action
    scene.frame_start = 1
    scene.frame_end = 24
    scene.frame_set(1)
    return rig, walk_action, idle_action


def render_preview(obj, out_path):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False

    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.94, 0.95, 0.96, 1.0)
    bg.inputs["Strength"].default_value = 0.95
    scene.world = world

    key_data = bpy.data.lights.new("KeyLight", type="SUN")
    key_data.energy = 2.6
    key_data.angle = math.radians(18.0)
    key_obj = bpy.data.objects.new("KeyLight", key_data)
    scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(46), math.radians(10), math.radians(-35))

    fill_data = bpy.data.lights.new("FillLight", type="SUN")
    fill_data.energy = 0.85
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-1.82, math.radians(58)),   # Front-3/4 matching reference angle (facing right)
        (-0.58, math.radians(0)),    # Front
        ( 0.62, math.radians(90)),   # Side (showing bun, earring, purse, suitcase)
        ( 1.86, math.radians(180)),  # Back
    ]
    obj.hide_render = True
    for (xpos, zrot) in specs:
        c = obj.copy()
        c.location = (xpos, 0.0, 0.0)
        c.rotation_euler = (0.0, 0.0, zrot)
        c.hide_render = False
        scene.collection.objects.link(c)
        clones.append(c)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 5.1
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.14)
    direction = Vector((0.0, 0.0, 0.85)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 560
    scene.render.filepath = out_path
    scene.view_settings.view_transform = "Standard"
    bpy.ops.render.render(write_still=True)

    obj.hide_render = False
    for o in [key_obj, fill_obj, floor, cam_obj] + clones:
        bpy.data.objects.remove(o, do_unlink=True)


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=58):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 20
    scene.cycles.use_denoising = False

    prev_action = rig.animation_data.action
    rig.animation_data.action = action

    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.94, 0.95, 0.96, 1.0)
    bg.inputs["Strength"].default_value = 0.95
    scene.world = world

    key_data = bpy.data.lights.new("StripKey", type="SUN")
    key_data.energy = 2.6
    key_data.angle = math.radians(18.0)
    key_obj = bpy.data.objects.new("StripKey", key_data)
    scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(46), math.radians(10), math.radians(-35))

    fill_data = bpy.data.lights.new("StripFill", type="SUN")
    fill_data.energy = 0.85
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("StripFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("StripFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    snapshots = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.hide_render = True
    for idx, f in enumerate(frames):
        scene.frame_set(f)
        depsgraph.update()
        eval_obj = obj.evaluated_get(depsgraph)
        snap_mesh = bpy.data.meshes.new_from_object(eval_obj)
        snap_obj = bpy.data.objects.new(f"StripSnap_{f}", snap_mesh)
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.28
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 8.0
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.15)
    direction = Vector((0.0, 0.0, 0.85)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1500
    scene.render.resolution_y = 460
    scene.render.filepath = out_path
    scene.view_settings.view_transform = "Standard"
    bpy.ops.render.render(write_still=True)

    obj.hide_render = False
    rig.animation_data.action = prev_action
    scene.frame_set(1)
    for o in [key_obj, fill_obj, floor, cam_obj]:
        bpy.data.objects.remove(o, do_unlink=True)
    for (so, sm) in snapshots:
        bpy.data.objects.remove(so, do_unlink=True)
        bpy.data.meshes.remove(sm)


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=55, zrot_right_deg=90):
    """Render a seamless looping dual-angle (front-3/4 + side) MP4 video of an action."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = False

    prev_action = rig.animation_data.action
    rig.animation_data.action = action

    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.94, 0.95, 0.96, 1.0)
    bg.inputs["Strength"].default_value = 0.95
    scene.world = world

    key_data = bpy.data.lights.new("VidKey", type="SUN")
    key_data.energy = 2.6
    key_data.angle = math.radians(18.0)
    key_obj = bpy.data.objects.new("VidKey", key_data)
    scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(46), math.radians(10), math.radians(-35))

    fill_data = bpy.data.lights.new("VidFill", type="SUN")
    fill_data.energy = 0.85
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("VidFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.25
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.12)
    direction = Vector((0.0, 0.0, 0.85)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 800
    scene.render.resolution_y = 520
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"

    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.hide_render = True

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in range(1, cycle_len + 1):
            scene.frame_set(f)
            depsgraph.update()
            eval_obj = obj.evaluated_get(depsgraph)
            snap_mesh = bpy.data.meshes.new_from_object(eval_obj)

            left_obj = bpy.data.objects.new(f"VidL_{f}", snap_mesh)
            left_obj.location = (-0.72, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.72, 0.0, 0.0)
            right_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_right_deg))
            scene.collection.objects.link(right_obj)

            scene.render.filepath = os.path.join(tmpdir, f"frame_{f:04d}.png")
            bpy.ops.render.render(write_still=True)

            bpy.data.objects.remove(left_obj, do_unlink=True)
            bpy.data.objects.remove(right_obj, do_unlink=True)
            bpy.data.meshes.remove(snap_mesh)

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(max(0, loops - 1)),
            "-framerate", "24",
            "-i", os.path.join(tmpdir, "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-movflags", "+faststart",
            out_path,
        ]
        subprocess.run(cmd, check=True)

    obj.hide_render = False
    rig.animation_data.action = prev_action
    scene.frame_set(1)
    for o in [key_obj, fill_obj, floor, cam_obj]:
        bpy.data.objects.remove(o, do_unlink=True)


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonTraveler")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonTraveler")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonTraveler", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    print("=== PersonTraveler Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    assert total_tris < 450, f"Triangle count {total_tris} exceeds strict 450-tri budget!"

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    # Export GLB with both Walk and Idle animations via ACTIONS mode
    os.makedirs(os.path.dirname(GLB_PATH), exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(o in (rig, ob))
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_selection=True,
        export_normals=True,
        export_vertex_color="ACTIVE",
        export_texcoords=True,
        export_materials="EXPORT",
        export_yup=True,
        export_skins=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
    )

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=58)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=48)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH,
                          zrot_left_deg=55, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH,
                          zrot_left_deg=46, zrot_right_deg=90)

    print(f"Saved blend:     {BLEND_PATH}")
    print(f"Exported glb:    {GLB_PATH}")
    print(f"Preview png:     {PREVIEW_PATH}")
    print(f"Walk preview:    {WALK_PREVIEW_PATH}")
    print(f"Idle preview:    {IDLE_PREVIEW_PATH}")
    if not stills_only:
        print(f"Walk video:      {WALK_VIDEO_PATH}")
        print(f"Idle video:      {IDLE_VIDEO_PATH}")


if __name__ == "__main__":
    main()
