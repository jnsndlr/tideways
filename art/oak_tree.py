"""Build a 3-level LOD stylized low-poly oak tree lineup in Blender.

Styled to match art/pine_tree.py: crisp flat-shaded facets, chiseled volumetric
foliage cushions with angular lobed rims, broad faceted crown planes and dark
tucked undersides, fluted gnarled oak bark with root buttresses, and harmonious
per-vertex colour gradients.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P art/oak_tree.py

Outputs:
    art/oak_tree.blend              Blender source with oak_tree, oak_tree_mid, oak_tree_lod side-by-side
    art/oak_tree_preview.png        4-angle side-by-side Cycles lineup (Hero | Mid | LOD)
    assets/models/oak_tree.glb      LOD0 Hero (~2,100 tris, +Y up, flat-shaded, vertex colours)
    assets/models/oak_tree_mid.glb  LOD1 Mid  (~680 tris,   +Y up, flat-shaded, vertex colours)
    assets/models/oak_tree_lod.glb  LOD2 Low  (~305 tris,   +Y up, flat-shaded, vertex colours)
"""
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"
OUT_BLEND = ART / "oak_tree.blend"
OUT_PREVIEW = ART / "oak_tree_preview.png"
OUT_GLB_HERO = ROOT / "assets" / "models" / "oak_tree.glb"
OUT_GLB_MID = ROOT / "assets" / "models" / "oak_tree_mid.glb"
OUT_GLB_LOD = ROOT / "assets" / "models" / "oak_tree_lod.glb"

UP = Vector((0.0, 0.0, 1.0))

# Palette in sRGB (converted to linear when written to vertex colours).
# Harmonized with pine_tree.py: deep cool teal-emerald shadows, rich verdant lower
# foliage, vibrant olive-lime shoulders, warm sunlit chartreuse crown tops, and
# warm golden-chestnut oak bark.
COL_LOW = (0.26, 0.54, 0.20)
COL_MID = (0.48, 0.68, 0.14)
COL_HIGH = (0.70, 0.80, 0.13)
COL_TIP_TOP = (0.87, 0.88, 0.14)
COL_TIP_WARM = (0.92, 0.89, 0.15)
COL_DEEP_SHADOW = (0.06, 0.24, 0.19)
COL_UNDER_PAD = (0.14, 0.40, 0.21)

COL_BARK = (0.52, 0.35, 0.19)
COL_BARK_DARK = (0.25, 0.15, 0.08)
COL_BARK_WARM = (0.68, 0.47, 0.25)

CANOPY_Z_MIN = 2.40
CANOPY_Z_MAX = 6.45


def lerp3(a, b, t):
    t = max(0.0, min(1.0, t))
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def scale3(c, s):
    return (
        min(1.0, max(0.0, c[0] * s)),
        min(1.0, max(0.0, c[1] * s)),
        min(1.0, max(0.0, c[2] * s)),
    )


def smoothstep(e0, e1, x):
    if e1 == e0:
        return 0.0
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def srgb_to_lin(c):
    return tuple(
        x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
        for x in c
    )


def canopy_color(u):
    """Base sRGB foliage colour by normalized canopy height u in [0, 1]."""
    u = max(0.0, min(1.0, u))
    if u < 0.40:
        return lerp3(COL_LOW, COL_MID, u / 0.40)
    if u < 0.76:
        return lerp3(COL_MID, COL_HIGH, (u - 0.40) / 0.36)
    return lerp3(COL_HIGH, COL_TIP_TOP, (u - 0.76) / 0.24)


def trunk_center(z):
    """Subtle organic oak trunk curve from flared roots to primary crown fork."""
    t = max(0.0, min(1.0, z / 2.15))
    x = 0.17 * math.sin(t * math.pi * 0.80) - 0.04 * (t ** 2)
    y = 0.07 * math.sin(t * math.pi * 1.10)
    return Vector((x, y, z))


def ortho_frame(up_vec, ref_dir=None):
    """Return orthonormal (e1, e2, up_n) with e1 aligned near ref_dir when given."""
    up_n = up_vec.normalized()
    if ref_dir is not None:
        proj = ref_dir - up_n * ref_dir.dot(up_n)
        if proj.length > 1e-4:
            e1 = proj.normalized()
            e2 = up_n.cross(e1).normalized()
            return e1, e2, up_n
    ref = Vector((1.0, 0.0, 0.0)) if abs(up_n.x) < 0.85 else Vector((0.0, 1.0, 0.0))
    e1 = up_n.cross(ref).normalized()
    e2 = up_n.cross(e1).normalized()
    return e1, e2, up_n


# Shared sturdy oak limb skeleton (asymmetric fork heights for natural oak posture).
PRIMARY_LIMBS = [
    # 0: Broad right-front sweeping bough (signature low spreading oak arm)
    dict(
        start_z=1.60,
        elbow=Vector((1.02, -0.32, 2.14)),
        end=Vector((1.84, -0.56, 2.78)),
        r0=0.260,
        r1=0.178,
        r2=0.102,
        forks=[
            (Vector((1.28, -1.16, 3.22)), 0.118, 0.056),
            (Vector((2.04, 0.26, 3.10)), 0.108, 0.052),
        ],
    ),
    # 1: Left-front strong bough (forking noticeably higher than right bough for asymmetry)
    dict(
        start_z=1.84,
        elbow=Vector((-0.82, -0.52, 2.48)),
        end=Vector((-1.58, -0.94, 3.16)),
        r0=0.245,
        r1=0.168,
        r2=0.096,
        forks=[
            (Vector((-1.78, -0.02, 3.44)), 0.112, 0.052),
            (Vector((-0.86, -1.44, 3.48)), 0.100, 0.048),
        ],
    ),
    # 2: Back-right ascending shoulder bough
    dict(
        start_z=1.90,
        elbow=Vector((0.72, 0.74, 2.58)),
        end=Vector((1.46, 1.38, 3.38)),
        r0=0.235,
        r1=0.155,
        r2=0.088,
        forks=[
            (Vector((0.68, 1.66, 3.74)), 0.102, 0.048),
            (Vector((1.78, 0.80, 3.28)), 0.096, 0.045),
        ],
    ),
    # 3: Back-left sweeping bough
    dict(
        start_z=1.74,
        elbow=Vector((-0.86, 0.64, 2.34)),
        end=Vector((-1.56, 1.16, 3.02)),
        r0=0.240,
        r1=0.160,
        r2=0.092,
        forks=[
            (Vector((-1.14, 1.68, 3.56)), 0.104, 0.048),
        ],
    ),
    # 4: Front-ascending inner bough
    dict(
        start_z=1.96,
        elbow=Vector((0.12, -0.64, 2.74)),
        end=Vector((0.22, -1.28, 3.54)),
        r0=0.205,
        r1=0.138,
        r2=0.078,
        forks=[
            (Vector((-0.34, -1.16, 3.92)), 0.092, 0.044),
        ],
    ),
]


