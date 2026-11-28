# Builds an ultra-low-poly (< 350 tris) stylized woman hiker/tourist with a texture-painted
# two-tone sage-and-taupe trucker baseball cap (with a snow-capped mountain emblem on the front),
# dark-brown hair with a chunky braided ponytail, teal hooded hiking jacket with mint-sage hood
# collar & elbow accents, dark slate backpack with side pockets & straps, golden-ochre rolled
# bedroll strapped atop the pack, khaki hiking shorts, bare legs with cream hiking socks, chunky
# brown hiking boots, and a pair of dark trekking poles held in both hands in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_hiker_woman.py)
# Saves art/person_hiker_woman.blend, exports assets/models/person_hiker_woman.glb (rigged + Walk & Idle cycles + embedded texture),
# renders art/person_hiker_woman_preview.png, art/person_hiker_woman_walk_preview.png,
# art/person_hiker_woman_idle_preview.png, and outputs rendered videos
# art/person_hiker_woman_walk.mp4 and art/person_hiker_woman_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.67 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_hiker_woman.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_hiker_woman.glb")
HAT_TEX_PATH = os.path.join(ROOT, "art", "person_hiker_woman_hat_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_hiker_woman_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_hiker_woman_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_hiker_woman_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_hiker_woman_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_hiker_woman_idle.mp4")

MAT_VCOL = 0
MAT_HAT = 1


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette closely matched to reference woman hiker concept art (sRGB -> linear).
# Every part has its own unique constants so person_recolor.py tags cleanly without collisions.
TEX_WHITE        = col_srgb(1.00, 1.00, 1.00)

SKIN             = col_srgb(0.98, 0.77, 0.53)
SKIN_SHADE       = col_srgb(0.87, 0.65, 0.42)
EYE              = col_srgb(0.11, 0.10, 0.11)

HAIR             = col_srgb(0.39, 0.28, 0.22)
HAIR_HIGHLIGHT   = col_srgb(0.50, 0.37, 0.29)
HAIR_SHADE       = col_srgb(0.28, 0.19, 0.15)

SHIRT            = col_srgb(0.22, 0.24, 0.27)

JACKET           = col_srgb(0.38, 0.58, 0.57)
JACKET_SHADE     = col_srgb(0.28, 0.46, 0.46)
JACKET_HOOD      = col_srgb(0.49, 0.73, 0.61)
JACKET_PATCH     = col_srgb(0.52, 0.76, 0.64)

PACK             = col_srgb(0.31, 0.36, 0.34)
PACK_SHADE       = col_srgb(0.22, 0.26, 0.25)
PACK_POCKET      = col_srgb(0.40, 0.45, 0.43)
PACK_STRAP       = col_srgb(0.24, 0.25, 0.26)
PACK_BUCKLE      = col_srgb(0.36, 0.33, 0.30)

BEDROLL          = col_srgb(0.90, 0.71, 0.37)
BEDROLL_SHADE    = col_srgb(0.77, 0.58, 0.27)
BEDROLL_END      = col_srgb(0.95, 0.79, 0.47)
BEDROLL_CORE     = col_srgb(0.72, 0.54, 0.25)

SHORTS           = col_srgb(0.63, 0.53, 0.40)
SHORTS_SHADE     = col_srgb(0.50, 0.41, 0.30)

SOCK             = col_srgb(0.95, 0.91, 0.82)
SOCK_SHADE       = col_srgb(0.83, 0.78, 0.69)

BOOT             = col_srgb(0.63, 0.49, 0.36)
BOOT_SHADE       = col_srgb(0.51, 0.38, 0.27)
BOOT_TONGUE      = col_srgb(0.31, 0.28, 0.25)
SOLE             = col_srgb(0.25, 0.22, 0.20)

POLE_SHAFT       = col_srgb(0.29, 0.30, 0.32)
POLE_GRIP        = col_srgb(0.18, 0.19, 0.21)
POLE_BASKET      = col_srgb(0.21, 0.22, 0.24)

# Parts the game recolours per passenger (see art/person_recolor.py).
# Texture-painted mountain cap, inner shirt, backpack, socks, boots, and trekking poles stay fixed.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR, HAIR_HIGHLIGHT, HAIR_SHADE],
    "top": [JACKET, JACKET_SHADE, JACKET_HOOD, JACKET_PATCH],
    "bottom": [SHORTS, SHORTS_SHADE],
    "accent": [BEDROLL, BEDROLL_SHADE, BEDROLL_END, BEDROLL_CORE],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared structural anchors for rig & geometry alignment
