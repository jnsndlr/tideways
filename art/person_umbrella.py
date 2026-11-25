# Builds an ultra-low-poly (< 350 tris) stylized lady with boots, scarf, satchel, and umbrella in Blender
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_umbrella.py)
# Saves art/person_umbrella.blend, exports assets/models/person_umbrella.glb (rigged + Walk & Idle cycles),
# renders art/person_umbrella_preview.png, art/person_umbrella_walk_preview.png, art/person_umbrella_idle_preview.png,
# and outputs rendered videos art/person_umbrella_walk.mp4 and art/person_umbrella_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.67 m person height (~2.12 m with umbrella).
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
BLEND_PATH = os.path.join(ROOT, "art", "person_umbrella.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_umbrella.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_umbrella_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_umbrella_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_umbrella_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_umbrella_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_umbrella_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference image (sRGB -> linear)
SKIN          = col_srgb(0.97, 0.73, 0.49)
SKIN_SHADE    = col_srgb(0.87, 0.61, 0.38)
EYE           = col_srgb(0.13, 0.11, 0.10)

HAIR          = col_srgb(0.39, 0.30, 0.26)
HAIR_HI       = col_srgb(0.45, 0.35, 0.30)
HAIR_SHADE    = col_srgb(0.29, 0.22, 0.19)

SCARF         = col_srgb(0.50, 0.34, 0.45)
SCARF_LIGHT   = col_srgb(0.57, 0.40, 0.52)
SCARF_DARK    = col_srgb(0.39, 0.26, 0.36)

COAT          = col_srgb(0.88, 0.79, 0.65)
COAT_SHADE    = col_srgb(0.79, 0.70, 0.56)
COAT_INNER    = col_srgb(0.64, 0.55, 0.43)
BUTTON        = col_srgb(0.44, 0.34, 0.25)

BOOT_SHAFT    = col_srgb(0.46, 0.31, 0.21)
BOOT_FOOT     = col_srgb(0.55, 0.39, 0.26)
BOOT_SOLE     = col_srgb(0.27, 0.19, 0.14)

BAG           = col_srgb(0.58, 0.41, 0.29)
BAG_FLAP      = col_srgb(0.64, 0.46, 0.33)
BAG_DARK      = col_srgb(0.41, 0.28, 0.20)
BAG_BUCKLE    = col_srgb(0.73, 0.54, 0.38)
STRAP         = col_srgb(0.36, 0.25, 0.19)

UMB_TOP       = col_srgb(0.37, 0.44, 0.56)
UMB_ALT       = col_srgb(0.33, 0.40, 0.52)
UMB_UNDER     = col_srgb(0.22, 0.28, 0.39)
UMB_TIP       = col_srgb(0.26, 0.31, 0.40)
UMB_SHAFT     = col_srgb(0.70, 0.72, 0.75)
UMB_HANDLE    = col_srgb(0.18, 0.19, 0.21)


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Key shared grip/anchor coordinates so Arm_R, Hand, and Umbrella align identically
GRIP_PT = V(-0.256, 0.880, 0.212)
HUB_PT  = V(-0.168, 1.800, -0.088)
UMB_AX  = (HUB_PT - GRIP_PT).normalized()


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
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=([wb] * 3) if wb else None)
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
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=([wt] * 3) if wt else None)

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


