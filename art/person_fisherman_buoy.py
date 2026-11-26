# Builds a low-poly (< 500 tris) stylized commercial fisherman with a chunky cuffed navy knit
# beanie, sculpted rounded brown beard & bushy mustache, olive-green pullover hoodie, thick
# layered golden-yellow foul-weather bib overalls (with scooped sides, full shoulder straps,
# bronze buttons, 3D chest pocket & cuffed legs), slate-blue rubber work gloves with thumbs,
# sculpted brown boots, and a plump 6-sided red-striped white lobster buoy tied with thick
# coiled hemp rope to his right overall shoulder strap in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_fisherman_buoy.py)
# Saves art/person_fisherman_buoy.blend, exports assets/models/person_fisherman_buoy.glb (rigged + Walk & Idle cycles),
# renders art/person_fisherman_buoy_preview.png, art/person_fisherman_buoy_walk_preview.png,
# art/person_fisherman_buoy_idle_preview.png, and outputs rendered videos
# art/person_fisherman_buoy_walk.mp4 and art/person_fisherman_buoy_idle.mp4.
#
# Strict triangle budget: < 500 triangles (350 base + 150 extra detail pass).
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.64 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_fisherman_buoy.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_fisherman_buoy.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_fisherman_buoy_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_fisherman_buoy_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_fisherman_buoy_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_fisherman_buoy_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_fisherman_buoy_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette closely matched to reference commercial fisherman concept art (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN              = col_srgb(0.95, 0.72, 0.48)
SKIN_SHADE        = col_srgb(0.84, 0.61, 0.39)
EYE               = col_srgb(0.11, 0.10, 0.11)

BEARD             = col_srgb(0.45, 0.32, 0.23)
HAIR_DARK         = col_srgb(0.38, 0.26, 0.19)
BEARD_SHADE       = col_srgb(0.33, 0.22, 0.16)
MUSTACHE          = col_srgb(0.49, 0.35, 0.25)

BEANIE            = col_srgb(0.35, 0.42, 0.56)
BEANIE_CUFF       = col_srgb(0.30, 0.37, 0.50)
BEANIE_SHADE      = col_srgb(0.23, 0.29, 0.41)

HOODIE            = col_srgb(0.39, 0.49, 0.39)
HOODIE_SHADE      = col_srgb(0.30, 0.40, 0.30)
HOODIE_HOOD       = col_srgb(0.35, 0.45, 0.35)

OVERALLS          = col_srgb(0.99, 0.82, 0.22)
OVERALLS_SHADE    = col_srgb(0.88, 0.70, 0.16)
OVERALLS_STRAP    = col_srgb(0.96, 0.78, 0.20)
OVERALLS_TRIM     = col_srgb(0.68, 0.53, 0.16)
OVERALLS_BUTTON   = col_srgb(0.42, 0.33, 0.22)

GLOVE             = col_srgb(0.36, 0.49, 0.69)
GLOVE_SHADE       = col_srgb(0.27, 0.39, 0.57)

BOOT              = col_srgb(0.60, 0.42, 0.27)
BOOT_SHADE        = col_srgb(0.48, 0.33, 0.20)
SOLE              = col_srgb(0.31, 0.23, 0.17)

BUOY_WHITE        = col_srgb(0.94, 0.91, 0.86)
BUOY_SHADE        = col_srgb(0.81, 0.78, 0.73)
BUOY_STRIPE       = col_srgb(0.77, 0.33, 0.25)
BUOY_STRIPE_SHADE = col_srgb(0.62, 0.25, 0.19)
BUOY_PEG          = col_srgb(0.68, 0.53, 0.38)
ROPE              = col_srgb(0.83, 0.69, 0.50)
ROPE_SHADE        = col_srgb(0.67, 0.54, 0.37)


# Parts the game recolours per passenger (see art/person_recolor.py).
# Note: "bottom" tags the foul-weather bib overalls; scripts/sim/passenger.gd restricts
# this model's bottom palette to orange and yellow oilskin shades only.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [BEARD, HAIR_DARK, BEARD_SHADE, MUSTACHE],
    "top": [HOODIE, HOODIE_SHADE, HOODIE_HOOD],
    "bottom": [OVERALLS, OVERALLS_SHADE, OVERALLS_STRAP, OVERALLS_TRIM],
    "accent": [BEANIE, BEANIE_CUFF, BEANIE_SHADE],
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
            wb = ring_weights[0] if ring_weights is not None else None
            if n <= 4:
                self.face(r0, col, out=out_dir, weights=([wb] * n if wb is not None else None))
            elif n == 5:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb is not None else None))
                self.face([r0[0], r0[3], r0[4]], col, out=out_dir, weights=([wb] * 3 if wb is not None else None))
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb is not None else None))
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=([wb] * 4 if wb is not None else None))
            else:
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=([wb] * 3 if wb is not None else None))
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt = ring_weights[-1] if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([wt] * n if wt is not None else None))
            elif n == 5:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt is not None else None))
                self.face([rt[0], rt[3], rt[4]], col, out=out_dir, weights=([wt] * 3 if wt is not None else None))
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt is not None else None))
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=([wt] * 4 if wt is not None else None))
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=([wt] * 3 if wt is not None else None))

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

    def tri_strap(self, pts, norms, half_w, thick, colors, skip_k=()):
        """Low-poly 3-sided prism ribbon along polyline `pts` with outward normals `norms`."""
        rings = []
        n_pts = len(pts)
        for idx in range(n_pts):
            p = Vector(pts[idx])
            if idx == 0:
                tang = (Vector(pts[1]) - p).normalized()
            elif idx == n_pts - 1:
                tang = (p - Vector(pts[idx - 1])).normalized()
            else:
                tang = (Vector(pts[idx + 1]) - Vector(pts[idx - 1])).normalized()
            nrm = Vector(norms[idx])
            nrm = (nrm - tang * nrm.dot(tang)).normalized()
            side = tang.cross(nrm).normalized()
            rings.append([
                p + nrm * (thick * 0.48) - side * half_w,
                p + nrm * (thick * 0.48) + side * half_w,
                p - nrm * (thick * 0.52),
            ])
        self.loft(rings, colors, cap_bottom=False, cap_top=False, skip_k=skip_k)

    def tube_path(self, pts, rad, n=4, colors=ROPE, cap_bottom=False, cap_top=False, phase=math.pi / 4.0):
        """Chunky N-sided tube following polyline `pts` (great for thick braided hemp ropes!)."""
        rings = []
        n_pts = len(pts)
        for idx in range(n_pts):
            p = Vector(pts[idx])
            if idx == 0:
                tang = (Vector(pts[1]) - p).normalized()
            elif idx == n_pts - 1:
                tang = (p - Vector(pts[idx - 1])).normalized()
            else:
                tang = (Vector(pts[idx + 1]) - Vector(pts[idx - 1])).normalized()
            ref = V(0.0, 1.0, 0.0) if abs(tang.y) < 0.85 else V(1.0, 0.0, 0.0)
            u = tang.cross(ref).normalized()
            v = tang.cross(u).normalized()
            r_i = rad[idx] if isinstance(rad, (list, tuple)) else rad
            rings.append([
                p + u * (r_i * math.cos(phase + 2.0 * math.pi * k / n))
                  + v * (r_i * math.sin(phase + 2.0 * math.pi * k / n))
                for k in range(n)
            ])
        self.loft(rings, colors, cap_bottom=cap_bottom, cap_top=cap_top)


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
    # 1. HEAD (6-sided stylized fisherman head nestled snugly over hoodie collar = 18 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.122,  0.012, 0.168, 0.156),  # 0: jaw/nape base
        (1.224,  0.016, 0.216, 0.200),  # 1: cheek / beard top line
        (1.412,  0.008, 0.216, 0.200),  # 2: brow tucked cleanly inside beanie cuff
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks, k=1,2,3 back/sideburns
    # Band i=0 front/cheeks (k=4,5,0) are fully covered by the sculpted beard shell so skip them!
    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            if i == 0 and k in (4, 5, 0):
                continue
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 0:
                col = BEARD_SHADE if k == 2 else HAIR_DARK
            else:
                col = SKIN if k in (4, 5, 0) else HAIR_DARK
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid))

    # =========================================================================
    # 2. SCULPTED ROUNDED FULL BEARD + PLUMP WALRUS MUSTACHE (30 + 16 = 46 tris)
    # =========================================================================
    mb.set_part("beard", bone="Head")
    # 5-segment rounded arc wrapping cleanly from sideburn -> outer cheek -> full rounded chin -> opposite sideburn!
    b_bot = [
        V(-0.194, 1.158, -0.014),  # 0: right jaw back (seals cleanly into nape hair)
        V(-0.172, 1.128,  0.118),  # 1: right outer jaw curve
        V(-0.088, 1.106,  0.204),  # 2: right front chin
        V( 0.088, 1.106,  0.204),  # 3: left front chin
        V( 0.172, 1.128,  0.118),  # 4: left outer jaw curve
        V( 0.194, 1.158, -0.014),  # 5: left jaw back
    ]
    b_top = [
        V(-0.222, 1.258, -0.014),  # 0: right sideburn high
        V(-0.204, 1.242,  0.126),  # 1: right cheek curve
        V(-0.098, 1.246,  0.222),  # 2: right upper beard under mustache
        V( 0.098, 1.246,  0.222),  # 3: left upper beard under mustache
        V( 0.204, 1.242,  0.126),  # 4: left cheek curve
        V( 0.222, 1.258, -0.014),  # 5: left sideburn high
    ]
    b_in_top = [
        V(-0.190, 1.254, -0.010),
        V(-0.176, 1.238,  0.114),
        V(-0.084, 1.242,  0.186),
        V( 0.084, 1.242,  0.186),
        V( 0.176, 1.238,  0.114),
        V( 0.190, 1.254, -0.010),
    ]
    b_in_bot = [
        V(-0.148, 1.148, -0.008),
        V(-0.128, 1.128,  0.088),
        V(-0.066, 1.116,  0.146),
        V( 0.066, 1.116,  0.146),
        V( 0.128, 1.128,  0.088),
        V( 0.148, 1.148, -0.008),
    ]
    for k in range(5):
        p0, p1, p2, p3 = b_bot[k], b_bot[k + 1], b_top[k + 1], b_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        col = BEARD_SHADE if k in (0, 4) else BEARD
        mb.face([p0, p1, p2, p3], col, out=V(mid.x, -0.10, mid.z))
        mb.face([b_top[k], b_top[k + 1], b_in_top[k + 1], b_in_top[k]], BEARD, out=(0, 1, 0.1))
        mb.face([b_bot[k + 1], b_bot[k], b_in_bot[k], b_in_bot[k + 1]], BEARD_SHADE, out=(0, -1, 0))

    # Plump, rounded 2-wing walrus fisherman mustache arching snugly across the upper lip (16 tris)
    # 3 cross-sections: left tip -> full plump center arch -> right tip!
    m_ctr = [
        V(0.000, 1.264, 0.198),  # 0: top back (against face)
        V(0.000, 1.262, 0.232),  # 1: top front ridge
        V(0.000, 1.222, 0.234),  # 2: lower front fullness
        V(0.000, 1.218, 0.200),  # 3: bottom back
    ]
    m_l = [
        V(-0.118, 1.236, 0.186),
        V(-0.114, 1.240, 0.218),
        V(-0.120, 1.202, 0.216),
        V(-0.118, 1.200, 0.186),
    ]
    m_r = [
        V( 0.118, 1.236, 0.186),
        V( 0.114, 1.240, 0.218),
        V( 0.120, 1.202, 0.216),
        V( 0.118, 1.200, 0.186),
    ]
    # Loft left wing -> center -> right wing, skipping k=3 (hidden back face flush against face = 12 tris + 2 end caps = 16 tris!)
    mb.loft(
        [m_l, m_ctr, m_r],
        lambda i, k: BEARD_SHADE if k == 2 else MUSTACHE,
        cap_bottom=True, cap_top=True,
        bot_color=BEARD_SHADE, top_color=BEARD_SHADE,
        skip_k=(3,),
    )

    # =========================================================================
    # 3. EARS (compact beveled low-poly wedges peeking cleanly below beanie cuff = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in  = side * 0.198
        x_out = side * 0.238
        p_in  = V(x_in,  1.272,  0.014)
        p_tf  = V(x_out, 1.304,  0.036)
        p_tb  = V(x_out, 1.304, -0.010)
        p_bf  = V(x_out, 1.242,  0.032)
        p_bb  = V(x_out, 1.242, -0.006)
        mb.face([p_bf, p_bb, p_tb, p_tf], SKIN,       out=(side, 0, 0))
        mb.face([p_in, p_bf, p_tf],       SKIN,       out=(0, 0, 1))
        mb.face([p_bb, p_in, p_tb],       SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 4. NECK (compact 3-sided throat peeking snugly above cozy hood collar = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.052, 0.016, 0.072, 0.068, n=3, phase=0.0)
    neck_r1 = oval_ring(0.0, 1.148, 0.018, 0.068, 0.064, n=3, phase=0.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 5. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    # Flat front face z ≈ 0.016 + 0.866025 * 0.200 = 0.1892
    z_eye = 0.194
    for side in (-1, 1):
        cx = side * 0.062
        cy = 1.314
        rx = 0.019
        ry = 0.045
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
    # 6. NAVY KNIT FISHERMAN BEANIE (chunky overhanging folded cuff + crisp step + rounded crown = 40 tris)
    # =========================================================================
    mb.set_part("beanie", bone="Head")
    tilt = math.radians(17.5)
    st, ct = math.sin(tilt), math.cos(tilt)
    beanie_orig = V(0.0, 1.362, -0.008)

    def beanie_ring(h, rx, rz):
        cy = beanie_orig.y + h * ct
        cz = beanie_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, tilt, n=6, phase=math.pi / 6.0)

    b_cuff0 = beanie_ring(0.000, 0.246, 0.238)  # thick folded cuff bottom rim
    b_cuff1 = beanie_ring(0.098, 0.252, 0.244)  # chunky overhanging cuff top ridge
    b_dome0 = beanie_ring(0.106, 0.224, 0.218)  # crisp inset knit fold crease!
    b_dome1 = beanie_ring(0.242, 0.146, 0.142)  # soft rounded beanie crown shoulder

    # Folded ribbed cuff outer band (12 tris)
    mb.loft(
        [b_cuff0, b_cuff1],
        lambda i, k: BEANIE_SHADE if k in (1, 2, 3) else BEANIE_CUFF,
        cap_bottom=False, cap_top=False,
    )
    # Crisp folded cuff top overhang step into dome (12 tris)
    mb.loft(
        [b_cuff1, b_dome0],
        BEANIE_SHADE,
        cap_bottom=False, cap_top=False,
    )
    # Rounded knit dome + flat-topped crown cap (12 + 4 = 16 tris)
    mb.loft(
        [b_dome0, b_dome1],
        lambda i, k: BEANIE_CUFF if k in (1, 2, 3) else BEANIE,
        cap_bottom=False, cap_top=True, top_color=BEANIE,
    )

    # =========================================================================
    # 7. OLIVE-GREEN PULLOVER HOODIE UPPER TORSO + CHUNKY FOLDED HOOD (16 + 10 = 26 tris)
    #    (Worn UNDERNEATH the thick yellow overalls so the overalls have real physical thickness!)
    # =========================================================================
    mb.set_part("hoodie", bone="Torso")
    h_bot  = oval_ring(0.0, 0.810, 0.004, 0.204, 0.138, n=6, phase=math.pi / 6.0)
    h_shld = oval_ring(0.0, 1.078, 0.002, 0.194, 0.132, n=6, phase=math.pi / 6.0)
    mb.loft(
        [h_bot, h_shld],
        lambda i, k: HOODIE_SHADE if k in (1, 2, 3) else HOODIE,
        cap_bottom=False, cap_top=True, top_color=HOODIE,
    )

    # Chunky cozy folded olive hood collar wrapping snugly around the neck & upper back (10 tris)
    hd_bot = [
        V(-0.144, 1.050,  0.072),
        V( 0.144, 1.050,  0.072),
        V( 0.174, 1.036, -0.194),
        V(-0.174, 1.036, -0.194),
    ]
    hd_top = [
        V(-0.118, 1.132,  0.056),
        V( 0.118, 1.132,  0.056),
        V( 0.146, 1.162, -0.166),
        V(-0.146, 1.162, -0.166),
    ]
    # Keep all 4 sides + top cap? Skip front bottom? No, skip k=0 front neck gap -> 6 sides + 2 top = 8 tris!
    # Add front collar left/right wrap lapels: actually keeping all 4 sides (k=0 dips slightly at throat) = 10 tris!
    hd_top[0] = V(-0.116, 1.116, 0.068)
    hd_top[1] = V( 0.116, 1.116, 0.068)
    mb.loft([hd_bot, hd_top], lambda i, k: HOODIE if k == 0 else HOODIE_HOOD,
            cap_bottom=False, cap_top=True, top_color=HOODIE)

    # =========================================================================
    # 8. THICK LAYERED YELLOW OILSKIN BIB OVERALLS TORSO (outer bib + thickness rim + crotch = 28 tris)
    #    - Sits physically OUTSIDE the olive hoodie (~2.2 cm fabric stand-off!)
    #    - Raised front & back chest bib panels with scooped lower sides under the armpits!
    # =========================================================================
    mb.set_part("overalls_torso", bone="Torso")
    o_hip  = oval_ring(0.0, 0.582, 0.004, 0.252, 0.178, n=6, phase=math.pi / 6.0)
    o_top  = oval_ring(0.0, 0.872, 0.004, 0.236, 0.168, n=6, phase=math.pi / 6.0)
    # Sculpt bib silhouette: front chest (indices 5, 0) rises proudly to 0.946;
    # back bib (indices 2, 3) rises to 0.922; side armpits (indices 1, 4) scoop down to 0.848!
    o_top[5] = V(o_top[5].x, 0.946, o_top[5].z + 0.008)
    o_top[0] = V(o_top[0].x, 0.946, o_top[0].z + 0.008)
    o_top[1] = V(o_top[1].x, 0.848, o_top[1].z)
    o_top[4] = V(o_top[4].x, 0.848, o_top[4].z)
    o_top[2] = V(o_top[2].x, 0.922, o_top[2].z - 0.006)
    o_top[3] = V(o_top[3].x, 0.922, o_top[3].z - 0.006)

    # Inner thickness edge stepping smoothly inward onto the olive hoodie (gives unmistakable thick oilskin rim!)
    o_rim_in = [
        V(p.x * 0.84, p.y - 0.006, p.z * 0.82) for p in o_top
    ]

    # Outer yellow oilskin overalls body (12 tris)
    mb.loft(
        [o_hip, o_top],
        lambda i, k: OVERALLS_SHADE if k in (1, 2, 3) else OVERALLS,
        cap_bottom=False, cap_top=False,
    )
    # Chunky 3D top thickness rim around front chest bib, scooped armholes & back bib (12 tris)
    mb.loft(
        [o_top, o_rim_in],
        OVERALLS_SHADE,
        cap_bottom=False, cap_top=False,
    )

    # Pelvis crotch bridge (front + back = 4 tris, weighted to Root so thighs never show a gap!)
    mb.set_part("overalls_torso", bone="Root")
    mb.box(-0.200, 0.200, 0.510, 0.610, -0.122, 0.122, OVERALLS_SHADE, skip=("top", "bottom", "left", "right"))

    # =========================================================================
    # 9. 3D BIB DETAILS: EXTRUDED CHEST POCKET, TOP WELT & BRONZE SNAP BUTTONS + THICK STRAPS (16 + 36 = 52 tris)
    # =========================================================================
    mb.set_part("overalls_details", bone="Torso")
    # Extruded 3D front chest pocket sitting proudly off the thick yellow bib (10 tris)
    # Main pocket box (front + left + right + bottom = 8 tris; skip back flush with bib & top covered by welt!)
    mb.box(
        -0.076, 0.076,
        0.758, 0.864,
        0.150, 0.172,
        {"front": OVERALLS, "left": OVERALLS_SHADE, "right": OVERALLS_SHADE, "bottom": OVERALLS_SHADE},
        skip=("back", "top"),
    )
    # Crisp darker horizontal top welt hem capping the extruded pocket (front + top = 4 tris)
    mb.box(
        -0.076, 0.076,
        0.864, 0.888,
        0.150, 0.173,
        {"front": OVERALLS_TRIM, "top": OVERALLS_TRIM},
        skip=("back", "bottom", "left", "right"),
    )

    # Two chunky dark bronze metal overall snap buttons sitting proudly on strap-to-bib corners (4 tris)
    for side in (-1, 1):
        bx = side * 0.100
        by = 0.916
        bz = 0.176
        r_btn = 0.019
        mb.face([
            V(bx - r_btn, by - r_btn, bz),
            V(bx + r_btn, by - r_btn, bz),
            V(bx + r_btn, by + r_btn, bz - 0.001),
            V(bx - r_btn, by + r_btn, bz - 0.001),
        ], OVERALLS_BUTTON, out=(0, 0, 1))

    # Two bold, chunky 4-point (3-segment) yellow oilskin shoulder straps riding cleanly OUTSIDE hoodie! (36 tris)
    mb.set_part("overalls_straps", bone="Torso")
    for side in (-1, 1):
        sx_bib = side * 0.100
        sx_sh  = side * 0.132
        strap_pts = [
            V(sx_bib, 0.922,  0.158),   # 0: front bib button anchor
            V(sx_sh,  1.088,  0.122),   # 1: front-top hoodie shoulder corner
            V(sx_sh,  1.088, -0.118),   # 2: back-top hoodie shoulder corner
            V(sx_bib, 0.902, -0.156),   # 3: back bib anchor
        ]
        strap_norms = [
            V(side * 0.14, 0.18,  0.97),
            V(side * 0.18, 0.78,  0.60),
            V(side * 0.18, 0.78, -0.60),
            V(side * 0.14, 0.18, -0.97),
        ]
        mb.tri_strap(
            strap_pts, strap_norms,
            half_w=0.029, thick=0.028,
            colors=lambda i, k: OVERALLS_STRAP if k == 0 else OVERALLS_SHADE,
        )

    # =========================================================================
    # 10. OLIVE HOODIE SLEEVES & BLUE RUBBER WORK GLOVES WITH CHUNKY THUMBS (32 + 30 = 62 tris)
    # =========================================================================
    def build_arm_and_glove(p_sh, p_el, p_wr, glove_len, side_sign, arm_bone, fore_bone):
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax_mid = (ax1 + ax2).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def ring4(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            if u.length < 1e-5:
                u = V(0.0, 0.0, 1.0)
            else:
                u = u.normalized()
            v = axis.cross(u).normalized()
            return [
                ctr + u * (-rx) + v * ( rperp),
                ctr + u * ( rx) + v * ( rperp),
                ctr + u * ( rx) + v * (-rperp),
                ctr + u * (-rx) + v * (-rperp),
            ]

        r_sh = ring4(p_sh, ax1,    0.072, 0.078)
        r_el = ring4(p_el, ax_mid, 0.084, 0.088)
        r_wr = ring4(p_wr, ax2,    0.072, 0.076)

        w_sh = {arm_bone: 1.0}
        w_el = {arm_bone: 0.5, fore_bone: 0.5}
        w_wr = {fore_bone: 1.0}

        mb.set_part("sleeves")
        mb.loft(
            [r_sh, r_el, r_wr],
            lambda i, k: HOODIE_SHADE if k in (2, 3) else HOODIE,
            cap_bottom=False, cap_top=False,
            ring_weights=[w_sh, w_el, w_wr],
        )

        # Chunky slate-blue commercial rubber fishing glove + distinct mitten thumb (10 + 5 = 15 tris)
        mb.set_part("gloves", bone=fore_bone)
        r_g0 = ring4(p_wr, ax2, 0.068, 0.072)
        r_g1 = ring4(p_wr + ax2 * glove_len, ax2, 0.052, 0.056)
        mb.loft(
            [r_g0, r_g1],
            lambda i, k: GLOVE_SHADE if k in (2, 3) else GLOVE,
            cap_bottom=False, cap_top=True, top_color=GLOVE_SHADE,
        )
        # Chunky rubber glove thumb protruding forward/inward (3-sided tapered stub skipping buried back = 5 tris!)
        th_base = p_wr + ax2 * (glove_len * 0.36) + V(-side_sign * 0.022, 0.004, 0.044)
        th_dir  = (ax2 * 0.62 + V(-side_sign * 0.25, -0.10, 0.74)).normalized()
        th_u = th_dir.cross(V(0.0, 1.0, 0.0)).normalized()
        th_v = th_dir.cross(th_u).normalized()
        th_r0 = [th_base + th_u * (0.026 * math.cos(2.0 * math.pi * k / 3.0))
                         + th_v * (0.026 * math.sin(2.0 * math.pi * k / 3.0)) for k in range(3)]
        th_r1 = [th_base + th_dir * 0.052
                         + th_u * (0.018 * math.cos(2.0 * math.pi * k / 3.0))
                         + th_v * (0.018 * math.sin(2.0 * math.pi * k / 3.0)) for k in range(3)]
        mb.loft([th_r0, th_r1], GLOVE, cap_bottom=False, cap_top=True, top_color=GLOVE_SHADE, skip_k=(2,))

    # Left arm (+X)
    p_l_sh = V( 0.184, 0.976,  0.002)
    p_l_el = V( 0.278, 0.824, -0.010)
    p_l_wr = V( 0.284, 0.684,  0.036)
    build_arm_and_glove(p_l_sh, p_l_el, p_l_wr, glove_len=0.130, side_sign=1, arm_bone="Arm_L", fore_bone="Forearm_L")

    # Right arm (-X, cleared cleanly forward of the hanging lobster buoy!)
    p_r_sh = V(-0.184, 0.976,  0.012)
    p_r_el = V(-0.282, 0.824, -0.002)
    p_r_wr = V(-0.286, 0.684,  0.046)
    build_arm_and_glove(p_r_sh, p_r_el, p_r_wr, glove_len=0.130, side_sign=-1, arm_bone="Arm_R", fore_bone="Forearm_R")

    # =========================================================================
    # 11. PLUMP 6-SIDED LOBSTER BUOY & THICK COILED HEMP ROPE TIED TO RIGHT STRAP (55 + 42 = 97 tris)
    # =========================================================================
    mb.set_part("buoy", bone="Buoy")
    buoy_ctr = V(-0.238, 0.566, -0.258)
    # Axis pointing UP-FORWARD-INWARD toward the chunky rope coil on the back-right shoulder strap
    buoy_axis = V(0.24, 0.91, 0.34).normalized()
    ref_up = V(1.0, 0.0, 0.0)
    buoy_u = buoy_axis.cross(ref_up).normalized()
    buoy_v = buoy_axis.cross(buoy_u).normalized()

    def buoy_ring(l_pos, rad, n=6, phase=math.pi / 6.0):
        c = buoy_ctr + buoy_axis * l_pos
        pts = []
        for k in range(n):
            a = phase + 2.0 * math.pi * k / n
            pts.append(c + buoy_u * (rad * math.cos(a)) + buoy_v * (rad * math.sin(a)))
        return pts

    # Plump 6-sided faceted white maritime float buoy with bold terracotta-red center band (40 tris)
    r_b_bot = buoy_ring(-0.158, 0.064, n=6)
    r_b_s0  = buoy_ring(-0.052, 0.112, n=6)
    r_b_s1  = buoy_ring( 0.044, 0.112, n=6)
    r_b_hi  = buoy_ring( 0.148, 0.058, n=6)

    mb.loft(
        [r_b_bot, r_b_s0],
        lambda i, k: BUOY_SHADE if k in (2, 3, 4) else BUOY_WHITE,
        cap_bottom=True, cap_top=False, bot_color=BUOY_SHADE,
    )
    mb.loft(
        [r_b_s0, r_b_s1],
        lambda i, k: BUOY_STRIPE_SHADE if k in (2, 3, 4) else BUOY_STRIPE,
        cap_bottom=False, cap_top=False,
    )
    mb.loft(
        [r_b_s1, r_b_hi],
        lambda i, k: BUOY_SHADE if k in (2, 3, 4) else BUOY_WHITE,
        cap_bottom=False, cap_top=False,
    )

    # Tapered white wooden top spindle/stem rising UP into the thick braided rope eye (8 tris)
    neck_r0 = buoy_ring(0.132, 0.046, n=4, phase=math.pi / 4.0)
    neck_r1 = buoy_ring(0.285, 0.024, n=4, phase=math.pi / 4.0)
    mb.loft(
        [neck_r0, neck_r1],
        lambda i, k: BUOY_SHADE if k in (2, 3) else BUOY_WHITE,
        cap_bottom=False, cap_top=False,
    )

    # Blunt stubby 3-sided tan wooden dowel peg protruding cleanly out the bottom of buoy (7 tris)
    peg_r0 = buoy_ring(-0.228, 0.024, n=3, phase=0.0)
    peg_r1 = buoy_ring(-0.148, 0.027, n=3, phase=0.0)
    mb.loft([peg_r0, peg_r1], BUOY_PEG, cap_bottom=True, cap_top=False, bot_color=BUOY_PEG)

    # THICK COILED HEMP ROPE tying the buoy to his right yellow overall shoulder strap (42 tris)
    mb.set_part("rope", bone="Buoy")
    # 1. Thick rope collar cinched tightly around the base of the buoy's white upper neck (8 tris)
    col_r0 = buoy_ring(0.140, 0.068, n=4, phase=math.pi / 4.0)
    col_r1 = buoy_ring(0.194, 0.066, n=4, phase=math.pi / 4.0)
    mb.loft(
        [col_r0, col_r1],
        lambda i, k: ROPE_SHADE if k in (2, 3) else ROPE,
        cap_bottom=False, cap_top=False,
    )

    # 2. Thick twin braided rope loop rising on BOTH sides of the white buoy neck up to the shoulder coil! (12 tris)
    coil_base = buoy_ctr + buoy_axis * 0.345 + V(0.015, 0.010, 0.022)
    for sgn in (-1.0, 1.0):
        strand_pts = [
            buoy_ctr + buoy_axis * 0.168 + buoy_u * (sgn * 0.056),
            buoy_ctr + buoy_axis * 0.258 + buoy_u * (sgn * 0.072) + buoy_v * (0.012),
            coil_base + buoy_u * (sgn * 0.036),
        ]
        # 3-sided thick braided rope strand along 2 segments? Wait: 1 segment = 6 tris, 2 segs = 12 tris!
        # Use thick 1-segment bowed rope bridge per side (2 x 6 = 12 tris) so the white neck peeks right between them!
        mb.tube_path(
            [strand_pts[0], strand_pts[2]],
            rad=0.032, n=3,
            colors=lambda i, k: ROPE_SHADE if k == 2 else ROPE,
            cap_bottom=False, cap_top=False,
        )

    # 3. Plump twin coiled hemp rope rolls bundled tightly behind the right shoulder (2 x 10 = 20 tris, closed ends!)
    for idx_c, offset in enumerate((V(-0.016, 0.012, -0.022), V(0.022, 0.032, 0.018))):
        rc_ctr = coil_base + offset
        # Fat pillowy 4-sided coil roll oriented cleanly along the shoulder strap!
        c_ax = V(0.55, 0.58, 0.60).normalized()
        c_u = c_ax.cross(V(0.0, 1.0, 0.0)).normalized()
        c_v = c_ax.cross(c_u).normalized()
        r0 = [rc_ctr - c_ax * 0.046 + c_u * (0.058 * math.cos(math.pi / 4.0 + math.pi * 0.5 * k))
                                    + c_v * (0.054 * math.sin(math.pi / 4.0 + math.pi * 0.5 * k)) for k in range(4)]
        r1 = [rc_ctr + c_ax * 0.046 + c_u * (0.058 * math.cos(math.pi / 4.0 + math.pi * 0.5 * k))
                                    + c_v * (0.054 * math.sin(math.pi / 4.0 + math.pi * 0.5 * k)) for k in range(4)]
        mb.loft(
            [r0, r1],
            lambda i, k: ROPE_SHADE if k in (2, 3) else ROPE,
            cap_bottom=(idx_c == 0), cap_top=(idx_c == 1),
            bot_color=ROPE_SHADE, top_color=ROPE,
        )

    # 4. Thick hemp rope lashing looping directly onto the right yellow overall shoulder strap! (6 tris)
    hitch_pts = [
        coil_base + V(0.024, 0.034, 0.026),
        V(-0.132, 1.072, -0.088),
    ]
    hitch_norms = [
        V(-0.48, 0.72, -0.50),
        V(-0.45, 0.78, -0.42),
    ]
    mb.tri_strap(
        hitch_pts, hitch_norms,
        half_w=0.038, thick=0.038,
        colors=lambda i, k: ROPE if k == 0 else ROPE_SHADE,
    )

    # =========================================================================
    # 12. WIDE CUFFED YELLOW OILSKIN OVERALL LEGS (2 x 26 = 52 tris)
    # =========================================================================
    for side in (-1, 1):
        leg_bone  = "Leg_L"  if side > 0 else "Leg_R"
        shin_bone = "Shin_L" if side > 0 else "Shin_R"

        y_hip  = 0.606
        y_knee = 0.402
        y_cuf1 = 0.258  # top edge of turned oilskin pant cuff
        y_cuf0 = 0.208  # crisp bottom hem edge right above brown boots

        def leg_ring(y, xi, xo, rz):
            xa, xb = min(side * xi, side * xo), max(side * xi, side * xo)
            return [
                V(xa, y,  rz),
                V(xb, y,  rz),
                V(xb, y, -rz),
                V(xa, y, -rz),
            ]

        w_hip  = {leg_bone: 1.0}
        w_knee = {leg_bone: 0.5, shin_bone: 0.5}
        w_shin = {shin_bone: 1.0}

        mb.set_part("overalls_legs")
        r_hip  = leg_ring(y_hip,  0.008, 0.214, 0.120)
        r_knee = leg_ring(y_knee, 0.016, 0.226, 0.116)
        r_cuf1 = leg_ring(y_cuf1, 0.020, 0.232, 0.114)
        r_cuf0 = leg_ring(y_cuf0, 0.014, 0.240, 0.120)  # subtle thick flared oilskin cuff!
        mb.loft(
            [r_cuf0, r_cuf1, r_knee, r_hip],
            lambda i, k: OVERALLS_SHADE if (k == 2 or i == 0) else OVERALLS,
            cap_bottom=True, cap_top=False, bot_color=OVERALLS_SHADE,
            ring_weights=[w_shin, w_shin, w_knee, w_hip],
        )

    # =========================================================================
    # 13. CHUNKY SCULPTED BROWN WORK BOOTS WITH TOE VAMP & DARK TREADED SOLES (2 x 26 = 52 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Shin_L" if side > 0 else "Shin_R")
        cx = side * 0.124
        w = 0.078
        w_toe = 0.068
        z_heel = -0.098
        z_inst =  0.072
        z_toe  =  0.184
        y_s0   =  0.000
        y_s1   =  0.038
        y_vamp =  0.106  # rounded chunky toe box height
        y_top  =  0.242  # rises cleanly inside cuffed overall hem for zero walk gap!

        # Thick dark brown treaded outsole (8 sides + 2 bottom cap = 10 tris)
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

        # Sculpted chunky brown boot vamp + ankle shaft (2 loft bands = 16 tris -> rounded toe silhouette!)
        vamp_ring = [
            V(cx - w * 0.96, y_vamp + 0.012, z_heel + 0.008),
            V(cx + w * 0.96, y_vamp + 0.012, z_heel + 0.008),
            V(cx + w_toe * 0.94, y_vamp,     z_toe - 0.018),
            V(cx - w_toe * 0.94, y_vamp,     z_toe - 0.018),
        ]
        boot_top = [
            V(cx - w * 0.92, y_top, z_heel + 0.016),
            V(cx + w * 0.92, y_top, z_heel + 0.016),
            V(cx + w * 0.92, y_top, z_inst),
            V(cx - w * 0.92, y_top, z_inst),
        ]
        mb.loft(
            [sole_top, vamp_ring, boot_top],
            lambda i, k: BOOT_SHADE if (k == 0 or (i == 1 and k == 2)) else BOOT,
            cap_bottom=False, cap_top=False,
        )

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
    """24-frame looping Walk cycle: sturdy sea-legs commercial fisherman stride in heavy boots
    & oilskins, free gloved arm swing, and weighted pendulum lag on the tied lobster buoy!

    Local bone axes (vertical upright bones): +X = left, +Y = up, +Z = forward.
    Right-hand rule around +X:
      +rx rotates +Y (up) -> +Z (forward), -Y (down) -> -Z (backward)
      -rx rotates +Y (up) -> -Z (backward), -Y (down) -> +Z (forward)
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

        # Sturdy grounded walk with slight sea-legs roll and confident forward lean (+rx)
        pb_root = rig.pose.bones["Root"]
        bob = 0.022 * (0.5 - 0.5 * c2) - 0.002
        root_pitch = 0.048
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.055 * s1, 0.038 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotating torso twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.015 * c2, 0.085 * s1, -0.024 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Steady bearded head leveling out the stride
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.042 - 0.026 * s2, -0.034 * s1, 0.015 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Heavy-booted leg stride: Leg_L -rx swings thigh FORWARD (s1 > 0), +rx swings BACKWARD
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.44 * s1 - 0.03, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.018, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        knee_l = 0.04 + 0.38 * max(0.0, math.sin(phi + math.pi - 0.50)) ** 1.35
        pb_shin_l = rig.pose.bones["Shin_L"]
        pb_shin_l.rotation_euler = (knee_l, 0.0, 0.0)
        pb_shin_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.44 * s1 - 0.03, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.018, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        knee_r = 0.04 + 0.38 * max(0.0, math.sin(phi - 0.50)) ** 1.35
        pb_shin_r = rig.pose.bones["Shin_R"]
        pb_shin_r.rotation_euler = (knee_r, 0.0, 0.0)
        pb_shin_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm (+X) swings briskly opposite Leg_L
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.38 * s1, 0.0, 0.04)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.14 + 0.12 * s1, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm (-X) swings naturally opposite Leg_R, staying slightly forward/outward to clear buoy
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.32 * s1 - 0.06, 0.0, -0.05)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.16 - 0.10 * s1, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Tied lobster buoy swings from the back-right shoulder strap knot with weighted pendulum lag!
        buoy_pitch = -0.14 * math.sin(phi - 0.55)
        buoy_roll  = -0.042 * math.sin(2.0 * phi - 0.45) - 0.025
        pb_buoy = rig.pose.bones["Buoy"]
        pb_buoy.rotation_euler = (buoy_pitch, 0.0, buoy_roll)
        pb_buoy.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: seasoned fisherman waiting on the dock, steady breathing,
    scanning the harbor left and right, subtle shoulder weight shift, and gentle buoy sway."""
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

        # Subtle shoulder shift / settle pulse mid-loop
        shift = max(0.0, math.sin(phi - 1.05)) ** 2

        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.006 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (0.008, 0.022 * s1, 0.016 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.018 * s2, 0.026 * s1 - 0.022 * shift, -0.012 * s1 - 0.018 * shift)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Thoughtful harbor scan left & right
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.040 * s2 + 0.020 * shift, 0.25 * s1 - 0.06 * shift, 0.036 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Heavy boots planted squarely on the pier
        for bname in ("Leg_L", "Leg_R", "Shin_L", "Shin_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed gloved arms drifting gently with breathing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.03 + 0.044 * s1, 0.0, 0.028 * s1 + 0.02)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.06 + 0.036 * s2, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.02 - 0.040 * s1 - 0.04 * shift, 0.0, -0.024 * s1 - 0.03)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.08 - 0.034 * s2, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Tied lobster buoy sways gently in the sea breeze & reacts to shoulder shift
        pb_buoy = rig.pose.bones["Buoy"]
        pb_buoy.rotation_euler = (0.048 * math.sin(phi - 0.45) - 0.055 * shift, 0.0, -0.032 * math.cos(phi - 0.30))
        pb_buoy.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 12-bone rig (Root, Torso, Head, Arm/Forearm L/R, Buoy, Leg/Shin L/R)
    with looping Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonFishermanBuoyRig")
    rig = bpy.data.objects.new("PersonFishermanBuoyRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.565,  0.000), ( 0.000, 0.675,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.610,  0.000), ( 0.000, 1.078,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.095,  0.000), ( 0.000, 1.430,  0.000)),
        ("Arm_L",     "Torso", ( 0.184, 0.976,  0.002), ( 0.184, 1.136,  0.002)),
        ("Forearm_L", "Arm_L", ( 0.278, 0.824, -0.010), ( 0.278, 0.964, -0.010)),
        ("Arm_R",     "Torso", (-0.184, 0.976,  0.012), (-0.184, 1.136,  0.012)),
        ("Forearm_R", "Arm_R", (-0.282, 0.824, -0.002), (-0.282, 0.964, -0.002)),
        ("Buoy",      "Torso", (-0.132, 1.072, -0.088), (-0.132, 1.232, -0.088)),
        ("Leg_L",     "Root",  ( 0.118, 0.560,  0.000), ( 0.118, 0.720,  0.000)),
        ("Shin_L",    "Leg_L", ( 0.122, 0.402,  0.000), ( 0.122, 0.542,  0.000)),
        ("Leg_R",     "Root",  (-0.118, 0.560,  0.000), (-0.118, 0.720,  0.000)),
        ("Shin_R",    "Leg_R", (-0.122, 0.402,  0.000), (-0.122, 0.542,  0.000)),
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
        (-1.74, math.radians(56)),   # Front-3/4 matching reference angle
        (-0.58, math.radians(0)),    # Front
        ( 0.58, math.radians(90)),   # Right side (showing lobster buoy & thick coiled rope clearly)
        ( 1.74, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 4.70
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.06)
    direction = Vector((0.0, 0.0, 0.83)) - cam_obj.location
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=56):
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.22
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.3
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.08)
    direction = Vector((0.0, 0.0, 0.83)) - cam_obj.location
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=56, zrot_right_deg=90):
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
    cam_data.ortho_scale = 3.00
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.08)
    direction = Vector((0.0, 0.0, 0.83)) - cam_obj.location
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
            left_obj.location = (-0.68, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.68, 0.0, 0.0)
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

    coll = bpy.data.collections.new("PersonFishermanBuoy")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonFishermanBuoy")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonFishermanBuoy", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=56)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=48)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=56, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)

    print("=== PersonFishermanBuoy Stats ===")
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
