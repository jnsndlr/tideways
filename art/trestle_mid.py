# Builds the mid-poly terminal trestle in Blender (run inside Blender, or headless:
# Blender -b --factory-startup --python art/trestle_mid.py) and exports its parts to
# assets/models/trestle_mid.glb (glTF, +Y up, vertex colours, flat shaded).
# A WSF-style trestle: the road out from a terminal lot that stands on higher ground,
# down over the water to the transfer span's shore hinge. Precast concrete deck bays on
# concrete pile bents; a raised walkway with a pipe railing on one side, a concrete
# barrier on the other. The slope lives in the trestle (up to about 8%), so the lot can
# sit on natural ground and the span only has to make up the tide.
# Game frame (Layout): +Z ("u") out to sea, +X across, +Y up, water at y = 0
# (Blender: +Z up, seaward to -Y). Parts, each about its own origin, for the game to tile:
#   bay        one BAY_L deck section, origin on the centre line at its shore end, deck
#              top at y 0, out +Z, cut every SEG along u. Not pitched: the game lifts each
#              vertex to profile(u) where it stands, so neighbouring bays, the lot and
#              the span all meet at exactly the same height and slope.
#   landing    the last bay, onto the span's hinge: the walkway stops short and a barrier
#              lines up with the span's girders; the hinge bent at its end seats the span.
#   bent       pile cap on four piles, origin at the cap's top centre (under the deck's
#              slab), piles down to PILE_DEPTH (the terrain and water hide the rest).
#   abutment   at the lot's seaward edge, origin at the deck top on the centre line: the
#              seat and wing walls below; on the lot, the curb, barrier and walkway ends.
#   lamp       a davit light pole, origin at its foot (stands on the barrier).
# profile() is the road's height from the lot's edge to the hinge: level at both ends,
# with vertical curves into and out of a steady grade.
# Below the parts, a PREVIEW collection lays a whole terminal approach out for a look:
# bank, lot, water, the trestle and (if assets/models/slip_mid.glb is there) the slip.
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

PAL = {
    "concrete": (0.62, 0.62, 0.6), "concrete_dark": (0.48, 0.48, 0.47), "concrete_wet": (0.3, 0.31, 0.3),
    "asphalt": (0.26, 0.27, 0.29), "yellow": (0.92, 0.78, 0.3), "white": (0.86, 0.86, 0.84),
    "galv": (0.68, 0.69, 0.68), "green": (0.07, 0.36, 0.25), "steel_dark": (0.3, 0.31, 0.32),
    "lamp": (1.0, 0.8, 0.45), "black": (0.08, 0.08, 0.09), "weed": (0.2, 0.26, 0.15),
    # Preview only.
    "grass": (0.32, 0.5, 0.2), "sand": (0.72, 0.65, 0.5), "rock": (0.42, 0.4, 0.38),
    "water": (0.1, 0.3, 0.42), "seabed": (0.35, 0.33, 0.28),
}
PARTS = ("bay", "landing", "bent", "abutment", "lamp")

# --- Dimensions (metres) -----------------------------------------------------------------
LOT_Y = 3.15             # the span's hinge, the car deck at mean tide
HINGE_U = 2.0            # the span's shore hinge (SlipRamp)
BAY_L = 12.0             # bent to bent; two 6 m centre-line dash periods
DECK_HW = 6.6            # half width between the curbs, as the transfer span
CURB_W = 0.4
CURB_H = 0.3             # as the span's curbs
WALK_W = 2.2             # walkway (on -X), its top just under the curb's
SLAB_T = 0.7
X_WALK = -(DECK_HW + CURB_W + WALK_W)   # outer edge of the walkway
X_BAR = DECK_HW + CURB_W                # inner foot of the barrier
BAR_W = 0.55
X_OUT = X_BAR + BAR_W                   # outer face of the barrier
X_MID = (X_WALK + X_OUT) / 2            # middle of the slab (bents centre on it)
CAP_H = 1.2
CAP_W = 1.4
PILE_R = 0.42
PILE_DEPTH = -18.0
PILES = (X_MID - 7.4, X_MID - 2.5, X_MID + 2.5, X_MID + 7.4)
LAMP_H = 9.0
WALK_END = BAY_L - 3.0   # the landing: where the walkway stops short of the span
SEG = 3.0                # deck parts are cut every SEG along u, so they bend to the profile
VC = 18.0                # vertical curve at each end of the profile (m along u)
MAX_GRADE = 0.075        # preview: the steepest the trestle gets
BAYS = 6                 # preview: bays from the lot to the hinge, the last one the landing
# Barrier cross-section (x, y), +X side; the landing mirrors it onto -X.
BARRIER = [(X_BAR, -0.02), (X_BAR, 0.25), (X_BAR + 0.15, 0.5), (X_BAR + 0.3, 0.85),
           (X_OUT, 0.85), (X_OUT, -0.02)]


