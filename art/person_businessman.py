# Builds an ultra-low-poly (< 350 tris) stylized nerdy businessman with glasses, navy V-neck
# sweater over white collared shirt & tie, khaki chinos, brown leather shoes, and a crossbody
# dark brown leather satchel in Blender matching the reference.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_businessman.py)
# Saves art/person_businessman.blend, exports assets/models/person_businessman.glb (rigged + Walk & Idle cycles),
# renders art/person_businessman_preview.png, art/person_businessman_walk_preview.png,
# art/person_businessman_idle_preview.png, and outputs rendered videos
# art/person_businessman_walk.mp4 and art/person_businessman_idle.mp4.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_businessman.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_businessman.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_businessman_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_businessman_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_businessman_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_businessman_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_businessman_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference image (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN           = col_srgb(0.97, 0.72, 0.48)
SKIN_SHADE     = col_srgb(0.86, 0.61, 0.39)

HAIR           = col_srgb(0.34, 0.26, 0.21)
HAIR_SHADE     = col_srgb(0.25, 0.19, 0.15)

EYE            = col_srgb(0.10, 0.10, 0.12)
GLASSES        = col_srgb(0.16, 0.16, 0.18)

SHIRT          = col_srgb(0.96, 0.95, 0.92)
SHIRT_SHADE    = col_srgb(0.85, 0.84, 0.81)
TIE            = col_srgb(0.29, 0.36, 0.47)
TIE_SHADE      = col_srgb(0.21, 0.27, 0.36)

SWEATER        = col_srgb(0.24, 0.29, 0.39)
SWEATER_SHADE  = col_srgb(0.18, 0.22, 0.31)
SWEATER_CUFF   = col_srgb(0.21, 0.25, 0.34)

SATCHEL        = col_srgb(0.41, 0.32, 0.25)
SATCHEL_SHADE  = col_srgb(0.30, 0.23, 0.17)
SATCHEL_FLAP   = col_srgb(0.46, 0.36, 0.28)
SATCHEL_STRAP  = col_srgb(0.48, 0.37, 0.27)

PANTS          = col_srgb(0.80, 0.70, 0.53)
PANTS_SHADE    = col_srgb(0.69, 0.59, 0.43)

