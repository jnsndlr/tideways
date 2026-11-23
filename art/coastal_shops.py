"""Run with blender -b -P art/coastal_shops.py. Pass -- --town-square to build the city hall and Main Street shops."""
from pathlib import Path
from math import atan2, cos, sin, tau
import sys
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/coastal_shops"
bpy.ops.wm.read_factory_settings(use_empty=True)
palette = {
    "Ivory": "faf0d8", "Cream": "e9d2a9", "Oyster": "c2b5a3",
    "Marine": "326884", "Ink": "263c49", "Glass": "316375",
    "Reflection": "55869a", "Cedar": "a56d45", "Honey": "d89b5b",
    "Vermilion": "c55245", "Brass": "efb85d", "Mint": "418e89",
    "Signal": "bd342e", "Lagoon": "238f9b", "Marigold": "efb830", "Pearl": "e5e3db",
    "Seafoam": "348e76", "CanvasMint": "0daa89",
    "Clay": "aa5c40", "OchreBrick": "b06547", "Mortar": "986d58", "Kiln": "924b36",
    "Butter": "ecb854", "Persimmon": "e47937", "Pennant": "2383c3",
    "DeepTeal": "214853", "Lamplight": "ffc656", "TileRed": "cf4229", "Petal": "e9519c", "Aqua": "10aeb8", "Zinc": "8fa4b4", "Dock": "ac865e", "Pile": "776351", "Slate": "415269", "Water": "477f8c",
    "Patina": "367f82", "Leaf": "48735a", "Bloom": "d97980",
}
mats = {}
for name, rgb in palette.items():
    mat = bpy.data.materials.new(name)
    srgb = [int(rgb[i:i+2], 16) / 255 for i in (0, 2, 4)]
    mat.diffuse_color = [((v + .055) / 1.055) ** 2.4 for v in srgb] + [1]
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = mat.diffuse_color
    shader.inputs["Roughness"].default_value = .36 if name in ("Glass", "Reflection") else .77
    mats[name] = mat

for name in ["Lamplight","Zinc"]:
    bsdf=mats[name].node_tree.nodes.get("Principled BSDF")
    if name=="Lamplight":
        bsdf.inputs["Emission Color"].default_value=(1,.46,.06,1)
        bsdf.inputs["Emission Strength"].default_value=2.6
    else:
        bsdf.inputs["Metallic"].default_value=.42

square = "--town-square" in sys.argv
parts = []

def painted(obj, color):
    obj.data.materials.append(mats[color])
    parts.append(obj)
    return obj

def box(x, y, z, w, d, h, color):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    obj = painted(bpy.context.object, color)
    obj.scale = (w, d, h)
    return obj

def rod(a, b, width, color, depth=None):
    direction = Vector(b) - Vector(a)
    obj = box(*((Vector(a) + Vector(b)) / 2), width, depth or width, direction.length, color)
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return obj

def cone(x, y, z, bottom, top, h, color, sides=12):
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=bottom, radius2=top,
                                    depth=h, location=(x, y, z))
    return painted(bpy.context.object, color)

def sign(words, y, z, size, width):
    box(0,y,z,width,.14,size*1.6,"Ink")
    bpy.ops.object.text_add(location=(0,y-.08,z), rotation=(tau/4,0,0))
    obj = bpy.context.object
    if square:
        obj.data.resolution_u = 3
    obj.data.body = words
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.size = size
    obj.data.space_character = 1.14
    bpy.ops.object.convert(target='MESH')
    painted(obj, "Ivory")

def window(x,y,z,w,h,side=False):
    def panel(dx, dy, dz, a,b,c, color):
        # Paint the glass and sash onto thin, two-sided cards on the town kit.
        # Opposite walls reuse these panels with mirrored positions.
        if square and dy in (-.08,-.111,-.13) and color != "Cream":
            depth = dy - b/2
            verts = [(u,0,v) for u,v in [(-a/2,-c/2),(a/2,-c/2),(a/2,c/2),(-a/2,c/2)]]
            mesh=bpy.data.meshes.new("Window detail")
            mesh.from_pydata(verts,[],[(0,1,2,3),(3,2,1,0)])
            obj=bpy.data.objects.new("Window detail",mesh)
            bpy.context.collection.objects.link(obj)
            obj.location=(x-depth,y+dx,z+dz) if side else (x+dx,y+depth,z+dz)
            if side:
                obj.rotation_euler.z=tau/4
            painted(obj,color)
            return
        if side:
            box(x-dy,y+dx,z+dz,b,a,c,color)
        else:
            box(x+dx,y+dy,z+dz,a,b,c,color)
    panel(0,0,0,w,.14,h,"Ivory")
    panel(0,-.08,0,w-.16,.05,h-.17,"Glass")
    panel(0,-.111,h*.34,w-.16,.025,h*.22,"Reflection")
    panel(0,-.13,0,.075,.045,h-.12,"Ivory")
    panel(0,-.13,h*.23,w-.12,.045,.07,"Ivory")
    panel(0,-.08,-h/2,w+.14,.26,.12,"Cream")

def planter(x,y):
    box(x,y,.55,1.25,.56,.44,"Cedar")
    box(x,y,.79,1.34,.62,.10,"Honey")
    count = 3 if square else 5
    for j in range(count):
        dx = x+(j-(count-1)/2)*(.35 if square else .22)
        cone(dx,y,.89,.23,.16,.24,"Leaf",5 if square else 7)
        cone(dx,y-.07,.99,.12,.09,.14,"Bloom" if j%2 else "Brass",5 if square else 6)

def shell(w,d,h,color):
    box(0,0,.20,w+.14,d+.14,.40,"Oyster")
    box(0,0,(h+.36)/2,w,d,h-.36,color)
    for i in range(1,int((h-.35)/.32)):
        z=.35+i*.32
        box(0,0,z,w+.04,d+.04,.044,color)
    for x in [-w/2,w/2]:
        for y in [-d/2,d/2]:
            box(x,y,(h+.36)/2,.16,.16,h-.36,"Ivory")
    for s in (-1,1):
        for y in [-d*.24,d*.24]:
            # The frame projects outward on each side.
            if s == 1:
                window(w/2,y,2.0,1.65,1.72,True)
            else:
                start=len(parts)
                window(w/2,y,2.0,1.65,1.72,True)
                for obj in parts[start:]:
                    obj.location.x *= -1
    for x in [-w*.25,w*.25]:
        start=len(parts)
        window(x,-d/2,2.0,1.7,1.6)
        for obj in parts[start:]:
            obj.location.y *= -1

def shopfront(w,d):
    y=-d/2
    for s in [-1,1]:
        window(s*(w/4+.27),y-.04,2.03,w*.40,2.35)
    box(0,y-.06,1.57,1.18,.19,2.65,"Ivory")
    box(0,y-.17,1.56,.99,.08,2.52,"Ink")
    box(0,y-.23,1.93,.78,.07,1.43,"Reflection")
    box(.38,y-.29,1.29,.07,.10,.27,"Brass")
    box(.83,y-.16,2.59,.20,.24,.36,"Ink")
    box(.83,y-.29,2.59,.14,.04,.22,"Brass")
    box(0,y-.32,.17,1.65,.64,.34,"Oyster")

