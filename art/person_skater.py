# Builds an ultra-low-poly (< 350 tris) stylized skater with mustard knit beanie, wavy dark-brown
# hair, open image-textured navy/caramel plaid flannel jacket over an off-white tee, slim charcoal
# backpack, loose charcoal skate pants, canvas low-top skate sneakers, and a skateboard tucked
# under the right arm in Blender.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_skater.py)
# Saves art/person_skater.blend, exports assets/models/person_skater.glb (rigged + Walk & Idle cycles + embedded texture),
# renders art/person_skater_preview.png, art/person_skater_walk_preview.png, art/person_skater_idle_preview.png,
# and outputs rendered videos art/person_skater_walk.mp4 and art/person_skater_idle.mp4.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_skater.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_skater.glb")
FLANNEL_TEX_PATH = os.path.join(ROOT, "art", "person_skater_flannel_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_skater_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_skater_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_skater_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_skater_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_skater_idle.mp4")

MAT_VCOL = 0
MAT_FLANNEL = 1


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference artwork (every colour made with col_srgb, unique per part)
TEX_WHITE        = col_srgb(1.00, 1.00, 1.00)

SKIN             = col_srgb(0.98, 0.77, 0.56)
SKIN_SHADE       = col_srgb(0.88, 0.66, 0.45)
EYE              = col_srgb(0.11, 0.10, 0.10)

HAIR_DARK        = col_srgb(0.34, 0.25, 0.20)
HAIR_MID         = col_srgb(0.42, 0.32, 0.25)
HAIR_SHADE       = col_srgb(0.25, 0.18, 0.14)

BEANIE           = col_srgb(0.85, 0.69, 0.28)
BEANIE_CUFF      = col_srgb(0.79, 0.63, 0.24)
BEANIE_TOP       = col_srgb(0.90, 0.75, 0.34)

TEE              = col_srgb(0.95, 0.93, 0.89)
TEE_SHADE        = col_srgb(0.85, 0.82, 0.78)

PACK             = col_srgb(0.30, 0.31, 0.33)
PACK_SHADE       = col_srgb(0.22, 0.23, 0.25)
PACK_STRAP       = col_srgb(0.26, 0.27, 0.29)

PANTS            = col_srgb(0.21, 0.21, 0.22)
PANTS_SHADE      = col_srgb(0.15, 0.15, 0.16)
PANTS_INNER      = col_srgb(0.11, 0.11, 0.12)

SHOE             = col_srgb(0.56, 0.57, 0.58)
SHOE_SHADE       = col_srgb(0.45, 0.46, 0.47)
SHOE_SOLE        = col_srgb(0.93, 0.90, 0.85)
SHOE_LACE        = col_srgb(0.97, 0.96, 0.94)

DECK_FACE        = col_srgb(0.28, 0.38, 0.47)
DECK_EDGE        = col_srgb(0.91, 0.73, 0.30)
DECK_GRIP        = col_srgb(0.17, 0.18, 0.20)
TRUCK            = col_srgb(0.24, 0.26, 0.29)
TRUCK_SHADE      = col_srgb(0.16, 0.18, 0.21)
WHEEL_YELLOW     = col_srgb(0.88, 0.71, 0.25)
WHEEL_YELLOW_SH  = col_srgb(0.72, 0.56, 0.19)
WHEEL_OLIVE      = col_srgb(0.45, 0.46, 0.36)
WHEEL_OLIVE_SH   = col_srgb(0.34, 0.35, 0.27)
WHEEL_TEAL       = col_srgb(0.37, 0.52, 0.45)
WHEEL_TEAL_SH    = col_srgb(0.27, 0.40, 0.34)

# Parts the game recolours per passenger (see art/person_recolor.py).
# Textured plaid flannel jacket, white undershirt, eyes, shoes, backpack, and skateboard stay fixed.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [HAIR_DARK, HAIR_MID, HAIR_SHADE],
    "bottom": [PANTS, PANTS_SHADE, PANTS_INNER],
    "accent": [BEANIE, BEANIE_CUFF, BEANIE_TOP],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared structural anchors for rig & geometry alignment
