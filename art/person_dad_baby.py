# Builds an ultra-low-poly (< 450 tris) stylized dad with olive baseball cap, dark full beard,
# painted warm-tan/olive plaid flannel shirt, dark charcoal backpack, baby in slate-blue front
# carrier (with oatmeal knit beanie, olive sleeves & cream booties), olive-khaki cargo pants,
# and chunky brown work boots in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_dad_baby.py)
# Saves art/person_dad_baby.blend, exports assets/models/person_dad_baby.glb (rigged + Walk & Idle cycles + embedded texture),
# renders art/person_dad_baby_preview.png, art/person_dad_baby_walk_preview.png, art/person_dad_baby_idle_preview.png,
# and outputs rendered videos art/person_dad_baby_walk.mp4 and art/person_dad_baby_idle.mp4.
#
# Strict triangle budget: < 450 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.71 m tall.
# Blender frame: -Y forward, +Z up via G(x, y, z) = (x, -z, y).

import math
import os
import subprocess
import sys
import tempfile
import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BLEND_PATH = os.path.join(ROOT, "art", "person_dad_baby.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_dad_baby.glb")
SHIRT_TEX_PATH = os.path.join(ROOT, "art", "person_dad_baby_shirt_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_dad_baby_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_dad_baby_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_dad_baby_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_dad_baby_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_dad_baby_idle.mp4")

MAT_VCOL = 0
MAT_SHIRT = 1


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (every colour made with col_srgb, unique per part)
TEX_WHITE        = col_srgb(1.00, 1.00, 1.00)

SKIN             = col_srgb(0.96, 0.75, 0.53)
SKIN_SHADE       = col_srgb(0.85, 0.63, 0.42)
BABY_SKIN        = col_srgb(0.99, 0.80, 0.60)
BABY_SKIN_SHADE  = col_srgb(0.89, 0.69, 0.49)
EYE              = col_srgb(0.11, 0.10, 0.10)

HAIR_DARK        = col_srgb(0.35, 0.27, 0.22)
BEARD            = col_srgb(0.37, 0.29, 0.24)
BEARD_DARK       = col_srgb(0.28, 0.21, 0.17)
MUSTACHE         = col_srgb(0.33, 0.25, 0.20)
BABY_HAIR        = col_srgb(0.45, 0.31, 0.22)

CAP_CROWN        = col_srgb(0.57, 0.58, 0.44)
CAP_TOP          = col_srgb(0.62, 0.63, 0.49)
CAP_BRIM         = col_srgb(0.52, 0.53, 0.39)
CAP_UNDER        = col_srgb(0.38, 0.39, 0.28)

PACK             = col_srgb(0.29, 0.29, 0.31)
PACK_SHADE       = col_srgb(0.21, 0.21, 0.23)
PACK_POCKET      = col_srgb(0.35, 0.35, 0.37)

CARRIER          = col_srgb(0.42, 0.49, 0.58)
CARRIER_SHADE    = col_srgb(0.33, 0.39, 0.47)
CARRIER_TRIM     = col_srgb(0.48, 0.56, 0.65)
CARRIER_STRAP    = col_srgb(0.33, 0.37, 0.43)
CARRIER_BELT     = col_srgb(0.28, 0.30, 0.35)

BABY_BEANIE      = col_srgb(0.87, 0.77, 0.62)
BABY_BEANIE_CUFF = col_srgb(0.81, 0.70, 0.54)
BABY_BEANIE_TOP  = col_srgb(0.91, 0.82, 0.67)

BABY_SLEEVE      = col_srgb(0.55, 0.59, 0.38)
BABY_SLEEVE_SH   = col_srgb(0.44, 0.48, 0.30)

BABY_SHOE        = col_srgb(0.96, 0.92, 0.86)
BABY_SHOE_SHADE  = col_srgb(0.87, 0.82, 0.75)
BABY_SHOE_SOLE   = col_srgb(0.76, 0.71, 0.64)

PANTS            = col_srgb(0.59, 0.56, 0.40)
PANTS_SHADE      = col_srgb(0.48, 0.45, 0.31)
PANTS_LIGHT      = col_srgb(0.65, 0.62, 0.45)
PANTS_INNER      = col_srgb(0.36, 0.34, 0.23)

BOOT             = col_srgb(0.53, 0.38, 0.27)
BOOT_SHADE       = col_srgb(0.41, 0.29, 0.20)
SOLE             = col_srgb(0.28, 0.22, 0.18)

# Parts the game recolours per passenger (see art/person_recolor.py).
# Textured plaid flannel shirt, eyes, shoes, backpack, and baby carrier/outfit stay fixed.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE, BABY_SKIN, BABY_SKIN_SHADE],
    "hair": [HAIR_DARK, BEARD, BEARD_DARK, MUSTACHE, BABY_HAIR],
    "bottom": [PANTS, PANTS_SHADE, PANTS_LIGHT, PANTS_INNER],
    "accent": [CAP_CROWN, CAP_TOP, CAP_BRIM, CAP_UNDER],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared structural anchors for rig & geometry alignment
