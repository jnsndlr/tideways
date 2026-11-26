"""Generate the metre-scale garden parts and three Godot assemblies with Blender -b -P."""
from math import atan2, cos, sin, tau
from pathlib import Path
from random import Random

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "assets/models/home_gardens"
PARTS = KIT / "parts"
PARTS.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
rng = Random(43)
material = bpy.data.materials.new("Garden palette")
material.use_nodes = True
colors = material.node_tree.nodes.new("ShaderNodeVertexColor")
colors.layer_name = "Paint"
shader = material.node_tree.nodes.get("Principled BSDF")
material.node_tree.links.new(colors.outputs["Color"], shader.inputs["Base Color"])
shader.inputs["Roughness"].default_value = 1
pieces = []


def paint(obj, color):
    rgb = bytes.fromhex(color)
    layer = obj.data.color_attributes.new(name="Paint", type="BYTE_COLOR", domain="CORNER")
    for poly in obj.data.polygons:
        shade = rng.uniform(.95, 1.04)
        tint = [min(1, c / 255 * shade) for c in rgb] + [1]
        for i in poly.loop_indices:
            layer.data[i].color_srgb = tint
    obj.data.materials.append(material)
    pieces.append(obj)
    return obj


def block(at, size, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=at)
    obj = bpy.context.object
    obj.scale = size
    return paint(obj, color)


def stone(at, size, color):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=at)
    obj = bpy.context.object
    obj.scale = size
    obj.rotation_euler.z = rng.random() * tau
    return paint(obj, color)


def shape(name, verts, faces, color):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return paint(obj, color)


def stem(start, end, base, tip, color, sides=3):
    axis = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=base, radius2=tip,
                                    end_fill_type="NOTHING", depth=axis.length,
                                    location=Vector(start) + axis / 2)
    obj = bpy.context.object
    obj.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
    return paint(obj, color)


def leaf(x, y, angle, length, width, height, color):
    # Two planes meet along the midrib. The side edges droop away from it.
    coords = [(0, 0, 0), (.51, -1, .34), (1, 0, 1), (.51, 1, .34)]
    verts = [(x + u*length*cos(angle) - v*width*sin(angle),
              y + u*length*sin(angle) + v*width*cos(angle), h*height) for u,v,h in coords]
    return shape("Leaf", verts, [(0,1,2),(0,2,3)], color)


def octahedron(at, size, color):
    verts = [(1,0,0),(0,1,0),(-1,0,0),(0,-1,0),(.1,0,1),(0,0,-1)]
    faces = [(i,(i+1)%4,4) for i in range(4)] + [((i+1)%4,i,5) for i in range(4)]
    obj = shape("Bud", verts, faces, color)
    obj.location, obj.scale = at, size
    obj.rotation_euler.z = rng.random()*tau
    return obj


