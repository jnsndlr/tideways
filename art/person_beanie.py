# Builds an ultra-low-poly stylized coastal hiker / fisherman in Blender matching the reference
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_beanie.py)
# Saves art/person_beanie.blend, exports assets/models/person_beanie.glb (rigged + Walk cycle),
# and renders art/person_beanie_preview.png and art/person_beanie_walk_preview.png.
#
# Game frame: +Z forward, +Y up, feet on ground at y = 0, ~1.73 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_beanie.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_beanie.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_beanie_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_beanie_walk_preview.png")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN       = col_srgb(0.96, 0.72, 0.51)
BEARD      = col_srgb(0.37, 0.26, 0.20)
BEARD_DARK = col_srgb(0.29, 0.20, 0.15)
EYE        = col_srgb(0.12, 0.13, 0.16)
BEANIE     = col_srgb(0.24, 0.33, 0.42)
BEANIE_CUF = col_srgb(0.28, 0.38, 0.48)
COAT       = col_srgb(0.95, 0.75, 0.22)
COAT_SHADE = col_srgb(0.86, 0.65, 0.17)
SHIRT      = col_srgb(0.21, 0.31, 0.36)
PANTS      = col_srgb(0.24, 0.25, 0.28)
PACK       = col_srgb(0.22, 0.22, 0.24)
BOOT       = col_srgb(0.62, 0.43, 0.26)
BOOT_CUFF  = col_srgb(0.54, 0.36, 0.21)
SOLE       = col_srgb(0.27, 0.21, 0.17)


def G(p):
    """Game frame (X right, Y up, Z forward) -> Blender frame (X right, -Z forward, Y up)."""
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


