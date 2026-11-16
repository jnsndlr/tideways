# Turns Jon's textured pine (Meshy, matching assets/textures/pine_card.png) into faceted,
# vertex-coloured trees like art/trees.py's, and exports assets/models/pines_meshy.glb.
#   Blender -b -P art/pines_meshy.py -- <source.glb>
# The texture is baked into the corners of each face (sampled a little in from the
# corner, so no black gutter bleeds in), faces are flat-shaded, and each variant gets a
# <name>_mid and <name>_far by decimation (Models.MPINE_*_DIST), and a <name>_lod of
# stacked cones that only casts the shadows.
import bpy, bmesh, sys, os, math
from mathutils import Vector

src = sys.argv[sys.argv.index("--") + 1]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "models", "pines_meshy.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
ob = next(o for o in bpy.data.objects if o.type == "MESH")
img = next(i for i in bpy.data.images if i.size[0])
W, H = img.size
px = list(img.pixels)


# Brings the texture's mean colour to the card sprite's (pine_card.png), so the woods
# keep one palette where modelled pines give way to the Backdrop's cards.
GAIN = (0.92, 0.67, 1.55)


def sample(uv):
    x = min(W - 1, max(0, int(uv.x * W)))
    y = min(H - 1, max(0, int(uv.y * H)))
    i = (y * W + x) * 4
    return (px[i] * GAIN[0], px[i + 1] * GAIN[1], px[i + 2] * GAIN[2], 1.0)


# Bake into a fresh base mesh: model space is Blender Z-up after import.
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new(); bm.from_mesh(ob.data)
uvl = bm.loops.layers.uv.active
cl = bm.loops.layers.color.new("Col")
for f in bm.faces:
    c = Vector((0, 0))
    for l in f.loops: c += l[uvl].uv
    c /= len(f.loops)
    for l in f.loops:
        l[cl] = sample(l[uvl].uv.lerp(c, 0.3))
zs = [v.co.z for v in bm.verts]
z0, z1 = min(zs), max(zs)
base = bm.copy()
bm.free()
bpy.data.objects.remove(ob)

def stand_in(src):
    """The far version: a stack of cones on the model's outline, each tier coloured with
    the average of the model's faces in that band (sides) and a dark underside."""
    b = bmesh.new()
    col = b.loops.layers.color.new("Col")
    scl = src.loops.layers.color["Col"]
    TIERS, K = 5, 7
    crown0 = z0 + (z1 - z0) * 0.12  # below this is trunk
    def band(i):
        return crown0 + (z1 - crown0) * i / TIERS
    for i in range(TIERS):
        lo, hi = band(i), band(i + 1)
        r, acc, n = 0.0, Vector((0, 0, 0)), 0
        for f in src.faces:
            c = f.calc_center_median()
            if lo <= c.z < hi + (hi - lo) * 0.3:
                r = max(r, max(Vector((v.co.x, v.co.y)).length for v in f.verts))
                for l in f.loops: acc += Vector(l[scl][:3]); n += 1
        side = tuple(acc / max(n, 1)) + (1.0,)
        under = tuple(x * 0.45 for x in side[:3]) + (1.0,)
        top = b.verts.new((0, 0, hi + (hi - lo) * 0.9 if i < TIERS - 1 else z1))
        ring = [b.verts.new((r * math.cos(math.tau * k / K), r * math.sin(math.tau * k / K), lo)) for k in range(K)]
        mid = b.verts.new((0, 0, lo + (hi - lo) * 0.25))
        for k in range(K):
            a, c = ring[k], ring[(k + 1) % K]
            for f, cc in ((b.faces.new((a, c, top)), side), (b.faces.new((c, a, mid)), under)):
                for l in f.loops: l[col] = cc
    # The trunk: a three-sided post.
    tb = [b.verts.new((0.08 * (z1 - z0) / 6 * math.cos(math.tau * k / 3), 0.08 * (z1 - z0) / 6 * math.sin(math.tau * k / 3), z)) for z in (z0, crown0 + 0.05) for k in range(3)]
    for k in range(3):
        f = b.faces.new((tb[k], tb[(k + 1) % 3], tb[3 + (k + 1) % 3], tb[3 + k]))
        for l in f.loops: l[col] = (0.35, 0.2, 0.12, 1.0)
    bmesh.ops.recalc_face_normals(b, faces=b.faces)
    return b


# name: (height m, width factor). Heights as art/trees.py's spruces.
VARIANTS = {
    "mpine": (6.4, 1.0),
    "mpine_tall": (7.4, 0.85),
    "mpine_broad": (5.2, 1.15),
    "mpine_young": (3.4, 1.0),
}
built = []
for i, (name, (h, wide)) in enumerate(VARIANTS.items()):
    for suffix, ratio in (("", 1.0), ("_mid", 0.4), ("_far", 0.15), ("_lod", 0.0)):
        b = base.copy() if ratio > 0.0 else stand_in(base)
        f = h / (z1 - z0)
        for v in b.verts:
            v.co = Vector((v.co.x * f * wide, v.co.y * f * wide, (v.co.z - z0) * f - 0.4))
        me = bpy.data.meshes.new(name + suffix); b.to_mesh(me); b.free()
        o = bpy.data.objects.new(name + suffix, me); bpy.context.scene.collection.objects.link(o)
        if 0.0 < ratio < 1.0:
            m = o.modifiers.new("dec", "DECIMATE"); m.ratio = ratio
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.modifier_apply(modifier="dec")
        for p in me.polygons: p.use_smooth = False
        o.location = (i * 6.0, {"": 0, "_mid": 8, "_far": 16, "_lod": 24}[suffix], 0)
        built.append(o)

for o in bpy.data.objects: o.select_set(o in built)
bpy.ops.export_scene.gltf(filepath=os.path.normpath(out), export_format="GLB", use_selection=True,
                          export_normals=True, export_vertex_color="ACTIVE", export_materials="NONE", export_yup=True)
for o in built: print("BUILT", o.name, len(o.data.polygons))
