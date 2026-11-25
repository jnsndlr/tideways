# Builds an ultra-low-poly stylized business woman commuter in Blender matching the reference
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_business.py)
# Saves art/person_business.blend, exports assets/models/person_business.glb (rigged + Walk & Idle cycles),
# and renders art/person_business_preview.png, art/person_business_walk_preview.png, and art/person_business_idle_preview.png.
#
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.71 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import sys
import subprocess
import tempfile
import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_business.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_business.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_business_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_business_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_business_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_business_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_business_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN          = col_srgb(0.96, 0.72, 0.48)
SKIN_SHADE    = col_srgb(0.88, 0.63, 0.40)
HAIR          = col_srgb(0.36, 0.26, 0.21)
HAIR_SHADE    = col_srgb(0.28, 0.20, 0.16)
EYE           = col_srgb(0.13, 0.13, 0.15)
GOLD          = col_srgb(0.93, 0.77, 0.35)
GOLD_SHADE    = col_srgb(0.77, 0.60, 0.22)
BLOUSE        = col_srgb(0.96, 0.92, 0.85)
BLOUSE_SHADE  = col_srgb(0.88, 0.83, 0.75)
BLAZER        = col_srgb(0.28, 0.32, 0.43)
BLAZER_SHADE  = col_srgb(0.21, 0.24, 0.33)
BLAZER_LAPEL  = col_srgb(0.33, 0.37, 0.49)
LANYARD       = col_srgb(0.35, 0.49, 0.49)
CLIP          = col_srgb(0.66, 0.68, 0.71)
BADGE_BG      = col_srgb(0.96, 0.92, 0.87)
BADGE_PHOTO   = col_srgb(0.89, 0.68, 0.50)
BADGE_LINE    = col_srgb(0.84, 0.79, 0.73)
BELT          = col_srgb(0.80, 0.66, 0.51)
PURSE         = col_srgb(0.32, 0.29, 0.31)
PURSE_DARK    = col_srgb(0.23, 0.21, 0.23)
PURSE_STRAP   = col_srgb(0.26, 0.24, 0.26)
CUP_WHITE     = col_srgb(0.96, 0.94, 0.90)
CUP_SLEEVE    = col_srgb(0.76, 0.61, 0.45)
CUP_LID       = col_srgb(0.22, 0.19, 0.18)
CUP_LID_TOP   = col_srgb(0.28, 0.24, 0.23)
PANTS         = col_srgb(0.23, 0.23, 0.27)
PANTS_SHADE   = col_srgb(0.18, 0.18, 0.21)
SHOE          = col_srgb(0.94, 0.88, 0.79)
SHOE_VAMP     = col_srgb(0.89, 0.82, 0.72)
SOLE          = col_srgb(0.74, 0.66, 0.56)


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            for k in range(n):
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
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir)

    def box(self, x0, x1, y0, y1, z0, z1, color, skip=()):
        p000 = V(x0, y0, z0); p100 = V(x1, y0, z0)
        p101 = V(x1, y0, z1); p001 = V(x0, y0, z1)
        p010 = V(x0, y1, z0); p110 = V(x1, y1, z0)
        p111 = V(x1, y1, z1); p011 = V(x0, y1, z1)
        if "front"  not in skip: self.face([p001, p101, p111, p011], color, out=(0, 0, 1))
        if "back"   not in skip: self.face([p100, p000, p010, p110], color, out=(0, 0, -1))
        if "right"  not in skip: self.face([p101, p100, p110, p111], color, out=(1, 0, 0))
        if "left"   not in skip: self.face([p000, p001, p011, p010], color, out=(-1, 0, 0))
        if "top"    not in skip: self.face([p011, p111, p110, p010], color, out=(0, 1, 0))
        if "bottom" not in skip: self.face([p000, p100, p101, p001], color, out=(0, -1, 0))

    def ribbon_path(self, centers, normals, half_w, half_t, color, cap_start=True, cap_end=True):
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
            ring = [
                c - b * half_w + n * half_t,
                c + b * half_w + n * half_t,
                c + b * half_w - n * half_t,
                c - b * half_w - n * half_t,
            ]
            rings.append(ring)
        self.loft(rings, color, cap_bottom=cap_start, cap_top=cap_end, bot_color=color, top_color=color)


