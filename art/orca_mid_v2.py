# Builds an improved mid-poly orca in Blender within the original ~1.1k tri budget
# (run inside Blender: exec(open(path).read())).
# Preserves the exact cetacean.gdshader contract:
#   - Game frame: 1 unit long, +Z forward, nose at z = 0.5, flukes back to z ~ -0.51, +Y up
#     (Blender frame: bow to -Y, Z up).
#   - Body vertex colour is plain black; per-animal markings are drawn by cetacean.gdshader
#     from UV = (s, theta / pi) in Blender (glTF flips V -> 1 - theta / pi in Godot),
#     where s is distance back from the nose and theta is angle round from the back (0) to belly (pi).
#   - Dorsal fin, pectoral flippers, and tail flukes carry UV = (-1.0, 0.0) so the shader keeps
#     their vertex colours.
#   - Dorsal fin vertices carry alpha = 1 - t/2 (t = 0 at base with alpha = 1.0; lifted stations
#     start at t >= 0.14 so alpha < 0.95) for cetacean.gdshader's dynamic height & sweep.
import bpy
import bmesh
import math
from mathutils import Vector


def G(x, y, z):
    """Convert game-space (X right, Y up, Z forward) to Blender-space (X right, -Z forward, Y up)."""
    return Vector((x, -z, y))


BLACK = (0.045, 0.05, 0.06, 1.0)
UNDER = (0.88, 0.89, 0.88, 1.0)
FIN_BASE = 0.085
FIN_H = 0.18
P = math.pi

# Resolution (~1,082 tris total — matches original 1,096-tri budget).
NS, NR = 22, 16

# Setup collection & material
coll = bpy.data.collections.get("Orca") or bpy.data.collections.new("Orca")
if coll.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(coll)

mat = bpy.data.materials.get("VertexColour") or bpy.data.materials.new("VertexColour")
mat.use_nodes = True
_nt = mat.node_tree
_bsdf = next(n for n in _nt.nodes if n.type == "BSDF_PRINCIPLED")
_attr = next((n for n in _nt.nodes if n.type == "VERTEX_COLOR"), None)
if _attr is None:
    _attr = _nt.nodes.new("ShaderNodeVertexColor")
_attr.name = "Attr"
_attr.layer_name = "Col"
_nt.links.new(_attr.outputs["Color"], _bsdf.inputs["Base Color"])
# Link Alpha so glTF export writes RGBA vertex colours (required for dorsal fin height/sweep).
_nt.links.new(_attr.outputs["Alpha"], _bsdf.inputs["Alpha"])
_bsdf.inputs["Roughness"].default_value = 0.35

for _old_name in ("Orca",):
    _o = bpy.data.objects.get(_old_name)
    if _o:
        bpy.data.objects.remove(_o, do_unlink=True)
    _m = bpy.data.meshes.get(_old_name)
    if _m:
        bpy.data.meshes.remove(_m)


# ---------------------------------------------------------------------------
# Body profile keyed on s = distance back from the nose (0.0 .. 0.935).
# Smoothly rounded melon/rostrum nose, subtle jawline tuck, muscular thorax,
# and laterally compressed caudal peduncle with dorsal & ventral keels.
# ---------------------------------------------------------------------------
S   = [0.0,    0.015,  0.04,   0.08,   0.14,   0.22,   0.32,   0.42,   0.52,   0.62,   0.72,   0.81,   0.88,   0.935]
TOP = [-0.020, 0.008,  0.036,  0.062,  0.080,  0.091,  0.095,  0.092,  0.082,  0.065,  0.048,  0.035,  0.026,  0.019]
BOT = [-0.020, -0.036, -0.050, -0.068, -0.085, -0.096, -0.098, -0.092, -0.077, -0.057, -0.038, -0.025, -0.015, -0.007]
HW  = [0.0,    0.024,  0.045,  0.066,  0.084,  0.098,  0.101,  0.095,  0.079,  0.056,  0.034,  0.019,  0.011,  0.006]


def interp(tab, s):
    s = min(max(s, S[0]), S[-1])
    for i in range(len(S) - 1):
        if S[i] <= s <= S[i + 1]:
            t = (s - S[i]) / (S[i + 1] - S[i])
            p0 = tab[max(i - 1, 0)]
            p1 = tab[i]
            p2 = tab[i + 1]
            p3 = tab[min(i + 2, len(S) - 1)]
            return 0.5 * (
                (2 * p1)
                + (-p0 + p2) * t
                + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3
            )
    return tab[-1]


