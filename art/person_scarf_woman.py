# Builds an ultra-low-poly (< 350 tris) stylized woman in a long open charcoal wool coat,
# burnt-orange scarf with hanging tail, Breton-striped sweater, round glasses, high faceted hair bun,
# dark slate trousers, and chunky brown ankle boots in Blender matching the reference artwork.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_scarf_woman.py)
# Saves art/person_scarf_woman.blend, exports assets/models/person_scarf_woman.glb (rigged + Walk & Idle cycles),
# renders art/person_scarf_woman_preview.png, art/person_scarf_woman_walk_preview.png,
# art/person_scarf_woman_idle_preview.png, and outputs rendered videos
# art/person_scarf_woman_walk.mp4 and art/person_scarf_woman_idle.mp4.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_scarf_woman.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_scarf_woman.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_scarf_woman_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_scarf_woman_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_scarf_woman_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_scarf_woman_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_scarf_woman_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN            = col_srgb(0.97, 0.72, 0.47)
SKIN_SHADE      = col_srgb(0.86, 0.60, 0.37)

HAIR            = col_srgb(0.51, 0.35, 0.23)
HAIR_HIGHLIGHT  = col_srgb(0.58, 0.41, 0.28)
HAIR_SHADE      = col_srgb(0.39, 0.26, 0.17)

EYE             = col_srgb(0.10, 0.09, 0.10)
GLASSES         = col_srgb(0.18, 0.18, 0.20)

SCARF           = col_srgb(0.80, 0.44, 0.19)
SCARF_LIGHT     = col_srgb(0.87, 0.51, 0.24)
SCARF_SHADE     = col_srgb(0.62, 0.32, 0.12)
SCARF_FRINGE    = col_srgb(0.71, 0.37, 0.15)

SHIRT_CREAM     = col_srgb(0.94, 0.91, 0.85)
SHIRT_STRIPE    = col_srgb(0.24, 0.26, 0.30)

COAT            = col_srgb(0.31, 0.29, 0.29)
COAT_LAPEL      = col_srgb(0.37, 0.35, 0.35)
COAT_SHADE      = col_srgb(0.24, 0.22, 0.23)
COAT_LINING     = col_srgb(0.16, 0.15, 0.16)

PANTS           = col_srgb(0.20, 0.21, 0.24)
PANTS_SHADE     = col_srgb(0.13, 0.15, 0.18)