SHOULDER_Y = 1.045
SHOULDER_Z = -0.002
HAND_L = V( 0.260, 0.742, 0.214)
HAND_R = V(-0.260, 0.742, 0.214)


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def generate_hat_texture(out_path):
    """Paint a 512x512 sRGB trucker baseball cap texture with a crisp mountain logo patch:
       - Upper band (v in [0.38, 1.00]):
           * Center front panel (u in [0.30, 0.70]): warm taupe-grey fabric with subtle canvas weave,
             stitched trucker side seams, and a multi-peak forest-green & snow-capped mountain emblem.
           * Side & rear panels (u in [0.00, 0.30] and [0.70, 1.00]): muted sage-olive green with
             subtle panel seams and gentle back shading.
       - Lower strip (v in [0.00, 0.36]):
           * Visor top (u in [0.00, 0.48]): sage-olive brim with concentric stitched arcs.
           * Visor underside (u in [0.50, 0.76]): deep forest-olive shade.
           * Crown top cap (u in [0.78, 1.00]): two-tone taupe-front / olive-back with center cap button.
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # Base sage-olive fabric across entire canvas
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[..., 0] = 0.41
    img[..., 1] = 0.46
    img[..., 2] = 0.40

    # Subtle woven twill grain
    weave = 1.0 + 0.015 * np.sin(uu * 240.0) * np.cos(vv * 240.0)
    img *= weave[..., None]

    # --- 1. CROWN BAND (v >= 0.37) ---
    in_crown = vv >= 0.37
    crown_v = np.clip((vv - 0.38) / 0.62, 0.0, 1.0)

    # Gentle back-panel darkening toward u=0 and u=1 (back center of cap)
    back_dist = np.minimum(uu, 1.0 - uu)
    back_shade = np.clip((0.18 - back_dist) / 0.18, 0.0, 1.0)
    img = _blend_mask(img, in_crown * back_shade * 0.38, (0.28, 0.33, 0.28))

    # Vertical panel seam lines on sage sides (at u=0.15 and u=0.85)
    side_seam = np.maximum(
        np.clip((0.006 - np.abs(uu - 0.15)) / 0.003, 0.0, 1.0),
        np.clip((0.006 - np.abs(uu - 0.85)) / 0.003, 0.0, 1.0),
    )
    img = _blend_mask(img, in_crown * side_seam * 0.32, (0.24, 0.29, 0.24))

    # Warm taupe-grey front trucker panel (u in [0.30, 0.70], v in [0.37, 1.00])
    front_panel = (
        in_crown.astype(np.float32)
        * np.clip((uu - 0.296) / 0.008, 0.0, 1.0)
        * np.clip((0.704 - uu) / 0.008, 0.0, 1.0)
    )
    img = _blend_mask(img, front_panel, (0.69, 0.67, 0.62))

    # Subtle dome shading on crown (slightly brighter on upper curve, darker sweatband rim)
    dome_light = 0.93 + 0.10 * np.sin(crown_v * math.pi * 0.82)
    img = np.where(in_crown[..., None], img * dome_light[..., None], img)

    # Crisp dark-olive piping / stitching border framing front trucker panel
    panel_border = np.maximum(
        np.clip((0.007 - np.abs(uu - 0.300)) / 0.003, 0.0, 1.0),
        np.clip((0.007 - np.abs(uu - 0.700)) / 0.003, 0.0, 1.0),
    )
    img = _blend_mask(img, in_crown * panel_border * 0.45, (0.29, 0.34, 0.29))

    # Subtle bottom headband stitch line across crown base
    band_seam = np.clip((0.005 - np.abs(vv - 0.415)) / 0.003, 0.0, 1.0)
    img = _blend_mask(img, in_crown * band_seam * 0.14, (0.30, 0.34, 0.29))

    # --- 1b. ICONIC MOUNTAIN LOGO ON FRONT PANEL (centered at u=0.50, v=0.64) ---
    # Local patch coordinates: x in [-1, 1] across u in [0.33, 0.67], y in [0, 1] across v in [0.47, 0.86]
    px = (uu - 0.50) / 0.168
    py = (vv - 0.48) / 0.36

    # Gently arched horizon base line of the emblem (matching reference artwork!)
    base_y = 0.04 + 0.08 * np.clip(1.0 - px * px, 0.0, 1.0)

    # Three-peak mountain ridge profile: tall crisp center peak + left & right shoulders
    ridge_ctr = 0.94 - 1.24 * np.abs(px - 0.00)
    ridge_l   = 0.58 - 1.28 * np.abs(px + 0.46)
    ridge_r   = 0.64 - 1.20 * np.abs(px - 0.44)
    ridge = np.maximum(ridge_ctr, np.maximum(ridge_l, ridge_r))

    # Soft anti-aliased mountain silhouette mask
    aa = 0.025
    in_mtn = (
        np.clip((ridge - py) / aa, 0.0, 1.0)
        * np.clip((py - base_y) / aa, 0.0, 1.0)
        * np.clip((1.02 - np.abs(px)) / 0.04, 0.0, 1.0)
        * in_crown.astype(np.float32)
    )

    # Rich forest-green mountain base
    img = _blend_mask(img, in_mtn, (0.27, 0.43, 0.35))

    # Subtle deeper pine shadow on the right slopes of the main peaks for crisp faceted depth
    shadow_slope = (
        in_mtn
        * np.clip((px - 0.00) / 0.04, 0.0, 1.0)
        * np.clip((0.36 - px) / 0.08, 0.0, 1.0)
    )
    img = _blend_mask(img, shadow_slope * 0.42, (0.17, 0.30, 0.24))

    # Crisp cream-white snow caps on the peaks with stylized jagged alpine snowline!
    jag = 0.065 * np.sin(px * 19.0 + 0.4)
    snow_ctr = py - (0.52 + 0.28 * np.abs(px) + jag)
    snow_l   = py - (0.37 + 0.25 * np.abs(px + 0.46) - 0.04 * np.cos(px * 22.0))
    snow_r   = py - (0.41 + 0.25 * np.abs(px - 0.44) + 0.04 * np.cos(px * 22.0))
    snow_val = np.maximum(
        snow_ctr * (np.abs(px) < 0.34),
        np.maximum(snow_l * (px < -0.22), snow_r * (px > 0.20)),
    )
    # Use clean continuous snowline across all 3 peaks
    snow_line = np.minimum(
        0.51 + 0.25 * np.abs(px) + 0.055 * np.sin(px * 20.0),
        np.minimum(
            0.39 + 0.35 * np.abs(px + 0.46),
            0.42 + 0.35 * np.abs(px - 0.44),
        ),
    )
    in_snow = in_mtn * np.clip((py - snow_line) / aa, 0.0, 1.0)
    img = _blend_mask(img, in_snow, (0.96, 0.94, 0.88))

    # Crisp dark-sage accent underline right below the mountain base
    under_bar = (
        np.clip((0.022 - np.abs(py - (base_y - 0.015))) / 0.010, 0.0, 1.0)
        * np.clip((0.94 - np.abs(px)) / 0.04, 0.0, 1.0)
        * in_crown.astype(np.float32)
    )
    img = _blend_mask(img, under_bar * 0.55, (0.19, 0.31, 0.25))

    # --- 2. LOWER STRIP (v < 0.37): VISOR TOP, VISOR UNDERSIDE, CROWN TOP CAP ---
    in_low = vv < 0.37

    # 2a. Visor top (u in [0.00, 0.49], v in [0.00, 0.37]): sage-olive with subtle concentric stitching
    in_vtop = in_low & (uu < 0.49)
    vt_u = uu / 0.48
    vt_v = vv / 0.36
    # Subtle warm highlight along outer bill edge
    vtop_col = np.zeros((h, w, 3), dtype=np.float32)
    vtop_col[..., 0] = 0.42 + 0.04 * vt_v
    vtop_col[..., 1] = 0.48 + 0.04 * vt_v
    vtop_col[..., 2] = 0.41 + 0.03 * vt_v
    # Concentric stitching arcs near visor front edge (v near 0.22 and 0.29)
    arc_r = np.sqrt(((vt_u - 0.50) * 1.15) ** 2 + (vt_v * 0.95) ** 2)
    stitch = np.maximum(
        np.clip((0.014 - np.abs(arc_r - 0.68)) / 0.006, 0.0, 1.0),
        np.clip((0.014 - np.abs(arc_r - 0.80)) / 0.006, 0.0, 1.0),
    )
    vtop_col = _blend_mask(vtop_col, stitch * 0.24, (0.28, 0.33, 0.28))
    img = np.where(in_vtop[..., None], vtop_col * weave[..., None], img)

    # 2b. Visor underside (u in [0.49, 0.77], v in [0.00, 0.37]): deep forest-olive shade
    in_vbot = in_low & (uu >= 0.49) & (uu < 0.77)
    vbot_col = np.zeros((h, w, 3), dtype=np.float32)
    vbot_col[..., 0] = 0.24
    vbot_col[..., 1] = 0.29
    vbot_col[..., 2] = 0.25
    img = np.where(in_vbot[..., None], vbot_col * weave[..., None], img)

    # 2c. Crown top cap (u in [0.77, 1.00], v in [0.00, 0.37]):
    #     Normalized local coords (tx, ty) in [-1, 1], +ty = front (+Z), -ty = back (-Z)
    in_ctop = in_low & (uu >= 0.77)
    tx = (uu - 0.885) / 0.105
    ty = (vv - 0.180) / 0.165
    ctop_col = np.zeros((h, w, 3), dtype=np.float32)
    ctop_col[..., 0] = 0.42
    ctop_col[..., 1] = 0.47
    ctop_col[..., 2] = 0.41
    # Front trucker wedge (ty > 0 and |tx| < ty * 1.25) is warm taupe-grey!
    front_wedge = np.clip((ty - np.abs(tx) * 0.58 + 0.02) / 0.06, 0.0, 1.0)
    ctop_col = _blend_mask(ctop_col, front_wedge, (0.71, 0.69, 0.64))
    # Subtle 6-panel radial seams meeting at the crown button
    ang = np.arctan2(tx, ty)
    rad = np.sqrt(tx * tx + ty * ty)
    seam_radial = np.clip((0.045 - np.abs(np.sin(ang * 3.0)) * rad) / 0.02, 0.0, 1.0)
    ctop_col = _blend_mask(ctop_col, seam_radial * 0.22, (0.28, 0.33, 0.28))
    # Cute dark olive crown top button in center!
    btn = np.clip((0.18 - rad) / 0.03, 0.0, 1.0)
    ctop_col = _blend_mask(ctop_col, btn, (0.31, 0.36, 0.31))
    img = np.where(in_ctop[..., None], ctop_col * weave[..., None], img)

    img = np.clip(img, 0.0, 1.0)

    bimg = bpy.data.images.new("HikerHatTex", width=w, height=h, alpha=True, float_buffer=False)
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
                self.face(r0, col, out=out_dir, weights=([wb] * n if wb else None), mat_idx=mat_idx)
            elif n == 5:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb else None), mat_idx=mat_idx)
                self.face([r0[0], r0[3], r0[4]], col, out=out_dir, weights=([wb] * 3 if wb else None), mat_idx=mat_idx)
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir, weights=([wb] * 4 if wb else None), mat_idx=mat_idx)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir, weights=([wb] * 4 if wb else None), mat_idx=mat_idx)
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
                self.face(rt, col, out=out_dir, weights=([wt] * n if wt else None), mat_idx=mat_idx)
            elif n == 5:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt else None), mat_idx=mat_idx)
                self.face([rt[0], rt[3], rt[4]], col, out=out_dir, weights=([wt] * 3 if wt else None), mat_idx=mat_idx)
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir, weights=([wt] * 4 if wt else None), mat_idx=mat_idx)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir, weights=([wt] * 4 if wt else None), mat_idx=mat_idx)
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


def oval_ring(cx, cy, cz, rx, rz, n=6, phase=0.0):
    pts = []
    for k in range(n):
        a = phase + 2.0 * math.pi * k / n
        pts.append(V(cx + rx * math.sin(a), cy, cz + rz * math.cos(a)))
    return pts


def tilted_ring(cx, cy, cz, rx, rz, tilt_rad, n=6, phase=math.pi / 6.0):
    """Ring tilted backward around X by tilt_rad (+tilt raises +Z front, lowers -Z back)."""
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
    # 1. HEAD (6-sided stylized low-poly head, y = 1.18..1.45 = 26 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.180,  0.018, 0.148, 0.144),  # 0: chin/jawline
        (1.268,  0.022, 0.208, 0.198),  # 1: full rounded cheeks
        (1.452,  0.010, 0.194, 0.186),  # 2: brow tucked cleanly inside trucker cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 wide flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks, k=1,2,3 rich brown hair
    def head_color(i, k):
        if i == 0:
            return HAIR_SHADE if k in (1, 2, 3) else SKIN
        return SKIN if k in (4, 5, 0) else HAIR

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)
    # Front chin underside cap (2 tris)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. SIDE HAIR LOCKS + CHUNKY BRAIDED PONYTAIL (6 + 25 = 31 tris)
    # =========================================================================
    mb.set_part("hair_sides", bone="Head")
    # Sleek dark-brown temple/sideburn curtains hugging cheeks cleanly beneath cap (3 tris/side = 6 tris)
    for side in (-1, 1):
        p_tf = V(side * 0.194, 1.430,  0.072)
        p_tb = V(side * 0.204, 1.404, -0.098)
        p_bf = V(side * 0.188, 1.214,  0.002)
        p_bb = V(side * 0.204, 1.202, -0.116)
        p_if = V(side * 0.148, 1.226,  0.036)
        mb.face([p_bf, p_bb, p_tb, p_tf], HAIR_HIGHLIGHT if side < 0 else HAIR, out=(side, 0, 0))
        mb.face([p_if, p_bf, p_tf], HAIR_SHADE, out=(side * 0.35, 0, 0.94))

    # Iconic chunky BRAIDED PONYTAIL cascading from under back-right cap rim down over right shoulder!
    # 5-ring (4-segment) staggered 3-sided braided plait chain + tapered tail tip (4*6 + 1 = 25 tris!)
    # Starts tucked solidly inside the back-right cap rim with zero floating gap, and zig-zags
    # with bold alternating diamond weave bulges & herringbone shading clearly ahead of the bedroll!
    mb.set_part("hair_braid")
    braid_specs = [
        # (center_pos,                   rx,    rz,    phase_deg, weight_head, weight_braid)
        (V(-0.080, 1.356, -0.168), 0.056, 0.054,   0.0, 0.90, 0.10),  # 0: tucked solidly under back cap rim
        (V(-0.152, 1.242, -0.140), 0.074, 0.070,  60.0, 0.40, 0.60),  # 1: plait 1 plump weave bulge
        (V(-0.156, 1.132, -0.108), 0.070, 0.066,   0.0, 0.15, 0.85),  # 2: plait 2 counter-weave bulge
        (V(-0.180, 1.022, -0.130), 0.066, 0.062,  60.0, 0.05, 0.95),  # 3: plait 3 lower weave bulge
        (V(-0.172, 0.904, -0.108), 0.038, 0.036,   0.0, 0.00, 1.00),  # 4: plump braided tassel tip
    ]
    braid_rings = []
    braid_weights = []
    for (ctr, rx, rz, pdeg, wh, wb) in braid_specs:
        ph = math.radians(pdeg)
        ring = []
        for k in range(3):
            a = ph + 2.0 * math.pi * k / 3.0
            ring.append(V(ctr.x + rx * math.sin(a), ctr.y, ctr.z + rz * math.cos(a)))
        braid_rings.append(ring)
        braid_weights.append({"Head": wh, "Braid": wb} if wh > 0.0 else {"Braid": 1.0})

    def braid_color(i, k):
        # Checkerboard herringbone shading across alternating plait segments
        if (i + k) % 3 == 0:
            return HAIR_HIGHLIGHT
        if (i + k) % 3 == 1:
            return HAIR
        return HAIR_SHADE

    mb.loft(
        braid_rings,
        braid_color,
        cap_bottom=False, cap_top=True, top_color=HAIR_SHADE,
        ring_weights=braid_weights,
    )

    # =========================================================================
    # 3. EARS (2 cute soft peach ear tabs peeking out of brown side hair = 4 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in  = side * 0.194
        x_out = side * 0.220
        p_t   = V(x_in,  1.338, 0.062)
        p_b   = V(x_in,  1.276, 0.058)
        p_o   = V(x_out, 1.308, 0.036)
        p_bk  = V(x_in,  1.308, 0.014)
        mb.face([p_b, p_o, p_t],  SKIN,       out=(side * 0.4, 0, 0.9))
        mb.face([p_t, p_o, p_bk], SKIN_SHADE, out=(side * 0.4, 0, -0.9))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill rectangles flush on flat front face = 4 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.189
    for side in (-1, 1):
        cx = side * 0.062
        cy = 1.356
        rx = 0.017
        ry = 0.043
        mb.face([
            V(cx - rx, cy - ry, z_eye),
            V(cx + rx, cy - ry, z_eye),
            V(cx + rx, cy + ry, z_eye),
            V(cx - rx, cy + ry, z_eye),
        ], EYE, out=(0, 0, 1))

    # =========================================================================
    # 5. NECK (3-sided tapered cylinder skipping hidden rear = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    neck_r0 = oval_ring(0.0, 1.078, 0.010, 0.066, 0.062, n=3, phase=0.0)
    neck_r1 = oval_ring(0.0, 1.190, 0.014, 0.062, 0.058, n=3, phase=0.0)
    mb.loft([neck_r0, neck_r1], SKIN_SHADE, cap_bottom=False, cap_top=False, skip_k=(1,))

    # =========================================================================
    # 6. TEXTURE-PAINTED MOUNTAIN TRUCKER CAP (6-sided dome + curved visor = 34 tris)
    # =========================================================================
    mb.set_part("trucker_cap", bone="Head")
    cap_tilt = math.radians(15.5)  # jaunty slight backward tilt showing eyes & mountain patch proudly!
    st, ct = math.sin(cap_tilt), math.cos(cap_tilt)
    cap_orig = V(0.0, 1.418, -0.006)

    def cap_ring(h, rx, rz):
        cy = cap_orig.y + h * ct
        cz = cap_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, cap_tilt, n=6, phase=math.pi / 6.0)

    c_rim = cap_ring(0.000, 0.238, 0.236)  # snug trucker headband rim enclosing brow
    c_mid = cap_ring(0.128, 0.218, 0.214)  # high structured trucker front crown
    c_top = cap_ring(0.212, 0.116, 0.114)  # soft crown peak

    # Map each of the 6 crown panels cleanly onto the upper band (v in [0.38, 0.99]) of HikerHatTex:
    # k=5 is the wide front (+Z) panel spanning u=[0.30..0.70] (taupe-grey + mountain emblem!)
    # k=4 (front-right) -> [0.15..0.30], k=0 (front-left) -> [0.70..0.85], back panels -> [0.00..0.15] & [0.85..1.00]
    cap_u_spans = {
        5: (0.300, 0.700),  # Front center panel (+Z): mountain logo!
        0: (0.700, 0.850),  # Front-left sage panel
        1: (0.850, 0.945),  # Back-left sage panel
        2: (0.945, 0.995),  # Back center sage panel
        3: (0.005, 0.150),  # Back-right sage panel
        4: (0.150, 0.300),  # Front-right sage panel
    }
    cap_v_levels = [0.390, 0.765, 0.985]

    def cap_uv(i, k):
        u0, u1 = cap_u_spans[k]
        v0, v1 = cap_v_levels[i], cap_v_levels[i + 1]
        return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]

    # Rounded 6-sided crown walls (24 tris)
    mb.loft([c_rim, c_mid, c_top], TEX_WHITE, cap_bottom=False, cap_top=False,
            mat_idx=MAT_HAT, uv_fn=cap_uv)

    # Crown top cap mapped onto the dedicated circular two-tone cap-top region (u in [0.78..0.99], v in [0.02..0.34] = 4 tris)
    def top_uv_of(k):
        a = math.pi / 6.0 + 2.0 * math.pi * k / 6.0
        tx = math.sin(a) * 0.90
        ty = math.cos(a) * 0.90
        return (0.885 + tx * 0.105, 0.180 + ty * 0.165)

    mb.face(
        [c_top[5], c_top[0], c_top[1], c_top[4]],
        TEX_WHITE, out=(0, ct, -st), mat_idx=MAT_HAT,
        uvs=[top_uv_of(5), top_uv_of(0), top_uv_of(1), top_uv_of(4)],
    )
    mb.face(
        [c_top[4], c_top[1], c_top[2], c_top[3]],
        TEX_WHITE, out=(0, ct, -st), mat_idx=MAT_HAT,
        uvs=[top_uv_of(4), top_uv_of(1), top_uv_of(2), top_uv_of(3)],
    )

    # Curved forward trucker bill/visor (2-segment curved top = 4 tris + clean underside = 2 tris -> 6 tris!)
    v_in_r = c_rim[5]
    v_in_m = (c_rim[5] + c_rim[0]) * 0.5 + V(0.0, 0.004, 0.010)
    v_in_l = c_rim[0]
    v_out_r = V(-0.188, 1.424, 0.296)
    v_out_m = V( 0.000, 1.440, 0.376)
    v_out_l = V( 0.188, 1.424, 0.296)

    # Visor top (2 curved quads mapped to sage-olive stitched visor strip u in [0.02..0.46], v in [0.02..0.34])
    mb.face([v_in_r, v_out_r, v_out_m, v_in_m], TEX_WHITE, out=(0, 1, 0.2), mat_idx=MAT_HAT,
            uvs=[(0.06, 0.04), (0.04, 0.31), (0.24, 0.34), (0.24, 0.04)])
    mb.face([v_in_m, v_out_m, v_out_l, v_in_l], TEX_WHITE, out=(0, 1, 0.2), mat_idx=MAT_HAT,
            uvs=[(0.24, 0.04), (0.24, 0.34), (0.44, 0.31), (0.42, 0.04)])
    # Visor underside (1 crisp shaded quad mapped to deep olive strip u in [0.52..0.74], v in [0.04..0.32])
    mb.face([
        V(v_in_l.x * 0.95, v_in_l.y - 0.014, v_in_l.z - 0.006),
        V(v_out_l.x * 0.94, v_out_l.y - 0.010, v_out_l.z - 0.004),
        V(v_out_r.x * 0.94, v_out_r.y - 0.010, v_out_r.z - 0.004),
        V(v_in_r.x * 0.95, v_in_r.y - 0.014, v_in_r.z - 0.006),
    ], TEX_WHITE, out=(0, -1, -0.2), mat_idx=MAT_HAT,
            uvs=[(0.74, 0.04), (0.74, 0.32), (0.52, 0.32), (0.52, 0.04)])

    # =========================================================================
    # 7. TEAL HOODED OUTDOOR JACKET + MINT-SAGE HOOD COLLAR + INNER TEE (14 + 7 = 21 tris)
    # =========================================================================
    mb.set_part("jacket_torso", bone="Torso")
    j_bot = oval_ring(0.0, 0.642, 0.006, 0.214, 0.144, n=6, phase=math.pi / 6.0)
    j_top = oval_ring(0.0, 1.092, 0.004, 0.190, 0.132, n=6, phase=math.pi / 6.0)
    mb.loft(
        [j_bot, j_top],
        lambda i, k: JACKET_SHADE if k in (1, 2, 3) else JACKET,
        cap_bottom=False, cap_top=False,
    )
    # Clean single shoulder deck quad bridging across both shoulders (center covered by hood/neck = 2 tris)
    mb.face([j_top[5], j_top[0], j_top[2], j_top[3]], JACKET, out=(0, 1, 0))

    # Cozy folded mint-sage outdoor jacket hood/collar framing throat & nape (3 outer flaps = 6 tris + 1 dark V-neck tri = 7 tris)
    mb.set_part("jacket_hood", bone="Torso")
    hd_b0 = V(-0.074, 1.062,  0.134)
    hd_b1 = V(-0.156, 1.084, -0.024)
    hd_b2 = V( 0.156, 1.084, -0.024)
    hd_b3 = V( 0.074, 1.062,  0.134)
    hd_t0 = V(-0.046, 1.158,  0.098)
    hd_t1 = V(-0.128, 1.168, -0.042)
    hd_t2 = V( 0.128, 1.168, -0.042)
    hd_t3 = V( 0.046, 1.158,  0.098)
    mb.face([hd_b0, hd_b1, hd_t1, hd_t0], JACKET_HOOD, out=(-0.75, 0.25,  0.60))
    mb.face([hd_b1, hd_b2, hd_t2, hd_t1], JACKET_HOOD, out=( 0.00, 0.35, -0.94))
    mb.face([hd_b2, hd_b3, hd_t3, hd_t2], JACKET_HOOD, out=( 0.75, 0.25,  0.60))
    # Dark charcoal undershirt triangle peeking cleanly in the front collar V-neck (1 tri)
    mb.set_part("shirt", bone="Torso")
    mb.face([V(0.0, 1.018, 0.138), V(0.056, 1.132, 0.104), V(-0.056, 1.132, 0.104)],
            SHIRT, out=(0, 0.1, 1.0))

    # =========================================================================
    # 8. BENT TEAL JACKET SLEEVES (WITH MINT ELBOW ACCENT) + PEACH FISTS (32 + 20 = 52 tris)
    # =========================================================================
    mb.set_part("sleeves_hands")
    for side in (-1, 1):
        arm_bone = "Arm_L" if side > 0 else "Arm_R"
        mb.set_bone(arm_bone)
        p_sh = V(side * 0.168, SHOULDER_Y, SHOULDER_Z)
        p_el = V(side * 0.264, 0.848, -0.026)
        p_wr = V(side * 0.260, 0.764,  0.146)
        p_hd = HAND_L if side > 0 else HAND_R

        ax1 = (p_el - p_sh).normalized()
        ax2 = (p_wr - p_el).normalized()
        axm = (ax1 + ax2).normalized()

        def s_ring(ctr, axis, rf, ro):
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

        r_sh = s_ring(p_sh, ax1, 0.068, 0.066)
        r_el = s_ring(p_el, axm, 0.078, 0.074)
        r_wr = s_ring(p_wr, ax2, 0.066, 0.064)

        # 2 segments x 4 quads = 16 tris per sleeve (cute mint-sage accent on outer-back elbow facet!)
        mb.loft(
            [r_sh, r_el, r_wr],
            lambda i, k: JACKET_PATCH if (i == 1 and k == 2) else (JACKET_SHADE if k in (2, 3) else JACKET),
            cap_bottom=False, cap_top=False,
        )

        # Chunky peach fist gripping the trekking pole cleanly ahead of the wrist cuff (10 tris per hand)
        ax_h = (p_hd - p_wr).normalized()
        r_h0 = s_ring(p_wr - ax_h * 0.008, ax_h, 0.050, 0.048)
        r_h1 = s_ring(p_hd + ax_h * 0.032, ax_h, 0.046, 0.044)
        mb.loft(
            [r_h0, r_h1],
            lambda i, k: SKIN_SHADE if k == 2 else SKIN,
            cap_bottom=False, cap_top=True, top_color=SKIN,
        )

    # =========================================================================
    # 9. DARK HIKING BACKPACK + SIDE POCKETS + STRAPS + GOLDEN BEDROLL (8 + 4 + 12 + 18 = 42 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # Tapered outdoor pack body tucked cleanly behind jacket & directly supporting the golden bedroll (8 tris)
    bp_bot = [
        V(-0.146, 0.654, -0.114),
        V( 0.146, 0.654, -0.114),
        V( 0.130, 0.674, -0.274),
        V(-0.130, 0.674, -0.274),
    ]
    bp_top = [
        V(-0.160, 0.994, -0.112),
        V( 0.160, 0.994, -0.112),
        V( 0.156, 0.994, -0.304),
        V(-0.156, 0.994, -0.304),
    ]
    # Skip k=0 (hidden flush against jacket back) & top (covered by rolled bedroll) -> 3 walls + bot = 8 tris!
    mb.loft(
        [bp_bot, bp_top],
        lambda i, k: PACK_SHADE if k in (1, 3) else PACK,
        cap_bottom=True, cap_top=False, bot_color=PACK_SHADE, skip_k=(0,),
    )

    # Side utility pockets on left & right of backpack (2 quads = 4 tris)
    for side in (-1, 1):
        xs = side * 0.164
        mb.face([
            V(xs, 0.728, -0.175),
            V(xs, 0.728, -0.285),
            V(xs, 0.892, -0.292),
            V(xs, 0.892, -0.182),
        ], PACK_POCKET, out=(side, 0, 0))

    # Backpack shoulder straps + horizontal chest sternum strap + waist belt buckle (12 tris)
    mb.set_part("backpack_straps", bone="Torso")
    for side in (-1, 1):
        xa = min(side * 0.106, side * 0.152)
        xb = max(side * 0.106, side * 0.152)
        # Top shoulder strap crossing over teal shoulder
        mb.face([
            V(xa, 1.098, -0.116),
            V(xb, 1.098, -0.116),
            V(xb, 1.098,  0.118),
            V(xa, 1.098,  0.118),
        ], PACK_STRAP, out=(0, 1, 0))
        # Front chest harness strap descending smoothly over jacket front
        mb.face([
            V(xa, 0.784, 0.140),
            V(xb, 0.784, 0.140),
            V(xb, 1.098, 0.118),
            V(xa, 1.098, 0.118),
        ], PACK_STRAP, out=(0, 0, 1))

    # Horizontal sternum strap linking shoulder straps across upper chest (2 tris)
    mb.face([
        V(-0.112, 0.946, 0.138),
        V( 0.112, 0.946, 0.138),
        V( 0.112, 0.976, 0.136),
        V(-0.112, 0.976, 0.136),
    ], PACK_STRAP, out=(0, 0, 1))

    # Hip/waist belt strap + buckle across lower front jacket (2 tris)
    mb.face([
        V(-0.148, 0.742, 0.146),
        V( 0.148, 0.742, 0.146),
        V( 0.148, 0.780, 0.144),
        V(-0.148, 0.780, 0.144),
    ], PACK_BUCKLE, out=(0, 0, 1))

    # Iconic GOLDEN-OCHRE ROLLED BEDROLL strapped horizontally atop the backpack (22 tris, RECOLOR accent!)
    mb.set_part("bedroll", bone="Torso")
    br_y = 1.058
    br_z = -0.282  # clean daylight behind braided ponytail!
    br_r = 0.090
    br_hw = 0.220  # protrudes proudly past both sides of the backpack just like the reference!

    def bedroll_ring(x_pos, rad, n=6, phase=0.0):
        pts = []
        for k in range(n):
            a = phase + 2.0 * math.pi * k / n
            pts.append(V(x_pos, br_y + rad * math.sin(a), br_z + rad * math.cos(a)))
        return pts

    br_l = bedroll_ring(-br_hw, br_r, n=6)
    br_r_ring = bedroll_ring(br_hw, br_r, n=6)
    # 6-sided horizontal cylinder skipping hidden bottom facet k=4 buried inside backpack (10 walls + 8 ends = 18 tris)
    mb.loft(
        [br_l, br_r_ring],
        lambda i, k: BEDROLL_SHADE if k in (2, 3) else BEDROLL,
        cap_bottom=True, cap_top=True,
        bot_color=BEDROLL_END, top_color=BEDROLL_END,
        skip_k=(4,),
    )
    # Crisp rolled-mat recessed inner spiral-core octagon/diamond on each flat hex end (+4 tris = 22 tris!)
    for side in (-1, 1):
        xe = side * (br_hw + 0.003)
        cr = 0.044
        cpts = [
            V(xe, br_y + cr * math.sin(math.pi / 4.0 + k * math.pi / 2.0),
              br_z + cr * math.cos(math.pi / 4.0 + k * math.pi / 2.0))
            for k in range(4)
        ]
        mb.face(cpts, BEDROLL_CORE, out=(side, 0, 0))

    # =========================================================================
    # 10. KHAKI HIKING SHORTS (pelvis 4 + 2 flared legs x 8 = 20 tris)
    # =========================================================================
    mb.set_part("shorts", bone="Root")
    mb.box(-0.184, 0.184, 0.546, 0.658, -0.106, 0.106, SHORTS, skip=("top", "bottom", "left", "right"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.006, side * 0.188
        x_in_b, x_out_b = side * 0.022, side * 0.214
        rz_t, rz_b = 0.100, 0.108
        r_top = [
            V(min(x_in_t, x_out_t), 0.650,  rz_t),
            V(max(x_in_t, x_out_t), 0.650,  rz_t),
            V(max(x_in_t, x_out_t), 0.650, -rz_t),
            V(min(x_in_t, x_out_t), 0.650, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.448,  rz_b),
            V(max(x_in_b, x_out_b), 0.448,  rz_b),
            V(max(x_in_b, x_out_b), 0.448, -rz_b),
            V(min(x_in_b, x_out_b), 0.448, -rz_b),
        ]
        mb.loft([r_bot, r_top], lambda i, k: SHORTS_SHADE if k == 2 else SHORTS,
                cap_bottom=False, cap_top=False)

    # =========================================================================
    # 11. BARE PEACH LOWER LEGS + CHUNKY CREAM HIKING SOCKS (2 x 16 = 32 tris)
    # =========================================================================
    mb.set_part("legs_socks")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.128
        # Continuous 2-segment 4-sided leg: hiking sock cuff (0.145..0.245) + bare peach calf (0.245..0.468)
        r_ankle = oval_ring(cx, 0.145, 0.000, 0.062, 0.064, n=4, phase=math.pi / 4.0)
        r_sock  = oval_ring(cx, 0.246, 0.000, 0.066, 0.068, n=4, phase=math.pi / 4.0)
        r_knee  = oval_ring(cx, 0.468, 0.000, 0.072, 0.074, n=4, phase=math.pi / 4.0)
        mb.loft(
            [r_ankle, r_sock, r_knee],
            lambda i, k: (
                (SOCK_SHADE if k in (1, 2) else SOCK)
                if i == 0
                else (SKIN_SHADE if k in (1, 2) else SKIN)
            ),
            cap_bottom=False, cap_top=False,
        )

    # =========================================================================
    # 12. CHUNKY TAN-BROWN HIKING BOOTS WITH DARK TONGUE & LUG SOLES (2 x 18 = 36 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.128
        w = 0.072
        w_toe = 0.062
        z_heel = -0.090
        z_mid  =  0.056
        z_toe  =  0.170
        y_sole0 = 0.000
        y_sole1 = 0.038
        y_toe   = 0.094
        y_col   = 0.162

        # Thick dark lug outsole (4 sides = 8 tris; rests flat on y = 0)
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
        mb.loft([sole_bot, sole_top], SOLE, cap_bottom=False, cap_top=False)

        # Tan-brown leather boot upper with chunky front toe-box & dark tongue instep (10 tris)
        p_bl_h = V(cx - w,     y_sole1, z_heel)
        p_br_h = V(cx + w,     y_sole1, z_heel)
        p_bl_t = V(cx - w_toe, y_sole1, z_toe)
        p_br_t = V(cx + w_toe, y_sole1, z_toe)

        p_tl_h = V(cx - w * 0.86,     y_col, z_heel + 0.012)
        p_tr_h = V(cx + w * 0.86,     y_col, z_heel + 0.012)
        p_tl_m = V(cx - w * 0.86,     y_col, z_mid)
        p_tr_m = V(cx + w * 0.86,     y_col, z_mid)
        p_tl_t = V(cx - w_toe * 0.88, y_toe, z_toe - 0.012)
        p_tr_t = V(cx + w_toe * 0.88, y_toe, z_toe - 0.012)

        mb.face([p_br_h, p_bl_h, p_tl_h, p_tr_h], BOOT_SHADE,  out=(0, 0, -1))
        mb.face([p_bl_t, p_br_t, p_tr_t, p_tl_t], BOOT,        out=(0, 0, 1))
        mb.face([p_tl_t, p_tr_t, p_tr_m, p_tl_m], BOOT_TONGUE, out=(0, 1, 0.5))
        # Watertight stepped side walls sealing heel-to-ankle-to-toe cleanly (3 tris/side)
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], BOOT,        out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h],         BOOT,        out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], BOOT,        out=( 1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m],         BOOT,        out=( 1, 0, 0))

    # =========================================================================
    # 13. PAIR OF DARK TREKKING / HIKING POLES WITH GRIPS & MUD BASKETS (2 x 17 = 34 tris)
    # =========================================================================
    mb.set_part("hiking_poles")
    for side in (-1, 1):
        pole_bone = "Pole_L" if side > 0 else "Pole_R"
        mb.set_bone(pole_bone)
        p_hand = HAND_L if side > 0 else HAND_R
        # Pole runs cleanly through the peach fist down to just above ground level (y = 0.020)
        p_tip = V(side * 0.252, 0.020, 0.168)
        p_axis = (p_hand - p_tip).normalized()  # unit vector pointing UP along pole
        _, pu, pv = ortho_basis(p_axis, hint=V(1.0, 0.0, 0.0))

        def pole_ring(pt, rad, n=3, phase=0.0):
            return [
                pt + pu * (rad * math.cos(phase + 2.0 * math.pi * k / n))
                   + pv * (rad * math.sin(phase + 2.0 * math.pi * k / n))
                for k in range(n)
            ]

        # 13a. Molded dark ergonomic pole grip protruding above & below the fist (6 walls + 1 top cap = 7 tris)
        p_g_top = p_hand + p_axis * 0.102
        p_g_bot = p_hand - p_axis * 0.074
        mb.loft(
            [pole_ring(p_g_bot, 0.027, n=3), pole_ring(p_g_top, 0.029, n=3)],
            POLE_GRIP, cap_bottom=False, cap_top=True, top_color=POLE_GRIP,
        )

        # 13b. Sleek tapered dark trekking pole shaft from hand down to ground tip (6 tris)
        p_s_top = p_hand - p_axis * 0.056
        mb.loft(
            [pole_ring(p_tip, 0.013, n=3), pole_ring(p_s_top, 0.017, n=3)],
            POLE_SHAFT, cap_bottom=False, cap_top=False,
        )

        # 13c. Crisp solid dark snow/mud basket flange just above tip (back-to-back wafer = 4 tris)
        p_bsk = p_tip + p_axis * 0.064
        r_bsk_top = pole_ring(p_bsk + p_axis * 0.002, 0.042, n=4, phase=math.pi / 4.0)
        r_bsk_bot = pole_ring(p_bsk - p_axis * 0.002, 0.042, n=4, phase=math.pi / 4.0)
        mb.face(r_bsk_top, POLE_BASKET, out=p_axis)
        mb.face(r_bsk_bot, POLE_BASKET, out=-p_axis)

    return mb


def setup_materials(hat_img):
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

    # Slot 1: Texture-painted Mountain Trucker Cap material
    mat_hat = bpy.data.materials.new("HikerHat")
    nt_h = mat_hat.node_tree
    bsdf_h = next(n for n in nt_h.nodes if n.type == "BSDF_PRINCIPLED")
    tex_h = nt_h.nodes.new("ShaderNodeTexImage")
    tex_h.image = hat_img
    vc_h = nt_h.nodes.new("ShaderNodeVertexColor")
    vc_h.layer_name = "Col"
    mix_h = nt_h.nodes.new("ShaderNodeMix")
    mix_h.data_type = "RGBA"
    mix_h.blend_type = "MULTIPLY"
    mix_h.inputs["Factor"].default_value = 1.0
    nt_h.links.new(tex_h.outputs["Color"], mix_h.inputs["A"])
    nt_h.links.new(vc_h.outputs["Color"], mix_h.inputs["B"])
    nt_h.links.new(mix_h.outputs["Result"], bsdf_h.inputs["Base Color"])
    bsdf_h.inputs["Roughness"].default_value = 0.88
    if "Specular IOR Level" in bsdf_h.inputs:
        bsdf_h.inputs["Specular IOR Level"].default_value = 0.18

    return [mat_vcol, mat_hat]


def _reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: energetic hiking stride with rhythmic trekking-pole planting & braid bounce."""
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

        # Purposeful trail-hiking stride with gentle forward lean balancing backpack & bedroll
        pb_root = rig.pose.bones["Root"]
        bob = -0.016 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.036, -0.068 * s1, 0.034 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp torso counter-rotation driving opposite-arm pole plant
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.014 * c2, 0.105 * s1, -0.022 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Alert hiker head keeping mountain cap level & eyes on the trail
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.030 - 0.020 * c2, -0.044 * s1, -0.014 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Lively braided ponytail bounce & outward sway (stays cleanly ahead of bedroll!)
        pb_braid = rig.pose.bones["Braid"]
        br_pitch = 0.028 + 0.075 * (1.0 - math.cos(2.0 * phi - 0.65)) * 0.5
        br_roll  = -0.040 - 0.075 * math.sin(phi - 0.50)
        pb_braid.rotation_euler = (br_pitch, 0.045 * math.sin(phi - 0.50), br_roll)
        pb_braid.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating hiking-boot stride with clean ground clearance
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.44 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.042, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.44 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.042, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Rhythmic trekking-pole arm swing in opposite phase to legs!
        # Slight upward bias (+0.075 rad) keeps hands & planted pole tips cleanly kissing the ground!
        arm_l_pitch = 0.28 * s1 + 0.075 + 0.035 * (1.0 - c1) * 0.5
        arm_r_pitch = -0.28 * s1 + 0.075 + 0.035 * (1.0 + c1) * 0.5

        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (arm_l_pitch, 0.0, 0.025 + 0.015 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (arm_r_pitch, 0.0, -0.025 + 0.015 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Trekking pole wrist-pivot counter-pitch: keeps poles planting smoothly & cleanly above ground!
        pb_pole_l = rig.pose.bones["Pole_L"]
        pb_pole_l.rotation_euler = (-0.54 * arm_l_pitch + 0.06 * c1, 0.0, -0.020)
        pb_pole_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_pole_r = rig.pose.bones["Pole_R"]
        pb_pole_r.rotation_euler = (-0.54 * arm_r_pitch - 0.06 * c1, 0.0, 0.020)
        pb_pole_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: hiker pausing on the trail, leaning gently on planted poles & admiring the view."""
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

        # Calm breathing & gentle weight shift while resting on trail poles
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.014, 0.024 * s1, 0.018 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.032 * s1, -0.014 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Taking in the scenic mountain/water views left & right
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.026 + 0.034 * s2, 0.26 * s1, 0.032 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Soft breeze drift on braided ponytail lagging gently behind head turn
        pb_braid = rig.pose.bones["Braid"]
        pb_braid.rotation_euler = (0.024 + 0.022 * s2, -0.068 * math.sin(phi - 0.55), -0.030 - 0.028 * c1)
        pb_braid.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Boots planted firmly on the trail
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle arm/wrist breath shift while keeping both hiking poles steady and planted!
        al_p = -0.032 * s1 + 0.018 * s2
        ar_p =  0.032 * s1 + 0.018 * s2
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (al_p, 0.0, 0.018 + 0.010 * s2)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (ar_p, 0.0, -0.018 - 0.010 * s2)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-rotate poles slightly so pole tips stay planted gently on the ground
        pb_pole_l = rig.pose.bones["Pole_L"]
        pb_pole_l.rotation_euler = (-0.75 * al_p, 0.0, -0.014)
        pb_pole_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_pole_r = rig.pose.bones["Pole_R"]
        pb_pole_r.rotation_euler = (-0.75 * ar_p, 0.0, 0.014)
        pb_pole_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build a 10-bone Tideways passenger rig (7 standard bones + Braid + Pole_L + Pole_R) with Walk & Idle."""
    arm_data = bpy.data.armatures.new("PersonHikerWomanRig")
    rig = bpy.data.objects.new("PersonHikerWomanRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",   None,    ( 0.000, 0.585,  0.000),              ( 0.000, 0.705,  0.000)),
        ("Torso",  "Root",  ( 0.000, 0.642,  0.000),              ( 0.000, 1.092,  0.000)),
        ("Head",   "Torso", ( 0.000, 1.135,  0.000),              ( 0.000, 1.450,  0.000)),
        ("Braid",  "Head",  (-0.080, 1.356, -0.168),              (-0.080, 1.476, -0.168)),
        ("Arm_L",  "Torso", ( 0.168, SHOULDER_Y, SHOULDER_Z),     ( 0.168, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Arm_R",  "Torso", (-0.168, SHOULDER_Y, SHOULDER_Z),     (-0.168, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Pole_L", "Arm_L", (HAND_L.x, HAND_L.y, HAND_L.z),       (HAND_L.x, HAND_L.y + 0.140, HAND_L.z)),
        ("Pole_R", "Arm_R", (HAND_R.x, HAND_R.y, HAND_R.z),       (HAND_R.x, HAND_R.y + 0.140, HAND_R.z)),
        ("Leg_L",  "Root",  ( 0.105, 0.568,  0.000),              ( 0.105, 0.728,  0.000)),
        ("Leg_R",  "Root",  (-0.105, 0.568,  0.000),              (-0.105, 0.728,  0.000)),
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
    fill_data.energy = 0.90
    fill_data.color = (0.89, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("FloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    clones = []
    specs = [
        (-1.82, math.radians(56)),   # Front-3/4 matching reference angle (facing right, showing braid + poles + mountain hat!)
        (-0.60, math.radians(0)),    # Front (showing mountain logo patch, teal hood, straps & trekking poles)
        ( 0.62, math.radians(90)),   # Right side (showing bedroll spiral, braided ponytail, cap visor & hiking poles)
        ( 1.84, math.radians(180)),  # Back (showing golden bedroll, dark backpack & braided ponytail)
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
    cam_data.ortho_scale = 5.1
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.5, 1.16)
    direction = Vector((0.0, 0.0, 0.85)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1360
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
    fill_data.energy = 0.90
    fill_data.color = (0.89, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("StripFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.34
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 8.4
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.5, 1.16)
    direction = Vector((0.0, 0.0, 0.85)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 1560
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
    fill_data.energy = 0.90
    fill_data.color = (0.89, 0.93, 1.0)
    fill_obj = bpy.data.objects.new("VidFill", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.rotation_euler = (math.radians(60), math.radians(-10), math.radians(145))

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0, 0, -0.001))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("VidFloorMat")
    fbsdf = next(n for n in fmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    fbsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.96, 1.0)
    fbsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(fmat)

    cam_data = bpy.data.cameras.new("VidCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 3.35
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.5, 1.15)
    direction = Vector((0.0, 0.0, 0.85)) - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj

    scene.render.resolution_x = 820
    scene.render.resolution_y = 540
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
            left_obj.location = (-0.74, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.74, 0.0, 0.0)
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

    coll = bpy.data.collections.new("PersonHikerWoman")
    bpy.context.scene.collection.children.link(coll)

    hat_img = generate_hat_texture(HAT_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonHikerWoman")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(hat_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonHikerWoman", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    # Verify ground clearance across both animations
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for act, clen in ((walk_action, 24), (idle_action, 48)):
        rig.animation_data.action = act
        min_z = 999.0
        for f in range(1, clen + 1):
            scene.frame_set(f)
            depsgraph.update()
            em = ob.evaluated_get(depsgraph).to_mesh()
            fz = min(v.co.z for v in em.vertices)
            if fz < min_z:
                min_z = fz
            ob.evaluated_get(depsgraph).to_mesh_clear()
        print(f"Animation {act.name:6s} min ground Z: {min_z:+.4f} m")
    rig.animation_data.action = walk_action
    scene.frame_set(1)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    print("=== PersonHikerWoman Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    assert total_tris < 350, f"Triangle budget exceeded: {total_tris} >= 350"

    os.makedirs(os.path.dirname(BLEND_PATH), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    # Export GLB with both Walk and Idle animations + embedded hat texture + Part UV via ACTIONS mode
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
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH,
                          zrot_left_deg=56, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH,
                          zrot_left_deg=48, zrot_right_deg=90)

    print(f"Hat texture:     {HAT_TEX_PATH}")
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
