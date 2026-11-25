# Builds an ultra-low-poly (< 350 tris) stylized school kid with a puffy quilted blue jacket,
# brown backpack, and yellow pom-pom beanie in Blender
# (run headless: /Applications/Blender.app/Contents/MacOS/Blender --factory-startup --background --python art/person_kid.py)
# Saves art/person_kid.blend, exports assets/models/person_kid.glb (rigged + Walk & Idle cycles),
# renders art/person_kid_preview.png, art/person_kid_walk_preview.png, art/person_kid_idle_preview.png,
# and outputs rendered videos art/person_kid_walk.mp4 and art/person_kid_idle.mp4.
#
# Strict triangle budget: < 350 triangles.
# Game frame: +Z forward, +Y up, +X left, feet on ground at y = 0, ~1.39 m tall (school kid scale).
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
BLEND_PATH = os.path.join(ROOT, "art", "person_kid.blend")
GLB_PATH = os.path.join(ROOT, "assets", "models", "person_kid.glb")
PREVIEW_PATH = os.path.join(ROOT, "art", "person_kid_preview.png")
WALK_PREVIEW_PATH = os.path.join(ROOT, "art", "person_kid_walk_preview.png")
IDLE_PREVIEW_PATH = os.path.join(ROOT, "art", "person_kid_idle_preview.png")
WALK_VIDEO_PATH = os.path.join(ROOT, "art", "person_kid_walk.mp4")
IDLE_VIDEO_PATH = os.path.join(ROOT, "art", "person_kid_idle.mp4")


def srgb_to_linear(c):
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def col_srgb(r, g, b, a=1.0):
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), a)


# Palette matched closely to reference image (sRGB -> linear)
SKIN           = col_srgb(0.98, 0.74, 0.51)
SKIN_SHADE     = col_srgb(0.89, 0.63, 0.42)
EYE            = col_srgb(0.14, 0.11, 0.10)

HAIR_DARK      = col_srgb(0.28, 0.20, 0.16)
HAIR_MID       = col_srgb(0.35, 0.25, 0.20)

BEANIE         = col_srgb(0.98, 0.82, 0.30)
BEANIE_CUFF    = col_srgb(0.95, 0.77, 0.25)
BEANIE_RIB     = col_srgb(0.89, 0.71, 0.21)
POM_POM        = col_srgb(0.99, 0.85, 0.34)
POM_SHADE      = col_srgb(0.91, 0.74, 0.25)

JACKET         = col_srgb(0.43, 0.58, 0.76)
JACKET_LIGHT   = col_srgb(0.49, 0.64, 0.82)
JACKET_SHADE   = col_srgb(0.35, 0.49, 0.68)
JACKET_HOOD    = col_srgb(0.40, 0.54, 0.72)

PACK           = col_srgb(0.43, 0.31, 0.23)
PACK_SHADE     = col_srgb(0.32, 0.23, 0.17)
PACK_FLAP      = col_srgb(0.72, 0.50, 0.29)
STRAP          = col_srgb(0.30, 0.22, 0.17)

PANTS          = col_srgb(0.28, 0.29, 0.35)
PANTS_SHADE    = col_srgb(0.21, 0.22, 0.27)