def ortho_basis(axis, hint=V(1.0, 0.0, 0.0)):
    ax = axis.normalized()
    u = hint - ax * hint.dot(ax)
    if u.length < 1e-5:
        hint = V(0.0, 0.0, 1.0)
        u = hint - ax * hint.dot(ax)
    u = u.normalized()
    v = ax.cross(u).normalized()
    return ax, u, v


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + SLEEK PARTED SHOULDER-LENGTH BOB HAIR (~60 tris)
    # =========================================================================
    mb.set_part("head_and_bob", bone="Head")
    # 6-sided head (phase = pi/6):
    #   k=5 -> 0: flat front face (+Z)
    #   k=0 -> 1: left cheek (+X)
    #   k=4 -> 5: right cheek (-X)
    #   k=1,2,3:  back/sides enclosed inside flared bob shell
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.212,  0.016, 0.148, 0.144),  # 0: chin / jaw
        (1.300,  0.020, 0.206, 0.196),  # 1: lower cheek
        (1.488,  0.015, 0.210, 0.200),  # 2: brow / temple
        (1.648, -0.012, 0.132, 0.140),  # 3: softer rounded crown dome
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # Front + cheeks of head (skip k=1,2,3 on i=0,1,2 since flared bob shell forms the seamless back/sides)
    for i in range(3):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6.0
        c1 = sum(r1, Vector()) / 6.0
        cmid = (c0 + c1) * 0.5
        for k in (4, 5, 0):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            out_dir = mid - cmid
            if i == 2 and k == 5:
                # Soft off-center parted forehead bangs framing face (4 tris)
                p_part = p2.lerp(p3, 0.36)
                p_part = V(p_part.x, p0.y + (p2.y - p0.y) * 0.42, p0.z * 0.62 + p2.z * 0.38)
                mb.face([p0, p1, p_part], SKIN, out=(0, 0, 1))
                mb.face([p0, p_part, p3], HAIR, out=(0, 0, 1))
                mb.face([p1, p2, p_part], HAIR, out=(0, 0, 1))
                mb.face([p_part, p2, p3], HAIR_HI, out=(0, 0.35, 1))
            elif i == 2 and k == 4:
                # Right temple sweeping bangs angled diagonally back over ear (2 tris)
                mb.face([p0, p1, p2], HAIR, out=out_dir)
                mb.face([p0, p2, p3], HAIR, out=out_dir)
            elif i == 2 and k == 0:
                # Left temple sweeping bangs angled diagonally back over ear (2 tris)
                mb.face([p0, p1, p3], HAIR, out=out_dir)
                mb.face([p1, p2, p3], HAIR, out=out_dir)
            elif i == 1 and k == 4:
                # Right cheek with diagonal dark hair strand sweeping back behind ear (3 tris)
                pt = p0.lerp(p3, 0.38)
                mb.face([p0, p1, p2, pt], SKIN, out=out_dir)
                mb.face([pt, p2, p3], HAIR, out=out_dir)
            elif i == 1 and k == 0:
                # Left cheek with diagonal dark hair strand sweeping back behind ear (3 tris)
                pt = p1.lerp(p2, 0.38)
                mb.face([p0, p1, pt, p3], SKIN, out=out_dir)
                mb.face([pt, p2, p3], HAIR, out=out_dir)
            else:
                mb.face([p0, p1, p2, p3], SKIN, out=out_dir)

    # Head crown top cap & chin bottom cap (4 + 4 = 8 tris)
    rt = head_rings[3]
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR_HI, out=(0, 1, 0))
    mb.face([rt[3], rt[4], rt[5], rt[0]], HAIR_HI, out=(0, 1, 0))
    rb = head_rings[0]
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[3], rb[4], rb[5], rb[0]], SKIN_SHADE, out=(0, -1, 0))

    # Sculpted Flared Bob Shell wrapping seamlessly from crown (r3[1..4]) down to blunt collar-level hem!
    # Top edge matches head crown vertices exactly (zero seam!), mid curves roundly, bottom flares out!
    bob_top = [
        rt[1],
        rt[2],
        rt[2].lerp(rt[3], 0.5) + V(0.0, 0.0, -0.018),
        rt[3],
        rt[4],
    ]
    bob_angles = [math.radians(a) for a in (90.0, 138.0, 180.0, 222.0, 270.0)]

    def bob_arc(y, cz, rx, rz, back_extra=0.0):
        pts = []
        for a in bob_angles:
            sx = math.sin(a)
            ca = math.cos(a)
            dz = rz * ca - back_extra * max(0.0, -ca) ** 1.5
            pts.append(V(rx * sx, y, cz + dz))
        return pts

    bob_mid = bob_arc(1.485, -0.002, 0.236, 0.246, back_extra=0.025)
    bob_bot = bob_arc(1.168, -0.018, 0.256, 0.278, back_extra=0.052)
    bob_in  = bob_arc(1.175, -0.005, 0.145, 0.135, back_extra=0.000)

    # Outer flared bob walls: 4 segs x 2 bands = 16 tris
    bob_rings = [bob_top, bob_mid, bob_bot]
    for i in range(2):
        r0, r1 = bob_rings[i], bob_rings[i + 1]
        c_ref = V(0.0, 0.5 * (r0[2].y + r1[2].y), 0.02)
        for k in range(4):
            p0, p1, p2, p3 = r0[k], r0[k + 1], r1[k + 1], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            col = HAIR if (i == 0 or k in (1, 2)) else HAIR_HI
            mb.face([p0, p1, p2, p3], col, out=(mid - c_ref))

    # Front-facing bob side returns closing cleanly behind the ears (left k=0 & right k=4, 2 bands each = 8 tris)
    l_in = [head_rings[3][1], head_rings[2][1], head_rings[1][1], head_rings[0][1]]
    r_in = [head_rings[3][4], head_rings[2][4], head_rings[1][4], head_rings[0][4]]
    # Left side return (+X facing forward +Z)
    mb.face([bob_top[0], bob_mid[0], l_in[2], l_in[1]], HAIR_SHADE, out=(0.2, 0.0, 1.0))
    mb.face([bob_mid[0], bob_bot[0], bob_in[0], l_in[2]], HAIR_SHADE, out=(0.2, 0.0, 1.0))
    # Right side return (-X facing forward +Z)
    mb.face([bob_top[4], l_in[1] * 0 + r_in[1], r_in[2], bob_mid[4]], HAIR_SHADE, out=(-0.2, 0.0, 1.0))
    mb.face([bob_mid[4], r_in[2], bob_in[4], bob_bot[4]], HAIR_SHADE, out=(-0.2, 0.0, 1.0))

    # Crisp blunt underside rim of bob hair (4 quads = 8 tris)
    for k in range(4):
        mb.face([bob_bot[k], bob_bot[k + 1], bob_in[k + 1], bob_in[k]], HAIR_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. CUTE PEEKING EARS (2 x 4 = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.196
        x_out = side * 0.236
        y0, y1 = 1.305, 1.388
        z0, z1 = 0.008, 0.068
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_tip], SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 3. VERTICAL PILL EYES (2 x 4 = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.194
    for side in (-1, 1):
        cx = side * 0.063
        cy = 1.385
        rx = 0.018
        ry = 0.047
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
    # 4. INNER NECK CORE (hidden inside scarf, prevents gap on head tilt = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.070, 1.120, -0.045), V(0.000, 1.120, 0.072), V(0.070, 1.120, -0.045)]
    n_t = [V(-0.066, 1.225, -0.042), V(0.000, 1.225, 0.068), V(0.066, 1.225, -0.042)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 5. COZY PLUM SCARF WRAP + HANGING FRONT END (24 + 8 = 32 tris)
    # =========================================================================
    mb.set_part("scarf_wrap", bone="Torso")
    n_sc = 6
    sc_specs = [
        # (y_base, y_tilt_fwd, cz,    rx,    rz)
        (1.062, -0.024, 0.006, 0.214, 0.186),  # 0: lower cozy fold on coat shoulders
        (1.132, -0.022, 0.012, 0.236, 0.208),  # 1: full chunky wrap belly
        (1.202, -0.008, 0.010, 0.174, 0.162),  # 2: tucked snugly under chin & bob
    ]
    sc_rings = []
    for (yb, yt, cz, rx, rz) in sc_specs:
        ring = []
        for k in range(n_sc):
            a = math.pi / n_sc + 2.0 * math.pi * k / n_sc
            ca, sa = math.cos(a), math.sin(a)
            bump = 1.0 + 0.035 * math.sin(2.0 * a + 0.5)
            ring.append(V(rx * sa * bump, yb + yt * ca + 0.008 * math.sin(a), cz + rz * ca * bump))
        sc_rings.append(ring)

    def scarf_col(i, k):
        if i == 0:
            return SCARF_DARK if k in (1, 2, 3) else SCARF
        return SCARF_LIGHT if k in (4, 5, 0) else SCARF

    mb.loft(sc_rings, scarf_col, cap_bottom=False, cap_top=False)

    # Hanging front scarf tail draping down chest right next to umbrella hand (8 tris, weighted to Scarf)
    mb.set_part("scarf_tail", bone="Scarf")
    # 4-sided tapered hanging cloth slab (skip top tucked into wrap & back flush against coat)
    st_top = [
        V(-0.048, 1.118, 0.172),  # front-right
        V( 0.088, 1.118, 0.172),  # front-left
        V( 0.084, 1.118, 0.120),  # back-left
        V(-0.044, 1.118, 0.120),  # back-right
    ]
    st_bot = [
        V(-0.056, 0.775, 0.194),
        V( 0.098, 0.775, 0.194),
        V( 0.094, 0.775, 0.146),
        V(-0.052, 0.775, 0.146),
    ]
    # Front, left side, right side, bottom cap (skip k=2 back face)
    mb.loft([st_bot, st_top], lambda i, k: SCARF_LIGHT if k == 0 else SCARF_DARK,
            cap_bottom=True, cap_top=False, bot_color=SCARF_DARK, skip_k=(2,))

    # =========================================================================
    # 6. BEIGE A-LINE TRENCH COAT + SINGLE BROWN BUTTON (32 + 4 = 36 tris)
    # =========================================================================
    mb.set_part("trench_coat")
    # Smooth 6-sided A-line trench coat flaring generously from shoulders to hem (y=0.408)
    # Wide front/back flare ensures tall boots stride cleanly with zero hem clipping!
    coat_specs = [
        # (y,     cz,     rx,    rz,    weights)
        (0.408,  0.000, 0.282, 0.236, {"Root": 0.85, "Torso": 0.15}),  # 0: wide flared A-line hem
        (0.735,  0.004, 0.230, 0.168, {"Root": 0.30, "Torso": 0.70}),  # 1: waist/hip
        (1.118,  0.006, 0.194, 0.130, {"Torso": 1.0}),                 # 2: shoulders
    ]
    coat_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz, _) in coat_specs]
    coat_weights = [w for (_, _, _, _, w) in coat_specs]

    def coat_col(i, k):
        return COAT if k in (4, 5, 0) else COAT_SHADE

    mb.loft(coat_rings, coat_col, cap_bottom=True, cap_top=True,
            bot_color=COAT_INNER, top_color=COAT_SHADE, ring_weights=coat_weights)

    # Single cute round-hex dark brown coat button on front center just below scarf tail (4 tris)
    mb.set_part("coat_button", bone={"Root": 0.45, "Torso": 0.55})
    by = 0.665
    t_b = (by - 0.408) / (0.735 - 0.408)
    # On 6-sided phase=pi/6, flat front face Z is cz + rz * cos(30 deg)
    rz_b = 0.236 + (0.168 - 0.236) * t_b
    cz_b = 0.000 + 0.004 * t_b
    bz = cz_b + rz_b * math.cos(math.pi / 6.0) + 0.006
    bx = 0.015
    br = 0.023
    b_pts = [V(bx + br * math.cos(math.pi / 6.0 + 2.0 * math.pi * k / 6.0),
               by + br * math.sin(math.pi / 6.0 + 2.0 * math.pi * k / 6.0), bz)
             for k in range(6)]
    mb.face([b_pts[0], b_pts[1], b_pts[2], b_pts[3]], BUTTON, out=(0, 0, 1))
    mb.face([b_pts[3], b_pts[4], b_pts[5], b_pts[0]], BUTTON, out=(0, 0, 1))

    # =========================================================================
    # 7. ASYMMETRIC COAT SLEEVES + CHUNKY PEACH HANDS (32 + 20 = 52 tris)
    # =========================================================================
    mb.set_part("sleeves")

    def build_sleeve(p_sh, p_el, p_wr, bone_name, r_sh=(0.072, 0.078), r_el=(0.082, 0.086), r_wr=(0.076, 0.080)):
        mb.set_bone(bone_name)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        axm = (ax1 + ax2).normalized()

        def ring4(ctr, axis, rx, rperp):
            _, u, v = ortho_basis(axis, hint=V(1.0, 0.0, 0.0))
            return [
                ctr - u * rx + v * rperp,
                ctr + u * rx + v * rperp,
                ctr + u * rx - v * rperp,
                ctr - u * rx - v * rperp,
            ]

        r0 = ring4(p_sh, ax1, r_sh[0], r_sh[1])
        r1 = ring4(p_el, axm, r_el[0], r_el[1])
        r2 = ring4(p_wr, ax2, r_wr[0], r_wr[1])
        mb.loft([r0, r1, r2], lambda i, k: COAT_SHADE if k == 2 else COAT,
                cap_bottom=False, cap_top=False)

    # Left arm (Arm_L, +X): relaxed slightly angled coat sleeve swinging freely beside flared skirt
    p_l_sh = V( 0.165, 1.052,  0.006)
    p_l_el = V( 0.264, 0.835, -0.008)
    p_l_wr = V( 0.304, 0.648,  0.038)
    build_sleeve(p_l_sh, p_l_el, p_l_wr, "Arm_L")

    # Right arm (Arm_R, -X): bent at elbow, raising hand forward to grip umbrella handle!
    p_r_sh = V(-0.165, 1.052,  0.006)
    p_r_el = V(-0.288, 0.842, -0.045)
    p_r_wr = V(-0.260, 0.870,  0.158)
    build_sleeve(p_r_sh, p_r_el, p_r_wr, "Arm_R")

    # Hands (10 tris each = 20 tris)
    mb.set_part("hands")
    # Left hand extending cleanly out of left sleeve cuff
    mb.set_bone("Arm_L")
    ax_lh = (p_l_wr - p_l_el).normalized()
    _, ul, vl = ortho_basis(ax_lh, hint=V(1.0, 0.0, 0.0))
    c0_l = p_l_wr - ax_lh * 0.012
    c1_l = p_l_wr + ax_lh * 0.100
    hl_r0 = [c0_l - ul * 0.050 + vl * 0.052, c0_l + ul * 0.050 + vl * 0.052,
             c0_l + ul * 0.050 - vl * 0.052, c0_l - ul * 0.050 - vl * 0.052]
    hl_r1 = [c1_l - ul * 0.040 + vl * 0.042, c1_l + ul * 0.040 + vl * 0.042,
             c1_l + ul * 0.040 - vl * 0.042, c1_l - ul * 0.040 - vl * 0.042]
    mb.loft([hl_r0, hl_r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # Right fist gripping umbrella handle centered on GRIP_PT
    mb.set_bone("Arm_R")
    ax_rh = (GRIP_PT - p_r_wr).normalized()
    _, ur, vr = ortho_basis(ax_rh, hint=V(1.0, 0.0, 0.0))
    c0_r = p_r_wr - ax_rh * 0.014
    c1_r = GRIP_PT + ax_rh * 0.050
    hr_r0 = [c0_r - ur * 0.052 + vr * 0.054, c0_r + ur * 0.052 + vr * 0.054,
             c0_r + ur * 0.052 - vr * 0.054, c0_r - ur * 0.052 - vr * 0.054]
    hr_r1 = [c1_r - ur * 0.048 + vr * 0.050, c1_r + ur * 0.048 + vr * 0.050,
             c1_r + ur * 0.048 - vr * 0.050, c1_r - ur * 0.048 - vr * 0.050]
    mb.loft([hr_r0, hr_r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN)

    # =========================================================================
    # 8. TALL CHESTNUT-BROWN BOOTS WITH DARK OUTSOLES (26 tris x 2 = 52 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx_t = side * 0.114
        cx_b = side * 0.128

        # Tall sleek boot shaft rising cleanly inside flared coat hem (y=0.105 to y=0.535 = 8 tris)
        r_shaft_bot = [
            V(cx_b - 0.054, 0.105,  0.058),
            V(cx_b + 0.054, 0.105,  0.058),
            V(cx_b + 0.054, 0.105, -0.066),
            V(cx_b - 0.054, 0.105, -0.066),
        ]
        r_shaft_top = [
            V(cx_t - 0.062, 0.535,  0.062),
            V(cx_t + 0.062, 0.535,  0.062),
            V(cx_t + 0.062, 0.535, -0.062),
            V(cx_t - 0.062, 0.535, -0.062),
        ]
        mb.loft([r_shaft_bot, r_shaft_top], BOOT_SHAFT, cap_bottom=False, cap_top=False)

        # Boot foot: dark outsole layer (10 tris) + warm chestnut leather vamp (8 tris)
        w = 0.062
        w_toe = 0.052
        z_heel = -0.086
        z_toe  =  0.162
        y_sole0 = 0.000
        y_sole1 = 0.032

        sole_bot = [
            V(cx_b - w,     y_sole0, z_heel),
            V(cx_b + w,     y_sole0, z_heel),
            V(cx_b + w_toe, y_sole0, z_toe),
            V(cx_b - w_toe, y_sole0, z_toe),
        ]
        sole_top = [
            V(cx_b - w,     y_sole1, z_heel),
            V(cx_b + w,     y_sole1, z_heel),
            V(cx_b + w_toe, y_sole1, z_toe),
            V(cx_b - w_toe, y_sole1, z_toe),
        ]
        mb.loft([sole_bot, sole_top], BOOT_SOLE, cap_bottom=True, cap_top=False, bot_color=BOOT_SOLE)

        boot_ank = [
            V(cx_b - 0.054, 0.112, -0.066),
            V(cx_b + 0.054, 0.112, -0.066),
            V(cx_b + 0.054, 0.112,  0.058),
            V(cx_b - 0.054, 0.112,  0.058),
        ]
        mb.loft([sole_top, boot_ank], lambda i, k: BOOT_SHAFT if k == 0 else BOOT_FOOT,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 9. CROSSBODY BROWN LEATHER SATCHEL + FLAP + BUCKLE + STRAP (22 tris)
    # =========================================================================
    mb.set_part("satchel", bone="Satchel")
    # Rests snugly on right hip (-X) below right elbow, tilted subtly outward to match coat A-line
    bag_tilt = math.radians(10.0)  # tilts bottom outward (-X) matching coat flare
    ct_b, st_b = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_c = V(-0.292, 0.650, -0.022)

    def bpt(lx, ly, lz):
        # lx: outward (-X is outer side), ly: up, lz: forward (+Z)
        rx = lx * ct_b + ly * st_b
        ry = -lx * st_b + ly * ct_b
        return V(bag_c.x + rx, bag_c.y + ry, bag_c.z + lz)

    # Main satchel body (6 faces = 12 tris, slightly tapered narrower at top)
    bx_in, bx_out = 0.044, -0.048
    by_b, by_t = -0.105, 0.102
    bz_b, bz_f = -0.112, 0.112
    p000 = bpt(bx_out, by_b, bz_b); p100 = bpt(bx_in, by_b, bz_b)
    p101 = bpt(bx_in,  by_b, bz_f); p001 = bpt(bx_out, by_b, bz_f)
    p010 = bpt(bx_out + 0.008, by_t, bz_b * 0.94); p110 = bpt(bx_in, by_t, bz_b * 0.94)
    p111 = bpt(bx_in,  by_t, bz_f * 0.94); p011 = bpt(bx_out + 0.008, by_t, bz_f * 0.94)

    mb.face([p000, p001, p011, p010], BAG,      out=(-1, 0, 0))  # outer face
    mb.face([p101, p100, p110, p111], BAG_DARK, out=( 1, 0, 0))  # inner face
    mb.face([p001, p101, p111, p011], BAG,      out=( 0, 0, 1))  # front edge
    mb.face([p100, p000, p010, p110], BAG_DARK, out=( 0, 0,-1))  # back edge
    mb.face([p011, p111, p110, p010], BAG_FLAP, out=( 0, 1, 0))  # top lid
    mb.face([p000, p100, p101, p001], BAG_DARK, out=( 0,-1, 0))  # bottom

    # Overlapping outer messenger flap + bottom lip shadow (4 tris)
    fx_top = bx_out + 0.004
    fx_bot = bx_out - 0.015
    fy_bot = -0.015
    f_tb = bpt(fx_top, by_t, bz_b * 0.95)
    f_tf = bpt(fx_top, by_t, bz_f * 0.95)
    f_bf = bpt(fx_bot, fy_bot, bz_f * 0.96)
    f_bb = bpt(fx_bot, fy_bot, bz_b * 0.96)
    f_in_bf = bpt(bx_out, fy_bot, bz_f * 0.96)
    f_in_bb = bpt(bx_out, fy_bot, bz_b * 0.96)
    mb.face([f_bb, f_bf, f_tf, f_tb], BAG_FLAP, out=(-1, 0, 0))
    mb.face([f_in_bb, f_in_bf, f_bf, f_bb], BAG_DARK, out=(0, -1, 0))

    # Cute center leather buckle tab on flap bottom edge (2 tris)
    mb.face([
        bpt(fx_bot - 0.005, fy_bot - 0.022, -0.022),
        bpt(fx_bot - 0.005, fy_bot - 0.022,  0.022),
        bpt(fx_bot - 0.004, fy_bot + 0.028,  0.022),
        bpt(fx_bot - 0.004, fy_bot + 0.028, -0.022),
    ], BAG_BUCKLE, out=(-1, 0, 0))

    # Crossbody leather straps rising from satchel top corners up beneath right arm (4 tris)
    mb.set_bone({"Satchel": 0.5, "Torso": 0.5})
    # Front strap ascending toward front chest/armpit
    mb.face([
        bpt(bx_out + 0.018, by_t - 0.005, bz_f * 0.72),
        bpt(bx_in  - 0.008, by_t - 0.005, bz_f * 0.72),
        V(-0.205, 0.945, 0.145),
        V(-0.228, 0.945, 0.140),
    ], STRAP, out=(-0.5, 0.2, 0.85))
    # Back strap ascending toward rear shoulder
    mb.face([
        bpt(bx_in  - 0.008, by_t - 0.005, bz_b * 0.72),
        bpt(bx_out + 0.018, by_t - 0.005, bz_b * 0.72),
        V(-0.228, 0.960, -0.125),
        V(-0.205, 0.960, -0.130),
    ], STRAP, out=(-0.5, 0.2, -0.85))

    # =========================================================================
    # 10. SLATE-BLUE UMBRELLA (8-RIBBED DOME + TIP + SHAFT + HANDLE = 54 tris)
    # =========================================================================
    mb.set_part("umbrella", bone="Umbrella")
    ax_u, u_u, v_u = ortho_basis(UMB_AX, hint=V(1.0, 0.0, 0.0))

    def umb_ring(ctr, rad, n=8, phase=0.0):
        return [ctr + (u_u * math.cos(phase + 2.0 * math.pi * k / n) +
                       v_u * math.sin(phase + 2.0 * math.pi * k / n)) * rad
                for k in range(n)]

    # 10a. Black handle grip held in right fist (extending cleanly below & above hand = 10 tris)
    h_bot = GRIP_PT - ax_u * 0.095
    h_top = GRIP_PT + ax_u * 0.105
    mb.loft([umb_ring(h_bot, 0.024, n=4, phase=math.pi / 4.0),
             umb_ring(h_top, 0.021, n=4, phase=math.pi / 4.0)],
            UMB_HANDLE, cap_bottom=True, cap_top=False, bot_color=UMB_HANDLE)

    # 10b. Brushed silver-grey umbrella shaft from handle top up into canopy underside hub (8 tris)
    s_bot = h_top - ax_u * 0.005
    s_top = HUB_PT + ax_u * 0.065
    mb.loft([umb_ring(s_bot, 0.014, n=4, phase=math.pi / 4.0),
             umb_ring(s_top, 0.013, n=4, phase=math.pi / 4.0)],
            UMB_SHAFT, cap_bottom=False, cap_top=False)

    # 10c. 8-ribbed slate-blue domed canopy (top dome 8 + outer skirt 16 + underside fan 8 = 32 tris)
    # Fuller cozy dome cradling closely above her bob hair!
    p_apex  = HUB_PT + ax_u * 0.255
    p_uhub  = HUB_PT + ax_u * 0.060  # underside runner hub (strictly below outer dome!)
    mid_ctr = HUB_PT + ax_u * 0.155
    rim_ctr = HUB_PT - ax_u * 0.105
    r_mid = 0.440
    r_rim = 0.745
    ring_mid = umb_ring(mid_ctr, r_mid, n=8, phase=math.pi / 8.0)
    ring_rim = umb_ring(rim_ctr, r_rim, n=8, phase=math.pi / 8.0)

    for k in range(8):
        kn = (k + 1) % 8
        col_panel = UMB_TOP if k % 2 == 0 else UMB_ALT
        # Upper dome panel (1 tri)
        mb.face([p_apex, ring_mid[k], ring_mid[kn]], col_panel, out=ax_u)
        # Outer sloped skirt panel (2 tris)
        mid_sk = (ring_mid[k] + ring_mid[kn] + ring_rim[kn] + ring_rim[k]) * 0.25
        mb.face([ring_mid[k], ring_rim[k], ring_rim[kn], ring_mid[kn]],
                col_panel, out=(mid_sk - HUB_PT) + ax_u * 0.35)
        # Dark navy underside fan panel (1 tri, facing downward/inward)
        mb.face([p_uhub, ring_rim[kn], ring_rim[k]], UMB_UNDER, out=-ax_u)

    # 10d. Cute little top ferrule/tip stub at canopy apex (4-sided pyramid = 4 tris)
    fer_base = umb_ring(p_apex - ax_u * 0.008, 0.022, n=4, phase=math.pi / 4.0)
    p_ftip = p_apex + ax_u * 0.058
    for k in range(4):
        kn = (k + 1) % 4
        mid_f = (fer_base[k] + fer_base[kn] + p_ftip) / 3.0
        mb.face([fer_base[k], fer_base[kn], p_ftip], UMB_TIP, out=(mid_f - p_apex))

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
    """24-frame looping Walk cycle: poised rainy-day stroll with swinging left arm, steady umbrella & satchel sway."""
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

        # Graceful buoyant walk bounce & light forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.024 * (1.0 - c2) * 0.5
        root_pitch = -0.044
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.058 * s1, 0.032 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Natural gentle torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.018 * c2, 0.072 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Cheerful steady head gaze under the umbrella
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.038 + 0.028 * s2, -0.038 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating boot stride clearing flared coat hem cleanly
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.40 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.036, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.40 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.036, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Left arm swings freely in natural counter-phase to legs
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.34 * s1, 0.0, 0.040)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm holds umbrella steadily with gentle cushion against torso twist & step bounce
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.042 * math.sin(2.0 * phi - 0.35), -0.038 * s1, -0.018 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Secondary umbrella gentle bounce & sway pivoting right at grip (zero hand drift!)
        pb_umb = rig.pose.bones["Umbrella"]
        pb_umb.rotation_euler = (0.028 * math.sin(2.0 * phi - 0.65), 0.0, -0.026 * math.sin(phi - 0.45))
        pb_umb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crossbody satchel swings gently at hip with weighted phase lag
        pb_bag = rig.pose.bones["Satchel"]
        pb_bag.rotation_euler = (0.070 * math.sin(phi - 0.55), 0.0, 0.032 * c1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Front scarf tail flutters softly with step bounce
        pb_scarf = rig.pose.bones["Scarf"]
        pb_scarf.rotation_euler = (0.048 * math.sin(2.0 * phi - 0.70), 0.0, 0.030 * math.sin(phi - 0.40))
        pb_scarf.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: calm coastal rain wait, gentle umbrella tilt, curious look & scarf breeze."""
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

        # Calm weight shift & soft breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.010, 0.022 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.024 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle look around & slight peek toward sky/rain
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.058 * s2, 0.21 * s1, 0.042 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Boots planted steadily on dock
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm drifts softly with breathing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.042 * s1 - 0.016 * s2, 0.0, 0.025 + 0.016 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm & umbrella settle smoothly with subtle coastal breeze sway
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.024 * s2, -0.015 * s1, -0.016 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_umb = rig.pose.bones["Umbrella"]
        pb_umb.rotation_euler = (0.032 * s2, 0.0, 0.038 * math.sin(phi - 0.35))
        pb_umb.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_bag = rig.pose.bones["Satchel"]
        pb_bag.rotation_euler = (0.020 * s1, 0.0, 0.018 * s2)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_scarf = rig.pose.bones["Scarf"]
        pb_scarf.rotation_euler = (0.032 * s2, 0.0, 0.028 * math.sin(phi - 0.50))
        pb_scarf.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 10-bone rig (7 standard passenger bones + Umbrella, Satchel, Scarf) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonUmbrellaRig")
    rig = bpy.data.objects.new("PersonUmbrellaRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",     None,    ( 0.000, 0.600,  0.000), ( 0.000, 0.700,  0.000)),
        ("Torso",    "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.120,  0.000)),
        ("Head",     "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Arm_L",    "Torso", ( 0.165, 1.052,  0.006), ( 0.165, 1.212,  0.006)),
        ("Arm_R",    "Torso", (-0.165, 1.052,  0.006), (-0.165, 1.212,  0.006)),
        ("Umbrella", "Arm_R", tuple(GRIP_PT),          tuple(GRIP_PT + UMB_AX * 0.35)),
        ("Satchel",  "Torso", (-0.258, 0.760, -0.022), (-0.258, 0.920, -0.022)),
        ("Scarf",    "Torso", ( 0.020, 1.115,  0.155), ( 0.020, 1.265,  0.155)),
        ("Leg_L",    "Root",  ( 0.114, 0.535,  0.000), ( 0.114, 0.695,  0.000)),
        ("Leg_R",    "Root",  (-0.114, 0.535,  0.000), (-0.114, 0.695,  0.000)),
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

    bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-2.55, math.radians(60)),   # Front-3/4 matching reference angle (facing right)
        (-0.85, math.radians(0)),    # Front
        ( 0.85, math.radians(90)),   # Side (showing umbrella, satchel, bob hair, boots)
        ( 2.55, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 7.2
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.5, 1.38)
    direction = Vector((0.0, 0.0, 1.05)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1440
    scene.render.resolution_y = 600
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("StripFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0, 0, -0.001))
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.62
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 10.2
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -7.5, 1.38)
    direction = Vector((0.0, 0.0, 1.05)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1600
    scene.render.resolution_y = 480
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("VidFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 4.0
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.38)
    direction = Vector((0.0, 0.0, 1.05)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 840
    scene.render.resolution_y = 580
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
            left_obj.location = (-0.90, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.90, 0.0, 0.0)
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
    "hair": [HAIR, HAIR_HI, HAIR_SHADE],
    "top": [COAT, COAT_SHADE, COAT_INNER],
    "accent": [UMB_TOP, UMB_ALT, UMB_UNDER],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonUmbrella")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonUmbrella")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonUmbrella", me)
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
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=44)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=58, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=44, zrot_right_deg=90)

    print("=== PersonUmbrella Stats ===")
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
