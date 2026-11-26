# Builds an ultra-low-poly (< 350 tris) stylized woman tourist with a beige baseball cap,
# golden-blonde side hair & curved ponytail, rust-orange open field jacket over a dark charcoal tee,
# charcoal backpack with side pockets & gold clasps, silver-and-black retro camera on a neck strap,
# olive-green cropped cargo pants with side pockets, exposed ankles, and chunky brown hiking boots.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_tourist_woman.py)
# Saves art/person_tourist_woman.blend, exports assets/models/person_tourist_woman.glb (rigged + Walk & Idle cycles),
# renders art/person_tourist_woman_preview.png, art/person_tourist_woman_walk_preview.png,
# art/person_tourist_woman_idle_preview.png, and outputs rendered videos
# art/person_tourist_woman_walk.mp4 and art/person_tourist_woman_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.69 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_tourist_woman.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_tourist_woman.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_tourist_woman_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_tourist_woman_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_tourist_woman_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_tourist_woman_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_tourist_woman_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference woman tourist artwork (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN            = col_srgb(0.97, 0.72, 0.48)
SKIN_SHADE      = col_srgb(0.85, 0.59, 0.37)
EYE             = col_srgb(0.11, 0.11, 0.13)

HAIR            = col_srgb(0.93, 0.74, 0.32)
HAIR_HIGHLIGHT  = col_srgb(0.97, 0.80, 0.41)
HAIR_SHADE      = col_srgb(0.81, 0.62, 0.25)

CAP             = col_srgb(0.89, 0.82, 0.68)
CAP_HIGHLIGHT   = col_srgb(0.93, 0.87, 0.74)
CAP_SHADE       = col_srgb(0.79, 0.72, 0.58)
CAP_UNDER       = col_srgb(0.57, 0.50, 0.39)

SHIRT           = col_srgb(0.30, 0.30, 0.33)

JACKET          = col_srgb(0.80, 0.42, 0.22)
JACKET_SHADE    = col_srgb(0.65, 0.32, 0.16)
JACKET_COLLAR   = col_srgb(0.85, 0.47, 0.26)

PACK            = col_srgb(0.22, 0.22, 0.24)
PACK_SHADE      = col_srgb(0.15, 0.15, 0.17)
PACK_POCKET     = col_srgb(0.27, 0.27, 0.30)
PACK_CLASP      = col_srgb(0.86, 0.66, 0.30)

CAM_TOP         = col_srgb(0.88, 0.87, 0.84)
CAM_BODY        = col_srgb(0.24, 0.24, 0.26)
CAM_SHADE       = col_srgb(0.16, 0.16, 0.18)
CAM_LENS        = col_srgb(0.38, 0.39, 0.42)
CAM_GLASS       = col_srgb(0.10, 0.12, 0.16)
CAM_STRAP       = col_srgb(0.19, 0.19, 0.21)

PANTS           = col_srgb(0.43, 0.46, 0.31)
PANTS_SHADE     = col_srgb(0.33, 0.36, 0.23)
PANTS_POCKET    = col_srgb(0.48, 0.51, 0.35)