def oval_ring(cx, cy, cz, rx, rz, n=8, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=8, phase=math.pi / 8):
    """8-sided ring tilted backward around X by tilt_rad (higher at +Z front, lower at -Z back)."""
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
    # 1. HEAD (broad 8-sided low-poly head, y = 1.18 .. 1.56, topped by beanie)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,    cz,     rx,    rz)
        (1.18,  0.008, 0.150, 0.145),  # 0: chin/jaw base
        (1.29,  0.014, 0.215, 0.200),  # 1: lower cheek / beard top
        (1.48,  0.010, 0.218, 0.205),  # 2: brow / under beanie cuff
        (1.56,  0.000, 0.195, 0.190),  # 3: tucked inside beanie
    ]
    head_rings = []
    for (y, cz, rx, rz) in head_specs:
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            ring.append(V(rx * math.sin(a) * 1.03, y, cz + rz * math.cos(a) * 1.03))
        head_rings.append(ring)

    # Color map on head:
    # - band i=0 (chin->lower cheek): BEARD on front/sides (k=5,6,7,0,1), BEARD/hair on back (k=2,3,4)
    # - band i=1 (lower cheek->brow): SKIN on front (k=6,7,0), BEARD/hair on sides/back (k=1,2,3,4,5)
    # - band i=2 (brow->inside beanie): SKIN on front (k=6,7,0), BEARD on sides/back
    def head_color(i, k):
        if i == 0:
            return BEARD
        return SKIN if k in (6, 7, 0) else BEARD

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)
    # Bottom cap (chin under-plane in BEARD)
    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], BEARD, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], BEARD, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], BEARD, out=(0, -1, 0))

    # =========================================================================
    # 2. FULL BEARD + MUSTACHE (snug, sculpted low-poly fisherman beard)
    # =========================================================================
    mb.set_part("beard", bone="Head")
    # Hugs the jaw/cheeks cleanly with a slightly raised central mustache arch
    b_bot = [
        V(-0.200, 1.215,  0.045),  # back-left jaw
        V(-0.150, 1.182,  0.185),  # front-left chin
        V(-0.072, 1.170,  0.222),  # chin left
        V( 0.072, 1.170,  0.222),  # chin right
        V( 0.150, 1.182,  0.185),  # front-right chin
        V( 0.200, 1.215,  0.045),  # back-right jaw
    ]
    b_mid = [
        V(-0.224, 1.300,  0.045),  # sideburn left
        V(-0.175, 1.292,  0.195),  # cheek left (dips slightly below eyes)
        V(-0.078, 1.330,  0.230),  # mustache arch left
        V( 0.078, 1.330,  0.230),  # mustache arch right
        V( 0.175, 1.292,  0.195),  # cheek right
        V( 0.224, 1.300,  0.045),  # sideburn right
    ]
    for k in range(5):
        p0, p1, p2, p3 = b_bot[k], b_bot[k + 1], b_mid[k + 1], b_mid[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], BEARD, out=V(mid.x, -0.1, mid.z))
    b_in = [
        V(-0.200, 1.300,  0.040),
        V(-0.155, 1.292,  0.178),
        V(-0.074, 1.324,  0.202),
        V( 0.074, 1.324,  0.202),
        V( 0.155, 1.292,  0.178),
        V( 0.200, 1.300,  0.040),
    ]
    for k in range(5):
        mb.face([b_mid[k], b_mid[k + 1], b_in[k + 1], b_in[k]], BEARD, out=(0, 1, 0))
    b_in_bot = [
        V(-0.175, 1.200,  0.040),
        V(-0.130, 1.180,  0.145),
        V(-0.065, 1.175,  0.172),
        V( 0.065, 1.175,  0.172),
        V( 0.130, 1.180,  0.145),
        V( 0.175, 1.200,  0.040),
    ]
    for k in range(5):
        mb.face([b_bot[k + 1], b_bot[k], b_in_bot[k], b_in_bot[k + 1]], BEARD_DARK, out=(0, -1, 0))

    # =========================================================================
    # 3. FISHERMAN'S BEANIE (tilted-back navy knit cap with chunky folded cuff)
    # =========================================================================
    mb.set_part("beanie", bone="Head")
    tilt = math.radians(16.0)
    cuff_bot = tilted_ring(0.0, 1.438, -0.004, 0.246, 0.242, tilt)
    cuff_top = tilted_ring(0.0, 1.532, -0.018, 0.250, 0.246, tilt)
    dome_0   = tilted_ring(0.0, 1.542, -0.020, 0.230, 0.226, tilt)
    dome_1   = tilted_ring(0.0, 1.635, -0.036, 0.195, 0.192, tilt)
    dome_2   = tilted_ring(0.0, 1.700, -0.046, 0.105, 0.102, tilt)

    # Folded cuff outer band + underside + top step into dome
    mb.loft([cuff_bot, cuff_top], BEANIE_CUF, cap_bottom=False, cap_top=False)
    # Subtle underside rim of cuff (connects cuff_bot inward to head)
    cuff_in = tilted_ring(0.0, 1.455, -0.012, 0.205, 0.198, tilt)
    mb.loft([cuff_in, cuff_bot], BEANIE, cap_bottom=False, cap_top=False)
    # Step from cuff top into dome
    mb.loft([cuff_top, dome_0], BEANIE, cap_bottom=False, cap_top=False)
    # Beanie dome
    mb.loft([dome_0, dome_1, dome_2], BEANIE, cap_bottom=False, cap_top=False)
    # Top cap of beanie (3 quads = 6 tris)
    mb.face([dome_2[7], dome_2[0], dome_2[3], dome_2[4]], BEANIE, out=(0, 1, 0))
    mb.face([dome_2[0], dome_2[1], dome_2[2], dome_2[3]], BEANIE, out=(0, 1, 0))
    mb.face([dome_2[4], dome_2[5], dome_2[6], dome_2[7]], BEANIE, out=(0, 1, 0))

    # =========================================================================
    # 4. EARS (2 compact tucked-in low-poly wedges)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.205
        x_out = side * 0.244
        y0, y1 = 1.295, 1.395
        z0, z1 = -0.025, 0.045
        p_out_b = V(x_out, y0 + 0.018, z0 + 0.015)
        p_out_f = V(x_out, y0 + 0.018, z1 - 0.010)
        p_out_t = V(x_out, y1 - 0.018, (z0 + z1) * 0.5)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_out_t, p_out_f], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_out_b, p_out_t], SKIN, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_out_f, p_out_b], SKIN, out=(0, -1, 0))
        mb.face([p_out_b, p_out_f, p_out_t], SKIN, out=(side, 0, 0))

    # =========================================================================
    # 5. EYES (2 vertical dark pill hexagons)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.214
    for side in (-1, 1):
        cx = side * 0.068
        cy = 1.400
        rx = 0.020
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
    # 6. NECK (6-sided short cylinder)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.10, 0.0, 0.074, 0.068, n=6, phase=math.pi / 6)
    neck_r1 = oval_ring(0.0, 1.19, 0.0, 0.070, 0.064, n=6, phase=math.pi / 6)
    mb.loft([neck_r0, neck_r1], SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 7. INNER SHIRT (dark slate-teal tee visible in V-opening of yellow coat)
    # =========================================================================
    mb.set_part("shirt", bone="Torso")
    sz_f = 0.105
    mb.face([V(-0.08, 0.84, sz_f), V(0.08, 0.84, sz_f), V(0.08, 1.13, sz_f), V(-0.08, 1.13, sz_f)], SHIRT, out=(0, 0, 1))
    mb.face([V(-0.09, 1.13, sz_f), V(0.09, 1.13, sz_f), V(0.09, 1.13, -0.09), V(-0.09, 1.13, -0.09)], SHIRT, out=(0, 1, 0))

    # =========================================================================
    # 8. YELLOW HOODED RAINCOAT (half-zipped front + folded hood collar)
    # =========================================================================
    mb.set_part("raincoat", bone="Torso")
    jy0, jy_zip, jy1 = 0.675, 0.855, 1.138
    jx_bot, jx_mid, jx_top = 0.224, 0.214, 0.198
    jz_fb, jz_fm, jz_ft = 0.128, 0.125, 0.118
    jz_bb, jz_bt = -0.125, -0.115
    v_top = 0.052  # half-width of V-opening at collar
    v_bot = 0.012  # narrow base of V-opening at zipper

    # Back panel
    mb.face([V(jx_bot, jy0, jz_bb), V(-jx_bot, jy0, jz_bb), V(-jx_top, jy1, jz_bt), V(jx_top, jy1, jz_bt)], COAT, out=(0, 0, -1))
    # Lower closed front panel (below zipper)
    mb.face([V(-jx_bot, jy0, jz_fb), V(jx_bot, jy0, jz_fb), V(jx_mid, jy_zip, jz_fm), V(-jx_mid, jy_zip, jz_fm)], COAT, out=(0, 0, 1))
    # Bottom hem underside
    mb.face([V(-jx_bot, jy0, jz_bb), V(jx_bot, jy0, jz_bb), V(jx_bot, jy0, jz_fb), V(-jx_bot, jy0, jz_fb)], COAT_SHADE, out=(0, -1, 0))

    for side in (-1, 1):
        # Side panel
        mb.face([V(side * jx_bot, jy0, jz_fb), V(side * jx_bot, jy0, jz_bb),
                 V(side * jx_top, jy1, jz_bt), V(side * jx_top, jy1, jz_ft)], COAT, out=(side, 0, 0))
        # Upper front lapel panel (forming V-opening around dark shirt)
        mb.face([V(side * v_bot, jy_zip, jz_fm), V(side * jx_mid, jy_zip, jz_fm),
                 V(side * jx_top, jy1, jz_ft),   V(side * v_top, jy1, jz_ft)], COAT, out=(0, 0, 1))
        # Inner thickness edge along V-opening
        mb.face([V(side * v_bot, jy_zip, sz_f),  V(side * v_bot, jy_zip, jz_fm),
                 V(side * v_top, jy1, jz_ft),    V(side * v_top, jy1, sz_f)], COAT_SHADE, out=(-side, 0, 0))
        # Shoulder top
        mb.face([V(side * v_top, jy1, jz_ft), V(side * jx_top, jy1, jz_ft),
                 V(side * jx_top, jy1, jz_bt), V(side * v_top, jy1, jz_bt)], COAT, out=(0, 1, 0))

    # Folded Raincoat Hood resting around back/sides of neck (chunky yellow collar roll!)
    mb.set_part("hood", bone="Torso")
    # 5-point U-shaped collar roll wrapping from left front lapel -> left -> back -> right -> right front lapel
    h_bot = [
        V(-0.085, 1.125,  0.115),
        V(-0.185, 1.125,  0.045),
        V(-0.175, 1.120, -0.115),
        V( 0.000, 1.115, -0.145),
        V( 0.175, 1.120, -0.115),
        V( 0.185, 1.125,  0.045),
        V( 0.085, 1.125,  0.115),
    ]
    h_top = [
        V(-0.068, 1.185,  0.095),
        V(-0.165, 1.195,  0.035),
        V(-0.165, 1.195, -0.105),
        V( 0.000, 1.190, -0.135),
        V( 0.165, 1.195, -0.105),
        V( 0.165, 1.195,  0.035),
        V( 0.068, 1.185,  0.095),
    ]
    h_in = [
        V(-0.055, 1.140,  0.075),
        V(-0.100, 1.145,  0.020),
        V(-0.095, 1.145, -0.075),
        V( 0.000, 1.145, -0.090),
        V( 0.095, 1.145, -0.075),
        V( 0.100, 1.145,  0.020),
        V( 0.055, 1.140,  0.075),
    ]
    for k in range(6):
        p0, p1, p2, p3 = h_bot[k], h_bot[k + 1], h_top[k + 1], h_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], COAT, out=V(mid.x, 0.1, mid.z))
        mb.face([h_top[k], h_top[k + 1], h_in[k + 1], h_in[k]], COAT_SHADE, out=(0, 1, 0))

    # =========================================================================
    # 9. SLEEVES (2 × 4-sided boxy yellow sleeves with cuff bevel)
    # =========================================================================
    mb.set_part("sleeves")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        p_sh = V(side * 0.180, 1.070, 0.000)
        p_wr = V(side * 0.365, 0.705, 0.015)
        axis = (p_wr - p_sh).normalized()
        fwd = V(0.0, 0.0, 1.0)
        u = axis.cross(fwd).normalized()
        v = u.cross(axis).normalized()

        stations = [
            (0.00, 0.076, 0.084),
            (0.84, 0.094, 0.098),
            (1.00, 0.076, 0.080),
        ]
        s_rings = []
        for (t, ru, rv) in stations:
            c = p_sh.lerp(p_wr, t)
            s_rings.append([
                c + u * (-ru) + v * ( rv),
                c + u * ( ru) + v * ( rv),
                c + u * ( ru) + v * (-rv),
                c + u * (-ru) + v * (-rv),
            ])
        mb.loft(s_rings, COAT, cap_bottom=False, cap_top=True, top_color=COAT_SHADE)

    # =========================================================================
    # 10. HANDS (2 chunky 4-sided beveled mitten blocks)
    # =========================================================================
    mb.set_part("hands")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        h_specs = [
            (side * 0.355, 0.705, 0.015, 0.048, 0.052),
            (side * 0.372, 0.618, 0.022, 0.056, 0.064),
            (side * 0.354, 0.562, 0.020, 0.036, 0.042),
        ]
        h_rings = []
        for (cx, cy, cz, rx, rz) in h_specs:
            h_rings.append([
                V(cx - rx, cy, cz + rz),
                V(cx + rx, cy, cz + rz),
                V(cx + rx, cy, cz - rz),
                V(cx - rx, cy, cz - rz),
            ])
        mb.loft(h_rings, SKIN, cap_bottom=True, cap_top=False, bot_color=SKIN)

    # =========================================================================
    # 11. BACKPACK + REAR POCKET + SHOULDER STRAPS
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    bp_specs = [
        (0.665, -0.185, 0.148, 0.072),
        (0.845, -0.240, 0.188, 0.128),
        (1.135, -0.180, 0.138, 0.066),
    ]
    bp_rings = []
    for (y, cz, rx, rz) in bp_specs:
        pts = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6)
        pts = [V(p.x, p.y, min(p.z, -0.114)) for p in pts]
        bp_rings.append(pts)
    mb.loft(bp_rings, PACK, cap_bottom=True, cap_top=True, bot_color=PACK, top_color=PACK)

    # Chunky lower-back pouch pocket hugging the pack
    mb.box(-0.125, 0.125, 0.720, 0.920, -0.362, -0.285, PACK, skip=("front",))

    # Shoulder straps curving over yellow shoulders
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        sw = 0.028
        path = [
            (side * 0.148, 1.136, -0.125),
            (side * 0.165, 1.150,  0.005),
            (side * 0.178, 1.102,  0.122),
            (side * 0.192, 0.935,  0.124),
            (side * 0.218, 0.790,  0.045),
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
            mb.face([p00, p01, p11, p10], PACK, out=out_hint)

    # =========================================================================
    # 12. PANTS (dark charcoal A-line cropped pants)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.190, 0.190, 0.555, 0.690, -0.104, 0.104, PANTS, skip=("top",))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t  = side * 0.012
        x_out_t = side * 0.188
        x_in_b  = side * 0.078
        x_out_b = side * 0.224
        rz_t = 0.098
        rz_b = 0.084
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.220,  rz_b),
            V(max(x_in_b, x_out_b), 0.220,  rz_b),
            V(max(x_in_b, x_out_b), 0.220, -rz_b),
            V(min(x_in_b, x_out_b), 0.220, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS)

    # =========================================================================
    # 13. BOOT CUFF / ANKLE (warm brown boot upper collar tucked under pants)
    # =========================================================================
    mb.set_part("boot_cuffs")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.152
        mb.box(cx - 0.052, cx + 0.052, 0.145, 0.230, -0.055, 0.055, BOOT_CUFF, skip=("top", "bottom"))

    # =========================================================================
    # 14. HIKING BOOTS (chunky brown leather boots with thick dark lug soles)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.152
        w = 0.072
        w_toe = 0.062
        z_heel = -0.092
        z_mid  =  0.062
        z_toe  =  0.160
        y_sole0 = 0.000
        y_sole1 = 0.040
        y_toe_top = 0.094
        y_collar  = 0.162

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