# Broad-shouldered, picturesquely asymmetric billowing oak canopy layout (13 macro regions).
# - Sweeping low right bough balances a higher, stately left-leaning upper crown crest
# - Expanded Y depth (~5.5m) for rich 360-degree volume from side and elevated angles
# - Hero uses bold, clean overlapping sub-billows (not tiny pebbles) to match pine_tree's graphic planes
CANOPY_CLUSTERS = [
    # --- Tier 1: Lower spreading bough billows (asymmetric undulating skirt) ---
    dict(
        name="low_right_front",
        center=Vector((1.88, -0.54, 3.00)),
        rx=1.28,
        ry=1.14,
        h_top=0.82,
        h_rim=0.26,
        h_under=0.28,
        tilt=Vector((0.26, -0.08, 1.0)),
        az=-0.26,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((-0.36, -0.58, 0.28)), 0.92, 0.84, 0.62, 0.21, Vector((0.14, -0.26, 1.0)), 0.42),
            (Vector((0.36, 0.46, 0.20)), 0.94, 0.82, 0.60, 0.20, Vector((0.30, 0.12, 1.0)), -0.70),
        ],
    ),
    dict(
        name="low_left_front",
        center=Vector((-1.68, -0.88, 3.38)),
        rx=1.22,
        ry=1.12,
        h_top=0.80,
        h_rim=0.25,
        h_under=0.28,
        tilt=Vector((-0.24, -0.14, 1.0)),
        az=2.62,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((-0.24, 0.60, 0.24)), 0.92, 0.84, 0.60, 0.20, Vector((-0.26, 0.08, 1.0)), 1.25),
            (Vector((0.46, -0.44, 0.20)), 0.88, 0.80, 0.56, 0.19, Vector((-0.08, -0.26, 1.0)), -1.10),
        ],
    ),
    dict(
        name="low_back_right",
        center=Vector((1.58, 1.26, 3.46)),
        rx=1.22,
        ry=1.12,
        h_top=0.80,
        h_rim=0.25,
        h_under=0.28,
        tilt=Vector((0.22, 0.18, 1.0)),
        az=0.64,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((0.42, -0.36, -0.08)), 0.88, 0.80, 0.58, 0.20, Vector((0.30, 0.02, 1.0)), 0.12),
            (Vector((-0.42, 0.46, 0.28)), 0.90, 0.82, 0.60, 0.20, Vector((0.08, 0.26, 1.0)), 1.45),
        ],
    ),
    dict(
        name="low_back_left",
        center=Vector((-1.64, 1.18, 3.24)),
        rx=1.24,
        ry=1.12,
        h_top=0.82,
        h_rim=0.25,
        h_under=0.28,
        tilt=Vector((-0.24, 0.16, 1.0)),
        az=2.45,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((0.40, 0.54, 0.28)), 0.92, 0.82, 0.60, 0.20, Vector((-0.08, 0.26, 1.0)), 1.92),
            (Vector((-0.38, -0.44, 0.12)), 0.88, 0.80, 0.56, 0.19, Vector((-0.30, 0.02, 1.0)), 2.95),
        ],
    ),
    dict(
        name="low_front_center",
        center=Vector((0.14, -1.62, 3.54)),
        rx=1.18,
        ry=1.08,
        h_top=0.78,
        h_rim=0.24,
        h_under=0.26,
        tilt=Vector((0.04, -0.26, 1.0)),
        az=-1.45,
        lod_keep=True,
        mid_sub=False,
        hero_subs=[
            (Vector((-0.48, 0.16, 0.28)), 0.86, 0.78, 0.56, 0.19, Vector((-0.14, -0.22, 1.0)), -1.88),
            (Vector((0.48, 0.14, 0.20)), 0.86, 0.78, 0.54, 0.19, Vector((0.18, -0.22, 1.0)), -0.92),
        ],
    ),

    # --- Tier 2: Full broad mid-upper oak shoulders ---
    dict(
        name="mid_right_front",
        center=Vector((1.50, -0.28, 4.22)),
        rx=1.26,
        ry=1.18,
        h_top=0.86,
        h_rim=0.25,
        h_under=0.26,
        tilt=Vector((0.22, -0.06, 1.0)),
        az=-0.18,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((0.28, 0.44, 0.20)), 0.94, 0.86, 0.66, 0.20, Vector((0.22, 0.12, 1.0)), 0.42),
            (Vector((-0.12, -0.26, 0.42)), 0.90, 0.82, 0.62, 0.19, Vector((0.12, -0.10, 1.0)), -0.45),
        ],
    ),
    dict(
        name="mid_left_front",
        center=Vector((-1.42, -0.26, 4.52)),
        rx=1.26,
        ry=1.18,
        h_top=0.88,
        h_rim=0.25,
        h_under=0.26,
        tilt=Vector((-0.22, -0.06, 1.0)),
        az=3.02,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((-0.26, 0.44, 0.22)), 0.94, 0.86, 0.66, 0.20, Vector((-0.22, 0.12, 1.0)), 2.55),
            (Vector((0.18, -0.28, 0.42)), 0.90, 0.82, 0.62, 0.19, Vector((-0.10, -0.10, 1.0)), -2.65),
        ],
    ),
    dict(
        name="mid_back_right",
        center=Vector((1.06, 1.32, 4.46)),
        rx=1.20,
        ry=1.14,
        h_top=0.84,
        h_rim=0.24,
        h_under=0.26,
        tilt=Vector((0.16, 0.20, 1.0)),
        az=0.88,
        lod_keep=True,
        mid_sub=False,
        hero_subs=[
            (Vector((-0.34, 0.20, 0.38)), 0.90, 0.82, 0.62, 0.19, Vector((0.06, 0.18, 1.0)), 1.32),
        ],
    ),
    dict(
        name="mid_back_left",
        center=Vector((-1.12, 1.26, 4.54)),
        rx=1.20,
        ry=1.14,
        h_top=0.84,
        h_rim=0.24,
        h_under=0.26,
        tilt=Vector((-0.16, 0.20, 1.0)),
        az=2.24,
        lod_keep=True,
        mid_sub=False,
        hero_subs=[
            (Vector((0.32, 0.22, 0.38)), 0.90, 0.82, 0.62, 0.19, Vector((-0.06, 0.18, 1.0)), 1.85),
        ],
    ),
    dict(
        name="mid_front_bridge",
        center=Vector((-0.18, -1.24, 4.56)),
        rx=1.20,
        ry=1.10,
        h_top=0.84,
        h_rim=0.23,
        h_under=0.24,
        tilt=Vector((-0.04, -0.18, 1.0)),
        az=-1.68,
        lod_keep=True,
        mid_sub=False,
        hero_subs=[
            (Vector((0.44, 0.10, 0.24)), 0.86, 0.78, 0.58, 0.18, Vector((0.10, -0.14, 1.0)), -1.18),
            (Vector((-0.38, 0.12, 0.32)), 0.86, 0.78, 0.58, 0.18, Vector((-0.10, -0.14, 1.0)), -2.05),
        ],
    ),

    # --- Tier 3: Broad asymmetric sunlit upper crown (stately picturesque oak silhouette) ---
    dict(
        name="top_main",
        center=Vector((-0.36, 0.18, 5.42)),
        rx=1.30,
        ry=1.22,
        h_top=1.02,
        h_rim=0.24,
        h_under=0.24,
        tilt=Vector((-0.05, 0.04, 1.0)),
        az=0.52,
        lod_keep=True,
        mid_sub=True,
        hero_subs=[
            (Vector((-0.44, 0.34, -0.06)), 0.92, 0.84, 0.72, 0.19, Vector((-0.14, 0.10, 1.0)), 2.32),
            (Vector((0.48, -0.24, -0.16)), 0.92, 0.84, 0.68, 0.19, Vector((0.14, -0.08, 1.0)), -0.45),
        ],
    ),
    dict(
        name="top_right_dome",
        center=Vector((0.98, -0.08, 4.98)),
        rx=1.12,
        ry=1.04,
        h_top=0.86,
        h_rim=0.22,
        h_under=0.24,
        tilt=Vector((0.16, -0.04, 1.0)),
        az=-0.16,
        lod_keep=True,
        mid_sub=False,
        hero_subs=[
            (Vector((0.14, 0.22, 0.28)), 0.82, 0.76, 0.60, 0.17, Vector((0.12, 0.04, 1.0)), 0.35),
        ],
    ),
    dict(
        name="top_left_dome",
        center=Vector((-1.02, 0.16, 5.18)),
        rx=1.06,
        ry=1.00,
        h_top=0.84,
        h_rim=0.22,
        h_under=0.24,
        tilt=Vector((-0.14, 0.04, 1.0)),
        az=2.92,
        lod_keep=True,
        mid_sub=False,
        hero_subs=[
            (Vector((-0.12, -0.18, 0.26)), 0.80, 0.74, 0.58, 0.17, Vector((-0.12, -0.04, 1.0)), -2.65),
        ],
    ),
]


