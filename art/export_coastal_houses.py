"""Run with Blender: blender -b art/hillside_town.blend -P art/export_coastal_houses.py.

Build metre-scale packed scenes in assets/models/coastal_houses. Each part GLB
uses the house origin so parts can be assembled or batched at identity.
"""
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ART = Path(bpy.data.filepath).parent
OUTPUT = ART.parent / "assets" / "models" / "coastal_houses"
PARTS = OUTPUT / "parts"
PARTS.mkdir(parents=True, exist_ok=True)
KIT_PATH = "res://assets/models/coastal_houses/parts"

# source collections in hillside_town.blend, ordered to match the art studies
SHELLS = {
    "cottage": "Shell | Cannery cottage",
    "craftsman": "Shell | Craftsman bungalow",
    "craftsman_lower": "Craftsman | Lower floor for full second story",
    "craftsman_upper": "Craftsman | Shingled second story and roof",
    "island_cabin": "Shell | Island cabin",
    "contemporary": "Contemporary | Common walls and entry",
}
ENTRIES = {
    "braced_stoop": "Cottage | Braced gable stoop",
    "rain_porch": "Cottage | Rain porch",
    "gable_porch": "Bungalow | Shingled gable porch",
    "veranda": "Bungalow | Full veranda",
    "lookout_deck": "Cabin | Long lookout deck",
    "mudroom": "Cabin | Mudroom",
    "view_terrace": "Contemporary | View terrace",
    "screened_entry": "Contemporary | Cedar entry screen",
}
ROOFS = {
    "single_shed": "Roof | Single shed",
    "butterfly": "Roof | Butterfly",
    "offset_gable": "Roof | Offset gable",
    "raised_clerestory": "Roof | Raised clerestory",
}

# For the elevated timber decks, bounds (left, right, seaward, inland) are in
# Blender metres, front -Y. Each scene exposes its level support as a separate node.
DECKS = {
    "lookout_deck": [(-3.54, 3.48, -4.44, -2.53)],
    "mudroom": [(-3.43, -1.18, -4.85, -3.95)],
    "view_terrace": [(-4.18, 4.32, -4.64, -3.14), (-1.46, 4.32, -3.14, -2.65)],
    "screened_entry": [(-4.22, -1.44, -4.76, -3.13)],
}
# x, front edge of deck, deck top
STAIRS = {
    "braced_stoop": (0, -5.27, .513), "rain_porch": (0, -5.27, .513),
    "gable_porch": (0, -5.59, .513), "veranda": (0, -5.59, .513),
    "lookout_deck": (-2.30, -4.44, .49), "mudroom": (-2.37, -4.85, .49),
    "view_terrace": (-3.04, -4.64, .49), "screened_entry": (-3.04, -4.76, .49),
}
MODERN_BASE = [(-1.52, 4.17, -2.62, 2.67), (-4.36, -1.49, -3.12, 1.98)]
CABIN_BASE = [(-3.65, 3.65, -2.5, 2.5)]


def paint_role(name):
    if any(tag in name for tag in ("Salt sage", "Oyster •", "Island fir /", "Shou sugi siding", "Weathered cedar siding")):
        return "Siding"
    if any(tag in name for tag in ("Graphite roof", "Coastal galvalume", "Zinc seam", "Ridge metal")):
        return "RoofFinish"
    return "Details"


def export_material(role):
    mat = bpy.data.materials.new(role)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    colors = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    colors.layer_name = "Col"
    mat.node_tree.links.new(colors.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = .82
    mat.use_backface_culling = False
    return mat


MATERIALS = {role: export_material(role) for role in ("Siding", "RoofFinish", "Details")}


MESH_NAMES = {}


class Part:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.face_roles = []
        self.face_colors = []

    def add_face(self, indices, role, color):
        self.faces.append(indices)
        self.face_roles.append(role)
        self.face_colors.append(color)

    def add_collection(self, collection, placement):
        for ob in collection.objects:
            transform = placement @ ob.matrix_local
            if ob.instance_type == "COLLECTION":
                child = ob.instance_collection
                self.add_collection(child, transform @ Matrix.Translation(-child.instance_offset))
            elif ob.type == "MESH":
                offset = len(self.vertices)
                self.vertices.extend(transform @ vertex.co for vertex in ob.data.vertices)
                for poly in ob.data.polygons:
                    material = ob.material_slots[poly.material_index].material
                    self.add_face(tuple(offset + i for i in poly.vertices),
                                  paint_role(material.name), tuple(material.diffuse_color))
        for child in collection.children:
            self.add_collection(child, placement)

    def box(self, center, size, material_name):
        color = tuple(bpy.data.materials[material_name].diffuse_color)
        start = len(self.vertices)
        half = Vector(size) / 2
        self.vertices.extend(Vector(center) + Vector((x * half.x, y * half.y, z * half.z))
                             for z in (-1, 1) for y in (-1, 1) for x in (-1, 1))
        for face in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
                     (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)]:
            self.add_face(tuple(start + i for i in face), "Details", color)

    def export(self, key):
        name = "".join(piece.capitalize() for piece in key.split("_"))
        objects = []
        for role in dict.fromkeys(self.face_roles):
            # Keep paintable surfaces independent. A house can change siding or
            # roof finish using one mesh override, including after ModelParts import.
            source_faces = [i for i, value in enumerate(self.face_roles) if value == role]
            vertices = {}
            faces = []
            for i in source_faces:
                faces.append(tuple(vertices.setdefault(v, len(vertices)) for v in self.faces[i]))
            node_name = "Kit" + name + role
            mesh = bpy.data.meshes.new(node_name)
            mesh.from_pydata([self.vertices[v] for v in vertices], [], faces)
            mesh.update()
            mesh.materials.append(MATERIALS[role])
            colors = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
            for poly, i in zip(mesh.polygons, source_faces):
                for loop in poly.loop_indices:
                    colors.data[loop].color = self.face_colors[i]
            mesh.color_attributes.active_color_name = colors.name
            obj = bpy.data.objects.new(node_name, mesh)
            bpy.context.scene.collection.objects.link(obj)
            objects.append(obj)
        MESH_NAMES[key] = [obj.name for obj in objects]
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        bpy.ops.export_scene.gltf(filepath=str(PARTS / (key + ".glb")), export_format="GLB",
                                  use_selection=True, export_vertex_color="MATERIAL", export_yup=True,
                                  export_animations=False, export_cameras=False, export_lights=False)
        for obj in objects:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)


