# Builds an ultra-low-poly (< 350 tris) stylized bearded man wearing a slate-navy baseball cap
# with a tan front patch, light-grey hair, full sculpted beard & walrus mustache, image-textured
# red-and-black buffalo-plaid flannel button-up shirt with folded collar, dark charcoal backpack
# with shoulder straps, dark charcoal-navy trousers, and chunky tan-brown leather hiking boots.
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_flannel_man.py)
# Saves art/person_flannel_man.blend, exports assets/models/person_flannel_man.glb (rigged + Walk & Idle cycles + embedded texture),
# renders art/person_flannel_man_preview.png, art/person_flannel_man_walk_preview.png, art/person_flannel_man_idle_preview.png,
# and outputs rendered videos art/person_flannel_man_walk.mp4 and art/person_flannel_man_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.69 m tall.
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
BLEND_PATH = os.path.join(ROOT, "art", "person_flannel_man.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_flannel_man.glb")
FLANNEL_TEX_PATH = os.path.join(ROOT, "art", "person_flannel_man_tex.png")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_flannel_man_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_flannel_man_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_flannel_man_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_flannel_man_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_flannel_man_idle.mp4")

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

SKIN             = col_srgb(0.98, 0.76, 0.53)
SKIN_SHADE       = col_srgb(0.87, 0.64, 0.42)
EYE              = col_srgb(0.11, 0.10, 0.11)

BEARD            = col_srgb(0.88, 0.86, 0.83)
HAIR             = col_srgb(0.85, 0.83, 0.80)
MUSTACHE         = col_srgb(0.92, 0.90, 0.87)
BEARD_SHADE      = col_srgb(0.74, 0.72, 0.69)

CAP              = col_srgb(0.32, 0.36, 0.46)
CAP_TOP          = col_srgb(0.37, 0.41, 0.51)
CAP_BRIM         = col_srgb(0.28, 0.32, 0.42)
CAP_UNDER        = col_srgb(0.20, 0.23, 0.32)
CAP_PATCH        = col_srgb(0.91, 0.68, 0.41)

PACK             = col_srgb(0.33, 0.32, 0.31)
PACK_SHADE       = col_srgb(0.23, 0.22, 0.22)
PACK_STRAP       = col_srgb(0.21, 0.21, 0.22)
PACK_TAB         = col_srgb(0.19, 0.18, 0.18)

PANTS            = col_srgb(0.23, 0.26, 0.33)
PANTS_SHADE      = col_srgb(0.17, 0.19, 0.25)
PANTS_INNER      = col_srgb(0.12, 0.14, 0.19)

BOOT             = col_srgb(0.64, 0.48, 0.29)
BOOT_SHADE       = col_srgb(0.51, 0.37, 0.22)
BOOT_TONGUE      = col_srgb(0.57, 0.42, 0.25)
SOLE             = col_srgb(0.32, 0.24, 0.18)

# Parts the game recolours per passenger (see art/person_recolor.py).
# Textured buffalo-plaid flannel shirt, cap patch, eyes, backpack, and hiking boots stay fixed.
RECOLOR_GROUPS = {
    "skin": [SKIN, SKIN_SHADE],
    "hair": [BEARD, HAIR, MUSTACHE, BEARD_SHADE],
    "bottom": [PANTS, PANTS_SHADE, PANTS_INNER],
    "accent": [CAP, CAP_TOP, CAP_BRIM, CAP_UNDER],
}


def G(p):
    """Game frame (X left, Y up, Z forward) -> Blender frame (X left, -Z forward, Y up)."""
    return Vector((p[0], -p[2], p[1]))


def V(x, y, z):
    return Vector((x, y, z))


# Shared structural anchors for rig & geometry alignment
SHOULDER_Y = 1.045
SHOULDER_Z = 0.002


def _blend_mask(img, mask, color):
    """Alpha-blend an sRGB tuple color over an (H, W, 3) float32 image using soft mask in [0, 1]."""
    m = np.clip(mask, 0.0, 1.0)[..., None]
    col = np.array(color, dtype=np.float32)[None, None, :]
    return img * (1.0 - m) + col * m


