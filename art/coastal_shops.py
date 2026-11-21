"""Run with blender -b -P art/coastal_shops.py. Append -- --waterfront-pair or -- --pier-restaurants to build either pair."""
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
    "Dock": "ac865e", "Pile": "776351", "Slate": "415269", "Water": "477f8c",
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
    obj.data.body = words
    obj.data.align_x = obj.data.align_y = 'CENTER'
    obj.data.size = size
    obj.data.space_character = 1.14
    bpy.ops.object.convert(target='MESH')
    painted(obj, "Ivory")

def window(x,y,z,w,h,side=False):
    def panel(dx, dy, dz, a,b,c, color):
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
    for j in range(5):
        dx = x+(j-2)*.22
        cone(dx,y,.89,.23,.16,.24,"Leaf",7)
        cone(dx,y-.07,.99,.12,.09,.14,"Bloom" if j%2 else "Brass",6)

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
        for x in [-6.78,-3.46,0,3.46,6.78]:
            box(x,y,-4.68,.35,.38,9.2,"Pile")
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


def pendant(x,y,top,drop):
    box(x,y,top-drop/2,.028,.03,drop,"Ink")
    cone(x,y,top-drop-.09,.105,.052,.18,"Brass",8)


def dining_tables(xs,fabric):
    for x in xs:
        start=len(parts)
        patio_table(x,-4.53,fabric)
        # The land version stands on a raised sidewalk.
        for obj in parts[start:]:
            obj.location.z-=.28


def sea_glass_grill():
    dining_pier()
    w,d=9.50,5.70
    shell(w,d,3.33,"Pearl")
    shopfront(w,d)
    gable(w,d,3.35,2.60,"Lagoon","Glass",standing_seams=True)
    for x in [-3.14,-1.55,0,1.55,3.14]:
        rise=2.60*(1-abs(x)/(w/2))
        box(x,-d/2-.064,3.35+rise/2,.12,.14,rise,"Ivory")
    box(0,-d/2-.09,3.37,w,.18,.16,"Ivory")
    for x in [-2.35,-.75,.75,2.35]:
        pendant(x,-2.97,5.88-abs(x)*.55,.44)
    for x,y in [(-2.9,1.3),(1.8,1.1),(3.45,.40)]:
        z=5.95-abs(x)*2.60/(w/2)
        cone(x,y,z+.25,.17,.17,.74,"Oyster")
        cone(x,y,z+.62,.24,.23,.18,"Ink")
    dining_tables([-4.54,-1.12,2.48],"Lagoon")
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
    shell(w,d,3.61,"Signal")
    shopfront(w,d)
    # A broad transverse roof behind the projecting entrance gable.
    start=len(parts)
    gable(d,w,3.63,1.71,"Slate","Signal",standing_seams=True)
    turn=Matrix.Rotation(tau/4,3,'Z')
    for obj in parts[start:]:
        x,y,_=obj.location
        obj.location.x,obj.location.y=-y,x
        obj.rotation_euler=(turn @ obj.rotation_euler.to_matrix()).to_euler()
    box(-.75,-2.88,1.84,5.45,.93,3.68,"Signal")
    start=len(parts)
    gable(5.45,3.53,3.70,2.05,"Slate","Signal",standing_seams=True)
    for obj in parts[start:]:
        obj.location.x-=.75
        obj.location.y-=1.58
    window(-.75,-3.39,2.07,3.65,2.84)
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
        pendant(x,-3.52,4.87-.61*abs(x+.75),.31)
    box(3.38,.49,5.18,.66,.68,2.06,"Signal")
    box(3.38,.49,6.22,.78,.80,.12,"Ivory")
    box(3.38,.49,6.40,.57,.59,.29,"Ink")
    box(3.38,.49,6.59,.80,.82,.11,"Slate")
    dining_tables([-4.82,-2.03,3.85],"Marigold")
    for x in [.72,5.95]:
        rail_flowers(x)
    life_ring(-2.21,-6.05,.51)
    for x in [4.17,5.25]:
        crab_pot(x,-5.28,0)
    crab_pot(4.74,-5.28,.66)


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
for name,build,x in lineup:
    export(name,build,(x,0,0))

scene=bpy.context.scene
def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(13,-48,16 if pair or restaurants else 22))
camera=bpy.context.object
aim(camera,(0,-.5,2.1 if restaurants else 3.65 if pair else 2.6))
camera.data.type='ORTHO'
camera.data.ortho_scale=36 if restaurants else 30 if pair else 35
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
box(0,0,-1.75 if restaurants else -.16,90,90,.3,"Water" if restaurants else "Oyster")
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
scene.render.resolution_x=1600
scene.render.resolution_y=680 if restaurants else 730 if pair else 590
scene.render.resolution_percentage=100
scene.render.filepath=str(ROOT/'art'/f'{study}_preview.png')
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'art'/f'{study}.blend'))
bpy.ops.render.render(write_still=True)
