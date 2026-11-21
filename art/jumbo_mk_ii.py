"""Build the Tacoma-style Jumbo Mk II. Run blender -b --factory-startup -P art/jumbo_mk_ii.py.

The two vehicle deck plans share a 3781.88 by 742.56 viewBox. Dimensions are
metres, in the same Y-up frame and vertex-colour palette as the Issaquah.
"""
import bisect
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ART = Path(__file__).resolve().parent
sys.path.insert(0, str(ART))
from issaquah_mid import (V, box, cyl, face, finish_meshes, hface, loft, model_collection,
                          panel, rail_loop, rect, torus)

HALF_LENGTH = 70.13
HALF_BEAM = 13.716
MAIN = 2.85
UPPER = 5.65
PAX = 9.30
SUN = 12.35
BRIDGE = 15.25

# Starboard half of Main_Deck_Shape. Sample the Illustrator cubics including
# the rounded apron nose; the parallel middle runs to z=29.9 m.
OUTLINE = [(0, HALF_BEAM)]
for control in [
    [(2695.77, 1), (2695.77, 1), (3042.33, 1), (3298.95, 79.70)],
    [(3298.95, 79.70), (3489.70, 138.19), (3722.88, 247.58), (3761.13, 306.18)],
    [(3761.13, 306.18), (3774.295, 326.36), (3780.8775, 348.82), (3780.8775, 371.28)],
]:
    for i in range(17):
        t = i / 16
        w = [(1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3]
        along, across = [sum(p[k]*a for p, a in zip(control, w)) for k in (0, 1)]
        OUTLINE.append(((along-1890.94)*HALF_LENGTH/1889.94,
                        (371.28-across)*HALF_BEAM/370.28))


def sample(stations, z):
    z = abs(z)
    i = min(bisect.bisect_right(stations, (z, math.inf)), len(stations)-1)
    a, b = stations[max(0, i-1)], stations[i]
    if a[0] == b[0]:
        return a[1]
    t = min(1, (z-a[0])/(b[0]-a[0]))
    return a[1] + (b[1]-a[1])*t


def beam(z):
    return max(0.025, sample(OUTLINE, z))


def stations(start, end, step=2):
    n = math.ceil((end-start)/step)
    return [start + (end-start)*i/n for i in range(n+1)]


def outline(y, length, breadth, scale_z=1):
    zs = stations(-length, length)
    return [V(s*breadth(z), y, z*scale_z) for s, run in [(1, zs), (-1, reversed(zs))] for z in run]


def slice_ring(x0, x1, z, y0, y1):
    return [V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z)]


def hull():
    # The body narrows and draws up at each propeller. The guard follows the
    # full footprint of the car deck and leaves bare aprons beyond the gates.
    rings = [outline(y, HALF_LENGTH, lambda z: beam(z)*width, length)
             for y, width, length in [(-5.5,.68,.74), (-3.8,.86,.84), (-1,.95,.94),
                                      (1.4,.985,.985), (2.05,1,1), (2.65,1,1), (MAIN,.99,.998)]]
    loft(rings, lambda i,j,c: ["hull","hull","hull","green","dark","guard"][i],
         cap_key="deck")
    for e in [-1, 1]:
        hub = V(0,-3.4,e*60.5)
        cyl(hub-V(0,0,e*4), hub+V(0,0,e*.4), .26,.36,8,"bronze")
        for i in range(4):
            angle = i*math.pi/2+.4
            radial = V(math.cos(angle), math.sin(angle),0)
            tangent = V(-radial.y,radial.x,0)
            blade = [hub+radial*.22, hub+radial*1.25-tangent*.40,
                     hub+radial*1.77+tangent*.14, hub+radial*1.32+tangent*.50]
            loft([blade,[p+V(0,0,.15) for p in blade]], "bronze")
        loft([rect(0,-5.5,e*64,.24,1.18,.1), rect(0,.6,e*64.7,.32,1.9,.15)],"hull")
        for x in [-3.45,0,3.45]:
            # Edge stripes leave the middle of each through lane clear.
            if x != 0:
                box(V(x/2,MAIN+.012,e*32),(0.10,.018,64),"yellow")