SHOULDER_Y = 1.078
SHOULDER_Z = 0.002
BABY_NECK = V(0.000, 0.962, 0.248)


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def _plaid_pattern(uu, vv, freq_u, freq_v):
    """Generate warm golden-tan / olive-khaki / dark-olive-brown plaid flannel pattern matched to reference."""
    pu = (uu * freq_u) % 1.0
    pv = (vv * freq_v) % 1.0

    # Base warm biscuit-tan / ochre flannel squares
    col = np.zeros(uu.shape + (3,), dtype=np.float32)
    col[..., 0] = 0.78
    col[..., 1] = 0.62
    col[..., 2] = 0.40

    # Broad warm olive-taupe bands occupying [0.22..0.78] in each repeat
    u_med = np.clip((pu - 0.20) * 32.0, 0.0, 1.0) * np.clip((0.80 - pu) * 32.0, 0.0, 1.0)
    v_med = np.clip((pv - 0.20) * 32.0, 0.0, 1.0) * np.clip((0.80 - pv) * 32.0, 0.0, 1.0)

    # Dark olive-brown core stripes occupying [0.36..0.64]
    u_dark = np.clip((pu - 0.35) * 42.0, 0.0, 1.0) * np.clip((0.65 - pu) * 42.0, 0.0, 1.0)
    v_dark = np.clip((pv - 0.35) * 42.0, 0.0, 1.0) * np.clip((0.65 - pv) * 42.0, 0.0, 1.0)

    # Subtle overcheck pinstripes centered on the golden-tan squares
    u_pin = np.clip((0.028 - np.minimum(pu, 1.0 - pu)) * 60.0, 0.0, 1.0)
    v_pin = np.clip((0.028 - np.minimum(pv, 1.0 - pv)) * 60.0, 0.0, 1.0)

    # Layer medium olive-khaki warp & weft
    med_blend = np.clip(0.50 * u_med + 0.50 * v_med - 0.14 * u_med * v_med, 0.0, 1.0)
    col = _blend_mask(col, med_blend, (0.50, 0.44, 0.29))

    # Layer dark olive-charcoal bands and deeper cross intersections
    dark_single = np.clip(np.maximum(u_dark, v_dark), 0.0, 1.0)
    dark_cross = u_dark * v_dark
    col = _blend_mask(col, dark_single * 0.72, (0.32, 0.29, 0.21))
    col = _blend_mask(col, dark_cross * 0.82, (0.21, 0.19, 0.14))

    # Subtle dark overcheck on tan squares
    pin = np.maximum(u_pin, v_pin) * (1.0 - dark_single)
    col = _blend_mask(col, pin * 0.36, (0.37, 0.31, 0.22))

    # Soft flannel twill micro-texture
    twill = 1.0 + 0.016 * np.sin((uu * 210.0 + vv * 210.0))
    col *= twill[..., None]
    return np.clip(col, 0.0, 1.0)


