# Exports the slip wing wall in art/wing_wall.blend to assets/models/wing_wall.glb.
#
#   blender -b art/wing_wall.blend -P art/export_wing_wall.py
#
# Frame (Godot, after the glTF +Y-up conversion): metres, water at y = 0, the wall
# runs along x centred on the origin, its rubber facing on z = 0 looking +z (towards
# the slip) and its piles behind at -z. WorldBuilder lays one either side of each slip
# and bakes the surface colours into the terminal mesh.
import os
import bpy

_here = os.path.dirname(os.path.abspath(__file__))
_glb = os.path.normpath(os.path.join(_here, "..", "assets", "models", "wing_wall.glb"))

# The game paints each material one flat colour: cut the procedural grime feeding the
# base colour and export the Principled BSDF's own Base Color, which holds the
# material's flat coat (the export runs on a throwaway copy; the .blend isn't saved).
for mat in bpy.data.materials:
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
    if bsdf:
        for link in list(bsdf.inputs["Base Color"].links):
            mat.node_tree.links.remove(link)

# Bevels add far more triangles than they show at the game's distances.
for o in bpy.data.objects:
    for m in o.modifiers:
        if m.type == "BEVEL":
            m.show_viewport = m.show_render = False

bpy.ops.object.select_all(action="DESELECT")
for o in bpy.data.objects:
    if o.type in {"MESH", "EMPTY"} and not o.hide_render and o.visible_get():
        o.select_set(True)

bpy.ops.export_scene.gltf(
    filepath=_glb,
    export_format="GLB",
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_cameras=False,
    export_lights=False,
    export_animations=True,
    export_morph=True,
    export_morph_normal=False,
    export_materials="EXPORT",
)
print("wing_wall:", _glb)