def profile(u, u0, h0, u1, h1, vc=VC):
    """The road's height along the approach: level at the lot (u0, h0), a vertical curve
    into a steady grade, and another out of it, level again at the span's hinge (u1, h1).
    Level at both ends, so the lot, the trestle and the span meet without a kink.
    (scripts/sim/layout.gd keeps the same curve for the game.)"""
    L = u1 - u0
    if L <= 0.0:
        return h1
    t = min(max((u - u0) / L, 0.0), 1.0)
    a = min(vc / L, 0.5)
    m = 1.0 / (1.0 - a)
    if t < a:
        f = m * t * t / (2.0 * a)
    elif t < 1.0 - a:
        f = m * (t - a / 2.0)
    else:
        f = 1.0 - m * (1.0 - t) ** 2 / (2.0 * a)
    return h0 + (h1 - h0) * f


def peak_grade(L, vc=VC):
    """The steepest grade per metre of rise over an approach `L` long."""
    return 1.0 / (L * (1.0 - min(vc / L, 0.5)))


def G(p): return Vector((p.x, -p.z, p.y))
def V(x, y, z): return Vector((x, y, z))


coll = bpy.data.collections.get("TRESTLE") or bpy.data.collections.new("TRESTLE")
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
PART = ["bay"]
BEND = [False]   # cut long runs every SEG along u (the deck parts)


def bm_for():
    role = PART[0]
    if role not in BMS:
        bm = bmesh.new(); bm.loops.layers.color.new("Col"); BMS[role] = bm
    return BMS[role]


def face(pts, key):
    q = [pts[0]]
    for p in pts[1:]:
        if (p - q[-1]).length > 1e-5: q.append(p)
    if len(q) > 2 and (q[0] - q[-1]).length < 1e-5: q.pop()
    if len(q) < 3: return
    bm = bm_for(); cl = bm.loops.layers.color["Col"]
    try:
        f = bm.faces.new([bm.verts.new(G(p)) for p in q])
    except ValueError:
        return
    f.smooth = False
    for l in f.loops: l[cl] = (*PAL[key], 1.0)


def normal(pts):
    n = Vector()
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += a.cross(b)
    return n


def centre(pts): return sum(pts, Vector()) / len(pts)


def oface(pts, key, out):
    face(pts if normal(pts).dot(out) > 0 else pts[::-1], key)


def loft(rings, key, caps=True):
    n = len(rings[0])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        ax = (centre(a) + centre(b)) * 0.5
        for j in range(n):
            k = (j + 1) % n
            q = [a[j], a[k], b[k], b[j]]
            oface(q, key, centre(q) - ax)
    if caps:
        for r, o in ((rings[0], rings[1]), (rings[-1], rings[-2])):
            oface(r, key, centre(r) - centre(o))


def zs(z0, z1):
    """Cuts along z: every SEG on the deck parts, so they bend smoothly."""
    n = max(1, math.ceil((z1 - z0) / SEG - 1e-6)) if BEND[0] else 1
    return [z0 + (z1 - z0) * i / n for i in range(n + 1)]


def span_box(x0, x1, y0, y1, z0, z1, key):
    loft([[V(x1, y0, z), V(x1, y1, z), V(x0, y1, z), V(x0, y0, z)] for z in zs(z0, z1)], key)


def frame(ax):
    e1 = ax.cross(V(0.3, 0, 1) if abs(ax.z) < 0.9 else V(1, 0, 0)).normalized()
    return e1, ax.cross(e1).normalized()


