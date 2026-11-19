# Builds the mid-poly Issaquah class car ferry in Blender (run inside Blender:
# exec(open(path).read()), or blender -b -P art/issaquah_mid.py) and exports it to
# assets/models/issaquah_mid.glb (glTF, +Y up, vertex colours, flat shaded).
# Built on the Evergreen State's script (art/ferry_mid.py): the same WSF look, a
# longer, beamier hull (100 m over the guards, 24 m in the beam) and WSF's first
# two-level car deck. Real scale, in metres; game frame: double ended, +Z and -Z ends
# alike, +Y up, waterline at y = 0.
# The car deck at CAR_DECK (laid out after WSF's two-level boats): a full-height centre
# tunnel of three lanes for trucks and vans between the casings, and outboard of each
# casing a wing of two lanes under a "tween deck" (the mezzanine, two lanes wide, top
# at MEZ_TOP, open below with no posts) running |z| < MEZ_Z. Its outer lane carries on
# toward each end as a single-lane ramp down into the hull's rounded corner, its foot
# at RAMP_Z; its inner half stops at MEZ_Z, a railed edge. Cars in the main deck's
# wing lanes park inside |z| ~ MEZ_Z and turn in past the ramp to leave.
# Above: the passenger deck at DECKHEAD, cabin, sun deck, twin funnels and pilothouses
# as the Evergreen State's, lifted LIFT for the taller car deck. Two rows of side
# openings, one onto each car-deck level.
#
# Numbers the game wants (game frame, metres):
#   CAR_DECK 2.85; MEZ_TOP 5.6; tunnel lanes x = 0, +-3.5 (|x| < 5.4: trucks); wing
#   lanes +-8.4, +-11.6 on both decks (cars), over |z| < MEZ_Z 27; ramps on the outer
#   lane from MEZ_Z (centre x 11.65) down to RAMP_Z 42 (centre 8.9). Masthead
#   lanterns MAST_TOP + LIFT at z = +-MAST_Z.
import bpy, bmesh, math, os
from mathutils import Vector

PAL = {
    "hull": (0.1, 0.1, 0.11), "antifoul": (0.4, 0.13, 0.11), "guard": (0.42, 0.43, 0.45),
    "green": (0.07, 0.36, 0.25), "white": (0.94, 0.95, 0.94), "deck": (0.4, 0.41, 0.42),
    "deckp": (0.5, 0.53, 0.52), "ceiling": (0.82, 0.83, 0.82), "panel": (0.66, 0.68, 0.7),
    "glass": (0.16, 0.22, 0.27), "window": (0.16, 0.22, 0.27), "pane": (0.62, 0.74, 0.8),
    "dark": (0.1, 0.1, 0.11), "black": (0.07, 0.07, 0.07), "steel": (0.6, 0.62, 0.64),
    "orange": (0.95, 0.42, 0.1), "red": (0.75, 0.12, 0.1), "lamp": (0.96, 0.95, 0.86),
    "yellow": (0.88, 0.7, 0.12), "bronze": (0.55, 0.42, 0.22), "apron": (0.4, 0.34, 0.29),
    "mesh": (0.72, 0.76, 0.75), "dkwall": (0.2, 0.21, 0.22), "gold": (0.78, 0.6, 0.2),
}
ROLES = ("glass", "window", "lamp")
UP = Vector((0, 1, 0))


def G(p): return Vector((p.x, -p.z, p.y))
def V(x, y, z): return Vector((x, y, z))
def lerp(a, b, t): return a + (b - a) * t


coll = bpy.data.collections.get("Issaquah") or bpy.data.collections.new("Issaquah")
if coll.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(coll)
for o in list(coll.objects):
    bpy.data.objects.remove(o, do_unlink=True)
mat = bpy.data.materials.get("VertexColour") or bpy.data.materials.new("VertexColour")
mat.use_nodes = True
_nt = mat.node_tree
_attr = _nt.nodes.get("Attr") or _nt.nodes.new("ShaderNodeVertexColor")
_attr.name = "Attr"; _attr.layer_name = "Col"
_nt.links.new(_attr.outputs["Color"], _nt.nodes["Principled BSDF"].inputs["Base Color"])

BMS = {}
THIN_PART = [None]  # set while thin() draws: the part its faces go to
LIFTED = [0.0]      # added to y while the upper works (built at the Evergreen's heights) draw


def bm_for(key):
    role = THIN_PART[0] or (key if key in ROLES else "fixed")
    if role not in BMS:
        bm = bmesh.new(); bm.loops.layers.color.new("Col"); BMS[role] = bm
    return BMS[role]


def face(pts, key):
    """One face in the given winding (callers orient it); colour by palette key."""
    if LIFTED[0]: pts = [p + V(0, LIFTED[0], 0) for p in pts]
    q = [pts[0]]
    for p in pts[1:]:
        if (p - q[-1]).length > 1e-5: q.append(p)
    if len(q) > 2 and (q[0] - q[-1]).length < 1e-5: q.pop()
    if len(q) < 3: return
    bm = bm_for(key); cl = bm.loops.layers.color["Col"]
    try:
        f = bm.faces.new([bm.verts.new(G(p)) for p in q])
    except ValueError:
        return
    f.smooth = False
    # (A bmesh `color` layer is bytes stored as sRGB and exported linear, so the palette
    # goes in as it is; Models turns the glTF's linear colours back into sRGB.)
    for l in f.loops: l[cl] = (*PAL[key], 1.0)


def normal(pts):
    n = Vector()
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += a.cross(b)
    return n


def centre(pts): return sum(pts, Vector()) / len(pts)


def hface(pts, key, up=True):
    """A horizontal face, wound to face up (or down)."""
    face(pts if (normal(pts).y > 0) == up else pts[::-1], key)


def loft(rings, key, closed_ring=True, closed_path=False, caps=True, cap_key=None):
    """Quads between successive rings (same vertex count, same direction). `key` is a
    palette key or fn(i, j, centroid) -> key. The whole surface is wound outward from
    the rings' centres (by majority, so concave sections like bulwarks stay right)."""
    n, quads = len(rings[0]), []
    m = len(rings) if closed_path else len(rings) - 1
    for i in range(m):
        a, b = rings[i], rings[(i + 1) % len(rings)]
        ax = (centre(a) + centre(b)) * 0.5
        for j in range(n if closed_ring else n - 1):
            k = (j + 1) % n
            quads.append((i, j, [a[j], a[k], b[k], b[j]], ax))
    s = sum(normal(q).dot(centre(q) - ax) for _, _, q, ax in quads)
    for i, j, q, _ in quads:
        c = key(i, j, centre(q)) if callable(key) else key
        face(q if s > 0 else q[::-1], c)
    if caps and not closed_path and closed_ring:
        ck = cap_key or (key if not callable(key) else "black")
        for r, o in ((rings[0], rings[1]), (rings[-1], rings[-2])):
            out = centre(r) - centre(o)
            face(r if normal(r).dot(out) > 0 else r[::-1], ck)


def rect(cx, y, cz, hw, hd, ch=0.0, chb=None):
    """Horizontal rectangle (optionally chamfered: `ch` the +z corners, `chb` the -z)."""
    chb = ch if chb is None else chb
    pts = [(cx + hw, cz - hd + chb), (cx + hw, cz + hd - ch), (cx + hw - ch, cz + hd), (cx - hw + ch, cz + hd),
           (cx - hw, cz + hd - ch), (cx - hw, cz - hd + chb), (cx - hw + chb, cz - hd), (cx + hw - chb, cz - hd)]
    return [V(x, y, z) for x, z in pts]


def box(c, size, key):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    loft([rect(c.x, c.y - hy, c.z, hx, hz), rect(c.x, c.y + hy, c.z, hx, hz)], key)


