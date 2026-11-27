# Builds an ultra-low-poly (< 450 tris) stylized man in a manual wheelchair:
# warm taupe baseball cap with darker visor, short dark-brown hair & sideburns,
# navy quilted hooded puffer vest with chest emblem over cream long-sleeves,
# warm dark-brown trousers, chunky off-white sneakers resting on an angled footrest,
# and a dark charcoal wheelchair with open 6-spoke light-rim rear wheels, push handles,
# and rolling front caster wheels, matching the reference artwork.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_wheelchair.py)
# Saves art/person_wheelchair.blend, exports assets/models/person_wheelchair.glb (rigged + Walk & Idle cycles),
# renders art/person_wheelchair_preview.png, art/person_wheelchair_walk_preview.png,
# art/person_wheelchair_idle_preview.png, and outputs rendered videos
# art/person_wheelchair_walk.mp4 and art/person_wheelchair_idle.mp4.
#
# Strict triangle budget: < 450 triangles.
# Game frame: +Z forward, +Y up, +X left, wheels on ground at y = 0, ~1.43 m seated height.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_wheelchair.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_wheelchair.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_wheelchair_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_wheelchair_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_wheelchair_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_wheelchair_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_wheelchair_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN              = col_srgb(0.98, 0.76, 0.55)
SKIN_SHADE        = col_srgb(0.87, 0.65, 0.44)

EYE               = col_srgb(0.11, 0.10, 0.10)

HAIR              = col_srgb(0.27, 0.20, 0.16)
HAIR_SHADE        = col_srgb(0.19, 0.14, 0.11)

CAP               = col_srgb(0.64, 0.59, 0.53)
CAP_TOP           = col_srgb(0.70, 0.65, 0.59)
CAP_SHADE         = col_srgb(0.54, 0.49, 0.44)
CAP_BRIM          = col_srgb(0.43, 0.40, 0.37)
CAP_UNDER         = col_srgb(0.31, 0.29, 0.27)

VEST              = col_srgb(0.24, 0.30, 0.42)
VEST_HIGHLIGHT    = col_srgb(0.31, 0.38, 0.50)
VEST_SHADE        = col_srgb(0.17, 0.22, 0.32)
VEST_HOOD         = col_srgb(0.27, 0.34, 0.46)
VEST_BADGE        = col_srgb(0.82, 0.75, 0.66)

SLEEVE            = col_srgb(0.96, 0.92, 0.85)
SLEEVE_SHADE      = col_srgb(0.86, 0.81, 0.74)

PANTS             = col_srgb(0.39, 0.34, 0.30)
PANTS_SHADE       = col_srgb(0.28, 0.24, 0.21)

SHOE              = col_srgb(0.96, 0.94, 0.90)
SHOE_SHADE        = col_srgb(0.87, 0.84, 0.80)
SOLE              = col_srgb(0.77, 0.74, 0.70)

CHAIR_FRAME       = col_srgb(0.29, 0.28, 0.28)
CHAIR_FRAME_DARK  = col_srgb(0.20, 0.19, 0.19)
CHAIR_SEAT        = col_srgb(0.24, 0.23, 0.23)
CHAIR_HANDLE      = col_srgb(0.33, 0.32, 0.32)

WHEEL_TIRE        = col_srgb(0.25, 0.24, 0.24)
WHEEL_TIRE_SIDE   = col_srgb(0.21, 0.20, 0.20)
WHEEL_RIM         = col_srgb(0.79, 0.78, 0.76)
WHEEL_SPOKE       = col_srgb(0.28, 0.27, 0.27)
WHEEL_HUB         = col_srgb(0.38, 0.37, 0.37)

CASTER_TIRE       = col_srgb(0.23, 0.22, 0.22)
CASTER_SIDE       = col_srgb(0.32, 0.31, 0.31)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin":   [SKIN, SKIN_SHADE],
    "hair":   [HAIR, HAIR_SHADE],
    "top":    [VEST, VEST_HIGHLIGHT, VEST_SHADE, VEST_HOOD],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [CAP, CAP_TOP, CAP_SHADE, CAP_BRIM, CAP_UNDER],
}


# Shared geometric anchors for model & rig alignment (Game frame)
R_MAIN        = 0.294   # large rear wheel outer radius (diameter 0.588 m)
REAR_WZ       = -0.145  # rear wheel axle Z
REAR_WX       = 0.264   # rear wheel center |X|

R_CASTER      = 0.098   # small front caster radius (exact 1:3 ratio with R_MAIN!)
FRONT_WZ      = 0.258   # front caster axle Z (cleanly clear of rear wheel!)
FRONT_WX      = 0.184   # front caster center |X|