def build_rig_and_walk(ob, mb, coll):
    """Build a minimal 7-bone rig with rigid per-part weights and a 24-frame looping Walk cycle."""
    arm_data = bpy.data.armatures.new("PersonBeanieRig")
    rig = bpy.data.objects.new("PersonBeanieRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.620, 0.000), ( 0.000, 0.720, 0.000)),
        ("Torso", "Root",  ( 0.000, 0.680, 0.000), ( 0.000, 1.120, 0.000)),
        ("Head",  "Torso", ( 0.000, 1.140, 0.000), ( 0.000, 1.450, 0.000)),
        ("Arm_L", "Torso", ( 0.180, 1.060, 0.000), ( 0.180, 1.220, 0.000)),
        ("Arm_R", "Torso", (-0.180, 1.060, 0.000), (-0.180, 1.220, 0.000)),
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

    action = bpy.data.actions.new(name="Walk")
    rig.animation_data_create()
    rig.animation_data.action = action

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")

    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"

    cycle_len = 24
    for frame in range(1, cycle_len + 2, 2):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        c1 = math.cos(phi)
        c2 = math.cos(2.0 * phi)

        # Slightly heavier, sturdy hiking stride!
        pb_root = rig.pose.bones["Root"]
        bob = -0.026 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.06, -0.075 * s1, 0.042 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * c2, 0.12 * s1, -0.025 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * c2, -0.045 * s1, -0.015 * c1)
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
        pb_arm_l.rotation_euler = (0.38 * s1, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.38 * s1, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    bpy.ops.object.mode_set(mode="OBJECT")
    scene.frame_set(1)
    return rig, action


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
        (-1.65, math.radians(38)),   # Front-3/4 matching reference angle
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


def render_walk_preview(rig, obj, out_path):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 20
    scene.cycles.use_denoising = False

    world = bpy.data.worlds.get("PreviewWorld") or bpy.data.worlds.new("PreviewWorld")
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.94, 0.95, 0.96, 1.0)
    bg.inputs["Strength"].default_value = 0.95
    scene.world = world

    key_data = bpy.data.lights.new("WalkKey", type="SUN")
    key_data.energy = 2.6
    key_data.angle = math.radians(18.0)
    key_obj = bpy.data.objects.new("WalkKey", key_data)
    scene.collection.objects.link(key_obj)
    key_obj.rotation_euler = (math.radians(46), math.radians(10), math.radians(-35))

    fill_data = bpy.data.lights.new("WalkFill", type="SUN")
    fill_data.energy = 0.85
    fill_data.color = (0.88, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("WalkFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("WalkFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    frames = [1, 5, 9, 13, 17, 21]
    snapshots = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.hide_render = True
    for idx, f in enumerate(frames):
        scene.frame_set(f)
        depsgraph.update()
        eval_obj = obj.evaluated_get(depsgraph)
        snap_mesh = bpy.data.meshes.new_from_object(eval_obj)
        snap_obj = bpy.data.objects.new(f"WalkSnap_{f}", snap_mesh)
        xpos = (idx - 2.5) * 1.08
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(52))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("WalkCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 6.7
    cam_obj = bpy.data.objects.new("WalkCam", cam_data)
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
    scene.frame_set(1)
    for o in [key_obj, fill_obj, floor, cam_obj]:
        bpy.data.objects.remove(o, do_unlink=True)
    for (so, sm) in snapshots:
        bpy.data.objects.remove(so, do_unlink=True)
        bpy.data.meshes.remove(sm)


def main():
    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonBeanie")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonBeanie")
    mb.bm.to_mesh(me)
    mb.bm.free()

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonBeanie", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, action = build_rig_and_walk(ob, mb, coll)

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
        export_frame_range=True,
        export_force_sampling=True,
    )

    render_walk_preview(rig, ob, WALK_PREVIEW_PATH)

    print("=== PersonBeanie Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animation:       {action.name} (frames {bpy.context.scene.frame_start}-{bpy.context.scene.frame_end} @ {bpy.context.scene.render.fps} fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:16s}: {cnt}")
    print(f"Saved blend:     {BLEND_PATH}")
    print(f"Exported glb:    {GLB_PATH}")
    print(f"Preview png:     {PREVIEW_PATH}")
    print(f"Walk preview:    {WALK_PREVIEW_PATH}")


if __name__ == "__main__":
    main()