def skin(s, z0, z1, bottom, top, color):
    loft([slice_ring(s*(beam(z)-.32),s*(beam(z)-.10),z,bottom(z),top(z))
          for z in stations(z0,z1)],color)


def sides():
    # Two tiers of genuine openings. The solid shoulders sweep down to the
    # apron leaving a full-height, open-ended drive-through passage.
    for s in [-1,1]:
        bay = s * 40
        for lo, hi, end, color in [(MAIN,4.05,66.6,"green"), (4.05,4.30,61.9,"white"),
                                   (5.39,6.22,61.9,"white"), (7.54,PAX,61.9,"white")]:
            spans = [(-end, end)] if lo >= 5.39 else [(-end, bay-3.7), (bay+3.7, end)]
            for start, stop in spans:
                skin(s,start,stop,lambda z:lo,lambda z:hi,color)
        for lo, hi, last, pitch, pier in [
            (4.30,5.39,43.6,4.0,.36),(6.22,7.54,53.6,4.0,.34)]:
            for i in range(-int(last/pitch),int(last/pitch)+1):
                if lo < 5 and abs(i*pitch-bay) < 3.7:
                    continue
                skin(s,i*pitch-pier/2,i*pitch+pier/2,lambda z:lo,lambda z:hi,"white")
            for e in [-1,1]:
                a,b = sorted([e*last,e*61.9])
                skin(s,a,b,lambda z:lo,lambda z:hi,"white")
        # A rescue-boat bay opens through the green belt on opposite quarters.
        box(V(s*10.05,4.11,bay),(.12,2.53,7.4),"dkwall")
        for z in (bay-3.7,bay+3.7):
            w = beam(z)-.24-10.05
            box(V(s*(10.05+w/2),4.11,z),(w,2.53,.12),"white")
        for z in (bay-1.35,bay+1.35):
            box(V(s*11.60,MAIN+.12,z),(1.65,.24,.22),"dark")
        # Curved cut-back seen in broadside at each end of the car deck.
        for e in [-1,1]:
            rim = [(61.9,PAX),(63.6,PAX-.3),(62.7,8.2),(62.8,7.3),
                   (63.6,5.8),(64.6,4.9),(66.2,4.55),(66.6,4.05),(61.9,4.05)]
            loft([[V(s*(beam(z)-offset),y,e*z) for z,y in rim] for offset in [.32,.10]],"white")


def decks():
    # Inner edge of the upper car deck from ramp_north/south in the upper
    # SVG. The longitudinal section sets the break in slope at z=38.5.
    # Beyond the outline at z=51, the lower drawing carries the ramp to the apron.
    inner = [(0,5.5),(38.5,5.5),(43.2,7.65),(51.1,5.5),(59.0,4.45)]
    outer = [(0,13.12),(32.7,13.10),(43.2,12.4),(49.7,11.10),(51.1,10.60),(59.0,8.25)]
    for s in [-1,1]:
        for e in [-1,1]:
            zs = sorted(set(stations(0,59) + [z for z,_ in inner+outer]))
            def level(z):
                return UPPER - (UPPER-MAIN)*max(0,z-38.5)/20.5
            loft([slice_ring(s*sample(inner,z),s*sample(outer,z),e*z,
                             level(z)-.16,level(z)) for z in zs],"deckp")
            rail_loop([V(s*sample(inner,z),level(z),e*z) for z in zs if z >= 38.5],
                      .74,"steel",closed=False)
            # The stair/elevator casings split the through lanes from the wings.
            box(V(s*6.45,(MAIN+PAX)/2,e*16.1),(1.6,PAX-MAIN,32.2),"ceiling")
            for i in range(10):
                box(V(s*6.45,MAIN+.15+i*.14,e*(34.6-i*.25)),(1.6,.3+i*.28,.27),"panel")
        for z in range(-30,31,10):
            for x,y in [(s*10.2,UPPER-.21),(s*10.2,PAX-.31),(s*2.0,PAX-.31)]:
                box(V(x,y,z),(.22,.08,1.0),"lamp")


