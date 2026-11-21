"""Build a 3-level LOD stylized low-poly pine tree lineup in Blender.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P art/pine_tree.py

Outputs:
    art/pine_tree.blend              Blender source with pine_tree, pine_tree_mid, pine_tree_lod side-by-side
    art/pine_tree_preview.png        4-angle side-by-side Cycles lineup (Hero | Mid | LOD)
    assets/models/pine_tree.glb      LOD0 Hero (~2,155 tris, +Y up, flat-shaded, vertex colours)
    assets/models/pine_tree_mid.glb  LOD1 Mid  (~687 tris,   +Y up, flat-shaded, vertex colours)
    assets/models/pine_tree_lod.glb  LOD2 Low  (~300 tris,   +Y up, flat-shaded, vertex colours)
"""
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"
OUT_BLEND = ART / "pine_tree.blend"
OUT_PREVIEW = ART / "pine_tree_preview.png"
OUT_GLB_HERO = ROOT / "assets" / "models" / "pine_tree.glb"
OUT_GLB_MID = ROOT / "assets" / "models" / "pine_tree_mid.glb"
OUT_GLB_LOD = ROOT / "assets" / "models" / "pine_tree_lod.glb"

UP = Vector((0.0, 0.0, 1.0))

# Palette in sRGB (converted to linear when written to vertex colours).
# Deep cool spruce shadows, vibrant olive-lime lit faces, warm chartreuse crown tip,
# and warm golden-chestnut cedar bark.
COL_LOW = (0.28, 0.55, 0.21)
COL_MID = (0.48, 0.68, 0.14)
COL_HIGH = (0.68, 0.78, 0.13)
COL_TIP_TOP = (0.86, 0.87, 0.14)
COL_TIP_WARM = (0.90, 0.88, 0.15)
COL_DEEP_SHADOW = (0.06, 0.24, 0.19)
COL_UNDER_FROND = (0.14, 0.40, 0.21)

COL_BARK = (0.56, 0.37, 0.19)
COL_BARK_DARK = (0.28, 0.17, 0.09)
COL_BARK_WARM = (0.71, 0.49, 0.25)


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
    """Base sRGB foliage colour by normalized tree height u in [0, 1]."""
    if u < 0.45:
        return lerp3(COL_LOW, COL_MID, u / 0.45)
    if u < 0.80:
        return lerp3(COL_MID, COL_HIGH, (u - 0.45) / 0.35)
    return lerp3(COL_HIGH, COL_TIP_TOP, (u - 0.80) / 0.20)