def gable(w,d,h,rise,roof,face, standing_seams=False):
    # Closed triangular prism with its ridge running away from the street.
    verts=[(x,y,z) for y in (-d/2,d/2) for x,z in [(-w/2,h),(w/2,h),(0,h+rise)]]
    mesh=bpy.data.meshes.new("Pediment")
    mesh.from_pydata(verts,[],[(0,1,2),(5,4,3),(3,4,1,0),(1,4,5,2),(2,5,3,0)])
    obj=bpy.data.objects.new("Pediment",mesh)
    bpy.context.collection.objects.link(obj)
    painted(obj,face)
    for s in [-1,1]:
        edge = w/2+.30
        slope = rise/(w/2)
        angle=s*atan2(rise,w/2)
        panel=box(s*edge/2,0,h+rise-edge*slope/2,edge*(1+slope*slope)**.5,d+.62,.19,roof)
        panel.rotation_euler.y=angle
        if standing_seams:
            count = round(d/.66)
            for i in range(count+1):
                y = d*(i/count-.5)
                rod((0,y,h+rise+.105),(s*edge,y,h+rise-edge*slope+.105),.043,roof)
        else:
            for i in range(1,int(edge/.47)+1):
                x=i*.47
                box(s*x,0,h+rise-x*slope+.11,.044,d+.60,.055,roof)
        for sy in [-1,1]:
            fascia=box(s*edge/2,sy*(d/2+.32),h+rise-edge*slope/2,
                       edge*(1+slope*slope)**.5,.13,.23,"Ivory")
            fascia.rotation_euler.y=angle

def bakery():
    shell(8,5.8,4.12,"Cream")
    shopfront(8,5.8)
    box(0,0,4.14,8.35,6.12,.22,"Ink")
    box(0,-2.91,4.50,8.1,.26,.72,"Cream")
    box(0,-2.91,4.89,8.30,.40,.13,"Ivory")
    sign("SALT  &  RYE",-3.08,4.51,.41,4.3)
    for i in range(17):
        x=(i-8)*.46
        color="Vermilion" if i%2==0 else "Ivory"
        obj=box(x,-3.53,3.52,.46,1.41,.095,color)
        obj.rotation_euler.x=.32
        box(x,-4.19,3.23,.46,.08,.22,color)
    for x in [-2.55,2.55]:
        planter(x,-3.39)
    cone(2.7,1.7,4.57,.22,.22,.7,"Ink")
    cone(2.7,1.7,4.95,.33,.19,.16,"Oyster")

def chandlery():
    shell(7,6.6,3.65,"Marine")
    shopfront(7,6.6)
    gable(7,6.6,3.65,2.14,"Ink","Marine")
    sign("CHANDLERY",-3.46,3.82,.34,3.4)
    # A brass ship's wheel mounted high in the gable.
    for i in range(8):
        a=i*tau/8
        b=(i+1)*tau/8
        rod((0,-3.44,4.66),(.55*cos(a),-3.44,4.66+.55*sin(a)),.056,"Brass")
        rod((.40*cos(a),-3.46,4.66+.40*sin(a)),(.40*cos(b),-3.46,4.66+.40*sin(b)),.074,"Honey")
    for x in [-3.14,-1.15]:
        box(x,-3.84,1.05,.105,.14,2.10,"Cedar")
    box(-2.14,-3.84,2.06,2.19,.16,.12,"Honey")
    for j in range(5):
        x=-2.92+j*.39
        cone(x,-3.84,1.84,.035,.035,.39,"Ink",8)
        cone(x,-3.84,1.51,.14,.07,.29,"Cream")
        cone(x,-3.84,1.31,.115,.14,.14,["Brass","Vermilion","Mint"][j%3])
    for x in [2.36,3.07]:
        cone(x,-3.79,.51,.31,.34,.84,"Honey")
        for z in [.25,.75]:
            cone(x,-3.79,z,.34,.34,.075,"Ink")

def cafe():
    shell(8.4,6,3.84,"Cream")
    shopfront(8.4,6)
    gable(8.4,6,3.84,2.28,"Patina","Glass")
    for x in [-2.8,-1.4,0,1.4,2.8]:
        h=2.28*(1-abs(x)/4.2)
        box(x,-3.07,3.84+h/2,.13,.16,h,"Ivory")
    box(0,-3.08,3.83,8.4,.18,.19,"Ivory")
    for j in range(12):
        box(0,-3.08-j*.19,.32,8.8,.181,.22,"Honey")
    for x in [-4.26,-2.50,-.86,.86,2.50,4.26]:
        box(x,-5.19,.80,.13,.14,1.12,"Cedar")
    for s in [-1,1]:
        for z in [.65,1.34]:
            box(s*2.56,-5.19,z,3.54,.13,.12,"Honey")
        for i in range(9):
            box(s*(1.12+i*.36),-5.19,.97,.065,.08,.64,"Cedar")
        x=s*2.45
        cone(x,-4.03,1.0,.10,.10,1.2,"Ink")
        cone(x,-4.03,1.36,.65,.65,.11,"Honey")
        cone(x,-4.03,1.98,.045,.045,1.23,"Cedar")
        cone(x,-4.03,2.79,1.07,.04,.43,"Vermilion",8)
        for offset in [-.83,.83]:
            box(x+offset,-4.03,.75,.39,.43,.12,"Patina")
            box(x+offset,-4.03,.56,.16,.16,.36,"Ink")
    box(0,-5.52,.14,1.62,.60,.28,"Oyster")
    sign("TIDELINE",-3.15,3.41,.34,3)

def cornice(x, y, z, w, d):
    box(x,y,z,w+.30,d+.30,.18,"Ivory")
    box(x,y,z+.12,w+.39,d+.39,.08,"Oyster")
    box(x,y,z+.19,w+.25,d+.25,.09,"Signal")


def patio_table(x, y, fabric):
    cone(x,y,.70,.075,.075,.96,"Ink")
    cone(x,y,1.10,.55,.55,.10,"Honey")
    cone(x,y,1.76,.035,.035,1.32,"Cedar")
    cone(x,y,2.54,1.16,.06,.43,fabric,8)
    cone(x,y,2.79,.065,.025,.10,"Brass")
    for side in [-1,1]:
        cx=x+side*.83
        box(cx,y,.71,.41,.49,.10,"Honey")
        box(cx+side*.18,y,.94,.08,.49,.42,"Honey")
        for dy in [-.18,.18]:
            box(cx,y+dy,.48,.33,.07,.41,"Cedar")


def harbor_inn():
    w,d=11.6,7.0
    shell(w,d,5.76,"Signal")
    shopfront(w,d)
    for x in [-4.70,-2.84,-.96,.96,2.84,4.70]:
        window(x,-3.53,4.51,.99,1.53)
        box(x,-3.66,5.31,1.15,.23,.11,"Ivory")
    for y in [-2.12,0,2.12]:
        window(w/2,y,4.51,1.06,1.53,True)
    cornice(0,0,5.78,w,d)
    # The third floor sits back from both the dining room and the side balcony.
    x,y=-.80,.63
    width,depth=8.85,5.55
    box(x,y,7.14,width,depth,2.30,"Signal")
    for i in range(1,9):
        box(x,y,6.00+i*.25,width+.035,depth+.035,.042,"Signal")
    for dx in [-width/2,width/2]:
        for dy in [-depth/2,depth/2]:
            box(x+dx,y+dy,7.14,.12,.12,2.30,"Ivory")
    for i in range(6):
        window(x+(i-2.5)*1.41,y-depth/2-.03,7.13,.83,1.33)
    for i in range(3):
        window(x+width/2,y+(i-1)*1.65,7.16,.88,1.34,True)
    cornice(x,y,8.31,width,depth)
    for dx in [-2.8,0,2.8]:
        box(x+dx,y+.68,8.79,.61,.54,.56,"Oyster")
        box(x+dx,y+.39,8.79,.36,.04,.30,"Ink")
    # Wrap the outer gallery around the exposed end of the top floor.
    for a,b in [((3.67,-2.43),(5.67,-2.43)),((5.67,-2.43),(5.67,3.30)),
                ((5.67,3.30),(3.67,3.30))]:
        for z in [6.12,6.93]:
            rod((*a,z),(*b,z),.10,"Ivory")
        n=round((Vector(b)-Vector(a)).length/.25)
        for i in range(n+1):
            px,py=Vector(a).lerp(Vector(b),i/n)
            box(px,py,6.53,.055,.055,.81,"Ivory")
    for py in [-.7,2.8]:
        box(5.47,py,7.03,.11,.11,2.00,"Ivory")
    canopy=box(4.67,1.05,8.12,2.33,3.93,.14,"Signal")
    canopy.rotation_euler.y=.12
    box(0,-4.45,.14,11.74,2.05,.28,"Oyster")
    for px,fabric in [(-4.02,"Marigold"),(-1.58,"Lagoon"),(3.25,"Lagoon")]:
        patio_table(px,-4.56,fabric)
    planter(5.08,-4.02)


