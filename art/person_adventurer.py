# Builds an ultra-low-poly (< 400 tris) stylized adventurer with a wide-brim safari hat,
# chin strap, low ponytail, olive hooded outdoor jacket over a dark blue tee, dark charcoal backpack
# with shoulder straps, chest-hanging binoculars on a neck strap, khaki cargo pants with side pockets,
# and chunky brown hiking boots in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_adventurer.py)
# Saves art/person_adventurer.blend, exports assets/models/person_adventurer.glb (rigged + Walk & Idle cycles),
# renders art/person_adventurer_preview.png, art/person_adventurer_walk_preview.png, art/person_adventurer_idle_preview.png,
# and outputs rendered videos art/person_adventurer_walk.mp4 and art/person_adventurer_idle.mp4.
#
# Strict triangle budget: < 400 triangles.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_adventurer.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_adventurer.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_adventurer_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_adventurer_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_adventurer_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_adventurer_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_adventurer_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference adventurer artwork (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN           = col_srgb(0.97, 0.71, 0.48)
SKIN_SHADE     = col_srgb(0.84, 0.58, 0.37)
EYE            = col_srgb(0.11, 0.11, 0.13)

HAIR           = col_srgb(0.32, 0.23, 0.18)
HAIR_SHADE     = col_srgb(0.24, 0.17, 0.13)

HAT            = col_srgb(0.77, 0.71, 0.55)
HAT_SHADE      = col_srgb(0.71, 0.65, 0.49)
HAT_UNDER      = col_srgb(0.51, 0.46, 0.34)
CHIN_STRAP     = col_srgb(0.25, 0.22, 0.20)

SHIRT          = col_srgb(0.25, 0.40, 0.54)

JACKET         = col_srgb(0.45, 0.52, 0.35)
JACKET_SHADE   = col_srgb(0.35, 0.42, 0.27)
JACKET_COLLAR  = col_srgb(0.49, 0.56, 0.39)

PACK           = col_srgb(0.25, 0.25, 0.27)
PACK_SHADE     = col_srgb(0.18, 0.18, 0.20)
PACK_DETAIL    = col_srgb(0.48, 0.45, 0.41)

BINOC          = col_srgb(0.28, 0.28, 0.31)
BINOC_SHADE    = col_srgb(0.19, 0.19, 0.22)
BINOC_LENS     = col_srgb(0.12, 0.14, 0.18)
BINOC_STRAP    = col_srgb(0.21, 0.21, 0.23)

PANTS          = col_srgb(0.73, 0.64, 0.49)
PANTS_SHADE    = col_srgb(0.60, 0.52, 0.38)
PANTS_POCKET   = col_srgb(0.78, 0.69, 0.53)

BOOT           = col_srgb(0.55, 0.38, 0.24)
BOOT_SHADE     = col_srgb(0.43, 0.29, 0.18)
SOLE           = col_srgb(0.27, 0.20, 0.15)

# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_SHADE],
    "top": [JACKET, JACKET_SHADE, JACKET_COLLAR],
    "bottom": [PANTS, PANTS_SHADE, PANTS_POCKET],
    "accent": [HAT, HAT_SHADE, HAT_UNDER],
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
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir)
            elif n == 8:
                self.face([r0[7], r0[0], r0[1], r0[2]], col, out=out_dir)
                self.face([r0[7], r0[2], r0[3], r0[6]], col, out=out_dir)
                self.face([r0[6], r0[3], r0[4], r0[5]], col, out=out_dir)
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
            elif n == 8:
                self.face([rt[7], rt[0], rt[1], rt[2]], col, out=out_dir)
                self.face([rt[7], rt[2], rt[3], rt[6]], col, out=out_dir)
                self.face([rt[6], rt[3], rt[4], rt[5]], col, out=out_dir)
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


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=8, phase=math.pi / 8.0):
    """Ring tilted around X by tilt_rad (+tilt raises +Z front, lowers -Z back)."""
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
    # 1. HEAD + HAIR SIDEBURNS (6-sided stylized low-poly head, y = 1.19..1.50)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.190,  0.016, 0.150, 0.146),  # 0: chin/jaw
        (1.276,  0.020, 0.214, 0.200),  # 1: lower cheek
        (1.488,  0.008, 0.214, 0.202),  # 2: brow / tucked cleanly inside safari hat
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks, k=1,2,3 are back/sides
    def head_color(i, k):
        if i == 0:
            return HAIR if k in (1, 2, 3) else SKIN
        return SKIN if k in (4, 5, 0) else HAIR

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            # Diagonal temple hairline on cheeks (k=0 left, k=4 right) matching reference!
            if i == 1 and k == 0:
                p_t = p1.lerp(p2, 0.42)
                mb.face([p0, p1, p_t, p3], SKIN, out=(mid - cmid))
                mb.face([p_t, p2, p3], HAIR, out=(mid - cmid))
            elif i == 1 and k == 4:
                p_t = p0.lerp(p3, 0.42)
                mb.face([p0, p1, p2, p_t], SKIN, out=(mid - cmid))
                mb.face([p_t, p2, p3], HAIR, out=(mid - cmid))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    # Chin bottom cap (front underside only = 2 tris; back sits inside neck/collar)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. LOW PONYTAIL PEEKING OUT UNDER BACK OF HAT (4-sided tapered = 10 tris)
    # =========================================================================
    mb.set_part("hair_ponytail", bone="Head")
    pt_r0 = [
        V(-0.078, 1.340, -0.140),
        V( 0.078, 1.340, -0.140),
        V( 0.074, 1.250, -0.160),
        V(-0.074, 1.250, -0.160),
    ]
    pt_r1 = [
        V(-0.060, 1.228, -0.212),
        V( 0.060, 1.228, -0.212),
        V( 0.052, 1.168, -0.192),
        V(-0.052, 1.168, -0.192),
    ]
    mb.loft([pt_r0, pt_r1], lambda i, k: HAIR_SHADE if k == 2 else HAIR,
            cap_bottom=False, cap_top=True, top_color=HAIR_SHADE)

    # =========================================================================
    # 3. EARS (2 cute tucked low-poly wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.198
        x_out = side * 0.240
        y0, y1 = 1.298, 1.388
        z0, z1 = -0.018, 0.046
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.012, zm)
        p_ot = V(x_out, y1 - 0.012, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.200
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.376
        rx = 0.019
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
    # 5. NECK (4-sided short tapered cylinder, skip rear quad = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.100, 0.008, 0.072, 0.066, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.202, 0.012, 0.068, 0.062, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 6. WIDE-BRIM SAFARI HAT (8-sided tilted explorer dome + sloping brim = 70 tris)
    # =========================================================================
    mb.set_part("safari_hat", bone="Head")
    hat_tilt = math.radians(18.0)  # tilted gracefully back to show eyes & brow clearly!
    # Crown rings: cozy rounded pith/safari dome matching reference silhouette
    h_base = tilted_ring(0.0, 1.466, -0.016, 0.244, 0.252, hat_tilt, n=8)
    h_mid  = tilted_ring(0.0, 1.584, -0.052, 0.220, 0.226, hat_tilt, n=8)
    h_top  = tilted_ring(0.0, 1.662, -0.076, 0.128, 0.132, hat_tilt, n=8)

    # Outer wide sloping brim (drops gracefully down along tilted hat axis)
    h_brim_out = tilted_ring(0.0, 1.388, 0.008, 0.376, 0.392, hat_tilt, n=8)
    # Inner under-brim ring tucked snugly onto head/hair
    h_brim_in  = tilted_ring(0.0, 1.448, -0.010, 0.195, 0.198, hat_tilt, n=8)

    # Dome crown (2 bands * 8 * 2 = 32 tris + 6 tri top cap = 38 tris)
    mb.loft([h_base, h_mid, h_top],
            lambda i, k: HAT_SHADE if i == 0 else HAT,
            cap_bottom=False, cap_top=True, top_color=HAT)

    # Brim top surface (8 quads = 16 tris)
    for k in range(8):
        kn = (k + 1) % 8
        mb.face([h_brim_out[k], h_brim_out[kn], h_base[kn], h_base[k]], HAT, out=(0, 1, 0))

    # Brim underside (8 quads = 16 tris)
    for k in range(8):
        kn = (k + 1) % 8
        mb.face([h_brim_in[k], h_brim_in[kn], h_brim_out[kn], h_brim_out[k]], HAT_UNDER, out=(0, -1, 0))

    # =========================================================================
    # 7. CHIN STRAP (dark cord riding cleanly outside cheek plane to chin toggle = 10 tris)
    # =========================================================================
    mb.set_part("chin_strap", bone="Head")
    for side in (-1, 1):
        # Upper segment from inside hat near temple cleanly outside cheek facet (no clipping!)
        p_t0 = V(side * 0.208, 1.432,  0.040)
        p_t1 = V(side * 0.198, 1.422,  0.062)
        p_m0 = V(side * 0.184, 1.274,  0.098)
        p_m1 = V(side * 0.172, 1.264,  0.120)
        # Lower segment from jaw corner to under-chin toggle
        p_c0 = V(side * 0.016, 1.168,  0.118)
        p_c1 = V(side * 0.016, 1.150,  0.136)
        mb.face([p_m0, p_m1, p_t1, p_t0], CHIN_STRAP, out=(side * 0.86, -0.1, 0.5))
        mb.face([p_c0, p_c1, p_m1, p_m0], CHIN_STRAP, out=(side * 0.5, -0.3, 0.85))
    # Small toggle knot under chin (1 quad = 2 tris)
    mb.face([
        V(-0.022, 1.142, 0.140),
        V( 0.022, 1.142, 0.140),
        V( 0.022, 1.174, 0.126),
        V(-0.022, 1.174, 0.126),
    ], CHIN_STRAP, out=(0, 0, 1))

    # =========================================================================
    # 8. DARK BLUE INNER SHIRT (visible down open front of olive jacket = 4 tris)
    # =========================================================================
    mb.set_part("shirt", bone="Torso")
    sz_f = 0.106
    mb.face([V(-0.088, 0.652, sz_f), V(0.088, 0.652, sz_f),
             V(0.088, 1.135, sz_f),  V(-0.088, 1.135, sz_f)], SHIRT, out=(0, 0, 1))
    mb.face([V(-0.088, 1.135, sz_f), V(0.088, 1.135, sz_f),
             V(0.088, 1.135, -0.090), V(-0.088, 1.135, -0.090)], SHIRT, out=(0, 1, 0))

    # =========================================================================
    # 9. OLIVE GREEN OPEN OUTDOOR JACKET + FOLDED HOOD/COLLAR (20 + 12 = 32 tris)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    jy0, jy1 = 0.650, 1.136
    jx_b, jx_t = 0.214, 0.194
    jz_fb, jz_ft = 0.132, 0.122
    jz_bb, jz_bt = -0.124, -0.114
    j_open_b = 0.068
    j_open_t = 0.060

    # Back panel (2 tris)
    mb.face([V(jx_b, jy0, jz_bb), V(-jx_b, jy0, jz_bb),
             V(-jx_t, jy1, jz_bt), V(jx_t, jy1, jz_bt)], JACKET, out=(0, 0, -1))
    # Bottom hem underside (2 tris)
    mb.face([V(-jx_b, jy0, jz_bb), V(jx_b, jy0, jz_bb),
             V(jx_b, jy0, jz_fb),  V(-jx_b, jy0, jz_fb)], JACKET_SHADE, out=(0, -1, 0))

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

    # Chunky folded hood/collar roll hugging around the neck (4-segment U-shape = 16 tris)
    mb.set_part("jacket_collar", bone="Torso")
    c_bot = [
        V(-0.074, 1.126,  0.116),
        V(-0.180, 1.120, -0.035),
        V( 0.000, 1.116, -0.142),
        V( 0.180, 1.120, -0.035),
        V( 0.074, 1.126,  0.116),
    ]
    c_top = [
        V(-0.064, 1.192,  0.096),
        V(-0.164, 1.196, -0.035),
        V( 0.000, 1.196, -0.132),
        V( 0.164, 1.196, -0.035),
        V( 0.064, 1.192,  0.096),
    ]
    c_in = [
        V(-0.056, 1.145,  0.072),
        V(-0.098, 1.145, -0.025),
        V( 0.000, 1.145, -0.088),
        V( 0.098, 1.145, -0.025),
        V( 0.056, 1.145,  0.072),
    ]
    for k in range(4):
        p0, p1, p2, p3 = c_bot[k], c_bot[k + 1], c_top[k + 1], c_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], JACKET_COLLAR, out=V(mid.x, 0.1, mid.z))
        mb.face([c_top[k], c_top[k + 1], c_in[k + 1], c_in[k]], JACKET_SHADE, out=(0, 1, 0))

    # =========================================================================
    # 10. SLEEVES (2 x chunky 4-sided slightly-bent outdoor sleeves = 32 tris)
    # =========================================================================
    mb.set_part("sleeves")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        p_sh = V(side * 0.162, 1.080,  0.002)
        p_el = V(side * 0.306, 0.878, -0.016)
        p_wr = V(side * 0.340, 0.708,  0.044)

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

        r_sh = s_ring(p_sh, ax1, 0.072, 0.080)
        r_el = s_ring(p_el, axm, 0.088, 0.092)
        r_wr = s_ring(p_wr, ax2, 0.072, 0.076)
        mb.loft([r_sh, r_el, r_wr],
                lambda i, k: JACKET_SHADE if i == 1 and k == 2 else JACKET,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 11. HANDS (2 chunky 4-sided tapered peach fists = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        h_specs = [
            (side * 0.338, 0.714, 0.044, 0.052, 0.056),
            (side * 0.346, 0.600, 0.058, 0.048, 0.052),
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
    # 12. DARK CHARCOAL BACKPACK + SHOULDER STRAPS (24 + 8 = 32 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # Faceted 4-ring hiker pack with flat-angled top, full back belly, chamfered lower edge
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.675, 0.148, -0.120, -0.258),  # 0: angled lower base
        (0.815, 0.184, -0.118, -0.346),  # 1: full lower-mid belly
        (1.020, 0.178, -0.114, -0.326),  # 2: upper-mid body
        (1.182, 0.132, -0.110, -0.215),  # 3: tapered top lid peeking behind collar
    ]
    bp_rings = []
    for (y, rx, zin, zout) in bp_specs:
        bp_rings.append([
            V(-rx, y, zin),
            V( rx, y, zin),
            V( rx, y, zout),
            V(-rx, y, zout),
        ])
    # Skip k=0 (front face flush against jacket back): 3 bands * 3 quads (18) + bot (2) + top (2) = 22 tris
    mb.loft(bp_rings, lambda i, k: PACK_SHADE if i == 0 else PACK,
            cap_bottom=True, cap_top=True, bot_color=PACK_SHADE, top_color=PACK, skip_k=(0,))

    # Subtle side pocket zipper pull tab detail on both sides (2 tris)
    for side in (-1, 1):
        xs = side * 0.186
        mb.face([
            V(xs, 0.840, -0.232),
            V(xs, 0.840, -0.254),
            V(xs, 0.915, -0.243),
        ], PACK_DETAIL, out=(side, 0, 0))

    # Two dark charcoal backpack straps curving cleanly over the shoulders & front chest (8 tris)
    mb.set_part("backpack_straps", bone="Torso")
    for side in (-1, 1):
        xa_t = min(side * 0.136, side * 0.184)
        xb_t = max(side * 0.136, side * 0.184)
        xa_b = min(side * 0.158, side * 0.206)
        xb_b = max(side * 0.158, side * 0.206)
        # Shoulder top strap quad
        mb.face([
            V(xa_t, 1.144, -0.122),
            V(xb_t, 1.144, -0.122),
            V(xb_t, 1.144,  0.126),
            V(xa_t, 1.144,  0.126),
        ], PACK, out=(0, 1, 0))
        # Front chest strap curving out under arm
        mb.face([
            V(xa_b, 0.875, 0.136),
            V(xb_b, 0.875, 0.136),
            V(xb_t, 1.144, 0.126),
            V(xa_t, 1.144, 0.126),
        ], PACK, out=(0, 0, 1))

    # =========================================================================
    # 13. BINOCULARS + NECK STRAP (hanging on chest, bone="Binoculars" = 38 tris)
    # =========================================================================
    mb.set_part("binoculars", bone="Binoculars")
    # Two chunky 4-sided diamond/beveled dark barrels resting cleanly against front chest
    # Eyepiece at top (y=0.992), wider objective lens at bottom (y=0.832)
    z_bin = 0.158
    for side in (-1, 1):
        cx = side * 0.050
        r_bot = oval_ring(cx, 0.832, z_bin + 0.006, 0.040, 0.040, n=4, phase=math.pi / 4.0)
        r_top = oval_ring(cx, 0.992, z_bin - 0.004, 0.031, 0.031, n=4, phase=math.pi / 4.0)
        mb.loft([r_bot, r_top],
                lambda i, k: BINOC_SHADE if k in (1, 2) else BINOC,
                cap_bottom=True, cap_top=True,
                bot_color=BINOC_LENS, top_color=BINOC_SHADE)

    # Center bridge / focus hinge connecting the two barrels (skip unseen back face = 6 tris)
    mb.box(-0.026, 0.026, 0.884, 0.950, z_bin - 0.022, z_bin + 0.024,
           {"front": BINOC, "top": BINOC, "bottom": BINOC_SHADE},
           skip=("left", "right", "back"))

    # Black neck strap rising cleanly from top of barrels up to the collar/neck (4 quads = 8 tris)
    mb.set_part("binoc_strap", bone="Binoculars")
    for side in (-1, 1):
        w = 0.013
        # Angled cord from top of barrel to collar front (slight outward tilt for side-view thickness)
        p_b0 = V(side * 0.052 - w, 0.990, z_bin - 0.002)
        p_b1 = V(side * 0.052 + w, 0.990, z_bin - 0.008)
        p_t0 = V(side * 0.082 - w, 1.132, 0.128)
        p_t1 = V(side * 0.082 + w, 1.132, 0.120)
        mb.face([p_b0, p_b1, p_t1, p_t0], BINOC_STRAP, out=(side * 0.25, 0, 1))
        # Upper collar wrap disappearing behind collar fold
        p_k0 = V(side * 0.095 - w, 1.168, 0.068)
        p_k1 = V(side * 0.095 + w, 1.168, 0.062)
        mb.face([p_t0, p_t1, p_k1, p_k0], BINOC_STRAP, out=(side * 0.2, 1, 0.4))

    # =========================================================================
    # 14. KHAKI CARGO PANTS + SIDE CARGO POCKETS (8 + 20 + 16 = 44 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.186, 0.186, 0.548, 0.672, -0.104, 0.104, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.010, side * 0.186
        x_in_b, x_out_b = side * 0.062, side * 0.232
        rz_t, rz_b = 0.098, 0.096
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.168,  rz_b),
            V(max(x_in_b, x_out_b), 0.168,  rz_b),
            V(max(x_in_b, x_out_b), 0.168, -rz_b),
            V(min(x_in_b, x_out_b), 0.168, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

        # Chunky watertight wedge cargo pocket on outer thigh (4 quads = 8 tris per leg)
        def leg_x_out(y):
            t = (0.585 - y) / (0.585 - 0.168)
            return x_out_t + (x_out_b - x_out_t) * t

        py_b, py_t = 0.295, 0.475
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
        p_out_bb = V(xo_b + depth * 0.72,  py_b + 0.012, pz_b)
        p_out_bf = V(xo_b + depth * 0.72,  py_b + 0.012, pz_f)

        mb.face([p_out_bb, p_out_bf, p_out_tf, p_out_tb], PANTS_POCKET, out=(side, 0, 0))
        mb.face([p_in_tb,  p_in_tf,  p_out_tf, p_out_tb], PANTS_SHADE,  out=(0, 1, 0))
        mb.face([p_in_bf,  p_out_bf, p_out_tf, p_in_tf],  PANTS_POCKET, out=(0, 0, 1))
        mb.face([p_out_bb, p_in_bb,  p_in_tb,  p_out_tb], PANTS_POCKET, out=(0, 0, -1))

    # =========================================================================
    # 15. CHUNKY BROWN HIKING BOOTS WITH DARK LUG SOLES (22 tris x 2 = 44 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.148
        w = 0.072
        w_toe = 0.060
        z_heel = -0.092
        z_mid  =  0.058
        z_toe  =  0.166
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_toe   = 0.092
        y_col   = 0.184  # tucks cleanly into cargo pant hem at y=0.168!

        # Thick dark lug sole (4 sides + bottom = 10 tris)
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

        # Warm chestnut brown boot upper (skip top face buried inside pant cuff = 12 tris)
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
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], BOOT,       out=(0, 1, 0.5))
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
    """24-frame looping Walk cycle: sturdy explorer hike stride with backpack balance & binocular pendulum."""
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

        # Sturdy explorer hike bounce & subtle forward lean balancing backpack
        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (0.048, -0.068 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-twisting torso
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.018 * c2, 0.105 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert, steady head keeping wide safari hat level with gentle step nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.040 + 0.026 * c2, -0.042 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp hiking boot stride with clean foot lift
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

        # Natural opposite-phase arm swing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.38 * s1, 0.0, 0.018 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.38 * s1, 0.0, 0.018 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Binoculars hanging on chest: gentle outward pendulum hop & side sway (biased outward to avoid clipping)
        pb_bin = rig.pose.bones["Binoculars"]
        bin_pitch = -0.038 - 0.038 * (1.0 - math.cos(2.0 * phi - 0.65)) * 0.5
        bin_sway = 0.055 * math.sin(phi - 0.45)
        pb_bin.rotation_euler = (bin_pitch, 0.0, bin_sway)
        pb_bin.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: curious explorer scanning horizon, calm breathing & gentle binocular settle."""
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
        pb_root.rotation_euler = (0.010, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.020 * s2, 0.032 * s1, -0.015 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious adventurer scanning the scenery left & right, slight tilt up under safari brim
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.025 + 0.038 * s2, 0.24 * s1, 0.035 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (-0.042 * s1, 0.0, 0.016 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.042 * s1, 0.0, -0.016 * s2)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_bin = rig.pose.bones["Binoculars"]
        pb_bin.rotation_euler = (-0.020 - 0.014 * (1.0 - s2) * 0.5, 0.0, -0.018 * s1)
        pb_bin.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Binoculars) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonAdventurerRig")
    rig = bpy.data.objects.new("PersonAdventurerRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",       None,    ( 0.000, 0.590, 0.000), ( 0.000, 0.710, 0.000)),
        ("Torso",      "Root",  ( 0.000, 0.655, 0.000), ( 0.000, 1.120, 0.000)),
        ("Head",       "Torso", ( 0.000, 1.150, 0.000), ( 0.000, 1.460, 0.000)),
        ("Arm_L",      "Torso", ( 0.162, 1.080, 0.002), ( 0.162, 1.240, 0.002)),
        ("Arm_R",      "Torso", (-0.162, 1.080, 0.002), (-0.162, 1.240, 0.002)),
        ("Binoculars", "Torso", ( 0.000, 1.132, 0.126), ( 0.000, 1.252, 0.126)),
        ("Leg_L",      "Root",  ( 0.105, 0.570, 0.000), ( 0.105, 0.730, 0.000)),
        ("Leg_R",      "Root",  (-0.105, 0.570, 0.000), (-0.105, 0.730, 0.000)),
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
        (-1.72, math.radians(45)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.58, math.radians(90)),   # Side (showing hat profile, ponytail, backpack, cargo pocket)
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=45, zrot_right_deg=90):
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
    cam_data.ortho_scale = 3.15
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

    coll = bpy.data.collections.new("PersonAdventurer")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonAdventurer")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonAdventurer", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    print("=== PersonAdventurer Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    assert total_tris < 400, f"Triangle count {total_tris} exceeds strict 400-tri budget!"

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
                          zrot_left_deg=45, zrot_right_deg=90)
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
