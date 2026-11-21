"""Build the Tideways river fleet in an empty Blender session.

blender -b -noaudio --factory-startup --python art/pusher_mid.py
Dimensions are metres. Work in (bow, port, up), with +Z forward on GLB export.
"""
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
TAU = math.tau
CREAM, NAVY, RED = "eee3bd", "243c50", "a44332"
DECK, EDGE, RUBBER, GLASS = "66766c", "879184", "272e31", "304858"
STEEL, YELLOW, ORANGE = "535e61", "d59c46", "de602f"
OXIDE, IRON = "875344", "454f50"

# A mesh per useful modelling part, with flat normals and the same vertex-colour
# convention as the escort tug. Each solid shares its vertices across its faces.
def blender_point(v):
    x, y, z = v
    return (y, -x, z)


class Part:
    def __init__(self, name):
        self.name = name
        self.vertices = []
        self.faces = []
        self.colors = []

    def vertex(self, point):
        self.vertices.append(blender_point(point))
        return len(self.vertices) - 1

    def face(self, indices, color):
        self.faces.append(indices)
        self.colors.append(color)

    def loft(self, rings, color, top=None, close=False):
        rows = [[self.vertex(p) for p in ring] for ring in rings]
        for j in range(len(rows) if close else len(rows) - 1):
            a, b = rows[j], rows[(j + 1) % len(rows)]
            for i in range(len(a)):
                k = (i + 1) % len(a)
                self.face((a[i], a[k], b[k], b[i]), color(j, i) if callable(color) else color)
        if not close:
            self.face(rows[0][::-1], top or color)
            self.face(rows[-1], top or color)

    def finish(self, collection, material):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        colors = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
        for poly, code in zip(mesh.polygons, self.colors):
            rgb = bytes.fromhex(code)
            rgba = (*[c / 255 for c in rgb], 1)
            for i in poly.loop_indices:
                colors.data[i].color_srgb = rgba
        mesh.materials.append(material)
        obj = bpy.data.objects.new(self.name, mesh)
        collection.objects.link(obj)
        return obj


def rect(cx, cy, z, length, width, corner=0):
    a, b = length / 2, width / 2
    if corner:
        c = min(corner, a * 0.9, b * 0.9)
        outline = [(-a+c,-b),(a-c,-b),(a,-b+c),(a,b-c),(a-c,b),(-a+c,b),(-a,b-c),(-a,-b+c)]
    else:
        outline = [(-a,-b),(a,-b),(a,b),(-a,b)]
    return [(cx+x, cy+y, z) for x,y in outline]


def block(part, x, y, bottom, length, width, height, color, corner=0):
    part.loft([rect(x,y,z,length,width,corner) for z in (bottom,bottom+height)], color)


def round_ring(c, axis, radius, count):
    axis = Vector(axis).normalized()
    u = axis.orthogonal().normalized()
    v = axis.cross(u)
    return [Vector(c) + radius * (u * math.cos(TAU*i/count) + v * math.sin(TAU*i/count)) for i in range(count)]


def pipe(part, a, b, radius, color, count=8, tip=None):
    axis = Vector(b) - Vector(a)
    part.loft([round_ring(a,axis,radius,count), round_ring(b,axis,radius if tip is None else tip,count)], color)


def ring_face(part, center, axis, outer, inner, color, count):
    outer_ids = [part.vertex(v) for v in round_ring(center,axis,outer,count)]
    inner_ids = [part.vertex(v) for v in round_ring(center,axis,inner,count)]
    for i in range(count):
        k=(i+1)%count
        part.face((outer_ids[i],outer_ids[k],inner_ids[k],inner_ids[i]),color)


def annulus(part, c, axis, radius, bore, width, color, end=None, count=16):
    axis = Vector(axis).normalized()
    lo, hi = Vector(c)-axis*width/2, Vector(c)+axis*width/2
    rings = [round_ring(p,axis,r,count) for p,r in ((lo,radius),(hi,radius),(hi,bore),(lo,bore))]
    part.loft(rings, lambda row,i: (end or color) if row in (1,3) else color, close=True)


def rail(part, points, height, color=CREAM):
    for x,y,z in points:
        pipe(part,(x,y,z),(x,y,z+height),0.043,color,6)
    for a,b in zip(points,points[1:]):
        for h in (height*0.47,height):
            pipe(part,(a[0],a[1],a[2]+h),(b[0],b[1],b[2]+h),0.032,color,6)