def smoothstep(edge0, edge1, x):
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def body_point(s, a):
    """Evaluate body surface point at longitudinal station s and angle a (0=back, pi=belly)."""
    if s < 0.022:
        u = s / 0.022
        ell = math.sqrt(max(2.0 * u - u * u, 0.0))
        t_ref = interp(TOP, 0.022)
        b_ref = interp(BOT, 0.022)
        w_ref = interp(HW, 0.022)
        c_nose = -0.020
        c_ref = 0.5 * (t_ref + b_ref)
        h_ref = 0.5 * (t_ref - b_ref)
        c = c_nose + (c_ref - c_nose) * (u ** 0.85)
        h = h_ref * ell
        w_ = w_ref * ell
        bl = smoothstep(0.55, 1.0, u)
        t_sp, b_sp, w_sp = interp(TOP, s), interp(BOT, s), max(interp(HW, s), 0.0)
        c = c * (1.0 - bl) + 0.5 * (t_sp + b_sp) * bl
        h = h * (1.0 - bl) + 0.5 * (t_sp - b_sp) * bl
        w_ = w_ * (1.0 - bl) + w_sp * bl
    else:
        t_, b_, w_ = interp(TOP, s), interp(BOT, s), max(interp(HW, s), 0.0)
        c = (t_ + b_) * 0.5
        h = (t_ - b_) * 0.5

    sa = math.sin(a)
    ca = math.cos(a)

    keel = smoothstep(0.58, 0.88, s)
    ex = 2.0 + 0.14 * smoothstep(0.02, 0.18, s) - 0.78 * keel

    x = w_ * math.copysign(abs(sa) ** (2.0 / ex), sa)
    y = c + h * math.copysign(abs(ca) ** (2.0 / ex), ca)

    # Subtle head sculpting: narrower chin/lower jaw + gentle mouthline contour
    if s < 0.24:
        head_w = math.sin(P * smoothstep(0.02, 0.24, s))
        if ca < 0.0:
            x *= 1.0 - 0.13 * head_w * ((-ca) ** 1.4)
        mouth_s = smoothstep(0.02, 0.06, s) * (1.0 - smoothstep(0.11, 0.20, s))
        th = a if a <= P else 2.0 * P - a
        mouth_a = math.exp(-((th - 0.62 * P) / (0.09 * P)) ** 2)
        x *= 1.0 - 0.05 * mouth_s * mouth_a

    # Peduncle keel pinch on sides near dorsal/ventral midline
    if keel > 0.0:
        x *= 1.0 - 0.18 * keel * (ca * ca)

    return G(x, y, 0.5 - s)


bm = bmesh.new()
cl = bm.loops.layers.color.new("Col")
uvl = bm.loops.layers.uv.new("UVMap")


def paint(f, col):
    for l in f.loops:
        l[cl] = col


# Non-uniform longitudinal ring placement: denser at the rostrum/melon curve
# so 22 rings keep the same smooth profile as 42.
sl = [0.004, 0.014, 0.032, 0.060]
n_rest = NS - len(sl)
for i in range(n_rest):
    u = i / (n_rest - 1)
    sl.append(0.095 + (0.935 - 0.095) * (0.12 * u * u + 0.88 * u))

body_uv = {}

nose_v = bm.verts.new(body_point(0.0, P * 0.5))
body_uv[nose_v] = (0.0, 0.5)

rings = []
for s_ in sl:
    ring = []
    for k in range(NR):
        a = 2.0 * P * k / NR
        v = bm.verts.new(body_point(s_, a))
        body_uv[v] = (s_, min(a, 2.0 * P - a) / P)
        ring.append(v)
    rings.append(ring)

for k in range(NR):
    f = bm.faces.new([nose_v, rings[0][(k + 1) % NR], rings[0][k]])
    paint(f, BLACK)

for i in range(len(rings) - 1):
    for k in range(NR):
        f = bm.faces.new([
            rings[i][k],
            rings[i][(k + 1) % NR],
            rings[i + 1][(k + 1) % NR],
            rings[i + 1][k],
        ])
        paint(f, BLACK)

tail_end_v = bm.verts.new(body_point(0.935, P * 0.5))
body_uv[tail_end_v] = (0.935, 0.5)
for k in range(NR):
    f = bm.faces.new([rings[-1][k], rings[-1][(k + 1) % NR], tail_end_v])
    paint(f, BLACK)


