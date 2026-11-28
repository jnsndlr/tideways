"""Build the Tideways stump kit, individual GLBs, and a diorama preview.

Styled to match art/pine_tree.py, art/oak_tree.py, and art/lumber_yard_kit.py:
crisp flat-shaded low-poly facets, flared root buttresses extending below z=0 so
stumps sit cleanly on sloped island terrain, warm cedar/oak bark harmonized with
the trees, and pale sapwood / warm heartwood cut tops.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P art/stump_kit.py

Outputs:
    art/stump_kit.blend
    art/stump_kit_preview.png
    assets/models/stump_kit/*.glb
"""
import math
from pathlib import Path
from random import Random

import bmesh
import bpy
from mathutils import Euler, Vector

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"
OUT = ROOT / "assets" / "models" / "stump_kit"
OUT.mkdir(parents=True, exist_ok=True)

UP = Vector((0.0, 0.0, 1.0))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Material palette harmonized with pine_tree.py, oak_tree.py, and lumber_yard_kit.py
PALETTE = {
    "bark": ("7A5232", 0.90, 0.0),          # warm chestnut-cedar bark
    "bark_dark": ("462C1A", 0.93, 0.0),     # root groove / shadow bark
    "bark_warm": ("986A3E", 0.88, 0.0),     # sunlit bark ridge
    "bark_aged": ("5E5348", 0.93, 0.0),     # silvered weathered bark
    "bark_aged_dark": ("3B342E", 0.95, 0.0),
    "sapwood": ("E8CD9A", 0.84, 0.0),       # fresh pale outer cut ring
    "heartwood": ("C9955B", 0.85, 0.0),     # warm amber inner heartwood
    "heartwood_dark": ("9E6E3C", 0.86, 0.0),
    "aged_top": ("9B8D7A", 0.92, 0.0),      # weathered grey-tan cut top
    "aged_core": ("766959", 0.93, 0.0),
    "splinter": ("DFBE86", 0.86, 0.0),      # sheared fresh wood spike
    "woodchip": ("E5C78E", 0.88, 0.0),
    "moss": ("5A8A32", 0.90, 0.0),          # bright olive-moss tuft
    "moss_dark": ("3A6322", 0.92, 0.0),
    "sprout": ("7AA828", 0.85, 0.0),
    "ground": ("6C8B3E", 0.95, 0.0),        # preview clearing grass
    "dirt": ("7D6650", 0.95, 0.0),          # preview logging dirt patch
}