def box_between(a, b, w, key):
    """A square-section member from a to b, its sides square to the x axis."""
    ax = (b - a).normalized()
    e1 = V(1, 0, 0); e2 = ax.cross(e1).normalized()
    ring = lambda c: [c + (e1 * sx + e2 * sy) * (w / 2) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    loft([ring(a), ring(b)], key)


def frame(ax):
    e1 = ax.cross(V(0.3, 0, 1) if abs(ax.z) < 0.9 else V(1, 0, 0)).normalized()
    return e1, ax.cross(e1).normalized()


def circle(c, ax, r, n, a0=0.0):
    e1, e2 = frame(ax)
    return [c + (e1 * math.cos(a0 + math.tau * i / n) + e2 * math.sin(a0 + math.tau * i / n)) * r for i in range(n)]


THIN = 0.035  # least pipe radius (m) that casts a clean shadow: ~2 shadow map texels across


def thin(r, key, draw):
    """Draws a pipe of radius `r` by draw(k), its radii scaled by k. One thinner than
    THIN would cast a shadow of broken dashes that crawl as she moves, so it goes to
    the "thin" part (drawn, casting no shadow), and a copy thickened to THIN to
    "thinshadow" (casting its shadow, never drawn)."""
    if r >= THIN or key in ROLES or THIN_PART[0]:
        draw(1.0); return
    for part, k in (("thin", 1.0), ("thinshadow", THIN / r)):
        THIN_PART[0] = part; draw(k)
    THIN_PART[0] = None


def cyl(a, b, r0, r1, n, key, a0=None):
    thin(max(r0, r1), key, lambda k: _cyl(a, b, r0 * k, r1 * k, n, key, a0))


def _cyl(a, b, r0, r1, n, key, a0=None):
    ax = (b - a).normalized()
    a0 = math.pi / n if a0 is None else a0
    loft([circle(a, ax, r0, n, a0), circle(b, ax, r1, n, a0)], key)


def tube(path, r, n, key, closed=False):
    thin(r, key, lambda k: _tube(path, r * k, n, key, closed))


def _tube(path, r, n, key, closed=False):
    """A round pipe along a polyline (rings square to the mean tangent)."""
    rings, prev = [], None
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        e1 = (prev - prev.dot(t) * t).normalized() if prev is not None else frame(t)[0]
        prev = e1; e2 = t.cross(e1)
        rings.append([p + (e1 * math.cos(math.tau * k / n) + e2 * math.sin(math.tau * k / n)) * r for k in range(n)])
    loft(rings, key, closed_path=closed)


def torus(c, ax, R, r, n1, n2, key):
    e1, e2 = frame(ax)
    rings = []
    for i in range(n1):
        a = math.tau * i / n1
        d = e1 * math.cos(a) + e2 * math.sin(a)
        rings.append([c + d * (R + r * math.cos(math.tau * k / n2)) + ax * (r * math.sin(math.tau * k / n2)) for k in range(n2)])
    for i in range(n1):
        a, b = rings[i], rings[(i + 1) % n1]
        ca = c + (e1 * math.cos(math.tau * (i + 0.5) / n1) + e2 * math.sin(math.tau * (i + 0.5) / n1)) * R
        for k in range(n2):
            q = [a[k], a[(k + 1) % n2], b[(k + 1) % n2], b[k]]
            face(q if normal(q).dot(centre(q) - ca) > 0 else q[::-1], key)


def panel(c, n, w, h, d, key):
    """A flat box standing on a wall: centre `c` on its face, `n` the wall's outward
    (horizontal) normal, `w` along the wall, `h` tall, `d` proud of it."""
    t = V(n.z, 0, -n.x)
    ring = lambda o: [c + n * o + t * (sw * w / 2) + UP * (sh * h / 2) for sw, sh in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    loft([ring(-0.01), ring(d)], key)


def horiz_normals(pts, closed):
    ns = []
    for i, p in enumerate(pts):
        a = pts[(i - 1) % len(pts)] if closed or i > 0 else p
        b = pts[(i + 1) % len(pts)] if closed or i < len(pts) - 1 else p
        t = b - a; t.y = 0; t.normalize()
        nrm = V(t.z, 0, -t.x)
        if nrm.dot(V(p.x, 0, p.z)) < 0: nrm = -nrm
        ns.append(nrm)
    return ns


# --- Plan outline -------------------------------------------------------------------
# Normalised: u along the half length (0 amidships, 1 at the end), v the half beam (1
# at the parallel body). At the deck her ends are one smooth oval, a superellipse from
# the parallel body round to the apron, that the hull sides, the forks and the green
# bulwarks all follow; under water her lines are much finer, so the hull's sides flare
# out toward the ends. `full` blends from the fine lines (0) to the deck's (1).

OVAL_Z, OVAL_P = 26.0, 2.3     # where the ends begin to round in, and how full they are


def deck_x(z):
    """Half beam of the hull at the deck at |z| (metres; the deck's end at HZ)."""
    t = min(max((abs(z) - OVAL_Z) / (HZ - OVAL_Z), 0.0), 1.0)
    return HB * max(0.0, 1.0 - t ** OVAL_P) ** (1.0 / OVAL_P)


def plan_v(u, full=1.0):
    u = min(abs(u), 1.0)
    t = max(0.0, (u - 0.3) / 0.7)
    fine = math.sqrt(max(0.0, 1.0 - t ** 2.2))
    return lerp(fine, deck_x(u * HZ) / HB, full)


# --- Dimensions (metres, game frame) ------------------------------------------------

HB = 13.6          # half beam of the hull at the deck (the guards stand 0.35 proud: 27.9 m)
HZ = 49.15         # half length of the hull at the deck (the guards' ends at 50.0)
GZ = 50.0          # the guards' ends
GUARD = 0.35
CAR_DECK = 2.85
GREEN_TOP = 3.92   # the green band up the hull side
DECKHEAD = 8.4     # underside of the passenger deck (the car deck's deckhead)
LIFT = DECKHEAD - 7.0   # the upper works are drawn at the Evergreen's heights, lifted this
PAX_DECK = 7.0     # (the upper works' own heights, before LIFT)
PAX_TOP = 7.3
RAKE = math.tan(math.radians(15.0))   # the forks' ends and the cabin's end faces lean back
FORK_Z = 44.0      # the forks' ends, where the hull sides round in to the car deck's opening
FORK_X = 6.0       # the forks' inner edges (over the casings)
GREEN_Z = 45.4     # the green bulwark's ends, at the apron's edge
CABIN_Z = 31.0     # the cabin's ends at the deck (raked back 15 degrees above)
WALK_Z = 32.6      # the walkway across the cabin's end, between the forks
SILL, HEAD, ROOF = 8.3, 9.75, 10.55
SUN = 10.75        # the sun deck (the cabin roof's top)
CASING_X0, CASING_X1, CASING_Z = 5.4, 6.8, 30.0
PH_Z0, PH_Z1, PH_HW = 23.4, 27.8, 5.0     # pilothouse (each end)
PH_SILL, PH_HEAD, PH_TOP = 12.4, 13.4, 13.7
MAST_Z, MAST_TOP = 24.3, 21.6     # on the pilothouse roofs, toward their inboard ends
STAIR_RUN = 5.6    # the open stair up inside each casing's end
FUNNEL_TOP = 14.8
# The tween decks (as WSF lays them out): each wing's two lanes on the main deck run
# under a tween deck of two lanes, flat over |z| < MEZ_Z; its outer lane runs on as a
# ramp down into the hull's rounded corner, its foot at RAMP_Z near the end.
MEZ_BOT, MEZ_TOP = 5.35, 5.6   # its plating (2.5 m clear under it, 2.8 over it)
MEZ_Z = 27.0       # its flat, |z| < MEZ_Z
RAMP_X = 10.0      # the ramp's inner edge at its top (between the wing's two lanes)
RAMP_Z, RAMP_FX = 42.0, 7.4   # the ramp's foot on the main deck, its inner edge there
LANES = (-3.5, 0.0, 3.5)      # tunnel: trucks and vans
WING = (8.4, 11.6)            # each wing's two lanes, on the main deck and the tween deck
POST_X = 10.0                 # the line between each wing's two lanes


def half_beam(z):
    """Half beam of the hull at the deck at z."""
    return HB * plan_v(z / HZ)


def side_pt(s, z, y, out=0.0):
    """Point on the hull side (s = +1 starboard... +x) at z, height y, and its outward normal."""
    dz = 0.05
    d = (half_beam(z + dz) - half_beam(z - dz)) / (2 * dz)
    n = V(s, 0, -d).normalized()
    return V(s * half_beam(z), y, z) + n * out, n


STATIONS = [0.0, 0.1, 0.2, 0.3, 0.38, 0.426, 0.47, 0.52, 0.57, 0.62, 0.67, 0.71, 0.75, 0.79, 0.83, 0.865,
            0.895, 0.92, 0.945, 0.965, 0.98, 0.99, 0.996, 1.0]
US = [-u for u in reversed(STATIONS[1:])] + STATIONS


def cabin_hd(y):
    """Half length of the cabin at height y, its end faces raked back."""
    return CABIN_Z - (y - PAX_TOP) * RAKE


def ring_at(y, sx, zt, d, full=1.0):
    """The hull's waterline at height y: x scaled by sx, its ends at +-zt, `d` out,
    `full` how full its ends are (see plan_v)."""
    stb = [V(HB * plan_v(u, full) * sx + d, y, u * zt) for u in US]
    return stb + [V(-p.x, y, p.z) for p in reversed(stb[1:-1])]


def zs_between(z0, z1, step=1.2):
    n = max(1, int(math.ceil((z1 - z0) / step)))
    return [lerp(z0, z1, i / n) for i in range(n + 1)]


# --- Hull ---------------------------------------------------------------------------

def hull():
    lines = [(-4.1, 0.8, 30.7, 0.0, 0.0), (-3.6, 0.92, 36.5, 0.0, 0.1), (-2.5, 0.975, 41.8, 0.0, 0.25),
             (-1.0, 0.995, 45.7, 0.0, 0.45), (0.0, 1.0, 47.2, 0.0, 0.6), (1.0, 1.0, 48.2, 0.0, 0.8), (2.15, 1.0, HZ, 0.0),
             (2.2, 1.0, GZ, GUARD), (2.78, 1.0, GZ, GUARD), (CAR_DECK, 1.0, GZ - 0.1, GUARD - 0.06)]
    rings = [ring_at(*l) for l in lines]

    def col(i, j, c):
        if c.y < 0.0: return "antifoul"
        if c.y < 2.17: return "hull"
        return "guard"
    loft(rings, col, caps=False)
    hface(rings[0], "antifoul", up=False)
    hface(rings[-1], "deck")
    # The aprons, worn bare steel, beyond the forks.
    for e in (1, -1):
        z0 = GREEN_Z - 0.3
        us = [u for u in STATIONS if u * (GZ - 0.1) > z0]
        stb = [V(HB * plan_v(u) + GUARD - 0.08, CAR_DECK + 0.006, e * u * (GZ - 0.1)) for u in [z0 / (GZ - 0.1)] + us]
        hface(stb + [V(-p.x, p.y, p.z) for p in reversed(stb)], "apron")
    # Under water at each end: a skeg, the propeller and the rudder abaft it.
    for e in (1, -1):
        box(V(0, -3.8, e * 35.0), (0.5, 0.9, 7.0), "antifoul")
        hub = V(0, -2.9, e * 41.9)
        cyl(V(0, -2.9, e * 39.0), hub, 0.22, 0.22, 6, "antifoul")
        cyl(hub, hub + V(0, 0, e * 0.6), 0.35, 0.2, 8, "bronze")
        for k in range(4):
            a = math.tau * k / 4 + 0.4
            tip = hub + V(math.cos(a), math.sin(a), 0) * 1.35 + V(0, 0, e * 0.3)
            loft([[hub + V(0, 0, e * 0.05) + V(-math.sin(a), math.cos(a), 0) * 0.25, hub + V(0, 0, e * 0.45),
                   tip + V(0, 0, e * 0.1)],
                  [hub + V(0, 0, e * 0.05) + V(-math.sin(a), math.cos(a), 0) * 0.25 + V(0, 0, 0.001), hub + V(0, 0, e * 0.45 + 0.001),
                   tip + V(0, 0, e * 0.1 + 0.001)]], "bronze")
        box(V(0, -2.3, e * 43.7), (0.4, 2.8, 1.6), "antifoul")


# The side openings: a low row onto the main deck's wings, a tall row onto the tween
# decks (with a cross of bars), the same pitch and in step. (y0, y1, half width, bars)
TIERS = [(4.2, 5.05, 1.3, False), (6.05, 7.7, 1.25, True)]
OPEN_Z = [-40.19 + k * 4.23 for k in range(20)]  # their centres, 20 down each side


def bulwarks():
    """The hull sides above the car deck: the green band to GREEN_Z, white to the
    passenger deck to the forks' raked ends, pierced by the two rows of ports, each with
    its corners filleted, the upper row's with a cross of round steel bars."""
    def band(s, y0, y1, z0, z1, key, top_key=None, in_key=None):
        prof = [(0.0, y0), (0.0, y1), (-0.3, y1), (-0.3, y0)]
        rings = []
        for z in zs_between(z0, z1):
            p, n = side_pt(s, z, 0.0)
            rings.append([p + n * u + UP * v for u, v in prof])
        loft(rings, lambda i, j, c: (top_key if j == 1 and top_key else in_key if j == 2 and in_key else key), cap_key=key)

    for s in (1, -1):
        band(s, CAR_DECK - 0.02, GREEN_TOP, -GREEN_Z, GREEN_Z, "green", "white", "dkwall")
        ys = [GREEN_TOP] + [y for t in TIERS for y in t[:2]] + [DECKHEAD + 0.02]
        for y0, y1 in zip(ys[::2], ys[1::2]):
            band(s, y0, y1, -FORK_Z, FORK_Z, "white")
        # The raked ends: a wedge from the deckhead out to the foot.
        for e in (1, -1):
            zb = FORK_Z + (DECKHEAD + 0.02 - GREEN_TOP) * RAKE
            pts = [side_pt(s, e * z, y) for z, y in ((FORK_Z, GREEN_TOP), (zb, GREEN_TOP), (FORK_Z, DECKHEAD + 0.02))]
            loft([[p for p, n in pts], [p - n * 0.3 for p, n in pts]], "white")
        for y0, y1, hw, bars in TIERS:
            edges = [-FORK_Z] + [z + d for z in OPEN_Z for d in (-hw, hw)] + [FORK_Z]
            for z0, z1 in zip(edges[::2], edges[1::2]):
                band(s, y0, y1, z0, z1, "white")
            f = min(0.28, (y1 - y0) * 0.3)
            for z in OPEN_Z:
                p, n = side_pt(s, z, (y0 + y1) / 2)
                t = V(n.z, 0, -n.x)
                mid = p - n * 0.15
                for sz in (-1, 1):
                    for sy in (-1, 1):
                        zc = z + sz * hw
                        cp, cn = side_pt(s, zc, 0.0)
                        yc = y1 if sy > 0 else y0
                        tz = V(cn.z, 0, -cn.x)
                        tri = lambda o: [cp + cn * o + UP * yc, cp + cn * o + UP * (yc - sy * f),
                                         cp + cn * o + UP * yc + tz * (s * sz * f)]
                        loft([tri(0.0), tri(-0.3)], "white")
                if bars:
                    cyl(mid + UP * -(y1 - y0) / 2, mid + UP * (y1 - y0) / 2, 0.06, 0.06, 6, "steel")
                    cyl(mid - t * (hw + 0.02), mid + t * (hw + 0.02), 0.06, 0.06, 6, "steel")
        # Inside: the side's frames, a port's pitch apart in quarters, from the dark lower
        # band up to the deckhead; a yellow kerb along the foot.
        pitch = 4.23 / 4
        z = OPEN_Z[0] - pitch / 2
        while z - pitch > -FORK_Z + 0.4: z -= pitch
        while z < FORK_Z - 0.4:
            p, n = side_pt(s, z, (GREEN_TOP + DECKHEAD) / 2, -0.3)
            panel(p, -n, 0.12, DECKHEAD - GREEN_TOP, 0.22, "white")
            z += pitch
        rings = []
        for z in zs_between(-FORK_Z, FORK_Z):
            p, n = side_pt(s, z, 0.0, -0.3)
            rings.append([p + n * u + UP * v for u, v in ((0.02, CAR_DECK), (0.02, CAR_DECK + 0.18),
                                                          (-0.2, CAR_DECK + 0.18), (-0.2, CAR_DECK))])
        loft(rings, "yellow")


# --- Car deck -----------------------------------------------------------------------

def car_deck():
    # The casings either side of the tunnel, carrying the stairs up to the cabin.
    cx, cw = (CASING_X0 + CASING_X1) / 2, CASING_X1 - CASING_X0
    cz = CASING_Z - STAIR_RUN       # where the solid casing ends and the stair bay begins
    for s in (1, -1):
        loft([rect(s * cx, CAR_DECK, 0, cw / 2, cz, 0.0), rect(s * cx, DECKHEAD, 0, cw / 2, cz, 0.0)], "white")
        for e in (1, -1):
            stair(s, e, cz)
        # Doors and fire stations on the tunnel face, a yellow-edged kerb along the foot.
        n = V(-s, 0, 0)
        for z in (-19.5, -8.0, 8.0, 19.5):
            panel(V(s * CASING_X0, CAR_DECK + 1.05, z), n, 0.9, 2.1, 0.04, "dark")
        for z in (-14.0, 0.0, 14.0):
            panel(V(s * CASING_X0, CAR_DECK + 1.3, z), n, 0.7, 0.8, 0.12, "red")
            panel(V(s * CASING_X1, MEZ_TOP + 1.3, z), -n, 0.7, 0.8, 0.12, "red")
        box(V(s * cx, CAR_DECK + 0.08, 0), (cw + 0.3, 0.16, 2 * cz + 0.3), "panel")
        # Yellow struts raked out from the casings' ends to the deckhead.
        for e in (1, -1):
            for x in (CASING_X0 + 0.25, CASING_X1 - 0.25):
                box_between(V(s * x, CAR_DECK, e * (CASING_Z - 0.15)), V(s * x, DECKHEAD - 0.05, e * (CASING_Z + 1.9)),
                            0.32, "yellow")
    # Lane lines: between the tunnel's three lanes, between each wing's two, and the
    # tunnel's edges past the casings.
    lines = [(x, -44.5, 44.5) for x in (-1.75, 1.75)]
    lines += [(s * POST_X, -MEZ_Z + 1.0, MEZ_Z - 1.0) for s in (1, -1)]
    lines += [(s * (CASING_X0 - 0.3), e0, e1) for s in (1, -1) for e0, e1 in ((CASING_Z + 0.5, 43.5), (-43.5, -CASING_Z - 0.5))]
    for x, z0, z1 in lines:
        z = z0
        while z < z1:
            box(V(x, CAR_DECK + 0.005, z + 1.0), (0.15, 0.01, 2.0), "yellow")
            z += 3.5
    # Deck beams across the deckhead (only under the forks past the walkway), curved
    # knees where they meet the hull sides, flat ceiling lights between them over each
    # lane (a shallow housing and its lens, flush on the deckhead), and under the tween
    # decks over the main deck's wing lanes; a big knee at each fork's end, arching
    # the wing's entrance.
    z = -42.0
    while z <= 42.01:
        hw = half_beam(z) - 0.3
        if abs(z) < WALK_Z:
            box(V(0, DECKHEAD - 0.13, z), (2 * hw, 0.26, 0.35), "ceiling")
        else:
            for s in (1, -1):
                box(V(s * (hw + FORK_X) / 2, DECKHEAD - 0.13, z), (hw - FORK_X, 0.26, 0.35), "ceiling")
        for s in (1, -1):
            knee(s, z, 0.9, 0.3)
        zl = z + 2.0
        for x in LANES + WING + tuple(-x for x in WING):
            if abs(x) < hw - 1.0 and abs(zl) < 43.0 and (abs(zl) < WALK_Z - 0.6 or abs(x) > FORK_X + 0.6):
                box(V(x, DECKHEAD - 0.03, zl), (0.7, 0.06, 1.6), "steel")
                box(V(x, DECKHEAD - 0.075, zl), (0.56, 0.03, 1.46), "lamp")
        if abs(zl) < MEZ_Z - 1.0:
            for x in WING + tuple(-x for x in WING):
                box(V(x, MEZ_BOT - 0.03, zl), (0.7, 0.06, 1.6), "steel")
                box(V(x, MEZ_BOT - 0.075, zl), (0.56, 0.03, 1.46), "lamp")
        z += 4.0
    for e in (1, -1):
        for s in (1, -1):
            knee(s, e * (FORK_Z - 0.2), 1.9, 0.4)


def ramp_edge(z):
    """The ramp's inner edge (x, outboard positive) at |z| between MEZ_Z and RAMP_Z."""
    return lerp(RAMP_X, RAMP_FX, min(max((abs(z) - MEZ_Z) / (RAMP_Z - MEZ_Z), 0.0), 1.0))


def ramp_y(z):
    """The ramp's (or the mezzanine's) top at |z|."""
    t = min(max((abs(z) - MEZ_Z) / (RAMP_Z - MEZ_Z), 0.0), 1.0)
    return lerp(MEZ_TOP, CAR_DECK + 0.01, t)


def tween_decks():
    """Each wing's mezzanine: a steel deck from the casing out to the hull side over
    |z| < MEZ_Z, clear span (no posts on the lanes under it), its outer lane running on
    toward each end as a ramp down into the hull's corner; railed along its inner end
    and up the ramps."""
    for s in (1, -1):
        inner = lambda z: half_beam(z) - 0.3
        # The flat.
        zs = zs_between(-MEZ_Z, MEZ_Z, 4.0)
        top = [V(s * CASING_X1, MEZ_TOP, z) for z in zs] + [V(s * inner(z), MEZ_TOP, z) for z in zs[::-1]]
        bot = [p + V(0, MEZ_BOT - MEZ_TOP, 0) for p in top]
        loft([bot, top], "panel", caps=False)
        hface(top, "deck")
        hface(bot, "ceiling", up=False)
        # Lane line between its two lanes, and its edge striped where it stops.
        z = -MEZ_Z + 0.5
        while z < MEZ_Z - 1.0:
            box(V(s * RAMP_X, MEZ_TOP + 0.005, z + 1.0), (0.15, 0.01, 2.0), "yellow")
            z += 3.5
        for e in (1, -1):
            box(V(s * (CASING_X1 + RAMP_X) / 2, MEZ_TOP + 0.005, e * (MEZ_Z - 0.15)), (RAMP_X - CASING_X1, 0.01, 0.3), "yellow")
            box(V(s * (CASING_X1 + RAMP_X) / 2, (MEZ_BOT + MEZ_TOP) / 2, e * (MEZ_Z + 0.01)),
                (RAMP_X - CASING_X1, MEZ_TOP - MEZ_BOT, 0.02), "yellow")
            # The ramp.
            zr = zs_between(MEZ_Z, RAMP_Z, 1.0)
            rings = []
            for zz in zr:
                y = ramp_y(zz)
                yb = max(CAR_DECK, y - (MEZ_TOP - MEZ_BOT))
                xi, xo = s * ramp_edge(zz), s * inner(zz)
                rings.append([V(xi, yb, e * zz), V(xi, y, e * zz), V(xo, y, e * zz), V(xo, yb, e * zz)])
            loft(rings, lambda i, j, c: "deck" if j == 1 else "panel", caps=False)
            # Chevrons up its middle and a yellow foot.
            for zz in zs_between(MEZ_Z + 1.5, RAMP_Z - 1.5, 2.5):
                xm = s * (ramp_edge(zz) + inner(zz)) / 2
                box(V(xm, ramp_y(zz) + 0.02, e * zz), (1.2, 0.02, 0.18), "yellow")
            box(V(s * (RAMP_FX + inner(RAMP_Z)) / 2, CAR_DECK + 0.01, e * (RAMP_Z - 0.1)),
                (inner(RAMP_Z) - RAMP_FX, 0.02, 0.25), "yellow")
            # The ramp's rail along its inner edge, from the flat's end to its foot.
            path = [V(s * (ramp_edge(zz) + 0.1), ramp_y(zz), e * zz) for zz in zs_between(MEZ_Z - 0.2, RAMP_Z - 1.0, 2.0)]
            tube([p + UP * 1.0 for p in path], 0.04, 4, "yellow")
            tube([p + UP * 0.5 for p in path], 0.03, 4, "yellow")
            for p in path:
                cyl(p, p + UP * 1.0, 0.035, 0.035, 4, "yellow")
            # The rail across the flat's inner end.
            rail_loop([V(s * (CASING_X1 + 0.1), MEZ_TOP, e * (MEZ_Z - 0.1)), V(s * (RAMP_X + 0.1), MEZ_TOP, e * (MEZ_Z - 0.1))],
                      1.0, "yellow", step=1.6, closed=False)

def stair(s, e, cz):
    """The open stair in casing s's end at end e: a flight climbing inboard from the car
    deck at the casing's end to the deckhead at cz, a wall on its wing side, open with
    a handrail to the tunnel."""
    x0, x1 = CASING_X0 + 0.15, CASING_X1 - 0.2
    xc, w = s * (x0 + x1) / 2, x1 - x0
    box(V(s * (CASING_X1 - 0.1), (CAR_DECK + DECKHEAD) / 2, e * (cz + CASING_Z) / 2), (0.2, DECKHEAD - CAR_DECK, CASING_Z - cz), "white")
    n = 18
    rise, going = (DECKHEAD - CAR_DECK) / n, STAIR_RUN / n
    for i in range(n):
        z = e * (CASING_Z - (i + 0.5) * going)
        box(V(xc, CAR_DECK + (i + 1) * rise - 0.03, z), (w, 0.06, going + 0.02), "steel")
        box(V(xc, CAR_DECK + (i + 0.5) * rise, e * (CASING_Z - (i + 1) * going + 0.02)), (w, rise, 0.03), "dkwall")
    a, b = V(xc, CAR_DECK, e * CASING_Z), V(xc, DECKHEAD, e * cz)
    for x in (x0 + 0.04, x1 - 0.04):
        box_between(V(s * x, CAR_DECK - 0.1, e * CASING_Z), V(s * x, DECKHEAD - 0.1, e * cz), 0.08, "dkwall")
    hx = s * (x0 + 0.05)
    tube([V(hx, CAR_DECK + 0.95, e * (CASING_Z - 0.2)), V(hx, DECKHEAD - 0.15, e * (cz + 1.0))], 0.03, 4, "yellow")
    for t in (0.1, 0.5, 0.9):
        p = lerp(V(hx, CAR_DECK, e * CASING_Z), V(hx, DECKHEAD, e * cz), t)
        cyl(p, p + UP * 0.95, 0.025, 0.025, 4, "yellow")


def knee(s, z, r, depth):
    """A curved knee in the corner between the hull side's inside and the deckhead."""
    xi = half_beam(z) - 0.3
    arc = [V(s * (xi - r + r * math.cos(a)), DECKHEAD - r + r * math.sin(a), z)
           for a in [math.pi / 2 * k / 6 for k in range(7)]]
    poly = [V(s * xi, DECKHEAD, z)] + arc
    loft([[p + V(0, 0, -depth / 2) for p in poly], [p + V(0, 0, depth / 2) for p in poly]], "ceiling")


# --- Passenger deck and cabin ---------------------------------------------------------

def deck_outline(y, zmax, out=0.0):
    zs = sorted(set([u * HZ for u in US if abs(u * HZ) < zmax - 0.3] + [-zmax, zmax]))
    stb = [V(half_beam(z) + out, y, z) for z in zs]
    return stb + [V(-p.x, y, p.z) for p in reversed(stb)]


def slab(poly_at, side="white"):
    """A deck plate between PAX_DECK and PAX_TOP over the outline poly_at(y)."""
    lo, hi = poly_at(PAX_DECK), poly_at(PAX_TOP)
    loft([lo, hi], side, caps=False)
    hface(lo, "ceiling", up=False)
    hface(hi, "deckp")


def pax_deck():
    """The passenger deck: full width to the walkway across the cabin's ends, then the
    two forks out over the wings, nothing over the tunnel between them."""
    slab(lambda y: deck_outline(y, WALK_Z, 0.12))
    for e in (1, -1):
        for s in (1, -1):
            zs = zs_between(WALK_Z, FORK_Z, 1.5)
            slab(lambda y, e=e, s=s, zs=zs: [V(s * (half_beam(z) + 0.12), y, e * z) for z in zs] +
                 [V(s * FORK_X, y, e * FORK_Z), V(s * FORK_X, y, e * WALK_Z)])
    # A grey rubbing strip along the deck edge.
    for s in (1, -1):
        rings = []
        for z in zs_between(-FORK_Z, FORK_Z):
            p, n = side_pt(s, z, PAX_TOP, 0.12)
            rings.append([p + n * u + UP * v for u, v in ((0.0, -0.14), (0.04, -0.14), (0.04, -0.02), (0.0, -0.02))])
        loft(rings, "panel")
    # The walkway's fascia over the tunnel: the end's number and the clearance board.
    for e in (1, -1):
        zf = e * (WALK_Z + 0.02)
        box(V(0.9, PAX_DECK - 0.2, zf), (1.3, 0.38, 0.04), "yellow")
        box(V(-0.9, PAX_DECK - 0.2, zf), (1.0, 0.3, 0.04), "white")


def cabin_dims():
    hw = min(HB - 0.5, half_beam(CABIN_Z - 3.0) - 0.25)
    ch = max(1.2, hw - (half_beam(CABIN_Z) - 0.3))
    return hw, ch


# The vestibules: at each end the cabin's outer parts stand back PORCH_D from its centre
# section (over the tunnel and casings, |x| < PORCH_X); either side of the fork the
# space in front of them is closed in by a vestibule, walled on its outboard side and
# its front (VEST_Z, upright) with a big chamfer across the corner (VEST_CH) holding an
# open doorway, roofed by the sun deck and a raised, bevelled cap of skylights.
PORCH_X, PORCH_D = 7.0, 5.5
VEST_CH = 2.2


def cabin_ring(y, hw, ch, grow=0.0):
    """The cabin's plan at height y: the centre section out to the raked end, the outer
    parts stood back PORCH_D (their walls raked alike), `grow` out all round."""
    hd, cx, c = cabin_hd(y) + grow, PORCH_X - grow, 0.3
    rd, w = hd - PORCH_D - 2 * grow, hw + grow
    q = [(w, rd - c), (w - c, rd), (cx, rd), (cx, hd - ch), (cx - ch, hd)]
    q = q + [(-x, z) for x, z in reversed(q)]
    q = q + [(-x, -z) for x, z in q]
    return [V(x, y, z) for x, z in q]


def cabin():
    hw, ch = cabin_dims()
    ch = 0.6
    base, sill, head, top = (cabin_ring(y, hw, ch) for y in (PAX_TOP, SILL, HEAD, ROOF))
    loft([base, sill, head, top], lambda i, j, c: "glass" if i == 1 else "white", caps=False)
    # Piers between the windows, about 2.1 m apart (following the raked ends).
    pw = 0.5
    n_e = len(sill)
    for k in range(n_e):
        a0, a1 = sill[k], sill[(k + 1) % n_e]
        b0, b1 = head[k], head[(k + 1) % n_e]
        L = (a1 - a0).length
        if L < 0.5:
            continue
        n = max(1, round(L / 2.13))
        mid = (a0 + a1) * 0.5
        out = V(a1.z - a0.z, 0, -(a1.x - a0.x)).normalized()
        # Outward: away from the cabin's inside (a point just in from the edge).
        probe = mid + out * 0.05
        inside = abs(probe.x) < hw and abs(probe.z) < (cabin_hd(SILL) if abs(probe.x) < PORCH_X else cabin_hd(SILL) - PORCH_D)
        if inside: out = -out
        for i in range(n + 1):
            t0, t1 = max(0.0, i / n - pw / 2 / L), min(1.0, i / n + pw / 2 / L)
            q = [lerp(a0, a1, t0), lerp(a0, a1, t1), lerp(b0, b1, t1), lerp(b0, b1, t0)]
            q = [p + out * 0.02 for p in q]
            face(q if normal(q).dot(out) > 0 else q[::-1], "white")
    # Its roof: the sun deck, overhanging a little, on over the porches to the cabin's
    # full length; its underside the porches' ceiling.
    lo = rect(0, ROOF, 0, hw + 0.15, cabin_hd(ROOF) + 0.15, cabin_dims()[1])
    hi = rect(0, SUN, 0, hw + 0.15, cabin_hd(ROOF) + 0.15, cabin_dims()[1])
    loft([lo, hi], "white", caps=False)
    hface(hi, "deckp")
    hface(lo, "ceiling", up=False)
    vestibules(hw)


def vest_wall(a, b, y0, y1, t=0.16, key="white"):
    """An upright wall slab along a -> b (on deck), t thick, centred on the line."""
    d = (b - a); d.y = 0; d.normalize()
    n = V(d.z, 0, -d.x)
    ring = lambda p: [p + n * (u * t / 2) + UP * y for u, y in ((-1, y0), (1, y0), (1, y1), (-1, y1))]
    loft([ring(a), ring(b)], key)


def vest_plan(hw):
    """The vestibule's walls in plan (starboard, +Z end): front, chamfer, side, inside
    faces; and its front's z."""
    zf = cabin_hd(ROOF) - 0.05
    zb = cabin_hd(ROOF) - PORCH_D - 0.1
    xo = hw - 0.08
    return zf, zb, xo


def vestibules(hw):
    """Each vestibule: its front, chamfer (an open doorway and a window) and outboard
    side (two windows) under the sun deck; inside, the cabin's back wall with its door
    and a bench, lights in the ceiling; over it a raised cap, bevelled down to the side
    and the front, set with dark skylights."""
    zf, zb, xo = vest_plan(hw)
    c = VEST_CH
    wy = (SILL + HEAD) / 2
    for e in (1, -1):
        for s in (1, -1):
            P = lambda x, z: V(s * x, 0, e * z)
            f0, f1 = P(PORCH_X - 0.05, zf), P(xo - c, zf)       # the front
            c1 = P(xo, zf - c)                                   # the chamfer's far end
            b1 = P(xo, zb)                                       # the side's back end
            # The front: a window inboard, then the open doorway (a lintel over it) toward
            # the chamfer, which is solid with a window of its own.
            d0, d1 = P(PORCH_X + 2.15, zf), P(PORCH_X + 3.35, zf)
            vest_wall(f0, d0, PAX_TOP, ROOF)
            vest_wall(d0, d1, PAX_TOP + 2.2, ROOF)
            vest_wall(d1, f1 + (f1 - f0).normalized() * 0.08, PAX_TOP, ROOF)
            vest_wall(f1, c1, PAX_TOP, ROOF)
            vest_wall(c1, b1, PAX_TOP, ROOF)
            # Windows: on the front, the chamfer and the side (their outer faces), lit like the cabin's.
            nf, ns = V(0, 0, e), V(s, 0, 0)
            nc = V(s, 0, e).normalized()
            panel(V(s * (PORCH_X + 1.0), wy, e * (zf + 0.08)), nf, 1.0, 1.25, 0.03, "glass")
            panel(lerp(f1, c1, 0.5) + UP * wy + nc * 0.08, nc, 1.1, 1.25, 0.03, "glass")
            for z in (zb + 1.1, zb + 2.7):
                panel(V(s * (xo + 0.08), wy, e * z), ns, 1.0, 1.25, 0.03, "glass")
            # Inside: a door in the cabin's back wall, and one in the centre section's side.
            zd = cabin_hd(PAX_TOP + 1.0) - PORCH_D
            panel(V(s * (PORCH_X + 2.2), PAX_TOP + 1.05, e * zd), V(0, 0, e), 1.0, 2.1, 0.05, "steel")
            panel(V(s * PORCH_X, PAX_TOP + 1.05, e * (zd + 1.6)), V(s, 0, 0), 0.9, 2.1, 0.05, "steel")
            box(V(s * (hw - 1.6), PAX_TOP + 0.45, e * (zd + 0.35)), (2.4, 0.08, 0.5), "bronze")
            for dx in (-1.0, 1.0):
                box(V(s * (hw - 1.6 + dx), PAX_TOP + 0.22, e * (zd + 0.35)), (0.08, 0.44, 0.4), "dark")
            zc = (zb + zf) / 2
            for x in (PORCH_X + 1.6, hw - 1.6):
                box(V(s * x, ROOF - 0.03, e * zc), (0.9, 0.06, 0.6), "steel")
                box(V(s * x, ROOF - 0.065, e * zc), (0.75, 0.03, 0.45), "lamp")
            # The cap: from the sun deck's edge up to a flat, bevelled in from the side
            # and the front (the corner's chamfer carried up), upright inboard and aft.
            ins, top = 1.0, SUN + 0.75
            xi, xe, ze, zk = PORCH_X - 0.1, hw + 0.15, zf + 0.2, zb - 0.1
            lo = [(xi, zk), (xi, ze), (xe - c, ze), (xe, ze - c), (xe, zk)]
            hi = [(xi, zk), (xi, ze - ins), (xe - ins - c + 0.4, ze - ins), (xe - ins, ze - ins - c + 0.4), (xe - ins, zk)]
            rl = [V(s * x, SUN, e * z) for x, z in lo]
            rh = [V(s * x, top, e * z) for x, z in hi]
            loft([rl, rh], "white", cap_key="white")
            # Skylights: a grid on the flat, a row down each bevel.
            for i in range(3):
                for j in range(2):
                    x = lerp(xi + 0.5, xe - ins - 0.4, (i + 0.5) / 3)
                    z = lerp(zk + 0.4, ze - ins - 0.3, (j + 0.5) / 2)
                    box(V(s * x, top + 0.02, e * z), (1.3, 0.04, 1.2), "dark")
            for k in (1, 2, 3):
                a0, a1 = rl[k], rl[(k + 1) % 5] if k < 4 else rl[0]
                b0, b1 = rh[k], rh[(k + 1) % 5] if k < 4 else rh[0]
                if k == 3:
                    a1, b1 = rl[4], rh[4]
                nb = normal([a0, a1, b1, b0])
                mid = centre([a0, a1, b1, b0])
                if nb.dot(mid - V(s * (xi + xe) / 2, mid.y, e * (zk + ze) / 2)) < 0: nb = -nb
                nb.normalize()
                m = 3 if k != 2 else 2
                for i in range(m):
                    t0, t1 = (i + 0.12) / m, (i + 0.88) / m
                    q = [lerp(lerp(a0, a1, t), lerp(b0, b1, t), u) + nb * 0.02 for t, u in ((t0, 0.2), (t1, 0.2), (t1, 0.8), (t0, 0.8))]
                    face(q if normal(q).dot(nb) > 0 else q[::-1], "dark")


def sun_rail(hw, ch):
    """The sun deck's rail: round its edge, stepping in around each vestibule's cap."""
    zf, zb, xo = vest_plan(hw)
    zk, xi = zb - 0.25, PORCH_X - 0.25
    hd = cabin_hd(ROOF) + 0.05
    w = hw + 0.05
    q = [(w, 0.0), (w, zk), (xi, zk), (xi, hd), (-xi, hd), (-xi, zk), (-w, zk), (-w, 0.0)]
    q = q + [(-x, -z) for x, z in q]
    pts = []
    for x, z in q:
        if not pts or (pts[-1] - V(x, SUN, z)).length > 1e-4: pts.append(V(x, SUN, z))
    if (pts[-1] - pts[0]).length < 1e-4: pts.pop()
    rail_loop(pts, 1.05, "green")


def rail_loop(pts, h, key, step=2.4, closed=True, posts=True):
    """Guard rail on deck along `pts`: top and mid rails, stanchions about `step` apart."""
    path = []
    segs = list(zip(pts, pts[1:] + pts[:1])) if closed else list(zip(pts, pts[1:]))
    for a, b in segs:
        n = max(1, round((b - a).length / step))
        path += [lerp(a, b, i / n) for i in range(n)]
    path.append(pts[0] if closed else pts[-1])
    tube([p + UP * h for p in path], 0.035, 4, key)
    tube([p + UP * (h * 0.5) for p in path], 0.025, 4, key)
    if posts:
        for p in path[:-1] if closed else path:
            cyl(p, p + UP * h, 0.03, 0.03, 4, key)


# --- The rescue boat --------------------------------------------------------------
# The boat itself is the shared sub model art/rib_mid.py (assets/models/rib_mid.glb),
# which the game places with its origin at RIB_AT (model metres) turned RIB_YAW about
# +Y (FerryClass keeps a copy: keep them in step). Here only her cradle, and the davit
# with its fall hooked onto her sling's master link.
RIB_HOOK = (0.0, 2.65, -0.4)   # rib_mid.py HOOK, in the boat's frame
RIB_LIFT = 0.78                # her origin above the deck, sat in the cradle


def rib_cradle(at, yaw, davit):
    """Two saddles under her (a keel chock and padded posts under the V either side),
    the davit's pedestal at `davit` (x, z on deck) with its winch, the boom curving up
    and over to a sheave above the hook, the fall down to the master link."""
    c, s = math.cos(yaw), math.sin(yaw)
    def P(x, y, z): return at + V(x * c + z * s, y, -x * s + z * c)
    for z in (-1.4, 0.2):
        cyl(P(-0.75, -RIB_LIFT + 0.07, z), P(0.75, -RIB_LIFT + 0.07, z), 0.08, 0.08, 4, "dark", math.pi / 4)
        cyl(P(0, -RIB_LIFT, z), P(0, -0.36, z), 0.07, 0.07, 4, "dark", math.pi / 4)
        for x in (-0.5, 0.5):
            cyl(P(x, -RIB_LIFT, z), P(x, -0.2, z), 0.05, 0.05, 4, "dark", math.pi / 4)
            box(P(x, -0.18, z), (0.2, 0.05, 0.22), "black")
    d0 = V(davit[0], at.y - RIB_LIFT, davit[1])
    h = P(*RIB_HOOK)
    cyl(d0, d0 + UP * 0.12, 0.3, 0.3, 8, "dark")
    cyl(d0 + UP * 0.12, d0 + UP * 3.2, 0.17, 0.13, 8, "white")
    box(d0 + V(0, 1.1, 0), (0.42, 0.42, 0.42), "dark")
    cyl(d0 + V(-0.24, 1.1, 0), d0 + V(0.24, 1.1, 0), 0.16, 0.16, 8, "dark")
    tip = V(h.x, h.y + 0.85, h.z)
    def over(t, y): return V(lerp(d0.x, tip.x, t), y, lerp(d0.z, tip.z, t))
    tube([d0 + UP * 3.05, over(0.12, h.y + 0.95), over(0.45, h.y + 1.12), over(0.85, h.y + 1.02), tip],
         0.1, 6, "white")
    box(tip + V(0, -0.06, 0), (0.16, 0.24, 0.16), "dark")
    cyl(tip + V(0, -0.18, 0), h + UP * 0.08, 0.014, 0.014, 3, "black")
    box(h + UP * 0.13, (0.06, 0.1, 0.05), "orange")


RIB_AT, RIB_YAW = V(7.6, PAX_TOP + LIFT + RIB_LIFT, -37.0), 0.0   # bow toward amidships


def end_decks():
    """The forks and the walkway: railed all round in green with mesh panels; the
    rescue boat and its davit out on one fork, vents and life rings."""
    prof = [(0.0, 0.0), (0.0, 0.95), (-0.06, 0.95), (-0.06, 0.0)]
    for e in (1, -1):
        def pt(x, z): return V(x, PAX_TOP, e * z)
        outer = zs_between(cabin_hd(ROOF) - VEST_CH - 0.2, FORK_Z - 0.1, 1.0)
        path = [pt(-(half_beam(z) + 0.05), z) for z in outer]
        xt = half_beam(FORK_Z - 0.1)
        path += [pt(-x, FORK_Z - 0.1) for x in (lerp(xt, FORK_X, 0.5), FORK_X + 0.05)]
        path += [pt(-(FORK_X + 0.05), z) for z in zs_between(WALK_Z + 0.05, FORK_Z - 1.2, 1.6)[::-1]]
        path += [pt(x, WALK_Z + 0.05) for x in (-(FORK_X + 0.05), -2.4, 0.0, 2.4, FORK_X + 0.05)]
        path += [pt(FORK_X + 0.05, z) for z in zs_between(WALK_Z + 0.05, FORK_Z - 1.2, 1.6)[1:]]
        path += [pt(x, FORK_Z - 0.1) for x in (FORK_X + 0.05, lerp(xt, FORK_X, 0.5))]
        path += [pt(half_beam(z) + 0.05, z) for z in outer[::-1]]
        ns = horiz_normals(path, False)
        loft([[p + n * u + UP * v for u, v in prof] for p, n in zip(path, ns)], "mesh", cap_key="green")
        tube([p + n * -0.03 + UP * 1.0 for p, n in zip(path, ns)], 0.06, 4, "green")
        tube([p + n * -0.03 + UP * 0.08 for p, n in zip(path, ns)], 0.05, 4, "green")
        for p, n in zip(path, ns):
            cyl(p + n * -0.03, p + n * -0.03 + UP * 1.0, 0.05, 0.05, 4, "green")
        # A staff on the walkway, raked out a little, and life rings on the fork rails.
        cyl(V(0, PAX_TOP + 0.95, e * (WALK_Z - 0.1)), V(0, 12.4, e * (WALK_Z + 0.9)), 0.06, 0.035, 4, "white")
        for s in (1, -1):
            torus(V(s * (FORK_X - 0.05), PAX_TOP + 0.6, e * (WALK_Z + 1.2)), V(1, 0, 0), 0.38, 0.09, 10, 4, "orange")
            torus(V(s * (half_beam(38.5) + 0.12), PAX_TOP + 0.6, e * 38.5), V(1, 0, 0), 0.38, 0.09, 10, 4, "orange")
    # The rescue boat's cradle on the -Z end, and its davit (the boat is rib_mid.glb).
    rib_cradle(RIB_AT - V(0, LIFT, 0), RIB_YAW, (half_beam(RIB_AT.z + RIB_HOOK[2]) - 0.6, RIB_AT.z + RIB_HOOK[2]))


# --- Sun deck -----------------------------------------------------------------------

def sun_deck():
    hw, ch = cabin_dims()
    sun_rail(hw, ch)
    # The crew houses: one toward each end, enclosed, running inboard from the pilothouse
    # nearly to the funnels; small square windows and doors down their sides, a name
    # board, and on the roof vents, an air-conditioning unit and a ladder up at the
    # inboard end.
    for e in (1, -1):
        z0, z1 = 5.6, PH_Z0
        cz, hd, hw, top = e * (z0 + z1) / 2, (z1 - z0) / 2, 5.0, 12.9
        loft([rect(0, SUN, cz, hw, hd, 0.3), rect(0, top, cz, hw, hd, 0.3)], "white", cap_key="white")
        loft([rect(0, top, cz, hw + 0.12, hd + 0.12, 0.35), rect(0, top + 0.15, cz, hw + 0.12, hd + 0.12, 0.35)],
             "white", cap_key="deckp")
        for s in (1, -1):
            n = V(s, 0, 0)
            for k, z in enumerate(zs_between(z0 + 1.2, z1 - 1.0, 2.4)):
                if k == 2:
                    panel(V(s * hw, SUN + 1.0, e * z), n, 0.85, 2.0, 0.04, "steel")
                else:
                    panel(V(s * hw, 11.95, e * z), n, 0.8, 0.8, 0.03, "window")
            box(V(s * (hw + 0.02), 12.62, e * (z0 + z1) / 2), (0.04, 0.3, 1.6), "orange")
        # The inboard end: a door, and the ladder up to the roof beside it.
        panel(V(1.2, SUN + 1.0, e * z0), V(0, 0, -e), 0.85, 2.0, 0.04, "steel")
        for x in (-2.0, -1.4):
            cyl(V(x, SUN, e * (z0 - 0.25)), V(x, top + 1.0, e * (z0 - 0.25)), 0.03, 0.03, 4, "steel")
        for k in range(8):
            y = SUN + 0.3 + k * 0.3
            cyl(V(-2.0, y, e * (z0 - 0.25)), V(-1.4, y, e * (z0 - 0.25)), 0.02, 0.02, 3, "steel")
        # Roof gear.
        box(V(2.4, top + 0.55, e * (z0 + 2.2)), (1.6, 0.8, 1.2), "steel")
        for x, z in ((-2.5, z0 + 5.0), (2.0, z0 + 8.5), (-1.0, z0 + 11.5)):
            cyl(V(x, top + 0.15, e * z), V(x, top + 0.75, e * z), 0.2, 0.2, 8, "white")
            cyl(V(x, top + 0.75, e * z), V(x, top + 0.95, e * z), 0.38, 0.3, 8, "white")
        rail_loop([V(-hw + 0.3, top + 0.15, e * (z0 + 0.3)), V(-hw + 0.3, top + 0.15, e * (z0 + 4.0)),
                   V(-0.6, top + 0.15, e * (z0 + 4.0))], 1.0, "green", step=1.8, closed=False)
    # Liferaft canisters on racks outboard of each pilothouse, life rings on the rail.
    for e in (1, -1):
        for s in (1, -1):
            for zr in (19.6, 21.7):
                box(V(s * 7.6, SUN + 0.2, e * zr), (3.2, 0.4, 1.6), "steel")
                for dz in (-0.42, 0.42):
                    a = V(s * 6.2, SUN + 0.75, e * (zr + dz))
                    cyl(a, a + V(s * 2.8, 0, 0), 0.36, 0.36, 8, "white")
            torus(V(s * (PORCH_X - 1.6), SUN + 0.75, e * (cabin_hd(ROOF) + 0.12)), V(0, 0, 1), 0.38, 0.09, 10, 4, "orange")


FUNNEL_X = 5.0      # the two funnels, side by side either side of the centreline


def funnel():
    """Two funnels side by side amidships, white with a gold band under the black top,
    the WSF disc on their outboard faces; the fan room between them."""
    for s in (1, -1):
        x = s * FUNNEL_X
        rings = [rect(x, SUN, 0, 1.3, 3.0, 1.0), rect(x, 13.62, 0, 1.24, 2.05, 0.95), rect(x, 13.84, 0, 1.235, 2.0, 0.95),
                 rect(x, FUNNEL_TOP, 0, 1.2, 1.75, 0.9)]
        loft(rings, lambda i, j, c: ("white", "gold", "black")[i], cap_key="black")
        cyl(V(x, FUNNEL_TOP - 0.1, 0.3), V(x, FUNNEL_TOP + 0.9, 0.3), 0.32, 0.32, 8, "black")
        cyl(V(x, FUNNEL_TOP - 0.1, -0.7), V(x, FUNNEL_TOP + 0.5, -0.7), 0.2, 0.2, 6, "black")
        xo = x + s * 1.27
        cyl(V(xo, 12.4, 0), V(xo + s * 0.06, 12.4, 0), 0.6, 0.6, 12, "green")
        box(V(xo + s * 0.07, 12.45, 0), (0.02, 0.12, 0.78), "white")
        box(V(xo + s * 0.07, 12.25, 0.15), (0.02, 0.12, 0.52), "white")
        panel(V(x, SUN + 1.0, 2.6), V(0, 0, 1), 0.8, 2.0, 0.04, "steel")
    # The fan room: louvred sides, doors at both ends.
    hw = FUNNEL_X - 1.3
    loft([rect(0, SUN, 0, hw, 3.4, 0.2), rect(0, 12.7, 0, hw, 3.4, 0.2)], "white", cap_key="white")
    box(V(0, 12.78, 0), (2 * hw + 0.2, 0.16, 7.0), "white")
    for e in (1, -1):
        panel(V(0, SUN + 1.0, e * 3.4), V(0, 0, e), 0.9, 2.0, 0.04, "steel")
        for x in (-1.6, 1.6):
            panel(V(x, SUN + 1.25, e * 3.4), V(0, 0, e), 0.8, 1.0, 0.04, "dkwall")
            for k in range(5):
                panel(V(x, SUN + 0.85 + k * 0.2, e * 3.4), V(0, 0, e), 0.8, 0.04, 0.07, "white")
    for x in (-0.8, 0.8):
        cyl(V(x, 12.86, 1.8), V(x, 13.3, 1.8), 0.3, 0.3, 8, "steel")
        cyl(V(x, 13.3, 1.8), V(x, 13.45, 1.8), 0.45, 0.45, 8, "steel")


def pilothouses():
    for e in (1, -1):
        cz, hd = e * (PH_Z0 + PH_Z1) / 2, (PH_Z1 - PH_Z0) / 2
        cho, chi = 1.3, 0.3          # outboard (end) corners raked, inboard nearly square
        ch, chb = (cho, chi) if e > 0 else (chi, cho)
        base = rect(0, SUN, cz, PH_HW, hd, ch, chb)
        sill = rect(0, PH_SILL, cz, PH_HW, hd, ch, chb)
        head = rect(0, PH_HEAD, cz + e * 0.12, PH_HW + 0.12, hd + 0.12, ch + 0.05, chb)
        top = rect(0, PH_TOP, cz + e * 0.12, PH_HW + 0.12, hd + 0.12, ch + 0.05, chb)
        loft([base, sill, head, top], lambda i, j, c: "glass" if i == 1 else "white", cap_key="white")
        for k in range(8):
            a0, a1, b0, b1 = sill[k], sill[(k + 1) % 8], head[k], head[(k + 1) % 8]
            n = max(1, round((a1 - a0).length / 1.25))
            for i in range(n):
                t = i / n
                cyl(lerp(a0, a1, t), lerp(b0, b1, t), 0.05, 0.05, 4, "white")
        # The green roof, overhanging most at the end; a door aft on each side.
        loft([rect(0, PH_TOP, cz + e * 0.45, PH_HW + 0.45, hd + 0.75, ch + 0.2, chb),
              rect(0, PH_TOP + 0.3, cz + e * 0.45, PH_HW + 0.45, hd + 0.75, ch + 0.2, chb)], "green")
        for s in (1, -1):
            panel(V(s * PH_HW, SUN + 1.0, e * (PH_Z0 + 0.8)), V(s, 0, 0), 0.8, 2.0, 0.04, "steel")


def masts():
    """A mast on each pilothouse roof: yards for the lights, the radar on a railed
    platform facing the end, the gaff raked toward amidships."""
    for e in (1, -1):
        z = e * MAST_Z
        base = PH_TOP + 0.3
        cyl(V(0, base, z), V(0, MAST_TOP, z), 0.18, 0.1, 8, "white")
        for a in (-1, 1):
            cyl(V(a * 1.2, base, z), V(0, 16.6, z), 0.06, 0.05, 4, "white")
        for y, w in ((18.5, 3.2), (17.4, 2.4)):
            box(V(0, y, z), (w, 0.12, 0.12), "white")
        box(V(0, 16.6, z + e * 0.9), (1.2, 0.1, 1.8), "white")
        rail_loop([V(0.6, 16.65, z + e * 0.15), V(0.6, 16.65, z + e * 1.8), V(-0.6, 16.65, z + e * 1.8),
                   V(-0.6, 16.65, z + e * 0.15)], 0.6, "white", step=1.0, closed=False)
        cyl(V(0, 16.7, z + e * 1.2), V(0, 16.9, z + e * 1.2), 0.12, 0.12, 6, "dark")
        box(V(0, 16.98, z + e * 1.2), (2.6, 0.12, 0.22), "dark")
        cyl(V(0, 19.6, z), V(0, 21.5, z - e * 3.2), 0.07, 0.05, 4, "white")
        cyl(V(0, MAST_TOP, z), V(0, MAST_TOP + 0.35, z), 0.06, 0.06, 4, "dark")
        # Whip aerials at the roof's corners.
        for a in (-1, 1):
            cyl(V(a * 3.8, base, e * (PH_Z0 + 0.4)), V(a * 3.9, base + 3.2, e * (PH_Z0 + 0.3)), 0.03, 0.015, 3, "dark")


def build():
    for bm in BMS.values(): bm.free()
    BMS.clear()
    hull(); bulwarks()
    car_deck(); tween_decks()
    LIFTED[0] = LIFT
    pax_deck(); cabin(); end_decks()
    sun_deck(); funnel(); pilothouses(); masts()
    LIFTED[0] = 0.0
    obs = []
    for role, bm in BMS.items():
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        old = bpy.data.meshes.get("issaquah_" + role)
        if old: bpy.data.meshes.remove(old)
        me = bpy.data.meshes.new("issaquah_" + role); bm.to_mesh(me); bm.free()
        me.materials.append(mat)
        me.color_attributes.active_color_name = "Col"; me.color_attributes.render_color_index = 0
        ob = bpy.data.objects.new(role, me); coll.objects.link(ob); obs.append(ob)
    BMS.clear()
    return obs


built = build()
_here = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.dirname(os.path.abspath(__file__)) \
    if "__file__" in globals() else "/Users/jon/Documents/GitHub/tideways/art"
_glb = os.path.normpath(os.path.join(_here, "..", "assets", "models", "issaquah_mid.glb"))
for o in bpy.data.objects: o.select_set(o in built)
bpy.ops.export_scene.gltf(filepath=_glb, export_format="GLB", use_selection=True,
                          export_normals=True, export_vertex_color="ACTIVE", export_materials="NONE", export_yup=True)
result = {o.name: len(o.data.polygons) for o in built}
print("ISSAQUAH", _glb, result)
