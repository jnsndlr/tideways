"""Build the Kitsap Fast Ferries M/V Finest passenger-only catamaran ferry.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender -b -noaudio --factory-startup -P art/fast_ferry_mid.py

Exports:
    assets/models/fast_ferry_mid.glb   (glTF, +Y up, +Z forward, vertex colours)
    art/fast_ferry.blend               (editable source + preview studio)
    art/fast_ferry_preview.png         (studio preview on harbour water)

Real-world dimensions (metres):
    LOA 38.0 m (x: -19.0 stern to +19.0 bow), Beam 10.0 m (y: -5.0 stbd to +5.0 port),
    waterline at z = 0.0. Working frame is (x=bow, y=port, z=up); mapped to Blender
    (y, -x, z) so glTF export (+Y up) puts +Z forward and +Y up.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
TAU = math.tau

# Palette tuned to Kitsap Fast Ferries M/V Finest under Tideways lighting.
WHITE = "eef1f0"
OFFWHITE = "dce2e2"
SILVER = "bfc9cc"
TEAL = "0d6e89"
TEAL_DARK = "09576e"
BOOT = "22282c"
ANTIFOUL = "171c1f"
RUBBER = "1d2125"
DECK = "4a5258"
DECK_DARK = "383f45"
ORANGE = "e04a1b"
ORANGE_HI = "ec5c2c"
ORANGE_DARK = "be3a12"
GLASS = "18242c"
GLASS_BRIDGE = "131e26"
PANE_FROST = "b4bec2"
STEEL = "6d767a"
IRON = "3a4247"
RED = "b82b24"
GREEN = "1c7d48"
AMBER = "e69b1e"
LAMP = "f7f4dc"
BLUE_FLAG = "1e3b70"


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


class Part:
    """Flat-shaded vertex-coloured mesh builder in (bow, port, up) coordinates."""

    def __init__(self, name):
        self.name = name
        self.vertices = []
        self.faces = []
        self.colors = []

    def vertex(self, point):
        self.vertices.append(blender_point(point))
        return len(self.vertices) - 1

    def face(self, indices, color):
        clean = [indices[0]]
        for idx in indices[1:]:
            if idx != clean[-1]:
                clean.append(idx)
        if len(clean) > 2 and clean[0] == clean[-1]:
            clean.pop()
        if len(clean) >= 3:
            self.faces.append(tuple(clean))
            self.colors.append(color)

    def quad(self, p0, p1, p2, p3, color):
        self.face([self.vertex(p) for p in (p0, p1, p2, p3)], color)

    def poly(self, pts, color):
        self.face([self.vertex(p) for p in pts], color)

    def loft(self, rings, color, top=None, bottom=None, close=False, caps=True):
        rows = [[self.vertex(p) for p in ring] for ring in rings]
        n = len(rows[0])
        m = len(rows) if close else len(rows) - 1
        for j in range(m):
            a, b = rows[j], rows[(j + 1) % len(rows)]
            for i in range(n):
                k = (i + 1) % n
                c = color(j, i) if callable(color) else color
                self.face((a[i], a[k], b[k], b[i]), c)
        if caps and not close:
            c0 = bottom if bottom is not None else (top if top is not None else (color(0, 0) if callable(color) else color))
            c1 = top if top is not None else (color(max(0, m - 1), 0) if callable(color) else color)
            self.face(rows[0][::-1], c0)
            self.face(rows[-1], c1)

    def finish(self, collection, material):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        cl = bm.loops.layers.color.new("Col")
        bm.faces.ensure_lookup_table()
        for f, code in zip(bm.faces, self.colors):
            f.smooth = False
            rgb = bytes.fromhex(code)
            rgba = (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)
            for loop in f.loops:
                loop[cl] = rgba
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        mesh.color_attributes.active_color_name = "Col"
        mesh.color_attributes.render_color_index = 0
        mesh.materials.append(material)
        obj = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(obj)
        return obj


def rect(cx, cy, z, length, width, corner=0.0):
    a, b = length / 2.0, width / 2.0
    if corner > 0.0:
        c = min(corner, a * 0.9, b * 0.9)
        outline = [
            (-a + c, -b), (a - c, -b), (a, -b + c), (a, b - c),
            (a - c, b), (-a + c, b), (-a, b - c), (-a, -b + c),
        ]
    else:
        outline = [(-a, -b), (a, -b), (a, b), (-a, b)]
    return [(cx + x, cy + y, z) for x, y in outline]


def block(part, x, y, bottom, length, width, height, color, corner=0.0, top=None):
    part.loft(
        [rect(x, y, z, length, width, corner) for z in (bottom, bottom + height)],
        color,
        top=top or color,
        bottom=color,
    )


def round_ring(c, axis, radius, count):
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    v = axis.cross(u)
    return [
        tuple(Vector(c) + radius * (u * math.cos(TAU * i / count) + v * math.sin(TAU * i / count)))
        for i in range(count)
    ]


def pipe(part, a, b, radius, color, count=8, tip=None):
    axis = Vector(b) - Vector(a)
    if axis.length < 1e-6:
        return
    part.loft(
        [round_ring(a, axis, radius, count), round_ring(b, axis, radius if tip is None else tip, count)],
        color,
    )


def annulus(part, c, axis, radius, bore, width, color, end=None, count=16):
    axis = Vector(axis).normalized()
    lo, hi = Vector(c) - axis * width / 2.0, Vector(c) + axis * width / 2.0
    rings = [round_ring(p, axis, r, count) for p, r in ((lo, radius), (hi, radius), (hi, bore), (lo, bore))]
    part.loft(rings, lambda row, i: (end or color) if row in (1, 3) else color, close=True)


def tapered_plate_y(part, profile_xz, y_center, thickness, color):
    """Extrude a 2D (x, z) CCW polygon in thickness along Y."""
    y0, y1 = y_center - thickness / 2.0, y_center + thickness / 2.0
    part.loft([[(x, y, z) for x, z in reversed(profile_xz)] for y in (y0, y1)], color)


def railing_run(part, points, height=1.05, bars=3, post_step=1.55, color=WHITE, post_r=0.032, rail_r=0.026):
    """Draw a clean marine pipe guardrail along a 3D polyline."""
    if len(points) < 2:
        return
    posts = [Vector(points[0])]
    for a, b in zip(points, points[1:]):
        va, vb = Vector(a), Vector(b)
        seg = (vb - va).length
        n = max(1, int(round(seg / post_step)))
        for k in range(1, n + 1):
            posts.append(va.lerp(vb, k / n))
    for p in posts:
        pipe(part, (p.x, p.y, p.z), (p.x, p.y, p.z + height), post_r, color, 6)
    for a, b in zip(points, points[1:]):
        for bi in range(1, bars + 1):
            h = height * (bi / bars)
            r = rail_r * (1.2 if bi == bars else 0.85)
            pipe(part, (a[0], a[1], a[2] + h), (b[0], b[1], b[2] + h), r, color, 6)


# ---------------------------------------------------------------------------
# Hull Geometry & Kitsap Fast Ferries Sweeping Wave Livery
# ---------------------------------------------------------------------------

def hull_sheer_z(x):
    """Main deck / rub-rail sheer height along the 38 m hull (matches Photo 1)."""
    t = clamp((x + 18.6) / 37.5, 0.0, 1.0)
    return 1.92 + 0.22 * (t ** 2.0) + 0.14 * smoothstep(11.0, 18.9, x)


def hull_boot_z(x):
    """Top of dark charcoal waterline boot."""
    return 0.44 + 0.16 * smoothstep(8.0, 17.5, x)


def hull_keel_z(x):
    """Demihull keel profile with a true ~45 deg raked wave-piercing bow stem (Photo 1 & 3)."""
    if x < -14.5:
        return lerp(-0.78, -1.28, smoothstep(-18.6, -14.5, x))
    if x > 14.2:
        # Clean raked wave-piercing stem from waterline entry (x=15.9, z=0) up to bow knuckle (x=18.85, z=2.12)
        t = clamp((x - 14.2) / (18.85 - 14.2), 0.0, 1.0)
        return lerp(-1.28, 2.12, t ** 1.12)
    return -1.28


def demihull_y_bounds(x, z):
    """Return (y_inner, y_outer) for the port (+Y) demihull at station x and height z."""
    if x <= -15.0:
        t = smoothstep(-18.6, -15.0, x)
        y_out_top = lerp(4.78, 4.96, t)
        y_in_top = lerp(2.70, 2.56, t)
    elif x <= 6.0:
        y_out_top = 4.96
        y_in_top = 2.56
    else:
        t = clamp((x - 6.0) / 12.85, 0.0, 1.0)
        z_flare = clamp((z - 0.0) / 2.2, 0.0, 1.0)
        y_out_top = lerp(4.96, lerp(3.78, 4.32, z_flare), t ** 1.60)
        y_in_top = lerp(2.56, 3.68, t ** 1.40)

    kz = hull_keel_z(x)
    y_center = 0.5 * (y_out_top + y_in_top)
    zs = hull_sheer_z(x)
    if z <= kz + 0.03:
        return y_center - 0.05, y_center + 0.05

    chine_z = clamp(-0.20 + 0.55 * smoothstep(9.0, 17.0, x), kz + 0.05, zs - 0.12)
    if z < chine_z:
        ft = clamp((z - kz) / max(0.05, chine_z - kz), 0.0, 1.0)
        y_in = lerp(y_center - 0.06, y_in_top + 0.15, ft ** 0.78)
        y_out = lerp(y_center + 0.06, y_out_top - 0.20, ft ** 0.78)
        return y_in, y_out
    else:
        ft = clamp((z - chine_z) / max(0.15, zs - chine_z), 0.0, 1.0)
        y_in = lerp(y_in_top + 0.15, y_in_top, ft)
        y_out = lerp(y_out_top - 0.20, y_out_top, ft)
        if y_out - y_in < 0.12:
            mid = 0.5 * (y_in + y_out)
            return mid - 0.06, mid + 0.06
        return y_in, y_out


def livery_band_heights(x):
    """Return ordered list of heights [z0..z4] strictly within [z_low, z_sheer] and 4 band colours
    tracing the unmistakable Kitsap Fast Ferries sweeping wave livery (Photo 1 & 4).
    """
    kz = hull_keel_z(x)
    zs = hull_sheer_z(x)
    zb = max(hull_boot_z(x), kz + 0.03)
    zb = min(zb, zs - 0.08)
    span = max(0.08, zs - zb)

    u = clamp((x + 18.6) / 37.45, 0.0, 1.0)

    if u >= 0.62:
        # Forward wave section (u=0.62..1.00, x ~ +4.6..+18.85):
        # Sweeping silver & white lower crescent arching from bow down into the midship splash trough,
        # beneath a bold sweeping Kitsap teal upper bow wave!
        s = (u - 0.62) / 0.38
        f1 = 0.28 * math.sin(math.pi * clamp(s * 1.04, 0.0, 1.0)) ** 0.95
        f2 = 0.48 * math.sin(math.pi * clamp(s * 1.08, 0.0, 1.0)) ** 0.85 + 0.06 * s
        # Near the splash trough (s < 0.15), white sweeps cleanly upward separating forward & aft waves!
        f3 = 0.96 - 0.30 * ((1.0 - s) ** 2.4)
        f3 = max(f3, f2 + 0.05)
        zs_list = [
            zb,
            zb + span * clamp(f1, 0.02, 0.82),
            zb + span * clamp(max(f2, f1 + 0.03), 0.06, 0.88),
            zb + span * clamp(f3, 0.12, 0.96),
            zs,
        ]
        cols = [SILVER, WHITE, TEAL, TEAL_DARK if s > 0.22 else WHITE]
        return zs_list, cols
    else:
        # Aft & midship wave section (u=0..0.62, stern to wave crest):
        # Sharp curling teal wave crest at u=0.61 plunging down into a crisp white negative-space arch
        # around u=0.44, then sweeping high into the aft teal quarter, sliced by two white/silver wake arcs!
        s = u / 0.62
        # Lower wake ribbon (silver) arching toward stern
        f1 = 0.26 * math.sin(math.pi * clamp((0.46 - s) / 0.46, 0.0, 1.0)) ** 0.9 if s < 0.46 else 0.02
        # Upper wake ribbon (white) curving above silver toward stern
        f2 = 0.44 * math.sin(math.pi * clamp((0.50 - s) / 0.50, 0.0, 1.0)) ** 0.85 if s < 0.50 else 0.04
        # Upper teal wave boundary
        if s > 0.78:
            # Steep crashing wave crest curling right up to the sheer!
            t_cr = (s - 0.78) / 0.22
            f3 = lerp(0.50, 0.97, t_cr ** 1.35)
        elif s > 0.25:
            # Graceful white arch dipping to ~0.46 mid-aft and rising smoothly aft
            t_mid = (s - 0.25) / 0.53
            f3 = lerp(0.97, 0.50, math.sin(0.5 * math.pi * t_mid) ** 0.95)
        else:
            f3 = lerp(0.84, 0.97, s / 0.25)
        f3 = max(f3, f2 + 0.06)
        zs_list = [
            zb,
            zb + span * clamp(f1, 0.02, 0.80),
            zb + span * clamp(max(f2, f1 + 0.02), 0.04, 0.86),
            zb + span * clamp(f3, 0.12, 0.97),
            zs,
        ]
        cols = [SILVER if f1 > 0.03 else TEAL, WHITE if f2 > 0.05 else TEAL, TEAL, WHITE]
        return zs_list, cols


def build_hulls():
    """Twin aluminum catamaran demihulls with raked wave-piercing bows, sweeping wave livery,
    wetdeck tunnel arch, curved bow boarding apron, heavy black rub rails & stern waterjets.
    """
    hull = Part("Hull")

    xs = sorted(set([
        -18.6, -18.0, -17.0, -16.0, -15.0, -14.0, -12.8, -11.5, -10.0, -8.5,
        -7.0, -5.5, -4.0, -2.5, -1.0, 0.5, 2.0, 3.2, 4.1, 4.65, 5.1, 6.0,
        7.5, 9.0, 10.5, 12.0, 13.4, 14.4, 15.2, 16.0, 16.8, 17.5, 18.1, 18.55, 18.85,
    ]))

    for side in (1, -1):
        rings = []
        ring_cols = []
        for x in xs:
            kz = hull_keel_z(x)
            zs = hull_sheer_z(x)
            zb = clamp(hull_boot_z(x), kz + 0.03, zs - 0.08)
            z_chine = clamp(-0.20 + 0.55 * smoothstep(9.0, 17.0, x), kz + 0.015, zb - 0.015)
            z_tunnel = clamp(1.22, zb + 0.02, zs - 0.06)

            yi_k, yo_k = demihull_y_bounds(x, kz)
            yi_c, yo_c = demihull_y_bounds(x, z_chine)
            yi_b, _ = demihull_y_bounds(x, zb)
            yi_t, _ = demihull_y_bounds(x, z_tunnel)
            yi_s, _ = demihull_y_bounds(x, zs)

            z_bands, band_cols = livery_band_heights(x)
            outer_pts = []
            for zb_i in z_bands:
                _, yo_i = demihull_y_bounds(x, zb_i)
                outer_pts.append((x, side * yo_i, zb_i))

            # If keel has risen above the normal waterline boot (forward of stem entry), paint lower bevel teal/boot cleanly
            bow_boot = TEAL if kz > 0.55 else BOOT
            bow_anti = BOOT if kz > 0.35 else ANTIFOUL

            pts = [
                (x, side * (0.5 * (yi_k + yo_k)), kz),
                (x, side * yo_c, z_chine),
                outer_pts[0],
                outer_pts[1],
                outer_pts[2],
                outer_pts[3],
                outer_pts[4],
                (x, side * yi_s, zs),
                (x, side * yi_t, z_tunnel),
                (x, side * yi_b, zb),
                (x, side * yi_c, z_chine),
            ]
            seg_cols_port = [
                bow_anti,
                bow_boot,
                band_cols[0],
                band_cols[1],
                band_cols[2],
                band_cols[3],
                DECK,
                OFFWHITE,
                OFFWHITE,
                bow_boot,
                bow_anti,
            ]
            if side == -1:
                pts = pts[::-1]
                n_pts = len(seg_cols_port)
                seg_cols = [seg_cols_port[(n_pts - 2 - i) % n_pts] for i in range(n_pts)]
            else:
                seg_cols = seg_cols_port
            rings.append(pts)
            ring_cols.append(seg_cols)

        hull.loft(
            rings,
            lambda j, i, rc=ring_cols: rc[j][i],
            top=WHITE,
            bottom=TEAL_DARK,
        )

    # --- Wetdeck cross-structure & overhanging rounded bow apron (Photo 3 & 5) ---
    wet_xs = [-18.55, -14.0, -6.0, 2.0, 10.0, 14.5, 16.5, 17.6, 18.3, 18.82]
    wet_rings = []
    for x in wet_xs:
        zs = hull_sheer_z(x)
        _, yo = demihull_y_bounds(x, zs)
        yi, _ = demihull_y_bounds(x, 1.25)
        if x > 15.8:
            t_bow = clamp((x - 15.8) / 3.02, 0.0, 1.0)
            y_edge = lerp(yo - 0.04, 2.30, t_bow ** 1.75)
            y_chamf = y_edge * 0.86
            z_bot = lerp(1.36, 1.88, t_bow ** 1.35)
        else:
            y_edge = yi + 0.35
            y_chamf = max(0.5, yi - 0.18)
            z_bot = 1.36
        ring = [
            (x, -y_chamf, z_bot),
            (x, y_chamf, z_bot),
            (x, y_edge, z_bot + 0.34),
            (x, y_edge, zs),
            (x, -y_edge, zs),
            (x, -y_edge, z_bot + 0.34),
        ]
        wet_rings.append(ring)
    hull.loft(
        wet_rings,
        lambda j, i: [OFFWHITE, OFFWHITE, WHITE, DECK, WHITE, OFFWHITE][i],
        top=WHITE,
        bottom=TEAL_DARK,
    )

    # --- Heavy Black Rubber Rub Rail & Curved Bow Fender ---
    for side in (1, -1):
        rail_pts = []
        for x in [-14.2, -10.0, -4.0, 2.0, 8.0, 13.5, 16.5, 17.9, 18.65]:
            zs = hull_sheer_z(x)
            _, yo = demihull_y_bounds(x, zs)
            rail_pts.append((x, side * (yo + 0.04), zs - 0.06))
        for a, b in zip(rail_pts, rail_pts[1:]):
            pipe(hull, a, b, 0.115, RUBBER, 8)
        # Subtle lower fender trim along stern quarter
        st_pts = []
        for x in [-18.55, -16.5, -14.2]:
            zs = hull_sheer_z(x)
            _, yo = demihull_y_bounds(x, zs)
            st_pts.append((x, side * (yo + 0.035), zs - 0.06))
        for a, b in zip(st_pts, st_pts[1:]):
            pipe(hull, a, b, 0.075, RUBBER, 6)

    # Curved black bow D-fender spanning across the overhanging bow deck
    bow_fender = []
    n_bow = 14
    for i in range(n_bow + 1):
        ang = lerp(-math.pi * 0.44, math.pi * 0.44, i / n_bow)
        bx = 18.52 + 0.48 * math.cos(ang)
        by = 4.28 * math.sin(ang)
        bz = hull_sheer_z(min(bx, 18.85)) - 0.02
        bow_fender.append((bx, by, bz))
    for a, b in zip(bow_fender, bow_fender[1:]):
        pipe(hull, a, b, 0.13, RUBBER, 8)

    # --- Stern Twin Waterjet Nozzles & Protective Aluminum Jet-Guard Cages ---
    for side in (1, -1):
        yc = side * 3.74
        pipe(hull, (-18.55, yc, 0.06), (-19.38, yc, 0.10), 0.36, IRON, 10, tip=0.26)
        block(hull, -19.24, yc, -0.18, 0.52, 0.76, 0.56, STEEL, 0.08)
        for dy in (-0.66, 0.66):
            pipe(hull, (-18.6, yc + dy, 0.78), (-19.68, yc + dy * 0.85, 0.22), 0.055, SILVER, 6)
            pipe(hull, (-18.6, yc + dy, -0.14), (-19.68, yc + dy * 0.85, 0.22), 0.055, SILVER, 6)
        pipe(hull, (-19.68, yc - 0.56, 0.22), (-19.68, yc + 0.56, 0.22), 0.06, SILVER, 6)

    return hull


# ---------------------------------------------------------------------------
# Main Passenger Cabin, Aerodynamic Forward Brow & Aft Deck Alcove
# ---------------------------------------------------------------------------

def main_cabin_width(x, z):
    """Outer half-width of the main superstructure at (x, z)."""
    t_z = clamp((z - 2.05) / 2.95, 0.0, 1.0)
    base_hw = lerp(4.86, 4.62, t_z)
    if x > 9.5:
        t_bow = clamp((x - 9.5) / 8.5, 0.0, 1.0)
        base_hw = lerp(base_hw, lerp(4.36, 3.88, t_z), t_bow ** 1.55)
    elif x < -13.0:
        t_st = clamp((-13.0 - x) / 5.5, 0.0, 1.0)
        base_hw = lerp(base_hw, 4.66, t_st)
    return base_hw


def brow_top_z(x):
    """Height of the sweeping aerodynamic forward brow/cheeks (x from +10.0 to +17.9)."""
    if x <= 10.0:
        return 4.95
    if x >= 17.9:
        return 2.25
    t = (x - 10.0) / 7.9
    return 4.95 - 2.70 * (t ** 1.72)


def build_main_cabin(glass_part, lamp_part):
    """Main passenger cabin, 19-bay side window band, Kitsap wave skirt accents,
    sculpted aerodynamic bow cheeks & brow, bow double doors, and aft deck alcove.
    """
    cab = Part("MainCabin")

    # 1. Main cabin shell (x from -11.8 to +12.6, z from 2.02 to 4.95)
    cab_xs = [-11.8, -10.5, -7.0, -2.0, 4.0, 9.5, 11.2, 12.6]
    core_rings = []
    for x in cab_xs:
        z_bot = hull_sheer_z(x) - 0.05
        z_top = min(4.95, brow_top_z(x))
        hw_bot = main_cabin_width(x, z_bot)
        hw_top = main_cabin_width(x, z_top)
        core_rings.append([
            (x, -hw_bot, z_bot),
            (x, hw_bot, z_bot),
            (x, hw_top, z_top),
            (x, -hw_top, z_top),
        ])
    cab.loft(core_rings, lambda j, i: [DECK, WHITE, DECK, WHITE][i], top=WHITE, bottom=WHITE)

    # 2. Above-rub-rail Teal Wave Accents on Lower Main Cabin Skirt (Photo 1)
    for side in (1, -1):
        # Forward slim teal wave crest where "FINEST" sits (x: +7.5 to +18.0)
        fw_xs = [7.5, 9.5, 11.5, 13.5, 15.5, 17.0, 18.0]
        fw_lo, fw_hi = [], []
        for x in fw_xs:
            zs = hull_sheer_z(x)
            t = (x - 7.5) / 10.5
            h_wave = 0.44 * math.sin(math.pi * clamp(t * 0.96, 0.0, 1.0)) ** 0.85
            _, yo = demihull_y_bounds(x, zs)
            y_s = side * (min(yo, main_cabin_width(x, zs + 0.1)) + 0.025)
            fw_lo.append((x, y_s, zs - 0.02))
            fw_hi.append((x, y_s, zs + max(0.05, h_wave)))
        for a0, a1, b1, b0 in zip(fw_lo, fw_lo[1:], fw_hi[1:], fw_hi):
            if side == 1:
                cab.quad(a0, a1, b1, b0, TEAL)
            else:
                cab.quad(a1, a0, b0, b1, TEAL)

        # Aft sweeping teal wave rising boldly above rub rail (x: -18.2 to -5.5)
        aw_xs = [-18.2, -16.8, -15.2, -13.6, -12.0, -10.4, -8.8, -7.2, -5.5]
        aw_lo, aw_hi = [], []
        for x in aw_xs:
            zs = hull_sheer_z(x)
            t = (x + 18.2) / 12.7
            h_wave = 0.86 * math.sin(math.pi * clamp(t, 0.0, 1.0)) ** 1.05
            y_s = side * (main_cabin_width(x, zs + 0.3) + 0.025)
            aw_lo.append((x, y_s, zs - 0.02))
            aw_hi.append((x, y_s, zs + max(0.04, h_wave)))
        for a0, a1, b1, b0 in zip(aw_lo, aw_lo[1:], aw_hi[1:], aw_hi):
            if side == 1:
                cab.quad(a0, a1, b1, b0, TEAL)
            else:
                cab.quad(a1, a0, b0, b1, TEAL)

        # Stylized Kitsap Fast Ferries color mark on white upper frieze (x ~ +0.4, z ~ 4.52)
        y_logo = side * (main_cabin_width(0.4, 4.52) + 0.025)
        annulus(cab, (0.35, y_logo, 4.52), (0, side, 0), 0.24, 0.06, 0.02, ORANGE, count=14)
        block(cab, 1.45, y_logo, 4.42, 1.42, 0.025, 0.20, TEAL)
        block(cab, -1.05, y_logo, 4.43, 1.82, 0.025, 0.17, ORANGE)

    # 3. Main Cabin Side Windows (19 bays: 1 forward frosted + 18 dark tinted, z=2.96..4.02)
    win_x_start = 11.45
    win_x_end = -10.85
    n_bays = 19
    bay_len = (win_x_start - win_x_end) / n_bays
    mullion_w = 0.18
    win_z0, win_z1 = 2.98, 4.04

    for side in (1, -1):
        for i in range(n_bays):
            x1 = win_x_start - i * bay_len - mullion_w * 0.5
            x0 = win_x_start - (i + 1) * bay_len + mullion_w * 0.5
            xc = 0.5 * (x0 + x1)
            y0 = side * (main_cabin_width(xc, win_z0) + 0.024)
            y1 = side * (main_cabin_width(xc, win_z1) + 0.024)
            p0, p1, p2, p3 = (x0, y0, win_z0), (x1, y0, win_z0), (x1, y1, win_z1), (x0, y1, win_z1)
            if i == 0:
                if side == 1:
                    cab.quad(p0, p1, p2, p3, PANE_FROST)
                else:
                    cab.quad(p1, p0, p3, p2, PANE_FROST)
            else:
                if side == 1:
                    glass_part.quad(p0, p1, p2, p3, GLASS)
                else:
                    glass_part.quad(p1, p0, p3, p2, GLASS)
            for za, zb_e, ya, yb_e in ((win_z0, win_z0 + 0.038, y0, y0), (win_z1 - 0.038, win_z1, y1, y1)):
                q0 = (x0, ya + side * 0.008, za)
                q1 = (x1, ya + side * 0.008, za)
                q2 = (x1, yb_e + side * 0.008, zb_e)
                q3 = (x0, yb_e + side * 0.008, zb_e)
                if side == 1:
                    cab.quad(q0, q1, q2, q3, RUBBER)
                else:
                    cab.quad(q1, q0, q3, q2, RUBBER)

    # 4. Sculpted Forward Aerodynamic Brow & Side Cheeks (Photos 1, 2, 3, 5)
    cheek_xs = [10.0, 11.2, 12.5, 13.8, 15.0, 16.1, 17.0, 17.85]
    for side in (1, -1):
        cheek_rings = []
        for x in cheek_xs:
            zt = brow_top_z(x)
            zb = hull_sheer_z(x) - 0.04
            zt = max(zt, zb + 0.14)
            y_out_b = main_cabin_width(x, zb)
            y_out_t = main_cabin_width(x, zt)
            t_open = smoothstep(12.2, 16.5, x)
            y_in_b = lerp(3.45, y_out_b - 0.34, t_open)
            y_in_t = lerp(3.22, y_out_t - 0.30, t_open)
            pts = [
                (x, side * y_in_b, zb),
                (x, side * y_out_b, zb),
                (x, side * y_out_t, zt),
                (x, side * y_in_t, zt),
            ]
            if side == -1:
                pts = pts[::-1]
            cheek_rings.append(pts)
        cab.loft(cheek_rings, WHITE, top=WHITE, bottom=WHITE)

    # Sloped upper foredeck roof hood arching from pilothouse base over bow bulkhead
    hood_xs = [10.0, 11.0, 12.0, 13.0, 13.7]
    hood_rings = []
    for x in hood_xs:
        zt = brow_top_z(x)
        zb = zt - 0.32
        hw = main_cabin_width(x, zt) - 0.10
        hood_rings.append([
            (x, -hw, zb),
            (x, 0.0, zb + 0.10),
            (x, hw, zb),
            (x, hw, zt),
            (x, 0.0, zt + 0.12),
            (x, -hw, zt),
        ])
    cab.loft(hood_rings, WHITE, top=WHITE, bottom=WHITE)

    # Recessed center bow bulkhead & double-leaf passenger boarding doors (Photo 3 & 5)
    z_bow_deck = hull_sheer_z(15.0)
    block(cab, 12.65, 0.0, z_bow_deck - 0.08, 0.30, 2.55, 2.02, WHITE)
    block(cab, 12.82, 0.0, z_bow_deck - 0.04, 0.08, 1.92, 1.94, OFFWHITE)
    for dy in (-0.45, 0.45):
        block(glass_part, 12.87, dy, z_bow_deck + 0.80, 0.04, 0.70, 0.96, GLASS)
        block(cab, 12.86, dy, z_bow_deck + 0.02, 0.04, 0.74, 0.70, SILVER)
        pipe(cab, (12.90, dy * 0.20, z_bow_deck + 0.68), (12.90, dy * 0.20, z_bow_deck + 1.12), 0.022, STEEL, 6)

    # Flanking sloped white wind-cowlings beside the bow doorway (Photo 3 & 5)
    for side in (1, -1):
        cowling_rings = []
        for y_frac in (0.0, 1.0):
            y = side * lerp(1.18, 3.45, y_frac)
            x_bot = lerp(14.95, 15.25, y_frac)
            x_top = lerp(13.30, 13.55, y_frac)
            z_top = lerp(z_bow_deck + 1.85, brow_top_z(x_top) - 0.04, y_frac)
            ring = [
                (12.50, y, z_bow_deck - 0.08),
                (x_bot, y, z_bow_deck - 0.08),
                (x_top, y, z_top),
                (12.50, y, z_top),
            ]
            if side == 1:
                ring = ring[::-1]
            cowling_rings.append(ring)
        cab.loft(cowling_rings, WHITE, top=WHITE, bottom=WHITE)

    # Two sleek white bow floodlight pods on the curved forward brow (Photo 3)
    for side in (1, -1):
        zf = brow_top_z(13.35) - 0.08
        block(cab, 13.35, side * 2.55, zf, 0.56, 0.42, 0.20, WHITE, 0.05)
        block(lamp_part, 13.64, side * 2.55, zf + 0.04, 0.04, 0.28, 0.12, LAMP)

    # 5. Aft Main Deck Alcove, Sloped Rear Structural Strut & Stern Bulwark (Photo 1 & 4)
    z_aft_deck = hull_sheer_z(-15.5)
    for side in (1, -1):
        # Clean non-self-intersecting CCW trapezoid sloping aft-downward behind the aft alcove!
        # Bottom: (-15.7, 2.75) -> (-14.7, 2.75), Top: (-13.0, 4.95) -> (-14.0, 4.95)
        # Check CCW order in (x, z): bottom-left -> bottom-right -> top-right -> top-left!
        tapered_plate_y(
            cab,
            [(-15.9, z_aft_deck + 0.72), (-14.9, z_aft_deck + 0.72), (-13.1, 4.95), (-14.0, 4.95)],
            side * 4.56,
            0.26,
            WHITE,
        )
        # Recessed inner aft bulkhead cheek (solid white backing behind the orange life ring, Photo 1!)
        tapered_plate_y(
            cab,
            [(-15.4, z_aft_deck + 0.65), (-11.75, z_aft_deck + 0.65), (-11.75, 4.95), (-13.6, 4.95)],
            side * 4.18,
            0.24,
            OFFWHITE,
        )
        # Solid lower aft side bulwark running from main cabin back to stern transom
        tapered_plate_y(
            cab,
            [(-18.55, z_aft_deck - 0.05), (-11.75, z_aft_deck - 0.05), (-11.75, z_aft_deck + 0.78), (-18.55, z_aft_deck + 0.78)],
            side * 4.66,
            0.24,
            WHITE,
        )

    # Aft deck floor & stern transom bulwark
    block(cab, -15.2, 0.0, z_aft_deck - 0.14, 6.8, 9.1, 0.16, DECK)
    block(cab, -18.45, 0.0, z_aft_deck - 0.05, 0.26, 9.25, 0.84, WHITE)
    # Aft cabin bulkhead doors (visible looking into aft alcove)
    block(cab, -11.86, 0.0, z_aft_deck + 0.02, 0.12, 2.20, 2.00, OFFWHITE)
    for dy in (-0.52, 0.52):
        block(glass_part, -11.92, dy, z_aft_deck + 0.92, 0.04, 0.72, 0.90, GLASS)

    return cab


# ---------------------------------------------------------------------------
# Signature Safety-Orange Pilothouse (Photos 1, 2, 3, 4, 5)
# ---------------------------------------------------------------------------

def build_pilothouse(glass_part, lamp_part):
    """Wide forward-raked Kitsap safety-orange bridge with wrap-around windshields,
    side bridge-wing doors, roof visor, navigation lights and aft black vent box.
    """
    ph = Part("Pilothouse")

    def nose_ring(z, x_front, x_back, hw_front, hw_back, chamf):
        return [
            (x_back, -hw_back, z),
            (x_front - chamf, -hw_front, z),
            (x_front, -hw_front + chamf, z),
            (x_front, hw_front - chamf, z),
            (x_front - chamf, hw_front, z),
            (x_back, hw_back, z),
        ]

    # Z levels aligned cleanly above main deck roof (z=4.95)
    z0, z_sill, z_head, z_roof = 4.86, 5.78, 6.88, 7.16

    r_base = nose_ring(z0, 10.65, 3.45, 3.18, 3.25, 0.55)
    r_sill = nose_ring(z_sill, 8.28, 3.45, 2.95, 3.16, 0.62)
    r_head = nose_ring(z_head, 7.42, 3.45, 2.75, 3.04, 0.56)
    r_roof = nose_ring(z_roof, 7.64, 3.45, 2.86, 3.12, 0.58)

    # Lower sloped orange apron & body
    ph.loft([r_base, r_sill], ORANGE, top=ORANGE_HI, bottom=ORANGE_DARK)

    # Recessed dark core behind glazing (strictly inset by 0.14 m so corner glass NEVER clips!)
    r_core_lo = nose_ring(z_sill, 8.12, 3.45, 2.78, 3.04, 0.58)
    r_core_hi = nose_ring(z_head, 7.26, 3.45, 2.58, 2.92, 0.52)
    ph.loft([r_core_lo, r_core_hi], GLASS_BRIDGE, top=ORANGE_HI, bottom=ORANGE_DARK)

    # Orange roof visor cap with light grey top deck
    ph.loft([r_head, r_roof], ORANGE, top=OFFWHITE, bottom=ORANGE_DARK)

    # 2. Wrap-around faceted raked front & corner windshields + orange mullions
    # Match exact vertex coordinates of r_sill and r_head so panes & mullions lie perfectly flush!
    # r_sill front edge: x=8.28, y in [-2.33, +2.33]; corner chamfer goes from (8.28, ±2.33) to (7.66, ±2.95)
    # r_head front edge: x=7.42, y in [-2.19, +2.19]; corner chamfer goes from (7.42, ±2.19) to (6.86, ±2.75)
    front_y_lo = [-2.33, -0.80, 0.80, 2.33]
    front_y_hi = [-2.19, -0.75, 0.75, 2.19]

    for ylo, yhi in zip(front_y_lo, front_y_hi):
        pipe(ph, (8.28, ylo, z_sill - 0.02), (7.42, yhi, z_head + 0.02), 0.072, ORANGE, 6)

    # 3 wide front dark glass panes
    for i in range(3):
        p0 = (8.25, front_y_lo[i] + 0.04, z_sill + 0.02)
        p1 = (8.25, front_y_lo[i + 1] - 0.04, z_sill + 0.02)
        p2 = (7.39, front_y_hi[i + 1] - 0.04, z_head - 0.02)
        p3 = (7.39, front_y_hi[i] + 0.04, z_head - 0.02)
        glass_part.quad(p0, p1, p2, p3, GLASS_BRIDGE)
        ym = 0.5 * (front_y_lo[i] + front_y_lo[i + 1])
        pipe(ph, (8.20, ym - 0.08, z_sill + 0.14), (7.94, ym + 0.16, z_sill + 0.68), 0.018, RUBBER, 5)

    # Clean non-clipping corner chamfer glass & side bridge-wing panes
    for side in (1, -1):
        # Corner chamfer vertices matching r_sill/r_head exactly (slightly proud of recessed core)
        c0 = (8.24, side * 2.33, z_sill + 0.02)
        c1 = (7.64, side * 2.93, z_sill + 0.02)
        c2 = (6.84, side * 2.73, z_head - 0.02)
        c3 = (7.38, side * 2.19, z_head - 0.02)
        if side == 1:
            glass_part.quad(c0, c1, c2, c3, GLASS_BRIDGE)
        else:
            glass_part.quad(c1, c0, c3, c2, GLASS_BRIDGE)
        pipe(ph, (7.66, side * 2.95, z_sill - 0.02), (6.86, side * 2.75, z_head + 0.02), 0.078, ORANGE, 6)

        # Side forward bridge window (x from 5.65 to 7.64)
        s0 = (5.68, side * 3.04, z_sill + 0.02)
        s1 = (7.62, side * 2.94, z_sill + 0.02)
        s2 = (6.84, side * 2.75, z_head - 0.02)
        s3 = (5.68, side * 2.86, z_head - 0.02)
        if side == 1:
            glass_part.quad(s0, s1, s2, s3, GLASS_BRIDGE)
        else:
            glass_part.quad(s1, s0, s3, s2, GLASS_BRIDGE)

        # Orange aft bridge-wing pillar & recessed wing door (Photo 1 & 4)
        tapered_plate_y(
            ph,
            [(3.46, z_sill - 0.02), (5.72, z_sill - 0.02), (5.72, z_head + 0.02), (3.46, z_head + 0.02)],
            side * 2.98,
            0.22,
            ORANGE,
        )
        block(ph, 4.55, side * 3.08, z0 + 0.16, 0.88, 0.08, 1.72, IRON)
        block(glass_part, 4.55, side * 3.12, z_sill + 0.12, 0.56, 0.05, 0.64, GLASS)

        # Port (red) & Starboard (green) navigation sidelight housings on bridge wing cheeks
        nav_col = RED if side == 1 else GREEN
        block(ph, 6.10, side * 3.12, z0 + 0.50, 0.42, 0.14, 0.18, RUBBER, 0.03)
        block(lamp_part, 6.32, side * 3.14, z0 + 0.53, 0.05, 0.10, 0.12, nav_col)

    # Crisp white "Kitsap Transit" nameplate bar sitting 0.025 m PROUD of the orange sloped front nose!
    # Slope plane connects (10.65, z=4.86) to (8.28, z=5.78): normal points along (+0.92, 0, +2.37) -> normalized (+0.36, 0, +0.93)
    t_lo, t_hi = 0.44, 0.64
    x_lo = lerp(10.65, 8.28, t_lo) + 0.035
    z_lo = lerp(z0, z_sill, t_lo) + 0.035
    x_hi = lerp(10.65, 8.28, t_hi) + 0.035
    z_hi = lerp(z0, z_sill, t_hi) + 0.035
    ph.quad(
        (x_lo, -1.65, z_lo),
        (x_lo, 1.30, z_lo),
        (x_hi, 1.24, z_hi),
        (x_hi, -1.58, z_hi),
        WHITE,
    )
    # Small white Kitsap Transit circle badge at port end of the front nameplate (Photo 3)
    xm_b = 0.5 * (x_lo + x_hi) + 0.01
    zm_b = 0.5 * (z_lo + z_hi) + 0.01
    annulus(ph, (xm_b, 1.68, zm_b), (0.36, 0.0, 0.93), 0.17, 0.02, 0.03, WHITE, count=12)

    # Chunky black exhaust/vent housing sitting at aft port corner of bridge roof (Photos 1, 2, 3, 5!)
    block(ph, 3.92, 2.25, z_roof - 0.02, 0.88, 0.72, 0.88, RUBBER, 0.05)
    block(ph, 3.92, 2.25, z_roof + 0.86, 0.76, 0.60, 0.10, IRON, 0.03)

    return ph


# ---------------------------------------------------------------------------
# Upper Passenger Cabin, Aft Twin Raised Fins, Life Rafts & Sun Deck
# ---------------------------------------------------------------------------

def build_upper_deck(glass_part):
    """Upper passenger cabin, 10-bay side windows, aft swept-back twin fins,
    mid-roof fairing, aft open sun deck, and twin banks of 4 white life-raft canisters.
    """
    up = Part("UpperDeck")

    z_ud = 4.98
    z_uroof = 7.08

    # 1. Upper deck walk-around floor slab extending back over aft sun deck
    deck_rings = []
    for x, hw in [(-15.5, 4.46), (-11.5, 4.60), (4.0, 4.62), (9.8, 4.55)]:
        deck_rings.append([
            (x, -hw, z_ud - 0.14),
            (x, hw, z_ud - 0.14),
            (x, hw, z_ud),
            (x, -hw, z_ud),
        ])
    up.loft(deck_rings, lambda j, i: [WHITE, WHITE, DECK, WHITE][i], top=WHITE, bottom=WHITE)

    # 2. Upper passenger cabin body (raked aft wall from x=-11.6 at deck to x=-9.85 at roof)
    def upper_outline(z):
        t = clamp((z - z_ud) / (z_uroof - z_ud), 0.0, 1.0)
        x_fwd = 3.65
        x_aft = lerp(-11.60, -9.85, t)
        hw = lerp(3.68, 3.45, t)
        return [
            (x_aft, -hw, z),
            (x_fwd, -hw, z),
            (x_fwd, hw, z),
            (x_aft, hw, z),
        ]

    up.loft([upper_outline(z_ud), upper_outline(z_uroof)], WHITE, top=OFFWHITE, bottom=WHITE)
    block(up, -3.1, 0.0, z_uroof, 13.0, 6.5, 0.14, OFFWHITE, 0.25)

    # 3. Upper Cabin Side Windows (10 crisp dark bays + small aft bay, Photo 1 & 4)
    uwin_x1 = 3.25
    uwin_x0 = -7.25
    n_ubays = 10
    ubay = (uwin_x1 - uwin_x0) / n_ubays
    umul = 0.17
    uz0, uz1 = z_ud + 0.56, z_ud + 1.52

    for side in (1, -1):
        for i in range(n_ubays):
            xb = uwin_x1 - i * ubay - umul * 0.5
            xa = uwin_x1 - (i + 1) * ubay + umul * 0.5
            t0 = (uz0 - z_ud) / (z_uroof - z_ud)
            t1 = (uz1 - z_ud) / (z_uroof - z_ud)
            y0 = side * (lerp(3.68, 3.45, t0) + 0.025)
            y1 = side * (lerp(3.68, 3.45, t1) + 0.025)
            p0, p1, p2, p3 = (xa, y0, uz0), (xb, y0, uz0), (xb, y1, uz1), (xa, y1, uz1)
            if side == 1:
                glass_part.quad(p0, p1, p2, p3, GLASS)
            else:
                glass_part.quad(p1, p0, p3, p2, GLASS)
            for za, zb_e, ya, yb_e in ((uz0, uz0 + 0.035, y0, y0), (uz1 - 0.035, uz1, y1, y1)):
                q0, q1 = (xa, ya + side * 0.008, za), (xb, ya + side * 0.008, za)
                q2, q3 = (xb, yb_e + side * 0.008, zb_e), (xa, yb_e + side * 0.008, zb_e)
                if side == 1:
                    up.quad(q0, q1, q2, q3, RUBBER)
                else:
                    up.quad(q1, q0, q3, q2, RUBBER)

        # Small aft upper cabin side window (Photo 4)
        t0, t1 = (uz0 - z_ud) / (z_uroof - z_ud), (uz1 - 0.06 - z_ud) / (z_uroof - z_ud)
        y0 = side * (lerp(3.68, 3.45, t0) + 0.025)
        y1 = side * (lerp(3.68, 3.45, t1) + 0.025)
        p0, p1, p2, p3 = (-8.85, y0, uz0), (-8.10, y0, uz0), (-8.10, y1, uz1 - 0.06), (-8.85, y1, uz1 - 0.06)
        if side == 1:
            glass_part.quad(p0, p1, p2, p3, GLASS)
        else:
            glass_part.quad(p1, p0, p3, p2, GLASS)

    # 4. Twin Signature Raised Swept-Back Aft Roof Fins ("Connecting Communities", Photos 1, 2, 4, 5)
    for side in (1, -1):
        fin_profile = [
            (-10.10, z_uroof - 0.02),
            (-6.20, z_uroof - 0.02),
            (-7.30, z_uroof + 1.02),
            (-9.60, z_uroof + 1.12),
            (-10.20, z_uroof + 0.90),
        ]
        tapered_plate_y(up, fin_profile, side * 2.86, 0.90, WHITE)
        y_out = side * (2.86 + 0.465)
        for z_line, w_line in ((z_uroof + 0.72, 1.55), (z_uroof + 0.46, 1.85)):
            block(up, -8.50, y_out, z_line, w_line, 0.025, 0.11, ORANGE)
        block(up, -10.02, side * 2.86, z_uroof + 0.22, 0.14, 0.62, 0.56, IRON)

    # Clean single streamlined mid-roof ventilation cowling (matching Photo 2 & 5)
    hvac_prof = [(-3.6, z_uroof + 0.12), (-0.4, z_uroof + 0.12), (-1.05, z_uroof + 0.74), (-3.25, z_uroof + 0.74)]
    tapered_plate_y(up, hvac_prof, 0.0, 2.65, OFFWHITE)
    # Cross bridge bar joining the twin aft fins softly
    block(up, -8.6, 0.0, z_uroof + 0.08, 2.1, 4.7, 0.34, OFFWHITE, 0.12)

    # 5. Aft Upper Cabin Rear Door flush with the raked rear wall (nothing protruding!)
    # Raked wall runs from (-11.60, z_ud) to (-9.85, z_uroof); draw flush doorframe & sloped glass!
    def aft_wall_x(z):
        t = clamp((z - z_ud) / (z_uroof - z_ud), 0.0, 1.0)
        return lerp(-11.60, -9.85, t) - 0.03

    dz0, dz1 = z_ud + 0.04, z_ud + 1.84
    up.quad(
        (aft_wall_x(dz0), 0.72, dz0),
        (aft_wall_x(dz0), -0.72, dz0),
        (aft_wall_x(dz1), -0.72, dz1),
        (aft_wall_x(dz1), 0.72, dz1),
        SILVER,
    )
    gz0, gz1 = z_ud + 0.92, z_ud + 1.68
    glass_part.quad(
        (aft_wall_x(gz0) - 0.02, 0.44, gz0),
        (aft_wall_x(gz0) - 0.02, -0.44, gz0),
        (aft_wall_x(gz1) - 0.02, -0.44, gz1),
        (aft_wall_x(gz1) - 0.02, 0.44, gz1),
        GLASS,
    )

    # 6. Twin Banks of 4 White Cylindrical Life-Raft Canisters (Photos 1 & 5)
    for side in (1, -1):
        y_rack = side * 4.18
        block(up, -10.45, y_rack, z_ud, 3.65, 0.72, 0.16, SILVER)
        for k in range(4):
            cx = -9.05 - k * 0.92
            pipe(up, (cx, y_rack - 0.48, z_ud + 0.48), (cx, y_rack + 0.48, z_ud + 0.48), 0.35, WHITE, 12)
            pipe(up, (cx, y_rack - 0.48, z_ud + 0.48), (cx, y_rack - 0.58, z_ud + 0.48), 0.35, OFFWHITE, 12, tip=0.22)
            pipe(up, (cx, y_rack + 0.48, z_ud + 0.48), (cx, y_rack + 0.58, z_ud + 0.48), 0.35, OFFWHITE, 12, tip=0.22)
            for dy in (-0.22, 0.22):
                annulus(up, (cx, y_rack + dy, z_ud + 0.48), (0, 1, 0), 0.365, 0.34, 0.05, RUBBER, count=12)

    # 7. Aft Upper Sun Deck Passenger Benches
    for side in (1, -1):
        block(up, -13.7, side * 3.1, z_ud, 2.2, 0.52, 0.46, WHITE, 0.04)
        block(up, -13.7, side * 3.1, z_ud + 0.46, 2.1, 0.48, 0.06, TEAL)

    return up


# ---------------------------------------------------------------------------
# Deck Gear, Railings, Life Rings, Flagstaff, Mast, Radars & Antennas
# ---------------------------------------------------------------------------

def build_deck_gear(lamp_part):
    """Bow & upper deck railings, red bow safety locker, aft life rings, stern flagstaff,
    mooring bollards, twin open-array radars, tapered mast, nav lights & whip antennas.
    """
    gear = Part("DeckGear")

    z_bow = hull_sheer_z(17.5)
    z_ud = 4.98
    z_aft = hull_sheer_z(-16.5)

    # 1. Bow Foredeck Pipe Railings (4 horizontal bars, Photos 2, 3, 5)
    bow_rail_pts = []
    n_arc = 10
    for i in range(n_arc + 1):
        ang = lerp(-math.pi * 0.42, math.pi * 0.42, i / n_arc)
        bx = 18.22 + 0.45 * math.cos(ang)
        by = 4.02 * math.sin(ang)
        bow_rail_pts.append((bx, by, z_bow))
    bow_rail_pts = [(16.3, -3.96, z_bow)] + bow_rail_pts + [(16.3, 3.96, z_bow)]
    railing_run(gear, bow_rail_pts, height=1.08, bars=4, post_step=1.15, color=WHITE, post_r=0.032, rail_r=0.026)

    # Red safety/cargo locker tucked neatly on starboard bow foredeck (Photo 3 & 5)
    block(gear, 17.50, -2.55, z_bow - 0.04, 0.78, 1.25, 0.78, RED, 0.05)
    block(gear, 17.50, -2.55, z_bow + 0.74, 0.82, 1.29, 0.07, OFFWHITE, 0.04)
    # Forward mooring bollards
    for side in (1, -1):
        block(gear, 17.85, side * 3.55, z_bow - 0.04, 0.48, 0.24, 0.07, IRON, 0.03)
        for dx in (-0.13, 0.13):
            pipe(gear, (17.85 + dx, side * 3.55, z_bow + 0.03), (17.85 + dx, side * 3.55, z_bow + 0.30), 0.06, STEEL, 8)
            pipe(gear, (17.85 + dx, side * 3.55, z_bow + 0.30), (17.85 + dx, side * 3.55, z_bow + 0.34), 0.085, STEEL, 8)

    # 2. Upper Side Walkway & Aft Sun Deck Guardrails (Photos 1, 2, 4, 5)
    for side in (1, -1):
        side_pts = [
            (7.8, side * 4.42, z_ud),
            (3.5, side * 4.52, z_ud),
            (-8.5, side * 4.52, z_ud),
        ]
        railing_run(gear, side_pts, height=1.02, bars=3, post_step=1.65, color=WHITE, post_r=0.028, rail_r=0.024)

    aft_sun_pts = [
        (-12.3, -4.48, z_ud),
        (-15.42, -4.38, z_ud),
        (-15.42, 4.38, z_ud),
        (-12.3, 4.48, z_ud),
    ]
    railing_run(gear, aft_sun_pts, height=1.08, bars=4, post_step=1.25, color=WHITE, post_r=0.032, rail_r=0.026)

    # 3. Aft Main Deck Stern Railings, Mooring Bitts & Prominent Orange Life Rings (Photo 1 & 4)
    z_bul_top = z_aft + 0.78
    stern_rail_pts = [
        (-15.3, -4.58, z_bul_top),
        (-18.42, -4.52, z_bul_top),
        (-18.42, 4.52, z_bul_top),
        (-15.3, 4.58, z_bul_top),
    ]
    railing_run(gear, stern_rail_pts, height=0.58, bars=2, post_step=1.45, color=WHITE, post_r=0.026, rail_r=0.022)

    for side in (1, -1):
        block(gear, -17.6, side * 3.95, z_aft, 0.56, 0.28, 0.08, IRON, 0.04)
        for dx in (-0.16, 0.16):
            pipe(gear, (-17.6 + dx, side * 3.95, z_aft + 0.08), (-17.6 + dx, side * 3.95, z_aft + 0.40), 0.07, STEEL, 8)
            pipe(gear, (-17.6 + dx, side * 3.95, z_aft + 0.40), (-17.6 + dx, side * 3.95, z_aft + 0.45), 0.095, STEEL, 8)

        # Bright orange life ring centered cleanly on the recessed aft side bulkhead (Photo 1!)
        ring_c = Vector((-13.35, side * 4.35, 3.84))
        annulus(gear, ring_c, (0, side, 0), 0.44, 0.25, 0.13, ORANGE, count=20)
        for k in range(4):
            ang = math.radians(45 + 90 * k)
            off = Vector((math.cos(ang), 0.0, math.sin(ang)))
            pipe(gear, ring_c + off * 0.25, ring_c + off * 0.44, 0.072, WHITE, 8)

    # 4. Stern Flagstaff & Stylized US Flag (Photo 1 & 4)
    pipe(gear, (-18.45, 0.0, z_bul_top - 0.18), (-18.78, 0.0, z_bul_top + 2.62), 0.036, WHITE, 8, tip=0.022)
    pipe(gear, (-18.78, 0.0, z_bul_top + 2.62), (-18.80, 0.0, z_bul_top + 2.74), 0.05, AMBER, 8)
    fx0, fz_top = -18.75, z_bul_top + 2.45
    flag_len, flag_h = 1.18, 0.70
    canton_w, canton_h = 0.47, 0.37
    block(gear, fx0 - canton_w * 0.5, 0.02, fz_top - canton_h, canton_w, 0.02, canton_h, BLUE_FLAG)
    for si in range(5):
        sh = flag_h / 5.0
        sz = fz_top - (si + 1) * sh
        col = RED if si % 2 == 0 else WHITE
        if si < 3:
            sw = flag_len - canton_w
            sx = fx0 - canton_w - sw * 0.5
        else:
            sw = flag_len
            sx = fx0 - sw * 0.5
        block(gear, sx, 0.02 + 0.02 * math.sin(si * 0.9), sz, sw, 0.02, sh, col)

    # 5. Roof Mast, Backstays, Twin Open-Array Radars, Satcom Domes & Whip Antennas (Photos 1, 2, 3, 5)
    mast_x = 3.55
    mast_z0 = 7.14
    mast_z1 = 12.55

    pipe(gear, (mast_x, 0.0, mast_z0), (mast_x - 0.18, 0.0, mast_z1), 0.13, WHITE, 10, tip=0.055)
    for side in (1, -1):
        pipe(gear, (mast_x - 0.10, 0.0, 10.75), (1.35, side * 1.15, 7.14), 0.042, WHITE, 6)
        pipe(gear, (mast_x - 0.04, 0.0, 9.05), (4.55, side * 0.65, 7.14), 0.038, WHITE, 6)

    pipe(gear, (mast_x - 0.08, -1.18, 9.95), (mast_x - 0.08, 1.18, 9.95), 0.036, WHITE, 6)
    pipe(gear, (mast_x - 0.13, -0.80, 11.25), (mast_x - 0.13, 0.80, 11.25), 0.030, WHITE, 6)

    for lz, lcol in ((10.12, LAMP), (11.42, LAMP), (mast_z1 + 0.15, AMBER)):
        pipe(gear, (mast_x - 0.18, 0.0, lz - 0.12), (mast_x - 0.18, 0.0, lz - 0.02), 0.055, IRON, 8)
        pipe(lamp_part, (mast_x - 0.18, 0.0, lz - 0.02), (mast_x - 0.18, 0.0, lz + 0.14), 0.070, lcol, 8)

    # Twin Open-Array Marine Radar Scanners (clearly visible in Photo 3!)
    rx1, ry1, rz1 = 5.05, -0.95, 7.14
    pipe(gear, (rx1, ry1, rz1), (rx1, ry1, rz1 + 0.85), 0.11, WHITE, 8, tip=0.085)
    block(gear, rx1, ry1, rz1 + 0.85, 0.36, 0.36, 0.24, WHITE, 0.04)
    block(gear, rx1, ry1, rz1 + 1.09, 0.18, 1.95, 0.12, WHITE, 0.03)

    rx2, ry2, rz2 = 3.92, 0.55, 7.14
    pipe(gear, (rx2, ry2, rz2), (rx2, ry2, rz2 + 1.48), 0.10, WHITE, 8, tip=0.08)
    block(gear, rx2, ry2, rz2 + 1.48, 0.38, 0.38, 0.24, WHITE, 0.04)
    block(gear, rx2, ry2, rz2 + 1.72, 0.18, 2.15, 0.13, WHITE, 0.03)

    # Small white GPS / Satcom radomes on bridge roof
    for dx, dy, r in ((5.85, 1.25, 0.24), (4.85, 1.45, 0.19)):
        pipe(gear, (dx, dy, 7.14), (dx, dy, 7.42), r * 0.55, WHITE, 10)
        pipe(gear, (dx, dy, 7.42), (dx, dy, 7.64), r, WHITE, 12, tip=r * 0.45)

    # Tall slender VHF / AIS whip antennas (Photos 1 & 3)
    for ax, ay, ah in (
        (5.75, 2.55, 3.35),
        (5.75, -2.55, 3.35),
        (4.35, -2.30, 2.75),
        (2.45, 2.10, 2.55),
    ):
        pipe(gear, (ax, ay, 7.14), (ax - 0.12, ay, 7.14 + ah), 0.022, SILVER, 6, tip=0.008)

    return gear


# ---------------------------------------------------------------------------
# Materials, Studio Setup, Export & Rendering
# ---------------------------------------------------------------------------

def make_vertex_material(name, roughness=0.45, metallic=0.08, spec=0.55):
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
    return mat


def setup_studio(scene):
    """Link Tideways' shared Preview Studio from barge_construction.blend if present."""
    barge_blend = ROOT / "art" / "barge_construction.blend"
    if barge_blend.exists():
        with bpy.data.libraries.load(str(barge_blend)) as (src, dst):
            dst.collections = ["Preview studio"]
            dst.worlds = ["Overcast sky"]
        studio = dst.collections[0]
        scene.collection.children.link(studio)
        scene.world = dst.worlds[0]
        camera = next(o for o in studio.objects if o.type == "CAMERA")
        key = next(o for o in studio.objects if o.type == "LIGHT")
    else:
        studio = bpy.data.collections.new("Preview studio")
        scene.collection.children.link(studio)
        bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0))
        water = bpy.context.object
        water.name = "Waterline"
        wmat = bpy.data.materials.new("Harbour water")
        if not wmat.node_tree:
            wmat.use_nodes = True
        wbsdf = next(n for n in wmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        wbsdf.inputs["Base Color"].default_value = (0.034, 0.102, 0.116, 1)
        wbsdf.inputs["Roughness"].default_value = 0.27
        water.data.materials.append(wmat)
        for owner in list(water.users_collection):
            owner.objects.unlink(water)
        studio.objects.link(water)

        bpy.ops.object.camera_add()
        camera = bpy.context.object
        for owner in list(camera.users_collection):
            owner.objects.unlink(camera)
        studio.objects.link(camera)

        bpy.ops.object.light_add(type="AREA", location=(26, -22, 38))
        key = bpy.context.object
        key.data.shape = "DISK"
        for owner in list(key.users_collection):
            owner.objects.unlink(key)
        studio.objects.link(key)

        scene.world = bpy.data.worlds.new("Overcast sky")
        if not scene.world.node_tree:
            scene.world.use_nodes = True
        bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
        bg.inputs[0].default_value = (0.73, 0.81, 0.90, 1)
        bg.inputs[1].default_value = 0.70

    target = Vector((0.0, 0.0, 3.4))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 36.5
    camera.location = target + Vector((34.0, -32.0, 16.0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    key.location = Vector((26.0, -22.0, 38.0))
    key.rotation_euler = (Vector((0, 0, 2)) - key.location).to_track_quat("-Z", "Y").to_euler()
    key.data.energy = 28000
    key.data.size = 16

    for obj in studio.objects:
        obj.hide_set(True)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 40
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    return studio, camera, target


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    glass_part = Part("glass")
    lamp_part = Part("lamp")

    hull_part = build_hulls()
    cabin_part = build_main_cabin(glass_part, lamp_part)
    upper_part = build_upper_deck(glass_part)
    pilot_part = build_pilothouse(glass_part, lamp_part)
    gear_part = build_deck_gear(lamp_part)

    mat_paint = make_vertex_material("Ferry paint", roughness=0.42, metallic=0.10, spec=0.55)
    mat_glass = make_vertex_material("Tinted glass", roughness=0.09, metallic=0.12, spec=0.85)
    mat_lamp = make_vertex_material("Nav lamps", roughness=0.20, metallic=0.0)
    bsdf_lamp = next(n for n in mat_lamp.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    if "Emission Strength" in bsdf_lamp.inputs:
        bsdf_lamp.inputs["Emission Strength"].default_value = 1.8
        vc_lamp = next(n for n in mat_lamp.node_tree.nodes if n.type == "VERTEX_COLOR")
        mat_lamp.node_tree.links.new(vc_lamp.outputs["Color"], bsdf_lamp.inputs["Emission Color"])

    coll = bpy.data.collections.new("FastFerry")
    scene.collection.children.link(coll)

    objs = [
        hull_part.finish(coll, mat_paint),
        cabin_part.finish(coll, mat_paint),
        upper_part.finish(coll, mat_paint),
        pilot_part.finish(coll, mat_paint),
        gear_part.finish(coll, mat_paint),
        glass_part.finish(coll, mat_glass),
        lamp_part.finish(coll, mat_lamp),
    ]

    root_obj = objs[0]
    for ob in objs[1:]:
        ob.parent = root_obj

    glb_path = ROOT / "assets" / "models" / "fast_ferry_mid.glb"
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

    counts = {o.name: len(o.data.polygons) for o in objs}
    print("FAST_FERRY", glb_path, counts, "TOTAL_TRIS:", sum(counts.values()))

    studio, camera, target = setup_studio(scene)
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            view = area.spaces.active
            view.shading.color_type = "VERTEX"
            view.overlay.show_overlays = False
            view.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            view.region_3d.view_location = target
            view.region_3d.view_distance = 45.0
            view.region_3d.view_perspective = "ORTHO"

    bpy.context.preferences.filepaths.save_version = 0
    blend_path = ROOT / "art" / "fast_ferry.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

    # Render main hero preview (bow-port 3/4 view)
    scene.render.filepath = str(ROOT / "art" / "fast_ferry_preview.png")
    bpy.ops.render.render(write_still=True)

    # Optional multi-angle diagnostic renders if --views <dir> is passed after --
    diag_dir = None
    if "--views" in sys.argv:
        idx = sys.argv.index("--views")
        if idx + 1 < len(sys.argv):
            diag_dir = sys.argv[idx + 1]
    if diag_dir:
        out_dir = Path(diag_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        scene.render.resolution_x, scene.render.resolution_y = 1100, 700
        scene.cycles.samples = 24
        views = [
            ("profile_port", Vector((52.0, 0.0, 2.6)), Vector((0.0, 0.0, 4.4)), 44.0),
            ("bow_low", Vector((22.0, -40.0, 6.0)), Vector((0.0, -3.0, 3.8)), 28.0),
            ("stern_stbd", Vector((-34.0, 32.0, 15.0)), Vector((0.0, 1.0, 3.6)), 36.5),
        ]
        for vname, offset, vt, oscale in views:
            camera.location = vt + offset
            camera.rotation_euler = (vt - camera.location).to_track_quat("-Z", "Y").to_euler()
            camera.data.ortho_scale = oscale
            scene.render.filepath = str(out_dir / f"{vname}.png")
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
