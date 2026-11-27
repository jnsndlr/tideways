# Builds an ultra-low-poly (< 400 tris) stylized man in a navy hooded jacket over a white tee,
# sculpted dark-brown swept hair with sideburns, brown leather crossbody satchel with flap & clasp,
# wide cropped dark-charcoal trousers, exposed ankles, and chunky cream sneakers in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_hoodie_satchel.py)
# Saves art/person_hoodie_satchel.blend, exports assets/models/person_hoodie_satchel.glb (rigged + Walk & Idle cycles),
# renders art/person_hoodie_satchel_preview.png, art/person_hoodie_satchel_walk_preview.png,
# art/person_hoodie_satchel_idle_preview.png, and outputs rendered videos
# art/person_hoodie_satchel_walk.mp4 and art/person_hoodie_satchel_idle.mp4.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_hoodie_satchel.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_hoodie_satchel.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_hoodie_satchel_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_hoodie_satchel_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_hoodie_satchel_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_hoodie_satchel_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_hoodie_satchel_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN            = col_srgb(0.95, 0.71, 0.48)
SKIN_SHADE      = col_srgb(0.83, 0.59, 0.37)

EYE             = col_srgb(0.11, 0.11, 0.13)

HAIR            = col_srgb(0.31, 0.24, 0.21)
HAIR_HIGHLIGHT  = col_srgb(0.39, 0.31, 0.27)
HAIR_SHADE      = col_srgb(0.22, 0.17, 0.15)

SHIRT           = col_srgb(0.95, 0.94, 0.91)

HOODIE          = col_srgb(0.24, 0.31, 0.42)
HOODIE_HOOD     = col_srgb(0.28, 0.36, 0.48)
HOODIE_SHADE    = col_srgb(0.17, 0.22, 0.31)
HOODIE_CUFF     = col_srgb(0.19, 0.25, 0.35)
HOODIE_POCKET   = col_srgb(0.27, 0.34, 0.45)

SATCHEL         = col_srgb(0.54, 0.40, 0.27)
SATCHEL_FLAP    = col_srgb(0.61, 0.46, 0.31)
SATCHEL_SHADE   = col_srgb(0.39, 0.28, 0.18)
SATCHEL_STRAP   = col_srgb(0.50, 0.36, 0.24)

PANTS           = col_srgb(0.25, 0.26, 0.28)
PANTS_SHADE     = col_srgb(0.18, 0.19, 0.21)

