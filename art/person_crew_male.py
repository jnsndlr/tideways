# Builds an ultra-low-poly stylized male ferry crew / deckhand in Blender (no ponytail)
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_crew_male.py)
# Saves art/person_crew_male.blend, exports assets/models/person_crew_male.glb (rigged + Walk & Idle cycles),
# renders art/person_crew_male_preview.png, art/person_crew_male_walk_preview.png, art/person_crew_male_idle_preview.png,
# and outputs rendered videos art/person_crew_male_walk.mp4 and art/person_crew_male_idle.mp4.
#
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.73 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_crew_male.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_crew_male.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_crew_male_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_crew_male_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_crew_male_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_crew_male_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_crew_male_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN             = col_srgb(0.96, 0.70, 0.45)
SKIN_SHADE       = col_srgb(0.87, 0.61, 0.38)
HAIR             = col_srgb(0.36, 0.25, 0.20)
HAIR_SHADE       = col_srgb(0.27, 0.18, 0.14)
EYE              = col_srgb(0.13, 0.13, 0.15)
CAP              = col_srgb(0.27, 0.30, 0.39)
CAP_SHADE        = col_srgb(0.20, 0.23, 0.31)
CAP_BRIM         = col_srgb(0.23, 0.26, 0.35)
EMBLEM           = col_srgb(0.95, 0.94, 0.89)
EMBLEM_DARK      = col_srgb(0.23, 0.26, 0.34)
SHIRT_INNER      = col_srgb(0.22, 0.27, 0.36)
JACKET           = col_srgb(0.25, 0.30, 0.40)
JACKET_SHADE     = col_srgb(0.19, 0.23, 0.32)
PLACKET          = col_srgb(0.28, 0.30, 0.35)
PLACKET_DOT      = col_srgb(0.19, 0.21, 0.26)
HIVIS            = col_srgb(0.91, 0.89, 0.60)
HIVIS_SHADE      = col_srgb(0.78, 0.77, 0.50)
BAG              = col_srgb(0.24, 0.24, 0.26)
BAG_DARK         = col_srgb(0.17, 0.17, 0.19)
STRAP            = col_srgb(0.21, 0.21, 0.23)
PANTS            = col_srgb(0.30, 0.30, 0.34)
PANTS_SHADE      = col_srgb(0.23, 0.23, 0.27)
SHOE_CREAM       = col_srgb(0.94, 0.87, 0.78)
SHOE_CREAM_SHADE = col_srgb(0.85, 0.78, 0.68)
SHOE_BROWN       = col_srgb(0.50, 0.40, 0.33)
SHOE_BROWN_SHADE = col_srgb(0.40, 0.31, 0.25)
SOLE             = col_srgb(0.56, 0.48, 0.39)


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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            for k in range(n):
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
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir)

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

    def ribbon_path(self, centers, normals, half_w, half_t, color, closed=False, cap_start=True, cap_end=True):
        """Sweep a rectangular strap along 3D centers with given outward normals."""
        rings = []
        m = len(centers)
        for i, c in enumerate(centers):
            if closed:
                t1 = (centers[i] - centers[(i - 1) % m]).normalized()
                t2 = (centers[(i + 1) % m] - centers[i]).normalized()
                t = (t1 + t2)
                t = t.normalized() if t.length > 1e-6 else t1
            elif i == 0:
                t = (centers[1] - centers[0]).normalized()
            elif i == m - 1:
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
        if closed:
            rings.append(rings[0])
            self.loft(rings, color, cap_bottom=False, cap_top=False)
        else:
            self.loft(rings, color, cap_bottom=cap_start, cap_top=cap_end, bot_color=color, top_color=color)


