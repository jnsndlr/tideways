# Builds an ultra-low-poly (~480 tri) stylized woman shopper with grocery tote bag & hanging scarf in Blender
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_shopper.py)
# Saves art/person_shopper.blend, exports assets/models/person_shopper.glb (rigged + Walk & Idle cycles),
# renders art/person_shopper_preview.png, art/person_shopper_walk_preview.png, art/person_shopper_idle_preview.png,
# and outputs rendered videos art/person_shopper_walk.mp4 and art/person_shopper_idle.mp4.
#
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
BLEND_PATH = os.path.join(ROOT, "art", "person_shopper.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_shopper.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_shopper_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_shopper_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_shopper_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_shopper_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_shopper_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN              = col_srgb(0.84, 0.57, 0.34)
SKIN_SHADE        = col_srgb(0.73, 0.46, 0.25)
EYE               = col_srgb(0.14, 0.14, 0.16)
GOLD              = col_srgb(0.96, 0.79, 0.29)
GOLD_SHADE        = col_srgb(0.80, 0.62, 0.19)

HAIR_DARK         = col_srgb(0.39, 0.34, 0.31)
HAIR_MID          = col_srgb(0.50, 0.45, 0.42)
HAIR_SILVER       = col_srgb(0.63, 0.59, 0.56)
HAIR_SILVER_LIGHT = col_srgb(0.71, 0.67, 0.64)

SCARF             = col_srgb(0.75, 0.38, 0.27)
SCARF_LIGHT       = col_srgb(0.82, 0.45, 0.34)
SCARF_DARK        = col_srgb(0.59, 0.28, 0.20)
SCARF_FRINGE      = col_srgb(0.68, 0.33, 0.23)

JACKET            = col_srgb(0.47, 0.48, 0.34)
JACKET_SHADE      = col_srgb(0.37, 0.38, 0.26)
JACKET_POCKET     = col_srgb(0.42, 0.43, 0.29)
BUTTON            = col_srgb(0.25, 0.26, 0.18)

BAG               = col_srgb(0.96, 0.88, 0.76)
BAG_SHADE         = col_srgb(0.86, 0.77, 0.64)
BAG_INNER         = col_srgb(0.66, 0.57, 0.45)
BAG_STRAP         = col_srgb(0.93, 0.85, 0.73)
FISH              = col_srgb(0.53, 0.51, 0.48)

LEAF_LIGHT        = col_srgb(0.53, 0.61, 0.29)
LEAF_MID          = col_srgb(0.41, 0.50, 0.23)
LEAF_DARK         = col_srgb(0.30, 0.39, 0.18)

PANTS             = col_srgb(0.38, 0.45, 0.55)
PANTS_SHADE       = col_srgb(0.29, 0.35, 0.44)
CUFF              = col_srgb(0.59, 0.65, 0.73)
CUFF_SHADE        = col_srgb(0.49, 0.55, 0.63)

SHOE              = col_srgb(0.96, 0.91, 0.83)
SHOE_VAMP         = col_srgb(0.90, 0.84, 0.75)
SOLE              = col_srgb(0.53, 0.50, 0.45)


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Unit icosahedron topology (12 verts, 20 tris) for chunky low-poly curly bun
_PHI = (1.0 + math.sqrt(5.0)) * 0.5
_ICO_RAW = [
    (-1,  _PHI, 0), ( 1,  _PHI, 0), (-1, -_PHI, 0), ( 1, -_PHI, 0),
    ( 0, -1,  _PHI), ( 0,  1,  _PHI), ( 0, -1, -_PHI), ( 0,  1, -_PHI),
    ( _PHI, 0, -1), ( _PHI, 0,  1), (-_PHI, 0, -1), (-_PHI, 0,  1),
]
_ICO_VERTS = [Vector(p).normalized() for p in _ICO_RAW]
_ICO_FACES = [
    (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
    (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
    (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
    (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
]


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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None, ring_weights=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            w0 = ring_weights[i] if ring_weights is not None else None
            w1 = ring_weights[i + 1] if ring_weights is not None else None
            for k in range(n):
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
            w0 = ring_weights[0] if ring_weights is not None else None
            if n <= 4:
                ws = [w0] * n if w0 is not None else None
                self.face(r0, col, out=out_dir, weights=ws)
            else:
                ws = [w0, w0, w0] if w0 is not None else None
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
            else:
                ws = [wt, wt, wt] if wt is not None else None
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=ws)

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

    def tri_strap(self, centers, normals, half_w, thick, color):
        """3-sided prism ribbon (6 tris per segment) — crisp 3D volume from all angles at low poly cost."""
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
            # Flat outer canvas face + beveled inner ridge (3 verts per ring)
            rings.append([
                c - b * half_w + n * (thick * 0.5),
                c + b * half_w + n * (thick * 0.5),
                c - n * (thick * 0.9),
            ])
        self.loft(rings, color, cap_bottom=False, cap_top=False)

    def puff(self, center, rx, ry, rz, color, rot_y=0.0, rot_x=0.0, alt_color=None, lump=0.08):
        """Chunky 20-tri faceted icosahedron with subtle curly lumpiness for the high hair bun."""
        cy, sy = math.cos(rot_y), math.sin(rot_y)
        cx, sx = math.cos(rot_x), math.sin(rot_x)
        pts = []
        for idx, v in enumerate(_ICO_VERTS):
            x1 = v.x * cy + v.z * sy
            z1 = -v.x * sy + v.z * cy
            y2 = v.y * cx - z1 * sx
            z2 = v.y * sx + z1 * cx
            sc = 1.0 + lump * (1.0 if idx % 2 == 0 else -0.8)
            pts.append(V(center.x + x1 * rx * sc, center.y + y2 * ry * sc, center.z + z2 * rz * sc))
        for fi, (a, b, c) in enumerate(_ICO_FACES):
            p0, p1, p2 = pts[a], pts[b], pts[c]
            mid = (p0 + p1 + p2) / 3.0
            col = alt_color if (alt_color is not None and fi % 3 == 0) else color
            self.face([p0, p1, p2], col, out=(mid - center))


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. UNIFIED HEAD + FACETED CURLY SALT-AND-PEPPER HAIR (~78 tris)
    # =========================================================================
    mb.set_part("head_and_hair", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.208,  0.012, 0.144, 0.140),  # 0: chin/jaw base
        (1.292,  0.018, 0.204, 0.194),  # 1: cheeks / nape
        (1.482,  0.012, 0.208, 0.200),  # 2: brow / curly hairline
        (1.615, -0.008, 0.214, 0.218),  # 3: full rounded curly crown dome
        (1.698, -0.016, 0.122, 0.126),  # 4: crown top cap
    ]
    head_rings = []
    for i, (y, cz, rx, rz) in enumerate(head_specs):
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            sx = math.sin(a)
            cz_a = math.cos(a)
            # Add curly hair volume & organic faceted ripple on hair zones (keep front face smooth!)
            is_hair_v = (i >= 3) or (i == 2 and k in (1, 2, 3, 4, 5)) or (i == 1 and k in (2, 3, 4))
            if is_hair_v:
                vol = 1.11 if i == 2 else (1.07 if i == 3 else 1.05)
                ripple = 1.0 + (0.045 if (i + k) % 2 == 0 else -0.025)
                # Slightly fuller at back of head
                back_boost = 1.0 + 0.08 * max(0.0, -cz_a)
                sc = vol * ripple * back_boost
                y_off = (0.010 if (i + k) % 2 == 0 else -0.008) if i >= 3 else 0.0
            else:
                sc = 1.03
                y_off = 0.0
            ring.append(V(rx * sx * sc, y + y_off, cz + rz * cz_a * sc))
        head_rings.append(ring)

    def hair_tri_col(i, k, half):
        # Salt-and-pepper silver-grey curly highlights concentrated at front hairline & top crown
        if k in (6, 7, 0):
            if i == 2:
                return HAIR_SILVER_LIGHT if (k + half) % 2 == 0 else HAIR_SILVER
            return HAIR_SILVER if half == 0 else HAIR_MID
        if k in (1, 5):
            if i >= 2:
                return HAIR_MID if half == 0 else HAIR_SILVER
            return HAIR_DARK if half == 0 else HAIR_MID
        # Back of head (k in 2, 3, 4): rich mocha brown facets
        return HAIR_DARK if (i + k + half) % 2 == 0 else HAIR_MID

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 8
        c1 = sum(r1, Vector()) / 8
        cmid = (c0 + c1) * 0.5
        for k in range(8):
            kn = (k + 1) % 8
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            out_dir = mid - cmid

            # Front face panels (SKIN)
            if i == 0 and k in (5, 6, 7, 0, 1):
                col = SKIN if k in (6, 7, 0) else HAIR_DARK
                mb.face([p0, p1, p2, p3], col, out=out_dir)
            elif i == 1 and k == 7:
                # Center face
                mb.face([p0, p1, p2, p3], SKIN, out=out_dir)
            elif i == 1 and k == 0:
                # Sweeping curly temple hairline (+X)
                pt = p1.lerp(p2, 0.42)
                mb.face([p0, p1, pt, p3], SKIN, out=out_dir)
                mb.face([pt, p2, p3], HAIR_SILVER, out=out_dir)
            elif i == 1 and k == 6:
                # Sweeping curly temple hairline (-X)
                pt = p0.lerp(p3, 0.42)
                mb.face([p0, p1, p2, pt], SKIN, out=out_dir)
                mb.face([pt, p2, p3], HAIR_SILVER, out=out_dir)
            elif i == 2 and k == 7:
                # Silver-grey curly forehead fringe framing top of face (inverted-V scallop)
                p_apex = p2.lerp(p3, 0.5)
                p_apex = V(p_apex.x, p0.y + (p2.y - p0.y) * 0.30, p0.z * 0.55 + p2.z * 0.45)
                mb.face([p0, p1, p_apex], SKIN, out=(0, 0, 1))
                mb.face([p0, p_apex, p3], HAIR_SILVER_LIGHT, out=(0, 0, 1))
                mb.face([p1, p2, p_apex], HAIR_SILVER, out=(0, 0, 1))
                mb.face([p_apex, p2, p3], HAIR_SILVER_LIGHT, out=(0, 0.3, 1))
            else:
                # Hair zone: split quad into 2 alternating crisp curl-colored triangles (same tri count!)
                if (i + k) % 2 == 0:
                    mb.face([p0, p1, p2], hair_tri_col(i, k, 0), out=out_dir)
                    mb.face([p0, p2, p3], hair_tri_col(i, k, 1), out=out_dir)
                else:
                    mb.face([p0, p1, p3], hair_tri_col(i, k, 0), out=out_dir)
                    mb.face([p1, p2, p3], hair_tri_col(i, k, 1), out=out_dir)

    # Top crown cap (6 tris, alternating curl tones)
    rt = head_rings[-1]
    mb.face([rt[7], rt[0], rt[3], rt[4]], HAIR_MID, out=(0, 1, 0))
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR_MID, out=(0, 1, 0))
    mb.face([rt[4], rt[5], rt[6], rt[7]], HAIR_SILVER, out=(0, 1, 0))

    # Chin bottom cap (6 tris)
    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. BIG HIGH CURLY BUN (1 chunky lumpy icosahedron = 20 tris!)
    # =========================================================================
    mb.set_part("hair_bun", bone="Head")
    mb.puff(V(0.0, 1.595, -0.300), 0.162, 0.156, 0.155,
            HAIR_DARK, rot_y=0.35, rot_x=0.22, alt_color=HAIR_MID, lump=0.07)

    # =========================================================================
    # 3. EARS + HOLLOW CHUNKY GOLD HOOP EARRINGS (12 + 48 = 60 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.198
        x_out = side * 0.246
        y0, y1 = 1.300, 1.398
        z0, z1 = -0.016, 0.054
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_tip], SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], SKIN, out=(0, 1, 0))

    # Chunky 4-segment hollow diamond gold hoops with 3-sided beveled cross-section (24 tris each)
    mb.set_part("earrings", bone="Head")
    r_out = 0.038
    r_in = 0.014
    for side in (-1, 1):
        xc = side * 0.244
        hw = 0.015
        cy = 1.280
        cz = 0.018
        # 4 angles around hoop (45, 135, 225, 315 deg -> rounded square/octagonal feel)
        ring_a, ring_b, ring_in = [], [], []
        for k in range(4):
            a = math.pi / 4.0 + 0.5 * math.pi * k
            ca, sa = math.cos(a), math.sin(a)
            ring_a.append(V(xc - hw, cy + r_out * sa, cz + r_out * ca))
            ring_b.append(V(xc + hw, cy + r_out * sa, cz + r_out * ca))
            ring_in.append(V(xc,     cy + r_in  * sa, cz + r_in  * ca))
        for k in range(4):
            kn = (k + 1) % 4
            a_mid = math.pi / 4.0 + 0.5 * math.pi * (k + 0.5)
            rad = V(0.0, math.sin(a_mid), math.cos(a_mid))
            col = GOLD if math.sin(a_mid) >= -0.2 else GOLD_SHADE
            # Outer perimeter + outer cheek bevel + inner cheek bevel (3 quads per segment)
            mb.face([ring_a[k], ring_b[k], ring_b[kn], ring_a[kn]], col, out=rad)
            mb.face([ring_a[k], ring_a[kn], ring_in[kn], ring_in[k]], col, out=(-1, -rad.y * 0.3, -rad.z * 0.3))
            mb.face([ring_in[k], ring_in[kn], ring_b[kn], ring_b[k]], col, out=( 1, -rad.y * 0.3, -rad.z * 0.3))

    # =========================================================================
    # 4. EYES (2 vertical dark pill quads = 4 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.213
    for side in (-1, 1):
        cx = side * 0.068
        cy = 1.390
        rx, ry = 0.019, 0.046
        mb.face([
            V(cx - rx, cy - ry, z_eye),
            V(cx + rx, cy - ry, z_eye),
            V(cx + rx, cy + ry, z_eye),
            V(cx - rx, cy + ry, z_eye),
        ], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. NECK (4-sided warm brown cylinder = 8 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.115, 0.008, 0.072, 0.066, n=4, phase=math.pi / 4)
    neck_r1 = oval_ring(0.0, 1.215, 0.010, 0.068, 0.064, n=4, phase=math.pi / 4)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 6. OLIVE GREEN BOXY UTILITY JACKET (torso + placket + buttons + pockets = 28 tris)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    jy0, jy1 = 0.642, 1.135
    jx_bot, jx_top = 0.216, 0.194
    jz_fb, jz_ft = 0.134, 0.124
    jz_bb, jz_bt = -0.124, -0.114

    j_bot = [
        V(-jx_bot, jy0, jz_fb),
        V( jx_bot, jy0, jz_fb),
        V( jx_bot, jy0, jz_bb),
        V(-jx_bot, jy0, jz_bb),
    ]
    j_top = [
        V(-jx_top, jy1, jz_ft),
        V( jx_top, jy1, jz_ft),
        V( jx_top, jy1, jz_bt),
        V(-jx_top, jy1, jz_bt),
    ]
    mb.loft([j_bot, j_top], JACKET, cap_bottom=True, cap_top=False,
            bot_color=JACKET_SHADE)

    # Center placket seam + 2 crisp dark utility buttons (6 tris)
    mb.face([
        V(-0.015, jy0 + 0.004, jz_fb + 0.002),
        V( 0.015, jy0 + 0.004, jz_fb + 0.002),
        V( 0.015, jy1 - 0.010, jz_ft + 0.002),
        V(-0.015, jy1 - 0.010, jz_ft + 0.002),
    ], JACKET_SHADE, out=(0, 0, 1))

    for by in (0.985, 0.855):
        t = (by - jy0) / (jy1 - jy0)
        bz = jz_fb + (jz_ft - jz_fb) * t + 0.004
        mb.face([
            V(-0.011, by - 0.011, bz),
            V( 0.011, by - 0.011, bz),
            V( 0.011, by + 0.011, bz),
            V(-0.011, by + 0.011, bz),
        ], BUTTON, out=(0, 0, 1))

    # Two lower front patch pockets with top-flap accent (8 tris)
    for side in (-1, 1):
        px0 = min(side * 0.056, side * 0.186)
        px1 = max(side * 0.056, side * 0.186)
        zf_p = jz_fb + 0.004
        mb.face([V(px0, 0.688, zf_p), V(px1, 0.688, zf_p),
                 V(px1, 0.818, zf_p), V(px0, 0.818, zf_p)], JACKET_POCKET, out=(0, 0, 1))
        mb.face([V(px0 - 0.003, 0.818, zf_p + 0.002), V(px1 + 0.003, 0.818, zf_p + 0.002),
                 V(px1 + 0.003, 0.842, zf_p + 0.002), V(px0 - 0.003, 0.842, zf_p + 0.002)],
                JACKET_SHADE, out=(0, 0, 1))

    # =========================================================================
    # 7. CHUNKY TERRACOTTA SCARF WRAP + 2-BONE HANGING END WITH FRINGE (~56 tris)
    # =========================================================================
    mb.set_part("scarf_wrap", bone="Torso")
    # Cozy chunky 6-sided faceted collar wrap (2 bands + flat top cap = 28 tris)
    n_sc = 6
    sc_rings_spec = [
        (1.072, -0.020, 0.002, 0.212, 0.194),  # 0: lower drape resting on shoulders
        (1.138, -0.022, 0.008, 0.242, 0.220),  # 1: full chunky wrap belly
        (1.212, -0.006, 0.010, 0.214, 0.196),  # 2: upper cozy wrap fold under chin
    ]
    sc_rings = []
    for (yb, yt, cz, rx, rz) in sc_rings_spec:
        ring = []
        for k in range(n_sc):
            a = math.pi / n_sc + 2.0 * math.pi * k / n_sc
            ca, sa = math.cos(a), math.sin(a)
            bump = 1.0 + 0.04 * math.sin(2.0 * a + 0.6)
            ring.append(V(rx * sa * bump, yb + yt * ca + 0.010 * math.sin(a - 0.4), cz + rz * ca * bump))
        sc_rings.append(ring)

    def scarf_wrap_col(i, k):
        return SCARF_LIGHT if (i + k) % 2 == 0 else SCARF

    mb.loft(sc_rings, scarf_wrap_col, cap_bottom=False, cap_top=False)
    # Flat 4-tri top cap tucked cleanly under chin
    rt_sc = sc_rings[-1]
    mb.face([rt_sc[5], rt_sc[0], rt_sc[2], rt_sc[3]], SCARF_DARK, out=(0, 1, 0))
    mb.face([rt_sc[0], rt_sc[1], rt_sc[2]], SCARF_DARK, out=(0, 1, 0))
    mb.face([rt_sc[3], rt_sc[4], rt_sc[5]], SCARF_DARK, out=(0, 1, 0))

    # Hanging scarf end (weighted Torso -> Scarf_Top -> Scarf_Tip for smooth cloth wave! = 24 tris)
    mb.set_part("scarf_tail")
    tail_specs = [
        # (y,     x0,     x1,     z_back, z_front, weights_dict)
        (1.135,  0.018,  0.130,  0.150,  0.202, {"Torso": 0.75, "Scarf_Top": 0.25}),
        (0.995,  0.020,  0.134,  0.146,  0.192, {"Scarf_Top": 1.0}),
        (0.865,  0.022,  0.140,  0.144,  0.188, {"Scarf_Top": 0.40, "Scarf_Tip": 0.60}),
        (0.715,  0.024,  0.144,  0.142,  0.178, {"Scarf_Tip": 1.0}),
    ]
    tail_rings = []
    tail_weights = []
    for (y, x0, x1, zb, zf, wd) in tail_specs:
        tail_rings.append([
            V(x0, y, zf),
            V(x1, y, zf),
            V(x1, y, zb),
            V(x0, y, zb),
        ])
        tail_weights.append(wd)

    def tail_col(i, k):
        if i == 1:
            return SCARF_LIGHT if k == 0 else SCARF
        if i == 2:
            return SCARF_DARK if k == 2 else SCARF
        return SCARF if k != 2 else SCARF_DARK

    mb.loft(tail_rings, tail_col, cap_bottom=False, cap_top=False, ring_weights=tail_weights)

    # Stylized low-poly fringe tassels along bottom edge (3 chunky hanging teeth = 9 tris!)
    mb.set_bone("Scarf_Tip")
    n_fringe = 3
    fx0, fx1 = 0.024, 0.144
    fw = (fx1 - fx0) / n_fringe
    zf_f, zb_f = 0.176, 0.144
    zm_f = 0.5 * (zf_f + zb_f)
    for fi in range(n_fringe):
        xa = fx0 + fi * fw + 0.003
        xb = fx0 + (fi + 1) * fw - 0.003
        xm = 0.5 * (xa + xb)
        y_top_f = 0.718
        y_tip = 0.648 + (0.008 if fi == 1 else 0.0)
        col = SCARF_FRINGE if fi % 2 == 0 else SCARF_DARK
        p_tip = V(xm, y_tip, zm_f)
        # 3-sided downward tassel wedge (front + back + outer) = 3 tris per tassel
        mb.face([V(xa, y_top_f, zf_f), V(xb, y_top_f, zf_f), p_tip], col, out=(0, 0, 1))
        mb.face([V(xb, y_top_f, zb_f), V(xa, y_top_f, zb_f), p_tip], SCARF_DARK, out=(0, 0, -1))
        mb.face([V(xa, y_top_f, zb_f), V(xa, y_top_f, zf_f), p_tip], col, out=(-1, 0, 0))

    # =========================================================================
    # 8. SLEEVES (4-sided bent low-poly sleeves, 18 tris each = 36 tris total)
    # =========================================================================
    mb.set_part("sleeves")

    def build_bent_sleeve(p_sh, p_el, p_wr, bone_name, cuff_flare=1.06):
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
        r_sh = aligned_ring(p_sh, ax1, 0.072, 0.080)
        r_el = aligned_ring(p_el, ax_mid, 0.086, 0.090)
        r_wr = aligned_ring(p_wr, ax2, 0.080 * cuff_flare, 0.082 * cuff_flare)
        mb.loft([r_sh, r_el, r_wr], JACKET, cap_bottom=False, cap_top=True, top_color=JACKET_SHADE)

    p_r_sh = V(-0.172, 1.055, -0.005)
    p_r_el = V(-0.262, 0.872, -0.042)
    p_r_wr = V(-0.218, 0.836,  0.098)
    build_bent_sleeve(p_r_sh, p_r_el, p_r_wr, "Arm_R", cuff_flare=1.08)

    p_l_sh = V(0.172, 1.055,  0.005)
    p_l_el = V(0.258, 0.865, -0.004)
    p_l_wr = V(0.254, 0.726,  0.082)
    build_bent_sleeve(p_l_sh, p_l_el, p_l_wr, "Arm_L", cuff_flare=1.04)

    # =========================================================================
    # 9. HANDS (warm brown low-poly mittens, 10 tris each = 20 tris total)
    # =========================================================================
    mb.set_part("hands")

    def build_hand(p_el, p_wr, bone_name):
        mb.set_bone(bone_name)
        ax = (p_wr - p_el).normalized()
        u = V(1.0, 0.0, 0.0) - ax * ax.x
        u = u.normalized()
        v = ax.cross(u).normalized()
        r0 = [
            p_wr + u * (-0.052) + v * ( 0.056),
            p_wr + u * ( 0.052) + v * ( 0.056),
            p_wr + u * ( 0.052) + v * (-0.056),
            p_wr + u * (-0.052) + v * (-0.056),
        ]
        c1 = p_wr + ax * 0.102
        r1 = [
            c1 + u * (-0.040) + v * ( 0.042),
            c1 + u * ( 0.040) + v * ( 0.042),
            c1 + u * ( 0.040) + v * (-0.042),
            c1 + u * (-0.040) + v * (-0.042),
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    build_hand(p_r_el, p_r_wr, "Arm_R")
    build_hand(p_l_el, p_l_wr, "Arm_L")

    # =========================================================================
    # 10. CANVAS GROCERY TOTE BAG + FISH + STRAP + LEAFY GREENS (~85 tris)
    # =========================================================================
    mb.set_part("grocery_bag", bone="Bag")
    bag_tilt = math.radians(-16.0)
    ct, st = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_orig = V(-0.286, 0.680, -0.116)

    def bag_pt(lx, ly, lz):
        ry = ly * ct - lz * st
        rz = ly * st + lz * ct
        return V(bag_orig.x + lx, bag_orig.y + ry, bag_orig.z + rz)

    # Tapered canvas tote with crisp gusset bevel & dark interior top (20 tris)
    bag_stations = [
        (-0.158,  0.052, -0.070, -0.150,  0.150),  # 0: bottom flat base
        (-0.110,  0.068, -0.090, -0.184,  0.184),  # 1: gusset belly
        ( 0.152,  0.060, -0.078, -0.190,  0.190),  # 2: top rim
    ]
    bag_rings = []
    for (ly, xi, xo, zb, zf) in bag_stations:
        bag_rings.append([
            bag_pt(xo, ly, zb),
            bag_pt(xi, ly, zb),
            bag_pt(xi, ly, zf),
            bag_pt(xo, ly, zf),
        ])

    def bag_col(i, k):
        if i == 0:
            return BAG_SHADE
        return BAG_SHADE if k == 1 else BAG

    mb.loft(bag_rings, bag_col, cap_bottom=True, cap_top=True,
            bot_color=BAG_SHADE, top_color=BAG_INNER)

    # Iconic grey fish graphic on outer (-X) canvas face (7 tris!)
    mb.set_part("bag_fish", bone="Bag")

    def fish_pt(ly, lz):
        t = (ly - (-0.110)) / (0.152 - (-0.110))
        xo = -0.090 + (-0.078 - (-0.090)) * t - 0.0028
        return bag_pt(xo, ly, lz)

    f_nose    = fish_pt( 0.004,  0.114)
    f_top_f   = fish_pt( 0.042,  0.036)
    f_dorsal  = fish_pt( 0.060, -0.014)
    f_top_b   = fish_pt( 0.030, -0.044)
    f_pinch   = fish_pt( 0.000, -0.076)
    f_tail_t  = fish_pt( 0.048, -0.124)
    f_tail_n  = fish_pt( 0.000, -0.100)
    f_tail_b  = fish_pt(-0.048, -0.124)
    f_bot_b   = fish_pt(-0.030, -0.042)
    f_bot_f   = fish_pt(-0.038,  0.038)

    out_fish = V(-1.0, 0.0, 0.0)
    mb.face([f_nose, f_top_f, f_bot_f], FISH, out=out_fish)             # 1 tri
    mb.face([f_top_f, f_top_b, f_bot_b, f_bot_f], FISH, out=out_fish)   # 2 tris
    mb.face([f_top_f, f_dorsal, f_top_b], FISH, out=out_fish)           # 1 tri
    mb.face([f_top_b, f_pinch, f_bot_b], FISH, out=out_fish)            # 1 tri
    mb.face([f_pinch, f_tail_t, f_tail_n], FISH, out=out_fish)          # 1 tri
    mb.face([f_pinch, f_tail_n, f_tail_b], FISH, out=out_fish)          # 1 tri

    # Wide cream canvas shoulder strap (4-segment 3-sided prism ribbon = 24 tris, smooth V-loop clearing Arm_R!)
    mb.set_part("bag_strap", bone="Bag")
    strap_loop = [
        bag_pt(-0.048, 0.142,  0.172),
        V(-0.292, 1.005,  0.072),
        V(-0.208, 1.132, -0.002),
        V(-0.272, 1.012, -0.132),
        bag_pt(-0.048, 0.142, -0.088),
    ]
    strap_norms = [
        V(-0.9, 0.0,  0.4),
        V(-0.8, 0.2,  0.6),
        V(-0.3, 0.9,  0.0),
        V(-0.7, 0.2, -0.7),
        V(-0.9, 0.0, -0.4),
    ]
    mb.tri_strap(strap_loop, strap_norms, half_w=0.029, thick=0.018, color=BAG_STRAP)

    # Chunky low-poly leafy greens poking out behind rear strap (5 diamond-blade leaves × 6 tris = 30 tris!)
    mb.set_part("groceries_greens", bone="Bag")

    def build_diamond_leaf(base_local, dir_local, length, w_mid, thick, col_main, col_tip):
        b_pt = bag_pt(*base_local)
        t_pt = bag_pt(
            base_local[0] + dir_local[0] * length,
            base_local[1] + dir_local[1] * length,
            base_local[2] + dir_local[2] * length,
        )
        ax = (t_pt - b_pt).normalized()
        ref = V(1.0, 0.0, 0.0) if abs(ax.x) < 0.85 else V(0.0, 0.0, 1.0)
        u = ax.cross(ref).normalized()
        v = ax.cross(u).normalized()

        m_pt = b_pt.lerp(t_pt, 0.56) + u * 0.010
        m0 = m_pt - u * w_mid + v * (thick * 0.6)
        m1 = m_pt + u * w_mid + v * (thick * 0.6)
        m2 = m_pt - v * thick
        mid_ring = [m0, m1, m2]
        for k in range(3):
            kn = (k + 1) % 3
            edge_mid = (mid_ring[k] + mid_ring[kn]) * 0.5 - m_pt
            mb.face([b_pt, mid_ring[k], mid_ring[kn]], col_main, out=edge_mid - ax * 0.3)
            mb.face([mid_ring[k], t_pt, mid_ring[kn]], col_tip, out=edge_mid + ax * 0.3)

    leaf_specs = [
        ((-0.016, 0.122, -0.116), (-0.14, 0.96, -0.22), 0.268, 0.044, 0.026, LEAF_MID,   LEAF_LIGHT),
        (( 0.014, 0.122, -0.138), ( 0.08, 0.92, -0.36), 0.246, 0.042, 0.024, LEAF_DARK,  LEAF_MID),
        ((-0.032, 0.122, -0.086), (-0.28, 0.95, -0.06), 0.236, 0.042, 0.026, LEAF_LIGHT, LEAF_LIGHT),
        ((-0.010, 0.122, -0.158), (-0.12, 0.87, -0.46), 0.222, 0.040, 0.024, LEAF_MID,   LEAF_LIGHT),
        (( 0.012, 0.122, -0.095), ( 0.10, 0.98, -0.10), 0.252, 0.040, 0.024, LEAF_MID,   LEAF_LIGHT),
    ]
    for (bl, dl, ln, wm, th, cm, ct_c) in leaf_specs:
        build_diamond_leaf(bl, dl, ln, wm, th, cm, ct_c)

    # =========================================================================
    # 11. SLATE-BLUE CROPPED TROUSERS + ROLLED LIGHT-SLATE CUFFS (26 + 24 = 50 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.188, 0.188, 0.545, 0.678, -0.104, 0.104, PANTS, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t  = side * 0.010
        x_out_t = side * 0.186
        x_in_b  = side * 0.062
        x_out_b = side * 0.232
        rz_t, rz_b = 0.098, 0.094
        r_top = [
            V(min(x_in_t, x_out_t), 0.582,  rz_t),
            V(max(x_in_t, x_out_t), 0.582,  rz_t),
            V(max(x_in_t, x_out_t), 0.582, -rz_t),
            V(min(x_in_t, x_out_t), 0.582, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.256,  rz_b),
            V(max(x_in_b, x_out_b), 0.256,  rz_b),
            V(max(x_in_b, x_out_b), 0.256, -rz_b),
            V(min(x_in_b, x_out_b), 0.256, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=False, cap_top=False)

    mb.set_part("pant_cuffs")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        xa = min(side * 0.052, side * 0.244)
        xb = max(side * 0.052, side * 0.244)
        rz_c = 0.106
        r_cb = [V(xa, 0.194, rz_c), V(xb, 0.194, rz_c), V(xb, 0.194, -rz_c), V(xa, 0.194, -rz_c)]
        r_ct = [V(xa, 0.268, rz_c), V(xb, 0.268, rz_c), V(xb, 0.268, -rz_c), V(xa, 0.268, -rz_c)]
        mb.loft([r_cb, r_ct], CUFF, cap_bottom=True, cap_top=True,
                bot_color=CUFF_SHADE, top_color=CUFF_SHADE)

    # =========================================================================
    # 12. ANKLES (16 tris)
    # =========================================================================
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.148
        mb.box(cx - 0.044, cx + 0.044, 0.118, 0.204, -0.046, 0.046, SKIN, skip=("top", "bottom"))

    # =========================================================================
    # 13. CREAM CHUNKY SLIP-ON LOAFERS WITH TAUPE-GREY SOLES (20 tris each = 40 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.148
        w, w_toe = 0.070, 0.058
        z_heel, z_toe = -0.092, 0.162
        y_sole0, y_sole1 = 0.000, 0.036
        y_collar, y_toe_top = 0.130, 0.082

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
        upper_top = [
            V(cx - w * 0.88,     y_collar,  z_heel + 0.014),
            V(cx + w * 0.88,     y_collar,  z_heel + 0.014),
            V(cx + w_toe * 0.88, y_toe_top, z_toe - 0.016),
            V(cx - w_toe * 0.88, y_toe_top, z_toe - 0.016),
        ]
        mb.loft([sole_bot, sole_top], SOLE, cap_bottom=True, cap_top=False, bot_color=SOLE)
        mb.loft([sole_top, upper_top], SHOE, cap_bottom=False, cap_top=True, top_color=SHOE_VAMP)

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
    """24-frame looping Walk cycle: lively neighborhood stroll, swaying grocery bag & flowing scarf tail."""
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

        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        root_pitch = -0.052
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.068 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_pitch = -0.024 * c2
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (torso_pitch, 0.100 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.040 + 0.024 * c2, -0.042 * s1, -0.015 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

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

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.36 * s1, 0.0, 0.02 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.095 * s1 + 0.02, 0.0, -0.015 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.062 * math.sin(phi - 0.60), 0.0, 0.024 * c1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_sc_top = rig.pose.bones["Scarf_Top"]
        pb_sc_top.rotation_euler = (
            -0.095 + 0.085 * math.sin(2.0 * phi - 0.55),
            0.0,
            0.075 * math.sin(phi - 0.45),
        )
        pb_sc_top.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_sc_tip = rig.pose.bones["Scarf_Tip"]
        pb_sc_tip.rotation_euler = (
            -0.075 + 0.145 * math.sin(2.0 * phi - 1.35),
            0.0,
            0.110 * math.sin(phi - 1.15),
        )
        pb_sc_tip.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: warm relaxed breathing, curious glance, calm bag & coastal-breeze scarf."""
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
        root_pitch = -0.012
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (root_pitch, 0.022 * s1, 0.016 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * s2, 0.028 * s1, -0.015 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * s2, 0.21 * s1, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.048 * s1, 0.0, 0.018 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.028 * s2, 0.0, -0.012 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.022 * s2, 0.0, -0.018 * s1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_sc_top = rig.pose.bones["Scarf_Top"]
        pb_sc_top.rotation_euler = (
            -0.060 + 0.048 * math.sin(phi - 0.35) + 0.026 * math.sin(2.0 * phi),
            0.0,
            0.052 * math.sin(phi - 0.20),
        )
        pb_sc_top.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_sc_tip = rig.pose.bones["Scarf_Tip"]
        pb_sc_tip.rotation_euler = (
            -0.050 + 0.085 * math.sin(phi - 1.05) + 0.048 * math.sin(2.0 * phi - 0.80),
            0.0,
            0.080 * math.sin(phi - 0.90),
        )
        pb_sc_tip.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 10-bone rig (7 standard passenger bones + Bag + 2-bone Scarf tail) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonShopperRig")
    rig = bpy.data.objects.new("PersonShopperRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,        ( 0.000, 0.620,  0.000), ( 0.000, 0.720,  0.000)),
        ("Torso",     "Root",      ( 0.000, 0.675,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",      "Torso",     ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Arm_L",     "Torso",     ( 0.180, 1.055,  0.000), ( 0.180, 1.215,  0.000)),
        ("Arm_R",     "Torso",     (-0.180, 1.055,  0.000), (-0.180, 1.215,  0.000)),
        ("Bag",       "Torso",     (-0.192, 1.115, -0.025), (-0.192, 1.275, -0.025)),
        ("Scarf_Top", "Torso",     ( 0.075, 1.095,  0.170), ( 0.075, 1.235,  0.170)),
        ("Scarf_Tip", "Scarf_Top", ( 0.082, 0.875,  0.165), ( 0.082, 1.015,  0.165)),
        ("Leg_L",     "Root",      ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R",     "Root",      (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-1.68, math.radians(64)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side
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

    coll = bpy.data.collections.new("PersonShopper")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonShopper")
    mb.bm.to_mesh(me)
    mb.bm.free()

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonShopper", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    os.makedirs(os.path.dirname(GLB_PATH), exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(o in (rig, ob))
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_selection=True,
        export_normals=True,
        export_vertex_color="ACTIVE",
        export_materials="EXPORT",
        export_yup=True,
        export_skins=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
    )

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=64)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=54, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonShopper Stats ===")
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