def circle(c, ax, r, n, a0=0.0):
    e1, e2 = frame(ax)
    return [c + (e1 * math.cos(a0 + math.tau * i / n) + e2 * math.sin(a0 + math.tau * i / n)) * r for i in range(n)]


def cyl(a, b, r0, r1, n, key, a0=None):
    ax = (b - a).normalized()
    a0 = math.pi / n if a0 is None else a0
    loft([circle(a, ax, r0, n, a0), circle(b, ax, r1, n, a0)], key)


def rail(x, y, z0, z1, r, key):
    """A rail along z, cut like the deck so it bends with it."""
    ax = V(0, 0, 1)
    loft([circle(V(x, y, z), ax, r, 6, math.pi / 6) for z in zs(z0, z1)], key)


def prism_z(profile_xy, z0, z1, key):
    """A convex cross-section (x, y) outline run along z0..z1."""
    loft([[V(x, y, z) for x, y in profile_xy] for z in zs(z0, z1)], key)


# --- Parts ---------------------------------------------------------------------------------
def walkway(z1):
    """The raised walkway on -X and its pipe railing, from the bay's start to z1."""
    inner = -(DECK_HW + CURB_W)
    span_box(X_WALK, inner, -0.02, CURB_H - 0.03, 0.0, z1, "concrete_dark")
    rx = X_WALK + 0.15
    z = 0.9
    while z < z1:
        cyl(V(rx, CURB_H, z), V(rx, CURB_H + 1.1, z), 0.04, 0.04, 6, "galv")
        z += 2.0
    for y in (CURB_H + 1.1, CURB_H + 0.6, CURB_H + 0.15):
        rail(rx, y, 0.0, z1, 0.035, "galv")


def barrier(z0, z1, side=1):
    """The concrete parapet with its steel top rail on posts, on +X (side 1) or -X."""
    prism_z([(side * x, y) for x, y in BARRIER], z0, z1, "concrete")
    xi, xo = sorted((side * (X_BAR + 0.28), side * X_OUT))
    span_box(xi, xo, 0.85, 0.87, z0, z1, "concrete_dark")
    px = side * (X_BAR + 0.41)
    z = z0 + 1.5
    while z < z1:
        span_box(px - 0.05, px + 0.05, 0.85, 1.25, z - 0.06, z + 0.06, "galv")
        z += 3.0
    rail(px, 1.28, z0, z1, 0.06, "galv")


