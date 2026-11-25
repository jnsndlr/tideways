# Builds an ultra-low-poly (< 350 tris) stylized biker girl with cycling helmet,
# chunky braided ponytail, teal 3/4-sleeve cycling jacket with hi-vis cuff stripes,
# dark cycling gloves, backpack, bike shorts, white socks, and grey sneakers in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_biker.py)
# Saves art/person_biker.blend, exports assets/models/person_biker.glb (rigged + Walk & Idle cycles),
# renders art/person_biker_preview.png, art/person_biker_walk_preview.png, art/person_biker_idle_preview.png,
# and outputs rendered videos art/person_biker_walk.mp4 and art/person_biker_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.71 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import subprocess
import sys
import tempfile
import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_biker.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_biker.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_biker_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_biker_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_biker_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_biker_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_biker_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette closely matched to reference biker girl image (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN           = col_srgb(0.95, 0.72, 0.49)
SKIN_SHADE     = col_srgb(0.84, 0.61, 0.39)
EYE            = col_srgb(0.11, 0.10, 0.11)

HAIR_DARK      = col_srgb(0.49, 0.30, 0.17)
HAIR_MID       = col_srgb(0.60, 0.39, 0.23)
HAIR_SHADE     = col_srgb(0.37, 0.22, 0.12)

HELMET         = col_srgb(0.95, 0.92, 0.87)
HELMET_SHADE   = col_srgb(0.89, 0.86, 0.81)
HELMET_VENT    = col_srgb(0.19, 0.19, 0.21)
HELMET_RIM     = col_srgb(0.24, 0.24, 0.26)
STRAP          = col_srgb(0.21, 0.20, 0.22)

JACKET         = col_srgb(0.30, 0.62, 0.56)
JACKET_SHADE   = col_srgb(0.23, 0.51, 0.46)
JACKET_ZIP     = col_srgb(0.21, 0.45, 0.42)
CUFF_STRIPE    = col_srgb(0.79, 0.88, 0.31)

GLOVE          = col_srgb(0.22, 0.22, 0.24)
GLOVE_SHADE    = col_srgb(0.16, 0.16, 0.18)

PACK           = col_srgb(0.29, 0.28, 0.30)
PACK_SHADE     = col_srgb(0.22, 0.21, 0.23)
PACK_POCKET    = col_srgb(0.34, 0.33, 0.35)
PACK_STRAP     = col_srgb(0.25, 0.24, 0.26)

SHORTS         = col_srgb(0.24, 0.25, 0.29)
SHORTS_SHADE   = col_srgb(0.17, 0.18, 0.22)

SOCK           = col_srgb(0.96, 0.94, 0.90)
SOCK_SHADE     = col_srgb(0.87, 0.85, 0.81)

SHOE           = col_srgb(0.57, 0.56, 0.57)
SHOE_VAMP      = col_srgb(0.63, 0.62, 0.63)
SOLE           = col_srgb(0.24, 0.23, 0.24)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR_DARK, HAIR_MID, HAIR_SHADE],
    "top": [JACKET, JACKET_SHADE, JACKET_ZIP],
    "bottom": [SHORTS, SHORTS_SHADE],
    "accent": [HELMET, HELMET_SHADE],
}


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
        self.current_weights = {"Root": 1.0}
        self.vert_weights = []

    def set_part(self, name, bone=None):
        self.current_part = name
        self.part_tris.setdefault(name, 0)
        if bone is not None:
            self.set_bone(bone)

    def set_bone(self, bone):
        if isinstance(bone, dict):
            self.current_weights = dict(bone)
        else:
            self.current_weights = {bone: 1.0}

    def face(self, pts, color, out=None, weights=None):
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
                if weights is not None:
                    weights = list(reversed(weights))
        vs = [self.bm.verts.new(G(p)) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            for v in vs:
                self.bm.verts.remove(v)
            return None
        for idx, _ in enumerate(vs):
            w = weights[idx] if weights is not None else self.current_weights
            self.vert_weights.append(dict(w))
        f.smooth = False
        for loop in f.loops:
            loop[self.cl] = color
        self.part_tris[self.current_part] = self.part_tris.get(self.current_part, 0) + (len(pts) - 2)
        return f

    def loft(self, rings, colors, cap_bottom=False, cap_top=False,
             bot_color=None, top_color=None, skip_k=(), ring_weights=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            w0 = ring_weights[i] if ring_weights is not None else None
            w1 = ring_weights[i + 1] if ring_weights is not None else None
            fw = [w0, w0, w1, w1] if ring_weights is not None else None
            for k in range(n):
                if k in skip_k:
                    continue
                kn = (k + 1) % n
                p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
                col = colors(i, k) if callable(colors) else colors
                mid = (p0 + p1 + p2 + p3) * 0.25
                self.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=fw)
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            wb = [ring_weights[0]] * 4 if ring_weights is not None else None
            if n <= 4:
                self.face(r0, col, out=out_dir, weights=([ring_weights[0]] * n if ring_weights is not None else None))
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=wb)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=wb)
            else:
                for k in range(n):
                    wt = [ring_weights[0]] * 3 if ring_weights is not None else None
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=wt)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt4 = [ring_weights[-1]] * 4 if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([ring_weights[-1]] * n if ring_weights is not None else None))
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=wt4)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=wt4)
            else:
                for k in range(n):
                    wt3 = [ring_weights[-1]] * 3 if ring_weights is not None else None
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=wt3)

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


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=6, phase=math.pi / 6.0, front_ext=0.0, back_ext=0.0):
    """Ring tilted backward around X by tilt_rad (higher at +Z front, lower at -Z back),
    with optional aero elongation at the front (+Z) and rear (-Z)."""
    pts = []
    ct, st = math.cos(tilt_rad), math.sin(tilt_rad)
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        lx = rx * math.sin(a)
        cz_raw = math.cos(a)
        lz = rz * cz_raw
        if cz_raw > 0:
            lz += front_ext * cz_raw
        else:
            lz += back_ext * cz_raw  # cz_raw < 0 -> pushes backward (-Z)
        py = cy + lz * st
        pz = cz + lz * ct
        pts.append(V(cx + lx, py, pz))
    return pts