class OakBuilder:
    def __init__(self, seed=41):
        self.bm = bmesh.new()
        self.cl = self.bm.loops.layers.color.new("Col")
        self.rng = random.Random(seed)

    def add_face(self, pts, col_srgb, out_hint=None):
        """Create a flat-shaded face with uniform sRGB colour, wound toward out_hint."""
        if len(pts) < 3:
            return None
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return None
        if out_hint is not None and n.dot(out_hint) < 0.0:
            pts = list(reversed(pts))
        try:
            f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        except ValueError:
            return None
        f.smooth = False
        lin = (*srgb_to_lin(col_srgb), 1.0)
        for loop in f.loops:
            loop[self.cl] = lin
        return f

    def add_vface(self, pts, cols_srgb, out_hint=None):
        """Create a flat-shaded face with per-corner sRGB colours."""
        if len(pts) < 3:
            return None
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return None
        if out_hint is not None and n.dot(out_hint) < 0.0:
            pts = list(reversed(pts))
            cols_srgb = list(reversed(cols_srgb))
        try:
            f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        except ValueError:
            return None
        f.smooth = False
        for loop, c in zip(f.loops, cols_srgb):
            loop[self.cl] = (*srgb_to_lin(c), 1.0)
        return f

    def add_quad_tris(self, pts, cols_srgb, out_hint=None, flip_diag=False):
        """Split a 4-point panel into 2 explicit flat triangles."""
        p0, p1, p2, p3 = pts
        c0, c1, c2, c3 = cols_srgb
        if not flip_diag:
            self.add_vface([p0, p1, p2], [c0, c1, c2], out_hint)
            self.add_vface([p0, p2, p3], [c0, c2, c3], out_hint)
        else:
            self.add_vface([p0, p1, p3], [c0, c1, c3], out_hint)
            self.add_vface([p1, p2, p3], [c1, c2, c3], out_hint)

    # =========================================================================
    # Wood geometry: fluted oak trunk, sturdy articulated limbs & sub-boughs
    # =========================================================================

    def add_limb_chain(self, points, radii, sides=5, ao_end=0.50, cap_end=False):
        """Build a continuous multi-segment angular oak limb with ridge/groove bark colour."""
        rings = []
        ring_cols = []
        n_pts = len(points)
        prev_e1 = None

        for idx, (pt, rad) in enumerate(zip(points, radii)):
            if idx == 0:
                ax = (points[1] - points[0]).normalized()
            elif idx == n_pts - 1:
                ax = (points[-1] - points[-2]).normalized()
            else:
                ax = (
                    (points[idx] - points[idx - 1]).normalized()
                    + (points[idx + 1] - points[idx]).normalized()
                ).normalized()

            if prev_e1 is None:
                e1, e2, _ = ortho_frame(ax)
            else:
                proj = prev_e1 - ax * prev_e1.dot(ax)
                if proj.length < 1e-4:
                    e1, e2, _ = ortho_frame(ax)
                else:
                    e1 = proj.normalized()
                    e2 = ax.cross(e1).normalized()
            prev_e1 = e1

            t = idx / max(1, n_pts - 1)
            ao = 0.88 - (0.88 - ao_end) * t
            pts = []
            cols = []
            for i in range(sides):
                ang = math.tau * i / sides + 0.25 + idx * 0.08
                is_ridge = (i % 2 == 0)
                flute = 1.06 if (is_ridge and sides >= 5) else (0.95 if sides >= 5 else 1.0)
                v = pt + (e1 * math.cos(ang) + e2 * math.sin(ang)) * (rad * flute)
                pts.append(v)
                base_c = COL_BARK_WARM if is_ridge else lerp3(COL_BARK, COL_BARK_DARK, 0.42)
                up_dot = (v - pt).normalized().z
                lit_ao = max(0.32, min(1.0, ao + 0.14 * up_dot))
                cols.append(lerp3(COL_BARK_DARK, base_c, lit_ao))
            rings.append(pts)
            ring_cols.append(cols)

        for k in range(n_pts - 1):
            r0, r1 = rings[k], rings[k + 1]
            c0, c1 = ring_cols[k], ring_cols[k + 1]
            mid_c = (points[k] + points[k + 1]) * 0.5
            for i in range(sides):
                j = (i + 1) % sides
                quad = [r0[i], r0[j], r1[j], r1[i]]
                qcols = [c0[i], c0[j], c1[j], c1[i]]
                fc = (quad[0] + quad[1] + quad[2] + quad[3]) * 0.25
                self.add_quad_tris(quad, qcols, fc - mid_c)

        if cap_end:
            end_c = points[-1]
            ax_end = (points[-1] - points[-2]).normalized()
            for i in range(sides):
                j = (i + 1) % sides
                self.add_face([end_c, rings[-1][i], rings[-1][j]], COL_BARK_DARK, ax_end)

    def add_trunk_and_limbs(self, lod_level=0):
        """Build the fluted oak trunk and sturdy forking boughs for Hero (0), Mid (1), LOD (2)."""
        if lod_level == 0:
            sides = 10
            rings_spec = [
                (-0.30, 0.60, 0.18, 0.78),
                (0.00, 0.56, 0.20, 0.94),
                (0.36, 0.41, 0.15, 1.00),
                (0.88, 0.35, 0.09, 0.96),
                (1.42, 0.35, 0.06, 0.88),
                (1.88, 0.39, 0.07, 0.76),
                (2.18, 0.28, 0.04, 0.56),
            ]
        elif lod_level == 1:
            sides = 8
            rings_spec = [
                (-0.30, 0.59, 0.17, 0.78),
                (0.00, 0.55, 0.19, 0.94),
                (0.42, 0.40, 0.12, 1.00),
                (1.30, 0.35, 0.06, 0.88),
                (2.04, 0.34, 0.05, 0.68),
            ]
        else:
            sides = 6
            rings_spec = [
                (-0.30, 0.58, 0.15, 0.78),
                (0.00, 0.54, 0.16, 0.94),
                (0.48, 0.39, 0.10, 1.00),
                (2.00, 0.33, 0.04, 0.70),
            ]

        rings, ring_cols = [], []
        centers = []
        for idx, (z, r, flute, ao) in enumerate(rings_spec):
            c = trunk_center(z)
            centers.append(c)
            twist = idx * 0.038
            pts, cols = [], []
            for i in range(sides):
                ang = math.tau * i / sides + 0.32 + twist
                is_ridge = (i % 2 == 0)
                jitter = 1.0 + (0.045 if is_ridge else -0.025) * math.sin(i * 2.1 + idx * 0.7)
                rr = r * (1.0 + (flute if is_ridge else -flute * 0.65)) * jitter
                pts.append(c + Vector((rr * math.cos(ang), rr * math.sin(ang), 0.0)))
                base_c = COL_BARK_WARM if is_ridge else lerp3(COL_BARK, COL_BARK_DARK, 0.40)
                cols.append(lerp3(COL_BARK_DARK, base_c, ao))
            rings.append(pts)
            ring_cols.append(cols)

        for k in range(len(rings) - 1):
            r0, r1 = rings[k], rings[k + 1]
            c0, c1 = ring_cols[k], ring_cols[k + 1]
            mid_c = (centers[k] + centers[k + 1]) * 0.5
            for i in range(sides):
                j = (i + 1) % sides
                quad = [r0[i], r0[j], r1[j], r1[i]]
                qcols = [c0[i], c0[j], c1[j], c1[i]]
                fc = (quad[0] + quad[1] + quad[2] + quad[3]) * 0.25
                out = Vector((fc.x - mid_c.x, fc.y - mid_c.y, 0.0))
                self.add_quad_tris(quad, qcols, out)

        if lod_level == 0:
            bot_c = centers[0]
            for i in range(sides):
                j = (i + 1) % sides
                self.add_face([bot_c, rings[0][j], rings[0][i]], COL_BARK_DARK, -UP)

        # Primary spreading limbs
        if lod_level == 0:
            for lm in PRIMARY_LIMBS:
                p0 = trunk_center(lm["start_z"])
                p1 = lm["elbow"]
                p2 = lm["end"]
                p_mid = p0.lerp(p1, 0.52) + Vector((0.0, 0.0, -0.05))
                self.add_limb_chain(
                    [p0, p_mid, p1, p2],
                    [lm["r0"], (lm["r0"] + lm["r1"]) * 0.54, lm["r1"], lm["r2"]],
                    sides=6,
                    ao_end=0.46,
                )
                for f_end, fr0, fr1 in lm["forks"]:
                    f_start = p1.lerp(p2, 0.24)
                    f_mid = f_start.lerp(f_end, 0.52) + Vector((0.0, 0.0, 0.08))
                    self.add_limb_chain([f_start, f_mid, f_end], [fr0, (fr0 + fr1) * 0.56, fr1], sides=4, ao_end=0.40)

            # Central stout ascending heart limb
            c_base = trunk_center(1.94)
            c_mid = Vector((-0.08, 0.12, 3.12))
            c_top = Vector((-0.20, 0.14, 4.20))
            self.add_limb_chain([c_base, c_mid, c_top], [0.24, 0.15, 0.08], sides=5, ao_end=0.40)
            self.add_limb_chain([c_mid, Vector((0.76, -0.14, 4.08))], [0.12, 0.055], sides=4, ao_end=0.38)
            self.add_limb_chain([c_mid, Vector((-0.82, -0.08, 4.10))], [0.12, 0.055], sides=4, ao_end=0.38)

            # Subtle gnarly bark elbow stubs under the lower skirt
            spurs = [
                (Vector((0.86, -0.28, 2.08)), Vector((1.22, -0.66, 2.20))),
                (Vector((-0.74, -0.44, 2.34)), Vector((-1.10, -0.30, 2.24))),
                (Vector((-0.74, 0.54, 2.24)), Vector((-1.08, 0.86, 2.34))),
            ]
            for sp0, sp1 in spurs:
                self.add_limb_chain([sp0, sp1], [0.065, 0.025], sides=4, ao_end=0.48)

        elif lod_level == 1:
            for lm in PRIMARY_LIMBS:
                p0 = trunk_center(lm["start_z"])
                self.add_limb_chain([p0, lm["elbow"], lm["end"]], [lm["r0"], lm["r1"], lm["r2"]], sides=4, ao_end=0.46)
                if lm["forks"]:
                    f_end, fr0, fr1 = lm["forks"][0]
                    f_start = lm["elbow"].lerp(lm["end"], 0.24)
                    self.add_limb_chain([f_start, f_end], [fr0, fr1], sides=3, ao_end=0.42)
            self.add_limb_chain(
                [trunk_center(1.90), Vector((-0.10, 0.12, 3.60))],
                [0.22, 0.10],
                sides=4,
                ao_end=0.42,
            )
        else:
            # LOD2: 4 sturdy asymmetric limbs + central heart stem visible beneath the canopy
            for lm in PRIMARY_LIMBS[:4]:
                p0 = trunk_center(lm["start_z"])
                self.add_limb_chain(
                    [p0, lm["elbow"], lm["end"]],
                    [lm["r0"] * 1.04, lm["r1"] * 1.04, lm["r2"] * 1.08],
                    sides=3,
                    ao_end=0.48,
                )
            self.add_limb_chain(
                [trunk_center(1.90), Vector((-0.10, 0.10, 3.55))],
                [0.20, 0.09],
                sides=3,
                ao_end=0.44,
            )

    # =========================================================================
    # Foliage geometry: dark interior cores + chiseled domed oak cushions
    # =========================================================================

    def add_dark_core(self, center, rx, ry, rz, sides=6):
        """Shaded faceted inner core tucked inside the boughs so gaps read as deep shadow."""
        top = center + Vector((0.0, 0.0, rz))
        bot = center - Vector((0.0, 0.0, rz * 0.72))
        rim = [
            center + Vector((
                rx * math.cos(math.tau * i / sides + 0.28),
                ry * math.sin(math.tau * i / sides + 0.28),
                rz * (0.08 if i % 2 == 0 else -0.06),
            ))
            for i in range(sides)
        ]
        for i in range(sides):
            j = (i + 1) % sides
            out_t = (rim[i] + rim[j]) * 0.5 - center + UP * 0.35
            out_b = (rim[i] + rim[j]) * 0.5 - center - UP * 0.35
            self.add_face([top, rim[i], rim[j]], COL_DEEP_SHADOW, out_t)
            self.add_face([bot, rim[j], rim[i]], COL_DEEP_SHADOW, out_b)

    def _foliage_vert_col(self, pos, crown_core, role="side", tone=1.0, local_lift=0.5, under_tint=0.0):
        """Compute sRGB vertex colour matching pine_tree's vivid light-to-shadow palette."""
        u = (pos.z - CANOPY_Z_MIN) / (CANOPY_Z_MAX - CANOPY_Z_MIN)
        u = max(0.0, min(1.0, u))
        base = canopy_color(u)
        if under_tint > 0.0:
            base = lerp3(base, COL_UNDER_PAD, under_tint)

        rel = pos - crown_core
        radial = math.hypot(rel.x, rel.y)
        r_ao = 0.54 + 0.46 * smoothstep(0.30, 2.20, radial)
        z_ao = 0.66 + 0.34 * smoothstep(0.0, 1.0, u)
        ao = max(0.44, min(1.0, r_ao * 0.60 + z_ao * 0.40))

        if role == "crown":
            c = lerp3(COL_DEEP_SHADOW, base, 0.64 + 0.36 * ao)
            warm_amt = (0.16 + 0.34 * u) * smoothstep(0.25, 1.0, local_lift)
            c = lerp3(c, COL_TIP_WARM, warm_amt)
            return scale3(c, tone)
        elif role == "side":
            c = lerp3(COL_DEEP_SHADOW, base, 0.50 + 0.46 * ao)
            warm_amt = (0.08 + 0.18 * u) * smoothstep(0.45, 1.0, local_lift)
            c = lerp3(c, COL_TIP_WARM, warm_amt)
            return scale3(c, tone)
        elif role == "rim":
            c = lerp3(COL_DEEP_SHADOW, base, (0.44 + 0.34 * ao) * 0.70)
            return scale3(c, tone)
        else:
            c = lerp3(COL_DEEP_SHADOW, base, 0.18 + 0.14 * u)
            return scale3(c, tone)

    def add_chiseled_cushion(
        self,
        center,
        rx,
        ry,
        h_top,
        h_rim,
        h_under,
        tilt_up,
        az=0.0,
        sides=8,
        cap_mode="dome",  # "dome" (Hero broad faceted crown), "tri_plateau" (Mid/LOD crisp rounded dome cap)
        with_rim=True,
        with_under=True,
        under_tint=0.0,
        lobe_strength=0.14,
        crown_core=Vector((0.0, 0.0, 4.15)),
    ):
        """Sculpt a chiseled, billowing oak foliage cushion with bold graphic planes."""
        ref_dir = Vector((math.cos(az), math.sin(az), 0.0))
        e1, e2, u_n = ortho_frame(tilt_up, ref_dir)

        under_hub = center - u_n * h_under
        phase = self.rng.uniform(0.0, math.tau / sides)

        rim_top = []
        rim_bot = []
        angles = []
        for i in range(sides):
            ang = phase + math.tau * i / sides + self.rng.uniform(-0.08, 0.08)
            angles.append(ang)
            is_lobe = (i % 2 == 0)
            r_mod = (
                1.0 + lobe_strength * self.rng.uniform(0.85, 1.15)
                if is_lobe
                else 1.0 - lobe_strength * self.rng.uniform(0.75, 1.08)
            )
            z_mod = (0.07 * h_top) if is_lobe else (-0.05 * h_top)
            z_mod += self.rng.uniform(-0.03, 0.03) * h_top

            ca, sa = math.cos(ang), math.sin(ang)
            local_xy = e1 * (rx * r_mod * ca) + e2 * (ry * r_mod * sa)
            p_top = center + local_xy + u_n * z_mod
            rim_top.append(p_top)

            inset = 0.84 if is_lobe else 0.88
            p_bot = center + local_xy * inset + u_n * (z_mod - h_rim * (1.06 if is_lobe else 0.90))
            rim_bot.append(p_bot)

        wedge_tones = [
            self.rng.uniform(0.98, 1.05) if (i % 2 == 0) else self.rng.uniform(0.89, 0.96)
            for i in range(sides)
        ]

        if cap_mode == "dome":
            # Broad faceted crown dome with chiseled shoulder ring and gentle ridge crest
            crest_off_x = self.rng.uniform(-0.10, 0.10) * rx
            crest_off_y = self.rng.uniform(-0.10, 0.10) * ry
            apex = center + e1 * crest_off_x + e2 * crest_off_y + u_n * h_top

            shoulder = []
            for i in range(sides):
                ang = angles[i] + self.rng.uniform(-0.05, 0.05)
                is_lobe = (i % 2 == 0)
                s_rad = (0.64 if is_lobe else 0.56) * self.rng.uniform(0.95, 1.05)
                s_h = h_top * (0.82 if is_lobe else 0.74) + self.rng.uniform(-0.03, 0.03) * h_top
                ca, sa = math.cos(ang), math.sin(ang)
                p_sh = (
                    center
                    + e1 * (rx * s_rad * ca + crest_off_x * 0.45)
                    + e2 * (ry * s_rad * sa + crest_off_y * 0.45)
                    + u_n * s_h
                )
                shoulder.append(p_sh)

            c_apex = self._foliage_vert_col(apex, crown_core, role="crown", tone=1.04, local_lift=1.0, under_tint=under_tint)

            for i in range(sides):
                j = (i + 1) % sides
                tone = wedge_tones[i]
                pt_i, pt_j = rim_top[i], rim_top[j]
                sh_i, sh_j = shoulder[i], shoulder[j]

                cs_i = self._foliage_vert_col(sh_i, crown_core, role="crown", tone=tone, local_lift=0.88, under_tint=under_tint)
                cs_j = self._foliage_vert_col(sh_j, crown_core, role="crown", tone=tone, local_lift=0.88, under_tint=under_tint)
                ct_i = self._foliage_vert_col(pt_i, crown_core, role="side", tone=tone, local_lift=0.45, under_tint=under_tint)
                ct_j = self._foliage_vert_col(pt_j, crown_core, role="side", tone=tone, local_lift=0.45, under_tint=under_tint)
                c_ap_w = scale3(c_apex, 0.96 + 0.08 * (i % 2))

                out_side = ((pt_i + pt_j) * 0.5 - center).normalized()
                out_up = (out_side * 0.42 + u_n).normalized()

                self.add_vface([apex, sh_i, sh_j], [c_ap_w, cs_i, cs_j], out_up)
                self.add_quad_tris([sh_i, pt_i, pt_j, sh_j], [cs_i, ct_i, ct_j, cs_j], out_up, flip_diag=(i % 2 == 1))

        elif cap_mode == "tri_plateau":
            # Lean 3-vertex broad chiseled crown cap (ideal for 6-sided Mid & LOD: bold graphic planes)
            assert sides == 6
            top_pts = []
            top_cols = []
            for k in range(3):
                ang = 0.5 * (angles[2 * k] + angles[2 * k + 1]) + self.rng.uniform(-0.06, 0.06)
                t_rad = 0.54 * self.rng.uniform(0.94, 1.06)
                t_h = h_top * self.rng.uniform(0.92, 1.00)
                p = center + e1 * (rx * t_rad * math.cos(ang)) + e2 * (ry * t_rad * math.sin(ang)) + u_n * t_h
                top_pts.append(p)
                top_cols.append(
                    self._foliage_vert_col(p, crown_core, role="crown", tone=1.02 + 0.03 * (k % 2), local_lift=0.96, under_tint=under_tint)
                )

            self.add_vface([top_pts[0], top_pts[1], top_pts[2]], top_cols, u_n)

            for k in range(3):
                kn = (k + 1) % 3
                i0 = (2 * k) % 6
                i1 = (2 * k + 1) % 6
                i2 = (2 * k + 2) % 6

                t0, t1 = top_pts[k], top_pts[kn]
                p0, p1, p2 = rim_top[i0], rim_top[i1], rim_top[i2]

                tone_a = wedge_tones[i0]
                tone_b = wedge_tones[i1]

                ct0_a = self._foliage_vert_col(t0, crown_core, role="crown", tone=tone_a, local_lift=0.92, under_tint=under_tint)
                ct0_b = self._foliage_vert_col(t0, crown_core, role="crown", tone=tone_b, local_lift=0.92, under_tint=under_tint)
                ct1_b = self._foliage_vert_col(t1, crown_core, role="crown", tone=tone_b, local_lift=0.92, under_tint=under_tint)

                cp0 = self._foliage_vert_col(p0, crown_core, role="side", tone=tone_a, local_lift=0.45, under_tint=under_tint)
                cp1_a = self._foliage_vert_col(p1, crown_core, role="side", tone=tone_a, local_lift=0.45, under_tint=under_tint)
                cp1_b = self._foliage_vert_col(p1, crown_core, role="side", tone=tone_b, local_lift=0.45, under_tint=under_tint)
                cp2 = self._foliage_vert_col(p2, crown_core, role="side", tone=tone_b, local_lift=0.45, under_tint=under_tint)

                out_a = (((p0 + p1) * 0.5 - center).normalized() * 0.55 + u_n).normalized()
                out_b = (((p1 + p2) * 0.5 - center).normalized() * 0.55 + u_n).normalized()
                out_m = (((t0 + t1) * 0.5 - center).normalized() * 0.50 + u_n).normalized()

                self.add_vface([t0, p0, p1], [ct0_a, cp0, cp1_a], out_a)
                self.add_vface([t0, p1, t1], [ct0_b, cp1_b, ct1_b], out_m)
                self.add_vface([t1, p1, p2], [ct1_b, cp1_b, cp2], out_b)

        # Beveled rim skirt & deep shaded tucked underside
        c_under_hub = self._foliage_vert_col(under_hub, crown_core, role="under", tone=0.90, local_lift=0.0, under_tint=under_tint)
        for i in range(sides):
            j = (i + 1) % sides
            tone = wedge_tones[i]
            pt_i, pt_j = rim_top[i], rim_top[j]
            pb_i, pb_j = rim_bot[i], rim_bot[j]
            out_side = ((pt_i + pt_j) * 0.5 - center).normalized()

            if with_rim:
                cr_i = self._foliage_vert_col(pt_i, crown_core, role="rim", tone=tone, local_lift=0.22, under_tint=under_tint)
                cr_j = self._foliage_vert_col(pt_j, crown_core, role="rim", tone=tone, local_lift=0.22, under_tint=under_tint)
                cb_i = self._foliage_vert_col(pb_i, crown_core, role="rim", tone=tone * 0.86, local_lift=0.04, under_tint=under_tint)
                cb_j = self._foliage_vert_col(pb_j, crown_core, role="rim", tone=tone * 0.86, local_lift=0.04, under_tint=under_tint)
                self.add_quad_tris([pt_i, pb_i, pb_j, pt_j], [cr_i, cb_i, cb_j, cr_j], out_side, flip_diag=(i % 2 == 0))

            if with_under:
                u_i = pb_i if with_rim else pt_i
                u_j = pb_j if with_rim else pt_j
                cu_i = self._foliage_vert_col(u_i, crown_core, role="under", tone=0.95, local_lift=0.0, under_tint=under_tint)
                cu_j = self._foliage_vert_col(u_j, crown_core, role="under", tone=0.95, local_lift=0.0, under_tint=under_tint)
                self.add_vface([under_hub, u_j, u_i], [c_under_hub, cu_j, cu_i], -u_n)

    # =========================================================================
    # Build LOD 0 (Hero), LOD 1 (Mid), LOD 2 (Low)
    # =========================================================================

    def build_oak_hero(self):
        """LOD0 Hero (~2,050 tris): gnarled fluted trunk, forked boughs, bold layered chiseled domes."""
        self.add_trunk_and_limbs(lod_level=0)

        # Deep shaded interior cores so gaps between billows read as lush inner shadow
        self.add_dark_core(Vector((0.02, 0.04, 3.68)), rx=1.48, ry=1.38, rz=0.80, sides=6)
        self.add_dark_core(Vector((-0.08, 0.08, 4.62)), rx=1.22, ry=1.14, rz=0.72, sides=6)

        for cl in CANOPY_CLUSTERS:
            c = cl["center"]
            # Primary broad chiseled dome cushion
            self.add_chiseled_cushion(
                center=c,
                rx=cl["rx"],
                ry=cl["ry"],
                h_top=cl["h_top"],
                h_rim=cl["h_rim"],
                h_under=cl["h_under"],
                tilt_up=cl["tilt"],
                az=cl["az"],
                sides=8,
                cap_mode="dome",
                with_rim=True,
                with_under=(c.z < 4.85),
                under_tint=0.22 if c.z < 3.85 else 0.06,
                lobe_strength=0.14,
            )

            # Bold overlapping chiseled sub-billows (clean graphic planes, never pebbly)
            for idx, (off, srx, sry, sht, shr, stilt, saz) in enumerate(cl["hero_subs"]):
                sub_c = c + off
                is_upper = (off.z > 0.24)
                self.add_chiseled_cushion(
                    center=sub_c,
                    rx=srx,
                    ry=sry,
                    h_top=sht,
                    h_rim=shr,
                    h_under=shr * 0.92,
                    tilt_up=stilt,
                    az=saz,
                    sides=6,
                    cap_mode="dome" if is_upper else "tri_plateau",
                    with_rim=True,
                    with_under=(sub_c.z < 4.35),
                    under_tint=0.0 if is_upper else 0.10,
                    lobe_strength=0.14,
                )

    def build_oak_mid(self):
        """LOD1 Mid (~680 tris): fluted trunk, 5 limbs, broad faceted dome-capped oak cushions."""
        self.add_trunk_and_limbs(lod_level=1)

        self.add_dark_core(Vector((0.0, 0.05, 3.92)), rx=1.44, ry=1.34, rz=0.84, sides=5)

        for cl in CANOPY_CLUSTERS:
            c = cl["center"]
            self.add_chiseled_cushion(
                center=c + Vector((0.0, 0.0, 0.03)),
                rx=cl["rx"] * 1.07,
                ry=cl["ry"] * 1.07,
                h_top=cl["h_top"] * 1.02,
                h_rim=cl["h_rim"] * 1.04,
                h_under=cl["h_under"],
                tilt_up=cl["tilt"],
                az=cl["az"],
                sides=6,
                cap_mode="tri_plateau",
                with_rim=True,
                with_under=(c.z < 4.55),
                under_tint=0.12 if c.z < 3.85 else 0.0,
                lobe_strength=0.13,
            )

            if cl["mid_sub"] and cl["hero_subs"]:
                off, srx, sry, sht, shr, stilt, saz = cl["hero_subs"][-1]
                self.add_chiseled_cushion(
                    center=c + off * 0.88,
                    rx=srx * 1.02,
                    ry=sry * 1.02,
                    h_top=sht * 1.00,
                    h_rim=shr,
                    h_under=shr * 0.85,
                    tilt_up=stilt,
                    az=saz,
                    sides=6,
                    cap_mode="tri_plateau",
                    with_rim=False,
                    with_under=False,
                    under_tint=0.0,
                    lobe_strength=0.12,
                )

    def build_oak_lod(self):
        """LOD2 Low (~305 tris): lean trunk, 4 sturdy limbs, dark inner core, bold dome-capped cushions."""
        self.add_trunk_and_limbs(lod_level=2)

        # Compact 8-tri shaded inner core closes any sky gaps between lower billows
        self.add_dark_core(Vector((0.0, 0.04, 3.82)), rx=1.42, ry=1.34, rz=0.86, sides=4)

        for cl in CANOPY_CLUSTERS:
            if not cl["lod_keep"]:
                continue
            c = cl["center"]
            self.add_chiseled_cushion(
                center=c + Vector((0.0, 0.0, 0.05)),
                rx=cl["rx"] * 1.11,
                ry=cl["ry"] * 1.11,
                h_top=cl["h_top"] * 1.02,
                h_rim=cl["h_rim"],
                h_under=cl["h_under"] + cl["h_rim"] * 0.72,
                tilt_up=cl["tilt"],
                az=cl["az"],
                sides=6,
                cap_mode="tri_plateau",
                with_rim=False,
                with_under=(c.z < 4.70),
                under_tint=0.08 if c.z < 3.85 else 0.0,
                lobe_strength=0.12,
            )

    def finish(self, name, mat):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-4)
        mesh = bpy.data.meshes.new(name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        mesh.materials.append(mat)
        ob = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(ob)
        return ob


def make_vertex_color_material():
    mat = bpy.data.materials.new("OakVertexColor")
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    vcol = nt.nodes.new("ShaderNodeVertexColor")
    vcol.layer_name = "Col"
    nt.links.new(vcol.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.86
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.10
    return mat


def export_single_glb(ob, out_path):
    """Export one mesh object centered at the world origin (restoring its scene location)."""
    saved_loc = ob.location.copy()
    ob.location = (0.0, 0.0, 0.0)
    for o in bpy.data.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(out_path),
        export_format="GLB",
        use_selection=True,
        export_normals=True,
        export_vertex_color="ACTIVE",
        export_materials="NONE",
        export_yup=True,
    )
    ob.location = saved_loc


def setup_studio_and_render(hero_ob, mid_ob, lod_ob):
    """Place Hero | Mid | LOD side-by-side, save .blend, and render a 4-angle lineup sheet."""
    scene = bpy.context.scene
    studio_col = bpy.data.collections.new("Studio")
    scene.collection.children.link(studio_col)

    def to_studio(obj):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        studio_col.objects.link(obj)

    # Lineup from left to right: Hero (LOD0) | Mid (LOD1) | Low (LOD2)
    hero_ob.location = (-7.0, 0.0, 0.0)
    mid_ob.location = (0.0, 0.0, 0.0)
    lod_ob.location = (7.0, 0.0, 0.0)

    bpy.ops.mesh.primitive_plane_add(size=100.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "StudioFloor"
    floor.is_shadow_catcher = True
    floor_mat = bpy.data.materials.new("StudioFloorMat")
    f_bsdf = next(n for n in floor_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    f_bsdf.inputs["Base Color"].default_value = (0.86, 0.88, 0.96, 1.0)
    f_bsdf.inputs["Roughness"].default_value = 0.95
    floor.data.materials.append(floor_mat)
    to_studio(floor)

    scene.world = bpy.data.worlds.new("StudioWorld")
    wnt = scene.world.node_tree
    wnt.nodes.clear()
    out_w = wnt.nodes.new("ShaderNodeOutputWorld")
    mix_w = wnt.nodes.new("ShaderNodeMixShader")
    lp = wnt.nodes.new("ShaderNodeLightPath")
    bg_lit = wnt.nodes.new("ShaderNodeBackground")
    bg_lit.inputs[0].default_value = (0.38, 0.66, 0.84, 1.0)
    bg_lit.inputs[1].default_value = 0.52
    bg_cam = wnt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs[0].default_value = (0.99, 0.985, 0.97, 1.0)
    bg_cam.inputs[1].default_value = 2.6
    wnt.links.new(lp.outputs["Is Camera Ray"], mix_w.inputs["Fac"])
    wnt.links.new(bg_lit.outputs["Background"], mix_w.inputs[1])
    wnt.links.new(bg_cam.outputs["Background"], mix_w.inputs[2])
    wnt.links.new(mix_w.outputs["Shader"], out_w.inputs["Surface"])

    bpy.ops.object.light_add(type="SUN", location=(12.0, -5.5, 9.5))
    sun = bpy.context.object
    sun.name = "KeySun"
    sun.rotation_euler = (Vector((0.0, 0.0, 3.0)) - sun.location).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = 6.2
    sun.data.color = (1.0, 0.94, 0.72)
    sun.data.angle = math.radians(4.5)
    to_studio(sun)

    bpy.ops.object.light_add(type="AREA", location=(-15.0, -4.0, 5.0))
    fill = bpy.context.object
    fill.name = "CoolFill"
    fill.rotation_euler = (Vector((0.0, 0.0, 2.8)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    fill.data.energy = 260.0
    fill.data.color = (0.42, 0.78, 0.94)
    fill.data.size = 12.0
    to_studio(fill)

    bpy.ops.object.light_add(type="AREA", location=(2.0, -5.5, 0.7))
    bounce = bpy.context.object
    bounce.name = "GroundBounce"
    bounce.rotation_euler = (Vector((0.0, 0.0, 2.4)) - bounce.location).to_track_quat("-Z", "Y").to_euler()
    bounce.data.energy = 110.0
    bounce.data.color = (0.96, 0.91, 0.80)
    bounce.data.size = 10.0
    to_studio(bounce)

    bpy.ops.object.camera_add(location=(0.0, -36.5, 3.35))
    cam = bpy.context.object
    cam.name = "StudioCamera"
    cam.data.lens = 58.0
    cam.rotation_euler = (Vector((0.0, 0.0, 3.15)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    to_studio(cam)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.render.image_settings.file_format = "PNG"

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True)

    # 2x2 lineup sheet (Hero | Mid | LOD left-to-right on front, quarter, elevated; reversed on back)
    views = [
        ("front", Vector((0.0, -36.5, 3.35)), Vector((0.0, 0.0, 3.15))),
        ("quarter", Vector((12.8, -35.0, 4.70)), Vector((0.0, 0.0, 3.15))),
        ("back", Vector((0.0, 36.5, 3.35)), Vector((0.0, 0.0, 3.15))),
        ("elevated", Vector((-8.8, -32.5, 19.0)), Vector((0.0, 0.0, 2.85))),
    ]
    tile_w, tile_h = 960, 560
    scene.render.resolution_x = tile_w
    scene.render.resolution_y = tile_h
    scene.render.resolution_percentage = 100

    tmp_paths = []
    for name, loc, tgt in views:
        cam.location = loc
        cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        p = ART / f"_tmp_oak_{name}.png"
        scene.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        tmp_paths.append(p)

    cam.location = views[0][1]
    cam.rotation_euler = (views[0][2] - views[0][1]).to_track_quat("-Z", "Y").to_euler()

    sheet_w, sheet_h = tile_w * 2, tile_h * 2
    sheet = bpy.data.images.new("OakPreviewSheet", width=sheet_w, height=sheet_h, alpha=False)
    buf = [0.0] * (sheet_w * sheet_h * 4)
    offsets = [(0, tile_h), (tile_w, tile_h), (0, 0), (tile_w, 0)]
    for path, (ox, oy) in zip(tmp_paths, offsets):
        im = bpy.data.images.load(str(path))
        px = list(im.pixels)
        for y in range(tile_h):
            src_start = y * tile_w * 4
            dst_start = ((oy + y) * sheet_w + ox) * 4
            buf[dst_start:dst_start + tile_w * 4] = px[src_start:src_start + tile_w * 4]
        bpy.data.images.remove(im)
        path.unlink(missing_ok=True)
    sheet.pixels.foreach_set(buf)
    sheet.filepath_raw = str(OUT_PREVIEW)
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)


def report_mesh(ob):
    verts = len(ob.data.vertices)
    polys = len(ob.data.polygons)
    tris = sum(max(0, len(p.vertices) - 2) for p in ob.data.polygons)
    bbox = [ob.matrix_world @ Vector(b) for b in ob.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    print(
        f"BUILT {ob.name}: verts={verts}, polys={polys}, tris={tris}, "
        f"size=({max(xs)-min(xs):.2f}, {max(ys)-min(ys):.2f}, {max(zs)-min(zs):.2f}), "
        f"z=[{min(zs):.2f}, {max(zs):.2f}]"
    )


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = make_vertex_color_material()

    hero_builder = OakBuilder(seed=41)
    hero_builder.build_oak_hero()
    hero_ob = hero_builder.finish("oak_tree", mat)

    mid_builder = OakBuilder(seed=41)
    mid_builder.build_oak_mid()
    mid_ob = mid_builder.finish("oak_tree_mid", mat)

    lod_builder = OakBuilder(seed=41)
    lod_builder.build_oak_lod()
    lod_ob = lod_builder.finish("oak_tree_lod", mat)

    report_mesh(hero_ob)
    report_mesh(mid_ob)
    report_mesh(lod_ob)

    export_single_glb(hero_ob, OUT_GLB_HERO)
    export_single_glb(mid_ob, OUT_GLB_MID)
    export_single_glb(lod_ob, OUT_GLB_LOD)
    setup_studio_and_render(hero_ob, mid_ob, lod_ob)
    print(f"SAVED {OUT_BLEND}, {OUT_GLB_HERO}, {OUT_GLB_MID}, {OUT_GLB_LOD}, {OUT_PREVIEW}")


if __name__ == "__main__":
    main()