def bay(landing=False):
    """One deck bay. The landing is the last, onto the span's hinge: its walkway stops
    short with a railing return, a barrier takes over on -X so both sides line up with
    the span's girders, and the hinge bent at its end carries the deck and the span."""
    L = BAY_L
    walk_to = WALK_END if landing else L
    # Precast slab with a darker fascia band along each edge; narrower past the walkway.
    span_box(X_WALK, X_OUT, -SLAB_T, -0.02, 0.0, walk_to, "concrete")
    span_box(X_WALK - 0.08, X_WALK, -SLAB_T, -0.25, 0.0, walk_to, "concrete_dark")
    span_box(X_OUT, X_OUT + 0.08, -SLAB_T, -0.25, 0.0, L, "concrete_dark")
    if landing:
        span_box(-X_OUT, X_OUT, -SLAB_T, -0.02, walk_to, L, "concrete")
        span_box(-X_OUT - 0.08, -X_OUT, -SLAB_T, -0.25, walk_to, L, "concrete_dark")
        span_box(X_WALK, -X_OUT, -SLAB_T, -0.02, walk_to - 0.01, walk_to, "concrete")
    # Roadway: asphalt, white edge lines, the yellow dashed centre line (in step with the span's).
    span_box(-DECK_HW, DECK_HW, -0.02, 0.0, 0.0, L, "asphalt")
    for s in (-1, 1):
        span_box(s * (DECK_HW - 0.45), s * (DECK_HW - 0.3), 0.0, 0.02, 0.0, L, "white")
    for z in (1.5, 7.5):
        span_box(-0.12, 0.12, 0.0, 0.02, z, z + 3.0, "yellow")
    # Deck joint at the shore end: a steel plate across the road.
    span_box(-DECK_HW, DECK_HW, 0.0, 0.015, 0.0, 0.25, "steel_dark")
    # Curbs, as the span's.
    for s in (-1, 1):
        x0, x1 = sorted((s * DECK_HW, s * (DECK_HW + CURB_W)))
        span_box(x0, x1, -0.02, CURB_H, 0.0, L, "concrete")
    walkway(walk_to)
    barrier(0.0, L, 1)
    for z in (3.0, 9.0):
        span_box(X_BAR - 0.01, X_BAR + 0.02, -0.02, 0.12, z - 0.3, z + 0.3, "black")
    if not landing:
        return
    # The walkway's end: a railing return to the curb, and the barrier on -X from there.
    rx = X_WALK + 0.15
    inner = -(DECK_HW + CURB_W)
    cyl(V(inner, CURB_H, walk_to), V(inner, CURB_H + 1.1, walk_to), 0.04, 0.04, 6, "galv")
    for y in (CURB_H + 1.1, CURB_H + 0.6, CURB_H + 0.15):
        cyl(V(rx, y, walk_to), V(inner, y, walk_to), 0.035, 0.035, 6, "galv")
    barrier(walk_to, L, -1)
    # Hinge bent: the trestle's slab bears on its shore half, the span's girders on a
    # lower seat on its sea half (they hang 0.9 under the span's deck).
    BEND[0] = False
    x0, x1 = X_WALK - 0.3, X_OUT + 0.3
    span_box(x0, x1, -SLAB_T - 1.4, -SLAB_T, L - 0.8, L, "concrete")
    span_box(x0, x1, -SLAB_T - 1.4, -0.95, L, L + 0.9, "concrete")
    span_box(-7.7, -6.7, -0.95, -0.9, L + 0.1, L + 0.8, "black")
    span_box(6.7, 7.7, -0.95, -0.9, L + 0.1, L + 0.8, "black")
    for x in PILES:
        cyl(V(x, -SLAB_T - 1.4, L), V(x, -3.2, L), PILE_R, PILE_R, 8, "concrete")
        cyl(V(x, -3.2, L), V(x, -5.4, L), PILE_R + 0.02, PILE_R + 0.02, 8, "weed")
        cyl(V(x, -5.4, L), V(x, PILE_DEPTH, L), PILE_R + 0.01, PILE_R + 0.01, 8, "concrete_wet")
    BEND[0] = True


def landing():
    bay(True)


def bent():
    # Cap beam, chamfered underneath, bearing pads on top; four round piles with a
    # weed line and wet staining near the water.
    cw = CAP_W / 2
    x0, x1 = X_WALK - 0.3, X_OUT + 0.3
    prism = [(-cw, 0.0), (cw, 0.0), (cw, -CAP_H + 0.25), (cw - 0.25, -CAP_H),
             (-cw + 0.25, -CAP_H), (-cw, -CAP_H + 0.25)]
    a = [V(x0, y, z) for z, y in prism]; b = [V(x1, y, z) for z, y in prism]
    c = centre(a + b)
    for j in range(len(prism)):
        k = (j + 1) % len(prism)
        q = [a[j], a[k], b[k], b[j]]
        oface(q, "concrete", centre(q) - c)
    oface(a, "concrete", V(-1, 0, 0)); oface(b, "concrete", V(1, 0, 0))
    for x in PILES:
        span_box(x - 0.5, x + 0.5, 0.0, 0.06, -0.4, 0.4, "black")
        cyl(V(x, -CAP_H, 0.0), V(x, -3.2, 0.0), PILE_R, PILE_R, 8, "concrete")
        cyl(V(x, -3.2, 0.0), V(x, -4.4, 0.0), PILE_R + 0.01, PILE_R + 0.01, 8, "concrete_wet")
        cyl(V(x, -4.4, 0.0), V(x, -5.4, 0.0), PILE_R + 0.03, PILE_R + 0.03, 8, "weed")
        cyl(V(x, -5.4, 0.0), V(x, PILE_DEPTH, 0.0), PILE_R + 0.01, PILE_R + 0.01, 8, "concrete_wet")


