# Builds an ultra-low-poly stylized elderly hiker / walker in Blender matching the reference
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_elder.py)
# Saves art/person_elder.blend, exports assets/models/person_elder.glb (rigged + Walk & Idle cycles),
# and renders art/person_elder_preview.png, art/person_elder_walk_preview.png, and art/person_elder_idle_preview.png.
#
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.73 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_elder.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_elder.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_elder_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_elder_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_elder_idle_preview.png")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN          = col_srgb(0.96, 0.71, 0.46)
SKIN_SHADE    = col_srgb(0.89, 0.63, 0.39)
HAIR          = col_srgb(0.93, 0.91, 0.88)
HAIR_SHADE    = col_srgb(0.83, 0.80, 0.76)
GLASSES       = col_srgb(0.15, 0.14, 0.15)
CAP           = col_srgb(0.45, 0.40, 0.37)
CAP_DARK      = col_srgb(0.32, 0.28, 0.26)
CAP_BRIM      = col_srgb(0.28, 0.25, 0.23)
SWEATER       = col_srgb(0.95, 0.89, 0.77)
SWEATER_SHADE = col_srgb(0.89, 0.82, 0.69)
SWEATER_RIB   = col_srgb(0.92, 0.85, 0.73)
COLLAR_RIM    = col_srgb(0.25, 0.22, 0.19)
VEST          = col_srgb(0.44, 0.47, 0.32)
VEST_SHADE    = col_srgb(0.36, 0.39, 0.26)
VEST_POCKET   = col_srgb(0.40, 0.43, 0.29)
PACK          = col_srgb(0.39, 0.38, 0.30)
PACK_DARK     = col_srgb(0.31, 0.30, 0.24)
STRAP         = col_srgb(0.37, 0.27, 0.21)
PANTS         = col_srgb(0.51, 0.40, 0.30)
PANTS_SHADE   = col_srgb(0.44, 0.34, 0.25)
BOOT          = col_srgb(0.39, 0.27, 0.20)
BOOT_CUFF     = col_srgb(0.33, 0.23, 0.17)
SOLE          = col_srgb(0.22, 0.16, 0.13)
CANE          = col_srgb(0.49, 0.34, 0.23)
CANE_DARK     = col_srgb(0.40, 0.27, 0.18)
CANE_TIP      = col_srgb(0.26, 0.20, 0.17)


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

    def tube_path(self, centers, radii, n=6, color=CANE, cap_start=True, cap_end=True):
        """Sweep an n-sided polygon tube along a 3D polyline."""
        rings = []
        up_ref = V(1.0, 0.0, 0.0)
        for i, c in enumerate(centers):
            if i == 0:
                t = (centers[1] - centers[0]).normalized()
            elif i == len(centers) - 1:
                t = (centers[-1] - centers[-2]).normalized()
            else:
                t1 = (centers[i] - centers[i - 1]).normalized()
                t2 = (centers[i + 1] - centers[i]).normalized()
                t = (t1 + t2)
                t = t.normalized() if t.length > 1e-6 else t1
            ref = up_ref if abs(t.dot(up_ref)) < 0.92 else V(0.0, 0.0, 1.0)
            u = t.cross(ref).normalized()
            v = t.cross(u).normalized()
            r = radii[i] if isinstance(radii, (list, tuple)) else radii
            ring = []
            for k in range(n):
                a = 2.0 * math.pi * k / n
                ring.append(c + (u * math.cos(a) + v * math.sin(a)) * r)
            rings.append(ring)
        self.loft(rings, color, cap_bottom=cap_start, cap_top=cap_end, bot_color=color, top_color=color)


