# Builds an ultra-low-poly (< 350 tris) stylized college student girl with voluminous curly hair,
# cream over-ear headphones, painted "W" cream hoodie sweatshirt (right hand tucked in kangaroo pocket),
# painted 3-pine-tree canvas book bag on right shoulder, dark charcoal wide-leg pants, and cream sneakers in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_student_girl.py)
# Saves art/person_student_girl.blend, exports assets/models/person_student_girl.glb (rigged + Walk & Idle cycles + embedded textures),
# renders art/person_student_girl_preview.png, art/person_student_girl_walk_preview.png, art/person_student_girl_idle_preview.png,
# and outputs rendered videos art/person_student_girl_walk.mp4 and art/person_student_girl_idle.mp4.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_student_girl.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_student_girl.glb")
HOODIE_TEX_PATH = os.path.join(ROOT, "art", "person_student_girl_hoodie_tex.png")
BAG_TEX_PATH = os.path.join(ROOT, "art", "person_student_girl_bag_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_student_girl_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_student_girl_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_student_girl_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_student_girl_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_student_girl_idle.mp4")

MAT_VCOL = 0
MAT_HOODIE = 1
MAT_BAG = 2


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (every colour made with col_srgb, unique per part)
TEX_WHITE       = col_srgb(1.00, 1.00, 1.00)

SKIN            = col_srgb(0.83, 0.57, 0.34)
SKIN_SHADE      = col_srgb(0.70, 0.45, 0.25)
EYE             = col_srgb(0.11, 0.10, 0.11)

HAIR_DARK       = col_srgb(0.30, 0.22, 0.18)
HAIR_MID        = col_srgb(0.39, 0.29, 0.24)

HP_MAIN         = col_srgb(0.96, 0.93, 0.87)
HP_SHADE        = col_srgb(0.84, 0.79, 0.71)

BAG_STRAP_DARK  = col_srgb(0.42, 0.33, 0.27)
BAG_STRAP_CREAM = col_srgb(0.92, 0.82, 0.71)

PANTS           = col_srgb(0.30, 0.30, 0.34)
PANTS_SHADE     = col_srgb(0.22, 0.22, 0.26)

SHOE            = col_srgb(0.94, 0.90, 0.84)
SHOE_VAMP       = col_srgb(0.87, 0.82, 0.75)
SOLE            = col_srgb(0.75, 0.70, 0.63)

# Parts the game recolours per passenger (see art/person_recolor.py).
# Textured surfaces (painted "W" hoodie and painted 3-tree book bag), eyes, shoes, and bag straps stay fixed.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR_DARK, HAIR_MID],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [HP_MAIN, HP_SHADE],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def _rect_mask(uu, vv, u0, u1, v0, v1, feather=0.003):
    mx = np.clip((uu - u0) / feather, 0.0, 1.0) * np.clip((u1 - uu) / feather, 0.0, 1.0)
    my = np.clip((vv - v0) / feather, 0.0, 1.0) * np.clip((v1 - vv) / feather, 0.0, 1.0)
    return mx * my


def _segment_mask(uu, vv, p0, p1, half_w, aspect=1.0, feather=0.0025):
    """Anti-aliased capsule/bar mask between p0=(u0,v0) and p1=(u1,v1)."""
    ax, ay = p0
    bx, by = p1
    dx = (bx - ax) * aspect
    dy = by - ay
    len2 = dx * dx + dy * dy + 1e-12
    px = (uu - ax) * aspect
    py = vv - ay
    t = np.clip((px * dx + py * dy) / len2, 0.0, 1.0)
    dist = np.sqrt((px - t * dx) ** 2 + (py - t * dy) ** 2)
    return np.clip((half_w - dist) / feather + 0.5, 0.0, 1.0)


def _triangle_mask(uu, vv, p0, p1, p2, feather=0.0025):
    """Anti-aliased filled triangle mask using signed half-plane distances."""
    pts = [p0, p1, p2]
    # Ensure CCW winding
    area = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
    if area < 0:
        pts = [p0, p2, p1]
    min_d = np.full_like(uu, 1e6, dtype=np.float32)
    for idx in range(3):
        ax, ay = pts[idx]
        bx, by = pts[(idx + 1) % 3]
        ex, ey = bx - ax, by - ay
        elen = math.hypot(ex, ey) + 1e-12
        # Left inward normal = (-ey, ex) / elen
        d = (-(uu - ax) * ey + (vv - ay) * ex) / elen
        min_d = np.minimum(min_d, d)
    return np.clip(min_d / feather + 0.5, 0.0, 1.0)