def bollards(part,x,y,z):
    block(part,x,y,z,1.12,0.51,0.09,STEEL,0.07)
    for dx in (-0.30,0.30):
        pipe(part,(x+dx,y,z+0.08),(x+dx,y,z+0.50),0.14,IRON)
        pipe(part,(x+dx,y,z+0.50),(x+dx,y,z+0.57),0.19,YELLOW)


def pusher():
    hull, house, fittings = Part("Hull and push knees"), Part("Pilothouse"), Part("Deck machinery")
    # A blunt working bow, long parallel sides and a tucked-under stern.
    layers = [(-1.45,-0.2,13.6,4.65),(-0.65,0,15.4,5.65),(0.04,0,16.15,6.10),
              (1.05,0,16.4,6.30),(1.32,0,16.4,6.30),(1.42,0,16.4,6.30)]
    hull.loft([rect(x,0,z,l,w,0.78) for z,x,l,w in layers],
              lambda j,i: [RED,RED,NAVY,RUBBER,CREAM][j],top=DECK)
    for side in (-1,1):
        y = side*2.04
        # Box-section push knees with triangular backing webs and layered rubber faces.
        for dy in (-0.25,0.25):
            profile = [(5.75,1.42),(7.99,1.42),(7.99,3.89),(7.58,3.89)]
            hull.loft([[(x,sy,z) for x,z in reversed(profile)] for sy in (y+dy-0.07,y+dy+0.07)],NAVY)
        block(hull,7.93,y,0.58,0.54,0.87,3.35,YELLOW,0.06)
        for i in range(5):
            block(hull,8.15,y,0.62+i*0.66,0.46,0.96,0.59,RUBBER,0.07)
        for x in (-6.2,-2.3,2.65):
            annulus(fittings,(x,side*3.15,0.80),(0,side,0),0.46,0.22,0.21,RUBBER, count=12)
            pipe(fittings,(x,side*3.22,1.21),(x+0.08,side*3.03,1.49),0.035,STEEL,5)
        bollards(fittings,-6.7,side*2.1,1.42)
        bollards(fittings,5.45,side*2.15,1.42)
        rail(fittings,[(-6.65,side*2.92,1.42),(-4.7,side*2.96,1.42),(-2.65,side*2.96,1.42)],0.88)
    # Low engine casing and the taller wheelhouse tower give a clear view over a load.
    block(house,-0.95,0,1.42,9.4,4.35,2.27,CREAM,0.30)
    block(house,-0.95,0,3.69,9.65,4.53,0.16,NAVY,0.32)
    block(house,1.18,0,3.85,3.18,2.93,1.74,CREAM,0.16)
    for side in (-1,1):
        for x in (-4.45,-3.73,-3.01):
            block(house,x,side*2.18,2.04,0.52,0.07,1.08,STEEL)
            for k in range(4):
                block(house,x,side*2.23,2.12+0.23*k,0.49,0.075,0.055,EDGE)
        for x in (0.03,1.24,2.48):
            block(house,x,side*2.18,2.61,0.84,0.065,0.64,GLASS,0.02)
        block(house,-1.12,side*2.20,1.54,0.83,0.08,1.79,"bdc0ab")
        block(house,-1.12,side*2.25,2.64,0.53,0.035,0.48,GLASS)
        annulus(fittings,(-2.12,side*2.23,2.71),(0,side,0),0.36,0.22,0.12,ORANGE,CREAM,12)
        for cx in (0.58,1.64):
            pipe(house,(cx,side*1.455,4.76),(cx,side*1.492,4.76),0.23,NAVY,10)
            pipe(house,(cx,side*1.492,4.76),(cx,side*1.51,4.76),0.165,GLASS,10)
        pipe(fittings,(-0.64,side*1.79,3.85),(0.07,side*1.79,5.57),0.105,CREAM)
        # Aft stack pair with black exhaust throats and the escort tug's white bands.
        fx,fy=-3.35,side*1.30
        tiers=[(3.85,0),(4.98,-0.13),(5.22,-0.16),(5.66,-0.23),(5.95,-0.27)]
        house.loft([rect(fx+dx,fy,z,1.14,0.66,0.18) for z,dx in tiers],
                   lambda j,i:[RED,CREAM,RED,RUBBER][j],top=RUBBER)
        annulus(fittings,(fx-0.30,fy,6.06),(0,0,1),0.23,0.155,0.24,IRON)
        rail(fittings,[(-5.28,side*2.0,3.85),(-3.38,side*2.0,3.85),(-1.46,side*2.0,3.85)],0.78)
    block(house,1.25,0,5.56,4.47,4.51,0.16,NAVY,0.32)
    tiers=[(5.72,1.29,3.72,3.74),(6.31,1.29,3.72,3.74),(7.37,1.39,3.96,4.02)]
    rings=[rect(cx,0,z,l,w,0.44) for z,cx,l,w in tiers]
    house.loft(rings,lambda j,i: CREAM if j==0 else GLASS,top=CREAM)
    for i in range(8):
        a,b=Vector(rings[1][i]),Vector(rings[2][i])
        pipe(house,a,b,0.068,CREAM,6)
        a2,b2=Vector(rings[1][(i+1)%8]),Vector(rings[2][(i+1)%8])
        if (a-a2).length>2.0:
            for t in (0.33,0.67):
                pipe(house,a.lerp(a2,t),b.lerp(b2,t),0.046,CREAM,6)
    block(house,1.47,0,7.37,4.38,4.39,0.18,CREAM,0.52)
    block(house,1.47,0,7.55,4.39,4.40,0.08,RED,0.52)
    for s,color in ((1,"cf4336"),(-1,"4e9467")):
        block(fittings,2.38,s*2,6.0,0.49,0.23,0.19,color)
    pipe(fittings,(0.84,0,7.63),(0.84,0,10.05),0.11,CREAM,8,0.055)
    pipe(fittings,(0.84,-0.88,8.81),(0.84,0.88,8.81),0.052,CREAM)
    block(fittings,0.84,0,8.17,0.71,0.80,0.09,STEEL)
    pipe(fittings,(0.84,0,8.26),(0.84,0,8.54),0.15,CREAM)
    block(fittings,0.84,0,8.54,0.24,1.77,0.105,CREAM)
    for z in (9.22,9.59,9.96):
        pipe(fittings,(0.84,0,z),(0.84,0,z+0.16),0.12,"e8cf95")
    # Access ladder and facing winches on the foredeck.
    for y in (-0.31,0.31):
        pipe(fittings,(2.91,y,3.85),(2.91,y,5.82),0.043,STEEL)
    for i in range(6):
        pipe(fittings,(2.91,-0.31,4.08+0.29*i),(2.91,0.31,4.08+0.29*i),0.039,STEEL)
    for y in (-1.06,1.06):
        block(fittings,4.75,y,1.42,1.18,1.17,0.16,IRON,0.12)
        pipe(fittings,(4.75,y-0.49,1.96),(4.75,y+0.49,1.96),0.34,"7a7260",12)
        for dy in (-0.52,0.52):
            pipe(fittings,(4.75,y+dy-0.055,1.96),(4.75,y+dy+0.055,1.96),0.46,YELLOW,12)
    return [hull,house,fittings]


