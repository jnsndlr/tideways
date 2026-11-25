# Builds an ultra-low-poly (< 350 tris) stylized old fisherman with olive fish-emblem cap,
# fluffy silver-gray hair & bushy mustache, painted brown plaid flannel shirt + orange fishing vest,
# red looped leash with silver snap hook, khaki cargo pants, and chunky brown boots in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_fisherman.py)
# Saves art/person_fisherman.blend, exports assets/models/person_fisherman.glb (rigged + Walk & Idle cycles + embedded texture),
# renders art/person_fisherman_preview.png, art/person_fisherman_walk_preview.png, art/person_fisherman_idle_preview.png,
# and outputs rendered videos art/person_fisherman_walk.mp4 and art/person_fisherman_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.70 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_fisherman.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_fisherman.glb")
SHIRT_TEX_PATH = os.path.join(ROOT, "art", "person_fisherman_shirt_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_fisherman_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_fisherman_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_fisherman_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_fisherman_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_fisherman_idle.mp4")

MAT_VCOL = 0
MAT_SHIRT = 1


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference old fisherman artwork (sRGB -> linear)
WHITE          = (1.0, 1.0, 1.0, 1.0)

SKIN           = col_srgb(0.97, 0.76, 0.54)
SKIN_SHADE     = col_srgb(0.86, 0.63, 0.42)
EYE            = col_srgb(0.10, 0.09, 0.09)

HAIR           = col_srgb(0.81, 0.81, 0.80)
HAIR_SHADE     = col_srgb(0.67, 0.67, 0.66)
MUSTACHE       = col_srgb(0.82, 0.82, 0.81)
MUSTACHE_SHADE = col_srgb(0.68, 0.68, 0.67)

CAP_CROWN      = col_srgb(0.43, 0.48, 0.37)
CAP_TOP        = col_srgb(0.47, 0.52, 0.41)
CAP_BRIM       = col_srgb(0.40, 0.45, 0.34)
CAP_UNDER      = col_srgb(0.28, 0.32, 0.24)
FISH_EMBLEM    = col_srgb(0.94, 0.84, 0.58)

VEST_TOP       = col_srgb(0.88, 0.47, 0.21)
VEST_BOT       = col_srgb(0.27, 0.26, 0.25)
CUFF_DARK      = col_srgb(0.24, 0.22, 0.20)

LEASH_RED      = col_srgb(0.66, 0.26, 0.21)
LEASH_SHADE    = col_srgb(0.49, 0.18, 0.14)
CLIP_SILVER    = col_srgb(0.79, 0.80, 0.81)
CLIP_SHADE     = col_srgb(0.57, 0.59, 0.61)

PANTS          = col_srgb(0.75, 0.66, 0.50)
PANTS_SHADE    = col_srgb(0.63, 0.54, 0.40)
PANTS_LIGHT    = col_srgb(0.79, 0.70, 0.54)
PANTS_INNER    = col_srgb(0.47, 0.40, 0.30)

BOOT           = col_srgb(0.49, 0.35, 0.24)
BOOT_SHADE     = col_srgb(0.38, 0.26, 0.17)
SOLE           = col_srgb(0.26, 0.19, 0.15)


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared anchor coordinates so left arm, hand, and hanging red leash align identically
SHOULDER_Y = 1.080
SHOULDER_Z = 0.008
HAND_L_GRIP = V(0.276, 0.706, 0.148)


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def _rect_mask(uu, vv, u0, u1, v0, v1, feather=0.003):
    mx = np.clip((uu - u0) / feather, 0.0, 1.0) * np.clip((u1 - uu) / feather, 0.0, 1.0)
    my = np.clip((vv - v0) / feather, 0.0, 1.0) * np.clip((v1 - vv) / feather, 0.0, 1.0)
    return mx * my


def _plaid_pattern(uu, vv, freq_u, freq_v):
    """Generate rich brown/warm-tan/charcoal plaid flannel pattern matched to reference artwork."""
    # Periodic phase in [0, 1)
    pu = (uu * freq_u) % 1.0
    pv = (vv * freq_v) % 1.0

    # Base warm camel-tan flannel cloth
    col = np.zeros(uu.shape + (3,), dtype=np.float32)
    col[..., 0] = 0.60
    col[..., 1] = 0.49
    col[..., 2] = 0.37

    # Medium warm brown bands (occupying [0.22..0.78] in each cell)
    u_med = np.clip((pu - 0.20) * 35.0, 0.0, 1.0) * np.clip((0.80 - pu) * 35.0, 0.0, 1.0)
    v_med = np.clip((pv - 0.20) * 35.0, 0.0, 1.0) * np.clip((0.80 - pv) * 35.0, 0.0, 1.0)

    # Dark charcoal-brown core stripes (occupying [0.36..0.64] in each cell)
    u_dark = np.clip((pu - 0.36) * 45.0, 0.0, 1.0) * np.clip((0.64 - pu) * 45.0, 0.0, 1.0)
    v_dark = np.clip((pv - 0.36) * 45.0, 0.0, 1.0) * np.clip((0.64 - pv) * 45.0, 0.0, 1.0)

    # Thin subtle dark overcheck lines centered on the tan squares (near 0.0 / 1.0)
    u_pin = np.clip((0.032 - np.minimum(pu, 1.0 - pu)) * 60.0, 0.0, 1.0)
    v_pin = np.clip((0.032 - np.minimum(pv, 1.0 - pv)) * 60.0, 0.0, 1.0)

    # Layer medium brown warp & weft bands with multiplicative weave feel
    med_blend = np.clip(0.48 * u_med + 0.48 * v_med - 0.14 * u_med * v_med, 0.0, 1.0)
    col = _blend_mask(col, med_blend, (0.42, 0.34, 0.26))

    # Layer dark charcoal-brown stripes (darkening further where warp & weft intersect!)
    dark_single = np.clip(np.maximum(u_dark, v_dark), 0.0, 1.0)
    dark_cross = u_dark * v_dark
    col = _blend_mask(col, dark_single * 0.78, (0.27, 0.25, 0.23))
    col = _blend_mask(col, dark_cross * 0.85, (0.19, 0.18, 0.17))

    # Subtle overcheck pinstripes on the warm tan squares
    pin = np.maximum(u_pin, v_pin) * (1.0 - dark_single)
    col = _blend_mask(col, pin * 0.45, (0.31, 0.26, 0.22))

    # Subtle soft flannel twill weave micro-texture
    twill = 1.0 + 0.018 * np.sin((uu * 220.0 + vv * 220.0))
    col *= twill[..., None]
    return np.clip(col, 0.0, 1.0)


