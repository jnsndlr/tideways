"""Build a sporty personal watercraft (jet ski) and rider for Tideways.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender -b -noaudio --factory-startup -P art/jetski_mid.py

Exports:
    assets/models/jetski_mid.glb   (glTF, +Y up, +Z forward, vertex colours)
    art/jetski.blend               (editable source + preview studio)
    art/jetski_preview.png         (studio preview on harbour water)

Real-world dimensions (metres):
    LOA 3.25 m (x: -1.64 stern to +1.61 bow), Beam 1.18 m (y: -0.59 stbd to +0.59 port),
    waterline at z = 0.0. Working frame is (x=bow, y=port, z=up); mapped to Blender
    (y, -x, z) so glTF export (+Y up) puts +Z forward and +Y up.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
TAU = math.tau

# Tideways coastal sporty palette
WHITE = "eff3f3"
OFFWHITE = "dce3e4"
TEAL = "12809a"
TEAL_LIGHT = "26a5bc"
TEAL_DARK = "0c5c70"
ORANGE = "ea5226"
ORANGE_HI = "f46b3a"
AMBER = "f2a830"
HULL_DARK = "1e252c"
HULL_MID = "2f3840"
RUBBER = "1b2025"
MAT_GREY = "2b3239"
SEAT_DARK = "1d2227"
SEAT_BOLSTER = "313941"
METAL = "a4aeb4"
GUNMETAL = "3c454c"
GLASS = "0f1a23"
LCD_BG = "122c38"
LCD_CYAN = "4ce0f0"

# Rider palette
WETSUIT = "20272f"
WETSUIT_SEAM = "17748b"
BOOT_SOLE = "15191d"
PFD_ORANGE = "eb5424"
PFD_DARK = "1e2329"
PFD_TRIM = "f3b034"
SKIN = "d9a27e"
SKIN_SHADE = "c48b67"
HAIR = "3a271c"
SHADES_LENS = "0d141c"
SHADES_FRAME = "20262c"


def blender_point(v):
    x, y, z = v
    return (y, -x, z)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hex_to_srgb(code):
    rgb = bytes.fromhex(code)
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)


def ring_normal(pts):
    n = Vector((0.0, 0.0, 0.0))
    for i in range(len(pts)):
        a = Vector(pts[i])
        b = Vector(pts[(i + 1) % len(pts)])
        n += a.cross(b)
    return n


def centroid(pts):
    s = Vector((0.0, 0.0, 0.0))
    for p in pts:
        s += Vector(p)
    return s / max(1, len(pts))


class Part:
    """Vertex-coloured mesh builder in (bow, port, up) coordinates."""

    def __init__(self, name, origin=(0.0, 0.0, 0.0), smooth_angle=44.0):
        self.name = name
        self.origin = Vector(origin)
        self.smooth_angle = smooth_angle
        self.vertices = []
        self.faces = []
        self.colors = []
        self.smooths = []

    def vertex(self, point):
        p = Vector(point) - self.origin
        self.vertices.append(blender_point((p.x, p.y, p.z)))
        return len(self.vertices) - 1

    def face(self, indices, color, smooth=True):
        clean = [indices[0]]
        for idx in indices[1:]:
            if idx != clean[-1]:
                clean.append(idx)
        if len(clean) > 2 and clean[0] == clean[-1]:
            clean.pop()
        if len(clean) >= 3:
            self.faces.append(tuple(clean))
            self.colors.append(color)
            self.smooths.append(smooth)

    def poly(self, pts, color, out=None, smooth=False):
        if len(pts) < 3:
            return
        if out is not None and ring_normal(pts).dot(Vector(out)) < 0:
            pts = list(reversed(pts))
        self.face([self.vertex(p) for p in pts], color, smooth=smooth)

    def loft(self, rings, color, closed_ring=True, closed_path=False,
             cap_start=None, cap_end=None, smooth=True):
        """Loft between matching point rings with automatic outward winding."""
        n = len(rings[0])
        m = len(rings) if closed_path else len(rings) - 1
        score = 0.0
        for j in range(m):
            ra = rings[j]
            rb = rings[(j + 1) % len(rings)]
            ax = (centroid(ra) + centroid(rb)) * 0.5
            for i in range(n if closed_ring else n - 1):
                k = (i + 1) % n
                q = [ra[i], ra[k], rb[k], rb[i]]
                score += ring_normal(q).dot(centroid(q) - ax)
        flip = score < 0.0

        rows = [[self.vertex(p) for p in ring] for ring in rings]
        for j in range(m):
            a = rows[j]
            b = rows[(j + 1) % len(rows)]
            ra = rings[j]
            rb = rings[(j + 1) % len(rings)]
            for i in range(n if closed_ring else n - 1):
                k = (i + 1) % n
                c = color(j, i, centroid([ra[i], ra[k], rb[k], rb[i]])) if callable(color) else color
                quad = (a[i], a[k], b[k], b[i]) if not flip else (a[i], b[i], b[k], a[k])
                self.face(quad, c, smooth=smooth)

        if not closed_path and closed_ring:
            if cap_start is not None:
                c0, c1 = centroid(rings[0]), centroid(rings[1])
                out = c0 - c1
                if ring_normal(rings[0]).dot(out) < 0:
                    self.face(rows[0][::-1], cap_start, smooth=False)
                else:
                    self.face(rows[0], cap_start, smooth=False)
            if cap_end is not None:
                c0, c1 = centroid(rings[-1]), centroid(rings[-2])
                out = c0 - c1
                if ring_normal(rings[-1]).dot(out) < 0:
                    self.face(rows[-1][::-1], cap_end, smooth=False)
                else:
                    self.face(rows[-1], cap_end, smooth=False)

    def tube(self, path, radii, color, sides=12, cap_start=None, cap_end=None,
             closed=False, smooth=True, scale_xy=None):
        """Sweep a circular or elliptical cross-section along a 3D polyline."""
        pts = [Vector(p) for p in path]
        count = len(pts)
        if not isinstance(radii, (list, tuple)):
            radii = [radii] * count
        if scale_xy is None:
            scale_xy = [(1.0, 1.0)] * count

        rings = []
        prev_u = None
        for idx, p in enumerate(pts):
            if closed:
                t = (pts[(idx + 1) % count] - pts[(idx - 1) % count]).normalized()
            elif idx == 0:
                t = (pts[1] - pts[0]).normalized()
            elif idx == count - 1:
                t = (pts[-1] - pts[-2]).normalized()
            else:
                t1 = (pts[idx] - pts[idx - 1]).normalized()
                t2 = (pts[idx + 1] - pts[idx]).normalized()
                t = t1 + t2
                t = t.normalized() if t.length > 1e-6 else t1

            if prev_u is None:
                ref = Vector((0.0, 0.0, 1.0)) if abs(t.z) < 0.92 else Vector((1.0, 0.0, 0.0))
                u = (ref - t * ref.dot(t)).normalized()
            else:
                u = prev_u - t * prev_u.dot(t)
                if u.length < 1e-6:
                    ref = Vector((0.0, 0.0, 1.0)) if abs(t.z) < 0.92 else Vector((1.0, 0.0, 0.0))
                    u = (ref - t * ref.dot(t)).normalized()
                else:
                    u.normalize()
            v = t.cross(u).normalized()
            prev_u = u

            r = radii[idx]
            sx, sy = scale_xy[idx]
            ring = []
            for s in range(sides):
                ang = TAU * s / sides
                off = u * (math.cos(ang) * r * sx) + v * (math.sin(ang) * r * sy)
                ring.append(p + off)
            rings.append(ring)

        self.loft(rings, color, closed_ring=True, closed_path=closed,
                  cap_start=cap_start, cap_end=cap_end, smooth=smooth)

    def ellipsoid(self, center, rx, ry, rz, color, rings=10, segs=16,
                  rot_euler=(0.0, 0.0, 0.0), smooth=True, color_fn=None):
        """Add an oriented ellipsoid."""
        c = Vector(center)
        rot = Euler(rot_euler, "XYZ").to_matrix()
        lat_rings = []
        for i in range(1, rings):
            phi = math.pi * i / rings
            sp, cp = math.sin(phi), math.cos(phi)
            ring = []
            for j in range(segs):
                th = TAU * j / segs
                local = Vector((rx * sp * math.cos(th), ry * sp * math.sin(th), rz * cp))
                ring.append(c + rot @ local)
            lat_rings.append(ring)

        north = c + rot @ Vector((0.0, 0.0, rz))
        south = c + rot @ Vector((0.0, 0.0, -rz))
        n_idx = self.vertex(north)
        s_idx = self.vertex(south)
        rows = [[self.vertex(p) for p in ring] for ring in lat_rings]

        def pick(p):
            return color_fn(p) if color_fn else color

        for j in range(segs):
            k = (j + 1) % segs
            p_mid = (north + lat_rings[0][j] + lat_rings[0][k]) / 3.0
            self.face((n_idx, rows[0][j], rows[0][k]), pick(p_mid), smooth=smooth)
        for i in range(len(rows) - 1):
            a, b = rows[i], rows[i + 1]
            ra, rb = lat_rings[i], lat_rings[i + 1]
            for j in range(segs):
                k = (j + 1) % segs
                p_mid = (ra[j] + ra[k] + rb[k] + rb[j]) * 0.25
                self.face((a[j], b[j], b[k], a[k]), pick(p_mid), smooth=smooth)
        for j in range(segs):
            k = (j + 1) % segs
            p_mid = (south + lat_rings[-1][j] + lat_rings[-1][k]) / 3.0
            self.face((s_idx, rows[-1][k], rows[-1][j]), pick(p_mid), smooth=smooth)

    def box(self, cx, cy, z0, lx, ly, lz, color, bevel=0.0, rot_y=0.0, rot_z=0.0, smooth=False):
        """Axis-aligned or rotated rounded box."""
        hx, hy = lx * 0.5, ly * 0.5
        if bevel > 0.0:
            c = min(bevel, hx * 0.85, hy * 0.85)
            pts2 = [(-hx + c, -hy), (hx - c, -hy), (hx, -hy + c), (hx, hy - c),
                    (hx - c, hy), (-hx + c, hy), (-hx, hy - c), (-hx, -hy + c)]
        else:
            pts2 = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        rot = Euler((0.0, rot_y, rot_z), "XYZ").to_matrix()
        base = Vector((cx, cy, z0 + lz * 0.5))
        rings = []
        for dz in (-lz * 0.5, lz * 0.5):
            rings.append([base + rot @ Vector((x, y, dz)) for x, y in pts2])
        self.loft(rings, color, cap_start=color, cap_end=color, smooth=smooth)

    def finish(self, collection, material):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()

        colors = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
        for poly, code, sm in zip(mesh.polygons, self.colors, self.smooths):
            poly.use_smooth = sm
            rgba = hex_to_srgb(code)
            for li in poly.loop_indices:
                colors.data[li].color_srgb = rgba

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.normal_update()

        thresh = math.radians(self.smooth_angle)
        sharp_edges = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                f0, f1 = e.link_faces[0], e.link_faces[1]
                if f0.smooth != f1.smooth:
                    sharp_edges.append(e)
                elif f0.smooth and e.calc_face_angle(0.0) > thresh:
                    sharp_edges.append(e)
        if sharp_edges:
            bmesh.ops.split_edges(bm, edges=sharp_edges)

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

        mesh.materials.append(material)
        obj = bpy.data.objects.new(self.name, mesh)
        obj.location = blender_point((self.origin.x, self.origin.y, self.origin.z))
        collection.objects.link(obj)
        return obj


# ---------------------------------------------------------------------------
# Hull analytical profile functions (metres: x=bow, y=port, z=up)
# ---------------------------------------------------------------------------

def hull_half_beam(x):
    """Half-width at the rub rail from stern (-1.64) to bow tip (+1.60)."""
    if x >= 1.60:
        return 0.0
    if x <= -1.64:
        return 0.48
    if x < -0.35:
        t = smoothstep(-1.64, -0.35, x)
        return lerp(0.48, 0.59, t)
    if x < 0.35:
        return 0.59
    u = clamp((x - 0.35) / (1.60 - 0.35), 0.0, 1.0)
    return 0.59 * (1.0 - u ** 1.55) ** 0.72


def hull_keel_z(x):
    """Deep-V keel line, waterline at z = 0.0."""
    if x < -0.45:
        t = smoothstep(-1.64, -0.45, x)
        return lerp(-0.13, -0.22, t)
    if x < 0.45:
        return -0.22
    u = clamp((x - 0.45) / (1.60 - 0.45), 0.0, 1.0)
    return lerp(-0.22, 0.30, u ** 1.75)


def hull_chine_z(x):
    """Lower spray chine elevation."""
    if x < 0.35:
        t = smoothstep(-1.64, 0.35, x)
        return lerp(-0.025, -0.04, t)
    u = clamp((x - 0.35) / (1.60 - 0.35), 0.0, 1.0)
    return lerp(-0.04, 0.33, u ** 1.65)


def hull_sheer_z(x):
    """Rub rail / deck seam elevation."""
    if x < -1.10:
        t = smoothstep(-1.64, -1.10, x)
        return lerp(0.175, 0.21, t)
    if x < 0.30:
        t = smoothstep(-1.10, 0.30, x)
        return lerp(0.21, 0.28, t)
    t = smoothstep(0.30, 1.60, x)
    return lerp(0.28, 0.38, t) - 0.025 * smoothstep(1.30, 1.60, x)


def hood_crown_z(x):
    """Centerline height of the bow hood from x=+0.15 to bow tip +1.58."""
    if x >= 1.58:
        return hull_sheer_z(1.58)
    if x >= 0.48:
        u = clamp((1.58 - x) / (1.58 - 0.48), 0.0, 1.0)
        return lerp(0.365, 0.76, u ** 0.72)
    u = clamp((0.48 - x) / (0.48 - 0.14), 0.0, 1.0)
    return lerp(0.76, 0.50, smoothstep(0.0, 1.0, u))


def build_hull():
    """Deep-V planing hull, sculpted upper deck coamings, bow hood & sponsons."""
    hull = Part("Hull", smooth_angle=38.0)

    # 1. Main lower hull + upper sides up to the sheer line (-1.64 .. +1.60)
    xs = [
        -1.64, -1.45, -1.20, -0.92, -0.64, -0.34, -0.04, 0.26,
        0.54, 0.80, 1.02, 1.22, 1.38, 1.50, 1.57, 1.60
    ]
    hull_rings = []
    for x in xs:
        hb = max(0.006, hull_half_beam(x))
        kz = hull_keel_z(x)
        cz = hull_chine_z(x)
        sz = hull_sheer_z(x)

        strake_y = hb * 0.46
        strake_z = lerp(kz, cz, 0.44) - 0.012 * (1.0 - smoothstep(0.8, 1.58, x))
        chine_y = hb * 0.84
        # Clean continuous flare & flush coral pin-stripe built right into the hull loft!
        stripe_t = lerp(0.42, 0.56, smoothstep(-1.40, 1.25, x))
        stripe_hi_t = lerp(0.54, 0.72, smoothstep(-1.40, 1.25, x))
        flare_y = hb * 0.94
        flare_z = lerp(cz, sz, stripe_t)
        stripe_y = hb * 0.975
        stripe_z = lerp(cz, sz, stripe_hi_t)

        inner_z = sz + 0.012 if x > 0.35 else max(0.145, sz - 0.03)
        if x < -1.10:
            inner_z = 0.165

        right_side = [
            (x, -strake_y, strake_z),
            (x, -chine_y, cz),
            (x, -flare_y, flare_z),
            (x, -stripe_y, stripe_z),
            (x, -hb, sz),
            (x, -hb * 0.88, inner_z),
        ]
        left_side = [(x, -y, z) for _, y, z in reversed(right_side)]
        ring = [(x, 0.0, kz)] + right_side + [(x, 0.0, inner_z)] + left_side
        hull_rings.append(ring)

    def hull_color(j, i, c):
        # Ring indices (14 total):
        # 0=keel, 1=stbd strake, 2=stbd chine, 3=stbd flare, 4=stbd stripe_hi, 5=stbd sheer,
        # 6=stbd inner, 7=center inner, 8=port inner, 9=port sheer, 10=port stripe_hi,
        # 11=port flare, 12=port chine, 13=port strake
        # Planing bottom below chine: dark graphite
        if i in (0, 1, 12, 13):
            return HULL_DARK
        # Inner deck / swim platform top
        if i in (5, 6, 7, 8):
            return WHITE if c.x > 0.35 else OFFWHITE
        # Lower hull flank (chine -> flare): sleek continuous Pacific teal band
        if i in (2, 11):
            return TEAL if c.x < 1.38 else WHITE
        # Flush swept coral-orange accent stripe (flare -> stripe_hi)
        if i in (3, 10):
            if -1.25 < c.x < 1.24:
                return ORANGE
            return WHITE
        # Upper hull flank (stripe_hi -> sheer): crisp marine white
        return WHITE

    hull.loft(hull_rings, hull_color, cap_start=HULL_DARK, cap_end=WHITE, smooth=True)

    # 2. Sculpted Bow Hood & Aerodynamic Side Fairing (x = +0.16 to +1.58)
    hood_xs = [0.16, 0.28, 0.40, 0.54, 0.72, 0.90, 1.08, 1.25, 1.40, 1.52, 1.58]
    hood_rings = []
    for x in hood_xs:
        hb = max(0.015, hull_half_beam(x) * 0.96)
        sz = hull_sheer_z(x) - 0.006
        cz = hood_crown_z(x)
        if x < 0.54:
            t = smoothstep(0.16, 0.54, x)
            hw = lerp(0.24, hb, t)
            base_z = lerp(0.36, sz, t)
        else:
            hw = hb
            base_z = sz

        shoulder_y = hw * 0.74
        shoulder_z = lerp(base_z, cz, 0.54)
        ridge_y = hw * 0.36
        ridge_z = lerp(base_z, cz, 0.91)
        crown_y = hw * 0.14
        crown_z = cz

        ring = [
            (x, -hw, base_z),
            (x, -shoulder_y, shoulder_z),
            (x, -ridge_y, ridge_z),
            (x, -crown_y, crown_z),
            (x, crown_y, crown_z),
            (x, ridge_y, ridge_z),
            (x, shoulder_y, shoulder_z),
            (x, hw, base_z),
            (x, hw * 0.55, base_z - 0.03),
            (x, -hw * 0.55, base_z - 0.03),
        ]
        hood_rings.append(ring)

    def hood_color(j, i, c):
        # Sleek continuous center teal racing spine from nose to windscreen
        if i == 3:
            if c.x > 0.54:
                return TEAL
            return HULL_DARK
        # Crisp coral racing edge framing the teal spine cleanly along the hood hatch
        if i in (2, 4):
            if 0.56 < c.x < 1.38:
                return ORANGE
            if c.x <= 0.56:
                return HULL_DARK
            return WHITE
        # Outer white fiberglass fairing sweeping smoothly into dark cowl cheeks
        if i in (1, 5):
            if c.x < 0.44:
                return TEAL_DARK
            return WHITE
        if i in (0, 6):
            return WHITE
        return HULL_DARK

    hull.loft(hood_rings, hood_color, cap_start=HULL_DARK, cap_end=WHITE, smooth=True)

    # 3. Sleek Low-Profile Side Gunwales / Coamings smoothly merging into bow fairing!
    # Lower midships so footwells & rider boots show cleanly, sweeping up cleanly into bow hood.
    for side in (-1, 1):
        gun_xs = [-1.18, -0.95, -0.60, -0.20, 0.15, 0.38, 0.54, 0.74]
        g_rings = []
        for x in gun_xs:
            hb = hull_half_beam(x)
            sz = hull_sheer_z(x)
            # Low sleek rim along footwells (0.04 -> 0.085 m), tapering smoothly into bow fairing
            if x <= 0.42:
                rise = lerp(0.035, 0.115, smoothstep(-1.18, 0.42, x))
            else:
                # Taper smoothly down/inward inside the bow hood edge so there is ZERO vertical step!
                rise = lerp(0.115, 0.02, smoothstep(0.42, 0.74, x))
            top_z = sz + rise
            w_in = hb - lerp(0.095, 0.125, smoothstep(-1.18, 0.42, x))
            if x > 0.42:
                w_in = lerp(w_in, hb * 0.86, smoothstep(0.42, 0.74, x))
            y_out = side * (hb * 0.96)
            y_top_out = side * (hb * 0.89)
            y_top_in = side * w_in
            y_floor = side * (w_in - 0.015)
            ring = [
                (x, y_out, sz - 0.008),
                (x, y_top_out, top_z),
                (x, y_top_in, top_z - 0.012),
                (x, y_floor, 0.145),
                (x, y_out * 0.92, 0.145),
            ]
            if side < 0:
                ring = list(reversed(ring))
            g_rings.append(ring)

        hull.loft(g_rings, WHITE, cap_start=WHITE, cap_end=WHITE, smooth=True)

    # 4. Sculpted Central Engine Bay / Saddle Spine (curved fiberglass sides + dark lower trim)
    ped_xs = [-1.14, -0.96, -0.64, -0.28, 0.02, 0.26, 0.38]
    ped_rings = []
    for x in ped_xs:
        knee_pinch = 1.0 - 0.30 * math.exp(-((x - 0.04) / 0.28) ** 2)
        bw = 0.215 * knee_pinch
        mw = 0.200 * knee_pinch
        tw = 0.165 * knee_pinch
        if x < -0.98:
            t = smoothstep(-1.14, -0.98, x)
            top_z = lerp(0.24, 0.45, t)
            mid_z = lerp(0.20, 0.32, t)
        elif x > 0.24:
            t = smoothstep(0.24, 0.38, x)
            top_z = lerp(0.48, 0.56, t)
            mid_z = lerp(0.34, 0.40, t)
        else:
            top_z = lerp(0.45, 0.48, smoothstep(-0.98, 0.24, x))
            mid_z = 0.31
        ring = [
            (x, -bw, 0.145),
            (x, -mw, mid_z),
            (x, -tw, top_z),
            (x, tw, top_z),
            (x, mw, mid_z),
            (x, bw, 0.145),
        ]
        ped_rings.append(ring)

    def ped_col(j, i, c):
        # Dark lower kick-panel along footwells (i in 0, 4), crisp white upper spine
        if i in (0, 4):
            return HULL_MID
        return WHITE

    hull.loft(ped_rings, ped_col, cap_start=HULL_MID, cap_end=HULL_DARK, smooth=True)

    # 5. Recessed Footwell Deck Floor & Swim Platform Base
    hull.box(-0.35, 0.0, 0.11, 1.56, 0.98, 0.045, OFFWHITE, bevel=0.06, smooth=False)
    hull.box(-1.38, 0.0, 0.125, 0.52, 0.92, 0.045, OFFWHITE, bevel=0.08, smooth=False)

    # 6. Rear Side Sponsons (iconic PWC carving stabilizer blades)
    for side in (-1, 1):
        sp_xs = [-1.36, -1.18, -0.85, -0.58]
        sp_rings = []
        for x in sp_xs:
            hb = hull_half_beam(x)
            cz = hull_chine_z(x)
            bulge = 0.052 * math.sin(math.pi * clamp((x - (-1.36)) / 0.78, 0.0, 1.0)) ** 0.6
            y0 = side * (hb * 0.85)
            y1 = side * (hb * 0.85 + bulge)
            ring = [
                (x, y0, cz + 0.01),
                (x, y1, cz + 0.03),
                (x, y1, cz + 0.085),
                (x, y0, cz + 0.10),
            ]
            if side < 0:
                ring = list(reversed(ring))
            sp_rings.append(ring)
        hull.loft(sp_rings, HULL_DARK, cap_start=HULL_DARK, cap_end=HULL_DARK, smooth=False)

    # 7. Integrated Swept Aerodynamic Side Mirror Pods & Flush Side Intake Vents
    for side in (-1, 1):
        # Smooth teardrop mirror pod emerging cleanly from the upper bow hood shoulder
        m_pts = [
            (0.64, side * 0.21, 0.625),
            (0.60, side * 0.29, 0.650),
            (0.54, side * 0.365, 0.665),
            (0.50, side * 0.395, 0.668),
        ]
        hull.tube(m_pts, [0.032, 0.038, 0.034, 0.018], WHITE, sides=12,
                  cap_start=WHITE, cap_end=WHITE, smooth=True,
                  scale_xy=[(0.80, 1.25), (0.72, 1.35), (0.70, 1.30), (0.65, 1.20)])

        # Flush side louver vent hugging the curved hood shoulder slope
        vent_pts = [
            (0.86, side * (hull_half_beam(0.86) * 0.69), lerp(hull_sheer_z(0.86), hood_crown_z(0.86), 0.56)),
            (0.68, side * (hull_half_beam(0.68) * 0.73), lerp(hull_sheer_z(0.68), hood_crown_z(0.68), 0.55)),
            (0.50, side * (hull_half_beam(0.50) * 0.74), lerp(hull_sheer_z(0.50), hood_crown_z(0.50), 0.54)),
        ]
        hull.tube(vent_pts, [0.014, 0.022, 0.018], HULL_DARK, sides=8,
                  cap_start=HULL_DARK, cap_end=HULL_DARK, smooth=True,
                  scale_xy=[(1.4, 0.45)] * 3)

    return hull


def build_trim_and_mats():
    """Rub rail bumper, nose guard, EVA traction mats, mirror glass & dash pod."""
    trim = Part("Trim", smooth_angle=45.0)

    # 1. Full 360-degree Wrap-Around Black Rub Rail Bumper (clean horizontal transom wrap)
    xs_rail = [
        -1.63, -1.45, -1.20, -0.92, -0.64, -0.34, -0.04, 0.26,
        0.54, 0.80, 1.02, 1.22, 1.38, 1.50, 1.57, 1.61
    ]
    z_stern = hull_sheer_z(-1.63)
    rail_path = []
    for x in xs_rail:
        rail_path.append((x, hull_half_beam(x) + 0.008, hull_sheer_z(x)))
    for x in reversed(xs_rail[:-1]):
        rail_path.append((x, -(hull_half_beam(x) + 0.008), hull_sheer_z(x)))
    # Clean level transom bumper across the rear edge
    rail_path.append((-1.64, -0.45, z_stern))
    rail_path.append((-1.64, -0.22, z_stern))
    rail_path.append((-1.64, 0.22, z_stern))
    rail_path.append((-1.64, 0.45, z_stern))

    trim.tube(rail_path, 0.032, RUBBER, sides=10, closed=True, smooth=True,
              scale_xy=[(0.85, 1.15)] * len(rail_path))

    # Molded rubber bow nose guard
    trim.ellipsoid((1.59, 0.0, 0.365), 0.072, 0.064, 0.052, RUBBER,
                   rings=8, segs=12, smooth=True)

    # 2. Footwell EVA Foam Traction Mats (port & starboard) + Teal accent border
    for side in (-1, 1):
        trim.box(-0.36, side * 0.34, 0.148, 1.44, 0.22, 0.016, MAT_GREY, bevel=0.04, smooth=False)
        for k in range(7):
            gx = -0.96 + k * 0.20
            trim.box(gx, side * 0.34, 0.162, 0.025, 0.18, 0.006, RUBBER, smooth=False)
        trim.box(-0.36, side * 0.435, 0.158, 1.34, 0.022, 0.009, TEAL, smooth=False)

    # 3. Rear Swim Platform EVA Traction Pad
    trim.box(-1.38, 0.0, 0.168, 0.44, 0.80, 0.016, MAT_GREY, bevel=0.05, smooth=False)
    for k in range(3):
        gx = -1.52 + k * 0.14
        trim.box(gx, 0.0, 0.182, 0.024, 0.70, 0.006, RUBBER, smooth=False)
    trim.box(-1.18, 0.0, 0.176, 0.032, 0.72, 0.010, ORANGE, smooth=False)

    # 4. Hood Storage Latch & Mirror Faces (flush inside aft end of teardrop mirror pods)
    trim.box(1.24, 0.0, 0.502, 0.085, 0.065, 0.020, RUBBER, bevel=0.01, rot_y=0.32, smooth=False)
    for side in (-1, 1):
        trim.box(0.518, side * 0.345, 0.652, 0.012, 0.066, 0.026, GLASS,
                 bevel=0.006, rot_z=-side * 0.32, smooth=False)

    # 5. Dash Bezel, Gauge Pod Housing & Steering Column Rubber Boot
    trim.box(0.41, 0.0, 0.665, 0.18, 0.26, 0.12, RUBBER, bevel=0.025, rot_y=-0.38, smooth=False)
    trim.tube([(0.32, 0.0, 0.49), (0.295, 0.0, 0.66)], [0.068, 0.048],
              RUBBER, sides=12, cap_start=RUBBER, cap_end=RUBBER, smooth=True)

    return trim


def build_windscreen():
    """Smoked acrylic mini-windscreen & glossy digital gauge display."""
    glass = Part("Windscreen", smooth_angle=50.0)

    w_xs = [0.43, 0.52, 0.64, 0.76]
    w_rings = []
    for i, x in enumerate(w_xs):
        t = i / (len(w_xs) - 1)
        hw = lerp(0.165, 0.105, t)
        z_top = lerp(0.845, 0.715, t ** 1.15)
        z_edge = lerp(0.765, 0.690, t)
        thick = 0.012
        ring = [
            (x, -hw, z_edge),
            (x, -hw * 0.52, lerp(z_edge, z_top, 0.80)),
            (x, 0.0, z_top),
            (x, hw * 0.52, lerp(z_edge, z_top, 0.80)),
            (x, hw, z_edge),
            (x, hw * 0.92, z_edge - thick),
            (x, 0.0, z_top - thick),
            (x, -hw * 0.92, z_edge - thick),
        ]
        w_rings.append(ring)
    glass.loft(w_rings, GLASS, cap_start=GLASS, cap_end=GLASS, smooth=True)

    # Digital LCD display face tilted toward rider
    glass.box(0.365, 0.0, 0.695, 0.014, 0.16, 0.068, LCD_BG, bevel=0.008, rot_y=-0.52, smooth=False)
    glass.box(0.358, -0.032, 0.728, 0.008, 0.055, 0.012, LCD_CYAN, rot_y=-0.52, smooth=False)
    glass.box(0.358, 0.036, 0.724, 0.008, 0.042, 0.016, ORANGE_HI, rot_y=-0.52, smooth=False)

    return glass


def build_metal_hardware():
    """Jet pump nozzle, steering bucket, rear grab bar, boarding step & tow eyes."""
    metal = Part("Hardware", smooth_angle=42.0)

    # 1. Jet Pump Tunnel Nozzle & Steering Cone at transom
    metal.tube([(-1.55, 0.0, -0.055), (-1.68, 0.0, -0.055)], [0.088, 0.072],
               GUNMETAL, sides=14, cap_start=GUNMETAL, cap_end=GUNMETAL, smooth=True)
    metal.tube([(-1.67, 0.0, -0.055), (-1.77, 0.0, -0.052)], [0.068, 0.052],
               METAL, sides=14, cap_start=GUNMETAL, cap_end=RUBBER, smooth=True)
    metal.box(-1.73, 0.0, -0.015, 0.11, 0.13, 0.075, GUNMETAL, bevel=0.018, rot_y=0.18, smooth=False)
    for side in (-1, 1):
        metal.tube([(-1.62, side * 0.095, -0.055), (-1.73, side * 0.072, -0.055)],
                   0.012, METAL, sides=8, cap_start=METAL, cap_end=METAL, smooth=True)

    # 2. Rear Passenger Grab Rail (U-hoop anchored solidly into rear seat pedestal)
    grab_path = [
        (-1.02, -0.145, 0.43),
        (-1.12, -0.155, 0.55),
        (-1.17, -0.11, 0.59),
        (-1.18, 0.00, 0.595),
        (-1.17, 0.11, 0.59),
        (-1.12, 0.155, 0.55),
        (-1.02, 0.145, 0.43),
    ]
    metal.tube(grab_path, 0.016, METAL, sides=10, cap_start=GUNMETAL, cap_end=GUNMETAL, smooth=True)

    # 3. Rear Reboarding Fold-Up Step tucked at transom
    step_path = [
        (-1.62, -0.17, 0.14),
        (-1.67, -0.17, 0.08),
        (-1.67, 0.17, 0.08),
        (-1.62, 0.17, 0.14),
    ]
    metal.tube(step_path, 0.014, GUNMETAL, sides=8, cap_start=GUNMETAL, cap_end=GUNMETAL, smooth=True)

    # 4. Ski Tow Eye (anchored cleanly on rear seat pedestal) & Bow Tie-Down Eye
    metal.tube([(-1.04, -0.028, 0.415), (-1.13, 0.0, 0.415), (-1.04, 0.028, 0.415)],
               0.010, METAL, sides=8, smooth=True)
    metal.tube([(1.48, -0.025, 0.24), (1.53, 0.0, 0.24), (1.48, 0.025, 0.24)],
               0.009, METAL, sides=8, smooth=True)

    # 5. Flush Billet Fuel Cap on forward bow port
    metal.tube([(0.92, 0.18, 0.588), (0.92, 0.18, 0.610)], 0.032, METAL,
               sides=12, cap_start=GUNMETAL, cap_end=METAL, smooth=True)

    return metal


def build_seat():
    """Sculpted two-tier ergonomic bolster saddle with racing panels & grab strap."""
    seat = Part("Seat", smooth_angle=44.0)

    stations = [
        (-1.06, 0.135, 0.44, 0.56),
        (-0.96, 0.170, 0.45, 0.63),
        (-0.76, 0.180, 0.45, 0.645),
        (-0.64, 0.180, 0.45, 0.635),
        (-0.56, 0.175, 0.45, 0.555),
        (-0.36, 0.168, 0.45, 0.545),
        (-0.14, 0.145, 0.45, 0.555),
        (0.04,  0.120, 0.46, 0.565),
        (0.18,  0.095, 0.47, 0.535),
    ]
    rings = []
    for x, hw, bz, tz in stations:
        mid_z = lerp(bz, tz, 0.58)
        crown_z = tz + 0.018
        ring = [
            (x, -hw * 0.94, bz),
            (x, -hw, mid_z),
            (x, -hw * 0.72, tz),
            (x, 0.0, crown_z),
            (x, hw * 0.72, tz),
            (x, hw, mid_z),
            (x, hw * 0.94, bz),
            (x, 0.0, bz - 0.01),
        ]
        rings.append(ring)

    def seat_color(j, i, c):
        if i in (2, 3):
            return SEAT_DARK
        if i in (1, 4):
            if -0.82 < c.x < -0.25:
                return TEAL_DARK
            return SEAT_BOLSTER
        return SEAT_DARK

    seat.loft(rings, seat_color, cap_start=SEAT_DARK, cap_end=SEAT_DARK, smooth=True)

    strap_pts = [
        (-0.66, -0.182, 0.47),
        (-0.66, -0.184, 0.57),
        (-0.66, -0.135, 0.648),
        (-0.66, 0.0, 0.665),
        (-0.66, 0.135, 0.648),
        (-0.66, 0.184, 0.57),
        (-0.66, 0.182, 0.47),
    ]
    seat.tube(strap_pts, 0.011, RUBBER, sides=8, smooth=True,
              scale_xy=[(1.6, 0.55)] * len(strap_pts))

    return seat


# Shared grip anchor so handlebars and rider hands lock together cleanly
GRIP_X = 0.185
GRIP_Y = 0.305
GRIP_Z = 0.855
STEER_PIVOT = (0.28, 0.0, 0.74)


def build_handlebars():
    """Steerable handlebar assembly pivoted at STEER_PIVOT."""
    hb = Part("Handlebars", origin=STEER_PIVOT, smooth_angle=45.0)

    # Steering column stem extending solidly down into the console rubber boot
    hb.tube([(0.305, 0.0, 0.58), (0.255, 0.0, 0.845)], [0.040, 0.032],
            GUNMETAL, sides=12, cap_start=GUNMETAL, cap_end=GUNMETAL, smooth=True)

    # Center padded handlebar shroud / clamp cover
    hb.box(0.245, 0.0, 0.825, 0.085, 0.21, 0.068, RUBBER, bevel=0.022, rot_y=0.20, smooth=True)
    hb.box(0.228, 0.0, 0.845, 0.022, 0.13, 0.032, ORANGE, bevel=0.008, rot_y=0.20, smooth=False)

    for side in (-1, 1):
        bar_pts = [
            (0.25, side * 0.06, 0.855),
            (0.24, side * 0.14, 0.865),
            (0.21, side * 0.21, 0.862),
            (GRIP_X, side * GRIP_Y, GRIP_Z),
            (GRIP_X - 0.022, side * (GRIP_Y + 0.065), GRIP_Z - 0.006),
        ]
        hb.tube(bar_pts, 0.016, GUNMETAL, sides=10, cap_start=GUNMETAL, cap_end=RUBBER, smooth=True)

        grip_pts = [
            (0.205, side * (GRIP_Y - 0.068), 0.860),
            (GRIP_X, side * GRIP_Y, GRIP_Z),
            (GRIP_X - 0.020, side * (GRIP_Y + 0.062), GRIP_Z - 0.006),
        ]
        hb.tube(grip_pts, 0.022, RUBBER, sides=12, cap_start=RUBBER, cap_end=RUBBER, smooth=True)

        hb.box(0.205, side * 0.215, 0.842, 0.045, 0.038, 0.046, RUBBER, bevel=0.008, smooth=False)
        hb.box(0.232, side * 0.255, 0.845, 0.018, 0.068, 0.018, METAL, bevel=0.004, smooth=False)

    # Red emergency kill-switch cap on port switch pod
    hb.ellipsoid((0.188, 0.212, 0.875), 0.012, 0.012, 0.012, ORANGE_HI, rings=6, segs=8, smooth=True)

    return hb


def build_rider():
    """Athletic seated rider leaning forward, gripping the bars, feet in footwells."""
    rider = Part("Rider", smooth_angle=52.0)

    neck_base = Vector((-0.23, 0.0, 1.13))
    neck_top = Vector((-0.20, 0.0, 1.21))

    # 1. Pelvis & Torso (athletic forward lean ~22 deg, cleanly sized inside PFD!)
    torso_stations = [
        # (center, rx_front_back, ry_width)
        (Vector((-0.49, 0.0, 0.565)), 0.112, 0.152),  # seated base
        (Vector((-0.46, 0.0, 0.640)), 0.118, 0.164),  # hips
        (Vector((-0.41, 0.0, 0.750)), 0.098, 0.140),  # waist
        (Vector((-0.35, 0.0, 0.885)), 0.106, 0.152),  # lower ribcage (inside PFD)
        (Vector((-0.285, 0.0, 1.025)), 0.112, 0.172),  # chest / shoulders
        (Vector((-0.245, 0.0, 1.112)), 0.088, 0.150),  # upper trapezius
        (Vector((-0.228, 0.0, 1.148)), 0.060, 0.068),  # collar
    ]
    t_rings = []
    segs = 16
    for ctr, rx, ry in torso_stations:
        ring = []
        for s in range(segs):
            ang = TAU * s / segs
            ca, sa = math.cos(ang), math.sin(ang)
            x_off = rx * ca * (1.04 if ca > 0 else 0.94)
            y_off = ry * sa
            ring.append(Vector((ctr.x + x_off, ctr.y + y_off, ctr.z)))
        t_rings.append(ring)

    rider.loft(t_rings, WETSUIT, cap_start=WETSUIT, cap_end=WETSUIT, smooth=True)

    # 2. High-Visibility Segmented Life Jacket (PFD) cleanly enveloping the torso!
    # Every station is strictly outside torso (+0.025 m margin) so ZERO clipping!
    pfd_levels = [
        # (z, cx, rx, ry)
        (0.735, -0.415, 0.132, 0.168),  # bottom hem
        (0.825, -0.375, 0.138, 0.178),  # lower panels
        (0.935, -0.325, 0.146, 0.190),  # mid chest
        (1.040, -0.278, 0.142, 0.182),  # upper chest (tapers inside armholes)
        (1.100, -0.252, 0.118, 0.142),  # collar base
    ]
    pfd_rings = []
    pfd_segs = 20
    for z, cx, rx, ry in pfd_levels:
        ring = []
        for s in range(pfd_segs):
            # Offset by half-segment so segment 0 straddles dead-center front (+x) for a clean zipper!
            ang = TAU * (s - 0.5) / pfd_segs
            ca, sa = math.cos(ang), math.sin(ang)
            # Squared-off athletic foam vest contour
            sq = 1.0 + 0.05 * math.cos(4 * ang)
            px = cx + rx * ca * sq * (1.06 if ca > 0 else 1.02)
            py = ry * sa * sq
            ring.append(Vector((px, py, z)))
        pfd_rings.append(ring)

    def pfd_color(j, i, c):
        # i == 0 is the exact center front vertical zipper strip!
        if i == 0:
            return PFD_DARK
        # Side gussets (port & starboard ribs, i around 4..6 and 14..16)
        if i in (4, 5, 6, 14, 15, 16):
            return PFD_DARK
        # Clean symmetric high-vis amber reflective stripes on upper chest & upper back
        if j == 2 and i in (2, 18, 9, 10, 11):
            return PFD_TRIM
        return PFD_ORANGE

    rider.loft(pfd_rings, pfd_color, cap_start=PFD_DARK, cap_end=PFD_DARK, smooth=True)

    # PFD shoulder straps curving smoothly & snugly over trapezius from front to back
    for side in (-1, 1):
        strap = [
            (-0.188, side * 0.086, 1.072),
            (-0.220, side * 0.090, 1.128),
            (-0.285, side * 0.090, 1.122),
            (-0.332, side * 0.086, 1.062),
        ]
        rider.tube(strap, 0.024, PFD_ORANGE, sides=8, cap_start=PFD_ORANGE, cap_end=PFD_ORANGE,
                   smooth=True, scale_xy=[(0.48, 1.45)] * len(strap))

    # Two horizontal black webbing waist belts hugging the PFD snugly + front buckles
    for bz, bx, rx, ry in [(0.795, -0.388, 0.141, 0.181), (0.895, -0.343, 0.148, 0.191)]:
        belt_pts = []
        for s in range(20):
            ang = TAU * s / 20
            ca, sa = math.cos(ang), math.sin(ang)
            sq = 1.0 + 0.05 * math.cos(4 * ang)
            px = bx + (rx + 0.004) * ca * sq * (1.06 if ca > 0 else 1.02)
            py = (ry + 0.004) * sa * sq
            belt_pts.append((px, py, bz))
        rider.tube(belt_pts, 0.012, PFD_DARK, sides=6, closed=True, smooth=False,
                   scale_xy=[(1.35, 0.50)] * len(belt_pts))
        rider.box(bx + rx * 1.10, 0.0, bz - 0.016, 0.024, 0.056, 0.032, RUBBER,
                  bevel=0.006, rot_y=0.36, smooth=False)

    # 3. Legs (Thighs, Knees, Calves & Neoprene Booties planted firmly on Footwells)
    for side in (-1, 1):
        hip = Vector((-0.46, side * 0.105, 0.615))
        mid_thigh = Vector((-0.26, side * 0.215, 0.595))
        knee = Vector((-0.075, side * 0.245, 0.545))
        calf = Vector((-0.145, side * 0.305, 0.385))
        ankle = Vector((-0.215, side * 0.335, 0.215))

        leg_path = [
            hip,
            hip.lerp(mid_thigh, 0.5),
            mid_thigh,
            mid_thigh.lerp(knee, 0.65),
            knee,
            knee.lerp(calf, 0.45),
            calf,
            calf.lerp(ankle, 0.60),
            ankle,
        ]
        leg_radii = [0.088, 0.086, 0.078, 0.068, 0.060, 0.061, 0.063, 0.048, 0.040]
        leg_scale = [(1.0, 1.05), (1.0, 1.04), (1.0, 1.02), (1.0, 1.0),
                     (1.04, 0.96), (1.05, 0.96), (1.06, 0.95), (1.0, 1.0), (1.0, 1.0)]

        def leg_col(j, i, c):
            if j in (3, 4) and c.x > -0.10:
                return PFD_DARK
            if j in (1, 2) and abs(c.y) > 0.22:
                return WETSUIT_SEAM
            return WETSUIT

        rider.tube(leg_path, leg_radii, leg_col, sides=12,
                   cap_start=WETSUIT, cap_end=WETSUIT, smooth=True, scale_xy=leg_scale)

        rider.ellipsoid(hip, 0.086, 0.082, 0.082, WETSUIT, rings=6, segs=10, smooth=True)
        rider.ellipsoid(knee, 0.062, 0.056, 0.060, PFD_DARK, rings=6, segs=10, smooth=True)

        # Neoprene Water Bootie planted flat on footwell EVA mat
        foot_pts = [
            (-0.255, side * 0.330, 0.195),
            (-0.185, side * 0.340, 0.198),
            (-0.085, side * 0.352, 0.190),
            (-0.010, side * 0.362, 0.182),
        ]
        foot_r = [0.038, 0.042, 0.043, 0.028]
        foot_s = [(0.82, 1.08), (0.88, 1.06), (0.72, 1.15), (0.62, 1.12)]
        rider.tube(foot_pts, foot_r, WETSUIT, sides=10,
                   cap_start=BOOT_SOLE, cap_end=BOOT_SOLE, smooth=True, scale_xy=foot_s)
        rider.box(-0.132, side * 0.346, 0.162, 0.25, 0.088, 0.022, BOOT_SOLE, bevel=0.025, smooth=False)

    # 4. Shoulders, Athletic Arms & Hands gripping Handlebars (smoothly tucked into PFD armholes!)
    for side in (-1, 1):
        shoulder_root = Vector((-0.268, side * 0.168, 1.045))
        shoulder = Vector((-0.255, side * 0.200, 1.040))
        bicep_mid = Vector((-0.170, side * 0.265, 0.965))
        elbow = Vector((-0.070, side * 0.305, 0.895))
        forearm_mid = Vector((0.040, side * 0.308, 0.875))
        wrist = Vector((0.145, side * 0.306, 0.860))

        # Smooth shoulder deltoid flowing directly out of torso armhole
        rider.ellipsoid(shoulder, 0.062, 0.056, 0.062, WETSUIT, rings=8, segs=12, smooth=True)

        # Short-sleeve upper arm (wetsuit -> teal cuff band)
        sleeve_end = shoulder.lerp(elbow, 0.56)
        cuff_end = shoulder.lerp(elbow, 0.62)
        rider.tube([shoulder_root, shoulder, bicep_mid, sleeve_end, cuff_end],
                   [0.060, 0.060, 0.054, 0.050, 0.051],
                   lambda j, i, c: WETSUIT_SEAM if j == 3 else WETSUIT,
                   sides=12, cap_start=WETSUIT, cap_end=WETSUIT_SEAM, smooth=True)

        # Bare sunlit lower bicep, elbow & forearm to wrist
        rider.tube([sleeve_end, elbow, forearm_mid, wrist],
                   [0.047, 0.044, 0.042, 0.032], SKIN,
                   sides=12, cap_start=SKIN, cap_end=SKIN, smooth=True)
        rider.ellipsoid(elbow, 0.045, 0.042, 0.044, SKIN, rings=6, segs=10, smooth=True)

        # Sculpted Hand curled tightly over handlebar grip
        rider.ellipsoid((GRIP_X - 0.012, side * GRIP_Y, GRIP_Z + 0.018),
                        0.036, 0.042, 0.024, SKIN, rings=6, segs=10, smooth=True)
        finger_arc = [
            (GRIP_X + 0.012, side * GRIP_Y, GRIP_Z + 0.020),
            (GRIP_X + 0.030, side * GRIP_Y, GRIP_Z + 0.002),
            (GRIP_X + 0.016, side * GRIP_Y, GRIP_Z - 0.022),
            (GRIP_X - 0.008, side * GRIP_Y, GRIP_Z - 0.022),
        ]
        rider.tube(finger_arc, 0.016, SKIN, sides=8, cap_start=SKIN, cap_end=SKIN,
                   smooth=True, scale_xy=[(0.75, 2.2)] * len(finger_arc))
        thumb_arc = [
            (GRIP_X - 0.018, side * (GRIP_Y - 0.030), GRIP_Z + 0.008),
            (GRIP_X - 0.002, side * (GRIP_Y - 0.036), GRIP_Z - 0.016),
            (GRIP_X + 0.016, side * (GRIP_Y - 0.024), GRIP_Z - 0.022),
        ]
        rider.tube(thumb_arc, 0.012, SKIN, sides=8, cap_start=SKIN, cap_end=SKIN, smooth=True)

    # 5. Neck, Sculpted Head, Natural Swept Hair & Sleek Sport Sunglasses
    rider.tube([neck_base, neck_top, Vector((-0.185, 0.0, 1.25))],
               [0.056, 0.051, 0.048], SKIN, sides=12, cap_start=WETSUIT, cap_end=SKIN, smooth=True)

    head_layers = [
        (1.208, -0.155, 0.040, 0.030, 0.034),
        (1.235, -0.172, 0.072, 0.055, 0.060),
        (1.272, -0.178, 0.088, 0.078, 0.072),
        (1.310, -0.182, 0.092, 0.092, 0.076),
        (1.348, -0.185, 0.088, 0.098, 0.077),
        (1.385, -0.190, 0.074, 0.092, 0.070),
        (1.412, -0.194, 0.046, 0.062, 0.048),
    ]
    h_rings = []
    h_segs = 16
    for z, cx, rxf, rxb, ry in head_layers:
        ring = []
        for s in range(h_segs):
            ang = TAU * s / h_segs
            ca, sa = math.cos(ang), math.sin(ang)
            rx = rxf if ca >= 0 else rxb
            nose = 0.013 * max(0.0, ca) ** 6 if 1.265 < z < 1.320 else 0.0
            ring.append(Vector((cx + rx * ca + nose, ry * sa, z)))
        h_rings.append(ring)

    def head_col(j, i, c):
        if c.z > 1.352 or (c.x < -0.205 and c.z > 1.250):
            return HAIR
        if c.z < 1.235 and c.x < -0.175:
            return SKIN_SHADE
        return SKIN

    rider.loft(h_rings, head_col, cap_start=SKIN_SHADE, cap_end=HAIR, smooth=True)

    for side in (-1, 1):
        rider.ellipsoid((-0.188, side * 0.076, 1.302), 0.016, 0.012, 0.024,
                        SKIN_SHADE, rings=6, segs=8, smooth=True)

    # Organic wind-swept hair smoothly hugging the skull & nape (no sharp back shelf!)
    rider.ellipsoid((-0.200, 0.0, 1.356), 0.096, 0.081, 0.066, HAIR,
                    rings=8, segs=14, rot_euler=(0.0, -0.18, 0.0), smooth=True)
    rider.ellipsoid((-0.215, 0.0, 1.318), 0.076, 0.072, 0.062, HAIR,
                    rings=8, segs=12, rot_euler=(0.0, -0.25, 0.0), smooth=True)
    # Subtle swept-back top quiff
    rider.tube([
        (-0.130, 0.0, 1.384),
        (-0.182, 0.0, 1.404),
        (-0.240, 0.0, 1.388),
        (-0.270, 0.0, 1.352),
    ], [0.028, 0.046, 0.044, 0.022], HAIR, sides=10,
       cap_start=HAIR, cap_end=HAIR, smooth=True,
       scale_xy=[(0.60, 1.35), (0.60, 1.35), (0.65, 1.25), (0.65, 1.10)])

    # Sleek Wrap-Around Sport Sunglasses (dark frames + glossy lenses + subtle orange temples)
    visor_pts = [
        (-0.162, -0.075, 1.314),
        (-0.104, -0.056, 1.312),
        (-0.086, 0.000, 1.314),
        (-0.104, 0.056, 1.312),
        (-0.162, 0.075, 1.314),
    ]
    rider.tube(visor_pts, 0.015, SHADES_LENS, sides=8, cap_start=SHADES_LENS, cap_end=SHADES_LENS,
               smooth=True, scale_xy=[(1.20, 0.50)] * len(visor_pts))
    brow_pts = [(p[0] + 0.002, p[1], p[2] + 0.013) for p in visor_pts]
    rider.tube(brow_pts, 0.0045, SHADES_FRAME, sides=6, cap_start=SHADES_FRAME, cap_end=SHADES_FRAME, smooth=True)
    for side in (-1, 1):
        rider.tube([(-0.150, side * 0.074, 1.318), (-0.195, side * 0.077, 1.320)],
                   0.005, ORANGE, sides=6, cap_start=ORANGE, cap_end=ORANGE, smooth=True)

    # Coiled red safety kill-switch lanyard draping softly from port switch pod to PFD buckle
    lanyard = [
        (0.188, 0.212, 0.855),
        (0.105, 0.185, 0.775),
        (-0.015, 0.140, 0.742),
        (-0.135, 0.090, 0.760),
        (-0.220, 0.035, 0.798),
    ]
    rider.tube(lanyard, 0.0065, ORANGE_HI, sides=6, cap_start=ORANGE_HI, cap_end=ORANGE_HI, smooth=True)

    return rider


def make_vertex_material(name, roughness=0.4, metallic=0.05, spec=0.5, coat=0.0):
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
        bsdf.inputs["Coat Roughness"].default_value = 0.08
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
        bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
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

        bpy.ops.object.light_add(type="AREA", location=(4, -4, 7))
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

    # Hero 3/4 bow-port camera (Blender +X is port, -Y is bow, +Z is up)
    target = Vector((0.0, 0.05, 0.56))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.9
    camera.location = target + Vector((4.8, -4.4, 2.35))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    key.location = Vector((4.2, -3.6, 6.2))
    key.rotation_euler = (Vector((0, 0, 0.6)) - key.location).to_track_quat("-Z", "Y").to_euler()
    key.data.energy = 820
    key.data.size = 4.2

    for obj in studio.objects:
        obj.hide_set(True)

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 44
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    return studio, camera, target


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    hull_part = build_hull()
    trim_part = build_trim_and_mats()
    seat_part = build_seat()
    glass_part = build_windscreen()
    metal_part = build_metal_hardware()
    bars_part = build_handlebars()
    rider_part = build_rider()

    mat_hull = make_vertex_material("Jetski fiberglass", roughness=0.22, metallic=0.06, spec=0.65, coat=0.45)
    mat_rubber = make_vertex_material("Jetski rubber", roughness=0.76, metallic=0.02, spec=0.28)
    mat_seat = make_vertex_material("Jetski vinyl", roughness=0.58, metallic=0.02, spec=0.38)
    mat_glass = make_vertex_material("Smoked acrylic", roughness=0.08, metallic=0.14, spec=0.88)
    mat_metal = make_vertex_material("Marine metal", roughness=0.28, metallic=0.82, spec=0.60)
    mat_rider = make_vertex_material("Rider gear", roughness=0.58, metallic=0.00, spec=0.34)

    coll = bpy.data.collections.new("Jetski")
    scene.collection.children.link(coll)

    hull_obj = hull_part.finish(coll, mat_hull)
    trim_obj = trim_part.finish(coll, mat_rubber)
    seat_obj = seat_part.finish(coll, mat_seat)
    glass_obj = glass_part.finish(coll, mat_glass)
    metal_obj = metal_part.finish(coll, mat_metal)
    bars_obj = bars_part.finish(coll, mat_rubber)
    rider_obj = rider_part.finish(coll, mat_rider)

    objs = [hull_obj, trim_obj, seat_obj, glass_obj, metal_obj, bars_obj, rider_obj]
    for ob in objs[1:]:
        ob.parent = hull_obj

    glb_path = ROOT / "assets" / "models" / "jetski_mid.glb"
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
    print("JETSKI", glb_path, counts, "TOTAL_POLYS:", sum(counts.values()))

    studio, camera, target = setup_studio(scene)
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            view = area.spaces.active
            view.shading.color_type = "VERTEX"
            view.overlay.show_overlays = False
            view.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            view.region_3d.view_location = target
            view.region_3d.view_distance = 5.5
            view.region_3d.view_perspective = "ORTHO"

    bpy.context.preferences.filepaths.save_version = 0
    blend_path = ROOT / "art" / "jetski.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

    scene.render.filepath = str(ROOT / "art" / "jetski_preview.png")
    bpy.ops.render.render(write_still=True)

    if "--views" in sys.argv:
        idx = sys.argv.index("--views")
        if idx + 1 < len(sys.argv):
            out_dir = Path(sys.argv[idx + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            scene.render.resolution_x, scene.render.resolution_y = 1000, 680
            scene.cycles.samples = 24
            views = [
                ("profile_port", Vector((6.0, 0.0, 0.65)), Vector((0.0, 0.0, 0.58)), 3.9),
                ("stern_stbd", Vector((-4.5, 4.4, 2.25)), Vector((0.0, 0.05, 0.56)), 3.9),
                ("bow_front", Vector((1.4, -5.8, 1.35)), Vector((0.0, 0.0, 0.62)), 2.8),
                ("closeup_rider", Vector((3.2, -2.2, 1.55)), Vector((0.0, 0.15, 0.85)), 2.0),
            ]
            for vname, offset, vt, oscale in views:
                camera.location = vt + offset
                camera.rotation_euler = (vt - camera.location).to_track_quat("-Z", "Y").to_euler()
                camera.data.ortho_scale = oscale
                scene.render.filepath = str(out_dir / f"{vname}.png")
                bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