def deck_plate(y, length, inset, thickness, top="deckp"):
    width = lambda z: beam(z)-inset
    rings = [outline(h,length,width) for h in (y-thickness,y)]
    loft(rings,"white",caps=False)
    hface(rings[0],"ceiling",False)
    hface(rings[1],top)
    return rings[1]


def glazed_house(z, y, height, hw, hd, cut, pitch, slope=0, roof="white", trim=.18):
    # Windows follow each facet including the slanted corner lights. These
    # dark panels remain legible at the game camera's normal ferry zoom.
    base = rect(0,y,z,hw,hd,cut)
    top = rect(0,y+height,z,hw+slope,hd+slope,cut)
    # The deck below and the roof plate above already close the house.
    loft([base,top],"white",caps=False)
    for i,a in enumerate(base):
        b = base[(i+1)%len(base)]
        direction = b-a
        length = direction.length
        if length < .65:
            continue
        n = V(direction.z,0,-direction.x).normalized()
        mid = (a+b)*.5
        if n.dot(mid-V(0,y,z)) < 0:
            n = -n
        count = max(1,round(length/pitch))
        for j in range(count):
            t = (j+.5)/count
            low = a.lerp(b,t)
            high = top[i].lerp(top[(i+1)%len(top)],t)
            at = low.lerp(high,.54) + n*(abs(slope)*.3+.035)
            panel(at,n,length/count*.80,height*.46,.035,"glass" if roof=="green" else "window")
    loft([rect(0,y+height,z,hw+slope+trim,hd+slope+trim,cut),
          rect(0,y+height+.19,z,hw+slope+trim,hd+slope+trim,cut)],roof)


def passenger_deck():
    deck_plate(PAX,55.25,.23,.30)
    for e in [-1,1]:
        # The lookout wings surround the notch above the vehicle entrance.
        for s in [-1,1]:
            zs = stations(55.25,63.65)
            inner = lambda z: 3.85 + (z-55.25)*.08
            loft([slice_ring(s*inner(z),s*(beam(z)-.23),e*z,PAX-.30,PAX)
                  for z in zs],"white",cap_key="white")
            rail = [V(s*(beam(z)-.23),PAX,e*z) for z in zs]
            rail += [V(s*inner(z),PAX,e*z) for z in reversed(zs)]
            rail_loop(rail,1.0,"green",closed=False)
        rail_loop([V(-3.85,PAX,e*55.25),V(3.85,PAX,e*55.25)],1.0,"green",closed=False)
    # Continuous passenger saloon following the hull taper, with end viewing decks.
    def width(z):
        return beam(z)-.39-max(0,abs(z)-50)*.28
    # The sun-deck plate is the saloon roof. End the walls at its underside
    # so the grey walkway has a single exposed surface all the way around.
    rings = [outline(y,54.0,width,k) for y,k in [(PAX,1),(SUN-.25,.987)]]
    loft(rings,"white",caps=False)
    for s in [-1,1]:
        for z in stations(-51.1,51.1,2.35):
            derivative = (width(z+.05)-width(z-.05))/.1
            n = V(s,0,-derivative).normalized()
            panel(V(s*(width(z/.993)+.065),PAX+1.48,z),n,1.87,1.22,.05,"window",.14)
    for e in [-1,1]:
        for x in stations(-8,8,1.8):
            panel(V(x,PAX+1.49,e*53.88),V(0,0,e),1.48,1.35,.035,"window")
    edge = deck_plate(SUN,53.4,.37,.25)
    # The public walkway has a solid white windbreak around each bridge base.
    for s in [-1, 1]:
        side = [p for p in edge if s*p.x > 0 and abs(p.z) < 41]
        rail_loop(side, 1.02, "green", step=2.7, closed=False)
    for e in [-1, 1]:
        end = sorted([p for p in edge if p.x > 0 and e*p.z > 38], key=lambda p: e*p.z)
        path = end + [V(-p.x, p.y, p.z) for p in reversed(end)]
        rings = []
        for p in path:
            height = min(.88, (e*p.z - 38)*.32)
            inside = V(p.x*.984, p.y, p.z - e*.19)
            rings.append([p, inside, inside+V(0,height,0), p+V(0,height,0)])
        loft(rings, "white")


