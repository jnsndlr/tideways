"""Build a coastal/aviation segmented windsock for Tideways.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender -b -noaudio --factory-startup -P art/windsock.py

Exports:
    assets/models/windsock.glb     (glTF 2.0, +Y up, +Z downwind, Skeleton3D + 4 wind animations)
    art/windsock.blend             (editable Blender source + preview studio)
    art/windsock_preview.png       (studio hero preview)

Real-world dimensions (metres):
    Total height: 5.84 m (pedestal base at z = 0.0, swivel pivot at z = 5.18 m,
    summit red obstruction beacon at z = 5.84 m).
    Throat hoop: diameter 0.60 m (radius 0.30 m), offset 0.38 m downwind from mast.
    Sock cone: 2.75 m long, 5 alternating FAA orange/white segments (0.55 m each),
    tapering from R = 0.300 m at the throat to R = 0.125 m at the open tail.

Rigging & Animation (Blender Armature -> Godot Skeleton3D):
    - Root       : base of mast at (0, 0, 0)
    - Swivel     : rotates 360 deg around vertical axis (local +Y) to point downwind
    - Sock_Seg0  : orange throat band (rot local -X = droop down, local Z = sway)
    - Sock_Seg1  : white band 1
    - Sock_Seg2  : orange middle band
    - Sock_Seg3  : white band 2
    - Sock_Seg4  : orange tail band

Exported looping AnimationPlayer clips:
    - Wind_Calm      (0-3 kt:  limp downward drape with slow lazy sway)
    - Wind_Light     (6-8 kt:  partial fill, outer segments drooping & rippling)
    - Wind_Moderate  (10-12 kt: mostly horizontal with lively travelling wave)
    - Wind_Strong    (15+ kt:  fully inflated horizontal with brisk tail snap)
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
TAU = math.tau

# Geometry constants (metres, Blender Z-up, -Y downwind -> Godot Y-up, +Z downwind)
FOOTING_H = 0.24
FLANGE_Z = FOOTING_H
HINGE_Z = 1.18
SWIVEL_Z = 5.18
MAST_TOP_Z = 5.62
BEACON_TOP_Z = 5.84

HOOP_OFFSET_Y = -0.38  # downwind offset from mast centerline
HOOP_RADIUS = 0.300
HOOP_TUBE_R = 0.013

NUM_SEGMENTS = 5
SEG_LEN = 0.55
SOCK_LEN = NUM_SEGMENTS * SEG_LEN  # 2.75 m
TAIL_RADIUS = 0.125
RADIAL_STEPS = 12
SUBSTEPS_PER_SEG = 3  # 15 spans (16 rings), single-sided doubleSided cloth (~360 tris)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def make_pbr_material(
    name,
    color,
    roughness=0.45,
    metallic=0.0,
    specular=0.5,
    coat=0.0,
    emission=None,
    emission_strength=0.0,
    sheen=0.0,
    double_sided=False,
):
    mat = bpy.data.materials.new(name)
    if not mat.node_tree:
        mat.use_nodes = True
    mat.use_backface_culling = not double_sided
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = specular
    if "Coat Weight" in bsdf.inputs and coat > 0.0:
        bsdf.inputs["Coat Weight"].default_value = coat
    if "Sheen Weight" in bsdf.inputs and sheen > 0.0:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if emission is not None and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = (*color, 1.0)
    return mat


def create_materials():
    """Tideways coastal aviation palette (harmonized with radio_tower & cessna_172)."""
    return {
        "concrete": make_pbr_material(
            "Cast concrete",
            (0.32, 0.34, 0.33),
            roughness=0.88,
            metallic=0.0,
            specular=0.25,
        ),
        "galvanized": make_pbr_material(
            "Galvanized steel",
            (0.42, 0.47, 0.50),
            roughness=0.36,
            metallic=0.84,
            specular=0.55,
        ),
        "aluminium": make_pbr_material(
            "Brushed aluminium",
            (0.58, 0.63, 0.67),
            roughness=0.28,
            metallic=0.90,
            specular=0.60,
        ),
        "graphite": make_pbr_material(
            "Graphite hardware",
            (0.055, 0.068, 0.080),
            roughness=0.44,
            metallic=0.65,
            specular=0.45,
        ),
        "brass": make_pbr_material(
            "Brass grommet",
            (0.76, 0.54, 0.16),
            roughness=0.30,
            metallic=0.88,
            specular=0.65,
        ),
        "white_enamel": make_pbr_material(
            "Warm white enamel",
            (0.86, 0.85, 0.80),
            roughness=0.30,
            metallic=0.05,
            specular=0.55,
            coat=0.25,
        ),
        "orange_enamel": make_pbr_material(
            "Signal vermilion",
            (0.76, 0.09, 0.02),
            roughness=0.28,
            metallic=0.04,
            specular=0.55,
            coat=0.25,
        ),
        "beacon_glass": make_pbr_material(
            "Ruby aviation glass",
            (0.95, 0.04, 0.015),
            roughness=0.12,
            metallic=0.0,
            specular=0.85,
            coat=0.6,
            emission=(1.0, 0.10, 0.02),
            emission_strength=3.2,
        ),
        "lamp_lens": make_pbr_material(
            "Floodlight lens",
            (0.96, 0.94, 0.86),
            roughness=0.14,
            metallic=0.0,
            specular=0.75,
            emission=(1.0, 0.95, 0.84),
            emission_strength=1.4,
        ),
        "nylon_orange": make_pbr_material(
            "Windsock nylon orange",
            (0.90, 0.145, 0.018),
            roughness=0.62,
            metallic=0.0,
            specular=0.35,
            sheen=0.25,
            double_sided=True,
        ),
        "nylon_white": make_pbr_material(
            "Windsock nylon white",
            (0.86, 0.86, 0.83),
            roughness=0.64,
            metallic=0.0,
            specular=0.32,
            sheen=0.22,
            double_sided=True,
        ),
    }


def add_cylinder_bm(bm, p0, p1, r0, r1, segs, mat_idx, cap0=True, cap1=True, smooth=True):
    """Add a tapered cylinder/tube between p0 and p1 in bmesh."""
    v0 = Vector(p0)
    v1 = Vector(p1)
    axis = v1 - v0
    length = axis.length
    if length < 1e-6:
        return
    z_dir = axis / length
    ref = Vector((1.0, 0.0, 0.0)) if abs(z_dir.z) > 0.92 else Vector((0.0, 0.0, 1.0))
    x_dir = ref.cross(z_dir).normalized()
    y_dir = z_dir.cross(x_dir).normalized()

    ring0 = []
    ring1 = []
    for i in range(segs):
        a = TAU * i / segs
        ca, sa = math.cos(a), math.sin(a)
        radial = x_dir * ca + y_dir * sa
        ring0.append(bm.verts.new(v0 + radial * r0))
        ring1.append(bm.verts.new(v1 + radial * r1))

    side_edges_0 = []
    side_edges_1 = []
    for i in range(segs):
        j = (i + 1) % segs
        f = bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        f.material_index = mat_idx
        f.smooth = smooth
        for e in f.edges:
            if (e.verts[0] in (ring0[i], ring0[j]) and e.verts[1] in (ring0[i], ring0[j])):
                side_edges_0.append(e)
            if (e.verts[0] in (ring1[i], ring1[j]) and e.verts[1] in (ring1[i], ring1[j])):
                side_edges_1.append(e)

    if cap0 and r0 > 1e-5:
        f0 = bm.faces.new(list(reversed(ring0)))
        f0.material_index = mat_idx
        f0.smooth = False
        for e in side_edges_0:
            e.smooth = False
    if cap1 and r1 > 1e-5:
        f1 = bm.faces.new(ring1)
        f1.material_index = mat_idx
        f1.smooth = False
        for e in side_edges_1:
            e.smooth = False


def add_box_bm(bm, center, size, mat_idx, rot_euler=(0.0, 0.0, 0.0), bevel=0.0):
    """Add an oriented box (optionally beveled) to bmesh."""
    sx, sy, sz = size
    mat = Matrix.Translation(Vector(center)) @ Euler(rot_euler, "XYZ").to_matrix().to_4x4()
    res = bmesh.ops.create_cube(bm, size=1.0)
    verts = res["verts"]
    for v in verts:
        v.co = mat @ Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    faces = list({f for v in verts for f in v.link_faces})
    edges = list({e for v in verts for e in v.link_edges})
    if bevel > 0.0:
        bev = bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=bevel,
            offset_type="OFFSET",
            segments=2,
            profile=0.5,
            affect="EDGES",
            clamp_overlap=True,
        )
        faces = list(set(faces) | set(bev.get("faces", [])))
    for f in faces:
        if f.is_valid:
            f.material_index = mat_idx
            f.smooth = False


def add_torus_bm(bm, center, normal, major_r, minor_r, major_segs, minor_segs, mat_idx):
    """Add a smooth torus ring centered at `center` with ring axis along `normal`."""
    c = Vector(center)
    n = Vector(normal).normalized()
    ref = Vector((1.0, 0.0, 0.0)) if abs(n.z) > 0.9 else Vector((0.0, 0.0, 1.0))
    u_dir = ref.cross(n).normalized()
    v_dir = n.cross(u_dir).normalized()

    rings = []
    for i in range(major_segs):
        a = TAU * i / major_segs
        rad_dir = u_dir * math.cos(a) + v_dir * math.sin(a)
        ring_center = c + rad_dir * major_r
        ring = []
        for j in range(minor_segs):
            b = TAU * j / minor_segs
            pt = ring_center + rad_dir * (minor_r * math.cos(b)) + n * (minor_r * math.sin(b))
            ring.append(bm.verts.new(pt))
        rings.append(ring)

    for i in range(major_segs):
        ni = (i + 1) % major_segs
        for j in range(minor_segs):
            nj = (j + 1) % minor_segs
            f = bm.faces.new((rings[i][j], rings[ni][j], rings[ni][nj], rings[i][nj]))
            f.material_index = mat_idx
            f.smooth = True


def add_uv_sphere_bm(bm, center, rx, ry, rz, u_segs, v_segs, mat_idx, z_clip_min=-1.0):
    """Add an ellipsoid / dome (clipped below z_clip_min in normalized sphere z)."""
    c = Vector(center)
    rings = []
    v_angles = []
    for iv in range(1, v_segs):
        phi = -math.pi * 0.5 + math.pi * iv / v_segs
        if math.sin(phi) >= z_clip_min - 1e-4:
            v_angles.append(phi)

    for phi in v_angles:
        cp, sp = math.cos(phi), math.sin(phi)
        ring = []
        for iu in range(u_segs):
            th = TAU * iu / u_segs
            p = Vector((rx * cp * math.cos(th), ry * cp * math.sin(th), rz * sp)) + c
            ring.append(bm.verts.new(p))
        rings.append(ring)

    top_v = bm.verts.new(c + Vector((0.0, 0.0, rz)))
    for r_idx in range(len(rings) - 1):
        r0 = rings[r_idx]
        r1 = rings[r_idx + 1]
        for iu in range(u_segs):
            ju = (iu + 1) % u_segs
            f = bm.faces.new((r0[iu], r0[ju], r1[ju], r1[iu]))
            f.material_index = mat_idx
            f.smooth = True
    # Top cap triangles
    top_ring = rings[-1]
    for iu in range(u_segs):
        ju = (iu + 1) % u_segs
        f = bm.faces.new((top_ring[iu], top_ring[ju], top_v))
        f.material_index = mat_idx
        f.smooth = True
    # Bottom flat cap if clipped
    if z_clip_min > -0.99:
        fb = bm.faces.new(list(reversed(rings[0])))
        fb.material_index = mat_idx
        fb.smooth = False
        for e in fb.edges:
            e.smooth = False
    else:
        bot_v = bm.verts.new(c + Vector((0.0, 0.0, -rz)))
        bot_ring = rings[0]
        for iu in range(u_segs):
            ju = (iu + 1) % u_segs
            f = bm.faces.new((bot_ring[ju], bot_ring[iu], bot_v))
            f.material_index = mat_idx
            f.smooth = True


def finalize_mesh(name, bm, mat_list, coll):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for m in mat_list:
        mesh.materials.append(m)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def build_mast_and_pedestal(mats, coll):
    """Build low-poly (~235 tris) concrete footing, flanged base, banded mast, lamps & summit beacon."""
    mat_list = [
        mats["concrete"],       # 0
        mats["galvanized"],     # 1
        mats["graphite"],       # 2
        mats["white_enamel"],   # 3
        mats["orange_enamel"],  # 4
        mats["beacon_glass"],   # 5
        mats["lamp_lens"],      # 6
        mats["aluminium"],      # 7
    ]
    bm = bmesh.new()

    # 1. Tapered octagonal concrete footing resting cleanly at z = 0.0 (no hidden bottom cap)
    add_cylinder_bm(bm, (0, 0, 0.0), (0, 0, FOOTING_H), 0.30, 0.24, 8, 0, cap0=False, cap1=True, smooth=False)

    # 2. Steel anchor baseplate & crossed gusset fins
    add_box_bm(bm, (0, 0, FLANGE_Z + 0.014), (0.34, 0.34, 0.028), 1)
    add_box_bm(bm, (0, 0, FLANGE_Z + 0.105), (0.26, 0.018, 0.16), 1)
    add_box_bm(bm, (0, 0, FLANGE_Z + 0.105), (0.018, 0.26, 0.16), 1)

    # 3. Lower mast & maintenance hinge collar
    add_cylinder_bm(bm, (0, 0, FLANGE_Z + 0.02), (0, 0, HINGE_Z - 0.04), 0.068, 0.060, 6, 3, cap0=False, cap1=False)
    add_cylinder_bm(bm, (0, 0, HINGE_Z - 0.04), (0, 0, HINGE_Z + 0.04), 0.086, 0.086, 6, 1)

    # 4. Upper tapered mast with crisp aviation visibility bands (6-sided smooth-shaded)
    mast_bands = [
        (HINGE_Z + 0.04, 2.25, 0.058, 0.052, 4),  # vermilion lower band
        (2.25, 3.35, 0.052, 0.046, 3),            # warm white band
        (3.35, 4.30, 0.046, 0.040, 4),            # vermilion upper band
        (4.30, SWIVEL_Z - 0.18, 0.040, 0.036, 3), # warm white top
    ]
    for z0, z1, r0, r1, mi in mast_bands:
        add_cylinder_bm(bm, (0, 0, z0), (0, 0, z1), r0, r1, 6, mi, cap0=False, cap1=False)

    # 5. Swivel spindle shaft
    add_cylinder_bm(bm, (0, 0, SWIVEL_Z - 0.18), (0, 0, MAST_TOP_Z), 0.032, 0.032, 6, 7, cap0=False, cap1=False)

    # 6. Overhead compact cross-arm with 2 angled downward floodlights
    arm_z = MAST_TOP_Z - 0.04
    add_cylinder_bm(bm, (-0.21, 0, arm_z + 0.03), (0.21, 0, arm_z + 0.03), 0.011, 0.011, 4, 1, cap0=False, cap1=False)
    for side in (-1, 1):
        ax = side * 0.21
        lamp_top = (ax, 0.0, arm_z + 0.045)
        lamp_bot = (ax * 1.15, 0.0, arm_z - 0.025)
        add_cylinder_bm(bm, lamp_top, lamp_bot, 0.020, 0.045, 6, 2, cap0=True, cap1=False)
        add_cylinder_bm(bm, (ax * 1.12, 0.0, arm_z - 0.018), lamp_bot, 0.040, 0.040, 6, 6, cap0=False, cap1=True)

    # 7. Summit Red Aviation Obstruction Beacon
    add_cylinder_bm(bm, (0, 0, MAST_TOP_Z), (0, 0, MAST_TOP_Z + 0.070), 0.046, 0.056, 6, 2, cap0=True, cap1=False)
    add_uv_sphere_bm(bm, (0, 0, MAST_TOP_Z + 0.066), 0.052, 0.052, 0.125, 6, 4, 5, z_clip_min=-0.02)

    return finalize_mesh("WindsockPole", bm, mat_list, coll)


def build_swivel_frame(mats, coll):
    """Build low-poly (~172 tris) rotating bearing collar, 4-strut FAA spider yoke & throat hoop."""
    mat_list = [
        mats["galvanized"],  # 0
        mats["graphite"],    # 1
        mats["aluminium"],   # 2
    ]
    bm = bmesh.new()

    # 1. Rotating bearing hub sleeve + top/bottom dark bearing seal rings
    add_cylinder_bm(bm, (0, 0, SWIVEL_Z - 0.16), (0, 0, SWIVEL_Z + 0.16), 0.054, 0.054, 6, 0)
    add_cylinder_bm(bm, (0, 0, SWIVEL_Z - 0.165), (0, 0, SWIVEL_Z - 0.130), 0.062, 0.062, 6, 1, cap0=False, cap1=False)
    add_cylinder_bm(bm, (0, 0, SWIVEL_Z + 0.130), (0, 0, SWIVEL_Z + 0.165), 0.062, 0.062, 6, 1, cap0=False, cap1=False)

    # 2. Throat Hoop (12-segment smooth torus ring)
    hoop_c = Vector((0.0, HOOP_OFFSET_Y, SWIVEL_Z))
    add_torus_bm(bm, hoop_c, (0.0, -1.0, 0.0), HOOP_RADIUS, HOOP_TUBE_R, 12, 4, 2)

    # 3. Four-strut FAA spider yoke connecting hub cleanly to top, bottom, left, right of hoop
    strut_specs = [
        ((0.0, -0.045, SWIVEL_Z + 0.12), (0.0, HOOP_OFFSET_Y, SWIVEL_Z + HOOP_RADIUS), 0.011),
        ((0.0, -0.045, SWIVEL_Z - 0.12), (0.0, HOOP_OFFSET_Y, SWIVEL_Z - HOOP_RADIUS), 0.011),
        ((0.042, -0.022, SWIVEL_Z), (HOOP_RADIUS, HOOP_OFFSET_Y, SWIVEL_Z), 0.010),
        ((-0.042, -0.022, SWIVEL_Z), (-HOOP_RADIUS, HOOP_OFFSET_Y, SWIVEL_Z), 0.010),
    ]
    for p_hub, p_hoop, r in strut_specs:
        add_cylinder_bm(bm, p_hub, p_hoop, r * 1.15, r, 4, 0, cap0=False, cap1=False)

    return finalize_mesh("WindsockSwivelFrame", bm, mat_list, coll)


def sock_radius_profile(u):
    """Radius of the windsock along normalized length u in [0, 1].

    Includes linear taper, subtle per-segment nylon billow, raised sewn seam lips,
    and reinforced throat/tail hems so the 5 segments look authentically stitched.
    """
    base_r = lerp(HOOP_RADIUS, TAIL_RADIUS, u)

    # Position inside current segment [0, 1]
    seg_pos = u * NUM_SEGMENTS
    seg_idx = min(NUM_SEGMENTS - 1, int(seg_pos))
    local_t = seg_pos - seg_idx

    # Subtle fabric inflation bulge across each stitched panel
    billow = math.sin(math.pi * local_t) * 0.0065 * (1.0 - 0.35 * u)

    # Slight tucked crease right at segment seams between bands
    seam_lip = 0.0
    for k in range(1, NUM_SEGMENTS):
        dist = abs(u - k / NUM_SEGMENTS)
        if dist < 0.018:
            # Tiny sewn-seam overlap ridge
            seam_lip += 0.0038 * math.cos((dist / 0.018) * math.pi * 0.5) ** 2

    # Reinforced rolled throat cuff wrapping snugly onto the metal hoop
    throat_cuff = 0.0085 * smoothstep(0.032, 0.0, u)

    # Reinforced double-stitched tail hem
    tail_hem = 0.0040 * smoothstep(0.965, 1.0, u)

    return base_r + billow + seam_lip + throat_cuff + tail_hem


def build_windsock_cloth(mats, coll):
    """Build the 5-segment hollow windsock cone (single-sided doubleSided material, ~360 tris).

    Returns (obj, u_by_index) where u_by_index maps vertex index -> normalized
    longitudinal position u in [0, 1] for exact analytical skinning weights.
    """
    mat_list = [
        mats["nylon_orange"],  # 0 double-sided orange
        mats["nylon_white"],   # 1 double-sided white
    ]

    # Exact band boundaries at k / 5.0 with 3 spans per segment placed near the bending joints
    u_samples = []
    for k in range(NUM_SEGMENTS):
        u0 = k / NUM_SEGMENTS
        u1 = (k + 1) / NUM_SEGMENTS
        local_ts = [0.0, 0.30, 0.70]
        for lt in local_ts:
            u_samples.append(lerp(u0, u1, lt))
    u_samples.append(1.0)

    bm = bmesh.new()
    rings = []
    vert_u = {}

    for u in u_samples:
        y = HOOP_OFFSET_Y - u * SOCK_LEN
        r_out = sock_radius_profile(u)
        ripple_amp = 0.0032 * (u ** 1.15)

        ring = []
        for j in range(RADIAL_STEPS):
            ang = TAU * j / RADIAL_STEPS
            ripple = ripple_amp * (math.sin(5.0 * ang + u * 4.5) + 0.5 * math.cos(3.0 * ang - u * 3.0))
            ro = r_out + ripple
            ca, sa = math.cos(ang), math.sin(ang)
            v = bm.verts.new((ca * ro, y, SWIVEL_Z + sa * ro))
            ring.append(v)
            vert_u[v] = u
        rings.append(ring)

    # Outer longitudinal faces with alternating orange / white bands (doubleSided in glTF & Godot)
    for r_i in range(len(u_samples) - 1):
        u_mid = 0.5 * (u_samples[r_i] + u_samples[r_i + 1])
        seg_idx = min(NUM_SEGMENTS - 1, int(u_mid * NUM_SEGMENTS))
        mat_idx = 0 if (seg_idx % 2 == 0) else 1

        r0, r1 = rings[r_i], rings[r_i + 1]
        for j in range(RADIAL_STEPS):
            nj = (j + 1) % RADIAL_STEPS
            f = bm.faces.new((r0[j], r0[nj], r1[nj], r1[j]))
            f.material_index = mat_idx
            f.smooth = True

    bm.verts.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    u_by_index = [vert_u[v] for v in bm.verts]

    mesh = bpy.data.meshes.new("WindsockCloth")
    bm.to_mesh(mesh)
    bm.free()
    for m in mat_list:
        mesh.materials.append(m)

    obj = bpy.data.objects.new("WindsockCloth", mesh)
    coll.objects.link(obj)
    return obj, u_by_index


def build_armature(coll):
    """Build clean bone hierarchy for Blender & Godot Skeleton3D.

    Bone hierarchy:
        Root
         └─ Swivel         (vertical yaw around local +Y; carries swivel frame & sock)
             └─ Sock_Seg0  (orange band 0; local -X = droop down, local Z = sway)
                 └─ Sock_Seg1 (white band 1)
                     └─ Sock_Seg2 (orange band 2)
                         └─ Sock_Seg3 (white band 3)
                             └─ Sock_Seg4 (orange band 4)
    """
    arm_data = bpy.data.armatures.new("WindsockRig")
    arm_data.display_type = "OCTAHEDRAL"
    arm_obj = bpy.data.objects.new("WindsockRig", arm_data)
    coll.objects.link(arm_obj)

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    b_root = eb.new("Root")
    b_root.head = Vector((0.0, 0.0, 0.0))
    b_root.tail = Vector((0.0, 0.0, 0.80))
    b_root.roll = 0.0

    b_swivel = eb.new("Swivel")
    b_swivel.head = Vector((0.0, 0.0, SWIVEL_Z))
    b_swivel.tail = Vector((0.0, 0.0, SWIVEL_Z + 0.42))
    b_swivel.roll = 0.0
    b_swivel.parent = b_root
    b_swivel.use_connect = False

    prev = b_swivel
    for k in range(NUM_SEGMENTS):
        y0 = HOOP_OFFSET_Y - k * SEG_LEN
        y1 = HOOP_OFFSET_Y - (k + 1) * SEG_LEN
        b = eb.new(f"Sock_Seg{k}")
        b.head = Vector((0.0, y0, SWIVEL_Z))
        b.tail = Vector((0.0, y1, SWIVEL_Z))
        b.align_roll(Vector((0.0, 0.0, 1.0)))  # local +Z = world Up, local +X = (-1, 0, 0)
        b.parent = prev
        b.use_connect = (k > 0)
        prev = b

    bpy.ops.object.mode_set(mode="OBJECT")

    # Set clean XYZ Euler rotation mode on all pose bones for easy keyframing in Blender
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = "XYZ"

    return arm_obj


def compute_sock_weights(u):
    """Compute smooth normalized skinning weights for longitudinal coord u in [0, 1].

    - Very front throat lip (u ~ 0) pins rigidly to `Swivel` so it never separates
      from the steel throat hoop, blending smoothly into `Sock_Seg0` over the first 4.5%
      of the sock length.
    - Across each internal segment boundary k/5, weights blend smoothly across +-5.5%
      of total sock length using a cubic smoothstep so bends never kink or pinch.
    """
    weights = {}

    # Throat attachment blend into Swivel vs segment chain
    swivel_w = 1.0 - smoothstep(0.012, 0.11, u)
    chain_w = 1.0 - swivel_w
    if swivel_w > 1e-5:
        weights["Swivel"] = swivel_w

    if chain_w > 1e-5:
        # Smooth piecewise partition of unity over the 5 segment bones
        # Boundary k is at u = k / 5 for k = 1..4
        half_blend = 0.065  # ~0.18 m smooth blend zone across each seam
        seg_w = [0.0] * NUM_SEGMENTS

        # Start with indicator of each segment, then smoothly crossfade near boundaries
        s_pos = u * NUM_SEGMENTS
        idx = min(NUM_SEGMENTS - 1, int(s_pos))
        seg_w[idx] = 1.0

        for k in range(1, NUM_SEGMENTS):
            ub = k / NUM_SEGMENTS
            if abs(u - ub) < half_blend:
                t = smoothstep(ub - half_blend, ub + half_blend, u)
                seg_w = [0.0] * NUM_SEGMENTS
                seg_w[k - 1] = 1.0 - t
                seg_w[k] = t
                break

        for k, w in enumerate(seg_w):
            if w * chain_w > 1e-5:
                weights[f"Sock_Seg{k}"] = w * chain_w

    # Normalize strictly to 1.0
    total = sum(weights.values())
    if total > 0.0:
        weights = {k: v / total for k, v in weights.items()}
    return weights


def bind_rig(arm_obj, pole_obj, swivel_obj, cloth_obj, u_by_index):
    """Attach pole, swivel frame, and skinned windsock cloth to the armature."""
    # Pole: parented cleanly to the rig root object so it stands vertically at (0, 0, 0)
    pole_obj.parent = arm_obj
    pole_obj.parent_type = "OBJECT"

    # Swivel frame: bone-parented to Swivel bone (rotates 360 deg with wind heading)
    # Compensate Blender's full bone-tail transform (rotation + translation) so rest pose = identity
    swivel_obj.parent = arm_obj
    swivel_obj.parent_type = "BONE"
    swivel_obj.parent_bone = "Swivel"
    b_swivel = arm_obj.data.bones["Swivel"]
    swivel_tail_mat = b_swivel.matrix_local @ Matrix.Translation((0.0, b_swivel.length, 0.0))
    swivel_obj.matrix_parent_inverse = (arm_obj.matrix_world @ swivel_tail_mat).inverted() @ swivel_obj.matrix_world

    # Cloth: skinned to armature via Armature modifier + analytical vertex groups
    cloth_obj.parent = arm_obj
    mod = cloth_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    mod.use_vertex_groups = True

    bone_names = ["Swivel"] + [f"Sock_Seg{k}" for k in range(NUM_SEGMENTS)]
    vgroups = {bn: cloth_obj.vertex_groups.new(name=bn) for bn in bone_names}

    for v_idx, u in enumerate(u_by_index):
        for bn, w in compute_sock_weights(u).items():
            vgroups[bn].add([v_idx], w, "REPLACE")


def set_action_linear_or_bezier(action):
    """Handle both Blender 4.x action.fcurves and Blender 5.x layered channelbags safely."""
    fcurves = []
    if hasattr(action, "fcurves") and action.fcurves is not None:
        try:
            fcurves.extend(list(action.fcurves))
        except Exception:
            pass
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in getattr(layer, "strips", []):
                for bag in getattr(strip, "channelbags", []):
                    fcurves.extend(list(bag.fcurves))
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def bake_wind_action(arm_obj, name, frame_count, spec):
    """Bake a seamlessly looping wind animation Action on the armature.

    `spec` keys:
      droop_deg: list of 5 base downward droop angles (degrees) per segment
      pitch_amp: list of 5 vertical flutter amplitudes (degrees)
      yaw_amp  : list of 5 horizontal sway amplitudes (degrees)
      swivel_amp: degrees of slow swivel wind-direction hunting
      cycles   : integer wave cycles per loop (guarantees exact seamless loop)
      phase_step: phase lag per segment (radians) for travelling wave from throat to tail
    """
    action = bpy.data.actions.new(name=name)
    if not arm_obj.animation_data:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = action

    droop_deg = spec["droop_deg"]
    pitch_amp = spec["pitch_amp"]
    yaw_amp = spec["yaw_amp"]
    swivel_amp = spec["swivel_amp"]
    cycles = spec["cycles"]
    phase_step = spec["phase_step"]

    pb_swivel = arm_obj.pose.bones["Swivel"]
    pb_segs = [arm_obj.pose.bones[f"Sock_Seg{k}"] for k in range(NUM_SEGMENTS)]

    # Sample every 2 frames + exact closing frame so loop matches frame 0 identically
    sample_frames = list(range(0, frame_count, 2)) + [frame_count]

    for f in sample_frames:
        t = f / float(frame_count)  # 0.0 -> 1.0 exact periodic loop
        w1 = TAU * cycles * t
        w2 = TAU * (cycles * 2) * t
        w_slow = TAU * 1.0 * t

        # Subtle wind direction hunting on the swivel
        swivel_rad = math.radians(swivel_amp * (0.7 * math.sin(w_slow) + 0.3 * math.sin(2.0 * w_slow + 0.9)))
        pb_swivel.rotation_euler = Euler((0.0, swivel_rad, 0.0), "XYZ")
        pb_swivel.keyframe_insert(data_path="rotation_euler", frame=f)

        for k, pb in enumerate(pb_segs):
            ph = k * phase_step
            # Negative local X = downward droop
            pitch_deg = -droop_deg[k] + pitch_amp[k] * (
                0.72 * math.sin(w1 - ph) + 0.28 * math.cos(w2 - ph * 1.35 + 0.4)
            )
            # Local Z = horizontal lateral wave
            yaw_deg = yaw_amp[k] * (
                0.75 * math.sin(w1 - ph + 0.8) + 0.25 * math.sin(w2 - ph * 1.2 - 0.5)
            )
            # Tiny torsional roll flutter near tail
            roll_deg = (0.18 * yaw_amp[k]) * math.cos(w1 - ph + 0.3)

            pb.rotation_euler = Euler(
                (math.radians(pitch_deg), math.radians(roll_deg), math.radians(yaw_deg)),
                "XYZ",
            )
            pb.keyframe_insert(data_path="rotation_euler", frame=f)

    set_action_linear_or_bezier(action)

    # Push to NLA track so glTF exports EVERY wind state as an AnimationPlayer clip
    track = arm_obj.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 0, action)
    strip.action_frame_start = 0
    strip.action_frame_end = frame_count
    track.mute = True
    return action


def create_wind_animations(arm_obj):
    """Create 4 FAA-inspired wind speed animation loops (Calm, Light, Moderate, Strong)."""
    specs = {
        # 0-3 kt: drapes cleanly downward (~78 deg total) with slow lazy breathing
        "Wind_Calm": {
            "frames": 96,
            "droop_deg": [18.0, 24.0, 18.0, 12.0, 8.0],
            "pitch_amp": [1.5, 2.2, 2.8, 3.2, 3.8],
            "yaw_amp": [1.2, 2.0, 2.8, 3.6, 4.5],
            "swivel_amp": 2.5,
            "cycles": 1,
            "phase_step": 0.65,
        },
        # 6-8 kt: first 2 segments lift out, outer 3 droop gracefully (~48 deg total)
        "Wind_Light": {
            "frames": 72,
            "droop_deg": [11.0, 12.0, 11.0, 8.5, 6.0],
            "pitch_amp": [2.2, 3.4, 4.6, 5.5, 6.5],
            "yaw_amp": [1.8, 3.2, 4.8, 6.2, 7.8],
            "swivel_amp": 3.5,
            "cycles": 2,
            "phase_step": 0.85,
        },
        # 10-12 kt: strong coastal breeze, mostly horizontal (~20 deg total), lively ripple
        "Wind_Moderate": {
            "frames": 60,
            "droop_deg": [3.5, 4.5, 4.8, 4.2, 3.5],
            "pitch_amp": [1.8, 3.2, 4.8, 6.2, 7.8],
            "yaw_amp": [2.2, 4.2, 6.5, 8.8, 11.2],
            "swivel_amp": 4.0,
            "cycles": 2,
            "phase_step": 1.05,
        },
        # 15+ kt: taut & fully inflated horizontal (~4 deg droop), brisk high-energy tail snap
        "Wind_Strong": {
            "frames": 48,
            "droop_deg": [0.8, 1.0, 1.0, 0.8, 0.6],
            "pitch_amp": [1.4, 2.8, 4.5, 6.4, 8.8],
            "yaw_amp": [2.4, 4.8, 7.8, 11.0, 14.5],
            "swivel_amp": 3.0,
            "cycles": 3,
            "phase_step": 1.20,
        },
    }

    actions = {}
    for name, spec in specs.items():
        actions[name] = bake_wind_action(arm_obj, name, spec["frames"], spec)

    # Set Wind_Moderate active in Blender for immediate playback when user opens windsock.blend
    arm_obj.animation_data.action = actions["Wind_Moderate"]
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = 60
    bpy.context.scene.render.fps = 24
    return actions


def setup_studio(scene):
    """Set up Tideways crisp overcast coastal studio for preview rendering."""
    studio = bpy.data.collections.new("Studio")
    scene.collection.children.link(studio)

    # Clean matte concrete/tarmac ground pad fading gently into coastal sky
    bpy.ops.mesh.primitive_plane_add(size=80.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    ground.name = "StudioGround"
    for owner in list(ground.users_collection):
        owner.objects.unlink(ground)
    studio.objects.link(ground)
    g_mat = make_pbr_material("Studio tarmac", (0.24, 0.27, 0.30), roughness=0.86, specular=0.22)
    ground.data.materials.append(g_mat)

    # Coastal sky background (soft slate-blue horizon like cessna_172 / beaver_floatplane)
    scene.world = bpy.data.worlds.new("Coastal sky")
    if not scene.world.node_tree:
        scene.world.use_nodes = True
    nt = scene.world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    tex_coord = nt.nodes.new("ShaderNodeTexCoord")

    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.36, 0.45, 0.54, 1.0)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (0.14, 0.23, 0.34, 1.0)

    nt.links.new(tex_coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.95
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # Warm coastal sun key + cool sky fill
    bpy.ops.object.light_add(type="SUN", location=(5.0, -5.0, 9.0))
    sun = bpy.context.object
    sun.name = "KeySun"
    sun.data.energy = 3.2
    sun.data.angle = math.radians(2.8)
    sun.data.color = (1.0, 0.96, 0.90)
    sun.rotation_euler = (Vector((0, -1.0, 3.0)) - Vector((6.0, -5.5, 9.5))).to_track_quat("-Z", "Y").to_euler()
    for owner in list(sun.users_collection):
        owner.objects.unlink(sun)
    studio.objects.link(sun)

    bpy.ops.object.light_add(type="AREA", location=(-6.5, 3.5, 5.5))
    rim = bpy.context.object
    rim.name = "RimFill"
    rim.data.shape = "DISK"
    rim.data.size = 4.5
    rim.data.energy = 340.0
    rim.data.color = (0.76, 0.88, 1.0)
    rim.rotation_euler = (Vector((0, -1.2, 4.2)) - rim.location).to_track_quat("-Z", "Y").to_euler()
    for owner in list(rim.users_collection):
        owner.objects.unlink(rim)
    studio.objects.link(rim)

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "StudioCamera"
    camera.data.lens = 52.0
    for owner in list(camera.users_collection):
        owner.objects.unlink(camera)
    studio.objects.link(camera)
    scene.camera = camera

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    return studio, camera


def aim_camera(camera, location, target, lens=52.0):
    camera.location = Vector(location)
    camera.data.lens = lens
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    mats = create_materials()
    coll = bpy.data.collections.new("Windsock")
    scene.collection.children.link(coll)

    pole_obj = build_mast_and_pedestal(mats, coll)
    swivel_obj = build_swivel_frame(mats, coll)
    cloth_obj, u_by_index = build_windsock_cloth(mats, coll)
    arm_obj = build_armature(coll)

    bind_rig(arm_obj, pole_obj, swivel_obj, cloth_obj, u_by_index)
    actions = create_wind_animations(arm_obj)

    # Export clean Godot-ready GLB (only the Windsock rig & meshes, not studio objects)
    glb_path = ROOT / "assets" / "models" / "windsock.glb"
    bpy.ops.object.select_all(action="DESELECT")
    for obj in (arm_obj, pole_obj, swivel_obj, cloth_obj):
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_normals=True,
        export_materials="EXPORT",
        export_skins=True,
        export_all_influences=False,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_bake_animation=True,
        export_optimize_animation_size=True,
    )

    counts = {
        o.name: (len(o.data.vertices), len(o.data.polygons))
        for o in (pole_obj, swivel_obj, cloth_obj)
    }
    print("WINDSOCK_EXPORTED:", glb_path)
    print("MESH_COUNTS (verts, polys):", counts)
    print("BONES:", [b.name for b in arm_obj.data.bones])
    print("ACTIONS:", list(actions.keys()))

    # Studio setup & preview renders
    studio, camera = setup_studio(scene)

    # Hero preview: full standing mast + fluttering Wind_Moderate sock + glowing summit beacon
    arm_obj.animation_data.action = actions["Wind_Moderate"]
    scene.frame_set(16)
    aim_camera(camera, (8.8, -6.6, 3.35), (0.0, -1.10, 2.95), lens=38.0)

    # Save editable .blend (keep studio hidden in viewport, visible in render)
    for o in studio.objects:
        o.hide_set(True)
    bpy.context.preferences.filepaths.save_version = 0
    blend_path = ROOT / "art" / "windsock.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

    # Render hero preview
    for o in studio.objects:
        o.hide_set(False)
    scene.render.filepath = str(ROOT / "art" / "windsock_preview.png")
    bpy.ops.render.render(write_still=True)

    # Optional diagnostic multi-view + all-wind-states renders
    if "--views" in sys.argv:
        idx = sys.argv.index("--views")
        if idx + 1 < len(sys.argv):
            out_dir = Path(sys.argv[idx + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            scene.render.resolution_x, scene.render.resolution_y = 1000, 750
            scene.cycles.samples = 28

            # 1. Close-up of swivel hub, spider yoke, throat hoop & beacon
            arm_obj.animation_data.action = actions["Wind_Moderate"]
            scene.frame_set(16)
            aim_camera(camera, (2.2, -2.1, 5.45), (0.0, -0.55, 5.20), lens=58.0)
            scene.render.filepath = str(out_dir / "closeup_swivel_hoop.png")
            bpy.ops.render.render(write_still=True)

            # 2. Close-up of base footing, bolts, gussets & tilt-down hinge
            aim_camera(camera, (1.65, -1.45, 0.95), (0.0, 0.0, 0.65), lens=52.0)
            scene.render.filepath = str(out_dir / "closeup_base.png")
            bpy.ops.render.render(write_still=True)

            # 3. Rear-3/4 view looking into open tail & hollow sock interior
            aim_camera(camera, (-2.6, -5.2, 5.05), (0.0, -1.6, 5.10), lens=55.0)
            scene.render.filepath = str(out_dir / "rear_hollow_tail.png")
            bpy.ops.render.render(write_still=True)

            # 4. Side profile comparison of all 4 wind animation states!
            for state_name, frame in [
                ("Wind_Calm", 24),
                ("Wind_Light", 18),
                ("Wind_Moderate", 15),
                ("Wind_Strong", 12),
            ]:
                arm_obj.animation_data.action = actions[state_name]
                scene.frame_set(frame)
                aim_camera(camera, (6.2, -1.45, 4.45), (0.0, -1.45, 4.35), lens=52.0)
                scene.render.filepath = str(out_dir / f"state_{state_name.lower()}.png")
                bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
