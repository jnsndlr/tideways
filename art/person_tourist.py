# Builds an ultra-low-poly (< 450 tris) stylized tourist with safari hat, silver hair,
# sunglasses, painted Hawaiian shirt, olive backpack, open painted map, khaki shorts, and walking shoes in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_tourist.py)
# Saves art/person_tourist.blend, exports assets/models/person_tourist.glb (rigged + Walk & Idle cycles + embedded textures),
# renders art/person_tourist_preview.png, art/person_tourist_walk_preview.png, art/person_tourist_idle_preview.png,
# and outputs rendered videos art/person_tourist_walk.mp4 and art/person_tourist_idle.mp4.
#
# Strict triangle budget: < 450 triangles.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_tourist.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_tourist.glb")
SHIRT_TEX_PATH = os.path.join(ROOT, "art", "person_tourist_shirt_tex.png")
MAP_TEX_PATH = os.path.join(ROOT, "art", "person_tourist_map_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_tourist_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_tourist_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_tourist_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_tourist_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_tourist_idle.mp4")

MAT_VCOL = 0
MAT_SHIRT = 1
MAT_MAP = 2


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference tourist image (sRGB -> linear)
WHITE          = (1.0, 1.0, 1.0, 1.0)

SKIN           = col_srgb(0.96, 0.72, 0.47)
SKIN_SHADE     = col_srgb(0.85, 0.59, 0.37)

HAIR           = col_srgb(0.82, 0.82, 0.83)
HAIR_SHADE     = col_srgb(0.68, 0.68, 0.70)
BROW           = col_srgb(0.86, 0.86, 0.87)

HAT_CROWN      = col_srgb(0.86, 0.77, 0.63)
HAT_TOP        = col_srgb(0.90, 0.81, 0.68)
HAT_BRIM       = col_srgb(0.83, 0.73, 0.59)
HAT_UNDER      = col_srgb(0.61, 0.52, 0.40)

SUN_FRAME      = col_srgb(0.14, 0.14, 0.15)
SUN_LENS       = col_srgb(0.21, 0.20, 0.20)

SHIRT_COLLAR   = col_srgb(0.39, 0.55, 0.73)
SHIRT_SHADE    = col_srgb(0.27, 0.41, 0.58)

PACK_MAIN      = col_srgb(0.45, 0.49, 0.36)
PACK_LIGHT     = col_srgb(0.51, 0.55, 0.41)
PACK_DARK      = col_srgb(0.35, 0.38, 0.27)
PACK_BASE      = col_srgb(0.24, 0.24, 0.23)
STRAP          = col_srgb(0.26, 0.26, 0.25)

MAP_EDGE       = col_srgb(0.90, 0.87, 0.80)

SHORTS         = col_srgb(0.80, 0.71, 0.57)
SHORTS_SHADE   = col_srgb(0.69, 0.60, 0.47)
SHORTS_INNER   = col_srgb(0.51, 0.44, 0.34)

SHOE           = col_srgb(0.45, 0.33, 0.25)
SHOE_SHADE     = col_srgb(0.36, 0.26, 0.19)
SOLE           = col_srgb(0.25, 0.19, 0.16)


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared anchor coordinates so arms, hands, and open folded map align identically
SHOULDER_Y = 1.076
SHOULDER_Z = 0.008
MAP_PIVOT = V(0.0, 0.880, 0.290)


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def _paint_tropical_leaf(img, uu, vv, cx, cy, scale_u, scale_v, angle_deg,
                         col_main=(0.91, 0.88, 0.81), col_stem=(0.82, 0.79, 0.72), wrap_u=False):
    """Paint a bold stylized 5-frond cream Hawaiian palm/leaf spray using smooth analytical SDFs."""
    du = uu - cx
    if wrap_u:
        du = ((du + 0.5) % 1.0) - 0.5
    dv = vv - cy
    rad = math.radians(angle_deg)
    ca, sa = math.cos(rad), math.sin(rad)
    # Local coordinates normalized by scale
    lx = (du * ca - dv * sa) / scale_u
    ly = (du * sa + dv * ca) / scale_v

    # 5 radiating rounded botanical palm/leaf fronds fanning cleanly from base (0, -0.34)
    fronds = [
        (-66.0, 0.72, 0.165),
        (-34.0, 0.90, 0.172),
        (  0.0, 1.00, 0.180),
        ( 34.0, 0.90, 0.172),
        ( 66.0, 0.72, 0.165),
    ]
    base_y = -0.34
    mask = np.zeros_like(lx, dtype=np.float32)
    stem_mask = np.zeros_like(lx, dtype=np.float32)

    # Small rounded stem knot at base
    d_base = np.sqrt((lx / 0.16) ** 2 + ((ly - base_y) / 0.15) ** 2)
    mask = np.maximum(mask, np.clip((1.0 - d_base) * 8.0, 0.0, 1.0))

    for (f_deg, length, width) in fronds:
        fa = math.radians(f_deg)
        fx, fy = math.sin(fa), math.cos(fa)
        dx = lx
        dy = ly - base_y
        t = dx * fx + dy * fy
        p = -dx * fy + dy * fx
        # Soft rounded botanical leaf lobe (full rounded tip, cleanly separated fronds!)
        tn = np.clip(t / length, 0.0, 1.0)
        w_prof = width * (0.30 + 0.85 * np.maximum(0.0, np.sin(tn * math.pi)) ** 0.55)
        t_clamped = np.clip(t, 0.0, length * 0.94)
        dist = np.sqrt((t - t_clamped) ** 2 + (p / np.maximum(w_prof / width, 0.22)) ** 2)
        m = np.clip((width * 0.86 - dist) / 0.032 + 0.5, 0.0, 1.0)
        mask = np.maximum(mask, m)
        vein = m * np.clip(1.0 - tn * 1.8, 0.0, 1.0) * np.clip(1.0 - np.abs(p) / (width * 0.40), 0.0, 1.0)
        stem_mask = np.maximum(stem_mask, vein * 0.50)

    img = _blend_mask(img, mask, col_main)
    img = _blend_mask(img, stem_mask, col_stem)
    return img


