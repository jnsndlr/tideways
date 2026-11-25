# Builds an ultra-low-poly stylized person in Blender matching the reference character
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_low.py)
# Saves art/person_low.blend, exports assets/models/person_low.glb, and renders art/person_low_preview.png.
#
# Game frame: +Z forward, +Y up, feet on ground at y = 0, ~1.70 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_low.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_low.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_low_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_low_walk_preview.png")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched to reference image (sRGB -> linear)
SKIN   = col_srgb(0.98, 0.78, 0.59)
HAIR   = col_srgb(0.51, 0.30, 0.20)
EYE    = col_srgb(0.14, 0.15, 0.18)
JACKET = col_srgb(0.35, 0.62, 0.55)
SHIRT  = col_srgb(0.96, 0.95, 0.93)
STRIPE = col_srgb(0.51, 0.65, 0.67)
PANTS  = col_srgb(0.30, 0.31, 0.35)
PACK   = col_srgb(0.24, 0.24, 0.26)
SHOE   = col_srgb(0.94, 0.92, 0.89)
SOLE   = col_srgb(0.83, 0.80, 0.75)


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
        """Create a flat-shaded face with per-face vertex color. Wound to match `out` if given."""
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


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + HAIR CAP (8-sided broad chibi low-poly head, y = 1.18 .. 1.69)
    # =========================================================================
    mb.set_part("head_and_hair", bone="Head")
    # 8-sided ring with flat front face centered on +Z (face k=7: verts 7 -> 0).
    # Make front/side vertices slightly squarish (superellipse-like) so the face is broad & cute!
    head_specs = [
        # (y,    cz,     rx,    rz)
        (1.18,  0.005, 0.145, 0.140),  # 0: chin/jaw base
        (1.26,  0.012, 0.215, 0.200),  # 1: lower cheek
        (1.48,  0.008, 0.220, 0.208),  # 2: brow / forehead top
        (1.60, -0.002, 0.195, 0.195),  # 3: upper crown
        (1.68, -0.008, 0.105, 0.105),  # 4: top cap
    ]
    head_rings = []
    for (y, cz, rx, rz) in head_specs:
        ring = []
        for k in range(8):
            a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
            sx, cz_a = math.sin(a), math.cos(a)
            # Subtle squaring so the front face is broad like the reference
            sq = 1.04
            ring.append(V(rx * sx * sq, y, cz + rz * cz_a * sq))
        head_rings.append(ring)

    # Slight hair volume offset on upper/back rings
    for i in (2, 3, 4):
        for k in range(8):
            if i >= 3 or k in (1, 2, 3, 4, 5):
                p = head_rings[i][k]
                head_rings[i][k] = V(p.x * 1.04, p.y, p.z * 1.04)

    def head_color(i, k):
        if i >= 2:  # brow -> crown -> top
            return HAIR
        if i == 1:  # lower cheek -> brow (broad skin face on k=6,7,0; hair on sides/back k=1..5)
            return SKIN if k in (6, 7, 0) else HAIR
        # i == 0: chin -> lower cheek (hair only on back k=2,3,4)
        return HAIR if k in (2, 3, 4) else SKIN

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 8
        c1 = sum(r1, Vector()) / 8
        cmid = (c0 + c1) * 0.5
        for k in range(8):
            kn = (k + 1) % 8
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 2 and k == 7:
                # Clean inverted-V hair part flush with the crown edge (no gap!)
                part_apex = (p2 + p3) * 0.5
                mb.face([p0, p1, part_apex], SKIN, out=(0, 0, 1))
                mb.face([p0, part_apex, p3], HAIR, out=(0, 0, 1))
                mb.face([p1, p2, part_apex], HAIR, out=(0, 0, 1))
            elif i == 1 and k == 0:
                # Front-right temple: open cheek, crisp sideburn/bang framing upper temple
                p_temple = p1.lerp(p2, 0.52)
                mb.face([p0, p1, p_temple, p3], SKIN, out=(mid - cmid))
                mb.face([p_temple, p2, p3], HAIR, out=(mid - cmid))
            elif i == 1 and k == 6:
                # Front-left temple: mirror of k=0
                p_temple = p0.lerp(p3, 0.52)
                mb.face([p0, p1, p2, p_temple], SKIN, out=(mid - cmid))
                mb.face([p_temple, p2, p3], HAIR, out=(mid - cmid))
            else:
                mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))

    # Top & bottom caps (3 quads each = 6 tris each)
    rt = head_rings[-1]
    mb.face([rt[7], rt[0], rt[3], rt[4]], HAIR, out=(0, 1, 0))
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR, out=(0, 1, 0))
    mb.face([rt[4], rt[5], rt[6], rt[7]], HAIR, out=(0, 1, 0))

    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], SKIN, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], SKIN, out=(0, -1, 0))

    # =========================================================================
    # 2. PONYTAIL (chunky 5-sided faceted teardrop, bold silhouette like ref!)
    # =========================================================================
    mb.set_part("ponytail", bone="Ponytail")
    # Ponytail sweeps down-back: rings are oriented perpendicular to the sweep axis!
    pt_stations = [
        # (center,               rx,    ry_l,  tilt_deg)
        (V(0.0, 1.41, -0.185),   0.058, 0.068, 30.0),
        (V(0.0, 1.34, -0.320),   0.115, 0.130, 48.0),
        (V(0.0, 1.19, -0.375),   0.088, 0.098, 65.0),
    ]
    pt_tip = V(0.0, 1.04, -0.400)

    pt_rings = []
    for (ctr, rx, ry_l, tilt_deg) in pt_stations:
        rad = math.radians(tilt_deg)
        ring = []
        for k in range(5):
            a = 2.0 * math.pi * k / 5.0 + math.pi / 10.0
            lx = rx * math.sin(a)
            ly = ry_l * math.cos(a)
            # Perpendicular to (-Z, -Y) sweep is (+Y*cos, -Z*sin) -> true 3D round cross-section!
            py = ctr.y + ly * math.cos(rad)
            pz = ctr.z - ly * math.sin(rad)
            ring.append(V(ctr.x + lx, py, pz))
        pt_rings.append(ring)

    mb.loft(pt_rings, HAIR, cap_bottom=False, cap_top=False)
    last_r = pt_rings[-1]
    c_last = sum(last_r, Vector()) / 5
    for k in range(5):
        kn = (k + 1) % 5
        mid = (last_r[k] + last_r[kn] + pt_tip) / 3.0
        mb.face([last_r[k], last_r[kn], pt_tip], HAIR, out=(mid - c_last))

    # =========================================================================
    # 3. EARS (2 compact tucked-in low-poly wedges, 6 tris each = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.205
        x_out = side * 0.242
        y0, y1 = 1.295, 1.395
        z0, z1 = -0.025, 0.045
        p_out_b = V(x_out, y0 + 0.018, z0 + 0.015)
        p_out_f = V(x_out, y0 + 0.018, z1 - 0.010)
        p_out_t = V(x_out, y1 - 0.018, (z0 + z1) * 0.5)
        # Compact 5-vert ear nub (6 tris per ear!)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_out_t, p_out_f], SKIN, out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_out_b, p_out_t], SKIN, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_out_f, p_out_b], SKIN, out=(0, -1, 0))
        mb.face([p_out_b, p_out_f, p_out_t], SKIN, out=(side, 0, 0))

    # =========================================================================
    # 4. EYES (2 vertical dark low-poly pill hexagons, 4 tris each = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    # Front face plane is at z ≈ 0.010 + 0.204 * 1.04 * cos(22.5 deg) ≈ 0.206
    z_eye = 0.214
    for side in (-1, 1):
        cx = side * 0.068
        cy = 1.385
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
    # 5. NECK (6-sided short cylinder)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.10, 0.0, 0.072, 0.066, n=6, phase=math.pi / 6)
    neck_r1 = oval_ring(0.0, 1.19, 0.0, 0.068, 0.062, n=6, phase=math.pi / 6)
    mb.loft([neck_r0, neck_r1], SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 6. TORSO: INNER STRIPED SHIRT (front visible panel with 2 stripes)
    # =========================================================================
    mb.set_part("shirt", bone="Torso")
    sx = 0.145
    sz_f = 0.098
    sz_b = -0.090
    bands = [
        (0.68, 0.77, SHIRT),
        (0.77, 0.84, STRIPE),
        (0.84, 0.92, SHIRT),
        (0.92, 0.99, STRIPE),
        (0.99, 1.12, SHIRT),
    ]
    for (yb, yt, col) in bands:
        mb.face([V(-sx, yb, sz_f), V(sx, yb, sz_f), V(sx, yt, sz_f), V(-sx, yt, sz_f)], col, out=(0, 0, 1))
    mb.face([V(-sx, 1.12, sz_f), V(sx, 1.12, sz_f), V(sx, 1.12, sz_b), V(-sx, 1.12, sz_b)], SHIRT, out=(0, 1, 0))

    # =========================================================================
    # 7. OPEN TEAL JACKET (boxy A-line jacket with open front)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    jy0, jy1 = 0.675, 1.135
    j_open_bot = 0.066
    j_open_top = 0.056
    jx_bot = 0.220
    jx_top = 0.195
    jz_f_bot = 0.125
    jz_f_top = 0.115
    jz_b_bot = -0.122
    jz_b_top = -0.112

    mb.face([V(jx_bot, jy0, jz_b_bot), V(-jx_bot, jy0, jz_b_bot), V(-jx_top, jy1, jz_b_top), V(jx_top, jy1, jz_b_top)], JACKET, out=(0, 0, -1))
    for side in (-1, 1):
        xo_b = side * jx_bot
        xo_t = side * jx_top
        xi_b = side * j_open_bot
        xi_t = side * j_open_top
        mb.face([V(xo_b, jy0, jz_f_bot), V(xo_b, jy0, jz_b_bot), V(xo_t, jy1, jz_b_top), V(xo_t, jy1, jz_f_top)], JACKET, out=(side, 0, 0))
        mb.face([V(xi_b, jy0, jz_f_bot), V(xo_b, jy0, jz_f_bot), V(xo_t, jy1, jz_f_top), V(xi_t, jy1, jz_f_top)], JACKET, out=(0, 0, 1))
        mb.face([V(xi_b, jy0, sz_f), V(xi_b, jy0, jz_f_bot), V(xi_t, jy1, jz_f_top), V(xi_t, jy1, sz_f)], JACKET, out=(-side, 0, 0))
        mb.face([V(xi_t, jy1, jz_f_top), V(xo_t, jy1, jz_f_top), V(xo_t, jy1, jz_b_top), V(xi_t, jy1, jz_b_top)], JACKET, out=(0, 1, 0))
        mb.face([V(xi_b, jy0, jz_b_bot), V(xo_b, jy0, jz_b_bot), V(xo_b, jy0, jz_f_bot), V(xi_b, jy0, jz_f_bot)], JACKET, out=(0, -1, 0))
    mb.face([V(-j_open_bot, jy0, jz_b_bot), V(j_open_bot, jy0, jz_b_bot), V(j_open_bot, jy0, sz_b), V(-j_open_bot, jy0, sz_b)], JACKET, out=(0, -1, 0))
    mb.face([V(-j_open_top, jy1, sz_b), V(j_open_top, jy1, sz_b), V(j_open_top, jy1, jz_b_top), V(-j_open_top, jy1, jz_b_top)], JACKET, out=(0, 1, 0))

    # =========================================================================
    # 8. SLEEVES (2 × 4-sided boxy flared jacket sleeves with cuff bevel = 36 tris)
    # =========================================================================
    mb.set_part("sleeves")
    for side in (-1, 1):
        mb.set_bone("Arm_L" if side > 0 else "Arm_R")
        # Seamless tuck into jacket shoulder
        p_sh = V(side * 0.175, 1.070, 0.000)
        p_wr = V(side * 0.365, 0.705, 0.015)
        axis = (p_wr - p_sh).normalized()
        fwd = V(0.0, 0.0, 1.0)
        u = axis.cross(fwd).normalized()
        v = u.cross(axis).normalized()

        stations = [
            (0.00, 0.074, 0.082),  # shoulder (tucked cleanly inside jacket)
            (0.84, 0.094, 0.098),  # wide boxy cuff flare
            (1.00, 0.076, 0.080),  # chamfered cuff lip
        ]
        s_rings = []
        for (t, ru, rv) in stations:
            c = p_sh.lerp(p_wr, t)
            # 4-sided boxy cross-section (rotated 45 deg so flats face front/back/in/out)
            ring = [
                c + u * (-ru) + v * ( rv),
                c + u * ( ru) + v * ( rv),
                c + u * ( ru) + v * (-rv),
                c + u * (-ru) + v * (-rv),
            ]
            s_rings.append(ring)
        mb.loft(s_rings, JACKET, cap_bottom=False, cap_top=True, top_color=JACKET)

    # =========================================================================
    # 9. HANDS (2 chunky 4-sided beveled mitten blocks = 36 tris)
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
    # 10. BACKPACK + SHOULDER STRAPS (clean faceted 3-station pack = 32 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    bp_specs = [
        # (y,     cz,     rx,    rz)
        (0.665, -0.180, 0.145, 0.070),  # bottom
        (0.840, -0.235, 0.185, 0.125),  # chunky mid-bulge
        (1.135, -0.175, 0.135, 0.065),  # top dome
    ]
    bp_rings = []
    for (y, cz, rx, rz) in bp_specs:
        pts = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6)
        pts = [V(p.x, p.y, min(p.z, -0.112)) for p in pts]
        bp_rings.append(pts)
    mb.loft(bp_rings, PACK, cap_bottom=True, cap_top=True, bot_color=PACK, top_color=PACK)

    # Shoulder straps: curved over shoulder near sleeve seam, hugging the jacket cleanly
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        sw = 0.028
        path = [
            (side * 0.145, 1.132, -0.125),
            (side * 0.162, 1.148,  0.005),
            (side * 0.175, 1.100,  0.120),
            (side * 0.188, 0.935,  0.126),
            (side * 0.214, 0.790,  0.055),
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
    # 11. PANTS (continuous A-line silhouette from waist to cropped cuffs)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    # Pelvis block: outer X matches top of legs cleanly (no horizontal ledge!)
    mb.box(-0.188, 0.188, 0.555, 0.690, -0.102, 0.102, PANTS, skip=("top",))

    # Two 4-sided cropped legs angling outward seamlessly from pelvis
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        # Top of leg tucked slightly into pelvis (y=0.585) so swinging never opens a gap
        x_in_t  = side * 0.012
        x_out_t = side * 0.186
        x_in_b  = side * 0.078
        x_out_b = side * 0.222
        rz_t = 0.096
        rz_b = 0.082
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.215,  rz_b),
            V(max(x_in_b, x_out_b), 0.215,  rz_b),
            V(max(x_in_b, x_out_b), 0.215, -rz_b),
            V(min(x_in_b, x_out_b), 0.215, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS)

    # =========================================================================
    # 12. ANKLES (2 short 4-sided skin prisms)
    # =========================================================================
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.150
        mb.box(cx - 0.044, cx + 0.044, 0.125, 0.220, -0.046, 0.046, SKIN, skip=("top", "bottom"))

    # =========================================================================
    # 13. SHOES (2 chunky low-poly sneakers with sole band & sloped toe = 44 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.152
        w = 0.068
        w_toe = 0.056
        z_heel = -0.088
        z_mid  =  0.062
        z_toe  =  0.152
        y_sole0 = 0.000
        y_sole1 = 0.032
        y_toe_top = 0.076
        y_collar  = 0.130

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

        p_tl_h = V(cx - w * 0.88, y_collar, z_heel + 0.01)
        p_tr_h = V(cx + w * 0.88, y_collar, z_heel + 0.01)
        p_tl_m = V(cx - w * 0.88, y_collar, z_mid)
        p_tr_m = V(cx + w * 0.88, y_collar, z_mid)

        p_tl_t = V(cx - w_toe * 0.90, y_toe_top, z_toe - 0.014)
        p_tr_t = V(cx + w_toe * 0.90, y_toe_top, z_toe - 0.014)

        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], SHOE, out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], SHOE, out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], SHOE, out=(0, 1, 0.5))
        mb.face([p_tl_m, p_tr_m, p_tr_h, p_tl_h], SHOE, out=(0, 1, 0))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], SHOE, out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h], SHOE, out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], SHOE, out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m], SHOE, out=(1, 0, 0))

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

    # 4-view turnaround: Ref-angle (+34 deg), Front (0), Side (+90), Back (180)
    clones = []
    specs = [
        (-1.65, math.radians(34)),   # Front-3/4 matching reference image orientation!
        (-0.55, math.radians(0)),    # Front
        ( 0.55, math.radians(90)),   # Side (showing ponytail & backpack clearly)
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
    cam_obj.location = (0.0, -5.0, 1.12)
    direction = Vector((0.0, 0.0, 0.84)) - cam_obj.location
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


def build_rig_and_walk(ob, mb, coll):
    """Build a minimal 8-bone rig with rigid per-part weights and a 24-frame looping Walk cycle."""
    arm_data = bpy.data.armatures.new("PersonRig")
    rig = bpy.data.objects.new("PersonRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    # Bone definitions in game frame: (name, parent_name, head_game, tail_game)
    # All bones point straight up (+Y in game -> +Z in Blender) with roll=0 so local axes are uniform:
    #   local X = world +X (pitch: -rot_x swings downward limb forward/+Z_game)
    #   local Y = world +Z (yaw/twist around vertical axis; location.y = vertical lift!)
    #   local Z = world -Y (roll/side tilt)
    bone_defs = [
        ("Root",     None,     ( 0.000, 0.620,  0.000), ( 0.000, 0.720,  0.000)),
        ("Torso",    "Root",   ( 0.000, 0.680,  0.000), ( 0.000, 1.120,  0.000)),
        ("Head",     "Torso",  ( 0.000, 1.140,  0.000), ( 0.000, 1.450,  0.000)),
        ("Ponytail", "Head",   ( 0.000, 1.410, -0.185), ( 0.000, 1.560, -0.185)),
        ("Arm_L",    "Torso",  ( 0.180, 1.060,  0.000), ( 0.180, 1.220,  0.000)),
        ("Arm_R",    "Torso",  (-0.180, 1.060,  0.000), (-0.180, 1.220,  0.000)),
        ("Leg_L",    "Root",   ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R",    "Root",   (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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

    # Assign rigid vertex groups (weight 1.0 per part)
    vgroups = {}
    for (bname, _, _, _) in bone_defs:
        vgroups[bname] = ob.vertex_groups.new(name=bname)
    for v_idx, bname in enumerate(mb.vert_bones):
        vgroups[bname].add([v_idx], 1.0, "REPLACE")

    # Parent mesh to armature and add Armature modifier
    ob.parent = rig
    mod = ob.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = rig

    # Create 24-frame looping Walk action (24 fps = 1.0 s per 2-step cycle)
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

    # Keyframe every 2 frames across 1..25 (frame 25 == frame 1 for seamless loop)
    cycle_len = 24
    for frame in range(1, cycle_len + 2, 2):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        c1 = math.cos(phi)
        c2 = math.cos(2.0 * phi)

        # Root: vertical bounce (lowest at stride extremes, highest at passing), subtle hip sway & lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.028 * (1.0 - c2) * 0.5  # 0 at passing, -0.028 at stride extremes (keeps feet near ground)
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.055, -0.08 * s1, 0.038 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Torso: counter-twist against hips + tiny pitch bob
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.025 * c2, 0.13 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Head: stabilize yaw + gentle cheerful nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.035 * c2, -0.05 * s1, -0.015 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Ponytail: delayed bounce & playful side sway
        pb_pony = rig.pose.bones["Ponytail"]
        pb_pony.rotation_euler = (0.15 * math.sin(2.0 * phi - 0.8), 0.0, 0.13 * math.sin(phi - 0.6))
        pb_pony.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs: crisp opposing stride + slight upward lift during forward swing
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

        # Arms: opposite to legs for natural balance
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.40 * s1, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.40 * s1, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    bpy.ops.object.mode_set(mode="OBJECT")
    scene.frame_set(1)
    return rig, action


def render_walk_preview(rig, obj, out_path):
    """Render a 6-frame walk cycle contact sheet (frames 1, 5, 9, 13, 17, 21) from a 3/4 view."""
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

    # Bake 6 posed snapshots across the walk cycle side-by-side!
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
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(52))  # 3/4 side-front view shows stride & arms clearly!
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("WalkCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 6.7
    cam_obj = bpy.data.objects.new("WalkCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.15)
    direction = Vector((0.0, 0.0, 0.84)) - cam_obj.location
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

    coll = bpy.data.collections.new("Person")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonLow")
    mb.bm.to_mesh(me)
    mb.bm.free()

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonLow", me)
    coll.objects.link(ob)

    # Render static 4-view turnaround in rest pose before rigging/posing
    render_preview(ob, PREVIEW_PATH)

    # Build minimal 8-bone rig and 24-frame looping Walk cycle
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

    # Render 6-frame walk cycle filmstrip
    render_walk_preview(rig, ob, WALK_PREVIEW_PATH)

    print("=== PersonLow Stats ===")
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