def bridge_ring(half_plan, e, y):
    """Mirror a half outline running from the inboard end to the bow centre."""
    plan = half_plan + [(-x, z) for x, z in reversed(half_plan[:-1])]
    return [V(x, y, e*z) for x, z in plan]


def pilothouse(e):
    # The casing leaves open air underneath the outboard lookouts. Its forward
    # face has four scuttles following the curve below the bridge windows.
    casing = [(6.05,40.85), (6.35,42.1), (6.35,48.9), (6.03,50.4),
              (5.22,51.55), (3.78,52.14), (1.88,52.50), (0,52.57)]
    base = bridge_ring(casing, e, SUN)
    loft([base, bridge_ring(casing, e, BRIDGE-.26)], "white", caps=False)
    for s in [-1, 1]:
        for i in (1, 4, 6):
            a, b = base[i:i+2]
            normal = V(e*(b.z-a.z), 0, -e*(b.x-a.x)).normalized()
            p = (a+b)*.5 + V(0,1.64,0)
            p.x *= s
            normal.x *= s
            cyl(p, p+normal*.055, .245, .245, 16, "steel")
            cyl(p+normal*.05, p+normal*.075, .197, .197, 16, "window")

    # The wing tips project past the sides of the ferry. The walkway steps
    # back in around each bridge door, leaving sightlines straight down.
    edge = [(6.28,40.78), (7.0,42.42), (12.82,43.00), (13.02,43.28),
            (13.02,45.34), (12.78,45.60), (8.10,45.92), (7.10,46.88),
            (7.10,49.20), (6.72,50.58), (5.82,51.87), (4.15,52.59),
            (2.05,52.94), (0,53.01)]
    floor = bridge_ring(edge, e, BRIDGE)
    underside = bridge_ring(edge, e, BRIDGE-.26)
    loft([underside, floor], "white", caps=False)
    hface(floor, "deckp")
    hface(underside, "ceiling", False)
    rail_loop([floor[-1], floor[0]], .99, "green", step=1.45, closed=False)
    for s in [-1, 1]:
        rail = [V(s*p.x,p.y,p.z) for p in floor[:11]]
        rail_loop(rail, .99, "green", step=1.45, closed=False)
        torus(V(s*10.63,BRIDGE+.55,e*45.79), V(.07*s,0,e), .30,.085,16,6,"orange")
        box(V(s*12.57,BRIDGE+.45,e*44.85), (.16,.90,1.04), "green")
        cyl(V(s*12.13,SUN,e*44.05), V(s*12.13,BRIDGE-.26,e*44.05),
            .09,.09,8,"white")
        # The narrow grated ledge below the forward windows follows the bow.
        nose = [V(s*x, BRIDGE-.07, e*z) for x,z in edge[10:]]
        for a,b in zip(nose, nose[1:]):
            outer_a = a + V(a.x*.048, 0, e*.40)
            outer_b = b + V(b.x*.048, 0, e*.40)
            cyl(outer_a, outer_b, .04,.04,6,"white")
            count = math.ceil((b-a).length/.26)
            for k in range(count):
                t = k/count
                cyl(a.lerp(b,t), outer_a.lerp(outer_b,t), .027,.027,4,"white")

    # A run of forward-raked windows follows the shallow arc across the bow.
    # Build the frames and glazing into each facet so they share their edges.
    house = [(4.62,43.45), (5.02,43.96), (5.02,45.6), (5.02,47.55),
             (5.02,49.28), (4.59,50.47), (3.48,51.20), (2.10,51.59),
             (.70,51.75), (0,51.75)]
    def outline_at(y, width, length):
        return bridge_ring([(x*width, 48+(z-48)*length) for x,z in house], e, y)

    sill = outline_at(BRIDGE+.68, 1.02, 1.01)
    head = outline_at(BRIDGE+2.25, 1.095, 1.09)
    loft([outline_at(BRIDGE,1,1), sill], "white", caps=False)
    for i, a in enumerate(sill):
        j = (i+1) % len(sill)
        b, c, d = sill[j], head[j], head[i]
        if (b-a).length > 5:  # solid inboard bulkhead behind the mast
            wall = [a,b,c,d]
            face(wall[::-1] if e > 0 else wall, "white")
            continue
        # The centre front pane spans the mirror line with just one frame
        # on each side of it.
        inset_a = 0 if abs(a.x) < .001 else .065/(b-a).length
        inset_b = 0 if abs(b.x) < .001 else .065/(b-a).length
        low_a, low_b = a.lerp(d,.055), b.lerp(c,.055)
        high_a, high_b = d.lerp(a,.045), c.lerp(b,.045)
        p, q = low_a.lerp(low_b,inset_a), low_b.lerp(low_a,inset_b)
        r, t = high_b.lerp(high_a,inset_b), high_a.lerp(high_b,inset_a)
        for polygon, color in [([a,b,q,p],"white"), ([b,c,r,q],"white"),
                               ([c,d,t,r],"white"), ([d,a,p,t],"white"),
                               ([p,q,r,t],"glass")]:
            face(polygon[::-1] if e > 0 else polygon, color)
    # Overhanging visor and tapered green crown visible from the approaches.
    rim = outline_at(BRIDGE+2.39,1.20,1.19)
    crown = outline_at(BRIDGE+2.85,1.10,1.09)
    loft([head, rim, crown], "green", caps=False)
    hface(crown, "green")
    # The bridge crew step out through the inboard bulkhead onto either wing.
    for s in [-1, 1]:
        sill_z = sill[0].z
        door_top = sill[0].lerp(head[0], .86)
        bottom = V(s*3.73, BRIDGE+.06, e*43.45-e*.055)
        top = V(bottom.x, door_top.y, door_top.z-e*.055)
        half = V(.44,0,0)
        door = [bottom-half,bottom+half,top+half,top-half]
        face(door if e < 0 else door[::-1], "panel")
        panel(V(bottom.x, BRIDGE+1.45, (sill_z+door_top.z)*.5-e*.12),
              V(0,0,-e), .56,.54,.025,"glass")