def airfoil_section(n_side, ch, thk, le_z):
    """Symmetric NACA-00xx airfoil perimeter (2 * n_side points), LE at le_z, TE at le_z - ch."""
    pts_pos = []
    pts_neg = []
    for i in range(n_side + 1):
        u = 0.5 * (1.0 - math.cos(P * i / n_side))
        z = le_z - u * ch
        yt = 5.0 * (
            0.2969 * math.sqrt(max(u, 0.0))
            - 0.1260 * u
            - 0.3516 * u * u
            + 0.2843 * u ** 3
            - 0.1015 * u ** 4
        )
        x = thk * (yt / 0.5)
        if i == 0 or i == n_side:
            pts_pos.append((0.0, z))
        else:
            pts_pos.append((x, z))
            pts_neg.append((-x, z))
    return pts_pos + list(reversed(pts_neg))


def loft_closed(sections, col, cap_start=False, tip_point=None):
    """Loft a list of closed 3D point loops into quad strips, with smooth tip cap."""
    vr = [[bm.verts.new(p) for p in sec] for sec in sections]
    n = len(sections[0])
    faces = []
    for i in range(len(vr) - 1):
        for j in range(n):
            faces.append(bm.faces.new([
                vr[i][j],
                vr[i][(j + 1) % n],
                vr[i + 1][(j + 1) % n],
                vr[i + 1][j],
            ]))
    if cap_start:
        c0 = sum((v.co for v in vr[0]), Vector()) / n
        vc0 = bm.verts.new(c0)
        for j in range(n):
            faces.append(bm.faces.new([vc0, vr[0][(j + 1) % n], vr[0][j]]))
    if tip_point is not None:
        vt = bm.verts.new(tip_point)
        for j in range(n):
            faces.append(bm.faces.new([vr[-1][j], vr[-1][(j + 1) % n], vt]))
    for f in faces:
        paint(f, col)
    return vr, faces


# ---------------------------------------------------------------------------
# 1. DORSAL FIN (6 stations x 6 airfoil pts -> 66 tris)
# t=0 at base (alpha=1.0), lifted stations start at t=0.16 (alpha=0.92 < 0.95).
# ---------------------------------------------------------------------------
FIN_T = (0.0, 0.16, 0.40, 0.66, 0.86, 0.97)
fin_sections = []
fin_ts = []

for t in FIN_T:
    le = 0.088 + (-0.032 - 0.088) * (t ** 0.82)
    te = -0.112 + (-0.056 + 0.112) * t + 0.016 * math.sin(P * t)
    if t > 0.82:
        u_tip = (t - 0.82) / (1.0 - 0.82)
        mid = 0.5 * (le + te)
        half_c = 0.5 * (le - te) * math.sqrt(max(1.0 - u_tip * u_tip, 0.02))
        le = mid + half_c
        te = mid - half_c
    ch = max(le - te, 0.004)
    base_flare = 1.0 + 0.18 * math.exp(-t * 5.5)
    thk = (0.0165 * (1.0 - 0.80 * t) + 0.0018) * base_flare
    if t > 0.82:
        u_tip = (t - 0.82) / (1.0 - 0.82)
        thk *= math.sqrt(max(1.0 - 0.85 * u_tip * u_tip, 0.08))

    sec_2d = airfoil_section(3, ch, thk, le)
    pts_3d = []
    for x, z in sec_2d:
        y = (interp(TOP, 0.5 - z) - 0.008) if t == 0.0 else (FIN_BASE + t * FIN_H)
        pts_3d.append(G(x, y, z))
    fin_sections.append(pts_3d)
    fin_ts.append(t)

fin_tip_pt = G(0.0, FIN_BASE + 1.0 * FIN_H, -0.044)
fin_vr, fin_faces = loft_closed(fin_sections, BLACK, cap_start=False, tip_point=fin_tip_pt)

for row, t in zip(fin_vr, fin_ts):
    alpha = 1.0 - t * 0.5
    for v in row:
        for l in v.link_loops:
            l[cl] = (BLACK[0], BLACK[1], BLACK[2], alpha)

for f in fin_faces:
    for l in f.loops:
        if (l.vert.co - fin_tip_pt).length < 1e-5:
            l[cl] = (BLACK[0], BLACK[1], BLACK[2], 0.5)


