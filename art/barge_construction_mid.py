"""Build the slip crew's crane scow. Run with blender -b -P art/barge_construction_mid.py."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pusher_mid import (
    CREAM, IRON, ROOT, RUBBER, STEEL, Part, annulus, barge, blender_point,
    block, pipe, rail, rect, round_ring,
)

GOLD, LIGHT_GOLD = "e3a535", "f3be52"
GREEN, PALE_GREEN = "365950", "608077"
GLAZING, TRIM, ROPE = "345460", "e3dfc6", "434b49"
RUST, SAFETY = "9c513a", "c95738"
PIVOT = (5, 0, 2.12)


def deck_equipment():
    deck = Part("Work deck and stores")
    # Load-spreading grillage and fixed pedestal under the swing bearing.
    for y in (-1.66, 0, 1.66):
        block(deck, 5, y, 1.06, 5.4, 0.45, 0.27, IRON)
    block(deck, 5, 0, 1.33, 5.1, 4.52, 0.18, STEEL, 0.22)
    pipe(deck, (5, 0, 1.51), PIVOT, 1.88, GREEN, 24, 1.57)
    annulus(deck, (5, 0, 2.04), (0, 0, 1), 1.69, 1.49, 0.14, RUBBER, count=24)

    # Open-ended pipe piles nested in a crib, with timber dunnage and red binders.
    for x in (-7.4, -1.6):
        block(deck, x, -0.84, 1.06, 0.41, 3.04, 0.26, "8d724e")
        for y in (-2.24, 0.56):
            block(deck, x, y, 1.32, 0.21, 0.15, 1.12, GOLD)
    for i, (y, z) in enumerate([(-1.67, 1.73), (-0.84, 1.73), (-0.01, 1.73),
                                (-1.255, 2.44), (-0.425, 2.44)]):
        annulus(deck, (-4.55, y, z), (1, 0, 0), 0.41, 0.353, 8.7 - i % 2 * 0.25,
                ["685443", "7e6550", "756051"][i % 3], "ba9774", 14)
    for x in (-7.4, -1.6):
        strap = [(x, y, z) for y, z in [(-2.25, 1.38), (-2.09, 1.87), (-1.59, 2.69),
                                        (-1.31, 2.87), (-0.38, 2.87), (-0.10, 2.70),
                                        (0.40, 1.85), (0.55, 1.38)]]
        for a, b in zip(strap, strap[1:]):
            pipe(deck, a, b, 0.052, SAFETY, 6)

    # A shore-power cabinet and a cable reel occupy the opposite side of the aisle.
    block(deck, -5.9, 1.91, 1.06, 2.85, 1.23, 0.18, IRON)
    block(deck, -5.9, 1.91, 1.24, 2.58, 1.10, 1.07, PALE_GREEN, 0.10)
    block(deck, -5.9, 1.91, 2.31, 2.70, 1.20, 0.09, TRIM, 0.10)
    for x in (-6.48, -5.32):
        block(deck, x, 2.468, 1.39, 0.98, 0.035, 0.76, GREEN, 0.03)
        block(deck, x + 0.30, 2.50, 1.60, 0.06, 0.07, 0.28, TRIM)
    for y in (1.24, 2.55):
        block(deck, -2.75, y, 1.06, 1.45, 0.16, 0.92, GREEN, 0.06)
        pipe(deck, (-2.75, y-0.055, 1.98), (-2.75, y+0.055, 1.98), 0.73, GOLD, 16)
    pipe(deck, (-2.75, 1.30, 1.98), (-2.75, 2.49, 1.98), 0.54, ROPE, 16)
    for i in range(9):
        annulus(deck, (-2.75, 1.38+i*0.13, 1.98), (0, 1, 0), 0.57, 0.53, 0.07, IRON, count=16)

    # Raised stern spuds with guide collars. Keep the push face and bitts clear.
    for y in (-1.63, 1.63):
        x = -10.73
        block(deck, x, y, 1.06, 1.02, 1.10, 0.19, IRON, 0.12)
        pipe(deck, (x, y, -1.28), (x, y, 5.36), 0.27, "6f6153", 12)
        for z in (1.36, 2.40):
            annulus(deck, (x, y, z), (0, 0, 1), 0.45, 0.28, 0.22, GOLD, count=12)
        for dx in (-0.36, 0.36):
            block(deck, x+dx, y, 1.25, 0.13, 0.40, 1.10, GREEN)
        for z in (4.72, 5.04):
            pipe(deck, (x, y, z), (x, y, z+0.12), 0.276, CREAM, 12)
    return deck


def machinery():
    # Coordinates local to the centre of the slew bearing.
    body = Part("CraneSlew")
    block(body, -0.45, 0, 0, 5.56, 4.05, 0.40, GREEN, 0.34)
    block(body, -0.45, 0, 0.40, 5.49, 4.01, 0.13, LIGHT_GOLD, 0.30)
    # Stacked cast counterweight wraps around the back of the engine house.
    for i in range(3):
        block(body, -2.48, 0, 0.54+i*0.37, 1.72, 3.85-i*0.07, 0.33,
              (GREEN, PALE_GREEN, GREEN)[i], 0.34)
    body.loft([rect(-1.17, 0.14, 0.53, 2.7, 3.0, 0.24),
               rect(-1.17, 0.14, 1.91, 2.7, 3.0, 0.24),
               rect(-1.15, 0.14, 2.16, 2.45, 2.80, 0.24)], GOLD)
    for side in (-1, 1):
        for i in range(8):
            block(body, -2.08+i*0.20, 0.14+side*1.51, 0.88, 0.105, 0.055, 0.81, GREEN)
    pipe(body, (-1.89, 0.82, 2.16), (-1.89, 0.82, 2.67), 0.13, IRON)
    pipe(body, (-1.89, 0.82, 2.67), (-1.89, 0.82, 2.72), 0.18, RUBBER)

    # Glazed cab with a raked windshield and a cream sun visor.
    cab = [rect(1.03, -1.33, 0.53, 1.96, 1.23, 0.11),
           rect(1.03, -1.33, 1.21, 1.96, 1.23, 0.11),
           rect(1.18, -1.33, 2.35, 2.16, 1.23, 0.11)]
    body.loft(cab, lambda row, i: GOLD if row == 0 else GLAZING, top=TRIM)
    for a, b in zip(cab[1], cab[2]):
        pipe(body, a, b, 0.052, TRIM, 5)
    for y in (-1.945, -0.715):
        pipe(body, (0.96, y, 1.21), (1.01, y, 2.35), 0.052, TRIM, 5)
    block(body, 1.19, -1.33, 2.35, 2.36, 1.40, 0.13, TRIM, 0.14)
    rail(body, [(-2.68, 1.83, 0.55), (-1.26, 1.88, 0.55), (0.18, 1.88, 0.55)], 0.84, TRIM)

    # Gantry carries the paired pendants to the boom head.
    for side in (-1, 1):
        y = side * 0.63
        pipe(body, (-2.52, y, 1.67), (-0.95, y, 4.39), 0.105, GOLD)
        pipe(body, (0.48, y, 0.54), (-0.95, y, 4.39), 0.125, LIGHT_GOLD)
    pipe(body, (-0.95, -0.76, 4.39), (-0.95, 0.76, 4.39), 0.17, IRON, 12)
    pipe(body, (0.15, -0.58, 1.33), (0.15, 0.59, 1.33), 0.45, ROPE, 14)
    for y in (-0.54, 0.54):
        block(body, 1.42, y, 0.53, 0.86, 0.20, 0.85, GOLD, 0.09)
    return body


def lattice_and_tackle():
    rig = Part("Boom and running gear")
    heel = Vector((1.42, 0, 1.25))
    head = Vector((12.30, 0, 14.30))
    along = (head-heel).normalized()
    across = Vector((0, 1, 0))
    normal = along.cross(across)
    # Square lattice widens above the heel, then tapers back to the sheave axle.
    rings = []
    for t, width, depth in [(0, 0.56, 0.10), (0.12, 0.70, 0.64), (0.26, 0.68, 0.61),
                            (0.40, 0.64, 0.59), (0.54, 0.60, 0.55), (0.68, 0.55, 0.50),
                            (0.82, 0.47, 0.43), (0.93, 0.36, 0.34), (1, 0.31, 0.10)]:
        center = heel.lerp(head, t)
        rings.append([center + across*width*a + normal*depth*b
                      for a, b in [(-1,-1), (1,-1), (1,1), (-1,1)]])
    for bay, (a, b) in enumerate(zip(rings, rings[1:])):
        paint = GOLD if bay < 6 else (TRIM if bay == 6 else SAFETY)
        for i in range(4):
            j = (i+1) % 4
            pipe(rig, a[i], b[i], 0.098, paint, 8)
            pipe(rig, b[i], b[j], 0.067, paint, 6)
            start, end = (a[i], b[j]) if bay % 2 else (a[j], b[i])
            pipe(rig, start, end, 0.062, paint, 6)
    for y in (-0.24, 0.24):
        pipe(rig, head+across*(y-0.07), head+across*(y+0.07), 0.34, IRON, 16)
        pipe(rig, (-0.95, math.copysign(0.63, y), 4.43), head+across*y+normal*0.10,
             0.055, ROPE, 6)
    # The running line leads up the boom and down to a striped traveling block.
    pipe(rig, (0.15, 0, 1.75), head+normal*0.26, 0.042, ROPE, 6)
    hook_x = head.x+0.24
    for y in (-0.24, 0.24):
        pipe(rig, (hook_x, y, head.z), (hook_x, y, 5.65), 0.043, ROPE, 6)
    for z, length, width, height, color in [(5.24, 0.82, 0.68, 0.23, GOLD),
            (5.47, 0.88, 0.72, 0.17, IRON), (5.64, 0.84, 0.69, 0.23, GOLD)]:
        block(rig, hook_x, 0, z, length, width, height, color, 0.11)
    pipe(rig, (hook_x, 0, 5.03), (hook_x, 0, 5.24), 0.13, STEEL)
    curve = [(0,5.12,0.13),(-0.04,4.93,0.14),(-0.18,4.74,0.15),(-0.15,4.52,0.15),
             (0.02,4.40,0.14),(0.25,4.45,0.10),(0.38,4.64,0.065),(0.40,4.78,0.025)]
    sections = []
    for i, (x, z, radius) in enumerate(curve):
        prev = curve[max(0,i-1)]
        nxt = curve[min(len(curve)-1,i+1)]
        sections.append(round_ring((hook_x+x, 0, z), (nxt[0]-prev[0], 0, nxt[1]-prev[1]), radius, 8))
    rig.loft(sections, STEEL)
    return rig


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    material = bpy.data.materials.new("Fleet vertex paint")
    material.use_nodes = True
    colors = material.node_tree.nodes.new("ShaderNodeVertexColor")
    colors.layer_name = "Col"
    shader = material.node_tree.nodes.get("Principled BSDF")
    material.node_tree.links.new(colors.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.82
    collection = bpy.data.collections.new("Construction barge")
    scene.collection.children.link(collection)
    hull, stores = [part.finish(collection, material) for part in barge(deck_equipment(), False)]
    stores.parent = hull
    upper = machinery().finish(collection, material)
    upper.parent = hull
    upper.location = blender_point(PIVOT)
    upper.rotation_euler.z = math.radians(28)
    boom = lattice_and_tackle().finish(collection, material)
    boom.parent = upper
    bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets/models/barge_construction_mid.glb"),
                              export_format="GLB", export_vertex_color="ACTIVE")

    # A waterline studio view for checking silhouette and deck load at a glance.
    target = Vector((0.7, -1.8, 6.25))
    bpy.ops.object.camera_add(location=target+Vector((-32, -15, 17)))
    camera = bpy.context.object
    camera.rotation_euler = (target-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 39
    scene.camera = camera
    studio = bpy.data.collections.new("Preview studio")
    scene.collection.children.link(studio)

    def to_studio(obj):
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        studio.objects.link(obj)
        obj.hide_set(True)

    to_studio(camera)
    bpy.ops.mesh.primitive_plane_add(size=500, location=(0, 0, 0))
    water = bpy.context.object
    water.name = "Waterline"
    water_mat = bpy.data.materials.new("Harbour water")
    water_mat.use_nodes = True
    water_shader = water_mat.node_tree.nodes.get("Principled BSDF")
    water_shader.inputs["Base Color"].default_value = (0.034, 0.102, 0.116, 1)
    water_shader.inputs["Roughness"].default_value = 0.27
    coords = water_mat.node_tree.nodes.new("ShaderNodeTexCoord")
    waves = water_mat.node_tree.nodes.new("ShaderNodeTexNoise")
    waves.inputs["Scale"].default_value = 1.9
    waves.inputs["Detail"].default_value = 1.6
    bump = water_mat.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.28
    bump.inputs["Distance"].default_value = 0.10
    links = water_mat.node_tree.links
    links.new(coords.outputs["Object"], waves.inputs["Vector"])
    links.new(waves.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], water_shader.inputs["Normal"])
    water.data.materials.append(water_mat)
    to_studio(water)
    scene.world = bpy.data.worlds.new("Overcast sky")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.73, 0.81, 0.9, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.65
    bpy.ops.object.light_add(type="AREA", location=(-15, -14, 29))
    sun = bpy.context.object
    sun.rotation_euler = (-sun.location).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = 15000
    sun.data.shape = "DISK"
    sun.data.size = 12
    to_studio(sun)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 980
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = "//barge_construction_preview.png"
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            view = area.spaces.active
            view.shading.color_type = "VERTEX"
            view.overlay.show_overlays = False
            view.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            view.region_3d.view_location = target
            view.region_3d.view_distance = 39
            view.region_3d.view_perspective = "ORTHO"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art/barge_construction.blend"), compress=True)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