BOOT           = col_srgb(0.80, 0.60, 0.37)
BOOT_SHADE     = col_srgb(0.68, 0.49, 0.29)
SOLE           = col_srgb(0.42, 0.29, 0.19)


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

    def loft(self, rings, colors, cap_bottom=False, cap_top=False, bot_color=None, top_color=None, skip_k=()):
        n = len(rings[0])
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            c0 = sum(r0, Vector()) / n
            c1 = sum(r1, Vector()) / n
            cmid = (c0 + c1) * 0.5
            for k in range(n):
                if k in skip_k:
                    continue
                kn = (k + 1) % n
                p0, p1, p2, p3 = r0[k], r0[kn], r1[kn], r1[k]
                col = colors(i, k) if callable(colors) else colors
                mid = (p0 + p1 + p2 + p3) * 0.25
                self.face([p0, p1, p2, p3], col, out=(mid - cmid))
        if cap_bottom:
            r0 = rings[0]
            c0 = sum(r0, Vector()) / n
            c1 = sum(rings[1], Vector()) / n
            out_dir = (c0 - c1).normalized()
            col = bot_color if bot_color is not None else (colors(0, 0) if callable(colors) else colors)
            if n <= 4:
                self.face(r0, col, out=out_dir)
            elif n == 6:
                self.face([r0[0], r0[1], r0[2], r0[3]], col, out=out_dir)
                self.face([r0[3], r0[4], r0[5], r0[0]], col, out=out_dir)
            else:
                for k in range(n):
                    self.face([c0, r0[(k + 1) % n], r0[k]], col, out=out_dir)
        if cap_top:
            rt = rings[-1]
            ct = sum(rt, Vector()) / n
            cp = sum(rings[-2], Vector()) / n
            out_dir = (ct - cp).normalized()
            col = top_color if top_color is not None else (colors(len(rings) - 2, 0) if callable(colors) else colors)
            if n <= 4:
                self.face(rt, col, out=out_dir)
            elif n == 6:
                self.face([rt[0], rt[1], rt[2], rt[3]], col, out=out_dir)
                self.face([rt[3], rt[4], rt[5], rt[0]], col, out=out_dir)
            else:
                for k in range(n):
                    self.face([ct, rt[k], rt[(k + 1) % n]], col, out=out_dir)

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
    # 1. CHIBI KID HEAD (6-sided, 3 rings + chin cap = 28 tris)
    # =========================================================================
    mb.set_part("head", bone="Head")
    # phase = pi/6 -> k=5 is wide flat front face (+Z), k=0 (+X) & k=4 (-X) are cheeks,
    # k=1,2,3 are back/sides (dark brown hair wrapping behind ears & nape)
    head_specs = [
        # (y,     cz,     rx,    rz)
        (0.838,  0.014, 0.162, 0.152),  # 0: cute rounded chin/jaw
        (0.908,  0.018, 0.214, 0.200),  # 1: full chibi cheeks
        (1.095,  0.014, 0.212, 0.198),  # 2: brow / tucked into hair & beanie
    ]
    head_rings = [oval_ring(0.0, y, cz, rx, rz, n=6, phase=math.pi / 6.0)
                  for (y, cz, rx, rz) in head_specs]

    def head_color(i, k):
        return SKIN if k in (4, 5, 0) else HAIR_DARK

    mb.loft(head_rings, head_color, cap_bottom=True, cap_top=False, bot_color=SKIN_SHADE)

    # =========================================================================
    # 2. EYES (2 crisp vertical dark pill hexagons on flat front face = 8 tris)
    # =========================================================================
    mb.set_part("eyes", bone="Head")
    # Flat front face z ≈ 0.018 + 0.866025 * 0.200 = 0.1912
    z_eye = 0.194
    for side in (-1, 1):
        cx = side * 0.060
        cy = 0.966
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
    # 3. EARS (2 cute rounded low-poly tabs = 12 tris)
    # =========================================================================
    mb.set_part("ears", bone="Head")
    for side in (-1, 1):
        x_in = side * 0.196
        x_out = side * 0.236
        y0, y1 = 0.908, 0.990
        z0, z1 = -0.012, 0.052
        zm = 0.5 * (z0 + z1)
        p_ob = V(x_out, y0 + 0.016, zm)
        p_ot = V(x_out, y1 - 0.016, zm)
        mb.face([V(x_in, y0, z1), V(x_in, y1, z1), p_ot, p_ob], SKIN,       out=(0, 0, 1))
        mb.face([V(x_in, y1, z0), V(x_in, y0, z0), p_ob, p_ot], SKIN_SHADE, out=(0, 0, -1))
        mb.face([V(x_in, y0, z0), V(x_in, y0, z1), p_ob],       SKIN_SHADE, out=(0, -1, 0))
        mb.face([V(x_in, y1, z1), V(x_in, y1, z0), p_ot],       SKIN,       out=(0, 1, 0))

    # =========================================================================
    # 4. DARK BROWN FOREHEAD BANGS (snug sculpted hairline under beanie = 10 tris)
    # =========================================================================
    mb.set_part("hair", bone="Head")
    # Snug 3-panel wavy bangs tucked cleanly beneath the tilted yellow beanie cuff!
    bx      = [-0.208, -0.106,  0.106,  0.208]
    by_top  = [ 1.024,  1.096,  1.096,  1.024]
    by_bot  = [ 0.978,  1.048,  1.048,  0.978]
    bz_top  = [ 0.032,  0.190,  0.190,  0.032]
    bz_bot  = [ 0.036,  0.198,  0.198,  0.036]
    for i in range(3):
        p_tl = V(bx[i],     by_top[i], bz_top[i])
        p_tr = V(bx[i + 1], by_top[i + 1], bz_top[i + 1])
        p_br = V(bx[i + 1], by_bot[i + 1], bz_bot[i + 1])
        p_bl = V(bx[i],     by_bot[i], bz_bot[i])
        mid_x = 0.5 * (bx[i] + bx[i + 1])
        out_v = V(mid_x * 2.5, 0.10, 0.95)
        col = HAIR_MID if i == 1 else HAIR_DARK
        mb.face([p_bl, p_br, p_tr, p_tl], col, out=out_v)
    # Subtle soft scalloped tuft dipping gently in the center forehead + underside bevel (4 tris)
    mb.face([
        V(-0.052, 1.048, 0.199),
        V( 0.052, 1.048, 0.199),
        V( 0.008, 1.025, 0.197),
    ], HAIR_MID, out=(0, 0, 1))
    mb.face([
        V(-0.106, 1.048, 0.184),
        V( 0.106, 1.048, 0.184),
        V( 0.106, 1.048, 0.198),
        V(-0.106, 1.048, 0.198),
    ], HAIR_DARK, out=(0, -1, 0))
    mb.face([
        V(-0.052, 1.048, 0.186),
        V( 0.008, 1.025, 0.197),
        V( 0.052, 1.048, 0.186),
    ], HAIR_DARK, out=(0, -1, 0))

    # =========================================================================
    # 5. YELLOW KNIT BEANIE WITH FOLDED CUFF + FLUFFY ROUND POM-POM (28 + 23 = 51 tris)
    # =========================================================================
    mb.set_part("beanie", bone="Head")
    tilt = math.radians(23.0)
    up_b = V(0.0, math.cos(tilt), -math.sin(tilt))
    c_base = V(0.0, 1.018, -0.010)
    c_ctop = c_base + up_b * 0.092
    c_dome = c_base + up_b * 0.230

    cuff_bot   = tilted_ring(c_base.x, c_base.y, c_base.z, 0.242, 0.236, tilt)
    cuff_top   = tilted_ring(c_ctop.x, c_ctop.y, c_ctop.z, 0.248, 0.242, tilt)
    dome_crown = tilted_ring(c_dome.x, c_dome.y, c_dome.z, 0.146, 0.142, tilt)

    # Folded ribbed yellow knit cuff (12 tris)
    mb.loft([cuff_bot, cuff_top], lambda i, k: BEANIE_CUFF if k % 2 == 0 else BEANIE_RIB,
            cap_bottom=False, cap_top=False)
    # Rounded sunny yellow dome + flat cap (16 tris)
    mb.loft([cuff_top, dome_crown], BEANIE, cap_bottom=False, cap_top=True, top_color=BEANIE)

    # Chunky round 5-sided fluffy yellow pom-pom perched on the tilted crown (zero spike! = 23 tris)
    mb.set_part("pom_pom", bone="Head")
    c_pbot = c_base + up_b * 0.224
    c_pmid = c_base + up_b * 0.286
    c_ptop = c_base + up_b * 0.348
    pom_bot = tilted_ring(c_pbot.x, c_pbot.y, c_pbot.z, 0.056, 0.056, tilt, n=5, phase=0.0)
    pom_mid = tilted_ring(c_pmid.x, c_pmid.y, c_pmid.z, 0.096, 0.096, tilt, n=5, phase=0.0)
    pom_top = tilted_ring(c_ptop.x, c_ptop.y, c_ptop.z, 0.058, 0.058, tilt, n=5, phase=0.0)
    mb.loft([pom_bot, pom_mid], lambda i, k: POM_SHADE if k % 2 == 1 else BEANIE,
            cap_bottom=False, cap_top=False)
    mb.loft([pom_mid, pom_top], lambda i, k: POM_POM if k % 2 == 0 else BEANIE,
            cap_bottom=False, cap_top=False)
    # Flat pentagonal top cap (1 quad + 1 tri = 3 tris -> chunky round silhouette!)
    mb.face([pom_top[0], pom_top[1], pom_top[2], pom_top[3]], POM_POM, out=up_b)
    mb.face([pom_top[0], pom_top[3], pom_top[4]], POM_POM, out=up_b)

    # =========================================================================
    # 6. NECK (short warm-peach front prism, rear hidden by hood = 4 tris)
    # =========================================================================
    mb.set_part("neck", bone="Head")
    n_pts_b = [V(-0.072, 0.775, -0.040), V(0.000, 0.775, 0.072), V(0.072, 0.775, -0.040)]
    n_pts_t = [V(-0.068, 0.855, -0.036), V(0.000, 0.855, 0.068), V(0.068, 0.855, -0.036)]
    mb.face([n_pts_b[0], n_pts_b[1], n_pts_t[1], n_pts_t[0]], SKIN_SHADE, out=(-0.7, 0, 0.7))
    mb.face([n_pts_b[1], n_pts_b[2], n_pts_t[2], n_pts_t[1]], SKIN_SHADE, out=( 0.7, 0, 0.7))

    # =========================================================================
    # 7. BLUE PUFFY QUILTED JACKET TORSO (3 pillowy horizontal baffles = 52 tris)
    # =========================================================================
    mb.set_part("jacket", bone="Torso")
    # Soft pillowy 3-tier quilted profile: gentle ~1.8 cm seam tucks so baffles read cozy & plump, not spiky!
    puffer_specs = [
        # (y,     rx,    zf,     zb)
        (0.432, 0.196, 0.148, -0.136),  # 0: tucked bottom hem
        (0.494, 0.218, 0.168, -0.154),  # 1: baffle 1 (bottom) plump peak
        (0.554, 0.203, 0.153, -0.141),  # 2: stitch crease 1
        (0.616, 0.222, 0.172, -0.157),  # 3: baffle 2 (middle) plump peak
        (0.678, 0.202, 0.152, -0.139),  # 4: stitch crease 2
        (0.738, 0.216, 0.165, -0.149),  # 5: baffle 3 (upper chest) plump peak
        (0.796, 0.178, 0.120, -0.116),  # 6: collar/shoulder top
    ]
    puffer_rings = []
    for (y, rx, zf, zb) in puffer_specs:
        puffer_rings.append([
            V(-rx, y, zf),
            V( rx, y, zf),
            V( rx, y, zb),
            V(-rx, y, zb),
        ])

    def puffer_col(i, k):
        # Keep the quilted baffles a unified cozy cornflower blue so 3D faceted lighting
        # creates natural soft pillowy shading (rather than painted dark horizontal stripes!)
        return JACKET

    mb.loft(puffer_rings, puffer_col, cap_bottom=True, cap_top=True,
            bot_color=JACKET_SHADE, top_color=JACKET_LIGHT)

    # =========================================================================
    # 8. PUFFY JACKET HOOD RESTING BEHIND COLLAR (10 tris)
    # =========================================================================
    mb.set_part("hood", bone="Torso")
    hd_bot = [
        V(-0.146, 0.778,  0.072),
        V( 0.146, 0.778,  0.072),
        V( 0.178, 0.768, -0.228),
        V(-0.178, 0.768, -0.228),
    ]
    hd_top = [
        V(-0.114, 0.848,  0.052),
        V( 0.114, 0.848,  0.052),
        V( 0.152, 0.875, -0.198),
        V(-0.152, 0.875, -0.198),
    ]
    mb.loft([hd_bot, hd_top], lambda i, k: JACKET_SHADE if k == 0 else JACKET_HOOD,
            cap_bottom=False, cap_top=True, top_color=JACKET_LIGHT)

    # =========================================================================
    # 9. PUFFY QUILTED SLEEVES (2 pillowy segments per arm = 52 tris)
    # =========================================================================
    mb.set_part("sleeves")
    # Cozy, plump 2-baffle puffy sleeves tucked neatly against the shoulders
    arm_specs = [
        ( 1, "Arm_L", V( 0.168, 0.742,  0.008), V( 0.260, 0.608,  0.014), V( 0.278, 0.486,  0.052)),
        (-1, "Arm_R", V(-0.168, 0.742,  0.008), V(-0.260, 0.608,  0.014), V(-0.278, 0.486,  0.052)),
    ]

    for (side, bname, p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        p0 = p_sh
        p1 = p_sh.lerp(p_el, 0.52)
        p2 = p_el
        p3 = p_el.lerp(p_wr, 0.54)
        p4 = p_wr
        pts_arm = [p0, p1, p2, p3, p4]
        # Soft plump quilted puff radii (cozy pillowy look, zero jagged spikes!)
        rads = [
            (0.070, 0.074),  # 0: shoulder tucked into torso
            (0.092, 0.096),  # 1: upper arm puff peak
            (0.078, 0.082),  # 2: elbow quilted stitch pinch
            (0.092, 0.096),  # 3: forearm puff peak
            (0.068, 0.072),  # 4: snug wrist cuff
        ]
        ax_up = (p2 - p0).normalized()
        ax_lo = (p4 - p2).normalized()

        rings = []
        for idx in range(5):
            ax = ax_up if idx < 2 else (ax_lo if idx > 2 else (ax_up + ax_lo).normalized())
            out_x = V(side, 0.0, 0.0)
            u = (out_x - ax * out_x.dot(ax)).normalized()
            fwd = V(0.0, 0.0, 1.0)
            v = fwd - ax * fwd.dot(ax)
            v = (v - u * v.dot(u)).normalized()
            ru, rv = rads[idx]
            c = pts_arm[idx]
            rings.append([
                c - u * ru + v * rv,  # 0: front-in
                c + u * ru + v * rv,  # 1: front-out
                c + u * ru - v * rv,  # 2: back-out
                c - u * ru - v * rv,  # 3: back-in
            ])

        # Build front (0->1), outer (1->2), back (2->3) across all 4 bands (24 tris/arm)
        # + 1 clean inner armpit face (2 tris/arm) = 26 tris/arm -> 52 tris total!
        for b in range(4):
            r0, r1 = rings[b], rings[b + 1]
            c0 = sum(r0, Vector()) * 0.25
            c1 = sum(r1, Vector()) * 0.25
            cmid = (c0 + c1) * 0.5
            for k in (0, 1, 2):
                kn = k + 1
                p_a, p_b, p_c, p_d = r0[k], r0[kn], r1[kn], r1[k]
                mid = (p_a + p_b + p_c + p_d) * 0.25
                mb.face([p_a, p_b, p_c, p_d], JACKET, out=(mid - cmid))
        mb.face([rings[0][3], rings[0][0], rings[4][0], rings[4][3]], JACKET_SHADE, out=(-side, 0, 0))

    # =========================================================================
    # 10. CHUNKY PEACH KID HANDS (2 x 10 tris = 20 tris)
    # =========================================================================
    mb.set_part("hands")
    for (side, bname, _p_sh, p_el, p_wr) in arm_specs:
        mb.set_bone(bname)
        ax = (p_wr - p_el).normalized()
        out_x = V(side, 0.0, 0.0)
        u = (out_x - ax * out_x.dot(ax)).normalized()
        fwd = V(0.0, 0.0, 1.0)
        v = fwd - ax * fwd.dot(ax)
        v = (v - u * v.dot(u)).normalized()

        c0 = p_wr - ax * 0.008
        c1 = p_wr + ax * 0.094
        r0 = [
            c0 - u * 0.050 + v * 0.054,
            c0 + u * 0.050 + v * 0.054,
            c0 + u * 0.050 - v * 0.054,
            c0 - u * 0.050 - v * 0.054,
        ]
        r1 = [
            c1 - u * 0.040 + v * 0.044,
            c1 + u * 0.040 + v * 0.044,
            c1 + u * 0.040 - v * 0.044,
            c1 - u * 0.040 - v * 0.044,
        ]
        mb.loft([r0, r1], SKIN, cap_bottom=False, cap_top=True, top_color=SKIN_SHADE)

    # =========================================================================
    # 11. BROWN SCHOOL BACKPACK + CARAMEL POCKET FLAP + STRAPS (16 + 8 + 8 = 32 tris)
    # =========================================================================
    mb.set_part("backpack", bone="Backpack")
    # Rounded warm chestnut-brown school backpack tucked snugly on puffy jacket back
    bp_specs = [
        # (y,     rx,    z_in,   z_out)
        (0.435, 0.160, -0.148, -0.305),  # sturdy full lower base
        (0.605, 0.178, -0.152, -0.335),  # plump rounded mid belly
        (0.755, 0.136, -0.132, -0.238),  # soft tapered top dome
    ]
    bp_rings = []
    for (y, rx, zin, zout) in bp_specs:
        bp_rings.append([
            V(-rx, y, zin),
            V( rx, y, zin),
            V( rx, y, zout),
            V(-rx, y, zout),
        ])
    mb.loft(bp_rings, lambda i, k: PACK_SHADE if i == 0 else PACK,
            cap_bottom=True, cap_top=True, bot_color=PACK_SHADE, top_color=PACK, skip_k=(0,))

    # Caramel-tan rear pocket/flap pouch (distinctive warm highlight seen in reference = 8 tris)
    # 4-face outward wedge (skip inner face against pack + bottom flush into lower pack curve)
    mb.box(
        -0.115, 0.115,
        0.485, 0.625,
        -0.372, -0.312,
        {"back": PACK_FLAP, "top": PACK_FLAP, "left": PACK_SHADE, "right": PACK_SHADE},
        skip=("front", "bottom"),
    )

    # Dark brown shoulder straps curving cleanly over the puffy shoulders & upper baffles (12 tris, Torso bone!)
    mb.set_part("straps", bone="Torso")
    for side in (-1, 1):
        # Straps wrap snugly over the outer shoulder seam & curve outward toward the underarm (zero baffle clipping!)
        xa_t, xb_t = sorted((side * 0.118, side * 0.168))
        xa_m, xb_m = sorted((side * 0.144, side * 0.194))
        xa_b, xb_b = sorted((side * 0.162, side * 0.212))
        # 1. Shoulder top strap quad
        mb.face([
            V(xa_t, 0.802, -0.125),
            V(xb_t, 0.802, -0.125),
            V(xb_t, 0.802,  0.128),
            V(xa_t, 0.802,  0.128),
        ], STRAP, out=(0, 1, 0))
        # 2. Upper front chest strap hugging smoothly over upper baffle peak (z = 0.172)
        mb.face([
            V(xa_m, 0.728, 0.174),
            V(xb_m, 0.728, 0.174),
            V(xb_t, 0.802, 0.128),
            V(xa_t, 0.802, 0.128),
        ], STRAP, out=(0, 0.35, 0.94))
        # 3. Mid front strap curving cleanly over middle baffle peak (z = 0.180) toward underarm
        mb.face([
            V(xa_b, 0.578, 0.180),
            V(xb_b, 0.578, 0.180),
            V(xb_m, 0.728, 0.174),
            V(xa_m, 0.728, 0.174),
        ], STRAP, out=(0, 0, 1))

    # =========================================================================
    # 12. DARK SLATE-NAVY BAGGY KID PANTS (8 + 20 = 28 tris)
    # =========================================================================
    mb.set_part("pants", bone="Root")
    mb.box(-0.182, 0.182, 0.352, 0.455, -0.110, 0.110, PANTS, skip=("top", "bottom"))

    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        x_in_t, x_out_t = side * 0.008, side * 0.180
        x_in_b, x_out_b = side * 0.058, side * 0.228
        rz_t, rz_b = 0.098, 0.100
        r_top = [
            V(min(x_in_t, x_out_t), 0.388,  rz_t),
            V(max(x_in_t, x_out_t), 0.388,  rz_t),
            V(max(x_in_t, x_out_t), 0.388, -rz_t),
            V(min(x_in_t, x_out_t), 0.388, -rz_t),
        ]
        r_bot = [
            V(min(x_in_b, x_out_b), 0.168,  rz_b),
            V(max(x_in_b, x_out_b), 0.168,  rz_b),
            V(max(x_in_b, x_out_b), 0.168, -rz_b),
            V(min(x_in_b, x_out_b), 0.168, -rz_b),
        ]
        mb.loft([r_bot, r_top], PANTS, cap_bottom=True, cap_top=False, bot_color=PANTS_SHADE)

    # =========================================================================
    # 13. CHUNKY TAN/CAMEL ANKLE BOOTS WITH DARK SOLES (18 tris x 2 = 36 tris)
    # =========================================================================
    mb.set_part("boots")
    for side in (-1, 1):
        mb.set_bone("Leg_L" if side > 0 else "Leg_R")
        cx = side * 0.142
        w = 0.072
        w_toe = 0.060
        z_heel = -0.092
        z_toe  =  0.168
        y_sole0 = 0.000
        y_sole1 = 0.036
        y_col   = 0.180

        # Layer 1: Sturdy dark chocolate outsole (10 tris)
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

        # Layer 2: Warm camel-tan leather boot upper rising cleanly into pant hem (8 tris)
        boot_top = [
            V(cx - w * 0.86, y_col, z_heel + 0.016),
            V(cx + w * 0.86, y_col, z_heel + 0.016),
            V(cx + w * 0.86, y_col, 0.056),
            V(cx - w * 0.86, y_col, 0.056),
        ]
        mb.loft([sole_top, boot_top], lambda i, k: BOOT_SHADE if k == 2 else BOOT,
                cap_bottom=False, cap_top=False)

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
    """24-frame looping Walk cycle: bouncy cheerful school-kid stride, jaunty arm swing & lively backpack bob."""
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

        # Bouncy cheerful kid walk & slight forward lean balancing backpack
        pb_root = rig.pose.bones["Root"]
        bob = -0.026 * (1.0 - c2) * 0.5
        root_pitch = -0.062
        pb_root.location = (0.0, bob, 0.0)
        pb_root.rotation_euler = (root_pitch, -0.075 * s1, 0.042 * c1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Playful torso counter-twist
        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.024 * c2, 0.105 * s1, -0.028 * c1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Jaunty head bob so the yellow pom-pom bounces happily!
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.052 + 0.048 * s2, -0.045 * s1, 0.026 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Brisk kid stride with energetic boot lift on swing phase
        pb_leg_l = rig.pose.bones["Leg_L"]
        pb_leg_l.rotation_euler = (-0.50 * s1, 0.0, 0.0)
        pb_leg_l.location = (0.0, max(0.0, c1) * 0.040, 0.0)
        pb_leg_l.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_l.keyframe_insert(data_path="location", frame=frame)

        pb_leg_r = rig.pose.bones["Leg_R"]
        pb_leg_r.rotation_euler = (0.50 * s1, 0.0, 0.0)
        pb_leg_r.location = (0.0, max(0.0, -c1) * 0.040, 0.0)
        pb_leg_r.keyframe_insert(data_path="rotation_euler", frame=frame)
        pb_leg_r.keyframe_insert(data_path="location", frame=frame)

        # Enthusiastic counter-swinging puffy arms (flared slightly outward to clear puffer & backpack)
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.38 * s1 - 0.04, 0.0, 0.068)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.38 * s1 - 0.04, 0.0, -0.068)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # School backpack bounces cheerfully with a small phase lag behind steps
        pb_pack = rig.pose.bones["Backpack"]
        pb_pack.location = (0.0, 0.009 * math.sin(2.0 * phi - 0.60), 0.0)
        pb_pack.rotation_euler = (0.032 * math.sin(2.0 * phi - 0.60), 0.0, -0.036 * math.sin(phi - 0.45))
        pb_pack.keyframe_insert(data_path="location", frame=frame)
        pb_pack.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def _create_idle_action(rig, scene):
    """48-frame looping Idle cycle: curious kid waiting at the pier, playful look-around & gentle bounce."""
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

        # Gentle fidgety kid weight shift & soft breathing
        pb_root = rig.pose.bones["Root"]
        pb_root.location = (0.0, -0.009 * (1.0 - c1) * 0.5, 0.0)
        pb_root.rotation_euler = (-0.014, 0.032 * s1, 0.026 * s1)
        pb_root.keyframe_insert(data_path="location", frame=frame)
        pb_root.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_torso = rig.pose.bones["Torso"]
        pb_torso.rotation_euler = (-0.026 * s2, 0.036 * s1, -0.020 * s1)
        pb_torso.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Curious kid look-around & cute inquisitive head tilt
        pb_head = rig.pose.bones["Head"]
        pb_head.rotation_euler = (0.068 * s2, 0.25 * s1, 0.055 * c1)
        pb_head.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Little boots planted squarely on ground
        for bname in ("Leg_L", "Leg_R"):
            pb = rig.pose.bones[bname]
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Relaxed puffy arms gently swinging with idle sway
        pb_arm_l = rig.pose.bones["Arm_L"]
        pb_arm_l.rotation_euler = (0.062 * s1 - 0.018 * s2, 0.0, 0.030 + 0.020 * s1)
        pb_arm_l.keyframe_insert(data_path="rotation_euler", frame=frame)

        pb_arm_r = rig.pose.bones["Arm_R"]
        pb_arm_r.rotation_euler = (-0.058 * s1 - 0.018 * s2, 0.0, -0.030 - 0.020 * s1)
        pb_arm_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Backpack settles softly with breathing
        pb_pack = rig.pose.bones["Backpack"]
        pb_pack.location = (0.0, 0.004 * s2, 0.0)
        pb_pack.rotation_euler = (0.018 * s2, 0.0, -0.018 * s1)
        pb_pack.keyframe_insert(data_path="location", frame=frame)
        pb_pack.keyframe_insert(data_path="rotation_euler", frame=frame)

    return action


