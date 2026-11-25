# Builds an ultra-low-poly (< 650 tris) stylized mom with baseball cap, curly hair, cream jacket,
# crossbody purse, cropped trousers, sneakers, pushing a 4-wheel stroller in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_stroller.py)
# Saves art/person_stroller.blend, exports assets/models/person_stroller.glb (rigged + Walk & Idle cycles),
# renders art/person_stroller_preview.png, art/person_stroller_walk_preview.png, art/person_stroller_idle_preview.png,
# and outputs rendered videos art/person_stroller_walk.mp4 and art/person_stroller_idle.mp4.
#
# Strict triangle budget: < 650 triangles.
# Game frame: +Z forward, +Y up, +X left, feet & stroller wheels on ground at y = 0, ~1.68 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_stroller.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_stroller.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_stroller_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_stroller_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_stroller_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_stroller_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_stroller_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (sRGB -> linear).
# Every part has its own unique constants so recolour tags never collide.
SKIN                = col_srgb(0.97, 0.72, 0.47)
SKIN_SHADE          = col_srgb(0.86, 0.60, 0.37)
EYE                 = col_srgb(0.11, 0.10, 0.10)

HAIR                = col_srgb(0.28, 0.22, 0.20)
HAIR_HI             = col_srgb(0.35, 0.28, 0.25)
HAIR_SHADE          = col_srgb(0.20, 0.15, 0.14)

CAP                 = col_srgb(0.35, 0.40, 0.52)
CAP_TOP             = col_srgb(0.40, 0.45, 0.57)
CAP_BRIM            = col_srgb(0.31, 0.36, 0.47)
CAP_UNDER           = col_srgb(0.22, 0.26, 0.35)

JACKET              = col_srgb(0.94, 0.89, 0.82)
JACKET_SHADE        = col_srgb(0.85, 0.79, 0.72)
JACKET_COLLAR       = col_srgb(0.90, 0.84, 0.77)
JACKET_POCKET       = col_srgb(0.88, 0.82, 0.75)

SHIRT_INNER         = col_srgb(0.24, 0.28, 0.36)

PANTS               = col_srgb(0.26, 0.31, 0.41)
PANTS_SHADE         = col_srgb(0.20, 0.24, 0.33)
PANTS_INNER         = col_srgb(0.15, 0.18, 0.25)

SHOE                = col_srgb(0.55, 0.50, 0.42)
SHOE_SHADE          = col_srgb(0.44, 0.40, 0.33)
SHOE_TONGUE         = col_srgb(0.76, 0.73, 0.67)
SHOE_SOLE           = col_srgb(0.30, 0.26, 0.23)

PURSE               = col_srgb(0.43, 0.40, 0.31)
PURSE_FLAP          = col_srgb(0.49, 0.46, 0.36)
PURSE_SHADE         = col_srgb(0.32, 0.30, 0.23)
PURSE_CLASP         = col_srgb(0.68, 0.49, 0.30)
PURSE_STRAP         = col_srgb(0.44, 0.31, 0.22)

STROLLER_CANOPY     = col_srgb(0.34, 0.39, 0.51)
STROLLER_CANOPY_ALT = col_srgb(0.38, 0.43, 0.55)
STROLLER_UNDER      = col_srgb(0.17, 0.20, 0.29)
STROLLER_SEAT       = col_srgb(0.32, 0.37, 0.49)
STROLLER_SEAT_DARK  = col_srgb(0.24, 0.28, 0.38)
STROLLER_FRAME      = col_srgb(0.39, 0.40, 0.43)
STROLLER_FRAME_DARK = col_srgb(0.29, 0.30, 0.33)
STROLLER_HANDLE     = col_srgb(0.19, 0.19, 0.21)
STROLLER_TIRE       = col_srgb(0.23, 0.23, 0.25)
STROLLER_TIRE_SIDE  = col_srgb(0.27, 0.27, 0.29)
STROLLER_HUB        = col_srgb(0.62, 0.63, 0.66)

# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_HI, HAIR_SHADE],
    "top": [JACKET, JACKET_SHADE, JACKET_COLLAR, JACKET_POCKET],
    "bottom": [PANTS, PANTS_SHADE, PANTS_INNER],
    "accent": [CAP, CAP_TOP, CAP_BRIM, CAP_UNDER],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared structural anchors so mom's hands and stroller handlebar align identically
ROOT_Y     = 0.580
SHOULDER_Y = 1.035
SHOULDER_Z = 0.010
HANDLE_Y   = 0.742
HANDLE_Z   = 0.382
HANDLE_HX  = 0.185

WHEEL_R    = 0.112
WHEEL_HX   = 0.215
REAR_WZ    = 0.535
FRONT_WZ   = 0.945
STROLLER_Z = 0.740


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
                ws = [w0, w0, w1, w1] if ring_weights is not None else None
                self.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=ws)
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            wb = ring_weights[0] if ring_weights is not None else None
            if n <= 4:
                self.face(r0, col, out=out_dir, weights=([wb] * len(r0)) if wb else None)
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4) if wb else None)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=([wb] * 4) if wb else None)
            else:
                self.face(r0, col, out=out_dir, weights=([wb] * n) if wb else None)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt = ring_weights[-1] if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([wt] * len(rt)) if wt else None)
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4) if wt else None)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=([wt] * 4) if wt else None)
            else:
                self.face(rt, col, out=out_dir, weights=([wt] * n) if wt else None)

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

    def tube(self, centers, radii, n=4, color=STROLLER_FRAME, cap_start=False, cap_end=False,
             hint=V(1.0, 0.0, 0.0), phase=math.pi / 4.0):
        """Sweep an n-sided polygon tube along a 3D polyline."""
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
            ref = hint if abs(t.dot(hint)) < 0.90 else V(0.0, 1.0, 0.0)
            if abs(t.dot(ref)) >= 0.90:
                ref = V(0.0, 0.0, 1.0)
            u = t.cross(ref).normalized()
            v = t.cross(u).normalized()
            r = radii[i] if isinstance(radii, (list, tuple)) else radii
            ring = []
            for k in range(n):
                a = phase + 2.0 * math.pi * k / n
                ring.append(c + (u * math.cos(a) + v * math.sin(a)) * r)
            rings.append(ring)
        self.loft(rings, color, cap_bottom=cap_start, cap_top=cap_end, bot_color=color, top_color=color)


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