def hall_planter(x,y):
    box(x,y,.19,1.09,.48,.38,"Cedar")
    planter(x,y)


def glass_hall():
    # A transverse main roof and a taller front cross-gable over the glazed entry.
    w,d=11.2,7.0
    shell(w,d,3.50,"Pearl")
    start=len(parts)
    gable(d,w,3.52,2.12,"Lagoon","Pearl", standing_seams=True)
    for obj in parts[start:]:
        x,y,_=obj.location
        obj.location.x,obj.location.y=-y,x
        obj.rotation_euler=(Matrix.Rotation(tau/4,3,'Z') @
                            obj.rotation_euler.to_matrix()).to_euler()
    for x in [-4.42,4.42]:
        window(x,-3.53,2.04,1.53,1.83)
    # The two roofs meet along valleys. Sink the back of the cross-gable into the ridge.
    box(0,-3.47,1.90,6.18,1.02,3.80,"Glass")
    start=len(parts)
    gable(6.18,4.16,3.81,1.92,"Lagoon","Glass", standing_seams=True)
    for obj in parts[start:]:
        obj.location.y-=1.90
    face=-4.01
    for x in [-3.00,-2.25,-.86,.86,2.25,3.00]:
        height=3.80+1.92*(1-abs(x)/3.09)
        box(x,face,height/2,.13,.17,height,"Ivory")
    for z in [.44,2.99,3.78]:
        box(0,face-.014,z,6.14,.17,.13,"Ivory")
    for x in [-.40,.40]:
        box(x,face-.09,1.67,.77,.10,2.52,"Marine")
        box(x,face-.16,1.84,.61,.035,1.78,"Glass")
        box(x*.38,face-.21,1.54,.055,.065,.29,"Brass")
    box(0,-4.22,.18,1.93,.76,.36,"Oyster")
    # Warm pendant silhouettes read through the dark glass from the ferry camera.
    for x in [-1.71,-.46,0,.46,1.71]:
        top=3.73+1.81*(1-abs(x)/3.09)
        drop=.46 if x else .71
        box(x,face-.10,top-drop/2,.034,.036,drop,"Ink")
        cone(x,face-.10,top-drop-.08,.10,.055,.16,"Brass",8)
    for x in [-4.60,-2.67,2.67,4.60]:
        hall_planter(x,-4.14 if abs(x)<3 else -3.91)
    for y in [-1.68,1.68]:
        start=len(parts)
        hall_planter(0,0)
        for obj in parts[start:]:
            px,py,_=obj.location
            obj.location.x,obj.location.y=w/2+.29-py,y+px
            obj.rotation_euler.z+=tau/4
    box(.83,-4.12,2.59,.20,.24,.36,"Ink")
    box(.83,-4.25,2.59,.14,.04,.22,"Brass")


def dining_pier():
    # The deck surface is the origin. Port-side opening connects directly to the jetty.
    for i in range(42):
        box(0,-5.92+i*.24,-.09,14,.233,.18,"Honey" if i%6==0 else "Dock")
    for y in [-5.86,-3.43,.04,3.82]:
        box(0,y,-.38,14,.33,.42,"Cedar")
        for x in [-6.78,-4.52,-2.26,0,2.26,4.52,6.78]:
            box(x,y,-4.68,.46,.46,9.2,"Pile")
    for x in [-6.80,0,6.80]:
        box(x,-1.0,-.42,.29,10.03,.44,"Cedar")
    # Rail posts, square caps, and vertical pickets around the terrace.
    runs=[((-6.81,-5.89),(6.81,-5.89),6),
          ((6.81,-5.89),(6.81,3.78),4),
          ((-6.81,-3.51),(-6.81,3.78),3),
          ((-6.81,3.78),(6.81,3.78),6)]
    posts = set()
    for a,b,bays in runs:
        start,end=Vector(a),Vector(b)
        for z,thickness in [(.25,.085),(1.02,.13)]:
            rod((*a,z),(*b,z),thickness,"Honey")
        for i in range(bays*6+1):
            x,y=start.lerp(end,i/(bays*6))
            if i%6:
                box(x,y,.63,.055,.055,.72,"Dock")
            elif (round(x,2), round(y,2)) not in posts:
                posts.add((round(x,2), round(y,2)))
                box(x,y,.55,.15,.15,1.10,"Cedar")
                box(x,y,1.13,.22,.22,.09,"Honey")


def rail_flowers(x):
    start=len(parts)
    planter(x,-5.83)
    for obj in parts[start:]:
        obj.location.z+=.67
    for j in range(13):
        dx=(j%7-3)*.172
        dy=(j//7-.5)*.22
        z=1.74+.10*cos(j*2.5)
        cone(x+dx,-5.83+dy,z,.19,.14,.23,"Leaf",7)
        cone(x+dx-.04,-5.87+dy,z+.12,.105,.075,.12,"Petal" if j%3 else "Bloom",7)


def pendant(x,y,top,drop):
    box(x,y,top-drop/2,.028,.03,drop,"Ink")
    cone(x,y,top-drop-.09,.105,.052,.18,"Brass",8)


def globe(x,y,z,r=.095):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,location=(x,y,z))
    obj=painted(bpy.context.object,"Lamplight")
    obj.scale=(r,r,r*1.23)


def dining_chair(x,y,angle):
    start=len(parts)
    box(0,0,.49,.42,.44,.09,"Marigold")
    for dx in [-.17,.17]:
        for dy in [-.17,.17]:
            height=.96 if dy>0 else .47
            rod((dx*1.2,dy*1.22,.02),(dx,dy,height),.055,"Honey")
    for z in [.75,.90]:
        box(0,.18,z,.43,.065,.095,"Marigold")
    for obj in parts[start:]:
        p=obj.location.copy()
        obj.location.x=x+p.x*cos(angle)-p.y*sin(angle)
        obj.location.y=y+p.x*sin(angle)+p.y*cos(angle)
        obj.rotation_euler=(Matrix.Rotation(angle,3,'Z') @ obj.rotation_euler.to_matrix()).to_euler()


def dining_tables(xs,fabric):
    for x in xs:
        y=-4.67
        cone(x,y,.46,.13,.085,.92,"Cedar")
        cone(x,y,.93,.62,.62,.085,"Honey")
        cone(x,y,1.84,.035,.035,1.82,"Brass")
        cone(x,y,2.79,1.27,.055,.41,fabric,10)
        cone(x,y,3.04,.06,.03,.10,"Brass")
        for a in [-1.18,1.18,3.14]:
            dining_chair(x+.81*sin(a),y+.81*cos(a),-a)