SHOE           = col_srgb(0.56, 0.40, 0.26)
SHOE_SHADE     = col_srgb(0.45, 0.31, 0.19)
SOLE           = col_srgb(0.32, 0.23, 0.16)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_SHADE],
    "top": [SWEATER, SWEATER_SHADE, SWEATER_CUFF],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [SATCHEL, SATCHEL_SHADE, SATCHEL_FLAP, SATCHEL_STRAP],
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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None,
             skip_k=(), ring_weights=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            w0 = ring_weights[i] if ring_weights is not None else None
            w1 = ring_weights[i + 1] if ring_weights is not None else None
            for k in range(n):
                if k in skip_k:
                    continue
                kn = (k + 1) % n
                p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
                col = colors(i, k) if callable(colors) else colors
                mid = (p0 + p1 + p2 + p3) * 0.25
                ws = [w0, w0, w1, w1] if (w0 is not None and w1 is not None) else None
                self.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=ws)
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            w0 = ring_weights[0] if ring_weights is not None else None
            if n <= 4:
                ws = [w0] * n if w0 is not None else None
                self.face(r0, col, out=out_dir, weights=ws)
            elif n == 6:
                ws = [w0] * 4 if w0 is not None else None
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=ws)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=ws)
            else:
                ws = [w0] * 3 if w0 is not None else None
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=ws)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt = ring_weights[-1] if ring_weights is not None else None
            if n <= 4:
                ws = [wt] * n if wt is not None else None
                self.face(rt, col, out=out_dir, weights=ws)
            elif n == 6:
                ws = [wt] * 4 if wt is not None else None
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=ws)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=ws)
            else:
                ws = [wt] * 3 if wt is not None else None
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=ws)

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


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + INTEGRATED NAPE/SIDE HAIR (6-sided, flat front face = 41 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 (330..30 deg) is wide flat front face (+Z),
    # k=0 (+X front-left cheek) & k=4 (-X front-right cheek), k=1,2,3 back/nape hair
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.198,  0.012, 0.152, 0.146),  # 0: chin/jaw base
        (1.278,  0.016, 0.210, 0.198),  # 1: lower cheek
        (1.508,  0.012, 0.212, 0.200),  # 2: brow / forehead hairline
        (1.612, -0.012, 0.196, 0.198),  # 3: upper skull crown blending cleanly into parted top
    ]
    head_rings = []
    for i, (y, cz, rx, rz) in enumerate(head_specs):
        ring = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
        # Sculpt fuller back-of-head hair volume continuously from nape to crown (no abrupt shelf!)
        if i == 1:
            for k in (2, 3):
                p = ring[k]
                ring[k] = V(p.x * 1.04, p.y, p.z * 1.06 - 0.012)
        elif i == 2:
            for k in (1, 2, 3, 4):
                p = ring[k]
                if k in (2, 3):
                    ring[k] = V(p.x * 1.08, p.y, p.z * 1.10 - 0.022)
                else:
                    ring[k] = V(p.x * 1.03, p.y, p.z)
        elif i == 3:
            for k in (2, 3):
                p = ring[k]
                ring[k] = V(p.x * 1.05, p.y, p.z * 1.05 - 0.012)
        head_rings.append(ring)

    def head_color(i, k):
        if i == 2:
            return HAIR
        if i == 1:
            return SKIN if k in (4, 5, 0) else HAIR
        return HAIR_SHADE if k in (1, 2, 3) else SKIN

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
                # Subtle asymmetric side-part hairline notch on forehead (+X side)
                # Keep height low (35% up from brow to crown) so forehead stays broad & natural, not pointy!
                part_notch = p0.lerp(p1, 0.72).lerp(p3.lerp(p2, 0.72), 0.34)
                part_notch = V(part_notch.x, part_notch.y, part_notch.z + 0.008)
                mb.face([p0, p1, part_notch], SKIN, out=(0, 0, 1))
                mb.face([p0, part_notch, p3], HAIR, out=(0, 0, 1))
                mb.face([p1, p2, part_notch], HAIR, out=(0, 0, 1))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    # Chin bottom cap (2 quads = 4 tris)
    rb = head_rings[0]
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[3], rb[4], rb[5], rb[0]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. SCULPTED SIDE-PARTED HAIR CREST + NEAT SIDEBURNS (22 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # Main swept hair crest covering center & right side (-X .. +0.066), corners tucked to match
    # the 6-sided skull radius cleanly (zero square-corner rear overhang!)
    hc_bot = [
        V(-0.172, 1.540,  0.132),  # front-right brow sweep (flush with skull corner)
        V( 0.064, 1.552,  0.168),  # front-left part edge
        V( 0.098, 1.568, -0.178),  # back-left crown (flush with rear skull)
        V(-0.152, 1.548, -0.174),  # back-right crown (tucked smoothly onto skull!)
    ]
    hc_top = [
        V(-0.130, 1.674,  0.112),  # top front-right
        V( 0.054, 1.686,  0.132),  # top front-left (crisp part ridge!)
        V( 0.082, 1.670, -0.136),  # top back-left
        V(-0.124, 1.656, -0.138),  # top back-right
    ]
    mb.loft([hc_bot, hc_top], lambda i, k: HAIR_SHADE if k == 2 else HAIR,
            cap_bottom=False, cap_top=True, top_color=HAIR)

    # Secondary left-side hair sweep tucked slightly lower beside the part ridge (4 quads = 8 tris)
    hl_b = [
        V(0.058, 1.546,  0.158),
        V(0.184, 1.535,  0.092),
        V(0.176, 1.545, -0.142),
        V(0.088, 1.564, -0.174),
    ]
    hl_t = [
        V(0.058, 1.642,  0.118),
        V(0.148, 1.630,  0.074),
        V(0.142, 1.622, -0.116),
        V(0.076, 1.640, -0.134),
    ]
    mb.loft([hl_b, hl_t], HAIR, cap_bottom=False, cap_top=True, top_color=HAIR, skip_k=(3,))

    # Neat tapered sideburns derived directly from cheek planes (100% flush, zero gap/z-fighting = 4 tris)
    for side in (-1, 1):
        # Cheek face is k=4 (verts 4->5) on -X side, k=0 (verts 1->0) on +X side
        if side < 0:
            v1_back, v1_front = head_rings[1][4], head_rings[1][5]
            v2_back, v2_front = head_rings[2][4], head_rings[2][5]
        else:
            v1_back, v1_front = head_rings[1][1], head_rings[1][0]
            v2_back, v2_front = head_rings[2][1], head_rings[2][0]
        cheek_out = V(side * 0.866, 0.0, 0.500) * 0.0045
        # Span from y=1.345 (mid-ear) up to y=1.508 (brow hairline), from rear edge (u=-0.03) to u=0.28 forward
        t_bot = (1.345 - 1.278) / (1.508 - 1.278)
        b_back  = v1_back.lerp(v2_back, t_bot)
        b_front = v1_front.lerp(v2_front, t_bot)
        p_t_b = v2_back.lerp(v2_front, -0.02) + cheek_out
        p_t_f = v2_back.lerp(v2_front,  0.34) + cheek_out
        p_b_f = b_back.lerp(b_front,    0.20) + cheek_out
        p_b_b = b_back.lerp(b_front,   -0.02) + cheek_out
        mb.face([p_b_b, p_b_f, p_t_f, p_t_b], HAIR, out=cheek_out)

    # =========================================================================
    # 3. EARS (2 chunky rounded low-poly tabs = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.198
        x_out = side * 0.238
        y0, y1 = 1.298, 1.388
        z0, z1 = -0.022, 0.042
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.016, zm)
        p_ot = V(x_out, y1 - 0.016, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. EYES (2 vertical dark pill hexagons inside glasses frames = 8 tris)
    # =========================================================================
    # Exact flat front face plane at y=1.390 (linear interp between ring 1 & ring 2)
    t_eye = (1.392 - 1.278) / (1.508 - 1.278)
    z_face = head_rings[1][5].z + (head_rings[2][5].z - head_rings[1][5].z) * t_eye
    mb.set_part("eyes", bone="Head")
    z_eye = z_face + 0.004
    cy_g = 1.392
    for side in (-1, 1):
        cx = side * 0.065
        rx = 0.017
        ry = 0.036
        pts = [
            V(cx,      cy_g + ry,        z_eye),
            V(cx + rx, cy_g + ry * 0.56, z_eye),
            V(cx + rx, cy_g - ry * 0.56, z_eye),
            V(cx,      cy_g - ry,        z_eye),
            V(cx - rx, cy_g - ry * 0.56, z_eye),
            V(cx - rx, cy_g + ry * 0.56, z_eye),
        ]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. ROUND BLACK-FRAMED GLASSES (frames + bridge + temples = 58 tris)
    # =========================================================================
    mb.set_part("glasses", bone="Head")
    z_g_base = z_face + 0.0045
    z_g_ridge = z_face + 0.022
    r_out = 0.061
    r_mid = 0.052
    r_in  = 0.043
    n_seg = 6
    for side in (-1, 1):
        cx = side * 0.065
        p_out, p_mid, p_in = [], [], []
        for k in range(n_seg):
            a = math.pi / 6.0 + 2.0 * math.pi * k / n_seg
            ca, sa = math.cos(a), math.sin(a)
            p_out.append(V(cx + r_out * ca, cy_g + r_out * sa, z_g_base))
            p_mid.append(V(cx + r_mid * ca, cy_g + r_mid * sa, z_g_ridge))
            p_in.append( V(cx + r_in  * ca, cy_g + r_in  * sa, z_g_base))
        for k in range(n_seg):
            kn = (k + 1) % n_seg
            a_mid = math.pi / 6.0 + 2.0 * math.pi * (k + 0.5) / n_seg
            rad = V(math.cos(a_mid), math.sin(a_mid), 0.0)
            mb.face([p_out[k], p_out[kn], p_mid[kn], p_mid[k]], GLASSES, out=rad + V(0, 0, 0.8))
            mb.face([p_mid[k], p_mid[kn], p_in[kn],  p_in[k]],  GLASSES, out=-rad + V(0, 0, 0.8))

    # Crisp nose bridge (1 quad = 2 tris)
    mb.face([
        V(-0.017, cy_g + 0.002, z_g_ridge - 0.002),
        V( 0.017, cy_g + 0.002, z_g_ridge - 0.002),
        V( 0.017, cy_g + 0.016, z_g_ridge - 0.002),
        V(-0.017, cy_g + 0.016, z_g_ridge - 0.002),
    ], GLASSES, out=(0, 0, 1))

    # Dark temple arms running cleanly from outer frames back over ears (4 tris x 2 = 8 tris)
    for side in (-1, 1):
        x_f = side * (0.065 + r_out - 0.006)
        x_b = side * 0.220
        y_t0, y_t1 = cy_g - 0.002, cy_g + 0.014
        z_tf, z_tb = z_g_base + 0.009, 0.012
        t_in = side * (-0.012)
        p0 = V(x_f, y_t0, z_tf); p1 = V(x_f, y_t1, z_tf)
        q0 = V(x_b, y_t0, z_tb); q1 = V(x_b, y_t1, z_tb)
        p1i = V(x_f + t_in, y_t1, z_tf); q1i = V(x_b + t_in, y_t1, z_tb)
        mb.face([p0, q0, q1, p1],   GLASSES, out=(side, 0, 0))
        mb.face([p1, q1, q1i, p1i], GLASSES, out=(0, 1, 0))

    # =========================================================================
    # 6. NECK (4-sided tapered skin prism = 8 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.120, 0.006, 0.068, 0.064, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.210, 0.008, 0.064, 0.060, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 7. NAVY V-NECK PULLOVER SWEATER TORSO (20 tris)
    # =========================================================================
    mb.set_part("sweater_torso", bone="Torso")
    jy0, jy_hem, jy1 = 0.650, 0.706, 1.132
    jx_b, jx_h, jx_t = 0.210, 0.214, 0.194
    jz_fb, jz_fh, jz_ft = 0.126, 0.130, 0.120
    jz_bb, jz_bh, jz_bt = -0.122, -0.126, -0.114

    r_sw_bot = [
        V(-jx_b, jy0,    jz_fb), V( jx_b, jy0,    jz_fb),
        V( jx_b, jy0,    jz_bb), V(-jx_b, jy0,    jz_bb),
    ]
    r_sw_hem = [
        V(-jx_h, jy_hem, jz_fh), V( jx_h, jy_hem, jz_fh),
        V( jx_h, jy_hem, jz_bh), V(-jx_h, jy_hem, jz_bh),
    ]
    r_sw_top = [
        V(-jx_t, jy1,    jz_ft), V( jx_t, jy1,    jz_ft),
        V( jx_t, jy1,    jz_bt), V(-jx_t, jy1,    jz_bt),
    ]
    # Ribbed lower sweater hem band + main sweater body
    mb.loft([r_sw_bot, r_sw_hem], SWEATER_CUFF, cap_bottom=True, cap_top=False, bot_color=SWEATER_SHADE)
    mb.loft([r_sw_hem, r_sw_top], SWEATER,      cap_bottom=False, cap_top=True, top_color=SWEATER)

    # =========================================================================
    # 8. WHITE COLLARED DRESS SHIRT & DARK SLATE TIE IN V-NECK (12 tris)
    # =========================================================================
    mb.set_part("collar_and_tie", bone="Torso")
    # Helper for front torso Z surface at height y
    def front_z(y):
        t = (y - jy_hem) / (jy1 - jy_hem)
        return jz_fh + (jz_ft - jz_fh) * t

    # Crisp white dress-shirt V-neck chest panel (1 tri, clearly proud of sweater front)
    mb.face([
        V(-0.088, 1.134, front_z(1.132) + 0.006),
        V( 0.088, 1.134, front_z(1.132) + 0.006),
        V( 0.000, 1.012, front_z(1.012) + 0.006),
    ], SHIRT, out=(0, 0, 1))

    # Crisp 3D folded white shirt collar wings framing the neck & tie cleanly (2 solid collar flaps = 4 tris)
    for side in (-1, 1):
        p_neck_b = V(side * 0.068, 1.168, -0.048)  # wraps cleanly behind neck side
        p_neck_f = V(side * 0.016, 1.158,  0.086)  # meets tie knot cleanly at front of throat
        p_tip    = V(side * 0.066, 1.078,  front_z(1.078) + 0.014)  # crisp lower-front collar point
        p_outer  = V(side * 0.122, 1.136,  0.072)  # outer shoulder edge of folded collar
        mb.face([p_tip, p_outer, p_neck_b, p_neck_f], SHIRT, out=(side * 0.35, 0.55, 0.75))

    # White shirt collar stand wrapping cleanly around back of neck (2 quads = 4 tris)
    mb.face([
        V( 0.076, 1.132, -0.094),
        V(-0.076, 1.132, -0.094),
        V(-0.068, 1.168, -0.068),
        V( 0.068, 1.168, -0.068),
    ], SHIRT_SHADE, out=(0, 0.25, -1))
    mb.face([
        V(-0.068, 1.168, -0.068),
        V( 0.068, 1.168, -0.068),
        V( 0.068, 1.168, -0.048),
        V(-0.068, 1.168, -0.048),
    ], SHIRT, out=(0, 1, 0))

    # Neat dark slate-blue necktie knot & upper blade nestled in V-neck (1 quad + 1 tri = 3 tris)
    z_tie_t = front_z(1.132) + 0.015
    z_tie_m = front_z(1.088) + 0.013
    z_tie_b = front_z(1.018) + 0.010
    mb.face([
        V(-0.018, 1.088, z_tie_m),
        V( 0.018, 1.088, z_tie_m),
        V( 0.025, 1.136, z_tie_t),
        V(-0.025, 1.136, z_tie_t),
    ], TIE, out=(0, 0, 1))
    mb.face([
        V(-0.026, 1.088, z_tie_m - 0.001),
        V( 0.026, 1.088, z_tie_m - 0.001),
        V( 0.000, 1.018, z_tie_b),
    ], TIE_SHADE, out=(0, 0, 1))

    # =========================================================================
    # 9. NAVY SWEATER SLEEVES (2 slightly bent arms = 32 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Right arm (-X) slightly bent forward so fist clears satchel cleanly; Left arm (+X) relaxed commuter bend
    arm_specs = [
        ( 1, "Arm_L", V( 0.168, 1.074,  0.002), V( 0.270, 0.864,  0.006), V( 0.276, 0.720, 0.056)),
        (-1, "Arm_R", V(-0.168, 1.074,  0.006), V(-0.276, 0.866,  0.020), V(-0.266, 0.732, 0.098)),
    ]

    for (side, bname, p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax_mid = (ax1 + ax2).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def sleeve_ring(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            u = u.normalized()
            v = axis.cross(u).normalized()
            return [
                ctr + u * (-rx) + v * ( rperp),
                ctr + u * ( rx) + v * ( rperp),
                ctr + u * ( rx) + v * (-rperp),
                ctr + u * (-rx) + v * (-rperp),
            ]

        r_sh = sleeve_ring(p_sh, ax1,    0.072, 0.082)
        r_el = sleeve_ring(p_el, ax_mid, 0.084, 0.088)
        r_wr = sleeve_ring(p_wr, ax2,    0.070, 0.074)
        mb.loft([r_sh, r_el, r_wr], lambda i, k: SWEATER_SHADE if k == 2 else (SWEATER_CUFF if i == 1 else SWEATER),
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 10. CHUNKY PEACH HANDS (2 x 10 tris = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for (side, bname, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        side_x = V(1.0, 0.0, 0.0)
        u = (side_x - ax * side_x.dot(ax)).normalized()
        v = ax.cross(u).normalized()

        c0 = p_wr - ax * 0.008
        c1 = p_wr + ax * 0.102
        r0 = [
            c0 + u * (-0.052) + v * ( 0.056),
            c0 + u * ( 0.052) + v * ( 0.056),
            c0 + u * ( 0.052) + v * (-0.056),
            c0 + u * (-0.052) + v * (-0.056),
        ]
        r1 = [
            c1 + u * (-0.042) + v * ( 0.044),
            c1 + u * ( 0.042) + v * ( 0.044),
            c1 + u * ( 0.042) + v * (-0.044),
            c1 + u * (-0.042) + v * (-0.044),
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 11. DARK BROWN LEATHER SATCHEL + FLAP + CROSSBODY STRAP (12 + 8 + 24 = 44 tris)
    # =========================================================================
    mb.set_part("satchel", bone="Satchel")
    # Hanging on right hip (-X) slightly behind right arm, tilted back ~12 deg like reference
    bag_tilt = math.radians(-12.0)
    ct, st = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_orig = V(-0.270, 0.650, -0.108)

    def bag_pt(lx, ly, lz):
        ry = ly * ct - lz * st
        rz = ly * st + lz * ct
        return V(bag_orig.x + lx, bag_orig.y + ry, bag_orig.z + rz)

    # Boxy structured leather satchel body (6 quads = 12 tris)
    # Local X: +0.052 (inner toward hip) .. -0.068 (outer)
    # Local Y: -0.125 (bottom) .. +0.125 (top)
    # Local Z: -0.145 (back) .. +0.145 (front)
    b_bot = [
        bag_pt(-0.062, -0.125, -0.135),
        bag_pt( 0.048, -0.125, -0.135),
        bag_pt( 0.048, -0.125,  0.135),
        bag_pt(-0.062, -0.125,  0.135),
    ]
    b_top = [
        bag_pt(-0.068,  0.125, -0.145),
        bag_pt( 0.052,  0.125, -0.145),
        bag_pt( 0.052,  0.125,  0.145),
        bag_pt(-0.068,  0.125,  0.145),
    ]
    mb.loft([b_bot, b_top], lambda i, k: SATCHEL_SHADE if k in (0, 1) else SATCHEL,
            cap_bottom=True, cap_top=True, bot_color=SATCHEL_SHADE, top_color=SATCHEL_FLAP)

    # Overlapping leather messenger flap on outer (-X) face + small central clasp tongue (4 quads = 8 tris)
    # Flap covers upper 56% of outer face, proud by 0.015 m
    fl_t_b = bag_pt(-0.078,  0.124, -0.144)
    fl_t_f = bag_pt(-0.078,  0.124,  0.144)
    fl_b_b = bag_pt(-0.082, -0.014, -0.138)
    fl_b_f = bag_pt(-0.082, -0.014,  0.138)
    # Outer flap face
    mb.face([fl_b_b, fl_b_f, fl_t_f, fl_t_b], SATCHEL_FLAP, out=(-1, 0, 0))
    # Top bevel connecting flap smoothly into satchel top
    mb.face([fl_t_b, fl_t_f, b_top[3], b_top[0]], SATCHEL_FLAP, out=(-0.4, 0.9, 0))
    # Crisp dark bottom shadow lip under the overlapping flap
    mb.face([fl_b_b, bag_pt(-0.065, -0.022, -0.138), bag_pt(-0.065, -0.022, 0.138), fl_b_f],
            SATCHEL_SHADE, out=(-0.3, -1.0, 0))
    # Small central leather closure tongue protruding slightly below flap center
    mb.face([
        bag_pt(-0.085, -0.058, -0.026),
        bag_pt(-0.085, -0.058,  0.026),
        bag_pt(-0.085,  0.008,  0.026),
        bag_pt(-0.085,  0.008, -0.026),
    ], SATCHEL_SHADE, out=(-1, 0, 0))

    # Crossbody leather strap: satchel front -> right lower waist -> left shoulder -> back waist -> satchel back
    # 5 segments using outward face + 1 visible upper/outer edge (or 3 faces on chest/shoulder) = 24 tris!
    mb.set_part("satchel_strap", bone="Torso")
    strap_pts = [
        bag_pt(-0.008, 0.118,  0.102),   # 0: satchel front-top attachment (Satchel)
        V(-0.214, 0.728,  0.136),        # 1: right lower front waist corner (Torso)
        V( 0.116, 1.136,  0.127),        # 2: left shoulder front (Torso)
        V( 0.116, 1.136, -0.121),        # 3: left shoulder back (Torso)
        V(-0.214, 0.728, -0.131),        # 4: right lower back waist corner (Torso)
        bag_pt(-0.008, 0.118, -0.102),   # 5: satchel back-top attachment (Satchel)
    ]
    strap_norms = [
        V(-0.8,  0.2,  0.5),
        V(-0.4,  0.0,  0.9),
        V( 0.1,  0.6,  0.8),
        V( 0.1,  0.6, -0.8),
        V(-0.4,  0.0, -0.9),
        V(-0.8,  0.2, -0.5),
    ]
    strap_weights = [
        {"Satchel": 1.0},
        {"Torso": 1.0},
        {"Torso": 1.0},
        {"Torso": 1.0},
        {"Torso": 1.0},
        {"Satchel": 1.0},
    ]
    half_w = 0.028
    half_t = 0.008
    s_rings = []
    for i, c in enumerate(strap_pts):
        if i == 0:
            t = (strap_pts[1] - strap_pts[0]).normalized()
        elif i == len(strap_pts) - 1:
            t = (strap_pts[-1] - strap_pts[-2]).normalized()
        else:
            t = ((strap_pts[i] - strap_pts[i - 1]).normalized() +
                 (strap_pts[i + 1] - strap_pts[i]).normalized()).normalized()
        n = strap_norms[i].normalized()
        b = t.cross(n)
        if b.length < 1e-6:
            b = t.cross(V(0, 1, 0))
        b = b.normalized()
        n = b.cross(t).normalized()
        s_rings.append([
            c - b * half_w + n * half_t,  # 0: outer-left edge
            c + b * half_w + n * half_t,  # 1: outer-right edge
            c + b * half_w - n * half_t,  # 2: inner-right edge
            c - b * half_w - n * half_t,  # 3: inner-left edge
        ])
    # Skip k=2 (inner back face pressed flush against sweater) -> 3 quads/seg x 5 segs = 30 tris!
    # Also on the short waist-to-bag connector segments (i=0 and i=4), draw outer + top/side only
    for i in range(len(s_rings) - 1):
        r0, r1 = s_rings[i], s_rings[i + 1]
        c0 = sum(r0, Vector()) / 4
        c1 = sum(r1, Vector()) / 4
        cmid = (c0 + c1) * 0.5
        w0, w1 = strap_weights[i], strap_weights[i + 1]
        # k=0 is outer broad face; k=1 and k=3 are thin strap thickness edges
        ks = (0, 1, 3) if i in (1, 2, 3) else (0, 1)
        for k in ks:
            kn = (k + 1) % 4
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            col = SATCHEL_STRAP if k == 0 else SATCHEL_SHADE
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=[w0, w0, w1, w1])

    # =========================================================================
    # 12. KHAKI / TAN TAILORED CHINOS (8 + 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.186, 0.186, 0.548, 0.668, -0.104, 0.104, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.186
        x_in_b, x_out_b = side * 0.056, side * 0.224
        rz_t, rz_b = 0.098, 0.096
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.142,  rz_b),
            V(max(x_in_b, x_out_b), 0.142,  rz_b),
            V(max(x_in_b, x_out_b), 0.142, -rz_b),
            V(min(x_in_b, x_out_b), 0.142, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 13. WARM BROWN LEATHER DRESS SHOES WITH DARK SOLES (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.140
        w = 0.068
        w_toe = 0.056
        z_heel = -0.090
        z_toe  =  0.168
        y_sole0 = 0.000
        y_sole1 = 0.032
        y_col   = 0.152

        # Layer 1: Dark chocolate outsole (10 tris)
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

        # Layer 2: Warm brown leather dress shoe upper rising cleanly into khaki pant hem (8 tris)
        shoe_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.014),
            V(cx + w * 0.84, y_col, z_heel + 0.014),
            V(cx + w * 0.84, y_col, 0.054),
            V(cx - w * 0.84, y_col, 0.054),
        ]
        mb.loft([sole_top, shoe_top], lambda i, k: SHOE_SHADE if k == 2 else SHOE,
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
    """24-frame looping Walk cycle: brisk nerdy commuter stride, neat arm swing & gently bobbing satchel."""
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

        # Brisk, purposeful commuter bounce & slight forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        root_pitch = -0.056
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.068 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.020 * c2, 0.098 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Focused, slightly earnest head bob keeping round glasses level
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.044 + 0.024 * c2, -0.042 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating khaki-trouser stride with clean foot lift
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

        # Left arm swings freely in crisp commuter counter-phase
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.30 * s1 - 0.04, 0.0, 0.028)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm swings neatly with slight forward & outward bias so hand stays cleanly in front of satchel!
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.18 * s1 + 0.09, 0.0, -0.045)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Leather satchel bounces & trails slightly at right hip with natural pendulum lag
        pb_bag = rig.pose.bones["Satchel"]
        pb_bag.location = (0.0, 0.008 * math.sin(2.0 * phi - 0.60), 0.0)
        pb_bag.rotation_euler = (0.060 * math.sin(phi - 0.55), 0.0, 0.028 * c1)
        pb_bag.keyframe_insert(data_path="location", frame=frame)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: thoughtful commuter wait, glasses-wearing glance around & satchel settle."""
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

        # Calm weight shift & steady breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.012, 0.022 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.026 * s1, -0.015 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious, alert commuter look-around (checking ferry schedule & dock)
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.036 * s2, 0.22 * s1, 0.032 * c1)
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
        pb_arm_l.rotation_euler = (0.042 * s1 - 0.015 * s2, 0.0, 0.016 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.038 * s1 - 0.014 * s2, 0.0, -0.020 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Satchel settles gently on hip
        pb_bag = rig.pose.bones["Satchel"]
        pb_bag.location = (0.0, 0.003 * s2, 0.0)
        pb_bag.rotation_euler = (0.018 * s2, 0.0, -0.018 * s1)
        pb_bag.keyframe_insert(data_path="location", frame=frame)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Satchel) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonBusinessmanRig")
    rig = bpy.data.objects.new("PersonBusinessmanRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",    None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",   "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",    "Torso", ( 0.000, 1.160,  0.000), ( 0.000, 1.480,  0.000)),
        ("Arm_L",   "Torso", ( 0.168, 1.074,  0.002), ( 0.168, 1.234,  0.002)),
        ("Arm_R",   "Torso", (-0.168, 1.074,  0.006), (-0.168, 1.234,  0.006)),
        ("Satchel", "Torso", (-0.265, 0.768, -0.088), (-0.265, 0.928, -0.088)),
        ("Leg_L",   "Root",  ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R",   "Root",  (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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
        (-1.68, math.radians(56)),   # Front-3/4 matching reference angle (facing right, showing satchel)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (showing satchel, hair profile, glasses temple)
        ( 1.68, math.radians(180)),  # Back (showing crossbody strap & hair)
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=56):
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


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonBusinessman")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonBusinessman")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonBusinessman", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=56)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=54, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonBusinessman Stats ===")
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