def build_rig_and_animations(ob, mb, coll):
    """Build an 8-bone rig (7 standard passenger bones + Backpack) with Walk & Idle cycles."""
    arm_data = bpy.data.armatures.new("PersonKidRig")
    rig = bpy.data.objects.new("PersonKidRig", arm_data)
    coll.objects.link(rig)

    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")

    bone_defs = [
        ("Root",     None,    ( 0.000, 0.405,  0.000), ( 0.000, 0.495,  0.000)),
        ("Torso",    "Root",  ( 0.000, 0.450,  0.000), ( 0.000, 0.785,  0.000)),
        ("Head",     "Torso", ( 0.000, 0.815,  0.000), ( 0.000, 1.120,  0.000)),
        ("Arm_L",    "Torso", ( 0.168, 0.742,  0.008), ( 0.168, 0.892,  0.008)),
        ("Arm_R",    "Torso", (-0.168, 0.742,  0.008), (-0.168, 0.892,  0.008)),
        ("Backpack", "Torso", ( 0.000, 0.620, -0.175), ( 0.000, 0.750, -0.220)),
        ("Leg_L",    "Root",  ( 0.105, 0.375,  0.000), ( 0.105, 0.515,  0.000)),
        ("Leg_R",    "Root",  (-0.105, 0.375,  0.000), (-0.105, 0.515,  0.000)),
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
        (-1.56, math.radians(58)),   # Front-3/4 matching reference angle (facing right)
        (-0.52, math.radians(0)),    # Front
        ( 0.52, math.radians(90)),   # Side (showing puffy sleeves, backpack, beanie & pom-pom)
        ( 1.56, math.radians(180)),  # Back
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
    cam_data.ortho_scale = 4.25
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 0.96)
    direction = Vector((0.0, 0.0, 0.69)) - cam_obj.location
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
        xpos = (idx - (len(frames) - 1) * 0.5) * 1.05
        snap_obj.location = (xpos, 0.0, 0.0)
        snap_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_deg))
        scene.collection.objects.link(snap_obj)
        snapshots.append((snap_obj, snap_mesh))

    cam_data = bpy.data.cameras.new("StripCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 6.4
    cam_obj = bpy.data.objects.new("StripCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -6.0, 0.95)
    direction = Vector((0.0, 0.0, 0.69)) - cam_obj.location
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


def render_anim_video(rig, obj, action, cycle_len, loops, out_path, zrot_left_deg=54, zrot_right_deg=90):
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
    cam_data.ortho_scale = 2.55
    cam_obj = bpy.data.objects.new("VidCam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -5.0, 0.94)
    direction = Vector((0.0, 0.0, 0.69)) - cam_obj.location
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
            left_obj.location = (-0.58, 0.0, 0.0)
            left_obj.rotation_euler = (0.0, 0.0, math.radians(zrot_left_deg))
            scene.collection.objects.link(left_obj)

            right_obj = bpy.data.objects.new(f"VidR_{f}", snap_mesh)
            right_obj.location = (0.58, 0.0, 0.0)
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
    "hair": [HAIR_DARK, HAIR_MID],
    "top": [JACKET, JACKET_LIGHT, JACKET_SHADE, JACKET_HOOD],
    "bottom": [PANTS, PANTS_SHADE],
    "accent": [BEANIE, BEANIE_CUFF, BEANIE_RIB, POM_POM, POM_SHADE],
}


def main():
    extra_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    stills_only = "--stills-only" in extra_args

    bpy.ops.wm.read_homefile(use_empty=True)

    coll = bpy.data.collections.new("PersonKid")
    bpy.context.scene.collection.children.link(coll)

    mb = build_person()
    me = bpy.data.meshes.new("PersonKid")
    mb.bm.to_mesh(me)
    mb.bm.free()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import person_recolor
    person_recolor.tag_parts(me, RECOLOR_GROUPS)

    mat = setup_material()
    me.materials.append(mat)
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.render_color_index = 0

    ob = bpy.data.objects.new("PersonKid", me)
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

    render_anim_strip(rig, ob, walk_action, [1, 5, 9, 13, 17, 21], WALK_PREVIEW_PATH, zrot_deg=58)
    render_anim_strip(rig, ob, idle_action, [1, 9, 17, 25, 33, 41], IDLE_PREVIEW_PATH, zrot_deg=42)
    if not stills_only:
        render_anim_video(rig, ob, walk_action, cycle_len=24, loops=4, out_path=WALK_VIDEO_PATH, zrot_left_deg=54, zrot_right_deg=90)
        render_anim_video(rig, ob, idle_action, cycle_len=48, loops=2, out_path=IDLE_VIDEO_PATH, zrot_left_deg=42, zrot_right_deg=90)

    print("=== PersonKid Stats ===")
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