def dining_room(w,d,h,paint):
    # Open glazed bays reveal the back wall, booths and hanging fixtures in both renderers.
    box(0,0,.10,w,d,.20,"Dock")
    box(0,d/2,h/2,w,.19,h,paint)
    box(0,d/2-.15,2.0,w-.28,.10,2.94,"DeepTeal")
    for x in [-w*.32,0,w*.32]:
        box(x,d/2-.23,2.28,2.04,.07,1.48,"Glass")
        box(x,d/2-.28,2.28,.07,.06,1.48,"Cream")
        box(x,d/2-.30,2.64,2.04,.05,.075,"Cream")
    for x in [-w/2,w/2]:
        box(x,0,.48,.17,d,.94,paint)
        for y in [-d/2,-d*.25,0,d*.25,d/2]:
            box(x,y,h/2,.14,.15,h,"Ivory")
        for z in [.94,h-.78,h-.06]:
            box(x,0,z,.17,d,.12,"Ivory")
    box(0,0,h-.05,w,d,.10,"Cedar")
    box(0,-d/2,.25,w,.15,.50,paint)
    for x in [-w/2,-w*.31,-w*.13,w*.13,w*.31,w/2]:
        box(x,-d/2,h/2,.15,.19,h,"Ivory")
    for z in [.49,h-.67,h-.06]:
        box(0,-d/2,z,w,.17,.13,"Ivory")
    for x in [-w*.34,0,w*.34]:
        box(x,.88,.57,1.85,.68,.72,"Marine")
        box(x,1.22,1.04,1.85,.14,.62,"Patina")
        box(x,.06,.68,.18,.22,.96,"Ink")
        box(x,.06,1.13,1.71,.85,.09,"Honey")
        for dx in [-.56,.56]:
            cone(x+dx,.06,1.23,.095,.075,.14,"Ivory")
        for y in [-1.05,1.10]:
            box(x,y,h-.28,.025,.025,.45,"Ink")
            cone(x,y,h-.57,.17,.055,.16,"Honey")
            globe(x,y,h-.68)
    # Shallow blue transom panes catch sky above the clear view into each booth.
    for a,b in zip([-.50,-.31,-.13,.13,.31],[-.31,-.13,.13,.31,.50]):
        box(w*(a+b)/2,-d/2+.06,h-.38,w*(b-a)-.13,.045,.46,"Reflection")
    for x in [-w/2,w/2]:
        for j in range(4):
            box(x,(-.375+j*.25)*d,h-.41,.05,d*.25-.15,.54,"Reflection")
    # Recessed glass double doors with brass pulls.
    for x in [-.45,.45]:
        box(x,-d/2+.05,1.46,.86,.10,2.55,"Marine")
        box(x,-d/2-.02,1.65,.70,.035,1.80,"Glass")
        box(x*.36,-d/2-.07,1.27,.045,.06,.33,"Brass")


def deck_lamp(x,y,z):
    rod((x,y,z),(x,y-.14,z+.31),.055,"Ink")
    rod((x,y-.14,z+.31),(x,y-.41,z+.31),.055,"Ink")
    rod((x,y-.41,z+.31),(x,y-.46,z+.15),.055,"Ink")
    cone(x,y-.46,z+.11,.16,.05,.12,"Ink")
    globe(x,y-.46,z+.01,.092)


def sea_glass_grill():
    dining_pier()
    w,d=9.50,5.70
    dining_room(w,d,3.33,"Pearl")
    gable(w,d,3.35,2.60,"Aqua","DeepTeal",standing_seams=True)
    for x in [-3.14,-1.55,0,1.55,3.14]:
        rise=2.60*(1-abs(x)/(w/2))
        box(x,-d/2-.064,3.35+rise/2,.12,.14,rise,"Ivory")
    box(0,-d/2-.09,3.37,w,.18,.16,"Ivory")
    for x in [-2.35,-.75,.75,2.35]:
        top=5.88-abs(x)*.55
        pendant(x,-2.97,top,.44)
        globe(x,-3.00,top-.62,.088)
    for x,y in [(-2.9,1.3),(1.8,1.1),(3.45,.40)]:
        z=5.95-abs(x)*2.60/(w/2)
        cone(x,y,z+.25,.21,.21,.74,"Zinc")
        cone(x,y,z+.62,.27,.27,.24,"Zinc")
    dining_tables([-5.05,-1.55,2.15],"Aqua")
    for x in [-4.72,4.72]:
        deck_lamp(x,-2.88,3.09)
    for x in [4.53,6.00]:
        rail_flowers(x)


def life_ring(x,y,z):
    # Alternating painted arcs, each with a circular tube section.
    for i in range(24):
        verts=[]
        for a in [tau*i/24,tau*(i+1)/24]:
            for j in range(8):
                b=tau*j/8
                radius=.41+.10*cos(b)
                verts.append((x+radius*cos(a),y+.10*sin(b),z+radius*sin(a)))
        mesh=bpy.data.meshes.new("Ring arc")
        mesh.from_pydata(verts,[],[(j,8+j,8+(j+1)%8,(j+1)%8) for j in range(8)])
        obj=bpy.data.objects.new("Ring arc",mesh)
        bpy.context.collection.objects.link(obj)
        painted(obj,"Ivory" if i%6<2 else "Signal")


def crab_pot(x,y,z):
    box(x,y,z+.31,.83,.61,.56,"Marine")
    for dx in [-.47,-.24,0,.24,.47]:
        rod((x+dx,y-.36,z),(x+dx,y-.27,z+.63),.046,"Marigold")
        rod((x+dx,y+.36,z),(x+dx,y+.27,z+.63),.046,"Marigold")
        box(x+dx,y,z+.64,.046,.56,.046,"Marigold")
    for height in [.03,.23,.44,.62]:
        depth=.36-.09*height/.63
        for side in [-1,1]:
            box(x,y+side*depth,z+height,.98,.047,.045,"Honey")


def red_net_kitchen():
    dining_pier()
    w,d=11.50,5.50
    dining_room(w,d,3.61,"TileRed")
    # Red clapboard spandrels, end piers and white lintels frame the dining bays.
    for x in [-4.47,4.24]:
        width=2.54 if x<0 else 3.00
        box(x,-2.80,3.20,width,.15,.80,"TileRed")
        for z in [2.98,3.20,3.42]:
            box(x,-2.89,z,width,.06,.045,"Signal")
        box(x,-2.91,2.78,width+.11,.15,.13,"Ivory")
    for x in [-5.54,5.54]:
        box(x,-2.81,1.78,.42,.22,3.54,"TileRed")
    # A broad transverse roof behind the projecting entrance gable.
    start=len(parts)
    gable(d,w,3.63,1.71,"Slate","Signal",standing_seams=True)
    turn=Matrix.Rotation(tau/4,3,'Z')
    for obj in parts[start:]:
        x,y,_=obj.location
        obj.location.x,obj.location.y=-y,x
        obj.rotation_euler=(turn @ obj.rotation_euler.to_matrix()).to_euler()
    for x in [-3.28,1.78]:
        box(x,-2.88,1.84,.43,.93,3.68,"TileRed")
        for h in range(1,15):
            box(x,-3.35,h*.24,.43,.05,.045,"Signal")
        deck_lamp(x,-3.35,3.12)
    for x in [-5.12,4.76]:
        deck_lamp(x,-2.83,3.39)
    for x in [-2.82,1.32]:
        box(x,-3.35,1.85,.15,.14,3.70,"Ivory")
    start=len(parts)
    gable(5.45,3.53,3.70,2.05,"Slate","Signal",standing_seams=True)
    for obj in parts[start:]:
        obj.location.x-=.75
        obj.location.y-=1.58
    box(-.75,-3.38,3.04,4.21,.16,.16,"Ivory")
    # Double doors in the central bay; matching glazed transom under the peak.
    for x in [-1.19,-.31]:
        box(x,-3.55,1.38,.85,.10,2.34,"Marine")
        box(x,-3.62,1.66,.69,.04,1.42,"Glass")
        box((x-.75)/2,-3.65,1.24,.055,.05,.24,"Brass")
    for i in range(9):
        x=(i-4)*.38
        h=1.26-.61*abs(x)
        box(-.75+x,-3.39,3.69+h/2,.38,.11,h,"Glass")
    for x in [-1.98,-.75,.48]:
        h=1.26-.61*abs(x+.75)
        box(x,-3.47,3.69+h/2,.08,.09,h,"Ivory")
    for side in [-1,1]:
        rod((-.75,-3.46,5.03),(-.75+side*1.74,-3.46,3.96),.15,"Ivory")
    box(-.75,-3.46,3.68,3.65,.14,.12,"Ivory")
    for x in [-1.50,-.75,0]:
        top=4.87-.61*abs(x+.75)
        pendant(x,-3.52,top,.31)
        globe(x,-3.54,top-.51,.09)
    box(3.38,.49,5.48,.66,.68,2.66,"Signal")
    box(3.38,.49,6.82,.78,.80,.12,"Ivory")
    box(3.38,.49,7.00,.57,.59,.29,"Ink")
    box(3.38,.49,7.19,.80,.82,.11,"Slate")
    for dx in [-.32,.32]:
        box(3.38+dx,.13,5.83,.07,.08,2.02,"Cream")
    for row in range(10):
        box(3.38,.132,4.87+row*.18,.56,.018,.022,"Cedar")
    dining_tables([-5.12,-2.14,3.91],"Marigold")
    for x in [.72,5.95]:
        rail_flowers(x)
    life_ring(-2.21,-6.05,.51)
    # A low gear shelf hangs outside the rail, above the water.
    box(3.10,-6.45,-.52,3.46,1.10,.16,"Dock")
    for x in [1.73,4.47]:
        rod((x,-5.79,-1.06),(x,-6.83,-.60),.12,"Pile")
    for x in [2.02,3.10,4.18]:
        crab_pot(x,-6.49,-.43)
    for x in [2.56,3.64]:
        crab_pot(x,-6.49,.23)


