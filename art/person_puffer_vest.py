# Builds an ultra-low-poly (< 350 tris) stylized man in a forest-green quilted puffer vest
# over a cream hoodie, curly dark-brown afro hair & full beard, dark charcoal cropped trousers,
# and chunky cream sneakers in Blender matching the reference artwork.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_puffer_vest.py)
# Saves art/person_puffer_vest.blend, exports assets/models/person_puffer_vest.glb (rigged + Walk & Idle cycles),
# renders art/person_puffer_vest_preview.png, art/person_puffer_vest_walk_preview.png,
# art/person_puffer_vest_idle_preview.png, and outputs rendered videos
# art/person_puffer_vest_walk.mp4 and art/person_puffer_vest_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_puffer_vest.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_puffer_vest.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_puffer_vest_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_puffer_vest_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_puffer_vest_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_puffer_vest_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_puffer_vest_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN            = col_srgb(0.83, 0.59, 0.38)
SKIN_SHADE      = col_srgb(0.70, 0.48, 0.29)

EYE             = col_srgb(0.11, 0.10, 0.10)
MOUTH           = col_srgb(0.46, 0.29, 0.20)

HAIR            = col_srgb(0.32, 0.25, 0.22)
HAIR_HIGHLIGHT  = col_srgb(0.40, 0.32, 0.28)
HAIR_SHADE      = col_srgb(0.24, 0.18, 0.16)
BEARD           = col_srgb(0.31, 0.24, 0.20)
BEARD_SHADE     = col_srgb(0.22, 0.17, 0.14)

HOODIE          = col_srgb(0.93, 0.87, 0.79)
HOODIE_SHADE    = col_srgb(0.82, 0.76, 0.68)
HOODIE_HOOD     = col_srgb(0.96, 0.91, 0.84)
HOODIE_INNER    = col_srgb(0.71, 0.65, 0.57)

VEST            = col_srgb(0.35, 0.47, 0.36)
VEST_HIGHLIGHT  = col_srgb(0.41, 0.54, 0.42)
VEST_SHADE      = col_srgb(0.25, 0.35, 0.26)
VEST_POCKET     = col_srgb(0.30, 0.41, 0.31)

PANTS           = col_srgb(0.25, 0.25, 0.27)
PANTS_SHADE     = col_srgb(0.17, 0.17, 0.19)