# ---------------------------------------------------------------------------
# 2. PECTORAL FLIPPERS (7 stations x 6 airfoil pts x 2 -> 156 tris)
# Broad rounded oval paddles with stations concentrated around the rounded tip.
# ---------------------------------------------------------------------------
FLIP_U = (0.0, 0.22, 0.48, 0.70, 0.85, 0.945, 0.99)
for side in (1.0, -1.0):
    flip_sections = []
    root = Vector((0.052 * side, -0.056, 0.255))
    tip  = Vector((0.205 * side, -0.126, 0.145))

    for u in FLIP_U:
        p = root.lerp(tip, u)
        p.z += 0.018 * math.sin(P * (u ** 0.85))
        p.y -= 0.007 * math.sin(P * u) - 0.004 * (u ** 3)

        if u < 0.52:
            s_in = u / 0.52
            chord_scale = 0.56 + 0.44 * math.sin(s_in * P * 0.5)
        else:
            s_out = (u - 0.52) / (1.0 - 0.52)
            chord_scale = math.sqrt(max(1.0 - s_out * s_out, 0.002))

        ch = 0.132 * chord_scale
        le_offset = 0.47 * ch
        thk = (0.014 * (1.0 - 0.42 * u) + 0.002) * math.sqrt(max(1.0 - (max(u - 0.5, 0.0) / 0.5) ** 2 * 0.88, 0.08))

        pitch = math.radians(-8.0 + 5.0 * u)
        cp, sp = math.cos(pitch), math.sin(pitch)
        bank = math.radians(-22.0 * side)
        cb, sb = math.cos(bank), math.sin(bank)

        sec_2d = airfoil_section(3, ch, thk, le_offset)
        pts_3d = []
        for dy_local, dz_local in sec_2d:
            dy1 = dy_local * cp - dz_local * sp
            dz1 = dy_local * sp + dz_local * cp
            dx2 = -dy1 * sb
            dy2 = dy1 * cb
            pts_3d.append(G(p.x + dx2, p.y + dy2, p.z + dz1))
        flip_sections.append(pts_3d)

    tip_pt = G(tip.x, tip.y + 0.004, tip.z)
    loft_closed(flip_sections, BLACK, cap_start=False, tip_point=tip_pt)


# ---------------------------------------------------------------------------
# 3. TAIL FLUKES (7 stations x 6 airfoil pts x 2 -> 156 tris)
# Sweeping S-curved flukes with median notch and crisp black-bordered white underside.
# ---------------------------------------------------------------------------
FLUKE_U = (0.0, 0.16, 0.36, 0.56, 0.74, 0.88, 0.975)
fluke_under_faces = []
for side in (1.0, -1.0):
    fluke_sections = []
    span = 0.168
    for u in FLUKE_U:
        x = (span * u) * side
        le = -0.392 - 0.026 * u - 0.090 * (u ** 1.55)
        te = -0.452 - 0.036 * math.sin(P * (u ** 0.72)) - 0.060 * (u ** 1.25)

        if u > 0.82:
            ut = (u - 0.82) / (1.0 - 0.82)
            mid = 0.5 * (le + te)
            hc = 0.5 * (le - te) * math.sqrt(max(1.0 - ut * ut, 0.015))
            le = mid + hc
            te = mid - hc

        ch = max(le - te, 0.003)
        thk = (0.014 * ((1.0 - u) ** 1.05) + 0.0014) * math.sqrt(max(1.0 - 0.85 * u * u, 0.06))
        y0 = 0.011 + 0.004 * math.sin(P * u) - 0.009 * (u ** 1.4)

        sec_2d = airfoil_section(3, ch, thk, le)
        pts_3d = [G(x, y0 + dy, z) for dy, z in sec_2d]
        fluke_sections.append(pts_3d)

    fluke_tip = G(span * side, 0.011 - 0.009, -0.514)
    _, f_faces = loft_closed(fluke_sections, BLACK, cap_start=False, tip_point=fluke_tip)
    fluke_under_faces.extend(f_faces)


# Clean up & recalculate normals
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# Paint white underside of flukes with a crisp black trailing-edge & tip margin
for f in fluke_under_faces:
    if not f.is_valid:
        continue
    c = f.calc_center_median()
    if abs(c.x) > 0.012 and f.normal.z < -0.25:
        u_est = min(max(abs(c.x) / 0.168, 0.0), 1.0)
        te_bl = 0.452 + 0.036 * math.sin(P * (u_est ** 0.72)) + 0.060 * (u_est ** 1.25)
        if u_est < 0.85 and c.y < te_bl - 0.014:
            paint(f, UNDER)

# Assign UVs: body gets (s, theta/pi); dorsal fin, flippers, flukes get (-1, 0)
for f in bm.faces:
    for l in f.loops:
        l[uvl].uv = body_uv.get(l.vert, (-1.0, 0.0))

me = bpy.data.meshes.new("Orca")
bm.to_mesh(me)
bm.free()
me.materials.append(mat)
for p in me.polygons:
    p.use_smooth = True

obj = bpy.data.objects.new("Orca", me)
coll.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

print(
    f"Built improved Orca: verts={len(me.vertices)}, faces={len(me.polygons)}, "
    f"tris={sum(max(0, len(p.vertices) - 2) for p in me.polygons)}"
)