def flat_roof(x,y,z,w,d):
    box(x,y,z,w+.26,d+.26,.22,"Ivory")
    box(x,y,z+.15,w+.36,d+.36,.09,"Slate")
    box(x,y,z+.21,w+.22,d+.22,.055,"Zinc")


def brick_skin(w,d,h, length=.60, course=.18):
    # One quad per brick, with staggered courses and narrow mortar joints.
    verts,faces,tones=[],[],[]
    for side,(span,depth) in enumerate([(w,d),(d,w),(w,d),(d,w)]):
        for row in range(int(h/course)):
            x=-span/2-length*.5*(row%2)
            col=0
            while x<span/2:
                a=max(x+.008,-span/2)
                b=min(x+length-.01,span/2)
                if b>a:
                    z=.17+row*course
                    face=[]
                    for u,v in [(a,z),(b,z),(b,z+course-.013),(a,z+course-.013)]:
                        xy=[(u,-depth/2-.012),(depth/2+.012,u),(-u,depth/2+.012),(-depth/2-.012,-u)][side]
                        face.append(len(verts))
                        verts.append((*xy,v))
                    faces.append(face)
                    tones.append((col*37+row*17+(col*row)%7)%9)
                x+=length
                col+=1
    mesh=bpy.data.meshes.new("Running bond")
    mesh.from_pydata(verts,[],faces)
    obj=bpy.data.objects.new("Running bond",mesh)
    bpy.context.collection.objects.link(obj)
    painted(obj,"Clay")
    for color in ["Kiln","OchreBrick"]:
        mesh.materials.append(mats[color])
    for poly,tone in zip(mesh.polygons,tones):
        poly.material_index=1 if tone==0 else 2 if tone in [1,2] else 0


def retail_bay(x,y,width,door=False):
    """Painted storefront with a recessed display, transom and brass door furniture."""
    box(x,y,1.47,width,.14,2.74,"Marine")
    box(x,y-.08,1.57,width-.14,.045,2.34,"DeepTeal")
    box(x,y-.12,2.52,width-.16,.035,.41,"Reflection")
    box(x,y-.15,2.26,width,.085,.09,"Cream")
    if door:
        for side in [-1,1]:
            cx=x+side*width/4
            box(cx,y-.16,1.23,width*.48,.09,2.01,"Marine")
            box(cx,y-.22,1.51,width*.48-.13,.045,1.24,"Glass")
            box(x+side*.12,y-.27,1.13,.045,.06,.26,"Brass")
    else:
        box(x,y-.14,.74,width-.19,.08,.10,"Honey")
        for j in range(5):
            cx=x+width*(j-2)*.15
            box(cx,y-.13,.92,.13,.07,.26+.06*(j%3),["Honey","Patina","Cream"][j%3])
        box(x,y-.18,1.49,.075,.10,2.59,"Marine")


def seafoam_cafe():
    w,d=9.1,5.65
    shell(w,d,3.72,"Seafoam")
    flat_roof(0,0,3.74,w,d)
    # The taller right-hand volume carries the canvas above the entry.
    box(1.22,.12,4.45,6.55,5.52,1.39,"Seafoam")
    flat_roof(1.22,.12,5.17,6.55,5.52)
    for x,y,z in [(-3.63,.98,4.02),(-1.04,.85,5.45),(.96,.94,5.45),(2.95,1.21,5.45)]:
        box(x,y,z+.23,.70,.55,.47,"Zinc")
        for j in range(4):
            box(x-.20+j*.13,y-.29,z+.23,.058,.03,.25,"Slate")
        box(x,y,z+.49,.75,.59,.07,"Oyster")
    for x in [-3.48,-1.86]:
        window(x,-d/2-.06,1.96,1.05,1.49)
    for x,width,door in [(.16,1.19,False),(1.47,1.38,True),(2.95,1.51,False)]:
        retail_bay(x,-d/2-.09,width,door)
    for x in [-.53,3.78]:
        box(x,-d/2-.11,1.92,.13,.21,3.66,"Ivory")
    box(1.47,-3.14,.15,1.78,.72,.30,"Oyster")
    # A pitched canvas with a round lower hem on each alternating stripe.
    for j in range(11):
        x=-.53+(j+.5)*.39
        color="CanvasMint" if j%2==0 else "Ivory"
        panel=box(x,-3.15,4.25,.39,1.91,.085,color)
        panel.rotation_euler.x=.53
        box(x,-3.98,3.68,.39,.08,.21,color)
        hem=cone(x,-3.98,3.595,.192,.192,.077,color,16)
        hem.rotation_euler.x=tau/4
    for x in [-3.36,2.84]:
        start=len(parts)
        planter(x,-3.03)
        for obj in parts[start:]:
            obj.location.z+=.48
    box(0,-3.88,.06,9.38,2.34,.12,"Oyster")
    for x in [-3.36,-1.35,2.80]:
        outdoor_table(x,-4.02,.12)
    deck_lamp(.83,-2.91,2.56)


def mercantile():
    w,d=9.8,6.3
    box(0,0,4.30,w,d,8.60,"Mortar")
    brick_skin(w,d,8.40)
    box(0,0,.15,w+.10,d+.10,.30,"Oyster")
    for x in [-4.73,-2.47,2.47,4.73]:
        box(x,-3.20,4.25,.29,.18,8.50,"Kiln")
        box(x,-3.26,.25,.42,.22,.50,"Oyster")
    for z in [4.44,7.00]:
        for x in [-3.62,-1.66,0,1.66,3.62]:
            window(x,-3.21,z,1.02,1.59)
            box(x,-3.36,z+.86,1.22,.21,.15,"Cream")
            box(x,-3.39,z+.87,.18,.24,.24,"Oyster")
        for y in [-1.94,0,1.94]:
            window(w/2,y,z,1.12,1.59,True)
        for x in [-3,0,3]:
            start=len(parts)
            window(x,-3.15,z,1.1,1.59)
            for obj in parts[start:]:
                obj.location.y*=-1
    # Deep teal shopfronts are separated by brick piers with stone plinths.
    for x,width,door in [(-3.65,1.71,True),(-1.36,2.06,False),(.47,1.43,True),
                         (2.28,1.66,False),(4.03,1.22,True)]:
        retail_bay(x,-3.23,width,door)
    for x in [-4.73,-2.47,1.36,3.29,4.73]:
        box(x,-3.27,1.53,.26,.23,2.98,"Kiln")
        box(x,-3.32,.22,.35,.27,.44,"Oyster")
    for x in [-3.62,3.62]:
        box(x,-3.24,5.72,1.55,.16,.54,"OchreBrick" if x<0 else "Cream")
    box(0,-3.23,3.08,w+.10,.22,.32,"Kiln")
    awning=box(2.28,-3.79,2.93,1.98,1.25,.105,"Signal")
    awning.rotation_euler.x=.31
    box(2.28,-4.38,2.66,1.98,.09,.19,"Signal")
    for x in [-3.78,.62]:
        deck_lamp(x,-3.40,2.71)
    for x in [-1.41,2.25]:
        hall_planter(x,-3.49)
    flat_roof(0,0,8.57,w,d)
    box(0,0,8.88,w+.43,d+.43,.13,"Cream")


