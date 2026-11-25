# Builds an ultra-low-poly stylized woman shopper with grocery tote bag and hanging scarf in Blender
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
JACKET_POCKET     = col_srgb(0.43, 0.44, 0.30)
BUTTON            = col_srgb(0.26, 0.27, 0.19)

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


# Unit icosahedron topology for chunky low-poly curly hair puffs
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

    def ribbon_path(self, centers, normals, half_w, half_t, color, cap_start=True, cap_end=True):
        """Sweep a rectangular strap along 3D centers with given outward normals."""
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
            ring = [
                c - b * half_w + n * half_t,
                c + b * half_w + n * half_t,
                c + b * half_w - n * half_t,
                c - b * half_w - n * half_t,
            ]
            rings.append(ring)
        self.loft(rings, color, cap_bottom=cap_start, cap_top=cap_end, bot_color=color, top_color=color)

    def puff(self, center, rx, ry, rz, color, rot_y=0.0, rot_x=0.0, alt_color=None):
        """Chunky 20-tri faceted icosahedron puff for stylized curly hair."""
        cy, sy = math.cos(rot_y), math.sin(rot_y)
        cx, sx = math.cos(rot_x), math.sin(rot_x)
        pts = []
        for v in _ICO_VERTS:
            # Rotate around Y then X for varied facet orientations
            x1 = v.x * cy + v.z * sy
            z1 = -v.x * sy + v.z * cy
            y2 = v.y * cx - z1 * sx
            z2 = v.y * sx + z1 * cx
            pts.append(V(center.x + x1 * rx, center.y + y2 * ry, center.z + z2 * rz))
        for fi, (a, b, c) in enumerate(_ICO_FACES):
            p0, p1, p2 = pts[a], pts[b], pts[c]
            mid = (p0 + p1 + p2) / 3.0
            col = alt_color if (alt_color is not None and fi % 3 == 0) else color
            self.face([p0, p1, p2], col, out=(mid - center))


