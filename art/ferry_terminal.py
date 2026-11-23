"""Build the Tideways passenger hall and ticket plaza. Run with Blender -b -P."""
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def paint(name, color, metallic=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    shader = m.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = .58
    return m


roof = paint("Oxidized bronze-green steel", (.073, .218, .202), .48)
rib = paint("Standing seams", (.12, .295, .265), .48)
dark = paint("Deep spruce trim", (.032,.082,.079))
cedar = paint("Oiled cedar", (.48,.239,.10))
cream = paint("Warm ivory siding", (.78,.747,.607))
stone = paint("Salt grey concrete", (.41,.425,.40))
glass = paint("Harbour blue glazing", (.085,.237,.29), .34)
light = paint("Pale sky glazing", (.19,.38,.42), .3)
white = paint("Enamel lettering", (.92,.89,.73))
yellow = paint("Island safety yellow", (.92,.56,.065))
green = paint("Lane open green", (.15,.78,.32))
kit = []


def box(name, location, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    kit.append(o)
    return o


def beam(name, a, b, width, depth, mat):
    delta = Vector(b)-Vector(a)
    o = box(name, (Vector(a)+Vector(b))/2, (width,depth,delta.length), mat)
    o.rotation_euler = delta.to_track_quat("Z","Y").to_euler()
    return o


def volume(name, verts, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    o = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(o)
    o.data.materials.append(mat)
    kit.append(o)


def label(text, loc, size, face):
    data = bpy.data.curves.new(text, 'FONT')
    data.body = text
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.size = size
    data.space_character = 1.13
    data.materials.append(white)
    o = bpy.data.objects.new(text, data)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = Vector(face).to_track_quat("Z","Y").to_euler()
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    kit.append(o)


def gable(cx, cy, w, length, eave, rise, end_mat, cross=False):
    # Coordinates across and along the ridge, optionally turned a quarter turn.
    def pt(u,v,h):
        return (cx+v, cy-u, h) if cross else (cx+u,cy+v,h)
    for sign in [-1,1]:
        y = sign*(length/2-.43)
        verts = [pt(-w/2+.46,y,eave),pt(w/2-.46,y,eave),pt(0,y,eave+rise-.12)]
        volume("Gable end", verts, [(0,1,2) if (sign < 0) else (2,1,0)], end_mat)
    for sign in [-1,1]:
        a,b,c,d = [pt(u,v,h) for u,v,h in [(0,-length/2,eave+rise),(sign*w/2,-length/2,eave),
                     (sign*w/2,length/2,eave),(0,length/2,eave+rise)]]
        verts = [a,b,c,d]+[(x,y,z-.15) for x,y,z in (a,b,c,d)]
        faces = [(0,1,2,3),(7,6,5,4),(1,0,4,5),(2,1,5,6),(3,2,6,7),(0,3,7,4)]
        volume("Folded metal roof", verts, faces if sign==1 else [f[::-1] for f in faces], roof)
        count = round(length/.92)
        for i in range(count+1):
            v = -length/2+length*i/count
            beam("Raised seam",pt(0,v,eave+rise+.025),pt(sign*w/2,v,eave+.025),.052,.066,rib)
        beam("Eave fascia",pt(sign*w/2,-length/2,eave-.09),pt(sign*w/2,length/2,eave-.09),.18,.20,dark)
    beam("Ridge cap",pt(0,-length/2,eave+rise),pt(0,length/2,eave+rise),.18,.18,rib)


def export(name, drawing_offset):
    bpy.ops.object.select_all(action="DESELECT")
    for o in kit:
        o.select_set(True)
    bpy.context.view_layer.objects.active = kit[0]
    bpy.ops.object.join()
    o = bpy.context.object
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    o.name = name
    # Tideways' shared window shader reads the Blender vertex alpha at night.
    colors = o.data.color_attributes.new(name="Building paint", type="BYTE_COLOR", domain="CORNER")
    for polygon in o.data.polygons:
        mat = o.data.materials[polygon.material_index]
        for index in polygon.loop_indices:
            colors.data[index].color = (.085,.237,.29,0) if mat in (glass,light) else (1,1,1,1)
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "assets/models" / (name+".glb")), use_selection=True, export_vertex_color="ACTIVE", export_all_vertex_colors=True)
    o.location.x += drawing_offset
    kit.clear()


# Long waterfront hall; a recessed service wing and a transverse porte-cochere.
box("Hall foundation",(1,-3,.02),(14.6,24.8,1.1),stone)
box("Hall siding",(1,-3,3.66),(14,24,6.4),cream)
gable(1,-3,15.5,25.3,6.85,3.65,cedar)
for side in [-1,1]:
    x = 1+side*7.04
    for i in range(7):
        y = -13.2+i*3.4
        box("Tall window frame",(x,y,3.68),(.16,2.99,4.65),dark)
        box("Tall glazing",(x+side*.10,y,3.68),(.06,2.73,4.37),glass if i%3 else light)
        box("Transom",(x+side*.14,y,4.93),(.06,2.77,.13),cream)
        box("Mullion",(x+side*.14,y,3.68),(.06,.10,4.4),dark)
        box("Timber pier",(x,y-1.6,3.65),(.25,.22,6.3),cedar)
for y,sign in [(-15,-1),(9,1)]:
    for x in [-4.4,-2.6,-.8,1,2.8,4.6,6.4]:
        if sign < 0 or x == -4.4:  # The lower wing covers the rest of this end wall.
            box("End wall glass",(x,y+sign*.08,4.12),(1.65,.13,4.7),glass)
        h = 2.95*(1-abs(x-1)/7)
        box("Fanlight",(x,y+sign*.24,6.86+h/2),(1.35,.12,h),light)
    box("End lintel",(1,y+sign*.18,6.63),(14.2,.31,.27),dark)
box("Wing plinth",(2.4,12,.02),(10.5,10.3,1.1),stone)
box("Boarded wing",(2.4,12,2.45),(10,10,4.4),cedar)
gable(2.4,12,11.2,11.15,4.65,2.15,cream)


def wing_window(x, y, end_wall=False):
    # Mount the same sash flush to either face, with a clerestory like the hall.
    def layer(name, offset, z, width, depth, height, mat):
        if end_wall:
            box(name, (x, y+offset, z), (width, depth, height), mat)
        else:
            box(name, (x-offset, y, z), (depth, width, height), mat)
    layer("Wing window frame", .045, 2.63, 1.70, .12, 2.24, dark)
    layer("Wing glazing", .12, 2.63, 1.48, .04, 2.02, glass)
    layer("Wing transom", .15, 3.15, 1.50, .04, .09, cream)
    layer("Wing mullion", .16, 2.63, .075, .04, 2.05, dark)


# The visible side wall starts at the hall return (Y=9) and ends at Y=17.
for y in [10.6, 13.0, 15.4]:
    wing_window(-2.6, y)
for x in [-.6, 2.4, 5.4]:
    wing_window(x, 17, end_wall=True)
# Lot-side entry with sheltered doors, exposed timber and a fascia sign.
box("Entry platform",(-8.4,-2,.06),(5.3,10.4,.32),stone)
gable(-8,-2,10.3,5.9,4.85,2.4,cedar,True)
for y in [-6.55,2.55]:
    box("Porch pier",(-10.3,y,2.55),(.37,.37,4.65),cedar)
    box("Post shoe",(-10.3,y,.68),(.57,.57,1.05),stone)
    beam("Knee brace",(-10.3,y,3.65),(-10.3,y+(1 if y<0 else -1)*1.2,4.85),.20,.20,cedar)
for y in [-2.78,-1.22]:
    box("Entry door",(-6.23,y,1.76),(.16,1.45,3.1),dark)
    box("Door glass",(-6.34,y,2.07),(.09,1.18,2.10),light)
box("Entry sign",(-11,-2,4.71),(.24,8.97,.96),dark)
label("FERRY TERMINAL",(-11.131,-2,4.71),.72,(-1,0,0))
export("ferry_passenger_terminal",0)

# Three inbound channels and an unobstructed return lane; +Blender Y faces town.
# All three service windows are on the driver's side of their inbound lane.
for lane,x in enumerate([-14.4,-8.4,-2.4],1):
    bx = x+2.55
    box("Island footing",(bx,0,-.08),(1.64,7.9,.78),stone)
    for y in [-3.55,3.55]:
        box("Impact bollard",(bx,y,.84),(.24,.24,1.26),yellow)
    box("Kiosk body",(bx,0,1.72),(1.48,3.54,2.92),cream)
    box("Kiosk belt",(bx,0,.79),(1.53,3.6,.52),cedar)
    box("Service glazing",(bx,0,2.22),(1.53,3.58,1.20),glass)
    for y in [-1.71,-.56,1.71]:
        box("Window mullions",(bx,y,2.20),(1.57,.09,1.30),dark)
    box("Ticket shelf",(bx-.82,0,1.56),(.40,2.30,.12),dark)
    box("Booth cap",(bx,0,3.23),(1.94,3.98,.17),roof)
    for y in [-2.65,2.65]:
        box("Canopy column",(bx,y,3.05),(.26,.26,6.25),dark)
        beam("Column haunch",(bx,y,4.72),(bx-1.05,y,5.88),.16,.18,cedar)
    for dx in [-1.2,1.2]:
        box("Sign hanger",(x+dx,3.7,6.12),(.075,.075,.72),dark)
    box("Lane sign",(x,3.7,5.41),(3.78,.23,.9),dark)
    label("TICKETS   "+str(lane),(x,3.83,5.41),.50,(0,1,0))
    box("Open lamp",(x+1.55,3.84,5.42),(.23,.07,.23),green)
for y in [-2.65,2.65]:
    for x in [-17.4,5.05]:
        box("Edge post",(x,y,2.99),(.30,.30,6.12),dark)
    box("Canopy girder",(-6.2,y,5.97),(23.1,.25,.34),cedar)
box("Exit sign",(2.5,-3.7,5.41),(3.1,.23,.9),dark)
label("EXIT",(2.5,-3.83,5.41),.52,(0,-1,0))
gable(-6.2,0,8.9,24.4,6.25,1.72,cedar,True)
export("ferry_ticket_plaza",35)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "art/ferry_terminal.blend"))