def canopy(x,y,z,w,d,height,color):
    # Shallow rectangular hip roof above the open timber pavilion.
    bpy.ops.mesh.primitive_cone_add(vertices=4,radius1=1,radius2=0,depth=height,
                                   location=(x,y,z+height/2),rotation=(0,0,tau/8))
    obj=painted(bpy.context.object,color)
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
    obj.scale=(w/1.41421356,d/1.41421356,1)
    box(x,y,z,w,d,.11,color)


def outdoor_table(x,y,floor,shade=None):
    cone(x,y,floor+.47,.105,.075,.91,"Cedar")
    cone(x,y,floor+.94,.55,.55,.11,"Honey")
    for a in [-1.32,1.32,2.89]:
        start=len(parts)
        dining_chair(x+.74*sin(a),y+.74*cos(a),-a)
        for obj in parts[start:]:
            obj.location.z+=floor
    if shade:
        cone(x,y,floor+1.68,.035,.035,1.48,"Honey")
        cone(x,y,floor+2.51,1.13,.035,.42,shade,8)


def pavilion(x,y,floor,w,d,clearance):
    z=floor+clearance
    for sx in [-1,1]:
        for sy in [-1,1]:
            px,py=x+sx*(w/2-.21),y+sy*(d/2-.20)
            box(px,py,floor+clearance/2,.13,.13,clearance,"Cedar")
            rod((px,py,z-.52),(px-sx*.50,py,z-.07),.085,"Honey")
            globe(px,py,z-.61,.082)
    canopy(x,y,z,w,d,w*.21,"Persimmon")


def sunset_terrace():
    w,d=12,6
    shell(w,d,3.02,"Butter")
    shopfront(w,d)
    box(-2.87,.12,4.42,6.28,5.68,2.80,"Butter")
    for x in [-4.34,-1.36]:
        window(x,-2.74,4.54,2.47,1.40)
    flat_roof(-2.87,.12,5.88,6.28,5.68)
    box(-2.97,-3.20,3.13,6.32,.70,.19,"Slate")
    for x in [-5.60,-4.64,-3.68,-2.72,-1.76,-.80]:
        rod((x,-3.03,2.59),(x,-3.44,3.09),.12,"Ink")
    box(3.06,-.26,3.14,6.16,6.41,.30,"Cedar")
    for y in [-3.45,2.9]:
        for z in [3.55,4.19]:
            box(3.05,y,z,6.11,.11,.12,"Honey")
        for j in range(20):
            box(.13+j*.31,y,3.82,.07,.09,.70,"Cedar")
    for z in [3.55,4.19]:
        box(6.05,-.28,z,.11,6.38,.12,"Honey")
    for j in range(20):
        box(6.05,-3.36+j*.32,3.82,.08,.08,.70,"Cedar")
    pavilion(2.22,-.18,3.28,4.35,4.0,2.56)
    outdoor_table(2.12,-1.13,3.30)
    outdoor_table(4.92,-.28,3.30,"Signal")
    box(0,-4.04,.12,12.24,2.23,.24,"Oyster")
    pavilion(1.64,-4.13,.24,3.63,2.03,2.58)
    outdoor_table(1.64,-4.10,.24)
    outdoor_table(-2.66,-4.14,.24,"Persimmon")
    outdoor_table(4.87,-4.16,.24,"Aqua")
    hall_planter(-5.47,-3.62)


def harbor_office():
    w,d=10.50,6.0
    shell(w,d,3.75,"Butter")
    flat_roof(0,0,3.81,w,d)
    for x in [-3.78,-2.10,.18,2.16,4.06]:
        window(x,-3.04,1.93,1.64,2.18)
    box(-1.95,-3.21,1.55,1.65,.14,2.65,"Marine")
    for x in [-2.35,-1.55]:
        box(x,-3.30,1.75,.66,.06,1.73,"Glass")
        box(x*.18-1.60,-3.36,1.26,.045,.05,.31,"Brass")
    box(-2.45,-3.91,.22,5.63,1.94,.44,"Oyster")
    box(-1.93,-5.03,.12,2.14,.42,.24,"Cream")
    flat_roof(-2.45,-3.91,3.22,5.65,2.09)
    for x in [-5.02,-2.87,.12]:
        box(x,-4.78,1.77,.17,.18,2.91,"Honey")
        for side in [-1,1]:
            rod((x,-4.78,2.57),(x+side*.46,-4.78,3.17),.109,"Honey")
    for z in [.62,1.34]:
        box(-4.05,-4.78,z,2,.10,.10,"Ivory")
    for j in range(10):
        box(-4.99+j*.20,-4.78,.98,.045,.07,.71,"Ivory")
    for j in range(3):
        box(2.57,-3.91+j*.12,.62,2.14,.10,.10,"Honey")
        box(2.57,-3.62,.83+j*.14,2.14,.10,.10,"Honey")
    for x in [1.78,3.36]:
        box(x,-3.76,.33,.13,.38,.54,"Ink")
    for x in [.75,4.57]:
        hall_planter(x,-3.76)
    for x in [-5.04,-3.05]:
        cone(x,-4.98,.49,.11,.10,.94,"Ink")
        cone(x,-4.98,.98,.12,.045,.12,"Zinc")
    # Four glazed faces below the shallow hipped lookout roof.
    box(-1.27,.42,4.76,3.62,2.62,1.37,"Glass")
    for sy in [-1,1]:
        for j in range(5):
            box(-3.04+j*.89,.42+sy*1.33,4.77,.09,.10,1.34,"Ivory")
        box(-1.27,.42+sy*1.34,4.90,3.68,.10,.09,"Ivory")
    for sx in [-1,1]:
        for j in range(4):
            box(-1.27+sx*1.83,-.86+j*.85,4.77,.10,.09,1.34,"Ivory")
        box(-1.27+sx*1.83,.42,4.90,.10,2.67,.09,"Ivory")
    flat_roof(-1.27,.42,4.10,3.69,2.68)
    canopy(-1.27,.42,5.49,4.05,3.08,.43,"Slate")
    box(-1.27,.42,6.03,.48,.45,.42,"Oyster")
    flat_roof(-1.27,.42,6.24,.49,.46)
    cone(1.92,.35,5.29,.05,.043,2.65,"Ink")
    cone(1.92,.35,6.66,.081,.032,.12,"Brass")
    verts=[(1.96,.35,6.52),(2.38,.22,6.56),(2.86,.45,6.42),(3.29,.37,6.40),
           (2.92,.43,6.23),(3.21,.37,6.12),(2.72,.45,6.04),(2.39,.22,6.16),(1.96,.35,6.10)]
    mesh=bpy.data.meshes.new("Swallowtail pennant")
    mesh.from_pydata(verts,[],[(0,8,7,1),(1,7,6,2),(2,6,5,4),(2,4,3)])
    obj=bpy.data.objects.new("Swallowtail pennant",mesh)
    bpy.context.collection.objects.link(obj)
    painted(obj,"Pennant")
    solid=obj.modifiers.new("Flag thickness",'SOLIDIFY')
    solid.thickness=.025
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.modifier_apply(modifier=solid.name)
    deck_lamp(.83,-3.01,2.56)


