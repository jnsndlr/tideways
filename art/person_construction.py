# Builds an ultra-low-poly (< 400 tris) stylized construction worker in Blender
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_construction.py)
# Saves art/person_construction.blend, exports assets/models/person_construction.glb (rigged + Walk & Idle cycles),
# renders art/person_construction_preview.png, art/person_construction_walk_preview.png, art/person_construction_idle_preview.png,
# and outputs rendered videos art/person_construction_walk.mp4 and art/person_construction_idle.mp4.
#
# Triangle budget: <= 400 triangles (~397 tris with extra head & hand definition).
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
BLEND_PATH = os.path.join(ROOT, "art", "person_construction.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_construction.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_construction_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_construction_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_construction_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_construction_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_construction_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference image (sRGB -> linear)
SKIN            = col_srgb(0.97, 0.74, 0.50)
SKIN_SHADE      = col_srgb(0.86, 0.61, 0.39)
EYE             = col_srgb(0.12, 0.12, 0.14)

HAIR_DARK       = col_srgb(0.35, 0.25, 0.19)
BEARD           = col_srgb(0.41, 0.29, 0.21)
BEARD_DARK      = col_srgb(0.31, 0.21, 0.15)
MUSTACHE        = col_srgb(0.45, 0.32, 0.23)

HAT_MAIN        = col_srgb(0.94, 0.90, 0.84)
HAT_TOP         = col_srgb(0.97, 0.94, 0.89)
HAT_SHADE       = col_srgb(0.82, 0.77, 0.70)
HAT_RIDGE       = col_srgb(0.95, 0.92, 0.86)

HOODIE          = col_srgb(0.28, 0.30, 0.35)
HOODIE_SHADE    = col_srgb(0.21, 0.23, 0.28)
HOODIE_DARK     = col_srgb(0.18, 0.20, 0.24)

VEST_YELLOW     = col_srgb(0.98, 0.91, 0.16)
VEST_SHADE      = col_srgb(0.86, 0.79, 0.12)
REFLECTIVE      = col_srgb(0.76, 0.78, 0.80)
REFLECTIVE_SHD  = col_srgb(0.64, 0.66, 0.69)
ZIPPER_DARK     = col_srgb(0.42, 0.44, 0.48)

GLOVE_ORANGE    = col_srgb(0.91, 0.59, 0.18)
GLOVE_SHADE     = col_srgb(0.78, 0.48, 0.14)
GLOVE_PALM      = col_srgb(0.29, 0.29, 0.32)

BELT_BROWN      = col_srgb(0.34, 0.25, 0.20)
BELT_SHADE      = col_srgb(0.25, 0.18, 0.14)
BUCKLE_SILVER   = col_srgb(0.66, 0.68, 0.72)

POUCH_TAN       = col_srgb(0.84, 0.54, 0.22)
POUCH_SHADE     = col_srgb(0.70, 0.43, 0.16)
POUCH_DARK      = col_srgb(0.28, 0.22, 0.18)
TOOL_SILVER     = col_srgb(0.76, 0.79, 0.83)
TOOL_DARK       = col_srgb(0.54, 0.57, 0.62)

PANTS           = col_srgb(0.32, 0.36, 0.41)
PANTS_SHADE     = col_srgb(0.24, 0.27, 0.32)

BOOT            = col_srgb(0.64, 0.45, 0.27)
BOOT_SHADE      = col_srgb(0.51, 0.35, 0.20)
SOLE            = col_srgb(0.31, 0.23, 0.17)


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
            elif n == 8:
                self.face([r0[7], r0[0], r0[3], r0[4]], col, out=out_dir)
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir)
                self.face([r0[4], r0[5], r0[6], r0[7]], col, out=out_dir)
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
                self.face([rt[7], rt[0], rt[3], rt[4]], col, out=out_dir)
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir)
                self.face([rt[4], rt[5], rt[6], rt[7]], col, out=out_dir)
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


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=6, phase=math.pi / 6.0):
    """6-sided ring tilted backward around X by tilt_rad (+tilt raises +Z front, lowers -Z back)."""
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
    # 1. ROUNDED 8-SIDED HEAD + FULL BEARD + CRISP SIDEBURNS (40 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # n=8, phase=pi/8 -> k=7 is wide flat front face (+Z), k=0 (+X) & k=6 (-X) are front cheeks/temples,
    # k=1 (+X) & k=5 (-X) are sides behind ears, k=2,3,4 are back of head (dark brown hair)
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.202,  0.022, 0.168, 0.164),  # 0: full rounded bearded chin/jaw
        (1.318,  0.020, 0.214, 0.204),  # 1: beard top / cheek line
        (1.505,  0.008, 0.210, 0.198),  # 2: forehead tucked neatly under hard hat
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=8, phase=math.pi / 8.0)
                  for (y, cz, rx, rz) in head_specs]

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 8
        c1 = sum(r1, Vector()) / 8
        cmid = (c0 + c1) * 0.5
        for k in range(8):
            kn = (k + 1) % 8
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 0:
                col = BEARD if k in (6, 7, 0) else HAIR_DARK
                mb.face([p0, p1, p2, p3], col, out=(mid - cmid))
            elif i == 1 and k == 0:
                # Front-left temple (+X): crisp dark-brown sideburn framing cheek into beard
                p_top = p3.lerp(p2, 0.64)
                mb.face([p0, p1, p_top, p3], SKIN,      out=(mid - cmid))
                mb.face([p1, p2, p_top],     HAIR_DARK, out=(mid - cmid))
            elif i == 1 and k == 6:
                # Front-right temple (-X): mirror sideburn framing cheek into beard
                p_top = p2.lerp(p3, 0.64)
                mb.face([p0, p1, p2, p_top], SKIN,      out=(mid - cmid))
                mb.face([p0, p_top, p3],     HAIR_DARK, out=(mid - cmid))
            else:
                col = SKIN if k == 7 else HAIR_DARK
                mb.face([p0, p1, p2, p3], col, out=(mid - cmid))

    # Rounded 8-sided bearded chin underside cap (3 quads = 6 tris)
    rb = head_rings[0]
    mb.face([rb[7], rb[0], rb[3], rb[4]], BEARD_DARK, out=(0, -1, 0))
    mb.face([rb[0], rb[1], rb[2], rb[3]], BEARD_DARK, out=(0, -1, 0))
    mb.face([rb[4], rb[5], rb[6], rb[7]], BEARD_DARK, out=(0, -1, 0))

    # Exact z on the flat front face (k=7) of the 8-sided head between ring 1 and ring 2
    cos_p8 = math.cos(math.pi / 8.0)
    z_face_r1 = 0.020 + 0.204 * cos_p8
    z_face_r2 = 0.008 + 0.198 * cos_p8

    def head_front_z(y):
        t = (y - 1.318) / (1.505 - 1.318)
        return z_face_r1 + (z_face_r2 - z_face_r1) * t

    # =========================================================================
    # 2. SCULPTED MUSTACHE + FRONT BEARD VOLUME (8 tris)
    # =========================================================================
    mb.set_part("mustache", bone="Head")
    p_ct_t = V(0.000, 1.334, z_face_r1 + 0.024)  # center bridge top under nose
    p_ct_b = V(0.000, 1.278, z_face_r1 + 0.020)  # center lower lip arch blending smoothly into beard
    p_cb_t = V(0.000, 1.330, z_face_r1 - 0.008)  # center back top (flush in face)
    p_cb_b = V(0.000, 1.272, z_face_r1 - 0.010)  # center back bottom
    for side in (-1, 1):
        p_out_f = V(side * 0.106, 1.284, z_face_r1 + 0.002)
        p_out_b = V(side * 0.122, 1.284, z_face_r1 - 0.036)
        mb.face([p_ct_b, p_out_f, p_out_b, p_ct_t], MUSTACHE,   out=(side * 0.22, 0.10, 1.0))
        mb.face([p_ct_t, p_out_b, p_cb_t],          BEARD,      out=(0, 1, 0.2))
        mb.face([p_ct_b, p_cb_b, p_out_f],          BEARD_DARK, out=(0, -1, 0.1))

    # =========================================================================
    # 3. VERTICAL BLACK PILL EYES (2 crisp 6-vertex hexagons = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    for side in (-1, 1):
        cx = side * 0.056
        cy = 1.398
        rx = 0.0175
        ry = 0.045
        ys = [cy + ry, cy + ry * 0.56, cy - ry * 0.56, cy - ry, cy - ry * 0.56, cy + ry * 0.56]
        xs = [cx, cx + rx, cx + rx, cx, cx - rx, cx - rx]
        pts = [V(xs[i], ys[i], head_front_z(ys[i]) + 0.004) for i in range(6)]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 4. EARS (2 chunky rounded low-poly tabs = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.200
        x_out = side * 0.238
        y0, y1 = 1.318, 1.404
        z0, z1 = -0.014, 0.048
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.018, zm)
        p_ot = V(x_out, y1 - 0.018, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 5. ROUNDED 8-SIDED CONSTRUCTION HARD HAT (dome 38 + curved brim 32 + ridge 10 = 80 tris)
    # =========================================================================
    mb.set_part("hard_hat", bone="Head")
    hat_tilt = math.radians(13.0)
    ct_h, st_h = math.cos(hat_tilt), math.sin(hat_tilt)

    # 8-sided dome rings (phase = pi/8 -> k=7..0 is flat front face at +Z, smooth curved sides!)
    hat_rim = tilted_ring(0.0, 1.464, -0.008, 0.236, 0.236, hat_tilt,        n=8, phase=math.pi / 8.0)
    hat_mid = tilted_ring(0.0, 1.580, -0.022, 0.224, 0.222, hat_tilt * 0.80, n=8, phase=math.pi / 8.0)
    hat_top = tilted_ring(0.0, 1.688, -0.036, 0.136, 0.134, hat_tilt * 0.50, n=8, phase=math.pi / 8.0)

    mb.loft([hat_rim, hat_mid], HAT_MAIN, cap_bottom=False, cap_top=False)
    mb.loft([hat_mid, hat_top], HAT_TOP,  cap_bottom=False, cap_top=True, top_color=HAT_TOP)

    # Smoothly curved 8-sided rain-gutter brim with extended front visor bill
    hat_brim_in = tilted_ring(0.0, 1.446, -0.008, 0.198, 0.196, hat_tilt, n=8, phase=math.pi / 8.0)
    hat_brim_out = []
    for k in range(8):
        a = math.pi / 8.0 + 2.0 * math.pi * k / 8.0
        # k=0 (+22.5 deg) & k=7 (-22.5 deg) form the forward visor peak; k=1 & k=6 flare gently into side rim
        if k in (0, 7):
            rx_b, rz_b, dy_lip = 0.258, 0.308, -0.015
        elif k in (1, 6):
            rx_b, rz_b, dy_lip = 0.264, 0.278, -0.014
        else:
            rx_b, rz_b, dy_lip = 0.264, 0.264, -0.012
        lx = rx_b * math.sin(a)
        lz = rz_b * math.cos(a)
        py = 1.464 + lz * st_h + dy_lip
        pz = -0.008 + lz * ct_h
        hat_brim_out.append(V(lx, py, pz))

    mb.loft([hat_rim, hat_brim_out],     HAT_MAIN,  cap_bottom=False, cap_top=False)
    mb.loft([hat_brim_out, hat_brim_in], HAT_SHADE, cap_bottom=False, cap_top=False)

    # Iconic raised central crown ridge hugging flush over front slope -> crown -> rear slope (5 quads = 10 tris)
    rw = 0.042  # half-width of central ridge
    r_fb_l = V(-rw, 1.568,  0.168); r_fb_r = V(rw, 1.568,  0.168)  # front anchor flush inside front slope
    r_ft_l = V(-rw, 1.714,  0.072); r_ft_r = V(rw, 1.714,  0.072)  # front top crest
    r_bt_l = V(-rw, 1.698, -0.146); r_bt_r = V(rw, 1.698, -0.146)  # back top crest
    r_bb_l = V(-rw, 1.542, -0.214); r_bb_r = V(rw, 1.542, -0.214)  # back anchor flush inside rear slope
    mb.face([r_fb_l, r_fb_r, r_ft_r, r_ft_l], HAT_RIDGE, out=(0, 0.55, 0.84))
    mb.face([r_ft_l, r_ft_r, r_bt_r, r_bt_l], HAT_TOP,   out=(0, 1.0,  0.0))
    mb.face([r_bt_l, r_bt_r, r_bb_r, r_bb_l], HAT_RIDGE, out=(0, 0.55, -0.84))
    mb.face([r_fb_r, r_bb_r, r_bt_r, r_ft_r], HAT_MAIN,  out=( 1, 0, 0))
    mb.face([r_bb_l, r_fb_l, r_ft_l, r_bt_l], HAT_MAIN,  out=(-1, 0, 0))

    # =========================================================================
    # 6. NECK (3-sided front/side prism, back hidden inside hood = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_pts_b = [V(-0.072, 1.112, -0.046), V(0.000, 1.112, 0.074), V(0.072, 1.112, -0.046)]
    n_pts_t = [V(-0.068, 1.216, -0.042), V(0.000, 1.216, 0.070), V(0.068, 1.216, -0.042)]
    mb.face([n_pts_b[0], n_pts_b[1], n_pts_t[1], n_pts_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_pts_b[1], n_pts_b[2], n_pts_t[2], n_pts_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 7. DARK CHARCOAL FOLDED HOODIE HOOD BEHIND NECK (8 tris)
    # =========================================================================
    mb.set_part("hood", bone="Torso")
    # Cozy rounded hood draped snugly behind the collar (skip front face buried behind neck)
    hd_bot = [
        V(-0.132, 1.115,  0.068),
        V( 0.132, 1.115,  0.068),
        V( 0.162, 1.072, -0.205),
        V(-0.162, 1.072, -0.205),
    ]
    hd_top = [
        V(-0.104, 1.186,  0.048),
        V( 0.104, 1.186,  0.048),
        V( 0.134, 1.182, -0.182),
        V(-0.134, 1.182, -0.182),
    ]
    mb.loft([hd_bot, hd_top], HOODIE, cap_bottom=False, cap_top=True, top_color=HOODIE_SHADE, skip_k=(0,))

    # =========================================================================
    # 8. HIGH-VIS YELLOW SAFETY VEST WITH SILVER REFLECTIVE STRIPES (49 tris)
    # =========================================================================
    mb.set_part("vest", bone="Torso")
    vy0 = 0.668    # vest bottom hem (meets top of tool belt cleanly)
    vy_s0 = 0.758  # horizontal reflective stripe bottom
    vy_s1 = 0.838  # horizontal reflective stripe top
    vy1 = 1.132    # shoulder top

    vx_b, vx_t = 0.214, 0.194
    vz_fb, vz_ft = 0.136, 0.122
    vz_bb, vz_bt = -0.128, -0.116

    def vx(y):
        t = (y - vy0) / (vy1 - vy0)
        return vx_b + (vx_t - vx_b) * t

    def vzf(y):
        t = (y - vy0) / (vy1 - vy0)
        return vz_fb + (vz_ft - vz_fb) * t

    def vzb(y):
        t = (y - vy0) / (vy1 - vy0)
        return vz_bb + (vz_bt - vz_bb) * t

    # -- Sides (left +X and right -X): 3 vertical bands (yellow / silver / yellow) = 12 tris --
    y_bands = [(vy0, vy_s0, VEST_SHADE), (vy_s0, vy_s1, REFLECTIVE_SHD), (vy_s1, vy1, VEST_SHADE)]
    for side in (-1, 1):
        for (ya, yb, col) in y_bands:
            xa, xb = side * vx(ya), side * vx(yb)
            mb.face([
                V(xa, ya, vzf(ya)),
                V(xa, ya, vzb(ya)),
                V(xb, yb, vzb(yb)),
                V(xb, yb, vzf(yb)),
            ], col, out=(side, 0, 0))

    # -- Front lower yellow band + horizontal silver reflective band (4 tris) --
    for (ya, yb, col) in ((vy0, vy_s0, VEST_YELLOW), (vy_s0, vy_s1, REFLECTIVE)):
        xa, xb = vx(ya), vx(yb)
        za, zb = vzf(ya), vzf(yb)
        mb.face([V(-xa, ya, za), V(xa, ya, za), V(xb, yb, zb), V(-xb, yb, zb)], col, out=(0, 0, 1))

    # -- Front upper chest (vy_s1 .. vy1): 5 clean vertical strips (yellow / silver / yellow / silver / yellow) = 10 tris --
    # Vertical reflective stripes sit nicely over left & right chest and line up with shoulder tops!
    xs_f_bot = [-vx(vy_s1), -0.146, -0.080,  0.080,  0.146, vx(vy_s1)]
    xs_f_top = [-vx(vy1),   -0.136, -0.072,  0.072,  0.136, vx(vy1)]
    cols_upper = [VEST_YELLOW, REFLECTIVE, VEST_YELLOW, REFLECTIVE, VEST_YELLOW]
    zf_a, zf_b = vzf(vy_s1), vzf(vy1)
    for c in range(5):
        mb.face([
            V(xs_f_bot[c],     vy_s1, zf_a),
            V(xs_f_bot[c + 1], vy_s1, zf_a),
            V(xs_f_top[c + 1], vy1,   zf_b),
            V(xs_f_top[c],     vy1,   zf_b),
        ], cols_upper[c], out=(0, 0, 1))

    # Dark charcoal hoodie V-neck triangle peeking out at upper center chest (1 tri)
    mb.face([
        V(-0.072, vy1 + 0.001, zf_b + 0.004),
        V( 0.072, vy1 + 0.001, zf_b + 0.004),
        V( 0.000, vy1 - 0.135, vzf(vy1 - 0.135) + 0.004),
    ], HOODIE_DARK, out=(0, 0, 1))

    # Crisp center vest zipper seam from V-neck down to hem (2 tris)
    y_zip_t = vy1 - 0.130
    mb.face([
        V(-0.0055, vy0,     vzf(vy0) + 0.004),
        V( 0.0055, vy0,     vzf(vy0) + 0.004),
        V( 0.0055, y_zip_t, vzf(y_zip_t) + 0.004),
        V(-0.0055, y_zip_t, vzf(y_zip_t) + 0.004),
    ], ZIPPER_DARK, out=(0, 0, 1))

    # -- Back lower yellow + horizontal silver reflective band (4 tris) --
    for (ya, yb, col) in ((vy0, vy_s0, VEST_YELLOW), (vy_s0, vy_s1, REFLECTIVE)):
        xa, xb = vx(ya), vx(yb)
        za, zb = vzb(ya), vzb(yb)
        mb.face([V(xa, ya, za), V(-xa, ya, za), V(-xb, yb, zb), V(xb, yb, zb)], col, out=(0, 0, -1))

    # -- Back upper (vy_s1 .. vy1): 5 matching vertical strips (yellow / silver / yellow / silver / yellow) = 10 tris --
    zb_a, zb_b = vzb(vy_s1), vzb(vy1)
    for c in range(5):
        mb.face([
            V(xs_f_bot[c + 1], vy_s1, zb_a),
            V(xs_f_bot[c],     vy_s1, zb_a),
            V(xs_f_top[c],     vy1,   zb_b),
            V(xs_f_top[c + 1], vy1,   zb_b),
        ], cols_upper[c], out=(0, 0, -1))

    # -- Shoulder tops: contiguous silver reflective stripe + outer yellow shoulder per side (8 tris) --
    for side in (-1, 1):
        x_in  = side * 0.072
        x_mid = side * 0.136
        x_out = side * vx(vy1)
        mb.face([
            V(min(x_in, x_mid),  vy1, zf_b),
            V(max(x_in, x_mid),  vy1, zf_b),
            V(max(x_in, x_mid),  vy1, zb_b),
            V(min(x_in, x_mid),  vy1, zb_b),
        ], REFLECTIVE, out=(0, 1, 0))
        mb.face([
            V(min(x_mid, x_out), vy1, zf_b),
            V(max(x_mid, x_out), vy1, zf_b),
            V(max(x_mid, x_out), vy1, zb_b),
            V(min(x_mid, x_out), vy1, zb_b),
        ], VEST_YELLOW, out=(0, 1, 0))

    # =========================================================================
    # 9. DARK CHARCOAL HOODIE SLEEVES (2 x 14 tris = 28 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Chunky relaxed sleeves clearing the hip tool pouch cleanly!
    arm_specs = [
        ( 1, "Arm_L", V( 0.172, 1.074,  0.006), V( 0.282, 0.858, -0.006), V( 0.298, 0.706, 0.022)),
        (-1, "Arm_R", V(-0.172, 1.074,  0.006), V(-0.282, 0.858, -0.006), V(-0.298, 0.706, 0.022)),
    ]

    for (side, bname, p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        pts_arm = [p_sh, p_el, p_wr]
        rads = [(0.078, 0.088), (0.090, 0.094), (0.078, 0.082)]
        ax_up = (p_el - p_sh).normalized()
        ax_lo = (p_wr - p_el).normalized()

        rings = []
        for idx in range(3):
            ax = ax_up if idx == 0 else ((ax_up + ax_lo).normalized() if idx == 1 else ax_lo)
            fwd = V(0.0, 0.0, 1.0)
            out_x = V(side, 0.0, 0.0)
            u = (out_x - ax * out_x.dot(ax)).normalized()
            v = fwd - ax * fwd.dot(ax)
            v = (v - u * v.dot(u)).normalized()
            ru, rv = rads[idx]
            c = pts_arm[idx]
            rings.append([
                c - u * ru + v * rv,  # 0: front-in
                c + u * ru + v * rv,  # 1: front-out
                c + u * ru - v * rv,  # 2: back-out
                c - u * ru - v * rv,  # 3: back-in
            ])

        # Front (2 quads), Outer (2 quads), Back (2 quads) + Inner (1 quad) = 14 tris/arm
        for b in range(2):
            r0, r1 = rings[b], rings[b + 1]
            mb.face([r0[0], r0[1], r1[1], r1[0]], HOODIE,       out=(0, 0, 1))
            mb.face([r0[1], r0[2], r1[2], r1[1]], HOODIE,       out=(side, 0, 0))
            mb.face([r0[2], r0[3], r1[3], r1[2]], HOODIE_SHADE, out=(0, 0, -1))
        mb.face([rings[0][3], rings[0][0], rings[2][0], rings[2][3]], HOODIE_SHADE, out=(-side, 0, 0))

    # =========================================================================
    # 10. SCULPTED ORANGE WORK GLOVES: FLARED CUFFS + 3D THUMBS + CURLED PALMS (2 x 28 = 56 tris)
    # =========================================================================
    mb.set_part("gloves")
    for (side, bname, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        out_x = V(side, 0.0, 0.0)
        u = (out_x - ax * out_x.dot(ax)).normalized()
        fwd = V(0.0, 0.0, 1.0)
        v = fwd - ax * fwd.dot(ax)
        v = (v - u * v.dot(u)).normalized()

        # Flared orange wrist cuff overlapping sleeve -> plump orange knuckle -> subtly curled dark fingertips
        c_in = p_wr - ax * 0.008                     # inner cuff edge tucked into charcoal sleeve
        c0   = p_wr + ax * 0.004                     # flared orange glove cuff collar
        c1   = p_wr + ax * 0.084 + u * 0.006         # rounded knuckle / back-of-hand
        c2   = p_wr + ax * 0.132 - u * 0.012         # fingertips curving softly inward toward palm

        def g_ring(ctr, ru, rv):
            return [
                ctr - u * ru + v * rv,  # 0: front-in
                ctr + u * ru + v * rv,  # 1: front-out
                ctr + u * ru - v * rv,  # 2: back-out
                ctr - u * ru - v * rv,  # 3: back-in
            ]

        r_in = g_ring(c_in, 0.064, 0.068)
        r0   = g_ring(c0,   0.082, 0.084)  # proud flared work-glove cuff!
        r1   = g_ring(c1,   0.068, 0.072)  # rounded mid-glove knuckle
        r2   = g_ring(c2,   0.046, 0.056)  # curled dark-grey fingertip grip

        # Flared cuff collar rim around front, outer, and back (3 quads = 6 tris)
        mb.face([r_in[0], r_in[1], r0[1], r0[0]], GLOVE_SHADE, out=-ax + v * 0.4)
        mb.face([r_in[1], r_in[2], r0[2], r0[1]], GLOVE_SHADE, out=-ax + u * 0.4)
        mb.face([r_in[2], r_in[3], r0[3], r0[2]], GLOVE_SHADE, out=-ax - v * 0.4)

        # Upper orange glove body (3 quads = 6 tris)
        mb.face([r0[0], r0[1], r1[1], r1[0]], GLOVE_ORANGE, out=(0, 0, 1))
        mb.face([r0[1], r0[2], r1[2], r1[1]], GLOVE_ORANGE, out=(side, 0, 0))
        mb.face([r0[2], r0[3], r1[3], r1[2]], GLOVE_SHADE,  out=(0, 0, -1))

        # Lower dark charcoal reinforced fingertips/grip (3 quads = 6 tris)
        mb.face([r1[0], r1[1], r2[1], r2[0]], GLOVE_PALM, out=(0, 0, 1))
        mb.face([r1[1], r1[2], r2[2], r2[1]], GLOVE_PALM, out=(side, 0, 0))
        mb.face([r1[2], r1[3], r2[3], r2[2]], GLOVE_PALM, out=(0, 0, -1))

        # Inner dark palm + curled fingertip bottom cap (2 quads = 4 tris)
        mb.face([r0[3], r0[0], r2[0], r2[3]], GLOVE_PALM, out=(-side, 0, 0))
        mb.face([r2[0], r2[1], r2[2], r2[3]], GLOVE_PALM, out=ax)

        # Sculpted watertight 3D thumb on the front-inner/front edge of each glove (6 tris/hand!)
        # Anchors cleanly into the front face of the orange glove with a chunky rounded gloved-thumb silhouette
        tb_to = r0[0].lerp(r0[1], 0.58) + ax * 0.018 - v * 0.008  # top-outer base
        tb_ti = r0[0].lerp(r0[1], 0.10) + ax * 0.018 - v * 0.008  # top-inner base
        tb_bo = r1[0].lerp(r1[1], 0.54) + ax * 0.006 - v * 0.008  # bottom-outer base
        tb_bi = r1[0].lerp(r1[1], 0.08) + ax * 0.006 - v * 0.008  # bottom-inner base
        t_tip_o = tb_bo + v * 0.036 + ax * 0.020 - u * 0.005      # chunky blunt outer thumb tip
        t_tip_i = tb_bi + v * 0.034 + ax * 0.020 - u * 0.003      # chunky blunt inner thumb tip

        mb.face([tb_to, tb_ti, t_tip_i, t_tip_o], GLOVE_ORANGE, out=v * 0.85 - ax * 0.35)
        mb.face([tb_bi, tb_bo, t_tip_o, t_tip_i], GLOVE_PALM,   out=ax * 0.85 - v * 0.25)
        mb.face([tb_bo, tb_to, t_tip_o],          GLOVE_ORANGE, out=u)
        mb.face([tb_ti, tb_bi, t_tip_i],          GLOVE_PALM,   out=-u)

    # =========================================================================
    # 11. DARK BROWN TOOL BELT + SILVER BUCKLE (10 tris)
    # =========================================================================
    mb.set_part("tool_belt", bone="Root")
    # Wraps cleanly around hips right beneath the hi-vis vest hem (y = 0.606 .. 0.672)
    mb.box(-0.198, 0.198, 0.606, 0.672, -0.118, 0.122,
           {"default": BELT_BROWN, "back": BELT_SHADE}, skip=("top", "bottom"))
    # Crisp silver belt buckle centered on front
    mb.face([
        V(-0.044, 0.610, 0.128),
        V( 0.044, 0.610, 0.128),
        V( 0.044, 0.668, 0.128),
        V(-0.044, 0.668, 0.128),
    ], BUCKLE_SILVER, out=(0, 0, 1))

    # =========================================================================
    # 12. TAN LEATHER TOOL POUCH + SILVER TOOLS (RIGHT HIP) & SMALL LEFT HOLDER (28 tris)
    # =========================================================================
    mb.set_part("tool_pouch", bone="ToolPouch")
    # Signature chunky tan leather tool pouch on right hip (-X), positioned slightly forward
    # so it reads clearly in the 3/4 view & clears the swinging right work glove!
    px_in  = -0.180
    px_out = -0.244
    py0, py1 = 0.448, 0.616
    pz0, pz1 = -0.004, 0.138
    # Main pouch body (4 faces, skip inner face against hip & unseen bottom = 8 tris)
    mb.box(px_out, px_in, py0, py1, pz0, pz1, {
        "left":   POUCH_TAN,
        "front":  POUCH_TAN,
        "back":   POUCH_SHADE,
        "top":    POUCH_DARK,
    }, skip=("right", "bottom"))

    # Sculpted outer front sub-pocket ledge for layered tool-pouch depth (3 quads = 6 tris)
    p2_out = -0.260
    mb.face([V(p2_out, 0.464, 0.010), V(p2_out, 0.464, 0.124), V(p2_out, 0.568, 0.124), V(p2_out, 0.568, 0.010)],
            POUCH_SHADE, out=(-1, 0, 0))
    mb.face([V(px_out, 0.464, 0.124), V(p2_out, 0.464, 0.124), V(p2_out, 0.568, 0.124), V(px_out, 0.568, 0.124)],
            POUCH_TAN, out=(0, 0, 1))
    mb.face([V(p2_out, 0.568, 0.010), V(p2_out, 0.568, 0.124), V(px_out, 0.568, 0.124), V(px_out, 0.568, 0.010)],
            POUCH_DARK, out=(0, 1, 0))

    # Two distinct bright silver metal tool tops peeking proudly above the pouch rim (2 x 4 tris = 8 tris)
    # Tool 1 (rear-outer: silver pliers/hammer top)
    mb.face([V(-0.236, 0.612, 0.014), V(-0.236, 0.612, 0.056), V(-0.230, 0.674, 0.050), V(-0.230, 0.674, 0.020)],
            TOOL_SILVER, out=(-1, 0, 0))
    mb.face([V(-0.236, 0.612, 0.056), V(-0.204, 0.612, 0.056), V(-0.204, 0.674, 0.050), V(-0.230, 0.674, 0.050)],
            TOOL_DARK, out=(0, 0, 1))
    # Tool 2 (front-outer: silver wrench/driver top)
    mb.face([V(-0.234, 0.612, 0.078), V(-0.234, 0.612, 0.118), V(-0.228, 0.668, 0.112), V(-0.228, 0.668, 0.082)],
            TOOL_SILVER, out=(-1, 0, 0))
    mb.face([V(-0.234, 0.612, 0.118), V(-0.204, 0.612, 0.118), V(-0.204, 0.668, 0.112), V(-0.228, 0.668, 0.112)],
            TOOL_DARK, out=(0, 0, 1))

    # Small dark brown side pouch/holster on left hip (+X, matching reference far hip = 6 tris)
    mb.set_part("left_pouch", bone="Root")
    mb.box(0.184, 0.232, 0.488, 0.614, -0.035, 0.068,
           {"right": BELT_BROWN, "front": BELT_SHADE, "back": BELT_SHADE},
           skip=("left", "top", "bottom"))

    # =========================================================================
    # 13. DARK SLATE WORK PANTS (8 + 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.188, 0.188, 0.542, 0.612, -0.106, 0.106, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.186
        x_in_b, x_out_b = side * 0.056, side * 0.228
        rz_t, rz_b = 0.098, 0.100
        r_top = [
            V(min(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585,  rz_t),
            V(max(x_in_t, x_out_t), 0.585, -rz_t),
            V(min(x_in_t, x_out_t), 0.585, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.165,  rz_b),
            V(max(x_in_b, x_out_b), 0.165,  rz_b),
            V(max(x_in_b, x_out_b), 0.165, -rz_b),
            V(min(x_in_b, x_out_b), 0.165, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 14. CHUNKY TAN-BROWN WORK BOOTS WITH DARK SOLES (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.144
        w = 0.072
        w_toe = 0.060
        z_heel = -0.092
        z_toe  =  0.170
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_col   = 0.175

        # Thick dark brown work outsole (10 tris)
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

        # Chunky tan-brown leather work boot upper rising into pant cuff (8 tris)
        boot_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, 0.054),
            V(cx - w * 0.84, y_col, 0.054),
        ]
        mb.loft([sole_top, boot_top], lambda i, k: BOOT_SHADE if k == 2 else BOOT,
                cap_bottom=False, cap_top=False)

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
    """24-frame looping Walk cycle: sturdy job-site stride, heavy-boot bounce & subtle tool pouch jostle."""
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

        # Sturdy purposeful walk bounce & subtle forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.026 * (1.0 - c2) * 0.5
        root_pitch = -0.048
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.064 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Broad-shouldered torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.018 * c2, 0.092 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Steady hard-hat head posture with subtle rhythmic nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.040 + 0.028 * s2, -0.038 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Heavy work-boot stride with crisp foot lift on swing phase
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.45 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.040, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.45 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.040, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Confident counter-swinging gloved arms angled slightly outward to clear tool pouch
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.30 * s1 - 0.03, 0.0, 0.052)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.30 * s1 - 0.03, 0.0, -0.082)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Leather tool pouch bounces & swings slightly behind heavy steps
        pb_pouch = rig.pose.bones["ToolPouch"]
        pb_pouch.location = (0.0, 0.008 * math.sin(2.0 * phi - 0.60), 0.0)
        pb_pouch.rotation_euler = (0.036 * math.sin(phi - 0.45), 0.0, -0.042 * math.sin(2.0 * phi - 0.60))
        pb_pouch.keyframe_insert(data_path="location", frame=frame)
        pb_pouch.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: grounded job-site stand, alert look-around & steady breathing."""
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

        # Grounded weight shift & steady breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.010, 0.022 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.030 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert job-site inspection: glancing left/right and slightly up
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.048 * s2 + 0.018, 0.22 * s1, 0.030 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Boots planted squarely
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gloved hands breathing gently at sides, clearing tool pouch cleanly
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.038 * s1 - 0.014 * s2, 0.0, 0.032 + 0.016 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.036 * s1 - 0.014 * s2, 0.0, -0.048 - 0.016 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Tool pouch settles subtly with weight shift
        pb_pouch = rig.pose.bones["ToolPouch"]
        pb_pouch.location = (0.0, 0.003 * s2, 0.0)
        pb_pouch.rotation_euler = (0.012 * s2, 0.0, -0.018 * s1)
        pb_pouch.keyframe_insert(data_path="location", frame=frame)
        pb_pouch.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + ToolPouch) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonConstructionRig")
    rig = bpy.data.objects.new("PersonConstructionRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Arm_L",     "Torso", ( 0.172, 1.074,  0.006), ( 0.172, 1.234,  0.006)),
        ("Arm_R",     "Torso", (-0.172, 1.074,  0.006), (-0.172, 1.234,  0.006)),
        ("ToolPouch", "Root",  (-0.215, 0.610,  0.048), (-0.215, 0.730,  0.048)),
        ("Leg_L",     "Root",  ( 0.105, 0.565,  0.000), ( 0.105, 0.725,  0.000)),
        ("Leg_R",     "Root",  (-0.105, 0.565,  0.000), (-0.105, 0.725,  0.000)),
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
        (-1.68, math.radians(60)),   # Front-3/4 matching reference angle (facing right)
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (showing hard hat bill, hood, pouch, gloves)
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
    "hair": [HAIR_DARK, BEARD, BEARD_DARK, MUSTACHE],
    "top": [HOODIE, HOODIE_SHADE, HOODIE_DARK],
    "bottom": [PANTS, PANTS_SHADE],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonConstruction")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonConstruction")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonConstruction", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris <= 400, f"Triangle budget exceeded: {total_tris} > 400"

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
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=54, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonConstruction Stats ===")
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
