"""Build the Tideways electric forklift and its pallet pickup animation in Blender."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
scene.frame_end = 180
scene.unit_settings.system = 'METRIC'


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = tuple(((int(rgb[i:i+2], 16)/255 + .055)/1.055)**2.4
                              for i in (0, 2, 4)) + (1,)
    if not mat.node_tree:
        mat.use_nodes = True
    shader = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = .57
    return mat


amber = material("Safety ochre", "F8AD38")
teal = material("Petrol enamel", "176267")
iron = material("Graphite steel", "29373C")
steel = material("Machined steel", "9DAFAF")
rubber = material("Rubber", "202A2E")
cream = material("Ivory enamel", "FAE9BE")
pine = material("Pine boards", "BB8655")
wood = material("Pine battens", "D7A774")
darkwood = material("End grain", "8D6148")


def empty(name, parent=None, pos=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    scene.collection.objects.link(obj)
    obj.parent = parent
    obj.location = pos
    obj.empty_display_size = .18
    return obj


def finish(name, mat, parent):
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.data.materials.append(mat)
    return obj


def box(name, pos, size, mat, parent, bevel=.02):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = finish(name, mat, parent)
    for vert in obj.data.vertices:
        for axis in range(3):
            vert.co[axis] *= size[axis]
    if bevel:
        mod = obj.modifiers.new("Cast edges", 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Face normals", 'WEIGHTED_NORMAL')
    return obj


def rod(name, start, end, radius, mat, parent):
    direction = Vector(end) - Vector(start)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=direction.length,
                                        location=(Vector(start) + Vector(end))/2)
    obj = finish(name, mat, parent)
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return obj


def label(body, pos, angle, size, mat, parent):
    bpy.ops.object.text_add(location=pos, rotation=(math.pi/2, 0, angle))
    obj = finish(body, mat, parent)
    obj.data.body = body
    obj.data.align_x = 'CENTER'
    obj.data.align_y = 'CENTER'
    obj.data.size = size
    obj.data.extrude = .0005


truck = empty("Forklift • travel")
lift = empty("Carriage • vertical travel", truck)
load = empty("Pallet • cargo assembly")
box("Underframe", (0,.1,.4), (1.08,1.89,.29), iron, truck, .08)
box("Battery compartment", (0,.12,.68), (1.21,1.76,.5), amber, truck, .11)
box("Cast counterweight", (0,.83,.84), (1.24,.65,.77), teal, truck, .16)
box("Operator deck", (0,-.13,.93), (1.05,1.22,.09), iron, truck)
box("Seat pedestal", (0,.29,1.04), (.52,.52,.23), teal, truck)
box("Seat cushion", (0,.23,1.22), (.6,.6,.17), rubber, truck, .07)
box("Seat back", (0,.49,1.48), (.59,.13,.53), rubber, truck, .07).rotation_euler.x = -.12
rod("Steering column", (0,-.54,.95), (0,-.38,1.45), .045, iron, truck)
bpy.ops.mesh.primitive_torus_add(major_radius=.17, minor_radius=.024, location=(0,-.38,1.45),
                                 rotation=(-.30,0,0))
finish("Steering rim", rubber, truck)
rod("Steering spoke", (-.17,-.38,1.45), (.17,-.38,1.45), .016, iron, truck)
for y in (-.13,.02):
    rod("Lift lever", (.37,y,.96), (.36,y-.05,1.31), .023, iron, truck)
for x in (-.51,.51):
    for y in (-.66,.65):
        rod("Overhead guard pillar", (x,y,.87), (x,y*.86,2.1), .045, iron, truck)
    box("Roof side rail", (x,0,2.12), (.10,1.48,.12), amber, truck)
    for y in (-.57,.57):
        box("Work lamp housing", (x,y,2.02), (.14,.10,.09), iron, truck)
        box("Work lamp lens", (x,y-.054,2.02), (.10,.01,.057), cream, truck)
for y in (-.66,-.32,0,.32,.66):
    box("Overhead guard slat", (0,y,2.13), (1.03,.12,.075), amber, truck)
for x in (-.624,.624):
    sign = 1 if x > 0 else -1
    label("PORT  07", (x,.8,.94), sign*math.pi/2, .115, cream, truck)
    for y in (.58,.66,.74,.82,.90):
        box("Cooling louvre", (x,y,.79), (.016,.036,.09), iron, truck)
for y,r in ((-.62,.34),(.71,.28)):
    for side in (-1,1):
        wheel = empty("Wheel assembly", truck, (side*.568,y,r))
        rod("Solid tire", (-.115,0,0), (.115,0,0), r, rubber, wheel)
        rod("Wheel rim", (side*.113,0,0), (side*.129,0,0), r*.64, steel, wheel)
        rod("Hub cap", (side*.13,0,0), (side*.15,0,0), r*.35, teal, wheel)
        for i in range(6):
            a = math.tau*i/6
            v,w = r*.47*math.cos(a),r*.47*math.sin(a)
            rod("Lug", (side*.13,v,w), (side*.145,v,w), .017, iron, wheel)
        driver = wheel.driver_add("rotation_euler", 0).driver
        var = driver.variables.new()
        var.name = 'travel'
        var.targets[0].id = truck
        var.targets[0].data_path = 'location.y'
        driver.expression = f'-travel/{r}'
for x in (-.38,.38):
    box("Fixed mast channel", (x,-.89,1.17), (.13,.16,2.13), iron, truck)
    box("Guide surface", (x,-.985,1.16), (.07,.035,2.06), steel, truck)
box("Mast crown", (0,-.89,2.22), (.89,.18,.13), iron, truck)
rod("Ram barrel", (0,-.88,.22), (0,-.88,.94), .087, teal, truck)
rod("Ram piston", (0,-.88,.27), (0,-.88,.99), .049, steel, lift)
box("Ram crosshead", (0,-.97,.99), (.86,.24,.10), iron, lift)
for z in (.29,.81):
    box("Carriage crossbar", (0,-1.045,z), (1.13,.1,.12), iron, lift)
for x in (-.32,.32):
    box("Fork heel", (x,-1.10,.47), (.13,.09,.80), iron, lift)
    box("Fork blade", (x,-1.66,.091), (.13,1.19,.054), steel, lift, .013)
    box("Backrest upright", (x,-1.04,.9), (.065,.08,.46), amber, lift)
box("Backrest top", (0,-1.04,1.13), (.95,.08,.07), amber, lift)

# The fork tops meet the underside of the deck at z=.118.
cy = -1.73
for x in (-.55,0,.55):
    box("Pallet bearer", (x,cy,.059), (.13,.98,.118), darkwood, load, .007)
for i in range(6):
    box("Deck slat", (0,cy+(i-2.5)*.166,.148), (1.26,.157,.06), wood, load, .006)
for side in (-1,1):
    cx = side*.309
    crate = empty("Crate A" if side < 0 else "Crate B", load, (cx,cy,.178))
    for i in range(5):
        box("Case board", (0,(i-2)*.171,.285), (.585,.166,.57),
            pine if i%2 else wood, crate, .005)
    for y in (-.438,.438):
        for z in (.065,.507):
            box("End batten", (0,y,z), (.59,.035,.084), darkwood, crate, .006)
        box("End brace", (0,y,.285), (.075,.035,.61), wood, crate, .005).rotation_euler.y = .91
    for y in (-.29,.29):
        box("Steel band across lid", (0,y,.577), (.60,.038,.014), teal, crate, .003)
        for x in (-.297,.297):
            box("Steel band return", (x,y,.285), (.013,.038,.57), teal, crate, .002)
    x = side*.306
    box("Shipping stencil plate", (x,0,.32), (.014,.43,.20), cream, crate, .004)
    label("TW / 0"+str(1 if side < 0 else 2), (x+side*.009,0,.32),
          side*math.pi/2,.085,iron,crate)

def animate(obj, axis, poses):
    for frame,value in poses:
        obj.location[axis] = value
        obj.keyframe_insert(data_path='location', index=axis, frame=frame)


animate(truck, 1, [(1,1.45),(36,0),(66,0),(90,.92),(102,.92),(126,0),(151,0),(180,1.45)])
animate(lift, 2, [(1,0),(36,0),(63,.64),(126,.64),(150,0),(180,0)])
constraint = load.constraints.new('CHILD_OF')
constraint.name = "Pallet engaged on forks"
constraint.target = lift
for frame, value in [(1,0),(35,0),(36,1),(150,1),(151,0),(180,0)]:
    constraint.influence = value
    constraint.keyframe_insert(data_path="influence", frame=frame)
for frame,title in [(1,"Approach"),(36,"Engage"),(63,"Lift"),(90,"Carry"),(126,"Lower"),(151,"Withdraw")]:
    scene.timeline_markers.new(title, frame=frame)

floor = box("Quayside slab", (0,0,-.15), (200,200,.30), material("Quay", "798D8C"), None)
bpy.ops.object.camera_add(location=(5.4,-3.7,3.25))
cam = bpy.context.object
target = Vector((0,-.30,1.00))
cam.rotation_euler = (target-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 5.35
scene.camera = cam
for pos,power,size in [((2,-4,6),630,5),((-4,1,4),450,4),((2,4,5),500,3)]:
    bpy.ops.object.light_add(type='AREA',location=pos)
    light = bpy.context.object
    light.rotation_euler = (-light.location).to_track_quat('-Z','Y').to_euler()
    light.data.energy, light.data.shape, light.data.size = power,'DISK',size
scene.world = bpy.data.worlds.new("Overcast harbor")
scene.world.color = (.32,.32,.32)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 960,640
scene.render.resolution_percentage = 100
for frame, expected in [(1,(0,0)),(18,(0,0)),(36,(0,0)),(63,(0,.64)),(90,(.92,.64)),(150,(0,0)),(180,(0,0))]:
    scene.frame_set(frame)
    p = load.matrix_world.translation
    assert abs(p.y-expected[0])+abs(p.z-expected[1]) < .001, (frame,p)
scene.frame_set(90)
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        area.spaces.active.overlay.show_overlays = False
        area.spaces.active.shading.color_type = 'MATERIAL'
bpy.ops.object.select_all(action='DESELECT')
scene.render.filepath = '//forklift_preview.png'
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'forklift.blend'))
bpy.ops.render.render(write_still=True)