def turned_profile(x, y, rings, sides, color):
    """Continuous ring mesh for stacked mouldings, open where the ends meet trim."""
    verts = [(x+r*cos(i*tau/sides), y+r*sin(i*tau/sides), z)
             for z,r in rings for i in range(sides)]
    faces = []
    for ring in range(len(rings)-1):
        for i in range(sides):
            a = ring*sides+i
            b = ring*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
    mesh = bpy.data.meshes.new("Turned moulding")
    mesh.from_pydata(verts,[],faces)
    obj = bpy.data.objects.new("Turned moulding",mesh)
    bpy.context.collection.objects.link(obj)
    painted(obj,color)


def city_hall():
    w, d = 11, 7
    shell(w, d, 4.45, "Cream")
    start = len(parts)
    gable(d, w, 4.48, 2.05, "DeepTeal", "Cream", standing_seams=True)
    turn = Matrix.Rotation(tau/4, 3, 'Z')
    for obj in parts[start:]:
        obj.location = turn @ obj.location
        obj.rotation_euler = (turn @ obj.rotation_euler.to_matrix()).to_euler()
    for x in (-4.35, 4.35):
        window(x, -3.53, 2.50, 1.36, 2.42)
    retail_bay(0, -3.55, 2, door=True)
    for i in range(4):
        depth = 2.82 - i*.31
        box(0, -3.48-depth/2, .09+i*.18, 6.0, depth, .18, "Oyster")
    for x in (-2.62, -1.31, 1.31, 2.62):
        turned_profile(x,-5.07,[(.72,.29),(.92,.29),(1.08,.215),
                                (3.91,.18),(4.08,.31)],8,"Ivory")
        box(x, -5.07, 4.13, .64,.64,.15,"Cream")
    box(0,-4.32,4.38,6.22,2.24,.45,"Ivory")
    sign("CITY  HALL", -5.47, 4.4, .32, 3.18)
    start = len(parts)
    gable(6.12,3.5,4.63,1.44,"DeepTeal","Cream",standing_seams=True)
    for obj in parts[start:]:
        obj.location.y -= 3.45
    for x in (-4.18,4.18):
        hall_planter(x,-4.12)
    # Square clock lantern above the roof ridge and a spun copper dome.
    box(0,0,6.52,2.15,2.15,.36,"Ivory")
    box(0,0,7.42,1.86,1.86,1.52,"Cream")
    for k in range(4):
        start = len(parts)
        # The bezel and dial share a rim; the tower closes the back.
        sides = 16
        rings = [(-.92,.65),(-1.03,.65),(-1.03,.55)]
        verts = [(r*cos(i*tau/sides), y, 7.43+r*sin(i*tau/sides))
                 for y,r in rings for i in range(sides)]
        faces = []
        for ring in range(2):
            for i in range(sides):
                a = ring*sides+i
                b = ring*sides+(i+1)%sides
                faces.append((a,b,b+sides,a+sides))
        faces.append(tuple(range(2*sides,3*sides)))
        # Flat hands and hour markers are painted just above the dial.
        def dial_mark(x0,z0,x1,z1,width,depth):
            direction=Vector((x1-x0,z1-z0)).normalized()
            dx,dz=-direction.y*width/2,direction.x*width/2
            start_vertex=len(verts)
            verts.extend([(x,depth,7.43+z) for x,z in
                          [(x0+dx,z0+dz),(x0-dx,z0-dz),(x1-dx,z1-dz),(x1+dx,z1+dz)]])
            faces.append(tuple(range(start_vertex,start_vertex+4)))
        for j in range(12):
            angle=j*tau/12
            dial_mark(.42*sin(angle),.42*cos(angle),.49*sin(angle),.49*cos(angle),.038,-1.035)
        dial_mark(0,0,-.23,.18,.071,-1.04)
        dial_mark(0,0,.17,.37,.060,-1.045)
        mesh=bpy.data.meshes.new("Clock face")
        mesh.from_pydata(verts,[],faces)
        clock=bpy.data.objects.new("Clock face",mesh)
        bpy.context.collection.objects.link(clock)
        painted(clock,"Cedar")
        mesh.materials.append(mats["Ivory"])
        mesh.materials.append(mats["Ink"])
        mesh.polygons[2*sides].material_index=1
        for face in list(mesh.polygons)[2*sides+1:]:
            face.material_index=2
        rot=Matrix.Rotation(k*tau/4,3,'Z')
        for obj in parts[start:]:
            obj.location=rot @ obj.location
            obj.rotation_euler=(rot @ obj.rotation_euler.to_matrix()).to_euler()
    box(0,0,8.23,2.18,2.18,.19,"Ivory")
    dome = [(8.31,1.12),(8.49,1.12)]
    for i in range(1,5):
        angle=i*tau/16
        dome.append((8.49+1.08*sin(angle),max(.04,1.1*cos(angle))))
    turned_profile(0,0,dome,16,"Patina")
    cone(0,0,9.83,.14,.028,.60,"Brass")


def striped_awning(w, y, z, color):
    # Join each stripe's slope to the valance, closing only the canopy ends.
    section = [(y,z+.24),(y-1.41,z-.19),(y-1.41,z-.42),
               (y-1.33,z-.42),(y-1.33,z-.25),(y,z+.15)]
    verts = [(w*(i/15-.5),v,h) for i in range(16) for v,h in section]
    faces, colors = [], []
    for i in range(15):
        for j in range(6):
            a,b = i*6+j,i*6+(j+1)%6
            faces.append((a,b,b+6,a+6))
            colors.append(i%2)
    faces.extend([tuple(reversed(range(6))),tuple(range(90,96))])
    mesh=bpy.data.meshes.new("Striped canopy")
    mesh.from_pydata(verts,[],faces)
    obj=bpy.data.objects.new("Striped canopy",mesh)
    bpy.context.collection.objects.link(obj)
    painted(obj,color)
    mesh.materials.append(mats["Ivory"])
    for face,index in zip(mesh.polygons,colors):
        face.material_index=index


def bookshop():
    shell(6.4,5.6,3.52,"Mint")
    gable(6.4,5.6,3.54,1.76,"DeepTeal","Mint",standing_seams=True)
    shopfront(6.4,5.6)
    sign("TIDETABLE  BOOKS",-2.98,3.45,.32,4.35)
    window(0,-2.86,4.36,.89,.83)
    box(-1.64,1.36,5.02,.68,.73,1.47,"Clay")
    box(-1.64,1.36,5.78,.84,.86,.15,"Kiln")
    for x in (-2.07,2.07):
        for j in range(7):
            height=.27+.086*(j%3)
            box(x+(j-3)*.15,-2.97,1.10+height/2,.13,.07,height,
                ["Butter","Cedar","Mint","Vermilion"][j%4])


def post_office():
    w, d = 3.3, 5.4
    face = -d/2
    shell(w, d, 5.18, "Butter")
    flat_roof(0, 0, 5.18, w, d)
    # A shallow arched parapet frames the upper sash above the mail counter.
    for x in (-1.48, 1.48):
        box(x, face-.09, 2.93, .22, .22, 5.24, "Ivory")
        box(x, face-.10, 5.56, .34, .36, .16, "Cream")
    window(0, face-.10, 4.28, 1.35, 1.40)
    for j in range(12):
        a, b = j*tau/24, (j+1)*tau/24
        rod((1.36*cos(a), face-.13, 5.13+.64*sin(a)),
            (1.36*cos(b), face-.13, 5.13+.64*sin(b)), .14, "Ivory", .21)
    retail_bay(-.63, face-.06, 1.36, door=True)
    window(.79, face-.07, 1.81, 1.05, 1.30)
    sign("POST  OFFICE", face-.24, 3.10, .29, 2.85)
    # Freestanding pillar box with a projecting cap and letter slot.
    x, y = 1.10, face-.49
    cone(x, y, .12, .29, .26, .24, "Ink")
    cone(x, y, .71, .23, .23, 1.04, "Signal")
    cone(x, y, 1.28, .29, .19, .15, "Signal")
    box(x, y-.22, .98, .23, .05, .065, "Ink")