BOOT            = col_srgb(0.61, 0.45, 0.29)
BOOT_SHADE      = col_srgb(0.49, 0.35, 0.22)
BOOT_LACE       = col_srgb(0.43, 0.31, 0.19)
SOLE            = col_srgb(0.25, 0.19, 0.15)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_HIGHLIGHT, HAIR_SHADE],
    "top": [JACKET, JACKET_SHADE, JACKET_COLLAR],
    "bottom": [PANTS, PANTS_SHADE, PANTS_POCKET],
    "accent": [CAP, CAP_HIGHLIGHT, CAP_SHADE, CAP_UNDER],
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
    """Ring tilted backward around X by tilt_rad (+tilt raises +Z front, lowers -Z back)."""
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
    # 1. HEAD (6-sided stylized low-poly head, y = 1.19..1.47 = 26 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.190,  0.018, 0.148, 0.144),  # 0: chin/jawline
        (1.278,  0.022, 0.210, 0.198),  # 1: lower cheeks
        (1.462,  0.010, 0.198, 0.188),  # 2: brow tucked cleanly inside baseball cap (zero bleed!)
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks, k=1,2,3 are blonde back/sides
    def head_color(i, k):
        if i == 0:
            return HAIR_SHADE if k in (1, 2, 3) else SKIN
        return SKIN if k in (4, 5, 0) else HAIR

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)

    # Chin bottom cap (front underside only = 2 tris; rear sits cleanly over collar/neck)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. GOLDEN-BLONDE SIDE HAIR DRAPES + CHUNKY CURVED PONYTAIL (12 + 18 = 30 tris)
    # =========================================================================
    mb.set_part("hair_sides", bone="Head")
    # Watertight chunky golden-blonde hair curtains hugging the cheeks & nape (6 tris/side = 12 tris)
    for side in (-1, 1):
        p_tf = V(side * 0.194, 1.442,  0.046)
        p_tb = V(side * 0.204, 1.418, -0.128)
        p_bf = V(side * 0.194, 1.214, -0.012)
        p_bb = V(side * 0.208, 1.202, -0.156)
        p_in = V(side * 0.105, 1.216, -0.148)
        p_if = V(side * 0.132, 1.236,  0.014)

        # Outer blonde side curtain (2 tris)
        mb.face([p_bf, p_bb, p_tb, p_tf], HAIR_HIGHLIGHT if side < 0 else HAIR, out=(side, 0, 0))
        # Watertight front edge closing cheek-to-hair gap (1 tri)
        mb.face([p_if, p_bf, p_tf], HAIR, out=(side * 0.35, 0, 0.94))
        # Watertight back edge closing nape-to-hair gap (1 tri)
        mb.face([p_bb, p_in, p_tb], HAIR_SHADE, out=(side * 0.25, 0, -0.96))
        # Bottom/underside closing hair lock cleanly into nape (2 tris)
        mb.face([p_bf, p_if, p_in, p_bb], HAIR_SHADE, out=(0, -1, 0))

    # Iconic chunky curved low-poly ponytail arching jauntily behind cap with blunt blocky tip (18 tris)
    mb.set_part("hair_ponytail")
    # Ring 0: root emerging cleanly from under the back of the baseball cap
    pt_r0 = [
        V(-0.074, 1.384, -0.162),  # 0: top-right
        V( 0.074, 1.384, -0.162),  # 1: top-left
        V( 0.068, 1.288, -0.172),  # 2: bot-left
        V(-0.068, 1.288, -0.172),  # 3: bot-right
    ]
    # Ring 1: plump arched outer elbow of the ponytail
    pt_r1 = [
        V(-0.094, 1.346, -0.322),  # 0: top-right
        V( 0.094, 1.346, -0.322),  # 1: top-left
        V( 0.080, 1.242, -0.268),  # 2: bot-left
        V(-0.080, 1.242, -0.268),  # 3: bot-right
    ]
    # Ring 2: chunky blunt angled ponytail tip stopping cleanly above backpack!
    pt_r2 = [
        V(-0.080, 1.186, -0.396),  # 0: top-right
        V( 0.080, 1.186, -0.396),  # 1: top-left
        V( 0.070, 1.152, -0.312),  # 2: bot-left
        V(-0.070, 1.152, -0.312),  # 3: bot-right
    ]

    w_pt0 = {"Head": 0.85, "Ponytail": 0.15}
    w_pt1 = {"Head": 0.25, "Ponytail": 0.75}
    w_pt2 = {"Ponytail": 1.0}

    # 2 chunky segments (16 tris) + blunt tip cap (2 tris) = 18 tris
    mb.loft(
        [pt_r0, pt_r1, pt_r2],
        lambda i, k: HAIR_HIGHLIGHT if k == 0 else (HAIR_SHADE if k == 2 else HAIR),
        cap_bottom=False, cap_top=True, top_color=HAIR,
        ring_weights=[w_pt0, w_pt1, w_pt2],
    )

    # =========================================================================
    # 3. EARS (2 cute small peach wedges peeking softly ahead of blonde side hair = 4 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.194
        x_out = side * 0.222
        p_t = V(x_in,  1.350, 0.068)
        p_b = V(x_in,  1.292, 0.062)
        p_o = V(x_out, 1.320, 0.042)
        p_bk = V(x_in, 1.320, 0.020)
        mb.face([p_b, p_o, p_t],  SKIN,       out=(side * 0.4, 0, 0.9))
        mb.face([p_t, p_o, p_bk], SKIN_SHADE, out=(side * 0.4, 0, -0.9))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    # Interpolated flat front face z at y=1.372 between ring 1 (z=0.1935) and ring 2 (z=0.1728)
    z_eye = 0.189
    for side in (-1, 1):
        cx = side * 0.062
        cy = 1.372
        rx = 0.018
        ry = 0.044
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
    # 5. NECK (3-sided tapered cylinder skipping hidden rear = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.095, 0.010, 0.068, 0.064, n=3, phase=0.0)
    neck_r1 = oval_ring(0.0, 1.200, 0.014, 0.064, 0.060, n=3, phase=0.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 6. BEIGE BASEBALL CAP (6-sided rounded dome + 3-segment curved forward visor = 40 tris)
    # =========================================================================
    mb.set_part("baseball_cap", bone="Head")
    cap_tilt = math.radians(15.0)  # jaunty slight backward tilt exposing eyes & brow cleanly
    st, ct = math.sin(cap_tilt), math.cos(cap_tilt)
    cap_orig = V(0.0, 1.428, -0.008)

    def cap_ring(h, rx, rz):
        cy = cap_orig.y + h * ct
        cz = cap_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, cap_tilt, n=6, phase=math.pi / 6.0)

    c_rim = cap_ring(0.000, 0.240, 0.236)  # snug cap headband rim cleanly enclosing brow
    c_mid = cap_ring(0.122, 0.218, 0.214)  # rounded baseball dome shoulder
    c_top = cap_ring(0.210, 0.114, 0.112)  # soft crown peak

    # Rounded dome crown: 2 bands * 6 * 2 = 24 tris + 2-quad top cap (4 tris) = 28 tris
    mb.loft(
        [c_rim, c_mid, c_top],
        lambda i, k: CAP_HIGHLIGHT if (i == 1 and k in (4, 5, 0)) else (CAP_SHADE if k in (1, 2, 3) else CAP),
        cap_bottom=False, cap_top=True, top_color=CAP_HIGHLIGHT,
    )

    # Gently curved downward-swooping 3-segment forward baseball bill/visor = 12 tris!
    v_in = [
        c_rim[4].lerp(c_rim[5], 0.35),  # 0: right temple anchor
        c_rim[5],                       # 1: front-right brow
        c_rim[0],                       # 2: front-left brow
        c_rim[1].lerp(c_rim[0], 0.35),  # 3: left temple anchor
    ]
    # Classic curved baseball visor sloping gently downward at tip and arching gracefully at sides
    v_out = [
        V(-0.228, 1.418, 0.172),        # 0: right outer bill wing
        V(-0.122, 1.438, 0.360),        # 1: front-right visor tip
        V( 0.122, 1.438, 0.360),        # 2: front-left visor tip
        V( 0.228, 1.418, 0.172),        # 3: left outer bill wing
    ]
    v_under_in = [V(p.x * 0.94, p.y - 0.018, p.z - 0.010) for p in v_in]
    v_under_out = [V(p.x, p.y - 0.010, p.z - 0.005) for p in v_out]

    for k in range(3):
        mb.face([v_in[k], v_out[k], v_out[k + 1], v_in[k + 1]],
                CAP_HIGHLIGHT if k == 1 else CAP, out=(0, 1, 0.20))
        mb.face([v_under_in[k + 1], v_under_out[k + 1], v_under_out[k], v_under_in[k]],
                CAP_UNDER, out=(0, -1, -0.20))

    # =========================================================================
    # 7. DARK CHARCOAL INNER SHIRT (visible down open rust jacket front = 2 tris)
    # =========================================================================
    mb.set_part("shirt", bone="Torso")
    sz_f = 0.104
    mb.face([V(-0.088, 0.652, sz_f), V(0.088, 0.652, sz_f),
             V(0.088, 1.132, sz_f),  V(-0.088, 1.132, sz_f)], SHIRT, out=(0, 0, 1))

    # =========================================================================
    # 8. RUST-ORANGE OPEN FIELD JACKET + FOLDED COLLAR (18 + 10 = 28 tris)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    jy0, jy1 = 0.650, 1.132
    jx_b, jx_t = 0.214, 0.192
    jz_fb, jz_ft = 0.130, 0.120
    jz_bb, jz_bt = -0.122, -0.112
    j_open_b = 0.066
    j_open_t = 0.056

    # Back panel (2 tris)
    mb.face([V(jx_b, jy0, jz_bb), V(-jx_b, jy0, jz_bb),
             V(-jx_t, jy1, jz_bt), V(jx_t, jy1, jz_bt)], JACKET_SHADE, out=(0, 0, -1))

    for side in (-1, 1):
        xo_b, xo_t = side * jx_b, side * jx_t
        xi_b, xi_t = side * j_open_b, side * j_open_t
        # Side panel (2 tris each)
        mb.face([V(xo_b, jy0, jz_fb), V(xo_b, jy0, jz_bb),
                 V(xo_t, jy1, jz_bt), V(xo_t, jy1, jz_ft)], JACKET, out=(side, 0, 0))
        # Open front panel (2 tris each)
        mb.face([V(xi_b, jy0, jz_fb), V(xo_b, jy0, jz_fb),
                 V(xo_t, jy1, jz_ft), V(xi_t, jy1, jz_ft)], JACKET, out=(0, 0, 1))
        # Inner thickness edge along front opening (2 tris each)
        mb.face([V(xi_b, jy0, sz_f),  V(xi_b, jy0, jz_fb),
                 V(xi_t, jy1, jz_ft), V(xi_t, jy1, sz_f)], JACKET_SHADE, out=(-side, 0, 0))
        # Shoulder top (2 tris each)
        mb.face([V(xi_t, jy1, jz_ft), V(xo_t, jy1, jz_ft),
                 V(xo_t, jy1, jz_bt), V(xi_t, jy1, jz_bt)], JACKET, out=(0, 1, 0))

    # Crisp folded field-jacket collar framing the neck (3 outer flaps = 6 tris)
    mb.set_part("jacket_collar", bone="Torso")
    col_bot = [
        V(-0.068, 1.124,  0.122),
        V(-0.154, 1.120, -0.020),
        V( 0.154, 1.120, -0.020),
        V( 0.068, 1.124,  0.122),
    ]
    col_top = [
        V(-0.056, 1.186,  0.094),
        V(-0.128, 1.190, -0.022),
        V( 0.128, 1.190, -0.022),
        V( 0.056, 1.186,  0.094),
    ]
    for k in range(3):
        p0, p1, p2, p3 = col_bot[k], col_bot[k + 1], col_top[k + 1], col_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        out_v = V(mid.x, 0.20, mid.z if k != 1 else -1.0)
        mb.face([p0, p1, p2, p3], JACKET_COLLAR, out=out_v)

    # =========================================================================
    # 9. RUST JACKET SLEEVES (2 x chunky 4-sided bent sleeves = 32 tris)
    # =========================================================================
    mb.set_part("sleeves")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        p_sh = V(side * 0.162, 1.076,  0.002)
        p_el = V(side * 0.298, 0.876, -0.016)
        p_wr = V(side * 0.326, 0.706,  0.044)

        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        axm = (ax1 + ax2).normalized()
        fwd = V(0.0, 0.0, 1.0)

        def s_ring(ctr, ax, ru, rv):
            u = ax.cross(fwd)
            if u.length < 1e-5:
                u = V(1.0, 0.0, 0.0)
            u = u.normalized()
            v = u.cross(ax).normalized()
            return [
                ctr + u * (-ru) + v * ( rv),
                ctr + u * ( ru) + v * ( rv),
                ctr + u * ( ru) + v * (-rv),
                ctr + u * (-ru) + v * (-rv),
            ]

        r_sh = s_ring(p_sh, ax1, 0.070, 0.078)
        r_el = s_ring(p_el, axm, 0.086, 0.090)
        r_wr = s_ring(p_wr, ax2, 0.072, 0.076)
        mb.loft([r_sh, r_el, r_wr], JACKET, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 10. HANDS (2 chunky 4-sided tapered peach fists = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        h_specs = [
            (side * 0.324, 0.712, 0.044, 0.050, 0.054),
            (side * 0.330, 0.600, 0.058, 0.046, 0.050),
        ]
        h_rings = []
        for (cx, cy, cz, rx, rz) in h_specs:
            h_rings.append([
                V(cx - rx, cy, cz + rz),
                V(cx + rx, cy, cz + rz),
                V(cx + rx, cy, cz - rz),
                V(cx - rx, cy, cz - rz),
            ])
        mb.loft(h_rings, SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 11. DARK CHARCOAL BACKPACK + SIDE POCKETS WITH GOLD CLASPS + STRAPS (14 + 6 + 8 = 28 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # Plump rounded 3-ring tourist daypack arching smoothly behind the rust jacket (14 tris)
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.672, 0.156, -0.118, -0.282),  # 0: full rounded lower base
        (0.885, 0.184, -0.116, -0.348),  # 1: smooth plump mid belly
        (1.095, 0.144, -0.110, -0.246),  # 2: rounded dome lid sitting cleanly under ponytail
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

    # Side pocket flap + crisp tiny golden-tan buckle/button on both sides matching reference (6 tris)
    for side in (-1, 1):
        xs = side * 0.186
        mb.face([
            V(xs, 0.728, -0.195),
            V(xs, 0.728, -0.305),
            V(xs, 0.880, -0.295),
            V(xs, 0.880, -0.205),
        ], PACK_POCKET, out=(side, 0, 0))
        xc = side * 0.192
        mb.face([
            V(xc, 0.816, -0.236),
            V(xc, 0.816, -0.264),
            V(xc, 0.844, -0.250),
        ], PACK_CLASP, out=(side, 0, 0))

    # Two dark charcoal backpack straps curving over shoulders & front chest (8 tris)
    mb.set_part("backpack_straps", bone="Torso")
    for side in (-1, 1):
        xa_t = min(side * 0.132, side * 0.180)
        xb_t = max(side * 0.132, side * 0.180)
        xa_b = min(side * 0.154, side * 0.202)
        xb_b = max(side * 0.154, side * 0.202)
        mb.face([
            V(xa_t, 1.140, -0.120),
            V(xb_t, 1.140, -0.120),
            V(xb_t, 1.140,  0.124),
            V(xa_t, 1.140,  0.124),
        ], PACK, out=(0, 1, 0))
        mb.face([
            V(xa_b, 0.875, 0.134),
            V(xb_b, 0.875, 0.134),
            V(xb_t, 1.140, 0.124),
            V(xa_t, 1.140, 0.124),
        ], PACK, out=(0, 0, 1))

    # =========================================================================
    # 12. RETRO SILVER-AND-BLACK CAMERA + LENS + NECK STRAP (bone="Camera" = 34 tris)
    # =========================================================================
    mb.set_part("camera", bone="Camera")
    # Classic two-tone retro camera resting snugly on mid-chest (y = 0.788..0.936, z = 0.122..0.188)
    cam_w = 0.098
    cam_zb = 0.122
    cam_zf = 0.188
    cam_y0 = 0.788   # bottom of dark camera body
    cam_ym = 0.890   # crisp horizontal split between matte black body & brushed silver top plate
    cam_y1 = 0.936   # top of silver plate

    cam_rings = []
    for y in (cam_y0, cam_ym, cam_y1):
        cam_rings.append([
            V(-cam_w, y, cam_zf),  # 0: front-right
            V( cam_w, y, cam_zf),  # 1: front-left
            V( cam_w, y, cam_zb),  # 2: back-left
            V(-cam_w, y, cam_zb),  # 3: back-right
        ])
    # Skip k=2 (hidden back face flush against chest): 2 bands * 3 quads (12) + bot (2) + top (2) = 16 tris
    mb.loft(
        cam_rings,
        lambda i, k: CAM_TOP if i == 1 else (CAM_SHADE if k in (1, 3) else CAM_BODY),
        cap_bottom=True, cap_top=True,
        bot_color=CAM_SHADE, top_color=CAM_TOP,
        skip_k=(2,),
    )

    # Brushed-silver central SLR viewfinder / pentaprism hump on top center (4 tris)
    pr_w0, pr_w1 = 0.044, 0.028
    pr_y0, pr_y1 = cam_y1, 0.968
    pr_zf, pr_zb = cam_zf - 0.008, cam_zb + 0.010
    mb.face([
        V(-pr_w0, pr_y0, pr_zf), V( pr_w0, pr_y0, pr_zf),
        V( pr_w1, pr_y1, pr_zf), V(-pr_w1, pr_y1, pr_zf),
    ], CAM_TOP, out=(0, 0, 1))
    mb.face([V( pr_w0, pr_y0, pr_zf), V( pr_w0, pr_y0, pr_zb), V( pr_w1, pr_y1, pr_zf)], CAM_TOP, out=( 1, 0.6, 0))
    mb.face([V(-pr_w0, pr_y0, pr_zb), V(-pr_w0, pr_y0, pr_zf), V(-pr_w1, pr_y1, pr_zf)], CAM_TOP, out=(-1, 0.6, 0))

    # Chunky protruding 4-sided camera lens barrel pointing forward (+Z) + dark glass lens cap (10 tris)
    lens_cx, lens_cy = 0.008, 0.850
    r_l0 = 0.048
    r_l1 = 0.042
    z_l0 = cam_zf - 0.002
    z_l1 = cam_zf + 0.054
    lens_r0 = [
        V(lens_cx + r_l0 * math.cos(math.pi / 4 + k * math.pi / 2),
          lens_cy + r_l0 * math.sin(math.pi / 4 + k * math.pi / 2), z_l0)
        for k in range(4)
    ]
    lens_r1 = [
        V(lens_cx + r_l1 * math.cos(math.pi / 4 + k * math.pi / 2),
          lens_cy + r_l1 * math.sin(math.pi / 4 + k * math.pi / 2), z_l1)
        for k in range(4)
    ]
    mb.loft([lens_r0, lens_r1],
            lambda i, k: CAM_SHADE if k == 2 else CAM_LENS,
            cap_bottom=False, cap_top=True, top_color=CAM_GLASS)

    # Dark camera neck strap rising cleanly from top corners up into collar (2 quads = 4 tris)
    mb.set_part("camera_strap", bone="Camera")
    for side in (-1, 1):
        w = 0.013
        p_b0 = V(side * 0.084 - w, cam_y1 - 0.004, cam_zf - 0.022)
        p_b1 = V(side * 0.084 + w, cam_y1 - 0.004, cam_zf - 0.028)
        p_t0 = V(side * 0.070 - w, 1.132, 0.124)
        p_t1 = V(side * 0.070 + w, 1.132, 0.116)
        mb.face([p_b0, p_b1, p_t1, p_t0], CAM_STRAP, out=(side * 0.25, 0, 1))

    # =========================================================================
    # 13. OLIVE CROPPED CARGO PANTS + 3D SIDE CARGO POCKETS + EXPOSED ANKLES (40 + 16 = 56 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    # Pelvis bridge (front & back only; sides tucked seamlessly inside upper thighs = 4 tris)
    mb.box(-0.184, 0.184, 0.548, 0.668, -0.102, 0.102, PANTS, skip=("top", "bottom", "left", "right"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        # Wide cropped cargo pant leg ending at mid-calf (y = 0.242) to show bare peach ankles above boots!
        x_in_t, x_out_t = side * 0.008, side * 0.188
        x_in_b, x_out_b = side * 0.044, side * 0.236
        rz_t, rz_b = 0.098, 0.100
        y_leg_t = 0.656
        y_leg_b = 0.242
        r_top = [
            V(min(x_in_t, x_out_t), y_leg_t,  rz_t),
            V(max(x_in_t, x_out_t), y_leg_t,  rz_t),
            V(max(x_in_t, x_out_t), y_leg_t, -rz_t),
            V(min(x_in_t, x_out_t), y_leg_t, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), y_leg_b,  rz_b),
            V(max(x_in_b, x_out_b), y_leg_b,  rz_b),
            V(max(x_in_b, x_out_b), y_leg_b, -rz_b),
            V(min(x_in_b, x_out_b), y_leg_b, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

        # Watertight chunky 3D cargo pocket on outer leg (4 quads = 8 tris per leg = 16 tris total)
        def leg_x_out(y):
            t = (y_leg_t - y) / (y_leg_t - y_leg_b)
            return x_out_t + (x_out_b - x_out_t) * t

        py_b, py_t = 0.305, 0.470
        pz_b, pz_f = -0.068, 0.068
        xo_b = leg_x_out(py_b)
        xo_t = leg_x_out(py_t)
        depth = side * 0.032

        p_in_tb  = V(xo_t,                 py_t,         pz_b)
        p_in_tf  = V(xo_t,                 py_t,         pz_f)
        p_in_bb  = V(xo_b,                 py_b,         pz_b)
        p_in_bf  = V(xo_b,                 py_b,         pz_f)
        p_out_tb = V(xo_t + depth,         py_t - 0.008, pz_b)
        p_out_tf = V(xo_t + depth,         py_t - 0.008, pz_f)
        p_out_bb = V(xo_b + depth * 0.72,  py_b + 0.010, pz_b)
        p_out_bf = V(xo_b + depth * 0.72,  py_b + 0.010, pz_f)

        mb.face([p_out_bb, p_out_bf, p_out_tf, p_out_tb], PANTS_POCKET, out=(side, 0, 0))
        mb.face([p_in_tb,  p_in_tf,  p_out_tf, p_out_tb], PANTS_SHADE,  out=(0, 1, 0))
        mb.face([p_in_bf,  p_out_bf, p_out_tf, p_in_tf],  PANTS_POCKET, out=(0, 0, 1))
        mb.face([p_out_bb, p_in_bb,  p_in_tb,  p_out_tb], PANTS_POCKET, out=(0, 0, -1))

    # Exposed warm-peach bare ankles between cropped cargo pant cuffs and hiking boots (16 tris)
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        a_bot = oval_ring(cx, 0.160, 0.000, 0.056, 0.058, n=4, phase=math.pi / 4.0)
        a_top = oval_ring(cx, 0.252, 0.000, 0.058, 0.060, n=4, phase=math.pi / 4.0)
        mb.loft([a_bot, a_top], lambda i, k: SKIN_SHADE if k in (1, 2) else SKIN,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 14. CHUNKY BROWN HIKING BOOTS WITH DARK LUG SOLES & LACE ACCENT (22 tris x 2 = 44 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        w = 0.072
        w_toe = 0.060
        z_heel = -0.090
        z_mid  =  0.056
        z_toe  =  0.168
        y_sole0 = 0.000
        y_sole1 = 0.038
        y_toe   = 0.094
        y_col   = 0.172  # meets exposed peach ankle cleanly!

        # Thick dark lug outsole (4 sides = 8 tris; bottom rests flat on ground at y=0)
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
        mb.loft([sole_bot, sole_top], SOLE, cap_bottom=False, cap_top=False)

        # Warm earthy-brown hiking boot upper with crisp stepped toe-box & dark lace instep (12 tris)
        p_bl_h = V(cx - w,     y_sole1, z_heel)
        p_br_h = V(cx + w,     y_sole1, z_heel)
        p_bl_t = V(cx - w_toe, y_sole1, z_toe)
        p_br_t = V(cx + w_toe, y_sole1, z_toe)

        p_tl_h = V(cx - w * 0.86,     y_col, z_heel + 0.012)
        p_tr_h = V(cx + w * 0.86,     y_col, z_heel + 0.012)
        p_tl_m = V(cx - w * 0.86,     y_col, z_mid)
        p_tr_m = V(cx + w * 0.86,     y_col, z_mid)
        p_tl_t = V(cx - w_toe * 0.88, y_toe, z_toe - 0.012)
        p_tr_t = V(cx + w_toe * 0.88, y_toe, z_toe - 0.012)

        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], BOOT_SHADE, out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], BOOT,       out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], BOOT_LACE,  out=(0, 1, 0.5))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], BOOT,       out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h],         BOOT,       out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], BOOT,       out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m],         BOOT,       out=(1, 0, 0))

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
    """24-frame looping Walk cycle: upbeat tourist sightseeing stride with ponytail bounce & camera sway."""
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

        # Upbeat sightseeing bounce & slight forward lean balancing backpack
        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.044, -0.064 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-twisting torso
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.016 * c2, 0.098 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert, curious head keeping cap level with gentle step nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.036 - 0.024 * c2, -0.038 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Playful ponytail bounce & side-to-side swing lagging slightly behind each step
        pb_pt = rig.pose.bones["Ponytail"]
        pt_pitch = -0.035 - 0.090 * (1.0 - math.cos(2.0 * phi - 0.70)) * 0.5
        pt_sway = 0.085 * math.sin(phi - 0.55)
        pb_pt.rotation_euler = (pt_pitch, pt_sway, 0.040 * math.sin(phi - 0.55))
        pb_pt.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp hiking boot stride with clean foot lift
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.44 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.038, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.44 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.038, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Natural opposite-phase arm swing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.36 * s1, 0.0, 0.020 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.36 * s1, 0.0, 0.020 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Retro camera hanging on chest: gentle outward pendulum hop & side sway (biased outward to avoid clipping)
        pb_cam = rig.pose.bones["Camera"]
        cam_pitch = 0.035 + 0.042 * (1.0 - math.cos(2.0 * phi - 0.60)) * 0.5
        cam_sway = 0.052 * math.sin(phi - 0.45)
        pb_cam.rotation_euler = (cam_pitch, 0.0, cam_sway)
        pb_cam.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: curious tourist looking around for a photo op, calm breathing & ponytail settle."""
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

        # Relaxed standing sway & calm breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.010, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.020 * s2, 0.034 * s1, -0.015 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious tourist taking in the sights left & right
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.024 + 0.036 * s2, 0.25 * s1, 0.034 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle breeze sway on ponytail lagging behind head turn
        pb_pt = rig.pose.bones["Ponytail"]
        pb_pt.rotation_euler = (-0.022 * s2, -0.075 * math.sin(phi - 0.55), -0.030 * c1)
        pb_pt.keyframe_insert(data_path="rotation_euler", frame=frame)

        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (-0.040 * s1, 0.0, 0.016 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.040 * s1, 0.0, -0.016 * s2)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_cam = rig.pose.bones["Camera"]
        pb_cam.rotation_euler = (0.022 + 0.014 * (1.0 - s2) * 0.5, 0.0, -0.018 * s1)
        pb_cam.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 9-bone Tideways passenger rig (7 standard bones + Ponytail + Camera) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonTouristWomanRig")
    rig = bpy.data.objects.new("PersonTouristWomanRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",     None,    ( 0.000, 0.595,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",    "Root",  ( 0.000, 0.655,  0.000), ( 0.000, 1.120,  0.000)),
        ("Head",     "Torso", ( 0.000, 1.150,  0.000), ( 0.000, 1.460,  0.000)),
        ("Ponytail", "Head",  ( 0.000, 1.320, -0.172), ( 0.000, 1.440, -0.172)),
        ("Arm_L",    "Torso", ( 0.162, 1.076,  0.002), ( 0.162, 1.236,  0.002)),
        ("Arm_R",    "Torso", (-0.162, 1.076,  0.002), (-0.162, 1.236,  0.002)),
        ("Camera",   "Torso", ( 0.000, 1.130,  0.124), ( 0.000, 1.250,  0.124)),
        ("Leg_L",    "Root",  ( 0.105, 0.575,  0.000), ( 0.105, 0.735,  0.000)),
        ("Leg_R",    "Root",  (-0.105, 0.575,  0.000), (-0.105, 0.735,  0.000)),
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
        (-1.72, math.radians(48)),   # Front-3/4 matching reference angle
        (-0.56, math.radians(0)),    # Front
        ( 0.58, math.radians(90)),   # Side (showing cap bill, ponytail, backpack, cargo pocket)
        ( 1.74, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 4.8
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=48):
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.24
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.8
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
    cam_data.ortho_scale = 3.10
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

    coll = bpy.data.collections.new("PersonTouristWoman")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonTouristWoman")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonTouristWoman", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    print("=== PersonTouristWoman Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    assert total_tris < 350, f"Triangle count {total_tris} exceeds strict 350-tri budget!"

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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=48)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH,
                          zrot_left_deg=48, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH,
                          zrot_left_deg=42, zrot_right_deg=90)

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