SHOULDER_Y = 1.032
SHOULDER_Z = 0.004


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def _plaid_pattern(uu, vv, freq_u, freq_v):
    """Generate bold navy-slate / warm caramel-ochre plaid flannel pattern matched to reference."""
    pu = (uu * freq_u) % 1.0
    pv = (vv * freq_v) % 1.0

    # Base warm caramel-tan / golden ochre flannel squares
    col = np.zeros(uu.shape + (3,), dtype=np.float32)
    col[..., 0] = 0.79
    col[..., 1] = 0.56
    col[..., 2] = 0.31

    # Broad slate-blue / muted navy bands occupying [0.24..0.76] in each repeat
    u_band = np.clip((pu - 0.22) * 36.0, 0.0, 1.0) * np.clip((0.78 - pu) * 36.0, 0.0, 1.0)
    v_band = np.clip((pv - 0.22) * 36.0, 0.0, 1.0) * np.clip((0.78 - pv) * 36.0, 0.0, 1.0)

    # Deeper navy-slate core inside bands [0.36..0.64]
    u_core = np.clip((pu - 0.35) * 44.0, 0.0, 1.0) * np.clip((0.65 - pu) * 44.0, 0.0, 1.0)
    v_core = np.clip((pv - 0.35) * 44.0, 0.0, 1.0) * np.clip((0.65 - pv) * 44.0, 0.0, 1.0)

    # Subtle warm-amber inner check stripe crossing the tan squares
    u_pin = np.clip((0.032 - np.minimum(pu, 1.0 - pu)) * 55.0, 0.0, 1.0)
    v_pin = np.clip((0.032 - np.minimum(pv, 1.0 - pv)) * 55.0, 0.0, 1.0)

    # Layer muted slate-blue warp & weft (caramel + slate weave where only one band crosses)
    single_band = np.clip(u_band + v_band - 2.0 * u_band * v_band, 0.0, 1.0)
    cross_band = u_band * v_band
    col = _blend_mask(col, single_band * 0.62, (0.37, 0.39, 0.37))
    col = _blend_mask(col, cross_band * 0.90, (0.21, 0.29, 0.36))

    # Deeper navy-charcoal stripe cores & crisp dark navy cross blocks
    core_single = np.clip(np.maximum(u_core, v_core), 0.0, 1.0)
    core_cross = u_core * v_core
    col = _blend_mask(col, core_single * 0.36, (0.24, 0.32, 0.39))
    col = _blend_mask(col, core_cross * 0.68, (0.16, 0.22, 0.28))

    # Subtle caramel-brown accent pinstripe on the golden squares
    pin = np.maximum(u_pin, v_pin) * (1.0 - core_single)
    col = _blend_mask(col, pin * 0.22, (0.55, 0.38, 0.21))

    # Soft flannel brushed weave micro-texture
    twill = 1.0 + 0.018 * np.sin((uu * 200.0 + vv * 200.0))
    col *= twill[..., None]
    return np.clip(col, 0.0, 1.0)


