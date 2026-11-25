# Builds an ultra-low-poly (< 350 tris) stylized sporty kid with a backwards beige
# baseball cap, curly dark brown hair, white over-ear headphones around the neck,
# burgundy pullover hoodie, navy gym duffel bag with cream stripes held by the right hand,
# dark charcoal athletic shorts, bare lower legs, and off-white sneakers in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_gym_kid.py)
# Saves art/person_gym_kid.blend, exports assets/models/person_gym_kid.glb (rigged + Walk & Idle cycles),
# renders art/person_gym_kid_preview.png, art/person_gym_kid_walk_preview.png, art/person_gym_kid_idle_preview.png,
# and outputs rendered videos art/person_gym_kid_walk.mp4 and art/person_gym_kid_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.53 m tall (sporty kid scale).
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
BLEND_PATH = os.path.join(ROOT, "art", "person_gym_kid.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_gym_kid.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_gym_kid_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_gym_kid_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_gym_kid_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_gym_kid_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_gym_kid_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette closely matched to reference sporty kid image (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
SKIN           = col_srgb(0.96, 0.72, 0.46)
SKIN_SHADE     = col_srgb(0.86, 0.61, 0.37)
EYE            = col_srgb(0.11, 0.10, 0.11)

HAIR_DARK      = col_srgb(0.32, 0.23, 0.18)
HAIR_MID       = col_srgb(0.41, 0.30, 0.23)
HAIR_SHADE     = col_srgb(0.24, 0.17, 0.13)

CAP            = col_srgb(0.92, 0.87, 0.78)
CAP_SHADE      = col_srgb(0.84, 0.78, 0.69)
CAP_BRIM       = col_srgb(0.89, 0.84, 0.74)
CAP_UNDER      = col_srgb(0.72, 0.66, 0.57)
CAP_STRAP      = col_srgb(0.30, 0.28, 0.28)

HP_MAIN        = col_srgb(0.96, 0.94, 0.90)
HP_SHADE       = col_srgb(0.86, 0.84, 0.79)
HP_PAD         = col_srgb(0.21, 0.21, 0.23)

HOODIE         = col_srgb(0.65, 0.36, 0.34)
HOODIE_SHADE   = col_srgb(0.53, 0.28, 0.27)
HOODIE_HOOD    = col_srgb(0.59, 0.32, 0.30)

BAG            = col_srgb(0.30, 0.37, 0.48)
BAG_SHADE      = col_srgb(0.22, 0.28, 0.38)
BAG_STRIPE     = col_srgb(0.93, 0.88, 0.80)
BAG_STRAP      = col_srgb(0.19, 0.21, 0.26)

SHORTS         = col_srgb(0.25, 0.25, 0.27)
SHORTS_SHADE   = col_srgb(0.17, 0.17, 0.19)

SHOE           = col_srgb(0.95, 0.92, 0.87)
SHOE_VAMP      = col_srgb(0.98, 0.96, 0.92)
SHOE_COLLAR    = col_srgb(0.15, 0.15, 0.17)
SOLE           = col_srgb(0.71, 0.68, 0.64)


# Parts the game recolours per passenger (see art/person_recolor.py).
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR_DARK, HAIR_MID, HAIR_SHADE],
    "top": [HOODIE, HOODIE_SHADE, HOODIE_HOOD],
    "bottom": [SHORTS, SHORTS_SHADE],
    "accent": [CAP, CAP_SHADE, CAP_BRIM, CAP_UNDER],
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

    def curl_cushion(self, base_pt, axis, depth, r_base, r_cap, aspect_y=1.0, phase=0.0,
                     n=5, color=HAIR_DARK, cap_color=HAIR_MID, shade_color=HAIR_SHADE,
                     scallop=0.08, skip_k=()):
        """Chunky beveled curl puff (5-sided = 13 tris, 4-sided = 10 tris or fewer with skip_k)."""
        ax = axis.normalized()
        ref = V(0.0, 1.0, 0.0) if abs(ax.y) < 0.85 else V(0.0, 0.0, 1.0)
        u = ax.cross(ref).normalized()
        v = ax.cross(u).normalized()

        def ring_n(ctr, rad, sc):
            pts = []
            for k in range(n):
                a = phase + 2.0 * math.pi * k / n
                bump = 1.0 + sc * (1.0 if k % 2 == 0 else -0.65)
                pts.append(ctr + u * (rad * bump * math.cos(a)) + v * (rad * aspect_y * bump * math.sin(a)))
            return pts

        r0 = ring_n(base_pt, r_base, scallop)
        r1 = ring_n(base_pt + ax * depth, r_cap, scallop * 0.7)
        c_mid = base_pt + ax * (depth * 0.5)
        for k in range(n):
            if k in skip_k:
                continue
            kn = (k + 1) % n
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if k == n - 1:
                col = shade_color
            elif k % 2 == 0:
                col = cap_color
            else:
                col = color
            self.face([p0, p1, p2, p3], col, out=(mid - c_mid))
        if n == 5:
            self.face([r1[0], r1[1], r1[2], r1[3]], cap_color, out=ax)
            self.face([r1[0], r1[3], r1[4]], color, out=ax)
        elif n == 4:
            self.face(r1, cap_color, out=ax)

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
    # 1. HEAD (6-sided stylized sporty kid head with full upper hair crown tucked into cap = 40 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.042,  0.016, 0.148, 0.138),  # 0: chin/jaw
        (1.114,  0.022, 0.206, 0.192),  # 1: full cheeks
        (1.296,  0.016, 0.205, 0.191),  # 2: brow/forehead hairline
        (1.424, -0.018, 0.160, 0.154),  # 3: full upper skull/hair crown tucked cleanly inside cap!
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks, k=1,2,3 back/nape under curls
    # Band i=2 (brow -> crown) is solid dark hair all the way around so zero hollow space under cap!
    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            if i == 2:
                col = HAIR_MID if k in (4, 5, 0) else HAIR_DARK
            else:
                col = SKIN if k in (4, 5, 0) else HAIR_DARK
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid))
    # Cap chin bottom & crown top so head is 100% solid and watertight from every angle
    rb = head_rings[0]
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[3], rb[4], rb[5], rb[0]], SKIN_SHADE, out=(0, -1, 0))
    rt = head_rings[-1]
    mb.face([rt[0], rt[1], rt[2], rt[3]], HAIR_DARK, out=(0, 1, 0))
    mb.face([rt[3], rt[4], rt[5], rt[0]], HAIR_DARK, out=(0, 1, 0))

    # =========================================================================
    # 2. CUTE LOW-POLY EARS (peeking cleanly beneath curly side hair = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        # Compact soft beveled ear wedge: outer quad (2 tris) + front tri + back tri = 4 tris/ear
        x_in  = side * 0.188
        x_out = side * 0.222
        p_in  = V(x_in,  1.168, 0.024)
        p_tf  = V(x_out, 1.192, 0.044)
        p_tb  = V(x_out, 1.192, 0.004)
        p_bf  = V(x_out, 1.144, 0.040)
        p_bb  = V(x_out, 1.144, 0.008)
        mb.face([p_bf, p_bb, p_tb, p_tf], SKIN,       out=(side, 0, 0))
        mb.face([p_in, p_bf, p_tf],       SKIN,       out=(0, 0, 1))
        mb.face([p_bb, p_in, p_tb],       SKIN_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 3. NECK (4-sided tapered cylinder, skip rear face tucked behind hood/band = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 0.955, 0.010, 0.066, 0.062, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.052, 0.012, 0.062, 0.058, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    # Flat front face z ≈ 0.022 + 0.866025 * 0.192 = 0.1883
    z_eye = 0.192
    for side in (-1, 1):
        cx = side * 0.060
        cy = 1.214
        rx = 0.018
        ry = 0.044
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
    # 5. CURLY DARK BROWN HAIR (nape cloud + scalloped front bangs + temple curls = 34 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # 1. Lush curly nape cloud billowing warmly underneath the backwards cap visor (11 tris)
    mb.curl_cushion(
        base_pt=V(0.0, 1.174, -0.055),
        axis=V(0.0, -0.24, -0.97),
        depth=0.195,
        r_base=0.214,
        r_cap=0.136,
        aspect_y=0.61,
        phase=math.pi / 2.0,
        n=5,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        shade_color=HAIR_SHADE,
        scallop=0.10,
        skip_k=(0,),
    )
    # 2. Soft scalloped 5-sided curly bangs hugging the brow & peeking out the front snapback cutout (13 tris)
    mb.curl_cushion(
        base_pt=V(0.0, 1.320, 0.098),
        axis=V(0.0, 0.22, 0.97),
        depth=0.102,
        r_base=0.176,
        r_cap=0.114,
        aspect_y=0.52,
        phase=math.pi / 2.0,
        n=5,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        shade_color=HAIR_SHADE,
        scallop=0.10,
    )
    # 3 & 4. Sleek rounded temple-to-nape curl cushions tucking snugly above & behind each ear (5 tris x 2 = 10 tris)
    for side in (-1, 1):
        # 3-sided rounded curl wedge bridging temple bangs to nape hair smoothly (no overhang!)
        base_c = V(side * 0.146, 1.242, -0.020)
        ax_c   = V(side * 0.72, -0.18, -0.67).normalized()
        u_c = ax_c.cross(V(0.0, 1.0, 0.0)).normalized()
        v_c = ax_c.cross(u_c).normalized()
        r0 = []
        r1 = []
        for k in range(3):
            a = math.pi / 6.0 + 2.0 * math.pi * k / 3.0
            r0.append(base_c + u_c * (0.114 * math.cos(a)) + v_c * (0.094 * math.sin(a)))
            r1.append(base_c + ax_c * 0.078 + u_c * (0.068 * math.cos(a)) + v_c * (0.056 * math.sin(a)))
        c_mid = base_c + ax_c * 0.039
        for k in range(3):
            if (side > 0 and k == 0) or (side < 0 and k == 2):
                continue
            kn = (k + 1) % 3
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], HAIR_DARK if k == 1 else HAIR_MID, out=(mid - c_mid))
        mb.face([r1[0], r1[1], r1[2]], HAIR_MID, out=ax_c)

    # =========================================================================
    # 6. BACKWARDS BEIGE BASEBALL CAP (crown + front snapback strap + rear brim = 38 tris)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    # Tilted slightly backward around X so front (+Z) sits snugly over curly brow & rear (-Z) hugs nape
    cap_tilt = math.radians(17.0)
    st, ct = math.sin(cap_tilt), math.cos(cap_tilt)
    cap_orig = V(0.0, 1.320, -0.016)

    def cap_ring(h, rx, rz):
        cy = cap_orig.y + h * ct
        cz = cap_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, cap_tilt, n=6, phase=math.pi / 6.0)

    c_r0 = cap_ring(0.000, 0.218, 0.212)  # sweatband rim
    c_r1 = cap_ring(0.112, 0.176, 0.170)  # mid crown dome
    c_r2 = cap_ring(0.184, 0.092, 0.090)  # top panel

    # Lower band (c_r0 -> c_r1): split front panel k=5 into dark snapback strap (bottom) + hair cutout (top)!
    c_mid01 = (sum(c_r0, Vector()) + sum(c_r1, Vector())) / 12.0
    for k in range(6):
        kn = (k + 1) % 6
        p0, p1, p2, p3 = c_r0[k], c_r0[kn], c_r1[kn], c_r1[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        if k == 5:
            # Front snapback opening: compact dark grey strap across bottom + curly hair peeking above
            m_l = p0.lerp(p3, 0.42)
            m_r = p1.lerp(p2, 0.42)
            mb.face([p0, p1, m_r, m_l], CAP_STRAP, out=(mid - c_mid01))
            mb.face([m_l, m_r, p2, p3], HAIR_DARK, out=(mid - c_mid01))
        else:
            col = CAP_SHADE if k in (1, 2, 3) else CAP
            mb.face([p0, p1, p2, p3], col, out=(mid - c_mid01))

    # Upper band (c_r1 -> c_r2) + flat top cap (12 + 4 = 16 tris)
    mb.loft([c_r1, c_r2], lambda i, k: CAP_SHADE if k == 2 else CAP,
            cap_bottom=False, cap_top=True, top_color=CAP)

    # Backwards visor / brim extending cleanly out the BACK (-Z) right above the curly nape cloud (8 tris)
    b_l_in  = c_r0[1].lerp(c_r0[2], 0.35)
    b_c_in  = c_r0[2].lerp(c_r0[3], 0.50)
    b_r_in  = c_r0[4].lerp(c_r0[3], 0.35)
    b_l_out = V( 0.160, 1.186, -0.320)
    b_c_out = V( 0.000, 1.164, -0.386)
    b_r_out = V(-0.160, 1.186, -0.320)
    thick_v = V(0.0, -0.017, 0.0)
    mb.face([b_l_in, b_c_in, b_c_out, b_l_out], CAP_BRIM,  out=(0, 1, -0.25))
    mb.face([b_c_in, b_r_in, b_r_out, b_c_out], CAP_BRIM,  out=(0, 1, -0.25))
    mb.face([b_l_in + thick_v, b_l_out + thick_v, b_c_out + thick_v, b_c_in + thick_v], CAP_UNDER, out=(0, -1, 0.25))
    mb.face([b_c_in + thick_v, b_c_out + thick_v, b_r_out + thick_v, b_r_in + thick_v], CAP_UNDER, out=(0, -1, 0.25))

    # =========================================================================
    # 7. WHITE OVER-EAR HEADPHONES AROUND THE NECK (band 12 + 2 cups 18 = 30 tris)
    # =========================================================================
    mb.set_part("headphones", bone="Torso")
    # Cream headband resting smoothly around back & sides of neck on top of burgundy hoodie collar
    hp_band_pts = [
        V(-0.114, 0.990,  0.098),
        V(-0.118, 1.014, -0.058),
        V( 0.118, 1.014, -0.058),
        V( 0.114, 0.990,  0.098),
    ]
    hp_band_norms = [
        V(-0.62, 0.74,  0.24),
        V(-0.50, 0.74, -0.45),
        V( 0.50, 0.74, -0.45),
        V( 0.62, 0.74,  0.24),
    ]
    mb.tri_strap(
        hp_band_pts, hp_band_norms,
        half_w=0.026, thick=0.024,
        colors=lambda i, k: HP_MAIN if k == 0 else HP_SHADE,
        skip_k=(2,),
    )

    # Two chunky 5-sided white earcups with dark inner cushions resting right on the upper front collarbones!
    for side in (-1, 1):
        cup_base = V(side * 0.064, 0.968, 0.116)
        cup_axis = V(side * 0.66, -0.06, 0.75).normalized()
        u_c = cup_axis.cross(V(0.0, 1.0, 0.0)).normalized()
        v_c = cup_axis.cross(u_c).normalized()
        r_pad = 0.066
        r_out = 0.058
        r0 = []
        r1 = []
        for k in range(5):
            a = math.pi / 10.0 + 2.0 * math.pi * k / 5.0
            ca, sa = math.cos(a), math.sin(a)
            r0.append(cup_base + u_c * (r_pad * ca) + v_c * (r_pad * sa))
            r1.append(cup_base + cup_axis * 0.054 + u_c * (r_out * ca) + v_c * (r_out * sa))
        c_mid = cup_base + cup_axis * 0.027
        # Skip 2 bottom/chest-buried side quads (k=2, 3) -> 3 visible side quads + 3-tri white shell cap = 9 tris/cup!
        # Dark cushion pad contrasts crisply on medial/top rim while cream white cap faces outward!
        for k in range(5):
            if k in (2, 3):
                continue
            kn = (k + 1) % 5
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            col = HP_PAD if k in (0, 4) else HP_SHADE
            mb.face([p0, p1, p2, p3], col, out=(mid - c_mid))
        mb.face([r1[0], r1[1], r1[2], r1[3]], HP_MAIN, out=cup_axis)
        mb.face([r1[0], r1[3], r1[4]], HP_MAIN, out=cup_axis)

    # =========================================================================
    # 8. BURGUNDY PULLOVER HOODIE TORSO + FOLDED HOOD (16 + 8 = 24 tris)
    # =========================================================================
    mb.set_part("hoodie", bone="Torso")
    # 6-sided relaxed hoodie torso (skip bottom cap plugged directly by shorts pelvis)
    t_bot = oval_ring(0.0, 0.548, 0.006, 0.210, 0.146, n=6, phase=math.pi / 6.0)
    t_top = oval_ring(0.0, 0.968, 0.004, 0.186, 0.132, n=6, phase=math.pi / 6.0)
    mb.loft(
        [t_bot, t_top],
        lambda i, k: HOODIE_SHADE if k in (1, 2, 3) else HOODIE,
        cap_bottom=False, cap_top=True, top_color=HOODIE,
    )

    # Folded maroon hood draped cozily behind the neck under the backwards cap brim (8 tris)
    hd_bot = [
        V(-0.130, 0.945,  0.030),
        V( 0.130, 0.945,  0.030),
        V( 0.158, 0.935, -0.205),
        V(-0.158, 0.935, -0.205),
    ]
    hd_top = [
        V(-0.108, 1.018,  0.015),
        V( 0.108, 1.018,  0.015),
        V( 0.136, 1.045, -0.175),
        V(-0.136, 1.045, -0.175),
    ]
    mb.loft([hd_bot, hd_top], HOODIE_HOOD, cap_bottom=False, cap_top=True, top_color=HOODIE, skip_k=(0,))

    # =========================================================================
    # 9. HOODIE SLEEVES & HANDS (32 + 20 = 52 tris)
    #    - Left arm (+X): relaxed swing at side with warm hand peeking below cuff
    #    - Right arm (-X): bent forward & up so chunky hand grips gym bag shoulder strap!
    # =========================================================================
    def build_arm_and_hand(p_sh, p_el, p_wr, hand_len, arm_bone, fore_bone, rx_scale=1.0):
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

        r_sh = ring4(p_sh, ax1,    0.058 * rx_scale, 0.064 * rx_scale)
        r_el = ring4(p_el, ax_mid, 0.068 * rx_scale, 0.072 * rx_scale)
        r_wr = ring4(p_wr, ax2,    0.054 * rx_scale, 0.058 * rx_scale)

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

        # Chunky warm-tan hand peeking from wrist cuff (10 tris)
        mb.set_part("hands", bone=fore_bone)
        r_h0 = ring4(p_wr, ax2, 0.046, 0.048)
        r_h1 = ring4(p_wr + ax2 * hand_len, ax2, 0.036, 0.038)
        mb.loft([r_h0, r_h1], lambda i, k: SKIN_SHADE if k in (2, 3) else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # Left arm (+X, free swinging)
    p_l_sh = V( 0.168, 0.896,  0.002)
    p_l_el = V( 0.236, 0.740, -0.016)
    p_l_wr = V( 0.232, 0.606,  0.042)
    build_arm_and_hand(p_l_sh, p_l_el, p_l_wr, hand_len=0.092, arm_bone="Arm_L", fore_bone="Forearm_L")

    # Right arm (-X, bent forward & holding dark gym bag shoulder strap cleanly!)
    p_r_sh = V(-0.168, 0.896, -0.006)
    p_r_el = V(-0.246, 0.752, -0.064)
    p_r_wr = V(-0.240, 0.692,  0.068)
    build_arm_and_hand(p_r_sh, p_r_el, p_r_wr, hand_len=0.094, arm_bone="Arm_R", fore_bone="Forearm_R")

    # =========================================================================
    # 10. NAVY GYM DUFFEL BAG + CREAM STRIPES + DARK SHOULDER STRAP (32 + 18 = 50 tris)
    # =========================================================================
    mb.set_part("gym_bag", bone="Bag")
    # Hanging beside right hip (-X), tilted ~16 deg nose-down toward +Z with clean leg clearance!
    bag_tilt = math.radians(-16.0)
    bct, bst = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_orig = V(-0.304, 0.468, -0.105)

    def bag_pt(lx, ly, lz):
        # Local +Z runs along bag length toward front; negative tilt lowers +Z front & raises -Z rear!
        ry = ly * bct + lz * bst
        rz = -ly * bst + lz * bct
        return V(bag_orig.x + lx, bag_orig.y + ry, bag_orig.z + rz)

    def bag_ring(lz, rx, ry):
        # 6-sided horizontal barrel cross-section in local (lx, ly)
        pts = []
        for k in range(6):
            a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
            lx = -rx * math.cos(a)  # -X is outer
            ly =  ry * math.sin(a)
            pts.append(bag_pt(lx, ly, lz))
        return pts

    half_len = 0.228
    b_back = bag_ring(-half_len, 0.088, 0.108)
    b_front = bag_ring( half_len, 0.088, 0.108)
    mb.loft(
        [b_back, b_front],
        lambda i, k: BAG_SHADE if k in (2, 3, 4) else BAG,
        cap_bottom=True, cap_top=True,
        bot_color=BAG_SHADE, top_color=BAG_SHADE,
    )

    # Two crisp cream athletic webbing stripes wrapping around outer/top/bottom of duffel (12 tris)
    for cz_s in (-0.110, 0.102):
        sr0 = bag_ring(cz_s - 0.028, 0.093, 0.113)
        sr1 = bag_ring(cz_s + 0.028, 0.093, 0.113)
        mb.loft([sr0, sr1], BAG_STRIPE, cap_bottom=False, cap_top=False, skip_k=(1, 2, 3))

    # Dark charcoal shoulder strap looping from duffel ends up over right shoulder & through right gripping hand!
    mb.set_part("bag_strap", bone="Bag")
    strap_pts = [
        bag_pt(-0.012, 0.098, -0.185),   # 0: rear top duffel attachment
        V(-0.200, 0.978, -0.008),        # 1: right hoodie shoulder crest
        V(-0.238, 0.690,  0.112),        # 2: passes right through right gripping hand!
        bag_pt(-0.012, 0.098,  0.188),   # 3: front top duffel attachment
    ]
    strap_norms = [
        V(-0.82, 0.35, -0.45),
        V(-0.32, 0.94,  0.04),
        V(-0.84, 0.15,  0.52),
        V(-0.85, 0.25,  0.46),
    ]
    mb.tri_strap(strap_pts, strap_norms, half_w=0.026, thick=0.016, colors=BAG_STRAP)

    # =========================================================================
    # 11. DARK CHARCOAL ATHLETIC SHORTS + BARE LOWER LEGS (20 + 16 = 36 tris)
    # =========================================================================
    mb.set_part("shorts", bone="Root")
    # Skip left/right faces enclosed inside upper short legs & hoodie hem (saves 4 tris, zero visible seam)
    mb.box(-0.172, 0.172, 0.470, 0.578, -0.098, 0.098, SHORTS, skip=("top", "bottom", "left", "right"))

    for side in (-1, 1):
        leg_bone = "Leg_L" if side > 0 else "Leg_R"
        shin_bone = "Shin_L" if side > 0 else "Shin_R"

        y_hip   = 0.562
        y_short = 0.345  # relaxed athletic shorts hem right at knee hinge
        y_ank   = 0.102  # tucked cleanly into sneaker collar

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

        # Loose dark charcoal gym shorts legs (8 tris/leg)
        mb.set_part("shorts")
        r_hip   = leg_ring(y_hip,   0.006, 0.172, 0.094)
        r_short = leg_ring(y_short, 0.026, 0.192, 0.094)
        mb.loft([r_short, r_hip], lambda i, k: SHORTS_SHADE if k == 2 else SHORTS,
                cap_bottom=False, cap_top=False, ring_weights=[w_knee, w_hip])

        # Bare warm-tan knees & lower legs down to sneakers (8 tris/leg)
        mb.set_part("bare_legs")
        r_bare_top = leg_ring(y_short + 0.015, 0.050, 0.164, 0.064)
        r_bare_bot = leg_ring(y_ank,           0.064, 0.158, 0.050)
        mb.loft([r_bare_bot, r_bare_top], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=False, ring_weights=[w_shin, w_knee])

    # =========================================================================
    # 12. CHUNKY OFF-WHITE SNEAKERS WITH GREY OUTSOLES & DARK COLLAR TRIM (20 x 2 = 40 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Shin_L" if side > 0 else "Shin_R")
        cx = side * 0.112
        w = 0.062
        w_toe = 0.050
        z_heel = -0.088
        z_mid  =  0.058
        z_toe  =  0.164
        y_s0   =  0.000
        y_s1   =  0.028
        y_col  =  0.118

        # Grey-taupe rubber outsole (4 sides + bottom cap = 10 tris)
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

        # Off-white chunky sneaker upper + crisp dark ankle collar rim peeking around bare ankle (8 + 2 = 10 tris)
        shoe_top = [
            V(cx - w * 0.94, y_col, z_heel + 0.018),
            V(cx + w * 0.94, y_col, z_heel + 0.018),
            V(cx + w * 0.94, y_col, z_mid),
            V(cx - w * 0.94, y_col, z_mid),
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
    """24-frame looping Walk cycle: upbeat sporty kid stride with smooth knee bend,
    free left-arm swing, right hand steady on the gym bag strap, and weighted duffel pendulum sway!

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

        # Upbeat bouncy sporty walk (two bounces per stride) + slight energetic forward lean (+rx)
        pb_root = rig.pose.bones["Root"]
        bob = 0.025 * (0.5 - 0.5 * c2) - 0.002
        root_pitch = 0.055
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.062 * s1, 0.032 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotating torso twist (slightly damped on right side to balance duffel weight)
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.016 * c2, 0.095 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Head stays level & alert with a cheerful rhythmic bob
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.050 - 0.034 * s2, -0.040 * s1, 0.018 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sporty kid walk stride: Leg_L -rx swings thigh FORWARD (s1 > 0), +rx swings BACKWARD (s1 < 0)
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.48 * s1 - 0.04, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.018, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        knee_l = 0.05 + 0.44 * max(0.0, math.sin(phi + math.pi - 0.50)) ** 1.35
        pb_shin_l = rig.pose.bones["Shin_L"]
        pb_shin_l.rotation_euler = (knee_l, 0.0, 0.0)
        pb_shin_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.48 * s1 - 0.04, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.018, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        knee_r = 0.05 + 0.44 * max(0.0, math.sin(phi - 0.50)) ** 1.35
        pb_shin_r = rig.pose.bones["Shin_R"]
        pb_shin_r.rotation_euler = (knee_r, 0.0, 0.0)
        pb_shin_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm (+X) swings freely opposite Leg_L
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.42 * s1, 0.0, 0.03)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.16 + 0.14 * s1, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gym bag swings gently from the right shoulder crest with weighted pendulum lag
        bag_swing = -0.10 * math.sin(phi - 0.45)
        bag_roll  = -0.026 * math.sin(2.0 * phi - 0.50) - 0.025
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (bag_swing, 0.0, bag_roll)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm (-X) holds steady on the gym bag strap, moving sympathetically with bag_swing!
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (bag_swing * 0.85, 0.0, -0.02)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (0.04 * math.sin(2.0 * phi - 0.35), 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: relaxed kid waiting at the dock, subtle weight shift,
    curious look-around & rhythmic head bop, plus gentle gym bag strap heft."""
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

        # Mid-loop smooth bag-strap heft pulse
        heft = max(0.0, math.sin(phi - 1.10)) ** 2

        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.007 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (0.010, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (0.016 * s2, 0.028 * s1 - 0.030 * heft, -0.014 * s1 - 0.022 * heft)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious look-around & upbeat sporty head bob
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.055 * s2 + 0.032 * heft, 0.28 * s1 - 0.08 * heft, 0.048 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sneakers planted squarely on the ground
        for bname in ("Leg_L", "Leg_R", "Shin_L", "Shin_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Left arm rests comfortably at side with gentle breathing sway
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.03 + 0.048 * s1, 0.0, 0.030 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_l = rig.pose.bones["Forearm_L"]
        pb_fore_l.rotation_euler = (-0.05 + 0.042 * s2, 0.0, 0.0)
        pb_fore_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gym bag hangs gently, lifting noticeably on the strap-heft pulse
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.location = (0.0, 0.022 * heft, 0.0)
        pb_bag.rotation_euler = (0.042 * math.sin(phi - 0.40) - 0.085 * heft, 0.0, -0.035 * heft)
        pb_bag.keyframe_insert(data_path="location", frame=frame)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm stays gripping strap and lifts naturally during heft pulse
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.032 * math.sin(phi - 0.40) - 0.115 * heft, 0.0, -0.026 * heft)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_fore_r = rig.pose.bones["Forearm_R"]
        pb_fore_r.rotation_euler = (-0.090 * heft, 0.0, 0.0)
        pb_fore_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 12-bone rig (Root, Torso, Head, Arm/Forearm L/R, Bag, Leg/Shin L/R)
    with looping Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonGymKidRig")
    rig = bpy.data.objects.new("PersonGymKidRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.525,  0.000), ( 0.000, 0.625,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.570,  0.000), ( 0.000, 0.975,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.005,  0.000), ( 0.000, 1.325,  0.000)),
        ("Arm_L",     "Torso", ( 0.168, 0.896,  0.002), ( 0.168, 1.056,  0.002)),
        ("Forearm_L", "Arm_L", ( 0.236, 0.740, -0.016), ( 0.236, 0.880, -0.016)),
        ("Arm_R",     "Torso", (-0.168, 0.896, -0.006), (-0.168, 1.056, -0.006)),
        ("Forearm_R", "Arm_R", (-0.244, 0.752, -0.068), (-0.244, 0.892, -0.068)),
        ("Bag",       "Torso", (-0.200, 0.978, -0.008), (-0.200, 1.138, -0.008)),
        ("Leg_L",     "Root",  ( 0.104, 0.515,  0.000), ( 0.104, 0.675,  0.000)),
        ("Shin_L",    "Leg_L", ( 0.110, 0.355,  0.000), ( 0.110, 0.495,  0.000)),
        ("Leg_R",     "Root",  (-0.104, 0.515,  0.000), (-0.104, 0.675,  0.000)),
        ("Shin_R",    "Leg_R", (-0.110, 0.355,  0.000), (-0.110, 0.495,  0.000)),
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
        (-1.68, math.radians(62)),   # Front-3/4 matching reference angle
        (-0.56, math.radians(0)),    # Front
        ( 0.56, math.radians(90)),   # Right side (showing backwards cap, gym bag, arm grip)
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
    cam_data.ortho_scale = 4.5
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.02)
    direction = Vector((0.0, 0.0, 0.78)) - cam_obj.location
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
    cam_data.ortho_scale = 7.0
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.05)
    direction = Vector((0.0, 0.0, 0.78)) - cam_obj.location
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
    cam_data.ortho_scale = 2.80
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 1.02)
    direction = Vector((0.0, 0.0, 0.78)) - cam_obj.location
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
            left_obj.location = (-0.64, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.64, 0.0, 0.0)
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

    coll = bpy.data.collections.new("PersonGymKid")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonGymKid")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonGymKid", me)
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
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=48)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=58, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)

    print("=== PersonGymKid Stats ===")
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