def ortho_basis(axis, hint=V(1.0, 0.0, 0.0)):
    ax = axis.normalized()
    u = hint - ax * hint.dot(ax)
    if u.length < 1e-5:
        hint = V(0.0, 0.0, 1.0)
        u = hint - ax * hint.dot(ax)
    u = u.normalized()
    v = ax.cross(u).normalized()
    return ax, u, v


def add_wheel(mb, cx, cy, cz, radius, half_w, side_sign, n=8, n_hub=6):
    """Build a chunky low-poly 8-sided stroller wheel with raised 6-sided light-grey hubcap."""
    x_in = cx - side_sign * half_w
    x_out = cx + side_sign * half_w
    x_hub = x_out + side_sign * 0.006

    r_in = []
    r_out = []
    for k in range(n):
        a = math.pi / n + 2.0 * math.pi * k / n
        dy = radius * math.sin(a)
        dz = radius * math.cos(a)
        r_in.append(V(x_in, cy + dy, cz + dz))
        r_out.append(V(x_out, cy + dy, cz + dz))

    r_hub = []
    for k in range(n_hub):
        a = math.pi / n_hub + 2.0 * math.pi * k / n_hub
        r_hub.append(V(x_hub, cy + radius * 0.54 * math.sin(a), cz + radius * 0.54 * math.cos(a)))

    # Tire tread (n quads = 2n tris)
    for k in range(n):
        kn = (k + 1) % n
        p0, p1, p2, p3 = r_in[k], r_in[kn], r_out[kn], r_out[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], STROLLER_TIRE, out=V(0.0, mid.y - cy, mid.z - cz))

    # Tire side faces (n - 2 tris each)
    mb.face(r_out, STROLLER_TIRE_SIDE, out=(side_sign, 0, 0))
    mb.face(r_in,  STROLLER_TIRE_SIDE, out=(-side_sign, 0, 0))

    # Raised light-grey hubcap on outer face (n_hub - 2 tris)
    mb.face(r_hub, STROLLER_HUB, out=(side_sign, 0, 0))


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD (6-sided stylized Tideways head, 28 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.208,  0.016, 0.152, 0.144),  # 0: chin/jaw
        (1.290,  0.020, 0.206, 0.196),  # 1: lower cheek
        (1.482,  0.010, 0.205, 0.195),  # 2: brow / hairline under cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        return SKIN if k in (4, 5, 0) else HAIR

    mb.loft(head_rings, head_color, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # =========================================================================
    # 2. NECK (4-sided short tapered cylinder, skip hidden back = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.108, 0.008, 0.066, 0.062, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.216, 0.012, 0.062, 0.058, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 3. EYES (2 vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.196
    for side in (-1, 1):
        cx = side * 0.060
        cy = 1.384
        rx = 0.018
        ry = 0.045
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
    # 4. EARS (2 cute low-poly ears peeking out beside hair = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.192
        x_out = side * 0.230
        y0, y1 = 1.312, 1.390
        z0, z1 = -0.048, 0.014
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.016, zm)
        p_ot = V(x_out, y1 - 0.016, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 5. FLUFFY CURLY DARK-BROWN HAIR (soft cheek framing curls + billowing cloud)
    # =========================================================================
    # 5a. Gently curved front hair lock hugging right along the front edge of each ear (Head bone, 16 tris)
    mb.set_part("hair_locks", bone="Head")
    for side in (-1, 1):
        # Sweeps gracefully from under cap temple down past ear edge, curling inward toward jaw
        l0 = V(side * 0.196, 1.462,  0.046)
        l1 = V(side * 0.210, 1.348,  0.048)
        l2 = V(side * 0.190, 1.242,  0.036)
        l3 = V(side * 0.150, 1.186,  0.048)
        w_f = 0.024
        w_t = 0.020
        r_a = [l0 + V(0, 0, -w_f), l0 + V(0, 0, w_f), l0 + V(-side * w_t, 0, 0)]
        r_b = [l1 + V(0, 0, -w_f), l1 + V(0, 0, w_f), l1 + V(-side * w_t, 0, 0)]
        r_c = [l2 + V(0, 0, -w_f * 0.8), l2 + V(0, 0, w_f * 0.8), l2 + V(-side * w_t * 0.7, 0, 0)]
        mb.face([r_a[0], r_a[1], r_b[1], r_b[0]], HAIR, out=(side, 0, 0.25))
        mb.face([r_b[0], r_b[1], r_c[1], r_c[0]], HAIR, out=(side, 0, 0.25))
        mb.face([r_c[0], r_c[1], l3],             HAIR_SHADE, out=(side, -0.3, 0.2))
        mb.face([r_a[1], r_a[2], r_b[2], r_b[1]], HAIR_HI, out=(0.2 * side, 0, 1))
        mb.face([r_b[1], r_b[2], l3],             HAIR, out=(0.2 * side, -0.2, 1))

    # 5b. Voluminous rounded curly hair cloud behind head (Hair bone, 40 tris)
    mb.set_part("hair_puff", bone="Hair")
    # 4 lush rounded rings giving a soft puffy curly cloud silhouette matching reference artwork
    puff_specs = [
        # (cy,    cz,     rx,    rz,    tilt_deg)
        (1.425, -0.105, 0.215, 0.148,  16.0),  # 0: tucked cleanly under rear of cap
        (1.305, -0.215, 0.272, 0.195,   8.0),  # 1: plush upper curly billow
        (1.145, -0.245, 0.285, 0.212,  -4.0),  # 2: big soft lower curly puff
        (1.028, -0.175, 0.205, 0.135, -14.0),  # 3: rounded lower curl hem
    ]
    puff_rings = []
    for (cy, cz, rx, rz, tdeg) in puff_specs:
        tr = math.radians(tdeg)
        ct, st = math.cos(tr), math.sin(tr)
        ring = []
        for k in range(6):
            a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
            lx = rx * math.sin(a)
            lz = rz * math.cos(a)
            if lz > 0:
                lz *= 0.65
            ring.append(V(lx, cy + lz * st, cz + lz * ct))
        puff_rings.append(ring)

    def puff_color(i, k):
        if i == 0:
            return HAIR_HI if k in (1, 2, 3) else HAIR
        if i == 2:
            return HAIR_SHADE
        return HAIR_HI if (i == 1 and k == 2) else HAIR

    mb.loft(puff_rings, puff_color, cap_bottom=False, cap_top=True, top_color=HAIR_SHADE)

    # =========================================================================
    # 6. SLATE-BLUE BASEBALL CAP (6-sided domed crown + curved visor + button = 44 tris)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    cap_tilt = math.radians(15.0)
    cap_r0 = tilted_ring(0.0, 1.460, -0.004, 0.232, 0.228, cap_tilt)
    cap_r1 = tilted_ring(0.0, 1.588, -0.022, 0.210, 0.208, cap_tilt)
    cap_r2 = tilted_ring(0.0, 1.672, -0.036, 0.112, 0.110, cap_tilt)

    def cap_color(i, k):
        return CAP_TOP if i == 1 else CAP

    mb.loft([cap_r0, cap_r1, cap_r2], cap_color, cap_bottom=False, cap_top=True, top_color=CAP_TOP)

    # Top cap button nub (4 tris)
    bt_c = V(0.0, 1.682, -0.038)
    bt_r = 0.024
    bt_base = [
        V(-bt_r, 1.668, -0.038),
        V( 0.0,  1.668, -0.038 + bt_r),
        V( bt_r, 1.668, -0.038),
        V( 0.0,  1.668, -0.038 - bt_r),
    ]
    for k in range(4):
        kn = (k + 1) % 4
        mid_b = (bt_base[k] + bt_base[kn] + bt_c) / 3.0
        mb.face([bt_base[k], bt_base[kn], bt_c], CAP_TOP, out=mid_b - V(0.0, 1.660, -0.038))

    # Gently curved forward baseball visor (12 tris)
    vt_top = [
        cap_r0[4] + V(-0.004, 0.015, 0.016),
        cap_r0[5] + V( 0.000, 0.018, 0.008),
        cap_r0[0] + V( 0.000, 0.018, 0.008),
        cap_r0[1] + V( 0.004, 0.015, 0.016),
    ]
    vt_bot = [
        cap_r0[4] + V(-0.004, -0.006, 0.016),
        cap_r0[5] + V( 0.000, -0.008, 0.008),
        cap_r0[0] + V( 0.000, -0.008, 0.008),
        cap_r0[1] + V( 0.004, -0.006, 0.016),
    ]
    vt_tip = [
        V(-0.210, 1.478, 0.138),
        V(-0.114, 1.498, 0.340),
        V( 0.114, 1.498, 0.340),
        V( 0.210, 1.478, 0.138),
    ]
    for j in range(3):
        mb.face([vt_top[j], vt_top[j + 1], vt_tip[j + 1], vt_tip[j]], CAP_BRIM,  out=(0, 1, 0.3))
        mb.face([vt_bot[j + 1], vt_bot[j], vt_tip[j], vt_tip[j + 1]], CAP_UNDER, out=(0, -1, -0.1))

    # =========================================================================
    # 7. CREAM CROPPED JACKET + INNER NAVY SHIRT + COLLAR + POCKETS (30 tris)
    # =========================================================================
    mb.set_part("torso_jacket", bone="Torso")
    y_hem, y_sh = 0.625, 1.110
    x_hb, x_sb = 0.188, 0.162
    z_hf, z_hb = 0.142, -0.134
    z_sf, z_sb = 0.118, -0.114
    x_open = 0.036

    mb.face([V( x_hb, y_hem, z_hb), V(-x_hb, y_hem, z_hb), V(-x_sb, y_sh, z_sb), V( x_sb, y_sh, z_sb)],
            JACKET, out=(0, 0, -1))
    mb.face([V( x_hb, y_hem, z_hf), V( x_hb, y_hem, z_hb), V( x_sb, y_sh, z_sb), V( x_sb, y_sh, z_sf)],
            JACKET_SHADE, out=(1, 0, 0))
    mb.face([V(-x_hb, y_hem, z_hb), V(-x_hb, y_hem, z_hf), V(-x_sb, y_sh, z_sf), V(-x_sb, y_sh, z_sb)],
            JACKET_SHADE, out=(-1, 0, 0))
    mb.face([V(-x_sb, y_sh, z_sf), V( x_sb, y_sh, z_sf), V( x_sb, y_sh, z_sb), V(-x_sb, y_sh, z_sb)],
            JACKET, out=(0, 1, 0))
    mb.face([V(-x_hb, y_hem, z_hb), V( x_hb, y_hem, z_hb), V( x_hb, y_hem, z_hf), V(-x_hb, y_hem, z_hf)],
            JACKET_SHADE, out=(0, -1, 0))

    # Front split: Left cream panel, Center navy shirt strip, Right cream panel
    mb.face([V( x_open, y_hem, z_hf), V( x_hb, y_hem, z_hf), V( x_sb, y_sh, z_sf), V( x_open, y_sh, z_sf)],
            JACKET, out=(0, 0, 1))
    mb.face([V(-x_hb, y_hem, z_hf), V(-x_open, y_hem, z_hf), V(-x_open, y_sh, z_sf), V(-x_sb, y_sh, z_sf)],
            JACKET, out=(0, 0, 1))
    mb.face([V(-x_open, y_hem, z_hf - 0.008), V(x_open, y_hem, z_hf - 0.008),
             V( x_open, y_sh,  z_sf - 0.006), V(-x_open, y_sh, z_sf - 0.006)],
            SHIRT_INNER, out=(0, 0, 1))

    # Cozy folded cream collar / hood rim around neck (10 tris)
    col_r0 = [
        V(-0.135, 1.095,  0.118),
        V( 0.135, 1.095,  0.118),
        V( 0.145, 1.085, -0.125),
        V(-0.145, 1.085, -0.125),
    ]
    col_r1 = [
        V(-0.105, 1.162,  0.095),
        V( 0.105, 1.162,  0.095),
        V( 0.120, 1.170, -0.112),
        V(-0.120, 1.170, -0.112),
    ]
    mb.loft([col_r0, col_r1], JACKET_COLLAR, cap_bottom=False, cap_top=True, top_color=JACKET_COLLAR)

    # Two subtle patch pockets on lower front panels of cream jacket (4 tris)
    for side in (-1, 1):
        px0 = side * 0.062
        px1 = side * 0.155
        if px0 > px1:
            px0, px1 = px1, px0
        pz0 = z_hf + 0.005
        pz1 = z_hf - 0.001
        mb.face([V(px0, 0.655, pz0), V(px1, 0.655, pz0), V(px1, 0.760, pz1), V(px0, 0.760, pz1)],
                JACKET_POCKET, out=(0, 0, 1))

    # =========================================================================
    # 8. BOTH ARMS & HANDS REACHING FORWARD TO STROLLER HANDLEBAR (52 tris)
    # =========================================================================
    mb.set_part("arms_and_hands")
    for side, bname in ((1, "Arm_L"), (-1, "Arm_R")):
        mb.set_bone(bname)
        p_sh = V(side * 0.168, SHOULDER_Y, SHOULDER_Z)
        p_el = V(side * 0.214, 0.818, 0.088)
        p_wr = V(side * 0.178, HANDLE_Y + 0.022, HANDLE_Z - 0.082)

        def arm_ring(ctr, axis, rx, ry):
            ax, u, v = ortho_basis(axis, hint=V(1.0, 0.0, 0.0))
            return [
                ctr + u * rx + v * ry,
                ctr - u * rx + v * ry,
                ctr - u * rx - v * ry,
                ctr + u * rx - v * ry,
            ]

        ax_up = (p_el - p_sh).normalized()
        ax_lo = (p_wr - p_el).normalized()
        ax_el = (ax_up + ax_lo).normalized()

        r_sh = arm_ring(p_sh, ax_up, 0.068, 0.068)
        r_el = arm_ring(p_el, ax_el, 0.064, 0.064)
        r_wr = arm_ring(p_wr, ax_lo, 0.056, 0.056)

        def sleeve_col(i, k):
            return JACKET_SHADE if k == 2 else JACKET

        # Skip hidden end caps (shoulder buried in torso, wrist tucked into hand)
        mb.loft([r_sh, r_el, r_wr], sleeve_col, cap_bottom=False, cap_top=False)

        # Chunky skin hand gripping right on top of the black stroller handlebar (10 tris per hand)
        hx = side * 0.162
        mb.box(
            hx - 0.040, hx + 0.040,
            HANDLE_Y - 0.016, HANDLE_Y + 0.054,
            HANDLE_Z - 0.084, HANDLE_Z + 0.024,
            {"default": SKIN, "bottom": SKIN_SHADE, "back": SKIN_SHADE},
            skip=("back",),
        )

    # =========================================================================
    # 9. CROSSBODY OLIVE-TAUPE MESSENGER PURSE + SNUG STRAP (30 tris)
    # =========================================================================
    mb.set_part("purse", bone="Purse")
    bc = V(-0.230, 0.600, -0.114)
    roll = math.radians(-10.0)
    yaw  = math.radians(-14.0)
    cr, sr = math.cos(roll), math.sin(roll)
    cy, sy = math.cos(yaw),  math.sin(yaw)

    def bpt(lx, ly, lz):
        rx = lx * cr - ly * sr
        ry = lx * sr + ly * cr
        rz = lz
        wx = rx * cy + rz * sy
        wz = -rx * sy + rz * cy
        return bc + V(wx, ry, wz)

    hx_b, hy_b, hz_b = 0.048, 0.086, 0.112
    p000 = bpt(-hx_b, -hy_b, -hz_b); p100 = bpt( hx_b, -hy_b, -hz_b)
    p101 = bpt( hx_b, -hy_b,  hz_b); p001 = bpt(-hx_b, -hy_b,  hz_b)
    p010 = bpt(-hx_b,  hy_b, -hz_b); p110 = bpt( hx_b,  hy_b, -hz_b)
    p111 = bpt( hx_b,  hy_b,  hz_b); p011 = bpt(-hx_b,  hy_b,  hz_b)
    mb.face([p000, p001, p011, p010], PURSE,       out=(-1, 0, 0))
    mb.face([p101, p100, p110, p111], PURSE_SHADE, out=( 1, 0, 0))
    mb.face([p001, p101, p111, p011], PURSE_SHADE, out=( 0, 0, 1))
    mb.face([p100, p000, p010, p110], PURSE_SHADE, out=( 0, 0,-1))
    mb.face([p011, p111, p110, p010], PURSE_FLAP,  out=( 0, 1, 0))
    mb.face([p000, p100, p101, p001], PURSE_SHADE, out=( 0,-1, 0))

    # Overlapping outer messenger flap (6 tris)
    fx_o = -hx_b - 0.011
    fy_t =  hy_b + 0.005
    fy_b = -0.014
    hz_f =  hz_b + 0.004
    fl0 = bpt(fx_o, fy_b, -hz_f); fl1 = bpt(fx_o, fy_b,  hz_f)
    fl2 = bpt(fx_o, fy_t,  hz_f); fl3 = bpt(fx_o, fy_t, -hz_f)
    mb.face([fl0, fl1, fl2, fl3], PURSE_FLAP, out=(-1, 0, 0))
    mb.face([fl3, fl2, p011, p010], PURSE_FLAP, out=(-0.3, 1, 0))
    mb.face([bpt(-hx_b, fy_b, -hz_f), bpt(-hx_b, fy_b, hz_f), fl1, fl0], PURSE_SHADE, out=(0, -1, 0))

    # Warm tan leather clasp tab centered on flap bottom (2 tris)
    cx_c = fx_o - 0.007
    mb.face([
        bpt(cx_c, fy_b - 0.018, -0.020),
        bpt(cx_c, fy_b - 0.018,  0.020),
        bpt(cx_c, fy_b + 0.032,  0.020),
        bpt(cx_c, fy_b + 0.032, -0.020),
    ], PURSE_CLASP, out=(-1, 0, 0))

    # Snug brown crossbody strap hugging jacket closely from purse to left shoulder (Torso bone, 10 tris)
    mb.set_part("purse_strap", bone="Torso")
    s_f0 = bpt(0.000, hy_b, hz_b * 0.55)
    s_f1 = V(-0.184, 0.725,  0.088)
    s_f2 = V(-0.048, 0.900,  0.140)
    s_f3 = V( 0.098, 1.114,  0.115)
    w_s = 0.020
    for (pa, pb, nrm) in (
        (s_f0, s_f1, V(-0.85, 0.15, 0.50)),
        (s_f1, s_f2, V(-0.20, 0.10, 0.98)),
        (s_f2, s_f3, V(-0.10, 0.20, 0.98)),
    ):
        d = (pb - pa).normalized()
        side_v = d.cross(nrm).normalized() * w_s
        mb.face([pa - side_v, pa + side_v, pb + side_v, pb - side_v], PURSE_STRAP, out=nrm)

    s_b0 = bpt(0.010, hy_b, -hz_b * 0.45)
    s_b1 = V(-0.155, 0.850, -0.134)
    s_b2 = V( 0.098, 1.114, -0.112)
    for (pa, pb, nrm) in (
        (s_b0, s_b1, V(-0.45, 0.10, -0.90)),
        (s_b1, s_b2, V(-0.10, 0.20, -0.98)),
    ):
        d = (pb - pa).normalized()
        side_v = d.cross(nrm).normalized() * w_s
        mb.face([pa - side_v, pa + side_v, pb + side_v, pb - side_v], PURSE_STRAP, out=nrm)

    # =========================================================================
    # 10. PELVIS BRIDGE + CROPPED WIDE-LEG PANTS + ANKLES + SNEAKERS (~80 tris)
    # =========================================================================
    mb.set_part("pelvis", bone="Root")
    mb.box(-0.170, 0.170, 0.545, 0.640, -0.110, 0.112, PANTS_SHADE, skip=("top", "left", "right"))

    mb.set_part("legs_and_shoes")
    for side, bname in ((1, "Leg_L"), (-1, "Leg_R")):
        mb.set_bone(bname)
        lx = side * 0.098

        # Wide cropped navy trouser leg (y = 0.245 .. 0.635, 10 tris per leg)
        p_bot = [
            V(lx - 0.086, 0.245,  0.096),
            V(lx + 0.086, 0.245,  0.096),
            V(lx + 0.086, 0.245, -0.092),
            V(lx - 0.086, 0.245, -0.092),
        ]
        p_top = [
            V(lx - 0.082, 0.635,  0.102),
            V(lx + 0.082, 0.635,  0.102),
            V(lx + 0.082, 0.635, -0.098),
            V(lx - 0.082, 0.635, -0.098),
        ]

        def pants_col(i, k):
            if k == 2:
                return PANTS_SHADE
            if (side == 1 and k == 3) or (side == -1 and k == 1):
                return PANTS_SHADE
            return PANTS

        mb.loft([p_bot, p_top], pants_col, cap_bottom=True, cap_top=False, bot_color=PANTS_INNER)

        # Bare skin ankle (y = 0.125 .. 0.255, 8 tris per leg)
        a_bot = oval_ring(lx, 0.125, -0.008, 0.044, 0.046, n=4, phase=math.pi / 4.0)
        a_top = oval_ring(lx, 0.255, -0.006, 0.046, 0.048, n=4, phase=math.pi / 4.0)
        mb.loft([a_bot, a_top], SKIN, cap_bottom=False, cap_top=False)

        # Taupe-olive casual sneaker with light tongue patch & dark sole (24 tris per shoe)
        sx0, sx1 = lx - 0.056, lx + 0.056
        sz_b, sz_m, sz_f = -0.072, 0.052, 0.158
        y_sole = 0.032

        # Dark sole rim (skip top & flat ground bottom = 8 tris)
        mb.box(sx0, sx1, 0.000, y_sole, sz_b, sz_f, SHOE_SOLE, skip=("top", "bottom"))

        # Sculpted shoe upper (16 tris)
        u_hb0 = V(sx0, y_sole, sz_b); u_hb1 = V(sx1, y_sole, sz_b)
        u_hm0 = V(sx0, y_sole, sz_m); u_hm1 = V(sx1, y_sole, sz_m)
        u_hf0 = V(sx0 + 0.008, y_sole, sz_f); u_hf1 = V(sx1 - 0.008, y_sole, sz_f)

        u_tb0 = V(sx0 + 0.004, 0.132, sz_b + 0.006); u_tb1 = V(sx1 - 0.004, 0.132, sz_b + 0.006)
        u_tm0 = V(sx0 + 0.004, 0.128, sz_m);         u_tm1 = V(sx1 - 0.004, 0.128, sz_m)
        u_tf0 = V(sx0 + 0.012, 0.074, sz_f - 0.008); u_tf1 = V(sx1 - 0.012, 0.074, sz_f - 0.008)

        mb.face([u_hb1, u_hb0, u_tb0, u_tb1], SHOE_SHADE, out=(0, 0, -1))
        mb.face([u_hb0, u_hm0, u_tm0, u_tb0], SHOE if side == -1 else SHOE_SHADE, out=(-1, 0, 0))
        mb.face([u_hm1, u_hb1, u_tb1, u_tm1], SHOE if side ==  1 else SHOE_SHADE, out=( 1, 0, 0))
        mb.face([u_hm0, u_hf0, u_tf0, u_tm0], SHOE, out=(-1, 0.2, 0.2))
        mb.face([u_hf1, u_hm1, u_tm1, u_tf1], SHOE, out=( 1, 0.2, 0.2))
        mb.face([u_tb0, u_tm0, u_tm1, u_tb1], SHOE_SHADE, out=(0, 1, 0))
        mb.face([u_tm0, u_tf0, u_tf1, u_tm1], SHOE_TONGUE, out=(0, 0.8, 0.6))
        mb.face([u_hf0, u_hf1, u_tf1, u_tf0], SHOE, out=(0, 0.2, 1))

    # =========================================================================
    # 11. 4-WHEEL STROLLER: FRAME + HANDLEBAR + SEAT + CANOPY + 4 WHEELS
    # =========================================================================
    # 11a. Curved padded handlebar & tubular A-frame chassis (Stroller bone, 68 tris)
    mb.set_part("stroller_frame", bone="Stroller")
    # Clean 4-point black padded handlebar arch (3 segments x 8 = 24 tris)
    hb_pts = [
        V(-HANDLE_HX - 0.008, HANDLE_Y - 0.098, HANDLE_Z + 0.088),
        V(-HANDLE_HX * 0.94,  HANDLE_Y + 0.002, HANDLE_Z),
        V( HANDLE_HX * 0.94,  HANDLE_Y + 0.002, HANDLE_Z),
        V( HANDLE_HX + 0.008, HANDLE_Y - 0.098, HANDLE_Z + 0.088),
    ]
    mb.tube(hb_pts, 0.022, n=4, color=STROLLER_HANDLE, cap_start=False, cap_end=False,
            hint=V(0.0, 1.0, 0.0))

    # Left & right grey metal side A-frame rails (32 tris)
    pivot_y = 0.435
    pivot_z = 0.660
    for side in (-1, 1):
        fx = side * 0.194
        p_top = V(fx, HANDLE_Y - 0.090, HANDLE_Z + 0.082)
        p_mid = V(fx, pivot_y, pivot_z)
        p_frt = V(fx, WHEEL_R + 0.004, FRONT_WZ)
        p_rer = V(fx, WHEEL_R + 0.004, REAR_WZ)

        mb.tube([p_top, p_frt], 0.016, n=4, color=STROLLER_FRAME, hint=V(1.0, 0.0, 0.0))
        mb.tube([p_mid, p_rer], 0.016, n=4, color=STROLLER_FRAME, hint=V(1.0, 0.0, 0.0))

    # Front & rear wheel axles (3-sided crisp rods hidden inside tires = 12 tris)
    mb.tube([V(-WHEEL_HX, WHEEL_R, REAR_WZ),  V(WHEEL_HX, WHEEL_R, REAR_WZ)],
            0.013, n=3, color=STROLLER_FRAME_DARK, hint=V(0.0, 1.0, 0.0))
    mb.tube([V(-WHEEL_HX, WHEEL_R, FRONT_WZ), V(WHEEL_HX, WHEEL_R, FRONT_WZ)],
            0.013, n=3, color=STROLLER_FRAME_DARK, hint=V(0.0, 1.0, 0.0))

    # 11b. Slate-blue stroller seat bucket meeting canopy cleanly with ZERO gap (Stroller bone, 20 tris)
    mb.set_part("stroller_seat", bone="Stroller")
    sx_s = 0.188
    # Raised rear backrest (0.610, 0.468) + higher side-rim contour tucking right into canopy base!
    seat_prof = [
        (0.615, 0.470),  # 0: high back rim nestled cleanly into canopy base
        (0.495, 0.665),  # 1: cozy recessed seat cushion
        (0.475, 0.895),  # 2: plump front cushion top
        (0.375, 0.935),  # 3: rounded front bumper nose
        (0.280, 0.785),  # 4: lower belly front
        (0.325, 0.515),  # 5: lower belly rear
    ]
    s_l = [V( sx_s, y, z) for (y, z) in seat_prof]
    s_r = [V(-sx_s, y, z) for (y, z) in seat_prof]
    n_sp = len(seat_prof)
    c_sp_y = sum(y for (y, _) in seat_prof) / n_sp
    c_sp_z = sum(z for (_, z) in seat_prof) / n_sp
    for k in range(n_sp):
        kn = (k + 1) % n_sp
        col = STROLLER_SEAT if k in (0, 1, 2) else STROLLER_SEAT_DARK
        mid_y = 0.5 * (seat_prof[k][0] + seat_prof[kn][0])
        mid_z = 0.5 * (seat_prof[k][1] + seat_prof[kn][1])
        mb.face([s_r[k], s_l[k], s_l[kn], s_r[kn]], col, out=(0.0, mid_y - c_sp_y, mid_z - c_sp_z))
    mb.face(s_l, STROLLER_SEAT, out=( 1, 0, 0))
    mb.face(s_r, STROLLER_SEAT, out=(-1, 0, 0))

    # 11c. Plush Domed Ribbed Sun Canopy (outer curved dome + dark shadowed interior + closed side cheeks = 44 tris)
    mb.set_part("stroller_canopy", bone="Stroller")

    def canopy_arch(y_side, y_peak, z_side, z_peak, hw):
        return [
            V(-hw,        y_side,                            z_side),
            V(-hw * 0.68, y_side + (y_peak - y_side) * 0.78, z_side + (z_peak - z_side) * 0.72),
            V( 0.0,       y_peak,                            z_peak),
            V( hw * 0.68, y_side + (y_peak - y_side) * 0.78, z_side + (z_peak - z_side) * 0.72),
            V( hw,        y_side,                            z_side),
        ]

    # Plush rounded quarter-dome resting flush onto the seat rim with zero daylight gap
    rib0 = canopy_arch(0.550, 0.620, 0.465, 0.450, 0.194)  # rear base tucked flush over seat back
    rib1 = canopy_arch(0.655, 0.875, 0.510, 0.560, 0.205)  # plush rounded upper-rear dome
    rib2 = canopy_arch(0.640, 0.892, 0.690, 0.775, 0.205)  # broad smooth crown
    rib3 = canopy_arch(0.560, 0.705, 0.900, 0.985, 0.194)  # curved front sunshade visor

    ribs = [rib0, rib1, rib2, rib3]
    dome_ctr = V(0.0, 0.540, 0.690)
    for i in range(3):
        r0, r1 = ribs[i], ribs[i + 1]
        col = STROLLER_CANOPY_ALT if i == 1 else STROLLER_CANOPY
        for j in range(4):
            p0, p1, p2, p3 = r0[j], r0[j + 1], r1[j + 1], r1[j]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], col, out=mid - dome_ctr)

    # Dark shadowed interior lining inside canopy opening (16 tris)
    rib_in_mid = canopy_arch(0.575, 0.785, 0.665, 0.715, 0.175)
    rib_in_bak = canopy_arch(0.515, 0.610, 0.505, 0.495, 0.170)
    for (ra, rb) in ((rib3, rib_in_mid), (rib_in_mid, rib_in_bak)):
        for j in range(4):
            p0, p1, p2, p3 = ra[j], ra[j + 1], rb[j + 1], rb[j]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], STROLLER_UNDER, out=dome_ctr - mid)

    # Closed side canopy cheek gussets bridging canopy rim seamlessly down onto seat sides (4 tris)
    mb.face([rib0[0], rib1[0], rib2[0], rib3[0]], STROLLER_SEAT, out=(-1, 0, 0))
    mb.face([rib0[4], rib3[4], rib2[4], rib1[4]], STROLLER_SEAT, out=( 1, 0, 0))

    # 11d. 4 Chunky 8-Sided Wheels with 6-Sided Light-Grey Hubcaps (128 tris)
    mb.set_part("stroller_wheels")
    mb.set_bone("Wheel_Rear")
    add_wheel(mb,  WHEEL_HX, WHEEL_R, REAR_WZ,  WHEEL_R, 0.032,  1, n=8, n_hub=6)
    add_wheel(mb, -WHEEL_HX, WHEEL_R, REAR_WZ,  WHEEL_R, 0.032, -1, n=8, n_hub=6)

    mb.set_bone("Wheel_Front")
    add_wheel(mb,  WHEEL_HX, WHEEL_R, FRONT_WZ, WHEEL_R, 0.032,  1, n=8, n_hub=6)
    add_wheel(mb, -WHEEL_HX, WHEEL_R, FRONT_WZ, WHEEL_R, 0.032, -1, n=8, n_hub=6)

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