def barge(cargo, high_sides):
    hull=Part("Steel scow")
    tiers=[(-1.55,-0.24,21.4,6.38),(-0.55,-0.18,23.05,7.05),
           (0.08,0,24,7.48),(0.94,0,24,7.48),(1.06,0,24,7.48)]
    hull.loft([rect(cx,0,z,l,w,0.43) for z,cx,l,w in tiers],
              lambda j,i:[OXIDE,OXIDE,"3d5356",IRON][j],top="746e5e")
    rim=1.03 if high_sides else 0.28
    for s in (-1,1):
        y=s*3.10
        block(hull,0,y,1.06,19.45,0.18,rim,OXIDE)
        block(hull,0,y,1.06+rim,19.6,0.27,0.11,"a77858")
        for x in range(-9,10,2):
            block(hull,x,y+s*0.13,1.06,0.105,0.16,rim,IRON)
        for x in (-10.65,10.65):
            bollards(hull,x,s*2.56,1.06)
        for x in (-9.9,-5,0,5,9.9):
            block(hull,x,s*3.75,0.38,0.28,0.18,0.64,RUBBER,0.045)
        for x in (-10.9,10.9):
            for i in range(4):
                block(hull,x,s*3.747,0.14+0.15*i,0.22 if i%2 else 0.38,0.02,0.047,"d5cba7")
        block(hull,s*9.64,0,1.06,0.16,6.2,rim,OXIDE)
        block(hull,s*9.64,0,1.06+rim,0.24,6.24,0.11,"a77858")
        block(hull,s*10.58,0,1.06,1.04,1.2,0.12,IRON,0.12)
    return [hull,cargo]