def generate_shirt_texture(out_path):
    """Paint a 512x512 sRGB flannel texture:
       - Top region (v in [0.34, 1.00]): Full plaid flannel torso with center button placket & buttons
         and gentle top-to-bottom shading.
       - Bottom strip (v in [0.00, 0.34]): Matching plaid flannel sleeves & collar with olive-brown wrist cuff.
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # 1. Torso plaid (v in [0.34, 1.00])
    # Wide front k=5 spans u in [0.00, 0.34] (center front = u = 0.17)
    torso_img = _plaid_pattern(uu + 0.04, vv, freq_u=11.0, freq_v=5.8)
    torso_v = np.clip((vv - 0.34) / 0.66, 0.0, 1.0)
    torso_img *= (0.91 + 0.11 * torso_v)[..., None]

    # Subtle vertical front button placket line at u = 0.170
    placket_bg = np.clip((0.016 - np.abs(uu - 0.170)) / 0.003, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, placket_bg * 0.22, (0.35, 0.30, 0.21))
    placket_line = np.clip((0.004 - np.abs(uu - 0.170)) / 0.002, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, placket_line * 0.45, (0.20, 0.18, 0.14))
    for bv in (0.42, 0.56, 0.72, 0.88):
        bd = np.sqrt(((uu - 0.170) / 0.0065) ** 2 + ((vv - bv) / 0.011) ** 2)
        torso_img = _blend_mask(torso_img, np.clip((1.0 - bd) * 5.0, 0.0, 1.0), (0.28, 0.24, 0.18))

    # Subtle lower hem stitching near v = 0.355
    hem_seam = np.clip((0.006 - np.abs(vv - 0.360)) / 0.003, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, hem_seam * 0.38, (0.24, 0.21, 0.16))

    # 2. Sleeve & collar strip (v in [0.00, 0.34])
    # Bold chunky checks (~4 checks around arm, ~3.5 down arm length matching reference!)
    sleeve_img = _plaid_pattern(uu + 0.05, vv, freq_u=4.0, freq_v=10.5)
    slv_t = np.clip(vv / 0.34, 0.0, 1.0)
    sleeve_img *= (0.92 + 0.10 * slv_t)[..., None]

    # Crisp slightly darker olive-tan cuff hem at wrist edge (v in [0.00, 0.048])
    cuff_m = np.clip((0.048 - vv) / 0.006, 0.0, 1.0)
    sleeve_img = _blend_mask(sleeve_img, cuff_m * 0.72, (0.42, 0.36, 0.25))
    cuff_seam = np.clip((0.006 - np.abs(vv - 0.050)) / 0.003, 0.0, 1.0)
    sleeve_img = _blend_mask(sleeve_img, cuff_seam * 0.52, (0.22, 0.19, 0.14))

    in_torso = (vv >= 0.340).astype(np.float32)
    img = sleeve_img * (1.0 - in_torso[..., None]) + torso_img * in_torso[..., None]
    img = np.clip(img, 0.0, 1.0)

    bimg = bpy.data.images.new("DadFlannelTex", width=w, height=h, alpha=True, float_buffer=False)
    bimg.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = img
    bimg.pixels.foreach_set(rgba.ravel())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bimg.filepath_raw = out_path
    bimg.file_format = "PNG"
    bimg.save()
    bimg.pack()
    return bimg


class MeshBuilder:
    def __init__(self):
        self.bm = bmesh.new()
        self.cl = self.bm.loops.layers.color.new("Col")
        self.uvl = self.bm.loops.layers.uv.new("UVMap")
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

    def face(self, pts, color, out=None, weights=None, mat_idx=MAT_VCOL, uvs=None):
        pts = [Vector(p) for p in pts]
        if len(pts) < 3:
            return None
        if uvs is not None:
            uvs = list(uvs)
        if out is not None:
            out_v = Vector(out)
            n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if n.length < 1e-12 and len(pts) > 3:
                n = (pts[2] - pts[0]).cross(pts[3] - pts[0])
            if n.dot(out_v) < 0:
                pts.reverse()
                if weights is not None:
                    weights = list(reversed(weights))
                if uvs is not None:
                    uvs.reverse()
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
        f.material_index = mat_idx
        vcol = TEX_WHITE if mat_idx != MAT_VCOL else color
        for idx, loop in enumerate(f.loops):
            loop[self.cl] = vcol
            if uvs is not None:
                loop[self.uvl].uv = uvs[idx]
            else:
                loop[self.uvl].uv = (0.0, 0.0)
        self.part_tris[self.current_part] = self.part_tris.get(self.current_part, 0) + (len(pts) - 2)
        return f

    def loft(self, rings, colors, cap_bottom=False, cap_top=False,
             bot_color=None, top_color=None, skip_k=(), ring_weights=None,
             mat_idx=MAT_VCOL, uv_fn=None):
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
                uvs = uv_fn(i, k) if uv_fn is not None else None
                self.face([p0, p1, p2, p3], col, out=(mid - cmid), weights=fw, mat_idx=mat_idx, uvs=uvs)
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            wb = ring_weights[0] if ring_weights is not None else None
            if n <= 4:
                self.face(r0, col, out=out_dir, weights=([wb] * n if wb else None))
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb else None))
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=([wb] * 4 if wb else None))
            elif n == 8:
                self.face([r0[7], r0[0], r0[1], r0[2]], col, out=out_dir, weights=([wb] * 4 if wb else None))
                self.face([r0[7], r0[2], r0[3], r0[6]], col, out=out_dir, weights=([wb] * 4 if wb else None))
                self.face([r0[6], r0[3], r0[4], r0[5]], col, out=out_dir, weights=([wb] * 4 if wb else None))
            else:
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=([wb] * 3 if wb else None))
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt = ring_weights[-1] if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([wt] * n if wt else None))
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt else None))
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=([wt] * 4 if wt else None))
            elif n == 8:
                self.face([rt[7], rt[0], rt[1], rt[2]], col, out=out_dir, weights=([wt] * 4 if wt else None))
                self.face([rt[7], rt[2], rt[3], rt[6]], col, out=out_dir, weights=([wt] * 4 if wt else None))
                self.face([rt[6], rt[3], rt[4], rt[5]], col, out=out_dir, weights=([wt] * 4 if wt else None))
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=([wt] * 3 if wt else None))

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


def wide_hex_ring(cx, cy, cz, rx, rz, front_w=0.76, sh_drop=0.0):
    """6-sided ring with broad flat front (k=5) and back (k=2) faces for crisp flannel plaid mapping."""
    zf = rz * 0.88
    yo = cy - sh_drop
    return [
        V(cx + rx * front_w, cy, cz + zf),   # 0: front-left
        V(cx + rx,           yo, cz),        # 1: left
        V(cx + rx * front_w, cy, cz - zf),   # 2: back-left
        V(cx - rx * front_w, cy, cz - zf),   # 3: back-right
        V(cx - rx,           yo, cz),        # 4: right
        V(cx - rx * front_w, cy, cz + zf),   # 5: front-right
    ]


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=8, phase=math.pi / 8.0):
    """Ring tilted around X by tilt_rad (+tilt raises +Z front, lowers -Z back)."""
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


def ortho_basis(axis, hint=V(1.0, 0.0, 0.0)):
    ax = axis.normalized()
    u = hint - ax * hint.dot(ax)
    if u.length < 1e-5:
        hint = V(0.0, 0.0, 1.0)
        u = hint - ax * hint.dot(ax)
    u = u.normalized()
    v = ax.cross(u).normalized()
    return ax, u, v


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. DAD HEAD + FULL DARK BEARD (6-sided, 3 rings + front chin cap = 26 tris)
    # =========================================================================
    mb.set_part("dad_head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.196,  0.020, 0.166, 0.162),  # 0: full bearded chin/jaw
        (1.312,  0.020, 0.214, 0.204),  # 1: cheek / upper beard line
        (1.494,  0.008, 0.208, 0.198),  # 2: forehead / tucked cleanly inside olive cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        if i == 0:
            # Lower face: full dark espresso beard across front/cheeks, dark hair at nape
            return BEARD if k in (4, 5, 0) else HAIR_DARK
        # Upper face: warm peach skin on front/cheeks, dark brown hair behind ears/back
        return SKIN if k in (4, 5, 0) else HAIR_DARK

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)
    # Front bearded chin underside cap (rear is above neck = 2 tris)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], BEARD_DARK, out=(0, -1, 0))

    # =========================================================================
    # 2. DAD SCULPTED MUSTACHE (2 curved dark wings = 8 tris)
    # =========================================================================
    mb.set_part("dad_mustache", bone="Head")
    p_ct_t = V(0.000, 1.326, 0.230)
    p_ct_b = V(0.000, 1.278, 0.226)
    p_cb_t = V(0.000, 1.322, 0.194)
    p_cb_b = V(0.000, 1.272, 0.190)
    for side in (-1, 1):
        p_out_f = V(side * 0.104, 1.284, 0.208)
        p_out_b = V(side * 0.114, 1.282, 0.172)
        mb.face([p_ct_b, p_out_f, p_out_b, p_ct_t], MUSTACHE,   out=(side * 0.2, 0.1, 1.0))
        mb.face([p_ct_t, p_out_b, p_cb_t],          BEARD,      out=(0, 1, 0.2))
        mb.face([p_ct_b, p_cb_b, p_out_f],          BEARD_DARK, out=(0, -1, 0.1))

    # =========================================================================
    # 3. DAD EARS (2 chunky peach wedges = 8 tris)
    # =========================================================================
    mb.set_part("dad_ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.198
        x_out = side * 0.242
        y0, y1 = 1.304, 1.388
        z0, z1 = 0.004, 0.072
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_tip], SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. DAD EYES (2 vertical dark pill hexagons flush on front face = 8 tris)
    # =========================================================================
    mb.set_part("dad_eyes", bone="Head")
    z_eye = 0.200
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.390
        rx = 0.019
        ry = 0.045
        pts = [
            V(cx,      cy + ry,        z_eye),
            V(cx + rx, cy + ry * 0.56, z_eye),
            V(cx + rx, cy - ry * 0.56, z_eye),
            V(cx,      cy - ry,        z_eye),
            V(cx - rx, cy - ry * 0.56, z_eye),
            V(cx - rx, cy + ry * 0.56, z_eye),
        ]
        mb.face([pts[5], pts[0], pts[1], pts[2]], EYE, out=(0, 0, 1))
        mb.face([pts[5], pts[2], pts[3], pts[4]], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. OLIVE-GREEN BASEBALL CAP + CURVED VISOR (8-sided crown + visor = 52 tris)
    # =========================================================================
    mb.set_part("dad_cap", bone="Head")
    cap_tilt = math.radians(11.5)
    c_rim = tilted_ring(0.0, 1.474, -0.008, 0.238, 0.248, cap_tilt, n=8, phase=math.pi / 8.0)
    c_mid = tilted_ring(0.0, 1.610, -0.004, 0.224, 0.232, cap_tilt * 0.72, n=8, phase=math.pi / 8.0)
    c_top = tilted_ring(0.0, 1.718, -0.012, 0.116, 0.120, cap_tilt * 0.40, n=8, phase=math.pi / 8.0)
    mb.loft([c_rim, c_mid, c_top], CAP_CROWN, cap_bottom=False, cap_top=True, top_color=CAP_TOP)

    v_back_t = [
        V(-0.202, 1.508, 0.128),
        V(-0.104, 1.532, 0.222),
        V( 0.104, 1.532, 0.222),
        V( 0.202, 1.508, 0.128),
    ]
    v_front = [
        V(-0.166, 1.482, 0.284),
        V(-0.086, 1.494, 0.382),
        V( 0.086, 1.494, 0.382),
        V( 0.166, 1.482, 0.284),
    ]
    v_back_b = [V(p.x, p.y - 0.022, p.z - 0.004) for p in v_back_t]
    for k in range(3):
        mb.face([v_back_t[k], v_back_t[k + 1], v_front[k + 1], v_front[k]], CAP_BRIM,  out=(0, 1, 0))
        mb.face([v_front[k], v_front[k + 1], v_back_b[k + 1], v_back_b[k]], CAP_UNDER, out=(0, -1, 0))
    mb.face([v_back_b[0], v_front[0], v_back_t[0]], CAP_UNDER, out=(-1, 0, 0))
    mb.face([v_front[3], v_back_b[3], v_back_t[3]], CAP_UNDER, out=( 1, 0, 0))

    # =========================================================================
    # 6. DAD NECK (2 front/side quads = 4 tris)
    # =========================================================================
    mb.set_part("dad_neck", bone="Head")
    n_b = [V(-0.070, 1.114, -0.040), V(0.000, 1.114, 0.076), V(0.070, 1.114, -0.040)]
    n_t = [V(-0.066, 1.206, -0.038), V(0.000, 1.206, 0.070), V(0.066, 1.206, -0.038)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 7. DAD TORSO: PAINTED PLAID FLANNEL SHIRT + 3D FOLDED COLLAR (23 tris)
    # =========================================================================
    mb.set_part("flannel_torso", bone="Torso")
    sh_bot = wide_hex_ring(0.0, 0.626, 0.006, 0.222, 0.152, front_w=0.76, sh_drop=0.000)
    sh_top = wide_hex_ring(0.0, 1.136, 0.006, 0.194, 0.136, front_w=0.76, sh_drop=0.018)

    torso_u_spans = {
        5: (0.00, 0.34),
        0: (0.34, 0.48),
        1: (0.48, 0.60),
        2: (0.60, 0.74),
        3: (0.74, 0.86),
        4: (0.86, 1.00),
    }

    def torso_uv(i, k):
        u0, u1 = torso_u_spans[k]
        return [(u0, 0.345), (u1, 0.345), (u1, 0.995), (u0, 0.995)]

    # 12 wall tris + 2 top shoulder cap + 2 bottom hem cap = 16 tris
    mb.loft([sh_bot, sh_top], TEX_WHITE, cap_bottom=False, cap_top=False,
            mat_idx=MAT_SHIRT, uv_fn=torso_uv)
    # Clean top shoulder deck (4 tris, plaid textured!) and bottom hem seal (2 tris)
    mb.face([sh_top[0], sh_top[1], sh_top[2], sh_top[3]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_SHIRT, uvs=[(0.35, 0.78), (0.50, 0.78), (0.50, 0.96), (0.35, 0.96)])
    mb.face([sh_top[3], sh_top[4], sh_top[5], sh_top[0]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_SHIRT, uvs=[(0.75, 0.78), (0.95, 0.78), (0.95, 0.96), (0.75, 0.96)])
    mb.face([sh_bot[0], sh_bot[2], sh_bot[3], sh_bot[5]], TEX_WHITE, out=(0, -1, 0),
            mat_idx=MAT_SHIRT, uvs=[(0.02, 0.35), (0.32, 0.35), (0.32, 0.45), (0.02, 0.45)])

    # 3D folded plaid shirt collar framing dad's neck (3 quads = 6 tris)
    z_chest_top = 0.006 + 0.136 * 0.88 + 0.005
    for side in (-1, 1):
        mb.face([
            V(side * 0.034, 1.132, z_chest_top + 0.006),
            V(side * 0.124, 1.116, z_chest_top + 0.012),
            V(side * 0.130, 1.186, 0.044),
            V(side * 0.060, 1.190, 0.070),
        ], TEX_WHITE, out=(side * 0.25, 0.35, 0.90), mat_idx=MAT_SHIRT,
                uvs=[(0.08, 0.09), (0.34, 0.09), (0.34, 0.27), (0.08, 0.27)])
    mb.face([
        V(-0.118, 1.134, -0.094),
        V( 0.118, 1.134, -0.094),
        V( 0.108, 1.186, -0.084),
        V(-0.108, 1.186, -0.084),
    ], TEX_WHITE, out=(0, 0, -1), mat_idx=MAT_SHIRT,
            uvs=[(0.40, 0.10), (0.72, 0.10), (0.72, 0.26), (0.40, 0.26)])

    # =========================================================================
    # 8. DAD LONG PLAID SLEEVES + CHUNKY PEACH HANDS (32 + 20 = 52 tris)
    # =========================================================================
    mb.set_part("dad_sleeves_hands")
    arm_specs = [
        # (side, bname,  p_sh,                            p_el,                             p_wr,                             p_hd)
        (-1, "Arm_R", V(-0.180, SHOULDER_Y, SHOULDER_Z), V(-0.266, 0.878, -0.012), V(-0.254, 0.728, 0.036), V(-0.244, 0.630, 0.056)),
        ( 1, "Arm_L", V( 0.180, SHOULDER_Y, SHOULDER_Z), V( 0.266, 0.878, -0.012), V( 0.254, 0.728, 0.036), V( 0.244, 0.630, 0.056)),
    ]

    for (side, bname, p_sh, p_el, p_wr, p_hd) in arm_specs:
        mb.set_bone(bname)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        axm = (ax1 + ax2).normalized()

        def slv_ring(ctr, axis, rf, ro):
            _, u_s, v_s = ortho_basis(axis, hint=V(0.0, 0.0, 1.0))
            if u_s.z < 0:
                u_s = -u_s
            v_s = axis.cross(u_s).normalized()
            if v_s.x * side < 0:
                v_s = -v_s
            return [
                ctr + u_s * rf - v_s * ro,  # 0: front-in
                ctr + u_s * rf + v_s * ro,  # 1: front-out
                ctr - u_s * rf + v_s * ro,  # 2: back-out
                ctr - u_s * rf - v_s * ro,  # 3: back-in
            ]

        r_sh = slv_ring(p_sh, ax1, 0.076, 0.072)
        r_el = slv_ring(p_el, axm, 0.078, 0.074)
        r_wr = slv_ring(p_wr, ax2, 0.070, 0.066)

        def slv_uv(i, k):
            u0 = k * 0.25
            u1 = (k + 1) * 0.25
            v_top = 0.330 if i == 0 else 0.165
            v_bot = 0.165 if i == 0 else 0.005
            return [(u0, v_top), (u1, v_top), (u1, v_bot), (u0, v_bot)]

        # 2 segments x 4 quads = 16 tris per sleeve (hand plugs tightly into wrist cuff!)
        mb.loft([r_sh, r_el, r_wr], TEX_WHITE, cap_bottom=False, cap_top=False,
                mat_idx=MAT_SHIRT, uv_fn=slv_uv)

        # Chunky peach hand emerging cleanly from sleeve cuff (8 walls + 2 tip = 10 tris per hand)
        ax_h = (p_hd - p_wr).normalized()
        p_h0 = p_wr - ax_h * 0.016
        p_h1 = p_hd + ax_h * 0.020
        rh0 = slv_ring(p_h0, ax_h, 0.056, 0.050)
        rh1 = slv_ring(p_h1, ax_h, 0.050, 0.044)
        mb.loft([rh0, rh1], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN)

    # =========================================================================
    # 9. DARK CHARCOAL BACKPACK ON DAD'S BACK (main body 10 + rear pocket 10 = 20 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # Tapered rounded-top backpack sitting snug against dad's back (-Z)
    bp_bot = [
        V(-0.156, 0.728, -0.118),
        V( 0.156, 0.728, -0.118),
        V( 0.146, 0.728, -0.284),
        V(-0.146, 0.728, -0.284),
    ]
    bp_top = [
        V(-0.136, 1.072, -0.106),
        V( 0.136, 1.072, -0.106),
        V( 0.118, 1.050, -0.244),
        V(-0.118, 1.050, -0.244),
    ]
    # k=0 is front (against back -> skip!), k=1 left, k=2 back, k=3 right + top & bottom caps = 10 tris
    mb.loft([bp_bot, bp_top], lambda i, k: PACK_SHADE if k in (1, 3) else PACK,
            cap_bottom=True, cap_top=True, bot_color=PACK_SHADE, top_color=PACK, skip_k=(0,))

    # Raised outer rear zip pouch on backpack (5 faces skipping front = 10 tris)
    mb.box(-0.112, 0.112, 0.758, 0.946, -0.326, -0.256,
           {"back": PACK_POCKET, "top": PACK_POCKET, "bottom": PACK_SHADE, "left": PACK_SHADE, "right": PACK_SHADE},
           skip=("front",))

    # =========================================================================
    # 10. BABY CARRIER WAIST BELT + PADDED SHOULDER STRAPS (10 + 12 = 22 tris)
    # =========================================================================
    mb.set_part("carrier_harness", bone="Torso")
    # Wide dark charcoal waist belt wrapping around dad's flannel torso above shirt hem (5 visible quads = 10 tris)
    wb_bot = wide_hex_ring(0.0, 0.684, 0.006, 0.232, 0.162, front_w=0.77, sh_drop=0.0)
    wb_top = wide_hex_ring(0.0, 0.768, 0.006, 0.228, 0.160, front_w=0.77, sh_drop=0.0)
    # Skip k=5 (front face covered by baby carrier pouch!) -> 5 quads = 10 tris
    mb.loft([wb_bot, wb_top], CARRIER_BELT, cap_bottom=False, cap_top=False, skip_k=(5,))

    # Two padded shoulder straps looping smoothly from baby carrier over dad's shoulders into backpack (2 x 6 = 12 tris)
    for side in (-1, 1):
        # Inner and outer edges of each strap curving over dad's shoulder
        xi_c, xo_c = side * 0.106, side * 0.156
        xi_f, xo_f = side * 0.122, side * 0.172
        xi_t, xo_t = side * 0.108, side * 0.162
        xi_b, xo_b = side * 0.102, side * 0.152
        p_c0 = V(xi_c, 0.942,  0.220); p_c1 = V(xo_c, 0.928,  0.200)   # attaches to upper carrier corner
        p_f0 = V(xi_f, 1.078,  0.144); p_f1 = V(xo_f, 1.064,  0.128)   # front upper chest
        p_t0 = V(xi_t, 1.150,  0.010); p_t1 = V(xo_t, 1.132,  0.008)   # over top of shoulder
        p_b0 = V(xi_b, 1.062, -0.118); p_b1 = V(xo_b, 1.046, -0.116)   # down into top of backpack
        mb.face([p_c0, p_c1, p_f1, p_f0], CARRIER_STRAP, out=(side * 0.3, 0.2, 0.9))
        mb.face([p_f0, p_f1, p_t1, p_t0], CARRIER_STRAP, out=(side * 0.2, 0.9, 0.4))
        mb.face([p_t0, p_t1, p_b1, p_b0], CARRIER_STRAP, out=(side * 0.2, 0.5, -0.8))

    # =========================================================================
    # 11. SLATE-BLUE ERGONOMIC BABY CARRIER POUCH (20 tris, bone="Torso")
    # =========================================================================
    mb.set_part("baby_carrier", bone="Torso")
    # Plump curved front cradle hugging baby's torso against dad's chest (k=3 back against chest skipped!)
    cp_bot = [
        V(-0.112, 0.668, 0.128),  # 0: back-right
        V(-0.088, 0.668, 0.292),  # 1: front-right
        V( 0.088, 0.668, 0.292),  # 2: front-left
        V( 0.112, 0.668, 0.128),  # 3: back-left
    ]
    cp_mid = [
        V(-0.148, 0.808, 0.128),
        V(-0.124, 0.808, 0.346),
        V( 0.124, 0.808, 0.346),
        V( 0.148, 0.808, 0.128),
    ]
    cp_top = [
        V(-0.136, 0.958, 0.128),
        V(-0.112, 0.954, 0.324),
        V( 0.112, 0.954, 0.324),
        V( 0.136, 0.958, 0.128),
    ]
    # 2 bands x 3 visible sides (right k=0, front k=1, left k=2) = 12 tris + bottom cap (2) + top padded collar (4) = 18 tris
    mb.loft([cp_bot, cp_mid, cp_top], lambda i, k: CARRIER_SHADE if k in (0, 2) else CARRIER,
            cap_bottom=True, cap_top=False, bot_color=CARRIER_SHADE, skip_k=(3,))
    # Padded rounded upper carrier rim tucking smoothly around baby's neck/chest (3 quads = 6 tris -> 20 total? Wait: 12+2+6=20!)
    cp_in = [
        V(-0.116, 0.966, 0.156),
        V(-0.092, 0.964, 0.292),
        V( 0.092, 0.964, 0.292),
        V( 0.116, 0.966, 0.156),
    ]
    for k in range(3):
        mb.face([cp_top[k], cp_top[k + 1], cp_in[k + 1], cp_in[k]], CARRIER_TRIM, out=(0, 1, 0.2))

    # =========================================================================
    # 12. BABY HEAD + WARM BROWN HAIR (6-sided, 3 rings + chin cap = 28 tris, bone="Baby_Head")
    # =========================================================================
    mb.set_part("baby_head", bone="Baby_Head")
    # Positioned snugly right above carrier rim & just below dad's beard, facing +Z!
    bh_specs = [
        # (y,     cz,     rx,    rz)
        (0.954,  0.252, 0.104, 0.100),  # 0: cute rounded baby chin resting above carrier
        (1.018,  0.256, 0.142, 0.134),  # 1: plump cheeks
        (1.154,  0.246, 0.138, 0.130),  # 2: forehead / tucked under knit beanie
    ]
    bh_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                for (y, cz, rx, rz) in bh_specs]

    def baby_head_color(i, k):
        # Front face (k=5) and front cheeks (k=0, 4) are rosy baby peach; sides/back (k=1, 2, 3) warm brown hair
        return BABY_SKIN if k in (4, 5, 0) else BABY_HAIR

    mb.loft(bh_rings, baby_head_color, cap_bottom=False, cap_top=False)
    rb_b = bh_rings[0]
    mb.face([rb_b[4], rb_b[5], rb_b[0], rb_b[1]], BABY_SKIN_SHADE, out=(0, -1, 0))

    # Cute warm-brown swept side-fringe / temple bangs tucked high under beanie cuff (2 tris, well above eyes!)
    br2 = bh_rings[2]
    br1 = bh_rings[1]
    mb.face([
        br2[0].lerp(br2[5], 0.16) + V(0.002, 0.0, 0.004),
        br2[1] + V(0.004, 0.0, 0.0),
        br1[1].lerp(br2[1], 0.42) + V(0.004, 0.0, 0.0),
    ], BABY_HAIR, out=(0.85, 0.0, 0.5))
    mb.face([
        br2[5].lerp(br2[0], 0.16) + V(-0.002, 0.0, 0.004),
        br1[4].lerp(br2[4], 0.42) + V(-0.004, 0.0, 0.0),
        br2[4] + V(-0.004, 0.0, 0.0),
    ], BABY_HAIR, out=(-0.85, 0.0, 0.5))

    # =========================================================================
    # 13. BABY EYES + TINY EARS (4 + 6 = 10 tris, bone="Baby_Head")
    # =========================================================================
    mb.set_part("baby_face_details", bone="Baby_Head")
    # Cute dark vertical pill eyes centered nicely on baby's cheeks (z_face at y=1.06 ≈ 0.366)
    z_beye = 0.372
    for side in (-1, 1):
        cx = side * 0.044
        cy = 1.064
        rx = 0.013
        ry = 0.030
        mb.face([
            V(cx - rx, cy - ry, z_beye),
            V(cx + rx, cy - ry, z_beye),
            V(cx + rx, cy + ry, z_beye),
            V(cx - rx, cy + ry, z_beye),
        ], EYE, out=(0, 0, 1))

    # Tiny rounded peach baby ears (3 tris x 2 = 6 tris)
    for side in (-1, 1):
        x_in = side * 0.130
        x_out = side * 0.160
        y0, y1 = 1.028, 1.084
        z0, z1 = 0.232, 0.278
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], BABY_SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], BABY_SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], BABY_SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 14. BABY OATMEAL-TAN KNIT BEANIE (6-sided tilted cuffed beanie = 28 tris, bone="Baby_Head")
    # =========================================================================
    mb.set_part("baby_beanie", bone="Baby_Head")
    btilt = math.radians(13.0)
    bc_bot = tilted_ring(0.0, 1.132, 0.240, 0.160, 0.156, btilt, n=6, phase=math.pi / 6.0)
    bc_top = tilted_ring(0.0, 1.202, 0.228, 0.164, 0.158, btilt, n=6, phase=math.pi / 6.0)
    bd_top = tilted_ring(0.0, 1.300, 0.208, 0.096, 0.094, btilt, n=6, phase=math.pi / 6.0)
    mb.loft([bc_bot, bc_top], BABY_BEANIE_CUFF, cap_bottom=False, cap_top=False)
    mb.loft([bc_top, bd_top], BABY_BEANIE, cap_bottom=False, cap_top=True, top_color=BABY_BEANIE_TOP)

    # =========================================================================
    # 15. BABY OLIVE SLEEVES + TINY PEACH HANDS (2 x 18 = 36 tris, bone="Torso")
    # =========================================================================
    mb.set_part("baby_arms", bone="Torso")
    for side in (-1, 1):
        # Short plump olive sleeve emerging from carrier side -> tiny peach hand forward!
        p_bsh = V(side * 0.118, 0.902, 0.206)
        p_bwr = V(side * 0.160, 0.858, 0.278)
        p_bhd = V(side * 0.146, 0.854, 0.336)
        ax_s = (p_bwr - p_bsh).normalized()
        ax_h = (p_bhd - p_bwr).normalized()
        ax_m = (ax_s + ax_h).normalized()

        def baby_ring(ctr, axis, r):
            _, u_b, v_b = ortho_basis(axis, hint=V(0.0, 1.0, 0.0))
            return [
                ctr + u_b * r + v_b * r,
                ctr - u_b * r + v_b * r,
                ctr - u_b * r - v_b * r,
                ctr + u_b * r - v_b * r,
            ]

        r0 = baby_ring(p_bsh, ax_s, 0.043)
        r1 = baby_ring(p_bwr, ax_m, 0.040)
        r2 = baby_ring(p_bhd, ax_h, 0.032)
        # Continuous 2-band loft (i=0: olive sleeve, i=1: peach hand + front tip cap = 18 tris per arm)
        mb.loft([r0, r1, r2],
                lambda i, k: (BABY_SLEEVE_SH if k == 2 else BABY_SLEEVE) if i == 0
                else (BABY_SKIN_SHADE if k == 2 else BABY_SKIN),
                cap_bottom=False, cap_top=True, top_color=BABY_SKIN)

    # =========================================================================
    # 16. BABY CREAM BOOTIES POKING OUT CARRIER SIDES (2 x 10 = 20 tris, bone="Torso")
    # =========================================================================
    mb.set_part("baby_booties", bone="Torso")
    for side in (-1, 1):
        # Adorable chunky cream baby booties angled gently out & forward from carrier lower sides!
        p_heel = V(side * 0.104, 0.728, 0.200)
        p_toe  = V(side * 0.168, 0.684, 0.326)
        ax_f = (p_toe - p_heel).normalized()
        _, u_f, v_f = ortho_basis(ax_f, hint=V(0.0, 1.0, 0.0))
        if u_f.y < 0:
            u_f = -u_f
        v_f = ax_f.cross(u_f).normalized()
        # 4-sided shoe ring: 0:top-out, 1:top-in, 2:bot-in, 3:bot-out -> k=2 is bottom sole!
        def shoe_ring(ctr, ry, rx):
            return [
                ctr + u_f * ry + v_f * rx,
                ctr + u_f * ry - v_f * rx,
                ctr - u_f * ry - v_f * rx,
                ctr - u_f * ry + v_f * rx,
            ]
        sr0 = shoe_ring(p_heel, 0.042, 0.038)
        sr1 = shoe_ring(p_toe,  0.038, 0.036)
        mb.loft([sr0, sr1], lambda i, k: BABY_SHOE_SOLE if k == 2 else (BABY_SHOE_SHADE if k in (1, 3) else BABY_SHOE),
                cap_bottom=False, cap_top=True, top_color=BABY_SHOE)

    # =========================================================================
    # 17. OLIVE-KHAKI CARGO PANTS + 3D SIDE CARGO POCKETS (8 + 20 + 12 = 40 tris)
    # =========================================================================
    mb.set_part("cargo_pants", bone="Root")
    mb.box(-0.194, 0.194, 0.540, 0.662, -0.118, 0.118, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.192
        x_in_b, x_out_b = side * 0.034, side * 0.224
        rz_t, rz_b = 0.106, 0.116
        r_top = [
            V(min(x_in_t, x_out_t), 0.590,  rz_t),
            V(max(x_in_t, x_out_t), 0.590,  rz_t),
            V(max(x_in_t, x_out_t), 0.590, -rz_t),
            V(min(x_in_t, x_out_t), 0.590, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.136,  rz_b),
            V(max(x_in_b, x_out_b), 0.136,  rz_b),
            V(max(x_in_b, x_out_b), 0.136, -rz_b),
            V(min(x_in_b, x_out_b), 0.136, -rz_b),
        ]
        mb.loft([r_bot, r_top], lambda i, k: PANTS_SHADE if k == 2 else PANTS,
                cap_bottom=True, cap_top=False, bot_color=PANTS_INNER)

        # Crisp 3D outer-thigh olive-khaki cargo pocket (6 tris per leg = 12 tris total)
        t_lo = (0.330 - 0.136) / (0.590 - 0.136)
        t_hi = (0.476 - 0.136) / (0.590 - 0.136)
        x_wall_lo = x_out_b * (1.0 - t_lo) + x_out_t * t_lo
        x_wall_hi = x_out_b * (1.0 - t_hi) + x_out_t * t_hi
        x_pk_lo = x_wall_lo + side * 0.024
        x_pk_hi = x_wall_hi + side * 0.018
        pz0, pz1 = -0.068, 0.068
        p_fb = V(x_pk_lo, 0.330, pz1); p_bb = V(x_pk_lo, 0.330, pz0)
        p_bt = V(x_pk_hi, 0.476, pz0); p_ft = V(x_pk_hi, 0.476, pz1)
        w_fb = V(x_wall_lo, 0.330, pz1); w_bb = V(x_wall_lo, 0.330, pz0)
        w_bt = V(x_wall_hi, 0.476, pz0); w_ft = V(x_wall_hi, 0.476, pz1)
        mb.face([p_bb, p_fb, p_ft, p_bt], PANTS_LIGHT, out=(side, 0, 0))
        mb.face([w_bb, w_fb, p_fb, p_bb], PANTS_SHADE, out=(0, -1, 0))
        mb.face([w_fb, w_ft, p_fb],       PANTS_SHADE, out=(0, 0, 1))
        mb.face([w_bt, w_bb, p_bb],       PANTS_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 18. CHUNKY BROWN WORK BOOTS WITH DARK SOLES (2 x 18 = 36 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.130
        w = 0.074
        w_toe = 0.062
        z_heel = -0.092
        z_toe  =  0.172
        y_sole0 = 0.000
        y_sole1 = 0.038
        y_col   = 0.158

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

        boot_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, 0.062),
            V(cx - w * 0.84, y_col, 0.062),
        ]
        mb.loft([sole_top, boot_top], lambda i, k: BOOT_SHADE if k == 0 else BOOT,
                cap_bottom=False, cap_top=False)

    return mb


def setup_materials(shirt_img):
    # Slot 0: Standard VertexColour material matching all other person_*.glb models
    mat_vcol = bpy.data.materials.get("VertexColour") or bpy.data.materials.new("VertexColour")
    nt = mat_vcol.node_tree
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

    # Slot 1: Painted Plaid Flannel Shirt material
    mat_shirt = bpy.data.materials.new("DadFlannelShirt")
    nt_t = mat_shirt.node_tree
    bsdf_t = next(n for n in nt_t.nodes if n.type == "BSDF_PRINCIPLED")
    tex_t = nt_t.nodes.new("ShaderNodeTexImage")
    tex_t.image = shirt_img
    vc_t = nt_t.nodes.new("ShaderNodeVertexColor")
    vc_t.layer_name = "Col"
    mix_t = nt_t.nodes.new("ShaderNodeMix")
    mix_t.data_type = "RGBA"
    mix_t.blend_type = "MULTIPLY"
    mix_t.inputs["Factor"].default_value = 1.0
    nt_t.links.new(tex_t.outputs["Color"], mix_t.inputs["A"])
    nt_t.links.new(vc_t.outputs["Color"], mix_t.inputs["B"])
    nt_t.links.new(mix_t.outputs["Result"], bsdf_t.inputs["Base Color"])
    bsdf_t.inputs["Roughness"].default_value = 0.88
    if "Specular IOR Level" in bsdf_t.inputs:
        bsdf_t.inputs["Specular IOR Level"].default_value = 0.18

    return [mat_vcol, mat_shirt]


def _reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: steady dad stride with balanced posture & gentle baby head bob."""
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

        # Steady, balanced walk with gentle double-frequency vertical bob
        pb_root = rig.pose.bones["Root"]
        bob = -0.022 * (1.0 - c2) * 0.5
        root_pitch = -0.026
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.062 * s1, 0.034 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle torso counter-twist (stabilized slightly for carrying baby!)
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.016 * c2, 0.072 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Dad looks steadily ahead
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.024 + 0.018 * c2, -0.032 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Baby head has a cute soft phase-lagged bounce & tiny curious sway!
        pb_baby = rig.pose.bones["Baby_Head"]
        pb_baby.rotation_euler = (
            0.048 * math.cos(2.0 * phi - 0.65),
            0.065 * math.sin(phi - 0.45),
            -0.038 * math.cos(phi - 0.50),
        )
        pb_baby.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating stride with clean boot lift above ground on swing
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

        # Natural relaxed counter-swinging arms clear of baby & cargo pockets
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.28 * s1 - 0.02, 0.0, 0.03)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.28 * s1 - 0.02, 0.0, -0.03)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: gentle dad bounce-rocking, glancing down at baby, baby looking around."""
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

        # Gentle rhythmic dad-rock weight shift & soothing micro-bounce
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.010 * (1.0 - math.cos(2.0 * phi)) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.008, 0.022 * s1, 0.026 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.020 * s2, 0.030 * s1, -0.018 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Dad calmly looks around and briefly glances down warmly toward baby
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (-0.085 * max(0.0, -c1) + 0.022 * s2, 0.22 * s1, 0.038 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Baby curiously turns head side-to-side taking in the harbor!
        pb_baby = rig.pose.bones["Baby_Head"]
        pb_baby.rotation_euler = (0.055 * s2 + 0.025, -0.32 * math.sin(phi - 0.5), 0.075 * c1)
        pb_baby.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Boots firmly planted on the dock
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed arms drifting gently with breathing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.038 * s1 - 0.016 * s2, 0.0, 0.022 + 0.014 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.038 * s1 - 0.016 * s2, 0.0, -0.022 - 0.014 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Baby_Head) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonDadBabyRig")
    rig = bpy.data.objects.new("PersonDadBabyRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",      None,    ( 0.000, 0.596,  0.000),      ( 0.000, 0.696,  0.000)),
        ("Torso",     "Root",  ( 0.000, 0.660,  0.000),      ( 0.000, 1.125,  0.000)),
        ("Head",      "Torso", ( 0.000, 1.158,  0.000),      ( 0.000, 1.480,  0.000)),
        ("Baby_Head", "Torso", tuple(BABY_NECK),             (BABY_NECK.x, BABY_NECK.y + 0.240, BABY_NECK.z)),
        ("Arm_L",     "Torso", ( 0.180, SHOULDER_Y, SHOULDER_Z), ( 0.180, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Arm_R",     "Torso", (-0.180, SHOULDER_Y, SHOULDER_Z), (-0.180, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Leg_L",     "Root",  ( 0.112, 0.560,  0.000),      ( 0.112, 0.720,  0.000)),
        ("Leg_R",     "Root",  (-0.112, 0.560,  0.000),      (-0.112, 0.720,  0.000)),
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-2.25, math.radians(56)),   # Front-3/4 matching reference angle (facing right)
        (-0.75, math.radians(0)),    # Front (showing baby face & carrier clearly)
        ( 0.75, math.radians(90)),   # Side (showing cap visor, baby profile & backpack)
        ( 2.25, math.radians(180)),  # Back (showing charcoal backpack & straps)
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
    cam_data.ortho_scale = 6.2
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.5, 1.30)
    direction = Vector((0.0, 0.0, 0.90)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1440
    scene.render.resolution_y = 600
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("StripFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0, 0, -0.001))
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.48
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 9.4
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -7.5, 1.30)
    direction = Vector((0.0, 0.0, 0.90)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1600
    scene.render.resolution_y = 480
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("VidFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.55
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.30)
    direction = Vector((0.0, 0.0, 0.90)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 840
    scene.render.resolution_y = 580
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
            left_obj.location = (-0.80, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.80, 0.0, 0.0)
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

    coll = bpy.data.collections.new("PersonDadBaby")
    bpy.context.scene.collection.children.link(coll)

    shirt_img = generate_shirt_texture(SHIRT_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonDadBaby")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(shirt_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonDadBaby", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris < 450, f"Triangle budget exceeded: {total_tris} >= 450"

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    # Export GLB with both Walk and Idle animations + embedded texture + Part UV via ACTIONS mode
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
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=44)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=56, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=44, zrot_right_deg=90)

    print("=== PersonDadBaby Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    print(f"Shirt texture:   {SHIRT_TEX_PATH}")
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