def generate_shirt_texture(out_path):
    """Paint a 512x512 sRGB Hawaiian shirt texture (torso wrap top 70%, sleeves bottom 30%)."""
    w, h = 512, 512
    # u in [0, 1] left->right, v in [0, 1] bottom->top
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Soft coastal denim-blue base matched to reference
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[..., 0] = 0.365
    img[..., 1] = 0.515
    img[..., 2] = 0.700

    # Subtle vertical-to-hem shading & gentle cloth warmth
    torso_v = np.clip((vv - 0.30) / 0.70, 0.0, 1.0)
    shade = 0.93 + 0.09 * torso_v
    img *= shade[..., None]

    # Very subtle horizontal fabric weave
    weave = 1.0 + 0.012 * np.sin(vv * 220.0) + 0.008 * np.sin(uu * 240.0)
    img *= weave[..., None]

    # Slightly darker band along sleeve region (v < 0.30) cuff bottom edge
    cuff_edge = np.clip((0.035 - vv) / 0.025, 0.0, 1.0)
    img = _blend_mask(img, cuff_edge * 0.55, (0.24, 0.37, 0.53))

    # Subtle bottom hem shadow on torso (v near 0.30..0.335)
    hem_band = np.clip((0.330 - vv) / 0.020, 0.0, 1.0) * (vv >= 0.30).astype(np.float32)
    img = _blend_mask(img, hem_band * 0.45, (0.25, 0.38, 0.55))

    # --- Paint bold cream Hawaiian leaf sprays across the TORSO (v in [0.30, 1.00]) ---
    # UV mapping around 6-sided torso:
    #   u = 0.00..0.24: front-right -> front-center (placket at u = 0.167) -> front-left
    #   Actually let's map k=5 (front flat face) cleanly to u in [0.00, 0.25], center front = 0.125!
    #   k=0 (front-left)  : [0.25, 0.40]
    #   k=1 (back-left)   : [0.40, 0.55]
    #   k=2 (back center) : [0.55, 0.75]
    #   k=3 (back-right)  : [0.75, 0.88]
    #   k=4 (front-right) : [0.88, 1.00]
    torso_leaves = [
        # (u,     v,     su,    sv,    rot_deg)
        # Front lower-right & lower-left (super prominent right below the map like reference!)
        (0.055, 0.415, 0.072, 0.125, -14.0),
        (0.205, 0.435, 0.070, 0.120,  16.0),
        # Front upper chest flanks (peeking beside collar & backpack straps)
        (0.045, 0.785, 0.062, 0.110,  18.0),
        (0.215, 0.770, 0.064, 0.112, -16.0),
        # Front-left side panel (k=0)
        (0.335, 0.590, 0.068, 0.118,  12.0),
        (0.325, 0.865, 0.058, 0.098, -22.0),
        # Back-left & back center (peeking around olive backpack!)
        (0.485, 0.445, 0.068, 0.118, -10.0),
        (0.650, 0.420, 0.072, 0.122,  14.0),
        (0.640, 0.780, 0.068, 0.115, -18.0),
        # Back-right & front-right side panel (k=3, 4 - facing reference 3/4 camera!)
        (0.820, 0.450, 0.068, 0.118,  16.0),
        (0.935, 0.620, 0.068, 0.118, -14.0),
        (0.920, 0.870, 0.058, 0.098,  20.0),
    ]
    for (lu, lv, su, sv, ang) in torso_leaves:
        img = _paint_tropical_leaf(img, uu, vv, lu, lv, su, sv, ang, wrap_u=True)

    # Crisp center front shirt button placket line & subtle coconut buttons at u = 0.125
    placket = np.clip((0.0055 - np.abs(uu - 0.125)) / 0.002, 0.0, 1.0) * (vv >= 0.30).astype(np.float32) * (vv <= 0.84).astype(np.float32)
    img = _blend_mask(img, placket * 0.45, (0.24, 0.37, 0.54))
    for by in (0.41, 0.56, 0.71):
        bd = np.sqrt(((uu - 0.125) / 0.009) ** 2 + ((vv - by) / 0.015) ** 2)
        bmask = np.clip((1.0 - bd) * 6.0, 0.0, 1.0)
        img = _blend_mask(img, bmask, (0.76, 0.71, 0.61))

    # --- Paint bold cream Hawaiian leaf sprays on SLEEVE STRIP (v in [0.00, 0.28]) ---
    # Each sleeve wraps u in [0, 1], with outer face centered at u = 0.375 (and back/front around 0.125, 0.625)
    sleeve_leaves = [
        (0.14, 0.155, 0.088, 0.098,  18.0),
        (0.38, 0.150, 0.098, 0.108, -10.0),  # Hero leaf right on outer sleeve facing 3/4 view!
        (0.64, 0.160, 0.088, 0.098,  22.0),
        (0.88, 0.145, 0.084, 0.095, -16.0),
    ]
    for (lu, lv, su, sv, ang) in sleeve_leaves:
        # Mask strictly inside sleeve strip v < 0.285 so leaves don't bleed onto torso hem
        before = img.copy()
        painted = _paint_tropical_leaf(img, uu, vv, lu, lv, su, sv, ang, wrap_u=True)
        in_strip = (vv < 0.285).astype(np.float32)[..., None]
        img = before * (1.0 - in_strip) + painted * in_strip

    img = np.clip(img, 0.0, 1.0)
    bimg = bpy.data.images.new("TouristShirtTex", width=w, height=h, alpha=True, float_buffer=False)
    bimg.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = img
    # img is already v=0 at index 0 (bottom) -> matches Blender's bottom-to-top pixel layout directly!
    bimg.pixels.foreach_set(rgba.ravel())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bimg.filepath_raw = out_path
    bimg.file_format = "PNG"
    bimg.save()
    bimg.pack()
    return bimg