def generate_shirt_texture(out_path):
    """Paint a 512x512 sRGB texture:
       - Top band (v in [0.34, 1.00]): Torso with center plaid flannel shirt + open burnt-orange fishing vest,
         upper orange pockets, lower brown-flap pockets, vest lapel shadows, and dark charcoal hem trim.
       - Bottom band (v in [0.00, 0.32]): Brown/tan/charcoal plaid flannel for long sleeves + collar,
         with dark charcoal cuff band along wrist edge (v in [0.00, 0.045]).
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Start with plaid flannel across the whole canvas
    img = _plaid_pattern(uu, vv, freq_u=4.0, freq_v=7.5)

    # =========================================================================
    # 1. SLEEVE / COLLAR STRIP (v in [0.00, 0.33])
    # =========================================================================
    # Crisp sleeve plaid scaled nicely so ~4 bold checks wrap around arm & ~3.5 down arm length
    sleeve_plaid = _plaid_pattern(uu + 0.06, vv, freq_u=4.0, freq_v=11.0)
    # Subtle soft shading along sleeve length (slightly warmer/brighter near shoulder v=0.32)
    slv_t = np.clip(vv / 0.32, 0.0, 1.0)
    sleeve_plaid *= (0.93 + 0.09 * slv_t)[..., None]

    # Dark charcoal-brown cuff band at wrist bottom edge (v in [0.00, 0.052])
    cuff_m = np.clip((0.052 - vv) / 0.006, 0.0, 1.0)
    sleeve_plaid = _blend_mask(sleeve_plaid, cuff_m, (0.24, 0.22, 0.20))
    # Subtle cuff top seam highlight
    cuff_seam = np.clip((0.007 - np.abs(vv - 0.054)) / 0.003, 0.0, 1.0)
    sleeve_plaid = _blend_mask(sleeve_plaid, cuff_seam * 0.50, (0.16, 0.14, 0.13))

    in_sleeve = (vv < 0.335).astype(np.float32)
    img = img * (1.0 - in_sleeve[..., None]) + sleeve_plaid * in_sleeve[..., None]

    # =========================================================================
    # 2. TORSO REGION (v in [0.335, 1.00])
    #    Front face k=5 maps to u in [0.00, 0.34] (center front = u = 0.17)
    #    - Center plaid flannel chest opening: u in [0.122, 0.218]
    #    - Burnt-orange fishing vest wraps everywhere else on torso!
    # =========================================================================
    in_torso = (vv >= 0.335).astype(np.float32)
    torso_v = np.clip((vv - 0.34) / 0.66, 0.0, 1.0)

    # Center plaid flannel chest (finely scaled to match sleeve check size!)
    chest_plaid = _plaid_pattern(uu + 0.02, vv, freq_u=11.5, freq_v=6.2)
    chest_plaid *= (0.90 + 0.12 * torso_v)[..., None]
    # Subtle center vertical button placket line at u = 0.170
    placket = np.clip((0.0055 - np.abs(uu - 0.170)) / 0.002, 0.0, 1.0) * in_torso
    chest_plaid = _blend_mask(chest_plaid, placket * 0.55, (0.19, 0.17, 0.16))
    # Subtle buttons down center flannel placket
    for bv in (0.48, 0.64, 0.80):
        bd = np.sqrt(((uu - 0.170) / 0.0065) ** 2 + ((vv - bv) / 0.011) ** 2)
        chest_plaid = _blend_mask(chest_plaid, np.clip((1.0 - bd) * 5.0, 0.0, 1.0), (0.34, 0.28, 0.23))

    # Orange vest base color with gentle top-to-bottom fabric gradient & subtle weave
    vest_col = np.zeros((h, w, 3), dtype=np.float32)
    vest_col[..., 0] = 0.89
    vest_col[..., 1] = 0.44
    vest_col[..., 2] = 0.16
    vest_grad = 0.94 + 0.08 * torso_v + 0.010 * np.sin(vv * 260.0)
    vest_col *= vest_grad[..., None]

    # Subtle side & back panel seam lines on vest (u = 0.34, 0.48, 0.86) and back shoulder yoke
    back_yoke = np.clip((0.006 - np.abs(vv - 0.83)) / 0.003, 0.0, 1.0) * _rect_mask(uu, vv, 0.45, 0.89, 0.81, 0.85, 0.005)
    vest_col = _blend_mask(vest_col, back_yoke * 0.35, (0.64, 0.30, 0.12))

    # Vest front opening mask: open down center front u in [0.124, 0.216], curving slightly wider at V-neck near top!
    neck_open = 0.022 * np.clip((torso_v - 0.72) / 0.28, 0.0, 1.0) ** 1.4
    open_l = 0.124 - neck_open
    open_r = 0.216 + neck_open
    is_vest = 1.0 - (
        np.clip((uu - open_l) / 0.004, 0.0, 1.0) * np.clip((open_r - uu) / 0.004, 0.0, 1.0)
    )

    # Combine center plaid shirt + orange vest on torso
    torso_img = chest_plaid * (1.0 - is_vest[..., None]) + vest_col * is_vest[..., None]

    # Soft cast shadow from the orange vest edges onto the plaid flannel chest (gives crisp 3D depth!)
    shadow_l = np.clip((0.014 - np.abs(uu - (open_l + 0.006))) / 0.012, 0.0, 1.0) * (1.0 - is_vest)
    shadow_r = np.clip((0.014 - np.abs(uu - (open_r - 0.006))) / 0.012, 0.0, 1.0) * (1.0 - is_vest)
    torso_img = _blend_mask(torso_img, np.maximum(shadow_l, shadow_r) * 0.50, (0.14, 0.12, 0.11))

    # Crisp slightly darker orange piping/edge along inner vest lapels
    piping_l = np.clip((0.007 - np.abs(uu - (open_l - 0.005))) / 0.003, 0.0, 1.0) * is_vest
    piping_r = np.clip((0.007 - np.abs(uu - (open_r + 0.005))) / 0.003, 0.0, 1.0) * is_vest
    torso_img = _blend_mask(torso_img, np.maximum(piping_l, piping_r) * 0.45, (0.68, 0.32, 0.13))

    # --- Paint Iconic Fishing Vest Pockets on Both Front Halves (u in [0.012..0.106] and [0.234..0.328]) ---
    # Each side has:
    #   1) Upper chest orange pocket (v in [0.695..0.815]) with top flap crease
    #   2) Lower cargo vest pocket (v in [0.445..0.635]) with prominent warm-brown flap (v in [0.575..0.635])!
    for (pu0, pu1) in ((0.010, 0.100), (0.240, 0.330)):
        # Upper pocket soft drop shadow
        up_sh = _rect_mask(uu, vv, pu0 - 0.005, pu1 + 0.005, 0.686, 0.815, 0.004)
        torso_img = _blend_mask(torso_img, up_sh * 0.45, (0.60, 0.26, 0.09))
        # Upper pocket orange body
        up_body = _rect_mask(uu, vv, pu0, pu1, 0.696, 0.815, 0.003)
        torso_img = _blend_mask(torso_img, up_body, (0.93, 0.48, 0.19))
        # Upper pocket flap seam line
        up_flap_line = _rect_mask(uu, vv, pu0, pu1, 0.770, 0.782, 0.002)
        torso_img = _blend_mask(torso_img, up_flap_line * 0.58, (0.64, 0.29, 0.10))

        # Lower pocket soft drop shadow
        lo_sh = _rect_mask(uu, vv, pu0 - 0.006, pu1 + 0.006, 0.442, 0.642, 0.005)
        torso_img = _blend_mask(torso_img, lo_sh * 0.50, (0.56, 0.24, 0.08))
        # Lower pocket orange pouch body
        lo_body = _rect_mask(uu, vv, pu0, pu1, 0.452, 0.585, 0.003)
        torso_img = _blend_mask(torso_img, lo_body, (0.93, 0.48, 0.19))
        # Lower pocket warm-brown top flap (signature detail from reference!)
        lo_flap_sh = _rect_mask(uu, vv, pu0 - 0.002, pu1 + 0.002, 0.568, 0.640, 0.003)
        torso_img = _blend_mask(torso_img, lo_flap_sh * 0.48, (0.34, 0.20, 0.12))
        lo_flap = _rect_mask(uu, vv, pu0 - 0.002, pu1 + 0.002, 0.576, 0.642, 0.003)
        torso_img = _blend_mask(torso_img, lo_flap, (0.53, 0.36, 0.25))
        # Subtle highlight along top edge of brown flap
        lo_hi = _rect_mask(uu, vv, pu0, pu1, 0.630, 0.642, 0.003)
        torso_img = _blend_mask(torso_img, lo_hi * 0.35, (0.64, 0.46, 0.33))

    # --- Dark charcoal-brown lower waist hem trim running cleanly under the orange vest (v in [0.34, 0.415]) ---
    # Only on the vest sections (keeps the center plaid shirt extending down cleanly between the vest hems!)
    hem_trim = np.clip((0.412 - vv) / 0.006, 0.0, 1.0) * is_vest
    torso_img = _blend_mask(torso_img, hem_trim, (0.28, 0.27, 0.26))
    # Crisp dark seam separating orange vest from charcoal bottom hem trim
    hem_seam = np.clip((0.007 - np.abs(vv - 0.415)) / 0.003, 0.0, 1.0) * is_vest
    torso_img = _blend_mask(torso_img, hem_seam * 0.55, (0.18, 0.17, 0.16))

    # Apply torso image onto upper canvas region
    img = img * (1.0 - in_torso[..., None]) + torso_img * in_torso[..., None]

    img = np.clip(img, 0.0, 1.0)
    bimg = bpy.data.images.new("FishermanShirtTex", width=w, height=h, alpha=True, float_buffer=False)
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
        vcol = WHITE if mat_idx != MAT_VCOL else color
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
    """6-sided ring with broad flat front (k=5) and back (k=2) faces for crisp vest + plaid chest mapping."""
    # k=0: front-left (+X), k=1: left, k=2: back-left, k=3: back-right, k=4: right, k=5: front-right (-X)
    zf = rz * 0.88
    yo = cy - sh_drop
    return [
        V(cx + rx * front_w, cy, cz + zf),   # 0: front-left
        V(cx + rx,           yo, cz),        # 1: left (gently sloped shoulder!)
        V(cx + rx * front_w, cy, cz - zf),   # 2: back-left
        V(cx - rx * front_w, cy, cz - zf),   # 3: back-right
        V(cx - rx,           yo, cz),        # 4: right (gently sloped shoulder!)
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
    # 1. HEAD (6-sided stylized low-poly head, flat front face = 28 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.196,  0.018, 0.156, 0.150),  # 0: chin/jaw
        (1.286,  0.022, 0.214, 0.204),  # 1: lower cheek
        (1.492,  0.008, 0.210, 0.200),  # 2: brow / tucked cleanly inside olive cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        # Front face (k=5) and front cheeks (k=0, 4) are warm peach skin; back (k=1, 2, 3) silver hair
        return SKIN if k in (4, 5, 0) else HAIR

    mb.loft(head_rings, head_color, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # =========================================================================
    # 2. FLUFFY SILVER-GRAY HAIR TUFT WRAP BEHIND EARS & NAPE (20 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # Expressive puffed silver hair sticking out behind ears and nape cleanly tucked under olive cap!
    hair_angles = [math.radians(a) for a in (74, 128, 180, 232, 286)]
    hair_specs = [
        # (y,     rx,    rz,    cz,     boost)
        (1.214, 0.194, 0.212, -0.024, 0.08),  # 0: lower tousled nape
        (1.326, 0.232, 0.238, -0.032, 0.11),  # 1: soft rounded fluffy back-of-head curl like reference!
        (1.452, 0.198, 0.200, -0.012, 0.02),  # 2: tucked strictly inside olive cap rim (zero back clipping!)
    ]
    h_rings = []
    for (y, rx, rz, cz, boost) in hair_specs:
        ring = []
        for a in hair_angles:
            b = 1.0 + boost * max(0.0, -math.cos(a))
            ring.append(V(rx * b * math.sin(a), y, cz + rz * b * math.cos(a)))
        h_rings.append(ring)

    for i in range(2):
        r0, r1 = h_rings[i], h_rings[i + 1]
        col = HAIR_SHADE if i == 0 else HAIR
        for k in range(4):
            p0, p1, p2, p3 = r0[k], r0[k + 1], r1[k + 1], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], col, out=V(mid.x, 0.0, mid.z))

    # Crisp bottom nape tuck merging into back of head (4 tris)
    rb_h = h_rings[0]
    for k in range(2):
        p0 = rb_h[k * 2]
        p1 = rb_h[k * 2 + 1]
        p2 = rb_h[k * 2 + 2]
        mb.face([p2, p1, p0, V(p0.x * 0.50, 1.210, p0.z * 0.50)], HAIR_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 3. EARS (2 compact rounded low-poly peach wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.198
        x_out = side * 0.242
        y0, y1 = 1.298, 1.384
        z0, z1 = 0.000, 0.068
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_tip], SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. EYES (2 vertical dark pill hexagons flush on front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    # On 6-sided head (phase=pi/6), front face Z at y=1.39 is ~0.193 -> place eyes at 0.199
    z_eye = 0.200
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.390
        rx = 0.019
        ry = 0.046
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
    # 5. BUSHY SILVER-GRAY MUSTACHE (sculpted 2-wing drooping mustache = 16 tris)
    # =========================================================================
    mb.set_part("mustache", bone="Head")
    # Two plump curved wings meeting cleanly at X = 0, skipping rear face against skin (8 tris x 2 = 16 tris)
    for side in (-1, 1):
        # Center cross-section (0: top-back, 1: top-front, 2: bot-front, 3: bot-back)
        r0 = [
            V(0.0, 1.326, 0.196),
            V(0.0, 1.322, 0.238),
            V(0.0, 1.280, 0.234),
            V(0.0, 1.282, 0.194),
        ]
        # Outer slightly drooping rounded wing tip
        r1 = [
            V(side * 0.098, 1.300, 0.172),
            V(side * 0.102, 1.294, 0.210),
            V(side * 0.098, 1.258, 0.204),
            V(side * 0.092, 1.262, 0.168),
        ]
        if side > 0:
            # k=0: top, k=1: front, k=2: bottom, k=3: back (skip back!)
            mb.loft([r0, r1], lambda i, k: MUSTACHE_SHADE if k == 2 else MUSTACHE,
                    cap_bottom=False, cap_top=True, top_color=MUSTACHE_SHADE, skip_k=(3,))
        else:
            mb.loft([r1, r0], lambda i, k: MUSTACHE_SHADE if k == 2 else MUSTACHE,
                    cap_bottom=True, cap_top=False, bot_color=MUSTACHE_SHADE, skip_k=(3,))

    # =========================================================================
    # 6. OLIVE GREEN BASEBALL CAP + CURVED VISOR + GOLDEN FISH EMBLEM (56 tris)
    # =========================================================================
    mb.set_part("cap", bone="Head")
    # Positive tilt lifts front brim gently above eyes while sitting low over silver nape hair
    cap_tilt = math.radians(10.5)
    c_rim = tilted_ring(0.0, 1.468, -0.008, 0.242, 0.252, cap_tilt, n=8, phase=math.pi / 8.0)
    c_mid = tilted_ring(0.0, 1.608, -0.004, 0.228, 0.236, cap_tilt * 0.72, n=8, phase=math.pi / 8.0)
    c_top = tilted_ring(0.0, 1.718, -0.012, 0.118, 0.122, cap_tilt * 0.40, n=8, phase=math.pi / 8.0)

    # 8-sided 2-band rounded dome + flat top (32 + 6 = 38 tris)
    mb.loft([c_rim, c_mid, c_top], CAP_CROWN, cap_bottom=False, cap_top=True, top_color=CAP_TOP)

    # Sleek tapered curved baseball visor projecting forward over brow (14 tris: 6 top + 6 underside + 2 side tris)
    v_back_t = [
        V(-0.205, 1.500, 0.130),
        V(-0.105, 1.522, 0.226),
        V( 0.105, 1.522, 0.226),
        V( 0.205, 1.500, 0.130),
    ]
    v_front = [
        V(-0.168, 1.464, 0.286),
        V(-0.088, 1.474, 0.388),
        V( 0.088, 1.474, 0.388),
        V( 0.168, 1.464, 0.286),
    ]
    v_back_b = [V(p.x, p.y - 0.022, p.z - 0.004) for p in v_back_t]

    for k in range(3):
        mb.face([v_back_t[k], v_back_t[k + 1], v_front[k + 1], v_front[k]], CAP_BRIM, out=(0, 1, 0))
        mb.face([v_front[k], v_front[k + 1], v_back_b[k + 1], v_back_b[k]], CAP_UNDER, out=(0, -1, 0))
    # Seal left/right triangular visor cheeks cleanly
    mb.face([v_back_b[0], v_front[0], v_back_t[0]], CAP_UNDER, out=(-1, 0, 0))
    mb.face([v_front[3], v_back_b[3], v_back_t[3]], CAP_UNDER, out=( 1, 0, 0))

    # Crisp golden-cream FISH emblem mounted flush on the front crown panel (c_rim -> c_mid, k=7..0) (4 tris!)
    mb.set_part("cap_emblem", bone="Head")
    p_bl = c_rim[7]; p_br = c_rim[0]
    p_tl = c_mid[7]; p_tr = c_mid[0]
    em_origin = (p_bl + p_br) * 0.5
    em_top_c  = (p_tl + p_tr) * 0.5
    em_x = (p_br - p_bl).normalized()
    em_y = (em_top_c - em_origin).normalized()
    em_n = em_x.cross(em_y).normalized()
    if em_n.z < 0:
        em_n = -em_n

    def em_pt(u_off, v_off, lift=0.006):
        return em_origin + em_x * u_off + em_y * v_off + em_n * lift

    cy_f = 0.078  # centered cleanly on front crown panel above visor
    # Plump diamond/oval fish body (2 tris)
    mb.face([
        em_pt(-0.044, cy_f),           # tail pinch
        em_pt( 0.010, cy_f - 0.034),   # belly
        em_pt( 0.072, cy_f),           # fish nose
        em_pt( 0.010, cy_f + 0.036),   # dorsal arch
    ], FISH_EMBLEM, out=em_n)
    # Forked fish tail fin (2 tris)
    mb.face([
        em_pt(-0.040, cy_f),
        em_pt(-0.082, cy_f + 0.032),
        em_pt(-0.066, cy_f),
    ], FISH_EMBLEM, out=em_n)
    mb.face([
        em_pt(-0.040, cy_f),
        em_pt(-0.066, cy_f),
        em_pt(-0.082, cy_f - 0.030),
    ], FISH_EMBLEM, out=em_n)

    # =========================================================================
    # 7. NECK (3-sided front/side skin prism, back hidden by hair/collar = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.070, 1.116, -0.040), V(0.000, 1.116, 0.078), V(0.070, 1.116, -0.040)]
    n_t = [V(-0.066, 1.210, -0.038), V(0.000, 1.210, 0.072), V(0.066, 1.210, -0.038)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 8. TORSO: PAINTED PLAID FLANNEL SHIRT + ORANGE FISHING VEST + 3D PLAID COLLAR (27 tris)
    # =========================================================================
    mb.set_part("torso_vest", bone="Torso")
    # 6-sided broad-front torso with softly sloped shoulders (20 tris: 12 walls + 4 bottom + 4 top)
    sh_bot = wide_hex_ring(0.0, 0.634, 0.006, 0.228, 0.156, front_w=0.76, sh_drop=0.000)
    sh_top = wide_hex_ring(0.0, 1.138, 0.006, 0.194, 0.136, front_w=0.76, sh_drop=0.018)

    # Custom UV intervals matching generate_shirt_texture() layout (v in [0.34, 1.00]):
    # k=5: wide front [0.00..0.34], k=0: front-left [0.34..0.48], k=1: back-left [0.48..0.60],
    # k=2: back [0.60..0.74],       k=3: back-right [0.74..0.86], k=4: front-right [0.86..1.00]
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
        return [(u0, 0.34), (u1, 0.34), (u1, 0.995), (u0, 0.995)]

    mb.loft([sh_bot, sh_top], WHITE, cap_bottom=True, cap_top=True,
            bot_color=VEST_BOT, top_color=VEST_TOP,
            mat_idx=MAT_SHIRT, uv_fn=torso_uv)

    # Open shirt throat skin V-peek (1 tri) + 3D folded plaid shirt collar flaps (6 tris -> UV-mapped to plaid!)
    z_chest_top = 0.006 + 0.136 * 0.88 + 0.005
    z_chest_mid = 0.006 + (0.136 + (0.156 - 0.136) * 0.22) * 0.88 + 0.005
    mb.face([
        V(-0.044, 1.138, z_chest_top),
        V( 0.044, 1.138, z_chest_top),
        V( 0.000, 1.055, z_chest_mid),
    ], SKIN, out=(0, 0, 1))

    # Crisp folded plaid flannel shirt collar framing the throat & resting cleanly over vest top (3 quads = 6 tris)
    for side in (-1, 1):
        mb.face([
            V(side * 0.036, 1.134, z_chest_top + 0.006),
            V(side * 0.122, 1.116, z_chest_top + 0.012),
            V(side * 0.130, 1.186, 0.046),
            V(side * 0.062, 1.190, 0.072),
        ], WHITE, out=(side * 0.25, 0.35, 0.90), mat_idx=MAT_SHIRT,
                uvs=[(0.08, 0.09), (0.34, 0.09), (0.34, 0.26), (0.08, 0.26)])
    # Back collar stand (2 tris)
    mb.face([
        V(-0.118, 1.136, -0.096),
        V( 0.118, 1.136, -0.096),
        V( 0.108, 1.186, -0.086),
        V(-0.108, 1.186, -0.086),
    ], WHITE, out=(0, 0, -1), mat_idx=MAT_SHIRT,
            uvs=[(0.40, 0.10), (0.72, 0.10), (0.72, 0.25), (0.40, 0.25)])

    # =========================================================================
    # 9. LONG PLAID FLANNEL SLEEVES + CHUNKY PEACH HANDS (36 + 20 = 56 tris)
    # =========================================================================
    mb.set_part("sleeves_and_hands")

    # Right arm (-X): relaxed slightly bent arm hanging naturally by right hip
    # Left arm (+X): angled slightly forward & out so left hand holds the red looped leash clear of thigh!
    arm_specs = [
        # (side, bname,  p_sh,                            p_el,                             p_wr,                             p_hd)
        (-1, "Arm_R", V(-0.175, SHOULDER_Y, SHOULDER_Z), V(-0.262, 0.872, -0.006), V(-0.246, 0.726, 0.056), V(-0.234, 0.626, 0.072)),
        ( 1, "Arm_L", V( 0.175, SHOULDER_Y, SHOULDER_Z), V( 0.266, 0.884,  0.036), V( 0.276, 0.768, 0.118), HAND_L_GRIP),
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

        r_sh = slv_ring(p_sh, ax1, 0.076, 0.070)
        r_el = slv_ring(p_el, axm, 0.078, 0.072)
        r_wr = slv_ring(p_wr, ax2, 0.070, 0.066)

        def slv_uv(i, k):
            u0 = k * 0.25
            u1 = (k + 1) * 0.25
            # i=0: upper sleeve [0.31 -> 0.16], i=1: lower sleeve + dark cuff [0.16 -> 0.005]
            v_top = 0.315 if i == 0 else 0.160
            v_bot = 0.160 if i == 0 else 0.005
            return [(u0, v_top), (u1, v_top), (u1, v_bot), (u0, v_bot)]

        # 2 segments x 4 quads = 16 tris + cuff cap 2 tris = 18 tris per sleeve!
        mb.loft([r_sh, r_el, r_wr], WHITE, cap_bottom=False, cap_top=True,
                top_color=CUFF_DARK, mat_idx=MAT_SHIRT, uv_fn=slv_uv)

        # Chunky peach hand emerging cleanly from flannel wrist cuff (4 walls + tip cap = 10 tris per hand)
        ax_h = (p_hd - p_wr).normalized()
        p_h0 = p_wr - ax_h * 0.014  # tucked slightly inside cuff for watertight join
        p_h1 = p_hd + ax_h * 0.022
        rh0 = slv_ring(p_h0, ax_h, 0.056, 0.050)
        rh1 = slv_ring(p_h1, ax_h, 0.050, 0.046)
        mb.loft([rh0, rh1], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN)

    # =========================================================================
    # 10. RED LOOPED LEASH / ROPE STRAP + SILVER SNAP HOOK (30 + 8 = 38 tris, bone="Leash")
    # =========================================================================
    mb.set_part("leash", bone="Leash")
    # 5-point closed teardrop loop held right in left hand grip, dangling gracefully in +Z / -Y!
    gx, gy, gz = HAND_L_GRIP.x, HAND_L_GRIP.y, HAND_L_GRIP.z
    loop_pts = [
        V(gx + 0.000, gy + 0.012, gz + 0.018),  # 0: held inside chunky left hand
        V(gx + 0.016, gy - 0.068, gz + 0.104),  # 1: forward upper arch
        V(gx + 0.014, gy - 0.218, gz + 0.112),  # 2: lower forward curve
        V(gx + 0.004, gy - 0.292, gz + 0.044),  # 3: bottom teardrop apex (clip attaches here!)
        V(gx - 0.006, gy - 0.156, gz - 0.024),  # 4: back rising strand
    ]
    # Sweep a crisp chunky 3-sided triangular tube around the closed 5-segment loop (5 x 3 = 15 quads = 30 tris!)
    m_pts = len(loop_pts)
    l_center = sum(loop_pts, Vector()) / m_pts
    l_rings = []
    rad_r = 0.025
    for i in range(m_pts):
        t1 = (loop_pts[i] - loop_pts[(i - 1) % m_pts]).normalized()
        t2 = (loop_pts[(i + 1) % m_pts] - loop_pts[i]).normalized()
        tang = (t1 + t2).normalized()
        out_v = (loop_pts[i] - l_center)
        out_v = (out_v - tang * out_v.dot(tang))
        out_v = out_v.normalized() if out_v.length > 1e-5 else V(0, 0, 1)
        side_v = tang.cross(out_v).normalized()
        ring = []
        for k in range(3):
            a = 2.0 * math.pi * k / 3.0
            ring.append(loop_pts[i] + out_v * (rad_r * math.cos(a)) + side_v * (rad_r * math.sin(a)))
        l_rings.append(ring)
    l_rings.append(l_rings[0])
    mb.loft(l_rings, lambda i, k: LEASH_SHADE if k == 1 else LEASH_RED, cap_bottom=False, cap_top=False)

    # Silver metal snap hook / clasp dangling cleanly from bottom apex loop_pts[3] (8 tris!)
    clip_top = loop_pts[3] + V(0.0, 0.008, 0.0)
    clip_mid = loop_pts[3] + V(0.0, -0.052, 0.006)
    clip_bot = loop_pts[3] + V(0.0, -0.106, 0.008)
    cr_mid = oval_ring(clip_mid.x, clip_mid.y, clip_mid.z, 0.024, 0.030, n=4, phase=0.0)
    for k in range(4):
        kn = (k + 1) % 4
        col = CLIP_SHADE if k in (1, 2) else CLIP_SILVER
        mb.face([clip_top, cr_mid[kn], cr_mid[k]], col, out=(cr_mid[k] + cr_mid[kn]) * 0.5 - clip_mid + V(0, 0.02, 0))
        mb.face([clip_bot, cr_mid[k], cr_mid[kn]], col, out=(cr_mid[k] + cr_mid[kn]) * 0.5 - clip_mid + V(0, -0.02, 0))

    # =========================================================================
    # 11. KHAKI CARGO PANTS + 3D SIDE CARGO POCKETS (8 + 20 + 12 = 40 tris)
    # =========================================================================
    mb.set_part("cargo_pants", bone="Root")
    mb.box(-0.194, 0.194, 0.542, 0.668, -0.118, 0.118, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        # Relaxed wide-leg khaki trousers flaring slightly toward ankle hem (matches reference!)
        x_in_t, x_out_t = side * 0.008, side * 0.192
        x_in_b, x_out_b = side * 0.036, side * 0.228
        rz_t, rz_b = 0.106, 0.116
        r_top = [
            V(min(x_in_t, x_out_t), 0.592,  rz_t),
            V(max(x_in_t, x_out_t), 0.592,  rz_t),
            V(max(x_in_t, x_out_t), 0.592, -rz_t),
            V(min(x_in_t, x_out_t), 0.592, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.136,  rz_b),
            V(max(x_in_b, x_out_b), 0.136,  rz_b),
            V(max(x_in_b, x_out_b), 0.136, -rz_b),
            V(min(x_in_b, x_out_b), 0.136, -rz_b),
        ]
        mb.loft([r_bot, r_top], lambda i, k: PANTS_SHADE if k == 2 else PANTS,
                cap_bottom=True, cap_top=False, bot_color=PANTS_INNER)

        # Crisp 3D outer-thigh khaki cargo pocket (6 tris per leg = 12 tris total!)
        # Slopes cleanly along outer trouser wall between y=0.33 and y=0.47
        t_lo = (0.330 - 0.136) / (0.592 - 0.136)
        t_hi = (0.475 - 0.136) / (0.592 - 0.136)
        x_wall_lo = x_out_b * (1.0 - t_lo) + x_out_t * t_lo
        x_wall_hi = x_out_b * (1.0 - t_hi) + x_out_t * t_hi
        x_pk_lo = x_wall_lo + side * 0.024
        x_pk_hi = x_wall_hi + side * 0.018
        pz0, pz1 = -0.068, 0.068
        # Outer pocket face (2 tris)
        p_fb = V(x_pk_lo, 0.330, pz1); p_bb = V(x_pk_lo, 0.330, pz0)
        p_bt = V(x_pk_hi, 0.475, pz0); p_ft = V(x_pk_hi, 0.475, pz1)
        w_fb = V(x_wall_lo, 0.330, pz1); w_bb = V(x_wall_lo, 0.330, pz0)
        w_bt = V(x_wall_hi, 0.475, pz0); w_ft = V(x_wall_hi, 0.475, pz1)
        mb.face([p_bb, p_fb, p_ft, p_bt], PANTS_LIGHT, out=(side, 0, 0))
        # Bottom overhang lip (2 tris) & front/back edges (1 quad front or 2 tapered tris? 2 quads = 4 tris?
        # Keep to 6 tris/pocket: outer quad (2) + bottom quad (2) + front/back bevel tris (2) = 6 tris!)
        mb.face([w_bb, w_fb, p_fb, p_bb], PANTS_SHADE, out=(0, -1, 0))
        mb.face([w_fb, w_ft, p_fb], PANTS_SHADE, out=(0, 0, 1))
        mb.face([w_bt, w_bb, p_bb], PANTS_SHADE, out=(0, 0, -1))

    # =========================================================================
    # 12. CHUNKY BROWN WORK BOOTS WITH DARK SOLES (2 x 18 = 36 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.132
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

    # Slot 1: Painted Plaid Flannel Shirt & Orange Fishing Vest material
    mat_shirt = bpy.data.materials.new("FishermanShirtVest")
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
    """24-frame looping Walk cycle: sturdy seaworthy harbor stroll with swinging arms and dangling leash."""
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

        # Sturdy, unhurried maritime stride with gentle double-frequency bob & hip roll
        pb_root = rig.pose.bones["Root"]
        bob = -0.024 * (1.0 - c2) * 0.5
        root_pitch = -0.048
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.072 * s1, 0.040 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Natural torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.020 * c2, 0.096 * s1, -0.026 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Steady weathered gaze forward along the dock
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.038 + 0.020 * c2, -0.040 * s1, -0.018 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating stride with clean boot lift so soles stay above ground on swing
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.43 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.036, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.43 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.036, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Counter-swinging arms: right arm swings freely, left arm carries red leash slightly forward clear of thigh!
        arm_l_rx = 0.14 * s1 - 0.11
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_rx, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.28 * s1 - 0.02, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Secondary pendulum physics on Leash (child of Arm_L): stays vertical with gentle phase-lagged swing!
        leash_rx = -0.72 * arm_l_rx + 0.14 * math.sin(phi - 0.65)
        leash_rz = -0.050 * math.cos(phi - 0.50)
        pb_leash = rig.pose.bones["Leash"]
        pb_leash.rotation_euler = (leash_rx, 0.0, leash_rz)
        pb_leash.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: calm dockside breathing, harbor scan, gentle leash sway."""
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

        # Relaxed dockside weight shift & steady breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.010, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.032 * s1, -0.016 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Leisurely harbor look-around scanning boats & tide
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * s2 - 0.015, 0.26 * s1, 0.036 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Boots firmly planted on the dock
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Soft breathing arm drift
        arm_l_rx = 0.045 * s1 - 0.020 * s2
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_rx, 0.0, 0.014 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.042 * s1 - 0.016 * s2, 0.0, -0.014 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle breeze pendulum sway on the red leash & silver clip
        pb_leash = rig.pose.bones["Leash"]
        pb_leash.rotation_euler = (-0.55 * arm_l_rx + 0.048 * math.sin(phi - 0.55), 0.0, -0.040 * math.cos(phi - 0.40))
        pb_leash.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Leash) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonFishermanRig")
    rig = bpy.data.objects.new("PersonFishermanRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.600,  0.000), ( 0.000, 0.700,  0.000)),
        ("Torso", "Root",  ( 0.000, 0.665,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",  "Torso", ( 0.000, 1.160,  0.000), ( 0.000, 1.480,  0.000)),
        ("Arm_L", "Torso", ( 0.175, SHOULDER_Y, SHOULDER_Z), ( 0.175, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Arm_R", "Torso", (-0.175, SHOULDER_Y, SHOULDER_Z), (-0.175, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Leash", "Arm_L", tuple(HAND_L_GRIP),               (HAND_L_GRIP.x, HAND_L_GRIP.y + 0.140, HAND_L_GRIP.z)),
        ("Leg_L", "Root",  ( 0.112, 0.560,  0.000),          ( 0.112, 0.720,  0.000)),
        ("Leg_R", "Root",  (-0.112, 0.560,  0.000),          (-0.112, 0.720,  0.000)),
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
        (-2.55, math.radians(60)),   # Front-3/4 matching reference angle (facing right)
        (-0.85, math.radians(0)),    # Front
        ( 0.85, math.radians(90)),   # Side
        ( 2.55, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 7.2
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.5, 1.32)
    direction = Vector((0.0, 0.0, 0.92)) - cam_obj.location
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.62
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 10.2
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -7.5, 1.32)
    direction = Vector((0.0, 0.0, 0.92)) - cam_obj.location
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
    cam_data.ortho_scale = 3.8
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 1.32)
    direction = Vector((0.0, 0.0, 0.92)) - cam_obj.location
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
            left_obj.location = (-0.88, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.88, 0.0, 0.0)
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
# Hair and mustache stay silver: he is an elder.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "top": [VEST_TOP, VEST_BOT],
    "bottom": [PANTS, PANTS_SHADE, PANTS_LIGHT, PANTS_INNER],
    "accent": [CAP_CROWN, CAP_TOP, CAP_BRIM, CAP_UNDER],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonFisherman")
    bpy.context.scene.collection.children.link(coll)

    shirt_img = generate_shirt_texture(SHIRT_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonFisherman")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(shirt_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonFisherman", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris < 350, f"Triangle budget exceeded: {total_tris} >= 350"

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    # Export GLB with both Walk and Idle animations + embedded texture via ACTIONS mode
    os.makedirs(os.path.dirname(GLB_PATH), exist_ok=True)
    for o in bpy.data.objects:
        o.select_set(o in (rig, ob))
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_selection=True,
        export_normals=True,
        export_texcoords=True,
        export_vertex_color="ACTIVE",
        export_materials="EXPORT",
        export_yup=True,
        export_skins=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
    )

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=60)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=44)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=56, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=44, zrot_right_deg=90)

    print("=== PersonFisherman Stats ===")
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
