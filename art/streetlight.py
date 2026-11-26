"""Build the Tideways roadside luminaire in Blender (dimensions in metres)."""
import bpy
from math import cos, sin, pi
from pathlib import Path
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
verts, faces, slots = [], [], []


def ring(points):
    start = len(verts)
    verts.extend(points)
    return list(range(start, len(verts)))


def face(indices, material):
    faces.append(indices)
    slots.append(material)


def connect(a, b, material):
    for i in range(len(a)):
        j = (i + 1) % len(a)
        face([a[i], a[j], b[j], b[i]], material)


# Cross-sections turn with the mast so its swept elbow keeps its thickness.
previous = None
for x, z, radius, tilt, material in [
    (0, 0, .145, 0, 0), (0, .40, .100, 0, 0),
    (0, 4.75, .072, .12, 1),
    (.27, 5.18, .068, 1.17, 1),
    (1.23, 5.35, .055, 1.52, 1),
]:
    section = ring([(x + radius*cos(a)*cos(tilt), radius*sin(a),
                     z - radius*cos(a)*sin(tilt))
                    for a in (pi/4 + pi*i/2 for i in range(4))])
    if previous:
        connect(previous, section, material)
    else:
        face(section[::-1], 0)
    previous = section

# The shallow ridge gives the diffuser a visible edge from street level.
outline = [(-.46,-.095), (.43,-.18), (.43,.18), (-.46,.095)]
rim = ring([(1.55+x, y, 5.25) for x,y in outline])
lid = ring([(1.55+x*.85, y*.85, 5.38) for x,y in outline])
connect(rim, lid, 0)
face(lid, 0)
heel, nose = ring([(1.22, 0, 5.20), (1.86, 0, 5.19)])
face([rim[1], rim[0], heel, nose], 2)
face([rim[2], rim[1], nose], 2)
face([rim[3], rim[2], nose, heel], 2)
face([rim[0], rim[3], heel], 2)
mesh = bpy.data.meshes.new("Streetlight")
mesh.from_pydata(verts, [], faces)
mesh.update()
mesh.calc_loop_triangles()
assert len(mesh.loop_triangles) <= 50
prop = bpy.data.objects.new("Streetlight", mesh)
bpy.context.collection.objects.link(prop)
for name, color, metal in [
    ("Deep petrol enamel", (.056,.099,.105), .38),
    ("Weathered galvanized steel", (.32,.39,.40), .55),
    ("Warm prismatic diffuser", (1,.74,.39), 0),
]:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color,1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color,1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = .53
    if not metal:
        shader.inputs["Emission Color"].default_value = (*color,1)
        shader.inputs["Emission Strength"].default_value = .7
    mesh.materials.append(mat)
for poly, slot in zip(mesh.polygons, slots):
    poly.material_index = slot
prop.select_set(True)
bpy.context.view_layer.objects.active = prop
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        region = area.spaces.active.region_3d
        region.view_location = (.6,0,2.7)
        region.view_distance = 9
        region.view_rotation = Vector((-.36,1,-.13)).to_track_quat('-Z','Y')
        area.spaces.active.shading.color_type = 'MATERIAL'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(root/"art/streetlight.blend"))
bpy.ops.export_scene.gltf(filepath=str(root/"assets/models/streetlight.glb"),
                          use_selection=True, export_format="GLB")
