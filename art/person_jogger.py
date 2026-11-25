# Builds an ultra-low-poly (< 350 tris) stylized jogger with earbuds, baseball cap,
# ponytail, coral zip-up hoodie, smartwatch, cropped striped leggings, and sneakers in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_jogger.py)
# Saves art/person_jogger.blend, exports assets/models/person_jogger.glb (rigged + Walk & Idle cycles),
# renders art/person_jogger_preview.png, art/person_jogger_walk_preview.png, art/person_jogger_idle_preview.png,
# and outputs rendered videos art/person_jogger_walk.mp4 and art/person_jogger_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_jogger.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_jogger.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_jogger_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_jogger_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_jogger_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_jogger_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_jogger_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette closely matched to reference jogger image (sRGB -> linear)
SKIN           = col_srgb(0.96, 0.74, 0.52)
SKIN_SHADE     = col_srgb(0.86, 0.63, 0.42)
EYE            = col_srgb(0.12, 0.11, 0.12)

HAIR_DARK      = col_srgb(0.41, 0.28, 0.20)
HAIR_MID       = col_srgb(0.49, 0.35, 0.25)
HAIR_SHADE     = col_srgb(0.32, 0.22, 0.15)

CAP            = col_srgb(0.96, 0.93, 0.88)
CAP_BRIM       = col_srgb(0.94, 0.90, 0.85)
CAP_SHADE      = col_srgb(0.84, 0.80, 0.74)

EARBUD         = col_srgb(0.99, 0.99, 0.99)
EARBUD_CORD    = col_srgb(0.94, 0.94, 0.95)

HOODIE         = col_srgb(0.90, 0.55, 0.45)
HOODIE_SHADE   = col_srgb(0.79, 0.45, 0.36)
ZIPPER         = col_srgb(0.97, 0.96, 0.94)
POCKET_TRIM    = col_srgb(0.96, 0.82, 0.70)

WATCH_BAND     = col_srgb(0.24, 0.24, 0.26)
WATCH_SCREEN   = col_srgb(0.11, 0.12, 0.14)

LEGGINGS       = col_srgb(0.30, 0.30, 0.33)
LEGGINGS_SHADE = col_srgb(0.23, 0.23, 0.26)
STRIPE         = col_srgb(0.90, 0.55, 0.45)

