# Game-weight copies of the slip's guide structures: the full models decimated to
# about 30% of their triangles, written beside them as *_lod.glb.
#
#   blender -b --factory-startup -P art/export_slip_guide_lods.py
#
# Each mesh gets a planar dissolve (2°) then a collapse to RATIO. Meshes with shape
# keys (the dolphins' fenders and their Compression key) are decimated in their rest
# shape, then each key is rebuilt on the new vertices from the original's offsets at
# the nearest point of its rest surface, and the fender animation is kept.
import os
import math
import bpy
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

RATIO = 0.3
_here = os.path.dirname(os.path.abspath(__file__))
_models = os.path.normpath(os.path.join(_here, "..", "assets", "models"))
SOURCES = ["ferry_dolphin", "ferry_dolphin_small", "wing_wall"]


def decimate(o):
    for name, kind in (("dissolve", "DISSOLVE"), ("collapse", "COLLAPSE")):
        m = o.modifiers.new(name, "DECIMATE")
        m.decimate_type = kind
        if kind == "DISSOLVE":
            m.angle_limit = math.radians(2.0)
        else:
            m.ratio = RATIO
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def decimate_keyed(o):
    me = o.data
    keys = me.shape_keys
    action = keys.animation_data.action if keys.animation_data else None
    slot = getattr(keys.animation_data, "action_slot", None) if action else None
    basis = [v.co.copy() for v in keys.key_blocks[0].data]
    offsets = {k.name: [k.data[i].co - basis[i] for i in range(len(basis))]
               for k in keys.key_blocks[1:]}
    polys = [list(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(basis, polys)
    bpy.context.view_layer.objects.active = o
    o.shape_key_clear()
    decimate(o)
    o.shape_key_add(name="Basis")
    for name, off in offsets.items():
        kb = o.shape_key_add(name=name)
        for v, d in zip(o.data.vertices, kb.data):
            hit, _n, face, _dist = bvh.find_nearest(v.co)
            ids = polys[face]
            w = poly_3d_calc([basis[i] for i in ids], hit)
            d.co = v.co + sum((off[i] * wi for i, wi in zip(ids, w)), v.co * 0)
    if action:
        ad = o.data.shape_keys.animation_data_create()
        ad.action = action
        if slot is not None:
            ad.action_slot = slot


for src in SOURCES:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(_models, src + ".glb"))
    before = after = 0
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        o.data.calc_loop_triangles()
        before += len(o.data.loop_triangles)
        if o.data.has_custom_normals:
            bpy.context.view_layer.objects.active = o
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
        if o.data.shape_keys:
            decimate_keyed(o)
        else:
            decimate(o)
        o.data.calc_loop_triangles()
        after += len(o.data.loop_triangles)
    out = os.path.join(_models, src + "_lod.glb")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_yup=True,
                              export_apply=False, export_animations=True,
                              export_morph=True, export_morph_normal=False)
    print("lod:", src, before, "->", after)