def gravel():
    p=Part("Gravel")
    rng=random.Random(41)
    tones=["88867b","99978a","96948a","a3a094","8e8f86","ada99c"]
    rows=[]
    # A continuous spill of aggregate with three overlapping dump peaks.
    for i in range(24):
        row=[]
        for j in range(10):
            x=-9.50+19*i/23
            y=-2.95+5.9*j/9
            if i not in (0,23): x+=rng.uniform(-0.28,0.28)
            if j not in (0,9): y+=rng.uniform(-0.18,0.18)
            h=max(height-0.60*math.hypot((x-cx)*0.86,y-cy) for cx,cy,height in
                  [(-6.24,-0.3,2.85),(-1.22,0.50,3.43),(4.95,-0.35,3.18)])
            h=min(h,0.77+0.88*(2.95-abs(y)),0.72+0.83*(9.5-abs(x)))
            row.append(p.vertex((x,y,1.08+max(0.51,h+rng.uniform(-0.16,0.16)))))
        rows.append(row)
    for a,b in zip(rows,rows[1:]):
        for j in range(9):
            quad=[a[j],b[j],b[j+1],a[j+1]]
            if rng.random()<0.5: quad=quad[1:]+quad[:1]
            for tri in (quad[:3],(quad[0],quad[2],quad[3])):
                p.face(tri,rng.choice(tones))
    # Skirt the pile down to the bed inside the coaming.
    edge=rows[0]+[r[-1] for r in rows[1:]]+rows[-1][-2::-1]+[r[0] for r in rows[-2:0:-1]]
    for i,v in enumerate(edge):
        w=edge[(i+1)%len(edge)]
        base=[]
        for k in (v,w):
            y,nx,_=p.vertices[k]
            base.append(p.vertex((-nx,y,1.06)))
        p.face((v,w,base[1],base[0]),tones[0])
    return p


def scrap():
    p=Part("Crushed car bodies")
    rng=random.Random(76)
    paints=["a65240","638689","b9b4a0","76829a","c69757","71826a","8c615c"]
    for level in range(3):
        for row in range(4):
            for col in range(3):
                if level==2 and (row,col) in ((0,2),(2,0),(3,1),(1,0),(3,0)): continue
                cx=(row-1.5)*4.52+rng.uniform(-0.17,0.17)
                cy=(col-1)*1.89+rng.uniform(-0.06,0.06)
                z=1.10+level*0.69
                angle=rng.uniform(-0.10,0.10)+rng.choice((0,math.pi))
                slope=rng.uniform(-0.05,0.05)
                dent=rng.uniform(0.15,0.32)
                dent_x=rng.uniform(-0.7,0.75)
                # A press creases high panels most, with a separate fold across the bonnet.
                def at(x,y,h):
                    h-=max(0,h-0.38)*dent*(1+0.6*y)
                    h+=0.105*max(0,1-abs(x-1.62)*3)*(0.7+y)

                    return (cx+x*math.cos(angle)-y*math.sin(angle),cy+x*math.sin(angle)+y*math.cos(angle),z+h+slope*x)
                def shell(layers,colors,cap):
                    rings=[[at(x,y,h) for x,y,_ in rect(dx,0,0,l,w,c)] for h,dx,l,w,c in layers]
                    p.loft(rings,lambda j,i: colors[j],top=cap)
                paint=rng.choice(paints)
                shell([(0,0,3.63,1.44,0.22),(0.14,0,3.99,1.65,0.23),(0.41,0,4.07,1.65,0.30),
                       (0.53,0.05,3.82,1.50,0.28)],[RUBBER,paint,paint],paint)
                # Buckled cabins with a surviving ribbon of glazing, pillars and exposed wheels.
                dx=rng.uniform(-0.29,0.06)
                shell([(0.49,dx,2.41,1.48,0.16),(0.69,dx-0.06,1.75,1.28,0.15),
                       (0.79,dx-0.10,1.65,1.26,0.15)],[GLASS,paint],paint)
                # Split the roof across a torn ridge. Raw inner metal shows at the split.
                roof_edges = [(-0.83,-0.80,0.798,0.798),
                              (dent_x*0.45-0.11,dent_x*0.38+0.14,0.94,0.83),
                              (dent_x*0.45-0.02,dent_x*0.38+0.23,0.80,0.802),
                              (0.68,0.71,0.80,0.80)]
                strips = [[p.vertex(at(dx+lx,-0.54,lh)),p.vertex(at(dx+rx,0.54,rh))]
                          for lx,rx,lh,rh in roof_edges]
                for j in range(3):
                    a,b = strips[j],strips[j+1]
                    p.face((a[0],b[0],b[1],a[1]),"a19a87" if j==1 else paint)
                for side in (-1,1):
                    pipe(p,at(dx+0.06,side*0.74,0.50),at(dx+0.04,side*0.645,0.69),0.052,paint,5)
                    for x in (-1.27,1.23):
                        pipe(p,at(x,side*0.78,0.20),at(x,side*0.86,0.20),0.216,RUBBER,9)
                        pipe(p,at(x,side*0.86,0.20),at(x,side*0.875,0.20),0.112,"a39e8e",8)
                for y in (-0.48,0.48):
                    pipe(p,at(1.96,y,0.35),at(1.99,y,0.35),0.092,"d4c8a6",6)
    return p