def oval_ring(cx, cy, cz, rx, rz, n=8, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=8, phase=math.pi / 8):
    """8-sided ring tilted around X by tilt_rad (+tilt raises +Z front, -tilt lowers +Z front)."""
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
    # 1. HEAD (broad 8-sided low-poly head, y = 1.20 .. 1.54)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,    rx,    rz)
        (1.200,  0.015, 0.148, 0.145),  # 0: chin/jaw base
        (1.295,  0.020, 0.205, 0.195),  # 1: cheeks
        (1.470,  0.018, 0.208, 0.198),  # 2: brow / under cap
        (1.545,  0.008, 0.185, 0.180),  # 3: tucked inside cap
    ]
    head_rings = []
    for (y, cz, rx, rz) in head_specs:
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            ring.append(V(rx * math.sin(a) * 1.03, y, cz + rz * math.cos(a) * 1.03))
        head_rings.append(ring)

    def head_color(i, k):
        # k in (6, 7, 0) is the front face; sides/back tucked into white hair
        if k in (6, 7, 0):
            return SKIN
        if k in (1, 5) and i >= 1:
            return SKIN
        return HAIR

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)
    # Chin underside
    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. BUSHY WHITE HAIR (thick sculpted cloud wrapping back & sides under cap)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # 7-point horseshoe wrap from left sideburn -> left back -> rear -> right back -> right sideburn
    hair_specs = [
        # (y,     r_scale, z_off)
        (1.215,  0.86,   -0.015),  # 0: nape/lower hair base
        (1.305,  1.08,   -0.036),  # 1: lower puff sticking out at back
        (1.420,  1.10,   -0.032),  # 2: widest fluffy white hair ring
        (1.525,  0.94,   -0.012),  # 3: tucked snugly under cap rim
    ]
    # Angles from +75 deg (left side near ear) around back (+180) to +285 deg (right side near ear)
    hair_angles = [math.radians(a) for a in (72, 108, 144, 180, 216, 252, 288)]
    hair_rings = []
    for (y, rsc, zoff) in hair_specs:
        pts = []
        for idx, a in enumerate(hair_angles):
            # Slightly fuller at the back
            back_boost = 1.0 + 0.14 * max(0.0, -math.cos(a))
            rx = 0.224 * rsc * back_boost
            rz = 0.222 * rsc * back_boost
            pts.append(V(rx * math.sin(a), y, zoff + rz * math.cos(a)))
        hair_rings.append(pts)

    # Outer shell of white hair
    for i in range(len(hair_rings) - 1):
        r0, r1 = hair_rings[i], hair_rings[i + 1]
        col = HAIR if i >= 1 else HAIR_SHADE
        for k in range(len(hair_angles) - 1):
            p0, p1, p2, p3 = r0[k], r0[k + 1], r1[k + 1], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], col, out=V(mid.x, 0.0, mid.z))

    # Front sideburn closing edges & bottom nape bevel connecting into head
    for i in range(len(hair_rings) - 1):
        # Left sideburn front edge (k=0)
        p0, p1 = hair_rings[i][0], hair_rings[i + 1][0]
        p0_in = V(p0.x * 0.80, p0.y, p0.z - 0.01)
        p1_in = V(p1.x * 0.80, p1.y, p1.z - 0.01)
        mb.face([p0_in, p0, p1, p1_in], HAIR, out=(0, 0, 1))
        # Right sideburn front edge (k=-1)
        q0, q1 = hair_rings[i][-1], hair_rings[i + 1][-1]
        q0_in = V(q0.x * 0.80, q0.y, q0.z - 0.01)
        q1_in = V(q1.x * 0.80, q1.y, q1.z - 0.01)
        mb.face([q0, q0_in, q1_in, q1], HAIR, out=(0, 0, 1))

    # Underside of hair puff at nape
    r_bot = hair_rings[0]
    for k in range(len(hair_angles) - 1):
        p0, p1 = r_bot[k], r_bot[k + 1]
        mb.face([p1, p0, V(p0.x * 0.55, 1.215, p0.z * 0.55), V(p1.x * 0.55, 1.215, p1.z * 0.55)],
                HAIR_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 3. FLAT CAP / NEWSBOY CAP (dark taupe-grey faceted crown + front visor)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    cap_tilt = math.radians(-6.5)  # tilts slightly down in front over brow
    band_bot = tilted_ring(0.0, 1.500, -0.004, 0.246, 0.264, cap_tilt)
    band_top = tilted_ring(0.0, 1.546,  0.000, 0.256, 0.276, cap_tilt)
    crown_mid = tilted_ring(0.0, 1.616,  0.004, 0.272, 0.290, cap_tilt)
    crown_top = tilted_ring(0.0, 1.686, -0.004, 0.168, 0.180, cap_tilt)

    # Lower band + underside rim
    mb.loft([band_bot, band_top], CAP_DARK, cap_bottom=False, cap_top=False)
    band_in = tilted_ring(0.0, 1.506, -0.006, 0.195, 0.205, cap_tilt)
    mb.loft([band_in, band_bot], CAP_DARK, cap_bottom=False, cap_top=False)
    # Wide flat-cap crown
    mb.loft([band_top, crown_mid, crown_top], CAP, cap_bottom=False, cap_top=False)
    # Flat top of crown
    mb.face([crown_top[7], crown_top[0], crown_top[3], crown_top[4]], CAP, out=(0, 1, 0))
    mb.face([crown_top[0], crown_top[1], crown_top[2], crown_top[3]], CAP, out=(0, 1, 0))
    mb.face([crown_top[4], crown_top[5], crown_top[6], crown_top[7]], CAP, out=(0, 1, 0))

    # Forward visor / peak projecting out over the brow (+Z)
    v_back_t = [
        V(-0.185, 1.518, 0.175),
        V(-0.105, 1.510, 0.238),
        V( 0.105, 1.510, 0.238),
        V( 0.185, 1.518, 0.175),
    ]
    v_front_t = [
        V(-0.162, 1.502, 0.280),
        V(-0.088, 1.490, 0.348),
        V( 0.088, 1.490, 0.348),
        V( 0.162, 1.502, 0.280),
    ]
    v_back_b = [V(p.x, p.y - 0.022, p.z) for p in v_back_t]
    v_front_b = [V(p.x, p.y - 0.018, p.z - 0.006) for p in v_front_t]
    for k in range(3):
        mb.face([v_back_t[k], v_back_t[k + 1], v_front_t[k + 1], v_front_t[k]], CAP_DARK, out=(0, 1, 0))
        mb.face([v_front_b[k], v_front_b[k + 1], v_back_b[k + 1], v_back_b[k]], CAP_BRIM, out=(0, -1, 0))
        mb.face([v_front_b[k], v_front_t[k], v_front_t[k + 1], v_front_b[k + 1]], CAP_BRIM, out=(0, 0, 1))
    # Side edges of visor
    mb.face([v_back_b[0], v_front_b[0], v_front_t[0], v_back_t[0]], CAP_BRIM, out=(-1, 0, 0))
    mb.face([v_front_b[3], v_back_b[3], v_back_t[3], v_front_t[3]], CAP_BRIM, out=(1, 0, 0))

    # =========================================================================
    # 4. EARS (2 compact warm-skin wedges peeking out in front of white hair)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.200
        x_out = side * 0.248
        y0, y1 = 1.305, 1.400
        z0, z1 = 0.010, 0.080
        p_out_b = V(x_out, y0 + 0.016, z0 + 0.014)
        p_out_f = V(x_out, y0 + 0.016, z1 - 0.010)
        p_out_t = V(x_out, y1 - 0.016, (z0 + z1) * 0.5)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_out_t, p_out_f], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_out_b, p_out_t], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_out_f, p_out_b], SKIN_SHADE, out=(0, -1, 0))
        mb.face([p_out_b, p_out_f, p_out_t], SKIN, out=(side, 0, 0))

    # =========================================================================
    # 5. WHITE EYEBROWS + ROUND BLACK GLASSES
    # =========================================================================
    mb.set_part("eyebrows", bone="Head")
    for side in (-1, 1):
        cx = side * 0.076
        mb.box(cx - 0.038, cx + 0.038, 1.456, 1.484, 0.214, 0.244, HAIR)

    mb.set_part("glasses", bone="Head")
    # Two crisp 10-sided hollow round black frames
    z_g0, z_g1 = 0.214, 0.236
    cy_g = 1.388
    r_out = 0.058
    r_in = 0.041
    n_seg = 10
    for side in (-1, 1):
        cx = side * 0.076
        out_f, out_b, in_f, in_b = [], [], [], []
        for k in range(n_seg):
            a = 2.0 * math.pi * k / n_seg
            ca, sa = math.cos(a), math.sin(a)
            out_f.append(V(cx + r_out * ca, cy_g + r_out * sa, z_g1))
            out_b.append(V(cx + r_out * ca, cy_g + r_out * sa, z_g0))
            in_f.append(V(cx + r_in * ca, cy_g + r_in * sa, z_g1))
            in_b.append(V(cx + r_in * ca, cy_g + r_in * sa, z_g0))
        for k in range(n_seg):
            kn = (k + 1) % n_seg
            a_mid = 2.0 * math.pi * (k + 0.5) / n_seg
            rad_dir = V(math.cos(a_mid), math.sin(a_mid), 0.0)
            mb.face([out_f[k], out_f[kn], in_f[kn], in_f[k]], GLASSES, out=(0, 0, 1))
            mb.face([in_b[k], in_b[kn], out_b[kn], out_b[k]], GLASSES, out=(0, 0, -1))
            mb.face([out_b[k], out_b[kn], out_f[kn], out_f[k]], GLASSES, out=rad_dir)
            mb.face([in_f[k], in_f[kn], in_b[kn], in_b[k]], GLASSES, out=-rad_dir)

    # Nose bridge connecting the two frames
    mb.box(-0.022, 0.022, cy_g + 0.004, cy_g + 0.020, z_g0, z_g1, GLASSES)

    # Temple arms going straight back from outer frame edges to ears
    for side in (-1, 1):
        x_f = side * (0.076 + r_out - 0.004)
        x_b = side * 0.222
        y_t0, y_t1 = cy_g + 0.002, cy_g + 0.018
        z_tf, z_tb = z_g0 + 0.008, 0.038
        # Build thin slanted temple bar
        t_off = side * 0.012
        p0 = V(x_f, y_t0, z_tf); p1 = V(x_f + t_off, y_t0, z_tf)
        p2 = V(x_f + t_off, y_t1, z_tf); p3 = V(x_f, y_t1, z_tf)
        q0 = V(x_b, y_t0, z_tb); q1 = V(x_b + t_off, y_t0, z_tb)
        q2 = V(x_b + t_off, y_t1, z_tb); q3 = V(x_b, y_t1, z_tb)
        mb.face([p1, q1, q2, p2], GLASSES, out=(side, 0, 0))
        mb.face([q0, p0, p3, q3], GLASSES, out=(-side, 0, 0))
        mb.face([p3, p2, q2, q3], GLASSES, out=(0, 1, 0))
        mb.face([q0, q1, p1, p0], GLASSES, out=(0, -1, 0))

    # =========================================================================
    # 6. BUSHY WHITE MUSTACHE + CHIN GOATEE
    # =========================================================================
    mb.set_part("mustache", bone="Head")
    # Sculpted curved handlebar-style mustache (2 wings meeting at center)
    for side in (-1, 1):
        r0 = [
            V(0.0, 1.318, 0.224),
            V(0.0, 1.312, 0.262),
            V(0.0, 1.276, 0.256),
            V(0.0, 1.278, 0.218),
        ]
        r1 = [
            V(side * 0.058, 1.312, 0.214),
            V(side * 0.062, 1.304, 0.254),
            V(side * 0.062, 1.264, 0.246),
            V(side * 0.058, 1.268, 0.208),
        ]
        r2 = [
            V(side * 0.118, 1.284, 0.188),
            V(side * 0.122, 1.278, 0.218),
            V(side * 0.116, 1.252, 0.212),
            V(side * 0.112, 1.258, 0.184),
        ]
        if side < 0:
            mb.loft([r2, r1, r0], HAIR, cap_bottom=True, cap_top=False, bot_color=HAIR_SHADE)
        else:
            mb.loft([r0, r1, r2], HAIR, cap_bottom=False, cap_top=True, top_color=HAIR_SHADE)

    # Small white chin beard / goatee beneath the mustache
    mb.box(-0.056, 0.056, 1.196, 1.268, 0.186, 0.236, HAIR)
    # Subtle lower jaw white fringe
    mb.box(-0.095, 0.095, 1.196, 1.232, 0.140, 0.190, HAIR_SHADE)

    # =========================================================================
    # 7. TURTLENECK COLLAR & CABLE-KNIT CREAM SWEATER TORSO
    # =========================================================================
    mb.set_part("turtleneck", bone="Torso")
    # Dark inner neckline accent peeking just below chin
    tn_r0 = oval_ring(0.0, 1.105, 0.005, 0.108, 0.096, n=8, phase=math.pi / 8)
    tn_r1 = oval_ring(0.0, 1.198, 0.008, 0.104, 0.092, n=8, phase=math.pi / 8)
    tn_r2 = oval_ring(0.0, 1.216, 0.008, 0.088, 0.078, n=8, phase=math.pi / 8)
    mb.loft([tn_r0, tn_r1], lambda i, k: SWEATER if k % 2 == 0 else SWEATER_RIB, cap_bottom=False, cap_top=False)
    mb.loft([tn_r1, tn_r2], COLLAR_RIM, cap_bottom=False, cap_top=True, top_color=COLLAR_RIM)

    mb.set_part("sweater", bone="Torso")
    # Inner sweater torso core (visible at front center opening & bottom hem)
    mb.box(-0.185, 0.185, 0.678, 1.132, -0.105, 0.114, SWEATER, skip=("front",))

    # Front ribbed hem of sweater (y = 0.678..0.738)
    z_sw_f = 0.116
    nx_rib = 6
    x_rib0, x_rib1 = -0.096, 0.096
    for i in range(nx_rib):
        xa = x_rib0 + (x_rib1 - x_rib0) * i / nx_rib
        xb = x_rib0 + (x_rib1 - x_rib0) * (i + 1) / nx_rib
        col = SWEATER if i % 2 == 0 else SWEATER_RIB
        mb.face([V(xa, 0.678, z_sw_f), V(xb, 0.678, z_sw_f),
                 V(xb, 0.742, z_sw_f), V(xa, 0.742, z_sw_f)], col, out=(0, 0, 1))

    # Cable-knit diamond lattice on front sweater panel (y = 0.742..1.132)
    # 3 columns x 4 rows of faceted diamond relief using vertex color contrast!
    cols_k = 3
    rows_k = 4
    xk0, xk1 = -0.096, 0.096
    yk0, yk1 = 0.742, 1.132
    dx_k = (xk1 - xk0) / cols_k
    dy_k = (yk1 - yk0) / rows_k
    for r in range(rows_k):
        ya = yk0 + r * dy_k
        yb = ya + dy_k
        ym = 0.5 * (ya + yb)
        for c in range(cols_k):
            xa = xk0 + c * dx_k
            xb = xa + dx_k
            xm = 0.5 * (xa + xb)
            # Diamond center slightly proud (+0.005) in bright SWEATER, corners in SWEATER_SHADE
            p_b = V(xm, ya, z_sw_f + 0.004)
            p_r = V(xb, ym, z_sw_f + 0.004)
            p_t = V(xm, yb, z_sw_f + 0.004)
            p_l = V(xa, ym, z_sw_f + 0.004)
            mb.face([p_b, p_r, p_t, p_l], SWEATER, out=(0, 0, 1))
            mb.face([V(xa, ya, z_sw_f), p_b, p_l], SWEATER_SHADE, out=(0, 0, 1))
            mb.face([p_b, V(xb, ya, z_sw_f), p_r], SWEATER_SHADE, out=(0, 0, 1))
            mb.face([p_r, V(xb, yb, z_sw_f), p_t], SWEATER_SHADE, out=(0, 0, 1))
            mb.face([p_l, p_t, V(xa, yb, z_sw_f)], SWEATER_SHADE, out=(0, 0, 1))

    # =========================================================================
    # 8. OLIVE UTILITY VEST (open front, pockets, folded collar)
    # =========================================================================
    mb.set_part("vest", bone="Torso")
    vy0, vy1 = 0.674, 1.142
    vx_bot, vx_top = 0.228, 0.208
    vz_fb, vz_ft = 0.136, 0.128
    vz_bb, vz_bt = -0.130, -0.120
    v_open = 0.082  # half-width of open center front showing cream cable-knit

    # Back panel
    mb.face([V(vx_bot, vy0, vz_bb), V(-vx_bot, vy0, vz_bb),
             V(-vx_top, vy1, vz_bt), V(vx_top, vy1, vz_bt)], VEST, out=(0, 0, -1))
    # Bottom hem underside (left & right vest panels)
    mb.face([V(-vx_bot, vy0, vz_bb), V(vx_bot, vy0, vz_bb),
             V(vx_bot, vy0, vz_fb), V(-vx_bot, vy0, vz_fb)], VEST_SHADE, out=(0, -1, 0))

    for side in (-1, 1):
        # Side panel
        mb.face([V(side * vx_bot, vy0, vz_fb), V(side * vx_bot, vy0, vz_bb),
                 V(side * vx_top, vy1, vz_bt), V(side * vx_top, vy1, vz_ft)], VEST, out=(side, 0, 0))
        # Front open vest panel
        mb.face([V(side * v_open, vy0, vz_fb), V(side * vx_bot, vy0, vz_fb),
                 V(side * vx_top, vy1, vz_ft), V(side * v_open, vy1, vz_ft)], VEST, out=(0, 0, 1))
        # Inner thickness edge along vertical opening
        mb.face([V(side * v_open, vy0, z_sw_f), V(side * v_open, vy0, vz_fb),
                 V(side * v_open, vy1, vz_ft), V(side * v_open, vy1, z_sw_f)], VEST_SHADE, out=(-side, 0, 0))
        # Shoulder top
        mb.face([V(side * v_open, vy1, vz_ft), V(side * vx_top, vy1, vz_ft),
                 V(side * vx_top, vy1, vz_bt), V(side * v_open, vy1, vz_bt)], VEST, out=(0, 1, 0))

        # Lower utility patch pocket + flap
        px0 = min(side * 0.102, side * 0.214)
        px1 = max(side * 0.102, side * 0.214)
        mb.box(px0, px1, 0.720, 0.875, 0.132, 0.160, VEST_POCKET, skip=("back",))
        mb.box(px0 - 0.002, px1 + 0.002, 0.855, 0.888, 0.134, 0.168, VEST_SHADE, skip=("back",))
        # Upper chest pocket flap accent
        mb.box(px0 + 0.008, px1 - 0.008, 0.960, 1.032, 0.128, 0.146, VEST_POCKET, skip=("back",))

    # Folded olive vest collar wrapping around back/sides of turtleneck
    mb.set_part("vest_collar", bone="Torso")
    vc_bot = [
        V(-0.095, 1.132,  0.122),
        V(-0.175, 1.132,  0.045),
        V(-0.168, 1.130, -0.115),
        V( 0.000, 1.128, -0.136),
        V( 0.168, 1.130, -0.115),
        V( 0.175, 1.132,  0.045),
        V( 0.095, 1.132,  0.122),
    ]
    vc_top = [
        V(-0.088, 1.192,  0.108),
        V(-0.158, 1.200,  0.038),
        V(-0.158, 1.200, -0.106),
        V( 0.000, 1.198, -0.128),
        V( 0.158, 1.200, -0.106),
        V( 0.158, 1.200,  0.038),
        V( 0.088, 1.192,  0.108),
    ]
    vc_in = [
        V(-0.075, 1.158,  0.092),
        V(-0.115, 1.162,  0.025),
        V(-0.112, 1.162, -0.086),
        V( 0.000, 1.162, -0.098),
        V( 0.112, 1.162, -0.086),
        V( 0.115, 1.162,  0.025),
        V( 0.075, 1.158,  0.092),
    ]
    for k in range(6):
        p0, p1, p2, p3 = vc_bot[k], vc_bot[k + 1], vc_top[k + 1], vc_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], VEST, out=V(mid.x, 0.1, mid.z))
        mb.face([vc_top[k], vc_top[k + 1], vc_in[k + 1], vc_in[k]], VEST_SHADE, out=(0, 1, 0))

    # =========================================================================
    # 9. CREAM KNIT SLEEVES WITH CHUNKY ROLLED CUFFS
    # =========================================================================
    mb.set_part("sleeves")
    # Arm_R (-X, free arm) hangs at side; Arm_L (+X, cane arm) angled slightly forward to grip cane
    arm_specs = [
        (-1, "Arm_R", V(-0.188, 1.072, 0.000), V(-0.348, 0.720, 0.012)),
        ( 1, "Arm_L", V( 0.188, 1.072, 0.000), V( 0.312, 0.735, 0.072)),
    ]
    for (side, bname, p_sh, p_wr) in arm_specs:
        mb.set_bone(bname)
        axis = (p_wr - p_sh).normalized()
        fwd = V(0.0, 0.0, 1.0)
        u = axis.cross(fwd).normalized()
        v = u.cross(axis).normalized()

        # 6-sided knit sleeve + chunky folded cuff at wrist
        stations = [
            (0.00, 0.080, 0.086),
            (0.45, 0.092, 0.096),
            (0.76, 0.088, 0.092),
            (0.79, 0.100, 0.104),  # rolled cuff ridge
            (0.98, 0.096, 0.100),  # rolled cuff outer lip
            (1.00, 0.074, 0.078),  # cuff inner bevel
        ]
        s_rings = []
        for (t, ru, rv) in stations:
            c = p_sh.lerp(p_wr, t)
            ring = []
            for k in range(6):
                a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
                ring.append(c + u * (ru * math.sin(a)) + v * (rv * math.cos(a)))
            s_rings.append(ring)

        def sleeve_col(i, k):
            if i >= 3:
                return SWEATER_RIB if k % 2 == 0 else SWEATER
            return SWEATER if k % 2 == 0 else SWEATER_RIB

        mb.loft(s_rings, sleeve_col, cap_bottom=False, cap_top=True, top_color=SWEATER_SHADE)

    # =========================================================================
    # 10. HANDS (2 chunky warm-skin mittens; Arm_L grips cane handle)
    # =========================================================================
    mb.set_part("hands")
    # Right hand (Arm_R, free)
    mb.set_bone("Arm_R")
    hr_specs = [
        (-0.348, 0.720, 0.012, 0.048, 0.052),
        (-0.362, 0.635, 0.020, 0.058, 0.064),
        (-0.346, 0.580, 0.018, 0.038, 0.044),
    ]
    hr_rings = []
    for (cx, cy, cz, rx, rz) in hr_specs:
        hr_rings.append([
            V(cx - rx, cy, cz + rz),
            V(cx + rx, cy, cz + rz),
            V(cx + rx, cy, cz - rz),
            V(cx - rx, cy, cz - rz),
        ])
    mb.loft(hr_rings, SKIN, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # Left hand (Arm_L, resting/gripping over top of wooden cane handle)
    mb.set_bone("Arm_L")
    hl_specs = [
        (0.312, 0.735, 0.072, 0.048, 0.052),
        (0.320, 0.658, 0.095, 0.060, 0.066),
        (0.312, 0.606, 0.098, 0.042, 0.048),
    ]
    hl_rings = []
    for (cx, cy, cz, rx, rz) in hl_specs:
        hl_rings.append([
            V(cx - rx, cy, cz + rz),
            V(cx + rx, cy, cz + rz),
            V(cx + rx, cy, cz - rz),
            V(cx - rx, cy, cz - rz),
        ])
    mb.loft(hl_rings, SKIN, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # =========================================================================
    # 11. WOODEN WALKING CANE (bone Cane, parented to Arm_L at grip)
    # =========================================================================
    mb.set_part("cane", bone="Cane")
    cx_c = 0.318
    cz_c = 0.112
    # Curved handle crook rising through the left hand and hooking slightly back
    crook_pts = [
        V(cx_c, 0.625, cz_c - 0.076),
        V(cx_c, 0.680, cz_c - 0.064),
        V(cx_c, 0.702, cz_c - 0.022),
        V(cx_c, 0.686, cz_c + 0.004),
        V(cx_c, 0.620, cz_c),
    ]
    mb.tube_path(crook_pts, 0.026, n=6, color=CANE_DARK, cap_start=True, cap_end=False)

    # Straight wooden shaft from handle down to rubber ferrule
    shaft_r0 = oval_ring(cx_c, 0.048, cz_c, 0.023, 0.023, n=6, phase=math.pi / 6)
    shaft_r1 = oval_ring(cx_c, 0.625, cz_c, 0.025, 0.025, n=6, phase=math.pi / 6)
    mb.loft([shaft_r0, shaft_r1], CANE, cap_bottom=False, cap_top=False)

    # Dark rubber ferrule tip resting on y = 0.000
    tip_r0 = oval_ring(cx_c, 0.000, cz_c, 0.029, 0.029, n=6, phase=math.pi / 6)
    tip_r1 = oval_ring(cx_c, 0.052, cz_c, 0.027, 0.027, n=6, phase=math.pi / 6)
    mb.loft([tip_r0, tip_r1], CANE_TIP, cap_bottom=True, cap_top=True, bot_color=CANE_TIP, top_color=CANE_TIP)

    # =========================================================================
    # 12. BACKPACK + REAR POUCH + BROWN SHOULDER STRAPS
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    bp_specs = [
        (0.695, -0.195, 0.155, 0.078),
        (0.875, -0.252, 0.192, 0.132),
        (1.135, -0.188, 0.142, 0.070),
    ]
    bp_rings = []
    for (y, cz, rx, rz) in bp_specs:
        pts = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6)
        pts = [V(p.x, p.y, min(p.z, -0.122)) for p in pts]
        bp_rings.append(pts)
    mb.loft(bp_rings, PACK, cap_bottom=True, cap_top=True, bot_color=PACK_DARK, top_color=PACK)

    # Chunky lower-back pouch pocket with darker flap
    mb.box(-0.132, 0.132, 0.745, 0.940, -0.376, -0.295, PACK_DARK, skip=("front",))
    mb.box(-0.136, 0.136, 0.910, 0.955, -0.382, -0.292, PACK, skip=("front",))

    # Warm brown shoulder straps curving over the olive vest shoulders
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        sw = 0.030
        path = [
            (side * 0.150, 1.140, -0.130),
            (side * 0.170, 1.154,  0.005),
            (side * 0.186, 1.106,  0.132),
            (side * 0.200, 0.945,  0.134),
            (side * 0.224, 0.800,  0.048),
        ]
        for i in range(len(path) - 1):
            x0, y0, z0 = path[i]
            x1, y1, z1 = path[i + 1]
            dx_w = sw if i < 3 else sw * 0.45
            dz_w = 0.0 if i < 3 else sw * 0.85
            p00 = V(x0 - dx_w, y0, z0 + dz_w * side)
            p01 = V(x0 + dx_w, y0, z0 - dz_w * side)
            p11 = V(x1 + dx_w, y1, z1 - dz_w * side)
            p10 = V(x1 - dx_w, y1, z1 + dz_w * side)
            out_hint = V(side * 0.35, 1.0 if i == 0 else 0.15, 1.0 if i >= 1 else 0.0)
            mb.face([p00, p01, p11, p10], STRAP, out=out_hint)

    # =========================================================================
    # 13. BROWN STRAIGHT-LEG TROUSERS
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.196, 0.196, 0.545, 0.690, -0.108, 0.108, PANTS, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t  = side * 0.012
        x_out_t = side * 0.194
        x_in_b  = side * 0.068
        x_out_b = side * 0.224
        rz_t = 0.104
        rz_b = 0.092
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.195,  rz_b),
            V(max(x_in_b, x_out_b), 0.195,  rz_b),
            V(max(x_in_b, x_out_b), 0.195, -rz_b),
            V(min(x_in_b, x_out_b), 0.195, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 14. DARK BROWN CHUNKY HIKING BOOTS + DARK SOLES
    # =========================================================================
    mb.set_part("boot_cuffs")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.146
        mb.box(cx - 0.056, cx + 0.056, 0.140, 0.215, -0.060, 0.060, BOOT_CUFF, skip=("top", "bottom"))

    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.146
        w = 0.074
        w_toe = 0.064
        z_heel = -0.096
        z_mid  =  0.064
        z_toe  =  0.166
        y_sole0 = 0.000
        y_sole1 = 0.042
        y_toe_top = 0.098
        y_collar  = 0.164

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

        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], BOOT, out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], BOOT, out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], BOOT, out=(0, 1, 0.5))
        mb.face([p_tl_m, p_tr_m, p_tr_h, p_tl_h], BOOT, out=(0, 1, 0))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], BOOT, out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h], BOOT, out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], BOOT, out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m], BOOT, out=(1, 0, 0))

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
    """24-frame looping Walk cycle with gentle elderly cadence and cane planting."""
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

        # Steady, slightly forward-leaning stride with gentle vertical bob
        pb_root = rig.pose.bones["Root"]
        bob = -0.022 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.075, -0.060 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.025 * c2, 0.095 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.045 + 0.026 * c2, -0.040 * s1, -0.015 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Shorter, measured stride
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.36 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.030, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.36 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.030, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Left arm holds the cane: reaches forward & plants with opposite (right) leg stride
        arm_l_pitch = 0.24 * s1 + 0.08
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_pitch, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotate Cane so the shaft stays nearly vertical and taps cleanly
        pb_cane = rig.pose.bones["Cane"]
        pb_cane.rotation_euler = (-arm_l_pitch * 0.85, 0.0, 0.0)
        pb_cane.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm swings freely opposite the left arm
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.34 * s1, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: calm breathing, gentle weight shift, head glance, steady cane."""
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

        # Gentle weight settle & breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.025, 0.018 * s1, 0.015 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.025 * s1, -0.012 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious, relaxed look-around
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.028 * s2, 0.14 * s1, 0.020 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs stay grounded
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm rests calmly on cane; cane counter-rotates to stay planted
        arm_l_pitch = 0.03 * s2
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_pitch, 0.0, 0.012 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_cane = rig.pose.bones["Cane"]
        pb_cane.rotation_euler = (-arm_l_pitch, 0.0, -0.012 * s1)
        pb_cane.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm gentle relaxed drift
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.045 * s1, 0.0, -0.018 * s2)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Cane child of Arm_L) with Walk and Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonElderRig")
    rig = bpy.data.objects.new("PersonElderRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.620, 0.000), ( 0.000, 0.720, 0.000)),
        ("Torso", "Root",  ( 0.000, 0.680, 0.000), ( 0.000, 1.120, 0.000)),
        ("Head",  "Torso", ( 0.000, 1.160, 0.000), ( 0.000, 1.460, 0.000)),
        ("Arm_L", "Torso", ( 0.188, 1.065, 0.000), ( 0.188, 1.225, 0.000)),
        ("Arm_R", "Torso", (-0.188, 1.065, 0.000), (-0.188, 1.225, 0.000)),
        ("Cane",  "Arm_L", ( 0.318, 0.655, 0.105), ( 0.318, 0.815, 0.105)),
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

    # Leave Walk active on the rig for default viewport playback
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
        (-1.65, math.radians(52)),   # Front-3/4 matching reference angle (facing right)
        (-0.55, math.radians(0)),    # Front
        ( 0.55, math.radians(90)),   # Side
        ( 1.65, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 4.6
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=55):
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.12
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.0
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


def main():
    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonElder")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonElder")
    mb.bm.to_mesh(me)
    mb.bm.free()

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonElder", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=55)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=32)

    print("=== PersonElder Stats ===")
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


if __name__ == "__main__":
    main()