def abutment():
    """Where the trestle leaves the lot. Below: the seat wall under the deck's first
    bay, a backwall up to the lot's paving, and wing walls into the bank. Above, on the
    lot (z < 0, which is level with the deck): the curbs and the barrier start with
    sloped noses, and the walkway runs back onto the lot and ramps down to it, so the
    lot's paving runs straight onto the trestle's."""
    bot = -SLAB_T - 4.5
    span_box(X_WALK - 0.5, X_OUT + 0.5, bot, -SLAB_T, -0.2, 1.2, "concrete")
    span_box(X_WALK - 0.5, X_OUT + 0.5, bot, -0.3, -1.4, -0.2, "concrete")
    span_box(X_WALK - 0.7, X_OUT + 0.7, bot - 0.2, bot + 0.1, -1.6, 1.4, "concrete_dark")
    for s, xe in ((-1, X_WALK - 0.5), (1, X_OUT + 0.5)):
        for z0, z1, xb, top1 in ((-1.4, -7.0, xe, -0.3), (-7.0, -12.0, xe + s * 3.0, -3.0)):
            xa = xe if z0 == -1.4 else xe
            pa = [V(xa, bot, z0), V(xa + s * 0.5, bot, z0), V(xa + s * 0.5, -0.3, z0), V(xa, -0.3, z0)]
            pb = [V(xb, bot, z1), V(xb + s * 0.5, bot, z1), V(xb + s * 0.5, top1, z1), V(xb, top1, z1)]
            loft([pa, pb], "concrete")
    # Curb noses ramping up from the lot to full height at the deck's start.
    for s in (-1, 1):
        x0, x1 = sorted((s * DECK_HW, s * (DECK_HW + CURB_W)))
        loft([[V(x1, -0.02, -1.5), V(x1, 0.02, -1.5), V(x0, 0.02, -1.5), V(x0, -0.02, -1.5)],
              [V(x1, -0.02, 0.0), V(x1, CURB_H, 0.0), V(x0, CURB_H, 0.0), V(x0, -0.02, 0.0)]], "concrete")
    # The barrier's nose, sloping down to the lot.
    flat = [(x, -0.02 + (y + 0.02) * 0.08) for x, y in BARRIER]
    loft([[V(x, y, -3.0) for x, y in flat], [V(x, y, 0.0) for x, y in BARRIER]], "concrete")
    # The walkway back onto the lot, ramping down to it, its railing ending at the edge.
    inner = -(DECK_HW + CURB_W) - 0.0
    span_box(X_WALK, -DECK_HW, -0.02, CURB_H - 0.03, -4.0, 0.0, "concrete_dark")
    loft([[V(-DECK_HW, -0.02, -7.0), V(-DECK_HW, 0.01, -7.0), V(X_WALK, 0.01, -7.0), V(X_WALK, -0.02, -7.0)],
          [V(-DECK_HW, -0.02, -4.0), V(-DECK_HW, CURB_H - 0.03, -4.0), V(X_WALK, CURB_H - 0.03, -4.0),
           V(X_WALK, -0.02, -4.0)]], "concrete_dark")
    rx = X_WALK + 0.15
    cyl(V(rx, CURB_H - 0.03, 0.0), V(rx, CURB_H + 1.1, 0.0), 0.05, 0.05, 6, "galv")


def lamp():
    # Galvanised pole with a davit arm out over the road and a cobra head.
    cyl(V(0, 0, 0), V(0, 0.3, 0), 0.22, 0.2, 8, "galv")
    cyl(V(0, 0.3, 0), V(0, LAMP_H, 0), 0.13, 0.08, 8, "galv")
    pts = [V(0, LAMP_H, 0)]
    for i in range(1, 7):
        a = i / 6 * math.pi / 2
        pts.append(V(-1.6 * (1 - math.cos(a)), LAMP_H + 1.0 * math.sin(a), 0))
    pts.append(V(-3.4, LAMP_H + 1.0, 0))
    for a, b in zip(pts, pts[1:]):
        cyl(a, b, 0.07, 0.07, 6, "galv")
    span_box(-4.3, -3.2, LAMP_H + 0.82, LAMP_H + 1.1, -0.28, 0.28, "steel_dark")
    span_box(-4.2, -3.3, LAMP_H + 0.78, LAMP_H + 0.82, -0.22, 0.22, "lamp")