def oval_ring(cx, cy, cz, rx, rz, n=8, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + SLEEK PULLED-BACK HAIR (8-sided low-poly head, y = 1.18 .. 1.69)
    # =========================================================================
    mb.set_part("head_and_hair", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.180,  0.008, 0.145, 0.142),  # 0: chin/jaw base
        (1.265,  0.014, 0.214, 0.200),  # 1: lower cheek
        (1.485,  0.010, 0.218, 0.208),  # 2: brow / forehead top
        (1.605, -0.002, 0.194, 0.196),  # 3: upper crown
        (1.685, -0.010, 0.105, 0.106),  # 4: top cap
    ]
    head_rings = []
    for (y, cz, rx, rz) in head_specs:
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            sq = 1.04
            ring.append(V(rx * math.sin(a) * sq, y, cz + rz * math.cos(a) * sq))
        head_rings.append(ring)

    # Slight hair volume offset on upper/back rings
    for i in (2, 3, 4):
        for k in range(8):
            if i >= 3 or k in (1, 2, 3, 4, 5):
                p = head_rings[i][k]
                head_rings[i][k] = V(p.x * 1.045, p.y, p.z * 1.045)

    def head_color(i, k):
        if i >= 2:
            return HAIR
        if i == 1:
            return SKIN if k in (6, 7, 0) else HAIR
        return HAIR if k in (2, 3, 4) else SKIN

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 8
        c1 = sum(r1, Vector()) / 8
        cmid = (c0 + c1) * 0.5
        for k in range(8):
            kn = (k + 1) % 8
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 2 and k == 7:
                # Crisp inverted-V center hair part flush with crown edge
                part_apex = (p2 + p3) * 0.5
                mb.face([p0, p1, part_apex], SKIN, out=(0, 0, 1))
                mb.face([p0, part_apex, p3], HAIR, out=(0, 0, 1))
                mb.face([p1, p2, part_apex], HAIR, out=(0, 0, 1))
            elif i == 1 and k == 0:
                # Front-left temple (+X): sweeping pulled-back hairline
                p_temple = p1.lerp(p2, 0.44)
                mb.face([p0, p1, p_temple, p3], SKIN, out=(mid - cmid))
                mb.face([p_temple, p2, p3], HAIR, out=(mid - cmid))
            elif i == 1 and k == 6:
                # Front-right temple (-X): mirror of k=0
                p_temple = p0.lerp(p3, 0.44)
                mb.face([p0, p1, p2, p_temple], SKIN, out=(mid - cmid))
                mb.face([p_temple, p2, p3], HAIR, out=(mid - cmid))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    # Top & bottom caps
    rt = head_rings[-1]
    mb.face([rt[7], rt[0], rt[3], rt[4]], HAIR, out=(0, 1, 0))
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR, out=(0, 1, 0))
    mb.face([rt[4], rt[5], rt[6], rt[7]], HAIR, out=(0, 1, 0))

    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. HIGH HAIR BUN (chunky faceted low-poly chignon at upper back of head)
    # =========================================================================
    mb.set_part("hair_bun", bone="Head")
    # Oriented along a gentle upward-back axis from skull attachment (-Z, +Y)
    bun_axis = V(0.0, 0.36, -0.93).normalized()
    bun_u = V(1.0, 0.0, 0.0)
    bun_v = bun_axis.cross(bun_u).normalized()
    bun_base = V(0.0, 1.515, -0.158)
    # (dist_along_axis, rx, ry)
    bun_stations = [
        (0.000, 0.088, 0.088),  # tucked root inside back of hair
        (0.050, 0.132, 0.130),  # expanding base
        (0.125, 0.158, 0.155),  # widest faceted belly
        (0.198, 0.136, 0.132),  # upper taper
        (0.240, 0.074, 0.072),  # faceted crown of bun
    ]
    bun_rings = []
    for (d, rx, ry) in bun_stations:
        c = bun_base + bun_axis * d
        ring = []
        for k in range(7):
            a = 2.0 * math.pi * k / 7.0 + math.pi / 7.0
            ring.append(c + bun_u * (rx * math.sin(a)) + bun_v * (ry * math.cos(a)))
        bun_rings.append(ring)

    def bun_col(i, k):
        return HAIR_SHADE if i == 0 else HAIR

    mb.loft(bun_rings, bun_col, cap_bottom=False, cap_top=True, top_color=HAIR)

    # =========================================================================
    # 3. EARS + GOLD SQUARE EARRINGS (iconic detail from reference!)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.204
        x_out = side * 0.248
        y0, y1 = 1.298, 1.402
        z0, z1 = -0.022, 0.052
        p_out_b = V(x_out, y0 + 0.015, z0 + 0.012)
        p_out_f = V(x_out, y0 + 0.015, z1 - 0.010)
        p_out_t = V(x_out, y1 - 0.015, (z0 + z1) * 0.5)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_out_t, p_out_f], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_out_b, p_out_t], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_out_f, p_out_b], SKIN_SHADE, out=(0, -1, 0))
        mb.face([p_out_b, p_out_f, p_out_t], SKIN, out=(side, 0, 0))

    mb.set_part("earrings", bone="Head")
    # Crisp gold square frame earrings tucked right onto the earlobe
    for side in (-1, 1):
        x_e0 = side * 0.232
        x_e1 = side * 0.254
        xa, xb = min(x_e0, x_e1), max(x_e0, x_e1)
        cy = 1.284
        cz = 0.018
        r_out = 0.032
        r_in = 0.013
        mb.box(xa, xb, cy + r_in, cy + r_out, cz - r_out, cz + r_out, GOLD)
        mb.box(xa, xb, cy - r_out, cy - r_in, cz - r_out, cz + r_out, GOLD_SHADE)
        mb.box(xa, xb, cy - r_in, cy + r_in, cz + r_in, cz + r_out, GOLD)
        mb.box(xa, xb, cy - r_in, cy + r_in, cz - r_out, cz - r_in, GOLD_SHADE)

    # =========================================================================
    # 4. EYES (2 vertical dark pill hexagons, matching person_low style)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.216
    for side in (-1, 1):
        cx = side * 0.068
        cy = 1.388
        rx = 0.020
        ry = 0.048
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
    # 5. NECK (6-sided warm skin cylinder)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.095, 0.004, 0.072, 0.066, n=6, phase=math.pi / 6)
    neck_r1 = oval_ring(0.0, 1.190, 0.006, 0.068, 0.062, n=6, phase=math.pi / 6)
    mb.loft([neck_r0, neck_r1], SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 6. CREAM COLLARED BLOUSE + V-NECK SKIN + TAN WAIST BELT
    # =========================================================================
    mb.set_part("blouse", bone="Torso")
    sx = 0.148
    sz_f = 0.104
    sz_b = -0.092
    # Main front blouse panel (below V-neck skin notch)
    mb.face([V(-sx, 0.675, sz_f), V(sx, 0.675, sz_f),
             V(sx, 1.015, sz_f),  V(-sx, 1.015, sz_f)], BLOUSE, out=(0, 0, 1))
    # Upper front left/right blouse panels flanking the open V-neckline
    v_top_x = 0.064
    v_bot_y = 1.015
    v_top_y = 1.132
    mb.face([V(-sx, v_bot_y, sz_f), V(0.0, v_bot_y, sz_f),
             V(-v_top_x, v_top_y, sz_f), V(-sx, v_top_y, sz_f)], BLOUSE, out=(0, 0, 1))
    mb.face([V(0.0, v_bot_y, sz_f), V(sx, v_bot_y, sz_f),
             V(sx, v_top_y, sz_f), V(v_top_x, v_top_y, sz_f)], BLOUSE, out=(0, 0, 1))
    # Warm skin V-neck triangle at collarbone
    mb.face([V(0.0, v_bot_y, sz_f + 0.001), V(v_top_x, v_top_y, sz_f + 0.001),
             V(-v_top_x, v_top_y, sz_f + 0.001)], SKIN, out=(0, 0, 1))
    # Subtle center placket shade line down blouse front
    mb.face([V(-0.007, 0.675, sz_f + 0.002), V(0.007, 0.675, sz_f + 0.002),
             V(0.007, v_bot_y, sz_f + 0.002), V(-0.007, v_bot_y, sz_f + 0.002)], BLOUSE_SHADE, out=(0, 0, 1))
    # Top shoulder fill under collar
    mb.face([V(-sx, v_top_y, sz_f), V(sx, v_top_y, sz_f),
             V(sx, v_top_y, sz_b),  V(-sx, v_top_y, sz_b)], BLOUSE, out=(0, 1, 0))

    # Crisp pointed shirt collar tabs folding out along the V-neck
    for side in (-1, 1):
        p_neck = V(side * 0.066, 1.134, 0.088)
        p_tip  = V(side * 0.012, 1.028, sz_f + 0.014)
        p_out  = V(side * 0.088, 1.062, sz_f + 0.016)
        p_top  = V(side * 0.092, 1.134, 0.098)
        mb.face([p_tip, p_out, p_top, p_neck], BLOUSE, out=(0, 0.1, 1))
        mb.face([p_neck, p_top, V(side * 0.092, 1.132, sz_f), V(side * 0.064, 1.132, sz_f)],
                BLOUSE_SHADE, out=(0, 1, 0))

    # Warm tan waist belt / blouse tuck accent visible in the lower open blazer
    mb.set_part("belt", bone="Torso")
    mb.box(-0.145, 0.145, 0.665, 0.706, sz_f - 0.004, sz_f + 0.016, BELT, skip=("back",))

    # =========================================================================
    # 7. TAILORED NAVY-SLATE BLAZER (open front, notched lapels, structured hem)
    # =========================================================================
    mb.set_part("blazer", bone="Torso")
    jy0, jy1 = 0.648, 1.140
    j_open_bot = 0.072
    j_open_top = 0.064
    jx_bot = 0.218
    jx_top = 0.198
    jz_fb = 0.130
    jz_ft = 0.120
    jz_bb = -0.124
    jz_bt = -0.114

    # Back panel
    mb.face([V(jx_bot, jy0, jz_bb), V(-jx_bot, jy0, jz_bb),
             V(-jx_top, jy1, jz_bt), V(jx_top, jy1, jz_bt)], BLAZER, out=(0, 0, -1))
    # Back collar stand wrapping solidly around back of neck
    mb.box(-0.084, 0.084, 1.135, 1.170, -0.114, -0.070, BLAZER_SHADE, skip=("bottom",))

    for side in (-1, 1):
        xo_b, xo_t = side * jx_bot, side * jx_top
        xi_b, xi_t = side * j_open_bot, side * j_open_top
        # Outer side panel
        mb.face([V(xo_b, jy0, jz_fb), V(xo_b, jy0, jz_bb),
                 V(xo_t, jy1, jz_bt), V(xo_t, jy1, jz_ft)], BLAZER, out=(side, 0, 0))
        # Front blazer panel
        mb.face([V(xi_b, jy0, jz_fb), V(xo_b, jy0, jz_fb),
                 V(xo_t, jy1, jz_ft), V(xi_t, jy1, jz_ft)], BLAZER, out=(0, 0, 1))
        # Inner thickness edge along front opening
        mb.face([V(xi_b, jy0, sz_f), V(xi_b, jy0, jz_fb),
                 V(xi_t, jy1, jz_ft), V(xi_t, jy1, sz_f)], BLAZER_SHADE, out=(-side, 0, 0))
        # Shoulder top
        mb.face([V(xi_t, jy1, jz_ft), V(xo_t, jy1, jz_ft),
                 V(xo_t, jy1, jz_bt), V(xi_t, jy1, jz_bt)], BLAZER, out=(0, 1, 0))
        # Bottom hem underside
        mb.face([V(xi_b, jy0, jz_bb), V(xo_b, jy0, jz_bb),
                 V(xo_b, jy0, jz_fb), V(xi_b, jy0, jz_fb)], BLAZER_SHADE, out=(0, -1, 0))

        # Tailored folded blazer lapel along the upper-mid front opening
        lp_b  = V(side * 0.070, 0.805, jz_fb + 0.010)
        lp_o  = V(side * 0.132, 0.995, jz_ft + 0.016)
        lp_t  = V(side * 0.095, 1.142, jz_ft + 0.008)
        lp_in = V(side * 0.064, 1.140, jz_ft + 0.004)
        mb.face([lp_b, lp_o, lp_t, lp_in], BLAZER_LAPEL, out=(0, 0, 1))
        # Subtle bevel edge on outer lapel
        mb.face([lp_b, V(side * 0.072, 0.805, jz_fb),
                 V(side * 0.132, 0.995, jz_ft), lp_o], BLAZER_SHADE, out=(side, 0, 0.2))
        mb.face([lp_o, V(side * 0.132, 0.995, jz_ft),
                 V(side * 0.095, 1.140, jz_ft), lp_t], BLAZER_SHADE, out=(side, 0.3, 0.2))

    # Center back hem underside & top back fill
    mb.face([V(-j_open_bot, jy0, jz_bb), V(j_open_bot, jy0, jz_bb),
             V(j_open_bot, jy0, sz_b),   V(-j_open_bot, jy0, sz_b)], BLAZER_SHADE, out=(0, -1, 0))
    mb.face([V(-j_open_top, jy1, sz_b),  V(j_open_top, jy1, sz_b),
             V(j_open_top, jy1, jz_bt),  V(-j_open_top, jy1, jz_bt)], BLAZER, out=(0, 1, 0))

    # =========================================================================
    # 8. TEAL LANYARD + SILVER CLIP + PHOTO ID BADGE (iconic commuter detail!)
    # =========================================================================
    mb.set_part("lanyard", bone="Torso")
    # Two flat teal ribbon straps descending in a V from under the shirt collar to the clip
    z_lan_top = sz_f + 0.015
    z_lan_bot = sz_f + 0.022
    for side in (-1, 1):
        p_t0 = V(side * 0.056, 1.118, z_lan_top)
        p_t1 = V(side * 0.074, 1.118, z_lan_top)
        p_b0 = V(side * 0.004, 0.892, z_lan_bot)
        p_b1 = V(side * 0.022, 0.896, z_lan_bot)
        mb.face([p_b0, p_b1, p_t1, p_t0], LANYARD, out=(0, 0, 1))
        # Thickness depth back toward shirt so it reads cleanly from 3/4 angles
        mb.face([p_t1, p_b1, V(p_b1.x, p_b1.y, sz_f + 0.003), V(p_t1.x, p_t1.y, sz_f + 0.003)],
                LANYARD, out=(side, 0, 0))
        mb.face([p_b0, p_t0, V(p_t0.x, p_t0.y, sz_f + 0.003), V(p_b0.x, p_b0.y, sz_f + 0.003)],
                LANYARD, out=(-side, 0, 0))

    # Silver lanyard clasp / clip
    mb.set_part("badge", bone="Torso")
    z_bg0 = sz_f + 0.010
    z_bg1 = sz_f + 0.028
    mb.box(-0.015, 0.015, 0.864, 0.902, z_bg0 + 0.002, z_bg1 + 0.002, CLIP)

    # Cream rectangular photo ID badge hanging at lower chest / waist (y = 0.728 .. 0.866)
    mb.box(-0.054, 0.054, 0.728, 0.866, z_bg0, z_bg1, BADGE_BG)
    # Warm peach portrait square + subtle text line detail on front face of badge
    z_bf = z_bg1 + 0.002
    mb.face([V(-0.036, 0.780, z_bf), V(0.018, 0.780, z_bf),
             V(0.018, 0.844, z_bf),  V(-0.036, 0.844, z_bf)], BADGE_PHOTO, out=(0, 0, 1))
    mb.face([V(-0.036, 0.748, z_bf), V(0.036, 0.748, z_bf),
             V(0.036, 0.764, z_bf),  V(-0.036, 0.764, z_bf)], BADGE_LINE, out=(0, 0, 1))

    # =========================================================================
    # 9. LEFT ARM (Arm_L, +X): BENT FORWARD HOLDING TAKEAWAY COFFEE CUP
    # =========================================================================
    mb.set_part("sleeves")
    mb.set_bone("Arm_L")
    # Two-segment bent blazer sleeve: tucked seamlessly into shoulder -> elbow -> wrist
    p_l_sh = V(0.168, 1.078, -0.002)
    p_l_el = V(0.256, 0.848,  0.036)
    p_l_wr = V(0.228, 0.858,  0.222)

    def build_bent_sleeve(p_sh, p_el, p_wr, bone_name):
        mb.set_bone(bone_name)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def aligned_ring(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            u = u.normalized()
            v = axis.cross(u).normalized()
            return [
                ctr + u * (-rx) + v * ( rperp),
                ctr + u * ( rx) + v * ( rperp),
                ctr + u * ( rx) + v * (-rperp),
                ctr + u * (-rx) + v * (-rperp),
            ]

        ax_mid = (ax1 + ax2).normalized()
        r_sh  = aligned_ring(p_sh, ax1, 0.072, 0.082)
        r_u   = aligned_ring(p_sh.lerp(p_el, 0.65), ax1, 0.078, 0.084)
        r_el  = aligned_ring(p_el, ax_mid, 0.084, 0.088)
        r_f   = aligned_ring(p_el.lerp(p_wr, 0.78), ax2, 0.082, 0.086)
        r_cuf = aligned_ring(p_wr, ax2, 0.068, 0.072)
        mb.loft([r_sh, r_u, r_el, r_f, r_cuf], BLAZER, cap_bottom=False, cap_top=True, top_color=BLAZER_SHADE)

    build_bent_sleeve(p_l_sh, p_l_el, p_l_wr, "Arm_L")

    # =========================================================================
    # 10. RIGHT ARM (Arm_R, -X): GENTLE COMMUTER BEND AT SIDE IN FRONT OF PURSE
    # =========================================================================
    p_r_sh = V(-0.168, 1.078,  0.002)
    p_r_el = V(-0.268, 0.858, -0.008)
    p_r_wr = V(-0.256, 0.742,  0.126)
    build_bent_sleeve(p_r_sh, p_r_el, p_r_wr, "Arm_R")

    # =========================================================================
    # 11. HANDS (Left hand gripping coffee cup; Right hand blocky commuter mitten)
    # =========================================================================
    mb.set_part("hands")
    # Left hand (Arm_L) wrapping around outer/front side of coffee cup
    mb.set_bone("Arm_L")
    hl_specs = [
        (0.228, 0.858, 0.218, 0.044, 0.044),
        (0.236, 0.858, 0.280, 0.054, 0.056),
        (0.220, 0.856, 0.336, 0.042, 0.044),
    ]
    hl_rings = []
    for (cx, cy, cz, rx, ry) in hl_specs:
        hl_rings.append([
            V(cx - rx, cy - ry, cz),
            V(cx + rx, cy - ry, cz),
            V(cx + rx, cy + ry, cz),
            V(cx - rx, cy + ry, cz),
        ])
    mb.loft(hl_rings, SKIN, cap_bottom=False, cap_top=True, top_color=SKIN)

    # Right hand (Arm_R) chunky low-poly mitten aligned along forearm axis
    mb.set_bone("Arm_R")
    r_ax = (p_r_wr - p_r_el).normalized()
    r_u = V(1.0, 0.0, 0.0) - r_ax * r_ax.x
    r_u = r_u.normalized()
    r_v = r_ax.cross(r_u).normalized()
    hr_stations = [
        (0.000, 0.044, 0.046),
        (0.068, 0.056, 0.060),
        (0.118, 0.038, 0.042),
    ]
    hr_rings = []
    for (dist, ru, rv) in hr_stations:
        c = p_r_wr + r_ax * dist
        hr_rings.append([
            c + r_u * (-ru) + r_v * ( rv),
            c + r_u * ( ru) + r_v * ( rv),
            c + r_u * ( ru) + r_v * (-rv),
            c + r_u * (-ru) + r_v * (-rv),
        ])
    mb.loft(hr_rings, SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 12. TAKEAWAY COFFEE CUP (bone Coffee, child of Arm_L)
    # =========================================================================
    mb.set_part("coffee_cup", bone="Coffee")
    cup_x = 0.184
    cup_z = 0.296
    # Cup base -> below sleeve -> sleeve -> above sleeve -> rim -> dark lid
    c_bot  = oval_ring(cup_x, 0.768, cup_z, 0.046, 0.046, n=8, phase=math.pi / 8)
    c_s0   = oval_ring(cup_x, 0.818, cup_z, 0.052, 0.052, n=8, phase=math.pi / 8)
    c_s1   = oval_ring(cup_x, 0.908, cup_z, 0.060, 0.060, n=8, phase=math.pi / 8)
    c_top  = oval_ring(cup_x, 0.958, cup_z, 0.065, 0.065, n=8, phase=math.pi / 8)

    # White paper cup body (lower & upper exposed portions)
    mb.loft([c_bot, c_s0], CUP_WHITE, cap_bottom=True, cap_top=False, bot_color=CUP_WHITE)
    mb.loft([c_s1, c_top], CUP_WHITE, cap_bottom=False, cap_top=False)

    # Kraft cardboard sleeve slightly proud (+0.004) over mid-cup
    sl_0 = oval_ring(cup_x, 0.816, cup_z, 0.056, 0.056, n=8, phase=math.pi / 8)
    sl_1 = oval_ring(cup_x, 0.910, cup_z, 0.064, 0.064, n=8, phase=math.pi / 8)
    mb.loft([sl_0, sl_1], CUP_SLEEVE, cap_bottom=True, cap_top=True,
            bot_color=CUP_SLEEVE, top_color=CUP_SLEEVE)

    # Dark espresso travel lid with overhanging brim + raised drinking tier
    lid_b0 = oval_ring(cup_x, 0.954, cup_z, 0.072, 0.072, n=8, phase=math.pi / 8)
    lid_b1 = oval_ring(cup_x, 0.978, cup_z, 0.073, 0.073, n=8, phase=math.pi / 8)
    lid_t0 = oval_ring(cup_x, 0.980, cup_z, 0.063, 0.063, n=8, phase=math.pi / 8)
    lid_t1 = oval_ring(cup_x, 1.004, cup_z, 0.059, 0.059, n=8, phase=math.pi / 8)
    mb.loft([lid_b0, lid_b1], CUP_LID, cap_bottom=True, cap_top=False, bot_color=CUP_LID)
    mb.loft([lid_b1, lid_t0], CUP_LID_TOP, cap_bottom=False, cap_top=False)
    mb.loft([lid_t0, lid_t1], CUP_LID, cap_bottom=False, cap_top=True, top_color=CUP_LID_TOP)

    # =========================================================================
    # 13. SHOULDER TOTE BAG / PURSE (bone Purse, child of Torso, right side -X)
    # =========================================================================
    mb.set_part("purse", bone="Purse")
    # Structured boxy low-poly leather tote bag hanging on right hip / slightly back (-X, -Z)
    # Tilted slightly backward (~14 deg) just like the reference silhouette, clear of Arm_R swing!
    bag_tilt = math.radians(-14.0)
    ct, st = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_orig = V(-0.292, 0.675, -0.172)

    def bag_pt(lx, ly, lz):
        ry = ly * ct - lz * st
        rz = ly * st + lz * ct
        return V(bag_orig.x + lx, bag_orig.y + ry, bag_orig.z + rz)

    # Tapered tote body: wider at top opening, slightly narrower/fuller at bottom
    bag_stations = [
        # (ly,    x_in,   x_out,  z_back, z_front)
        (-0.155,  0.050, -0.068, -0.142,  0.142),  # bottom base
        (-0.120,  0.064, -0.084, -0.166,  0.166),  # lower bevel
        ( 0.145,  0.058, -0.076, -0.178,  0.178),  # top rim
    ]
    bag_rings = []
    for (ly, xi, xo, zb, zf) in bag_stations:
        bag_rings.append([
            bag_pt(xo, ly, zb),
            bag_pt(xi, ly, zb),
            bag_pt(xi, ly, zf),
            bag_pt(xo, ly, zf),
        ])
    mb.loft(bag_rings, PURSE, cap_bottom=True, cap_top=False, bot_color=PURSE_DARK)

    # Recessed dark top opening rim of tote bag
    top_outer = bag_rings[-1]
    top_inner = [
        bag_pt(-0.052, 0.145, -0.156),
        bag_pt( 0.038, 0.145, -0.156),
        bag_pt( 0.038, 0.145,  0.156),
        bag_pt(-0.052, 0.145,  0.156),
    ]
    top_deep = [
        bag_pt(-0.048, 0.110, -0.152),
        bag_pt( 0.034, 0.110, -0.152),
        bag_pt( 0.034, 0.110,  0.152),
        bag_pt(-0.048, 0.110,  0.152),
    ]
    for k in range(4):
        kn = (k + 1) % 4
        mb.face([top_outer[k], top_outer[kn], top_inner[kn], top_inner[k]], PURSE, out=(0, 1, 0))
        mb.face([top_inner[k], top_inner[kn], top_deep[kn], top_deep[k]], PURSE_DARK, out=(0, 0.2, 0))
    mb.face(top_deep, PURSE_DARK, out=(0, 1, 0))

    # Continuous shoulder strap looping seamlessly from bag front -> over shoulder -> bag back
    # hugs blazer shoulder cleanly with zero seam spike and clears right sleeve during walk!
    mb.set_part("purse_strap", bone="Purse")
    strap_loop = [
        bag_pt(-0.008, 0.130,  0.105),
        V(-0.236, 0.905,  0.025),
        V(-0.210, 1.060,  0.095),
        V(-0.188, 1.142,  0.042),
        V(-0.182, 1.148, -0.025),
        V(-0.200, 1.115, -0.115),
        V(-0.244, 0.985, -0.185),
        bag_pt(-0.008, 0.130, -0.105),
    ]
    strap_norms = [
        V(-1.0, 0.0,  0.2),
        V(-0.9, 0.0,  0.4),
        V(-0.6, 0.2,  0.8),
        V(-0.3, 0.8,  0.5),
        V(-0.2, 1.0, -0.1),
        V(-0.3, 0.6, -0.7),
        V(-0.7, 0.1, -0.7),
        V(-1.0, 0.0, -0.2),
    ]
    mb.ribbon_path(strap_loop, strap_norms, half_w=0.024, half_t=0.010, color=PURSE_STRAP)

    # =========================================================================
    # 14. WIDE-LEG CROPPED CHARCOAL TROUSERS
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.190, 0.190, 0.548, 0.680, -0.104, 0.104, PANTS, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        # Wide tailored culotte / cropped trouser flare matching reference silhouette
        x_in_t  = side * 0.010
        x_out_t = side * 0.188
        x_in_b  = side * 0.064
        x_out_b = side * 0.238
        rz_t = 0.098
        rz_b = 0.098
        r_top = [
            V(min(x_in_t, x_out_t), 0.582,  rz_t),
            V(max(x_in_t, x_out_t), 0.582,  rz_t),
            V(max(x_in_t, x_out_t), 0.582, -rz_t),
            V(min(x_in_t, x_out_t), 0.582, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.205,  rz_b),
            V(max(x_in_b, x_out_b), 0.205,  rz_b),
            V(max(x_in_b, x_out_b), 0.205, -rz_b),
            V(min(x_in_b, x_out_b), 0.205, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 15. ANKLES (warm peach skin peeking cleanly above loafers)
    # =========================================================================
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.152
        mb.box(cx - 0.044, cx + 0.044, 0.120, 0.212, -0.046, 0.046, SKIN, skip=("top", "bottom"))

    # =========================================================================
    # 16. CREAM SLIP-ON LOAFERS WITH TAN SOLES
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.152
        w = 0.068
        w_toe = 0.056
        z_heel = -0.090
        z_mid  =  0.060
        z_toe  =  0.158
        y_sole0 = 0.000
        y_sole1 = 0.032
        y_toe_top = 0.076
        y_collar  = 0.130

        sole_bot = [
            V(cx - w,     y_sole0, z_heel),
            V(cx + w,     y_sole0, z_heel),
            V(cx + w_toe, y_sole0, z_toe),
            V(cx - w_toe, y_sole0, z_toe),
        ]
        sole_top = [
            V(cx - w,     y_sole1, z_heel),
            V(cx + w,     y_sole1, z_heel),
            V(cx + w_toe, y_sole1, z_toe),
            V(cx - w_toe, y_sole1, z_toe),
        ]
        mb.loft([sole_bot, sole_top], SOLE, cap_bottom=True, cap_top=False, bot_color=SOLE)

        p_bl_h = V(cx - w,     y_sole1, z_heel)
        p_br_h = V(cx + w,     y_sole1, z_heel)
        p_bl_t = V(cx - w_toe, y_sole1, z_toe)
        p_br_t = V(cx + w_toe, y_sole1, z_toe)

        p_tl_h = V(cx - w * 0.88, y_collar, z_heel + 0.012)
        p_tr_h = V(cx + w * 0.88, y_collar, z_heel + 0.012)
        p_tl_m = V(cx - w * 0.88, y_collar, z_mid)
        p_tr_m = V(cx + w * 0.88, y_collar, z_mid)

        p_tl_t = V(cx - w_toe * 0.90, y_toe_top, z_toe - 0.014)
        p_tr_t = V(cx + w_toe * 0.90, y_toe_top, z_toe - 0.014)

        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], SHOE, out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], SHOE, out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], SHOE_VAMP, out=(0, 1, 0.5))
        mb.face([p_tl_m, p_tr_m, p_tr_h, p_tl_h], SHOE, out=(0, 1, 0))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], SHOE, out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h], SHOE, out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], SHOE, out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m], SHOE, out=(1, 0, 0))

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


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: brisk commuter stride, steady coffee hand, gently swaying purse."""
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

        # Brisk, confident commuter stride with crisp vertical bob
        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        root_pitch = -0.055
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.072 * s1, 0.038 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_pitch = -0.022 * c2
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (torso_pitch, 0.105 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.042 + 0.024 * c2, -0.045 * s1, -0.015 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp wide-trouser stride
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.44 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.036, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.44 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.036, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Left arm holds the hot coffee steady: controlled small bounce & swing
        arm_l_pitch = 0.11 * s1 - 0.02 * c2
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_pitch, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotate Coffee cup so it stays upright and never spills
        pb_coffee = rig.pose.bones["Coffee"]
        pb_coffee.rotation_euler = (-(arm_l_pitch + torso_pitch + root_pitch), 0.0, -0.018 * c1)
        pb_coffee.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm swings cleanly in front of the shoulder purse
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.20 * s1 + 0.05, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Shoulder tote bag trails slightly with natural pendulum sway
        pb_purse = rig.pose.bones["Purse"]
        pb_purse.rotation_euler = (0.065 * math.sin(phi - 0.55), 0.0, 0.025 * c1)
        pb_purse.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: poised commuter breathing, glance around, subtle coffee lift & purse settle."""
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

        # Subtle weight shift & calm breathing
        pb_root = rig.pose.bones["Root"]
        root_pitch = -0.012
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (root_pitch, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_pitch = -0.024 * s2
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (torso_pitch, 0.030 * s1, -0.016 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert commuter glance (checking arrival board / ferry)
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * s2, 0.21 * s1, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs stay grounded
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm holds coffee with gentle lift-and-settle breath; cup stays level
        arm_l_pitch = 0.075 * s2 - 0.040 * (1.0 - c1) * 0.5
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_pitch, 0.0, 0.016 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_coffee = rig.pose.bones["Coffee"]
        pb_coffee.rotation_euler = (-(arm_l_pitch + torso_pitch + root_pitch), 0.0, -0.018 * s1)
        pb_coffee.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm gentle relaxed drift
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.045 * s1, 0.0, -0.016 * s2)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Purse hangs calmly with gentle counter-settle
        pb_purse = rig.pose.bones["Purse"]
        pb_purse.rotation_euler = (0.022 * s2, 0.0, -0.020 * s1)
        pb_purse.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 9-bone rig (7 standard passenger bones + Coffee & Purse) with Walk and Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonBusinessRig")
    rig = bpy.data.objects.new("PersonBusinessRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",   None,    ( 0.000, 0.620,  0.000), ( 0.000, 0.720,  0.000)),
        ("Torso",  "Root",  ( 0.000, 0.675,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",   "Torso", ( 0.000, 1.150,  0.000), ( 0.000, 1.460,  0.000)),
        ("Arm_L",  "Torso", ( 0.184, 1.068,  0.000), ( 0.184, 1.228,  0.000)),
        ("Coffee", "Arm_L", ( 0.184, 0.860,  0.296), ( 0.184, 1.010,  0.296)),
        ("Arm_R",  "Torso", (-0.184, 1.068,  0.000), (-0.184, 1.228,  0.000)),
        ("Purse",  "Torso", (-0.185, 1.135, -0.010), (-0.185, 1.295, -0.010)),
        ("Leg_L",  "Root",  ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R",  "Root",  (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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

    # Push both actions onto NLA tracks so glTF exports both "Walk" and "Idle" cleanly
    for act, end_f in ((walk_action, 25), (idle_action, 49)):
        track = rig.animation_data.nla_tracks.new()
        track.name = act.name
        strip = track.strips.new(act.name, 1, act)
        strip.action_frame_start = 1
        strip.action_frame_end = end_f
        track.mute = True

    # Leave Walk active on the rig for default viewport playback
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

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-1.68, math.radians(58)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (showing bun, earring, purse, coffee)
        ( 1.68, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 4.7
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.14)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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

    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, -0.001))
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.15
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.2
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.15)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=42, zrot_right_deg=90):
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
    cam_data.ortho_scale = 2.95
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
            left_obj.location = (-0.66, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.66, 0.0, 0.0)
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


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_SHADE],
    "top": [BLAZER, BLAZER_SHADE, BLAZER_LAPEL],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [PURSE, PURSE_DARK, PURSE_STRAP],
}


def main():
    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonBusiness")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonBusiness")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonBusiness", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)

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
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=35)
    render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)
    render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=35, zrot_right_deg=90)

    print("=== PersonBusiness Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:16s}: {cnt}")
    print(f"Saved blend:     {BLEND_PATH}")
    print(f"Exported glb:    {GLB_PATH}")
    print(f"Preview png:     {PREVIEW_PATH}")
    print(f"Walk preview:    {WALK_PREVIEW_PATH}")
    print(f"Idle preview:    {IDLE_PREVIEW_PATH}")
    print(f"Walk video:      {WALK_VIDEO_PATH}")
    print(f"Idle video:      {IDLE_VIDEO_PATH}")


if __name__ == "__main__":
    main()