def _buffalo_plaid(uu, vv, freq_u, freq_v):
    """Generate authentic red-and-black buffalo-plaid flannel pattern matched to reference artwork."""
    pu = (uu * freq_u) % 1.0
    pv = (vv * freq_v) % 1.0

    # Soft anti-aliased 50/50 warp & weft dark bands occupying [0.25..0.75] of each check repeat
    edge = 34.0
    u_dark = np.clip((pu - 0.25) * edge, 0.0, 1.0) * np.clip((0.75 - pu) * edge, 0.0, 1.0)
    v_dark = np.clip((pv - 0.25) * edge, 0.0, 1.0) * np.clip((0.75 - pv) * edge, 0.0, 1.0)

    # Pure red square: neither dark band; Mid maroon/brown weave: one dark band; Charcoal-black: both!
    single_dark = np.clip(u_dark + v_dark - 2.0 * u_dark * v_dark, 0.0, 1.0)
    cross_dark = u_dark * v_dark

    # Base warm brick-red flannel square
    col = np.zeros(uu.shape + (3,), dtype=np.float32)
    col[..., 0] = 0.69
    col[..., 1] = 0.27
    col[..., 2] = 0.19

    # Deep burgundy-brown / dark maroon single-band overlap (classic buffalo check mid-tone)
    col = _blend_mask(col, single_dark * 0.90, (0.39, 0.18, 0.15))

    # Rich dark warm-charcoal cross squares
    col = _blend_mask(col, cross_dark * 0.96, (0.15, 0.14, 0.15))

    # Subtle diagonal brushed flannel twill micro-texture
    twill = 1.0 + 0.022 * np.sin((uu * 240.0 + vv * 240.0))
    weave = 1.0 + 0.012 * np.cos((uu * 180.0 - vv * 180.0))
    col *= (twill * weave)[..., None]
    return np.clip(col, 0.0, 1.0)


def generate_flannel_texture(out_path):
    """Paint a 512x512 sRGB red/black buffalo-plaid flannel shirt texture:
       - Top region (v in [0.34, 1.00]): Torso shirt front, sides, back & shoulders.
       - Bottom strip (v in [0.00, 0.34]): Matching plaid sleeves & folded shirt collar with dark wrist cuff.
    """
    w, h = 512, 512
    u = np.linspace(0.0, 1.0, w, endpoint=False, dtype=np.float32)
    v = np.linspace(0.0, 1.0, h, endpoint=False, dtype=np.float32)
    uu, vv = np.meshgrid(u, v)

    # 1. Torso buffalo plaid (v in [0.34, 1.00])
    # Bold square checks (~3.5 repeats vertically across torso, ~6 repeats around torso circumference)
    torso_img = _buffalo_plaid(uu + 0.06, vv + 0.04, freq_u=6.0, freq_v=5.4)
    torso_t = np.clip((vv - 0.34) / 0.66, 0.0, 1.0)
    # Subtle soft shading toward lower hem for crisp grounded form
    torso_img *= (0.89 + 0.13 * torso_t)[..., None]

    # Subtle center-front button placket shadow seam at u = 0.50 (front chest center)
    placket = np.clip((0.007 - np.abs(uu - 0.50)) / 0.003, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, placket * 0.25, (0.11, 0.08, 0.09))

    # Subtle lower shirt hem stitch near v = 0.354
    hem_seam = np.clip((0.006 - np.abs(vv - 0.354)) / 0.003, 0.0, 1.0)
    torso_img = _blend_mask(torso_img, hem_seam * 0.38, (0.12, 0.09, 0.10))

    # 2. Sleeve & folded collar strip (v in [0.00, 0.34])
    # ~3.5 checks around arm circumference, ~3.2 checks along sleeve length
    sleeve_img = _buffalo_plaid(uu + 0.10, vv + 0.02, freq_u=3.5, freq_v=9.5)
    slv_t = np.clip(vv / 0.34, 0.0, 1.0)
    sleeve_img *= (0.90 + 0.12 * slv_t)[..., None]

    # Subtle dark cuff hem & seam at wrist bottom (v in [0.00, 0.045])
    cuff_m = np.clip((0.044 - vv) / 0.006, 0.0, 1.0)
    sleeve_img = _blend_mask(sleeve_img, cuff_m * 0.45, (0.18, 0.11, 0.10))
    cuff_seam = np.clip((0.006 - np.abs(vv - 0.046)) / 0.003, 0.0, 1.0)
    sleeve_img = _blend_mask(sleeve_img, cuff_seam * 0.48, (0.10, 0.08, 0.08))

    in_torso = (vv >= 0.340).astype(np.float32)
    img = sleeve_img * (1.0 - in_torso[..., None]) + torso_img * in_torso[..., None]
    img = np.clip(img, 0.0, 1.0)

    bimg = bpy.data.images.new("FlannelManTex", width=w, height=h, alpha=True, float_buffer=False)
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