def oval_ring(cx, cy, cz, rx, rz, n=8, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=8, phase=math.pi / 8):
    """n-sided ring tilted around X by tilt_rad (+tilt raises +Z front, lowers -Z back)."""
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
    # 1. HEAD + SHORT CROPPED DARK BROWN HAIR (8-sided low-poly head, y = 1.185 .. 1.60)
    # =========================================================================
    mb.set_part("head_and_hair", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.185,  0.008, 0.152, 0.146),  # 0: slightly squarer chin / jaw base
        (1.275,  0.014, 0.214, 0.200),  # 1: lower cheek / short nape hairline
        (1.480,  0.010, 0.216, 0.206),  # 2: brow / cap line
        (1.585, -0.002, 0.190, 0.192),  # 3: tucked cleanly inside cap
    ]
    head_rings = []
    for (y, cz, rx, rz) in head_specs:
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            sq = 1.04
            ring.append(V(rx * math.sin(a) * sq, y, cz + rz * math.cos(a) * sq))
        head_rings.append(ring)

    # Subtle short cropped hair volume on back & sides under cap
    for i in (1, 2, 3):
        for k in range(8):
            if k in (2, 3, 4, 5):
                p = head_rings[i][k]
                sc = 1.018 if i == 1 else 1.026
                head_rings[i][k] = V(p.x * sc, p.y, p.z * sc)

    def head_color(i, k):
        if i >= 2:
            return HAIR
        if i == 1:
            return SKIN if k in (6, 7, 0) else HAIR
        # Clean cropped nape: skin below the lower skull ring
        return SKIN_SHADE if k in (2, 3, 4) else SKIN

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
                # Front-left temple (+X): crisp short sideburn in front of ear
                p_side = p1.lerp(p2, 0.34)
                p_top = p3.lerp(p2, 0.54)
                mb.face([p0, p1, p_side, p_top, p3], SKIN, out=(mid - cmid))
                mb.face([p_side, p2, p_top], HAIR, out=(mid - cmid))
            elif i == 1 and k == 6:
                # Front-right temple (-X): mirror of k=0
                p_side = p0.lerp(p3, 0.34)
                p_top = p2.lerp(p3, 0.54)
                mb.face([p0, p1, p2, p_top, p_side], SKIN, out=(mid - cmid))
                mb.face([p_side, p_top, p3], HAIR, out=(mid - cmid))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    # Chin underside
    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. NAVY BASEBALL CAP WITH WHITE FERRY EMBLEM (no ponytail / bun)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    # Positive tilt raises the front brow edge and sits low over the nape hair
    cap_tilt = math.radians(10.0)
    c_rim_in = tilted_ring(0.0, 1.472, -0.004, 0.198, 0.202, cap_tilt, n=8, phase=math.pi / 8)
    c_rim    = tilted_ring(0.0, 1.468, -0.002, 0.244, 0.246, cap_tilt, n=8, phase=math.pi / 8)
    c_mid    = tilted_ring(0.0, 1.568,  0.002, 0.248, 0.248, cap_tilt * 0.85, n=8, phase=math.pi / 8)
    c_upper  = tilted_ring(0.0, 1.678, -0.004, 0.204, 0.202, cap_tilt * 0.65, n=8, phase=math.pi / 8)
    c_top    = tilted_ring(0.0, 1.732, -0.010, 0.106, 0.106, cap_tilt * 0.45, n=8, phase=math.pi / 8)

    # Cap underside lip & faceted 8-panel baseball crown
    mb.loft([c_rim_in, c_rim], CAP_SHADE, cap_bottom=False, cap_top=False)
    mb.loft([c_rim, c_mid, c_upper, c_top], CAP, cap_bottom=False, cap_top=False)
    # Flat-faceted top cap
    mb.face([c_top[7], c_top[0], c_top[3], c_top[4]], CAP, out=(0, 1, 0))
    mb.face([c_top[0], c_top[1], c_top[2], c_top[3]], CAP, out=(0, 1, 0))
    mb.face([c_top[4], c_top[5], c_top[6], c_top[7]], CAP, out=(0, 1, 0))

    # Small baseball cap crown button on top
    btn_r0 = oval_ring(0.0, 1.730, -0.010, 0.024, 0.024, n=6, phase=0.0)
    btn_r1 = oval_ring(0.0, 1.746, -0.010, 0.020, 0.020, n=6, phase=0.0)
    mb.loft([btn_r0, btn_r1], CAP_SHADE, cap_bottom=False, cap_top=True, top_color=CAP)

    # Curved front baseball visor / bill projecting cleanly forward over the brow
    # Back edge anchors directly into the front 3 segments of c_rim (k = 6, 7, 0, 1)
    v_back_t = [
        V(-0.220, 1.500, 0.108),
        V(-0.145, 1.522, 0.212),
        V( 0.000, 1.530, 0.236),
        V( 0.145, 1.522, 0.212),
        V( 0.220, 1.500, 0.108),
    ]
    v_mid_t = [
        V(-0.202, 1.482, 0.214),
        V(-0.130, 1.500, 0.308),
        V( 0.000, 1.506, 0.338),
        V( 0.130, 1.500, 0.308),
        V( 0.202, 1.482, 0.214),
    ]
    v_front_t = [
        V(-0.168, 1.454, 0.296),
        V(-0.096, 1.466, 0.382),
        V( 0.000, 1.470, 0.408),
        V( 0.096, 1.466, 0.382),
        V( 0.168, 1.454, 0.296),
    ]
    v_back_b  = [V(p.x, p.y - 0.020, p.z) for p in v_back_t]
    v_mid_b   = [V(p.x, p.y - 0.020, p.z - 0.004) for p in v_mid_t]
    v_front_b = [V(p.x, p.y - 0.018, p.z - 0.008) for p in v_front_t]

    for k in range(4):
        # Top surface of visor (2 rows for subtle baseball bill curve)
        mb.face([v_back_t[k], v_back_t[k + 1], v_mid_t[k + 1], v_mid_t[k]], CAP_BRIM, out=(0, 1, 0))
        mb.face([v_mid_t[k], v_mid_t[k + 1], v_front_t[k + 1], v_front_t[k]], CAP_BRIM, out=(0, 1, 0))
        # Dark shaded underside of visor
        mb.face([v_mid_b[k], v_mid_b[k + 1], v_back_b[k + 1], v_back_b[k]], CAP_SHADE, out=(0, -1, 0))
        mb.face([v_front_b[k], v_front_b[k + 1], v_mid_b[k + 1], v_mid_b[k]], CAP_SHADE, out=(0, -1, 0))
        # Front edge lip of visor
        mb.face([v_front_b[k], v_front_t[k], v_front_t[k + 1], v_front_b[k + 1]], CAP_SHADE, out=(0, 0, 1))
    # Side edges of visor
    for a_t, b_t, a_b, b_b in ((v_back_t[0], v_mid_t[0], v_back_b[0], v_mid_b[0]),
                                (v_mid_t[0], v_front_t[0], v_mid_b[0], v_front_b[0])):
        mb.face([a_b, b_b, b_t, a_t], CAP_SHADE, out=(-1, 0, 0))
    for a_t, b_t, a_b, b_b in ((v_back_t[4], v_mid_t[4], v_back_b[4], v_mid_b[4]),
                                (v_mid_t[4], v_front_t[4], v_mid_b[4], v_front_b[4])):
        mb.face([b_b, a_b, a_t, b_t], CAP_SHADE, out=(1, 0, 0))

    # Crisp white stylized Ferry Boat emblem mounted flush on the front crown panel (c_mid -> c_upper, k=7..0)
    mb.set_part("cap_emblem", bone="Head")
    p_bl = c_mid[7];   p_br = c_mid[0]
    p_tl = c_upper[7]; p_tr = c_upper[0]
    em_origin = (p_bl + p_br) * 0.5
    em_top_c  = (p_tl + p_tr) * 0.5
    em_x = (p_br - p_bl).normalized()          # +X across front panel
    em_y = (em_top_c - em_origin).normalized() # upward along angled front crown panel
    em_n = em_x.cross(em_y).normalized()       # outward normal (+Z/+Y)
    if em_n.z < 0:
        em_n = -em_n

    def emblem_quad(u0, u1, v0, v1, col, lift=0.005):
        pts = [
            em_origin + em_x * u0 + em_y * v0 + em_n * lift,
            em_origin + em_x * u1 + em_y * v0 + em_n * lift,
            em_origin + em_x * u1 + em_y * v1 + em_n * lift,
            em_origin + em_x * u0 + em_y * v1 + em_n * lift,
        ]
        mb.face(pts, col, out=em_n)

    def emblem_trap(u0_b, u1_b, u0_t, u1_t, v0, v1, col, lift=0.005):
        pts = [
            em_origin + em_x * u0_b + em_y * v0 + em_n * lift,
            em_origin + em_x * u1_b + em_y * v0 + em_n * lift,
            em_origin + em_x * u1_t + em_y * v1 + em_n * lift,
            em_origin + em_x * u0_t + em_y * v1 + em_n * lift,
        ]
        mb.face(pts, col, out=em_n)

    # Stylized ferry silhouette: hull, cabin deck, bridge, mast + crisp deck window slits
    emblem_trap(-0.058, 0.058, -0.068, 0.068, 0.002, 0.032, EMBLEM, lift=0.005)      # white ferry hull
    emblem_quad(-0.056, 0.056, 0.032, 0.060, EMBLEM, lift=0.005)                    # main passenger deck
    emblem_quad(-0.044, 0.044, 0.036, 0.046, EMBLEM_DARK, lift=0.007)               # lower deck window slit
    emblem_quad(-0.034, 0.034, 0.060, 0.082, EMBLEM, lift=0.005)                    # upper wheelhouse/bridge
    emblem_quad(-0.024, 0.024, 0.065, 0.073, EMBLEM_DARK, lift=0.007)               # bridge window slit
    emblem_quad(-0.006, 0.006, 0.082, 0.104, EMBLEM, lift=0.005)                    # tiny signal mast

    # =========================================================================
    # 4. EARS (2 compact warm-skin wedges peeking out in front of nape hair)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.204
        x_out = side * 0.250
        y0, y1 = 1.298, 1.398
        z0, z1 = -0.024, 0.050
        p_out_b = V(x_out, y0 + 0.015, z0 + 0.012)
        p_out_f = V(x_out, y0 + 0.015, z1 - 0.010)
        p_out_t = V(x_out, y1 - 0.015, (z0 + z1) * 0.5)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_out_t, p_out_f], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_out_b, p_out_t], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_out_f, p_out_b], SKIN_SHADE, out=(0, -1, 0))
        mb.face([p_out_b, p_out_f, p_out_t], SKIN, out=(side, 0, 0))

    # =========================================================================
    # 5. EYES (2 vertical dark pill hexagons, matching sibling characters)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.215
    for side in (-1, 1):
        cx = side * 0.068
        cy = 1.385
        rx = 0.020
        ry = 0.049
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
    # 6. NECK (6-sided warm skin cylinder) + INNER NAVY T-SHIRT
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.095, 0.004, 0.072, 0.066, n=6, phase=math.pi / 6)
    neck_r1 = oval_ring(0.0, 1.195, 0.006, 0.068, 0.062, n=6, phase=math.pi / 6)
    mb.loft([neck_r0, neck_r1], SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 7. NAVY HI-VIS FERRY CREW JACKET + COLLAR + PLACKET + REFLECTIVE STRIPES
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    # 4 horizontal rings so the hi-vis yellow band wraps seamlessly around torso
    # (y,    x_half, z_front, z_back, sh_drop)
    j_specs = [
        (0.652, 0.228, 0.136, -0.128, 0.000),  # 0: relaxed boxy jacket hem
        (0.768, 0.224, 0.134, -0.126, 0.000),  # 1: bottom of hi-vis torso stripe
        (0.854, 0.218, 0.130, -0.123, 0.000),  # 2: top of hi-vis torso stripe
        (1.138, 0.194, 0.120, -0.114, 0.022),  # 3: gently sloped sporty shoulders
    ]
    j_rings = []
    for (y, xh, zf, zb, drop) in j_specs:
        # 8-sided chamfered box ring so jacket feels cozy & slightly rounded like reference
        ch = 0.032
        yo = y - drop
        j_rings.append([
            V(-xh + ch, y,  zf),
            V( xh - ch, y,  zf),
            V( xh,      yo, zf - ch),
            V( xh,      yo, zb + ch),
            V( xh - ch, y,  zb),
            V(-xh + ch, y,  zb),
            V(-xh,      yo, zb + ch),
            V(-xh,      yo, zf - ch),
        ])

    def jacket_col(i, k):
        return HIVIS if i == 1 else JACKET

    mb.loft(j_rings, jacket_col, cap_bottom=True, cap_top=True,
            bot_color=JACKET_SHADE, top_color=JACKET)

    # Front V-notch showing dark navy crew-neck tee + warm skin triangle at throat
    z_f_top = 0.120
    mb.face([V(-0.068, 1.138, z_f_top + 0.003), V(0.068, 1.138, z_f_top + 0.003),
             V(0.000, 1.032, 0.126)], SHIRT_INNER, out=(0, 0, 1))
    mb.face([V(-0.044, 1.138, z_f_top + 0.005), V(0.044, 1.138, z_f_top + 0.005),
             V(0.000, 1.090, 0.126)], SKIN, out=(0, 0, 1))

    # Center front dark charcoal-slate button/zipper placket splitting the hi-vis stripe cleanly
    mb.set_part("placket", bone="Torso")
    pw = 0.022
    p_bot_l = V(-pw, 0.652, 0.136 + 0.007)
    p_bot_r = V( pw, 0.652, 0.136 + 0.007)
    p_top_l = V(-pw, 1.040, 0.124 + 0.007)
    p_top_r = V( pw, 1.040, 0.124 + 0.007)
    mb.face([p_bot_l, p_bot_r, p_top_r, p_top_l], PLACKET, out=(0, 0, 1))
    # Subtle side thickness of placket
    mb.face([p_bot_r, V(pw, 0.652, 0.136), V(pw, 1.040, 0.124), p_top_r], JACKET_SHADE, out=(1, 0, 0))
    mb.face([V(-pw, 0.652, 0.136), p_bot_l, p_top_l, V(-pw, 1.040, 0.124)], JACKET_SHADE, out=(-1, 0, 0))
    # Crisp dark snap buttons down the placket
    for by in (0.715, 0.812, 0.905, 0.992):
        t = (by - 0.652) / (1.040 - 0.652)
        bz = 0.136 * (1.0 - t) + 0.124 * t + 0.009
        mb.face([V(-0.008, by - 0.008, bz), V(0.008, by - 0.008, bz),
                 V(0.008, by + 0.008, bz), V(-0.008, by + 0.008, bz)], PLACKET_DOT, out=(0, 0, 1))

    # Upper-left chest hi-vis reflective bar (+X) matching reference
    mb.set_part("hivis_accents", bone="Torso")
    x0, x1 = 0.030, 0.148
    y0, y1 = 0.952, 0.994
    t0 = (y0 - 0.854) / (1.138 - 0.854)
    t1 = (y1 - 0.854) / (1.138 - 0.854)
    z0 = 0.130 * (1.0 - t0) + 0.120 * t0 + 0.004
    z1 = 0.130 * (1.0 - t1) + 0.120 * t1 + 0.004
    mb.face([V(x0, y0, z0), V(x1, y0, z0), V(x1, y1, z1), V(x0, y1, z1)], HIVIS, out=(0, 0, 1))

    # Folded standing maritime collar with iconic HI-VIS YELLOW outer border trim!
    mb.set_part("collar", bone="Torso")
    # Open at front V-neck, wrapping around sides & back of neck
    col_bot = [
        V(-0.022, 1.036,  0.128),
        V(-0.118, 1.136,  0.098),
        V(-0.145, 1.136,  0.000),
        V(-0.122, 1.134, -0.105),
        V( 0.000, 1.134, -0.122),
        V( 0.122, 1.134, -0.105),
        V( 0.145, 1.136,  0.000),
        V( 0.118, 1.136,  0.098),
        V( 0.022, 1.036,  0.128),
    ]
    col_top = [
        V(-0.028, 1.062,  0.142),
        V(-0.105, 1.192,  0.104),
        V(-0.132, 1.196,  0.002),
        V(-0.112, 1.194, -0.098),
        V( 0.000, 1.194, -0.114),
        V( 0.112, 1.194, -0.098),
        V( 0.132, 1.196,  0.002),
        V( 0.105, 1.192,  0.104),
        V( 0.028, 1.062,  0.142),
    ]
    col_in = [
        V(-0.018, 1.045,  0.124),
        V(-0.074, 1.164,  0.082),
        V(-0.092, 1.168,  0.002),
        V(-0.084, 1.168, -0.074),
        V( 0.000, 1.168, -0.086),
        V( 0.084, 1.168, -0.074),
        V( 0.092, 1.168,  0.002),
        V( 0.074, 1.164,  0.082),
        V( 0.018, 1.045,  0.124),
    ]
    for k in range(len(col_bot) - 1):
        p0, p1, p2, p3 = col_bot[k], col_bot[k + 1], col_top[k + 1], col_top[k]
        # Split outer collar face into lower navy band + bright upper hi-vis yellow piping
        m0 = p0.lerp(p3, 0.45)
        m1 = p1.lerp(p2, 0.45)
        mid = (p0 + p1 + p2 + p3) * 0.25
        out_hint = V(mid.x, 0.15, mid.z)
        mb.face([p0, p1, m1, m0], JACKET, out=out_hint)
        mb.face([m0, m1, p2, p3], HIVIS, out=out_hint)
        # Top folded collar rim in hi-vis yellow-lime
        mb.face([col_top[k], col_top[k + 1], col_in[k + 1], col_in[k]], HIVIS_SHADE, out=(0, 1, 0))

    # =========================================================================
    # 8. PUFFY SLEEVES WITH HI-VIS ARMBANDS + CASUAL HANDS (Arm_L, Arm_R)
    # =========================================================================
    mb.set_part("sleeves")

    def build_crew_sleeve(side, bone_name):
        mb.set_bone(bone_name)
        # Gentle relaxed bend toward front-side hip/pocket, clearing torso and rear bag cleanly
        p_sh = V(side * 0.164, 1.092,  0.002)
        p_el = V(side * 0.278, 0.884, -0.020)
        p_wr = V(side * 0.252, 0.722,  0.068)

        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax_mid = (ax1 + ax2).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def sleeve_ring(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            u = u.normalized()
            v = axis.cross(u).normalized()
            # 6-sided chunky faceted sleeve
            pts = []
            for k in range(6):
                a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
                pts.append(ctr + u * (rx * math.sin(a)) + v * (rperp * math.cos(a)))
            return pts

        r0 = sleeve_ring(p_sh, ax1, 0.080, 0.088)
        r1 = sleeve_ring(p_sh.lerp(p_el, 0.72), ax1, 0.095, 0.099)   # top of crisp hi-vis armband
        r2 = sleeve_ring(p_el, ax_mid, 0.098, 0.102)                  # mid elbow
        r3 = sleeve_ring(p_el.lerp(p_wr, 0.20), ax2, 0.095, 0.098)   # bottom of crisp hi-vis armband
        r4 = sleeve_ring(p_el.lerp(p_wr, 0.82), ax2, 0.088, 0.092)   # lower cuff swell
        r5 = sleeve_ring(p_wr, ax2, 0.072, 0.076)                     # neat tapered cuff lip

        def s_col(i, k):
            return HIVIS if i in (1, 2) else JACKET

        mb.loft([r0, r1, r2, r3, r4, r5], s_col, cap_bottom=False, cap_top=True, top_color=JACKET_SHADE)
        return p_el, p_wr

    el_l, wr_l = build_crew_sleeve( 1, "Arm_L")
    el_r, wr_r = build_crew_sleeve(-1, "Arm_R")

    # Chunky warm-skin mittens emerging from cuffs, angled slightly forward toward hip/pocket
    mb.set_part("hands")
    for (side, bname, p_el, p_wr) in ((1, "Arm_L", el_l, wr_l), (-1, "Arm_R", el_r, wr_r)):
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        u = V(1.0, 0.0, 0.0) - ax * ax.x
        u = u.normalized()
        v = ax.cross(u).normalized()
        h_stations = [
            (-0.008, 0.046, 0.048),
            ( 0.058, 0.056, 0.060),
            ( 0.108, 0.036, 0.040),
        ]
        h_rings = []
        for (dist, ru, rv) in h_stations:
            c = p_wr + ax * dist
            h_rings.append([
                c + u * (-ru) + v * ( rv),
                c + u * ( ru) + v * ( rv),
                c + u * ( ru) + v * (-rv),
                c + u * (-ru) + v * (-rv),
            ])
        mb.loft(h_rings, SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 9. CROSSBODY STRAP (Torso) + CHARCOAL MESSENGER SATCHEL BAG (Bag)
    # =========================================================================
    mb.set_part("crossbody_strap", bone="Torso")
    # Continuous dark charcoal strap hugging LEFT shoulder (+X) diagonally across chest
    # to RIGHT rear hip (-X, -Z), and hugging the back diagonally up to left shoulder!
    strap_pts = [
        V( 0.118, 1.140, -0.118),  # left-rear shoulder (flush outside jacket back)
        V( 0.122, 1.152,  0.005),  # top of left shoulder
        V( 0.118, 1.112,  0.122),  # front left collarbone
        V( 0.032, 0.990,  0.136),  # upper chest diagonal
        V(-0.072, 0.870,  0.142),  # mid chest diagonal
        V(-0.184, 0.766,  0.130),  # right front waist
        V(-0.228, 0.715,  0.035),  # right side hip hugging jacket
        V(-0.232, 0.680, -0.085),  # bag front anchor (right hip)
        V(-0.205, 0.700, -0.135),  # bag back anchor hugging jacket back
        V(-0.105, 0.835, -0.131),  # lower back diagonal (flush against jacket)
        V( 0.012, 0.992, -0.126),  # upper back diagonal (flush against jacket)
    ]
    strap_norms = [
        V( 0.25,  0.75, -0.60),
        V( 0.20,  1.00,  0.05),
        V( 0.20,  0.35,  0.90),
        V( 0.05,  0.10,  1.00),
        V(-0.15,  0.05,  1.00),
        V(-0.55,  0.00,  0.85),
        V(-1.00,  0.00,  0.15),
        V(-0.85, -0.05, -0.50),
        V(-0.60,  0.00, -0.80),
        V(-0.25,  0.05, -0.95),
        V( 0.05,  0.15, -0.98),
    ]
    mb.ribbon_path(strap_pts, strap_norms, half_w=0.026, half_t=0.008, color=STRAP, closed=True)

    # Chunky faceted messenger / sling pouch tucked snugly at right rear hip (-X, -Z)
    mb.set_part("satchel_bag", bone="Bag")
    bag_tilt_x = math.radians(-16.0)   # tilted gently back
    bag_tilt_z = math.radians(-12.0)   # angled slightly outward from hip
    cx_t, sx_t = math.cos(bag_tilt_x), math.sin(bag_tilt_x)
    cz_t, sz_t = math.cos(bag_tilt_z), math.sin(bag_tilt_z)
    bag_orig = V(-0.244, 0.608, -0.158)

    def bag_pt(lx, ly, lz):
        # Rotate around Z then X
        x1 = lx * cz_t - ly * sz_t
        y1 = lx * sz_t + ly * cz_t
        z1 = lz
        y2 = y1 * cx_t - z1 * sx_t
        z2 = y1 * sx_t + z1 * cx_t
        return V(bag_orig.x + x1, bag_orig.y + y2, bag_orig.z + z2)

    # 6-sided faceted chunky pouch profile (tapered softly at top and bottom)
    bag_stations = [
        # (ly,    rx,    rz)
        (-0.125, 0.058, 0.095),  # bottom base
        (-0.075, 0.092, 0.138),  # chunky faceted belly lower
        ( 0.045, 0.096, 0.145),  # chunky faceted belly upper
        ( 0.118, 0.068, 0.112),  # top closure / flap
    ]
    bag_rings = []
    for (ly, rx, rz) in bag_stations:
        ring = []
        for k in range(6):
            a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
            ring.append(bag_pt(rx * math.sin(a), ly, rz * math.cos(a)))
        bag_rings.append(ring)

    def bag_col(i, k):
        if i == 0:
            return BAG_DARK
        return BAG if k in (0, 1, 5) else BAG_DARK

    mb.loft(bag_rings, bag_col, cap_bottom=True, cap_top=True, bot_color=BAG_DARK, top_color=BAG)

    # =========================================================================
    # 10. RELAXED CHARCOAL-GREY WORK TROUSERS (Root + Leg_L, Leg_R)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.196, 0.196, 0.545, 0.680, -0.106, 0.106, PANTS, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t  = side * 0.010
        x_out_t = side * 0.194
        x_in_b  = side * 0.068
        x_out_b = side * 0.228
        rz_t = 0.104
        rz_b = 0.092
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_mid = [
            V(min(x_in_t, x_out_t) * 0.55 + min(x_in_b, x_out_b) * 0.45, 0.370, 0.100),
            V(max(x_in_t, x_out_t) * 0.55 + max(x_in_b, x_out_b) * 0.45, 0.370, 0.100),
            V(max(x_in_t, x_out_t) * 0.55 + max(x_in_b, x_out_b) * 0.45, 0.370, -0.100),
            V(min(x_in_t, x_out_t) * 0.55 + min(x_in_b, x_out_b) * 0.45, 0.370, -0.100),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.150,  rz_b),
            V(max(x_in_b, x_out_b), 0.150,  rz_b),
            V(max(x_in_b, x_out_b), 0.150, -rz_b),
            V(min(x_in_b, x_out_b), 0.150, -rz_b),
        ]
        mb.loft([r_bot, r_mid, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 11. TWO-TONE CREAM & WARM-BROWN DECK SNEAKERS (taupe sole + cream wall + brown vamp)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.148
        w = 0.072
        w_toe = 0.060
        z_heel = -0.092
        z_mid  =  0.056
        z_toe  =  0.164
        y_sole0 = 0.000
        y_sole1 = 0.022
        y_fox_h = 0.096   # chunky cream foxing height at heel/mid
        y_fox_t = 0.082   # chunky cream toe cap height
        y_vamp  = 0.158   # warm brown upper instep/collar meeting pants hem

        # Layer 1: Taupe outsole (y = 0.000 .. 0.022)
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

        # Layer 2: Chunky cream sneaker foxing wall & toe cap (y = 0.022 .. 0.096)
        p_bl_h = V(cx - w,     y_sole1, z_heel)
        p_br_h = V(cx + w,     y_sole1, z_heel)
        p_bl_t = V(cx - w_toe, y_sole1, z_toe)
        p_br_t = V(cx + w_toe, y_sole1, z_toe)

        p_fl_h = V(cx - w * 0.96, y_fox_h, z_heel + 0.006)
        p_fr_h = V(cx + w * 0.96, y_fox_h, z_heel + 0.006)
        p_fl_m = V(cx - w * 0.94, y_fox_h, z_mid)
        p_fr_m = V(cx + w * 0.94, y_fox_h, z_mid)
        p_fl_t = V(cx - w_toe * 0.94, y_fox_t, z_toe - 0.008)
        p_fr_t = V(cx + w_toe * 0.94, y_fox_t, z_toe - 0.008)

        # Cream perimeter walls & sloped cream toe deck
        mb.face([p_br_h, p_bl_h, p_fl_h, p_fr_h], SHOE_CREAM, out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_fr_t, p_fl_t], SHOE_CREAM, out=(0, 0, 1))
        mb.face([p_bl_h, p_bl_t, p_fl_t, p_fl_m], SHOE_CREAM, out=(-1, 0, 0))
        mb.face([p_bl_h, p_fl_m, p_fl_h], SHOE_CREAM, out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_fr_m, p_fr_t], SHOE_CREAM, out=(1, 0, 0))
        mb.face([p_br_h, p_fr_h, p_fr_m], SHOE_CREAM, out=(1, 0, 0))
        mb.face([p_fl_t, p_fr_t, p_fr_m, p_fl_m], SHOE_CREAM_SHADE, out=(0, 1, 0.3))
        mb.face([p_fl_m, p_fr_m, p_fr_h, p_fl_h], SHOE_CREAM, out=(0, 1, 0))

        # Layer 3: Warm brown upper vamp / ankle collar rising cleanly into trouser hem
        v_bot = [
            V(cx - w * 0.80, y_fox_h - 0.006, z_heel + 0.018),
            V(cx + w * 0.80, y_fox_h - 0.006, z_heel + 0.018),
            V(cx + w * 0.78, y_fox_h - 0.004, z_mid + 0.022),
            V(cx - w * 0.78, y_fox_h - 0.004, z_mid + 0.022),
        ]
        v_top = [
            V(cx - w * 0.72, y_vamp, z_heel + 0.028),
            V(cx + w * 0.72, y_vamp, z_heel + 0.028),
            V(cx + w * 0.72, y_vamp, z_mid - 0.006),
            V(cx - w * 0.72, y_vamp, z_mid - 0.006),
        ]
        mb.loft([v_bot, v_top], SHOE_BROWN, cap_bottom=False, cap_top=True, top_color=SHOE_BROWN_SHADE)

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
    """24-frame looping Walk cycle: confident deckhand stride, relaxed arm swing, trailing satchel."""
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

        # Confident casual stride with crisp double-frequency bob
        pb_root = rig.pose.bones["Root"]
        bob = -0.026 * (1.0 - c2) * 0.5
        root_pitch = -0.055
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.075 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_pitch = -0.022 * c2
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (torso_pitch, 0.105 * s1, -0.024 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.045 + 0.022 * c2, -0.042 * s1, -0.016 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alternating stride with clean foot lift on swing phase
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

        # Relaxed natural counter-swinging arms (Arm_R slightly forward-biased to clear rear satchel)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.28 * s1 - 0.03, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.24 * s1 - 0.04, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crossbody satchel trails slightly with natural pendulum sway
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.080 * math.sin(phi - 0.55), 0.0, 0.028 * c1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: alert dockside breathing, harbour glance, gentle arm & satchel settle."""
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

        # Calm weight shift & breathing
        pb_root = rig.pose.bones["Root"]
        root_pitch = -0.010
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (root_pitch, 0.026 * s1, 0.020 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        torso_pitch = -0.024 * s2
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (torso_pitch, 0.032 * s1, -0.018 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert ferry crew scan across the harbour / slip
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.034 * s2, 0.23 * s1, 0.030 * c1)
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
        pb_arm_l.rotation_euler = (0.050 * s1 - 0.018 * s2, 0.0, 0.016 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.048 * s1 - 0.016 * s2, 0.0, -0.016 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Satchel rests gently against hip with subtle counter-sway
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.026 * s2, 0.0, -0.022 * s1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Bag) with Walk and Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonCrewMaleRig")
    rig = bpy.data.objects.new("PersonCrewMaleRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.620,  0.000), ( 0.000, 0.720,  0.000)),
        ("Torso", "Root",  ( 0.000, 0.675,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",  "Torso", ( 0.000, 1.150,  0.000), ( 0.000, 1.460,  0.000)),
        ("Arm_L", "Torso", ( 0.164, 1.084,  0.000), ( 0.164, 1.244,  0.000)),
        ("Arm_R", "Torso", (-0.164, 1.084,  0.000), (-0.164, 1.244,  0.000)),
        ("Bag",   "Torso", (-0.220, 0.695, -0.120), (-0.220, 0.855, -0.120)),
        ("Leg_L", "Root",  ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R", "Root",  (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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


def _setup_studio(scene, floor_size=10.0, tag="Preview"):
    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.94, 0.95, 0.96, 1.0)
    bg.inputs["Strength"].default_value = 0.95
    scene.world = world

    key_data = bpy.data.lights.new(f"{tag}Key", type="SUN")
    key_data.energy = 2.6
    key_data.angle = math.radians(18.0)
    key_obj = bpy.data.objects.new(f"{tag}Key", key_data)
    scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(46), math.radians(10), math.radians(-35))

    fill_data = bpy.data.lights.new(f"{tag}Fill", type="SUN")
    fill_data.energy = 0.85
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new(f"{tag}Fill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=floor_size, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new(f"{tag}FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    return key_obj, fill_obj, floor


def render_preview(obj, out_path):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False

    key_obj, fill_obj, floor = _setup_studio(scene, floor_size=10.0, tag="Prev")

    clones = []
    specs = [
        (-1.68, math.radians(58)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (showing cap visor, low bun, satchel, hi-vis bands)
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
    direction = Vector((0.0, 0.0, 0.87)) - cam_obj.location
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=58):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 20
    scene.cycles.use_denoising = False

    prev_action = rig.animation_data.action
    rig.animation_data.action = action

    key_obj, fill_obj, floor = _setup_studio(scene, floor_size=14.0, tag="Strip")

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
    direction = Vector((0.0, 0.0, 0.87)) - cam_obj.location
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

    key_obj, fill_obj, floor = _setup_studio(scene, floor_size=10.0, tag="Vid")

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 2.95
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.12)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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
    stills_only = "--stills-only" in sys.argv

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonCrewMale")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonCrewMale")
    mb.bm.to_mesh(me)
    mb.bm.free()

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonCrewMale", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=58)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=35)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=35, zrot_right_deg=90)

    print("=== PersonCrewMale Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:16s}: {cnt}")
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
