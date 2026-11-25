# Builds an ultra-low-poly (< 350 tris) stylized hipster with a guitar case in Blender
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_hipster.py)
# Saves art/person_hipster.blend, exports assets/models/person_hipster.glb (rigged + Walk & Idle cycles),
# renders art/person_hipster_preview.png, art/person_hipster_walk_preview.png, art/person_hipster_idle_preview.png,
# and outputs rendered videos art/person_hipster_walk.mp4 and art/person_hipster_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.72 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_hipster.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_hipster.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_hipster_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_hipster_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_hipster_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_hipster_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_hipster_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference image (sRGB -> linear)
SKIN           = col_srgb(0.97, 0.74, 0.52)
SKIN_SHADE     = col_srgb(0.87, 0.62, 0.41)

HAIR_DARK      = col_srgb(0.35, 0.25, 0.19)
BEARD          = col_srgb(0.41, 0.29, 0.21)
BEARD_DARK     = col_srgb(0.31, 0.21, 0.15)
MUSTACHE       = col_srgb(0.46, 0.33, 0.24)

GLASSES        = col_srgb(0.14, 0.14, 0.15)

BEANIE         = col_srgb(0.64, 0.31, 0.26)
BEANIE_CUFF    = col_srgb(0.73, 0.38, 0.32)
BEANIE_SHADE   = col_srgb(0.53, 0.24, 0.20)

FLANNEL_RUST   = col_srgb(0.68, 0.35, 0.23)
FLANNEL_BROWN  = col_srgb(0.49, 0.30, 0.22)
FLANNEL_DARK   = col_srgb(0.25, 0.23, 0.22)
FLANNEL_COLLAR = col_srgb(0.57, 0.29, 0.20)

TEE_CREAM      = col_srgb(0.95, 0.92, 0.86)
UNDERSHIRT     = col_srgb(0.29, 0.28, 0.29)

CASE_MAIN      = col_srgb(0.27, 0.25, 0.24)
CASE_SIDE      = col_srgb(0.22, 0.20, 0.19)
CASE_SHADE     = col_srgb(0.18, 0.17, 0.16)
STRAP          = col_srgb(0.21, 0.20, 0.20)

PANTS          = col_srgb(0.31, 0.32, 0.36)
PANTS_SHADE    = col_srgb(0.23, 0.24, 0.28)