def generate_hoodie_texture(out_path):
    """Paint a 512x512 sRGB cream sweatshirt texture:
       - Top band (v in [0.34, 1.00]): Torso wrap.
         Front chest (u in [0.00, 0.34], center u=0.170) has the crisp dark slate-navy serif block "W",
         subtle kangaroo front pouch pocket with side entry shadow, and ribbed waist hem along v=[0.34, 0.415].
       - Bottom-left band (u in [0.00, 0.65], v in [0.00, 0.32]): Sleeves with ribbed wrist cuff along v=[0.00, 0.058].
       - Bottom-right band (u in [0.66, 1.00], v in [0.00, 0.32]): Folded hood fleece with subtle collar/fold shading.
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Cozy warm oatmeal/cream sweatshirt base matched to reference
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[..., 0] = 0.935
    img[..., 1] = 0.865
    img[..., 2] = 0.755

    # Ultra-subtle soft knit cotton grain
    grain = 1.0 + 0.0025 * np.sin(uu * 260.0) + 0.003 * np.sin(vv * 280.0)
    img *= grain[..., None]

    # =========================================================================
    # 1. TORSO REGION (v in [0.34, 1.00])
    # =========================================================================
    in_torso = (vv >= 0.335).astype(np.float32)
    torso_v = np.clip((vv - 0.34) / 0.66, 0.0, 1.0)
    torso = img.copy()
    torso *= (0.94 + 0.08 * torso_v)[..., None]

    # Ribbed bottom waist hem band (v in [0.34, 0.410])
    rib_band = np.clip((0.410 - vv) / 0.005, 0.0, 1.0) * in_torso
    rib_tex = 0.5 + 0.5 * np.sin(uu * 360.0)
    torso = _blend_mask(torso, rib_band * 0.38, (0.85, 0.77, 0.65))
    torso = _blend_mask(torso, rib_band * rib_tex * 0.14, (0.77, 0.69, 0.57))
    # Crisp stitched seam above waist rib
    hem_seam = np.clip((0.005 - np.abs(vv - 0.412)) / 0.0025, 0.0, 1.0) * in_torso
    torso = _blend_mask(torso, hem_seam * 0.42, (0.74, 0.65, 0.53))

    # --- Soft Cozy Kangaroo Front Pocket on Front Panel (u in [0.00, 0.34], center u=0.170) ---
    p_t = np.clip((vv - 0.418) / (0.605 - 0.418), 0.0, 1.0)
    p_half = 0.122 - 0.038 * p_t
    in_pouch_v = np.clip((vv - 0.414) / 0.006, 0.0, 1.0) * np.clip((0.606 - vv) / 0.006, 0.0, 1.0)
    in_pouch_u = np.clip((p_half - np.abs(uu - 0.170)) / 0.006, 0.0, 1.0)
    pouch_body = in_pouch_v * in_pouch_u
    # Gentle soft rounded highlight on pouch center
    torso = _blend_mask(torso, pouch_body * 0.24, (0.97, 0.91, 0.81))
    # Subtle soft top seam of kangaroo pocket
    pouch_top = np.clip((0.004 - np.abs(vv - 0.606)) / 0.0025, 0.0, 1.0) * np.clip((0.082 - np.abs(uu - 0.170)) / 0.005, 0.0, 1.0)
    torso = _blend_mask(torso, pouch_top * 0.26, (0.76, 0.67, 0.55))
    # Soft curved pocket entry shadows on left & right sides (right side frames tucked cuff cleanly!)
    slit_r = _segment_mask(uu, vv, (0.048, 0.422), (0.088, 0.602), half_w=0.0042, aspect=1.0, feather=0.0035)
    slit_l = _segment_mask(uu, vv, (0.292, 0.422), (0.252, 0.602), half_w=0.0042, aspect=1.0, feather=0.0035)
    torso = _blend_mask(torso, np.maximum(slit_r, slit_l) * 0.36, (0.70, 0.60, 0.48))
    tuck_sh = _segment_mask(uu, vv, (0.040, 0.455), (0.076, 0.575), half_w=0.016, aspect=1.0, feather=0.014)
    torso = _blend_mask(torso, tuck_sh * 0.30, (0.72, 0.62, 0.50))

    # --- Iconic Painted Navy/Slate Collegiate Serif Block "W" on Upper Chest ---
    # Front flat face k=5 spans ~0.232 m in width (du=0.34) and ~0.490 m in height (dv=0.66):
    # world_u_per_uv = 0.682 m, world_v_per_uv = 0.742 m -> aspect = 0.92.
    # Make the W bold, boxy & slightly wider than tall (classic UW varsity serif block W!)
    w_aspect = 0.92
    cx = 0.170
    vy_top = 0.858
    vy_bot = 0.704
    vy_mid = 0.794  # crisp center peak of the W

    # Wide bold collegiate W stroke vertices
    p_tl  = (cx - 0.102, vy_top)
    p_bl  = (cx - 0.056, vy_bot)
    p_mid = (cx,         vy_mid)
    p_br  = (cx + 0.056, vy_bot)
    p_tr  = (cx + 0.102, vy_top)

    stroke_hw = 0.0215
    w_mask = np.zeros_like(uu, dtype=np.float32)
    for (pa, pb) in ((p_tl, p_bl), (p_bl, p_mid), (p_mid, p_br), (p_br, p_tr)):
        w_mask = np.maximum(w_mask, _segment_mask(uu, vv, pa, pb, half_w=stroke_hw, aspect=w_aspect, feather=0.0022))

    # Crisp flat horizontal collegiate block serifs along top tips & center peak
    serif_hw = 0.0125
    # Left top serif
    w_mask = np.maximum(w_mask, _rect_mask(uu, vv, cx - 0.132, cx - 0.068, vy_top - serif_hw, vy_top + serif_hw, feather=0.002))
    # Right top serif
    w_mask = np.maximum(w_mask, _rect_mask(uu, vv, cx + 0.068, cx + 0.132, vy_top - serif_hw, vy_top + serif_hw, feather=0.002))
    # Center peak flat serif bar
    w_mask = np.maximum(w_mask, _rect_mask(uu, vv, cx - 0.032, cx + 0.032, vy_mid - 0.006, vy_mid + 0.014, feather=0.002))
    # Trim cleanly flat at top and bottom horizontal bounds
    w_mask *= np.clip((vy_top + serif_hw + 0.002 - vv) / 0.002, 0.0, 1.0)
    w_mask *= np.clip((vv - (vy_bot - 0.015)) / 0.002, 0.0, 1.0)

    # Rich dark slate-indigo / navy-purple varsity ink matched to reference
    torso = _blend_mask(torso, w_mask, (0.31, 0.32, 0.42))
    ink_grain = 1.0 + 0.010 * np.sin(uu * 280.0 + vv * 210.0)
    torso = torso * (1.0 - w_mask[..., None] * 0.20) + np.clip(torso * ink_grain[..., None], 0.0, 1.0) * (w_mask[..., None] * 0.20)

    # Subtle vertical side seams on torso edges (u = 0.34, 0.99)
    side_seam = np.maximum(
        np.clip((0.004 - np.abs(uu - 0.34)) / 0.002, 0.0, 1.0),
        np.clip((0.004 - np.abs(uu - 0.002)) / 0.002, 0.0, 1.0),
    ) * in_torso
    torso = _blend_mask(torso, side_seam * 0.22, (0.76, 0.68, 0.56))

    # =========================================================================
    # 2. SLEEVE REGION (u in [0.00, 0.65], v in [0.00, 0.335])
    # =========================================================================
    sleeve = img.copy()
    slv_t = np.clip(vv / 0.32, 0.0, 1.0)
    sleeve *= (0.93 + 0.09 * slv_t)[..., None]
    # Ribbed wrist cuff band along bottom edge (v in [0.00, 0.058])
    cuff_m = np.clip((0.058 - vv) / 0.005, 0.0, 1.0)
    cuff_rib = 0.5 + 0.5 * np.sin(uu * 320.0)
    sleeve = _blend_mask(sleeve, cuff_m * 0.45, (0.85, 0.77, 0.65))
    sleeve = _blend_mask(sleeve, cuff_m * cuff_rib * 0.20, (0.75, 0.67, 0.55))
    cuff_seam = np.clip((0.006 - np.abs(vv - 0.060)) / 0.003, 0.0, 1.0)
    sleeve = _blend_mask(sleeve, cuff_seam * 0.45, (0.72, 0.63, 0.51))

    # =========================================================================
    # 3. FOLDED HOOD REGION (u in [0.65, 1.00], v in [0.00, 0.335])
    # =========================================================================
    hood = img.copy()
    hd_t = np.clip(vv / 0.32, 0.0, 1.0)
    # Darker recessed inner hood shade near v=0, warm cream outer drape near v=0.32
    hood *= (0.82 + 0.21 * hd_t)[..., None]
    # Subtle soft collar fold crease
    fold_line = np.clip((0.008 - np.abs(vv - 0.145)) / 0.004, 0.0, 1.0)
    hood = _blend_mask(hood, fold_line * 0.28, (0.75, 0.66, 0.54))

    # Combine all three atlas regions cleanly
    in_hood = ((vv < 0.335) & (uu >= 0.65)).astype(np.float32)
    in_sleeve = ((vv < 0.335) & (uu < 0.65)).astype(np.float32)
    out = torso * in_torso[..., None] + sleeve * in_sleeve[..., None] + hood * in_hood[..., None]
    out = np.clip(out, 0.0, 1.0)

    bimg = bpy.data.images.new("StudentGirlHoodieTex", width=w, height=h, alpha=True, float_buffer=False)
    bimg.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = out
    bimg.pixels.foreach_set(rgba.ravel())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bimg.filepath_raw = out_path
    bimg.file_format = "PNG"
    bimg.save()
    bimg.pack()
    return bimg


def _paint_pine_tree(img, uu, vv, cx, base_v, width, height, col_main=(0.24, 0.35, 0.26), col_dark=(0.17, 0.26, 0.19)):
    """Paint a crisp stylized 3-tier PNW evergreen pine tree with short trunk onto canvas texture."""
    # Short stout trunk at bottom
    tw = width * 0.13
    th = height * 0.14
    trunk_m = _rect_mask(uu, vv, cx - tw, cx + tw, base_v, base_v + th + 0.02, feather=0.002)
    img = _blend_mask(img, trunk_m, col_dark)

    # 3 overlapping evergreen bough triangles from bottom to top
    tiers = [
        # (y_bot_frac, y_top_frac, half_width_frac, col)
        (0.11, 0.50, 0.50, col_main),
        (0.36, 0.76, 0.41, col_main),
        (0.62, 1.00, 0.31, col_main),
    ]
    for idx, (yb_f, yt_f, hw_f, col) in enumerate(tiers):
        yb = base_v + height * yb_f
        yt = base_v + height * yt_f
        hw = width * hw_f
        # Subtle shadow under upper tiers onto lower tier for layered hand-printed charm
        if idx > 0:
            sh_m = _triangle_mask(
                uu, vv,
                (cx - hw * 0.92, yb - height * 0.022),
                (cx + hw * 0.92, yb - height * 0.022),
                (cx, yt - height * 0.022),
                feather=0.003,
            )
            img = _blend_mask(img, sh_m * 0.45, col_dark)
        tri_m = _triangle_mask(
            uu, vv,
            (cx - hw, yb),
            (cx + hw, yb),
            (cx, yt),
            feather=0.0022,
        )
        img = _blend_mask(img, tri_m, col)
    return img


def generate_bag_texture(out_path):
    """Paint a 512x512 sRGB warm canvas book bag texture:
       - Left region (u in [0.00, 0.65], v in [0.00, 1.00]): Outer book bag panel with 3 crisp forest-green pine trees.
       - Right-top region (u in [0.66, 1.00], v in [0.50, 1.00]): Matching cream canvas gussets & inner face with crease shading.
       - Right-mid region (u in [0.66, 1.00], v in [0.22, 0.50]): Warm shaded underside/bottom canvas fold.
       - Right-bot region (u in [0.66, 1.00], v in [0.00, 0.22]): Dark shaded inner bag opening.
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Warm peach-cream heavy canvas base matched to reference tote bag
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[..., 0] = 0.975
    img[..., 1] = 0.875
    img[..., 2] = 0.765

    # Soft woven canvas micro-texture
    weave = 1.0 + 0.004 * np.sin(uu * 310.0) + 0.004 * np.sin(vv * 310.0)
    img *= weave[..., None]

    # =========================================================================
    # 1. OUTER PANEL WITH 3 PAINTED PINE TREES (u in [0.00, 0.65])
    # =========================================================================
    outer = img.copy()
    # Gentle canvas shading (brighter top-middle, softly warmer/shaded near bottom corner gusset)
    outer *= (0.93 + 0.08 * vv)[..., None]

    # Soft bottom gusset fold shadow (v < 0.10)
    bot_sh = np.clip((0.10 - vv) / 0.06, 0.0, 1.0)
    outer = _blend_mask(outer, bot_sh * 0.36, (0.84, 0.69, 0.55))

    # Crisp top stitched canvas hem band (v near 0.90)
    top_stitch = np.clip((0.005 - np.abs(vv - 0.900)) / 0.0025, 0.0, 1.0)
    outer = _blend_mask(outer, top_stitch * 0.28, (0.78, 0.65, 0.52))

    # Three iconic PNW forest-green pine trees standing side-by-side!
    # Fuller, slightly wider evergreen silhouettes closely matching reference artwork
    trees = [
        # (cx,    base_v, width, height)
        (0.150, 0.210, 0.190, 0.470),
        (0.325, 0.195, 0.205, 0.545),
        (0.500, 0.210, 0.190, 0.470),
    ]
    for (tx, bv, tw, th) in trees:
        outer = _paint_pine_tree(outer, uu, vv, tx, bv, tw, th)

    # =========================================================================
    # 2. GUSSETS, BOTTOM & INTERIOR ATLAS REGIONS (u in [0.65, 1.00])
    # =========================================================================
    side = img.copy()
    side *= (0.90 + 0.09 * np.clip((vv - 0.50) / 0.50, 0.0, 1.0))[..., None]
    # Vertical gusset center fold crease at u = 0.825
    crease = np.clip((0.014 - np.abs(uu - 0.825)) / 0.010, 0.0, 1.0)
    side = _blend_mask(side, crease * 0.30, (0.81, 0.68, 0.55))
    # Subtle top stitched edge on gussets too
    side_stitch = np.clip((0.006 - np.abs(vv - 0.945)) / 0.0025, 0.0, 1.0)
    side = _blend_mask(side, side_stitch * 0.35, (0.78, 0.65, 0.52))

    bottom = img.copy() * np.array([0.85, 0.81, 0.77], dtype=np.float32)[None, None, :]
    interior = np.zeros_like(img)
    interior[..., 0] = 0.52
    interior[..., 1] = 0.43
    interior[..., 2] = 0.35

    m_outer = (uu < 0.65).astype(np.float32)
    m_side = ((uu >= 0.65) & (vv >= 0.50)).astype(np.float32)
    m_bot = ((uu >= 0.65) & (vv >= 0.22) & (vv < 0.50)).astype(np.float32)
    m_int = ((uu >= 0.65) & (vv < 0.22)).astype(np.float32)

    out = (
        outer * m_outer[..., None]
        + side * m_side[..., None]
        + bottom * m_bot[..., None]
        + interior * m_int[..., None]
    )
    out = np.clip(out, 0.0, 1.0)

    bimg = bpy.data.images.new("StudentGirlBagTex", width=w, height=h, alpha=True, float_buffer=False)
    bimg.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = out
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
             mat_idx=MAT_VCOL, uv_fn=None, bot_uvs=None, top_uvs=None):
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
                self.face(r0, col, out=out_dir, weights=([wb] * n if wb else None), mat_idx=mat_idx, uvs=bot_uvs)
            elif n == 6:
                u_a = bot_uvs[:4] if bot_uvs is not None else None
                u_b = [bot_uvs[3], bot_uvs[4], bot_uvs[5], bot_uvs[0]] if bot_uvs is not None else None
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb else None), mat_idx=mat_idx, uvs=u_a)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=([wb] * 4 if wb else None), mat_idx=mat_idx, uvs=u_b)
            else:
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir, weights=([wb] * 3 if wb else None), mat_idx=mat_idx)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            wt = ring_weights[-1] if ring_weights is not None else None
            if n <= 4:
                self.face(rt, col, out=out_dir, weights=([wt] * n if wt else None), mat_idx=mat_idx, uvs=top_uvs)
            elif n == 6:
                u_a = top_uvs[:4] if top_uvs is not None else None
                u_b = [top_uvs[3], top_uvs[4], top_uvs[5], top_uvs[0]] if top_uvs is not None else None
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt else None), mat_idx=mat_idx, uvs=u_a)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=([wt] * 4 if wt else None), mat_idx=mat_idx, uvs=u_b)
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir, weights=([wt] * 3 if wt else None), mat_idx=mat_idx)

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
                     color=HAIR_DARK, cap_color=None, scallop=0.08):
        """Chunky, non-spiky 5-sided beveled curl cushion (13 tris: 5 side quads + 3-tri flat cap)."""
        ax = axis.normalized()
        ref = V(0.0, 1.0, 0.0) if abs(ax.y) < 0.85 else V(0.0, 0.0, 1.0)
        u = ax.cross(ref).normalized()
        v = ax.cross(u).normalized()

        def ring5(ctr, rad, sc):
            pts = []
            for k in range(5):
                a = phase + 2.0 * math.pi * k / 5.0
                bump = 1.0 + sc * (1.0 if k % 2 == 0 else -0.65)
                pts.append(ctr + u * (rad * bump * math.cos(a)) + v * (rad * aspect_y * bump * math.sin(a)))
            return pts

        r0 = ring5(base_pt, r_base, scallop)
        r1 = ring5(base_pt + ax * depth, r_cap, scallop * 0.7)
        c_mid = base_pt + ax * (depth * 0.5)
        for k in range(5):
            kn = (k + 1) % 5
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            col = cap_color if (cap_color is not None and k % 2 == 0) else color
            self.face([p0, p1, p2, p3], col, out=(mid - c_mid))
        cc = cap_color if cap_color is not None else color
        self.face([r1[0], r1[1], r1[2], r1[3]], cc, out=ax)
        self.face([r1[0], r1[3], r1[4]], cc, out=ax)

    def tri_strap(self, pts, norms, half_w, thick, colors):
        """Low-poly 3-sided prism ribbon along polyline `pts` with outward normals `norms` (6 tris/seg)."""
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
                p + nrm * (thick * 0.45) - side * half_w,
                p + nrm * (thick * 0.45) + side * half_w,
                p - nrm * (thick * 0.55),
            ])
        self.loft(rings, colors, cap_bottom=False, cap_top=False)


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD (6-sided stylized low-poly head, flat front face, 32 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.205,  0.016, 0.152, 0.140),  # 0: chin/jaw
        (1.280,  0.022, 0.210, 0.196),  # 1: lower cheek
        (1.488,  0.018, 0.212, 0.198),  # 2: brow / forehead
        (1.608,  0.000, 0.164, 0.160),  # 3: crown tucked under curls/headband
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        if i == 2:
            return HAIR_DARK
        if i == 1:
            return SKIN if k in (4, 5, 0) else HAIR_DARK
        return HAIR_DARK if k in (1, 2, 3) else SKIN

    # Skip back-of-skull quads completely enclosed inside lush curly hair puff
    hidden_head_quads = {(2, 1), (2, 2), (2, 3), (1, 2)}
    for i in range(len(head_rings) - 1):
        r0, r1 = head_rings[i], head_rings[i + 1]
        c0 = sum(r0, Vector()) / 6
        c1 = sum(r1, Vector()) / 6
        cmid = (c0 + c1) * 0.5
        for k in range(6):
            if (i, k) in hidden_head_quads:
                continue
            kn = (k + 1) % 6
            p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
            mid = (p0 + p1 + p2 + p3) * 0.25
            mb.face([p0, p1, p2, p3], head_color(i, k), out=(mid - cmid))
    rb = head_rings[0]
    mb.face([rb[0], rb[1], rb[2], rb[3]], SKIN_SHADE, out=(0, -1, 0))
    mb.face([rb[3], rb[4], rb[5], rb[0]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. NECK (4-sided short tapered cylinder, skip rear quad inside hood = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.108, 0.010, 0.070, 0.066, n=4, phase=math.pi / 4.0)
    neck_r1 = oval_ring(0.0, 1.215, 0.012, 0.066, 0.062, n=4, phase=math.pi / 4.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 3. EYES (2 crisp vertical dark pill hexagons on flat front face, 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.197
    for side in (-1, 1):
        cx = side * 0.062
        cy = 1.386
        rx = 0.019
        ry = 0.047
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
    # 4. VOLUMINOUS CURLY AFRO/PUFF HAIR (5 chunky rounded 5-sided cushions = 65 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # Lush, rounded billowing dark-brown curly hair matching reference silhouette!
    # 1. Upper-back curly crown cloud (tucked cleanly flush behind the cream headband arch!)
    mb.curl_cushion(
        base_pt=V(0.0, 1.498, -0.032),
        axis=V(0.0, 0.14, -0.99),
        depth=0.250,
        r_base=0.228,
        r_cap=0.146,
        aspect_y=0.78,
        phase=math.pi / 2.0,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        scallop=0.07,
    )
    # 2. Mid-back wide billowing curl cloud (generous rounded curly puff framing both sides behind headphones!)
    mb.curl_cushion(
        base_pt=V(0.0, 1.395, -0.052),
        axis=V(0.0, -0.06, -1.00),
        depth=0.285,
        r_base=0.258,
        r_cap=0.166,
        aspect_y=0.74,
        phase=-math.pi / 2.0,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        scallop=0.08,
    )
    # 3. Lower-nape curly cascade tucked warmly right above the folded hood
    mb.curl_cushion(
        base_pt=V(0.0, 1.288, -0.056),
        axis=V(0.0, -0.26, -0.96),
        depth=0.235,
        r_base=0.228,
        r_cap=0.142,
        aspect_y=0.68,
        phase=0.25,
        color=HAIR_DARK,
        cap_color=HAIR_MID,
        scallop=0.08,
    )
    # 4 & 5. Soft parted curly bangs framing forehead & temples in front of headphones!
    for side in (-1, 1):
        mb.curl_cushion(
            base_pt=V(side * 0.074, 1.522, 0.044),
            axis=V(side * 0.52, 0.10, 0.85),
            depth=0.144,
            r_base=0.126,
            r_cap=0.078,
            aspect_y=0.80,
            phase=side * 0.42,
            color=HAIR_DARK,
            cap_color=HAIR_MID,
            scallop=0.08,
        )

    # =========================================================================
    # 5. OVER-EAR CREAM HEADPHONES (4-seg rounded band 24 + 2x6-sided cups 32 = 56 tris)
    # =========================================================================
    mb.set_part("headphones", bone="Head")
    band_stations = [
        # (cx,    cy,    cz,    norm_dir)
        ( 0.218, 1.432, 0.018, V( 0.98, 0.20, 0.0)),
        ( 0.174, 1.622, 0.012, V( 0.62, 0.78, 0.0)),
        ( 0.000, 1.675, 0.008, V( 0.00, 1.00, 0.0)),
        (-0.174, 1.622, 0.012, V(-0.62, 0.78, 0.0)),
        (-0.218, 1.432, 0.018, V(-0.98, 0.20, 0.0)),
    ]
    hw_z = 0.042
    ht   = 0.022
    band_rings = []
    for (cx, cy, cz, nd) in band_stations:
        n = nd.normalized()
        c = V(cx, cy, cz)
        ring = [
            c + n * ht + V(0, 0,  hw_z),
            c + n * ht + V(0, 0, -hw_z),
            c - n * ht + V(0, 0, -hw_z),
            c - n * ht + V(0, 0,  hw_z),
        ]
        band_rings.append(ring)

    def band_col(i, k):
        return HP_MAIN if k == 0 else HP_SHADE

    mb.loft(band_rings, band_col, cap_bottom=False, cap_top=False, skip_k=(2,))

    # Two chunky 6-sided cream over-ear cups (skip inner cap tucked into head/hair)
    cup_r = 0.096
    cup_cy = 1.380
    cup_cz = 0.020
    for side in (-1, 1):
        x_in = side * 0.172
        x_out = side * 0.254
        r_in = []
        r_out = []
        for k in range(6):
            a = 2.0 * math.pi * k / 6.0
            dy = cup_r * math.sin(a)
            dz = cup_r * math.cos(a)
            r_in.append(V(x_in, cup_cy + dy, cup_cz + dz))
            r_out.append(V(x_out, cup_cy + dy * 0.88, cup_cz + dz * 0.88))
        mb.loft([r_in, r_out], HP_SHADE, cap_bottom=False, cap_top=True, top_color=HP_MAIN)

    # =========================================================================
    # 6. PAINTED CREAM "W" HOODIE TORSO + FOLDED HOOD (16 + 10 = 26 tris, MAT_HOODIE)
    # =========================================================================
    mb.set_part("hoodie", bone="Torso")
    # 6-sided soft boxy torso (phase=pi/6 -> k=5 is wide flat front chest face for crisp "W" & pocket!)
    jy0, jy1 = 0.642, 1.132
    t_bot = oval_ring(0.0, jy0, 0.008, 0.232, 0.160, n=6, phase=math.pi / 6.0)
    t_top = oval_ring(0.0, jy1, 0.004, 0.206, 0.142, n=6, phase=math.pi / 6.0)

    # UV wrap around torso in top band v in [0.34, 1.00]:
    # k=5 (front flat face: -X -> +X) maps cleanly to u in [0.00, 0.34] so W center is u=0.170!
    torso_u_spans = {
        5: (0.00, 0.34),  # Front chest (+Z) with "W" & kangaroo pocket
        0: (0.34, 0.48),  # Front-left (+X, +Z)
        1: (0.48, 0.62),  # Back-left (+X, -Z)
        2: (0.62, 0.78),  # Back center (-Z)
        3: (0.78, 0.90),  # Back-right (-X, -Z)
        4: (0.90, 1.00),  # Front-right (-X, +Z)
    }

    def torso_uv(i, k):
        ua, ub = torso_u_spans[k]
        return [(ua, 0.34), (ub, 0.34), (ub, 1.00), (ua, 1.00)]

    # Bottom cap samples shaded cream waist hem; top cap samples clean shoulder fleece
    bot_hoodie_uvs = [(0.65, 0.35), (0.75, 0.35), (0.75, 0.39), (0.65, 0.39), (0.70, 0.37), (0.66, 0.36)]
    top_hoodie_uvs = [(0.65, 0.85), (0.75, 0.85), (0.75, 0.95), (0.65, 0.95), (0.70, 0.90), (0.66, 0.88)]
    mb.loft(
        [t_bot, t_top], TEX_WHITE,
        cap_bottom=True, cap_top=True,
        mat_idx=MAT_HOODIE,
        uv_fn=torso_uv,
        bot_uvs=bot_hoodie_uvs,
        top_uvs=top_hoodie_uvs,
    )

    # Chunky folded hood draped cozily behind/around neck (skip bottom buried in torso = 10 tris)
    hd_bot = [
        V(-0.145, 1.115,  0.075),
        V( 0.145, 1.115,  0.075),
        V( 0.178, 1.102, -0.228),
        V(-0.178, 1.102, -0.228),
    ]
    hd_top = [
        V(-0.114, 1.186,  0.052),
        V( 0.114, 1.186,  0.052),
        V( 0.152, 1.224, -0.198),
        V(-0.152, 1.224, -0.198),
    ]

    def hood_uv(i, k):
        # Front neck opening k=0 gets slightly deeper inner shadow, outer drape gets sunlit fleece
        if k == 0:
            return [(0.68, 0.04), (0.96, 0.04), (0.96, 0.15), (0.68, 0.15)]
        return [(0.68, 0.14), (0.96, 0.14), (0.96, 0.31), (0.68, 0.31)]

    mb.loft(
        [hd_bot, hd_top], TEX_WHITE,
        cap_bottom=False, cap_top=True,
        mat_idx=MAT_HOODIE,
        uv_fn=hood_uv,
        top_uvs=[(0.68, 0.06), (0.96, 0.06), (0.96, 0.20), (0.68, 0.20)],
    )

    # =========================================================================
    # 7. COZY HOODIE SLEEVES (4-sided bent sleeves, MAT_HOODIE = 34 tris)
    #    - Right arm (-X): bent down & forward so cuff tucks warmly into kangaroo pocket!
    #    - Left arm (+X): hangs naturally at side with warm brown hand peeking below cuff!
    # =========================================================================
    mb.set_part("sleeves")

    def build_bent_sleeve(p_sh, p_el, p_wr, bone_name, cap_wrist=False, rx_scale=1.0):
        mb.set_bone(bone_name)
        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        side_x = V(1.0, 0.0, 0.0)

        def ring4(ctr, axis, rx, rperp):
            u = side_x - axis * side_x.dot(axis)
            u = u.normalized()
            v = axis.cross(u).normalized()
            return [
                ctr + u * (-rx) + v * ( rperp),
                ctr + u * ( rx) + v * ( rperp),
                ctr + u * ( rx) + v * (-rperp),
                ctr + u * (-rx) + v * (-rperp),
            ]

        ax_mid = (ax1 + ax2).normalized()
        r_sh = ring4(p_sh, ax1, 0.064 * rx_scale, 0.072 * rx_scale)
        r_el = ring4(p_el, ax_mid, 0.078 * rx_scale, 0.082 * rx_scale)
        r_wr = ring4(p_wr, ax2, 0.060 * rx_scale, 0.064 * rx_scale)

        # Map rings from shoulder (i=0 -> v=0.31) down to ribbed wrist cuff (i=2 -> v=0.00)
        v_levels = [0.31, 0.16, 0.00]

        def slv_uv(i, k):
            u0 = 0.02 + 0.15 * k
            u1 = 0.02 + 0.15 * (k + 1)
            va = v_levels[i]
            vb = v_levels[i + 1]
            return [(u0, va), (u1, va), (u1, vb), (u0, vb)]

        mb.loft(
            [r_sh, r_el, r_wr], TEX_WHITE,
            cap_bottom=False, cap_top=cap_wrist,
            mat_idx=MAT_HOODIE,
            uv_fn=slv_uv,
            top_uvs=[(0.05, 0.01), (0.20, 0.01), (0.20, 0.05), (0.05, 0.05)],
        )

    # Right arm (-X, viewer-facing side in reference): shoulder -> relaxed elbow -> tucked cleanly into front pocket!
    p_r_sh = V(-0.172, 1.044, -0.006)
    p_r_el = V(-0.240, 0.854, -0.010)
    p_r_wr = V(-0.088, 0.752,  0.118)
    build_bent_sleeve(p_r_sh, p_r_el, p_r_wr, "Arm_R", cap_wrist=True, rx_scale=0.98)

    # Left arm (+X, far side in reference): gentle relaxed campus swing down beside hip!
    p_l_sh = V( 0.178, 1.052,  0.004)
    p_l_el = V( 0.260, 0.862,  0.002)
    p_l_wr = V( 0.252, 0.708,  0.068)
    build_bent_sleeve(p_l_sh, p_l_el, p_l_wr, "Arm_L", cap_wrist=False, rx_scale=1.00)

    # =========================================================================
    # 8. LEFT HAND (warm brown chunky mitten peeking from left cuff, 10 tris)
    #    (Right hand is cozily tucked inside the hoodie's kangaroo pocket!)
    # =========================================================================
    mb.set_part("hand_l", bone="Arm_L")
    ax_lh = (p_l_wr - p_l_el).normalized()
    u_lh = V(1.0, 0.0, 0.0) - ax_lh * ax_lh.x
    u_lh = u_lh.normalized()
    v_lh = ax_lh.cross(u_lh).normalized()
    lh_r0 = [
        p_l_wr + u_lh * (-0.052) + v_lh * ( 0.054),
        p_l_wr + u_lh * ( 0.052) + v_lh * ( 0.054),
        p_l_wr + u_lh * ( 0.052) + v_lh * (-0.054),
        p_l_wr + u_lh * (-0.052) + v_lh * (-0.054),
    ]
    lh_c1 = p_l_wr + ax_lh * 0.102
    lh_r1 = [
        lh_c1 + u_lh * (-0.040) + v_lh * ( 0.042),
        lh_c1 + u_lh * ( 0.040) + v_lh * ( 0.042),
        lh_c1 + u_lh * ( 0.040) + v_lh * (-0.042),
        lh_c1 + u_lh * (-0.040) + v_lh * (-0.042),
    ]
    mb.loft([lh_r0, lh_r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 9. PAINTED 3-PINE-TREE CANVAS BOOK BAG + TWO-TONE STRAP (20 + 24 = 44 tris)
    # =========================================================================
    mb.set_part("book_bag", bone="Bag")
    # Hanging naturally at a gentle backward tilt on her right hip (-X), matching reference!
    bag_tilt = math.radians(-14.0)
    ct, st = math.cos(bag_tilt), math.sin(bag_tilt)
    bag_orig = V(-0.278, 0.668, -0.088)

    def bag_pt(lx, ly, lz):
        ry = ly * ct - lz * st
        rz = ly * st + lz * ct
        return V(bag_orig.x + lx, bag_orig.y + ry, bag_orig.z + rz)

    # Crisp boxy canvas tote with subtle bottom gusset bevel (3 rings -> 20 tris)
    bag_stations = [
        # (ly,     x_in,   x_out,  z_back, z_front)
        (-0.185,  0.048, -0.068, -0.162,  0.162),  # 0: flat bottom base
        (-0.140,  0.064, -0.088, -0.194,  0.194),  # 1: gusset corner belly
        ( 0.168,  0.056, -0.076, -0.200,  0.200),  # 2: top open rim
    ]
    bag_rings = []
    for (ly, xi, xo, zb, zf) in bag_stations:
        bag_rings.append([
            bag_pt(xo, ly, zb),  # 0: outer-back
            bag_pt(xi, ly, zb),  # 1: inner-back
            bag_pt(xi, ly, zf),  # 2: inner-front
            bag_pt(xo, ly, zf),  # 3: outer-front
        ])

    # Face mapping around ring:
    # k=0: back gusset (0->1)
    # k=1: inner face (1->2, facing her leg)
    # k=2: front gusset (2->3)
    # k=3: OUTER FACE (3->0, -X facing viewer -> 3 PAINTED PINE TREES! Note 3 is front, 0 is back)
    # Wait: viewed from -X looking toward +X: left is -Z (back, idx 0), right is +Z (front, idx 3)!
    # In loft: p0=r0[3](front-bot), p1=r0[0](back-bot), p2=r1[0](back-top), p3=r1[3](front-top)
    # So u=0.64 at front (p0,p3) and u=0.01 at back (p1,p2) puts trees upright left-to-right!
    def bag_uv(i, k):
        if i == 0:
            # Lower gusset bevel strip -> warm shaded bottom-fold canvas
            return [(0.68, 0.25), (0.98, 0.25), (0.98, 0.46), (0.68, 0.46)]
        if k == 3:
            # HERO OUTER PANEL with 3 crisp forest-green pine trees!
            return [(0.64, 0.03), (0.01, 0.03), (0.01, 0.98), (0.64, 0.98)]
        # Gussets & inner panel -> matching woven cream canvas with vertical crease
        return [(0.68, 0.52), (0.98, 0.52), (0.98, 0.98), (0.68, 0.98)]

    mb.loft(
        bag_rings, TEX_WHITE,
        cap_bottom=True, cap_top=True,
        mat_idx=MAT_BAG,
        uv_fn=bag_uv,
        bot_uvs=[(0.68, 0.25), (0.98, 0.25), (0.98, 0.46), (0.68, 0.46)],
        top_uvs=[(0.68, 0.03), (0.98, 0.03), (0.98, 0.19), (0.68, 0.19)],
    )

    # Shoulder strap arching smoothly over right shoulder, completely clearing Arm_R sleeve!
    # Matches reference's signature two-tone strap: dark brown front strap + cream canvas back strap!
    mb.set_part("bag_strap", bone="Bag")
    strap_loop = [
        bag_pt(-0.044, 0.156,  0.174),  # 0: front rim attachment (smooth taut line up to shoulder)
        V(-0.282, 0.990,  0.072),       # 1: smooth front curve clearing upper arm cleanly
        V(-0.202, 1.146,  0.004),       # 2: shoulder crest resting cleanly on hoodie shoulder
        V(-0.278, 0.992, -0.134),       # 3: rear descent clear behind elbow
        bag_pt(-0.044, 0.156, -0.122),  # 4: back rim attachment
    ]
    strap_norms = [
        V(-0.88, 0.0,  0.48),
        V(-0.78, 0.22,  0.58),
        V(-0.30, 0.95,  0.05),
        V(-0.72, 0.20, -0.66),
        V(-0.88, 0.0, -0.47),
    ]
    mb.tri_strap(
        strap_loop, strap_norms,
        half_w=0.032, thick=0.018,
        colors=lambda i, k: BAG_STRAP_DARK if i <= 1 else BAG_STRAP_CREAM,
    )

    # =========================================================================
    # 10. DARK CHARCOAL WIDE-LEG PANTS (8 + 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.192, 0.192, 0.545, 0.665, -0.112, 0.112, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        # Relaxed wide-leg campus trousers flaring subtly toward ankle hem
        x_in_t, x_out_t = side * 0.008, side * 0.190
        x_in_b, x_out_b = side * 0.048, side * 0.244
        rz_t, rz_b = 0.104, 0.114
        r_top = [
            V(min(x_in_t, x_out_t), 0.580,  rz_t),
            V(max(x_in_t, x_out_t), 0.580,  rz_t),
            V(max(x_in_t, x_out_t), 0.580, -rz_t),
            V(min(x_in_t, x_out_t), 0.580, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.120,  rz_b),
            V(max(x_in_b, x_out_b), 0.120,  rz_b),
            V(max(x_in_b, x_out_b), 0.120, -rz_b),
            V(min(x_in_b, x_out_b), 0.120, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 11. CHUNKY CREAM SNEAKERS (14 tris x 2 = 28 tris)
    # =========================================================================
    mb.set_part("shoes")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.146
        w = 0.070
        w_toe = 0.058
        z_heel = -0.092
        z_mid  =  0.062
        z_toe  =  0.170
        y_bot  =  0.000
        y_toe  =  0.072
        y_col  =  0.136

        p_bl_h = V(cx - w,     y_bot, z_heel)
        p_br_h = V(cx + w,     y_bot, z_heel)
        p_bl_t = V(cx - w_toe, y_bot, z_toe)
        p_br_t = V(cx + w_toe, y_bot, z_toe)

        p_tl_h = V(cx - w * 0.90,     y_col, z_heel + 0.010)
        p_tr_h = V(cx + w * 0.90,     y_col, z_heel + 0.010)
        p_tl_m = V(cx - w * 0.90,     y_col, z_mid)
        p_tr_m = V(cx + w * 0.90,     y_col, z_mid)
        p_tl_t = V(cx - w_toe * 0.90, y_toe, z_toe - 0.012)
        p_tr_t = V(cx + w_toe * 0.90, y_toe, z_toe - 0.012)

        mb.face([p_bl_h, p_br_h, p_br_t, p_bl_t], SOLE,      out=(0, -1, 0))
        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], SHOE,      out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], SHOE,      out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], SHOE_VAMP, out=(0, 1, 0.5))
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], SHOE,      out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h],         SHOE,      out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], SHOE,      out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m],         SHOE,      out=(1, 0, 0))

    return mb