BOOT            = col_srgb(0.49, 0.33, 0.22)
BOOT_SHADE      = col_srgb(0.36, 0.24, 0.16)
SOLE            = col_srgb(0.28, 0.19, 0.13)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_HIGHLIGHT, HAIR_SHADE],
    "top": [COAT, COAT_LAPEL, COAT_SHADE, COAT_LINING],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [SCARF, SCARF_LIGHT, SCARF_SHADE, SCARF_FRINGE],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Unit icosahedron topology (12 verts, 20 tris) for chunky low-poly hair bun.
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

    def bun_sphere(self, center, rx, ry, rz, rot_y=0.0, rot_x=0.0):
        """Chunky 20-tri faceted icosahedron for a cohesive low-poly high hair bun."""
        cy, sy = math.cos(rot_y), math.sin(rot_y)
        cx, sx = math.cos(rot_x), math.sin(rot_x)
        pts = []
        for v in _ICO_VERTS:
            x1 = v.x * cy + v.z * sy
            z1 = -v.x * sy + v.z * cy
            y2 = v.y * cx - z1 * sx
            z2 = v.y * sx + z1 * cx
            pts.append(V(center.x + x1 * rx, center.y + y2 * ry, center.z + z2 * rz))
        for (a, b, c) in _ICO_FACES:
            p0, p1, p2 = pts[a], pts[b], pts[c]
            mid = (p0 + p1 + p2) / 3.0
            out_dir = mid - center
            if out_dir.y < -0.04:
                col = HAIR_SHADE
            elif out_dir.y > 0.06:
                col = HAIR_HIGHLIGHT
            else:
                col = HAIR
            self.face([p0, p1, p2], col, out=out_dir)


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + SLEEK PULLED-BACK HAIR + CENTER PART + WISPS (49 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks/temples,
    # k=1, 2, 3 are pulled-back chestnut hair wrapping cleanly into the bun.
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.202,  0.016, 0.148, 0.144),  # 0: chin/jawline tucked above scarf
        (1.288,  0.018, 0.210, 0.198),  # 1: soft lower cheeks / nape
        (1.488,  0.010, 0.214, 0.204),  # 2: brow / diagonal swept hairline
        (1.624, -0.022, 0.148, 0.156),  # 3: softly tapered rounded crown dome
    ]
    head_rings = []
    for i, (y, cz, rx, rz) in enumerate(head_specs):
        ring = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
        # Subtle extra hair fullness on back of skull (k=1,2,3,4)
        if i == 1:
            for k in (2, 3):
                p = ring[k]
                ring[k] = V(p.x * 1.05, p.y, p.z * 1.08 - 0.010)
        elif i == 2:
            for k in (1, 2, 3, 4):
                p = ring[k]
                if k in (2, 3):
                    ring[k] = V(p.x * 1.09, p.y, p.z * 1.12 - 0.020)
                else:
                    ring[k] = V(p.x * 1.03, p.y, p.z)
        elif i == 3:
            for k in (2, 3):
                p = ring[k]
                ring[k] = V(p.x * 1.08, p.y, p.z * 1.08 - 0.014)
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
                    # Front-left cheek (+X): swept diagonal hairline from brow down toward ear
                    p_hair = p1.lerp(p2, 0.36)
                    mb.face([p0, p1, p_hair, p3], SKIN, out=out_dir)
                    mb.face([p_hair, p2, p3], HAIR, out=out_dir)
                elif k == 4:
                    # Front-right cheek (-X): mirrored swept diagonal hairline
                    p_hair = p0.lerp(p3, 0.36)
                    mb.face([p0, p1, p2, p_hair], SKIN, out=out_dir)
                    mb.face([p_hair, p2, p3], HAIR, out=out_dir)
                else:
                    col = SKIN if k == 5 else HAIR
                    mb.face([p0, p1, p2, p3], col, out=out_dir)
            else:
                if k == 5:
                    # Crisp watertight inverted-V center part on forehead matching reference (4 tris)
                    part_apex = p0.lerp(p1, 0.5).lerp(p2.lerp(p3, 0.5), 0.72)
                    mb.face([p0, p1, part_apex], SKIN, out=(0, 0.3, 1))
                    mb.face([p0, part_apex, p3], HAIR, out=(0, 0.3, 1))
                    mb.face([p1, p2, part_apex], HAIR, out=(0, 0.3, 1))
                    mb.face([part_apex, p2, p3], HAIR, out=(0, 0.3, 1))
                else:
                    col = HAIR_HIGHLIGHT if k in (0, 4) else HAIR
                    mb.face([p0, p1, p2, p3], col, out=out_dir)

    # Top crown dome cap (2 quads = 4 tris)
    rt = head_rings[-1]
    mb.face([rt[5], rt[0], rt[1], rt[2]], HAIR_HIGHLIGHT, out=(0, 1, 0))
    mb.face([rt[2], rt[3], rt[4], rt[5]], HAIR_HIGHLIGHT, out=(0, 1, 0))

    # Front chin underside cap (1 quad = 2 tris; rear sits snugly inside scarf wrap)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # Cute tiny tapered hair sideburn wisps right in front of ears (2 tris = 1 per side, flush on cheek!)
    for side in (-1, 1):
        if side < 0:
            v1_b, v1_f = head_rings[1][4], head_rings[1][5]
            v2_b, v2_f = head_rings[2][4], head_rings[2][5]
        else:
            v1_b, v1_f = head_rings[1][1], head_rings[1][0]
            v2_b, v2_f = head_rings[2][1], head_rings[2][0]
        cheek_n = V(side * 0.866, 0.0, 0.500) * 0.0045
        p_top_b = v1_b.lerp(v2_b, 0.52) + cheek_n
        p_top_f = v1_b.lerp(v2_b, 0.52).lerp(v1_f.lerp(v2_f, 0.52), 0.22) + cheek_n
        p_tip   = v1_b.lerp(v2_b, 0.22).lerp(v1_f.lerp(v2_f, 0.22), 0.14) + cheek_n
        mb.face([p_top_b, p_tip, p_top_f], HAIR_SHADE, out=cheek_n)

    # =========================================================================
    # 2. HIGH CHUNKY FACETED HAIR BUN (20-tri icosahedron = 20 tris)
    # =========================================================================
    mb.set_part("hair_bun", bone="Head")
    # Prominent rounded faceted chignon nestled organically into the upper-back crown like reference
    mb.bun_sphere(
        center=V(0.0, 1.592, -0.226),
        rx=0.150, ry=0.146, rz=0.146,
        rot_y=0.30, rot_x=0.22,
    )

    # =========================================================================
    # 3. EARS (2 rounded low-poly peach wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.194
        x_out = side * 0.238
        y0, y1 = 1.298, 1.388
        z0, z1 = -0.020, 0.044
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.015, zm)
        p_ot = V(x_out, y1 - 0.015, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons inside glasses = 8 tris)
    # =========================================================================
    cy_g = 1.396
    t_eye = (cy_g - 1.288) / (1.488 - 1.288)
    z_face = head_rings[1][5].z + (head_rings[2][5].z - head_rings[1][5].z) * t_eye
    mb.set_part("eyes", bone="Head")
    z_eye = z_face + 0.004
    for side in (-1, 1):
        cx = side * 0.068
        rx = 0.015
        ry = 0.036
        pts = [
            V(cx,      cy_g + ry,        z_eye),
            V(cx + rx, cy_g + ry * 0.56, z_eye),
            V(cx + rx, cy_g - ry * 0.56, z_eye),
            V(cx,      cy_g - ry,        z_eye),
            V(cx - rx, cy_g - ry * 0.56, z_eye),
            V(cx - rx, cy_g + ry * 0.56, z_eye),
        ]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. ROUND DARK-CHARCOAL GLASSES (frames + bridge + temples = 54 tris)
    # =========================================================================
    mb.set_part("glasses", bone="Head")
    z_g_base = z_face + 0.0045
    z_g_ridge = z_face + 0.019
    r_out = 0.066
    r_mid = 0.058
    r_in  = 0.050
    n_seg = 6
    for side in (-1, 1):
        cx = side * 0.068
        p_out, p_mid, p_in = [], [], []
        for k in range(n_seg):
            a = math.pi / 6.0 + 2.0 * math.pi * k / n_seg
            ca, sa = math.cos(a), math.sin(a)
            p_out.append(V(cx + r_out * ca, cy_g + r_out * sa, z_g_base))
            p_mid.append(V(cx + r_mid * ca, cy_g + r_mid * sa, z_g_ridge))
            p_in.append( V(cx + r_in  * ca, cy_g + r_in  * sa, z_g_base))
        for k in range(n_seg):
            kn = (k + 1) % n_seg
            a_mid = math.pi / 6.0 + 2.0 * math.pi * (k + 0.5) / n_seg
            rad = V(math.cos(a_mid), math.sin(a_mid), 0.0)
            mb.face([p_out[k], p_out[kn], p_mid[kn], p_mid[k]], GLASSES, out=rad + V(0, 0, 0.8))
            mb.face([p_mid[k], p_mid[kn], p_in[kn],  p_in[k]],  GLASSES, out=-rad + V(0, 0, 0.8))

    # Crisp nose bridge (1 quad = 2 tris)
    mb.face([
        V(-0.013, cy_g + 0.002, z_g_ridge - 0.002),
        V( 0.013, cy_g + 0.002, z_g_ridge - 0.002),
        V( 0.013, cy_g + 0.014, z_g_ridge - 0.002),
        V(-0.013, cy_g + 0.014, z_g_ridge - 0.002),
    ], GLASSES, out=(0, 0, 1))

    # Clean dark temple arms running from outer frames back over ears (1 angled ribbon quad/side = 4 tris)
    for side in (-1, 1):
        x_f = side * (0.068 + r_out - 0.006)
        x_b = side * 0.218
        y_t0, y_t1 = cy_g - 0.001, cy_g + 0.013
        z_tf, z_tb = z_g_base + 0.008, 0.012
        mb.face([
            V(x_f, y_t0, z_tf),
            V(x_b, y_t0, z_tb),
            V(x_b, y_t1, z_tb),
            V(x_f, y_t1, z_tf),
        ], GLASSES, out=(side, 0, 0))

    # =========================================================================
    # 6. CHUNKY BURNT-ORANGE SCARF WRAP + HANGING TAIL (28 + 16 = 44 tris)
    # =========================================================================
    mb.set_part("scarf_wrap", bone="Torso")
    # Cozy chunky 6-sided faceted collar wrap sitting snugly around neck & coat collar (28 tris)
    n_sc = 6
    sc_rings_spec = [
        # (y_base, y_tilt, cz,    rx,    rz)
        (1.074, -0.024, 0.006, 0.218, 0.194),  # 0: lower fold resting across coat shoulders
        (1.140, -0.022, 0.012, 0.244, 0.220),  # 1: full chunky wrap belly
        (1.206, -0.008, 0.012, 0.208, 0.190),  # 2: upper cozy fold tucked right under chin
    ]
    sc_rings = []
    for (yb, yt, cz, rx, rz) in sc_rings_spec:
        ring = []
        for k in range(n_sc):
            a = math.pi / n_sc + 2.0 * math.pi * k / n_sc
            ca, sa = math.cos(a), math.sin(a)
            bump = 1.0 + 0.04 * math.sin(2.0 * a + 0.5)
            ring.append(V(rx * sa * bump, yb + yt * ca + 0.008 * math.sin(a - 0.3), cz + rz * ca * bump))
        sc_rings.append(ring)

    def scarf_wrap_col(i, k):
        if i == 0 and k in (2, 3):
            return SCARF_SHADE
        return SCARF_LIGHT if (i + k) % 2 == 0 else SCARF

    mb.loft(sc_rings, scarf_wrap_col, cap_bottom=False, cap_top=False)
    # Top cap closing scarf cleanly under chin/nape (2 quads = 4 tris)
    rt_sc = sc_rings[-1]
    mb.face([rt_sc[5], rt_sc[0], rt_sc[1], rt_sc[2]], SCARF_SHADE, out=(0, 1, 0))
    mb.face([rt_sc[2], rt_sc[3], rt_sc[4], rt_sc[5]], SCARF_SHADE, out=(0, 1, 0))

    # Hanging scarf tail on front-left chest (+X side, matching reference! = 16 tris)
    # Weighted Torso -> Scarf_Tail so it sways gently in Walk & Idle
    mb.set_part("scarf_tail")
    tail_specs = [
        # (y,     x0,    x1,    z_back, z_front, weights)
        (1.095,  0.042, 0.150,  0.146,  0.194, {"Torso": 0.85, "Scarf_Tail": 0.15}),
        (0.895,  0.056, 0.168,  0.152,  0.192, {"Torso": 0.30, "Scarf_Tail": 0.70}),
        (0.700,  0.068, 0.184,  0.158,  0.194, {"Scarf_Tail": 1.0}),
    ]
    t_rings = []
    t_weights = []
    for (y, x0, x1, zb, zf, wd) in tail_specs:
        t_rings.append([
            V(x0, y, zf),  # 0: front-inner
            V(x1, y, zf),  # 1: front-outer
            V(x1, y, zb),  # 2: back-outer
            V(x0, y, zb),  # 3: back-inner
        ])
        t_weights.append(wd)

    # 2 segments: k=0 (front), k=1 (outer side), k=3 (inner side), plus k=2 (back) on lower segment -> 14 tris
    for i in range(2):
        r0, r1 = t_rings[i], t_rings[i + 1]
        c0 = sum(r0, Vector()) / 4
        c1 = sum(r1, Vector()) / 4
        cmid = (c0 + c1) * 0.5
        w0, w1 = t_weights[i], t_weights[i + 1]
        ks = (0, 1, 3) if i == 0 else (0, 1, 2, 3)
        for k in ks:
            kn = (k + 1) % 4
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if k == 0:
                col = SCARF_LIGHT if i == 0 else SCARF
            elif k == 2:
                col = SCARF_SHADE
            else:
                col = SCARF_SHADE if i == 1 else SCARF
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=[w0, w0, w1, w1])

    # Crisp fringed bottom edge hem band (1 bottom quad = 2 tris)
    mb.set_bone("Scarf_Tail")
    rb_t = t_rings[-1]
    mb.face([rb_t[0], rb_t[1], rb_t[2], rb_t[3]], SCARF_FRINGE, out=(0, -1, 0))

    # =========================================================================
    # 7. BRETON-STRIPED INNER SWEATER PANEL (7 crisp horizontal stripes = 14 tris)
    # =========================================================================
    mb.set_part("striped_shirt", bone="Torso")
    # Visible front panel between the open charcoal coat lapels/edges, from scarf down to waist
    # Reference order top-to-bottom: dark, cream, dark, cream, dark, cream, dark? Bottom is cream above dark pants!
    # 7 bands: cream? No, dark under scarf -> cream -> dark -> cream -> dark -> cream (6) or 7 with top cream peeking ->
    # Reference shows 4 dark + 4 cream (or 3 dark + 4 cream, starting dark right below scarf and ending cream at waist):
    # Let's do 6 crisp high-readability stripes: dark, cream, dark, cream, dark, cream (12 tris) OR
    # 7 stripes: cream(narrow under scarf), dark, cream, dark, cream, dark, cream -> actually dark right under scarf,
    # then cream, dark, cream, dark, cream, dark, cream = 8? 6 stripes (3 dark + 3 cream) reads super cleanly at game scale!
    # Wait: let's check tri count! 7 stripes (dark, cream, dark, cream, dark, cream, dark? No, 6 or 8 so top=dark, bottom=cream!)
    # Let's use 6 stripes (3 dark + 3 cream = 12 tris) or 8 stripes (4 dark + 4 cream = 16 tris).
    # Let's try 7? Wait: if we have 8 stripes (16 tris) let's see if total stays < 350:
    # 49 + 20 + 8 + 8 + 54 + 44 + 16 + 38 + 32 + 20 + 26 + 36 = 351 -> too close!
    # With 6 stripes (3 bold navy-charcoal + 3 cream = 12 tris), every stripe is ~0.072m tall — super crisp,
    # zero aliasing from afar, AND saves 4 tris!
    y_sh_bot, y_sh_top = 0.648, 1.080
    z_sh_bot, z_sh_top = 0.130, 0.122
    n_stripes = 6
    for s in range(n_stripes):
        t0 = s / n_stripes
        t1 = (s + 1) / n_stripes
        ya = y_sh_bot + (y_sh_top - y_sh_bot) * t0
        yb = y_sh_bot + (y_sh_top - y_sh_bot) * t1
        za = z_sh_bot + (z_sh_top - z_sh_bot) * t0
        zb = z_sh_bot + (z_sh_top - z_sh_bot) * t1
        # s=0 (bottom hem above pants) is CREAM; s=5 (top under scarf) is DARK STRIPE
        col = SHIRT_CREAM if s % 2 == 0 else SHIRT_STRIPE
        mb.face([
            V(-0.088, ya, za),
            V( 0.088, ya, za),
            V( 0.088, yb, zb),
            V(-0.088, yb, zb),
        ], col, out=(0, 0, 1))

    # =========================================================================
    # 8. LONG OPEN CHARCOAL A-LINE WOOL OVERCOAT + LAPELS (38 tris)
    # =========================================================================
    mb.set_part("coat", bone="Torso")
    # Iconic flared knee-length open overcoat!
    # 6 vertices per ring (k=0..4 are the 5 outer panels; k=5 is the open front!):
    #   0: front-R inner opening (-ox)
    #   1: front-R outer corner (-rx)
    #   2: back-R outer corner (-rx)
    #   3: back-L outer corner (+rx)
    #   4: front-L outer corner (+rx)
    #   5: front-L inner opening (+ox)
    coat_specs = [
        # (y,     rx,    z_fi,  z_fo,  z_b,    open_x)
        (0.352, 0.278,  0.172, 0.162, -0.178,  0.072),  # 0: flared knee-level coat hem
        (0.648, 0.236,  0.150, 0.140, -0.144,  0.068),  # 1: hip/waist transition
        (1.106, 0.200,  0.136, 0.128, -0.128,  0.072),  # 2: fitted shoulders tucked under scarf
    ]
    c_rings = []
    for (y, rx, zfi, zfo, zb, ox) in coat_specs:
        c_rings.append([
            V(-ox, y, zfi),  # 0: front-R inner
            V(-rx, y, zfo),  # 1: front-R outer
            V(-rx, y, zb),   # 2: back-R outer
            V( rx, y, zb),   # 3: back-L outer
            V( rx, y, zfo),  # 4: front-L outer
            V( ox, y, zfi),  # 5: front-L inner
        ])

    # Per-vertex weights so the lower coat skirt flows naturally with each leg stride (zero clipping!)
    w_hem = [
        {"Root": 0.42, "Leg_R": 0.58},  # 0: front-R inner hem follows right leg
        {"Root": 0.48, "Leg_R": 0.52},  # 1: front-R outer hem follows right leg
        {"Root": 0.55, "Leg_R": 0.45},  # 2: back-R outer hem follows right leg
        {"Root": 0.55, "Leg_L": 0.45},  # 3: back-L outer hem follows left leg
        {"Root": 0.48, "Leg_L": 0.52},  # 4: front-L outer hem follows left leg
        {"Root": 0.42, "Leg_L": 0.58},  # 5: front-L inner hem follows left leg
    ]
    w_hip = [
        {"Torso": 0.65, "Root": 0.35},
        {"Torso": 0.65, "Root": 0.35},
        {"Torso": 0.65, "Root": 0.35},
        {"Torso": 0.65, "Root": 0.35},
        {"Torso": 0.65, "Root": 0.35},
        {"Torso": 0.65, "Root": 0.35},
    ]
    w_top = [{"Torso": 1.0}] * 6
    coat_vweights = [w_hem, w_hip, w_top]

    # 2 bands x 5 outer quads = 20 tris
    for i in range(2):
        r0, r1 = c_rings[i], c_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        vw0, vw1 = coat_vweights[i], coat_vweights[i + 1]
        for k in range(5):
            kn = k + 1
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], COAT, out=(mid - cmid),
                    weights=[vw0[k], vw0[kn], vw1[kn], vw1[k]])

    # Inner dark coat lining visible inside the open lower A-line skirt (3 quads = 6 tris)
    # Offset slightly inward (+Z) from outer back coat panel so zero coplanar Z-fighting!
    lin_b_l = V(c_rings[0][3].x * 0.94, c_rings[0][3].y + 0.004, c_rings[0][3].z + 0.012)
    lin_b_r = V(c_rings[0][2].x * 0.94, c_rings[0][2].y + 0.004, c_rings[0][2].z + 0.012)
    lin_t_r = V(c_rings[1][2].x * 0.94, c_rings[1][2].y,         c_rings[1][2].z + 0.012)
    lin_t_l = V(c_rings[1][3].x * 0.94, c_rings[1][3].y,         c_rings[1][3].z + 0.012)
    mb.face([lin_b_l, lin_b_r, lin_t_r, lin_t_l],
            COAT_LINING, out=(0, 0, 1),
            weights=[w_hem[3], w_hem[2], w_hip[2], w_hip[3]])
    # Front placket edge thickness / inner facing on right (-X) and left (+X) edges (2 quads = 4 tris)
    for idx, sx in ((0, -1), (5, 1)):
        p_b_out = c_rings[0][idx]
        p_t_out = c_rings[2][idx]
        p_b_in  = V(p_b_out.x + sx * 0.022, p_b_out.y, p_b_out.z - 0.026)
        p_t_in  = V(p_t_out.x + sx * 0.016, p_t_out.y, z_sh_top - 0.002)
        mb.face([p_b_in, p_b_out, p_t_out, p_t_in], COAT_LINING, out=(-sx, 0, 0),
                weights=[w_hem[idx], w_hem[idx], w_top[idx], w_top[idx]])

    # Shoulder top caps sealing coat cleanly beneath scarf (2 quads = 4 tris)
    mb.set_bone("Torso")
    rt_c = c_rings[-1]
    mb.face([rt_c[0], rt_c[1], rt_c[2], V(-0.072, 1.110, -0.118)], COAT, out=(0, 1, 0))
    mb.face([rt_c[5], V(0.072, 1.110, -0.118), rt_c[3], rt_c[4]],  COAT, out=(0, 1, 0))

    # Crisp notched coat lapels framing the upper chest just under the burnt-orange scarf (2 quads = 4 tris)
    for side in (-1, 1):
        p_in_top  = V(side * 0.072, 1.072, 0.148)
        p_out_top = V(side * 0.152, 1.066, 0.144)
        p_notch   = V(side * 0.130, 0.958, 0.153)
        p_in_bot  = V(side * 0.070, 0.880, 0.154)
        mb.face([p_in_bot, p_notch, p_out_top, p_in_top], COAT_LAPEL, out=(side * 0.15, 0.0, 1.0))

    # Subtle diagonal slanted coat pocket flap on right (-X) coat front (1 quad = 2 tris)
    # Matching the reference where her right hand rests casually at the coat pocket!
    mb.face([
        V(-0.122, 0.618, 0.156),
        V(-0.228, 0.706, 0.148),
        V(-0.228, 0.728, 0.146),
        V(-0.122, 0.640, 0.154),
    ], COAT_SHADE, out=(-0.35, 0.20, 0.92),
        weights=[{"Torso": 0.65, "Root": 0.35}] * 4)

    # =========================================================================
    # 9. CHUNKY CHARCOAL COAT SLEEVES (2 bent sleeves = 32 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Asymmetric stylish pose matching reference:
    # - Right arm (-X): casually bent elbow angled back-out with wrist tucked neatly right at the coat pocket!
    # - Left arm (+X): relaxed gentle natural bend hanging down cleanly beside the open coat!
    arm_specs = [
        ( 1, "Arm_L", V( 0.174, 1.052,  0.002), V( 0.288, 0.858, -0.018), V( 0.312, 0.684,  0.036)),
        (-1, "Arm_R", V(-0.174, 1.052,  0.002), V(-0.324, 0.858, -0.068), V(-0.264, 0.718,  0.088)),
    ]
    for (side, bname, p_sh, p_el, p_wr) in arm_specs:
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

        r_sh = s_ring(p_sh, ax1, 0.076, 0.084)
        r_el = s_ring(p_el, axm, 0.094, 0.098)
        r_wr = s_ring(p_wr, ax2, 0.078, 0.082)
        mb.loft([r_sh, r_el, r_wr],
                lambda i, k: COAT_SHADE if k == 2 else COAT,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 10. HANDS (2 chunky warm-peach hands peeking from coat cuffs = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for (side, bname, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        fwd = V(0.0, 0.0, 1.0)
        u = ax.cross(fwd)
        if u.length < 1e-5:
            u = V(1.0, 0.0, 0.0)
        u = u.normalized()
        v = u.cross(ax).normalized()

        # Right hand slightly shorter/tucked right toward pocket welt; left hand full relaxed fist
        h_len = 0.098 if side > 0 else 0.082
        c0 = p_wr - ax * 0.010
        c1 = p_wr + ax * h_len
        r0 = [
            c0 + u * (-0.050) + v * ( 0.054),
            c0 + u * ( 0.050) + v * ( 0.054),
            c0 + u * ( 0.050) + v * (-0.054),
            c0 + u * (-0.050) + v * (-0.054),
        ]
        r1 = [
            c1 + u * (-0.040) + v * ( 0.044),
            c1 + u * ( 0.040) + v * ( 0.044),
            c1 + u * ( 0.040) + v * (-0.044),
            c1 + u * (-0.040) + v * (-0.044),
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 11. DARK SLATE STRAIGHT TROUSERS (6 + 20 = 26 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    # Pelvis block peeking cleanly between open coat below the cream sweater hem (skip top, bottom, back -> 6 tris)
    mb.box(-0.184, 0.184, 0.542, 0.660, -0.100, 0.104, PANTS, skip=("top", "bottom", "back"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.184
        x_in_b, x_out_b = side * 0.048, side * 0.214
        rz_t, rz_b = 0.096, 0.092
        r_top = [
            V(min(x_in_t, x_out_t), 0.582,  rz_t),
            V(max(x_in_t, x_out_t), 0.582,  rz_t),
            V(max(x_in_t, x_out_t), 0.582, -rz_t),
            V(min(x_in_t, x_out_t), 0.582, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.156,  rz_b),
            V(max(x_in_b, x_out_b), 0.156,  rz_b),
            V(max(x_in_b, x_out_b), 0.156, -rz_b),
            V(min(x_in_b, x_out_b), 0.156, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 12. CHUNKY BROWN ANKLE BOOTS WITH DARK SOLES (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.132
        w = 0.068
        w_toe = 0.056
        z_heel = -0.090
        z_toe  =  0.166
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_col   = 0.172

        # Chunky dark cocoa outsole (4 sides + bottom = 10 tris)
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

        # Warm cocoa-brown ankle boot upper rising cleanly into dark trouser cuffs (8 tris)
        boot_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.014),
            V(cx + w * 0.84, y_col, z_heel + 0.014),
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
    """24-frame looping Walk cycle: poised autumn stroll with flowing open coat & gentle scarf sway."""
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

        # Crisp, poised bounce & subtle forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.022 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.044, -0.058 * s1, 0.032 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Graceful torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.016 * c2, 0.086 * s1, -0.020 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Steady, alert head motion keeping round glasses level
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.036 + 0.020 * c2, -0.036 * s1, -0.012 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Clean alternating stride; coat skirt follows legs via soft vertex weights
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.42 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.036, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.42 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.036, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Left arm swings naturally in opposite phase, clearing flared coat cleanly
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.28 * s1, 0.0, 0.042 + 0.014 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm (bent casually near pocket) sways gently with smaller amplitude & outward clearance
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.16 * s1 + 0.02, 0.0, -0.048 + 0.014 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Hanging burnt-orange scarf tail bobs & swings gently with cloth lag
        pb_scarf = rig.pose.bones["Scarf_Tail"]
        pb_scarf.rotation_euler = (0.065 + 0.075 * math.sin(2.0 * phi - 0.55), 0.0, 0.068 * math.sin(phi - 0.45))
        pb_scarf.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: cozy dockside wait, calm breathing, curious look-around & breezy scarf."""
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
        pb_root.rotation_euler = (-0.012, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * s2, 0.028 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Thoughtful harbor look-around
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.036 * s2, 0.26 * s1, 0.030 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Boots planted squarely on deck
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Cozy arm breathing drift
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.040 * s1 - 0.015 * s2, 0.0, 0.022 + 0.014 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.030 * s1 - 0.014 * s2, 0.0, -0.024 + 0.012 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle coastal breeze flutter on scarf tail
        pb_scarf = rig.pose.bones["Scarf_Tail"]
        pb_scarf.rotation_euler = (0.032 + 0.048 * s2, 0.0, 0.052 * math.sin(phi - 0.6))
        pb_scarf.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build 8-bone Tideways passenger rig (7 standard bones + Scarf_Tail) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonScarfWomanRig")
    rig = bpy.data.objects.new("PersonScarfWomanRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",       None,    ( 0.000, 0.615, 0.000), ( 0.000, 0.715, 0.000)),
        ("Torso",      "Root",  ( 0.000, 0.670, 0.000), ( 0.000, 1.125, 0.000)),
        ("Head",       "Torso", ( 0.000, 1.160, 0.000), ( 0.000, 1.480, 0.000)),
        ("Arm_L",      "Torso", ( 0.174, 1.052, 0.002), ( 0.174, 1.212, 0.002)),
        ("Arm_R",      "Torso", (-0.174, 1.052, 0.002), (-0.174, 1.212, 0.002)),
        ("Scarf_Tail", "Torso", ( 0.104, 1.080, 0.170), ( 0.104, 1.220, 0.170)),
        ("Leg_L",      "Root",  ( 0.102, 0.565, 0.000), ( 0.102, 0.725, 0.000)),
        ("Leg_R",      "Root",  (-0.102, 0.565, 0.000), (-0.102, 0.725, 0.000)),
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

    coll = bpy.data.collections.new("PersonScarfWoman")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonScarfWoman")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonScarfWoman", me)
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

    print("=== PersonScarfWoman Stats ===")
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
