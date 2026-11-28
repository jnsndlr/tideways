"""Build the three Coast Guard GLBs and their editable Blender fleet.
Run blender -b -P art/coast_guard.py. Units are metres, bow is -Y, waterline is Z=0.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ART = Path(__file__).resolve().parent
OUT = ART.parent / "assets/models/coast_guard"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)


def paint(name, rgb, metallic=0.0, roughness=0.5, coat=0.0, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if coat > 0 and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.08
    if emission is not None and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


white = paint("Warm white enamel", (.86, .89, .86), metallic=0.02, roughness=0.28, coat=0.25)
offwhite = paint("Superstructure offwhite", (.78, .81, .80), metallic=0.04, roughness=0.38, coat=0.1)
alloy = paint("Satin aluminium", (.50, .55, .57), metallic=0.72, roughness=0.34)
silver = paint("Rail tubing", (.72, .77, .79), metallic=0.88, roughness=0.22)
steel = paint("Dark marine steel", (.14, .16, .18), metallic=0.65, roughness=0.45)
black = paint("Graphite rubber", (.022, .026, .030), metallic=0.0, roughness=0.78)
deck = paint("Non-skid deck", (.072, .090, .102), metallic=0.0, roughness=0.88)
antifoul = paint("Antifouling hull red", (.24, .055, .045), metallic=0.0, roughness=0.62)
glass = paint("Storm blue glass", (.020, .068, .095), metallic=0.18, roughness=0.06, coat=0.85)
frame_dark = paint("Window gasket", (.035, .040, .045), metallic=0.1, roughness=0.65)
red = paint("International orange", (.85, .073, .018), metallic=0.0, roughness=0.30, coat=0.22)
blue = paint("Service blue", (.022, .19, .42), metallic=0.0, roughness=0.28, coat=0.22)
ink = paint("Hull lettering", (.009, .018, .028), metallic=0.0, roughness=0.45)
safety_yellow = paint("Safety yellow", (.86, .66, .04), metallic=0.0, roughness=0.38)
nav_red = paint("Nav light port", (.9, .05, .02), roughness=0.15, emission=(1.0, .08, .02), emission_strength=2.2)
nav_green = paint("Nav light stbd", (.04, .85, .18), roughness=0.15, emission=(.05, 1.0, .22), emission_strength=2.2)
nav_white = paint("Nav light white", (.95, .95, .88), roughness=0.15, emission=(1.0, .98, .90), emission_strength=2.0)
beacon_blue = paint("Law enforcement blue", (.04, .28, .95), roughness=0.12, emission=(.06, .35, 1.0), emission_strength=3.0)


def mesh(name, verts, faces, mat, smooth=False):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    if smooth:
        for p in data.polygons:
            p.use_smooth = True
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    return obj


def box(name, loc, dims, mat, bevel=0, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    for v in obj.data.vertices:
        for i, size in enumerate(dims):
            v.co[i] *= size
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Cast edges", "BEVEL")
        mod.width, mod.segments = bevel, 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cyl(name, loc, radius, depth, mat, sides=16, rot=(0, 0, 0), smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def sphere(name, loc, radius, mat, segs=16, rings=10, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings,
                                         radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    for v in obj.data.vertices:
        v.co.x *= scale[0]
        v.co.y *= scale[1]
        v.co.z *= scale[2]
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def spar(a, b, radius, mat, end=None, name="Tube", sides=10):
    v = Vector(b) - Vector(a)
    if v.length < 1e-5:
        return None
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=radius,
                                    radius2=radius if end is None else end,
                                    depth=v.length, location=(Vector(a)+Vector(b))/2)
    obj = bpy.context.object
    obj.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    obj.name = name
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def bollard(x, y, z, scale=1.0):
    box("Bollard base", (x, y, z + .04*scale), (.45*scale, .9*scale, .08*scale), steel, .015*scale)
    for dy in (-.22*scale, .22*scale):
        cyl("Bitt post", (x, y + dy, z + .24*scale), .11*scale, .36*scale, steel, 10)
        cyl("Bitt cap", (x, y + dy, z + .42*scale), .14*scale, .06*scale, steel, 10)


def liferaft_canister(x, y, z, scale=1.0, rot_z=0.0):
    cyl("Liferaft canister", (x, y, z), .38*scale, 1.25*scale, white, 14, (math.pi/2, 0, rot_z))
    for dy in (-.32*scale, .32*scale):
        dx = -math.sin(rot_z) * dy
        dyr = math.cos(rot_z) * dy
        cyl("Liferaft strap", (x + dx, y + dyr, z), .395*scale, .07*scale, black, 14, (math.pi/2, 0, rot_z))


def watertight_door(x, y, z, width, height, side, facing="X"):
    if facing == "X":
        box("Door frame", (x, y, z), (.09, width + .14, height + .14), frame_dark, .02)
        box("Door panel", (x + side*.02, y, z), (.08, width, height), offwhite, .02)
        box("Door port", (x + side*.05, y, z + height*.22), (.04, width*.42, width*.42), glass, .02)
        box("Door handle", (x + side*.07, y + width*.32, z - height*.04), (.05, .14, .05), steel)
    else:
        box("Door frame", (x, y, z), (width + .14, .09, height + .14), frame_dark, .02)
        box("Door panel", (x, y + side*.02, z), (width, .08, height), offwhite, .02)
        box("Door port", (x, y + side*.05, z + height*.22), (width*.42, .04, width*.42), glass, .02)
        box("Door handle", (x + width*.32, y + side*.07, z - height*.04), (.14, .05, .05), steel)


def hull(length, beam, height, mat, lower_mat=black):
    stations = [(-.5,.015,1.28),(-.46,.33,1.19),(-.38,.63,1.08),
                (-.26,.87,1.02),(-.10,1,1),(.16,1,1),(.36,.97,.98),(.5,.91,.98)]
    rings, faces = [], []
    for t, width, sheer in stations:
        w, y, z = width*beam/2, t*length, height*sheer
        rings.append([(-w,y,z),(w,y,z),(.87*w,y+.018*length*(t<-.49),.02*height),
                      (.65*w,y+.026*length*(t<-.49),-.34*height),
                      (0,y+.03*length*(t<-.49),-.64*height),
                      (-.65*w,y+.026*length*(t<-.49),-.34*height),
                      (-.87*w,y+.018*length*(t<-.49),.02*height)])
    for a in range(len(rings)-1):
        for j in range(7):
            k=(j+1)%7
            faces.append((7*a+j,7*a+k,7*(a+1)+k,7*(a+1)+j))
    faces += [tuple(reversed(range(7))),tuple(range(49,56))]
    obj=mesh("Chined hull",sum(rings,[]),faces,mat)
    obj.data.materials.append(deck)
    obj.data.materials.append(black)
    obj.data.materials.append(lower_mat)
    for i,p in enumerate(obj.data.polygons[:49]):
        if i%7 == 0:
            p.material_index = 1
        elif i%7 in (2, 5):
            p.material_index = 2
        elif i%7 in (3, 4):
            p.material_index = 3
        else:
            p.material_index = 0

    def edge(t):
        for (a,w,h),(b,v,k) in zip(stations,stations[1:]):
            if a <= t <= b:
                f=(t-a)/(b-a)
                return (w+(v-w)*f)*beam/2,(h+(k-h)*f)*height
        raise ValueError(t)

    # Project markings onto the triangulated shell, including across its chines.
    bpy.context.view_layer.update()
    def skin(side,y,z):
        hit, point, _, _ = obj.ray_cast(Vector((side*beam,y,z)), Vector((-side,0,0)))
        if not hit:
            raise ValueError(f"Marking outside hull at {y}, {z}")
        return (point.x+side*.002*beam,y,z)

    for side in (-1,1):
        for (a,w,h),(b,v,k) in zip(stations,stations[1:]):
            if length<20:
                spar((side*w*beam/2,a*length,h*height),(side*v*beam/2,b*length,k*height),.095,black,name="Rubbing strake")
            else:
                # Subtle bulwark cap rail along the sheer of the cutter
                spar((side*w*beam/2,a*length,h*height+.06),(side*v*beam/2,b*length,k*height+.06),.11,offwhite,name="Sheer cap")
        for t,width,m in [(-.31,.067,red),(-.243,.012,white),(-.231,.015,blue)]:
            vertices, quads = [], []
            for row in range(9):
                f=row/8
                for col in range(9):
                    q=t+width*col/8+.054*(1-f)
                    vertices.append(skin(side,q*length,edge(q)[1]*(.035+.947*f)))
                    idx=len(vertices)-1
                    if row and col:
                        quad=(idx-10,idx-9,idx,idx-1)
                        quads.append(quad if side==1 else quad[::-1])
            mesh("Service stripe",vertices,quads,m)
    return edge, obj


def house(name, lower, upper, mat, panes=0, wipers=False):
    # Cut corners give the wheelhouse wraparound quarter lights.
    def outline(spec):
        w,f,a,z=spec
        c=min(.27*w,(a-f)*.16)
        return [Vector(p) for p in [(-w+c,f,z),(w-c,f,z),(w,f+c,z),(w,a-c,z),
                (w-c,a,z),(-w+c,a,z),(-w,a-c,z),(-w,f+c,z)]]
    lo,hi=outline(lower),outline(upper)
    body = mesh(name,lo+hi,[tuple(reversed(range(8))),tuple(range(8,16))]+
         [(j,(j+1)%8,(j+1)%8+8,j+8) for j in range(8)],mat)
    if panes:
        for j in range(8):
            k=(j+1)%8
            outward=(lo[k]-lo[j]).cross(hi[j]-lo[j]).normalized()
            count=panes if j in (0,2,4,6) else 1
            for i in range(count):
                def point(u,v,off):
                    return lo[j].lerp(lo[k],u).lerp(hi[j].lerp(hi[k],u),v)+outward*off
                # Dark window gasket / frame slightly behind the glass
                fu,fv=(i+.035)/count,(i+.965)/count
                mesh("Window frame",[point(fu,.12,.010),point(fv,.12,.010),
                                     point(fv,.90,.010),point(fu,.90,.010)],[(0,1,2,3)],frame_dark)
                # Glazing pane
                u,v=(i+.065)/count,(i+.935)/count
                mesh("Bridge glazing",[point(u,.16,.020),point(v,.16,.020),
                                       point(v,.86,.020),point(u,.86,.020)],[(0,1,2,3)],glass)
                # Windshield wipers on forward panes (j == 0)
                if wipers and j == 0:
                    top_mid = point((u+v)*0.5, .86, .035)
                    blade_end = point((u+v)*0.5 + (v-u)*0.12, .40, .035)
                    spar(top_mid, blade_end, .012 if (lo[1]-lo[0]).length < 4 else .025, black, name="Wiper", sides=6)
    return body


def rail(edge,length,start,end,count,height,r, mid_rail=True):
    for s in (-1,1):
        prev_top=None
        prev_mid=None
        for i in range(count+1):
            t=start+(end-start)*i/count
            w,z=edge(t)
            top=(s*w*.965,t*length,z+height)
            mid=(s*w*.965,t*length,z+height*.52)
            spar((top[0],top[1],z),top,r,silver)
            if prev_top:
                spar(prev_top,top,r,silver)
                if mid_rail:
                    spar(prev_mid,mid,r*.75,silver)
            prev_top=top
            prev_mid=mid


def label(words, x,y,z,size,side,mat, shell=None):
    bpy.ops.object.text_add(location=(side*x,y,z),rotation=(math.pi/2,0,side*math.pi/2))
    obj=bpy.context.object
    obj.data.body=words
    obj.data.align_x="CENTER"
    obj.data.align_y="CENTER"
    obj.data.size=size
    obj.data.materials.append(mat)
    bpy.ops.object.convert(target="MESH")
    if shell is not None:
        lettering=bpy.context.object
        transform=lettering.matrix_world
        inverse=transform.inverted()
        for vertex in lettering.data.vertices:
            pos=transform@vertex.co
            hit,point,_,_=shell.ray_cast((side*100,pos.y,pos.z),(-side,0,0))
            if hit:
                pos.x=point.x+side*max(.022, size*.03)
                vertex.co=inverse@pos


def rescue_ring(x,y,z, scale=1.0):
    bpy.ops.mesh.primitive_torus_add(major_radius=.32*scale,minor_radius=.072*scale,major_segments=24,
        minor_segments=10, location=(x,y,z),rotation=(0,math.pi/2,0))
    obj=bpy.context.object
    obj.name="Life buoy"
    obj.data.materials.append(red)
    obj.data.materials.append(white)
    for p in obj.data.polygons:
        p.use_smooth = True
        if round(math.atan2(p.center.y,p.center.x)*12/math.pi)%6==0:
            p.material_index=1


def cutter():
    edge,shell=hull(127,16.5,5.8,white, lower_mat=antifoul)

    # Main superstructure & tiered stealth-faceted blocks
    house("Forward superstructure",(7.7,-23,18,5.72),(6.8,-19,17,13),white)
    house("Navigation bridge",(6.9,-19.5,-6,13),(7.7,-20.5,-5,16.1),white,6, wipers=True)
    house("Bridge visor",(8.0,-21.0,-4.6,16.1),(7.9,-20.9,-4.7,16.50),white)
    house("Bridge roof deck",(7.5,-20.0,-5.2,16.50),(7.4,-19.8,-5.4,16.75),deck)
    house("Hangar",(7.4,7,29,5.6),(6.7,8,28,12.1),white)
    house("Hangar roof",(6.5,8.5,27.5,12.1),(6.4,8.7,27.3,12.35),deck)

    # Bridge wings extending port & starboard with nav lights & wing consoles
    for s in (-1,1):
        box("Bridge wing deck",(s*8.2,-15.5,13.2),(2.2,3.4,.32),white,.06)
        box("Bridge wing bulwark",(s*9.15,-15.5,13.85),(.22,3.4,1.1),white,.04)
        box("Wing console",(s*8.65,-16.2,13.95),(.55,.65,.85),steel,.05)
        box("Nav light housing",(s*9.32,-16.8,14.35),(.28,.45,.32),black,.04)
        sphere("Nav light",(s*9.45,-16.95,14.35),.14,nav_red if s==-1 else nav_green)

    # Exhaust casings & louvered stacks
    for s in (-1,1):
        casing = house("Exhaust casing",(2.5,2,15,12),(2.1,4,15,16.4),white)
        casing.location.x=s*3.4
        # Louvered intake grilles on casing sides
        for z_louv in (13.4, 14.3, 15.2):
            box("Intake louver",(s*5.58,8.5,z_louv),(.14,5.4,.32),steel,.03)
        for y in (8,12):
            spar((s*3.4,y,16.1),(s*3.4,y+.45,17.6),1.0,black,end=.92,sides=16)
            spar((s*3.4,y+.45,17.5),(s*3.4,y+.55,17.95),1.06,steel,end=1.06,sides=16)

        # Hull lettering & bow numbers
        label("COAST GUARD",8.17,-.3,4.6,1.55,s,ink,shell)
        label("752",edge(-.34)[0]*.99,-43,5.75,1.65,s,ink,shell)

        # Anchor hawsepipe & recessed anchor pocket at bow
        ax, az = edge(-.44)
        box("Anchor pocket",(s*(ax-.05),-55.5,az-1.45),(.38,1.5,1.1),steel,.06)
        box("Anchor fluke",(s*(ax+.10),-55.4,az-1.65),(.28,.85,.75),black,.05)

        # Framed gallery ports along superstructure
        for y in (-12,-9,-6,10,13,16):
            px = s*(7.06 if y<0 else 6.98)
            box("Gallery frame",(px,y,10.7),(.18,1.06,.78),frame_dark,.04)
            box("Gallery port",(px+s*.03,y,10.7),(.18,.90,.62),glass,.05)

        # Watertight doors on superstructure sides
        watertight_door(s*7.25, -17.5, 7.3, .95, 2.05, s, "X")
        watertight_door(s*6.95, 22.0, 7.3, .95, 2.05, s, "X")

        # Liferaft canisters in cradles along superstructure
        for y in (-2.0, 1.5, 19.0):
            liferaft_canister(s*7.35, y, 7.6, scale=1.15)

        # Shipboard cutter boats (OTB) in recessed cradles with davit arms
        box("Rescue launch cradle",(s*7.15,4,8.1),(1.28,5.8,.32),deck,.12)
        box("Shipboard rescue launch",(s*7.22,4,8.58),(1.42,5.3,.64),red,.28)
        box("Launch collar",(s*7.22,4,8.68),(1.52,5.4,.22),black,.09)
        box("Launch console",(s*7.22,3.65,9.06),(.75,1.0,.52),alloy,.12)
        box("Launch windshield",(s*7.22,3.18,9.16),(.68,.12,.32),glass,.04)
        for dy in (1.5, 6.5):
            spar((s*6.4,dy,8.0),(s*7.7,dy,10.2),.14,steel,name="Davit arm")
            spar((s*7.7,dy,10.2),(s*7.7,dy,9.0),.06,black,name="Davit fall")

        # Mast tripod legs
        for y in (-5,1):
            spar((s*4,y,13),(s*.55,1.5,27),.28,steel)

    # Main mast, platforms, planar radar & yardarms
    spar((0,-2,13),(0,2,32.5),1.25,deck,.42,sides=16)
    for z,w in [(21,8.6),(25.8,6.8),(30,4.2)]:
        py = 1 + (z-21)*.09
        box("Mast platform",(0,py,z),(w,2.2,.28),deck,.05)
        for s in (-1,1):
            spar((0,py,z-2.1),(s*w*.47,py,z),.14,steel)
            # Platform safety rails
            spar((s*w*.48,py-.95,z),(s*w*.48,py-.95,z+.95),.05,silver)
            spar((s*w*.48,py+.95,z),(s*w*.48,py+.95,z+.95),.05,silver)
            spar((s*w*.48,py-.95,z+.95),(s*w*.48,py+.95,z+.95),.05,silver)
    # TRS-3D / SPS-75 planar radar array on top platform
    box("Planar radar pedestal",(0,2.0,30.6),(1.2,1.2,1.0),steel,.08)
    box("Search radar",(0,2.0,31.6),(4.2,.55,1.35),alloy,.08, rot=(.22,0,0))
    # Navigation radar crossbar on lower platform
    box("Nav radar",(0,-.2,21.55),(3.2,.32,.26),white,.06)
    # Top mast spire & masthead light
    spar((0,2,31.5),(0,2,36.2),.13,silver,.045)
    sphere("Masthead light",(0,2,36.3),.16,nav_white)
    # Twin SATCOM radomes (forward of mast on bridge roof, and aft on hangar)
    cyl("Fwd satcom pedestal",(0,-11.5,17.2),.55,1.1,white,14)
    sphere("Fwd satcom dome",(0,-11.5,18.45),1.15,white,18,12)
    cyl("Aft satcom pedestal",(0,17.5,12.8),.55,1.1,white,14)
    sphere("Aft satcom dome",(0,17.5,14.0),1.10,white,18,12)

    # Iconic Phalanx 20mm CIWS white radome on aft hangar roof
    cyl("CIWS base",(0,24.2,12.7),.95,.95,offwhite,14)
    cyl("CIWS radome body",(0,24.2,13.95),.62,1.65,white,16)
    sphere("CIWS radome cap",(0,24.2,14.78),.62,white,16,10)
    spar((0,24.8,13.8),(0,26.8,14.1),.13,steel,.09,name="CIWS barrel")

    # Aft hangar roll-up bay doors & LSO flight-deck control booth
    for s in (-1,1):
        box("Hangar door frame",(s*2.8,28.85,8.2),(4.2,.30,4.8),steel,.05)
        box("Hangar door",(s*2.8,28.95,8.2),(3.8,.22,4.4),deck,.04)
    box("LSO booth",(5.2,28.5,10.2),(1.8,1.6,1.9),white,.06)
    box("LSO glass",(5.2,29.32,10.35),(1.45,.12,1.05),glass,.03)

    # 57mm Mk 110 Naval Gun on foredeck + breakwater + mooring gear
    house("Foredeck gun cupola",(2.35,-38.2,-32.8,6.1),(1.55,-37.9,-33.3,8.85),white)
    box("Gun elevation slot",(0,-38.1,8.05),(.58,.45,1.15),black,.04)
    spar((0,-37.7,8.0),(0,-39.5,8.22),.28,steel,.24,name="Gun sleeve")
    spar((0,-39.4,8.20),(0,-43.4,8.72),.19,alloy,.11,name="Gun barrel")
    # Foredeck breakwater V-wall ahead of gun (flush with foredeck)
    for s in (-1,1):
        box("Breakwater wall",(s*1.75,-44.5,6.45),(3.8,.32,1.15),white,.04, rot=(0,0,s*-.62))
    # Anchor windlasses & bollards on foredeck
    for y in (-49.5, -29.0):
        for x in (-1.9, 1.9):
            cyl("Windlass drum",(x,y,6.72),.48,.85,steel,12)
            cyl("Windlass cap",(x,y,7.20),.56,.14,deck,12)
    for y in (-56.0, -45.0, 56.0):
        for s in (-1,1):
            bx, bz = edge(y/127)
            bollard(s*(bx - 1.1), y, bz, scale=1.15)

    # Flight deck markings (landing circle, H, lineup stripe) + safety netting
    def line(x,y):
        return (x,y,edge(y/127)[1]+.08)
    for i in range(48):
        a,b=math.tau*i/48,math.tau*(i+1)/48
        spar(line(5.7*math.cos(a),46+5.7*math.sin(a)),line(5.7*math.cos(b),46+5.7*math.sin(b)),.10,white)
    for x in (-1.5,1.5):
        spar(line(x,44),line(x,48),.18,white)
    spar(line(-1.5,46),line(1.5,46),.18,white)
    spar(line(0,32),line(0,40.1),.12,safety_yellow)
    # Angled perimeter safety nets along flight deck
    for s in (-1,1):
        for i in range(11):
            t = .24 + .24*i/10
            wx, wz = edge(t)
            spar((s*wx, t*127, wz), (s*(wx+1.05), t*127, wz+.18), .05, steel, name="Net stanchion")
        wx0, wz0 = edge(.24)
        wx1, wz1 = edge(.48)
        spar((s*(wx0+1.05), .24*127, wz0+.18), (s*(wx1+1.05), .48*127, wz1+.18), .045, steel, name="Net outer rail")

    rail(edge,127,-.48,-.19,14,1.05,.065)
    rail(edge,127,.23,.5,12,1.05,.06)


def response_hull():
    # The keel sweeps aft and up beneath the nose of the flotation collar.
    sections = [(-3.62,.26,.99,.62,.49), (-3.53,.56,.97,.57,.37),
                (-3.31,.83,.93,.52,.16), (-2.92,1.04,.86,.40,-.06),
                (-2.38,1.17,.79,.27,-.22), (-1.65,1.22,.74,.13,-.32),
                (-.65,1.24,.73,.05,-.37), (1.70,1.24,.73,0,-.37),
                (3.00,1.21,.72,0,-.34), (3.82,1.14,.71,0,-.30)]
    section = [(-1,0),(1,0),(.995,.28),(.94,.52),(.82,.68),
               (.58,.82),(.25,.95),(0,1),(-.25,.95),(-.58,.82),
               (-.82,.68),(-.94,.52),(-.995,.28)]
    verts = [(x*w,y+setback*f,z+(keel-z)*f)
             for y,w,z,setback,keel in sections for x,f in section]
    n=len(section)
    faces=[(i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j)
           for i in range(len(sections)-1) for j in range(n)]
    faces.extend([tuple(reversed(range(n))),tuple(range(len(verts)-n,len(verts)))])
    shell=mesh("Rounded response hull",verts,faces,black)
    shell.data.materials.append(deck)
    for i,face in enumerate(shell.data.polygons[:-2]):
        face.material_index=int(i%n==0)
        face.use_smooth=i%n!=0


def response_collar():
    side=[(1.12,3.78,.73,.32,.32),(1.18,3.15,.74,.37,.35),
          (1.21,1.65,.76,.38,.37),(1.21,-.65,.80,.39,.38),
          (1.19,-1.65,.84,.40,.40),(1.13,-2.45,.91,.42,.43)]
    path=[(-x,y,z,r,h) for x,y,z,r,h in side]
    for step in range(1,24):
        a=math.pi*step/24
        fullness=math.sin(a)
        path.append((-1.13*math.cos(a),-2.45-1.12*fullness,
                     .91+.22*fullness,.42+.06*fullness,.43+.07*fullness))
    path.extend(reversed(side))
    verts,faces=[],[]
    n=32
    for i,(x,y,z,r,h) in enumerate(path):
        prev=path[max(i-1,0)]
        nxt=path[min(i+1,len(path)-1)]
        normal=Vector((nxt[1]-prev[1],prev[0]-nxt[0])).normalized()
        for j in range(n):
            a=math.tau*j/n
            offset=r*math.cos(a)
            verts.append((x+normal.x*offset,y+normal.y*offset,z+h*math.sin(a)))
            if i:
                k=(j+1)%n
                faces.append(((i-1)*n+j,i*n+j,i*n+k,(i-1)*n+k))
    faces.extend([tuple(range(n)),tuple(reversed(range(len(verts)-n,len(verts))))])
    tube=mesh("Wraparound flotation collar",verts,faces,red)
    tube.data.materials.append(black)
    for i,face in enumerate(tube.data.polygons[:-2]):
        face.material_index=int(i%n in (29,30,31,0))
        face.use_smooth=True
    return tube


def outboard_motor(x):
    # Sculpted outboard cowling, midsection, lower unit, skeg & 3-blade prop
    box("Outboard cowling",(x,4.02,.96),(.52,.66,.74),alloy,.15)
    box("Cowling stripe",(x,4.04,1.02),(.53,.67,.12),black,.04)
    box("Outboard midsection",(x,4.02,.46),(.24,.36,.42),steel,.05)
    box("Gearcase",(x,4.04,.10),(.16,.34,.44),black,.05)
    box("Cavitation plate",(x,4.08,.24),(.34,.36,.035),black,.01)
    cyl("Prop hub",(x,4.24,.04),.065,.20,steel,10,(math.pi/2,0,0))
    for k in range(3):
        ang = math.tau * k / 3
        box("Prop blade",(x + math.cos(ang)*.10, 4.30, .04 + math.sin(ang)*.10),
            (.15,.03,.08),steel,.01, rot=(.35, ang, 0))


def response():
    response_hull()
    tube=response_collar()
    bpy.context.view_layer.update()

    # Heavy bow push-knee bumper & bow tow bitt
    box("Bow push knee",(0,-3.96,1.12),(.44,.22,.62),black,.06)
    bollard(0,-2.65,.78,scale=.48)

    # Pilothouse with framed raked windshield, wipers & hardtop brow
    house("Alloy pilothouse",(.96,-1.7,1.52,.73),(.93,-1.39,1.46,1.23),alloy)
    house("Raked windshield",(.93,-1.39,1.46,1.23),(.97,-1.70,1.48,2.31),alloy,2, wipers=True)
    house("Hardtop",(1.07,-1.82,1.60,2.31),(1.03,-1.78,1.56,2.42),white)
    # Aft cabin door frame
    watertight_door(0, 1.50, 1.48, .68, 1.42, 1, "Y")

    # Roof grab rails, collar lifelines, nav lights, twin outboards & crash bar
    for s in (-1,1):
        outboard_motor(s*.46)
        # Engine guard / crash bar arch behind outboards
        spar((s*.88,3.62,.76),(s*.88,4.38,1.02),.034,silver,name="Engine guard")
        # Cabin aft bracing struts
        spar((s*.87,2.12,.76),(s*.87,3.3,1.34),.034,silver)
        # Hardtop roof grab rails
        spar((s*.94,-1.55,2.42),(s*.94,-1.55,2.54),.022,silver)
        spar((s*.94,1.38,2.42),(s*.94,1.38,2.54),.022,silver)
        spar((s*.94,-1.55,2.54),(s*.94,1.38,2.54),.022,silver)
        # Collar grab-line rope loops along outer upper shoulder
        for y0, y1 in [(-1.6, -.3), (-.3, 1.0), (1.0, 2.4)]:
            spar((s*1.48, y0, 1.15), (s*1.48, y1, 1.12), .018, black, name="Grab line", sides=6)
        # Port & starboard nav lights on hardtop brow
        box("Nav light box",(s*1.02,-1.45,2.48),(.12,.18,.10),black,.02)
        sphere("Nav light",(s*1.04,-1.52,2.48),.045,nav_red if s==-1 else nav_green)
        label("COAST GUARD",1.60,.13,.977,.155,s,white,tube)

    # Crossbar connecting engine guard & stern tow post
    spar((-.88,4.38,1.02),(.88,4.38,1.02),.034,silver,name="Engine guard top")
    cyl("Stern tow post",(0,2.85,1.02),.065,.62,silver,10)
    spar((-.42,2.85,1.26),(.42,2.85,1.26),.045,silver,name="Tow bitt bar")

    # Roof electronics: radar dome on angled pedestal, blue law-enforcement beacon, searchlight, horns, antennas
    box("Radar pedestal",(0,.48,2.56),(.30,.38,.36),alloy,.045)
    cyl("Radar dome",(0,.48,2.82),.36,.24,white,18)
    cyl("Beacon pedestal",(0,-.22,2.48),.09,.14,steel,12)
    cyl("Blue beacon",(0,-.22,2.62),.085,.18,beacon_blue,14)
    # Roof searchlight & GPS mushroom
    cyl("Searchlight",(0,-1.35,2.52),.09,.16,white,12,(math.pi/2,0,0))
    cyl("Searchlight lens",(0,-1.43,2.52),.075,.02,nav_white,12,(math.pi/2,0,0))
    cyl("GPS dome",(.42,-.85,2.48),.08,.09,white,12)
    # VHF whip antennas
    for x,y,h in [(-.66,.96,3.72),(.62,.85,3.34)]:
        spar((x,y,2.38),(x,y+.12,h),.022,silver,.008)


def lifeboat():
    edge,shell=hull(14.3,4.18,1.46,alloy, lower_mat=black)

    # Heavy rubber bow push-bumper & foredeck towing bitt
    box("Bow fender",(0,-7.18,1.52),(.52,.28,.92),black,.08)
    bollard(0,-5.85,edge(-5.85/14.3)[1],scale=.62)

    # Raised deckhouse & enclosed bridge with framed windows & wipers
    house("Raised deckhouse",(1.77,-2.94,3.45,1.43),(1.60,-2.48,3.25,2.54),alloy)
    house("Enclosed bridge",(1.58,-2.40,.59,2.54),(1.69,-2.58,.70,3.48),alloy,3, wipers=True)
    house("Bridge brow",(1.78,-2.72,.78,3.48),(1.68,-2.62,.72,3.60),white)

    # Watertight aft cabin door & liferaft canister on deckhouse
    watertight_door(0, 3.35, 1.98, .78, 1.15, 1, "Y")
    liferaft_canister(0, -1.85, 3.76, scale=.62, rot_z=math.pi/2)

    # Open flying bridge helm console (wheel, binnacle, throttles)
    box("Helm console",(0,.85,2.95),(1.35,.46,.82),alloy,.05)
    box("Helm panel",(0,.88,3.38),(1.22,.32,.14),black,.03, rot=(-.35,0,0))
    bpy.ops.mesh.primitive_torus_add(major_radius=.18,minor_radius=.022,major_segments=18,
        minor_segments=8,location=(-.32,1.10,3.18),rotation=(math.pi/2-.35,0,0))
    wheel=bpy.context.object
    wheel.name="Helm wheel"
    wheel.data.materials.append(steel)
    for dx in (.08, .18):
        spar((dx,1.02,3.36),(dx,1.08,3.52),.015,steel,name="Throttle")
        sphere("Throttle knob",(dx,1.08,3.53),.026,red if dx<.12 else black)

    for s in (-1,1):
        # Framed cabin portholes
        for y in (.33,1.51):
            box("Cabin port frame",(s*1.69,y,2.02),(.10,.68,.38),frame_dark,.03)
            box("Cabin port",(s*1.71,y,2.02),(.10,.56,.27),glass,.04)
        # Flying bridge seats with pedestals
        cyl("Seat pedestal",(s*.62,1.35,2.68),.06,.34,steel,10)
        box("Flying bridge seat",(s*.62,1.35,2.90),(.48,.48,.18),deck,.05)
        box("Seat back",(s*.62,1.59,3.14),(.48,.13,.54),deck,.05)
        # Rescue rings on open bridge sides
        rescue_ring(s*1.65,1.63,3.08)
        # Heavy-weather stainless grab rails along bridge roof & deckhouse sides
        spar((s*1.58,-2.25,3.60),(s*1.58,-2.25,3.72),.025,silver)
        spar((s*1.58,.45,3.60),(s*1.58,.45,3.72),.025,silver)
        spar((s*1.58,-2.25,3.72),(s*1.58,.45,3.72),.025,silver)
        # Nav lights on bridge sides
        box("Nav light board",(s*1.72,-1.95,3.15),(.16,.34,.18),black,.03)
        sphere("Nav light",(s*1.76,-2.08,3.15),.06,nav_red if s==-1 else nav_green)
        # A-frame mast legs & flying bridge side rails
        spar((s*1.45,2.62,2.55),(s*1.15,2.30,4.56),.078,silver)
        spar((s*1.48,.77,2.57),(s*1.48,.77,3.35),.045,silver)
        spar((s*1.48,.77,3.35),(s*1.48,2.65,3.35),.045,silver)
        spar((s*1.48,.77,2.96),(s*1.48,2.65,2.96),.032,silver)
        # Aft deck cleats / bollards
        bx, bz = edge(.42)
        bollard(s*(bx - .32), 6.0, bz, scale=.48)
        label("COAST GUARD",2.045,.08,1.13,.26,s,ink,shell)

    # A-frame cross-brace & electronics mast
    spar((-1.32,2.48,3.45),(1.32,2.48,3.45),.055,silver,name="Mast crossbrace")
    box("Antenna platform",(0,2.25,4.54),(2.56,.86,.22),alloy,.08)
    spar((0,2.3,4.6),(0,2.43,6.40),.11,alloy,.046)
    # Open-array radar scanner & searchlight
    box("Radar pedestal",(0,2.33,5.08),(.36,.32,.24),alloy,.05)
    box("Radar",(0,2.33,5.28),(1.28,.24,.18),white,.06)
    cyl("Mast searchlight",(.72,2.05,4.78),.11,.22,white,12,(math.pi/2,0,0))
    sphere("Masthead light",(0,2.43,6.44),.075,nav_white)
    for x in (-.95,.92):
        spar((x,2.28,4.61),(x,2.36,6.36),.024,silver,.009)

    # Stern tow-bar arch over aft deck
    for s in (-1,1):
        spar((s*1.35,4.55,1.45),(s*1.22,4.55,2.28),.055,silver,name="Tow arch leg")
    spar((-1.22,4.55,2.28),(1.22,4.55,2.28),.06,silver,name="Tow arch bar")
    bollard(0,4.55,1.44,scale=.55)

    rail(edge,14.3,-.47,-.20,5,.74,.036)
    rail(edge,14.3,.27,.49,4,.66,.036)
    for y in (-4.84,5.55):
        hz = edge(y/14.3)[1]
        box("Deck hatch coaming",(0,y,hz+.05),(1.30,.92,.10),steel,.03)
        box("Deck hatch",(0,y,hz+.11),(1.20,.82,.06),deck,.03)


fleet=[]
for name,build in [("national_security_cutter",cutter),("response_boat_small",response),
                   ("motor_lifeboat_47",lifeboat)]:
    build()
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active=bpy.context.selected_objects[0]
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+".glb")),use_selection=True)
    fleet.append(obj)
    obj.hide_set(True)

for obj,x in zip(fleet,(0,15,23)):
    obj.hide_set(False)
    obj.location.x=x
bpy.ops.object.select_all(action="DESELECT")
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ART/"coast_guard.blend"))