def build():
    for bm in BMS.values(): bm.free()
    BMS.clear()
    for role, fn, bend in (("bay", bay, True), ("landing", landing, True), ("bent", bent, False),
                           ("abutment", abutment, False), ("lamp", lamp, False)):
        PART[0] = role; BEND[0] = bend; fn()
    BEND[0] = False
    obs = {}
    for role in PARTS:
        bm = BMS[role]
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        old = bpy.data.meshes.get("trestle_" + role)
        if old: bpy.data.meshes.remove(old)
        me = bpy.data.meshes.new("trestle_" + role); bm.to_mesh(me); bm.free()
        me.materials.append(mat)
        me.color_attributes.active_color_name = "Col"; me.color_attributes.render_color_index = 0
        ob = bpy.data.objects.new(role, me); coll.objects.link(ob); obs[role] = ob
    BMS.clear()
    return obs


# --- Preview -----------------------------------------------------------------------------
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # game -> Blender


def place(me, name, pos, pcoll):
    """A linked copy of a part at a game-frame position."""
    ob = bpy.data.objects.new(name, me)
    ob.matrix_world = C @ Matrix.Translation(pos) @ C.inverted()
    pcoll.objects.link(ob)
    return ob


def place_bent_to(me, name, u_at, prof, pcoll):
    """A copy of a deck part at u_at, each vertex lifted to the profile where it stands
    (verticals stay vertical), as the game does: so neighbours share their joints exactly."""
    m = me.copy(); m.name = name
    for v in m.vertices:
        u = u_at - v.co.y          # Blender -Y is the game's +u
        v.co.z += prof(u)
    ob = bpy.data.objects.new(name, m)
    ob.matrix_world = C @ Matrix.Translation(V(0, 0, u_at)) @ C.inverted()
    pcoll.objects.link(ob)
    return ob


def ground_mesh(pcoll, u_bank, h_top):
    """Bank, lot shelf and seabed as one strip across the approach; a water sheet over it."""
    PART[0] = "ground"
    xs = [-70.0 + 7.0 * i for i in range(21)]
    us = [-150.0 + 4.0 * i for i in range(46)]

    def h(x, u):
        wob = 0.6 * math.sin(x * 0.21 + u * 0.13) + 0.4 * math.sin(x * 0.07 - u * 0.31)
        if u < u_bank + 2.0:
            return h_top - 0.3 + (wob * 0.5 if abs(x) > 26 or u < -128 else 0.0)
        if u < u_bank + 40.0:
            t = (u - (u_bank + 2.0)) / 38.0
            s = t * t * (3 - 2 * t)
            return h_top - 0.3 + (-4.0 - h_top) * s + wob
        return -4.0 - (u - u_bank - 40.0) * 0.18 + wob

    def col(y, u):
        if y < -0.6: return "seabed"
        if y < 1.6: return "sand"
        if y < h_top - 0.9 and u > u_bank - 2: return "rock" if (int(u) + int(y * 3)) % 3 else "grass"
        return "grass"

    for j in range(len(us) - 1):
        for i in range(len(xs) - 1):
            q = [V(xs[i], h(xs[i], us[j]), us[j]), V(xs[i + 1], h(xs[i + 1], us[j]), us[j]),
                 V(xs[i + 1], h(xs[i + 1], us[j + 1]), us[j + 1]), V(xs[i], h(xs[i], us[j + 1]), us[j + 1])]
            ym = sum(p.y for p in q) / 4
            oface(q, col(ym, us[j]), V(0, 1, 0))
    # The lot: its paving's top exactly at the deck's, out to the abutment's face.
    span_box(-26.0, 26.0, h_top - 0.3, h_top, -128.0, u_bank, "asphalt")
    for k in range(-5, 6):
        if k == 0: continue
        x = k * 4.4
        span_box(x - 0.08, x + 0.08, h_top, h_top + 0.02, -120.0, -95.0, "white")
    span_box(-0.12, 0.12, h_top, h_top + 0.02, -128.0, u_bank - 8.0, "yellow")
    # The lot's seaward edge either side of the trestle: a kerb wall with a pipe rail.
    for x0, x1 in ((-26.0, X_WALK), (X_OUT, 26.0)):
        span_box(x0, x1, h_top - 1.2, h_top + 0.45, u_bank - 0.5, u_bank, "concrete")
        cyl(V(x0, h_top + 1.1, u_bank - 0.25), V(x1, h_top + 1.1, u_bank - 0.25), 0.04, 0.04, 6, "galv")
        x = x0 + 0.5
        while x < x1:
            cyl(V(x, h_top + 0.45, u_bank - 0.25), V(x, h_top + 1.1, u_bank - 0.25), 0.04, 0.04, 6, "galv")
            x += 2.0
    PART[0] = "water"
    span_box(-70.0, 70.0, -0.05, 0.0, u_bank + 10.0, 40.0, "water")
    for role in ("ground", "water"):
        bm = BMS.pop(role)
        me = bpy.data.meshes.new("preview_" + role); bm.to_mesh(me); bm.free()
        me.materials.append(mat)
        me.color_attributes.active_color_name = "Col"; me.color_attributes.render_color_index = 0
        ob = bpy.data.objects.new("preview_" + role, me); pcoll.objects.link(ob)