def upper_works():
    glazed_house(0,SUN,2.65,8.4,19.4,2.3,2.5,slope=-.7)
    glazed_house(0,SUN+2.82,.95,6.9,12.4,1.4,2.2,slope=-.5)
    # Green-based, louvred central stack and raised black rain cap.
    y = SUN+3.96
    for bot,top,hw0,hw1,hd0,hd1,col in [
        (0,.58,3.1,3.0,6.45,6.3,"green"),(.58,4.25,3,2.48,6.3,4.8,"white"),
        (4.25,4.47,2.6,2.6,4.96,4.96,"dark")]:
        loft([rect(0,y+bot,0,hw0,hd0,.55),rect(0,y+top,0,hw1,hd1,.55)],col)
    for e in [-1,1]:
        for i in range(4):
            h=1.05+i*.78
            box(V(0,y+h,e*(6.3-(h-.58)*1.5/3.67)),(4.85,.23,.16),"dark")
    for x in [-1.15,1.15]:
        for z in [-2.7,2.7]:
            cyl(V(x,y+4.4,z),V(x,y+5.68,z),.31,.31,8,"dark")
    loft([rect(0,y+5.28,0,3.0,5.72,.8),rect(0,y+5.47,0,3.0,5.72,.8)],"dark")

    for e in [-1,1]:
        # Skylights over the solarium, in panels between white roof mullions.
        glazed_house(e*32.4,SUN,2.57,7.9,8.05,.85,1.9)
        for x in range(-3,4):
            for j in range(6):
                box(V(x*2.04,SUN+2.81,e*(25.9+j*2.57)),(1.88,.075,2.37),"pane")
        pilothouse(e)
        # Fin mast with two forward-facing radar platforms, matching both ends.
        cyl(V(0,SUN+.16,e*53.05),V(0,SUN+3.8,e*60.25),.12,.045,6,"white")
        mz=e*43.8
        loft([rect(0,BRIDGE,e*43.7,1.0,1.52,.2),rect(0,20.0,mz,.45,.82,.1),
              rect(0,24.8,mz,.17,.32,.06)],"white")
        for h,length in [(20.8,1.7),(23.25,2.20)]:
            box(V(0,h,mz+e*.94),(2.2,.14,length),"white")
            cyl(V(0,h,mz+e*1.3),V(0,h+.64,mz+e*1.3),.12,.09,6,"white")
            box(V(0,h+.66,mz+e*1.3),(2.65,.15,.27),"white")
        cyl(V(0,24.7,mz),V(0,26.65,mz),.12,.065,8,"white")
        for s in [-1,1]:
            torus(V(s*(beam(36)-.47),SUN+.61,e*36),V(s,0,0),.39,.095,12,5,"orange")