def srgb_hex_to_linear(hex_value):
    srgb = [int(hex_value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


MATERIALS = {}
for mat_name, (hex_val, rough, metal) in PALETTE.items():
    linear = srgb_hex_to_linear(hex_val)
    mat = bpy.data.materials.new(mat_name)
    mat.diffuse_color = linear
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = linear
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    MATERIALS[mat_name] = mat


class KitMesh:
    """Flat-shaded material-indexed mesh builder."""

    def __init__(self, seed=101):
        self.verts = []
        self.faces = []
        self.mats = []
        self.rng = Random(seed)

    def add_face(self, pts, mat_name, out_hint=None):
        if len(pts) < 3:
            return
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if n.length < 1e-9:
            return
        if out_hint is not None and n.dot(out_hint) < 0.0:
            pts = list(reversed(pts))
        start = len(self.verts)
        self.verts.extend(pts)
        self.faces.append(tuple(range(start, start + len(pts))))
        self.mats.append(mat_name)

    def add_quad(self, p0, p1, p2, p3, mat_name, out_hint=None):
        self.add_face([p0, p1, p2], mat_name, out_hint)
        self.add_face([p0, p2, p3], mat_name, out_hint)

    def add_box(self, center, size, mat_name, rot=(0.0, 0.0, 0.0)):
        c = Vector(center)
        m = Euler(rot).to_matrix()
        sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
        pts = [
            c + m @ Vector((x * sx, y * sy, z * sz))
            for z in (-1, 1)
            for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        quads = [
            (3, 2, 1, 0),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]
        for a, b, cc, d in quads:
            self.add_quad(pts[a], pts[b], pts[cc], pts[d], mat_name)

    def add_stump_body(
        self,
        offset=Vector((0.0, 0.0, 0.0)),
        radius_top=0.30,
        radius_base=0.44,
        height=0.55,
        depth_below=-0.24,
        sides=10,
        flute_base=0.18,
        flute_top=0.05,
        tilt_x=0.0,
        tilt_y=0.0,
        lean=Vector((0.0, 0.0)),
        notch_dir=None,
        notch_depth=0.0,
        notch_height=0.0,
        bark_main="bark",
        bark_ridge="bark_warm",
        bark_groove="bark_dark",
        top_outer="sapwood",
        top_inner="heartwood",
        top_core="heartwood_dark",
        jagged_spike=0.0,
        phase=0.35,
    ):
        """Build a faceted fluted stump with flared root buttresses and concentric cut top."""
        z_levels = [
            (depth_below, radius_base * 1.06, flute_base * 0.90),
            (0.0, radius_base, flute_base),
            (height * 0.42, (radius_base * 0.42 + radius_top * 0.58), flute_base * 0.45),
            (height, radius_top, flute_top),
        ]

        rings = []
        for idx, (z, r, flute) in enumerate(z_levels):
            t = max(0.0, min(1.0, (z - depth_below) / max(0.01, height - depth_below)))
            twist = idx * 0.04
            ring = []
            for i in range(sides):
                ang = math.tau * i / sides + phase + twist
                is_ridge = (i % 2 == 0)
                jitter = 1.0 + (0.06 if is_ridge else -0.04) * math.sin(i * 2.1 + idx * 0.7 + phase)
                rr = r * (1.0 + (flute if is_ridge else -flute * 0.62)) * jitter
                x = rr * math.cos(ang) + lean.x * t
                y = rr * math.sin(ang) + lean.y * t
                zz = z
                if idx == len(z_levels) - 1:
                    zz += x * tilt_x + y * tilt_y
                    # Optional felling wedge notch on one side
                    if notch_dir is not None and notch_depth > 0.0:
                        nd = notch_dir.normalized()
                        proj = Vector((x, y)).dot(nd)
                        if proj > radius_top * (1.0 - notch_depth):
                            frac = (proj - radius_top * (1.0 - notch_depth)) / max(0.05, radius_top * notch_depth)
                            zz -= notch_height * min(1.0, frac)
                    # Optional jagged splintered spike on one side
                    if jagged_spike > 0.0:
                        spike_dir = Vector((math.cos(phase + 0.6), math.sin(phase + 0.6)))
                        proj = Vector((x, y)).normalized().dot(spike_dir)
                        if proj > 0.35:
                            zz += jagged_spike * ((proj - 0.35) / 0.65) ** 1.4
                ring.append(offset + Vector((x, y, zz)))
            rings.append(ring)

        # Side walls
        for k in range(len(rings) - 1):
            r0, r1 = rings[k], rings[k + 1]
            c_z = 0.5 * (z_levels[k][0] + z_levels[k + 1][0])
            center = offset + Vector((0.0, 0.0, c_z))
            for i in range(sides):
                j = (i + 1) % sides
                fc = (r0[i] + r0[j] + r1[j] + r1[i]) * 0.25
                out = Vector((fc.x - center.x, fc.y - center.y, 0.0))
                if k == 0:
                    mat = bark_groove
                elif i % 2 == 0:
                    mat = bark_ridge if (i % 4 == 0) else bark_main
                else:
                    mat = bark_groove if (k == 1) else bark_main
                self.add_quad(r0[i], r0[j], r1[j], r1[i], mat, out)

        # Cut top face: outer sapwood rim -> inner heartwood ring -> center pith
        top_ring = rings[-1]
        top_center = sum(top_ring, Vector((0.0, 0.0, 0.0))) / len(top_ring)
        inner_ring = [top_center.lerp(p, 0.68) + Vector((0.0, 0.0, 0.008)) for p in top_ring]
        core_ring = [top_center.lerp(p, 0.26) + Vector((0.0, 0.0, 0.012)) for p in top_ring]

        for i in range(sides):
            j = (i + 1) % sides
            self.add_quad(top_ring[i], top_ring[j], inner_ring[j], inner_ring[i], top_outer, UP)
            self.add_quad(inner_ring[i], inner_ring[j], core_ring[j], core_ring[i], top_inner, UP)
            self.add_face([top_center + Vector((0.0, 0.0, 0.014)), core_ring[i], core_ring[j]], top_core, UP)

        return top_center, top_ring

    def add_root_buttress(self, offset, angle, length, width, height, mat_top="bark_warm", mat_side="bark_dark"):
        """Add an outward-flaring surface root spur anchored below z=0."""
        d = Vector((math.cos(angle), math.sin(angle), 0.0))
        s = Vector((-d.y, d.x, 0.0))
        p_in_l = offset + d * 0.12 + s * (width * 0.5) + Vector((0.0, 0.0, -0.22))
        p_in_r = offset + d * 0.12 - s * (width * 0.5) + Vector((0.0, 0.0, -0.22))
        p_in_t = offset + d * 0.16 + Vector((0.0, 0.0, height))

        p_mid_l = offset + d * (length * 0.62) + s * (width * 0.36) + Vector((0.0, 0.0, -0.18))
        p_mid_r = offset + d * (length * 0.62) - s * (width * 0.36) + Vector((0.0, 0.0, -0.18))
        p_mid_t = offset + d * (length * 0.60) + Vector((0.0, 0.0, height * 0.42))

        p_tip = offset + d * length + Vector((0.0, 0.0, -0.14))

        self.add_quad(p_in_l, p_mid_l, p_mid_t, p_in_t, mat_top, s + UP)
        self.add_quad(p_in_t, p_mid_t, p_mid_r, p_in_r, mat_side, -s + UP)
        self.add_face([p_mid_l, p_tip, p_mid_t], mat_top, d + s + UP)
        self.add_face([p_mid_t, p_tip, p_mid_r], mat_side, d - s + UP)

    def add_log_section(self, center, radius, length, rot=(0.0, 0.0, 0.0), sides=8, bark="bark", end="sapwood", core="heartwood"):
        """Add a felled horizontal log section along local X."""
        c = Vector(center)
        m = Euler(rot).to_matrix()
        r0, r1 = [], []
        for i in range(sides):
            a = math.tau * i / sides + 0.2
            rad_a = radius * (1.0 + 0.04 * math.sin(i * 2.3))
            rad_b = radius * 0.94 * (1.0 + 0.04 * math.cos(i * 1.9))
            r0.append(c + m @ Vector((-length * 0.5, rad_a * math.cos(a), rad_a * math.sin(a))))
            r1.append(c + m @ Vector((length * 0.5, rad_b * math.cos(a), rad_b * math.sin(a))))

        for i in range(sides):
            j = (i + 1) % sides
            fc = (r0[i] + r0[j] + r1[j] + r1[i]) * 0.25
            out = fc - c
            mat = "bark_warm" if i % 3 == 0 else ("bark_dark" if i % 3 == 2 else bark)
            self.add_quad(r0[i], r0[j], r1[j], r1[i], mat, out)

        for ring, dir_sign in ((r0, -1.0), (r1, 1.0)):
            ec = sum(ring, Vector((0.0, 0.0, 0.0))) / len(ring)
            out_n = m @ Vector((dir_sign, 0.0, 0.0))
            inner = [ec.lerp(p, 0.62) for p in ring]
            for i in range(sides):
                j = (i + 1) % sides
                self.add_quad(ring[i], ring[j], inner[j], inner[i], end, out_n)
                self.add_face([ec, inner[i], inner[j]], core, out_n)

    def add_moss_tuft(self, center, rx, ry, h, mat="moss"):
        """Low-poly faceted moss cushion."""
        c = Vector(center)
        sides = 6
        rim = [
            c + Vector((rx * math.cos(math.tau * i / sides), ry * math.sin(math.tau * i / sides), 0.0))
            for i in range(sides)
        ]
        top = c + Vector((0.0, 0.0, h))
        for i in range(sides):
            j = (i + 1) % sides
            self.add_face([top, rim[i], rim[j]], mat if i % 2 == 0 else "moss_dark", UP)

    def finish(self, name, origin=(0.0, 0.0, 0.0)):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        slots = list(dict.fromkeys(self.mats))
        for mname in slots:
            mesh.materials.append(MATERIALS[mname])
        mesh.polygons.foreach_set("material_index", [slots.index(m) for m in self.mats])
        for poly in mesh.polygons:
            poly.use_smooth = False
        obj = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(obj)
        obj.location = Vector(origin)
        return obj


# -----------------------------------------------------------------------------
# Stump kit asset builders
# -----------------------------------------------------------------------------

def build_stump_fresh_pine():
    kb = KitMesh(seed=11)
    kb.add_stump_body(
        radius_top=0.28,
        radius_base=0.44,
        height=0.52,
        sides=10,
        flute_base=0.18,
        flute_top=0.04,
        tilt_x=0.06,
        tilt_y=-0.04,
        notch_dir=Vector((1.0, -0.3)),
        notch_depth=0.35,
        notch_height=0.09,
        phase=0.25,
    )
    for ang in (0.3, 1.55, 2.85, 4.15, 5.4):
        kb.add_root_buttress(Vector((0.0, 0.0, 0.0)), ang, length=0.66, width=0.20, height=0.22)
    return kb.finish("stump_fresh_pine")


def build_stump_fresh_broad():
    kb = KitMesh(seed=22)
    kb.add_stump_body(
        radius_top=0.42,
        radius_base=0.64,
        height=0.46,
        sides=12,
        flute_base=0.20,
        flute_top=0.05,
        tilt_x=-0.04,
        tilt_y=0.05,
        notch_dir=Vector((-0.8, -0.6)),
        notch_depth=0.32,
        notch_height=0.08,
        phase=0.50,
    )
    for idx, ang in enumerate((0.15, 1.20, 2.25, 3.45, 4.55, 5.55)):
        kb.add_root_buttress(
            Vector((0.0, 0.0, 0.0)),
            ang,
            length=0.88 + 0.08 * (idx % 2),
            width=0.26,
            height=0.26,
        )
    return kb.finish("stump_fresh_broad")


def build_stump_high_cut():
    kb = KitMesh(seed=33)
    kb.add_stump_body(
        radius_top=0.26,
        radius_base=0.42,
        height=0.92,
        sides=10,
        flute_base=0.16,
        flute_top=0.04,
        tilt_x=0.10,
        tilt_y=0.04,
        lean=Vector((0.04, -0.03)),
        notch_dir=Vector((0.9, 0.4)),
        notch_depth=0.48,
        notch_height=0.18,
        phase=0.70,
    )
    for ang in (0.5, 1.8, 3.2, 4.7):
        kb.add_root_buttress(Vector((0.0, 0.0, 0.0)), ang, length=0.64, width=0.19, height=0.24)
    return kb.finish("stump_high_cut")


def build_stump_jagged():
    kb = KitMesh(seed=44)
    kb.add_stump_body(
        radius_top=0.27,
        radius_base=0.44,
        height=0.58,
        sides=10,
        flute_base=0.17,
        flute_top=0.06,
        tilt_x=-0.08,
        tilt_y=0.06,
        jagged_spike=0.34,
        top_outer="splinter",
        top_inner="heartwood",
        phase=0.95,
    )
    # Extra sheared splinter shard on the high edge
    kb.add_box((0.14, 0.16, 0.80), (0.09, 0.13, 0.30), "splinter", rot=(0.18, -0.14, 0.45))
    kb.add_box((0.06, 0.19, 0.72), (0.07, 0.09, 0.22), "sapwood", rot=(0.10, -0.22, 0.20))
    for ang in (0.2, 1.5, 2.9, 4.3, 5.5):
        kb.add_root_buttress(Vector((0.0, 0.0, 0.0)), ang, length=0.68, width=0.20, height=0.22)
    return kb.finish("stump_jagged")


def build_stump_weathered():
    kb = KitMesh(seed=55)
    top_c, _ = kb.add_stump_body(
        radius_top=0.31,
        radius_base=0.48,
        height=0.42,
        sides=10,
        flute_base=0.19,
        flute_top=0.06,
        tilt_x=0.05,
        tilt_y=-0.06,
        bark_main="bark_aged",
        bark_ridge="bark_aged",
        bark_groove="bark_aged_dark",
        top_outer="aged_top",
        top_inner="aged_core",
        top_core="bark_aged_dark",
        phase=1.20,
    )
    for ang in (0.4, 1.6, 2.8, 4.1, 5.3):
        kb.add_root_buttress(
            Vector((0.0, 0.0, 0.0)),
            ang,
            length=0.72,
            width=0.21,
            height=0.20,
            mat_top="bark_aged",
            mat_side="bark_aged_dark",
        )
    # Moss patches on top rim and root shoulder
    kb.add_moss_tuft(top_c + Vector((0.12, -0.08, -0.01)), 0.16, 0.13, 0.07, "moss")
    kb.add_moss_tuft(Vector((-0.34, 0.24, 0.04)), 0.18, 0.14, 0.09, "moss")
    kb.add_moss_tuft(Vector((0.28, 0.28, 0.02)), 0.14, 0.11, 0.06, "sprout")
    return kb.finish("stump_weathered")


def build_stump_cluster_small():
    kb = KitMesh(seed=66)
    kb.add_stump_body(
        offset=Vector((-0.24, -0.08, 0.0)),
        radius_top=0.19,
        radius_base=0.30,
        height=0.48,
        sides=8,
        flute_base=0.15,
        flute_top=0.04,
        tilt_x=0.08,
        lean=Vector((-0.05, -0.02)),
        phase=0.20,
    )
    kb.add_stump_body(
        offset=Vector((0.26, 0.14, 0.0)),
        radius_top=0.16,
        radius_base=0.26,
        height=0.34,
        sides=8,
        flute_base=0.14,
        flute_top=0.04,
        tilt_y=-0.09,
        lean=Vector((0.04, 0.03)),
        phase=0.85,
    )
    for ang in (2.3, 3.6, 4.8):
        kb.add_root_buttress(Vector((-0.24, -0.08, 0.0)), ang, length=0.46, width=0.14, height=0.16)
    for ang in (0.1, 1.2, 5.6):
        kb.add_root_buttress(Vector((0.26, 0.14, 0.0)), ang, length=0.42, width=0.13, height=0.14)
    return kb.finish("stump_cluster_small")


def build_stump_with_chips():
    kb = KitMesh(seed=77)
    kb.add_stump_body(
        radius_top=0.30,
        radius_base=0.46,
        height=0.50,
        sides=10,
        flute_base=0.18,
        flute_top=0.05,
        tilt_x=0.05,
        notch_dir=Vector((1.0, 0.15)),
        notch_depth=0.36,
        notch_height=0.09,
        phase=0.45,
    )
    for ang in (0.2, 1.45, 2.75, 4.05, 5.25):
        kb.add_root_buttress(Vector((0.0, 0.0, 0.0)), ang, length=0.66, width=0.20, height=0.22)
    # Scattered wood chips around the base
    chip_specs = [
        (0.54, 0.12, 0.02, 0.14, 0.07, 0.025, 0.4),
        (0.66, -0.18, 0.02, 0.12, 0.06, 0.022, 1.1),
        (0.42, -0.44, 0.02, 0.15, 0.08, 0.028, 2.3),
        (-0.50, -0.32, 0.02, 0.11, 0.06, 0.022, 0.8),
        (-0.58, 0.22, 0.02, 0.13, 0.07, 0.025, 1.9),
        (0.24, 0.56, 0.02, 0.12, 0.05, 0.020, 2.7),
    ]
    for cx, cy, cz, sx, sy, sz, rz in chip_specs:
        kb.add_box((cx, cy, cz), (sx, sy, sz), "woodchip", rot=(0.08, -0.06, rz))
    # Small cut offcut round lying nearby
    kb.add_log_section((0.76, 0.42, 0.14), radius=0.18, length=0.38, rot=(0.0, 0.0, 0.65), sides=8)
    return kb.finish("stump_with_chips")


def build_felled_log_short():
    kb = KitMesh(seed=88)
    kb.add_log_section((0.0, 0.0, 0.20), radius=0.25, length=2.45, rot=(0.0, 0.02, 0.0), sides=8)
    # Small branch stub sticking off the log
    kb.add_log_section((0.42, 0.22, 0.30), radius=0.065, length=0.32, rot=(0.0, -0.45, 0.95), sides=6)
    return kb.finish("felled_log_short")


# -----------------------------------------------------------------------------
# Export each asset centered at origin, then arrange in preview diorama
# -----------------------------------------------------------------------------

ASSETS = [
    ("stump_fresh_pine", build_stump_fresh_pine, -3.6, 1.4, 0.2),
    ("stump_fresh_broad", build_stump_fresh_broad, -1.2, 1.5, -0.4),
    ("stump_high_cut", build_stump_high_cut, 1.3, 1.4, 0.5),
    ("stump_jagged", build_stump_jagged, 3.6, 1.4, -0.3),
    ("stump_weathered", build_stump_weathered, -3.4, -1.4, 0.7),
    ("stump_cluster_small", build_stump_cluster_small, -1.0, -1.5, -0.2),
    ("stump_with_chips", build_stump_with_chips, 1.5, -1.4, 0.4),
    ("felled_log_short", build_felled_log_short, 3.6, -1.6, 0.35),
]

for name, builder, px, py, rot_z in ASSETS:
    obj = builder()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    glb_path = OUT / f"{name}.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        use_selection=True,
        export_format="GLB",
    )
    tri_count = sum(max(1, len(p.vertices) - 2) for p in obj.data.polygons)
    print(f"Exported {glb_path.name}: {tri_count} tris")
    obj.location = Vector((px, py, 0.0))
    obj.rotation_euler.z = rot_z

# Preview diorama ground pad (not exported)
ground_kb = KitMesh(seed=99)
ground_kb.add_box((0.0, 0.0, -0.20), (11.5, 6.2, 0.40), "ground")
ground_kb.add_box((0.2, -0.1, 0.008), (9.6, 4.6, 0.016), "dirt")
ground_kb.finish("preview_ground")

# Camera, lighting, and Cycles preview render
target = Vector((0.0, 0.0, 0.35))
direction = Vector((4.8, -9.8, 6.8))
rotation = (-direction).to_track_quat("-Z", "Y")

bpy.ops.object.camera_add(location=target + direction)
camera = bpy.context.object
camera.rotation_euler = rotation.to_euler()
camera.data.type = "ORTHO"
camera.data.ortho_scale = 11.2
scene.camera = camera

scene.world = bpy.data.worlds.new("Overcast sky")
scene.world.color = (0.58, 0.68, 0.78)

bpy.ops.object.light_add(type="SUN")
bpy.context.object.rotation_euler = (0.55, -0.50, -0.40)
bpy.context.object.data.energy = 3.6
bpy.context.object.data.angle = 0.15

scene.render.engine = "CYCLES"
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = 1440
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.filepath = str(ART / "stump_kit_preview.png")

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART / "stump_kit.blend"))
bpy.ops.render.render(write_still=True)
print("Stump kit exported to", OUT)
