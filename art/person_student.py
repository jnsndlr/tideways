# Builds an ultra-low-poly stylized college student with headphones, backpack, and stack of books in Blender
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_student.py)
# Saves art/person_student.blend, exports assets/models/person_student.glb (rigged + Walk & Idle cycles),
# renders art/person_student_preview.png, art/person_student_walk_preview.png, art/person_student_idle_preview.png,
# and outputs rendered videos art/person_student_walk.mp4 and art/person_student_idle.mp4.
#
# Strict triangle budget: <= 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.71 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_student.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_student.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_student_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_student_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_student_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_student_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_student_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN          = col_srgb(0.84, 0.59, 0.36)
SKIN_SHADE    = col_srgb(0.72, 0.48, 0.27)
EYE           = col_srgb(0.13, 0.13, 0.15)

HAIR_DARK     = col_srgb(0.32, 0.24, 0.20)
HAIR_MID      = col_srgb(0.40, 0.31, 0.26)

HP_MAIN       = col_srgb(0.96, 0.91, 0.83)
HP_SHADE      = col_srgb(0.85, 0.78, 0.69)

HOODIE        = col_srgb(0.92, 0.85, 0.75)
HOODIE_SHADE  = col_srgb(0.82, 0.74, 0.63)
PINE_GREEN    = col_srgb(0.30, 0.47, 0.35)

PACK          = col_srgb(0.34, 0.34, 0.41)
PACK_SHADE    = col_srgb(0.25, 0.25, 0.31)

BOOK_RED      = col_srgb(0.83, 0.44, 0.31)
BOOK_BLUE     = col_srgb(0.35, 0.52, 0.66)
BOOK_BROWN    = col_srgb(0.58, 0.45, 0.30)
BOOK_DARK     = col_srgb(0.24, 0.22, 0.21)
PAGES         = col_srgb(0.96, 0.92, 0.84)

PANTS         = col_srgb(0.35, 0.34, 0.38)
PANTS_SHADE   = col_srgb(0.26, 0.25, 0.29)
PANTS_POCKET  = col_srgb(0.41, 0.40, 0.45)