def level_support(entry):
    part = Part()
    if entry in DECKS:
        foundation = MODERN_BASE if entry in ("view_terrace", "screened_entry") else CABIN_BASE
        if entry == "mudroom":
            foundation = foundation + [(-3.46, -.99, -3.97, -2.51)]
        for left, right, front, rear in foundation:
            part.box(((left + right) / 2, (front + rear) / 2, .15),
                     (right - left - .12, rear - front - .12, .64), "Formed concrete")
        if entry in ("mudroom", "lookout_deck"):
            part.box((3.79, .06, .15), (.49, 1.04, .64), "Formed concrete")
        for left, right, front, rear in DECKS[entry]:
            count = math.ceil((right - left) / 2.45)
            for y in (front + .14, rear - .14):
                part.box(((left + right) / 2, y, .22), (right - left - .09, .19, .20), "Oiled fir")
                for i in range(count + 1):
                    x = left + .17 + (right - left - .34) * i / count
                    part.box((x, y, .04), (.29, .30, .22), "Formed concrete")
    x, front, deck_top = STAIRS[entry]
    for i in range(1, 4):
        h = deck_top * (1 - i / 4)
        y = front - (i - .5) * .30
        part.box((x, y, h / 2), (1.58, .30, h), "Pier concrete")
        part.box((x, y, h - .01), (1.65, .32, .045), "Fir end grain")
    return part


def assembled_scene(name, components, lamp, entrance):
    lines = ['[gd_scene format=3]', '']
    lines.append('[ext_resource type="Material" path="res://assets/models/coastal_houses/house_colors.tres" id="Colors"]')
    for title, key in components:
        lines.append(f'[ext_resource type="PackedScene" path="{KIT_PATH}/{key}.glb" id="{title}"]')
    lines += ['', f'[node name="{name}" type="Node3D"]']
    for title, key in components:
        lines += ['', f'[node name="{title}" parent="." instance=ExtResource("{title}")]']
    for title, key in components:
        for mesh_name in MESH_NAMES[key]:
            lines += ['', f'[node name="{mesh_name}" parent="{title}"]',
                      'material_override = ExtResource("Colors")']
    for title, coordinates in (("PorchLight", lamp), ("Entry", entrance)):
        x, y, z = coordinates
        lines += ['', f'[node name="{title}" type="Marker3D" parent="."]',
                  f'position = Vector3({x:.4f}, {z:.4f}, {-y:.4f})']
    (OUTPUT / (name + ".tscn")).write_text("\n".join(lines) + "\n")


def build():
    for key, source in (SHELLS | ENTRIES | ROOFS).items():
        part = Part()
        part.add_collection(bpy.data.collections[source], Matrix.Identity(4))
        part.export(key)
    # Both legacy porch shapes for a family use identical ground-level steps.
    site_keys = {}
    for entry in ENTRIES:
        canonical = {"rain_porch": "braced_stoop", "veranda": "gable_porch"}.get(entry, entry)
        site_keys[entry] = canonical + "_site"
        if entry == canonical:
            level_support(entry).export(site_keys[entry])
    for family, entries, body in [
        ("cottage", ("braced_stoop", "rain_porch"), [("Shell", "cottage")]),
        ("craftsman", ("gable_porch", "veranda"), [("Shell", "craftsman")]),
        ("craftsman_two_story", ("gable_porch", "veranda"),
         [("Shell", "craftsman_lower"), ("UpperStory", "craftsman_upper")]),
        ("cabin", ("lookout_deck", "mudroom"), [("Shell", "island_cabin")]),
        ("contemporary", ("view_terrace", "screened_entry"), [("Shell", "contemporary")]),
    ]:
        for entry in entries:
            # Fixture centers in Blender coordinates: +Z up and front toward -Y.
            if family == "cottage":
                lamp = (.8, -3.735, 2.17)
            elif family.startswith("craftsman"):
                lamp = (.8, -3.535, 2.17)
            elif family == "cabin":
                lamp = (-1.64, -4.12, 2.42) if entry == "mudroom" else (-1.55, -2.65, 2.42)
            else:
                lamp = (-2.31, -3.26, 2.42)
            x, front, top = STAIRS[entry]
            for roof in ROOFS if family == "contemporary" else (None,):
                components = list(body)
                if roof:
                    components.append(("Roof", roof))
                components.extend([("Porch", entry), ("LevelSite", site_keys[entry])])
                name = "_".join(filter(None, [family, roof, entry]))
                assembled_scene(name, components, lamp, (x, front, top))


build()