SHOULDER_X    = 0.162
SHOULDER_Y    = 0.842
SHOULDER_Z    = -0.040
ELBOW_X       = 0.232
ELBOW_Y       = 0.672
ELBOW_Z       = -0.068
WRIST_X       = 0.194
WRIST_Y       = 0.594
WRIST_Z       = 0.112


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

    def tube(self, centers, radii, n=3, color=CHAIR_FRAME, cap_start=False, cap_end=False,
             hint=V(1.0, 0.0, 0.0), phase=0.0):
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


def add_big_wheel(mb, cx, cy, cz, radius, side_sign, n=8):
    """Build a crisp hollow 8-sided wheelchair rear wheel with chunky dark charcoal outer tire,
    crisp light-grey inner metal rim, 6 open radial spokes (3 diameter bars), and central hub.
    Total = 48 (3-band hollow tire+rim) + 12 (6 spokes) + 2 (hub) = 62 tris per wheel!
    """
    r_outer = radius            # 0.294 m outer rubber tire crown
    r_rim   = radius * 0.818    # 0.240 m meaty dark tire -> crisp light-grey metal rim
    r_hole  = radius * 0.708    # 0.208 m open inner rim bore

    x_crown = cx - side_sign * 0.004
    x_out   = cx + side_sign * 0.026
    x_in    = cx - side_sign * 0.022

    ring_crown = []
    ring_out   = []
    ring_in    = []
    for k in range(n):
        a = math.pi / n + 2.0 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        ring_crown.append(V(x_crown, cy + r_outer * sa, cz + r_outer * ca))
        ring_out.append(  V(x_out,   cy + r_rim   * sa, cz + r_rim   * ca))
        ring_in.append(   V(x_in,    cy + r_hole  * sa, cz + r_hole  * ca))

    # 3-band watertight triangular-section hollow ring (3 * 8 * 2 = 48 tris):
    #   1. ring_crown -> ring_out: dark charcoal outer tire wall & tread bevel (visible side + 3/4 + front/back)
    #   2. ring_out   -> ring_in:  bright light-grey inner metal rim sloping gently inward (visible side + 3/4!)
    #   3. ring_in    -> ring_crown: dark charcoal inner tire wall closing the back cleanly
    for k in range(n):
        kn = (k + 1) % n
        # 1. Outer tire bevel/sidewall
        p0, p1, p2, p3 = ring_crown[k], ring_crown[kn], ring_out[kn], ring_out[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        rad = V(0.0, mid.y - cy, mid.z - cz).normalized()
        mb.face([p0, p1, p2, p3], WHEEL_TIRE, out=(rad * 0.70 + V(side_sign * 0.70, 0.0, 0.0)))

        # 2. Bright light-grey inner metal rim / push-rim
        p0, p1, p2, p3 = ring_out[k], ring_out[kn], ring_in[kn], ring_in[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        inward = V(0.0, cy - mid.y, cz - mid.z).normalized()
        mb.face([p0, p1, p2, p3], WHEEL_RIM, out=(inward * 0.65 + V(side_sign * 0.75, 0.0, 0.0)))

        # 3. Inner back tire sidewall
        p0, p1, p2, p3 = ring_in[k], ring_in[kn], ring_crown[kn], ring_crown[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        rad = V(0.0, mid.y - cy, mid.z - cz).normalized()
        mb.face([p0, p1, p2, p3], WHEEL_TIRE_SIDE, out=(rad * 0.35 + V(-side_sign * 0.92, 0.0, 0.0)))

    # 6 crisp open radial spokes built from 3 full-diameter bars (3 * 4 = 12 tris)
    spoke_len = r_hole + 0.012
    spoke_hw = 0.0135
    sx_out = cx + side_sign * 0.006
    sx_in  = cx - side_sign * 0.006
    for s_idx in range(3):
        ang = math.radians(15.0 + s_idx * 60.0)
        dy, dz = math.sin(ang), math.cos(ang)
        py, pz = -dz, dy  # perpendicular in YZ plane
        pA0 = V(sx_out, cy - dy * spoke_len - py * spoke_hw, cz - dz * spoke_len - pz * spoke_hw)
        pA1 = V(sx_out, cy - dy * spoke_len + py * spoke_hw, cz - dz * spoke_len + pz * spoke_hw)
        pB1 = V(sx_out, cy + dy * spoke_len + py * spoke_hw, cz + dz * spoke_len + pz * spoke_hw)
        pB0 = V(sx_out, cy + dy * spoke_len - py * spoke_hw, cz + dz * spoke_len - pz * spoke_hw)
        mb.face([pA0, pA1, pB1, pB0], WHEEL_SPOKE, out=(side_sign, 0.0, 0.0))

        qA0 = V(sx_in, cy - dy * spoke_len - py * spoke_hw, cz - dz * spoke_len - pz * spoke_hw)
        qA1 = V(sx_in, cy - dy * spoke_len + py * spoke_hw, cz - dz * spoke_len + pz * spoke_hw)
        qB1 = V(sx_in, cy + dy * spoke_len + py * spoke_hw, cz + dz * spoke_len + pz * spoke_hw)
        qB0 = V(sx_in, cy + dy * spoke_len - py * spoke_hw, cz + dz * spoke_len - pz * spoke_hw)
        mb.face([qA1, qA0, qB0, qB1], WHEEL_SPOKE, out=(-side_sign, 0.0, 0.0))

    # Crisp central hubcap diamond on outer face (1 quad = 2 tris)
    hx = cx + side_sign * 0.014
    hr = 0.044
    mb.face([
        V(hx, cy + hr, cz),
        V(hx, cy,      cz + hr),
        V(hx, cy - hr, cz),
        V(hx, cy,      cz - hr),
    ], WHEEL_HUB, out=(side_sign, 0.0, 0.0))


def add_caster_wheel(mb, cx, cy, cz, radius, half_w, side_sign, n=6):
    """Build a sturdy low-poly 6-sided front caster wheel (12 + 4 + 4 = 20 tris)."""
    x_in = cx - side_sign * half_w
    x_out = cx + side_sign * half_w
    r_in = []
    r_out = []
    for k in range(n):
        a = math.pi / n + 2.0 * math.pi * k / n
        dy = radius * math.sin(a)
        dz = radius * math.cos(a)
        r_in.append(V(x_in, cy + dy, cz + dz))
        r_out.append(V(x_out, cy + dy, cz + dz))

    for k in range(n):
        kn = (k + 1) % n
        p0, p1, p2, p3 = r_in[k], r_in[kn], r_out[kn], r_out[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], CASTER_TIRE, out=V(0.0, mid.y - cy, mid.z - cz))

    mb.face(r_out, CASTER_SIDE, out=(side_sign, 0.0, 0.0))
    mb.face(r_in,  CASTER_SIDE, out=(-side_sign, 0.0, 0.0))


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + INTEGRATED DARK-BROWN BACK HAIR & CRISP SIDEBURNS (30 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,      rx,    rz)
        (0.986, -0.012, 0.156, 0.150),  # 0: rounded jaw/chin nestled cozily above navy collar
        (1.070, -0.008, 0.208, 0.198),  # 1: full cheeks & ear line
        (1.248, -0.020, 0.200, 0.190),  # 2: brow/hairline tucked snugly inside cap rim
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks with crisp dark sideburns,
    # k=1,2,3 dark brown hair wrapping smoothly around back & nape.
    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            out_dir = mid - cmid
            if i == 0:
                col = SKIN if k in (4, 5, 0) else HAIR_SHADE
                mb.face([p0, p1, p2, p3], col, out=out_dir)
            else:
                if k == 0:
                    # Left cheek (+X): crisp dark-brown sideburn strip in front of ear
                    p_b_sb = p0.lerp(p1, 0.64)
                    p_t_sb = p3.lerp(p2, 0.52)
                    mb.face([p0, p_b_sb, p_t_sb, p3], SKIN, out=out_dir)
                    mb.face([p_b_sb, p1, p2, p_t_sb], HAIR, out=out_dir)
                elif k == 4:
                    # Right cheek (-X): mirrored crisp dark-brown sideburn strip
                    p_b_sb = p1.lerp(p0, 0.64)
                    p_t_sb = p2.lerp(p3, 0.52)
                    mb.face([p_b_sb, p1, p2, p_t_sb], SKIN, out=out_dir)
                    mb.face([p0, p_b_sb, p_t_sb, p3], HAIR, out=out_dir)
                else:
                    col = SKIN if k == 5 else HAIR
                    mb.face([p0, p1, p2, p3], col, out=out_dir)

    # Front chin underside cap (2 tris)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. EARS (2 cute tucked low-poly wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in  = side * 0.192
        x_out = side * 0.236
        y0, y1 = 1.072, 1.158
        z0, z1 = -0.036, 0.024
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.012, zm)
        p_ot = V(x_out, y1 - 0.012, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 3. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    cy_e = 1.156
    t_eye = (cy_e - 1.070) / (1.248 - 1.070)
    z_face = head_rings[1][5].z + (head_rings[2][5].z - head_rings[1][5].z) * t_eye
    z_eye = z_face + 0.0045
    for side in (-1, 1):
        cx = side * 0.060
        rx = 0.017
        ry = 0.046
        pts = [
            V(cx,      cy_e + ry,        z_eye),
            V(cx + rx, cy_e + ry * 0.58, z_eye),
            V(cx + rx, cy_e - ry * 0.58, z_eye),
            V(cx,      cy_e - ry,        z_eye),
            V(cx - rx, cy_e - ry * 0.58, z_eye),
            V(cx - rx, cy_e + ry * 0.58, z_eye),
        ]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 4. NECK (front/side skin prism, back tucked inside navy hood = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.066, 0.922, -0.068), V(0.000, 0.922, 0.044), V(0.066, 0.922, -0.068)]
    n_t = [V(-0.062, 1.002, -0.064), V(0.000, 1.002, 0.040), V(0.062, 1.002, -0.064)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 5. WARM TAUPE BASEBALL CAP WITH DARKER CURVED BRIM (26 tris)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    # Classic 6-panel rounded baseball cap tilted back ~15 deg so rim sits snugly above eyes
    # and dips smoothly down over back dark hair, with a soft rounded dome (never pointy!).
    cap_tilt = math.radians(15.0)
    st, ct = math.sin(cap_tilt), math.cos(cap_tilt)
    cap_orig = V(0.0, 1.216, -0.020)

    def cap_ring(h, rx, rz):
        cy = cap_orig.y + h * ct
        cz = cap_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, cap_tilt, n=6, phase=math.pi / 6.0)

    c_r0 = cap_ring(0.000, 0.232, 0.228)  # sweatband rim hugging cleanly outside head
    c_r1 = cap_ring(0.146, 0.184, 0.188)  # broad rounded upper crown shoulder (soft silhouette!)
    c_apex = V(0.0, cap_orig.y + 0.188 * ct, cap_orig.z - 0.188 * st)

    # Lower 6 panels (12 tris) + 6 gently domed top crown panels (6 tris) = 18 tris!
    mb.loft([c_r0, c_r1], lambda i, k: CAP_SHADE if k in (1, 2, 3) else CAP,
            cap_bottom=False, cap_top=False)
    for k in range(6):
        kn = (k + 1) % 6
        col = CAP_TOP if k in (4, 5, 0) else CAP
        mb.face([c_r1[k], c_r1[kn], c_apex], col, out=(0, ct, -st))

    # Sculpted curved darker taupe-charcoal visor / brim (top 4 tris + underside 4 tris = 8 tris)
    b_l_in  = c_r0[0].lerp(c_r0[1], 0.32)
    b_c_in  = c_r0[5].lerp(c_r0[0], 0.50)
    b_r_in  = c_r0[5].lerp(c_r0[4], 0.32)
    b_l_out = V( 0.182, 1.218, 0.274)
    b_c_out = V( 0.000, 1.250, 0.354)
    b_r_out = V(-0.182, 1.218, 0.274)
    brim_drop = V(0.0, -0.024, -0.006)
    mb.face([b_l_in, b_c_in, b_c_out, b_l_out], CAP_BRIM,  out=(0, 1, 0.25))
    mb.face([b_c_in, b_r_in, b_r_out, b_c_out], CAP_BRIM,  out=(0, 1, 0.25))
    mb.face([b_l_in + brim_drop, b_l_out, b_c_out, b_c_in + brim_drop], CAP_UNDER, out=(0, -1, -0.2))
    mb.face([b_c_in + brim_drop, b_c_out, b_r_out, b_r_in + brim_drop], CAP_UNDER, out=(0, -1, -0.2))

    # =========================================================================
    # 6. NAVY QUILTED HOODED PUFFER VEST + DRAPED HOOD + CHEST BADGE (32 tris)
    # =========================================================================
    mb.set_part("puffer_vest", bone="Torso")
    # 3-ring 4-sided plush puffer vest torso (2 rounded puffy bands = 16 tris + top cap 2 tris = 18 tris)
    vest_specs = [
        # (y,     rx,    zf,     zb)
        (0.556, 0.194,  0.112, -0.182),  # 0: lower hem tucked cleanly onto seated hips
        (0.748, 0.214,  0.144, -0.196),  # 1: plush rounded mid-chest puffer baffle swell
        (0.934, 0.192,  0.104, -0.166),  # 2: broad shoulder top framing cream sleeves cleanly
    ]
    v_rings = []
    for (y, rx, zf, zb) in vest_specs:
        v_rings.append([
            V(-rx, y, zf),  # 0: front-right
            V( rx, y, zf),  # 1: front-left
            V( rx, y, zb),  # 2: back-left
            V(-rx, y, zb),  # 3: back-right
        ])

    def vest_col(i, k):
        if k == 0:
            return VEST_HIGHLIGHT if i == 1 else VEST
        if k == 2:
            return VEST_SHADE
        return VEST

    mb.loft(v_rings, vest_col, cap_bottom=False, cap_top=True, top_color=VEST_HOOD)

    # Crisp small warm-beige chest logo patch on upper-left chest (2 tris, fixed color!)
    def _vest_u_z(y):
        t = (y - 0.748) / (0.934 - 0.748)
        return 0.144 + (0.104 - 0.144) * t + 0.0055

    mb.face([
        V(0.058, 0.796, _vest_u_z(0.796)),
        V(0.092, 0.796, _vest_u_z(0.796)),
        V(0.092, 0.830, _vest_u_z(0.830)),
        V(0.058, 0.830, _vest_u_z(0.830)),
    ], VEST_BADGE, out=(0, 0.2, 1))

    # Plush 3-segment draped navy hood/collar rolling warmly behind neck & shoulders (12 tris)
    mb.set_part("vest_hood", bone="Torso")
    hb = [
        V(-0.080, 0.916,  0.096),  # 0: front-right collar base
        V(-0.184, 0.904, -0.222),  # 1: plump rounded back-right hood drape
        V( 0.184, 0.904, -0.222),  # 2: plump rounded back-left hood drape
        V( 0.080, 0.916,  0.096),  # 3: front-left collar base
    ]
    ht = [
        V(-0.072, 0.986,  0.084),  # 0: front-right collar crest
        V(-0.160, 0.998, -0.198),  # 1: softly rounded back-right upper hood fold
        V( 0.160, 0.998, -0.198),  # 2: softly rounded back-left upper hood fold
        V( 0.072, 0.986,  0.084),  # 3: front-left collar crest
    ]
    h_in = [
        V(-0.056, 0.946,  0.052),
        V(-0.092, 0.958, -0.110),
        V( 0.092, 0.958, -0.110),
        V( 0.056, 0.946,  0.052),
    ]
    for k in range(3):
        p0, p1, p2, p3 = hb[k], hb[k + 1], ht[k + 1], ht[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], VEST_HOOD if k != 1 else VEST_SHADE, out=V(mid.x, 0.12, mid.z + 0.04))
        mb.face([ht[k], ht[k + 1], h_in[k + 1], h_in[k]], VEST_HOOD if k != 1 else VEST, out=(0, 1, 0))

    # =========================================================================
    # 7. CREAM LONG-SLEEVE ARMS (tucked cleanly under vest armholes = 32 tris)
    # =========================================================================
    mb.set_part("sleeves")
    arm_specs = [
        ( 1, "Arm_L", "Forearm_L",
          V( SHOULDER_X, SHOULDER_Y, SHOULDER_Z),
          V( ELBOW_X,    ELBOW_Y,    ELBOW_Z),
          V( WRIST_X,    WRIST_Y,    WRIST_Z)),
        (-1, "Arm_R", "Forearm_R",
          V(-SHOULDER_X, SHOULDER_Y, SHOULDER_Z),
          V(-ELBOW_X,    ELBOW_Y,    ELBOW_Z),
          V(-WRIST_X,    WRIST_Y,    WRIST_Z)),
    ]
    for (side, b_up, b_fo, p_sh, p_el, p_wr) in arm_specs:
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        axm = (ax1 + ax2).normalized()

        def s_ring(ctr, ax, ru, rv):
            ref = V(1.0, 0.0, 0.0)
            u = ax.cross(ref)
            if u.length < 1e-5:
                u = V(0.0, 1.0, 0.0)
            u = u.normalized()
            v = u.cross(ax).normalized()
            return [
                ctr + u * (-ru) + v * ( rv),
                ctr + u * ( ru) + v * ( rv),
                ctr + u * ( ru) + v * (-rv),
                ctr + u * (-ru) + v * (-rv),
            ]

        r_sh = s_ring(p_sh, ax1, 0.068, 0.066)
        r_el = s_ring(p_el, axm, 0.084, 0.080)
        r_wr = s_ring(p_wr, ax2, 0.062, 0.060)
        rw = [{b_up: 1.0}, {b_up: 0.5, b_fo: 0.5}, {b_fo: 1.0}]
        mb.loft([r_sh, r_el, r_wr],
                lambda i, k: SLEEVE_SHADE if k in (2, 3) else SLEEVE,
                cap_bottom=False, cap_top=False, ring_weights=rw)

    # =========================================================================
    # 8. CHUNKY HANDS (resting near thighs/rims, on Forearm bones = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for (side, _b_up, b_fo, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(b_fo)
        ax = (p_wr - p_el).normalized()
        u = ax.cross(V(1.0, 0.0, 0.0)).normalized()
        v = u.cross(ax).normalized()

        c0 = p_wr - ax * 0.010
        c1 = p_wr + ax * 0.094
        r0 = [
            c0 + u * (-0.050) + v * ( 0.050),
            c0 + u * ( 0.050) + v * ( 0.050),
            c0 + u * ( 0.050) + v * (-0.050),
            c0 + u * (-0.050) + v * (-0.050),
        ]
        r1 = [
            c1 + u * (-0.038) + v * ( 0.040),
            c1 + u * ( 0.038) + v * ( 0.040),
            c1 + u * ( 0.038) + v * (-0.040),
            c1 + u * (-0.038) + v * (-0.040),
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 9. SEATED WARM-BROWN TROUSERS (2 bent legs on seat -> footrest = 24 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    for side in (-1, 1):
        x_in  = side * 0.006
        x_out = side * 0.184
        x0, x1 = min(x_in, x_out), max(x_in, x_out)
        # 3 cross-section rings: hip (under vest), bent knee, ankle cuff (over sneaker)
        r_hip = [
            V(x0, 0.596, -0.140),
            V(x1, 0.596, -0.140),
            V(x1, 0.456, -0.140),
            V(x0, 0.456, -0.140),
        ]
        r_knee = [
            V(x0, 0.590,  0.324),
            V(x1, 0.590,  0.324),
            V(x1, 0.450,  0.186),
            V(x0, 0.450,  0.186),
        ]
        r_ank = [
            V(x0 + (0.012 if side < 0 else 0.008), 0.214,  0.392),
            V(x1 - (0.008 if side < 0 else 0.012), 0.214,  0.392),
            V(x1 - (0.008 if side < 0 else 0.012), 0.194,  0.238),
            V(x0 + (0.012 if side < 0 else 0.008), 0.194,  0.238),
        ]
        inner_k = 1 if side < 0 else 3
        mb.loft([r_hip, r_knee],
                lambda i, k: PANTS_SHADE if k == 2 else PANTS,
                cap_bottom=False, cap_top=False, skip_k=(2, inner_k))
        mb.loft([r_knee, r_ank],
                lambda i, k: PANTS_SHADE if k in (2, inner_k) else PANTS,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 10. CHUNKY OFF-WHITE SNEAKERS ON ANGLED FOOTREST (2 x 16 = 32 tris)
    # =========================================================================
    mb.set_part("shoes", bone="Root")
    # Footrest top plane slopes gently upward toward front
    def _y_rest(z):
        return 0.120 + 0.075 * (z - FRONT_WZ)

    for side in (-1, 1):
        cx = side * 0.096
        w_heel = 0.066
        w_toe  = 0.056
        z_heel = 0.246
        z_mid  = 0.386
        z_toe  = 0.494
        h_sole = 0.032
        h_col  = 0.106

        # Sole bottom rests flush on footrest -> skip bottom face (4 side quads = 8 tris)
        s_bot = [
            V(cx - w_heel, _y_rest(z_heel), z_heel),
            V(cx + w_heel, _y_rest(z_heel), z_heel),
            V(cx + w_toe,  _y_rest(z_toe),  z_toe),
            V(cx - w_toe,  _y_rest(z_toe),  z_toe),
        ]
        s_top = [
            V(cx - w_heel, _y_rest(z_heel) + h_sole, z_heel),
            V(cx + w_heel, _y_rest(z_heel) + h_sole, z_heel),
            V(cx + w_toe,  _y_rest(z_toe)  + h_sole, z_toe),
            V(cx - w_toe,  _y_rest(z_toe)  + h_sole, z_toe),
        ]
        mb.loft([s_bot, s_top], SOLE, cap_bottom=False, cap_top=False)

        # Chunky off-white sneaker upper tucking smoothly into trouser cuff (4 side quads = 8 tris)
        u_top = [
            V(cx - w_heel * 0.84, _y_rest(z_heel) + h_col, z_heel + 0.012),
            V(cx + w_heel * 0.84, _y_rest(z_heel) + h_col, z_heel + 0.012),
            V(cx + w_heel * 0.82, _y_rest(z_mid)  + h_col, z_mid),
            V(cx - w_heel * 0.82, _y_rest(z_mid)  + h_col, z_mid),
        ]
        mb.loft([s_top, u_top], lambda i, k: SHOE_SHADE if k == 2 else SHOE,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 11. WHEELCHAIR CHASSIS: SEAT, BACKREST, PUSH HANDLES, FORKS, RAILS, FOOTREST (66 tris)
    # =========================================================================
    mb.set_part("chair_frame", bone="Root")

    # 11a. Seat base / cushion frame (skip top under thighs & back into backrest = 8 tris)
    mb.box(-0.210, 0.210, 0.398, 0.460, -0.215, 0.258,
           {"front": CHAIR_FRAME, "left": CHAIR_SEAT, "right": CHAIR_SEAT, "bottom": CHAIR_FRAME_DARK},
           skip=("top", "back"))

    # 11b. Slightly reclined dark charcoal backrest (skip bottom into seat = 10 tris)
    bx = 0.204
    b_bot = [
        V(-bx, 0.440, -0.168),
        V( bx, 0.440, -0.168),
        V( bx, 0.440, -0.228),
        V(-bx, 0.440, -0.228),
    ]
    b_top = [
        V(-bx, 0.838, -0.220),
        V( bx, 0.838, -0.220),
        V( bx, 0.838, -0.280),
        V(-bx, 0.838, -0.280),
    ]
    mb.loft([b_bot, b_top], lambda i, k: CHAIR_SEAT if k == 0 else CHAIR_FRAME,
            cap_bottom=False, cap_top=True, top_color=CHAIR_FRAME)

    # 11c. 2 Chunky backward-extending push handles at top of backrest (3-sided + cap = 7 tris x 2 = 14 tris)
    for side in (-1, 1):
        hx = side * 0.194
        mb.tube(
            [V(hx, 0.816, -0.244), V(hx, 0.822, -0.376)],
            radii=0.036, n=3, color=CHAIR_HANDLE,
            cap_start=False, cap_end=True, hint=V(0.0, 1.0, 0.0), phase=math.pi / 6.0
        )

    # 11d. 2 Front vertical caster struts/forks & 2 lower side frame rails (3-sided = 24 tris)
    for side in (-1, 1):
        fx = side * FRONT_WX
        # Front vertical strut from front seat down to caster axle (6 tris)
        mb.tube(
            [V(fx, 0.422, FRONT_WZ - 0.012), V(fx, R_CASTER, FRONT_WZ)],
            radii=0.022, n=3, color=CHAIR_FRAME,
            cap_start=False, cap_end=False, hint=V(1.0, 0.0, 0.0)
        )
        # Lower side rail linking rear wheel axle mount cleanly forward to caster strut (6 tris)
        mb.tube(
            [V(side * (REAR_WX - 0.024), R_MAIN, REAR_WZ), V(fx, R_CASTER + 0.042, FRONT_WZ)],
            radii=0.021, n=3, color=CHAIR_FRAME_DARK,
            cap_start=False, cap_end=False, hint=V(0.0, 1.0, 0.0)
        )

    # 11e. Angled dark charcoal footrest platform under both sneakers (skip rear edge into forks = 10 tris)
    fx0, fx1 = -0.192, 0.192
    fz0, fz1 = FRONT_WZ - 0.008, 0.514
    t_plate = 0.036
    fp_bot = [
        V(fx0, _y_rest(fz0) - t_plate, fz0),
        V(fx1, _y_rest(fz0) - t_plate, fz0),
        V(fx1, _y_rest(fz1) - t_plate, fz1),
        V(fx0, _y_rest(fz1) - t_plate, fz1),
    ]
    fp_top = [
        V(fx0, _y_rest(fz0), fz0),
        V(fx1, _y_rest(fz0), fz0),
        V(fx1, _y_rest(fz1), fz1),
        V(fx0, _y_rest(fz1), fz1),
    ]
    # Loft 3 exposed edges (left, front, right; skip k=0 back) + top + bottom = 5 quads = 10 tris
    mb.loft([fp_bot, fp_top], CHAIR_FRAME_DARK, cap_bottom=True, cap_top=True,
            bot_color=CHAIR_FRAME_DARK, top_color=CHAIR_FRAME, skip_k=(0,))

    # =========================================================================
    # 12. 2 LARGE 8-SIDED HOLLOW SPOKED REAR WHEELS (Wheel_Rear bone = 124 tris)
    # =========================================================================
    mb.set_part("rear_wheels", bone="Wheel_Rear")
    add_big_wheel(mb,  REAR_WX, R_MAIN, REAR_WZ, R_MAIN,  1, n=8)
    add_big_wheel(mb, -REAR_WX, R_MAIN, REAR_WZ, R_MAIN, -1, n=8)

    # =========================================================================
    # 13. 2 SMALL 6-SIDED FRONT CASTER WHEELS (Wheel_Front bone = 40 tris)
    # =========================================================================
    mb.set_part("front_casters", bone="Wheel_Front")
    add_caster_wheel(mb,  FRONT_WX, R_CASTER, FRONT_WZ, R_CASTER, 0.020,  1, n=6)
    add_caster_wheel(mb, -FRONT_WX, R_CASTER, FRONT_WZ, R_CASTER, 0.020, -1, n=6)

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
    """24-frame looping Walk cycle: rhythmic manual wheelchair propulsion!
    Both arms reach back to grab the push-rims, drive smoothly forward & down along
    the wheel arc with a subtle forward torso lean, then lift & return for the next stroke,
    while rear wheels roll 1 full revolution (2*pi) and 1/3-size front casters roll 3 full revolutions (6*pi).
    """
    action = bpy.data.actions.new(name="Walk")
    rig.animation_data.action = action
    _reset_pose(rig)

    cycle_len = 24
    # Keyframe every frame (1..25) so fast-spinning front casters (45 deg/frame) interpolate smoothly in glTF!
    for frame in range(1, cycle_len + 2):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        c1 = math.cos(phi)
        # Smooth push-stroke envelope: forward drive during phi in [0, pi], recovery return in [pi, 2*pi]
        # push_pos peaks forward at phi = pi/2, reaches back at phi = 3*pi/2
        push_fwd = -c1                      # -1 (back grab) -> +1 (forward finish) -> -1
        lift = max(0.0, -s1)                # 0 during forward power stroke, lifts smoothly on return arc!

        # Root stays rock-steady on ground y = 0 with a tiny suspension micro-pitch on push
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, 0.0, 0.0)
        pb_root.rotation_euler = (0.0, 0.0, 0.0)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Torso leans forward (+rx) slightly into each wheelchair push stroke
        torso_pitch = 0.055 + 0.075 * push_fwd
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (torso_pitch, 0.0, 0.0)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Head counter-pitches (-rx) to keep eyes comfortably level and looking ahead
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-torso_pitch * 0.80 + 0.022 * s1, 0.020 * s1, 0.0)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Symmetric manual wheelchair push stroke right along the light-grey push-rims!
        # Outward flare (+rz on Arm_L, -rz on Arm_R) places both hands cleanly over x = +-0.268
        # so they grip the top-rear rim, push forward-down along the rim arc, then lift & return!
        arm_pitch = 0.10 - 0.36 * push_fwd                 # +0.46 (back rim grab) -> -0.26 (forward rim drive)
        arm_flare = 0.30 + 0.06 * lift                     # aligns hand right over the outer push-rim!
        fore_pitch = -0.04 + 0.34 * push_fwd - 0.26 * lift  # reaches back-up on grab, drives down-fwd on push!

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_pitch, 0.0, arm_flare)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (fore_pitch, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (arm_pitch, 0.0, -arm_flare)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (fore_pitch, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Rear wheels roll forward 1 full revolution (2*pi); 1/3-size front casters roll 3 full revolutions (6*pi)
        pb_wr = rig.pose.bones["Wheel_Rear"]
        pb_wr.rotation_euler = (phi, 0.0, 0.0)
        pb_wr.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_wf = rig.pose.bones["Wheel_Front"]
        pb_wf.rotation_euler = (3.0 * phi, 0.0, 0.0)
        pb_wf.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: calm seated harbor wait, gentle breathing,
    friendly look-around, and subtle relaxed hand rest."""
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

        # Wheelchair parked steadily on ground
        for bname in ("Root", "Wheel_Rear", "Wheel_Front"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle relaxed breathing & subtle posture shift
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.022 * s2, 0.028 * s1, -0.012 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious, friendly harbor look-around
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.028 * s2, 0.22 * s1, 0.026 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Hands rest comfortably with gentle breathing drift
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.024 * s2, 0.0, 0.016 + 0.012 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.022 * s2, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.024 * s2, 0.0, -0.016 + 0.012 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.022 * s2, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build 9-bone wheelchair passenger rig (standard passenger Torso/Head/Arms + Forearms + Rolling Wheels)."""
    arm_data = bpy.data.armatures.new("PersonWheelchairRig")
    rig = bpy.data.objects.new("PersonWheelchairRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",        None,    ( 0.000,       0.450,      0.000),      ( 0.000,       0.570,      0.000)),
        ("Wheel_Rear",  "Root",  ( 0.000,       R_MAIN,     REAR_WZ),    ( 0.000,       R_MAIN + 0.14, REAR_WZ)),
        ("Wheel_Front", "Root",  ( 0.000,       R_CASTER,   FRONT_WZ),   ( 0.000,       R_CASTER + 0.10, FRONT_WZ)),
        ("Torso",       "Root",  ( 0.000,       0.556,     -0.045),      ( 0.000,       0.928,     -0.045)),
        ("Head",        "Torso", ( 0.000,       0.968,     -0.018),      ( 0.000,       1.268,     -0.018)),
        ("Arm_L",       "Torso", ( SHOULDER_X,  SHOULDER_Y, SHOULDER_Z), ( SHOULDER_X,  SHOULDER_Y + 0.14, SHOULDER_Z)),
        ("Forearm_L",   "Arm_L", ( ELBOW_X,     ELBOW_Y,    ELBOW_Z),    ( ELBOW_X,     ELBOW_Y + 0.12,    ELBOW_Z)),
        ("Arm_R",       "Torso", (-SHOULDER_X,  SHOULDER_Y, SHOULDER_Z), (-SHOULDER_X,  SHOULDER_Y + 0.14, SHOULDER_Z)),
        ("Forearm_R",   "Arm_R", (-ELBOW_X,     ELBOW_Y,    ELBOW_Z),    (-ELBOW_X,     ELBOW_Y + 0.12,    ELBOW_Z)),
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
    fill_data.energy = 0.90
    fill_data.color = (0.89, 0.93, 1.0)
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
        (-1.86, math.radians(60)),   # Front-3/4 matching reference angle (facing right)
        (-0.62, math.radians(0)),    # Front
        ( 0.62, math.radians(90)),   # Side (showing full wheelchair profile)
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
    cam_obj.location = (0.0, -5.0, 0.96)
    direction = Vector((0.0, 0.0, 0.72)) - cam_obj.location
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
    fill_data.energy = 0.90
    fill_data.color = (0.89, 0.93, 1.0)
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
    cam_obj.location = (0.0, -6.0, 0.98)
    direction = Vector((0.0, 0.0, 0.72)) - cam_obj.location
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
    fill_data.energy = 0.90
    fill_data.color = (0.89, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.001))
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
    cam_obj.location = (0.0, -5.0, 0.96)
    direction = Vector((0.0, 0.0, 0.72)) - cam_obj.location
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

    coll = bpy.data.collections.new("PersonWheelchair")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonWheelchair")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonWheelchair", me)
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
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=48)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=60, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)

    print("=== PersonWheelchair Stats ===")
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