SHOE            = col_srgb(0.96, 0.93, 0.88)
SHOE_SHADE      = col_srgb(0.87, 0.83, 0.77)
SOLE            = col_srgb(0.80, 0.75, 0.68)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_HIGHLIGHT, HAIR_SHADE, BEARD, BEARD_SHADE],
    "top": [VEST, VEST_HIGHLIGHT, VEST_SHADE, VEST_POCKET],
    "bottom": [PANTS, PANTS_SHADE],
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

    def curl_puff(self, base_pt, axis, depth, rx, ry, r_cap_scale=0.68, phase=0.0,
                  n=4, side_col=HAIR, cap_col=HAIR_HIGHLIGHT, shade_col=HAIR_SHADE,
                  skip_k=()):
        """Chunky faceted low-poly afro curl cluster (4-sided = 10 tris, or fewer with skip_k)."""
        ax = axis.normalized()
        ref = V(0.0, 1.0, 0.0) if abs(ax.y) < 0.85 else V(0.0, 0.0, 1.0)
        u = ax.cross(ref).normalized()
        v = ax.cross(u).normalized()

        def ring_n(ctr, sx, sy):
            pts = []
            for k in range(n):
                a = phase + 2.0 * math.pi * k / n
                pts.append(ctr + u * (sx * math.cos(a)) + v * (sy * math.sin(a)))
            return pts

        r0 = ring_n(base_pt, rx, ry)
        r1 = ring_n(base_pt + ax * depth, rx * r_cap_scale, ry * r_cap_scale)
        c_mid = base_pt + ax * (depth * 0.5)
        for k in range(n):
            if k in skip_k:
                continue
            kn = (k + 1) % n
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            out_dir = mid - c_mid
            if out_dir.y < -0.02:
                col = shade_col
            elif out_dir.y > 0.02:
                col = cap_col
            else:
                col = side_col
            self.face([p0, p1, p2, p3], col, out=out_dir)
        if n == 4:
            self.face(r1, cap_col, out=ax)
        elif n == 3:
            self.face(r1, cap_col, out=ax)


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD + INTEGRATED FULL BEARD + SIDEBURNS + HAIR BASE (6-sided = 42 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks,
    # k=1,2,3 are back/sides (dark curly afro hair & nape).
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.196,  0.020, 0.168, 0.162),  # 0: full bearded jaw/chin
        (1.298,  0.020, 0.214, 0.204),  # 1: lower cheek / beard line
        (1.498,  0.010, 0.210, 0.198),  # 2: brow / forehead hairline
        (1.618, -0.024, 0.192, 0.194),  # 3: upper hair base crown (sealed under afro puffs)
    ]
    head_rings = []
    for i, (y, cz, rx, rz) in enumerate(head_specs):
        ring = oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
        # Extra lush rear-hair volume on back of head (k=2, 3)
        if i in (1, 2):
            for k in (2, 3):
                p = ring[k]
                ring[k] = V(p.x * 1.12, p.y, p.z * 1.14 - 0.022)
        elif i == 3:
            for k in (2, 3):
                p = ring[k]
                ring[k] = V(p.x * 1.08, p.y, p.z * 1.08 - 0.018)
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
            if i == 0:
                col = BEARD if k in (4, 5, 0) else HAIR_SHADE
                mb.face([p0, p1, p2, p3], col, out=(mid - cmid))
            elif i == 1:
                if k == 0:
                    # Left cheek (+X): vertical sideburn strip at back (near ear) connecting temple hair to beard!
                    p_b_sb = p0.lerp(p1, 0.64)
                    p_t_sb = p3.lerp(p2, 0.54)
                    mb.face([p0, p_b_sb, p_t_sb, p3], SKIN, out=(mid - cmid))
                    mb.face([p_b_sb, p1, p2, p_t_sb], BEARD, out=(mid - cmid))
                elif k == 4:
                    # Right cheek (-X): mirrored sideburn strip at back connecting temple hair to beard!
                    p_b_sb = p1.lerp(p0, 0.64)
                    p_t_sb = p2.lerp(p3, 0.54)
                    mb.face([p_b_sb, p1, p2, p_t_sb], SKIN, out=(mid - cmid))
                    mb.face([p0, p_b_sb, p_t_sb, p3], BEARD, out=(mid - cmid))
                else:
                    col = SKIN if k == 5 else HAIR
                    mb.face([p0, p1, p2, p3], col, out=(mid - cmid))
            else:
                col = HAIR_HIGHLIGHT if k in (4, 5, 0) else HAIR
                mb.face([p0, p1, p2, p3], col, out=(mid - cmid))

    # Chin bottom cap (front underside = 2 tris; rear sits directly above neck/hood)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], BEARD_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. SCULPTED FULL BEARD + MOUSTACHE FRONT VOLUME (14 tris)
    # =========================================================================
    mb.set_part("beard_muzzle", bone="Head")
    # Snug rounded 3D moustache/chin cushion matching the reference's bold dark beard
    z_f1 = head_rings[1][5].z  # front cheek plane at y=1.298
    z_f0 = head_rings[0][5].z  # chin plane at y=1.196
    b_top = [
        V(-0.114, 1.300, z_f1 - 0.016),
        V(-0.056, 1.318, z_f1 + 0.022),
        V( 0.056, 1.318, z_f1 + 0.022),
        V( 0.114, 1.300, z_f1 - 0.016),
    ]
    b_bot = [
        V(-0.098, 1.214, z_f0 + 0.004),
        V(-0.052, 1.212, z_f0 + 0.036),
        V( 0.052, 1.212, z_f0 + 0.036),
        V( 0.098, 1.214, z_f0 + 0.004),
    ]
    b_in_t = [
        V(-0.104, 1.300, z_f1 - 0.024),
        V(-0.048, 1.314, z_f1 - 0.008),
        V( 0.048, 1.314, z_f1 - 0.008),
        V( 0.104, 1.300, z_f1 - 0.024),
    ]
    for k in range(3):
        p0, p1, p2, p3 = b_bot[k], b_bot[k + 1], b_top[k + 1], b_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], BEARD, out=V(mid.x * 0.4, 0.0, 1.0))
        mb.face([b_top[k], b_top[k + 1], b_in_t[k + 1], b_in_t[k]], BEARD, out=(0, 1, 0.35))
    # Subtle warm mouth accent nestled inside front moustache/beard (1 small quad = 2 tris)
    mb.face([
        V(-0.022, 1.258, z_f1 + 0.024),
        V( 0.022, 1.258, z_f1 + 0.024),
        V( 0.022, 1.274, z_f1 + 0.025),
        V(-0.022, 1.274, z_f1 + 0.025),
    ], MOUTH, out=(0, 0, 1))

    # =========================================================================
    # 3. CHUNKY FACETED CURLY AFRO HAIR CROWN (6 cohesive solid puffs = 50 tris)
    # =========================================================================
    mb.set_part("hair_curls", bone="Head")
    # Cohesive, lush low-poly afro silhouette: chunky rounded blocks merging into a full
    # cloud over brow, crown, upper temples, and back of head (100% solid, zero gaps!).
    # 3a. Front-left brow puff (skip hidden rear face buried inside crown = 8 tris)
    mb.curl_puff(
        base_pt=V( 0.068, 1.542,  0.070),
        axis=V( 0.20,  0.88,  0.42),
        depth=0.114, rx=0.134, ry=0.120, r_cap_scale=0.80, phase=0.45, n=4,
        side_col=HAIR, cap_col=HAIR_HIGHLIGHT, shade_col=HAIR_SHADE, skip_k=(2,)
    )
    # 3b. Front-right brow puff (skip hidden rear face = 8 tris)
    mb.curl_puff(
        base_pt=V(-0.084, 1.536,  0.064),
        axis=V(-0.28,  0.87,  0.40),
        depth=0.110, rx=0.130, ry=0.116, r_cap_scale=0.80, phase=0.68, n=4,
        side_col=HAIR, cap_col=HAIR_HIGHLIGHT, shade_col=HAIR_SHADE, skip_k=(2,)
    )
    # 3c. Main top crown afro cluster (full rounded apex reaching y ~ 1.72 = 10 tris)
    mb.curl_puff(
        base_pt=V(-0.006, 1.580, -0.046),
        axis=V(-0.04,  0.97, -0.22),
        depth=0.132, rx=0.174, ry=0.158, r_cap_scale=0.80, phase=0.28, n=4,
        side_col=HAIR, cap_col=HAIR_HIGHLIGHT, shade_col=HAIR_SHADE
    )
    # 3d. Upper-back voluminous afro puff (broad rounded rear silhouette = 10 tris)
    mb.curl_puff(
        base_pt=V( 0.004, 1.502, -0.114),
        axis=V( 0.02,  0.34, -0.94),
        depth=0.142, rx=0.194, ry=0.148, r_cap_scale=0.80, phase=0.52, n=4,
        side_col=HAIR, cap_col=HAIR_HIGHLIGHT, shade_col=HAIR_SHADE
    )
    # 3e. Left & Right rounded side-temple afro puffs tucked smoothly into crown (2 x 8 = 16 tris? skip buried bottom -> 2 x 8 = 16 -> 52 tris -> 345 total!)
    for side in (-1, 1):
        mb.curl_puff(
            base_pt=V(side * 0.122, 1.512, -0.026),
            axis=V(side * 0.74, 0.56, -0.36),
            depth=0.106, rx=0.128, ry=0.120, r_cap_scale=0.80, phase=0.55, n=4,
            side_col=HAIR, cap_col=HAIR_HIGHLIGHT, shade_col=HAIR_SHADE, skip_k=(2,)
        )

    # =========================================================================
    # 4. EARS (2 cute tucked low-poly wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.196
        x_out = side * 0.242
        y0, y1 = 1.304, 1.394
        z0, z1 = -0.018, 0.046
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.014, zm)
        p_ot = V(x_out, y1 - 0.014, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 5. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    t_eye = (1.394 - 1.298) / (1.498 - 1.298)
    z_face = head_rings[1][5].z + (head_rings[2][5].z - head_rings[1][5].z) * t_eye
    z_eye = z_face + 0.0045
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.394
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
    # 6. NECK (3-sided front/side skin prism, back hidden inside cream hood = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.072, 1.112, -0.046), V(0.000, 1.112, 0.078), V(0.072, 1.112, -0.046)]
    n_t = [V(-0.068, 1.214, -0.042), V(0.000, 1.214, 0.074), V(0.068, 1.214, -0.042)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 7. INNER CREAM HOODIE FRONT PANEL + CHUNKY FOLDED HOOD (4 + 18 = 22 tris)
    # =========================================================================
    mb.set_part("hoodie_torso", bone="Torso")
    # Center front cream hoodie panel peeking between the open puffer vest sides
    sz_f = 0.132
    mb.face([
        V(-0.074, 0.712, sz_f),
        V( 0.074, 0.712, sz_f),
        V( 0.074, 1.132, sz_f - 0.006),
        V(-0.074, 1.132, sz_f - 0.006),
    ], HOODIE, out=(0, 0, 1))
    # Ribbed lower hoodie waistband hem peeking cleanly at bottom front opening
    mb.face([
        V(-0.074, 0.654, sz_f - 0.002),
        V( 0.074, 0.654, sz_f - 0.002),
        V( 0.074, 0.712, sz_f),
        V(-0.074, 0.712, sz_f),
    ], HOODIE_SHADE, out=(0, 0, 1))

    # Generous chunky folded cream hood draped behind neck & shoulders (4-seg U-roll = 17 tris)
    mb.set_part("hoodie_hood", bone="Torso")
    h_bot = [
        V(-0.072, 1.116,  0.112),  # 0: front-right throat tuck
        V(-0.194, 1.110, -0.070),  # 1: right shoulder/back flare
        V( 0.194, 1.110, -0.070),  # 2: left shoulder/back flare
        V( 0.072, 1.116,  0.112),  # 3: front-left throat tuck
    ]
    # Plump curved rear hood resting generously behind neck & upper back
    h_mid_b = V(0.000, 1.118, -0.244)
    h_mid_t = V(0.000, 1.238, -0.210)
    h_top = [
        V(-0.062, 1.196,  0.098),  # 0: front-right collar edge
        V(-0.172, 1.232, -0.068),  # 1: right upper hood fold
        V( 0.172, 1.232, -0.068),  # 2: left upper hood fold
        V( 0.062, 1.196,  0.098),  # 3: front-left collar edge
    ]
    h_in = [
        V(-0.052, 1.142,  0.074),
        V(-0.098, 1.150, -0.045),
        V( 0.000, 1.154, -0.128),
        V( 0.098, 1.150, -0.045),
        V( 0.052, 1.142,  0.074),
    ]
    # Build 4-segment curved horseshoe: [0 -> 1 -> back-center -> 2 -> 3]
    hb = [h_bot[0], h_bot[1], h_mid_b, h_bot[2], h_bot[3]]
    ht = [h_top[0], h_top[1], h_mid_t, h_top[2], h_top[3]]
    for k in range(4):
        p0, p1, p2, p3 = hb[k], hb[k + 1], ht[k + 1], ht[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        mb.face([p0, p1, p2, p3], HOODIE if k in (0, 3) else HOODIE_SHADE, out=V(mid.x, 0.08, mid.z))
        mb.face([ht[k], ht[k + 1], h_in[k + 1], h_in[k]], HOODIE_HOOD if k in (0, 3) else HOODIE_INNER, out=(0, 1, 0))
    # Rear hood overhang underside (closing back gap cleanly behind vest shoulders = 1 tri)
    mb.face([hb[1], hb[2], hb[3]], HOODIE_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 8. FOREST-GREEN QUILTED PUFFER VEST (3 plush horizontal baffles = 64 tris)
    # =========================================================================
    mb.set_part("puffer_vest", bone="Torso")
    # 6 profile rings (5 vertical bands) sculpting 3 tall, pillowy horizontal down baffles
    # separated by crisp narrow stitched horizontal creases, tapering softly at shoulders:
    #   Band 0 (y=0.654 -> 0.798): tall lower puffer baffle (with diagonal hand pockets)
    #   Band 1 (y=0.798 -> 0.822): crisp narrow stitched crease 1 pinching inward
    #   Band 2 (y=0.822 -> 0.964): tall middle puffer baffle swelling outward
    #   Band 3 (y=0.964 -> 0.988): crisp narrow stitched crease 2 pinching inward
    #   Band 4 (y=0.988 -> 1.126): tall upper chest baffle tapering smoothly to shoulders
    vest_specs = [
        # (y,     rx,    z_f_in, z_f_out, z_b,    open_x)
        (0.654, 0.214,  0.150,  0.140,  -0.134,  0.056),  # 0: bottom hem (tucked in)
        (0.798, 0.242,  0.168,  0.172,  -0.164,  0.052),  # 1: baffle 1 pillowy crest
        (0.822, 0.214,  0.152,  0.144,  -0.136,  0.052),  # 2: narrow stitched crease 1
        (0.964, 0.236,  0.166,  0.168,  -0.160,  0.050),  # 3: baffle 2 pillowy crest
        (0.988, 0.208,  0.150,  0.140,  -0.132,  0.052),  # 4: narrow stitched crease 2
        (1.126, 0.194,  0.152,  0.146,  -0.138,  0.060),  # 5: baffle 3 tapered shoulder top
    ]
    v_rings = []
    for (y, rx, zfi, zfo, zb, ox) in vest_specs:
        v_rings.append([
            V(-ox, y, zfi),  # 0: front-R inner
            V(-rx, y, zfo),  # 1: front-R outer
            V(-rx, y, zb),   # 2: back-R outer
            V( rx, y, zb),   # 3: back-L outer
            V( rx, y, zfo),  # 4: front-L outer
            V( ox, y, zfi),  # 5: front-L inner
        ])

    # 5 bands x 5 outer quads = 50 tris (k=0..4; skip k=5 which is open front gap!)
    for i in range(len(v_rings) - 1):
        r0, r1 = v_rings[i], v_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        # Narrow crease channels (i=1, 3) shaded dark green; tall puffy pillows catch brighter green!
        for k in range(5):
            p0, p1, p2, p3 = r0[k], r0[k + 1], r1[k + 1], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i in (1, 3):
                col = VEST_SHADE
            elif k in (0, 4):
                col = VEST_HIGHLIGHT if i in (2, 4) else VEST
            else:
                col = VEST
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid))

    # Inner thickness walls along open front placket (2 quads = 4 tris, neatly flush with zipper edge)
    for side_idx, sx in ((0, -1), (5, 1)):
        p_b_out = v_rings[0][side_idx]
        p_t_out = v_rings[-1][side_idx]
        p_b_in  = V(p_b_out.x, p_b_out.y, sz_f - 0.004)
        p_t_in  = V(p_t_out.x, p_t_out.y, sz_f - 0.008)
        mb.face([p_b_in, p_b_out, p_t_out, p_t_in], VEST_SHADE, out=(-sx, 0, 0))

    # Shoulder top caps closing vest smoothly onto hoodie shoulders (2 quads = 4 tris)
    rt = v_rings[-1]
    mb.face([rt[0], rt[1], rt[2], V(-0.072, 1.132, -0.124)], VEST, out=(0, 1, 0))
    mb.face([rt[5], V(0.072, 1.132, -0.124), rt[3], rt[4]],  VEST, out=(0, 1, 0))

    # Bottom hem underside closing vest cleanly over charcoal trousers (1 quad = 2 tris)
    rb_v = v_rings[0]
    mb.face([rb_v[1], rb_v[2], rb_v[3], rb_v[4]], VEST_SHADE, out=(0, -1, 0))

    # Slanted side pocket welt strips hugging lowest puffer baffle surface tightly (2 quads = 4 tris)
    for side in (-1, 1):
        # Interpolate lower baffle front plane (y=0.654..0.798) + 0.005 m proud
        def _baffle0_z(y, u_out):
            t = (y - 0.654) / (0.798 - 0.654)
            z_in_t = 0.150 + (0.168 - 0.150) * t
            z_out_t = 0.140 + (0.172 - 0.140) * t
            return z_in_t + (z_out_t - z_in_t) * u_out + 0.005

        x_lo, y_lo = side * 0.156, 0.684
        x_hi, y_hi = side * 0.228, 0.772
        z_lo = _baffle0_z(y_lo, 0.62)
        z_hi = _baffle0_z(y_hi, 0.96)
        mb.face([
            V(x_lo, y_lo,         z_lo),
            V(x_hi, y_hi,         z_hi),
            V(x_hi, y_hi + 0.016, _baffle0_z(y_hi + 0.016, 0.96)),
            V(x_lo, y_lo + 0.016, _baffle0_z(y_lo + 0.016, 0.62)),
        ], VEST_POCKET, out=(side * 0.45, 0.15, 0.88))

    # =========================================================================
    # 9. CHUNKY CREAM HOODIE SLEEVES (2 bent geometric sleeves = 32 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Chunky bent hoodie sleeves echoing the reference's relaxed hands-by-pockets posture,
    # emerging cleanly under the tapered vest shoulders and clear of the lower baffle in Walk & Idle!
    arm_specs = [
        ( 1, "Arm_L", V( 0.174, 1.028,  0.000), V( 0.326, 0.866, -0.024), V( 0.278, 0.740, 0.056)),
        (-1, "Arm_R", V(-0.174, 1.028,  0.000), V(-0.326, 0.866, -0.024), V(-0.278, 0.740, 0.056)),
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

        r_sh = s_ring(p_sh, ax1, 0.082, 0.088)
        r_el = s_ring(p_el, axm, 0.098, 0.102)
        r_wr = s_ring(p_wr, ax2, 0.074, 0.078)
        mb.loft([r_sh, r_el, r_wr],
                lambda i, k: HOODIE_SHADE if (k == 2 or (i == 1 and k == 3)) else HOODIE,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 10. HANDS (2 chunky warm-tan fists peeking from cream cuffs = 20 tris)
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

        c0 = p_wr - ax * 0.010
        c1 = p_wr + ax * 0.096
        r0 = [
            c0 + u * (-0.052) + v * ( 0.056),
            c0 + u * ( 0.052) + v * ( 0.056),
            c0 + u * ( 0.052) + v * (-0.056),
            c0 + u * (-0.052) + v * (-0.056),
        ]
        r1 = [
            c1 + u * (-0.042) + v * ( 0.046),
            c1 + u * ( 0.042) + v * ( 0.046),
            c1 + u * ( 0.042) + v * (-0.046),
            c1 + u * (-0.042) + v * (-0.046),
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 11. DARK CHARCOAL WIDE CROPPED TROUSERS + EXPOSED ANKLES (8 + 20 + 16 = 44 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.194, 0.194, 0.546, 0.672, -0.108, 0.108, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        # Wide straight-cut cropped charcoal trousers matching reference silhouette
        x_in_t, x_out_t = side * 0.006, side * 0.194
        x_in_b, x_out_b = side * 0.046, side * 0.244
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

    # Warm tan bare ankles peeking cleanly between cropped trouser cuffs and cream sneakers (2 x 6 = 12 tris)
    mb.set_part("ankles")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.144
        a_bot = oval_ring(cx, 0.118, 0.002, 0.056, 0.058, n=3, phase=0.0)
        a_top = oval_ring(cx, 0.192, 0.002, 0.060, 0.062, n=3, phase=0.0)
        mb.loft([a_bot, a_top], SKIN_SHADE, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 12. CHUNKY CREAM SNEAKERS / LOAFERS WITH BEIGE OUTSOLES (20 tris x 2 = 40 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.144
        w = 0.072
        w_toe = 0.060
        z_heel = -0.092
        z_toe  =  0.172
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_col   = 0.130

        # Thick chunky warm-beige outsole (4 sides + bottom = 10 tris)
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
    """24-frame looping Walk cycle: relaxed, confident urban stroll in puffer vest & hoodie."""
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

        # Easygoing bounce & slight forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.024 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.046, -0.064 * s1, 0.034 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Natural torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.018 * c2, 0.095 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Steady, laid-back head bob
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.038 + 0.022 * c2, -0.038 * s1, -0.014 * c1)
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

        # Relaxed opposite-phase hoodie arm swing clearing puffer vest cleanly
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.30 * s1, 0.0, 0.054 + 0.016 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.30 * s1, 0.0, -0.054 + 0.016 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: chill ferry-dock wait, calm breathing & casual look-around."""
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

        # Relaxed weight shift & cozy breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.010, 0.022 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.024 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Easygoing look-around across the harbor
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * s2, 0.22 * s1, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Feet planted squarely
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Cozy breathing drift on hoodie sleeves
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.036 * s1 - 0.014 * s2, 0.0, 0.024 + 0.014 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.036 * s1 - 0.014 * s2, 0.0, -0.024 + 0.014 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build standard 7-bone Tideways passenger rig with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonPufferVestRig")
    rig = bpy.data.objects.new("PersonPufferVestRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.615, 0.000), ( 0.000, 0.715, 0.000)),
        ("Torso", "Root",  ( 0.000, 0.670, 0.000), ( 0.000, 1.125, 0.000)),
        ("Head",  "Torso", ( 0.000, 1.160, 0.000), ( 0.000, 1.480, 0.000)),
        ("Arm_L", "Torso", ( 0.174, 1.028, 0.000), ( 0.174, 1.188, 0.000)),
        ("Arm_R", "Torso", (-0.174, 1.028, 0.000), (-0.174, 1.188, 0.000)),
        ("Leg_L", "Root",  ( 0.106, 0.565, 0.000), ( 0.106, 0.725, 0.000)),
        ("Leg_R", "Root",  (-0.106, 0.565, 0.000), (-0.106, 0.725, 0.000)),
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

    coll = bpy.data.collections.new("PersonPufferVest")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonPufferVest")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonPufferVest", me)
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

    print("=== PersonPufferVest Stats ===")
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