def generate_flannel_texture(out_path):
    """Paint a 512x512 sRGB navy/caramel flannel jacket texture:
       - Top region (v in [0.34, 1.00]): Open-front flannel torso panels & back with bold checks.
       - Bottom strip (v in [0.00, 0.34]): Matching chunky-check flannel sleeves & folded collar with navy cuff.
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # 1. Torso flannel (v in [0.34, 1.00])
    # Bold square checks (~4.5 checks vertically on torso, matching reference!)
    torso_img = _plaid_pattern(uu + 0.05, vv, freq_u=8.0, freq_v=5.4)
    torso_v = np.clip((vv - 0.34) / 0.66, 0.0, 1.0)
    torso_img *= (0.91 + 0.11 * torso_v)[..., None]

    # Subtle stitched edge along open front lapels (at u = 0.00 and u = 1.00 boundary)
    lapel_edge = np.clip((0.016 - np.minimum(uu, 1.0 - uu)) / 0.006, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, lapel_edge * 0.28, (0.14, 0.19, 0.24))

    # Subtle lower hem seam near v = 0.356
    hem_seam = np.clip((0.006 - np.abs(vv - 0.356)) / 0.003, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, hem_seam * 0.40, (0.14, 0.18, 0.23))

    # 2. Sleeve & collar strip (v in [0.00, 0.34])
    # Bold chunky checks (~4 checks around arm, ~3.5 checks down arm length matching reference!)
    sleeve_img = _plaid_pattern(uu + 0.08, vv, freq_u=4.0, freq_v=11.0)
    slv_t = np.clip(vv / 0.34, 0.0, 1.0)
    sleeve_img *= (0.91 + 0.11 * slv_t)[..., None]

    # Crisp dark navy-slate wrist cuff hem at bottom of sleeve (v in [0.00, 0.048])
    cuff_m = np.clip((0.048 - vv) / 0.006, 0.0, 1.0)
    sleeve_img = _blend_mask(sleeve_img, cuff_m * 0.78, (0.20, 0.27, 0.34))
    cuff_seam = np.clip((0.006 - np.abs(vv - 0.050)) / 0.003, 0.0, 1.0)
    sleeve_img = _blend_mask(sleeve_img, cuff_seam * 0.55, (0.12, 0.16, 0.21))

    in_torso = (vv >= 0.340).astype(np.float32)
    img = sleeve_img * (1.0 - in_torso[..., None]) + torso_img * in_torso[..., None]
    img = np.clip(img, 0.0, 1.0)

    bimg = bpy.data.images.new("SkaterFlannelTex", width=w, height=h, alpha=True, float_buffer=False)
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


def open_jacket_ring(cx, cy, cz, rx, rz, tee_half_w=0.056, sh_drop=0.0):
    """8-sided torso ring: k=7 (v7->v0) is recessed center off-white tee; k=0..6 are open flannel panels."""
    zf_tee = rz * 0.84
    zf_pan = rz * 0.96
    zb = rz * 0.88
    yo = cy - sh_drop
    return [
        V(cx + tee_half_w,  cy, cz + zf_tee),  # 0: front-center-left (tee/flannel seam)
        V(cx + rx * 0.78,   cy, cz + zf_pan),  # 1: front-left outer flannel edge
        V(cx + rx,          yo, cz),           # 2: left side
        V(cx + rx * 0.76,   cy, cz - zb),      # 3: back-left
        V(cx - rx * 0.76,   cy, cz - zb),      # 4: back-right
        V(cx - rx,          yo, cz),           # 5: right side
        V(cx - rx * 0.78,   cy, cz + zf_pan),  # 6: front-right outer flannel edge
        V(cx - tee_half_w,  cy, cz + zf_tee),  # 7: front-center-right (tee/flannel seam)
    ]


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
    # 1. HEAD (clean-shaven chunky low-poly skater head, 6-sided = 26 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.160,  0.022, 0.160, 0.156),  # 0: rounded jaw/chin
        (1.258,  0.024, 0.214, 0.204),  # 1: full cheeks
        (1.472,  0.008, 0.190, 0.180),  # 2: forehead tapered slightly so wavy bangs wrap cleanly outside!
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        # k=5 flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks; k=1,2,3 dark brown hair on back/sides
        return SKIN if k in (4, 5, 0) else HAIR_DARK

    mb.loft(head_rings, head_color, cap_bottom=False, cap_top=False)
    # Front chin underside cap (rear half sits directly above neck/nape hair = 2 tris)
    rb = head_rings[0]
    mb.face([rb[4], rb[5], rb[0], rb[1]], SKIN_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 2. WAVY DARK-BROWN HAIR (sealed wavy bangs + watertight temple locks + soft wavy nape = 36 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")

    # 2a. Chunky watertight forehead bangs / wavy curl tucked solidly under the beanie cuff (14 tris)
    # Outer ends taper cleanly into a tucked rear vertex inside the temple hair so all sides are 100% sealed!
    b_r_f0 = V(-0.148, 1.430, 0.172); b_r_f1 = V(-0.148, 1.486, 0.166); b_r_bk = V(-0.132, 1.472, 0.100)
    b_m_f0 = V( 0.010, 1.428, 0.218); b_m_f1 = V( 0.012, 1.490, 0.204)
    b_m_b1 = V( 0.010, 1.524, 0.102); b_m_b0 = V( 0.010, 1.434, 0.110)
    b_l_f0 = V( 0.148, 1.428, 0.170); b_l_f1 = V( 0.148, 1.484, 0.164); b_l_bk = V( 0.132, 1.470, 0.100)
    # Front curl (4 tris), underside brow tuck (4 tris), top tuck into beanie (4 tris), sealed side ends (2 tris) = 14 tris!
    mb.face([b_r_f0, b_m_f0, b_m_f1, b_r_f1], HAIR_MID,   out=(-0.2, 0.2, 1.0))
    mb.face([b_m_f0, b_l_f0, b_l_f1, b_m_f1], HAIR_MID,   out=( 0.2, 0.2, 1.0))
    mb.face([b_r_bk, b_m_b0, b_m_f0, b_r_f0], HAIR_SHADE, out=(0, -1, 0.2))
    mb.face([b_m_b0, b_l_bk, b_l_f0, b_m_f0], HAIR_SHADE, out=(0, -1, 0.2))
    mb.face([b_r_f1, b_m_f1, b_m_b1, b_r_bk], HAIR_DARK,  out=(-0.15, 1, 0.2))
    mb.face([b_m_f1, b_l_f1, b_l_bk, b_m_b1], HAIR_DARK,  out=( 0.15, 1, 0.2))
    mb.face([b_r_bk, b_r_f0, b_r_f1],         HAIR_DARK,  out=(-1, 0, 0.2))
    mb.face([b_l_f0, b_l_bk, b_l_f1],         HAIR_DARK,  out=( 1, 0, 0.2))

    # 2b. Solid stepped side-temple hair locks hugging cheek & tucking up inside beanie cuff (2 x 5 = 10 tris)
    for side in (-1, 1):
        x_in  = side * 0.148
        x_out = side * 0.218
        y_bot = 1.334
        y_top = 1.492
        z_bk  = -0.024
        z_fr  =  0.132
        p_fb  = V(x_out, y_bot, z_fr);         p_ft  = V(x_out, y_top, z_fr)
        p_bb  = V(x_out, y_bot + 0.014, z_bk); p_bt  = V(x_out, y_top - 0.018, z_bk)
        p_ifb = V(x_in,  y_bot, z_fr);         p_ift = V(x_in,  y_top, z_fr)
        p_ibb = V(x_in,  y_bot + 0.014, z_bk)
        # Outer side (2 tris), front step (2 tris), bottom ledge above ear (1 tri) = 5 tris/side -> 10 tris!
        mb.face([p_bb, p_fb, p_ft, p_bt],     HAIR_DARK,  out=(side, 0, 0.15))
        mb.face([p_ifb, p_fb, p_ft, p_ift],   HAIR_MID,   out=(side * 0.3, 0, 1.0))
        mb.face([p_ibb, p_ifb, p_fb],         HAIR_SHADE, out=(0, -1, 0))

    # 2c. Soft tousled wavy nape curls curving gently out behind ears & neck below beanie (12 tris)
    # Top edge tucks cleanly up inside the tilted beanie cuff (y=1.385) so zero gap even zoomed in!
    h_top = [
        V(-0.214, 1.385, -0.004),  # 0: right behind ear (overlaps side temple cleanly!)
        V(-0.158, 1.378, -0.172),  # 1: back-right
        V( 0.000, 1.378, -0.204),  # 2: back-center
        V( 0.158, 1.378, -0.172),  # 3: back-left
        V( 0.214, 1.385, -0.004),  # 4: left behind ear
    ]
    h_bot = [
        V(-0.220, 1.210, -0.022),  # 0: right lower wave
        V(-0.166, 1.178, -0.216),  # 1: back-right soft curl kick
        V( 0.000, 1.186, -0.246),  # 2: back-center wavy curl
        V( 0.166, 1.178, -0.216),  # 3: back-left soft curl kick
        V( 0.220, 1.210, -0.022),  # 4: left lower wave
    ]
    # 4 outer wave quads = 8 tris
    for k in range(4):
        p0, p1, p2, p3 = h_bot[k], h_bot[k + 1], h_top[k + 1], h_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        col = HAIR_MID if k in (1, 2) else HAIR_DARK
        mb.face([p0, p1, p2, p3], col, out=V(mid.x, 0.12, mid.z - 0.10))
    # Underside closure tucking cleanly to nape (2 quads = 4 tris -> 12 tris total!)
    h_in_r = V(-0.138, 1.202, -0.048)
    h_in_c = V( 0.000, 1.192, -0.108)
    h_in_l = V( 0.138, 1.202, -0.048)
    mb.face([h_bot[0], h_bot[1], h_bot[2], h_in_r], HAIR_SHADE, out=(0, -1, 0))
    mb.face([h_bot[2], h_bot[3], h_bot[4], h_in_l], HAIR_SHADE, out=(0, -1, 0))

    # =========================================================================
    # 3. EARS (2 chunky peach wedges peeking beneath hair = 8 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.194
        x_out = side * 0.238
        y0, y1 = 1.250, 1.332
        z0, z1 = 0.004, 0.072
        p_tip = V(x_out, 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_tip], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_tip], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_tip], SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_tip], SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. EYES (2 vertical dark pill hexagons flush on front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.200
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.334
        rx = 0.019
        ry = 0.044
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
    # 5. MUSTARD-GOLD KNIT BEANIE (6-sided tilted cuffed dome = 28 tris)
    # =========================================================================
    mb.set_part("beanie", bone="Head")
    # Slouchy backward tilt (~21 deg) seated snugly onto forehead bangs!
    btilt = math.radians(21.0)
    cuff_bot   = tilted_ring(0.0, 1.424, -0.018, 0.244, 0.244, btilt, n=6, phase=math.pi / 6.0)
    cuff_top   = tilted_ring(0.0, 1.512, -0.044, 0.252, 0.252, btilt, n=6, phase=math.pi / 6.0)
    dome_crown = tilted_ring(0.0, 1.658, -0.090, 0.146, 0.148, btilt, n=6, phase=math.pi / 6.0)
    mb.loft([cuff_bot, cuff_top], BEANIE_CUFF, cap_bottom=False, cap_top=False)
    mb.loft([cuff_top, dome_crown], BEANIE, cap_bottom=False, cap_top=True, top_color=BEANIE_TOP)

    # =========================================================================
    # 6. NECK (closed 3-sided peach prism = 6 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.070, 1.068, -0.036), V(0.000, 1.068, 0.074), V(0.070, 1.068, -0.036)]
    n_t = [V(-0.066, 1.174, -0.034), V(0.000, 1.174, 0.070), V(0.066, 1.174, -0.034)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))
    mb.face([n_b[2], n_b[0], n_t[0], n_t[2]], SKIN_SHADE, out=( 0.0, 0, -1.0))

    # =========================================================================
    # 7. TORSO: OPEN IMAGE-TEXTURED FLANNEL JACKET + WHITE TEE (22 tris)
    # =========================================================================
    mb.set_part("flannel_torso", bone="Torso")
    sh_bot = open_jacket_ring(0.0, 0.586, 0.006, 0.208, 0.146, tee_half_w=0.056, sh_drop=0.000)
    sh_top = open_jacket_ring(0.0, 1.092, 0.006, 0.188, 0.132, tee_half_w=0.054, sh_drop=0.016)

    # k=7 is the center front white t-shirt (MAT_VCOL); k=0..6 are the open plaid flannel panels (MAT_FLANNEL)
    flannel_u_spans = {
        0: (0.00, 0.16),  # front-left panel
        1: (0.16, 0.30),  # left-front side
        2: (0.30, 0.42),  # left-back side
        3: (0.42, 0.62),  # wide back panel
        4: (0.62, 0.74),  # right-back side
        5: (0.74, 0.88),  # right-front side
        6: (0.88, 1.00),  # front-right panel
    }

    cmid_t = (sum(sh_bot, Vector()) + sum(sh_top, Vector())) / 16.0
    for k in range(8):
        kn = (k + 1) % 8
        p0, p1, p2, p3 = sh_bot[k], sh_bot[kn], sh_top[kn], sh_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        if k == 7:
            # Off-white undershirt visible down the center front
            mb.face([p0, p1, p2, p3], TEE, out=(0, 0, 1), mat_idx=MAT_VCOL)
        else:
            u0, u1 = flannel_u_spans[k]
            uvs = [(u0, 0.345), (u1, 0.345), (u1, 0.995), (u0, 0.995)]
            mb.face([p0, p1, p2, p3], TEX_WHITE, out=(mid - cmid_t), mat_idx=MAT_FLANNEL, uvs=uvs)

    # Top shoulder deck (2 textured flannel quads + center neckline fill = 6 tris)
    mb.face([sh_top[0], sh_top[1], sh_top[2], sh_top[3]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_FLANNEL, uvs=[(0.05, 0.74), (0.35, 0.74), (0.35, 0.96), (0.05, 0.96)])
    mb.face([sh_top[4], sh_top[5], sh_top[6], sh_top[7]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_FLANNEL, uvs=[(0.65, 0.74), (0.95, 0.74), (0.95, 0.96), (0.65, 0.96)])
    mb.face([sh_top[7], sh_top[0], sh_top[3], sh_top[4]], TEE_SHADE, out=(0, 1, 0), mat_idx=MAT_VCOL)

    # =========================================================================
    # 8. LONG FLANNEL SLEEVES + CHUNKY PEACH HANDS (32 + 20 = 52 tris)
    # =========================================================================
    mb.set_part("sleeves_hands")
    # Right arm (-X) arches slightly out over the tucked skateboard so hand grips mid-lower deck!
    # Left arm (+X) hangs naturally at skater's side with a relaxed slight elbow bend.
    arm_specs = [
        # (side, bname,  p_sh,                            p_el,                             p_wr,                             p_hd)
        (-1, "Arm_R", V(-0.166, SHOULDER_Y, SHOULDER_Z), V(-0.286, 0.840, -0.016), V(-0.292, 0.700, 0.012), V(-0.270, 0.598, 0.022)),
        ( 1, "Arm_L", V( 0.166, SHOULDER_Y, SHOULDER_Z), V( 0.248, 0.838, -0.014), V( 0.240, 0.688, 0.032), V( 0.232, 0.590, 0.048)),
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

        r_sh = slv_ring(p_sh, ax1, 0.066, 0.062)
        r_el = slv_ring(p_el, axm, 0.076, 0.066)
        r_wr = slv_ring(p_wr, ax2, 0.068, 0.058)

        def slv_uv(i, k):
            u0 = k * 0.25
            u1 = (k + 1) * 0.25
            v_top = 0.330 if i == 0 else 0.165
            v_bot = 0.165 if i == 0 else 0.005
            return [(u0, v_top), (u1, v_top), (u1, v_bot), (u0, v_bot)]

        # 2 segments x 4 quads = 16 tris per sleeve
        mb.loft([r_sh, r_el, r_wr], TEX_WHITE, cap_bottom=False, cap_top=False,
                mat_idx=MAT_FLANNEL, uv_fn=slv_uv)

        # Chunky peach hand emerging cleanly from sleeve cuff (8 walls + 2 tip = 10 tris per hand)
        ax_h = (p_hd - p_wr).normalized()
        p_h0 = p_wr - ax_h * 0.016
        p_h1 = p_hd + ax_h * 0.018
        rh0 = slv_ring(p_h0, ax_h, 0.056, 0.048)
        rh1 = slv_ring(p_h1, ax_h, 0.050, 0.042)
        mb.loft([rh0, rh1], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN)

    # =========================================================================
    # 9. SLIM DARK CHARCOAL BACKPACK + SHOULDER STRAPS (10 + 8 = 18 tris, bone="Torso")
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    bp_bot = [
        V(-0.138, 0.692, -0.114),
        V( 0.138, 0.692, -0.114),
        V( 0.128, 0.692, -0.246),
        V(-0.128, 0.692, -0.246),
    ]
    bp_top = [
        V(-0.120, 1.032, -0.104),
        V( 0.120, 1.032, -0.104),
        V( 0.104, 1.010, -0.214),
        V(-0.104, 1.010, -0.214),
    ]
    # Skip k=0 (against back) -> 3 walls + top + bottom = 10 tris
    mb.loft([bp_bot, bp_top], lambda i, k: PACK_SHADE if k in (1, 3) else PACK,
            cap_bottom=True, cap_top=True, bot_color=PACK_SHADE, top_color=PACK, skip_k=(0,))

    # Two dark charcoal backpack straps hugging snugly over shoulders (2 x 4 = 8 tris)
    for side in (-1, 1):
        xi_f, xo_f = side * 0.114, side * 0.156
        xi_t, xo_t = side * 0.108, side * 0.150
        xi_b, xo_b = side * 0.098, side * 0.140
        p_f0 = V(xi_f, 0.908,  0.140); p_f1 = V(xo_f, 0.898,  0.120)
        p_t0 = V(xi_t, 1.092,  0.034); p_t1 = V(xo_t, 1.080,  0.024)
        p_b0 = V(xi_b, 1.028, -0.112); p_b1 = V(xo_b, 1.016, -0.110)
        mb.face([p_f0, p_f1, p_t1, p_t0], PACK_STRAP, out=(side * 0.25, 0.35, 0.90))
        mb.face([p_t0, p_t1, p_b1, p_b0], PACK_STRAP, out=(side * 0.20, 0.80, -0.55))

    # =========================================================================
    # 10. SKATEBOARD TUCKED UNDER RIGHT ARM (deck 28 + trucks 12 + wheels 32 = 72 tris, bone="Arm_R")
    # =========================================================================
    mb.set_part("skateboard", bone="Arm_R")
    board_ctr = V(-0.230, 0.644, -0.046)
    pitch = math.radians(-14.5)  # nose tilts slightly down (+Z, -Y), tail sticks slightly up (-Z, +Y)
    u_len = V(0.0, math.sin(pitch), math.cos(pitch))     # along length toward nose (+Z)
    v_wid = V(0.0, math.cos(pitch), -math.sin(pitch))    # across width toward top edge (+Y)
    n_out = V(-1.0, 0.0, 0.0)                            # outward toward viewer (-X)

    def bpt(s, t, d):
        """Point on skateboard: s along length, t across width, d outward from board_ctr."""
        return board_ctr + u_len * s + v_wid * t + n_out * d

    # 10a. Rounded-nose/tail popsicle deck (8-vertex stadium perimeter, beveled yellow wood rim!)
    # Outer face (d = +0.013) is inset slightly in (s, t) so the single 8-quad bevel band forms
    # a super crisp golden-yellow maple border framing the slate-blue bottom graphic!
    hl = 0.365   # half-length (~73 cm total deck)
    hw = 0.112   # half-width (~22.4 cm total width)
    st_in = [
        ( hl,        hw * 0.44),  # 0: nose-top
        ( hl * 0.72, hw),         # 1: front-top shoulder
        (-hl * 0.72, hw),         # 2: rear-top shoulder
        (-hl,        hw * 0.44),  # 3: tail-top
        (-hl,       -hw * 0.44),  # 4: tail-bot
        (-hl * 0.72,-hw),         # 5: rear-bot shoulder
        ( hl * 0.72,-hw),         # 6: front-bot shoulder
        ( hl,       -hw * 0.44),  # 7: nose-bot
    ]
    st_out = [(s * 0.915, t * 0.870) for (s, t) in st_in]
    deck_in  = [bpt(s, t, -0.013) for (s, t) in st_in]
    deck_out = [bpt(s, t,  0.013) for (s, t) in st_out]

    # Beveled golden-yellow wood rim around 8 sides (16 tris) + dark grip inner cap (6) + slate-blue outer cap (6) = 28 tris!
    mb.loft([deck_in, deck_out], DECK_EDGE,
            cap_bottom=True, cap_top=True,
            bot_color=DECK_GRIP, top_color=DECK_FACE)

    # 10b. Two dark charcoal truck hangers spanning between top & bottom wheels (2 x 6 = 12 tris)
    for s_tr in (-0.195, 0.175):
        sw = 0.022
        tw = 0.072
        d0 = 0.012
        d1 = 0.044
        # 4-sided bar along v_wid (skip inner deck face + top/bottom ends covered by wheels -> 3 quads = 6 tris)
        p_bf0 = bpt(s_tr + sw, -tw, d0); p_bf1 = bpt(s_tr + sw, -tw, d1)
        p_bb1 = bpt(s_tr - sw, -tw, d1); p_bb0 = bpt(s_tr - sw, -tw, d0)
        p_tf0 = bpt(s_tr + sw,  tw, d0); p_tf1 = bpt(s_tr + sw,  tw, d1)
        p_tb1 = bpt(s_tr - sw,  tw, d1); p_tb0 = bpt(s_tr - sw,  tw, d0)
        mb.face([p_bf1, p_bb1, p_tb1, p_tf1], TRUCK,       out=n_out)
        mb.face([p_bf0, p_bf1, p_tf1, p_tf0], TRUCK_SHADE, out=u_len)
        mb.face([p_bb1, p_bb0, p_tb0, p_tb1], TRUCK_SHADE, out=-u_len)

    # 10c. Four chunky stylized skateboard wheels (4 x 8 = 32 tris: 3 visible tread quads + 1 outer hub cap!)
    # Rear truck: olive top + mustard-yellow bottom; Front truck: sage-teal pair (matching reference!)
    wheel_specs = [
        # (s_tr,  side_t, col_main,      col_shade)
        (-0.195,  1,      WHEEL_OLIVE,   WHEEL_OLIVE_SH),
        (-0.195, -1,      WHEEL_YELLOW,  WHEEL_YELLOW_SH),
        ( 0.175,  1,      WHEEL_TEAL,    WHEEL_TEAL_SH),
        ( 0.175, -1,      WHEEL_TEAL,    WHEEL_TEAL_SH),
    ]
    for (s_tr, side_t, wcol, wsh) in wheel_specs:
        t_in  = side_t * 0.068
        t_out = side_t * 0.118
        rs = 0.030
        d_in  = 0.013
        d_out = 0.066
        # 4 corners around the wheel perimeter in (s, d): 0=front-in, 1=front-out, 2=back-out, 3=back-in
        r_in = [
            bpt(s_tr + rs, t_in, d_in),
            bpt(s_tr + rs, t_in, d_out),
            bpt(s_tr - rs, t_in, d_out),
            bpt(s_tr - rs, t_in, d_in),
        ]
        r_out = [
            bpt(s_tr + rs, t_out, d_in),
            bpt(s_tr + rs, t_out, d_out),
            bpt(s_tr - rs, t_out, d_out),
            bpt(s_tr - rs, t_out, d_in),
        ]
        # Skip k=3 (deck-facing tread hidden against board!) -> 3 tread quads (6 tris) + exposed outer end cap (2 tris) = 8 tris!
        mb.loft([r_in, r_out], lambda i, k, wc=wcol, ws=wsh: wc if k == 1 else ws,
                cap_bottom=False, cap_top=True, top_color=wcol, skip_k=(3,))

    # =========================================================================
    # 11. LOOSE DARK CHARCOAL SKATER PANTS (pelvis 8 + 2 legs 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.184, 0.184, 0.518, 0.626, -0.112, 0.112, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.182
        x_in_b, x_out_b = side * 0.028, side * 0.210
        rz_t, rz_b = 0.104, 0.114
        r_top = [
            V(min(x_in_t, x_out_t), 0.562,  rz_t),
            V(max(x_in_t, x_out_t), 0.562,  rz_t),
            V(max(x_in_t, x_out_t), 0.562, -rz_t),
            V(min(x_in_t, x_out_t), 0.562, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.124,  rz_b),
            V(max(x_in_b, x_out_b), 0.124,  rz_b),
            V(max(x_in_b, x_out_b), 0.124, -rz_b),
            V(min(x_in_b, x_out_b), 0.124, -rz_b),
        ]
        mb.loft([r_bot, r_top], lambda i, k: PANTS_SHADE if k == 2 else PANTS,
                cap_bottom=True, cap_top=False, bot_color=PANTS_INNER)

    # =========================================================================
    # 12. CHUNKY CANVAS SKATE SNEAKERS (grey upper + cream rubber sole & toe cap + white laces = 40 tris)
    # =========================================================================
    mb.set_part("sneakers")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.122
        w = 0.072
        w_toe = 0.062
        z_heel = -0.090
        z_toe  =  0.172
        y_sole0 = 0.000
        y_sole1 = 0.042
        y_toe_cap = 0.078  # Raised rubber toe bumper gives Converse-style white toe cap + grey canvas upper!
        y_col   = 0.140

        sole_bot = [
            V(cx - w,     y_sole0, z_heel),
            V(cx + w,     y_sole0, z_heel),
            V(cx + w_toe, y_sole0, z_toe),
            V(cx - w_toe, y_sole0, z_toe),
        ]
        sole_top = [
            V(cx - w,     y_sole1,   z_heel),
            V(cx + w,     y_sole1,   z_heel),
            V(cx + w_toe, y_toe_cap, z_toe),
            V(cx - w_toe, y_toe_cap, z_toe),
        ]
        mb.loft([sole_bot, sole_top], SHOE_SOLE, cap_bottom=True, cap_top=False, bot_color=SHOE_SOLE)

        # Canvas upper: grey on sides & upper instep, slightly shaded on heel back
        shoe_top = [
            V(cx - w * 0.86, y_col, z_heel + 0.014),
            V(cx + w * 0.86, y_col, z_heel + 0.014),
            V(cx + w * 0.82, y_col, 0.058),
            V(cx - w * 0.82, y_col, 0.058),
        ]
        mb.loft([sole_top, shoe_top],
                lambda i, k: SHOE_SHADE if k == 0 else SHOE,
                cap_bottom=False, cap_top=False)

        # Crisp white skate-shoe laces strip sitting flush on the grey upper instep (2 tris per shoe)
        lw = 0.034
        mb.face([
            V(cx - lw, y_toe_cap + 0.018, 0.144),
            V(cx + lw, y_toe_cap + 0.018, 0.144),
            V(cx + lw, y_col - 0.012,     0.072),
            V(cx - lw, y_col - 0.012,     0.072),
        ], SHOE_LACE, out=(0, 0.72, 0.70))

    return mb


def setup_materials(flannel_img):
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

    # Slot 1: Painted Plaid Flannel Jacket material
    mat_flannel = bpy.data.materials.new("SkaterFlannel")
    nt_t = mat_flannel.node_tree
    bsdf_t = next(n for n in nt_t.nodes if n.type == "BSDF_PRINCIPLED")
    tex_t = nt_t.nodes.new("ShaderNodeTexImage")
    tex_t.image = flannel_img
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

    return [mat_vcol, mat_flannel]


def _reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _create_walk_action(rig, scene):
    """24-frame looping Walk cycle: relaxed skater stride carrying skateboard tucked under right arm."""
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

        # Easy, slightly bouncy skater stride
        pb_root = rig.pose.bones["Root"]
        bob = -0.024 * (1.0 - c2) * 0.5
        root_pitch = -0.032
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.072 * s1, 0.038 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.018 * c2, 0.088 * s1, -0.026 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed head stabilization looking ahead
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.030 + 0.022 * c2, -0.044 * s1, -0.018 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating skate-shoe stride with clean foot lift above ground
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.44 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.038, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.44 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.038, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Free left arm swings naturally in counter-phase to legs
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.34 * s1 - 0.02, 0.0, 0.035)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm carries the skateboard snugly with subtle weighted sway (keeps board clear of leg!)
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.085 * s1 - 0.025 * c2, 0.0, -0.022 - 0.015 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: chilled skater weight shift, looking around, gentle skateboard heft."""
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

        # Laid-back weight sway & soft breathing bob
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - math.cos(2.0 * phi)) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.006, 0.028 * s1, 0.030 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.022 * s2, 0.036 * s1, -0.022 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Casually glancing side to side with a tiny laid-back nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.032 * s2 + 0.015 * c1, 0.28 * s1, 0.048 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Sneakers planted cleanly on the ground
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed free left arm drifting gently with breath
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.045 * s1 - 0.020 * s2, 0.0, 0.028 + 0.016 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Right arm gently adjusts/tilts the tucked skateboard slightly while waiting
        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (0.055 * s2 - 0.020 * c1, 0.0, -0.024 - 0.018 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build standard 7-bone passenger rig (Root, Torso, Head, Arm_L, Arm_R, Leg_L, Leg_R) with Walk & Idle."""
    arm_data = bpy.data.armatures.new("PersonSkaterRig")
    rig = bpy.data.objects.new("PersonSkaterRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.568,  0.000),      ( 0.000, 0.668,  0.000)),
        ("Torso", "Root",  ( 0.000, 0.620,  0.000),      ( 0.000, 1.080,  0.000)),
        ("Head",  "Torso", ( 0.000, 1.116,  0.000),      ( 0.000, 1.440,  0.000)),
        ("Arm_L", "Torso", ( 0.166, SHOULDER_Y, SHOULDER_Z), ( 0.166, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Arm_R", "Torso", (-0.166, SHOULDER_Y, SHOULDER_Z), (-0.166, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Leg_L", "Root",  ( 0.106, 0.532,  0.000),      ( 0.106, 0.692,  0.000)),
        ("Leg_R", "Root",  (-0.106, 0.532,  0.000),      (-0.106, 0.692,  0.000)),
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
        (-2.25, math.radians(58)),   # Front-3/4 matching reference angle (facing right, showing skateboard!)
        (-0.75, math.radians(0)),    # Front (showing open flannel + white tee + face)
        ( 0.75, math.radians(90)),   # Right side (showing skateboard deck, trucks, wheels, beanie tilt & nape curls)
        ( 2.25, math.radians(180)),  # Back (showing charcoal backpack, plaid back & wavy hair)
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
    cam_obj.location = (0.0, -6.5, 1.24)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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


def render_anim_strip(rig, obj, action, frames, out_path, zrot_deg=58):
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
    cam_obj.location = (0.0, -7.5, 1.24)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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
    cam_obj.location = (0.0, -6.0, 1.24)
    direction = Vector((0.0, 0.0, 0.86)) - cam_obj.location
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

    coll = bpy.data.collections.new("PersonSkater")
    bpy.context.scene.collection.children.link(coll)

    flannel_img = generate_flannel_texture(FLANNEL_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonSkater")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(flannel_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonSkater", me)
    coll.objects.link(ob)

    render_preview(ob, PREVIEW_PATH)

    rig, walk_action, idle_action = build_rig_and_animations(ob, mb, coll)

    total_tris = sum(len(p.vertices) - 2 for p in me.polygons)
    total_faces = len(me.polygons)
    total_verts = len(me.vertices)
    assert total_tris < 350, f"Triangle budget exceeded: {total_tris} >= 350"

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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=58)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=48)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=58, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)

    print("=== PersonSkater Stats ===")
    print(f"Total triangles: {total_tris}")
    print(f"Total polygons:  {total_faces}")
    print(f"Total vertices:  {total_verts}")
    print(f"Rig bones:       {len(rig.data.bones)}")
    print(f"Animations:      {walk_action.name} (1-24 @ 24fps), {idle_action.name} (1-48 @ 24fps)")
    print("Per-part triangles:")
    for part, cnt in mb.part_tris.items():
        print(f"  {part:18s}: {cnt}")
    print(f"Flannel texture: {FLANNEL_TEX_PATH}")
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