def florist():
    w,d=6.6,5.8
    box(0,0,3.04,w,d,6.08,"Mortar")
    brick_skin(w,d,5.93, length=.87, course=.29)
    flat_roof(0,0,6.06,w,d)
    for x in (-1.62,1.62):
        window(x,-2.96,4.84,1.45,1.36)
        box(x,-3.09,4.10,1.66,.43,.26,"Leaf")
    shopfront(w,d)
    striped_awning(w+.14,-3,3.46,"Vermilion")
    sign("POPPY  &  STEM",-3.34,3.88,.27,3.40)
    for x in (-2.24,2.24):
        hall_planter(x,-3.43)
    for z,width in [(6.33,5.80),(6.69,4.88),(7.05,3.96)]:
        box(0,-2.74,z,width,.46,.36,"Clay")
        box(0,-2.74,z+.18,width+.14,.54,.09,"Cream")


def fish_market():
    w,d=6.2,5.4
    shell(w,d,3.94,"Lagoon")
    flat_roof(0,0,3.94,w,d)
    # An arched false front carrying a gilded salmon silhouette.
    profile = []
    for j in range(17):
        x=w*(j/16-.5)
        profile.append((x,4.29+1.10*(1-(2*x/w)**2)))
    outline_top = [(-w/2,3.95),(w/2,3.95)] + list(reversed(profile))
    count = len(outline_top)
    verts = [(x,y,z) for y in (-2.82,-2.54) for x,z in outline_top]
    faces = [tuple(range(count)),tuple(reversed(range(count,2*count)))]
    faces.extend((i,i+count,(i+1)%count+count,(i+1)%count) for i in range(count))
    mesh=bpy.data.meshes.new("Market parapet")
    mesh.from_pydata(verts,[],faces)
    parapet=bpy.data.objects.new("Market parapet",mesh)
    bpy.context.collection.objects.link(parapet)
    painted(parapet,"DeepTeal")
    for (x,z),(nx,nz) in zip(profile,profile[1:]):
        rod((x,-2.68,z),(nx,-2.68,nz),.12,"Mint",.36)
    outline=[(-1.18,.02),(-1.59,.35),(-1.48,0),(-1.59,-.35),
             (-1.09,-.10),(-.41,-.33),(.39,-.31),(1.07,-.12),
             (1.35,.07),(.93,.27),(.39,.34),(-.13,.32),(-.57,.53),(-.51,.26)]
    mesh=bpy.data.meshes.new("Salmon")
    mesh.from_pydata([(x,-2.86,4.62+z) for x,z in outline],[],[tuple(range(len(outline)))])
    fish=bpy.data.objects.new("Salmon",mesh)
    bpy.context.collection.objects.link(fish)
    painted(fish,"Brass")
    eye=cone(.85,-2.90,4.74,.065,.065,.045,"Ink")
    eye.rotation_euler.x=tau/4
    shopfront(w,d)
    striped_awning(w+.12,-2.76,3.38,"Mint")
    for x in (-2.34,2.30):
        cone(x,-3.20,.40,.36,.40,.78,"Cedar")
        for z in (.17,.64):
            cone(x,-3.20,z,.40,.40,.055,"Ink")


def export(name, build, offset):
    parts.clear()
    build()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+".glb")),use_selection=True)
    obj.location=offset

OUT.mkdir(parents=True,exist_ok=True)
pair = "--waterfront-pair" in sys.argv
study = "waterfront_pair" if pair else "coastal_shops"
lineup = ([("harbor_inn",harbor_inn,-7),("glass_hall",glass_hall,7)] if pair else
          [("salt_and_rye",bakery,-11),("sound_chandlery",chandlery,0),("tideline_cafe",cafe,11)])
restaurants = "--pier-restaurants" in sys.argv
if restaurants:
    study = "pier_restaurants"
    lineup = [("sea_glass_grill", sea_glass_grill, -8.6), ("red_net_kitchen", red_net_kitchen, 8.6)]
trio = "--commercial-trio" in sys.argv
if trio:
    study = "commercial_trio"
    lineup = [("brick_mercantile",mercantile,-13.3),("sunset_terrace",sunset_terrace,0),
              ("harbor_office",harbor_office,14.0)]
main_street = "--main-street-pair" in sys.argv
if main_street:
    study = "main_street_pair"
    lineup = [("seafoam_cafe",seafoam_cafe,-5.95),("brick_mercantile",mercantile,5.95)]
if square:
    study = "town_square"
    lineup = [("city_hall",city_hall,-11.2),("tidetable_books",bookshop,.1),
              ("post_office",post_office,5.65),("poppy_and_stem",florist,11.0),
              ("sound_fish_market",fish_market,17.81)]
for name,build,x in lineup:
    export(name,build,(x,0,0))
    if main_street:
        bpy.context.object.rotation_euler.z = -.13 if name=="seafoam_cafe" else .14
    if restaurants:
        bpy.context.object.rotation_euler.z = -.25 if name=="sea_glass_grill" else .17

scene=bpy.context.scene
def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(10,-56,11 if main_street else 15 if trio else 8 if restaurants else 16 if pair else 22))
camera=bpy.context.object
aim(camera,(0,-.5,4.0 if main_street else 3.7 if trio else 2.1 if restaurants else 3.65 if pair else 2.6))
camera.data.type='ORTHO'
camera.data.ortho_scale=24.4 if main_street else 42.8 if trio else 36 if restaurants else 30 if pair else 35
if square:
    camera.location=(-12,-58,20)
    aim(camera,(1.95,-.7,3.9))
    camera.data.ortho_scale=42.5
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.samples=12
scene.cycles.use_denoising=True
scene.world=bpy.data.worlds.new("Overcast coast")
scene.world.color=(.65,.65,.65)
bpy.ops.object.light_add(type='AREA',location=(-12,-17,28))
light=bpy.context.object
light.data.energy=14500
light.data.shape='DISK'
light.data.size=15
aim(light,(0,0,0))
box(0,0,-1.75 if restaurants else -.16,420 if restaurants or trio or main_street or square else 90,420 if restaurants or trio or main_street or square else 90,.3,"Water" if restaurants else "Ivory" if trio or main_street or square else "Oyster")
if restaurants:
    water=mats["Water"].node_tree
    surface=water.nodes.get("Principled BSDF")
    surface.inputs["Roughness"].default_value=.24
    ripple=water.nodes.new("ShaderNodeTexNoise")
    coords=water.nodes.new("ShaderNodeTexCoord")
    water.links.new(coords.outputs["Generated"],ripple.inputs["Vector"])
    ripple.inputs["Scale"].default_value=150
    ripple.inputs["Detail"].default_value=1.6
    bump=water.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=.20
    bump.inputs["Distance"].default_value=.06
    water.links.new(ripple.outputs["Fac"],bump.inputs["Height"])
    water.links.new(bump.outputs["Normal"],surface.inputs["Normal"])
if restaurants:
    scene.view_settings.view_transform="AgX"
    scene.view_settings.exposure=.55
scene.render.resolution_x=2000 if trio else 1800 if restaurants else 1600
scene.render.resolution_y=780 if main_street else 700 if trio else 680 if restaurants else 730 if pair else 590
if square:
    scene.render.resolution_x,scene.render.resolution_y=1600,700
scene.render.resolution_percentage=100
scene.render.filepath=str(ROOT/'art'/f'{study}_preview.png')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art'/f'{study}.blend'))
bpy.ops.render.render(write_still=True)