def oval_ring(cx, cy, cz, rx, rz, n=8, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD (rounded 8-sided low-poly head, warm brown skin, y = 1.21 .. 1.66)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.208,  0.012, 0.142, 0.138),  # 0: chin/jaw base
        (1.288,  0.018, 0.205, 0.194),  # 1: lower cheek
        (1.488,  0.014, 0.208, 0.198),  # 2: brow / forehead
        (1.595,  0.000, 0.184, 0.184),  # 3: upper skull inside curly hair
        (1.660, -0.010, 0.105, 0.105),  # 4: top cap inside curly hair
    ]
    head_rings = []
    for (y, cz, rx, rz) in head_specs:
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            ring.append(V(rx * math.sin(a) * 1.03, y, cz + rz * math.cos(a) * 1.03))
        head_rings.append(ring)

    def head_color(i, k):
        if i >= 2:
            return HAIR_MID if k in (6, 7, 0) else HAIR_DARK
        if i == 1:
            return SKIN if k in (6, 7, 0) else HAIR_DARK
        return HAIR_DARK if k in (2, 3, 4) else SKIN

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 8
        c1 = sum(r1, Vector()) / 8
        cmid = (c0 + c1) * 0.5
        for k in range(8):
            kn = (k + 1) % 8
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 1 and k == 0:
                # Curved curly temple hairline on +X (left side)
                p_t = p1.lerp(p2, 0.42)
                mb.face([p0, p1, p_t, p3], SKIN, out=(mid - cmid))
                mb.face([p_t, p2, p3], HAIR_DARK, out=(mid - cmid))
            elif i == 1 and k == 6:
                # Curved curly temple hairline on -X (right side)
                p_t = p0.lerp(p3, 0.42)
                mb.face([p0, p1, p2, p_t], SKIN, out=(mid - cmid))
                mb.face([p_t, p2, p3], HAIR_DARK, out=(mid - cmid))
            elif i == 2 and k == 7:
                # Upper forehead skin tucked slightly beneath silver front curls
                p_m = p0.lerp(p3, 0.35)
                p_n = p1.lerp(p2, 0.35)
                mb.face([p0, p1, p_n, p_m], SKIN, out=(0, 0, 1))
                mb.face([p_m, p_n, p2, p3], HAIR_MID, out=(0, 0, 1))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    # Top & bottom caps
    rt = head_rings[-1]
    mb.face([rt[7], rt[0], rt[3], rt[4]], HAIR_DARK, out=(0, 1, 0))
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR_DARK, out=(0, 1, 0))
    mb.face([rt[4], rt[5], rt[6], rt[7]], HAIR_DARK, out=(0, 1, 0))

    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. CURLY TEXTURED HAIR WITH SILVER-GREY FRONT HIGHLIGHTS + HIGH CURLY BUN
    # =========================================================================
    mb.set_part("hair_curls", bone="Head")
    # Rounded, softly clustered faceted curly hairline & crown puffs matching reference silhouette
    # (cx, cy, cz, rx, ry, rz, primary_col, alt_col, ry_rot, rx_rot)
    hair_puffs = [
        # Front hairline silver-grey salt-and-pepper curls framing forehead & temples
        ( 0.000, 1.608,  0.135, 0.095, 0.080, 0.082, HAIR_SILVER,       HAIR_SILVER_LIGHT, 0.2, 0.1),
        (-0.098, 1.584,  0.122, 0.092, 0.082, 0.082, HAIR_SILVER_LIGHT, HAIR_SILVER,       0.7, 0.3),
        ( 0.098, 1.584,  0.122, 0.092, 0.082, 0.082, HAIR_SILVER_LIGHT, HAIR_SILVER,      -0.7, 0.3),
        (-0.165, 1.515,  0.088, 0.084, 0.082, 0.080, HAIR_SILVER,       HAIR_MID,          1.1, 0.2),
        ( 0.165, 1.515,  0.088, 0.084, 0.082, 0.080, HAIR_SILVER,       HAIR_MID,         -1.1, 0.2),
        (-0.188, 1.434,  0.052, 0.072, 0.076, 0.070, HAIR_MID,          HAIR_SILVER,       0.4, 0.5),
        ( 0.188, 1.434,  0.052, 0.072, 0.076, 0.070, HAIR_MID,          HAIR_SILVER,      -0.4, 0.5),

        # Upper crown puffs (soft rounded dome transitioning from silver-grey to mocha brown)
        ( 0.000, 1.648,  0.020, 0.135, 0.098, 0.128, HAIR_SILVER,       HAIR_MID,          0.5, 0.2),
        (-0.120, 1.608,  0.002, 0.112, 0.098, 0.110, HAIR_MID,          HAIR_SILVER,       1.3, 0.4),
        ( 0.120, 1.608,  0.002, 0.112, 0.098, 0.110, HAIR_MID,          HAIR_SILVER,      -1.3, 0.4),
        ( 0.000, 1.628, -0.095, 0.136, 0.110, 0.125, HAIR_MID,          HAIR_DARK,         0.9, 0.1),

        # Side & rear curly hair volume wrapping smoothly behind ears & down to nape
        (-0.172, 1.505, -0.055, 0.108, 0.104, 0.108, HAIR_MID,          HAIR_DARK,         0.6, 0.3),
        ( 0.172, 1.505, -0.055, 0.108, 0.104, 0.108, HAIR_MID,          HAIR_DARK,        -0.6, 0.3),
        (-0.160, 1.380, -0.100, 0.104, 0.102, 0.105, HAIR_DARK,         HAIR_MID,          1.5, 0.2),
        ( 0.160, 1.380, -0.100, 0.104, 0.102, 0.105, HAIR_DARK,         HAIR_MID,         -1.5, 0.2),
        (-0.118, 1.285, -0.118, 0.094, 0.086, 0.096, HAIR_DARK,         HAIR_DARK,         0.8, 0.4),
        ( 0.118, 1.285, -0.118, 0.094, 0.086, 0.096, HAIR_DARK,         HAIR_DARK,        -0.8, 0.4),
        ( 0.000, 1.460, -0.145, 0.134, 0.124, 0.122, HAIR_DARK,         HAIR_MID,          0.3, 0.5),
        ( 0.000, 1.318, -0.148, 0.124, 0.108, 0.112, HAIR_DARK,         HAIR_DARK,         1.1, 0.2),
    ]
    for (cx, cy, cz, rx, ry, rz, c1, c2, ry_r, rx_r) in hair_puffs:
        mb.puff(V(cx, cy, cz), rx, ry, rz, c1, rot_y=ry_r, rot_x=rx_r, alt_color=c2)

    # Big chunky high curly bun at the upper back of head (prominent in all 4 views!)
    mb.set_part("hair_bun", bone="Head")
    bun_puffs = [
        ( 0.000, 1.595, -0.305, 0.152, 0.146, 0.145, HAIR_DARK, HAIR_MID,  0.35, 0.20),
        ( 0.000, 1.682, -0.285, 0.106, 0.096, 0.102, HAIR_MID,  HAIR_DARK, 1.10, 0.40),
        ( 0.000, 1.495, -0.318, 0.104, 0.096, 0.100, HAIR_DARK, HAIR_DARK, 0.70, 0.15),
        (-0.082, 1.595, -0.312, 0.102, 0.102, 0.100, HAIR_DARK, HAIR_MID,  1.45, 0.55),
        ( 0.082, 1.595, -0.312, 0.102, 0.102, 0.100, HAIR_DARK, HAIR_MID, -1.45, 0.55),
        ( 0.000, 1.585, -0.398, 0.098, 0.102, 0.094, HAIR_DARK, HAIR_MID,  0.90, 0.30),
    ]
    for (cx, cy, cz, rx, ry, rz, c1, c2, ry_r, rx_r) in bun_puffs:
        mb.puff(V(cx, cy, cz), rx, ry, rz, c1, rot_y=ry_r, rot_x=rx_r, alt_color=c2)

    # =========================================================================
    # 3. EARS + CHUNKY GOLD HOOP EARRINGS (iconic detail from reference!)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.198
        x_out = side * 0.246
        y0, y1 = 1.300, 1.402
        z0, z1 = -0.018, 0.056
        p_out_b = V(x_out, y0 + 0.015, z0 + 0.012)
        p_out_f = V(x_out, y0 + 0.015, z1 - 0.010)
        p_out_t = V(x_out, y1 - 0.015, (z0 + z1) * 0.5)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_out_t, p_out_f], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_out_b, p_out_t], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_out_f, p_out_b], SKIN_SHADE, out=(0, -1, 0))
        mb.face([p_out_b, p_out_f, p_out_t], SKIN, out=(side, 0, 0))

    mb.set_part("earrings", bone="Head")
    # Chunky 8-sided circular gold hoop earrings hugging each earlobe
    n_hoop = 8
    r_out = 0.036
    r_in = 0.015
    for side in (-1, 1):
        x_e0 = side * 0.228
        x_e1 = side * 0.256
        xa, xb = min(x_e0, x_e1), max(x_e0, x_e1)
        cy = 1.280
        cz = 0.018
        out_a, out_b, in_a, in_b = [], [], [], []
        for k in range(n_hoop):
            a = math.pi / n_hoop + 2.0 * math.pi * k / n_hoop
            ca, sa = math.cos(a), math.sin(a)
            out_a.append(V(xa, cy + r_out * sa, cz + r_out * ca))
            out_b.append(V(xb, cy + r_out * sa, cz + r_out * ca))
            in_a.append(V(xa, cy + r_in * sa, cz + r_in * ca))
            in_b.append(V(xb, cy + r_in * sa, cz + r_in * ca))
        for k in range(n_hoop):
            kn = (k + 1) % n_hoop
            a_mid = math.pi / n_hoop + 2.0 * math.pi * (k + 0.5) / n_hoop
            rad_dir = V(0.0, math.sin(a_mid), math.cos(a_mid))
            col = GOLD if math.sin(a_mid) >= -0.25 else GOLD_SHADE
            mb.face([out_a[k], out_a[kn], in_a[kn], in_a[k]], col, out=(-1, 0, 0))
            mb.face([in_b[k], in_b[kn], out_b[kn], out_b[k]], col, out=(1, 0, 0))
            mb.face([out_a[k], out_b[k], out_b[kn], out_a[kn]], col, out=rad_dir)
            mb.face([in_b[k], in_a[k], in_a[kn], in_b[kn]], GOLD_SHADE, out=-rad_dir)

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.214
    for side in (-1, 1):
        cx = side * 0.068
        cy = 1.390
        rx = 0.020
        ry = 0.048
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
    # 5. NECK (6-sided warm brown skin cylinder tucked cleanly inside scarf)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.110, 0.008, 0.072, 0.066, n=6, phase=math.pi / 6)
    neck_r1 = oval_ring(0.0, 1.215, 0.010, 0.068, 0.064, n=6, phase=math.pi / 6)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 6. OLIVE GREEN BOXY UTILITY JACKET (buttoned front, patch pockets)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    jy0, jy1 = 0.642, 1.135
    jx_bot, jx_top = 0.216, 0.194
    jz_fb, jz_ft = 0.134, 0.124
    jz_bb, jz_bt = -0.124, -0.114

    j_bot = [
        V(-jx_bot, jy0,  jz_fb),
        V( jx_bot, jy0,  jz_fb),
        V( jx_bot, jy0,  jz_bb),
        V(-jx_bot, jy0,  jz_bb),
    ]
    j_top = [
        V(-jx_top, jy1,  jz_ft),
        V( jx_top, jy1,  jz_ft),
        V( jx_top, jy1,  jz_bt),
        V(-jx_top, jy1,  jz_bt),
    ]
    mb.loft([j_bot, j_top], JACKET, cap_bottom=True, cap_top=True,
            bot_color=JACKET_SHADE, top_color=JACKET)

    # Center front placket seam strip + 3 small dark utility buttons
    z_pl = 0.132
    mb.face([
        V(-0.016, jy0 + 0.002, jz_fb + 0.002),
        V( 0.016, jy0 + 0.002, jz_fb + 0.002),
        V( 0.016, jy1 - 0.010, jz_ft + 0.002),
        V(-0.016, jy1 - 0.010, jz_ft + 0.002),
    ], JACKET_SHADE, out=(0, 0, 1))

    for by in (1.015, 0.900, 0.785):
        t = (by - jy0) / (jy1 - jy0)
        bz = jz_fb + (jz_ft - jz_fb) * t
        mb.box(-0.010, 0.010, by - 0.010, by + 0.010, bz, bz + 0.010, BUTTON, skip=("back",))

    # Two chunky lower front utility patch pockets
    for side in (-1, 1):
        px0 = min(side * 0.056, side * 0.186)
        px1 = max(side * 0.056, side * 0.186)
        mb.box(px0, px1, 0.688, 0.838, 0.128, 0.150, JACKET_POCKET, skip=("back",))
        mb.box(px0 - 0.002, px1 + 0.002, 0.818, 0.842, 0.130, 0.154, JACKET_SHADE, skip=("back",))

    # =========================================================================
    # 7. CHUNKY TERRACOTTA SCARF WRAP + HANGING END WITH FRINGE
    # =========================================================================
    mb.set_part("scarf_wrap", bone="Torso")
    # Cozy layered 10-sided faceted wrap around neck & upper shoulders
    # Ring specs: (y_base, y_tilt_z, cz, rx, rz)
    n_sc = 10
    sc_rings_spec = [
        (1.068, -0.020,  0.002, 0.214, 0.195),  # 0: lower drape over shoulders
        (1.115, -0.025,  0.006, 0.236, 0.214),  # 1: lower belly bulge
        (1.158, -0.012,  0.008, 0.218, 0.200),  # 2: fold crease between loops
        (1.196, -0.008,  0.012, 0.228, 0.208),  # 3: upper cozy wrap bulge
        (1.236, -0.004,  0.010, 0.184, 0.172),  # 4: upper collar edge under chin
        (1.215,  0.000,  0.008, 0.118, 0.110),  # 5: inner tuck around neck
    ]
    sc_rings = []
    for (yb, yt, cz, rx, rz) in sc_rings_spec:
        ring = []
        for k in range(n_sc):
            a = math.pi / n_sc + 2.0 * math.pi * k / n_sc
            ca = math.cos(a)
            sa = math.sin(a)
            # Subtle organic wrap undulation so it looks hand-wrapped rather than mechanical
            bump = 1.0 + 0.045 * math.sin(2.0 * a + 0.6)
            px = rx * sa * bump
            pz = cz + rz * ca * bump
            py = yb + yt * ca + 0.012 * math.sin(a - 0.5)
            ring.append(V(px, py, pz))
        sc_rings.append(ring)

    def scarf_wrap_col(i, k):
        if i == 2:
            return SCARF_DARK
        if i == 4:
            return SCARF_DARK
        if (i + k) % 3 == 0:
            return SCARF_LIGHT
        return SCARF

    mb.loft(sc_rings, scarf_wrap_col, cap_bottom=True, cap_top=False, bot_color=SCARF_DARK)

    # Front-left diagonal knot/drape ridge feeding seamlessly into the hanging tail
    knot_r0 = [
        V(-0.015, 1.178, 0.170),
        V( 0.135, 1.196, 0.165),
        V( 0.135, 1.196, 0.224),
        V(-0.015, 1.178, 0.228),
    ]
    knot_r1 = [
        V(-0.005, 1.102, 0.160),
        V( 0.142, 1.116, 0.155),
        V( 0.142, 1.116, 0.214),
        V(-0.005, 1.102, 0.218),
    ]
    mb.loft([knot_r1, knot_r0], SCARF_LIGHT, cap_bottom=True, cap_top=True,
            bot_color=SCARF_DARK, top_color=SCARF)

    # Hanging scarf end (weighted across Torso -> Scarf_Top -> Scarf_Tip for smooth cloth wave!)
    mb.set_part("scarf_tail")
    # Positioned slightly left-of-center on front (+X = 0.018..0.132) so it drapes clearly
    # beside the jacket buttons, matching the reference 3/4 silhouette & clearing the tote bag!
    tail_specs = [
        # (y,     x0,     x1,     z_back, z_front, weights_dict)
        (1.115,  0.018,  0.128,  0.152,  0.194, {"Torso": 0.75, "Scarf_Top": 0.25}),
        (1.020,  0.020,  0.132,  0.148,  0.192, {"Scarf_Top": 1.0}),
        (0.925,  0.022,  0.136,  0.146,  0.188, {"Scarf_Top": 0.80, "Scarf_Tip": 0.20}),
        (0.848,  0.024,  0.140,  0.144,  0.184, {"Scarf_Top": 0.35, "Scarf_Tip": 0.65}),
        (0.775,  0.024,  0.142,  0.142,  0.180, {"Scarf_Tip": 1.0}),
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
        # Upper folded band contrast matching the reference scarf layering
        if i in (0, 1):
            return SCARF if k != 2 else SCARF_DARK
        if i == 2:
            return SCARF_DARK if k == 0 else SCARF
        return SCARF_LIGHT if (i == 3 and k == 0) else SCARF

    mb.loft(tail_rings, tail_col, cap_bottom=False, cap_top=True,
            top_color=SCARF_DARK, ring_weights=tail_weights)

    # Subtle folded horizontal cuff/overlap ridge halfway down the hanging scarf (iconic reference detail!)
    mb.set_bone({"Scarf_Top": 0.45, "Scarf_Tip": 0.55})
    mb.box(0.019, 0.141, 0.865, 0.905, 0.180, 0.198, SCARF_LIGHT, skip=("back",))
    mb.box(0.019, 0.141, 0.855, 0.867, 0.178, 0.195, SCARF_DARK, skip=("back", "top"))

    # Crisp faceted fringe tassels along the bottom edge of the hanging scarf (100% Scarf_Tip)
    mb.set_bone("Scarf_Tip")
    n_fringe = 5
    fx_start, fx_end = 0.024, 0.144
    fw = (fx_end - fx_start) / n_fringe
    for fi in range(n_fringe):
        xa = fx_start + fi * fw + 0.0025
        xb = fx_start + (fi + 1) * fw - 0.0025
        y_tip = 0.652 + (0.006 if fi % 2 == 1 else 0.0)
        col = SCARF_FRINGE if fi % 2 == 0 else SCARF_DARK
        mb.box(xa, xb, y_tip, 0.718, 0.146, 0.175, col, skip=("top",))

    # =========================================================================
    # 8. SLEEVES (Arm_R bent holding/tucking grocery bag; Arm_L free walking swing)
    # =========================================================================
    mb.set_part("sleeves")

    def build_bent_sleeve(p_sh, p_el, p_wr, bone_name, cuff_flare=1.08):
        mb.set_bone(bone_name)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def aligned_ring(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            u = u.normalized()
            v = axis.cross(u).normalized()
            # 6-sided chunky sleeve for softer faceted jacket volume
            pts = []
            for k in range(6):
                a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
                pts.append(ctr + u * (rx * math.sin(a)) + v * (rperp * math.cos(a)))
            return pts

        ax_mid = (ax1 + ax2).normalized()
        r_sh  = aligned_ring(p_sh, ax1, 0.076, 0.084)
        r_u   = aligned_ring(p_sh.lerp(p_el, 0.58), ax1, 0.086, 0.090)
        r_el  = aligned_ring(p_el, ax_mid, 0.090, 0.094)
        r_f   = aligned_ring(p_el.lerp(p_wr, 0.72), ax2, 0.088 * cuff_flare, 0.090 * cuff_flare)
        r_cuf = aligned_ring(p_wr, ax2, 0.084 * cuff_flare, 0.086 * cuff_flare)
        r_in  = aligned_ring(p_wr - ax2 * 0.008, ax2, 0.062, 0.064)
        mb.loft([r_sh, r_u, r_el, r_f, r_cuf, r_in],
                lambda i, k: JACKET_SHADE if i == 4 else JACKET,
                cap_bottom=False, cap_top=True, top_color=JACKET_SHADE)

    # Right arm (Arm_R, -X): passes through grocery tote strap & bends forward to cradle front of tote!
    p_r_sh = V(-0.172, 1.055, -0.005)
    p_r_el = V(-0.278, 0.870, -0.048)
    p_r_wr = V(-0.236, 0.836,  0.092)
    build_bent_sleeve(p_r_sh, p_r_el, p_r_wr, "Arm_R", cuff_flare=1.08)

    # Left arm (Arm_L, +X): relaxed gentle bend at left side, free to swing while walking
    p_l_sh = V(0.172, 1.055,  0.005)
    p_l_el = V(0.258, 0.865, -0.004)
    p_l_wr = V(0.254, 0.726,  0.082)
    build_bent_sleeve(p_l_sh, p_l_el, p_l_wr, "Arm_L", cuff_flare=1.04)

    # =========================================================================
    # 9. HANDS (warm brown chunky low-poly mittens)
    # =========================================================================
    mb.set_part("hands")

    def build_hand(p_el, p_wr, bone_name):
        mb.set_bone(bone_name)
        ax = (p_wr - p_el).normalized()
        u = V(1.0, 0.0, 0.0) - ax * ax.x
        u = u.normalized()
        v = ax.cross(u).normalized()
        stations = [
            (-0.005, 0.046, 0.048),
            ( 0.056, 0.058, 0.062),
            ( 0.104, 0.042, 0.044),
        ]
        rings = []
        for (dist, ru, rv) in stations:
            c = p_wr + ax * dist
            rings.append([
                c + u * (-ru) + v * ( rv),
                c + u * ( ru) + v * ( rv),
                c + u * ( ru) + v * (-rv),
                c + u * (-ru) + v * (-rv),
            ])
        mb.loft(rings, SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    build_hand(p_r_el, p_r_wr, "Arm_R")
    build_hand(p_l_el, p_l_wr, "Arm_L")

    # =========================================================================
    # 10. CANVAS GROCERY TOTE BAG + FISH GRAPHIC + LEAFY GREENS (bone Bag)
    # =========================================================================
    mb.set_part("grocery_bag", bone="Bag")
    # Slung over right shoulder (-X), nestled warmly at right hip/side, tilted back ~16 deg
    bag_tilt = math.radians(-16.0)
    ct, st = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_orig = V(-0.276, 0.682, -0.142)

    def bag_pt(lx, ly, lz):
        ry = ly * ct - lz * st
        rz = ly * st + lz * ct
        return V(bag_orig.x + lx, bag_orig.y + ry, bag_orig.z + rz)

    # Tapered canvas tote with faceted gusset bottom corners matching reference
    bag_stations = [
        # (ly,    x_in,   x_out,  z_back, z_front)
        (-0.158,  0.052, -0.070, -0.150,  0.150),  # 0: bottom flat base
        (-0.110,  0.068, -0.090, -0.184,  0.184),  # 1: full lower gusset belly
        ( 0.152,  0.060, -0.078, -0.190,  0.190),  # 2: top canvas rim
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

    mb.loft(bag_rings, bag_col, cap_bottom=True, cap_top=False, bot_color=BAG_SHADE)

    # Recessed dark canvas interior opening at top of tote
    top_outer = bag_rings[-1]
    top_inner = [
        bag_pt(-0.056, 0.152, -0.168),
        bag_pt( 0.040, 0.152, -0.168),
        bag_pt( 0.040, 0.152,  0.168),
        bag_pt(-0.056, 0.152,  0.168),
    ]
    top_deep = [
        bag_pt(-0.052, 0.100, -0.160),
        bag_pt( 0.036, 0.100, -0.160),
        bag_pt( 0.036, 0.100,  0.160),
        bag_pt(-0.052, 0.100,  0.160),
    ]
    for k in range(4):
        kn = (k + 1) % 4
        mb.face([top_outer[k], top_outer[kn], top_inner[kn], top_inner[k]], BAG, out=(0, 1, 0))
        mb.face([top_inner[k], top_inner[kn], top_deep[kn], top_deep[k]], BAG_INNER, out=(0, 0.2, 0))
    mb.face(top_deep, BAG_INNER, out=(0, 1, 0))

    # Iconic stylized grey fish graphic flush-mounted on outer (-X) canvas face!
    mb.set_part("bag_fish", bone="Bag")

    def fish_pt(ly, lz):
        t = (ly - (-0.110)) / (0.152 - (-0.110))
        xo = -0.090 + (-0.078 - (-0.090)) * t - 0.0028
        return bag_pt(xo, ly, lz)

    # Fish facing forward (+Z) with plump body, small dorsal fin, and forked tail (-Z)
    f_nose   = fish_pt( 0.004,  0.112)
    f_top_f  = fish_pt( 0.038,  0.056)
    f_top_m  = fish_pt( 0.046, -0.006)
    f_dorsal = fish_pt( 0.060, -0.018)
    f_top_b  = fish_pt( 0.028, -0.058)
    f_pinch_t = fish_pt( 0.013, -0.078)
    f_tail_t = fish_pt( 0.048, -0.124)
    f_tail_n = fish_pt( 0.000, -0.102)
    f_tail_b = fish_pt(-0.048, -0.124)
    f_pinch_b = fish_pt(-0.013, -0.078)
    f_bot_b  = fish_pt(-0.028, -0.054)
    f_bot_m  = fish_pt(-0.042,  0.002)
    f_bot_f  = fish_pt(-0.034,  0.058)

    out_fish = V(-1.0, 0.0, 0.0)
    mb.face([f_nose, f_top_f, f_bot_f], FISH, out=out_fish)
    mb.face([f_top_f, f_top_m, f_bot_m, f_bot_f], FISH, out=out_fish)
    mb.face([f_top_m, f_top_b, f_bot_b, f_bot_m], FISH, out=out_fish)
    mb.face([f_top_m, f_dorsal, f_top_b], FISH, out=out_fish)
    mb.face([f_top_b, f_pinch_t, f_pinch_b, f_bot_b], FISH, out=out_fish)
    mb.face([f_pinch_t, f_tail_t, f_tail_n, f_pinch_b], FISH, out=out_fish)
    mb.face([f_pinch_b, f_tail_n, f_tail_b], FISH, out=out_fish)

    # Wide cream canvas shoulder strap framing Arm_R cleanly with ZERO sleeve clipping!
    # Front strap sweeps forward cleanly in front of upper sleeve; rear strap drops behind sleeve in front of greens.
    mb.set_part("bag_strap", bone="Bag")
    strap_loop = [
        bag_pt(-0.010, 0.140,  0.145),  # front attachment at top-front of tote
        V(-0.278, 0.905,  0.105),       # rising cleanly in front of forearm/upper sleeve
        V(-0.252, 1.015,  0.098),       # curving up cleanly clear of front shoulder sleeve
        V(-0.205, 1.118,  0.025),       # top front of shoulder (tucks neatly under scarf!)
        V(-0.202, 1.122, -0.045),       # top rear of shoulder
        V(-0.246, 1.040, -0.125),       # curving down cleanly behind upper sleeve
        V(-0.272, 0.942, -0.168),       # descending cleanly behind elbow, in front of greens
        bag_pt(-0.010, 0.140, -0.088),  # rear attachment slightly forward of back edge so greens poke out behind!
    ]
    strap_norms = [
        V(-0.9, 0.0,  0.4),
        V(-0.7, 0.0,  0.7),
        V(-0.6, 0.2,  0.8),
        V(-0.3, 0.9,  0.3),
        V(-0.3, 0.9, -0.3),
        V(-0.6, 0.3, -0.7),
        V(-0.8, 0.1, -0.6),
        V(-0.9, 0.0, -0.4),
    ]
    mb.ribbon_path(strap_loop, strap_norms, half_w=0.028, half_t=0.010, color=BAG_STRAP)

    # Lush upright cluster of chunky low-poly leafy greens poking out behind the rear strap!
    mb.set_part("groceries_greens", bone="Bag")

    def build_leaf(base_local, dir_local, length, w_mid, thick, col_main, col_tip):
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

        stations = [
            (0.00, 0.012, 0.010),
            (0.32, w_mid * 0.72, thick * 0.95),
            (0.68, w_mid, thick),
            (0.90, w_mid * 0.78, thick * 0.80),
            (1.00, 0.014, 0.010),
        ]
        rings = []
        for (t, rw, rt) in stations:
            c = b_pt.lerp(t_pt, t)
            bend = u * (0.016 * (t * t))
            rings.append([
                c + bend - u * rw + v * rt,
                c + bend + u * rw + v * rt,
                c + bend + u * rw - v * rt,
                c + bend - u * rw - v * rt,
            ])
        mb.loft(rings, lambda i, k: col_tip if i >= 2 else col_main,
                cap_bottom=False, cap_top=True, top_color=col_tip)

    leaf_specs = [
        # (base_local, dir_local, length, w_mid, thick, col_main, col_tip)
        ((-0.018, 0.118, -0.118), (-0.14, 0.96, -0.22), 0.258, 0.036, 0.022, LEAF_MID,   LEAF_LIGHT),
        (( 0.012, 0.118, -0.135), ( 0.06, 0.93, -0.34), 0.242, 0.034, 0.020, LEAF_DARK,  LEAF_MID),
        ((-0.032, 0.118, -0.090), (-0.26, 0.96, -0.08), 0.232, 0.034, 0.022, LEAF_LIGHT, LEAF_LIGHT),
        (( 0.016, 0.118, -0.095), ( 0.10, 0.98, -0.12), 0.238, 0.032, 0.020, LEAF_MID,   LEAF_LIGHT),
        ((-0.012, 0.118, -0.155), (-0.12, 0.88, -0.44), 0.215, 0.033, 0.020, LEAF_MID,   LEAF_LIGHT),
        ((-0.022, 0.118, -0.068), (-0.22, 0.97,  0.04), 0.205, 0.030, 0.019, LEAF_DARK,  LEAF_MID),
        (( 0.000, 0.118, -0.110), (-0.02, 0.99, -0.08), 0.272, 0.035, 0.022, LEAF_MID,   LEAF_LIGHT),
    ]
    for (bl, dl, ln, wm, th, cm, ct_c) in leaf_specs:
        build_leaf(bl, dl, ln, wm, th, cm, ct_c)

    # =========================================================================
    # 11. SLATE-BLUE CROPPED TROUSERS WITH LIGHT-SLATE ROLLED CUFFS
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.188, 0.188, 0.545, 0.678, -0.104, 0.104, PANTS, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t  = side * 0.010
        x_out_t = side * 0.186
        x_in_b  = side * 0.062
        x_out_b = side * 0.232
        rz_t = 0.098
        rz_b = 0.094
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

    # Thick turned-up light-slate trouser cuffs (iconic detail from reference!)
    mb.set_part("pant_cuffs")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_c  = side * 0.052
        x_out_c = side * 0.244
        xa, xb = min(x_in_c, x_out_c), max(x_in_c, x_out_c)
        rz_c = 0.106
        r_cb = [
            V(xa, 0.194,  rz_c),
            V(xb, 0.194,  rz_c),
            V(xb, 0.194, -rz_c),
            V(xa, 0.194, -rz_c),
        ]
        r_ct = [
            V(xa, 0.268,  rz_c),
            V(xb, 0.268,  rz_c),
            V(xb, 0.268, -rz_c),
            V(xa, 0.268, -rz_c),
        ]
        mb.loft([r_cb, r_ct], CUFF, cap_bottom=True, cap_top=True,
                bot_color=CUFF_SHADE, top_color=CUFF_SHADE)

    # =========================================================================
    # 12. ANKLES (warm brown skin showing between rolled cuffs & loafers)
    # =========================================================================
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.148
        mb.box(cx - 0.044, cx + 0.044, 0.118, 0.204, -0.046, 0.046, SKIN, skip=("top", "bottom"))

    # =========================================================================
    # 13. CREAM CHUNKY SLIP-ON LOAFERS WITH TAUPE-GREY SOLES
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.148
        w = 0.070
        w_toe = 0.058
        z_heel = -0.092
        z_mid  =  0.062
        z_toe  =  0.162
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_toe_top = 0.082
        y_collar  = 0.132

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

        p_bl_h = V(cx - w,     y_sole1, z_heel)
        p_br_h = V(cx + w,     y_sole1, z_heel)
        p_bl_t = V(cx - w_toe, y_sole1, z_toe)
        p_br_t = V(cx + w_toe, y_sole1, z_toe)

        p_tl_h = V(cx - w * 0.88, y_collar, z_heel + 0.012)
        p_tr_h = V(cx + w * 0.88, y_collar, z_heel + 0.012)
        p_tl_m = V(cx - w * 0.88, y_collar, z_mid)
        p_tr_m = V(cx + w * 0.88, y_collar, z_mid)

        p_tl_t = V(cx - w_toe * 0.90, y_toe_top, z_toe - 0.014)
        p_tr_t = V(cx + w_toe * 0.90, y_toe_top, z_toe - 0.014)

        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], SHOE, out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], SHOE, out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], SHOE_VAMP, out=(0, 1, 0.5))
        mb.face([p_tl_m, p_tr_m, p_tr_h, p_tl_h], SHOE, out=(0, 1, 0))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], SHOE, out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h], SHOE, out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], SHOE, out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m], SHOE, out=(1, 0, 0))

        # Subtle loafer tongue/penny-strap accent on top of instep
        mb.box(cx - 0.044, cx + 0.044, y_collar - 0.008, y_collar + 0.008,
               z_mid - 0.018, z_mid + 0.018, SHOE_VAMP, skip=("bottom",))

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

        # Warm, bouncy everyday stroll
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

        # Crisp cuffed-trouser stride
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

        # Left arm (free arm) swings naturally in opposition to left leg
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.36 * s1, 0.0, 0.02 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm (bent arm cradling grocery tote) stays cozy & moves gently with bag
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.095 * s1 + 0.02, 0.0, -0.015 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Grocery tote bag trails with weighted pendulum sway & gentle hip bounce
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.062 * math.sin(phi - 0.60), 0.0, 0.024 * c1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        # 2-bone hanging scarf end with expressive overlapping cloth wave (always clear of jacket!)
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

        # Calm breathing & gentle weight shift
        pb_root = rig.pose.bones["Root"]
        root_pitch = -0.012
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (root_pitch, 0.022 * s1, 0.016 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * s2, 0.028 * s1, -0.015 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Friendly curious look around harbor/market
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * s2, 0.21 * s1, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs stay grounded
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm relaxed subtle breath drift
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.048 * s1, 0.0, 0.018 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm gently cradles grocery tote
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.028 * s2, 0.0, -0.012 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Grocery bag hangs calmly with slight weighted settle
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.022 * s2, 0.0, -0.018 * s1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Hanging scarf catches a soft harbor breeze with phase-delayed flutter
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
        (-1.68, math.radians(64)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (showing bun, hoop earring, tote fish & greens, scarf)
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