def shirt_ring(cx, cy, cz, rx, rz, sh_drop=0.0):
    """8-sided chamfered boxy shirt ring with flat chest, flat back, angled corners, flat sides."""
    yo = cy - sh_drop
    # Ordered CCW around +Y starting at back-center-left -> front -> back so U wraps smoothly around!
    return [
        V(cx + rx * 0.72, cy, cz - rz),         # 0: back-left corner
        V(cx + rx,        yo, cz - rz * 0.56),  # 1: left-back side
        V(cx + rx,        yo, cz + rz * 0.56),  # 2: left-front side
        V(cx + rx * 0.72, cy, cz + rz),         # 3: front-left corner
        V(cx - rx * 0.72, cy, cz + rz),         # 4: front-right corner
        V(cx - rx,        yo, cz + rz * 0.56),  # 5: right-front side
        V(cx - rx,        yo, cz - rz * 0.56),  # 6: right-back side
        V(cx - rx * 0.72, cy, cz - rz),         # 7: back-right corner
    ]


def build_person():
    mb = MeshBuilder()

    # =========================================================================
    # 1. HEAD (6-sided chunky head with warm peach face & light-grey back hair = 18 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    head_specs = [
        # (y,     cz,     rx,    rz)
        (1.168,  0.012, 0.166, 0.156),  # 0: jaw / nape base
        (1.264,  0.018, 0.218, 0.204),  # 1: cheek / beard top line
        (1.454,  0.010, 0.216, 0.202),  # 2: forehead tucked cleanly inside baseball cap
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    # k=5 flat front face (+Z), k=0 (+X) & k=4 (-X) cheeks; k=1,2,3 back & side hair.
    # Skip band i=0 for k in (4, 5, 0) since the full sculpted beard completely encloses the lower front/cheeks!
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
                col = BEARD_SHADE if k == 2 else HAIR
            else:
                col = SKIN if k in (4, 5, 0) else HAIR
            mb.face([p0, p1, p2, p3], col, out=(mid - cmid))

    # =========================================================================
    # 2. FULL SCULPTED GREY BEARD + PLUMP WALRUS MUSTACHE (26 + 16 = 42 tris)
    # =========================================================================
    mb.set_part("beard", bone="Head")
    # 5-segment rounded beard wrapping cleanly from under ears/sideburns around a full rounded chin
    b_bot = [
        V(-0.196, 1.198, -0.022),  # 0: right jaw back (seals cleanly into nape hair below ear)
        V(-0.172, 1.168,  0.118),  # 1: right outer jaw curve
        V(-0.086, 1.148,  0.208),  # 2: right front chin
        V( 0.086, 1.148,  0.208),  # 3: left front chin
        V( 0.172, 1.168,  0.118),  # 4: left outer jaw curve
        V( 0.196, 1.198, -0.022),  # 5: left jaw back
    ]
    b_top = [
        V(-0.220, 1.292, -0.022),  # 0: right sideburn high (seals cleanly under ear!)
        V(-0.204, 1.280,  0.126),  # 1: right cheek curve
        V(-0.098, 1.284,  0.222),  # 2: right upper beard under mustache
        V( 0.098, 1.284,  0.222),  # 3: left upper beard under mustache
        V( 0.204, 1.280,  0.126),  # 4: left cheek curve
        V( 0.220, 1.292, -0.022),  # 5: left sideburn high
    ]
    b_in_top = [
        V(-0.190, 1.288, -0.018),
        V(-0.178, 1.276,  0.112),
        V(-0.084, 1.280,  0.186),
        V( 0.084, 1.280,  0.186),
        V( 0.178, 1.276,  0.112),
        V( 0.190, 1.288, -0.018),
    ]
    b_in_bot = [
        V(-0.146, 1.190, -0.014),
        V(-0.126, 1.168,  0.088),
        V(-0.066, 1.156,  0.146),
        V( 0.066, 1.156,  0.146),
        V( 0.126, 1.168,  0.088),
        V( 0.146, 1.190, -0.014),
    ]
    # 5 outer quads (10 tris) + 5 top cheek ledges (10 tris) = 20 tris
    for k in range(5):
        p0, p1, p2, p3 = b_bot[k], b_bot[k + 1], b_top[k + 1], b_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        col = BEARD_SHADE if k in (0, 4) else BEARD
        mb.face([p0, p1, p2, p3], col, out=V(mid.x, -0.10, mid.z))
        mb.face([b_top[k], b_top[k + 1], b_in_top[k + 1], b_in_top[k]], BEARD, out=(0, 1, 0.1))
    # 3 streamlined underside chin quads (6 tris -> 26 tris total for full watertight beard!)
    mb.face([b_bot[2], b_bot[1], b_bot[0], b_in_bot[2]], BEARD_SHADE, out=(0, -1, 0))
    mb.face([b_bot[3], b_bot[2], b_in_bot[2], b_in_bot[3]], BEARD_SHADE, out=(0, -1, 0))
    mb.face([b_bot[5], b_bot[4], b_bot[3], b_in_bot[3]], BEARD_SHADE, out=(0, -1, 0))

    # Plump, rounded 2-wing walrus mustache arching cleanly across upper lip (16 tris)
    m_ctr = [
        V(0.000, 1.306, 0.200),  # 0: top back (against face)
        V(0.000, 1.304, 0.242),  # 1: top front ridge
        V(0.000, 1.262, 0.244),  # 2: lower front fullness
        V(0.000, 1.258, 0.202),  # 3: bottom back
    ]
    m_r = [
        V(-0.098, 1.280, 0.192),
        V(-0.094, 1.282, 0.220),
        V(-0.098, 1.248, 0.218),
        V(-0.096, 1.246, 0.192),
    ]
    m_l = [
        V( 0.098, 1.280, 0.192),
        V( 0.094, 1.282, 0.220),
        V( 0.098, 1.248, 0.218),
        V( 0.096, 1.246, 0.192),
    ]
    mb.loft(
        [m_r, m_ctr, m_l],
        lambda i, k: BEARD_SHADE if k == 2 else MUSTACHE,
        cap_bottom=True, cap_top=True,
        bot_color=BEARD_SHADE, top_color=BEARD_SHADE,
        skip_k=(3,),
    )

    # =========================================================================
    # 3. EARS (2 cute rounded blocky low-poly peach tabs above beard line = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.194
        x_out = side * 0.236
        y0, y1 = 1.286, 1.368
        z0, z1 = -0.016, 0.056
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.016, zm)
        p_ot = V(x_out, y1 - 0.016, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. EYES (2 crisp vertical dark pill hexagons flush on front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    z_eye = 0.198
    for side in (-1, 1):
        cx = side * 0.064
        cy = 1.358
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
    # 5. NECK (3-sided front/side peach prism peeking inside open flannel collar = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_b = [V(-0.068, 1.062, -0.036), V(0.000, 1.062, 0.106), V(0.068, 1.062, -0.036)]
    n_t = [V(-0.066, 1.186, -0.034), V(0.000, 1.186, 0.092), V(0.066, 1.186, -0.034)]
    mb.face([n_b[0], n_b[1], n_t[1], n_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_b[1], n_b[2], n_t[2], n_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 6. SLATE-NAVY BASEBALL CAP + TAN LEATHER PATCH + TOP BUTTON (46 tris)
    # =========================================================================
    mb.set_part("baseball_cap", bone="Head")
    cap_tilt = math.radians(14.0)  # jaunty backward tilt exposing clean brow above eyes
    st, ct = math.sin(cap_tilt), math.cos(cap_tilt)
    cap_orig = V(0.0, 1.430, -0.006)

    def cap_ring(h, rx, rz):
        cy = cap_orig.y + h * ct
        cz = cap_orig.z - h * st
        return tilted_ring(0.0, cy, cz, rx, rz, cap_tilt, n=6, phase=math.pi / 6.0)

    c_rim = cap_ring(0.000, 0.244, 0.242)  # snug headband rim sitting over grey hair & brow
    c_mid = cap_ring(0.118, 0.222, 0.220)  # rounded dome shoulder
    c_top = cap_ring(0.204, 0.118, 0.116)  # crown top ring

    # 6-sided dome crown (2 bands * 12 = 24 tris + 4 tri top cap = 28 tris)
    mb.loft(
        [c_rim, c_mid, c_top],
        lambda i, k: CAP_TOP if (i == 1 and k in (4, 5, 0)) else (CAP_BRIM if k in (1, 2, 3) else CAP),
        cap_bottom=False, cap_top=True, top_color=CAP_TOP,
    )

    # Cute low-poly top cap button (4-sided squat pyramid = 4 tris)
    btn_h = 0.204
    btn_ctr = V(0.0, cap_orig.y + (btn_h + 0.020) * ct, cap_orig.z - (btn_h + 0.020) * st)
    b_pts = [
        V( 0.000, cap_orig.y + btn_h * ct + 0.036 * st, cap_orig.z - btn_h * st + 0.036 * ct),
        V( 0.036, cap_orig.y + btn_h * ct,              cap_orig.z - btn_h * st),
        V( 0.000, cap_orig.y + btn_h * ct - 0.036 * st, cap_orig.z - btn_h * st - 0.036 * ct),
        V(-0.036, cap_orig.y + btn_h * ct,              cap_orig.z - btn_h * st),
    ]
    for k in range(4):
        kn = (k + 1) % 4
        mb.face([b_pts[k], b_pts[kn], btn_ctr], CAP_TOP, out=(0, 1, 0))

    # Tan rectangular leather patch sitting cleanly on the upper front panel of the cap (2 tris)
    f_bl = c_rim[5].lerp(c_rim[0], 0.25).lerp(c_mid[5].lerp(c_mid[0], 0.25), 0.36)
    f_br = c_rim[5].lerp(c_rim[0], 0.75).lerp(c_mid[5].lerp(c_mid[0], 0.75), 0.36)
    f_tl = c_rim[5].lerp(c_rim[0], 0.27).lerp(c_mid[5].lerp(c_mid[0], 0.27), 0.92)
    f_tr = c_rim[5].lerp(c_rim[0], 0.73).lerp(c_mid[5].lerp(c_mid[0], 0.73), 0.92)
    patch_n = ((f_br - f_bl).cross(f_tl - f_bl)).normalized()
    if patch_n.z < 0:
        patch_n = -patch_n
    p_off = patch_n * 0.008
    mb.face([f_bl + p_off, f_br + p_off, f_tr + p_off, f_tl + p_off], CAP_PATCH, out=patch_n)

    # Gently downward-curving 3-segment forward baseball bill / visor (top 6 + underside 6 = 12 tris)
    v_in = [
        c_rim[4].lerp(c_rim[5], 0.35),  # 0: right temple anchor
        c_rim[5],                       # 1: front-right brow
        c_rim[0],                       # 2: front-left brow
        c_rim[1].lerp(c_rim[0], 0.35),  # 3: left temple anchor
    ]
    v_out = [
        V(-0.228, 1.416, 0.184),        # 0: right outer bill wing
        V(-0.122, 1.422, 0.356),        # 1: front-right visor tip (gentle downward curve!)
        V( 0.122, 1.422, 0.356),        # 2: front-left visor tip
        V( 0.228, 1.416, 0.184),        # 3: left outer bill wing
    ]
    v_under_in = [V(p.x * 0.94, p.y - 0.022, p.z - 0.010) for p in v_in]
    v_under_out = [V(p.x, p.y - 0.014, p.z - 0.006) for p in v_out]
    for k in range(3):
        mb.face([v_in[k], v_out[k], v_out[k + 1], v_in[k + 1]],
                CAP if k == 1 else CAP_BRIM, out=(0, 1, 0.25))
        mb.face([v_under_in[k + 1], v_under_out[k + 1], v_under_out[k], v_under_in[k]],
                CAP_UNDER, out=(0, -1, -0.15))

    # =========================================================================
    # 7. TEXTURE-PAINTED BUFFALO-PLAID FLANNEL SHIRT TORSO + FOLDED COLLAR (39 tris)
    # =========================================================================
    mb.set_part("flannel_torso", bone="Torso")
    # 8-sided chamfered boxy shirt body (y = 0.594..1.106)
    sh_bot = shirt_ring(0.0, 0.594, 0.006, 0.214, 0.146, sh_drop=0.000)
    sh_top = shirt_ring(0.0, 1.106, 0.006, 0.194, 0.134, sh_drop=0.014)

    # Clean arc-length proportional U mapping so plaid squares are crisp and unstretched all around!
    # k=3 is the flat center front chest -> spans u in [0.38, 0.62] centered cleanly on u=0.50!
    torso_u_spans = {
        0: (0.08, 0.16),  # back-left bevel
        1: (0.16, 0.30),  # left flat side
        2: (0.30, 0.38),  # front-left bevel
        3: (0.38, 0.62),  # flat front chest (centered on u=0.50!)
        4: (0.62, 0.70),  # front-right bevel
        5: (0.70, 0.84),  # right flat side
        6: (0.84, 0.92),  # back-right bevel
        7: (0.92, 1.08),  # flat back panel (wraps smoothly!)
    }

    cmid_t = (sum(sh_bot, Vector()) + sum(sh_top, Vector())) / 16.0
    for k in range(8):
        kn = (k + 1) % 8
        p0, p1, p2, p3 = sh_bot[k], sh_bot[kn], sh_top[kn], sh_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        u0, u1 = torso_u_spans[k]
        uvs = [(u0, 0.345), (u1, 0.345), (u1, 0.995), (u0, 0.995)]
        mb.face([p0, p1, p2, p3], TEX_WHITE, out=(mid - cmid_t), mat_idx=MAT_FLANNEL, uvs=uvs)

    # Top shoulder deck (2 textured quads flanking the neck + 1 center bridge = 6 tris)
    mb.face([sh_top[0], sh_top[1], sh_top[2], sh_top[3]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_FLANNEL, uvs=[(0.12, 0.78), (0.34, 0.78), (0.34, 0.98), (0.12, 0.98)])
    mb.face([sh_top[4], sh_top[5], sh_top[6], sh_top[7]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_FLANNEL, uvs=[(0.66, 0.78), (0.88, 0.78), (0.88, 0.98), (0.66, 0.98)])
    mb.face([sh_top[7], sh_top[0], sh_top[3], sh_top[4]], TEX_WHITE, out=(0, 1, 0),
            mat_idx=MAT_FLANNEL, uvs=[(0.38, 0.80), (0.62, 0.80), (0.62, 0.98), (0.38, 0.98)])

    # Small warm-skin open V-neck triangle at top center of unbuttoned flannel collar (1 tri)
    mb.face([
        V(-0.042, 1.114, 0.144),
        V( 0.042, 1.114, 0.144),
        V( 0.000, 1.032, 0.148),
    ], SKIN_SHADE, out=(0, 0, 1))

    # Bold chunky folded flannel shirt collar wrapping around neck with crisp pointed front lapels (16 tris)
    mb.set_part("flannel_collar", bone="Torso")
    c_bot = [
        V(-0.036, 1.058,  0.156),  # 0: right front collar point flanking open V-neck!
        V(-0.172, 1.104,  0.048),  # 1: right outer shoulder fold
        V( 0.000, 1.102, -0.148),  # 2: back collar fold
        V( 0.172, 1.104,  0.048),  # 3: left outer shoulder fold
        V( 0.036, 1.058,  0.156),  # 4: left front collar point
    ]
    c_top = [
        V(-0.056, 1.164,  0.106),  # 0: right collar front fold crest
        V(-0.148, 1.174,  0.024),  # 1: right collar side crest
        V( 0.000, 1.176, -0.124),  # 2: back collar crest
        V( 0.148, 1.174,  0.024),  # 3: left collar side crest
        V( 0.056, 1.164,  0.106),  # 4: left collar front fold crest
    ]
    c_in = [
        V(-0.044, 1.132,  0.072),
        V(-0.092, 1.134,  0.010),
        V( 0.000, 1.134, -0.078),
        V( 0.092, 1.134,  0.010),
        V( 0.044, 1.132,  0.072),
    ]
    for k in range(4):
        p0, p1, p2, p3 = c_bot[k], c_bot[k + 1], c_top[k + 1], c_top[k]
        mid = (p0 + p1 + p2 + p3) * 0.25
        u0, u1 = k * 0.24, (k + 1) * 0.24
        mb.face([p0, p1, p2, p3], TEX_WHITE, out=V(mid.x, 0.12, mid.z),
                mat_idx=MAT_FLANNEL, uvs=[(u0, 0.14), (u1, 0.14), (u1, 0.30), (u0, 0.30)])
        mb.face([c_top[k], c_top[k + 1], c_in[k + 1], c_in[k]], TEX_WHITE, out=(0, 1, 0),
                mat_idx=MAT_FLANNEL, uvs=[(u0, 0.08), (u1, 0.08), (u1, 0.16), (u0, 0.16)])

    # =========================================================================
    # 8. LONG FLANNEL SLEEVES + CHUNKY PEACH HANDS (32 + 20 = 52 tris)
    # =========================================================================
    mb.set_part("sleeves_hands")
    arm_specs = [
        # (side, bname,  p_sh,                            p_el,                             p_wr,                             p_hd)
        (-1, "Arm_R", V(-0.178, SHOULDER_Y, SHOULDER_Z), V(-0.284, 0.854, -0.016), V(-0.280, 0.702, 0.036), V(-0.268, 0.600, 0.052)),
        ( 1, "Arm_L", V( 0.178, SHOULDER_Y, SHOULDER_Z), V( 0.284, 0.854, -0.016), V( 0.280, 0.702, 0.036), V( 0.268, 0.600, 0.052)),
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

        r_sh = slv_ring(p_sh, ax1, 0.070, 0.066)
        r_el = slv_ring(p_el, axm, 0.080, 0.070)
        r_wr = slv_ring(p_wr, ax2, 0.072, 0.062)

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
        p_h0 = p_wr - ax_h * 0.014
        p_h1 = p_hd + ax_h * 0.014
        rh0 = slv_ring(p_h0, ax_h, 0.056, 0.050)
        rh1 = slv_ring(p_h1, ax_h, 0.052, 0.044)
        mb.loft([rh0, rh1], lambda i, k: SKIN_SHADE if k == 2 else SKIN,
                cap_bottom=False, cap_top=True, top_color=SKIN)

    # =========================================================================
    # 9. CHUNKY DARK CHARCOAL BACKPACK + SIDE TABS + CURVED SHOULDER STRAPS (22 + 4 + 12 = 38 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Torso")
    # Faceted 4-ring hiker pack matching reference profile: angled bottom, full deep belly, sloped top lid
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.640, 0.146, -0.122, -0.264),  # 0: angled lower base
        (0.785, 0.184, -0.122, -0.366),  # 1: full lower-mid belly
        (0.985, 0.178, -0.118, -0.336),  # 2: upper-mid body
        (1.116, 0.130, -0.114, -0.214),  # 3: tapered top lid sitting neatly behind collar
    ]
    bp_rings = []
    for (y, rx, zin, zout) in bp_specs:
        bp_rings.append([
            V(-rx, y, zin),
            V( rx, y, zin),
            V( rx, y, zout),
            V(-rx, y, zout),
        ])
    # Skip k=0 (hidden face flush against shirt back): 3 bands * 3 quads (18) + bot (2) + top (2) = 22 tris
    mb.loft(bp_rings, lambda i, k: PACK_SHADE if i == 0 else PACK,
            cap_bottom=True, cap_top=True, bot_color=PACK_SHADE, top_color=PACK, skip_k=(0,))

    # Subtle side pocket buckle / tab detail on both sides (matching reference side profile = 4 tris)
    for side in (-1, 1):
        xs = side * 0.189
        mb.face([
            V(xs, 0.800, -0.228),
            V(xs, 0.800, -0.280),
            V(xs, 0.868, -0.280),
            V(xs, 0.868, -0.228),
        ], PACK_TAB, out=(side, 0, 0))

    # Bold curved dark charcoal shoulder straps hugging proudly over shoulders & around front armpits (2 x 6 = 12 tris)
    mb.set_part("backpack_straps", bone="Torso")
    for side in (-1, 1):
        # 4 cross-sections along strap path: back pack anchor -> top shoulder -> front chest -> underarm curve
        xi_b, xo_b = side * 0.104, side * 0.162
        xi_t, xo_t = side * 0.114, side * 0.178
        xi_f, xo_f = side * 0.126, side * 0.192
        xi_u, xo_u = side * 0.174, side * 0.224

        pb0 = V(xi_b, 1.092, -0.128); pb1 = V(xo_b, 1.080, -0.122)
        pt0 = V(xi_t, 1.136,  0.048); pt1 = V(xo_t, 1.124,  0.036)
        pf0 = V(xi_f, 1.005,  0.162); pf1 = V(xo_f, 0.992,  0.140)
        pu0 = V(xi_u, 0.835,  0.132); pu1 = V(xo_u, 0.835,  0.078)

        mb.face([pb0, pb1, pt1, pt0], PACK_STRAP, out=(side * 0.20, 0.85, -0.45))
        mb.face([pt0, pt1, pf1, pf0], PACK_STRAP, out=(side * 0.25, 0.42,  0.88))
        mb.face([pf0, pf1, pu1, pu0], PACK_STRAP, out=(side * 0.62, -0.10, 0.78))

    # =========================================================================
    # 10. DARK CHARCOAL-NAVY TROUSERS (pelvis 8 + 2 legs 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.186, 0.186, 0.526, 0.634, -0.112, 0.112, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.184
        x_in_b, x_out_b = side * 0.036, side * 0.212
        rz_t, rz_b = 0.104, 0.102
        r_top = [
            V(min(x_in_t, x_out_t), 0.568,  rz_t),
            V(max(x_in_t, x_out_t), 0.568,  rz_t),
            V(max(x_in_t, x_out_t), 0.568, -rz_t),
            V(min(x_in_t, x_out_t), 0.568, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.162,  rz_b),
            V(max(x_in_b, x_out_b), 0.162,  rz_b),
            V(max(x_in_b, x_out_b), 0.162, -rz_b),
            V(min(x_in_b, x_out_b), 0.162, -rz_b),
        ]
        mb.loft([r_bot, r_top], lambda i, k: PANTS_SHADE if k == 2 else PANTS,
                cap_bottom=True, cap_top=False, bot_color=PANTS_INNER)

    # =========================================================================
    # 11. CHUNKY TAN-BROWN LEATHER HIKING BOOTS WITH DARK SOLES (22 tris x 2 = 44 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.126
        w = 0.072
        w_toe = 0.062
        z_heel = -0.092
        z_mid  =  0.056
        z_toe  =  0.172
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_toe   = 0.096
        y_col   = 0.178  # tucks cleanly into pant cuff at y=0.162!

        # Thick dark chocolate-brown sole (4 walls + bottom = 10 tris)
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

        # Warm tan-brown leather boot upper (skip top buried inside pant cuff = 12 tris)
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
        mb.face([p_bl_h, p_bl_t, p_tl_t, p_tl_m], BOOT,        out=(-1, 0, 0))
        mb.face([p_bl_h, p_tl_m, p_tl_h],         BOOT,        out=(-1, 0, 0))
        mb.face([p_br_t, p_br_h, p_tr_m, p_tr_t], BOOT,        out=(1, 0, 0))
        mb.face([p_br_h, p_tr_h, p_tr_m],         BOOT,        out=(1, 0, 0))

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

    # Slot 1: Painted Buffalo-Plaid Flannel Shirt material
    mat_flannel = bpy.data.materials.new("FlannelManShirt")
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
    """24-frame looping Walk cycle: sturdy outdoorsy hiker stride with backpack balance & natural arm swing."""
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

        # Grounded, sturdy stride bounce with slight forward lean to balance the backpack
        pb_root = rig.pose.bones["Root"]
        bob = -0.024 * (1.0 - c2) * 0.5
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (-0.042, -0.068 * s1, 0.036 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Counter-twisting torso carrying the daypack
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.016 * c2, 0.096 * s1, -0.024 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Steady head keeping baseball cap level with gentle step nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.036 + 0.022 * c2, -0.042 * s1, -0.016 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Crisp alternating hiking-boot stride with clean foot lift above ground
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

        # Relaxed opposite-phase arm swing clear of torso & backpack
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.36 * s1, 0.0, 0.022 * c1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.36 * s1, 0.0, 0.022 * c1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: calm bearded hiker weight shift, gentle breathing, looking around."""
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

        # Calm weight sway & subtle breathing bob
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.008 * (1.0 - math.cos(2.0 * phi)) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.006, 0.024 * s1, 0.026 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.020 * s2, 0.032 * s1, -0.020 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Easygoing look side-to-side with gentle nod
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.028 * s2 + 0.014 * c1, 0.26 * s1, 0.042 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Hiking boots planted cleanly on the ground
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Subtle arm sway in rhythm with breathing
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.042 * s1 - 0.018 * s2, 0.0, 0.024 + 0.014 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.042 * s1 - 0.018 * s2, 0.0, -0.024 + 0.014 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build standard 7-bone passenger rig (Root, Torso, Head, Arm_L, Arm_R, Leg_L, Leg_R) with Walk & Idle."""
    arm_data = bpy.data.armatures.new("PersonFlannelManRig")
    rig = bpy.data.objects.new("PersonFlannelManRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",  None,    ( 0.000, 0.576,  0.000),      ( 0.000, 0.676,  0.000)),
        ("Torso", "Root",  ( 0.000, 0.628,  0.000),      ( 0.000, 1.096,  0.000)),
        ("Head",  "Torso", ( 0.000, 1.132,  0.000),      ( 0.000, 1.456,  0.000)),
        ("Arm_L", "Torso", ( 0.178, SHOULDER_Y, SHOULDER_Z), ( 0.178, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Arm_R", "Torso", (-0.178, SHOULDER_Y, SHOULDER_Z), (-0.178, SHOULDER_Y + 0.160, SHOULDER_Z)),
        ("Leg_L", "Root",  ( 0.112, 0.540,  0.000),      ( 0.112, 0.700,  0.000)),
        ("Leg_R", "Root",  (-0.112, 0.540,  0.000),      (-0.112, 0.700,  0.000)),
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
        (-2.25, math.radians(52)),   # Front-3/4 matching reference angle (facing right!)
        (-0.75, math.radians(0)),    # Front (showing face, beard, mustache, cap patch & buffalo plaid)
        ( 0.75, math.radians(90)),   # Right side (showing backpack profile, visor, beard & plaid sleeve)
        ( 2.25, math.radians(180)),  # Back (showing charcoal backpack, grey hair & plaid back)
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

    coll = bpy.data.collections.new("PersonFlannelMan")
    bpy.context.scene.collection.children.link(coll)

    flannel_img = generate_flannel_texture(FLANNEL_TEX_PATH)

    mb = build_person()
    me = bpy.data.meshes.new("PersonFlannelMan")
    mb.bm.to_mesh(me)
    mb.bm.free()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    for mat in setup_materials(flannel_img):
        me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonFlannelMan", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=52)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=48)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=52, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=48, zrot_right_deg=90)

    print("=== PersonFlannelMan Stats ===")
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