class TreeBuilder:
    def __init__(self, seed=31):
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

    def _add_branch_stub(self, a, b, ra, rb, sides=4):
        ax = (b - a).normalized()
        ref = UP if abs(ax.z) < 0.9 else Vector((1.0, 0.0, 0.0))
        e1 = ax.cross(ref).normalized()
        e2 = ax.cross(e1).normalized()
        lo = [a + (e1 * math.cos(math.tau * i / sides) + e2 * math.sin(math.tau * i / sides)) * ra for i in range(sides)]
        hi = [b + (e1 * math.cos(math.tau * i / sides) + e2 * math.sin(math.tau * i / sides)) * rb for i in range(sides)]
        for i in range(sides):
            j = (i + 1) % sides
            out = (lo[i] + lo[j]) * 0.5 - a
            col = lerp3(COL_BARK_DARK, COL_BARK, 0.64 if i % 2 == 0 else 0.42)
            self.add_quad_tris([lo[i], lo[j], hi[j], hi[i]], [col] * 4, out)

    def add_dark_core(self, z_top, z_bot, r_bot, sides=6, cap_under=True):
        """Shaded inner cone tucked inside a tier so gaps read as deep pine shadow."""
        apex = Vector((0.0, 0.0, z_top))
        under = Vector((0.0, 0.0, z_bot + (z_top - z_bot) * 0.30))
        rim = [
            Vector((
                r_bot * math.cos(math.tau * i / sides + 0.3),
                r_bot * math.sin(math.tau * i / sides + 0.3),
                z_bot,
            ))
            for i in range(sides)
        ]
        for i in range(sides):
            j = (i + 1) % sides
            out = (rim[i] + rim[j]) * 0.5 - Vector((0.0, 0.0, z_bot)) + UP * 0.3
            self.add_face([apex, rim[i], rim[j]], COL_DEEP_SHADOW, out)
            if cap_under:
                self.add_face([under, rim[j], rim[i]], COL_DEEP_SHADOW, -UP)

    # =========================================================================
    # LOD 0 — HERO PINE (~2,155 tris): full volumetric chiseled 5-vertex slabs
    # =========================================================================

    def add_trunk_hero(self):
        sides = 10  # 5 alternating root ridges & bark grooves
        rings_spec = [
            (-0.30, 0.42, 0.14, 0.80),
            (0.00, 0.40, 0.16, 0.94),
            (0.36, 0.30, 0.11, 1.00),
            (0.90, 0.25, 0.07, 0.96),
            (1.50, 0.22, 0.03, 0.84),
            (2.40, 0.18, 0.01, 0.60),
            (4.00, 0.10, 0.00, 0.46),
            (5.85, 0.025, 0.00, 0.42),
        ]
        rings, ring_cols = [], []
        for idx, (z, r, flute, ao) in enumerate(rings_spec):
            twist = idx * 0.022
            pts, cols = [], []
            for i in range(sides):
                ang = math.tau * i / sides + 0.38 + twist
                is_ridge = (i % 2 == 0)
                jitter = 1.0 + (0.04 if is_ridge else -0.02) * math.sin(i * 1.9 + idx * 0.6)
                rr = r * (1.0 + (flute if is_ridge else -flute * 0.65)) * jitter
                pts.append(Vector((rr * math.cos(ang), rr * math.sin(ang), z)))
                base_c = COL_BARK_WARM if is_ridge else lerp3(COL_BARK, COL_BARK_DARK, 0.38)
                cols.append(lerp3(COL_BARK_DARK, base_c, ao))
            rings.append(pts)
            ring_cols.append(cols)

        for k in range(len(rings) - 1):
            r0, r1 = rings[k], rings[k + 1]
            c0, c1 = ring_cols[k], ring_cols[k + 1]
            center = Vector((0.0, 0.0, 0.5 * (rings_spec[k][0] + rings_spec[k + 1][0])))
            for i in range(sides):
                j = (i + 1) % sides
                quad = [r0[i], r0[j], r1[j], r1[i]]
                qcols = [c0[i], c0[j], c1[j], c1[i]]
                fc = (quad[0] + quad[1] + quad[2] + quad[3]) * 0.25
                out = Vector((fc.x - center.x, fc.y - center.y, 0.0))
                self.add_quad_tris(quad, qcols, out)

        bot_c = Vector((0.0, 0.0, rings_spec[0][0]))
        for i in range(sides):
            j = (i + 1) % sides
            self.add_face([bot_c, rings[0][j], rings[0][i]], COL_BARK_DARK, -UP)

        for i in range(5):
            ang = math.tau * i / 5.0 + 0.50 + self.rng.uniform(-0.18, 0.18)
            out = Vector((math.cos(ang), math.sin(ang), 0.0))
            z0 = self.rng.uniform(1.18, 1.56)
            p0 = out * 0.16 + Vector((0.0, 0.0, z0))
            p1 = p0 + out * self.rng.uniform(0.58, 0.88) + Vector((0.0, 0.0, self.rng.uniform(0.02, 0.18)))
            self._add_branch_stub(p0, p1, 0.066, 0.026, sides=4)

    def add_frond_hero(
        self,
        root,
        azimuth,
        reach,
        drop,
        w_base,
        w_max,
        thickness,
        ridge_ratio,
        flare,
        base_col,
        notch_style=0,
        roll=0.0,
        ridge_bias=0.0,
        two_stage=True,
        ao_root=0.56,
        tip_warmth=0.18,
    ):
        """Full volumetric chiseled 5-vertex branch plank for the LOD0 Hero model."""
        out_h = Vector((math.cos(azimuth), math.sin(azimuth), 0.0))
        side_h = Vector((-math.sin(azimuth), math.cos(azimuth), 0.0))

        pr = reach * (0.50 - 0.36 * flare)
        pd = drop * (0.50 + 0.40 * flare)

        def curve(t):
            r = 2.0 * (1.0 - t) * t * pr + t * t * reach
            d = 2.0 * (1.0 - t) * t * pd + t * t * drop
            return r, d

        def tangent_frame(t):
            r0, d0 = curve(max(0.0, t - 0.015))
            r1, d1 = curve(min(1.0, t + 0.015))
            tang = (out_h * (r1 - r0) - UP * (d1 - d0)).normalized()
            up_n = side_h.cross(tang).normalized()
            if up_n.z < 0.0:
                up_n = -up_n
            if abs(roll) > 1e-5:
                rot = Matrix.Rotation(roll * t, 3, tang)
                s_vec = (rot @ side_h).normalized()
                u_vec = (rot @ up_n).normalized()
            else:
                s_vec, u_vec = side_h, up_n
            return tang, s_vec, u_vec

        if notch_style == 2:
            t_end = 0.68 if not two_stage else 0.72
            ts = [0.0, 0.38, t_end] if two_stage else [0.0, t_end]
        else:
            t_end = 0.80 if two_stage else 0.76
            ts = [0.0, 0.44, t_end] if two_stage else [0.0, t_end]

        stations = []
        for t in ts:
            r, d = curve(t)
            c = root + out_h * r - UP * d
            tang, s_vec, u_vec = tangent_frame(t)
            w = w_base + (w_max - w_base) * (t / t_end)
            th = thickness * (0.82 + 0.22 * t)
            rh = w * ridge_ratio
            inset = th * 0.24
            tl = c - s_vec * (w * 0.5)
            tm = c + s_vec * (w * ridge_bias) + u_vec * rh
            tr = c + s_vec * (w * 0.5)
            bl = c - s_vec * (w * 0.5 - inset) - u_vec * th
            br = c + s_vec * (w * 0.5 - inset) - u_vec * th
            stations.append((tl, tm, tr, br, bl, t, c, tang, s_vec, u_vec, w, th, rh))

        tone_l = self.rng.uniform(0.96, 1.03)
        tone_r = self.rng.uniform(0.96, 1.03)

        def top_col(t, side_tone):
            ao = ao_root + (1.0 - ao_root) * smoothstep(0.0, 0.46, t)
            c = lerp3(COL_DEEP_SHADOW, base_col, ao)
            c = lerp3(c, COL_TIP_WARM, tip_warmth * smoothstep(0.50, 1.0, t))
            return scale3(c, side_tone)

        def rim_col(t):
            ao = ao_root + (1.0 - ao_root) * smoothstep(0.0, 0.58, t)
            return lerp3(COL_DEEP_SHADOW, base_col, ao * 0.68)

        def under_col(t):
            return lerp3(COL_DEEP_SHADOW, base_col, 0.22 + 0.14 * t)

        for k in range(len(stations) - 1):
            a, b = stations[k], stations[k + 1]
            tl0, tm0, tr0, br0, bl0, t0 = a[:6]
            tl1, tm1, tr1, br1, bl1, t1 = b[:6]
            u_mid = (a[9] + b[9]).normalized()
            s_mid = (a[8] + b[8]).normalized()

            cl0, cl1 = top_col(t0, tone_l), top_col(t1, tone_l)
            cr0, cr1 = top_col(t0, tone_r), top_col(t1, tone_r)
            rm0, rm1 = rim_col(t0), rim_col(t1)
            un0, un1 = under_col(t0), under_col(t1)

            self.add_quad_tris([tl0, tm0, tm1, tl1], [cl0, cl0, cl1, cl1], u_mid - s_mid * 0.25)
            self.add_quad_tris([tm0, tr0, tr1, tm1], [cr0, cr0, cr1, cr1], u_mid + s_mid * 0.25, flip_diag=True)
            self.add_vface([bl0, tl0, tl1, bl1], [rm0, rm0, rm1, rm1], -s_mid)
            self.add_vface([tr0, br0, br1, tr1], [rm0, rm0, rm1, rm1], s_mid)
            self.add_vface([br0, bl0, bl1, br1], [un0, un0, un1, un1], -u_mid)

        tl0, tm0, tr0, br0, bl0 = stations[0][:5]
        self.add_face([tl0, bl0, br0, tr0], COL_DEEP_SHADOW, -stations[0][7])
        self.add_face([tl0, tr0, tm0], COL_DEEP_SHADOW, -stations[0][7])

        tl, tm, tr, br, bl, t_last, c_last, tang, s_vec, u_vec, w, th, rh = stations[-1]
        r_tip, d_tip = curve(1.0)
        c_tip = root + out_h * r_tip - UP * d_tip
        tip_dir = c_tip - c_last
        tip_len = tip_dir.length
        tip_fwd = tip_dir.normalized() if tip_len > 1e-6 else tang

        th_corner = th * 0.56
        th_apex = th * 0.36

        cl_e, cl_t = top_col(t_last, tone_l), top_col(1.0, tone_l)
        cr_e, cr_t = top_col(t_last, tone_r), top_col(1.0, tone_r)
        rm_e, rm_t = rim_col(t_last), rim_col(1.0)
        un_e, un_t = under_col(t_last), under_col(1.0)
        w_hem = w * (1.0 + 0.10 * (1.0 - t_last) / max(t_last, 0.2))

        if notch_style == 0:
            notch_right = (self.rng.random() < 0.5)
            if notch_right:
                pt_l = c_last + tip_fwd * (tip_len * 0.42) - s_vec * (w_hem * 0.49)
                pt_m = c_tip + s_vec * (w_hem * ridge_bias) + u_vec * (rh * 0.38)
                n_in = c_last + tip_fwd * (tip_len * 0.34) + s_vec * (w_hem * 0.33) + u_vec * (rh * 0.14)
                pt_r = c_last + tip_fwd * (tip_len * 0.64) + s_vec * (w_hem * 0.50)

                pb_l = pt_l - u_vec * th_corner
                pb_m = pt_m - u_vec * th_apex
                nb_in = n_in - u_vec * (th * 0.68)
                pb_r = pt_r - u_vec * th_corner

                self.add_quad_tris([tl, tm, pt_m, pt_l], [cl_e, cl_e, cl_t, cl_t], u_vec)
                self.add_vface([tm, n_in, pt_m], [cr_e, cr_t, cr_t], u_vec)
                self.add_vface([tm, tr, n_in], [cr_e, cr_e, cr_t], u_vec)
                self.add_vface([tr, pt_r, n_in], [cr_e, cr_t, cr_t], u_vec)

                self.add_vface([bl, tl, pt_l, pb_l], [rm_e, rm_e, rm_t, rm_t], -s_vec)
                self.add_vface([pt_l, pt_m, pb_m, pb_l], [rm_t] * 4, tip_fwd - s_vec * 0.25)
                self.add_vface([pt_m, n_in, nb_in, pb_m], [rm_t] * 4, tip_fwd + s_vec * 0.4)
                self.add_vface([n_in, pt_r, pb_r, nb_in], [rm_t] * 4, tip_fwd - s_vec * 0.2)
                self.add_vface([tr, br, pb_r, pt_r], [rm_e, rm_e, rm_t, rm_t], s_vec)

                self.add_vface([br, bl, pb_l, pb_m], [un_e, un_e, un_t, un_t], -u_vec)
                self.add_vface([br, pb_m, nb_in], [un_e, un_t, un_t], -u_vec)
                self.add_vface([br, nb_in, pb_r], [un_e, un_t, un_t], -u_vec)
            else:
                pt_r = c_last + tip_fwd * (tip_len * 0.42) + s_vec * (w_hem * 0.49)
                pt_m = c_tip + s_vec * (w_hem * ridge_bias) + u_vec * (rh * 0.38)
                n_in = c_last + tip_fwd * (tip_len * 0.34) - s_vec * (w_hem * 0.33) + u_vec * (rh * 0.14)
                pt_l = c_last + tip_fwd * (tip_len * 0.64) - s_vec * (w_hem * 0.50)

                pb_r = pt_r - u_vec * th_corner
                pb_m = pt_m - u_vec * th_apex
                nb_in = n_in - u_vec * (th * 0.68)
                pb_l = pt_l - u_vec * th_corner

                self.add_quad_tris([tm, tr, pt_r, pt_m], [cr_e, cr_e, cr_t, cr_t], u_vec, flip_diag=True)
                self.add_vface([tm, pt_m, n_in], [cl_e, cl_t, cl_t], u_vec)
                self.add_vface([tl, tm, n_in], [cl_e, cl_e, cl_t], u_vec)
                self.add_vface([tl, n_in, pt_l], [cl_e, cl_t, cl_t], u_vec)

                self.add_vface([tr, br, pb_r, pt_r], [rm_e, rm_e, rm_t, rm_t], s_vec)
                self.add_vface([pt_m, pt_r, pb_r, pb_m], [rm_t] * 4, tip_fwd + s_vec * 0.25)
                self.add_vface([n_in, pt_m, pb_m, nb_in], [rm_t] * 4, tip_fwd - s_vec * 0.4)
                self.add_vface([pt_l, n_in, nb_in, pb_l], [rm_t] * 4, tip_fwd + s_vec * 0.2)
                self.add_vface([bl, tl, pt_l, pb_l], [rm_e, rm_e, rm_t, rm_t], -s_vec)

                self.add_vface([br, bl, pb_m, pb_r], [un_e, un_e, un_t, un_t], -u_vec)
                self.add_vface([bl, nb_in, pb_m], [un_e, un_t, un_t], -u_vec)
                self.add_vface([bl, pb_l, nb_in], [un_e, un_t, un_t], -u_vec)

        elif notch_style == 1:
            sign = 1.0 if (self.rng.random() < 0.5) else -1.0
            skew = sign * self.rng.uniform(0.14, 0.28)
            pt_l = c_last + tip_fwd * (tip_len * (0.44 + skew)) - s_vec * (w_hem * 0.48)
            pt_r = c_last + tip_fwd * (tip_len * (0.44 - skew)) + s_vec * (w_hem * 0.48)
            pt_m = c_tip + s_vec * (w_hem * ridge_bias) + u_vec * (rh * 0.36)
            pb_l = pt_l - u_vec * th_corner
            pb_r = pt_r - u_vec * th_corner
            pb_m = pt_m - u_vec * th_apex

            self.add_quad_tris([tl, tm, pt_m, pt_l], [cl_e, cl_e, cl_t, cl_t], u_vec)
            self.add_quad_tris([tm, tr, pt_r, pt_m], [cr_e, cr_e, cr_t, cr_t], u_vec, flip_diag=True)

            self.add_vface([bl, tl, pt_l, pb_l], [rm_e, rm_e, rm_t, rm_t], -s_vec)
            self.add_vface([pt_l, pt_m, pb_m, pb_l], [rm_t] * 4, tip_fwd - s_vec * 0.3)
            self.add_vface([pt_m, pt_r, pb_r, pb_m], [rm_t] * 4, tip_fwd + s_vec * 0.3)
            self.add_vface([tr, br, pb_r, pt_r], [rm_e, rm_e, rm_t, rm_t], s_vec)

            self.add_vface([br, bl, pb_l, pb_m], [un_e, un_e, un_t, un_t], -u_vec)
            self.add_vface([br, pb_m, pb_r], [un_e, un_t, un_t], -u_vec)

        else:
            peak_off = self.rng.uniform(-0.07, 0.07)
            apex_top = c_tip + s_vec * (w * peak_off) + u_vec * (rh * 0.14)
            apex_bot = apex_top - u_vec * (th_apex * 0.85)

            self.add_vface([tl, tm, apex_top], [cl_e, cl_e, cl_t], u_vec)
            self.add_vface([tm, tr, apex_top], [cr_e, cr_e, cr_t], u_vec)

            self.add_vface([bl, tl, apex_top, apex_bot], [rm_e, rm_e, rm_t, rm_t], -s_vec + tip_fwd)
            self.add_vface([tr, br, apex_bot, apex_top], [rm_e, rm_e, rm_t, rm_t], s_vec + tip_fwd)
            self.add_vface([br, bl, apex_bot], [un_e, un_e, un_t], -u_vec)

    def add_spire_hero(self, z_base, z_tip, r_base):
        sides = 5
        apex = Vector((0.0, 0.0, z_tip))
        z_mid = z_base + (z_tip - z_base) * 0.44
        r_mid = r_base * 0.44
        a0 = 0.25
        bot_ring = [Vector((r_base * math.cos(a0 + math.tau * i / sides), r_base * math.sin(a0 + math.tau * i / sides), z_base)) for i in range(sides)]
        mid_ring = [Vector((r_mid * math.cos(a0 + math.tau * i / sides + 0.04), r_mid * math.sin(a0 + math.tau * i / sides + 0.04), z_mid)) for i in range(sides)]
        c_bot, c_mid, c_top = canopy_color(0.88), canopy_color(0.95), COL_TIP_TOP
        for i in range(sides):
            j = (i + 1) % sides
            out_lo = (bot_ring[i] + bot_ring[j]) * 0.5 - Vector((0.0, 0.0, z_base)) + UP * 0.2
            self.add_quad_tris([bot_ring[i], bot_ring[j], mid_ring[j], mid_ring[i]], [c_bot, c_bot, c_mid, c_mid], out_lo)
            out_hi = (mid_ring[i] + mid_ring[j]) * 0.5 - Vector((0.0, 0.0, z_mid)) + UP * 0.2
            self.add_vface([mid_ring[i], mid_ring[j], apex], [c_mid, c_mid, c_top], out_hi)

        for i in range(5):
            ang = a0 + math.tau * (i + 0.5) / 5.0 + self.rng.uniform(-0.08, 0.08)
            out = Vector((math.cos(ang), math.sin(ang), 0.0))
            self.add_frond_hero(
                root=Vector((0.0, 0.0, z_base + 0.44)) + out * 0.02,
                azimuth=ang,
                reach=0.40 * self.rng.uniform(0.94, 1.06),
                drop=0.68 * self.rng.uniform(0.95, 1.05),
                w_base=0.14,
                w_max=0.34,
                thickness=0.052,
                ridge_ratio=0.28,
                flare=0.54,
                base_col=canopy_color(0.93),
                notch_style=2,
                roll=self.rng.uniform(-0.05, 0.05),
                ridge_bias=self.rng.uniform(-0.05, 0.05),
                two_stage=False,
                ao_root=0.74,
                tip_warmth=0.26,
            )

    def build_pine_hero(self):
        """LOD0 Hero (~2,155 tris): full sculpted volumetric slabs + 3 recessed under-layers."""
        H = 6.50
        self.add_trunk_hero()

        tiers = [
            dict(z_root=2.76, reach=2.26, drop=1.74, k=8, w_mult=1.08, thick=0.125, flare=0.62, u=0.06, under=True),
            dict(z_root=3.60, reach=1.92, drop=1.78, k=8, w_mult=1.10, thick=0.118, flare=0.60, u=0.22, under=True),
            dict(z_root=4.34, reach=1.54, drop=1.68, k=7, w_mult=1.14, thick=0.108, flare=0.58, u=0.40, under=True),
            dict(z_root=4.96, reach=1.16, drop=1.44, k=6, w_mult=1.22, thick=0.094, flare=0.55, u=0.58, under=False),
            dict(z_root=5.46, reach=0.82, drop=1.12, k=6, w_mult=1.30, thick=0.078, flare=0.54, u=0.74, under=False),
            dict(z_root=5.90, reach=0.55, drop=0.84, k=5, w_mult=1.36, thick=0.064, flare=0.54, u=0.86, under=False),
        ]

        phase = 0.26
        for t_idx, td in enumerate(tiers):
            z_root, reach, drop, k, u = td["z_root"], td["reach"], td["drop"], td["k"], td["u"]
            core_r = reach * (0.44 if t_idx == 0 else (0.64 if t_idx >= 3 else 0.56))
            core_z_bot = max(1.52, z_root - drop * 0.68) if t_idx == 0 else (z_root - drop * 0.76)
            self.add_dark_core(z_root + 0.14, core_z_bot, core_r, sides=6, cap_under=True)

            base_col = canopy_color(u)
            if td["under"]:
                k_u = max(5, k - 2)
                u_phase = phase + math.pi / k
                for i in range(k_u):
                    ang = u_phase + math.tau * (i + self.rng.uniform(-0.14, 0.14)) / k_u
                    out = Vector((math.cos(ang), math.sin(ang), 0.0))
                    r_len = reach * self.rng.uniform(0.92, 1.02)
                    d_len = drop * self.rng.uniform(0.99, 1.07)
                    w_max = (math.tau * reach / k) * 0.90 * self.rng.uniform(0.92, 1.06)
                    col_u = lerp3(COL_UNDER_FROND, base_col, 0.30 + 0.25 * u)
                    self.add_frond_hero(
                        root=Vector((0.0, 0.0, z_root - 0.12)) + out * 0.08,
                        azimuth=ang,
                        reach=r_len,
                        drop=d_len,
                        w_base=w_max * 0.30,
                        w_max=w_max,
                        thickness=td["thick"] * 0.82,
                        ridge_ratio=0.22,
                        flare=td["flare"] + 0.04,
                        base_col=col_u,
                        notch_style=1,
                        roll=self.rng.uniform(-0.08, 0.08),
                        ridge_bias=self.rng.uniform(-0.07, 0.07),
                        two_stage=False,
                        ao_root=0.46,
                        tip_warmth=0.08,
                    )

            for i in range(k):
                ang = phase + math.tau * (i + self.rng.uniform(-0.12, 0.12)) / k
                out = Vector((math.cos(ang), math.sin(ang), 0.0))
                layer_z = 0.07 if (i % 2 == 0) else -0.05
                r_len = reach * self.rng.uniform(0.94, 1.07)
                d_len = drop * self.rng.uniform(0.93, 1.06)
                w_max = min((math.tau * reach / k) * td["w_mult"], reach * 0.76) * self.rng.uniform(0.94, 1.06)
                w_base = w_max * (0.34 if t_idx >= 3 else 0.28)
                frond_col = scale3(base_col, self.rng.uniform(0.95, 1.05))
                if t_idx <= 2 and i % 3 == 1:
                    frond_col = lerp3(frond_col, COL_UNDER_FROND, 0.14)

                if t_idx <= 2:
                    style = self.rng.choices([0, 1], weights=[0.48, 0.52])[0]
                elif t_idx == 3:
                    style = self.rng.choices([0, 1, 2], weights=[0.28, 0.44, 0.28])[0]
                else:
                    style = 2

                self.add_frond_hero(
                    root=Vector((0.0, 0.0, z_root + layer_z)) + out * 0.05,
                    azimuth=ang,
                    reach=r_len,
                    drop=d_len,
                    w_base=w_base,
                    w_max=w_max,
                    thickness=td["thick"] * self.rng.uniform(0.92, 1.10),
                    ridge_ratio=self.rng.uniform(0.26, 0.32),
                    flare=td["flare"] + self.rng.uniform(-0.03, 0.04),
                    base_col=frond_col,
                    notch_style=style,
                    roll=self.rng.uniform(-0.07, 0.07),
                    ridge_bias=self.rng.uniform(-0.09, 0.09),
                    two_stage=(t_idx <= 2),
                    ao_root=0.56 + 0.16 * u,
                    tip_warmth=0.16 + 0.16 * u,
                )

            phase += math.pi / k + 0.34

        self.add_spire_hero(z_base=5.78, z_tip=H, r_base=0.26)

    # =========================================================================
    # LOD 1 (Mid ~687 tris) & LOD 2 (Low ~300 tris): lean origami fronds
    # =========================================================================

    def add_trunk_lean(self, low=False):
        sides = 6 if low else 8
        rings_spec = (
            [(-0.30, 0.42, 0.12, 0.80), (0.00, 0.40, 0.14, 0.94), (0.50, 0.28, 0.08, 1.00), (1.65, 0.21, 0.02, 0.78)]
            if low
            else [(-0.30, 0.42, 0.14, 0.80), (0.00, 0.40, 0.16, 0.94), (0.45, 0.28, 0.10, 1.00), (1.65, 0.21, 0.03, 0.78)]
        )
        rings, ring_cols = [], []
        for idx, (z, r, flute, ao) in enumerate(rings_spec):
            twist = idx * 0.04
            pts, cols = [], []
            for i in range(sides):
                ang = math.tau * i / sides + 0.35 + twist
                is_ridge = (i % 2 == 0)
                rr = r * (1.0 + (flute if is_ridge else -flute * 0.65))
                pts.append(Vector((rr * math.cos(ang), rr * math.sin(ang), z)))
                base_c = COL_BARK_WARM if is_ridge else lerp3(COL_BARK, COL_BARK_DARK, 0.38)
                cols.append(lerp3(COL_BARK_DARK, base_c, ao))
            rings.append(pts)
            ring_cols.append(cols)

        for k in range(len(rings) - 1):
            r0, r1 = rings[k], rings[k + 1]
            c0, c1 = ring_cols[k], ring_cols[k + 1]
            center = Vector((0.0, 0.0, 0.5 * (rings_spec[k][0] + rings_spec[k + 1][0])))
            for i in range(sides):
                j = (i + 1) % sides
                quad = [r0[i], r0[j], r1[j], r1[i]]
                qcols = [c0[i], c0[j], c1[j], c1[i]]
                fc = (quad[0] + quad[1] + quad[2] + quad[3]) * 0.25
                out = Vector((fc.x - center.x, fc.y - center.y, 0.0))
                self.add_quad_tris(quad, qcols, out)

        if not low:
            for i in range(3):
                ang = math.tau * i / 3.0 + 0.65 + self.rng.uniform(-0.18, 0.18)
                out = Vector((math.cos(ang), math.sin(ang), 0.0))
                z0 = self.rng.uniform(1.18, 1.48)
                p0 = out * 0.16 + Vector((0.0, 0.0, z0))
                p1 = p0 + out * self.rng.uniform(0.55, 0.78) + Vector((0.0, 0.0, self.rng.uniform(0.02, 0.14)))
                self._add_branch_stub(p0, p1, 0.062, 0.024, sides=3)

    def add_frond_lean(
        self,
        root,
        azimuth,
        reach,
        drop,
        w_max,
        thickness,
        ridge_ratio,
        flare,
        base_col,
        two_stage=True,
        with_notch=False,
        with_under=True,
        keel_hem=False,
        roll=0.0,
        ridge_bias=0.0,
        ao_root=0.56,
        tip_warmth=0.18,
    ):
        """Lean origami frond for LOD1 Mid (8–18 tris) and LOD2 Low (4–10 tris)."""
        out_h = Vector((math.cos(azimuth), math.sin(azimuth), 0.0))
        side_h = Vector((-math.sin(azimuth), math.cos(azimuth), 0.0))

        pr = reach * (0.50 - 0.36 * flare)
        pd = drop * (0.50 + 0.40 * flare)

        def curve(t):
            return (
                2.0 * (1.0 - t) * t * pr + t * t * reach,
                2.0 * (1.0 - t) * t * pd + t * t * drop,
            )

        def frame_at(t):
            r0, d0 = curve(max(0.0, t - 0.02))
            r1, d1 = curve(min(1.0, t + 0.02))
            tang = (out_h * (r1 - r0) - UP * (d1 - d0)).normalized()
            up_n = side_h.cross(tang).normalized()
            if up_n.z < 0.0:
                up_n = -up_n
            if abs(roll) > 1e-5:
                rot = Matrix.Rotation(roll * t, 3, tang)
                return tang, (rot @ side_h).normalized(), (rot @ up_n).normalized()
            return tang, side_h, up_n

        tone_l = self.rng.uniform(0.96, 1.03)
        tone_r = self.rng.uniform(0.96, 1.03)

        def top_col(t, side_tone):
            ao = ao_root + (1.0 - ao_root) * smoothstep(0.0, 0.48, t)
            c = lerp3(COL_DEEP_SHADOW, base_col, ao)
            c = lerp3(c, COL_TIP_WARM, tip_warmth * smoothstep(0.50, 1.0, t))
            return scale3(c, side_tone)

        def rim_col(t):
            ao = ao_root + (1.0 - ao_root) * smoothstep(0.0, 0.60, t)
            return lerp3(COL_DEEP_SHADOW, base_col, ao * 0.68)

        def under_col(t):
            return lerp3(COL_DEEP_SHADOW, base_col, 0.22 + 0.14 * t)

        sign = 1.0 if (self.rng.random() < 0.5) else -1.0
        skew = sign * self.rng.uniform(0.03, 0.07) if two_stage else sign * self.rng.uniform(0.01, 0.04)
        t_l = max(0.72, min(0.92, (0.83 if two_stage else 0.72) + skew))
        t_r = max(0.72, min(0.92, (0.83 if two_stage else 0.72) - skew))

        rl, dl = curve(t_l)
        rr, dr = curve(t_r)
        rm, dm = curve(1.0)
        _, s_end, u_end = frame_at(0.92)

        rh_end = w_max * ridge_ratio
        th_corner = thickness * 0.68
        th_apex = thickness * (0.72 if keel_hem else 0.42)

        pt_l = root + out_h * rl - UP * dl - s_end * (w_max * 0.50)
        pt_r = root + out_h * rr - UP * dr + s_end * (w_max * 0.50)
        pt_m = root + out_h * rm - UP * dm + s_end * (w_max * ridge_bias) + u_end * (rh_end * 0.55)

        pb_l = pt_l - u_end * th_corner
        pb_r = pt_r - u_end * th_corner
        pb_m = pt_m - u_end * th_apex

        cl0, cl_m, cl1 = top_col(0.0, tone_l), top_col(0.50, tone_l), top_col(1.0, tone_l)
        cr0, cr_m, cr1 = top_col(0.0, tone_r), top_col(0.50, tone_r), top_col(1.0, tone_r)
        rm_m, rm1 = rim_col(0.50), rim_col(1.0)
        un0, un1 = under_col(0.25), under_col(1.0)

        if two_stage:
            r_mid, d_mid = curve(0.48)
            c_mid = root + out_h * r_mid - UP * d_mid
            _, s_mid, u_mid = frame_at(0.48)
            w_mid = w_max * 0.54
            rh_mid = w_mid * ridge_ratio * 1.15
            tl_m = c_mid - s_mid * (w_mid * 0.50)
            tm_m = c_mid + s_mid * (w_mid * ridge_bias) + u_mid * rh_mid
            tr_m = c_mid + s_mid * (w_mid * 0.50)
            u_top = (u_mid + u_end).normalized()

            self.add_vface([root, tl_m, tm_m], [cl0, cl_m, cl_m], u_mid - s_mid * 0.25)
            self.add_vface([root, tm_m, tr_m], [cr0, cr_m, cr_m], u_mid + s_mid * 0.25)

            if keel_hem:
                self.add_quad_tris([tl_m, tm_m, pt_m, pt_l], [cl_m, cl_m, cl1, cl1], u_top - s_end * 0.2)
                self.add_quad_tris([tm_m, tr_m, pt_r, pt_m], [cr_m, cr_m, cr1, cr1], u_top + s_end * 0.2, flip_diag=True)
                self.add_vface([pt_l, pt_m, pb_m], [rm1] * 3, out_h - s_end * 0.3 - u_end * 0.3)
                self.add_vface([pt_m, pt_r, pb_m], [rm1] * 3, out_h + s_end * 0.3 - u_end * 0.3)
                if with_under:
                    u_apex = c_mid - u_mid * (thickness * 0.95)
                    self.add_vface([u_apex, pt_l, pb_m], [un0, un1, un1], -u_top)
                    self.add_vface([u_apex, pb_m, pt_r], [un0, un1, un1], -u_top)
            elif with_notch:
                notch_right = (self.rng.random() < 0.5)
                if notch_right:
                    r_n, d_n = curve(t_r - 0.11)
                    n_in = root + out_h * r_n - UP * d_n + s_end * (w_max * 0.30) + u_end * (rh_end * 0.22)
                    nb_in = n_in - u_end * (thickness * 0.68)

                    self.add_quad_tris([tl_m, tm_m, pt_m, pt_l], [cl_m, cl_m, cl1, cl1], u_top - s_end * 0.2)
                    self.add_vface([tm_m, n_in, pt_m], [cr_m, cr1, cr1], u_top + s_end * 0.2)
                    self.add_vface([tm_m, tr_m, n_in], [cr_m, cr_m, cr1], u_top + s_end * 0.2)
                    self.add_vface([tr_m, pt_r, n_in], [cr_m, cr1, cr1], u_top + s_end * 0.2)

                    self.add_vface([tl_m, pt_l, pb_l], [rm_m, rm1, rm1], -s_end)
                    self.add_quad_tris([pb_l, pt_l, pt_m, pb_m], [rm1] * 4, out_h - s_end * 0.3)
                    self.add_quad_tris([pb_m, pt_m, n_in, nb_in], [rm1] * 4, out_h + s_end * 0.4)
                    self.add_quad_tris([nb_in, n_in, pt_r, pb_r], [rm1] * 4, out_h - s_end * 0.2)
                    self.add_vface([tr_m, pb_r, pt_r], [rm_m, rm1, rm1], s_end)

                    if with_under:
                        u_apex = c_mid - u_mid * (thickness * 0.95)
                        self.add_vface([u_apex, pb_l, pb_m], [un0, un1, un1], -u_top)
                        self.add_vface([u_apex, pb_m, nb_in], [un0, un1, un1], -u_top)
                        self.add_vface([u_apex, nb_in, pb_r], [un0, un1, un1], -u_top)
                else:
                    r_n, d_n = curve(t_l - 0.11)
                    n_in = root + out_h * r_n - UP * d_n - s_end * (w_max * 0.30) + u_end * (rh_end * 0.22)
                    nb_in = n_in - u_end * (thickness * 0.68)

                    self.add_quad_tris([tm_m, tr_m, pt_r, pt_m], [cr_m, cr_m, cr1, cr1], u_top + s_end * 0.2, flip_diag=True)
                    self.add_vface([tm_m, pt_m, n_in], [cl_m, cl1, cl1], u_top - s_end * 0.2)
                    self.add_vface([tl_m, tm_m, n_in], [cl_m, cl_m, cl1], u_top - s_end * 0.2)
                    self.add_vface([tl_m, n_in, pt_l], [cl_m, cl1, cl1], u_top - s_end * 0.2)

                    self.add_vface([tr_m, pb_r, pt_r], [rm_m, rm1, rm1], s_end)
                    self.add_quad_tris([pb_m, pt_m, pt_r, pb_r], [rm1] * 4, out_h + s_end * 0.3)
                    self.add_quad_tris([nb_in, n_in, pt_m, pb_m], [rm1] * 4, out_h - s_end * 0.4)
                    self.add_quad_tris([pb_l, pt_l, n_in, nb_in], [rm1] * 4, out_h + s_end * 0.2)
                    self.add_vface([tl_m, pt_l, pb_l], [rm_m, rm1, rm1], -s_end)

                    if with_under:
                        u_apex = c_mid - u_mid * (thickness * 0.95)
                        self.add_vface([u_apex, pb_m, pb_r], [un0, un1, un1], -u_top)
                        self.add_vface([u_apex, nb_in, pb_m], [un0, un1, un1], -u_top)
                        self.add_vface([u_apex, pb_l, nb_in], [un0, un1, un1], -u_top)
            else:
                self.add_quad_tris([tl_m, tm_m, pt_m, pt_l], [cl_m, cl_m, cl1, cl1], u_top - s_end * 0.2)
                self.add_quad_tris([tm_m, tr_m, pt_r, pt_m], [cr_m, cr_m, cr1, cr1], u_top + s_end * 0.2, flip_diag=True)

                self.add_vface([tl_m, pt_l, pb_l], [rm_m, rm1, rm1], -s_end)
                self.add_quad_tris([pb_l, pt_l, pt_m, pb_m], [rm1] * 4, out_h - s_end * 0.3)
                self.add_quad_tris([pb_m, pt_m, pt_r, pb_r], [rm1] * 4, out_h + s_end * 0.3)
                self.add_vface([tr_m, pb_r, pt_r], [rm_m, rm1, rm1], s_end)

                if with_under:
                    u_apex = c_mid - u_mid * (thickness * 0.95)
                    self.add_vface([u_apex, pb_l, pb_m], [un0, un1, un1], -u_top)
                    self.add_vface([u_apex, pb_m, pb_r], [un0, un1, un1], -u_top)
        else:
            self.add_vface([root, pt_l, pt_m], [cl0, cl1, cl1], u_end - s_end * 0.25)
            self.add_vface([root, pt_m, pt_r], [cr0, cr1, cr1], u_end + s_end * 0.25)

            if keel_hem:
                self.add_vface([pt_l, pt_m, pb_m], [rm1] * 3, out_h - s_end * 0.3 - u_end * 0.3)
                self.add_vface([pt_m, pt_r, pb_m], [rm1] * 3, out_h + s_end * 0.3 - u_end * 0.3)
                if with_under:
                    u_apex = root - u_end * (thickness * 0.6)
                    self.add_vface([u_apex, pt_l, pb_m], [un0, un1, un1], -u_end)
                    self.add_vface([u_apex, pb_m, pt_r], [un0, un1, un1], -u_end)
            else:
                self.add_vface([root, pt_l, pb_l], [rm_m, rm1, rm1], -s_end)
                self.add_quad_tris([pb_l, pt_l, pt_m, pb_m], [rm1] * 4, out_h - s_end * 0.3)
                self.add_quad_tris([pb_m, pt_m, pt_r, pb_r], [rm1] * 4, out_h + s_end * 0.3)
                self.add_vface([root, pb_r, pt_r], [rm_m, rm1, rm1], s_end)

                if with_under:
                    u_apex = root - u_end * (thickness * 0.6)
                    self.add_vface([u_apex, pb_l, pb_m], [un0, un1, un1], -u_end)
                    self.add_vface([u_apex, pb_m, pb_r], [un0, un1, un1], -u_end)

    def add_spire_lean(self, z_base, z_tip, r_base, low=False):
        sides = 5
        apex = Vector((0.0, 0.0, z_tip))
        a0 = 0.25
        bot_ring = [Vector((r_base * math.cos(a0 + math.tau * i / sides), r_base * math.sin(a0 + math.tau * i / sides), z_base)) for i in range(sides)]
        c_bot, c_top = canopy_color(0.90), COL_TIP_TOP
        for i in range(sides):
            j = (i + 1) % sides
            out_hi = (bot_ring[i] + bot_ring[j]) * 0.5 - Vector((0.0, 0.0, z_base)) + UP * 0.2
            self.add_vface([bot_ring[i], bot_ring[j], apex], [c_bot, c_bot, c_top], out_hi)

        for i in range(4):
            ang = a0 + math.tau * (i + 0.5) / 4.0 + self.rng.uniform(-0.08, 0.08)
            out = Vector((math.cos(ang), math.sin(ang), 0.0))
            self.add_frond_lean(
                root=Vector((0.0, 0.0, z_base + 0.72)) + out * 0.01,
                azimuth=ang,
                reach=0.40 * self.rng.uniform(0.95, 1.05),
                drop=0.66 * self.rng.uniform(0.95, 1.05),
                w_max=0.42,
                thickness=0.048,
                ridge_ratio=0.30,
                flare=0.52,
                base_col=canopy_color(0.93),
                two_stage=False,
                with_notch=False,
                with_under=False,
                keel_hem=low,
                roll=self.rng.uniform(-0.04, 0.04),
                ridge_bias=self.rng.uniform(-0.05, 0.05),
                ao_root=0.74,
                tip_warmth=0.26,
            )

    def build_pine_lean(self, low=False):
        """Build LOD1 Mid (~687 tris) or LOD2 Low (~300 tris)."""
        H = 6.50
        self.add_trunk_lean(low=low)

        if not low:
            tiers = [
                dict(z_root=2.76, reach=2.26, drop=1.74, k=8, w_mult=1.18, thick=0.130, flare=0.62, u=0.06, stage2=True, under_ring=True, keel=False),
                dict(z_root=3.60, reach=1.92, drop=1.78, k=7, w_mult=1.24, thick=0.122, flare=0.60, u=0.22, stage2=True, under_ring=True, keel=False),
                dict(z_root=4.34, reach=1.54, drop=1.68, k=7, w_mult=1.24, thick=0.112, flare=0.58, u=0.40, stage2=True, under_ring=False, keel=False),
                dict(z_root=4.96, reach=1.16, drop=1.44, k=6, w_mult=1.34, thick=0.096, flare=0.55, u=0.58, stage2=False, under_ring=False, keel=False),
                dict(z_root=5.46, reach=0.82, drop=1.12, k=5, w_mult=1.44, thick=0.080, flare=0.54, u=0.74, stage2=False, under_ring=False, keel=False),
                dict(z_root=5.90, reach=0.55, drop=0.84, k=5, w_mult=1.44, thick=0.065, flare=0.54, u=0.86, stage2=False, under_ring=False, keel=False),
            ]
            self.add_dark_core(2.85, 1.54, 1.05, sides=5, cap_under=True)
            self.add_dark_core(4.40, 2.50, 0.90, sides=5, cap_under=True)
        else:
            tiers = [
                dict(z_root=2.76, reach=2.26, drop=1.74, k=7, w_mult=1.32, thick=0.145, flare=0.62, u=0.06, stage2=True, under_ring=False, keel=True),
                dict(z_root=3.60, reach=1.92, drop=1.78, k=7, w_mult=1.30, thick=0.135, flare=0.60, u=0.22, stage2=True, under_ring=False, keel=True),
                dict(z_root=4.34, reach=1.54, drop=1.68, k=6, w_mult=1.40, thick=0.125, flare=0.58, u=0.40, stage2=False, under_ring=False, keel=True),
                dict(z_root=4.96, reach=1.16, drop=1.44, k=6, w_mult=1.40, thick=0.105, flare=0.55, u=0.58, stage2=False, under_ring=False, keel=True),
                dict(z_root=5.46, reach=0.82, drop=1.12, k=5, w_mult=1.48, thick=0.088, flare=0.54, u=0.74, stage2=False, under_ring=False, keel=True),
                dict(z_root=5.90, reach=0.55, drop=0.84, k=5, w_mult=1.48, thick=0.072, flare=0.54, u=0.86, stage2=False, under_ring=False, keel=True),
            ]
            self.add_dark_core(2.85, 1.54, 1.15, sides=5, cap_under=True)
            self.add_dark_core(4.40, 2.50, 0.92, sides=5, cap_under=False)

        phase = 0.26
        for t_idx, td in enumerate(tiers):
            z_root, reach, drop, k, u = td["z_root"], td["reach"], td["drop"], td["k"], td["u"]
            base_col = canopy_color(u)

            if td["under_ring"]:
                k_u = 4
                u_phase = phase + math.pi / k
                for i in range(k_u):
                    ang = u_phase + math.tau * (i + self.rng.uniform(-0.14, 0.14)) / k_u
                    out = Vector((math.cos(ang), math.sin(ang), 0.0))
                    r_len = reach * self.rng.uniform(0.92, 1.01)
                    d_len = drop * self.rng.uniform(0.99, 1.06)
                    w_max = (math.tau * reach / k) * 1.02 * self.rng.uniform(0.92, 1.06)
                    col_u = lerp3(COL_UNDER_FROND, base_col, 0.30 + 0.25 * u)
                    self.add_frond_lean(
                        root=Vector((0.0, 0.0, z_root - 0.14)) + out * 0.08,
                        azimuth=ang,
                        reach=r_len,
                        drop=d_len,
                        w_max=w_max,
                        thickness=td["thick"] * 0.80,
                        ridge_ratio=0.22,
                        flare=td["flare"] + 0.04,
                        base_col=col_u,
                        two_stage=False,
                        with_notch=False,
                        with_under=True,
                        keel_hem=False,
                        roll=self.rng.uniform(-0.08, 0.08),
                        ridge_bias=self.rng.uniform(-0.07, 0.07),
                        ao_root=0.44,
                        tip_warmth=0.08,
                    )

            for i in range(k):
                ang = phase + math.tau * (i + self.rng.uniform(-0.12, 0.12)) / k
                out = Vector((math.cos(ang), math.sin(ang), 0.0))
                layer_z = 0.07 if (i % 2 == 0) else -0.05
                r_len = reach * self.rng.uniform(0.94, 1.07)
                d_len = drop * self.rng.uniform(0.93, 1.06)
                w_max = min((math.tau * reach / k) * td["w_mult"], reach * 0.88) * self.rng.uniform(0.94, 1.06)

                frond_col = scale3(base_col, self.rng.uniform(0.95, 1.05))
                if t_idx <= 2 and i % 3 == 1:
                    frond_col = lerp3(frond_col, COL_UNDER_FROND, 0.14)

                use_notch = (not low) and td["stage2"] and (i % 2 == 0)

                self.add_frond_lean(
                    root=Vector((0.0, 0.0, z_root + layer_z)) + out * 0.05,
                    azimuth=ang,
                    reach=r_len,
                    drop=d_len,
                    w_max=w_max,
                    thickness=td["thick"] * self.rng.uniform(0.92, 1.10),
                    ridge_ratio=self.rng.uniform(0.26, 0.32),
                    flare=td["flare"] + self.rng.uniform(-0.03, 0.04),
                    base_col=frond_col,
                    two_stage=td["stage2"],
                    with_notch=use_notch,
                    with_under=(t_idx <= 2 if not low else t_idx <= 1),
                    keel_hem=td["keel"],
                    roll=self.rng.uniform(-0.07, 0.07),
                    ridge_bias=self.rng.uniform(-0.09, 0.09),
                    ao_root=0.56 + 0.16 * u,
                    tip_warmth=0.16 + 0.16 * u,
                )

            phase += math.pi / k + 0.34

        self.add_spire_lean(z_base=5.42, z_tip=H, r_base=0.36, low=low)

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
    mat = bpy.data.materials.new("PineVertexColor")
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
    hero_ob.location = (-5.2, 0.0, 0.0)
    mid_ob.location = (0.0, 0.0, 0.0)
    lod_ob.location = (5.2, 0.0, 0.0)

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

    bpy.ops.object.camera_add(location=(0.0, -30.0, 3.35))
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
        ("front", Vector((0.0, -30.0, 3.35)), Vector((0.0, 0.0, 3.15))),
        ("quarter", Vector((10.5, -29.0, 4.60)), Vector((0.0, 0.0, 3.15))),
        ("back", Vector((0.0, 30.0, 3.35)), Vector((0.0, 0.0, 3.15))),
        ("elevated", Vector((-7.5, -27.5, 16.0)), Vector((0.0, 0.0, 2.85))),
    ]
    tile_w, tile_h = 960, 560
    scene.render.resolution_x = tile_w
    scene.render.resolution_y = tile_h
    scene.render.resolution_percentage = 100

    tmp_paths = []
    for name, loc, tgt in views:
        cam.location = loc
        cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        p = ART / f"_tmp_pine_{name}.png"
        scene.render.filepath = str(p)
        bpy.ops.render.render(write_still=True)
        tmp_paths.append(p)

    cam.location = views[0][1]
    cam.rotation_euler = (views[0][2] - views[0][1]).to_track_quat("-Z", "Y").to_euler()

    sheet_w, sheet_h = tile_w * 2, tile_h * 2
    sheet = bpy.data.images.new("PinePreviewSheet", width=sheet_w, height=sheet_h, alpha=False)
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

    hero_builder = TreeBuilder(seed=31)
    hero_builder.build_pine_hero()
    hero_ob = hero_builder.finish("pine_tree", mat)

    mid_builder = TreeBuilder(seed=31)
    mid_builder.build_pine_lean(low=False)
    mid_ob = mid_builder.finish("pine_tree_mid", mat)

    lod_builder = TreeBuilder(seed=31)
    lod_builder.build_pine_lean(low=True)
    lod_ob = lod_builder.finish("pine_tree_lod", mat)

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