SHOE            = col_srgb(0.96, 0.93, 0.88)
SHOE_SHADE      = col_srgb(0.87, 0.83, 0.77)
SOLE            = col_srgb(0.76, 0.72, 0.65)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_HIGHLIGHT, HAIR_SHADE],
    "top": [HOODIE, HOODIE_HOOD, HOODIE_SHADE, HOODIE_CUFF, HOODIE_POCKET],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [SATCHEL, SATCHEL_FLAP, SATCHEL_SHADE, SATCHEL_STRAP],
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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None,
             skip_k=(), ring_weights=None):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            w0 = ring_weights[i] if ring_weights is not None else None
            w1 = ring_weights[i + 1] if ring_weights is not None else None
            for k in range(n):
                if k in skip_k:
                    continue
                kn = (k + 1) % n
                p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
                col = colors(i, k) if callable(colors) else colors
                mid = (p0 + p1 + p2 + p3) * 0.25
                ws = [w0, w0, w1, w1] if (w0 is not None and w1 is not None) else None
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
            elif n == 6:
                ws = [w0] * 4 if w0 is not None else None
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=ws)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=ws)
            else:
                ws = [w0] * 3 if w0 is not None else None
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
            elif n == 6:
                ws = [wt] * 4 if wt is not None else None
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=ws)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=ws)
            else:
                ws = [wt] * 3 if wt is not None else None
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=ws)

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


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. CONTINUOUS HEAD + ROUNDED HAIR SKULL + SIDEBURNS + PART (72 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # Single continuous 6-ring 6-sided skull curving smoothly from chin/nape up over the
    # rounded occiput and crown so the sides and back flow organically with ZERO sharp seam!
    # phase = pi/6 -> k=5 is flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks/temples,
    # k=1,2,3 are back-left, back, back-right (smoothly rounded espresso hair to nape).
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.196,  0.018, 0.156, 0.152),  # 0: jaw/chin & tucked nape
        (1.292,  0.020, 0.214, 0.200),  # 1: lower cheek / ear line
        (1.400,  0.014, 0.216, 0.202),  # 2: mid-ear / gentle occiput swell
        (1.494,  0.008, 0.214, 0.200),  # 3: brow / temple / full rounded occiput
        (1.592, -0.016, 0.196, 0.192),  # 4: upper crown taper
        (1.648, -0.032, 0.132, 0.138),  # 5: soft rounded top crown cap
    ]
    head_rings = []
    for i, (y, cz, rx, rz) in enumerate(head_specs):
        ring = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
        # Smooth spherical rear-hair curve (gentle fullness at occiput, zero step/ledge)
        rear_scale = [
            (1.03, 1.05, -0.006),  # 0: nape
            (1.06, 1.10, -0.012),  # 1: lower back
            (1.09, 1.16, -0.022),  # 2: mid-back swell
            (1.10, 1.18, -0.026),  # 3: full occiput curve
            (1.07, 1.12, -0.018),  # 4: upper back taper
            (1.03, 1.05, -0.008),  # 5: crown top
        ][i]
        sx_r, sz_r, dz_r = rear_scale
        for k in (2, 3):
            p = ring[k]
            ring[k] = V(p.x * sx_r, p.y, p.z * sz_r + dz_r)
        head_rings.append(ring)

    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            out_dir = mid - cmid

            if i == 0:
                col = SKIN if k in (4, 5, 0) else HAIR_SHADE
                mb.face([p0, p1, p2, p3], col, out=out_dir)
            elif i == 1:
                if k == 0:
                    # Left cheek (+X): crisp tapered lower sideburn in front of ear
                    p_b_sb = p0.lerp(p1, 0.74)
                    p_t_sb = p3.lerp(p2, 0.66)
                    mb.face([p0, p_b_sb, p_t_sb, p3], SKIN, out=out_dir)
                    mb.face([p_b_sb, p1, p2, p_t_sb], HAIR, out=out_dir)
                elif k == 4:
                    # Right cheek (-X): mirrored lower sideburn in front of ear
                    p_b_sb = p1.lerp(p0, 0.74)
                    p_t_sb = p2.lerp(p3, 0.66)
                    mb.face([p_b_sb, p1, p2, p_t_sb], SKIN, out=out_dir)
                    mb.face([p0, p_b_sb, p_t_sb, p3], HAIR, out=out_dir)
                else:
                    col = SKIN if k == 5 else HAIR
                    mb.face([p0, p1, p2, p3], col, out=out_dir)
            elif i == 2:
                if k == 0:
                    # Left upper cheek (+X): diagonal temple hairline curving up smoothly
                    p_b_sb = p0.lerp(p1, 0.66)
                    p_t_sb = p3.lerp(p2, 0.52)
                    mb.face([p0, p_b_sb, p_t_sb, p3], SKIN, out=out_dir)
                    mb.face([p_b_sb, p1, p2, p_t_sb], HAIR, out=out_dir)
                elif k == 4:
                    # Right upper cheek (-X): mirrored diagonal temple hairline
                    p_b_sb = p1.lerp(p0, 0.66)
                    p_t_sb = p2.lerp(p3, 0.52)
                    mb.face([p_b_sb, p1, p2, p_t_sb], SKIN, out=out_dir)
                    mb.face([p0, p_b_sb, p_t_sb, p3], HAIR, out=out_dir)
                else:
                    col = SKIN if k == 5 else HAIR
                    mb.face([p0, p1, p2, p3], col, out=out_dir)
            elif i == 3:
                if k == 5:
                    # Crisp off-center forehead hair-part notch matching reference!
                    # p0 is right brow (-X), p1 is left brow (+X); part sits toward +X (u = 0.72)
                    part_apex = p0.lerp(p1, 0.72).lerp(p3.lerp(p2, 0.72), 0.50)
                    mb.face([p0, p1, part_apex], SKIN, out=(0, 0.25, 1))
                    mb.face([p0, part_apex, p3], HAIR, out=(0, 0.25, 1))
                    mb.face([p1, p2, part_apex], HAIR, out=(0, 0.25, 1))
                    mb.face([part_apex, p2, p3], HAIR, out=(0, 0.25, 1))
                else:
                    mb.face([p0, p1, p2, p3], HAIR, out=out_dir)
            else:
                col = HAIR_HIGHLIGHT if k in (4, 5, 0) else HAIR
                mb.face([p0, p1, p2, p3], col, out=out_dir)

    # Top crown cap (2 quads = 4 tris)
    rt = head_rings[-1]
    mb.face([rt[5], rt[0], rt[1], rt[2]], HAIR_HIGHLIGHT, out=(0, 1, 0))
    mb.face([rt[2], rt[3], rt[4], rt[5]], HAIR_HIGHLIGHT, out=(0, 1, 0))

    # Chin bottom cap (front underside = 2 tris; rear sits cleanly over neck/hood)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. SCULPTED SWEPT-BACK HAIR WAVES (continuous front-to-back flow = 44 tris)
    # =========================================================================
    mb.set_part("hair_crown", bone="Head")
    # Two lush, gently domed, swept-back hair waves curving organically from the parted
    # forehead up over the crown and tapering smoothly INTO the rounded back of the head
    # (zero rectangular back block, zero helmet rim!).

    # 2a. Main swept-back front-right-to-crown wave (4-ring 4-sided curved flow = 22 tris)
    w1_r0 = [
        V(-0.184, 1.494,  0.156),  # right temple brow start
        V( 0.046, 1.504,  0.194),  # part edge right side
        V( 0.054, 1.594,  0.222),  # front wave crest near part
        V(-0.160, 1.580,  0.174),  # rounded right brow crest
    ]
    w1_r1 = [
        V(-0.204, 1.545,  0.012),  # snug right temple (tucks into skull)
        V( 0.062, 1.584,  0.036),  # inner crown ridge
        V( 0.062, 1.716,  0.026),  # rounded swept pompadour apex
        V(-0.146, 1.682, -0.002),  # softly sloped right crown bevel
    ]
    w1_r2 = [
        V(-0.184, 1.515, -0.152),  # wraps smoothly down upper-back right
        V( 0.036, 1.535, -0.172),  # wraps smoothly down upper-back center
        V( 0.032, 1.672, -0.156),  # rounded upper-back crown curve
        V(-0.136, 1.642, -0.138),  # rounded back-right slope
    ]
    w1_r3 = [
        V(-0.132, 1.445, -0.214),  # melts cleanly into mid-occiput skull
        V( 0.018, 1.455, -0.226),  # melts cleanly into mid-occiput center
        V( 0.014, 1.568, -0.228),  # soft curved back-crown taper (no ledge!)
        V(-0.104, 1.552, -0.212),  # soft curved back-right taper
    ]
    mb.loft([w1_r0, w1_r1, w1_r2, w1_r3],
            lambda i, k: HAIR_HIGHLIGHT if (k == 2 and i < 2) else HAIR,
            cap_bottom=True, cap_top=True,
            bot_color=HAIR, top_color=HAIR,
            skip_k=(0,))

    # 2b. Secondary front-left swept hair wave (other side of off-center part = 22 tris)
    w2_r0 = [
        V( 0.072, 1.510,  0.184),  # part edge left side (crisp V-notch with w1!)
        V( 0.184, 1.494,  0.136),  # left brow temple
        V( 0.162, 1.578,  0.148),  # softly rounded left brow crest
        V( 0.074, 1.606,  0.186),  # left wave crest near part
    ]
    w2_r1 = [
        V( 0.044, 1.578,  0.016),  # merges smoothly under main wave along crown
        V( 0.202, 1.542, -0.004),  # snug left temple
        V( 0.144, 1.662, -0.014),  # softly sloped left crown bevel
        V( 0.044, 1.686,  0.008),  # left crown apex
    ]
    w2_r2 = [
        V( 0.018, 1.532, -0.170),  # merges cleanly along back-center
        V( 0.182, 1.512, -0.150),  # wraps smoothly down upper-back left
        V( 0.132, 1.634, -0.136),  # rounded back-left slope
        V( 0.018, 1.662, -0.154),  # rounded back-center crown curve
    ]
    w2_r3 = [
        V( 0.006, 1.454, -0.224),  # melts cleanly into mid-occiput center
        V( 0.130, 1.444, -0.212),  # melts cleanly into mid-occiput left
        V( 0.102, 1.548, -0.210),  # soft curved back-left taper
        V( 0.006, 1.564, -0.226),  # soft curved back-center taper (no ledge!)
    ]
    mb.loft([w2_r0, w2_r1, w2_r2, w2_r3],
            lambda i, k: HAIR_HIGHLIGHT if (k == 2 and i < 2) else HAIR,
            cap_bottom=True, cap_top=True,
            bot_color=HAIR, top_color=HAIR,
            skip_k=(0,))

    # =========================================================================
    # 3. EARS (2 cute tucked low-poly wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.196
        x_out = side * 0.242
        y0, y1 = 1.298, 1.390
        z0, z1 = -0.018, 0.046
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.014, zm)
        p_ot = V(x_out, y1 - 0.014, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    cy_e = 1.384
    t_eye = (cy_e - 1.292) / (1.400 - 1.292)
    z_face = head_rings[1][5].z + (head_rings[2][5].z - head_rings[1][5].z) * t_eye
    z_eye = z_face + 0.0045
    for side in (-1, 1):
        cx = side * 0.064
        rx = 0.017
        ry = 0.048
        pts = [
            V(cx,      cy_e + ry,        z_eye),
            V(cx + rx, cy_e + ry * 0.58, z_eye),
            V(cx + rx, cy_e - ry * 0.58, z_eye),
            V(cx,      cy_e - ry,        z_eye),
            V(cx - rx, cy_e - ry * 0.58, z_eye),
            V(cx - rx, cy_e + ry * 0.58, z_eye),
        ]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. NECK (4-sided front/side skin column, skip rear quad inside hood = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.110, 0.020, 0.074, 0.074, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.214, 0.020, 0.070, 0.070, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 6. WHITE INNER T-SHIRT (crisp V-neck peeking inside hoodie collar = 4 tris)
    # =========================================================================
    mb.set_part("shirt", bone="Torso")
    sz_f = 0.124
    mb.face([
        V(-0.074, 1.005, sz_f),
        V( 0.074, 1.005, sz_f),
        V( 0.074, 1.138, sz_f - 0.004),
        V(-0.074, 1.138, sz_f - 0.004),
    ], SHIRT, out=(0, 0, 1))
    mb.face([
        V(-0.074, 1.138, sz_f - 0.004),
        V( 0.074, 1.138, sz_f - 0.004),
        V( 0.074, 1.138, -0.080),
        V(-0.074, 1.138, -0.080),
    ], SHIRT, out=(0, 1, 0))

    # =========================================================================
    # 7. NAVY BLUE HOODIE TORSO + COLLAR LAPELS + DRAPED HOOD (26 + 22 = 48 tris)
    # =========================================================================
    mb.set_part("hoodie_torso", bone="Torso")
    hy0, hy_mid, hy1 = 0.654, 1.015, 1.136
    hx_b, hx_m, hx_t = 0.216, 0.210, 0.198
    hz_fb, hz_fm, hz_ft = 0.144, 0.142, 0.136
    hz_bb, hz_bt = -0.130, -0.122
    v_open = 0.068  # half-width of V-neck collar opening at top

    # Lower closed front panel (y = 0.654 .. 1.015 = 2 tris)
    mb.face([
        V(-hx_b, hy0, hz_fb),
        V( hx_b, hy0, hz_fb),
        V( hx_m, hy_mid, hz_fm),
        V(-hx_m, hy_mid, hz_fm),
    ], HOODIE, out=(0, 0, 1))

    # Upper front left & right V-neck panels (framing white tee cleanly = 4 tris)
    mb.face([
        V(-hx_m,   hy_mid, hz_fm),
        V( 0.000,  hy_mid, hz_fm),
        V(-v_open, hy1,    hz_ft),
        V(-hx_t,   hy1,    hz_ft),
    ], HOODIE, out=(0, 0, 1))
    mb.face([
        V( 0.000,  hy_mid, hz_fm),
        V( hx_m,   hy_mid, hz_fm),
        V( hx_t,   hy1,    hz_ft),
        V( v_open, hy1,    hz_ft),
    ], HOODIE, out=(0, 0, 1))

    # V-neck inner thickness bevel edges (2 quads = 4 tris)
    mb.face([
        V( 0.000,  hy_mid, sz_f),
        V( 0.000,  hy_mid, hz_fm),
        V(-v_open, hy1,    hz_ft),
        V(-v_open, hy1,    sz_f),
    ], HOODIE_SHADE, out=(0.75, -0.45, 0.2))
    mb.face([
        V( 0.000,  hy_mid, hz_fm),
        V( 0.000,  hy_mid, sz_f),
        V( v_open, hy1,    sz_f),
        V( v_open, hy1,    hz_ft),
    ], HOODIE_SHADE, out=(-0.75, -0.45, 0.2))

    # Back panel (2 tris)
    mb.face([
        V( hx_b, hy0, hz_bb),
        V(-hx_b, hy0, hz_bb),
        V(-hx_t, hy1, hz_bt),
        V( hx_t, hy1, hz_bt),
    ], HOODIE, out=(0, 0, -1))

    # Side panels + shoulder top caps (2 * (2 + 2) = 8 tris)
    for side in (-1, 1):
        xo_b, xo_t = side * hx_b, side * hx_t
        xi_t = side * v_open
        mb.face([
            V(xo_b, hy0, hz_fb),
            V(xo_b, hy0, hz_bb),
            V(xo_t, hy1, hz_bt),
            V(xo_t, hy1, hz_ft),
        ], HOODIE, out=(side, 0, 0))
        mb.face([
            V(xi_t, hy1, hz_ft),
            V(xo_t, hy1, hz_ft),
            V(xo_t, hy1, hz_bt),
            V(xi_t, hy1, hz_bt),
        ], HOODIE, out=(0, 1, 0))

    # Bottom hem underside cap (2 tris)
    mb.face([
        V(-hx_b, hy0, hz_bb),
        V( hx_b, hy0, hz_bb),
        V( hx_b, hy0, hz_fb),
        V(-hx_b, hy0, hz_fb),
    ], HOODIE_SHADE, out=(0, -1, 0))

    # Subtle front hoodie kangaroo pocket patch on lower chest (left side visible in ref + symmetric right = 4 tris)
    for side in (-1, 1):
        px0 = min(side * 0.042, side * 0.168)
        px1 = max(side * 0.042, side * 0.168)
        pz = hz_fb + 0.0055
        mb.face([
            V(px0, 0.692, pz),
            V(px1, 0.692, pz),
            V(px1, 0.832, pz),
            V(px0, 0.832, pz),
        ], HOODIE_POCKET, out=(0, 0, 1))

    # Chunky draped navy hood resting behind neck & shoulders + front collar points (20 tris)
    mb.set_part("hoodie_hood", bone="Torso")
    hb = [
        V(-0.072, 1.124,  0.128),  # 0: front-right collar lapel base
        V(-0.190, 1.116, -0.055),  # 1: right shoulder/back flare
        V( 0.000, 1.112, -0.236),  # 2: plush rounded rear hood fold
        V( 0.190, 1.116, -0.055),  # 3: left shoulder/back flare
        V( 0.072, 1.124,  0.128),  # 4: front-left collar lapel base
    ]
    ht = [
        V(-0.066, 1.184,  0.114),  # 0: front-right collar edge
        V(-0.168, 1.218, -0.056),  # 1: right upper hood fold
        V( 0.000, 1.224, -0.214),  # 2: rear upper hood ridge (plush & rounded)
        V( 0.168, 1.218, -0.056),  # 3: left upper hood fold
        V( 0.066, 1.184,  0.114),  # 4: front-left collar edge
    ]
    h_in = [
        V(-0.056, 1.142,  0.078),
        V(-0.098, 1.150, -0.042),
        V( 0.000, 1.156, -0.128),
        V( 0.098, 1.150, -0.042),
        V( 0.056, 1.142,  0.078),
    ]
    for k in range(4):
        p0, p1, p2, p3 = hb[k], hb[k + 1], ht[k + 1], ht[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], HOODIE_HOOD if k in (0, 3) else HOODIE, out=V(mid.x, 0.08, mid.z))
        mb.face([ht[k], ht[k + 1], h_in[k + 1], h_in[k]], HOODIE_HOOD if k in (0, 3) else HOODIE_SHADE, out=(0, 1, 0))
    # Rear hood underside closing overhang cleanly behind back shoulders (2 tris)
    mb.face([hb[1], hb[2], hb[3], V(0.0, 1.124, -0.122)], HOODIE_SHADE, out=(0, -1, 0))
    # Two crisp turned-out collar lapel points flanking front V-neck (2 tris)
    for side in (-1, 1):
        mb.face([
            V(side * 0.062, 1.140, 0.142),
            V(side * 0.128, 1.104, 0.148),
            V(side * 0.086, 1.064, 0.148),
        ], HOODIE_HOOD, out=(0, 0, 1))

    # =========================================================================
    # 8. RELAXED NAVY HOODIE SLEEVES WITH RIBBED CUFFS (2 x 24 = 48 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Relaxed boxy drop-shoulder hoodie sleeves blending seamlessly into shoulders
    # and angled slightly outward so Arm_R cleanly clears the satchel throughout Walk & Idle!
    arm_specs = [
        ( 1, "Arm_L", V( 0.164, 1.068, 0.004), V( 0.300, 0.870, -0.012), V( 0.308, 0.740, 0.032), V( 0.308, 0.696, 0.042)),
        (-1, "Arm_R", V(-0.164, 1.068, 0.004), V(-0.314, 0.870, -0.008), V(-0.324, 0.740, 0.046), V(-0.324, 0.696, 0.056)),
    ]
    for (side, bname, p_sh, p_el, p_c0, p_wr) in arm_specs:
        mb.set_bone(bname)
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

        r_sh = s_ring(p_sh, ax1, 0.086, 0.092)
        r_el = s_ring(p_el, axm, 0.098, 0.104)
        r_c0 = s_ring(p_c0, ax2, 0.088, 0.092)
        r_wr = s_ring(p_wr, ax2, 0.068, 0.072)
        mb.loft([r_sh, r_el, r_c0, r_wr],
                lambda i, k: HOODIE_CUFF if i == 2 else (HOODIE_SHADE if k == 2 else HOODIE),
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 9. HANDS (2 chunky warm-tan fists peeking from navy cuffs = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for (side, bname, _p_sh, p_el, _p_c0, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        fwd = V(0.0, 0.0, 1.0)
        u = ax.cross(fwd)
        if u.length < 1e-5:
            u = V(1.0, 0.0, 0.0)
        u = u.normalized()
        v = u.cross(ax).normalized()

        c0 = p_wr - ax * 0.008
        c1 = p_wr + ax * 0.094
        r0 = [
            c0 + u * (-0.050) + v * ( 0.054),
            c0 + u * ( 0.050) + v * ( 0.054),
            c0 + u * ( 0.050) + v * (-0.054),
            c0 + u * (-0.050) + v * (-0.054),
        ]
        r1 = [
            c1 + u * (-0.042) + v * ( 0.046),
            c1 + u * ( 0.042) + v * ( 0.046),
            c1 + u * ( 0.042) + v * (-0.046),
            c1 + u * (-0.042) + v * (-0.046),
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 10. BROWN LEATHER CROSSBODY SATCHEL + FLAP + CLASP + STRAP (22 + 12 = 34 tris)
    # =========================================================================
    # 10a. Satchel bag body hanging cleanly at the right-rear hip (bone="Satchel")
    mb.set_part("satchel", bone="Satchel")
    # Local tilted satchel basis: rests snugly at right-rear hip (-X), tilted ~14 deg forward-bottom
    # and slightly flared outward along hip so both Arm_R and Leg_R clear it in Walk & Idle.
    s_orig = V(-0.256, 0.585, -0.118)
    # Local axes: sx = outward (-X, slightly down), sy = up-back along bag height, sz = front-to-back along bag width
    sx = V(-0.985, -0.155, -0.075).normalized()
    sz = V(-0.075, -0.220,  0.973).normalized()
    sy = sz.cross(sx).normalized()

    def sp(lx, ly, lz):
        return s_orig + sx * lx + sy * ly + sz * lz

    # Boxy leather body (lx in [-0.044, +0.044], ly in [-0.106, +0.106], lz in [-0.108, +0.108] = 12 tris)
    hx, hy, hz = 0.044, 0.106, 0.108
    b000 = sp(-hx, -hy, -hz); b100 = sp( hx, -hy, -hz)
    b101 = sp( hx, -hy,  hz); b001 = sp(-hx, -hy,  hz)
    b010 = sp(-hx,  hy, -hz); b110 = sp( hx,  hy, -hz)
    b111 = sp( hx,  hy,  hz); b011 = sp(-hx,  hy,  hz)

    mb.face([b100, b101, b111, b110], SATCHEL,       out= sx)   # outer face
    mb.face([b001, b000, b010, b011], SATCHEL_SHADE, out=-sx)   # inner face (against hip)
    mb.face([b001, b101, b111, b011], SATCHEL_SHADE, out= sz)   # front edge
    mb.face([b100, b000, b010, b110], SATCHEL_SHADE, out=-sz)   # rear edge
    mb.face([b011, b111, b110, b010], SATCHEL_FLAP,  out= sy)   # top
    mb.face([b000, b100, b101, b001], SATCHEL_SHADE, out=-sy)   # bottom

    # Fold-over leather top flap wrapping cleanly over outer side (4 quads = 8 tris)
    fx = hx + 0.014
    fy_top = hy + 0.008
    fy_bot = -0.012
    fz = hz + 0.004
    f_t0 = sp(-hx * 0.4, fy_top, -fz)
    f_t1 = sp(-hx * 0.4, fy_top,  fz)
    f_m0 = sp( fx,       fy_top - 0.010, -fz)
    f_m1 = sp( fx,       fy_top - 0.010,  fz)
    f_b0 = sp( fx,       fy_bot,         -fz * 0.94)
    f_b1 = sp( fx,       fy_bot,          fz * 0.94)
    f_i0 = sp( hx,       fy_bot + 0.006, -fz * 0.94)
    f_i1 = sp( hx,       fy_bot + 0.006,  fz * 0.94)
    mb.face([f_t1, f_m1, f_m0, f_t0], SATCHEL_FLAP,  out= sy)          # flap top wrap
    mb.face([f_b0, f_b1, f_m1, f_m0], SATCHEL_FLAP,  out= sx)          # flap outer face
    mb.face([f_i0, f_b0, f_b1, f_i1], SATCHEL_SHADE, out=-sy)          # flap bottom shadow lip
    mb.face([f_b1, sp(hx, fy_bot, fz), sp(hx, fy_top - 0.010, fz), f_m1], SATCHEL_SHADE, out=sz)  # front flap thickness

    # Cute center leather buckle/tongue clasp tab hanging down from flap center (1 quad = 2 tris)
    cx = fx + 0.0045
    mb.face([
        sp(cx, fy_bot - 0.042, -0.024),
        sp(cx, fy_bot - 0.042,  0.024),
        sp(cx, fy_bot + 0.024,  0.024),
        sp(cx, fy_bot + 0.024, -0.024),
    ], SATCHEL_STRAP, out=sx)

    # 10b. Bold crossbody leather strap from left shoulder (+X) diagonally across chest & back to satchel (12 tris)
    mb.set_part("satchel_strap", bone="Torso")
    # Shoulder top strap wrap over left hoodie shoulder (1 quad = 2 tris)
    p_sh_fl = V( 0.168, 1.148,  0.146)
    p_sh_fr = V( 0.106, 1.148,  0.146)
    p_sh_bl = V( 0.168, 1.148, -0.132)
    p_sh_br = V( 0.106, 1.148, -0.132)
    mb.face([p_sh_fr, p_sh_fl, p_sh_bl, p_sh_br], SATCHEL_STRAP, out=(0, 1, 0))

    # Front diagonal chest strap (bold ~0.060 m width wrapping around right hip into satchel front = 4 tris)
    p_f_mid_l = V(-0.172, 0.706,  0.158)
    p_f_mid_r = V(-0.222, 0.746,  0.158)
    p_f_att_l = sp(0.004, hy - 0.018,  hz - 0.010)
    p_f_att_r = sp(0.004, hy + 0.008,  hz - 0.062)
    mb.face([p_f_mid_r, p_f_mid_l, p_sh_fl, p_sh_fr], SATCHEL_STRAP, out=(0, 0, 1))
    mb.face([p_f_att_r, p_f_att_l, p_f_mid_l, p_f_mid_r], SATCHEL_STRAP, out=(-0.75, 0.1, 0.65))

    # Crisp 3D bevel edge along outer side of front chest strap (1 quad = 2 tris)
    mb.face([
        V(-0.172, 0.706, 0.145),
        p_f_mid_l,
        p_sh_fl,
        V( 0.168, 1.148, 0.134),
    ], SATCHEL_SHADE, out=(0.7, -0.7, 0.0))

    # Back diagonal strap across hoodie back connecting smoothly into satchel rear (2 quads = 4 tris)
    p_b_mid_l = V(-0.176, 0.708, -0.142)
    p_b_mid_r = V(-0.224, 0.748, -0.142)
    p_b_att_l = sp(0.004, hy - 0.018, -hz + 0.010)
    p_b_att_r = sp(0.004, hy + 0.008, -hz + 0.062)
    mb.face([p_b_mid_l, p_b_mid_r, p_sh_br, p_sh_bl], SATCHEL_STRAP, out=(0, 0, -1))
    mb.face([p_b_att_l, p_b_att_r, p_b_mid_r, p_b_mid_l], SATCHEL_STRAP, out=(-0.75, 0.1, -0.65))

    # =========================================================================
    # 11. DARK CHARCOAL WIDE CROPPED TROUSERS + EXPOSED ANKLES (28 + 12 = 40 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.194, 0.194, 0.546, 0.672, -0.108, 0.108, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.006, side * 0.194
        x_in_b, x_out_b = side * 0.044, side * 0.240
        rz_t, rz_b = 0.104, 0.106
        r_top = [
            V(min(x_in_t, x_out_t), 0.588,  rz_t),
            V(max(x_in_t, x_out_t), 0.588,  rz_t),
            V(max(x_in_t, x_out_t), 0.588, -rz_t),
            V(min(x_in_t, x_out_t), 0.588, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.178,  rz_b),
            V(max(x_in_b, x_out_b), 0.178,  rz_b),
            V(max(x_in_b, x_out_b), 0.178, -rz_b),
            V(min(x_in_b, x_out_b), 0.178, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # Warm-tan bare ankles peeking between cropped trouser cuffs and cream sneakers (2 x 6 = 12 tris)
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        a_bot = oval_ring(cx, 0.118, 0.002, 0.056, 0.058, n=3, phase=0.0)
        a_top = oval_ring(cx, 0.192, 0.002, 0.060, 0.062, n=3, phase=0.0)
        mb.loft([a_bot, a_top], SKIN_SHADE, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 12. CHUNKY CREAM SNEAKERS WITH WARM BEIGE SOLES (20 tris x 2 = 40 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        w = 0.072
        w_toe = 0.060
        z_heel = -0.092
        z_toe  =  0.174
        y_sole0 = 0.000
        y_sole1 = 0.034
        y_col   = 0.128

        # Flat chunky warm-beige outsole (4 sides + bottom = 10 tris)
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

        # Clean chunky cream sneaker upper + top collar cap sealing smoothly around ankle (10 tris)
        shoe_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.012),
            V(cx + w * 0.84, y_col, z_heel + 0.012),
            V(cx + w * 0.84, y_col, 0.064),
            V(cx - w * 0.84, y_col, 0.064),
        ]
        mb.loft([sole_top, shoe_top], lambda i, k: SHOE_SHADE if k == 2 else SHOE,
                cap_bottom=False, cap_top=True, top_color=SHOE_SHADE)

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
    """24-frame looping Walk cycle: casual commuter stride with gentle satchel bounce & sway."""
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

        # Easygoing bounce & subtle forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.024 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (0.042, -0.064 * s1, 0.032 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Natural torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.016 * c2, 0.092 * s1, -0.020 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Level, alert commuter head with gentle step nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.036 + 0.022 * c2, -0.036 * s1, -0.012 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp wide-trouser stride with clean sneaker lift
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

        # Relaxed opposite-phase hoodie arm swing (Arm_R slightly abducted to clear satchel cleanly)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.34 * s1, 0.0, 0.042 + 0.014 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.28 * s1, 0.0, -0.065 + 0.016 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Lively secondary bounce & trailing pendulum sway on leather satchel
        pb_satchel = rig.pose.bones["Satchel"]
        pb_satchel.rotation_euler = (0.070 * math.sin(phi - 0.55), 0.0, -0.035 - 0.045 * math.sin(2.0 * phi - 0.50))
        pb_satchel.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: casual harbor-side wait, calm breathing & relaxed look-around."""
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

        # Gentle weight shift & calm breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (0.010, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.022 * s2, 0.024 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious look-around across the waterfront
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.032 * s2, 0.24 * s1, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sneakers planted squarely on ground
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle breathing drift on hoodie sleeves
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.036 * s1 + 0.014 * s2, 0.0, 0.022 + 0.014 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.030 * s1 + 0.014 * s2, 0.0, -0.028 + 0.012 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle settled pendulum sway on leather satchel
        pb_satchel = rig.pose.bones["Satchel"]
        pb_satchel.rotation_euler = (0.022 * math.sin(phi - 0.5), 0.0, -0.022 * math.sin(2.0 * phi - 0.4))
        pb_satchel.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build 8-bone Tideways passenger rig (7 standard bones + Satchel) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonHoodieSatchelRig")
    rig = bpy.data.objects.new("PersonHoodieSatchelRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",    None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso",   "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",    "Torso", ( 0.000, 1.160,  0.000), ( 0.000, 1.480,  0.000)),
        ("Arm_L",   "Torso", ( 0.164, 1.068,  0.004), ( 0.164, 1.228,  0.004)),
        ("Arm_R",   "Torso", (-0.164, 1.068,  0.004), (-0.164, 1.228,  0.004)),
        ("Satchel", "Torso", (-0.238, 0.692, -0.098), (-0.238, 0.812, -0.098)),
        ("Leg_L",   "Root",  ( 0.104, 0.565,  0.000), ( 0.104, 0.725,  0.000)),
        ("Leg_R",   "Root",  (-0.104, 0.565,  0.000), (-0.104, 0.725,  0.000)),
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
        (-1.68, math.radians(52)),   # Front-3/4 matching reference angle
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Side (satchel side)
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=52):
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=52, zrot_right_deg=90):
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
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonHoodieSatchel")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonHoodieSatchel")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonHoodieSatchel", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=52)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=52, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonHoodieSatchel Stats ===")
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
