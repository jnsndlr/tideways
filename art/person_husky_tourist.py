# Builds an ultra-low-poly (< 350 tris) stylized husky tourist in a two-tone grey/navy
# baseball cap, dark Wayfarer sunglasses, maroon pullover hoodie with white drawstrings
# and kangaroo pocket, black backpack with curved straps, dark slate shorts, white crew
# socks, and slate sneakers with white soles & toe caps in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_husky_tourist.py)
# Saves art/person_husky_tourist.blend, exports assets/models/person_husky_tourist.glb (rigged + Walk & Idle cycles),
# renders art/person_husky_tourist_preview.png, art/person_husky_tourist_walk_preview.png, art/person_husky_tourist_idle_preview.png,
# and outputs rendered videos art/person_husky_tourist_walk.mp4 and art/person_husky_tourist_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.70 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_husky_tourist.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_husky_tourist.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_husky_tourist_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_husky_tourist_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_husky_tourist_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_husky_tourist_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_husky_tourist_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to the reference husky tourist image (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN           = col_srgb(0.98, 0.76, 0.54)
SKIN_SHADE     = col_srgb(0.88, 0.65, 0.44)

HAIR_MID       = col_srgb(0.47, 0.36, 0.27)
HAIR_DARK      = col_srgb(0.37, 0.28, 0.21)
HAIR_SHADE     = col_srgb(0.28, 0.21, 0.16)

CAP_NAVY       = col_srgb(0.27, 0.31, 0.40)
CAP_SHADE      = col_srgb(0.20, 0.23, 0.31)
CAP_BRIM       = col_srgb(0.24, 0.28, 0.37)
CAP_UNDER      = col_srgb(0.15, 0.18, 0.25)
CAP_PATCH      = col_srgb(0.22, 0.26, 0.35)
CAP_FRONT      = col_srgb(0.58, 0.60, 0.65)

SUN_FRAME      = col_srgb(0.12, 0.12, 0.13)
SUN_LENS       = col_srgb(0.21, 0.21, 0.23)

HOODIE         = col_srgb(0.63, 0.28, 0.27)
HOODIE_SHADE   = col_srgb(0.50, 0.21, 0.20)
HOODIE_HOOD    = col_srgb(0.57, 0.24, 0.23)
HOODIE_POCKET  = col_srgb(0.59, 0.25, 0.24)
HOODIE_STRING  = col_srgb(0.96, 0.94, 0.90)

PACK_MAIN      = col_srgb(0.24, 0.24, 0.26)
PACK_DARK      = col_srgb(0.16, 0.16, 0.18)
PACK_TOP       = col_srgb(0.29, 0.29, 0.31)
PACK_TAB       = col_srgb(0.44, 0.34, 0.26)
PACK_STRAP     = col_srgb(0.19, 0.20, 0.22)

SHORTS         = col_srgb(0.30, 0.35, 0.42)
SHORTS_SHADE   = col_srgb(0.22, 0.26, 0.32)

SOCK           = col_srgb(0.95, 0.92, 0.87)
SOCK_SHADE     = col_srgb(0.85, 0.81, 0.76)

SHOE           = col_srgb(0.34, 0.37, 0.44)
SHOE_SHADE     = col_srgb(0.25, 0.28, 0.34)
SHOE_TOE       = col_srgb(0.93, 0.90, 0.85)
SHOE_LACE      = col_srgb(0.97, 0.95, 0.91)
SOLE           = col_srgb(0.90, 0.87, 0.82)

# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR_MID, HAIR_DARK, HAIR_SHADE],
    "top": [HOODIE, HOODIE_SHADE, HOODIE_HOOD, HOODIE_POCKET],
    "bottom": [SHORTS, SHORTS_SHADE],
    "accent": [CAP_NAVY, CAP_SHADE, CAP_BRIM, CAP_UNDER, CAP_PATCH],
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
            wb = ring_weights[0] if ring_weights is not None else None
            if n <= 4:
                self.face(r0, col, out=out_dir, weights=([wb] * n if wb is not None else None))
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb is not None else None))
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=([wb] * 4 if wb is not None else None))
            else:
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=([wb] * 3 if wb is not None else None))
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt = ring_weights[-1] if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([wt] * n if wt is not None else None))
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt is not None else None))
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=([wt] * 4 if wt is not None else None))
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=([wt] * 3 if wt is not None else None))

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


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=6, phase=math.pi / 6.0):
    """Ring tilted backward around X by tilt_rad (higher at +Z front, lower at -Z back)."""
    pts = []
    ct, st = math.cos(tilt_rad), math.sin(tilt_rad)
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        lx = rx * math.sin(a)
        lz = rz * math.cos(a)
        py = cy + lz * st
        pz = cz + lz * ct
        pts.append(V(cx + lx, py, pz))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + SHORT BROWN BACK HAIR + SIDEBURNS + CHUNKY NOSE (28 + 4 + 3 = 35 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.190,  0.024, 0.194, 0.174),  # 0: sturdy chin/jaw
        (1.275,  0.030, 0.242, 0.214),  # 1: broad husky cheeks
        (1.452,  0.014, 0.222, 0.198),  # 2: upper brow tucked 100% inside cap rim (zero poke-through!)
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks, k=1,2,3 short brown hair wrapping nape/sides
    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if k in (4, 5, 0):
                col = SKIN_SHADE if (i == 0 and k != 5) else SKIN
            elif k == 2:
                col = HAIR_DARK if i == 1 else HAIR_SHADE
            else:
                col = HAIR_MID if i == 1 else HAIR_DARK
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid))
    # Watertight jaw/chin bottom cap (4 tris)
    rb = head_rings[0]
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[3], rb[4], rb[5], rb[0]], SKIN_SHADE, out=(0, -1, 0))

    # Crisp short brown sideburns hugging the cheek right in front of each ear below the cap rim (4 tris)
    mb.set_part("hair", bone="Head")
    for side in (-1, 1):
        # Cheek plane spans from side vertex (rx, cz) to front-corner (0.5*rx, cz+0.866*rz)
        # Interpolate cleanly along that exact cheek facet so sideburn hugs flush (+0.005 proud)
        def cheek_pt(y, u):
            # u=0 at ear-side edge, u=1 at front corner
            t = (y - 1.275) / (1.452 - 1.275)
            rx = 0.242 + t * (0.222 - 0.242)
            rz = 0.214 + t * (0.198 - 0.214)
            cz = 0.030 + t * (0.014 - 0.030)
            x0, z0 = side * rx, cz
            x1, z1 = side * 0.5 * rx, cz + 0.866025 * rz
            px = x0 + u * (x1 - x0)
            pz = z0 + u * (z1 - z0)
            return V(px + side * 0.005, y, pz + 0.003)

        mb.face([
            cheek_pt(1.335, 0.02),
            cheek_pt(1.335, 0.34),
            cheek_pt(1.438, 0.36),
            cheek_pt(1.438, 0.02),
        ], HAIR_MID, out=(side * 0.866, 0, 0.5))

    # Cute subtle protruding nose pyramid between/below sunglasses bridge (3 tris)
    mb.set_part("head", bone="Head")
    n_top  = V( 0.000, 1.384, 0.203)
    n_bl   = V( 0.024, 1.332, 0.209)
    n_br   = V(-0.024, 1.332, 0.209)
    n_tip  = V( 0.000, 1.336, 0.236)
    mb.face([n_top, n_bl, n_tip],  SKIN,       out=( 0.5, 0.2, 0.8))
    mb.face([n_top, n_tip, n_br],  SKIN,       out=(-0.5, 0.2, 0.8))
    mb.face([n_bl, n_br, n_tip],   SKIN_SHADE, out=( 0.0, -1.0, 0.2))

    # =========================================================================
    # 2. CHUNKY ROUNDED EARS (8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in  = side * 0.226
        x_out = side * 0.260
        p_in  = V(x_in,  1.326, 0.028)
        p_tf  = V(x_out, 1.358, 0.056)
        p_tb  = V(x_out, 1.358, 0.002)
        p_bf  = V(x_out, 1.294, 0.050)
        p_bb  = V(x_out, 1.294, 0.008)
        mb.face([p_bf, p_bb, p_tb, p_tf], SKIN,       out=(side, 0, 0))
        mb.face([p_in, p_bf, p_tf],       SKIN,       out=(0, 0, 1))
        mb.face([p_bb, p_in, p_tb],       SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 3. STURDY NECK (6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.105, 0.018, 0.082, 0.074, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.205, 0.020, 0.078, 0.070, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 4. TWO-TONE BASEBALL CAP (grey front panel + dark navy sides/back/brim/patch = 38 tris)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    # Snug baseball cap tilted back ~13 deg so rim hugs cleanly above sunglasses & down over back hair
    cap_tilt = math.radians(13.0)
    st, ct = math.sin(cap_tilt), math.cos(cap_tilt)
    cap_orig = V(0.0, 1.425, 0.010)

    def cap_ring(h, rx, rz):
        cy = cap_orig.y + h * ct
        cz = cap_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, cap_tilt, n=6, phase=math.pi / 6.0)

    c_r0 = cap_ring(0.000, 0.264, 0.244)  # sweatband rim (cleanly outside head_rings[2]!)
    c_r1 = cap_ring(0.145, 0.214, 0.198)  # mid crown dome
    c_r2 = cap_ring(0.232, 0.114, 0.106)  # rounded top panel (~1.69 m peak!)

    # Crown side walls: k=5 front panel is light slate-grey (CAP_FRONT); sides/back are dark navy!
    def cap_wall_col(i, k):
        if k == 5:
            return CAP_FRONT
        if k in (1, 2, 3):
            return CAP_SHADE
        return CAP_NAVY

    mb.loft([c_r0, c_r1, c_r2], cap_wall_col, cap_bottom=False, cap_top=False)

    # Top cap split front-half grey (CAP_FRONT) & back-half navy (CAP_NAVY) matching reference trucker cap! (4 tris)
    mb.face([c_r2[4], c_r2[5], c_r2[0], c_r2[1]], CAP_FRONT, out=(0, ct, -st))
    mb.face([c_r2[1], c_r2[2], c_r2[3], c_r2[4]], CAP_NAVY,  out=(0, ct, -st))

    # Centered dark navy square patch squarely on the flat front grey panel (c_r0 -> c_r1, zero bend clipping!) (2 tris)
    p0_l, p0_r = c_r0[5], c_r0[0]
    p1_l, p1_r = c_r1[5], c_r1[0]
    panel_n = (p0_r - p0_l).cross(p1_l - p0_l)
    if panel_n.z < 0:
        panel_n = -panel_n
    panel_n = panel_n.normalized()
    pn_out = panel_n * 0.007
    mb.face([
        p0_l.lerp(p1_l, 0.34).lerp(p0_r.lerp(p1_r, 0.34), 0.31) + pn_out,
        p0_l.lerp(p1_l, 0.34).lerp(p0_r.lerp(p1_r, 0.34), 0.69) + pn_out,
        p0_l.lerp(p1_l, 0.84).lerp(p0_r.lerp(p1_r, 0.84), 0.71) + pn_out,
        p0_l.lerp(p1_l, 0.84).lerp(p0_r.lerp(p1_r, 0.84), 0.29) + pn_out,
    ], CAP_PATCH, out=panel_n)

    # Sculpted curved dark navy visor / brim with closed tapered front edge (zero hollow razor gap!) (8 tris)
    b_l_in  = c_r0[0].lerp(c_r0[1], 0.34)
    b_c_in  = c_r0[5].lerp(c_r0[0], 0.50)
    b_r_in  = c_r0[5].lerp(c_r0[4], 0.34)
    # Slight sporty downward curve over sunglasses, meeting cleanly along the outer rim edge
    b_l_out = V( 0.205, 1.430, 0.316)
    b_c_out = V( 0.000, 1.448, 0.402)
    b_r_out = V(-0.205, 1.430, 0.316)
    brim_drop = V(0.0, -0.022, -0.006)
    mb.face([b_l_in, b_c_in, b_c_out, b_l_out], CAP_BRIM,  out=(0, 1, 0.3))
    mb.face([b_c_in, b_r_in, b_r_out, b_c_out], CAP_BRIM,  out=(0, 1, 0.3))
    mb.face([b_l_in + brim_drop, b_l_out, b_c_out, b_c_in + brim_drop], CAP_UNDER, out=(0, -1, -0.2))
    mb.face([b_c_in + brim_drop, b_c_out, b_r_out, b_r_in + brim_drop], CAP_UNDER, out=(0, -1, -0.2))

    # =========================================================================
    # 5. DARK WAYFARER SUNGLASSES (brow bar + 2 chunky dark lenses + sleek temples = 24 tris)
    # =========================================================================
    mb.set_part("sunglasses", bone="Head")
    z_bk  = 0.200
    z_fr  = 0.228
    y_top = 1.422
    y_br  = 1.400
    y_bot = 1.334

    # Continuous Wayfarer brow bar & nose bridge (front + top = 4 tris)
    mb.face([V(-0.158, y_br, z_fr), V(0.158, y_br, z_fr), V(0.164, y_top, z_fr), V(-0.164, y_top, z_fr)],
            SUN_FRAME, out=(0, 0, 1))
    mb.face([V(-0.164, y_top, z_fr), V(0.164, y_top, z_fr), V(0.158, y_top, z_bk), V(-0.158, y_top, z_bk)],
            SUN_FRAME, out=(0, 1, 0))

    # Two chunky tapered dark lenses (each: front lens + bottom rim + outer rim = 6 tris -> 12 tris)
    for side in (-1, 1):
        x_in_t  = side * 0.022
        x_out_t = side * 0.152
        x_in_b  = side * 0.036
        x_out_b = side * 0.132

        if side > 0:
            pf = [V(x_in_b, y_bot, z_fr), V(x_out_b, y_bot, z_fr), V(x_out_t, y_br, z_fr), V(x_in_t, y_br, z_fr)]
            pb = [V(x_in_b, y_bot, z_bk), V(x_out_b, y_bot, z_bk), V(x_out_t, y_br, z_bk), V(x_in_t, y_br, z_bk)]
        else:
            pf = [V(x_out_b, y_bot, z_fr), V(x_in_b, y_bot, z_fr), V(x_in_t, y_br, z_fr), V(x_out_t, y_br, z_fr)]
            pb = [V(x_out_b, y_bot, z_bk), V(x_in_b, y_bot, z_bk), V(x_in_t, y_br, z_bk), V(x_out_t, y_br, z_bk)]

        mb.face(pf, SUN_LENS, out=(0, 0, 1))
        mb.face([pb[0], pb[1], pf[1], pf[0]], SUN_FRAME, out=(0, -1, 0))
        if side > 0:
            mb.face([pf[1], pb[1], pb[2], pf[2]], SUN_FRAME, out=( 1, 0, 0))
        else:
            mb.face([pb[0], pf[0], pf[3], pb[3]], SUN_FRAME, out=(-1, 0, 0))

    # Two sleek black temple arms stretching straight back across sideburns onto tops of ears (4 tris x 2 = 8 tris)
    for side in (-1, 1):
        x_f = side * 0.156
        x_b = side * 0.256
        y_t0, y_t1 = y_br + 0.002, y_top - 0.002
        y_b0, y_b1 = 1.356, 1.376
        z_tf, z_tb = z_bk + 0.015, 0.025
        t_in = side * (-0.014)
        p0 = V(x_f, y_t0, z_tf); p1 = V(x_f, y_t1, z_tf)
        q0 = V(x_b, y_b0, z_tb); q1 = V(x_b, y_b1, z_tb)
        p1i = V(x_f + t_in, y_t1, z_tf); q1i = V(x_b + t_in, y_b1, z_tb)
        mb.face([p0, q0, q1, p1],   SUN_FRAME, out=(side, 0, 0))
        mb.face([p1, q1, q1i, p1i], SUN_FRAME, out=(0, 1, 0))

    # =========================================================================
    # 6. HUSKY MAROON PULLOVER HOODIE (3-ring barrel torso + hood + kangaroo pocket + drawstrings = 46 tris)
    # =========================================================================
    mb.set_part("hoodie", bone="Torso")
    # 3-ring chunky husky silhouette: slightly tapered hem -> full plush belly -> broad sturdy shoulders (28 tris)
    t_bot   = oval_ring(0.0, 0.592, 0.008, 0.282, 0.200, n=6, phase=math.pi / 6.0)
    t_belly = oval_ring(0.0, 0.778, 0.018, 0.308, 0.226, n=6, phase=math.pi / 6.0)
    t_top   = oval_ring(0.0, 1.132, 0.004, 0.270, 0.184, n=6, phase=math.pi / 6.0)
    mb.loft(
        [t_bot, t_belly, t_top],
        lambda i, k: HOODIE_SHADE if k in (1, 2, 3) else HOODIE,
        cap_bottom=False, cap_top=True, top_color=HOODIE,
    )

    # Chunky folded hood collar wrapping cozily around neck right up under the jaw (8 tris)
    hd_bot = [
        V(-0.165, 1.100,  0.112),
        V( 0.165, 1.100,  0.112),
        V( 0.215, 1.095, -0.210),
        V(-0.215, 1.095, -0.210),
    ]
    hd_top = [
        V(-0.118, 1.196,  0.105),
        V( 0.118, 1.196,  0.105),
        V( 0.185, 1.220, -0.182),
        V(-0.185, 1.220, -0.182),
    ]
    mb.loft([hd_bot, hd_top], HOODIE_HOOD, cap_bottom=False, cap_top=True, top_color=HOODIE, skip_k=(0,))

    # Front kangaroo pocket sitting proudly on the lower front belly (front + left slant + right slant = 6 tris)
    # Front surface z on torso: y=0.592 -> 0.1812, y=0.778 -> 0.2137, y=1.132 -> 0.1633
    def torso_front_z(y):
        if y <= 0.778:
            t = (y - 0.592) / (0.778 - 0.592)
            return 0.1812 + t * (0.2137 - 0.1812)
        t = (y - 0.778) / (1.132 - 0.778)
        return 0.2137 + t * (0.1633 - 0.2137)

    pk_yb = 0.625
    pk_yt = 0.855
    pk_zb_in  = torso_front_z(pk_yb) - 0.002
    pk_zt_in  = torso_front_z(pk_yt) - 0.002
    pk_zb_out = torso_front_z(pk_yb) + 0.024
    pk_zt_out = torso_front_z(pk_yt) + 0.022
    pk_w_bot  = 0.132
    pk_w_top  = 0.098
    pk_fl_b = V( pk_w_bot, pk_yb, pk_zb_out)
    pk_fr_b = V(-pk_w_bot, pk_yb, pk_zb_out)
    pk_fl_t = V( pk_w_top, pk_yt, pk_zt_out)
    pk_fr_t = V(-pk_w_top, pk_yt, pk_zt_out)
    pk_il_b = V( pk_w_bot + 0.012, pk_yb, pk_zb_in)
    pk_ir_b = V(-pk_w_bot - 0.012, pk_yb, pk_zb_in)
    pk_il_t = V( pk_w_top + 0.010, pk_yt, pk_zt_in)
    pk_ir_t = V(-pk_w_top - 0.010, pk_yt, pk_zt_in)
    mb.face([pk_fr_b, pk_fl_b, pk_fl_t, pk_fr_t], HOODIE_POCKET, out=( 0, 0, 1))
    mb.face([pk_fl_b, pk_il_b, pk_il_t, pk_fl_t], HOODIE_SHADE,  out=( 1, 0.2, 0.2))
    mb.face([pk_ir_b, pk_fr_b, pk_fr_t, pk_ir_t], HOODIE_SHADE,  out=(-1, 0.2, 0.2))

    # Two crisp off-white hoodie drawstrings hanging down the upper chest (4 tris)
    mb.set_part("drawstrings", bone="Torso")
    for side in (-1, 1):
        cx_t = side * 0.044
        cx_b = side * 0.048
        hw   = 0.011
        y_dt = 1.108
        y_db = 0.895
        z_dt = torso_front_z(y_dt) + 0.011
        z_db = torso_front_z(y_db) + 0.012
        mb.face([
            V(cx_b - hw, y_db, z_db),
            V(cx_b + hw, y_db, z_db),
            V(cx_t + hw, y_dt, z_dt),
            V(cx_t - hw, y_dt, z_dt),
        ], HOODIE_STRING, out=(0, 0.16, 0.98))

    # =========================================================================
    # 7. PUFFY HOODIE SLEEVES & CHUNKY HANDS (32 + 20 = 52 tris)
    # =========================================================================
    def build_arm_and_hand(p_sh, p_el, p_wr, hand_len, arm_bone, fore_bone):
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax_mid = (ax1 + ax2).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def ring4(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            if u.length < 1e-5:
                u = V(0.0, 0.0, 1.0)
            else:
                u = u.normalized()
            v = axis.cross(u).normalized()
            return [
                ctr + u * (-rx) + v * ( rperp),
                ctr + u * ( rx) + v * ( rperp),
                ctr + u * ( rx) + v * (-rperp),
                ctr + u * (-rx) + v * (-rperp),
            ]

        # Generous puffy hoodie sleeve tapering neatly into wrist cuff
        r_sh = ring4(p_sh, ax1,    0.080, 0.086)
        r_el = ring4(p_el, ax_mid, 0.094, 0.100)
        r_wr = ring4(p_wr, ax2,    0.068, 0.072)

        w_sh = {arm_bone: 1.0}
        w_el = {arm_bone: 0.5, fore_bone: 0.5}
        w_wr = {fore_bone: 1.0}

        mb.set_part("sleeves")
        mb.loft(
            [r_sh, r_el, r_wr],
            lambda i, k: HOODIE_SHADE if k in (2, 3) else HOODIE,
            cap_bottom=False, cap_top=False,
            ring_weights=[w_sh, w_el, w_wr],
        )

        # Chunky stylized fist peeking cleanly below hoodie cuff (10 tris)
        mb.set_part("hands", bone=fore_bone)
        r_h0 = ring4(p_wr, ax2, 0.058, 0.060)
        r_h1 = ring4(p_wr + ax2 * hand_len, ax2, 0.046, 0.048)
        mb.loft([r_h0, r_h1], lambda i, k: SKIN_SHADE if k in (2, 3) else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # Smoothly blended shoulders & relaxed husky stance clearing wide hoodie & shorts
    for side in (-1, 1):
        arm_b  = "Arm_L" if side > 0 else "Arm_R"
        fore_b = "Forearm_L" if side > 0 else "Forearm_R"
        p_sh = V(side * 0.214, 1.028,  0.002)
        p_el = V(side * 0.324, 0.842, -0.014)
        p_wr = V(side * 0.312, 0.675,  0.024)
        build_arm_and_hand(p_sh, p_el, p_wr, hand_len=0.106, arm_bone=arm_b, fore_bone=fore_b)

    # =========================================================================
    # 8. BLACK BACKPACK + TOP GRAB BLOCK + BROWN LEATHER TABS + CURVED STRAPS (16 + 6 + 4 + 12 = 38 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Backpack")
    # 3-ring beveled chunky black pack resting cleanly behind the maroon hoodie (skip front flush against back = 16 tris)
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.665, 0.178, -0.158, -0.320),  # 0: rounded lower base
        (0.880, 0.212, -0.170, -0.382),  # 1: full chunky pack belly
        (1.130, 0.148, -0.146, -0.275),  # 2: beveled top shoulder dome
    ]
    bp_rings = []
    for (y, rx, zin, zout) in bp_specs:
        bp_rings.append([
            V(-rx, y, zin),
            V( rx, y, zin),
            V( rx, y, zout),
            V(-rx, y, zout),
        ])

    mb.loft(
        bp_rings,
        lambda i, k: PACK_DARK if k in (1, 3) else PACK_MAIN,
        cap_bottom=True, cap_top=True,
        bot_color=PACK_DARK, top_color=PACK_TOP,
        skip_k=(0,),
    )

    # Stepped top collar / grab-handle block rising cleanly behind the hood (back + top + 2 side tris = 6 tris)
    tp_fl = V( 0.108, 1.125, -0.155)
    tp_fr = V(-0.108, 1.125, -0.155)
    tp_bl = V( 0.108, 1.125, -0.272)
    tp_br = V(-0.108, 1.125, -0.272)
    tp_tl = V( 0.096, 1.192, -0.250)
    tp_tr = V(-0.096, 1.192, -0.250)
    mb.face([tp_br, tp_bl, tp_tl, tp_tr], PACK_DARK, out=(0, 0, -1))
    mb.face([tp_fl, tp_fr, tp_tr, tp_tl], PACK_TOP,  out=(0, 1, 0.25))
    mb.face([tp_fl, tp_tl, tp_bl],        PACK_DARK, out=( 1, 0, 0))
    mb.face([tp_fr, tp_br, tp_tr],        PACK_DARK, out=(-1, 0, 0))

    # Cute tiny brown leather side tabs / zipper pulls matching reference detail (4 tris)
    for side in (-1, 1):
        x_tab = side * 0.205
        mb.face([
            V(x_tab, 0.770, -0.320),
            V(x_tab, 0.770, -0.276),
            V(x_tab, 0.822, -0.282),
            V(x_tab, 0.822, -0.328),
        ], PACK_TAB, out=(side, 0, -0.15))

    # Curved dark charcoal backpack shoulder straps hugging hoodie shoulders & sweeping under arms (12 tris)
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        xa_t = min(side * 0.145, side * 0.202)
        xb_t = max(side * 0.145, side * 0.202)
        xa_f = min(side * 0.185, side * 0.244)
        xb_f = max(side * 0.185, side * 0.244)
        # Top shoulder strap crossing from rear pack over hoodie shoulder to upper chest
        mb.face([
            V(xa_t, 1.138, -0.152),
            V(xb_t, 1.138, -0.152),
            V(xb_t, 1.134,  0.140),
            V(xa_t, 1.134,  0.140),
        ], PACK_STRAP, out=(0, 1, 0.1))
        # Front curved chest strap hugging hoodie side-chest cleanly toward armpit
        mb.face([
            V(xa_f, 0.870, 0.176),
            V(xb_f, 0.870, 0.146),
            V(xb_t, 1.134, 0.140),
            V(xa_t, 1.134, 0.140),
        ], PACK_STRAP, out=(side * 0.45, 0.12, 0.88))
        # Lower side underarm strap sweeping back into the dark backpack base
        x_s = side * 0.268
        mb.face([
            V(x_s, 0.742, -0.168),
            V(x_s, 0.788, -0.168),
            V(side * 0.244, 0.892, 0.146),
            V(side * 0.244, 0.850, 0.146),
        ], PACK_STRAP, out=(side, 0, 0))

    # =========================================================================
    # 9. DARK SLATE-NAVY SHORTS + BARE LOWER LEGS + WHITE CREW SOCKS (20 + 16 + 16 = 52 tris)
    # =========================================================================
    mb.set_part("shorts", bone="Root")
    # Pelvis bridge (front & back only; sides tucked inside shorts legs, top inside hoodie = 4 tris)
    mb.box(-0.235, 0.235, 0.505, 0.618, -0.128, 0.128, SHORTS, skip=("top", "bottom", "left", "right"))

    for side in (-1, 1):
        leg_bone  = "Leg_L"  if side > 0 else "Leg_R"
        shin_bone = "Shin_L" if side > 0 else "Shin_R"

        y_hip   = 0.608
        y_short = 0.376  # relaxed A-line shorts hem right at knee joint
        y_sock  = 0.214  # crisp white crew sock top
        y_ank   = 0.118  # tucked snugly inside dark slate sneaker collar

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

        # Loose dark slate-navy A-line shorts legs (8 tris/leg)
        mb.set_part("shorts")
        r_hip   = leg_ring(y_hip,   0.006, 0.235, 0.122)
        r_short = leg_ring(y_short, 0.032, 0.258, 0.122)
        mb.loft([r_short, r_hip], lambda i, k: SHORTS_SHADE if k == 2 else SHORTS,
                cap_bottom=False, cap_top=False, ring_weights=[w_knee, w_hip])

        # Sturdy warm-peach bare lower legs from inside shorts down to sock top (8 tris/leg)
        mb.set_part("bare_legs")
        r_bare_top = leg_ring(y_short + 0.018, 0.068, 0.210, 0.080)
        r_bare_bot = leg_ring(y_sock  - 0.008, 0.078, 0.198, 0.066)
        mb.loft([r_bare_bot, r_bare_top], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=False, ring_weights=[w_shin, w_knee])

        # Crisp chunky off-white crew socks rising boldly above the sneakers! (8 tris/leg)
        mb.set_part("socks", bone=shin_bone)
        r_sock_top = leg_ring(y_sock, 0.074, 0.202, 0.070)
        r_sock_bot = leg_ring(y_ank,  0.078, 0.198, 0.066)
        mb.loft([r_sock_bot, r_sock_top], lambda i, k: SOCK_SHADE if k == 2 else SOCK,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 10. DARK SLATE SNEAKERS WITH OFF-WHITE SOLES, TOE CAPS & WHITE LACE BARS (24 x 2 = 48 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Shin_L" if side > 0 else "Shin_R")
        cx = side * 0.138
        w = 0.076
        w_toe = 0.064
        z_heel = -0.104
        z_mid  =  0.068
        z_toe  =  0.196
        y_s0   =  0.000
        y_s1   =  0.036
        y_col  =  0.136

        # Thick off-white rubber outsole (4 sides + bottom cap = 10 tris)
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

        # Dark slate-blue sneaker upper: back, left, right + top collar (6 + 2 = 8 tris)
        shoe_top = [
            V(cx - w * 0.94, y_col, z_heel + 0.018),
            V(cx + w * 0.94, y_col, z_heel + 0.018),
            V(cx + w * 0.94, y_col, z_mid),
            V(cx - w * 0.94, y_col, z_mid),
        ]
        # Skip k=2 (front sloped face) so we can split it cleanly into white rubber toe cap + slate vamp!
        mb.loft(
            [sole_top, shoe_top],
            lambda i, k: SHOE_SHADE if k == 0 else SHOE,
            cap_bottom=False, cap_top=True, top_color=SHOE_SHADE,
            skip_k=(2,),
        )

        # Split front sloped face (sole_top[2..3] -> shoe_top[2..3]):
        # Lower 38% = crisp off-white rubber toe cap (2 tris); upper 62% = dark slate tongue/vamp (2 tris)
        p_bl = sole_top[2]
        p_br = sole_top[3]
        p_tl = shoe_top[2]
        p_tr = shoe_top[3]
        p_ml = p_bl.lerp(p_tl, 0.38)
        p_mr = p_br.lerp(p_tr, 0.38)
        mb.face([p_br, p_bl, p_ml, p_mr], SHOE_TOE, out=(0, 0.62, 0.78))
        mb.face([p_mr, p_ml, p_tl, p_tr], SHOE,     out=(0, 0.62, 0.78))

        # Crisp off-white lace panel sitting neatly centered on the upper dark vamp (2 tris)
        vn_out = V(0.0, 0.62, 0.78) * 0.007
        lc_bl = p_ml.lerp(p_tl, 0.18).lerp(p_mr.lerp(p_tr, 0.18), 0.28) + vn_out
        lc_br = p_ml.lerp(p_tl, 0.18).lerp(p_mr.lerp(p_tr, 0.18), 0.72) + vn_out
        lc_tl = p_ml.lerp(p_tl, 0.78).lerp(p_mr.lerp(p_tr, 0.78), 0.30) + vn_out
        lc_tr = p_ml.lerp(p_tl, 0.78).lerp(p_mr.lerp(p_tr, 0.78), 0.70) + vn_out
        mb.face([lc_br, lc_bl, lc_tl, lc_tr], SHOE_LACE, out=(0, 0.62, 0.78))

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
    """24-frame looping Walk cycle: sturdy, slightly lumbering husky-tourist stroll with
    grounded side-to-side hip sway, crisp knee bend, wide arm swing clearing the hoodie & shorts,
    steady head bob, and weighted backpack bounce.

    Local bone axes (vertical upright bones): +X = left, +Y = up, +Z = forward.
    Right-hand rule around +X:
      +rx rotates +Y (up) -> +Z (forward), -Y (down) -> -Z (backward)
      -rx rotates +Y (up) -> -Z (backward), -Y (down) -> +Z (forward)
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

        # Solid grounded double-bounce + hearty husky side-to-side sway & slight forward lean
        pb_root = rig.pose.bones["Root"]
        bob = 0.022 * (0.5 - 0.5 * c2) - 0.002
        sway_x = 0.016 * c1
        pb_root.location = (sway_x, bob, 0.0)
        pb_root.rotation_euler = (0.052, -0.056 * s1, 0.044 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotating torso twist & slight husky shoulder roll
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.018 * c2, 0.088 * s1, -0.032 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Cool steady head holding level behind sunglasses with a rhythmic stride bob
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.042 - 0.028 * s2, -0.042 * s1, 0.018 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Black backpack bounces gently with weighted phase lag behind each step
        pb_pack = rig.pose.bones["Backpack"]
        pb_pack.location = (0.0, 0.014 * math.sin(2.0 * phi - 0.65), 0.0)
        pb_pack.rotation_euler = (-0.045 * math.sin(2.0 * phi - 0.55), 0.0, -0.024 * math.cos(phi - 0.40))
        pb_pack.keyframe_insert(data_path="location", frame=frame)
        pb_pack.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sturdy stride: Leg_L -rx swings thigh FORWARD (s1 > 0), +rx swings BACKWARD (s1 < 0)
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.42 * s1 - 0.03, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.018, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        knee_l = 0.04 + 0.42 * max(0.0, math.sin(phi + math.pi - 0.48)) ** 1.35
        pb_shin_l = rig.pose.bones["Shin_L"]
        pb_shin_l.rotation_euler = (knee_l, 0.0, 0.0)
        pb_shin_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.42 * s1 - 0.03, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.018, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        knee_r = 0.04 + 0.42 * max(0.0, math.sin(phi - 0.48)) ** 1.35
        pb_shin_r = rig.pose.bones["Shin_R"]
        pb_shin_r.rotation_euler = (knee_r, 0.0, 0.0)
        pb_shin_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Broad relaxed arm swing opposite legs, abducted slightly outward to clear wide hoodie & shorts
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.36 * s1, 0.0, 0.055)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.18 + 0.14 * s1, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.36 * s1, 0.0, -0.055)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.18 - 0.14 * s1, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: relaxed husky tourist standing solidly at the dock,
    subtle weight shift, deep calm breathing, cool sightseeing look-around behind sunglasses,
    and gentle backpack settle."""
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

        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.008 * s1, -0.006 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (0.008, 0.022 * s1, 0.016 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Deep relaxed breathing & subtle torso turn toward where he is looking
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.020 * s2, 0.045 * s1, -0.012 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Cool tourist look-around taking in the ferry & harbor behind dark shades
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.048 * s2 - 0.025 * (1.0 - c1) * 0.5, 0.30 * s1, 0.036 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle backpack breathing settle
        pb_pack = rig.pose.bones["Backpack"]
        pb_pack.location = (0.0, 0.005 * s2, 0.0)
        pb_pack.rotation_euler = (-0.016 * s2, 0.0, 0.0)
        pb_pack.keyframe_insert(data_path="location", frame=frame)
        pb_pack.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sneakers planted squarely on the ground
        for bname in ("Leg_L", "Leg_R", "Shin_L", "Shin_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed arms resting at sides with subtle breathing & weight-shift sway
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.025 + 0.042 * s1, 0.0, 0.038 + 0.022 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.06 + 0.038 * s2, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.025 - 0.042 * s1, 0.0, -0.038 - 0.022 * s2)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.06 - 0.038 * s2, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 12-bone rig (Root, Torso, Head, Backpack, Arm/Forearm L/R, Leg/Shin L/R)
    with looping Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonHuskyTouristRig")
    rig = bpy.data.objects.new("PersonHuskyTouristRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.560,  0.000), ( 0.000, 0.670,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.615,  0.000), ( 0.000, 1.115,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.155,  0.015), ( 0.000, 1.505,  0.015)),
        ("Backpack",  "Torso", ( 0.000, 0.895, -0.175), ( 0.000, 1.075, -0.175)),
        ("Arm_L",     "Torso", ( 0.214, 1.028,  0.002), ( 0.214, 1.188,  0.002)),
        ("Forearm_L", "Arm_L", ( 0.324, 0.842, -0.014), ( 0.324, 0.992, -0.014)),
        ("Arm_R",     "Torso", (-0.214, 1.028,  0.002), (-0.214, 1.188,  0.002)),
        ("Forearm_R", "Arm_R", (-0.324, 0.842, -0.014), (-0.324, 0.992, -0.014)),
        ("Leg_L",     "Root",  ( 0.132, 0.555,  0.000), ( 0.132, 0.725,  0.000)),
        ("Shin_L",    "Leg_L", ( 0.138, 0.380,  0.000), ( 0.138, 0.530,  0.000)),
        ("Leg_R",     "Root",  (-0.132, 0.555,  0.000), (-0.132, 0.725,  0.000)),
        ("Shin_R",    "Leg_R", (-0.138, 0.380,  0.000), (-0.138, 0.530,  0.000)),
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
        (-1.80, math.radians(45)),   # Front-3/4 matching reference angle
        (-0.60, math.radians(0)),    # Front
        ( 0.60, math.radians(90)),   # Right side (showing cap brim, sunglasses, hoodie, backpack)
        ( 1.80, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 4.9
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.12)
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=50):
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.25
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.6
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=48, zrot_right_deg=90):
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
    cam_data.ortho_scale = 3.05
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.12)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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
            left_obj.location = (-0.68, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.68, 0.0, 0.0)
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

    coll = bpy.data.collections.new("PersonHuskyTourist")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonHuskyTourist")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonHuskyTourist", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=50)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=45)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonHuskyTourist Stats ===")
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