def setup_materials(hoodie_img, bag_img):
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

    def make_tex_mat(name, img, roughness=0.88):
        mat = bpy.data.materials.new(name)
        nt_t = mat.node_tree
        bsdf_t = next(n for n in nt_t.nodes if n.type == "BSDF_PRINCIPLED")
        tex_t = nt_t.nodes.new("ShaderNodeTexImage")
        tex_t.image = img
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
            bsdf_t.inputs["Specular IOR Level"].default_value = 0.18
        return mat

    mat_hoodie = make_tex_mat("StudentGirlHoodie", hoodie_img, roughness=0.90)
    mat_bag = make_tex_mat("StudentGirlBag", bag_img, roughness=0.92)
    return [mat_vcol, mat_hoodie, mat_bag]


def _reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: relaxed campus stroll, headphone head-bob, pocket-tucked right arm & swinging book bag."""
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

        # Upbeat campus walk bounce & slight forward lean
        pb_root = rig.pose.bones["Root"]
        bob = -0.025 * (1.0 - c2) * 0.5
        root_pitch = -0.050
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.068 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Natural torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * c2, 0.088 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Charming headphone music-groove head bob!
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.042 + 0.052 * s2, -0.045 * s1, 0.028 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Clean wide-leg stride with crisp sneaker lift
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.45 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.038, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.45 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.038, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Free left arm counter-swings naturally at her side
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.34 * s1, 0.0, 0.020 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm stays cozily tucked in the hoodie's kangaroo pocket with tiny bounce!
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.032 * c2, 0.0, -0.016 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Phase-lagged secondary pendulum swing on the 3-tree book bag
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.064 * math.sin(phi - 0.60), 0.0, 0.024 * c1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: relaxed campus wait, headphone head-nod groove & gentle bag sway."""
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

        # Relaxed standing weight shift & calm breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.012, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * s2, 0.028 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Upbeat music-listening head bob & casual campus glance
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.088 * s2, 0.21 * s1, 0.048 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sneakers stay firmly planted
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed left arm drift
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.048 * s1, 0.0, 0.016 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm gently shifts with breathing inside hoodie pocket
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.022 * s2, 0.0, -0.010 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Soft breeze sway on book bag
        pb_bag = rig.pose.bones["Bag"]
        pb_bag.rotation_euler = (0.024 * s2, 0.0, -0.018 * s1)
        pb_bag.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Bag) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonStudentGirlRig")
    rig = bpy.data.objects.new("PersonStudentGirlRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.615,  0.000), ( 0.000, 0.715,  0.000)),
        ("Torso", "Root",  ( 0.000, 0.670,  0.000), ( 0.000, 1.125,  0.000)),
        ("Head",  "Torso", ( 0.000, 1.165,  0.000), ( 0.000, 1.485,  0.000)),
        ("Arm_L", "Torso", ( 0.178, 1.055,  0.000), ( 0.178, 1.215,  0.000)),
        ("Arm_R", "Torso", (-0.178, 1.055,  0.000), (-0.178, 1.215,  0.000)),
        ("Bag",   "Torso", (-0.195, 1.115, -0.020), (-0.195, 1.275, -0.020)),
        ("Leg_L", "Root",  ( 0.106, 0.565,  0.000), ( 0.106, 0.725,  0.000)),
        ("Leg_R", "Root",  (-0.106, 0.565,  0.000), (-0.106, 0.725,  0.000)),
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

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-1.74, math.radians(56)),   # Front-3/4 matching reference angle (facing right)
        (-0.58, math.radians(0)),    # Front (showing "W" sweatshirt & bangs)
        ( 0.58, math.radians(90)),   # Side (showing 3-tree tote bag, headphones & curly puff)
        ( 1.74, math.radians(180)),  # Back (showing full afro puff & folded hood)
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
    cam_data.ortho_scale = 4.9
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.18
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 7.4
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
    fill_data.energy = 0.95
    fill_data.color = (0.90, 0.94, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(65), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("VidFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.05
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

    coll = bpy.data.collections.new("PersonStudentGirl")
    bpy.context.scene.collection.children.link(coll)

    hoodie_img = generate_hoodie_texture(HOODIE_TEX_PATH)
    bag_img = generate_bag_texture(BAG_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonStudentGirl")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(hoodie_img, bag_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonStudentGirl", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris < 350, f"Triangle budget exceeded: {total_tris} >= 350"

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    # Export GLB with both Walk and Idle animations + embedded textures + Part UV via ACTIONS mode
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
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=52, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=44, zrot_right_deg=90)

    print("=== PersonStudentGirl Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    print(f"Hoodie texture:  {HOODIE_TEX_PATH}")
    print(f"Bag texture:     {BAG_TEX_PATH}")
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