def generate_map_texture(out_path):
    """Paint a 512x512 sRGB stylized folded tourist map matching the reference artwork."""
    w, h = 512, 512
    # u in [0, 1] left->right across both map panels, v in [0, 1] bottom->top
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # 1. Soft sage-cream map parchment sky/land backdrop
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[..., 0] = 0.78 + 0.04 * vv
    img[..., 1] = 0.83 + 0.03 * vv
    img[..., 2] = 0.72 + 0.03 * vv

    # 2. Warm coral-terracotta sun/landmark disc on right panel (matches reference top-right orange accent!)
    d_sun = np.sqrt(((uu - 0.79) / 0.068) ** 2 + ((vv - 0.72) / 0.088) ** 2)
    img = _blend_mask(img, np.clip((1.0 - d_sun) * 8.0, 0.0, 1.0), (0.81, 0.59, 0.44))

    # 3. Stylized faceted green mountains across upper-middle (3 overlapping low-poly peaks)
    # Peak A (left olive-green hill with white snow peak tip)
    m1_top = 0.67 - np.abs(uu - 0.25) * 1.65
    m1_mask = np.clip((m1_top - vv) * 70.0, 0.0, 1.0) * (vv > 0.34).astype(np.float32)
    img = _blend_mask(img, m1_mask, (0.42, 0.56, 0.38))
    # Bright cream/white snow cap on left peak (iconic detail from reference!)
    snow1 = np.clip((m1_top - vv) * 70.0, 0.0, 1.0) * np.clip((vv - (0.57 + 0.03 * np.sin(uu * 35.0))) * 70.0, 0.0, 1.0)
    img = _blend_mask(img, snow1, (0.93, 0.91, 0.86))

    # Peak B (tall hero center emerald mountain spanning left of fold)
    m2_top = 0.78 - np.abs(uu - 0.45) * 1.72
    m2_mask = np.clip((m2_top - vv) * 70.0, 0.0, 1.0) * (vv > 0.34).astype(np.float32)
    # Sunlit left slope vs deeper shaded right slope
    m2_left = m2_mask * (uu <= 0.45).astype(np.float32)
    m2_right = m2_mask * (uu > 0.45).astype(np.float32)
    img = _blend_mask(img, m2_left, (0.46, 0.64, 0.42))
    img = _blend_mask(img, m2_right, (0.35, 0.52, 0.34))

    # Peak C (right darker pine-green mountain ridge on right panel)
    m3_top = 0.68 - np.abs(uu - 0.71) * 1.48
    m3_mask = np.clip((m3_top - vv) * 70.0, 0.0, 1.0) * (vv > 0.30).astype(np.float32)
    m3_left = m3_mask * (uu <= 0.71).astype(np.float32)
    m3_right = m3_mask * (uu > 0.71).astype(np.float32)
    img = _blend_mask(img, m3_left, (0.39, 0.55, 0.37))
    img = _blend_mask(img, m3_right, (0.31, 0.46, 0.31))

    # 4. Warm golden-yellow rolling meadow / sandy peninsula below mountains
    coast_top = 0.44 + 0.065 * np.sin(uu * 5.2 - 0.4) + 0.03 * np.cos(uu * 9.5)
    land_mask = np.clip((coast_top - vv) * 65.0, 0.0, 1.0)
    # Warm yellow-gold on left/center blending gently to olive-ochre on right
    ochre_t = np.clip((uu - 0.52) * 2.4, 0.0, 1.0)
    land_r = 0.85 * (1.0 - ochre_t) + 0.67 * ochre_t
    land_g = 0.77 * (1.0 - ochre_t) + 0.66 * ochre_t
    land_b = 0.47 * (1.0 - ochre_t) + 0.42 * ochre_t
    land_col = np.stack([land_r, land_g, land_b], axis=-1)
    img = img * (1.0 - land_mask[..., None]) + land_col * land_mask[..., None]

    # 5. Coastal blue bay / ocean water sweeping across bottom ~28%
    water_top = 0.27 + 0.055 * np.sin(uu * 4.6 + 0.8) - 0.035 * np.exp(-((uu - 0.74) / 0.14) ** 2)
    water_mask = np.clip((water_top - vv) * 65.0, 0.0, 1.0)
    # Subtle lighter turquoise coastal shore edge
    shore_band = np.clip((water_top + 0.022 - vv) * 65.0, 0.0, 1.0) * (1.0 - water_mask)
    img = _blend_mask(img, shore_band * 0.55, (0.58, 0.73, 0.78))
    img = _blend_mask(img, water_mask, (0.38, 0.56, 0.74))

    # Subtle gentle wave highlight lines in the blue water
    wave_y = 0.17 + 0.012 * np.sin(uu * 18.0)
    wave_m = np.clip((0.008 - np.abs(vv - wave_y)) / 0.004, 0.0, 1.0) * water_mask * (uu > 0.14).astype(np.float32) * (uu < 0.44).astype(np.float32)
    img = _blend_mask(img, wave_m * 0.45, (0.64, 0.78, 0.89))

    # 6. Cute red/terracotta trail dots & small X destination marker
    trail_pts = [
        (0.24, 0.30), (0.31, 0.34), (0.39, 0.37), (0.47, 0.38),
        (0.55, 0.36), (0.63, 0.37), (0.70, 0.42),
    ]
    for (tx, ty) in trail_pts:
        dt = np.sqrt(((uu - tx) / 0.011) ** 2 + ((vv - ty) / 0.013) ** 2)
        img = _blend_mask(img, np.clip((1.0 - dt) * 6.0, 0.0, 1.0) * 0.85, (0.76, 0.36, 0.27))

    # 7. Crisp warm cream/white paper border around all 4 edges (6.5% margin)
    mx, my = 0.062, 0.068
    in_x = np.clip((uu - mx) * 140.0, 0.0, 1.0) * np.clip((1.0 - mx - uu) * 140.0, 0.0, 1.0)
    in_y = np.clip((vv - my) * 140.0, 0.0, 1.0) * np.clip((1.0 - my - vv) * 140.0, 0.0, 1.0)
    border_mask = 1.0 - (in_x * in_y)
    img = _blend_mask(img, border_mask, (0.94, 0.91, 0.85))

    # 8. Subtle vertical center fold crease shadow right at u = 0.50
    crease = np.exp(-((uu - 0.50) / 0.018) ** 2) * 0.16
    img *= (1.0 - crease)[..., None]

    img = np.clip(img, 0.0, 1.0)
    bimg = bpy.data.images.new("TouristMapTex", width=w, height=h, alpha=True, float_buffer=False)
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
        # Textured materials use pure white vertex color so glTF COLOR_0 * baseColorTexture is untinted!
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


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=8, phase=math.pi / 8.0):
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
    # 1. HEAD (6-sided stylized low-poly head, flat front face, 28 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.196,  0.018, 0.156, 0.150),  # 0: chin/jaw
        (1.286,  0.022, 0.212, 0.204),  # 1: lower cheek
        (1.488,  0.010, 0.206, 0.198),  # 2: brow / tucked inside safari hat
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        # Front face (k=5) and front-side cheeks (k=0, 4) are warm peach skin;
        # behind ears and back of head (k=1, 2, 3) are silver-gray hair!
        return SKIN if k in (4, 5, 0) else HAIR

    mb.loft(head_rings, head_color, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # =========================================================================
    # 2. TRIM SILVER-GRAY HAIR WRAP + EYEBROW WISPS (20 + 4 = 24 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # Neat low-poly silver hair puff rounding out behind ears and nape cleanly under safari hat brim
    hair_angles = [math.radians(a) for a in (82, 132, 180, 228, 278)]
    hair_specs = [
        # (y,     rx,    rz,    cz)
        (1.216, 0.184, 0.192, -0.016),  # 0: trim lower nape
        (1.320, 0.222, 0.228, -0.022),  # 1: fuller sculpted back-of-head volume
        (1.442, 0.206, 0.204, -0.010),  # 2: tucked strictly below safari hat brim (zero poke-through!)
    ]
    h_rings = []
    for (y, rx, rz, cz) in hair_specs:
        ring = []
        for a in hair_angles:
            back_boost = 1.0 + 0.06 * max(0.0, -math.cos(a))
            ring.append(V(rx * back_boost * math.sin(a), y, cz + rz * back_boost * math.cos(a)))
        h_rings.append(ring)

    # Outer silver hair walls (4 segs x 2 bands = 16 tris)
    for i in range(2):
        r0, r1 = h_rings[i], h_rings[i + 1]
        col = HAIR_SHADE if i == 0 else HAIR
        for k in range(4):
            p0, p1, p2, p3 = r0[k], r0[k + 1], r1[k + 1], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], col, out=V(mid.x, 0.0, mid.z))

    # Crisp bottom nape tuck (2 quads = 4 tris, merging seamlessly into neck/head)
    rb_h = h_rings[0]
    for k in range(2):
        p0 = rb_h[k * 2]
        p1 = rb_h[k * 2 + 1]
        p2 = rb_h[k * 2 + 2]
        mb.face([p2, p1, p0, V(p0.x * 0.55, 1.214, p0.z * 0.55)], HAIR_SHADE, out=(0, -1, 0))

    # Two subtle silver-gray eyebrow wisps peeking just above sunglasses under hat brim (4 tris)
    for side in (-1, 1):
        cx = side * 0.068
        mb.face([
            V(cx - 0.030, 1.444, 0.194),
            V(cx + 0.030, 1.444, 0.194),
            V(cx + 0.026, 1.462, 0.192),
            V(cx - 0.026, 1.462, 0.192),
        ], BROW, out=(0, 0, 1))

    # =========================================================================
    # 3. EARS (2 compact rounded low-poly peach wedges = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.196
        x_out = side * 0.238
        y0, y1 = 1.300, 1.384
        z0, z1 = 0.002, 0.066
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_tip], SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. NECK (3-sided sturdy front/side prism, skip rear hidden by hair = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.072, 1.118, -0.042), V(0.000, 1.118, 0.078), V(0.072, 1.118, -0.042)]
    n_t = [V(-0.068, 1.210, -0.040), V(0.000, 1.210, 0.072), V(0.068, 1.210, -0.040)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 5. WAYFARER DARK SUNGLASSES (brow bar + 2 chunky dark lenses + temples = 30 tris)
    # =========================================================================
    mb.set_part("sunglasses", bone="Head")
    z_bk = 0.194
    z_fr = 0.216
    y_top = 1.428
    y_br  = 1.406

    # Continuous sleek Wayfarer top brow bar + nose bridge (front + top + underside = 6 tris)
    mb.face([V(-0.138, y_br, z_fr), V(0.138, y_br, z_fr), V(0.144, y_top, z_fr), V(-0.144, y_top, z_fr)],
            SUN_FRAME, out=(0, 0, 1))
    mb.face([V(-0.144, y_top, z_fr), V(0.144, y_top, z_fr), V(0.138, y_top, z_bk), V(-0.138, y_top, z_bk)],
            SUN_FRAME, out=(0, 1, 0))
    mb.face([V(-0.024, y_br, z_bk), V(0.024, y_br, z_bk), V(0.024, y_br, z_fr), V(-0.024, y_br, z_fr)],
            SUN_FRAME, out=(0, -1, 0))

    # Two chunky tapered Wayfarer dark lenses (each: front + outer + bottom + inner bevel = 8 tris -> 16 tris)
    for side in (-1, 1):
        x_in_t  = side * 0.017
        x_out_t = side * 0.134
        x_in_b  = side * 0.030
        x_out_b = side * 0.118
        y_bot   = 1.334

        if side > 0:
            pf = [V(x_in_b, y_bot, z_fr), V(x_out_b, y_bot, z_fr), V(x_out_t, y_br, z_fr), V(x_in_t, y_br, z_fr)]
            pb = [V(x_in_b, y_bot, z_bk), V(x_out_b, y_bot, z_bk), V(x_out_t, y_br, z_bk), V(x_in_t, y_br, z_bk)]
        else:
            pf = [V(x_out_b, y_bot, z_fr), V(x_in_b, y_bot, z_fr), V(x_in_t, y_br, z_fr), V(x_out_t, y_br, z_fr)]
            pb = [V(x_out_b, y_bot, z_bk), V(x_in_b, y_bot, z_bk), V(x_in_t, y_br, z_bk), V(x_out_t, y_br, z_bk)]

        # Dark tinted front lens quad
        mb.face(pf, SUN_LENS, out=(0, 0, 1))
        # Chunky black frame bottom & outer & inner rim
        mb.face([pb[0], pb[1], pf[1], pf[0]], SUN_FRAME, out=(0, -1, 0))
        if side > 0:
            mb.face([pf[1], pb[1], pb[2], pf[2]], SUN_FRAME, out=( 1, 0, 0))
            mb.face([pb[0], pf[0], pf[3], pb[3]], SUN_FRAME, out=(-1, 0, 0))
        else:
            mb.face([pb[0], pf[0], pf[3], pb[3]], SUN_FRAME, out=(-1, 0, 0))
            mb.face([pf[1], pb[1], pb[2], pf[2]], SUN_FRAME, out=( 1, 0, 0))

    # Two sleek black temple arms stretching straight back over ears into hair (4 tris x 2 = 8 tris)
    for side in (-1, 1):
        x_f = side * 0.136
        x_b = side * 0.220
        y_t0, y_t1 = y_br + 0.002, y_top - 0.002
        z_tf, z_tb = z_bk + 0.012, 0.015
        t_in = side * (-0.012)
        p0 = V(x_f, y_t0, z_tf); p1 = V(x_f, y_t1, z_tf)
        q0 = V(x_b, y_t0, z_tb); q1 = V(x_b, y_t1, z_tb)
        p1i = V(x_f + t_in, y_t1, z_tf); q1i = V(x_b + t_in, y_t1, z_tb)
        mb.face([p0, q0, q1, p1],   SUN_FRAME, out=(side, 0, 0))
        mb.face([p1, q1, q1i, p1i], SUN_FRAME, out=(0, 1, 0))

    # =========================================================================
    # 6. WIDE-BRIMMED KHAKI SAFARI HAT (8-sided crown + double-sided brim = 54 tris)
    # =========================================================================
    mb.set_part("safari_hat", bone="Head")
    hat_tilt = math.radians(6.5)  # crisp jaunty safari hat tilt clearing back hair completely
    # 8-sided tapered flat-top safari crown (16 walls + 6 flat top cap = 22 tris)
    cr_bot = tilted_ring(0.0, 1.488, -0.002, 0.236, 0.244, hat_tilt, n=8, phase=math.pi / 8.0)
    cr_top = tilted_ring(0.0, 1.668, -0.014, 0.178, 0.186, hat_tilt, n=8, phase=math.pi / 8.0)
    mb.loft([cr_bot, cr_top], HAT_CROWN, cap_bottom=False, cap_top=True, top_color=HAT_TOP)

    # Wide flared octagonal brim sloping gently downward (16 top + 16 underside = 32 tris)
    brim_in_top = tilted_ring(0.0, 1.494, -0.002, 0.232, 0.240, hat_tilt, n=8, phase=math.pi / 8.0)
    brim_in_bot = tilted_ring(0.0, 1.476, -0.002, 0.205, 0.212, hat_tilt, n=8, phase=math.pi / 8.0)
    brim_outer  = tilted_ring(0.0, 1.448,  0.002, 0.376, 0.394, hat_tilt, n=8, phase=math.pi / 8.0)

    for k in range(8):
        kn = (k + 1) % 8
        # Upper brim surface
        mb.face([brim_in_top[k], brim_in_top[kn], brim_outer[kn], brim_outer[k]],
                HAT_BRIM, out=(0, 1, 0))
        # Shaded underside brim surface
        mb.face([brim_outer[k], brim_outer[kn], brim_in_bot[kn], brim_in_bot[k]],
                HAT_UNDER, out=(0, -1, 0))

    # =========================================================================
    # 7. PAINTED BLUE HAWAIIAN SHIRT TORSO + OPEN COLLAR + SHORT SLEEVES (48 tris)
    # =========================================================================
    mb.set_part("hawaiian_shirt", bone="Torso")
    # 6-sided relaxed untucked Hawaiian shirt overhanging shorts (20 tris: 12 walls + 4 top + 4 bot)
    # phase = pi/6 -> k=5 is wide flat front face (+Z), k=0 front-left, k=1 back-left, k=2 back, k=3 back-right, k=4 front-right
    sh_bot = oval_ring(0.0, 0.642, 0.006, 0.228, 0.152, n=6, phase=math.pi / 6.0)
    sh_top = oval_ring(0.0, 1.144, 0.006, 0.202, 0.136, n=6, phase=math.pi / 6.0)

    # Custom UV intervals matching generate_shirt_texture() layout (v in [0.30, 1.00]):
    # k=5: front [0.00..0.25], k=0: front-left [0.25..0.40], k=1: back-left [0.40..0.55],
    # k=2: back [0.55..0.75],  k=3: back-right [0.75..0.88], k=4: front-right [0.88..1.00]
    torso_u_spans = {
        5: (0.00, 0.25),
        0: (0.25, 0.40),
        1: (0.40, 0.55),
        2: (0.55, 0.75),
        3: (0.75, 0.88),
        4: (0.88, 1.00),
    }

    def shirt_torso_uv(i, k):
        u0, u1 = torso_u_spans[k]
        return [(u0, 0.30), (u1, 0.30), (u1, 0.99), (u0, 0.99)]

    mb.loft([sh_bot, sh_top], WHITE, cap_bottom=True, cap_top=True,
            bot_color=SHIRT_SHADE, top_color=SHIRT_COLLAR,
            mat_idx=MAT_SHIRT, uv_fn=shirt_torso_uv)

    # Open camp-collar V-neck chest skin peek (1 tri) + folded blue collar lapels (4 tris)
    # On 6-sided phase=pi/6, flat front face Z is cz + rz * cos(30 deg)
    z_chest_top = 0.006 + 0.136 * math.cos(math.pi / 6.0) + 0.005
    z_chest_mid = 0.006 + (0.136 + (0.152 - 0.136) * 0.24) * math.cos(math.pi / 6.0) + 0.005
    mb.face([
        V(-0.062, 1.144, z_chest_top),
        V( 0.062, 1.144, z_chest_top),
        V( 0.000, 1.012, z_chest_mid),
    ], SKIN, out=(0, 0, 1))

    for side in (-1, 1):
        # Crisp folded Hawaiian camp collar flap resting outward over upper chest/shoulders
        mb.face([
            V(side * 0.056, 1.136, z_chest_top + 0.002),
            V(side * 0.132, 1.080, z_chest_top + 0.006),
            V(side * 0.148, 1.170, 0.048),
            V(side * 0.068, 1.176, 0.066),
        ], SHIRT_COLLAR, out=(side * 0.25, 0.35, 0.90))

    # Relaxed short Hawaiian sleeves UV-mapped to bottom sleeve strip of shirt texture (2 x 10 = 20 tris)
    mb.set_part("short_sleeves")
    sleeve_anchors = []
    for (side, bname) in ((1, "Arm_L"), (-1, "Arm_R")):
        mb.set_bone(bname)
        p_sh   = V(side * 0.172, SHOULDER_Y, SHOULDER_Z)
        p_cuff = V(side * 0.272, 0.902, 0.018)
        ax_s = (p_cuff - p_sh).normalized()
        _, u_s, v_s = ortho_basis(ax_s, hint=V(0.0, 0.0, 1.0))
        # Ensure u_s points forward (+Z) and v_s points outward (side * +X)
        if u_s.z < 0:
            u_s = -u_s
        v_s = ax_s.cross(u_s).normalized()
        if v_s.x * side < 0:
            v_s = -v_s

        def slv_ring(ctr, rf, ro):
            # k=0: front->outer, k=1: outer->back, k=2: back->inner, k=3: inner->front
            return [
                ctr + u_s * rf - v_s * ro,  # 0: front-in
                ctr + u_s * rf + v_s * ro,  # 1: front-out
                ctr - u_s * rf + v_s * ro,  # 2: back-out
                ctr - u_s * rf - v_s * ro,  # 3: back-in
            ]

        r_sh   = slv_ring(p_sh,   0.084, 0.076)
        r_cuff = slv_ring(p_cuff, 0.094, 0.088)

        def slv_uv(i, k):
            # k=1 is the prominent outer face -> map right to u in [0.25, 0.50] where hero leaf lives!
            u0 = k * 0.25
            u1 = (k + 1) * 0.25
            return [(u0, 0.275), (u1, 0.275), (u1, 0.01), (u0, 0.01)]

        mb.loft([r_sh, r_cuff], WHITE, cap_bottom=False, cap_top=True,
                top_color=SHIRT_SHADE, mat_idx=MAT_SHIRT, uv_fn=slv_uv)
        sleeve_anchors.append((side, bname, p_sh, p_cuff))

    # =========================================================================
    # 8. BARE PEACH FOREARMS & CHUNKY HANDS HOLDING THE OPEN MAP (52 tris)
    # =========================================================================
    mb.set_part("arms_and_hands")
    for (side, bname, _p_sh, p_cuff) in sleeve_anchors:
        mb.set_bone(bname)
        p_in = p_cuff + V(-side * 0.014, 0.036, -0.004)  # tucked cleanly inside short sleeve
        p_el = V(side * 0.276, 0.826, 0.042)             # relaxed bent elbow
        p_wr = V(side * 0.228, 0.862, 0.222)             # wrist reaching cleanly to map side edge
        p_hd = V(side * 0.214, 0.874, 0.284)             # chunky hand cradling map outer border

        ax1 = (p_el - p_in).normalized()
        ax2 = (p_wr - p_el).normalized()
        ax3 = (p_hd - p_wr).normalized()
        axm1 = (ax1 + ax2).normalized()
        axm2 = (ax2 + ax3).normalized()

        def arm_ring(ctr, axis, rx, ry):
            _, u, v = ortho_basis(axis, hint=V(1.0, 0.0, 0.0))
            if u.x < 0:
                u = -u
            v = axis.cross(u).normalized()
            return [
                ctr - u * rx + v * ry,
                ctr + u * rx + v * ry,
                ctr + u * rx - v * ry,
                ctr - u * rx - v * ry,
            ]

        r0 = arm_ring(p_in, ax1,  0.056, 0.056)
        r1 = arm_ring(p_el, axm1, 0.058, 0.058)
        r2 = arm_ring(p_wr, axm2, 0.050, 0.052)
        r3 = arm_ring(p_hd, ax3,  0.046, 0.050)
        mb.loft([r0, r1, r2, r3], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN)

    # =========================================================================
    # 9. OPEN FOLDED TOURIST MAP WITH PAINTED TEXTURE (20 tris, bone="Map")
    # =========================================================================
    mb.set_part("map", bone="Map")
    # 2-panel open V-folded map tilted ~21 deg so he reads it comfortably while outer map faces viewer!
    # Center crease slightly forward (+Z), outer edges angled gently back into both hands
    # Front (outward-facing +Z) & Back (inward-facing -Z toward his face) separated by 0.008 m paper thickness
    hw_map = 0.214
    t_map = 0.008  # crisp solid paper thickness (zero z-fighting!)

    # Front (+Z outward) corners: left edge (+X), center crease (0), right edge (-X)
    f_lb = V( hw_map, 0.752, 0.214)
    f_lt = V( hw_map, 1.048, 0.342)
    f_cb = V( 0.000,  0.742, 0.264)
    f_ct = V( 0.000,  1.038, 0.392)
    f_rb = V(-hw_map, 0.752, 0.214)
    f_rt = V(-hw_map, 1.048, 0.342)

    # Normal offset toward tourist (-Z, +Y slightly) for back side of paper
    n_off = V(0.0, 0.003, -t_map)
    b_lb = f_lb + n_off; b_lt = f_lt + n_off
    b_cb = f_cb + n_off; b_ct = f_ct + n_off
    b_rb = f_rb + n_off; b_rt = f_rt + n_off

    # Outward-facing painted map artwork (viewer's left is -X right-hand panel -> u=0..0.5, viewer's right is +X -> u=0.5..1.0)
    mb.face([f_rb, f_cb, f_ct, f_rt], WHITE, out=( 0.2, -0.3, 1.0), mat_idx=MAT_MAP,
            uvs=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)])
    mb.face([f_cb, f_lb, f_lt, f_ct], WHITE, out=(-0.2, -0.3, 1.0), mat_idx=MAT_MAP,
            uvs=[(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)])

    # Inward-facing painted map artwork (facing the tourist's sunglasses so it looks authentic from behind too!)
    mb.face([b_lb, b_cb, b_ct, b_lt], WHITE, out=( 0.2, 0.3, -1.0), mat_idx=MAT_MAP,
            uvs=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)])
    mb.face([b_cb, b_rb, b_rt, b_ct], WHITE, out=(-0.2, 0.3, -1.0), mat_idx=MAT_MAP,
            uvs=[(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)])

    # Thin cream paper rim sealing all 6 outer edges cleanly (12 tris -> 20 tris total for watertight map!)
    mb.face([f_rt, f_ct, b_ct, b_rt], MAP_EDGE, out=(0, 1, 0))
    mb.face([f_ct, f_lt, b_lt, b_ct], MAP_EDGE, out=(0, 1, 0))
    mb.face([b_rb, b_cb, f_cb, f_rb], MAP_EDGE, out=(0, -1, 0))
    mb.face([b_cb, b_lb, f_lb, f_cb], MAP_EDGE, out=(0, -1, 0))
    mb.face([b_rb, f_rb, f_rt, b_rt], MAP_EDGE, out=(-1, 0, 0))
    mb.face([f_lb, b_lb, b_lt, f_lt], MAP_EDGE, out=( 1, 0, 0))

    # =========================================================================
    # 10. OLIVE GREEN BACKPACK + REAR POCKET/FLAP + DARK STRAPS (46 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Backpack")
    # 4-sided 4-ring rounded olive hiking pack with dark charcoal lower base (skip front flush against shirt = 22 tris)
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.688, 0.162, -0.130, -0.268),  # 0: dark charcoal reinforced base
        (0.768, 0.180, -0.132, -0.312),  # 1: charcoal-to-olive seam
        (0.992, 0.174, -0.126, -0.300),  # 2: full olive main pack body
        (1.112, 0.122, -0.118, -0.214),  # 3: softly rounded olive top dome
    ]
    bp_rings = []
    for (y, rx, zin, zout) in bp_specs:
        bp_rings.append([
            V(-rx, y, zin),
            V( rx, y, zin),
            V( rx, y, zout),
            V(-rx, y, zout),
        ])

    def bp_col(i, k):
        if i == 0:
            return PACK_BASE
        return PACK_DARK if k in (1, 3) else PACK_MAIN

    mb.loft(bp_rings, bp_col, cap_bottom=True, cap_top=True,
            bot_color=PACK_BASE, top_color=PACK_LIGHT, skip_k=(0,))

    # Chunky olive rear pocket + overhanging top flap lid (10 + 4 = 14 tris)
    mb.box(
        -0.136, 0.136,
        0.742, 0.935,
        -0.382, -0.296,
        {"back": PACK_LIGHT, "left": PACK_DARK, "right": PACK_DARK, "top": PACK_LIGHT, "bottom": PACK_DARK},
        skip=("front",),
    )
    # Overhanging pocket flap lid + subtle shadow lip (4 tris)
    mb.face([
        V( 0.142, 0.875, -0.394),
        V(-0.142, 0.875, -0.394),
        V(-0.138, 0.942, -0.386),
        V( 0.138, 0.942, -0.386),
    ], PACK_LIGHT, out=(0, 0, -1))
    mb.face([
        V(-0.142, 0.875, -0.394),
        V( 0.142, 0.875, -0.394),
        V( 0.136, 0.875, -0.382),
        V(-0.136, 0.875, -0.382),
    ], PACK_DARK, out=(0, -1, 0))

    # Dark charcoal shoulder straps wrapping over Hawaiian shirt shoulders & down front/sides (12 tris)
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        xa_t = min(side * 0.132, side * 0.178)
        xb_t = max(side * 0.132, side * 0.178)
        xa_b = min(side * 0.154, side * 0.200)
        xb_b = max(side * 0.154, side * 0.200)
        # Shoulder top strap
        mb.face([
            V(xa_t, 1.150, -0.128),
            V(xb_t, 1.150, -0.128),
            V(xb_t, 1.150,  0.128),
            V(xa_t, 1.150,  0.128),
        ], STRAP, out=(0, 1, 0))
        # Front chest strap sloping cleanly down toward underarm hugging shirt front
        mb.face([
            V(xa_b, 0.865, 0.136),
            V(xb_b, 0.865, 0.136),
            V(xb_t, 1.150, 0.128),
            V(xa_t, 1.150, 0.128),
        ], STRAP, out=(0, 0, 1))
        # Lower side underarm strap connecting cleanly into dark backpack base
        x_side = side * 0.218
        mb.face([
            V(x_side, 0.742, -0.145),
            V(x_side, 0.778, -0.145),
            V(side * 0.196, 0.895, 0.126),
            V(side * 0.196, 0.860, 0.126),
        ], STRAP, out=(side, 0, 0))

    # =========================================================================
    # 11. KHAKI SHORTS + BARE LOWER LEGS (8 + 20 + 16 = 44 tris)
    # =========================================================================
    mb.set_part("shorts", bone="Root")
    mb.box(-0.190, 0.190, 0.545, 0.672, -0.112, 0.112, SHORTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.188
        x_in_b, x_out_b = side * 0.038, side * 0.226
        rz_t, rz_b = 0.104, 0.112
        r_top = [
            V(min(x_in_t, x_out_t), 0.592,  rz_t),
            V(max(x_in_t, x_out_t), 0.592,  rz_t),
            V(max(x_in_t, x_out_t), 0.592, -rz_t),
            V(min(x_in_t, x_out_t), 0.592, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.342,  rz_b),
            V(max(x_in_b, x_out_b), 0.342,  rz_b),
            V(max(x_in_b, x_out_b), 0.342, -rz_b),
            V(min(x_in_b, x_out_b), 0.342, -rz_b),
        ]
        mb.loft([r_bot, r_top], lambda i, k: SHORTS_SHADE if k == 2 else SHORTS,
                cap_bottom=True, cap_top=False, bot_color=SHORTS_INNER)

    # Bare peach calves/ankles extending cleanly from inside shorts down into shoes (2 x 8 = 16 tris)
    mb.set_part("legs")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx_t = side * 0.128
        cx_b = side * 0.136
        rt = oval_ring(cx_t, 0.375, 0.002, 0.068, 0.068, n=4, phase=math.pi / 4.0)
        rb = oval_ring(cx_b, 0.124, 0.004, 0.058, 0.058, n=4, phase=math.pi / 4.0)
        mb.loft([rb, rt], lambda i, k: SKIN_SHADE if k == 1 else SKIN, cap_bottom=False, cap_top=False)

    # =========================================================================
    # 12. CHUNKY BROWN WALKING SHOES WITH DARK SOLES (2 x 18 = 36 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.136
        w = 0.070
        w_toe = 0.058
        z_heel = -0.090
        z_toe  =  0.165
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_col   = 0.138

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

        shoe_top = [
            V(cx - w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, z_heel + 0.016),
            V(cx + w * 0.84, y_col, 0.060),
            V(cx - w * 0.84, y_col, 0.060),
        ]
        mb.loft([sole_top, shoe_top], lambda i, k: SHOE_SHADE if k == 0 else SHOE,
                cap_bottom=False, cap_top=False)

    return mb


def setup_materials(shirt_img, map_img):
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

    def _make_tex_mat(name, image, roughness, spec):
        mat = bpy.data.materials.new(name)
        nt_t = mat.node_tree
        bsdf_t = next(n for n in nt_t.nodes if n.type == "BSDF_PRINCIPLED")
        tex_t = nt_t.nodes.new("ShaderNodeTexImage")
        tex_t.image = image
        # Multiply by white vertex color "Col" so all 3 materials share identical vertex color spec for glTF!
        vc_t = nt_t.nodes.new("ShaderNodeVertexColor")
        vc_t.layer_name = "Col"
        mix_t = nt_t.nodes.new("ShaderNodeMix")
        mix_t.data_type = "RGBA"
        mix_t.blend_type = "MULTIPLY"
        mix_t.inputs["Factor"].default_value = 1.0
        nt_t.links.new(tex_t.outputs["Color"], mix_t.inputs["A"])
        nt_t.links.new(vc_t.outputs["Color"], mix_t.inputs["B"])
        nt_t.links.new(mix_t.outputs["Result"], bsdf_t.inputs["Base Color"])
        bsdf_t.inputs["Roughness"].default_value = roughness
        if "Specular IOR Level" in bsdf_t.inputs:
            bsdf_t.inputs["Specular IOR Level"].default_value = spec
        return mat

    # Slot 1: Painted Hawaiian Shirt material
    mat_shirt = _make_tex_mat("HawaiianShirt", shirt_img, roughness=0.88, spec=0.18)

    # Slot 2: Painted Tourist Map material
    mat_map = _make_tex_mat("TouristMap", map_img, roughness=0.90, spec=0.15)

    return [mat_vcol, mat_shirt, mat_map]


def _reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _map_lockstep_offset(arm_pitch):
    """Exact rigid-body translation (in bone-local XYZ) keeping Map glued to hands as arms pitch by arm_pitch."""
    # Bone local axes: X = +game_x, Y = +game_y, Z = -game_z
    dy = MAP_PIVOT.y - SHOULDER_Y
    dz = -(MAP_PIVOT.z - SHOULDER_Z)  # bone-local Z
    ct, st = math.cos(arm_pitch), math.sin(arm_pitch)
    dy_new = dy * ct - dz * st
    dz_new = dy * st + dz * ct
    return (0.0, dy_new - dy, dz_new - dz)


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: unhurried sightseeing stroll reading the map with backpack bounce."""
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

        # Relaxed sightseeing walk bounce & subtle forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.022 * (1.0 - c2) * 0.5
        root_pitch = -0.045
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.056 * s1, 0.034 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gentle torso counter-twist keeping map readable
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.018 * c2, 0.068 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Tourist glances slightly down toward map (+rx = chin down) & scans slightly left/right
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.068 + 0.030 * s2, -0.045 * s1 + 0.055 * c1, -0.016 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Leisurely alternating walking stride with crisp foot lift
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

        # Both bent arms + open Map move in exact lockstep so hands stay glued to map edges!
        arm_pitch = -0.048 * math.sin(2.0 * phi - 0.50)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_pitch, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (arm_pitch, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_map = rig.pose.bones["Map"]
        pb_map.location = _map_lockstep_offset(arm_pitch)
        pb_map.rotation_euler = (arm_pitch, 0.0, 0.0)
        pb_map.keyframe_insert(data_path="location", frame=frame)
        pb_map.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Olive backpack bounces gently with phase lag behind steps
        pb_pack = rig.pose.bones["Backpack"]
        pb_pack.location = (0.0, 0.008 * math.sin(2.0 * phi - 0.65), 0.0)
        pb_pack.rotation_euler = (0.024 * math.sin(2.0 * phi - 0.65), 0.0, -0.028 * math.sin(phi - 0.45))
        pb_pack.keyframe_insert(data_path="location", frame=frame)
        pb_pack.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: tourist studies his map, tilts it up slightly, then looks around taking in the view."""
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

        # Relaxed weight shift & calm breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.012, 0.026 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.036 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Expressive sightseeing look: +rx looks DOWN at map (c1 > 0), -rx looks UP & around at harbor (c1 < 0)!
        head_pitch = 0.15 * max(0.0, c1) - 0.10 * max(0.0, -c1) + 0.02
        head_yaw = 0.28 * s1
        head_roll = 0.052 * s2
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (head_pitch, head_yaw, head_roll)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Walking shoes stay firmly planted on ground
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # -rx raises map up when studying it (c1 > 0), +rx lowers map softly while taking in sights (c1 < 0)!
        arm_pitch = -0.115 * max(0.0, c1) + 0.070 * max(0.0, -c1) + 0.018 * s2
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_pitch, 0.0, 0.0)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (arm_pitch, 0.0, 0.0)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_map = rig.pose.bones["Map"]
        pb_map.location = _map_lockstep_offset(arm_pitch)
        pb_map.rotation_euler = (arm_pitch, 0.0, 0.0)
        pb_map.keyframe_insert(data_path="location", frame=frame)
        pb_map.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle backpack settle with breathing
        pb_pack = rig.pose.bones["Backpack"]
        pb_pack.location = (0.0, 0.004 * s2, 0.0)
        pb_pack.rotation_euler = (0.014 * s2, 0.0, 0.014 * s1)
        pb_pack.keyframe_insert(data_path="location", frame=frame)
        pb_pack.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 9-bone rig (7 standard passenger bones + Map, Backpack) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonTouristRig")
    rig = bpy.data.objects.new("PersonTouristRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",     None,    ( 0.000, 0.600,  0.000), ( 0.000, 0.700,  0.000)),
        ("Torso",    "Root",  ( 0.000, 0.665,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",     "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.495,  0.000)),
        ("Arm_L",    "Torso", ( 0.172, SHOULDER_Y, SHOULDER_Z), ( 0.172, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Arm_R",    "Torso", (-0.172, SHOULDER_Y, SHOULDER_Z), (-0.172, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Map",      "Torso", tuple(MAP_PIVOT),                 (MAP_PIVOT.x, MAP_PIVOT.y + 0.160, MAP_PIVOT.z)),
        ("Backpack", "Torso", ( 0.000, 0.880, -0.155),          ( 0.000, 1.060, -0.155)),
        ("Leg_L",    "Root",  ( 0.118, 0.560,  0.000),          ( 0.118, 0.720,  0.000)),
        ("Leg_R",    "Root",  (-0.118, 0.560,  0.000),          (-0.118, 0.720,  0.000)),
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
        ( 0.85, math.radians(90)),   # Side (showing backpack, safari hat, map)
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
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_SHADE, BROW],
    "bottom": [SHORTS, SHORTS_SHADE, SHORTS_INNER],
    "accent": [HAT_CROWN, HAT_TOP, HAT_BRIM, HAT_UNDER],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonTourist")
    bpy.context.scene.collection.children.link(coll)

    shirt_img = generate_shirt_texture(SHIRT_TEX_PATH)
    map_img = generate_map_texture(MAP_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonTourist")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(shirt_img, map_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonTourist", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris < 450, f"Triangle budget exceeded: {total_tris} >= 450"

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    # Export GLB with both Walk and Idle animations + embedded textures via ACTIONS mode
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

    print("=== PersonTourist Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    print(f"Shirt texture:   {SHIRT_TEX_PATH}")
    print(f"Map texture:     {MAP_TEX_PATH}")
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