def preview(parts):
    pcoll = bpy.data.collections.get("PREVIEW") or bpy.data.collections.new("PREVIEW")
    if pcoll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(pcoll)
    for o in list(pcoll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(m)
    length = BAYS * BAY_L
    u0 = HINGE_U - length                 # the lot's edge, top of the approach
    h0 = LOT_Y + MAX_GRADE / peak_grade(length)
    prof = lambda u: profile(u, u0, h0, HINGE_U, LOT_Y)
    ground_mesh(pcoll, u0, h0)
    place(parts["abutment"].data, "pv_abutment", V(0, h0, u0), pcoll)
    for i in range(BAYS):
        u = u0 + i * BAY_L
        part = parts["landing" if i == BAYS - 1 else "bay"].data
        place_bent_to(part, "pv_bay%d" % i, u, prof, pcoll)
        if i > 0:
            place(parts["bent"].data, "pv_bent%d" % i, V(0, prof(u) - SLAB_T, u), pcoll)
        if i % 2 == 1:
            place(parts["lamp"].data, "pv_lamp%d" % i, V(X_BAR + 0.41, prof(u + 6.0) + 0.85, u + 6.0), pcoll)
    # The slip, if its model has been exported: the trestle's foot lands on its hinge.
    glb = os.path.normpath(os.path.join(_here, "..", "assets", "models", "slip_mid.glb"))
    if os.path.exists(glb):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=glb)
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            for c in list(o.users_collection): c.objects.unlink(o)
            pcoll.objects.link(o)
            o.name = "pv_slip_" + o.name
        # Drop the span's tip a little, as at a low tide: it pivots on its shore hinge.
        tilt = math.radians(-TILT_DEG)
        hinge = C @ V(0, LOT_Y, HINGE_U)
        for o in new:
            base = o.name.replace("pv_slip_", "").split(".")[0]
            if base in ("span", "apron"):
                o.matrix_world = Matrix.Translation(hinge) @ Matrix.Rotation(tilt, 4, "X") \
                    @ Matrix.Translation(-hinge) @ o.matrix_world
            elif base in ("cable", "counterweight", "rambody", "ramrod"):
                o.hide_set(True); o.hide_render = True
    return pcoll, u0, h0


TILT_DEG = 3.0
_here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    (os.path.dirname(bpy.data.filepath) or "/Users/jon/Documents/GitHub/tideways/art")
built = build()
_glb = os.path.normpath(os.path.join(_here, "..", "assets", "models", "trestle_mid.glb"))
for o in bpy.data.objects: o.select_set(o in built.values())
bpy.ops.export_scene.gltf(filepath=_glb, export_format="GLB", use_selection=True,
                          export_normals=True, export_vertex_color="ACTIVE", export_materials="NONE", export_yup=True)
for o in built.values(): o.hide_set(True)
_pv = preview(built)
result = {k: len(o.data.polygons) for k, o in built.items()}
result["lot_u"] = _pv[1]; result["lot_h"] = round(_pv[2], 2)
print("trestle_mid:", result, "total", sum(result.values()))
if bpy.app.background and not bpy.data.filepath:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(_here, "trestle_mid.blend"))