def quad_bilerp(p0, p1, p2, p3, u, v):
    """Bilinear interpolation on quad (p0, p1, p2, p3) where u runs p0->p1 and v runs p0->p3."""
    bot = p0.lerp(p1, u)
    top = p3.lerp(p2, u)
    return bot.lerp(top, v)


def quad_out_normal(p0, p1, p2, p3, ref_center):
    n = (p1 - p0).cross(p2 - p0)
    if n.length < 1e-12:
        n = (p2 - p0).cross(p3 - p0)
    n.normalize()
    mid = (p0 + p1 + p2 + p3) * 0.25
    if n.dot(mid - ref_center) < 0:
        n = -n
    return n


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD (6-sided stylized low-poly head + swept temple hair = 30 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.214,  0.016, 0.156, 0.146),  # 0: chin/jaw
        (1.292,  0.020, 0.208, 0.198),  # 1: lower cheek
        (1.488,  0.008, 0.206, 0.196),  # 2: brow / hairline tucked under helmet
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        # Front face (k=5) and cheeks (k=0, 4) are warm peach skin;
        # behind ears and back of head (k=1, 2, 3) are warm chestnut hair.
        return SKIN if k in (4, 5, 0) else HAIR_DARK

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)
    # Front chin underside cap (rear half is buried directly above neck/collar = 2 tris)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # Chestnut hair temple sweeps framing forehead under helmet front edge (2 tris)
    r1, r2 = head_rings[1], head_rings[2]
    mb.face([
        r2[0].lerp(r2[1], 0.10) + V(0.003, 0.0, 0.003),
        r2[1] + V(0.004, 0.0, 0.0),
        r1[1].lerp(r2[1], 0.34) + V(0.004, 0.0, 0.0),
    ], HAIR_DARK, out=(0.85, 0.0, 0.5))
    mb.face([
        r2[5].lerp(r2[4], 0.10) + V(-0.003, 0.0, 0.003),
        r2[4] + V(-0.004, 0.0, 0.0),
        r1[4].lerp(r2[4], 0.34) + V(-0.004, 0.0, 0.0),
    ], HAIR_DARK, out=(-0.85, 0.0, 0.5))

    # =========================================================================
    # 2. NECK (3-sided tapered cylinder skipping rear quad behind collar = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.114, 0.008, 0.070, 0.066, n=3, phase=0.0)
    neck_r1 = oval_ring(0.0, 1.220, 0.012, 0.066, 0.062, n=3, phase=0.0)
    # phase=0, n=3 -> k=0 (front-left), k=1 (back, skipped), k=2 (front-right)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 3. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.197
    for side in (-1, 1):
        cx = side * 0.062
        cy = 1.388
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
    # 4. EARS (2 chunky rounded low-poly ear tabs = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.194
        x_out = side * 0.232
        y0, y1 = 1.320, 1.398
        z0, z1 = -0.016, 0.044
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.014, zm)
        p_ot = V(x_out, y1 - 0.014, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 5. CYCLING HELMET + DARK RIM + 7 VENTS + Y-STRAP (28 + 10 + 10 + 8 = 56 tris)
    # =========================================================================
    mb.set_part("helmet", bone="Head")
    helm_tilt = math.radians(14.0)
    # Sleek aero-elongated off-white cycling helmet dome sitting snugly over brow & nape
    h_r0 = tilted_ring(0.0, 1.474, -0.008, 0.238, 0.244, helm_tilt, front_ext=0.022, back_ext=0.022)
    h_r1 = tilted_ring(0.0, 1.600, -0.018, 0.214, 0.222, helm_tilt, front_ext=0.014, back_ext=0.014)
    h_r2 = tilted_ring(0.0, 1.692, -0.024, 0.118, 0.130, helm_tilt, front_ext=0.006, back_ext=0.006)
    h_rings = [h_r0, h_r1, h_r2]

    def helmet_color(i, k):
        # Subtle warm shade on rear/lower flank facets; bright ivory on top & front
        if i == 0 and k in (1, 2, 3):
            return HELMET_SHADE
        return HELMET

    mb.loft(h_rings, helmet_color, cap_bottom=False, cap_top=True, top_color=HELMET)

    # Dark charcoal lower inner shell rim peeking below outer white shell (5 quads = 10 tris)
    h_rim = tilted_ring(0.0, 1.450, -0.008, 0.218, 0.224, helm_tilt, front_ext=0.002, back_ext=0.012)
    mb.loft([h_rim, h_r0], HELMET_RIM, cap_bottom=False, cap_top=False, skip_k=(5,))

    # 6 crisp dark cycling helmet vents flush on the shell (+0.0045 along facet normal = 10 tris)
    mb.set_part("helmet_vents", bone="Head")
    helm_center = V(0.0, 1.540, -0.015)

    def add_vent_quad(band_idx, k, u0, u1, v0, v1, inset_top=0.0):
        r_lo, r_hi = h_rings[band_idx], h_rings[band_idx + 1]
        kn = (k + 1) % 6
        p0, p1, p2, p3 = r_lo[k], r_lo[kn], r_hi[kn], r_hi[k]
        n = quad_out_normal(p0, p1, p2, p3, helm_center)
        off = n * 0.0045
        q0 = quad_bilerp(p0, p1, p2, p3, u0, v0) + off
        q1 = quad_bilerp(p0, p1, p2, p3, u1, v0) + off
        q2 = quad_bilerp(p0, p1, p2, p3, u1 - inset_top, v1) + off
        q3 = quad_bilerp(p0, p1, p2, p3, u0 + inset_top, v1) + off
        mb.face([q0, q1, q2, q3], HELMET_VENT, out=n)

    def add_vent_tri(band_idx, k, uv0, uv1, uv2):
        r_lo, r_hi = h_rings[band_idx], h_rings[band_idx + 1]
        kn = (k + 1) % 6
        p0, p1, p2, p3 = r_lo[k], r_lo[kn], r_hi[kn], r_hi[k]
        n = quad_out_normal(p0, p1, p2, p3, helm_center)
        off = n * 0.0045
        t0 = quad_bilerp(p0, p1, p2, p3, uv0[0], uv0[1]) + off
        t1 = quad_bilerp(p0, p1, p2, p3, uv1[0], uv1[1]) + off
        t2 = quad_bilerp(p0, p1, p2, p3, uv2[0], uv2[1]) + off
        mb.face([t0, t1, t2], HELMET_VENT, out=n)

    # Prominent upper-front side vents (left k=0, right k=4 on upper band = 4 tris)
    add_vent_quad(1, 0, 0.16, 0.80, 0.14, 0.72, inset_top=0.06)
    add_vent_quad(1, 4, 0.20, 0.84, 0.14, 0.72, inset_top=0.06)
    # Rear-side lower aero vents (left k=1, right k=3 on lower band = 4 tris)
    add_vent_quad(0, 1, 0.20, 0.76, 0.24, 0.78, inset_top=0.04)
    add_vent_quad(0, 3, 0.24, 0.80, 0.24, 0.78, inset_top=0.04)
    # Front-brow twin aero vents (k=5 upper band = 2 tris)
    add_vent_tri(1, 5, (0.10, 0.20), (0.42, 0.22), (0.28, 0.76))
    add_vent_tri(1, 5, (0.58, 0.22), (0.90, 0.20), (0.72, 0.76))

    # Dark helmet chin strap hugging cheek & jaw facets flush + under-chin clasp (9 tris)
    mb.set_part("chin_strap", bone="Head")
    head_ctr = V(0.0, 1.350, 0.016)
    r0, r1, r2 = head_rings[0], head_rings[1], head_rings[2]
    for (k, u_top_a, u_top_b, u_mid_a, u_mid_b, u_bot_a, u_bot_b) in (
        # k=0 (left cheek, u=0 front-corner -> u=1 mid-side ear)
        (0, 0.64, 0.78, 0.60, 0.74, 0.14, 0.34),
        # k=4 (right cheek, u=0 mid-side ear -> u=1 front-corner)
        (4, 0.22, 0.36, 0.26, 0.40, 0.66, 0.86),
    ):
        kn = (k + 1) % 6
        # Upper cheek segment (brow/helmet down to lower cheek)
        n_hi = quad_out_normal(r1[k], r1[kn], r2[kn], r2[k], head_ctr)
        o_hi = n_hi * 0.0045
        p_m0 = quad_bilerp(r1[k], r1[kn], r2[kn], r2[k], u_mid_a, 0.0) + o_hi
        p_m1 = quad_bilerp(r1[k], r1[kn], r2[kn], r2[k], u_mid_b, 0.0) + o_hi
        p_t1 = quad_bilerp(r1[k], r1[kn], r2[kn], r2[k], u_top_b, 0.94) + o_hi
        p_t0 = quad_bilerp(r1[k], r1[kn], r2[kn], r2[k], u_top_a, 0.94) + o_hi
        mb.face([p_m0, p_m1, p_t1, p_t0], STRAP, out=n_hi)

        # Lower jaw segment (lower cheek curving forward & down along jaw to chin)
        n_lo = quad_out_normal(r0[k], r0[kn], r1[kn], r1[k], head_ctr)
        o_lo = n_lo * 0.0045
        p_b0 = quad_bilerp(r0[k], r0[kn], r1[kn], r1[k], u_bot_a, 0.0) + o_lo
        p_b1 = quad_bilerp(r0[k], r0[kn], r1[kn], r1[k], u_bot_b, 0.0) + o_lo
        mb.face([p_b0, p_b1, p_m1, p_m0], STRAP, out=n_lo)

    # Under-chin dark strap buckle tucked cleanly beneath chin edge (1 tri)
    mb.face([
        V(-0.048, 1.210, 0.132),
        V( 0.048, 1.210, 0.132),
        V( 0.000, 1.196, 0.092),
    ], STRAP, out=(0.0, -0.92, 0.38))

    # =========================================================================
    # 6. CHUNKY 3-BEAD CHESTNUT BRAIDED PONYTAIL (3 x 8 = 24 tris)
    # =========================================================================
    mb.set_part("braid", bone="Braid")
    # Diagonal axis angling cleanly down & back behind the upper backpack dome
    braid_dir = V(0.0, -0.71, -0.704).normalized()
    braid_u = V(1.0, 0.0, 0.0)
    braid_v = braid_u.cross(braid_dir).normalized()  # upward-backward perpendicular

    # 3 plump overlapping low-poly braid cushions packed closely so they read as a thick woven braid!
    bead_specs = [
        # (center,               half_len, rx,    rv)
        (V(0.0, 1.224, -0.214), 0.088,    0.092, 0.088),  # bead 1 emerging below helmet nape
        (V(0.0, 1.148, -0.290), 0.084,    0.084, 0.080),  # bead 2 mid-braid lobe
        (V(0.0, 1.072, -0.366), 0.082,    0.072, 0.068),  # bead 3 chunky tapered tail tuft
    ]
    for b_idx, (ctr, hlen, rx, rv) in enumerate(bead_specs):
        p_in  = ctr - braid_dir * hlen
        p_out = ctr + braid_dir * hlen
        # 4-sided diamond ring rotated 45 deg so facets read like plump woven braid links
        ring = []
        for k in range(4):
            a = math.pi / 4.0 + k * (math.pi / 2.0)
            ring.append(ctr + braid_u * (rx * math.cos(a)) + braid_v * (rv * math.sin(a)))
        for k in range(4):
            kn = (k + 1) % 4
            # Highlight top/sunlit facets, rich dark mid-facets, shaded underside
            c_in  = HAIR_SHADE if k in (2, 3) else HAIR_DARK
            c_out = HAIR_MID if (k == 0 or (b_idx % 2 == 1 and k == 1)) else (HAIR_SHADE if k == 2 else HAIR_DARK)
            mid_in = (p_in + ring[k] + ring[kn]) / 3.0
            mid_out = (p_out + ring[k] + ring[kn]) / 3.0
            mb.face([p_in,  ring[kn], ring[k]],  c_in,  out=(mid_in  - ctr))
            mb.face([p_out, ring[k],  ring[kn]], c_out, out=(mid_out - ctr))

    # =========================================================================
    # 7. TEAL CYCLING JACKET TORSO + STANDING COLLAR + PLACKET (10 + 6 + 2 = 18 tris)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    jy0, jy1 = 0.654, 1.128
    jx_b, jx_t = 0.188, 0.178
    jz_fb, jz_ft = 0.122, 0.114
    jz_bb, jz_bt = -0.114, -0.106
    j_bot = [
        V(-jx_b, jy0, jz_fb),
        V( jx_b, jy0, jz_fb),
        V( jx_b, jy0, jz_bb),
        V(-jx_b, jy0, jz_bb),
    ]
    j_top = [
        V(-jx_t, jy1, jz_ft),
        V( jx_t, jy1, jz_ft),
        V( jx_t, jy1, jz_bt),
        V(-jx_t, jy1, jz_bt),
    ]
    mb.loft([j_bot, j_top], lambda i, k: JACKET_SHADE if k == 2 else JACKET,
            cap_bottom=False, cap_top=True, top_color=JACKET)

    # Neat standing teal mock-neck cycling collar around base of neck (skip rear quad = 6 tris)
    col_r0 = oval_ring(0.0, 1.118, 0.008, 0.104, 0.096, n=4, phase=math.pi / 4.0)
    col_r1 = oval_ring(0.0, 1.176, 0.010, 0.092, 0.086, n=4, phase=math.pi / 4.0)
    mb.loft([col_r0, col_r1], JACKET_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # Darker teal vertical center placket / zipper strip on jacket front (2 tris)
    def torso_zf(y):
        t = (y - jy0) / (jy1 - jy0)
        return jz_fb + (jz_ft - jz_fb) * t

    pw = 0.022
    mb.face([
        V(-pw, jy0 + 0.004, torso_zf(jy0 + 0.004) + 0.004),
        V( pw, jy0 + 0.004, torso_zf(jy0 + 0.004) + 0.004),
        V( pw, jy1 - 0.002, torso_zf(jy1 - 0.002) + 0.004),
        V(-pw, jy1 - 0.002, torso_zf(jy1 - 0.002) + 0.004),
    ], JACKET_ZIP, out=(0, 0, 1))

    # =========================================================================
    # 8. DARK CHARCOAL CYCLING BACKPACK + LOWER POCKET + STRAPS (14 + 8 + 8 = 30 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # 3-ring rounded aerodynamic commuter backpack (skip hidden front face & underside = 14 tris)
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.668, 0.156, -0.114, -0.278),  # sturdy lower base
        (0.915, 0.170, -0.112, -0.304),  # mid rounded fullness
        (1.095, 0.128, -0.106, -0.208),  # tapered rounded top dome
    ]
    bp_rings = []
    for (y, rx, zin, zout) in bp_specs:
        bp_rings.append([
            V(-rx, y, zin),
            V( rx, y, zin),
            V( rx, y, zout),
            V(-rx, y, zout),
        ])
    mb.loft(bp_rings, lambda i, k: PACK_SHADE if i == 0 else PACK,
            cap_bottom=False, cap_top=True, top_color=PACK, skip_k=(0,))

    # Watertight chunky lower rear zippered pouch pocket on backpack (4 quads = 8 tris)
    px = 0.128
    py0, py1 = 0.680, 0.855
    pz_in_b, pz_in_t = -0.276, -0.296
    pz_out_b, pz_out_t = -0.346, -0.350
    p_bl = V(-px, py0, pz_out_b); p_br = V( px, py0, pz_out_b)
    p_tl = V(-px, py1, pz_out_t); p_tr = V( px, py1, pz_out_t)
    p_il = V(-px, py1, pz_in_t);  p_ir = V( px, py1, pz_in_t)
    p_ibl = V(-px, py0, pz_in_b); p_ibr = V( px, py0, pz_in_b)
    mb.face([p_br, p_bl, p_tl, p_tr],   PACK_POCKET, out=(0, 0, -1))
    mb.face([p_tl, p_tr, p_ir, p_il],   PACK_SHADE,  out=(0, 1, -0.2))
    mb.face([p_bl, p_ibl, p_il, p_tl],  PACK_POCKET, out=(-1, 0, 0))
    mb.face([p_ibr, p_br, p_tr, p_ir],  PACK_POCKET, out=( 1, 0, 0))

    # Two dark charcoal backpack shoulder straps over shoulders & front chest (8 tris)
    for side in (-1, 1):
        xa_t = min(side * 0.106, side * 0.154)
        xb_t = max(side * 0.106, side * 0.154)
        xa_b = min(side * 0.124, side * 0.172)
        xb_b = max(side * 0.124, side * 0.172)
        mb.face([
            V(xa_t, 1.136, -0.114),
            V(xb_t, 1.136, -0.114),
            V(xb_t, 1.136,  0.120),
            V(xa_t, 1.136,  0.120),
        ], PACK_STRAP, out=(0, 1, 0))
        mb.face([
            V(xa_b, 0.880, 0.129),
            V(xb_b, 0.880, 0.129),
            V(xb_t, 1.136, 0.120),
            V(xa_t, 1.136, 0.120),
        ], PACK_STRAP, out=(0, 0, 1))

    # =========================================================================
    # 9. 3/4 TEAL SLEEVES + HI-VIS LIME CUFF STRIPES + BARE WRISTS + GLOVES
    #    (32 + 12 + 16 + 20 = 80 tris)
    # =========================================================================
    # Natural relaxed cycling/walking arm posture: gentle bend down & slightly forward
    arm_specs = [
        ( 1, "Arm_L", "Forearm_L", V( 0.146, 1.036, 0.004), V( 0.244, 0.858, -0.028), V( 0.244, 0.714, 0.068)),
        (-1, "Arm_R", "Forearm_R", V(-0.146, 1.036, 0.004), V(-0.244, 0.858, -0.028), V(-0.244, 0.714, 0.068)),
    ]

    for (side, arm_bone, fore_bone, p_sh, p_el, p_wr) in arm_specs:
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax_mid = (ax1 + ax2).normalized()
        out_x = V(side, 0.0, 0.0)

        def arm_ring(ctr, axis, ru, rv):
            u = (out_x - axis * out_x.dot(axis)).normalized()  # outward (+side X)
            v = axis.cross(u).normalized()
            # Ensure v points generally forward (+Z)
            if v.z < 0:
                v = -v
            return [
                ctr - u * ru + v * rv,  # 0: inner-front
                ctr + u * ru + v * rv,  # 1: outer-front
                ctr + u * ru - v * rv,  # 2: outer-back
                ctr - u * ru - v * rv,  # 3: inner-back
            ]

        # 3/4 sleeve ends at ~56% along forearm, leaving bare wrist above cycling gloves!
        p_cuff = p_el.lerp(p_wr, 0.56)

        r_sh   = arm_ring(p_sh,   ax1,    0.056, 0.062)
        r_el   = arm_ring(p_el,   ax_mid, 0.064, 0.066)
        r_cuff = arm_ring(p_cuff, ax2,    0.058, 0.060)

        rw_sleeve = [
            {arm_bone: 1.0},
            {arm_bone: 0.5, fore_bone: 0.5},
            {fore_bone: 1.0},
        ]
        mb.set_part("sleeves")
        # k=0: front, k=1: outer, k=2: back, k=3: inner (skip hidden upper-armpit inner quad k=3)
        mb.loft([r_sh, r_el], lambda i, k: JACKET_SHADE if k in (2, 3) else JACKET,
                cap_bottom=False, cap_top=False, skip_k=(3,), ring_weights=rw_sleeve[:2])
        mb.loft([r_el, r_cuff], lambda i, k: JACKET_SHADE if k in (2, 3) else JACKET,
                cap_bottom=False, cap_top=False, ring_weights=rw_sleeve[1:])

        # Crisp hi-vis lime-yellow reflective cuff stripe wrapped around front, outer & back (6 tris/arm = 12 tris)
        mb.set_part("cuff_stripes", bone=fore_bone)
        p_st0 = p_el.lerp(p_wr, 0.38)
        p_st1 = p_el.lerp(p_wr, 0.50)
        r_st0 = arm_ring(p_st0, ax2, 0.063, 0.065)
        r_st1 = arm_ring(p_st1, ax2, 0.061, 0.063)
        c_st = (p_st0 + p_st1) * 0.5
        for k in (0, 1, 2):  # front, outer, back (skip inner armpit)
            kn = (k + 1) % 4
            q = [r_st0[k], r_st0[kn], r_st1[kn], r_st1[k]]
            mid = sum(q, Vector()) * 0.25
            mb.face(q, CUFF_STRIPE, out=(mid - c_st))

        # Exposed bare warm-peach lower forearm / wrist between 3/4 sleeve cuff and glove (8 tris/arm = 16 tris)
        mb.set_part("wrists", bone=fore_bone)
        p_w0 = p_el.lerp(p_wr, 0.52)  # tucked 0.04 inside sleeve cuff
        r_w0 = arm_ring(p_w0, ax2, 0.046, 0.048)
        r_w1 = arm_ring(p_wr, ax2, 0.044, 0.046)
        mb.loft([r_w0, r_w1], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=False)

        # Chunky dark charcoal cycling gloves (10 tris/arm = 20 tris)
        mb.set_part("gloves", bone=fore_bone)
        p_g0 = p_wr - ax2 * 0.012
        p_g1 = p_wr + ax2 * 0.096
        r_g0 = arm_ring(p_g0, ax2, 0.052, 0.054)
        r_g1 = arm_ring(p_g1, ax2, 0.045, 0.048)
        mb.loft([r_g0, r_g1], lambda i, k: GLOVE_SHADE if k in (2, 3) else GLOVE,
                cap_bottom=False, cap_top=True, top_color=GLOVE_SHADE)

    # =========================================================================
    # 10. BIKE SHORTS + BARE KNEES/CALVES + WHITE CREW SOCKS (8 + 16 + 16 + 16 = 56 tris)
    # =========================================================================
    mb.set_part("bike_shorts", bone="Root")
    mb.box(-0.172, 0.172, 0.552, 0.668, -0.096, 0.096, SHORTS, skip=("top", "bottom"))

    for side in (-1, 1):
        leg_bone = "Leg_L" if side > 0 else "Leg_R"
        shin_bone = "Shin_L" if side > 0 else "Shin_R"

        y_hip   = 0.585
        y_short = 0.390  # above-knee bike shorts hem (right at knee hinge!)
        y_sock  = 0.198  # crisp white crew sock top
        y_ank   = 0.092  # tucked cleanly into sneaker collar

        def leg_ring(y, xi, xo, rz):
            xa, xb = min(side * xi, side * xo), max(side * xi, side * xo)
            return [
                V(xa, y,  rz),
                V(xb, y,  rz),
                V(xb, y, -rz),
                V(xa, y, -rz),
            ]

        w_hip  = {leg_bone: 1.0}
        w_knee = {leg_bone: 0.5, shin_bone: 0.5}
        w_shin = {shin_bone: 1.0}

        # Fitted dark charcoal bike shorts (hip -> above-knee hem, 8 tris/leg)
        mb.set_part("bike_shorts")
        r_hip   = leg_ring(y_hip,   0.008, 0.170, 0.088)
        r_short = leg_ring(y_short, 0.032, 0.178, 0.078)
        mb.loft([r_short, r_hip], lambda i, k: SHORTS_SHADE if k == 2 else SHORTS,
                cap_bottom=False, cap_top=False, ring_weights=[w_knee, w_hip])

        # Bare warm-peach knees & lower legs (tucked slightly inside shorts hem -> sock top, 8 tris/leg)
        mb.set_part("bare_legs")
        r_bare_top = leg_ring(y_short + 0.012, 0.044, 0.168, 0.068)
        r_sock_top = leg_ring(y_sock,          0.062, 0.166, 0.056)
        mb.loft([r_sock_top, r_bare_top], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=False, ring_weights=[w_shin, w_knee])

        # Crisp off-white crew socks peeking cleanly above grey sneakers (8 tris/leg)
        mb.set_part("socks", bone=shin_bone)
        r_sk_t = leg_ring(y_sock + 0.006, 0.060, 0.168, 0.058)
        r_sk_b = leg_ring(y_ank,          0.066, 0.166, 0.056)
        mb.loft([r_sk_b, r_sk_t], lambda i, k: SOCK_SHADE if k == 2 else SOCK,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 11. GREY CYCLING SNEAKERS WITH DARK OUTSOLES (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Shin_L" if side > 0 else "Shin_R")
        cx = side * 0.116
        w = 0.062
        w_toe = 0.050
        z_heel = -0.090
        z_mid  =  0.058
        z_toe  =  0.166
        y_s0   =  0.000
        y_s1   =  0.028
        y_col  =  0.108

        # Dark charcoal rubber outsole (4 sides + bottom cap = 10 tris)
        sole_bot = [
            V(cx - w,     y_s0, z_heel),
            V(cx + w,     y_s0, z_heel),
            V(cx + w_toe, y_s0, z_toe),
            V(cx - w_toe, y_s0, z_toe),
        ]
        sole_top = [
            V(cx - w,     y_s1, z_heel),
            V(cx + w,     y_s1, z_heel),
            V(cx + w_toe, y_s1, z_toe),
            V(cx - w_toe, y_s1, z_toe),
        ]
        mb.loft([sole_bot, sole_top], SOLE, cap_bottom=True, cap_top=False, bot_color=SOLE)

        # Sculpted medium-grey sneaker upper hugging the white crew sock snugly (4 sides = 8 tris)
        shoe_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.026),
            V(cx + w * 0.84, y_col, z_heel + 0.026),
            V(cx + w * 0.84, y_col, z_mid),
            V(cx - w * 0.84, y_col, z_mid),
        ]
        mb.loft([sole_top, shoe_top], lambda i, k: SHOE_VAMP if k == 2 else SHOE,
                cap_bottom=False, cap_top=False)

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
    """24-frame looping Walk cycle: brisk, athletic cyclist stride with smooth knee bend,
    natural opposite arm swing, upbeat helmeted head bob, and bouncy 3-bead braid!

    Local bone axes (vertical upright bones): +X = left, +Y = up, +Z = forward.
    Right-hand rule around +X:
      +rx rotates +Y (up) -> +Z (forward), -Y (down) -> -Z (backward), -Z (back) -> +Y (up)
      -rx rotates +Y (up) -> -Z (backward), -Y (down) -> +Z (forward), +Z (fwd) -> +Y (up)
    """
    action = bpy.data.actions.new(name="Walk")
    rig.animation_data.action = action
    _reset_pose(rig)

    cycle_len = 24
    for frame in range(1, cycle_len + 2, 2):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        c1 = math.cos(phi)
        s2 = math.sin(2.0 * phi)
        c2 = math.cos(2.0 * phi)

        # Crisp brisk-walk bounce (two bounces per stride) + slight energetic forward lean (+rx)
        pb_root = rig.pose.bones["Root"]
        bob = 0.026 * (0.5 - 0.5 * c2) - 0.002
        root_pitch = 0.065
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.068 * s1, 0.030 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotating torso twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.018 * c2, 0.115 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Keep head upright & eyes forward (-rx cancels root forward lean) + subtle brisk bob
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.060 - 0.028 * s2, -0.045 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Bouncy braided ponytail (+rx lifts braid upward) with smooth phase lag
        pb_braid = rig.pose.bones["Braid"]
        braid_bounce = 0.14 * math.sin(2.0 * phi - 0.65) + 0.04
        braid_sway = 0.13 * math.sin(phi - 0.50)
        pb_braid.rotation_euler = (braid_bounce, braid_sway, -0.04 * s1)
        pb_braid.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Brisk walk stride: Leg_L -rx swings thigh FORWARD (s1 > 0), +rx swings BACKWARD (s1 < 0)
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.46 * s1 - 0.05, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.018, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        # Knee bends BACKWARD (+rx > 0) cleanly on trailing lift & gently on pass-through
        knee_l = 0.05 + 0.46 * max(0.0, math.sin(phi + math.pi - 0.50)) ** 1.35
        pb_shin_l = rig.pose.bones["Shin_L"]
        pb_shin_l.rotation_euler = (knee_l, 0.0, 0.0)
        pb_shin_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.46 * s1 - 0.05, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.018, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        knee_r = 0.05 + 0.46 * max(0.0, math.sin(phi - 0.50)) ** 1.35
        pb_shin_r = rig.pose.bones["Shin_R"]
        pb_shin_r.rotation_euler = (knee_r, 0.0, 0.0)
        pb_shin_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Opposite arm swing: when Leg_L swings forward (s1 > 0), Arm_L swings back (+rx), Arm_R swings forward (-rx)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.42 * s1, 0.0, 0.03)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Forearm flexes gently upward (-rx) on forward swing, relaxes on backswing
        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.18 + 0.16 * s1, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.42 * s1, 0.0, -0.03)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.18 - 0.16 * s1, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: relaxed weight shift, curious look around,
    gentle backpack-strap/glove check gesture, and soft braid sway."""
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

        # Smooth pulse mid-loop where she lifts her right gloved hand to tug/check her backpack strap
        strap_tug = max(0.0, math.sin(phi - 1.05)) ** 2

        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.007 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (0.012, 0.022 * s1, 0.014 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.018 * s2, 0.026 * s1 - 0.035 * strap_tug, -0.012 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert look-around head turn & gentle nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.032 * s2 + 0.05 * strap_tug, 0.18 * s1 - 0.08 * strap_tug, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Braid follows head turns with subtle pendulum lag
        pb_braid = rig.pose.bones["Braid"]
        pb_braid.rotation_euler = (-0.025 - 0.038 * math.sin(2.0 * phi - 0.5), -0.08 * math.sin(phi - 0.45), 0.0)
        pb_braid.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs planted squarely on the ground
        for bname in ("Leg_L", "Leg_R", "Shin_L", "Shin_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm rests calmly at her side with gentle breathing sway
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.04 + 0.032 * s1, 0.0, 0.020 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (0.08 + 0.028 * s2, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm rests, then smoothly raises (-rx) & bends inward to adjust backpack shoulder strap!
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.04 - 0.028 * s1 - 0.48 * strap_tug, 0.0, -0.020 * s1 + 0.06 * strap_tug)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (0.08 - 0.80 * strap_tug, 0.26 * strap_tug, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 12-bone rig (7 standard passenger bones + Braid + Forearms + Shins)
    with looping Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonBikerRig")
    rig = bpy.data.objects.new("PersonBikerRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Braid",     "Head",  ( 0.000, 1.262, -0.178), ( 0.000, 1.422, -0.178)),
        ("Arm_L",     "Torso", ( 0.146, 1.036,  0.004), ( 0.146, 1.196,  0.004)),
        ("Forearm_L", "Arm_L", ( 0.244, 0.858, -0.028), ( 0.244, 0.998, -0.028)),
        ("Arm_R",     "Torso", (-0.146, 1.036,  0.004), (-0.146, 1.196,  0.004)),
        ("Forearm_R", "Arm_R", (-0.244, 0.858, -0.028), (-0.244, 0.998, -0.028)),
        ("Leg_L",     "Root",  ( 0.104, 0.565,  0.000), ( 0.104, 0.725,  0.000)),
        ("Shin_L",    "Leg_L", ( 0.108, 0.390,  0.000), ( 0.108, 0.530,  0.000)),
        ("Leg_R",     "Root",  (-0.104, 0.565,  0.000), (-0.104, 0.725,  0.000)),
        ("Shin_R",    "Leg_R", (-0.108, 0.390,  0.000), (-0.108, 0.530,  0.000)),
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
    for v_idx, wdict in enumerate(mb.vert_weights):
        for bname, weight in wdict.items():
            vgroups[bname].add([v_idx], weight, "REPLACE")

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
        (-1.68, math.radians(62)),   # Front-3/4 matching reference angle
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Right side (showing helmet vents, braid, backpack, stripe)
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=62):
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=58, zrot_right_deg=90):
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


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonBiker")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonBiker")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonBiker", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=62)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=44)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=58, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=44, zrot_right_deg=90)

    print("=== PersonBiker Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
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