def _stroller_ground_compensation(root_loc, root_rot, push_z=0.0):
    """Exact local (location, rotation_euler) for Stroller (child of Root) so wheels stay locked on y = 0."""
    # Bone spaces of Root and Stroller are both aligned with Game (X, Y, Z).
    # Offset of Stroller head relative to Root head in Game frame:
    d = Vector((0.0, WHEEL_R - ROOT_Y, STROLLER_Z))
    m_root = Matrix.Translation(Vector(root_loc)) @ Euler(root_rot, "XYZ").to_matrix().to_4x4()
    m_local = (
        Matrix.Translation(-d)
        @ m_root.inverted()
        @ Matrix.Translation(d + Vector((0.0, 0.0, push_z)))
    )
    loc, quat, _ = m_local.decompose()
    return loc, quat.to_euler("XYZ")


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: lively stroll pushing stroller with rolling wheels, bouncy curls & swinging purse."""
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

        # Gentle energetic step bounce & natural slight forward lean into pushing stroller
        # Positive local X rotation tilts +Y (upper body) toward +Z (forward).
        pb_root = rig.pose.bones["Root"]
        bob = -0.020 * (1.0 - c2) * 0.5
        root_loc = (0.0, bob, 0.0)
        root_rot = (0.044, -0.032 * s1, 0.022 * c1)
        pb_root.location = root_loc
        pb_root.rotation_euler = root_rot
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle torso counter-twist while keeping hands steady on handlebar
        pb_torso = rig.pose.bones["Torso"]
        torso_pitch = 0.014 * c2
        pb_torso.rotation_euler = (torso_pitch, 0.038 * s1, -0.016 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Cheerful attentive head gaze looking ahead (countering slight forward lean)
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.036 + 0.024 * s2, -0.020 * s1, -0.012 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Fluffy curly hair bounces happily with slight phase lag
        pb_hair = rig.pose.bones["Hair"]
        pb_hair.rotation_euler = (0.055 * math.sin(2.0 * phi - 0.65), 0.0, 0.032 * math.sin(phi - 0.45))
        pb_hair.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating sneaker stride clearing stroller rear axle cleanly
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.36 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.032, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.36 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.032, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Arms counter-pitch smoothly so both hands stay locked right onto the black handlebar!
        arm_comp_x = -(root_rot[0] + torso_pitch) * 0.85 - bob * 1.40
        for bname in ("Arm_L", "Arm_R"):
            pb_a = rig.pose.bones[bname]
            pb_a.rotation_euler = (arm_comp_x, -0.024 * s1, -0.008 * c1)
            pb_a.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crossbody purse swings gently at right hip with weighted phase lag
        pb_purse = rig.pose.bones["Purse"]
        pb_purse.rotation_euler = (0.075 * math.sin(phi - 0.55), 0.0, 0.032 * c1)
        pb_purse.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Exact matrix compensation pins all 4 stroller wheels firmly onto y = 0.0!
        push_z = 0.008 * s2
        s_loc, s_rot = _stroller_ground_compensation(root_loc, root_rot, push_z=push_z)
        pb_stroller = rig.pose.bones["Stroller"]
        pb_stroller.location = s_loc
        pb_stroller.rotation_euler = s_rot
        pb_stroller.keyframe_insert(data_path="location", frame=frame)
        pb_stroller.keyframe_insert(data_path="rotation_euler", frame=frame)

        # All 4 wheels roll continuously forward 1 full revolution (2*pi) per walk cycle!
        for wname in ("Wheel_Rear", "Wheel_Front"):
            pb_w = rig.pose.bones[wname]
            pb_w.rotation_euler = (phi, 0.0, 0.0)
            pb_w.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: calm wait with gentle soothing stroller rock & affectionate downward peek."""
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

        # Gentle soothing forward/back stroller rock (+-3.6 cm)
        rock_z = 0.036 * s1
        bob = -0.006 * (1.0 - c1) * 0.5
        root_loc = (0.0, bob, 0.0)
        root_rot = (0.012 + 0.022 * s1, 0.012 * s2, 0.010 * s1)

        pb_root = rig.pose.bones["Root"]
        pb_root.location = root_loc
        pb_root.rotation_euler = root_rot
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        torso_pitch = 0.024 * s1 + 0.012 * s2
        pb_torso.rotation_euler = (torso_pitch, 0.014 * s1, -0.008 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Affectionate downward glance (+X pitch nods chin down toward baby in stroller!), then looks up/around
        pb_head = rig.pose.bones["Head"]
        head_pitch = 0.095 - 0.105 * c1   # ranges from -0.01 (level ahead) to +0.20 rad (warm peek down into stroller!)
        pb_head.rotation_euler = (head_pitch, 0.14 * s1, 0.026 * s1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curly hair shifts softly with affectionate head nod
        pb_hair = rig.pose.bones["Hair"]
        pb_hair.rotation_euler = (0.028 * math.sin(phi - 0.4), 0.0, 0.018 * s1)
        pb_hair.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sneakers planted steadily on dock
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Arms smoothly push and pull in sync with the gentle stroller rock, staying locked on handlebar
        arm_x = -(root_rot[0] + torso_pitch) * 0.55 - 0.045 * s1
        for bname in ("Arm_L", "Arm_R"):
            pb_a = rig.pose.bones[bname]
            pb_a.rotation_euler = (arm_x, -0.010 * s1, 0.0)
            pb_a.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crossbody purse settles gently
        pb_purse = rig.pose.bones["Purse"]
        pb_purse.rotation_euler = (0.026 * s1, 0.0, 0.016 * s2)
        pb_purse.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Exact matrix compensation keeps all 4 stroller wheels glued to y = 0 while rocking smoothly!
        s_loc, s_rot = _stroller_ground_compensation(root_loc, root_rot, push_z=rock_z)
        pb_stroller = rig.pose.bones["Stroller"]
        pb_stroller.location = s_loc
        pb_stroller.rotation_euler = s_rot
        pb_stroller.keyframe_insert(data_path="location", frame=frame)
        pb_stroller.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Wheels roll cleanly by rock_z / WHEEL_R
        wheel_ang = rock_z / WHEEL_R
        for wname in ("Wheel_Rear", "Wheel_Front"):
            pb_w = rig.pose.bones[wname]
            pb_w.rotation_euler = (wheel_ang, 0.0, 0.0)
            pb_w.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 12-bone rig (7 standard passenger bones + Hair, Purse, Stroller, Wheel_Rear, Wheel_Front)."""
    arm_data = bpy.data.armatures.new("PersonStrollerRig")
    rig = bpy.data.objects.new("PersonStrollerRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",        None,       ( 0.000, ROOT_Y,  0.000), ( 0.000, ROOT_Y + 0.12, 0.000)),
        ("Torso",       "Root",     ( 0.000, 0.640,   0.000), ( 0.000, 1.100,         0.000)),
        ("Head",        "Torso",    ( 0.000, 1.155,   0.000), ( 0.000, 1.485,         0.000)),
        ("Hair",        "Head",     ( 0.000, 1.380,  -0.145), ( 0.000, 1.530,        -0.145)),
        ("Arm_L",       "Torso",    ( 0.168, SHOULDER_Y, SHOULDER_Z), ( 0.168, SHOULDER_Y + 0.16, SHOULDER_Z)),
        ("Arm_R",       "Torso",    (-0.168, SHOULDER_Y, SHOULDER_Z), (-0.168, SHOULDER_Y + 0.16, SHOULDER_Z)),
        ("Purse",       "Torso",    (-0.235, 0.720,  -0.115), (-0.235, 0.870,        -0.115)),
        ("Leg_L",       "Root",     ( 0.098, ROOT_Y,  0.000), ( 0.098, ROOT_Y + 0.16, 0.000)),
        ("Leg_R",       "Root",     (-0.098, ROOT_Y,  0.000), (-0.098, ROOT_Y + 0.16, 0.000)),
        ("Stroller",    "Root",     ( 0.000, WHEEL_R, STROLLER_Z), ( 0.000, WHEEL_R + 0.20, STROLLER_Z)),
        ("Wheel_Rear",  "Stroller", ( 0.000, WHEEL_R, REAR_WZ),    ( 0.000, WHEEL_R + 0.14, REAR_WZ)),
        ("Wheel_Front", "Stroller", ( 0.000, WHEEL_R, FRONT_WZ),   ( 0.000, WHEEL_R + 0.14, FRONT_WZ)),
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-2.90, math.radians(62)),   # Front-3/4 matching reference angle (facing right)
        (-0.95, math.radians(0)),    # Front
        ( 0.95, math.radians(90)),   # Side (showing full mom + stroller profile)
        ( 2.90, math.radians(180)),  # Back
    ]
    obj.hide_render = True
    for (xpos, zrot) in specs:
        c = obj.copy()
        dx = -0.36 * math.sin(zrot)
        dy =  0.36 * math.cos(zrot)
        c.location = (xpos + dx, dy, 0.0)
        c.rotation_euler = (0.0, 0.0, zrot)
        c.hide_render = False
        scene.collection.objects.link(c)
        clones.append(c)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.8
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.5, 1.25)
    direction = Vector((0.0, 0.0, 0.88)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1520
    scene.render.resolution_y = 560
    scene.render.filepath = out_path
    scene.view_settings.view_transform = "Standard"
    bpy.ops.render.render(write_still=True)

    obj.hide_render = False
    for o in [key_obj, fill_obj, floor, cam_obj] + clones:
        bpy.data.objects.remove(o, do_unlink=True)


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=64):
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("StripFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=22.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("StripFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    zrot = math.radians(zrot_deg)
    dx = -0.36 * math.sin(zrot)
    dy =  0.36 * math.cos(zrot)

    snapshots = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.hide_render = True
    for idx, f in enumerate(frames):
        scene.frame_set(f)
        depsgraph.update()
        eval_obj = obj.evaluated_get(depsgraph)
        snap_mesh = bpy.data.meshes.new_from_object(eval_obj)
        snap_obj = bpy.data.objects.new(f"StripSnap_{f}", snap_mesh)
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.88
        snap_obj.location = (xpos + dx, dy, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, zrot)
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 11.6
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -7.5, 1.25)
    direction = Vector((0.0, 0.0, 0.88)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1680
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=60, zrot_right_deg=90):
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("VidFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 4.6
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.22)
    direction = Vector((0.0, 0.0, 0.88)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 920
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"

    zrot_l = math.radians(zrot_left_deg)
    zrot_r = math.radians(zrot_right_deg)
    dxl, dyl = -0.36 * math.sin(zrot_l), 0.36 * math.cos(zrot_l)
    dxr, dyr = -0.36 * math.sin(zrot_r), 0.36 * math.cos(zrot_r)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.hide_render = True

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in range(1, cycle_len + 1):
            scene.frame_set(f)
            depsgraph.update()
            eval_obj = obj.evaluated_get(depsgraph)
            snap_mesh = bpy.data.meshes.new_from_object(eval_obj)

            left_obj = bpy.data.objects.new(f"VidL_{f}", snap_mesh)
            left_obj.location = (-1.05 + dxl, dyl, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, zrot_l)
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (1.05 + dxr, dyr, 0.0)
            right_obj.rotation_euler = (0.0, 0.0, zrot_r)
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

    coll = bpy.data.collections.new("PersonStroller")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonStroller")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonStroller", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris < 650, f"Triangle count {total_tris} exceeds strict 650-tri budget!"

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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=64)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=56)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH,
                          zrot_left_deg=60, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH,
                          zrot_left_deg=52, zrot_right_deg=90)

    print("=== PersonStroller Stats ===")
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