BOOT           = col_srgb(0.60, 0.43, 0.27)
BOOT_SHADE     = col_srgb(0.49, 0.34, 0.20)
SOLE           = col_srgb(0.30, 0.22, 0.17)


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


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=6, phase=math.pi / 6.0):
    """6-sided ring tilted backward around X by tilt_rad (higher at +Z front, lower at -Z back)."""
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
    # 1. UNIFIED HEAD + FULL BEARD (6-sided, 3 rings + chin cap = 28 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks,
    # k=1,2,3 are back/sides (dark hair & rear beard)
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.204,  0.022, 0.165, 0.162),  # 0: full rounded bearded chin/jaw
        (1.318,  0.020, 0.214, 0.204),  # 1: beard top / cheek line
        (1.505,  0.008, 0.210, 0.198),  # 2: forehead / tucked under beanie cuff
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        if i == 0:
            # Lower face: full dark brown beard across front/cheeks, dark hair at nape
            return BEARD if k in (4, 5, 0) else HAIR_DARK
        # Upper face: warm peach skin on front/cheeks, dark espresso hair behind ears/back
        return SKIN if k in (4, 5, 0) else HAIR_DARK

    mb.loft(head_rings, head_color, cap_bottom=True, cap_top=False, bot_color=BEARD_DARK)

    # =========================================================================
    # 2. SCULPTED BUSHY MUSTACHE + FRONT BEARD VOLUME (8 tris)
    # =========================================================================
    mb.set_part("mustache", bone="Head")
    # Prominent plush hipster mustache curving naturally into full cheek beard
    p_ct_t = V(0.000, 1.334, 0.228)  # center bridge top (under nose)
    p_ct_b = V(0.000, 1.284, 0.224)  # center bottom lip arch blending into beard
    p_cb_t = V(0.000, 1.330, 0.194)  # center back top (flush in face)
    p_cb_b = V(0.000, 1.278, 0.190)  # center back bottom
    for side in (-1, 1):
        p_out_f = V(side * 0.104, 1.288, 0.208)  # outer drooping wing tip front
        p_out_b = V(side * 0.114, 1.286, 0.170)  # outer wing tucked into cheek beard
        # Front wing face (2 tris), top bevel (1 tri), underside bevel (1 tri) = 4 tris/wing -> 8 tris!
        mb.face([p_ct_b, p_out_f, p_out_b, p_ct_t], MUSTACHE,   out=(side * 0.2, 0.1, 1.0))
        mb.face([p_ct_t, p_out_b, p_cb_t],          BEARD,      out=(0, 1, 0.2))
        mb.face([p_ct_b, p_cb_b, p_out_f],          BEARD_DARK, out=(0, -1, 0.1))

    # =========================================================================
    # 3. EARS (2 chunky rounded low-poly tabs = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.196
        x_out = side * 0.232
        y0, y1 = 1.312, 1.398
        z0, z1 = -0.014, 0.048
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.018, zm)
        p_ot = V(x_out, y1 - 0.018, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. RUST-RED FOLDED-CUFF BEANIE (6-sided tilted cap = 28 tris)
    # =========================================================================
    mb.set_part("beanie", bone="Head")
    tilt = math.radians(17.5)
    cuff_bot   = tilted_ring(0.0, 1.448, -0.008, 0.244, 0.238, tilt)
    cuff_top   = tilted_ring(0.0, 1.546, -0.022, 0.250, 0.244, tilt)
    dome_crown = tilted_ring(0.0, 1.692, -0.050, 0.148, 0.145, tilt)
    mb.loft([cuff_bot, cuff_top], BEANIE_CUFF, cap_bottom=False, cap_top=False)
    mb.loft([cuff_top, dome_crown], BEANIE, cap_bottom=False, cap_top=True, top_color=BEANIE)

    # =========================================================================
    # 5. ROUND BLACK-FRAMED GLASSES (2x6-sided beveled hollow frames + bridge + temples = 58 tris)
    # =========================================================================
    mb.set_part("glasses", bone="Head")
    # Watertight 3D beveled 6-sided round frames resting directly on flat front face (z_face ≈ 0.196)
    z_face = 0.195
    z_ridge = 0.215
    cy_g = 1.390
    r_out = 0.058
    r_mid = 0.048
    r_in  = 0.038
    n_seg = 6
    for side in (-1, 1):
        cx = side * 0.065
        p_out, p_mid, p_in = [], [], []
        for k in range(n_seg):
            a = math.pi / 6.0 + 2.0 * math.pi * k / n_seg
            ca, sa = math.cos(a), math.sin(a)
            p_out.append(V(cx + r_out * ca, cy_g + r_out * sa, z_face))
            p_mid.append(V(cx + r_mid * ca, cy_g + r_mid * sa, z_ridge))
            p_in.append( V(cx + r_in  * ca, cy_g + r_in  * sa, z_face))
        for k in range(n_seg):
            kn = (k + 1) % n_seg
            a_mid = math.pi / 6.0 + 2.0 * math.pi * (k + 0.5) / n_seg
            rad = V(math.cos(a_mid), math.sin(a_mid), 0.0)
            # Outer front bevel + inner front bevel (2 quads/seg = 24 tris per lens, zero gaps!)
            mb.face([p_out[k], p_out[kn], p_mid[kn], p_mid[k]], GLASSES, out=rad + V(0, 0, 0.8))
            mb.face([p_mid[k], p_mid[kn], p_in[kn],  p_in[k]],  GLASSES, out=-rad + V(0, 0, 0.8))

    # Crisp thin nose bridge (1 front quad = 2 tris)
    mb.face([
        V(-0.020, cy_g + 0.002, z_ridge - 0.002),
        V( 0.020, cy_g + 0.002, z_ridge - 0.002),
        V( 0.020, cy_g + 0.017, z_ridge - 0.002),
        V(-0.020, cy_g + 0.017, z_ridge - 0.002),
    ], GLASSES, out=(0, 0, 1))

    # Two dark temple arms stretching from outer frames straight back over ears into hair (4 tris x 2 = 8 tris)
    for side in (-1, 1):
        x_f = side * (0.065 + r_out - 0.007)
        x_b = side * 0.218
        y_t0, y_t1 = cy_g + 0.002, cy_g + 0.018
        z_tf, z_tb = z_face + 0.009, 0.018
        t_in = side * (-0.012)
        p0 = V(x_f, y_t0, z_tf); p1 = V(x_f, y_t1, z_tf)
        q0 = V(x_b, y_t0, z_tb); q1 = V(x_b, y_t1, z_tb)
        p1i = V(x_f + t_in, y_t1, z_tf); q1i = V(x_b + t_in, y_t1, z_tb)
        mb.face([p0, q0, q1, p1],   GLASSES, out=(side, 0, 0))
        mb.face([p1, q1, q1i, p1i], GLASSES, out=(0, 1, 0))

    # =========================================================================
    # 6. NECK (3-sided sturdy front/side prism, skip rear hidden by hair/case = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_pts_b = [V(-0.074, 1.110, -0.048), V(0.000, 1.110, 0.076), V(0.074, 1.110, -0.048)]
    n_pts_t = [V(-0.070, 1.216, -0.044), V(0.000, 1.216, 0.072), V(0.070, 1.216, -0.044)]
    mb.face([n_pts_b[0], n_pts_b[1], n_pts_t[1], n_pts_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_pts_b[1], n_pts_b[2], n_pts_t[2], n_pts_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 7. INNER CREAM TEE + DARK CHARCOAL UNDERSHIRT V-PEEK (3 tris)
    # =========================================================================
    mb.set_part("inner_tee", bone="Torso")
    jy0, jy1 = 0.650, 1.132
    jx_b, jx_t = 0.212, 0.194
    jz_fb, jz_ft = 0.132, 0.122
    jz_bb, jz_bt = -0.122, -0.114
    v_open = 0.066  # half-width of open center showing cream t-shirt

    # Cream t-shirt center front panel recessed slightly behind flannel lapels (2 tris)
    z_tee_b = jz_fb - 0.008
    z_tee_t = jz_ft - 0.008
    mb.face([
        V(-v_open - 0.006, jy0, z_tee_b),
        V( v_open + 0.006, jy0, z_tee_b),
        V( v_open + 0.006, jy1, z_tee_t),
        V(-v_open - 0.006, jy1, z_tee_t),
    ], TEE_CREAM, out=(0, 0, 1))

    # Dark charcoal undershirt V-neck triangle peeking cleanly at top of cream tee (1 tri)
    mb.face([
        V(-0.052, jy1 - 0.002, z_tee_t + 0.004),
        V( 0.052, jy1 - 0.002, z_tee_t + 0.004),
        V( 0.000, jy1 - 0.112, z_tee_t + 0.006),
    ], UNDERSHIRT, out=(0, 0, 1))

    # =========================================================================
    # 8. OPEN PLAID FLANNEL SHIRT TORSO + FOLDED COLLAR (38 tris)
    # =========================================================================
    mb.set_part("flannel_torso", bone="Torso")

    def torso_x_out(t):
        return jx_b + (jx_t - jx_b) * t

    def torso_zf(t):
        return jz_fb + (jz_ft - jz_fb) * t

    def torso_zb(t):
        return jz_bb + (jz_bt - jz_bb) * t

    # Open front plaid lapels: 2 cols x 2 rows per side (16 tris total -> bold chunky flannel checks!)
    front_plaid = [
        [FLANNEL_RUST,  FLANNEL_BROWN],  # bottom row (inner, outer)
        [FLANNEL_BROWN, FLANNEL_RUST],   # top row (inner, outer)
    ]
    y_rows = [jy0, 0.5 * (jy0 + jy1), jy1]
    t_rows = [0.0, 0.5, 1.0]
    for side in (-1, 1):
        for r in range(2):
            ya, yb = y_rows[r], y_rows[r + 1]
            ta, tb = t_rows[r], t_rows[r + 1]
            zfa, zfb = torso_zf(ta), torso_zf(tb)
            xa_out, xb_out = torso_x_out(ta), torso_x_out(tb)
            xa_mid = 0.5 * (v_open + xa_out)
            xb_mid = 0.5 * (v_open + xb_out)
            xs_a = [side * v_open, side * xa_mid, side * xa_out]
            xs_b = [side * v_open, side * xb_mid, side * xb_out]
            for c in range(2):
                col = front_plaid[r][c]
                if (r == 0 and c == 1) or (r == 1 and c == 0):
                    col = FLANNEL_DARK if side > 0 else FLANNEL_BROWN
                elif side < 0 and r == 0 and c == 0:
                    col = FLANNEL_DARK
                mb.face([
                    V(xs_a[c],     ya, zfa),
                    V(xs_a[c + 1], ya, zfa),
                    V(xs_b[c + 1], yb, zfb),
                    V(xs_b[c],     yb, zfb),
                ], col, out=(0, 0, 1))

    # Side panels: 1 col x 2 rows per side (8 tris)
    for side in (-1, 1):
        for r in range(2):
            ya, yb = y_rows[r], y_rows[r + 1]
            ta, tb = t_rows[r], t_rows[r + 1]
            xa, xb = side * torso_x_out(ta), side * torso_x_out(tb)
            col = FLANNEL_RUST if r == 0 else FLANNEL_DARK
            mb.face([
                V(xa, ya, torso_zf(ta)),
                V(xa, ya, torso_zb(ta)),
                V(xb, yb, torso_zb(tb)),
                V(xb, yb, torso_zf(tb)),
            ], col, out=(side, 0, 0))

    # Back panel (mostly behind guitar case, 1 clean quad = 2 tris)
    mb.face([
        V( jx_b, jy0, jz_bb),
        V(-jx_b, jy0, jz_bb),
        V(-jx_t, jy1, jz_bt),
        V( jx_t, jy1, jz_bt),
    ], FLANNEL_RUST, out=(0, 0, -1))

    # Shoulder tops (2 quads = 4 tris)
    for side in (-1, 1):
        mb.face([
            V(side * v_open, jy1, jz_ft),
            V(side * jx_t,   jy1, jz_ft),
            V(side * jx_t,   jy1, jz_bt),
            V(side * v_open, jy1, jz_bt),
        ], FLANNEL_RUST, out=(0, 1, 0))

    # Folded flannel shirt collar lapels flanking the neck (2 angled 3D flaps = 4 tris)
    for side in (-1, 1):
        mb.face([
            V(side * 0.056, 1.120, 0.130),
            V(side * 0.128, 1.072, 0.134),
            V(side * 0.146, 1.158, 0.055),
            V(side * 0.068, 1.168, 0.072),
        ], FLANNEL_COLLAR, out=(side * 0.25, 0.35, 0.90))

    # =========================================================================
    # 9. PLAID FLANNEL SLEEVES (2x3 outer plaid + 1x2 front + 1x2 back + 1 inner = 44 tris)
    # =========================================================================
    mb.set_part("flannel_sleeves")
    # Relaxed slightly bent arms tucked seamlessly into shoulders so they swing freely past guitar case!
    arm_specs = [
        ( 1, "Arm_L", V( 0.168, 1.078,  0.006), V( 0.278, 0.862, -0.002), V( 0.290, 0.708, 0.044)),
        (-1, "Arm_R", V(-0.168, 1.078,  0.006), V(-0.278, 0.862, -0.002), V(-0.290, 0.708, 0.044)),
    ]

    # Outer 2x3 plaid pattern (matching reference flannel!)
    sleeve_outer_plaid = [
        [FLANNEL_RUST,  FLANNEL_DARK],   # upper arm (front-col, back-col)
        [FLANNEL_DARK,  FLANNEL_RUST],   # mid elbow
        [FLANNEL_BROWN, FLANNEL_DARK],   # forearm/cuff
    ]
    sleeve_front_cols = [FLANNEL_RUST, FLANNEL_DARK]
    sleeve_back_cols  = [FLANNEL_DARK, FLANNEL_RUST]

    for (side, bname, p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        # Keep p0 -> p1 -> p2 strictly collinear & linearly interpolated so 0->2 front/back quads are 100% watertight!
        p0 = p_sh
        p2 = p_el
        p1 = p0.lerp(p2, 0.5)
        p3 = p_wr
        pts_arm = [p0, p1, p2, p3]
        r0_sz = (0.076, 0.086)
        r2_sz = (0.088, 0.092)
        r1_sz = (0.5 * (r0_sz[0] + r2_sz[0]), 0.5 * (r0_sz[1] + r2_sz[1]))
        r3_sz = (0.078, 0.082)
        rads = [r0_sz, r1_sz, r2_sz, r3_sz]

        ax_up = (p2 - p0).normalized()
        ax_lo = (p3 - p2).normalized()

        # Build 4 corner rings: [front-in, front-out, back-out, back-in]
        rings = []
        for idx in range(4):
            ax = ax_up if idx < 3 else ax_lo
            fwd = V(0.0, 0.0, 1.0)
            out_x = V(side, 0.0, 0.0)
            u = out_x - ax * out_x.dot(ax)
            u = u.normalized()
            v = fwd - ax * fwd.dot(ax)
            v = (v - u * v.dot(u)).normalized()
            ru, rv = rads[idx]
            c = pts_arm[idx]
            rings.append([
                c - u * ru + v * rv,  # 0: front-in
                c + u * ru + v * rv,  # 1: front-out
                c + u * ru - v * rv,  # 2: back-out
                c - u * ru - v * rv,  # 3: back-in
            ])
        # Guarantee exact midpoint linearity on ring 1 (zero hairline gap against 0->2 quads!)
        rings[1] = [rings[0][k].lerp(rings[2][k], 0.5) for k in range(4)]

        # Outer face: 2 cols x 3 rows = 6 quads (12 tris) — unmistakable plaid!
        for b in range(3):
            r0, r1 = rings[b], rings[b + 1]
            m0 = r0[1].lerp(r0[2], 0.5)
            m1 = r1[1].lerp(r1[2], 0.5)
            mb.face([r0[1], m0, m1, r1[1]], sleeve_outer_plaid[b][0], out=(side, 0, 0))
            mb.face([m0, r0[2], r1[2], m1], sleeve_outer_plaid[b][1], out=(side, 0, 0))

        # Front face: 1 col x 2 rows = 2 quads (4 tris)
        mb.face([rings[0][0], rings[0][1], rings[2][1], rings[2][0]], sleeve_front_cols[0], out=(0, 0, 1))
        mb.face([rings[2][0], rings[2][1], rings[3][1], rings[3][0]], sleeve_front_cols[1], out=(0, 0, 1))

        # Back face: 1 col x 2 rows = 2 quads (4 tris)
        mb.face([rings[0][2], rings[0][3], rings[2][3], rings[2][2]], sleeve_back_cols[0], out=(0, 0, -1))
        mb.face([rings[2][2], rings[2][3], rings[3][3], rings[3][2]], sleeve_back_cols[1], out=(0, 0, -1))

        # Inner face (tucked against torso): 1 single quad (2 tris)
        mb.face([rings[0][3], rings[0][0], rings[3][0], rings[3][3]], FLANNEL_DARK, out=(-side, 0, 0))

    # =========================================================================
    # 10. CHUNKY TAN HANDS (2 x 10 tris = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for (side, bname, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        out_x = V(side, 0.0, 0.0)
        u = (out_x - ax * out_x.dot(ax)).normalized()
        fwd = V(0.0, 0.0, 1.0)
        v = (fwd - ax * fwd.dot(ax))
        v = (v - u * v.dot(u)).normalized()

        c0 = p_wr - ax * 0.010
        c1 = p_wr + ax * 0.105
        r0 = [
            c0 - u * 0.052 + v * 0.056,
            c0 + u * 0.052 + v * 0.056,
            c0 + u * 0.052 - v * 0.056,
            c0 - u * 0.052 - v * 0.056,
        ]
        r1 = [
            c1 - u * 0.042 + v * 0.046,
            c1 + u * 0.042 + v * 0.046,
            c1 + u * 0.042 - v * 0.046,
            c1 - u * 0.042 - v * 0.046,
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 11. ACOUSTIC GUITAR CASE ON BACK (5-level contoured gig bag = 36 tris) + STRAPS (8 tris)
    # =========================================================================
    mb.set_part("guitar_case", bone="GuitarCase")
    # Slung snugly against back, tilting backward (+11 deg) so neck clears beanie cleanly with zero back gap!
    case_tilt = math.radians(11.0)
    ct, st = math.cos(case_tilt), math.sin(case_tilt)
    case_orig = V(0.0, 0.460, -0.168)  # bottom center of guitar case

    def case_pt(lx, ly, lz):
        ry = ly * ct + lz * st
        rz = -ly * st + lz * ct
        return V(case_orig.x + lx, case_orig.y + ry, case_orig.z + rz)

    # 5 symmetric horizontal levels defining the unmistakable acoustic guitar silhouette:
    # (ly, half_w, zf hugging torso back, zb forming clean tilted rear silhouette)
    case_levels = [
        (0.000, 0.148, 0.052, -0.095),  # 0: flat rounded lower base
        (0.150, 0.224, 0.082, -0.122),  # 1: wide chunky acoustic lower bout (flush w/ jacket hem)
        (0.455, 0.202, 0.136, -0.118),  # 2: upper body shoulder (flush w/ upper back!)
        (0.605, 0.114, 0.110, -0.092),  # 3: crisp taper into guitar neck
        (1.165, 0.098, 0.072, -0.082),  # 4: tall headstock rising prominently behind beanie
    ]
    # Build 10-point perimeter loops for front (+Z facing torso) and back (-Z facing outward)
    front_loop = []
    back_loop = []
    for (ly, hw, zf, zb) in case_levels:
        front_loop.append(case_pt( hw, ly, zf))
        back_loop.append( case_pt( hw, ly, zb))
    for (ly, hw, zf, zb) in reversed(case_levels):
        front_loop.append(case_pt(-hw, ly, zf))
        back_loop.append( case_pt(-hw, ly, zb))

    # Side perimeter wall (10 quads = 20 tris)
    n_p = len(front_loop)
    c_mid = case_pt(0.0, 0.54, 0.0)
    for k in range(n_p):
        kn = (k + 1) % n_p
        p0, p1, p2, p3 = front_loop[k], front_loop[kn], back_loop[kn], back_loop[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        col = CASE_SHADE if k in (4, 9) else CASE_SIDE
        mb.face([p0, p1, p2, p3], col, out=(mid - c_mid))

    # Back face (4 horizontal quads = 8 tris) & Front face (4 horizontal quads = 8 tris)
    for i in range(len(case_levels) - 1):
        r_idx0 = i
        r_idx1 = i + 1
        l_idx0 = n_p - 1 - i
        l_idx1 = n_p - 1 - (i + 1)
        mb.face([back_loop[r_idx0], back_loop[r_idx1], back_loop[l_idx1], back_loop[l_idx0]],
                CASE_MAIN, out=V(0, -st, -ct))
        mb.face([front_loop[r_idx0], front_loop[l_idx0], front_loop[l_idx1], front_loop[r_idx1]],
                CASE_SHADE, out=V(0, st, ct))

    # Dark charcoal shoulder straps hugging over flannel shoulders & curving smoothly toward underarms (8 tris)
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        xa_t = min(side * 0.126, side * 0.178)
        xb_t = max(side * 0.126, side * 0.178)
        xa_b = min(side * 0.162, side * 0.214)
        xb_b = max(side * 0.162, side * 0.214)
        # Shoulder top strap quad
        mb.face([
            V(xa_t, 1.139, -0.120),
            V(xb_t, 1.139, -0.120),
            V(xb_t, 1.139,  0.128),
            V(xa_t, 1.139,  0.128),
        ], STRAP, out=(0, 1, 0))
        # Front chest strap curving outward toward underarm
        mb.face([
            V(xa_b, 0.895, 0.136),
            V(xb_b, 0.895, 0.136),
            V(xb_t, 1.139, 0.128),
            V(xa_t, 1.139, 0.128),
        ], STRAP, out=(0, 0, 1))

    # =========================================================================
    # 12. DARK CHARCOAL STRAIGHT WIDE PANTS (8 + 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.188, 0.188, 0.548, 0.668, -0.106, 0.106, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.186
        x_in_b, x_out_b = side * 0.058, side * 0.228
        rz_t, rz_b = 0.098, 0.100
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.165,  rz_b),
            V(max(x_in_b, x_out_b), 0.165,  rz_b),
            V(max(x_in_b, x_out_b), 0.165, -rz_b),
            V(min(x_in_b, x_out_b), 0.165, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 13. CHUNKY BROWN BOOTS WITH DARK SOLES (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.144
        w = 0.070
        w_toe = 0.058
        z_heel = -0.092
        z_toe  =  0.168
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_col   = 0.175

        # Layer 1: Thick dark chocolate-brown outsole (10 tris)
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

        # Layer 2: Chunky warm brown leather boot upper rising into pant hem (8 tris)
        boot_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, 0.052),
            V(cx - w * 0.84, y_col, 0.052),
        ]
        mb.loft([sole_top, boot_top], lambda i, k: BOOT_SHADE if k == 2 else BOOT,
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
    """24-frame looping Walk cycle: easygoing rhythmic stride, relaxed arm swing & weighted guitar case sway."""
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
        s2 = math.sin(2.0 * phi)

        # Easygoing casual walk bounce & slight forward lean balancing the guitar case
        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        root_pitch = -0.052
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.068 * s1, 0.034 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Natural torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.020 * c2, 0.095 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle laid-back musical head nod keeping glasses level
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.042 + 0.032 * s2, -0.040 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Clean alternating stride with crisp foot lift on swing phase
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.45 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.038, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.45 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.038, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Relaxed counter-swinging arms (slight forward bias so cuffs clear the guitar case!)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.28 * s1 - 0.04, 0.0, 0.035)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.28 * s1 - 0.04, 0.0, -0.035)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Weighted guitar case bounces & sways gently with slight phase lag behind steps
        pb_case = rig.pose.bones["GuitarCase"]
        pb_case.location = (0.0, 0.009 * math.sin(2.0 * phi - 0.65), 0.0)
        pb_case.rotation_euler = (0.028 * math.sin(2.0 * phi - 0.65), 0.0, -0.034 * math.sin(phi - 0.50))
        pb_case.keyframe_insert(data_path="location", frame=frame)
        pb_case.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: chill dockside sway, casual look-around & subtle guitar case settle."""
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

        # Calm weight shift & relaxed breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.012, 0.024 * s1, 0.020 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.028 * s1, -0.016 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Laid-back look-around & gentle rhythm nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.055 * s2, 0.21 * s1, 0.036 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs planted squarely
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed arms drifting softly with breathing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.045 * s1 - 0.016 * s2, 0.0, 0.018 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.042 * s1 - 0.016 * s2, 0.0, -0.018 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Guitar case settles subtly with breathing
        pb_case = rig.pose.bones["GuitarCase"]
        pb_case.location = (0.0, 0.004 * s2, 0.0)
        pb_case.rotation_euler = (0.016 * s2, 0.0, -0.016 * s1)
        pb_case.keyframe_insert(data_path="location", frame=frame)
        pb_case.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + GuitarCase) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonHipsterRig")
    rig = bpy.data.objects.new("PersonHipsterRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",       None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",      "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",       "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Arm_L",      "Torso", ( 0.168, 1.078,  0.006), ( 0.168, 1.238,  0.006)),
        ("Arm_R",      "Torso", (-0.168, 1.078,  0.006), (-0.168, 1.238,  0.006)),
        ("GuitarCase", "Torso", ( 0.000, 1.020, -0.180), ( 0.000, 1.240, -0.235)),
        ("Leg_L",      "Root",  ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R",      "Root",  (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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
        (-1.68, math.radians(60)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (showing guitar case, plaid sleeve, glasses, beanie)
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=60):
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=54, zrot_right_deg=90):
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
    "hair": [HAIR_DARK, BEARD, BEARD_DARK, MUSTACHE],
    "top": [FLANNEL_RUST, FLANNEL_BROWN, FLANNEL_DARK, FLANNEL_COLLAR],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [BEANIE, BEANIE_CUFF, BEANIE_SHADE],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonHipster")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonHipster")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonHipster", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=60)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=54, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonHipster Stats ===")
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