SHOE          = col_srgb(0.95, 0.89, 0.79)
SHOE_VAMP     = col_srgb(0.88, 0.81, 0.70)
SOLE          = col_srgb(0.76, 0.69, 0.59)


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

    def curl_cushion(self, base_pt, axis, depth, r_base, r_cap, aspect_y=1.0, phase=0.0,
                     color=HAIR_DARK, cap_color=None, scallop=0.10):
        """Chunky, non-spiky 5-sided beveled curl cushion (13 tris: 5 side quads + 3-tri flat cap)."""
        ax = axis.normalized()
        ref = V(0.0, 1.0, 0.0) if abs(ax.y) < 0.85 else V(0.0, 0.0, 1.0)
        u = ax.cross(ref).normalized()
        v = ax.cross(u).normalized()

        def ring5(ctr, rad, sc):
            pts = []
            for k in range(5):
                a = phase + 2.0 * math.pi * k / 5.0
                bump = 1.0 + sc * (1.0 if k % 2 == 0 else -0.65)
                pts.append(ctr + u * (rad * bump * math.cos(a)) + v * (rad * aspect_y * bump * math.sin(a)))
            return pts

        r0 = ring5(base_pt, r_base, scallop)
        r1 = ring5(base_pt + ax * depth, r_cap, scallop * 0.7)
        c_mid = base_pt + ax * (depth * 0.5)
        for k in range(5):
            kn = (k + 1) % 5
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            col = cap_color if (cap_color is not None and k % 2 == 0) else color
            self.face([p0, p1, p2, p3], col, out=(mid - c_mid))
        # Flat pentagonal outer cap = 1 quad + 1 tri = 3 tris (rounded chunky silhouette, zero spike!)
        cc = cap_color if cap_color is not None else color
        self.face([r1[0], r1[1], r1[2], r1[3]], cc, out=ax)
        self.face([r1[0], r1[3], r1[4]], cc, out=ax)


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD (6-sided stylized low-poly head, flat front face, 32 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 (330..30 deg) is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.210,  0.015, 0.155, 0.142),  # 0: chin/jaw
        (1.285,  0.020, 0.212, 0.198),  # 1: lower cheek
        (1.495,  0.016, 0.214, 0.200),  # 2: brow / forehead
        (1.615, -0.002, 0.165, 0.162),  # 3: crown inside curls/headband
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        if i == 2:
            return HAIR_DARK
        if i == 1:
            return SKIN if k in (4, 5, 0) else HAIR_DARK
        return HAIR_DARK if k in (1, 2, 3) else SKIN

    # Skip 4 back-of-skull quads completely enclosed inside rear curly hair clouds (-8 tris)
    hidden_head_quads = {(2, 1), (2, 2), (2, 3), (1, 2)}
    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            if (i, k) in hidden_head_quads:
                continue
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))
    rb = head_rings[0]
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[3], rb[4], rb[5], rb[0]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. NECK (4-sided short tapered cylinder, skip rear quad inside hood = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.110, 0.008, 0.072, 0.068, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.218, 0.010, 0.068, 0.064, n=4, phase=math.pi / 4.0)
    # phase=pi/4 -> k=1 is back (-Z, 135..225 deg), completely hidden inside folded hood
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 3. EYES (2 crisp vertical dark pill hexagons on flat front face, 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.196
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.392
        rx = 0.019
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
    # 4. VOLUMINOUS CURLY HAIR (4 chunky rounded 5-sided curl cushions = 52 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # Lush, non-spiky rounded afro-curly clouds hugging closely under the cream headband!
    # 1. Upper-back big rounded curly cloud (billowing smoothly behind crown & headphones)
    mb.curl_cushion(
        base_pt=V(0.0, 1.515, -0.025),
        axis=V(0.0, 0.14, -0.99),
        depth=0.250,
        r_base=0.222,
        r_cap=0.138,
        aspect_y=0.82,
        phase=math.pi / 2.0,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        scallop=0.06,
    )
    # 2. Lower-back billowing curly lobe (overlaps warmly with upper cloud for soft curly silhouette!)
    mb.curl_cushion(
        base_pt=V(0.0, 1.385, -0.065),
        axis=V(0.0, -0.14, -0.99),
        depth=0.255,
        r_base=0.214,
        r_cap=0.132,
        aspect_y=0.78,
        phase=-math.pi / 2.0,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        scallop=0.07,
    )
    # 3 & 4. Soft rounded front forehead/temple curly bangs puffs (hugging cleanly below headband!)
    for side in (-1, 1):
        mb.curl_cushion(
            base_pt=V(side * 0.048, 1.545, 0.038),
            axis=V(side * 0.42, 0.22, 0.88),
            depth=0.148,
            r_base=0.128,
            r_cap=0.080,
            aspect_y=0.80,
            phase=side * 0.35,
            color=HAIR_DARK,
            cap_color=HAIR_MID,
            scallop=0.07,
        )

    # =========================================================================
    # 5. OVER-EAR CREAM HEADPHONES (4-seg curved band 24 + 2x6-sided cups 32 = 56 tris)
    # =========================================================================
    mb.set_part("headphones", bone="Head")
    # Smooth 4-segment rounded dome arch hugging snugly onto the curls with zero peak or gap!
    band_stations = [
        # (cx,    cy,    cz,    norm_dir)
        ( 0.220, 1.438, 0.020, V( 0.98, 0.20, 0.0)),
        ( 0.172, 1.625, 0.020, V( 0.62, 0.78, 0.0)),
        ( 0.000, 1.672, 0.020, V( 0.00, 1.00, 0.0)),
        (-0.172, 1.625, 0.020, V(-0.62, 0.78, 0.0)),
        (-0.220, 1.438, 0.020, V(-0.98, 0.20, 0.0)),
    ]
    hw_z = 0.044  # half-width front-to-back (chunky stylized strap)
    ht   = 0.022  # half-thickness radially
    band_rings = []
    for (cx, cy, cz, nd) in band_stations:
        n = nd.normalized()
        c = V(cx, cy, cz)
        ring = [
            c + n * ht + V(0, 0,  hw_z),
            c + n * ht + V(0, 0, -hw_z),
            c - n * ht + V(0, 0, -hw_z),
            c - n * ht + V(0, 0,  hw_z),
        ]
        band_rings.append(ring)

    def band_col(i, k):
        return HP_MAIN if k == 0 else HP_SHADE

    mb.loft(band_rings, band_col, cap_bottom=False, cap_top=False, skip_k=(2,))

    # Two chunky 6-sided cream over-ear cups (skip inner cap tucked into head/hair)
    cup_r = 0.098
    cup_cy = 1.385
    cup_cz = 0.020
    for side in (-1, 1):
        x_in = side * 0.175
        x_out = side * 0.258
        r_in = []
        r_out = []
        for k in range(6):
            a = 2.0 * math.pi * k / 6.0
            dy = cup_r * math.sin(a)
            dz = cup_r * math.cos(a)
            r_in.append(V(x_in, cup_cy + dy, cup_cz + dz))
            r_out.append(V(x_out, cup_cy + dy * 0.88, cup_cz + dz * 0.88))
        mb.loft([r_in, r_out], HP_SHADE, cap_bottom=False, cap_top=True, top_color=HP_MAIN)

    # =========================================================================
    # 6. CREAM HOODIE TORSO + FOLDED REAR HOOD + PINE TREE EMBLEM (25 tris)
    # =========================================================================
    mb.set_part("hoodie", bone="Torso")
    jy0, jy1 = 0.652, 1.135
    jx_b, jx_t = 0.214, 0.192
    jz_fb, jz_ft = 0.130, 0.118
    jz_bb, jz_bt = -0.126, -0.114
    h_bot = [
        V(-jx_b, jy0, jz_fb),
        V( jx_b, jy0, jz_fb),
        V( jx_b, jy0, jz_bb),
        V(-jx_b, jy0, jz_bb),
    ]
    h_top = [
        V(-jx_t, jy1, jz_ft),
        V( jx_t, jy1, jz_ft),
        V( jx_t, jy1, jz_bt),
        V(-jx_t, jy1, jz_bt),
    ]
    mb.loft([h_bot, h_top], HOODIE, cap_bottom=True, cap_top=True,
            bot_color=HOODIE_SHADE, top_color=HOODIE)

    # Chunky folded hood draped behind/around neck (5 faces, skip bottom buried in torso = 10 tris)
    hd_bot = [
        V(-0.142, 1.118,  0.080),
        V( 0.142, 1.118,  0.080),
        V( 0.172, 1.105, -0.225),
        V(-0.172, 1.105, -0.225),
    ]
    hd_top = [
        V(-0.112, 1.192,  0.056),
        V( 0.112, 1.192,  0.056),
        V( 0.148, 1.235, -0.195),
        V(-0.148, 1.235, -0.195),
    ]
    mb.loft([hd_bot, hd_top], lambda i, k: HOODIE_SHADE if k == 0 else HOODIE,
            cap_bottom=False, cap_top=True, top_color=HOODIE_SHADE)

    # Stylized 3-tier forest-green pine tree print on hoodie front chest (3 tris!)
    # Positioned slightly higher so the full 3-tier pine tree shines cleanly above the book stack!
    tx = -0.015
    def tree_z(y):
        t = (y - jy0) / (jy1 - jy0)
        return jz_fb + (jz_ft - jz_fb) * t + 0.004
    tiers = [
        (1.028, 1.116, 0.040),
        (0.968, 1.062, 0.054),
        (0.905, 1.002, 0.066),
    ]
    for (yb, yt, hw) in tiers:
        mb.face([
            V(tx - hw, yb, tree_z(yb)),
            V(tx + hw, yb, tree_z(yb)),
            V(tx,      yt, tree_z(yt)),
        ], PINE_GREEN, out=(0, 0, 1))

    # =========================================================================
    # 7. DARK SLATE BACKPACK + SHOULDER STRAPS (16 + 8 = 24 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # 4-sided 3-ring rounded dome backpack (fuller lower-back profile matching reference = 16 tris)
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.680, 0.164, -0.122, -0.278),  # sturdy full lower base
        (0.925, 0.184, -0.118, -0.312),  # rounded upper-mid fullness
        (1.102, 0.144, -0.114, -0.218),  # soft tapered top dome
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
            cap_bottom=True, cap_top=True, bot_color=PACK_SHADE, top_color=PACK, skip_k=(0,))

    # Two dark charcoal backpack straps curving cleanly over the shoulders & chest (8 tris)
    for side in (-1, 1):
        xa_t = min(side * 0.116, side * 0.164)
        xb_t = max(side * 0.116, side * 0.164)
        xa_b = min(side * 0.132, side * 0.180)
        xb_b = max(side * 0.132, side * 0.180)
        # Shoulder top strap quad
        mb.face([
            V(xa_t, 1.142, -0.122),
            V(xb_t, 1.142, -0.122),
            V(xb_t, 1.142,  0.124),
            V(xa_t, 1.142,  0.124),
        ], PACK, out=(0, 1, 0))
        # Front chest strap quad gently angling outward toward underarm
        mb.face([
            V(xa_b, 0.895, 0.132),
            V(xb_b, 0.895, 0.132),
            V(xb_t, 1.142, 0.124),
            V(xa_t, 1.142, 0.124),
        ], PACK, out=(0, 0, 1))

    # =========================================================================
    # 8. BENT HOODIE SLEEVES + CHUNKY HANDS CARRYING BOOKS (32 + 16 = 48 tris)
    # =========================================================================
    mb.set_part("sleeves")

    def build_bent_sleeve(p_sh, p_el, p_wr, bone_name):
        mb.set_bone(bone_name)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def ring4(ctr, axis, rx, rperp):
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
        r_sh = ring4(p_sh, ax1, 0.074, 0.082)
        r_el = ring4(p_el, ax_mid, 0.088, 0.092)
        r_wr = ring4(p_wr, ax2, 0.074, 0.078)
        mb.loft([r_sh, r_el, r_wr], lambda i, k: HOODIE_SHADE if k == 2 else HOODIE,
                cap_bottom=False, cap_top=False)

    # Both arms bend warmly down-out to elbows, then forward-in to cradle the stack of books
    p_l_sh = V( 0.172, 1.062,  0.002)
    p_l_el = V( 0.268, 0.858,  0.015)
    p_l_wr = V( 0.168, 0.808,  0.195)
    build_bent_sleeve(p_l_sh, p_l_el, p_l_wr, "Arm_L")

    p_r_sh = V(-0.172, 1.062,  0.002)
    p_r_el = V(-0.268, 0.858,  0.015)
    p_r_wr = V(-0.168, 0.808,  0.195)
    build_bent_sleeve(p_r_sh, p_r_el, p_r_wr, "Arm_R")

    # Warm brown chunky hands cradling the sides/front-corners of the book stack (8 tris x 2 = 16 tris)
    mb.set_part("hands")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        # Palm sits snugly against book stack outer side (x ≈ ±0.125), fingers curl forward to z ≈ 0.305
        x_in  = side * 0.118
        x_out = side * 0.205
        xa, xb = min(x_in, x_out), max(x_in, x_out)
        # Skip wrist back (inside sleeve) and inner palm face (flush against books)
        inner_skip = "left" if side > 0 else "right"
        mb.box(
            xa, xb,
            0.742, 0.848,
            0.185, 0.302,
            {"default": SKIN, "bottom": SKIN_SHADE},
            skip=("back", inner_skip),
        )

    # =========================================================================
    # 9. STACK OF 3 BOOKS (bottom brown, middle blue, top terracotta = 24 tris)
    # =========================================================================
    mb.set_part("books", bone="Books")
    # Held snugly across chest between both hands (skip hidden back face against chest + touching faces)
    # Bottom book: warm olive-brown cover + dark bottom shadow (8 tris)
    mb.box(
        -0.126, 0.126,
        0.742, 0.816,
        0.155, 0.322,
        {"front": BOOK_BROWN, "left": BOOK_BROWN, "right": BOOK_BROWN, "bottom": BOOK_DARK},
        skip=("top", "back"),
    )
    # Middle book: slate-blue cover (top + front spine) with crisp cream pages on sides (8 tris)
    mb.box(
        -0.132, 0.132,
        0.816, 0.896,
        0.155, 0.338,
        {"front": BOOK_BLUE, "top": BOOK_BLUE, "left": PAGES, "right": PAGES},
        skip=("bottom", "back"),
    )
    # Top book: terracotta/rust-orange cover on top & front edge, cream pages on sides (8 tris)
    mb.box(
        -0.114, 0.114,
        0.896, 0.958,
        0.162, 0.312,
        {"front": BOOK_RED, "top": BOOK_RED, "left": PAGES, "right": PAGES},
        skip=("bottom", "back"),
    )

    # =========================================================================
    # 10. DARK CHARCOAL CARGO PANTS + SIDE CARGO POCKETS (8 + 20 + 16 = 44 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.186, 0.186, 0.548, 0.672, -0.105, 0.105, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.186
        x_in_b, x_out_b = side * 0.056, side * 0.232
        rz_t, rz_b = 0.098, 0.100
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.125,  rz_b),
            V(max(x_in_b, x_out_b), 0.125,  rz_b),
            V(max(x_in_b, x_out_b), 0.125, -rz_b),
            V(min(x_in_b, x_out_b), 0.125, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

        # Chunky watertight wedge cargo pocket on outer thigh (4 quads = 8 tris per leg)
        # Outer leg surface linearly interpolates from x_out_t at y=0.585 to x_out_b at y=0.125
        def leg_x_out(y):
            t = (0.585 - y) / (0.585 - 0.125)
            return x_out_t + (x_out_b - x_out_t) * t

        py_b, py_t = 0.305, 0.485
        pz_b, pz_f = -0.068, 0.068
        xo_b = leg_x_out(py_b)
        xo_t = leg_x_out(py_t)
        depth = side * 0.032

        p_in_tb  = V(xo_t,         py_t, pz_b)
        p_in_tf  = V(xo_t,         py_t, pz_f)
        p_in_bb  = V(xo_b,         py_b, pz_b)
        p_in_bf  = V(xo_b,         py_b, pz_f)
        p_out_tb = V(xo_t + depth, py_t - 0.008, pz_b)
        p_out_tf = V(xo_t + depth, py_t - 0.008, pz_f)
        p_out_bb = V(xo_b + depth * 0.72, py_b + 0.012, pz_b)
        p_out_bf = V(xo_b + depth * 0.72, py_b + 0.012, pz_f)

        # Outer face, darker top flap, front edge, back edge (bottom merges seamlessly back into leg)
        mb.face([p_out_bb, p_out_bf, p_out_tf, p_out_tb], PANTS_POCKET, out=(side, 0, 0))
        mb.face([p_in_tb, p_in_tf, p_out_tf, p_out_tb],   PANTS_SHADE,  out=(0, 1, 0))
        mb.face([p_in_bf, p_out_bf, p_out_tf, p_in_tf],   PANTS_POCKET, out=(0, 0, 1))
        mb.face([p_out_bb, p_in_bb, p_in_tb, p_out_tb],   PANTS_POCKET, out=(0, 0, -1))

    # =========================================================================
    # 11. CHUNKY CREAM SNEAKERS / LOAFERS (14 tris x 2 = 28 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.144
        w = 0.070
        w_toe = 0.058
        z_heel = -0.092
        z_mid  =  0.062
        z_toe  =  0.168
        y_bot  =  0.000
        y_toe  =  0.072
        y_col  =  0.136

        p_bl_h = V(cx - w,     y_bot, z_heel)
        p_br_h = V(cx + w,     y_bot, z_heel)
        p_bl_t = V(cx - w_toe, y_bot, z_toe)
        p_br_t = V(cx + w_toe, y_bot, z_toe)

        p_tl_h = V(cx - w * 0.90,     y_col, z_heel + 0.010)
        p_tr_h = V(cx + w * 0.90,     y_col, z_heel + 0.010)
        p_tl_m = V(cx - w * 0.90,     y_col, z_mid)
        p_tr_m = V(cx + w * 0.90,     y_col, z_mid)
        p_tl_t = V(cx - w_toe * 0.90, y_toe, z_toe - 0.012)
        p_tr_t = V(cx + w_toe * 0.90, y_toe, z_toe - 0.012)

        # Sole bottom (2), heel back (2), toe front (2), sloped vamp (2), outer/inner sides (3+3) = 14 tris
        # Top collar face is buried inside wide cargo pant hem at y=0.125
        mb.face([p_bl_h, p_br_h, p_br_t, p_bl_t], SOLE,      out=(0, -1, 0))
        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], SHOE,      out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], SHOE,      out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], SHOE_VAMP, out=(0, 1, 0.5))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], SHOE,      out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h],         SHOE,      out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], SHOE,      out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m],         SHOE,      out=(1, 0, 0))

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
    """24-frame looping Walk cycle: brisk campus stride, cradling book stack & bobbing head to headphones."""
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

        # Upbeat campus walk bounce & slight forward lean balancing backpack
        pb_root = rig.pose.bones["Root"]
        bob = -0.026 * (1.0 - c2) * 0.5
        root_pitch = -0.058
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.062 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-twist torso slightly while keeping chest steady for books
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * c2, 0.072 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle upbeat music-groove head bob with headphones!
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.045 + 0.055 * s2, -0.048 * s1, 0.032 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp wide cargo-pant stride
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.46 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.038, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.46 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.038, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Both bent arms + book stack bounce together in lockstep so hands stay glued to books!
        book_heft_y = 0.014 * math.sin(2.0 * phi - 0.55)
        arm_heft_pitch = -0.055 * math.sin(2.0 * phi - 0.55)

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_heft_pitch, 0.0, -0.018 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (arm_heft_pitch, 0.0, -0.018 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_books = rig.pose.bones["Books"]
        pb_books.location = (0.0, book_heft_y, 0.0)
        pb_books.rotation_euler = (arm_heft_pitch * 0.65, 0.0, -0.022 * c1)
        pb_books.keyframe_insert(data_path="location", frame=frame)
        pb_books.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: relaxed campus wait, headphone head-nod groove & gentle book heft."""
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
        pb_root.rotation_euler = (-0.014, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * s2, 0.026 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Charming music-listening head bob & casual campus glance
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.095 * s2, 0.20 * s1, 0.055 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs stay firmly planted
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Both arms & book stack shift weight gently in unison with breathing
        heft_pitch = -0.036 * s2
        heft_y = 0.009 * s2
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (heft_pitch, 0.0, 0.010 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (heft_pitch, 0.0, 0.010 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_books = rig.pose.bones["Books"]
        pb_books.location = (0.0, heft_y, 0.0)
        pb_books.rotation_euler = (heft_pitch * 0.7, 0.0, 0.012 * s1)
        pb_books.keyframe_insert(data_path="location", frame=frame)
        pb_books.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Books) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonStudentRig")
    rig = bpy.data.objects.new("PersonStudentRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.615, 0.000), ( 0.000, 0.715, 0.000)),
        ("Torso", "Root",  ( 0.000, 0.670, 0.000), ( 0.000, 1.125, 0.000)),
        ("Head",  "Torso", ( 0.000, 1.165, 0.000), ( 0.000, 1.485, 0.000)),
        ("Arm_L", "Torso", ( 0.175, 1.060, 0.000), ( 0.175, 1.220, 0.000)),
        ("Arm_R", "Torso", (-0.175, 1.060, 0.000), (-0.175, 1.220, 0.000)),
        ("Books", "Torso", ( 0.000, 0.850, 0.240), ( 0.000, 0.990, 0.240)),
        ("Leg_L", "Root",  ( 0.105, 0.565, 0.000), ( 0.105, 0.725, 0.000)),
        ("Leg_R", "Root",  (-0.105, 0.565, 0.000), (-0.105, 0.725, 0.000)),
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
        ( 0.56, math.radians(90)),   # Side (showing curly hair, headphones, backpack, books, cargo pocket)
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


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR_DARK, HAIR_MID],
    "top": [HOODIE, HOODIE_SHADE],
    "bottom": [PANTS, PANTS_SHADE, PANTS_POCKET],
    "accent": [PACK, PACK_SHADE],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonStudent")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonStudent")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonStudent", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=64)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=54, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonStudent Stats ===")
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