def finish(name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in pieces:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = name
    obj.data.name = name
    bpy.ops.export_scene.gltf(filepath=str(PARTS / (name + ".glb")), use_selection=True,
                              export_yup=True)
    pieces.clear()


soil = "594439"
# Only the visible surfaces of the frame and soil are needed at ground level.
def rect(x, y, z):
    return [(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]


shape("Soil", rect(1.18,.59,.20), [(0,1,2,3)], soil)
outer = rect(1.3,.71,.27)
inner = rect(1.18,.59,.27)
for i in range(4):
    j = (i+1)%4
    a,b,c,d = outer[i],outer[j],inner[j],inner[i]
    verts = [a,b,c,d, (*a[:2],0),(*b[:2],0),(*c[:2],.20),(*d[:2],.20)]
    shape("Board", verts, [(0,1,2,3),(4,5,1,0),(7,6,2,3)], ["987451","AB835C"][i%2])
for x in [-1.23,1.23]:
    for y in [-.64,.64]:
        verts = rect(.075,.075,.27) + rect(.075,.075,.31)
        faces = [(4,5,6,7)] + [(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)]
        shape("Peg", verts, faces, "765A43").location = (x,y,0)
finish("cedar_bed")

# A low oval soil mound and individually turned fieldstones.
bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=1, depth=.2, location=(0, 0, .1))
obj = bpy.context.object
obj.scale = (1.42, .86, 1)
paint(obj, soil)
for i in range(16):
    a = i * tau / 16
    # Five ground corners and a tilted triangular crown give each stone a broad top.
    verts = [(-.78,-.65,-1),(.55,-1,-1),(1,.18,-1),(.20,.95,-1),(-1,.61,-1),
             (-.60,-.36,.51),(.54,-.44,.75),(.08,.59,.98)]
    faces = [(0,1,6,5),(1,2,6),(2,3,7,6),(3,4,5,7),(4,0,5),(5,6,7)]
    obj = shape("Fieldstone", verts, faces, rng.choice(["858984","AAA394","918C82"]))
    obj.location = (1.42*cos(a), .86*sin(a), .12)
    obj.scale = (.24,.14,rng.uniform(.12,.17))
    obj.rotation_euler.z = atan2(.86*cos(a), -1.42*sin(a))
finish("fieldstone_bed")

for x in [-.74, 0, .74]:
    for y in [-.27, .27]:
        octahedron((x,y,.13), (.23,.23,.20), "92AC69")
        for i in range(5):
            leaf(x,y,i*tau/5+.23,.31,.13,.18, rng.choice(["527D62","73986A"]))
finish("cabbages")

for x in [-.77, -.05, .70]:
    for y in [-.25,.26]:
        for i in range(5):
            leaf(x,y,i*tau/5+rng.uniform(0,.4),rng.uniform(.19,.33),.09,
                 rng.uniform(.30,.53),rng.choice(["638044","899648","496E4F"]))
        stem((x,y,0),(x+.025,y,.30),.033,.015,"BF5449")
finish("chard")

for i in range(7):
    x, y = (i//2-1.5)*.48, (-1)**i*.22
    h = rng.uniform(.49,.78)
    stem((x,y,0),(x,y,h),.018,.012,"54724F")
    for j in range(4):
        leaf(x,y,j*tau/4+i,.21,.064,.22,"64876B")
    tint = ["A48AC1","7C71AD","D79FAE"][i%3]
    for j in range(3):
        z = h-.13+j*.085
        stem((x,y,z),(x,y,z+.13),.105-j*.024,0 if j == 2 else .045-j*.018,tint,4)
finish("lupines")

stem((0,0,0),(.08,0,1.29),.13,.085,"71543C",6)
for x,y,h,r in [(-.49,.08,1.56,.71),(.47,.18,1.75,.69),(.10,-.40,1.73,.64),(.02,.08,2.12,.65)]:
    stem((.04,0,.82),(x,y,h),.075,.035,"816147")
    stone((x,y,h),(r,r*.90,r*.83),rng.choice(["658348","799348","587744"]))
    for j in range(4):
        a=j*tau/4+.45
        octahedron((x+.84*r*cos(a),y+.79*r*sin(a),h-.13),(.086,.086,.092),"C65B3E")
finish("apple_tree")

for x,y,h in [(-.32,.03,2.15),(.33,.12,2.55),(.06,-.16,2.91)]:
    stem((x*.13,y*.13,0),(x,y,h),.077,.029,"D3CDB4")
    for j in range(2):
        sign=(-1)**j
        end=(x+.23*sign,y+.11,h-.47+j*.43)
        stem((x*.65,y*.65,h*.51),end,.046,.015,"BCB69C")
        stone(end,(.47,.43,.65),["96AD66","A7B86C"][j])
finish("birch_clump")

gardens = {
    "kitchen_garden": [("cedar_bed","cabbages",0,-1),("cedar_bed","chard",0,1)],
    "cottage_border": [("fieldstone_bed","lupines",0,0)],
    "orchard_plot": [("fieldstone_bed","chard",0,1)],
}
trees = {"cottage_border": ("birch_clump",2.1,.65), "orchard_plot": ("apple_tree",.7,-1.45)}
for name, beds in gardens.items():
    layout = []
    for bed, plants, x, z in beds:
        layout.extend([(bed,x,0,z),(plants,x,.2,z)])
    if name in trees:
        tree,x,z = trees[name]
        layout.append((tree,x,0,z))
    lines = ["[gd_scene format=3]", ""]
    for part in dict.fromkeys(row[0] for row in layout):
        lines.append(f'[ext_resource type="PackedScene" path="res://assets/models/home_gardens/parts/{part}.glb" id="{part}"]')
    lines.extend(["", f'[node name="{name}" type="Node3D"]'])
    for i,(part,x,y,z) in enumerate(layout):
        lines.extend(["", f'[node name="{part}_{i+1}" parent="." instance=ExtResource("{part}")]',
                      f'position = Vector3({x}, {y}, {z})'])
    (KIT / (name + ".tscn")).write_text("\n".join(lines)+"\n")

# Fence scenes span 2.4 m between post centers. EndPost can be hidden at a join.
SPAN = 2.4
FENCES = KIT / "fences"
FENCES.mkdir(exist_ok=True)


def board(x, width, depth, bottom, shoulder, peak, color):
    outline = [(x-width/2,bottom),(x+width/2,bottom),(x+width/2,shoulder),
               (x,peak),(x-width/2,shoulder)]
    verts = [(px,y,z) for y in (-depth/2,depth/2) for px,z in outline]
    faces = [(0,1,2,3,4),(9,8,7,6,5)] + [
        (i,i+5,(i+1)%5+5,(i+1)%5) for i in range(1,5)]
    return shape("Paling", verts, faces, color)


def fence_scene(style):
    (FENCES / (style+".tscn")).write_text(f'''[gd_scene format=3]

[ext_resource type="PackedScene" path="res://assets/models/home_gardens/parts/{style}_post.glb" id="Post"]
[ext_resource type="PackedScene" path="res://assets/models/home_gardens/parts/{style}_span.glb" id="Span"]

[node name="{style}" type="Node3D"]

[node name="StartPost" parent="." instance=ExtResource("Post")]

[node name="Panel" parent="." instance=ExtResource("Span")]

[node name="EndPost" parent="." instance=ExtResource("Post")]
position = Vector3({SPAN}, 0, 0)
''')


board(0,.115,.115,0,.89,.96,"E7E2D1")
finish("white_picket_post")
for z in (.24,.59):
    block((SPAN/2,.046,z),(SPAN-.115,.058,.075),"D5D2BF")
for i in range(11):
    board((i+.5)*SPAN/11,.112,.045,.065,.735,.825,"F3EFDE")
finish("white_picket_span")
fence_scene("white_picket")

block((0,0,.79),(.14,.14,1.58),"865D43")
block((0,0,1.59),(.17,.17,.045),"AD8059")
finish("cedar_post")
for z in (.30,1.19):
    block((SPAN/2,.051,z),(SPAN-.14,.068,.105),"856046")
for i in range(12):
    width = (SPAN-.14)/12
    x = .07+(i+.5)*width
    block((x,0,.77),(width-.008,.046,1.42),rng.choice(["9D704E","AC7951","A57450","BA8861"]))
block((SPAN/2,0,1.5),(SPAN-.14,.095,.055),"C69669")
finish("cedar_span")
fence_scene("cedar")

# A seamless cutout tile gives the galvanized wire real openings on one quad.
def chain_fabric():
    n = 64
    tile = bpy.data.images.new("Galvanized diamonds", width=n, height=n, alpha=True)
    pixels = []
    for y in range(n):
        for x in range(n):
            u,v = (x+.5)/n,(y+.5)/n
            distance = min(abs((u+v)%1-.5),abs((u-v)%1-.5))
            pixels.extend((.47,.53,.53, max(0,min(1,(.050-distance)*n))))
    tile.pixels[:] = pixels
    tile.pack()
    mat = bpy.data.materials.new("Galvanized wire")
    mat.use_nodes = True
    mat.use_backface_culling = False
    nodes = mat.node_tree.nodes
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = tile
    clip = nodes.new("ShaderNodeMath")
    clip.operation = "GREATER_THAN"
    clip.inputs[1].default_value = .5
    bsdf = nodes.get("Principled BSDF")
    links = mat.node_tree.links
    links.new(tex.outputs["Color"],bsdf.inputs["Base Color"])
    links.new(tex.outputs["Alpha"],clip.inputs[0])
    links.new(clip.outputs[0],bsdf.inputs["Alpha"])
    verts = [(.032,0,.055),(SPAN-.032,0,.055),(SPAN-.032,0,1.14),(.032,0,1.14)]
    obj = shape("Fabric",verts,[(0,1,2,3)],"A6B2AE")
    obj.data.materials[0] = mat
    uv = obj.data.uv_layers.new()
    for loop,coord in zip(uv.data,[(0,0),(14,0),(14,6),(0,6)]):
        loop.uv = coord


stem((0,0,0),(0,0,1.23),.036,.036,"9CA9A9",6)
octahedron((0,0,1.23),(.045,.045,.026),"C3CBC8")
finish("chain_link_post")
stem((.028,0,1.16),(SPAN-.028,0,1.16),.024,.024,"AAB5B4",6)
chain_fabric()
finish("chain_link_span")
fence_scene("chain_link")