def stowed_boats(parts):
    # Reuse the fleet's rescue boat, with its lifting sling stowed.
    coll, mat = model_collection("Rescue boats")
    bpy.ops.import_scene.gltf(filepath=str(ART.parent/"assets/models/rib_mid.glb"))
    rib = next(ob for ob in bpy.context.selected_objects if ob.name == "fixed")
    for ob in list(bpy.context.selected_objects):
        if ob != rib:
            bpy.data.objects.remove(ob, do_unlink=True)
    for source in list(rib.users_collection):
        source.objects.unlink(rib)
    coll.objects.link(rib)
    # The ship uses a corner-domain Col layer. Match it before Blender joins
    # the meshes, so the RIB's orange tubes keep their imported paint.
    mesh = rib.data
    original = mesh.color_attributes.active_color
    old_colors = [tuple(c.color_srgb) for c in original.data]
    per_vertex = original.domain == "POINT"
    mesh.color_attributes.remove(original)
    colors = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
    for loop in mesh.loops:
        colors.data[loop.index].color_srgb = old_colors[loop.vertex_index if per_vertex else loop.index]
    mesh.color_attributes.active_color_name = "Col"
    rib.data.materials.clear()
    rib.data.materials.append(mat)
    for s in (1, -1):
        boat = rib if s == 1 else rib.copy()
        if s == -1:
            coll.objects.link(boat)
        boat.name = "Rescue boat " + ("starboard" if s == 1 else "port")
        boat.location = (s*11.60,-s*40,3.41)
        boat.rotation_euler.z = math.pi if s == 1 else 0
        boat.scale = (.90, .90, .90)
        parts["fixed"].append(boat)


def build():
    # Generate an editable source with deck groups, then a role-batched GLB
    # for Tideways' vertex-colour, night-light and shadow handling.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = {}
    for name, draw in [("Hull and running gear", hull), ("Side shell", sides),
                       ("Vehicle decks and ramps",decks), ("Passenger deck",passenger_deck),
                       ("Solariums, bridges and funnel",upper_works)]:
        coll, mat = model_collection(name)
        draw()
        for ob in finish_meshes(name,coll,mat):
            role = ob.name.split(".")[0]
            ob.name = name + " - " + role
            parts.setdefault(role,[]).append(ob)
    stowed_boats(parts)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                view = area.spaces.active
                view.shading.color_type = "VERTEX"
                view.overlay.show_overlays = False
                view.region_3d.view_rotation = Vector((1,-1.55,.7)).to_track_quat("Z","Y")
                view.region_3d.view_location = (0,0,7)
                view.region_3d.view_distance = 159
    bpy.context.preferences.filepaths.save_version = 0
    for ob in parts["thinshadow"]:
        ob.hide_set(True)
        ob.hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=str(ART/"jumbo_mk_ii.blend"), compress=True)
    for role, objects in parts.items():
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objects:
            ob.hide_set(False)
            ob.hide_render = False
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objects[0]
        if len(objects) > 1:
            bpy.ops.object.join()
        objects[0].name = role
    bpy.ops.export_scene.gltf(filepath=str(ART.parent/"assets/models/jumbo_mk_ii.glb"),
                              export_format="GLB", export_vertex_color="ACTIVE",
                              export_materials="NONE", export_yup=True)


if __name__ == "__main__":
    if not bpy.app.background:
        raise RuntimeError("Run the generator in background Blender with -b")
    build()