def timber():
    p=Part("Lashed sawlogs")
    rng=random.Random(55)
    for cx in (-4.72,4.72):
        for level,n in enumerate((6,5,4)):
            for j in range(n):
                y=(j-(n-1)/2)*0.89
                z=1.55+level*0.73
                r=rng.uniform(0.45,0.49)
                a=Vector((cx-4.58+rng.uniform(0,0.40),y,z))
                b=Vector((cx+4.58-rng.uniform(0,0.35),y+rng.uniform(-0.09,0.09),z+rng.uniform(-0.07,0.07)))
                axis=(b-a).normalized()
                bark=rng.choice(["705344","805c43","896744","68513e"])
                p.loft([round_ring(a,axis,r,9),round_ring(b,axis,r*0.9,9)],bark,top="d2ab77")
                for end,sgn,rad in ((a,-1,r),(b,1,r*0.9)):
                    heart=end+axis*sgn*0.008
                    pipe(p,heart,heart+axis*sgn*0.008,rad*rng.uniform(0.49,0.69),"b58b5e",9)
        for x in (cx-2.75,cx+2.75):
            for s in (-1,1):
                block(p,x,s*2.83,1.06,0.20,0.17,2.72,OXIDE)
            path=[(x,-2.82,1.67),(x,-2.68,2.26),(x,-1.80,3.35),(x,-1.39,3.48),
                  (x,1.39,3.48),(x,1.80,3.35),(x,2.68,2.26),(x,2.82,1.67)]
            for a,b in zip(path,path[1:]): pipe(p,a,b,0.055,IRON,6)
    return p


def coils():
    p=Part("Banded steel coils")
    for j,x in enumerate((-7.08,-3.54,0,3.54,7.08)):
        for i,y in enumerate((-1.35,1.35)):
            r=(1.34,1.43,1.38)[(i+j)%3]
            for dx in (-0.72,0.72):
                block(p,x+dx,y,1.06,0.43,2.19,0.32,"9e7d54",0.06)
            center=(x,y,1.21+r)
            annulus(p,center,(0,1,0),r,0.46,1.94,"697d87","a7b3b3",24)
            for s in (-1,1):
                # Concentric wraps on the exposed ends and two binding straps over the roll.
                for ring in (0.66,0.89,r-0.12):
                    ring_face(p,(x,y+s*0.978,center[2]),(0,s,0),ring,ring-0.032,"74868a",24)
                annulus(p,(x,y+s*0.57,center[2]),(0,1,0),r+0.021,r-0.002,0.105,"485858",count=24)
    return p


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat=bpy.data.materials.new("Fleet vertex paint")
    mat.use_nodes=True
    node=mat.node_tree.nodes.new("ShaderNodeVertexColor")
    node.layer_name="Col"
    shader=mat.node_tree.nodes.get("Principled BSDF")
    mat.node_tree.links.new(node.outputs["Color"],shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value=0.84
    fleet=[("pusher",pusher()),("barge_gravel",barge(gravel(),True)),
           ("barge_scrap",barge(scrap(),True)),("barge_logs",barge(timber(),False)),
           ("barge_coils",barge(coils(),False))]
    for index,(name,parts) in enumerate(fleet):
        collection=bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
        bpy.ops.object.select_all(action="DESELECT")
        objects=[part.finish(collection,mat) for part in parts]
        for ob in objects: ob.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(ROOT/"assets"/"models"/(name+"_mid.glb")),
                                  export_format="GLB",use_selection=True,export_vertex_color="ACTIVE")
        # Lay the editable sources out abeam after exporting at the waterline origin.
        for ob in objects: ob.location.x=(index-2)*9
    bpy.ops.object.select_all(action="DESELECT")
    for area in bpy.context.screen.areas:
        if area.type=="VIEW_3D":
            space=area.spaces.active
            space.shading.color_type="VERTEX"
            space.overlay.show_overlays=False
            space.region_3d.view_distance=53
            space.region_3d.view_rotation=Vector((-0.77,0.93,-0.87)).to_track_quat("-Z","Y")
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/"art"/"pusher_fleet.blend"),compress=True)


if __name__=="__main__":
    build()
