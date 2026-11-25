"""Build a mid-poly Victorian fantasy submarine (Nautilus-inspired) for Tideways.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender -b -noaudio --factory-startup -P art/fantasy_sub_mid.py
    /Applications/Blender.app/Contents/MacOS/Blender -b -noaudio --factory-startup -P art/fantasy_sub_mid.py -- --views /tmp/sub_views

Exports:
    assets/models/fantasy_sub_mid.glb   (glTF, +Y up, +Z forward, vertex colours + PBR)
    art/fantasy_sub_mid.blend           (editable source + preview studio)
    art/fantasy_sub_mid_preview.png     (studio hero preview with full keel visible)

Real-world dimensions (metres):
    LOA ~59.5 m (x: -29.4 tail trailing tip to +30.1 bow ram tip),
    Beam ~11.8 m across side saloon dome blisters (main hull beam ~8.8 m),
    Height ~14.8 m (keel teeth -5.7 m to wheelhouse searchlight brow +9.1 m),
    surfaced waterline at z = 0.0. Working frame is (x=bow, y=port, z=up);
    mapped to Blender (y, -x, z) so glTF export (+Y up) puts +Z forward and +Y up.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
TAU = math.tau

# Rich, moody antique tarnished bronze & aged Victorian brass palette (calibrated for AgX + Godot).
BRONZE_HI = "705635"       # Burnished upper carapace & sun-worn ridges
BRONZE_WARM = "634b2d"     # Primary weathered antique bronze
BRONZE_MID = "574126"      # Rich mid-hull bronze plate
BRONZE_PATINA = "4e3e28"   # Subtle patinated umber-bronze variation
BRONZE_DARK = "43321d"     # Lower flank shadowed bronze
BRONZE_DEEP = "332515"     # Deep oxidized keel & underbelly bronze

BRASS_BRIGHT = "9c7d48"    # Highlighted cast brass collars, spearhead, propeller
BRASS_TRIM = "82663a"      # Primary burnished brass flanges & ribs
BRASS_AGED = "664e2c"      # Aged dark brass strakes, bezels, rivets
BRASS_DARK = "4c3920"      # Deep recessed brass frames

IRON_MID = "342b21"        # Guard struts, manifolds, iris shutter bezel
IRON_DARK = "211b15"       # Louver vents & recessed frames
IRON_RECESS = "14100c"     # Deep shadowed ballast bays

GLASS_DARK = "0c1216"      # Deep obsidian-emerald glossy dome glass
LAMP_IVORY = "fff6dc"      # Bright glowing pearl-ivory saloon ring floodlights
LAMP_WARM = "f2d99b"       # Warm searchlight lens core


def blender_point(v):
    x, y, z = v
    return (y, -x, z)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def smoothstep(edge0, edge1, x):
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def panel_hash(a, b):
    n = (a * 73856093) ^ (b * 19349663)
    return ((n & 0xFFFFFFFF) * 2654435761 & 0xFFFFFFFF) / 4294967296.0


def pick_bronze(row, col, z_mid):
    """Subtle, organic weathered-bronze gradation without harsh checkerboard striping."""
    h = panel_hash(row + 19, col + 41)
    if z_mid > 1.85:
        return BRONZE_HI if h > 0.35 else BRONZE_WARM
    if z_mid > 0.10:
        return BRONZE_WARM if h > 0.42 else BRONZE_MID
    if z_mid > -1.40:
        return BRONZE_MID if h > 0.45 else BRONZE_PATINA
    if z_mid > -3.10:
        return BRONZE_PATINA if h > 0.55 else BRONZE_DARK
    return BRONZE_DARK if h > 0.45 else BRONZE_DEEP


class Part:
    """Vertex-colored mesh builder in (bow, port, up) coordinates."""

    def __init__(self, name, smooth=False):
        self.name = name
        self.default_smooth = smooth
        self.vertices = []
        self.faces = []
        self.colors = []
        self.smooth_flags = []

    def vertex(self, point):
        self.vertices.append(blender_point(point))
        return len(self.vertices) - 1

    def face(self, indices, color, smooth=None):
        clean = [indices[0]]
        for idx in indices[1:]:
            if idx != clean[-1]:
                clean.append(idx)
        if len(clean) > 2 and clean[0] == clean[-1]:
            clean.pop()
        if len(clean) >= 3:
            self.faces.append(tuple(clean))
            self.colors.append(color)
            self.smooth_flags.append(self.default_smooth if smooth is None else smooth)

    def quad(self, p0, p1, p2, p3, color, smooth=None):
        self.face([self.vertex(p) for p in (p0, p1, p2, p3)], color, smooth=smooth)

    def poly(self, pts, color, smooth=None):
        self.face([self.vertex(p) for p in pts], color, smooth=smooth)

    def loft(self, rings, color, top=None, bottom=None, close=False, caps=True, smooth=None):
        rows = [[self.vertex(p) for p in ring] for ring in rings]
        n = len(rows[0])
        m = len(rows) if close else len(rows) - 1
        for j in range(m):
            a, b = rows[j], rows[(j + 1) % len(rows)]
            for i in range(n):
                k = (i + 1) % n
                c = color(j, i) if callable(color) else color
                self.face((a[i], a[k], b[k], b[i]), c, smooth=smooth)
        if caps and not close:
            c0 = bottom if bottom is not None else (
                top if top is not None else (color(0, 0) if callable(color) else color)
            )
            c1 = top if top is not None else (
                color(max(0, m - 1), 0) if callable(color) else color
            )
            self.face(rows[0][::-1], c0, smooth=smooth)
            self.face(rows[-1], c1, smooth=smooth)

    def finish(self, collection, material, recalc_normals=True):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        cl = bm.loops.layers.color.new("Col")
        bm.faces.ensure_lookup_table()
        for f, code, sm in zip(bm.faces, self.colors, self.smooth_flags):
            f.smooth = sm
            rgb = bytes.fromhex(code)
            rgba = (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)
            for loop in f.loops:
                loop[cl] = rgba
        if recalc_normals:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        mesh.color_attributes.active_color_name = "Col"
        mesh.color_attributes.render_color_index = 0
        mesh.materials.append(material)
        obj = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(obj)
        return obj


# ---------------------------------------------------------------------------
# Geometric primitives in working (bow, port, up) coordinates
# ---------------------------------------------------------------------------

def ortho_basis(axis):
    a = Vector(axis).normalized()
    ref = Vector((0.0, 0.0, 1.0)) if abs(a.z) < 0.92 else Vector((1.0, 0.0, 0.0))
    u = a.cross(ref).normalized()
    v = a.cross(u).normalized()
    return a, u, v


def round_ring(center, axis, radius, count, phase=0.0):
    _, u, v = ortho_basis(axis)
    c = Vector(center)
    return [
        tuple(c + radius * (u * math.cos(TAU * i / count + phase) + v * math.sin(TAU * i / count + phase)))
        for i in range(count)
    ]


def pipe(part, a, b, radius, color, count=6, tip=None, smooth=None):
    vec = Vector(b) - Vector(a)
    if vec.length < 1e-6:
        return
    r2 = radius if tip is None else tip
    part.loft([round_ring(a, vec, radius, count), round_ring(b, vec, r2, count)], color, caps=False, smooth=smooth)


def cylinder_stack(part, origin, axis, profile, color, count=12, smooth=None, caps=True):
    a, u, v = ortho_basis(axis)
    o = Vector(origin)
    rings = []
    for offset, r in profile:
        c = o + a * offset
        rr = max(r, 1e-4)
        rings.append([
            tuple(c + rr * (u * math.cos(TAU * i / count) + v * math.sin(TAU * i / count)))
            for i in range(count)
        ])
    part.loft(rings, color, caps=caps, smooth=smooth)


def annulus(part, center, axis, outer_r, inner_r, depth, color, end_color=None, count=16, smooth=None, closed=False):
    a, _, _ = ortho_basis(axis)
    c = Vector(center)
    lo = c - a * (depth * 0.5)
    hi = c + a * (depth * 0.5)
    rings = [
        round_ring(lo, a, outer_r, count),
        round_ring(hi, a, outer_r, count),
        round_ring(hi, a, inner_r, count),
        round_ring(lo, a, inner_r, count),
    ]
    part.loft(
        rings,
        lambda row, i: (end_color or color) if row in (1, 3) else color,
        caps=False,
        close=closed,
        smooth=smooth,
    )


def dome(part, center, normal, radius, depth, color, segs=18, rings_n=5, smooth=True):
    """Build the exposed lens with a shared pole. Its base sits inside the bezel."""
    a, u, v = ortho_basis(normal)
    c = Vector(center)
    rows = []
    for k in range(rings_n):
        theta = (math.pi * 0.5) * k / rings_n
        origin = c + a * depth * math.sin(theta)
        rows.append([
            part.vertex(origin + radius * math.cos(theta) *
                        (u * math.cos(TAU * i / segs) + v * math.sin(TAU * i / segs)))
            for i in range(segs)
        ])
    for lower, upper in zip(rows, rows[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            part.face((lower[i], lower[j], upper[j], upper[i]), color, smooth)
    tip = part.vertex(c + a * depth)
    for i in range(segs):
        part.face((rows[-1][i], rows[-1][(i + 1) % segs], tip), color, smooth)


def extruded_profile_y(part, poly_xz, y_center, half_w_base, half_w_tip, color_side, color_edge=None, z_tip_ref=None):
    """Extrude a 2D (x, z) polygon symmetrically across y = y_center with optional z taper."""
    n = len(poly_xz)
    if z_tip_ref is None:
        left = [(x, y_center + half_w_base, z) for x, z in poly_xz]
        right = [(x, y_center - half_w_base, z) for x, z in poly_xz]
    else:
        z_base, z_tip = z_tip_ref
        span = max(abs(z_tip - z_base), 1e-4)
        left, right = [], []
        for x, z in poly_xz:
            t = clamp(abs(z - z_base) / span, 0.0, 1.0)
            hw = lerp(half_w_base, half_w_tip, t)
            left.append((x, y_center + hw, z))
            right.append((x, y_center - hw, z))
    l_idx = [part.vertex(p) for p in left]
    r_idx = [part.vertex(p) for p in right]
    part.face(l_idx, color_side)
    part.face(r_idx[::-1], color_side)
    ec = color_edge or color_side
    for i in range(n):
        k = (i + 1) % n
        part.face((l_idx[i], r_idx[i], r_idx[k], l_idx[k]), ec)


def box_aligned(part, center, x_len, y_len, z_len, color, top_color=None):
    cx, cy, cz = center
    hx, hy, hz = x_len * 0.5, y_len * 0.5, z_len * 0.5
    r0 = [(cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
          (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz)]
    r1 = [(x, y, cz + hz) for x, y, _ in r0]
    part.loft([r0, r1], color, top=top_color or color, bottom=color)


def rivet_stud(part, pos, normal, radius=0.085, height=0.075, color=BRASS_AGED):
    """Lightweight 4-sided pyramid rivet stud for crisp mid-poly metallic accents."""
    a, u, v = ortho_basis(normal)
    p = Vector(pos)
    b_idx = [
        part.vertex(tuple(p - a * 0.015 + radius * (u * math.cos(TAU * i / 4 + 0.4) + v * math.sin(TAU * i / 4 + 0.4))))
        for i in range(4)
    ]
    apex = part.vertex(tuple(p + a * height))
    for i in range(4):
        part.face((b_idx[i], b_idx[(i + 1) % 4], apex), color)


# ---------------------------------------------------------------------------
# Hull parametric profile (fuller ironclad carapace matching the reference)
# ---------------------------------------------------------------------------

# Stations: (x, z_deck, w_deck, z_u1, w_u1, z_chine, w_chine, z_l1, w_l1, z_keel, w_keel)
HULL_STATIONS = [
    (23.00, -0.35, 0.06, -0.45, 0.14, -0.62, 0.22, -0.74, 0.15, -0.82, 0.06),
    (21.40,  0.14, 0.30, -0.16, 0.68, -0.58, 1.08, -0.98, 0.76, -1.32, 0.26),
    (18.50,  0.94, 0.60,  0.26, 1.40, -0.46, 2.12, -1.38, 1.56, -2.08, 0.48),
    (14.80,  1.78, 0.96,  0.84, 2.10, -0.32, 3.06, -1.88, 2.34, -2.96, 0.72),
    (10.80,  2.54, 1.32,  1.40, 2.78, -0.15, 3.84, -2.40, 3.04, -3.88, 0.98),
    ( 6.80,  3.04, 1.62,  1.82, 3.24,  0.00, 4.28, -2.82, 3.46, -4.64, 1.22),
    ( 3.00,  3.22, 1.80,  1.98, 3.46,  0.14, 4.44, -3.02, 3.60, -5.22, 1.38),
    ( 0.00,  3.24, 1.84,  2.02, 3.52,  0.24, 4.46, -3.02, 3.58, -5.32, 1.42),
    (-3.40,  3.22, 1.80,  2.02, 3.46,  0.34, 4.38, -2.88, 3.48, -5.18, 1.36),
    (-6.80,  3.18, 1.72,  2.00, 3.34,  0.44, 4.22, -2.64, 3.28, -4.84, 1.24),
    (-8.60,  3.14, 1.64,  2.00, 3.22,  0.50, 4.08, -2.24, 3.02, -3.62, 1.02),
    (-10.50, 3.08, 1.52,  1.98, 3.04,  0.56, 3.90, -1.80, 2.70, -2.54, 0.80),
    (-13.20, 2.98, 1.36,  1.96, 2.76,  0.64, 3.58, -1.48, 2.32, -2.28, 0.68),
    (-16.20, 2.86, 1.16,  1.90, 2.40,  0.74, 3.10, -1.16, 1.92, -1.96, 0.54),
    (-19.20, 2.70, 0.92,  1.80, 1.96,  0.84, 2.50, -0.78, 1.46, -1.42, 0.40),
    (-22.20, 2.50, 0.68,  1.68, 1.44,  0.94, 1.78, -0.32, 0.98, -0.74, 0.28),
    (-24.60, 2.26, 0.42,  1.56, 0.88,  1.02, 1.04,  0.14, 0.56, -0.14, 0.18),
    (-26.00, 1.90, 0.20,  1.40, 0.42,  1.06, 0.48,  0.62, 0.28,  0.42, 0.10),
]


def interp_hull(x):
    if x >= HULL_STATIONS[0][0]:
        return HULL_STATIONS[0][1:]
    if x <= HULL_STATIONS[-1][0]:
        return HULL_STATIONS[-1][1:]
    for a, b in zip(HULL_STATIONS, HULL_STATIONS[1:]):
        if a[0] >= x >= b[0]:
            t = (a[0] - x) / (a[0] - b[0])
            return tuple(lerp(va, vb, t) for va, vb in zip(a[1:], b[1:]))
    return HULL_STATIONS[-1][1:]


def arch_spine_z(x):
    """Graceful Nautilus raker arch sweeping steadily up from bow nose (x=22.4) and arching over into wheelhouse brow (x=1.4)."""
    u = clamp((22.4 - x) / (22.4 - 1.4), 0.0, 1.0)
    z_start = -0.05
    z_end = 7.95
    # Smooth S-to-arch sweep matching the reference photo: sleek bow rise, gentle convex arch over the foredeck
    curve = 0.80 * u + 0.60 * (u ** 2) - 0.40 * (u ** 3)
    return lerp(z_start, z_end, clamp(curve, 0.0, 1.0))


def arch_spine_slope(x):
    eps = 0.05
    return (arch_spine_z(x - eps) - arch_spine_z(x + eps)) / (2.0 * eps)


# ---------------------------------------------------------------------------
# Sub-Assembly Builders
# ---------------------------------------------------------------------------

def build_hull(hull_part, brass_part):
    """Build the faceted ironclad carapace hull, longitudinal armor ribs, and shoulder louver trim."""
    rings = []
    ring_z = []
    for st in HULL_STATIONS:
        x, zd, wd, zu1, wu1, zc, wc, zl1, wl1, zk, wk = st
        ring = [
            (x,  wd, zd),
            (x,  wu1, zu1),
            (x,  wc, zc),
            (x,  wl1, zl1),
            (x,  wk, zk),
            (x, -wk, zk),
            (x, -wl1, zl1),
            (x, -wc, zc),
            (x, -wu1, zu1),
            (x, -wd, zd),
        ]
        rings.append(ring)
        ring_z.append([p[2] for p in ring])

    def hull_shade(row, col):
        z_avg = 0.25 * (
            ring_z[row][col] + ring_z[row][(col + 1) % 10]
            + ring_z[row + 1][col] + ring_z[row + 1][(col + 1) % 10]
        )
        if col == 9:
            return BRONZE_HI
        if col == 4:
            return BRONZE_DEEP
        sym_col = col if col < 5 else (8 - col)
        return pick_bronze(row, sym_col, z_avg)

    hull_part.loft(rings, hull_shade, top=BRONZE_DARK, bottom=BRONZE_DARK)

    # Raised longitudinal armor strake ribs along the visible shoulder
    for side in (-1, 1):
        rib_rings = []
        for st in HULL_STATIONS[1:-1]:
            x, zd, wd, zu1, wu1, zc, wc, zl1, wl1, zk, wk = st
            cy, cz = side * wu1, zu1
            ny, nz = side * 0.72, 0.69
            ty, tz = -nz * side, ny * side
            p0 = (x, cy - ty * 0.13 - ny * 0.03, cz - tz * 0.13 - nz * 0.03)
            p1 = (x, cy - ty * 0.07 + ny * 0.075, cz - tz * 0.07 + nz * 0.075)
            p2 = (x, cy + ty * 0.07 + ny * 0.075, cz + tz * 0.07 + nz * 0.075)
            p3 = (x, cy + ty * 0.13 - ny * 0.03, cz + tz * 0.13 - nz * 0.03)
            rib_rings.append([p0, p1, p2, p3] if side == 1 else [p3, p2, p1, p0])
        hull_part.loft(rib_rings, BRASS_AGED)

    # Rhythmic row of beveled ballast-scupper / armor tooth blocks along the upper deck shoulder
    for side in (-1, 1):
        xs = [11.8 - i * 2.08 for i in range(16)]
        for idx, x in enumerate(xs):
            zd, wd, *_ = interp_hull(x)
            y_in = side * (wd + 0.02)
            y_out = side * (wd + 0.30)
            z_lo = zd - 0.16
            z_hi = zd + 0.08
            bx0, bx1 = x + 0.32, x - 0.32
            c_blk = BRONZE_HI if idx % 2 == 0 else BRASS_AGED
            r_in = [(bx0, y_in, z_lo), (bx1, y_in, z_lo), (bx1, y_in, z_hi), (bx0, y_in, z_hi)]
            r_out = [(bx0 - 0.05, y_out, z_lo - 0.07), (bx1 + 0.05, y_out, z_lo - 0.07),
                     (bx1 + 0.05, y_out, z_hi - 0.09), (bx0 - 0.05, y_out, z_hi - 0.09)]
            hull_part.loft([r_in, r_out] if side == 1 else [r_out, r_in], c_blk)

    # Subtle rivet studs along the main upper armor seam
    for side in (-1, 1):
        for i in range(20):
            x = 19.2 - i * 2.05
            zd, wd, zu1, wu1, zc, wc, *_ = interp_hull(x)
            ym = side * lerp(wu1, wc, 0.38)
            zm = lerp(zu1, zc, 0.38)
            rivet_stud(brass_part, (x, ym, zm), (0.0, side * 0.78, 0.62), radius=0.075, height=0.055, color=BRASS_AGED)


def build_lateral_wings(hull_part, brass_part):
    """Build the flared lateral rubbing-strake with scalloped forward bumper flutes and sleek aft dive wings."""
    for side in (-1, 1):
        fwd_xs = [22.4, 20.6, 18.2, 15.4, 12.2, 8.8, 5.2, 1.6, -2.0, -5.6, -8.8, -10.8]
        rings = []
        for x in fwd_xs:
            _, _, _, _, zc, wc, *_ = interp_hull(x)
            t_bow = smoothstep(22.4, 14.0, x)
            proj = lerp(0.28, 0.94, t_bow)
            if x < -2.0:
                proj += 0.32 * smoothstep(-2.0, -9.5, x)
            y_in = side * (wc - 0.30)
            y_mid = side * (wc + proj * 0.62)
            y_tip = side * (wc + proj)
            ht = lerp(0.14, 0.34, t_bow)
            ring = [
                (x, y_in,  zc + ht),
                (x, y_mid, zc + ht * 0.56),
                (x, y_tip, zc + 0.02),
                (x, y_mid, zc - ht * 0.56),
                (x, y_in,  zc - ht),
            ]
            rings.append(ring if side == 1 else ring[::-1])
        hull_part.loft(rings, lambda r, c: BRASS_AGED if c in (1, 2) else BRONZE_MID)

        # Scalloped / serrated bumper flutes along the forward lateral strake edge
        n_scallops = 11
        for i in range(n_scallops):
            x0 = lerp(21.4, -5.8, i / n_scallops)
            x1 = lerp(21.4, -5.8, (i + 1) / n_scallops)
            xm = lerp(x0, x1, 0.72)
            _, _, _, _, zc0, wc0, *_ = interp_hull(x0)
            _, _, _, _, zcm, wcm, *_ = interp_hull(xm)
            _, _, _, _, zc1, wc1, *_ = interp_hull(x1)
            if max(zc0, zcm, zc1) < -0.20:
                continue
            t0 = smoothstep(22.4, 14.0, x0)
            tm = smoothstep(22.4, 14.0, xm)
            t1 = smoothstep(22.4, 14.0, x1)
            p0 = lerp(0.28, 0.94, t0)
            pm = lerp(0.28, 0.94, tm) + lerp(0.20, 0.42, tm)
            p1 = lerp(0.28, 0.94, t1)
            ht = lerp(0.14, 0.27, tm)

            base_in = side * (wcm + lerp(0.28, 0.94, tm) - 0.18)
            tip_out = side * (wcm + pm)
            r_a = [(x0, side * (wc0 + p0 - 0.15), zc0 + ht * 0.52),
                   (x0, side * (wc0 + p0 + 0.04), zc0),
                   (x0, side * (wc0 + p0 - 0.15), zc0 - ht * 0.52)]
            r_m = [(xm, base_in, zcm + ht * 0.70),
                   (xm, tip_out, zcm + 0.03),
                   (xm, base_in, zcm - ht * 0.62)]
            r_b = [(x1, side * (wc1 + p1 - 0.15), zc1 + ht * 0.52),
                   (x1, side * (wc1 + p1 + 0.04), zc1),
                   (x1, side * (wc1 + p1 - 0.15), zc1 - ht * 0.52)]
            seq = [r_a, r_m, r_b] if side == 1 else [r[::-1] for r in (r_a, r_m, r_b)]
            brass_part.loft(seq, BRASS_TRIM if i % 2 == 0 else BRASS_AGED)

        # Sleek Aft Horizontal Stabilizer Wing behind the side saloon blister
        aft_xs = [-14.2, -16.4, -19.0, -21.8, -24.4, -26.4]
        aft_projs = [1.45, 1.56, 1.52, 1.38, 1.15, 0.62]
        aft_rings = []
        for x, proj in zip(aft_xs, aft_projs):
            _, _, _, _, zc, wc, *_ = interp_hull(x)
            y_in = side * max(wc - 0.35, 0.15)
            y_mid = side * (wc + proj * 0.55)
            y_tip = side * (wc + proj)
            ht = lerp(0.32, 0.12, smoothstep(-14.2, -26.4, x))
            ring = [
                (x, y_in,  zc + ht),
                (x, y_mid, zc + ht * 0.52),
                (x, y_tip, zc + 0.02),
                (x, y_mid, zc - ht * 0.48),
                (x, y_in,  zc - ht),
            ]
            aft_rings.append(ring if side == 1 else ring[::-1])
        hull_part.loft(aft_rings, lambda r, c: BRONZE_HI if c in (0, 1) else BRONZE_DARK)


def build_bow_ram(hull_part, brass_part):
    """Build the iconic horizontal armor-piercing bow ram spear."""
    z_ram = -0.60
    cylinder_stack(
        hull_part,
        origin=(21.8, 0.0, z_ram),
        axis=(1.0, 0.0, 0.0),
        profile=[
            (0.00, 0.88),
            (2.05, 0.49),
        ],
        color=BRONZE_MID,
        count=6,
        smooth=False,
    )
    cylinder_stack(
        brass_part,
        origin=(23.75, 0.0, z_ram),
        axis=(1.0, 0.0, 0.0),
        profile=[
            (0.00, 0.47),
            (4.05, 0.38),
            (4.18, 0.57),   # Spearhead shoulder flare
            (4.52, 0.58),
            (6.25, 0.03),   # Pointed ram tip at x = 30.0
        ],
        color=lambda r, i: BRASS_BRIGHT if r >= 2 else BRASS_TRIM,
        count=6,
        smooth=True,
    )


def build_upper_raker_arch(hull_part, brass_part):
    """Build the sweeping convex-upward forward raker arch, open crescent daylight window, and 7 swept sawtooth blades."""
    # 1. Curved arch spine + solid forward web merging smoothly into hull nose + graceful open crescent gap
    xs = [22.4 - i * (21.2 / 12) for i in range(13)]  # 22.4 -> 1.2
    arch_rings = []
    for x in xs:
        zt = arch_spine_z(x)
        zd, wd, *_ = interp_hull(x)
        if x > 11.8:
            zb = zd - 0.35
            wb_bot = lerp(0.32, 0.58, smoothstep(22.4, 11.8, x))
        else:
            # Smoothly curved arch soffit filleting down to deck around x=11.8 -> 8.6,
            # then forming a clean open crescent beam (~0.92 m thick) into the wheelhouse brow!
            fillet = smoothstep(11.8, 8.6, x)
            beam_target = zt - lerp(1.18, 0.86, smoothstep(10.0, 1.2, x))
            zb = lerp(zd - 0.25, max(zd - 0.10, beam_target), fillet)
            wb_bot = lerp(0.56, 0.36, smoothstep(11.8, 2.0, x))

        wb_top = lerp(0.30, 0.42, smoothstep(22.4, 6.0, x))
        flange_w = wb_top + 0.16
        ring = [
            (x,  flange_w, zt),
            (x,  flange_w, zt - 0.18),
            (x,  wb_top,   zt - 0.26),
            (x,  wb_bot,   zb),
            (x, -wb_bot,   zb),
            (x, -wb_top,   zt - 0.26),
            (x, -flange_w, zt - 0.18),
            (x, -flange_w, zt),
        ]
        arch_rings.append(ring)

    hull_part.loft(
        arch_rings,
        lambda r, c: BRASS_TRIM if c in (0, 6, 7) else (BRONZE_HI if c in (1, 5) else BRONZE_WARM),
    )

    # Rivets along both flanks of the forward arch web & curved beam
    for side in (-1, 1):
        for i in range(17):
            x = 20.6 - i * 1.08
            zt = arch_spine_z(x)
            zd, *_ = interp_hull(x)
            if x > 11.2:
                z_riv = lerp(zd + 0.28, zt - 0.42, 0.56)
                y_riv = side * lerp(0.34, 0.48, smoothstep(21.0, 11.2, x))
            else:
                z_riv = zt - 0.48
                y_riv = side * 0.40
            rivet_stud(brass_part, (x, y_riv, z_riv), (0.0, side, 0.0), radius=0.075, height=0.055, color=BRASS_AGED)

    # 2. Seven sculpted backward-hooked sawtooth raker blades curving seamlessly along the arch
    n_teeth = 7
    for i in range(n_teeth):
        t0 = 0.03 + i * 0.128
        t1 = t0 + 0.116
        x_fwd = lerp(22.4, 1.4, t0)
        x_aft = lerp(22.4, 1.4, t1)
        x_mid = lerp(x_fwd, x_aft, 0.56)
        x_hook = lerp(x_fwd, x_aft, 0.94)

        z_fwd = arch_spine_z(x_fwd) - 0.06
        z_mid = arch_spine_z(x_mid)
        z_aft = arch_spine_z(x_aft) - 0.06
        z_hook = arch_spine_z(x_hook)

        slope = arch_spine_slope(x_mid)
        n_vec = Vector((slope, 0.0, 1.0)).normalized()
        tan_aft = Vector((-1.0, 0.0, slope)).normalized()
        tooth_h = lerp(0.84, 1.08, smoothstep(0, 4, i)) * (0.90 if i == n_teeth - 1 else 1.0)

        # Cohesive curved alligator-scute raker blade profile
        p_base_f = Vector((x_fwd, 0.0, z_fwd))
        p_ramp1 = Vector((lerp(x_fwd, x_mid, 0.50), 0.0, lerp(z_fwd, z_mid, 0.50))) + n_vec * (tooth_h * 0.30)
        p_ramp2 = Vector((lerp(x_mid, x_hook, 0.45), 0.0, lerp(z_mid, z_hook, 0.45))) + n_vec * (tooth_h * 0.72)
        p_crest = Vector((x_hook, 0.0, z_hook)) + n_vec * tooth_h + tan_aft * 0.10
        p_hook_back = p_crest + tan_aft * 0.24 - n_vec * 0.14
        p_notch = Vector((x_aft, 0.0, z_aft)) + n_vec * (tooth_h * 0.30) - tan_aft * 0.12
        p_base_a = Vector((x_aft, 0.0, z_aft))

        poly_xz = [
            (p_base_f.x, p_base_f.z),
            (p_ramp1.x, p_ramp1.z),
            (p_ramp2.x, p_ramp2.z),
            (p_crest.x, p_crest.z),
            (p_hook_back.x, p_hook_back.z),
            (p_notch.x, p_notch.z),
            (p_base_a.x, p_base_a.z),
        ]
        w_base = lerp(0.36, 0.46, smoothstep(0, 5, i))
        extruded_profile_y(
            brass_part,
            poly_xz,
            y_center=0.0,
            half_w_base=w_base,
            half_w_tip=w_base * 0.86,
            color_side=BRONZE_WARM if i % 2 == 0 else BRONZE_HI,
            color_edge=BRASS_TRIM,
            z_tip_ref=(z_fwd, p_crest.z),
        )
        # Sleek flared top flange strip hugging the upper curved ramp cleanly (no boxy overhang)
        cap_poly = [
            (p_ramp1.x, p_ramp1.z + 0.01),
            (p_ramp2.x, p_ramp2.z + 0.02),
            (p_crest.x, p_crest.z + 0.03),
            (p_hook_back.x, p_hook_back.z - 0.02),
            (p_crest.x - n_vec.x * 0.15, p_crest.z - n_vec.z * 0.15),
            (p_ramp2.x - n_vec.x * 0.14, p_ramp2.z - n_vec.z * 0.14),
            (p_ramp1.x - n_vec.x * 0.11, p_ramp1.z - n_vec.z * 0.11),
        ]
        extruded_profile_y(
            brass_part,
            cap_poly,
            y_center=0.0,
            half_w_base=w_base * 1.06,
            half_w_tip=w_base * 1.06,
            color_side=BRASS_AGED,
            color_edge=BRASS_BRIGHT,
        )


def build_lower_keel(hull_part):
    """Keep the submerged silhouette with simple teeth, keel box and aft skeg."""
    # 1. Eight beefy downward-hooking sawtooth ventral keel spurs from bow nose to deepest belly
    n_teeth = 8
    for i in range(n_teeth):
        t0 = i / n_teeth
        t1 = (i + 0.96) / n_teeth
        x_fwd = lerp(21.8, 1.2, t0)
        x_aft = lerp(21.8, 1.2, t1)
        x_hook = lerp(x_fwd, x_aft, 0.92)

        zk_f = interp_hull(x_fwd)[8] + 0.20
        zk_a = interp_hull(x_aft)[8] + 0.20
        zk_h = interp_hull(x_hook)[8]

        depth = lerp(0.75, 1.02, smoothstep(0, 5, i))
        p0 = (x_fwd, zk_f)
        p2 = (x_hook - 0.12, zk_h - depth)
        p5 = (x_aft, zk_a)

        w_base = lerp(0.32, 0.52, smoothstep(0, 6, i))
        extruded_profile_y(
            hull_part,
            [p0, p2, p5],
            y_center=0.0,
            half_w_base=w_base,
            half_w_tip=w_base * 0.48,
            color_side=BRONZE_DARK if i % 2 == 0 else BRONZE_DEEP,
            color_edge=BRASS_DARK,
            z_tip_ref=(zk_f, zk_h - depth),
        )

    # Midship armored keel box
    keel_poly = [
        (1.6, -4.35),
        (-8.6, -3.45),
        (-8.2, -4.95),
        (-2.2, -5.52),
        (1.4, -5.50),
    ]
    extruded_profile_y(
        hull_part,
        keel_poly,
        y_center=0.0,
        half_w_base=1.36,
        half_w_tip=1.18,
        color_side=BRONZE_DARK,
        color_edge=BRONZE_DEEP,
        z_tip_ref=(-4.0, -5.52),
    )

    # 3. Aft Ventral Skeg Fin (x = -10.8 to -19.8)
    skeg_poly = [
        (-10.8, -2.10),
        (-12.2, -4.35),
        (-15.8, -3.82),
        (-19.8, -1.22),
    ]
    extruded_profile_y(
        hull_part,
        skeg_poly,
        y_center=0.0,
        half_w_base=0.80,
        half_w_tip=0.38,
        color_side=BRONZE_DARK,
        color_edge=BRONZE_DEEP,
        z_tip_ref=(-1.8, -4.35),
    )

def build_wheelhouse(hull_part, brass_part, iron_part, glass_part, lamp_part):
    """Build the iconic conning tower / wheelhouse with twin 'alligator eye' bubble domes and rounded searchlight brow."""
    # 1. Main armored wheelhouse body (faceted loft rising from deck z=2.90 up to z=8.15)
    wh_levels = [
        (2.90,  4.45, -5.45, 1.42, 2.12, 1.08),
        (4.10,  3.95, -4.40, 1.36, 2.02, 1.00),
        (5.75,  3.20, -3.15, 1.26, 1.88, 0.88),
        (7.35,  2.42, -2.10, 1.08, 1.56, 0.72),
        (8.15,  1.65, -1.55, 0.84, 1.18, 0.56),
    ]
    wh_rings = []
    for z, xf, xa, wf, wm, wa in wh_levels:
        xm_f = lerp(xf, xa, 0.28)
        xm_a = lerp(xf, xa, 0.66)
        ring = [
            (xf,    0.0, z),
            (xm_f,  wf,  z),
            (xm_a,  wm,  z),
            (xa,    wa,  z),
            (xa,   -wa,  z),
            (xm_a, -wm,  z),
            (xm_f, -wf,  z),
        ]
        wh_rings.append(ring)

    hull_part.loft(
        wh_rings,
        lambda r, c: BRONZE_HI if r >= 3 else (BRONZE_WARM if c in (0, 1, 5, 6) else BRONZE_MID),
        top=BRONZE_HI,
        bottom=BRONZE_DARK,
    )

    # Rear armored ladder-step / louver ribs descending the aft slope of the wheelhouse
    for k in range(6):
        t = (k + 0.5) / 6.0
        z_r = lerp(7.45, 3.70, t)
        x_r = lerp(-2.05, -4.68, t)
        w_r = lerp(0.84, 1.34, t)
        box_aligned(brass_part, (x_r - 0.08, 0.0, z_r), 0.26, w_r * 2.0, 0.16, BRASS_AGED, top_color=BRASS_TRIM)

    # 2. Rounded Sculpted Top Searchlight / Periscope Brow Hood (peaking smoothly behind the raker arch junction!)
    brow_levels = [
        (7.75,  1.60, -1.85, 0.88, 0.78),
        (8.48,  1.32, -1.42, 0.80, 0.68),
        (9.08,  0.76, -0.78, 0.54, 0.48),
    ]
    brow_rings = []
    for z, xf, xa, wf, wa in brow_levels:
        xm = lerp(xf, xa, 0.50)
        brow_rings.append([
            (xf,  wf * 0.78, z), (xm,  wf, z), (xa,  wa, z),
            (xa, -wa, z), (xm, -wf, z), (xf, -wf * 0.78, z),
        ])
    hull_part.loft(brow_rings, BRONZE_HI, top=BRASS_AGED)

    # Forward-facing circular armored searchlight bezel & lens nestled cleanly into the rounded brow
    sl_center = (1.18, 0.0, 8.48)
    sl_axis = (0.96, 0.0, 0.28)
    annulus(brass_part, sl_center, sl_axis, outer_r=0.58, inner_r=0.40, depth=0.34,
            color=BRASS_TRIM, end_color=BRASS_BRIGHT, count=14)
    dome(glass_part, (1.24, 0.0, 8.50), sl_axis, radius=0.40, depth=0.22, color=GLASS_DARK, segs=12, rings_n=3, smooth=True)
    dome(lamp_part, (1.40, 0.0, 8.54), sl_axis, radius=0.14, depth=0.05, color=LAMP_WARM, segs=8, rings_n=2, smooth=True)

    # Subtle forward arched bridge brow cowl just ahead of the searchlight hood (blending into raker arch)
    cowl_rings = [
        [(2.15,  0.65, 7.60), (1.35,  0.78, 7.60), (1.35, -0.78, 7.60), (2.15, -0.65, 7.60)],
        [(1.95,  0.54, 8.32), (1.25,  0.66, 8.32), (1.25, -0.66, 8.32), (1.95, -0.54, 8.32)],
        [(1.72,  0.34, 8.54), (1.20,  0.44, 8.54), (1.20, -0.44, 8.54), (1.72, -0.34, 8.54)],
    ]
    hull_part.loft(cowl_rings, BRONZE_WARM, top=BRONZE_HI)

    # 3. Twin Iconic "Alligator Eye" Bubble Domes (Port & Starboard — larger & prominently sculpted!)
    for side in (-1, 1):
        eye_center = (0.78, side * 1.58, 6.08)
        eye_normal = Vector((0.26, side * 0.95, 0.14)).normalized()

        # Sculpted bronze hood/socket flaring smoothly out from wheelhouse wall
        cylinder_stack(
            hull_part,
            origin=Vector(eye_center) - eye_normal * 0.50,
            axis=eye_normal,
            profile=[
                (0.00, 1.80),
                (0.48, 1.66),
                (0.76, 1.58),
            ],
            color=BRONZE_WARM,
            count=16,
            smooth=False,
        )
        # Thick cast-brass riveted viewport collar
        collar_c = Vector(eye_center) + eye_normal * 0.30
        annulus(
            brass_part,
            collar_c,
            eye_normal,
            outer_r=1.62,
            inner_r=1.35,
            depth=0.34,
            color=BRASS_TRIM,
            end_color=BRASS_BRIGHT,
            count=16,
        )
        # 12 crisp pyramid bolt studs around the brass collar
        _, u_e, v_e = ortho_basis(eye_normal)
        for b in range(12):
            ang = TAU * b / 12.0
            bp = collar_c + eye_normal * 0.17 + 1.48 * (u_e * math.cos(ang) + v_e * math.sin(ang))
            rivet_stud(brass_part, bp, eye_normal, radius=0.085, height=0.075, color=BRASS_BRIGHT)

        # Prominent smooth-shaded convex hemispherical glass dome!
        dome(
            glass_part,
            Vector(eye_center) + eye_normal * 0.26,
            eye_normal,
            radius=1.36,
            depth=1.06,
            color=GLASS_DARK,
            segs=16,
            rings_n=3,
            smooth=True,
        )

    # 4. Foredeck mini-hatch & miniature brass deck railing tucked under the open crescent of the raker arch
    cylinder_stack(
        brass_part,
        origin=(5.8, 0.0, 3.12),
        axis=(0.0, 0.0, 1.0),
        profile=[(0.0, 0.66), (0.28, 0.62), (0.38, 0.48)],
        color=BRASS_AGED,
        count=10,
    )
    for side in (-1, 1):
        rail_xs = [8.8, 7.4, 6.0, 4.6]
        posts_top = []
        for rx in rail_xs:
            zd, wd, *_ = interp_hull(rx)
            py = side * (wd - 0.18)
            p_lo = (rx, py, zd - 0.04)
            p_hi = (rx, py, zd + 0.56)
            pipe(brass_part, p_lo, p_hi, 0.045, BRASS_AGED, 4)
            posts_top.append(p_hi)
        for a, b in zip(posts_top, posts_top[1:]):
            pipe(brass_part, a, b, 0.042, BRASS_TRIM, 4)


def build_dorsal_spine_and_fin(hull_part, brass_part):
    """Build the aft dorsal walkway spine, swept barbed dorsal crest fin, and aft deck hatches."""
    spine_xs = [-4.6, -7.8, -11.2, -14.8, -18.4, -21.6, -23.6]
    spine_rings = []
    for x in spine_xs:
        zd, wd, *_ = interp_hull(x)
        wb = min(wd * 0.82, 1.15)
        wt = wb * 0.64
        ht = lerp(0.86, 0.48, smoothstep(-4.6, -23.6, x))
        spine_rings.append([
            (x,  wb, zd - 0.14),
            (x,  wt, zd + ht),
            (x, -wt, zd + ht),
            (x, -wb, zd - 0.14),
        ])
    hull_part.loft(spine_rings, lambda r, c: BRONZE_HI if c == 1 else BRONZE_WARM)

    # Iconic Swept Barbed Aft Dorsal Fin (concave hooked dragon/shark barbs, matching the photo!)
    fin_poly = [
        (-10.10, 3.35),
        (-10.75, 4.08),   # Barb 1 peak
        (-11.08, 3.92),   # Concave dip
        (-11.55, 4.62),   # Barb 2 peak
        (-11.88, 4.46),
        (-12.35, 5.20),   # Barb 3 peak
        (-12.68, 5.04),
        (-13.20, 5.82),   # Barb 4 peak
        (-13.52, 5.66),
        (-14.32, 6.72),   # Tall hooked apex spire!
        (-14.78, 6.84),
        (-14.42, 6.18),   # Graceful concave trailing edge sweep
        (-14.32, 5.05),
        (-14.68, 3.88),
        (-15.20, 3.25),
    ]
    extruded_profile_y(
        hull_part,
        fin_poly,
        y_center=0.0,
        half_w_base=0.38,
        half_w_tip=0.10,
        color_side=BRONZE_WARM,
        color_edge=BRASS_TRIM,
        z_tip_ref=(3.35, 6.84),
    )

    # Aft Airlock Cupola Hatch right behind the dorsal fin (x = -16.4)
    zd16 = interp_hull(-16.4)[0]
    cylinder_stack(
        brass_part,
        origin=(-16.4, 0.0, zd16 + 0.35),
        axis=(0.0, 0.0, 1.0),
        profile=[
            (0.00, 0.96),
            (0.45, 0.92),
            (0.56, 1.02),
            (0.68, 0.98),
            (0.84, 0.62),
            (0.92, 0.18),
        ],
        color=lambda r, i: BRASS_TRIM if r >= 2 else BRONZE_MID,
        count=8,
    )

    # Stern Flat Armored Deck Hatch ahead of tail fin (x = -21.8)
    zd21 = interp_hull(-21.8)[0]
    cylinder_stack(
        brass_part,
        origin=(-21.8, 0.0, zd21 + 0.20),
        axis=(0.0, 0.0, 1.0),
        profile=[
            (0.00, 1.24),
            (0.32, 1.20),
            (0.42, 1.30),
            (0.54, 1.26),
            (0.60, 0.96),
        ],
        color=lambda r, i: BRASS_AGED if r < 2 else BRASS_TRIM,
        count=8,
    )


def build_saloon_blisters(hull_part, brass_part, iron_part, glass_part, lamp_part):
    """Build the sculpted cast-bronze side saloon blister pods, giant iris domes, and glowing ivory floodlamp rings."""
    x_pod = -12.4
    z_pod = 0.60

    for side in (-1, 1):
        # 1. Rounded organic cast-bronze tear-drop blister fairing (8-point vertical ring for smooth flow)
        pod_stations = [
            # (x, y_in, y_out, z_bot, z_top)
            (-8.4,   3.15, 4.18, -0.30, 1.54),
            (-9.6,   3.02, 4.78, -0.84, 2.04),
            (-11.0,  2.88, 5.18, -1.28, 2.46),
            (-12.4,  2.78, 5.32, -1.44, 2.60),
            (-13.8,  2.68, 5.14, -1.24, 2.42),
            (-15.2,  2.58, 4.56, -0.78, 1.94),
            (-16.5,  2.48, 3.62, -0.22, 1.46),
        ]
        pod_rings = []
        for px, yin, yout, zb, zt in pod_stations:
            zm = 0.5 * (zb + zt)
            hz = 0.5 * (zt - zb)
            # Elliptical arc across the outer flank from top to bottom
            ring = []
            for k in (0, 1, 2, 3, 4, 6):
                ang = math.pi * 0.5 - math.pi * (k / 6.0)
                yy = lerp(yin, yout, math.cos(ang) ** 0.72)
                zz = zm + hz * math.sin(ang)
                ring.append((px, side * yy, zz))
            pod_rings.append(ring if side == 1 else ring[::-1])
        hull_part.loft(
            pod_rings,
            lambda r, c: BRONZE_HI if c in (0, 1) else (BRONZE_WARM if c in (2, 3) else BRONZE_DARK),
        )

        # 2. Massive Cast-Bronze Circular Iris Collar
        dome_normal = Vector((0.09, side * 0.995, 0.02)).normalized()
        collar_center = Vector((x_pod, side * 4.98, z_pod))

        annulus(
            brass_part,
            collar_center,
            dome_normal,
            outer_r=1.96,
            inner_r=1.58,
            depth=0.52,
            color=BRASS_AGED,
            end_color=BRASS_TRIM,
            count=14,
        )
        annulus(
            iron_part,
            collar_center + dome_normal * 0.22,
            dome_normal,
            outer_r=1.66,
            inner_r=1.52,
            depth=0.18,
            color=IRON_MID,
            end_color=BRASS_DARK,
            count=14,
        )

        # 3. Giant Convex Smooth-Shaded Saloon Glass Dome!
        dome(
            glass_part,
            collar_center + dome_normal * 0.20,
            dome_normal,
            radius=1.56,
            depth=1.22,
            color=GLASS_DARK,
            segs=14,
            rings_n=3,
            smooth=True,
        )

        # 4. Iconic Ring of Bright Glowing Ivory Floodlights nestled tightly into the bronze collar
        f_dir = Vector((1.0, 0.0, 0.0))
        f_dir = (f_dir - dome_normal * f_dir.dot(dome_normal)).normalized()
        up_dir = dome_normal.cross(f_dir).normalized()
        if up_dir.z < 0:
            up_dir = -up_dir

        lamp_specs = [
            (  -4.0, 1.94, 0.35, 0.34),   # Large prominent forward lamp
            (  54.0, 1.88, 0.25, 0.28),   # Upper arc cluster
            (  80.0, 1.86, 0.24, 0.28),
            ( 106.0, 1.88, 0.24, 0.28),
        ]
        for deg, r_dist, lr, b_dep in lamp_specs:
            rad = math.radians(deg)
            radial = f_dir * math.cos(rad) + up_dir * math.sin(rad)
            # Sit proudly on the outer face of the circular bronze collar so every round orb gleams cleanly!
            l_pos = collar_center + dome_normal * 0.22 + radial * r_dist
            l_axis = (dome_normal + (f_dir * 0.18 if abs(deg) < 20 else radial * 0.10)).normalized()

            cylinder_stack(
                brass_part,
                origin=l_pos - l_axis * 0.18,
                axis=l_axis,
                profile=[(0.0, lr * 1.26), (b_dep, lr * 1.16)],
                color=BRASS_TRIM,
                count=8,
            )
            dome(
                lamp_part,
                l_pos + l_axis * (b_dep - 0.16),
                l_axis,
                radius=lr * 0.96,
                depth=lr * 0.48,
                color=LAMP_IVORY,
                segs=8,
                rings_n=1,
                smooth=True,
            )


def build_stern_tail_and_propeller(hull_part, brass_part, iron_part):
    """Build the taller curved shark/whale caudal tail fin, 4-blade brass screw, and clean protective guard cage."""
    z_axis = 1.05

    # 1. Upper Caudal Tail Fin Lobe — steeper, gracefully curved leading edge & rounded tip (matching photo!)
    upper_fin = [
        (-23.00, 2.25),
        (-25.00, 2.75),
        (-26.40, 3.70),
        (-27.45, 5.10),
        (-28.20, 6.45),
        (-28.70, 6.95),
        (-29.15, 6.82),
        (-29.15, 5.95),
        (-28.75, 4.30),
        (-28.30, 2.85),
        (-26.00, 2.08),
        (-24.70, 1.45),
    ]
    extruded_profile_y(
        hull_part,
        upper_fin,
        y_center=0.0,
        half_w_base=0.40,
        half_w_tip=0.11,
        color_side=BRONZE_WARM,
        color_edge=BRASS_TRIM,
        z_tip_ref=(2.0, 6.95),
    )

    # 2. Lower Caudal Tail Fin Lobe — compact rounded ventral lobe
    lower_fin = [
        (-23.30,  0.15),
        (-27.95, -2.22),
        (-28.55, -2.25),
        (-28.75, -1.85),
        (-27.80, -0.42),
        (-26.05,  0.06),
        (-24.70,  0.65),
    ]
    extruded_profile_y(
        hull_part,
        lower_fin,
        y_center=0.0,
        half_w_base=0.38,
        half_w_tip=0.10,
        color_side=BRONZE_DARK,
        color_edge=BRASS_DARK,
        z_tip_ref=(0.2, -2.25),
    )

    # 3. Stern Propeller Shaft & Tapered Brass Hub Cone
    cylinder_stack(
        brass_part,
        origin=(-25.2, 0.0, z_axis),
        axis=(-1.0, 0.0, 0.0),
        profile=[
            (0.00, 0.56),
            (2.25, 0.40),
            (2.90, 0.36),
            (3.65, 0.03),
        ],
        color=BRASS_TRIM,
        count=10,
        smooth=True,
    )

    # 4. Four Broad Pitched Brass Propeller Blades
    x_screw = -27.55
    pitch = math.radians(36.0)
    for b in range(4):
        ang = b * (math.pi * 0.5) + math.radians(28.0)
        rad_dir = Vector((0.0, math.cos(ang), math.sin(ang)))
        tan_dir = Vector((0.0, -math.sin(ang), math.cos(ang)))
        fwd_dir = Vector((1.0, 0.0, 0.0))
        chord_dir = (tan_dir * math.cos(pitch) + fwd_dir * math.sin(pitch)).normalized()
        thick_dir = rad_dir.cross(chord_dir).normalized()

        blade_rings = []
        for r, chord, thick in [
            (0.32, 0.56, 0.11),
            (0.76, 1.04, 0.09),
            (1.22, 1.10, 0.07),
            (1.62, 0.22, 0.03),
        ]:
            c = Vector((x_screw, 0.0, z_axis)) + rad_dir * r
            ring = [
                tuple(c + chord_dir * (chord * 0.50)),
                tuple(c + chord_dir * (chord * 0.12) + thick_dir * thick),
                tuple(c - chord_dir * (chord * 0.50)),
                tuple(c + chord_dir * (chord * 0.12) - thick_dir * thick),
            ]
            blade_rings.append(ring)
        brass_part.loft(blade_rings, BRASS_BRIGHT if b % 2 == 0 else BRASS_TRIM)

    # 5. Protective Propeller Shroud Ring & Clean Guard Struts
    shroud_r = 1.72
    annulus(iron_part, (x_screw, 0.0, z_axis), (1, 0, 0),
            shroud_r + 0.065, shroud_r - 0.065, 0.13, IRON_MID, count=14, closed=True)

    strut_links = [
        ((-26.2,  0.0,  2.25), (x_screw,  0.0,  z_axis + shroud_r)),
        ((-28.3,  0.0,  3.10), (x_screw,  0.0,  z_axis + shroud_r)),
        ((-28.0,  0.0, -0.82), (x_screw,  0.0,  z_axis - shroud_r)),
        ((-26.0,  1.25, z_axis), (x_screw,  shroud_r, z_axis)),
        ((-26.0, -1.25, z_axis), (x_screw, -shroud_r, z_axis)),
        ((-25.4,  1.15, z_axis + 0.25), (-28.3, 0.16, 2.85)),
        ((-25.4, -1.15, z_axis + 0.25), (-28.3, -0.16, 2.85)),
    ]
    for a, b in strut_links:
        pipe(iron_part, a, b, 0.060, IRON_MID, 4)


# ---------------------------------------------------------------------------
# Materials, Studio Lighting & Export
# ---------------------------------------------------------------------------

def make_vertex_material(name, roughness=0.45, metallic=0.55, spec=0.55, coat=0.0, emission=0.0):
    mat = bpy.data.materials.new(name)
    if not mat.node_tree:
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec
    if coat > 0.0 and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.04
    if emission > 0.0 and "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = emission
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Emission Color"])
    return mat


def setup_studio(scene):
    """Set up a clean Tideways studio backdrop with full keel visibility."""
    studio = bpy.data.collections.new("Preview studio")
    scene.collection.children.link(studio)

    scene.world = bpy.data.worlds.new("Submarine studio")
    if not scene.world.node_tree:
        scene.world.use_nodes = True
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.36, 0.43, 0.48, 1.0)
    bg.inputs[1].default_value = 0.90

    def add_area_light(name, loc, target, energy, size, color=(1.0, 1.0, 1.0)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        lt = bpy.context.object
        lt.name = name
        lt.data.shape = "DISK"
        lt.data.energy = energy
        lt.data.size = size
        lt.data.color = color
        lt.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        for c in list(lt.users_collection):
            c.objects.unlink(lt)
        studio.objects.link(lt)
        return lt

    add_area_light("KeyLight", (48.0, -34.0, 44.0), (0.0, 0.0, 1.0), energy=155000, size=22.0, color=(1.0, 0.96, 0.89))
    add_area_light("FillLight", (-42.0, -28.0, -18.0), (0.0, 0.0, -1.0), energy=52000, size=32.0, color=(0.76, 0.88, 1.0))
    add_area_light("RimLight", (-16.0, 48.0, 32.0), (0.0, 0.0, 2.0), energy=90000, size=20.0, color=(0.95, 0.97, 1.0))

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "HeroCamera"
    for c in list(camera.users_collection):
        c.objects.unlink(camera)
    studio.objects.link(camera)

    target = Vector((0.0, -0.4, 1.4))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 63.0
    camera.data.clip_end = 400.0
    camera.location = target + Vector((66.0, -26.0, 10.0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 680
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    return studio, camera, target


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    hull_part = Part("HullBronze", smooth=False)
    brass_part = Part("BrassTrim", smooth=False)
    iron_part = Part("DarkIron", smooth=False)
    glass_part = Part("DomeGlass", smooth=True)
    lamp_part = Part("FloodLamp", smooth=True)

    build_hull(hull_part, brass_part)
    build_lateral_wings(hull_part, brass_part)
    build_bow_ram(hull_part, brass_part)
    build_upper_raker_arch(hull_part, brass_part)
    build_lower_keel(hull_part)
    build_wheelhouse(hull_part, brass_part, iron_part, glass_part, lamp_part)
    build_dorsal_spine_and_fin(hull_part, brass_part)
    build_saloon_blisters(hull_part, brass_part, iron_part, glass_part, lamp_part)
    build_stern_tail_and_propeller(hull_part, brass_part, iron_part)

    mat_hull = make_vertex_material("HullBronze", roughness=0.42, metallic=0.66, spec=0.60)
    mat_brass = make_vertex_material("BrassTrim", roughness=0.28, metallic=0.82, spec=0.70)
    mat_iron = make_vertex_material("DarkIron", roughness=0.56, metallic=0.54, spec=0.45)
    mat_glass = make_vertex_material("DomeGlass", roughness=0.04, metallic=0.14, spec=0.95, coat=0.88)
    mat_lamp = make_vertex_material("FloodLamp", roughness=0.18, metallic=0.0, spec=0.5, emission=2.8)

    coll = bpy.data.collections.new("FantasySubmarine")
    scene.collection.children.link(coll)

    objs = [
        hull_part.finish(coll, mat_hull),
        brass_part.finish(coll, mat_brass),
        iron_part.finish(coll, mat_iron),
        glass_part.finish(coll, mat_glass),
        lamp_part.finish(coll, mat_lamp),
    ]

    root_obj = objs[0]
    for ob in objs[1:]:
        ob.parent = root_obj

    tri_counts = {}
    for ob in objs:
        ob.data.calc_loop_triangles()
        tri_counts[ob.name] = len(ob.data.loop_triangles)
    total_tris = sum(tri_counts.values())

    glb_path = ROOT / "assets" / "models" / "fantasy_sub_mid.glb"
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_normals=True,
        export_vertex_color="ACTIVE",
        export_yup=True,
    )

    print("FANTASY_SUB_MID", glb_path, tri_counts, "TOTAL_TRIS:", total_tris)

    studio, camera, target = setup_studio(scene)

    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            view = area.spaces.active
            view.shading.color_type = "VERTEX"
            view.overlay.show_overlays = False
            view.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            view.region_3d.view_location = target
            view.region_3d.view_distance = 75.0
            view.region_3d.view_perspective = "ORTHO"

    bpy.context.preferences.filepaths.save_version = 0
    blend_path = ROOT / "art" / "fantasy_sub_mid.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

    preview_path = ROOT / "art" / "fantasy_sub_mid_preview.png"
    scene.render.filepath = str(preview_path)
    bpy.ops.render.render(write_still=True)

    if "--views" in sys.argv:
        idx = sys.argv.index("--views")
        if idx + 1 < len(sys.argv):
            out_dir = Path(sys.argv[idx + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            scene.render.resolution_x, scene.render.resolution_y = 1100, 620
            scene.cycles.samples = 28
            views = [
                ("profile_port", Vector((75.0, 0.0, 1.5)), Vector((0.0, 0.0, 1.4)), 64.0),
                ("ref_match", Vector((68.0, -24.0, 5.0)), Vector((0.0, -0.5, 1.3)), 62.0),
                ("stern_stbd", Vector((-54.0, 44.0, 18.0)), Vector((0.0, 1.0, 1.5)), 62.0),
                ("top_down", Vector((0.0, -0.1, 80.0)), Vector((0.0, 0.0, 0.0)), 64.0),
                ("bow_closeup", Vector((28.0, -30.0, 10.0)), Vector((0.0, -9.0, 2.4)), 30.0),
                ("aft_closeup", Vector((30.0, 14.0, 5.0)), Vector((0.0, 17.0, 1.2)), 26.0),
            ]
            for vname, offset, vt, oscale in views:
                camera.location = vt + offset
                camera.rotation_euler = (vt - camera.location).to_track_quat("-Z", "Y").to_euler()
                camera.data.ortho_scale = oscale
                scene.render.filepath = str(out_dir / f"{vname}.png")
                bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