SHOE           = col_srgb(0.96, 0.95, 0.92)
SHOE_VAMP      = col_srgb(0.91, 0.89, 0.85)
SHOE_COLLAR    = col_srgb(0.75, 0.75, 0.77)
SOLE           = col_srgb(0.77, 0.75, 0.71)


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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False,
             bot_color=None, top_color=None, skip_k=(), ring_weights=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            w0 = ring_weights[i] if ring_weights is not None else None
            w1 = ring_weights[i + 1] if ring_weights is not None else None
            fw = [w0, w0, w1, w1] if ring_weights is not None else None
            for k in range(n):
                if k in skip_k:
                    continue
                kn = (k + 1) % n
                p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
                col = colors(i, k) if callable(colors) else colors
                mid = (p0 + p1 + p2 + p3) * 0.25
                self.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=fw)
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            wb = [ring_weights[0]] * 4 if ring_weights is not None else None
            if n <= 4:
                self.face(r0, col, out=out_dir, weights=([ring_weights[0]] * n if ring_weights is not None else None))
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=wb)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=wb)
            else:
                for k in range(n):
                    wt = [ring_weights[0]] * 3 if ring_weights is not None else None
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=wt)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt4 = [ring_weights[-1]] * 4 if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([ring_weights[-1]] * n if ring_weights is not None else None))
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=wt4)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=wt4)
            else:
                for k in range(n):
                    wt3 = [ring_weights[-1]] * 3 if ring_weights is not None else None
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=wt3)

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


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=6, phase=math.pi / 6.0):
    """Ring tilted backward around X by tilt_rad (higher at +Z front, lower at -Z back)."""
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
    # 1. HEAD (6-sided stylized low-poly head with side hair framing, 28 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks,
    # k=1,2,3 are back/sides (dark brown hair tucked under baseball cap).
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.214,  0.016, 0.156, 0.146),  # 0: chin/jaw
        (1.292,  0.020, 0.208, 0.198),  # 1: lower cheek
        (1.488,  0.008, 0.206, 0.196),  # 2: brow / hairline under cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        # Front face (k=5) and front-side cheeks (k=0, 4) are warm peach skin;
        # behind ears and back of head (k=1, 2, 3) are dark chocolate hair.
        return SKIN if k in (4, 5, 0) else HAIR_DARK

    mb.loft(head_rings, head_color, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # Subtle side-swept dark brown hair temple patches framing forehead under cap (2 tris x 2 = 4 tris)
    r1, r2 = head_rings[1], head_rings[2]
    # k=0 spans vertex 0 (front-left) to vertex 1 (mid-left); k=4 spans vertex 4 (mid-right) to vertex 5 (front-right)
    # Left temple hair wedge (sits flush +0.003 outside cheek quad k=0)
    mb.face([
        r2[0].lerp(r2[1], 0.18) + V(0.003, 0.0, 0.003),
        r2[1] + V(0.004, 0.0, 0.0),
        r1[1].lerp(r2[1], 0.36) + V(0.004, 0.0, 0.0),
    ], HAIR_DARK, out=(0.85, 0.0, 0.5))
    # Right temple hair wedge (sits flush +0.003 outside cheek quad k=4)
    mb.face([
        r2[5].lerp(r2[4], 0.18) + V(-0.003, 0.0, 0.003),
        r2[4] + V(-0.004, 0.0, 0.0),
        r1[4].lerp(r2[4], 0.36) + V(-0.004, 0.0, 0.0),
    ], HAIR_DARK, out=(-0.85, 0.0, 0.5))

    # =========================================================================
    # 2. NECK (4-sided short tapered cylinder, skip rear quad inside hood = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.112, 0.008, 0.068, 0.064, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.220, 0.012, 0.064, 0.060, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 3. EYES (2 crisp vertical dark pill hexagons on flat front face, 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.197
    for side in (-1, 1):
        cx = side * 0.062
        cy = 1.388
        rx = 0.018
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
    # 4. EARS (2 chunky rounded low-poly tabs = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.194
        x_out = side * 0.232
        y0, y1 = 1.322, 1.404
        z0, z1 = -0.014, 0.050
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.016, zm)
        p_ot = V(x_out, y1 - 0.016, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 5. WHITE EARBUDS + CURVED DANGLING CORDS (20 + 12 = 32 tris)
    # =========================================================================
    mb.set_part("earbuds", bone="Head")
    for side in (-1, 1):
        # Crisp white 4-sided rounded earbud dome nestled right in the ear (10 tris x 2 = 20 tris)
        x_b0 = side * 0.214
        x_b1 = side * 0.246
        yc = 1.366
        zc = 0.022
        r_in = 0.022
        r_out = 0.015
        rb = [
            V(x_b0, yc + r_in, zc),
            V(x_b0, yc,        zc + r_in),
            V(x_b0, yc - r_in, zc),
            V(x_b0, yc,        zc - r_in),
        ]
        ro = [
            V(x_b1, yc + r_out, zc),
            V(x_b1, yc,         zc + r_out),
            V(x_b1, yc - r_out, zc),
            V(x_b1, yc,         zc - r_out),
        ]
        mb.loft([rb, ro], EARBUD, cap_bottom=False, cap_top=True, top_color=EARBUD)

        # Clean slender curved white earbud stem/cord hugging closer to cheek/neck into hoodie collar (6 tris x 2 = 12 tris)
        s0 = V(side * 0.228, 1.352, 0.024)
        s1 = V(side * 0.206, 1.268, 0.048)
        s2 = V(side * 0.146, 1.178, 0.072)
        w_cord = 0.0085
        # Upper segment: outer + front face for 3D crispness from every angle (4 tris)
        mb.face([
            s0 + V(0, 0, -w_cord),
            s0 + V(0, 0,  w_cord),
            s1 + V(0, 0,  w_cord),
            s1 + V(0, 0, -w_cord),
        ], EARBUD_CORD, out=(side, 0, 0.15))
        mb.face([
            s0 + V(-side * w_cord, 0, w_cord),
            s0 + V(0, 0, w_cord),
            s1 + V(0, 0, w_cord),
            s1 + V(-side * w_cord, 0, w_cord),
        ], EARBUD, out=(0, 0, 1))
        # Lower segment tucking cleanly inward to collar (1 angled face visible from front & 3/4 = 2 tris)
        mb.face([
            s1 + V(-side * w_cord * 0.5, 0, -w_cord * 0.6),
            s1 + V( side * w_cord * 0.3, 0,  w_cord * 0.8),
            s2 + V( side * w_cord * 0.3, 0,  w_cord * 0.8),
            s2 + V(-side * w_cord * 0.5, 0, -w_cord * 0.6),
        ], EARBUD, out=(side * 0.65, 0.0, 0.75))

    # =========================================================================
    # 6. OFF-WHITE BASEBALL CAP (6-sided uniform cream dome + curved visor = 40 tris)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    # Snug tilted dome sitting just above the brow, uniform warm cream color
    cap_tilt = math.radians(16.0)
    cap_r0 = tilted_ring(0.0, 1.462, -0.004, 0.232, 0.228, cap_tilt)  # snug headband rim
    cap_r1 = tilted_ring(0.0, 1.588, -0.022, 0.212, 0.210, cap_tilt)  # fuller rounded upper dome
    cap_r2 = tilted_ring(0.0, 1.674, -0.036, 0.118, 0.116, cap_tilt)  # smooth top crown
    mb.loft([cap_r0, cap_r1, cap_r2], CAP, cap_bottom=False, cap_top=True, top_color=CAP)

    # Curved athletic baseball visor projecting smoothly forward with gentle downward slope
    vt_top = [
        cap_r0[4] + V(-0.004, 0.015, 0.016),
        cap_r0[5] + V( 0.000, 0.017, 0.008),
        cap_r0[0] + V( 0.000, 0.017, 0.008),
        cap_r0[1] + V( 0.004, 0.015, 0.016),
    ]
    vt_bot = [
        cap_r0[4] + V(-0.004, -0.006, 0.016),
        cap_r0[5] + V( 0.000, -0.008, 0.008),
        cap_r0[0] + V( 0.000, -0.008, 0.008),
        cap_r0[1] + V( 0.004, -0.006, 0.016),
    ]
    # Gently arched downward bill matching reference curve
    vt_tip = [
        V(-0.212, 1.472, 0.132),  # right temple taper
        V(-0.112, 1.474, 0.326),  # front-right curved bill
        V( 0.112, 1.474, 0.326),  # front-left curved bill
        V( 0.212, 1.472, 0.132),  # left temple taper
    ]
    for j in range(3):
        mb.face([vt_top[j], vt_top[j + 1], vt_tip[j + 1], vt_tip[j]], CAP_BRIM,  out=(0, 1, 0.3))
        mb.face([vt_bot[j + 1], vt_bot[j], vt_tip[j], vt_tip[j + 1]], CAP_SHADE, out=(0, -1, -0.1))

    # =========================================================================
    # 7. CHUNKY SWOOPING LOW-POLY PONYTAIL (4-sided S-wave loft = 26 tris)
    # =========================================================================
    mb.set_part("ponytail", bone="Ponytail")
    # Emerges from back of cap, swells into a buoyant upper wave, curls down & back into a chunky blunt tail!
    pt_specs = [
        # (center,                rx,    ry_v)
        (V(0.0, 1.472, -0.165), 0.064, 0.060),  # 0: hair tie tucked cleanly into back of cap
        (V(0.0, 1.505, -0.305), 0.134, 0.124),  # 1: buoyant upper ponytail crest
        (V(0.0, 1.348, -0.372), 0.126, 0.116),  # 2: full lower S-wave lobe
        (V(0.0, 1.296, -0.478), 0.072, 0.064),  # 3: chunky blunt sculpted tail tip
    ]
    pt_rings = []
    for idx, (ctr, rx, ry_v) in enumerate(pt_specs):
        if idx == 0:
            ax = (pt_specs[1][0] - ctr).normalized()
        elif idx == len(pt_specs) - 1:
            ax = (ctr - pt_specs[-2][0]).normalized()
        else:
            ax = (pt_specs[idx + 1][0] - pt_specs[idx - 1][0]).normalized()
        u = V(1.0, 0.0, 0.0)
        v = u.cross(ax).normalized()
        pt_rings.append([
            ctr + v * ry_v,
            ctr + u * rx,
            ctr - v * ry_v,
            ctr - u * rx,
        ])

    def pt_color(i, k):
        if k in (0, 3) and i == 0:
            return HAIR_MID
        if k == 2:
            return HAIR_SHADE
        return HAIR_MID if (i == 1 and k == 0) else HAIR_DARK

    mb.loft(pt_rings, pt_color, cap_bottom=False, cap_top=True, top_color=HAIR_DARK)

    # =========================================================================
    # 8. CORAL ZIP-UP HOODIE TORSO + FOLDED HOOD + ZIPPER + POCKETS (26 tris)
    # =========================================================================
    mb.set_part("hoodie", bone="Torso")
    jy0, jy1 = 0.654, 1.132
    jx_b, jx_t = 0.194, 0.184
    jz_fb, jz_ft = 0.124, 0.116
    jz_bb, jz_bt = -0.116, -0.108
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
    # Skip bottom cap buried solidly inside waist/pelvis (-2 tris)
    mb.loft([h_bot, h_top], HOODIE, cap_bottom=False, cap_top=True, top_color=HOODIE)

    # Chunky folded coral hood resting neatly behind neck & framing collar (10 tris)
    hd_bot = [
        V(-0.132, 1.116,  0.072),
        V( 0.132, 1.116,  0.072),
        V( 0.158, 1.106, -0.205),
        V(-0.158, 1.106, -0.205),
    ]
    hd_top = [
        V(-0.104, 1.186,  0.048),
        V( 0.104, 1.186,  0.048),
        V( 0.136, 1.224, -0.175),
        V(-0.136, 1.224, -0.175),
    ]
    mb.loft([hd_bot, hd_top], lambda i, k: HOODIE_SHADE if k == 0 else HOODIE,
            cap_bottom=False, cap_top=True, top_color=HOODIE_SHADE)

    # Crisp white center zipper running full length of hoodie front (2 tris)
    def torso_zf(y):
        t = (y - jy0) / (jy1 - jy0)
        return jz_fb + (jz_ft - jz_fb) * t

    zw = 0.011
    mb.face([
        V(-zw, jy0 + 0.004, torso_zf(jy0 + 0.004) + 0.004),
        V( zw, jy0 + 0.004, torso_zf(jy0 + 0.004) + 0.004),
        V( zw, jy1 - 0.004, torso_zf(jy1 - 0.004) + 0.004),
        V(-zw, jy1 - 0.004, torso_zf(jy1 - 0.004) + 0.004),
    ], ZIPPER, out=(0, 0, 1))

    # Slanted light-peach/cream front jacket pocket trims (higher toward center, lower toward hip = 4 tris)
    for side in (-1, 1):
        p_in_t  = V(side * 0.072, 0.816, torso_zf(0.816) + 0.004)
        p_out_b = V(side * 0.146, 0.728, torso_zf(0.728) + 0.004)
        d_slit = (p_out_b - p_in_t)
        perp = V(-d_slit.y, d_slit.x, 0.0).normalized() * 0.013
        mb.face([
            p_in_t  - perp,
            p_in_t  + perp,
            p_out_b + perp,
            p_out_b - perp,
        ], POCKET_TRIM, out=(0, 0, 1))

    # =========================================================================
    # 9. ATHLETIC BENT CORAL SLEEVES + FISTS + RIGHT SMARTWATCH (32 + 20 + 10 = 62 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Tucked smoothly into shoulders (zero shoulder overhang!), natural jogger bent elbow posture
    arm_specs = [
        ( 1, "Arm_L", "Forearm_L", V( 0.144, 1.036, 0.004), V( 0.260, 0.874, -0.068), V( 0.244, 0.852, 0.130)),
        (-1, "Arm_R", "Forearm_R", V(-0.144, 1.036, 0.004), V(-0.260, 0.874, -0.068), V(-0.244, 0.852, 0.130)),
    ]

    for (side, arm_bone, fore_bone, p_sh, p_el, p_wr) in arm_specs:
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax_mid = (ax1 + ax2).normalized()
        out_x = V(side, 0.0, 0.0)

        def arm_ring(ctr, axis, ru, rv):
            u = (out_x - axis * out_x.dot(axis)).normalized()
            v = axis.cross(u).normalized()
            return [
                ctr - u * ru + v * rv,
                ctr + u * ru + v * rv,
                ctr + u * ru - v * rv,
                ctr - u * ru - v * rv,
            ]

        r_sh = arm_ring(p_sh, ax1, 0.056, 0.062)
        r_el = arm_ring(p_el, ax_mid, 0.068, 0.070)
        r_wr = arm_ring(p_wr, ax2, 0.056, 0.058)
        rw = [
            {arm_bone: 1.0},
            {arm_bone: 0.5, fore_bone: 0.5},
            {fore_bone: 1.0},
        ]
        mb.loft([r_sh, r_el, r_wr], lambda i, k: HOODIE_SHADE if k == 2 else HOODIE,
                cap_bottom=False, cap_top=False, ring_weights=rw)

    # Chunky peach fists (10 tris x 2 = 20 tris)
    mb.set_part("hands")
    for (side, _arm_bone, fore_bone, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(fore_bone)
        ax = (p_wr - p_el).normalized()
        out_x = V(side, 0.0, 0.0)
        u = (out_x - ax * out_x.dot(ax)).normalized()
        v = ax.cross(u).normalized()

        c0 = p_wr - ax * 0.008
        c1 = p_wr + ax * 0.094
        r0 = [
            c0 - u * 0.048 + v * 0.050,
            c0 + u * 0.048 + v * 0.050,
            c0 + u * 0.048 - v * 0.050,
            c0 - u * 0.048 - v * 0.050,
        ]
        r1 = [
            c1 - u * 0.042 + v * 0.044,
            c1 + u * 0.042 + v * 0.044,
            c1 + u * 0.042 - v * 0.044,
            c1 - u * 0.042 - v * 0.044,
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # Black smartwatch / fitness tracker on RIGHT wrist (Forearm_R, side=-1) (10 tris)
    mb.set_part("smartwatch", bone="Forearm_R")
    _, _, _, _, p_r_el, p_r_wr = arm_specs[1]
    ax_w = (p_r_wr - p_r_el).normalized()
    out_w = V(-1.0, 0.0, 0.0)
    u_w = (out_w - ax_w * out_w.dot(ax_w)).normalized()  # outward (-X)
    v_w = ax_w.cross(u_w).normalized()
    if v_w.y < 0:
        v_w = -v_w  # upward (+Y)

    wc0 = p_r_wr - ax_w * 0.022
    wc1 = p_r_wr + ax_w * 0.024
    wr_u, wr_v = 0.062, 0.064
    w_r0 = [
        wc0 - u_w * wr_u + v_w * wr_v,
        wc0 + u_w * wr_u + v_w * wr_v,
        wc0 + u_w * wr_u - v_w * wr_v,
        wc0 - u_w * wr_u - v_w * wr_v,
    ]
    w_r1 = [
        wc1 - u_w * wr_u + v_w * wr_v,
        wc1 + u_w * wr_u + v_w * wr_v,
        wc1 + u_w * wr_u - v_w * wr_v,
        wc1 - u_w * wr_u - v_w * wr_v,
    ]
    mb.loft([w_r0, w_r1], WATCH_BAND, cap_bottom=False, cap_top=False)
    # Raised dark smartwatch display beveled along top-outer wrist face (reads cleanly from 3/4, side & front!)
    n_sc = (u_w * 0.72 + v_w * 0.69).normalized()
    t_sc = (v_w * 0.72 - u_w * 0.69).normalized()
    sc_c = (wc0 + wc1) * 0.5 + n_sc * 0.064
    sh_ax = 0.024
    sh_t = 0.032
    mb.face([
        sc_c - ax_w * sh_ax - t_sc * sh_t,
        sc_c + ax_w * sh_ax - t_sc * sh_t,
        sc_c + ax_w * sh_ax + t_sc * sh_t,
        sc_c - ax_w * sh_ax + t_sc * sh_t,
    ], WATCH_SCREEN, out=n_sc)

    # =========================================================================
    # 10. CROPPED DARK LEGGINGS + CORAL STRIPES + EXPOSED ANKLES (8 + 56 = 64 tris)
    # =========================================================================
    mb.set_part("leggings", bone="Root")
    mb.box(-0.174, 0.174, 0.552, 0.668, -0.098, 0.098, LEGGINGS, skip=("top", "bottom"))

    for side in (-1, 1):
        leg_bone = "Leg_L" if side > 0 else "Leg_R"
        shin_bone = "Shin_L" if side > 0 else "Shin_R"

        # Leg tapers cleanly from athletic thigh -> knee -> cropped mid-calf legging cuff -> slim exposed ankle
        # (y, x_in, x_out, rz)
        y_hip  = 0.585
        y_knee = 0.375
        y_cuff = 0.232
        y_ank  = 0.096

        def leg_ring(y, xi, xo, rz):
            xa, xb = min(side * xi, side * xo), max(side * xi, side * xo)
            return [
                V(xa, y,  rz),
                V(xb, y,  rz),
                V(xb, y, -rz),
                V(xa, y, -rz),
            ]

        r_hip  = leg_ring(y_hip,  0.008, 0.172, 0.090)
        r_knee = leg_ring(y_knee, 0.034, 0.184, 0.080)
        r_cuff = leg_ring(y_cuff, 0.056, 0.186, 0.068)

        w_hip  = {leg_bone: 1.0}
        w_knee = {leg_bone: 0.5, shin_bone: 0.5}
        w_shin = {shin_bone: 1.0}

        # Cropped 3/4 dark charcoal leggings (hip -> knee -> mid-calf cuff, 16 tris/leg)
        mb.set_part("leggings")
        mb.loft([r_cuff, r_knee, r_hip],
                lambda i, k: LEGGINGS_SHADE if k == 2 else LEGGINGS,
                cap_bottom=False, cap_top=False,
                ring_weights=[w_shin, w_knee, w_hip])

        # Bold coral athletic stripe running down the outer side of the leggings (split at knee = 4 tris/leg)
        mb.set_part("legging_stripes")
        xo_top  = side * (0.172 + (0.184 - 0.172) * 0.25) + side * 0.004
        xo_knee = side * 0.184 + side * 0.004
        xo_cuff = side * 0.186 + side * 0.004
        y_st_top = 0.532
        sw = 0.024
        # Upper stripe segment (hip-to-knee)
        mb.face([
            V(xo_knee, y_knee, -sw),
            V(xo_knee, y_knee,  sw),
            V(xo_top,  y_st_top,  sw),
            V(xo_top,  y_st_top, -sw),
        ], STRIPE, out=(side, 0, 0), weights=[w_knee, w_knee, w_hip, w_hip])
        # Lower stripe segment (knee-to-cuff)
        mb.face([
            V(xo_cuff, y_cuff + 0.004, -sw * 0.88),
            V(xo_cuff, y_cuff + 0.004,  sw * 0.88),
            V(xo_knee, y_knee,  sw),
            V(xo_knee, y_knee, -sw),
        ], STRIPE, out=(side, 0, 0), weights=[w_shin, w_shin, w_knee, w_knee])

        # Exposed peach skin ankle / lower shin between cropped cuff and sneaker collar (8 tris/leg)
        mb.set_part("ankles", bone=shin_bone)
        r_ank_top = leg_ring(y_cuff + 0.012, 0.068, 0.174, 0.056)
        r_ank_bot = leg_ring(y_ank,          0.072, 0.170, 0.054)
        mb.loft([r_ank_bot, r_ank_top], SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 11. WHITE RUNNING SNEAKERS WITH GREY OUTSOLES & COLLARS (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Shin_L" if side > 0 else "Shin_R")
        cx = side * 0.121
        w = 0.064
        w_toe = 0.052
        z_heel = -0.094
        z_mid  =  0.054
        z_toe  =  0.168
        y_s0   =  0.000
        y_s1   =  0.028
        y_col  =  0.112

        # Layer 1: Sculpted light-grey running sole (4 side quads + bottom = 10 tris)
        sole_bot = [
            V(cx - w,     y_s0, z_heel),
            V(cx + w,     y_s0, z_heel),
            V(cx + w_toe, y_s0, z_toe),
            V(cx - w_toe, y_s0, z_toe),
        ]
        sole_top = [
            V(cx - w,     y_s1, z_heel),
            V(cx + w,     y_s1, z_heel),
            V(cx + w_toe, y_s1, z_toe),
            V(cx - w_toe, y_s1, z_toe),
        ]
        mb.loft([sole_bot, sole_top], SOLE, cap_bottom=True, cap_top=False, bot_color=SOLE)

        # Layer 2: Crisp white athletic upper tapering to grey collar around ankle (4 sides + top = 10 tris?
        # Wait: let's keep 4 sides + grey ankle collar top = 10 tris -> 20 tris/shoe = 40 tris total!)
        shoe_top = [
            V(cx - w * 0.86, y_col, z_heel + 0.014),
            V(cx + w * 0.86, y_col, z_heel + 0.014),
            V(cx + w * 0.86, y_col, z_mid),
            V(cx - w * 0.86, y_col, z_mid),
        ]
        mb.loft([sole_top, shoe_top], lambda i, k: SHOE_VAMP if k == 2 else SHOE,
                cap_bottom=False, cap_top=True, top_color=SHOE_COLLAR)

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
    """24-frame looping Walk/Jog cycle: springy athletic jog stride with proper backward knee tuck,
    forward lean, pumping bent arms, upbeat earbud head bob, and bouncy ponytail!

    Local bone axes (vertical upright bones): +X = left, +Y = up, +Z = forward.
    Right-hand rule around +X:
      +rx rotates +Y (up) -> +Z (forward), -Y (down) -> -Z (backward), -Z (back) -> +Y (up)
      -rx rotates +Y (up) -> -Z (backward), -Y (down) -> +Z (forward), +Z (fwd) -> +Y (up)
    """
    action = bpy.data.actions.new(name="Walk")
    rig.animation_data.action = action
    _reset_pose(rig)

    cycle_len = 24
    for frame in range(1, cycle_len + 2, 2):
        scene.frame_set(frame)
        phi = 2.0 * math.pi * (frame - 1) / cycle_len
        s1 = math.sin(phi)
        c1 = math.cos(phi)
        s2 = math.sin(2.0 * phi)
        c2 = math.cos(2.0 * phi)

        # Springy jogger bounce (two bounces per stride) + authentic athletic forward lean (+rx)
        pb_root = rig.pose.bones["Root"]
        bob = 0.036 * (0.5 - 0.5 * c2) - 0.002
        root_pitch = 0.115
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.078 * s1, 0.038 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Energetic torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.024 * c2, 0.135 * s1, -0.026 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Keep head upright & eyes forward (-rx cancels root forward lean) + upbeat earbud rhythm bob
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.105 - 0.042 * s2, -0.055 * s1, -0.018 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Joyful bouncy ponytail (+rx lifts tail upward!) with slight phase lag behind vertical bounce
        pb_pony = rig.pose.bones["Ponytail"]
        pony_bounce = 0.18 * math.sin(2.0 * phi - 0.65) + 0.06
        pony_sway = 0.15 * math.sin(phi - 0.55)
        pb_pony.rotation_euler = (pony_bounce, pony_sway, -0.05 * s1)
        pb_pony.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Dynamic athletic stride with proper backward knee bend (+rx on Shin bends heel backward!)
        # Leg_L: -rx swings thigh FORWARD (when s1 > 0), +rx swings thigh BACKWARD (when s1 < 0)
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.54 * s1 - 0.10, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.026, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        # Knee bends BACKWARD (+rx > 0) sharply on trailing heel-kick (when s1 < 0) and softly on front strike
        knee_l = 0.10 + 0.68 * max(0.0, math.sin(phi + math.pi - 0.45)) ** 1.3
        pb_shin_l = rig.pose.bones["Shin_L"]
        pb_shin_l.rotation_euler = (knee_l, 0.0, 0.0)
        pb_shin_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.54 * s1 - 0.10, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.026, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        knee_r = 0.10 + 0.68 * max(0.0, math.sin(phi - 0.45)) ** 1.3
        pb_shin_r = rig.pose.bones["Shin_R"]
        pb_shin_r.rotation_euler = (knee_r, 0.0, 0.0)
        pb_shin_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Opposite athletic arm pump: when Leg_L swings forward (s1 > 0), Arm_L swings back (+rx), Arm_R swings forward (-rx)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.48 * s1, 0.0, 0.04)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Forearm flexes upward (-rx) on forward pump, opens slightly (+rx) on backswing
        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.16 + 0.14 * s1, -0.06 * max(0.0, -s1), 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.48 * s1, 0.0, -0.04)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.16 - 0.14 * s1, 0.06 * max(0.0, s1), 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: post-jog catch-breath sway, relaxed arms, earbud music nod,
    and a charming mid-loop glance down at her right-wrist smartwatch!"""
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

        # Smooth pulse peaking around frame 24..34 for checking her smartwatch
        watch_check = max(0.0, math.sin(phi - 1.15)) ** 2

        # Calm standing weight shift & athletic post-jog breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (0.015, 0.024 * s1, 0.016 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.022 * s2 + 0.030 * watch_check, 0.026 * s1 - 0.05 * watch_check, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Upbeat music groove head bob + quick glance down (+rx) and right (-ry) at smartwatch
        pb_head = rig.pose.bones["Head"]
        head_pitch = -0.048 * s2 + 0.22 * watch_check
        head_yaw = 0.16 * s1 - 0.24 * watch_check
        head_roll = 0.032 * c1
        pb_head.rotation_euler = (head_pitch, head_yaw, head_roll)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Ponytail sways softly behind head bob & turns
        pb_pony = rig.pose.bones["Ponytail"]
        pb_pony.rotation_euler = (-0.04 - 0.055 * math.sin(2.0 * phi - 0.5), -0.08 * math.sin(phi - 0.4), 0.0)
        pb_pony.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Legs planted squarely & straight on ground
        for bname in ("Leg_L", "Leg_R", "Shin_L", "Shin_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm relaxed softly downward (+rx lowers forearm toward hip!)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.06 + 0.038 * s1, 0.0, 0.022 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (0.38 + 0.035 * s2, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm relaxes downward, then lifts smoothly (-rx!) inward to check smartwatch!
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.06 - 0.032 * s1 - 0.26 * watch_check, 0.0, -0.022 * s1 + 0.06 * watch_check)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (0.38 - 0.64 * watch_check, 0.24 * watch_check, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 12-bone rig (7 standard passenger bones + Ponytail + Forearms + Shins)
    with looping Walk (athletic jog) & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonJoggerRig")
    rig = bpy.data.objects.new("PersonJoggerRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Ponytail",  "Head",  ( 0.000, 1.472, -0.175), ( 0.000, 1.632, -0.175)),
        ("Arm_L",     "Torso", ( 0.144, 1.036,  0.004), ( 0.144, 1.196,  0.004)),
        ("Forearm_L", "Arm_L", ( 0.260, 0.874, -0.068), ( 0.260, 1.014, -0.068)),
        ("Arm_R",     "Torso", (-0.144, 1.036,  0.004), (-0.144, 1.196,  0.004)),
        ("Forearm_R", "Arm_R", (-0.260, 0.874, -0.068), (-0.260, 1.014, -0.068)),
        ("Leg_L",     "Root",  ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Shin_L",    "Leg_L", ( 0.112, 0.375,  0.000), ( 0.112, 0.515,  0.000)),
        ("Leg_R",     "Root",  (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
        ("Shin_R",    "Leg_R", (-0.112, 0.375,  0.000), (-0.112, 0.515,  0.000)),
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
        (-1.68, math.radians(62)),   # Front-3/4 matching reference angle (facing right, showing watch & earbud)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Right side (showing ponytail, cap visor, earbud, smartwatch, stripe)
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=62):
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
    "hair": [HAIR_DARK, HAIR_MID, HAIR_SHADE],
    "top": [HOODIE, HOODIE_SHADE],
    "bottom": [LEGGINGS, LEGGINGS_SHADE],
    "accent": [CAP, CAP_BRIM, CAP_SHADE],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonJogger")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonJogger")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonJogger", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=62)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=44)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=58, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=44, zrot_right_deg=90)

    print("=== PersonJogger Stats ===")
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
