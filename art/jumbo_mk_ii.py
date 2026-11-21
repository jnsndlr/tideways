"""Build the Tacoma-style Jumbo Mk II. Run blender -b --factory-startup -P art/jumbo_mk_ii.py.

The two vehicle deck plans share a 3781.88 by 742.56 viewBox. Dimensions are
metres, in the same Y-up frame and vertex-colour palette as the Issaquah.

The game's cars are drawn a third over real size, so the real boat's four-lane
tunnel won't fit them at her true 27.4 m beam. She is drawn at true size below
and then stretched STRETCH in length and beam (not height, so her decks keep
their levels), with her stair casings set further out (CASING_X) so the tunnel
takes four lanes. Numbers the game wants, after the stretch (model metres):
tunnel lanes x = +-1.7, +-5.1; wing lanes +-10.3, +-13.3; casings' faces at
+-7.22 and +-9.02; half length 79.1, half beam 15.47.
"""
import bisect
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

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
STRETCH = 1.128   # length and beam, applied to the finished model (build)
CASING_X = 7.2    # the casings' centres before the stretch (8.12 after)

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
        for x in [-3.4,0,3.4]:
            # Stripes between the four through lanes (at +-1.7, +-5.1 stretched).
            box(V(x/STRETCH,MAIN+.012,e*32),(0.10,.018,64),"yellow")


def skin(s, z0, z1, bottom, top, color):
    loft([slice_ring(s*(beam(z)-.32),s*(beam(z)-.10),z,bottom(z),top(z))
          for z in stations(z0,z1)],color)


def car_port(s, left, right, sill, head):
    def point(z, y, inset):
        return V(s*(beam(z)-inset), y, z)

    # Roll the four corners through the full thickness of the shell.
    radius = .23
    for z, dz in [(left,1), (right,-1)]:
        for y, dy in [(sill,1), (head,-1)]:
            profile = [(z,y)]
            for k in range(6):
                angle = k*math.pi/10
                profile.append((z+dz*radius*(1-math.cos(angle)),
                                y+dy*radius*(1-math.sin(angle))))
            loft([[point(u,v,inset) for u,v in profile] for inset in (.10,.32)], "white")
    mid_z, mid_y = (left+right)/2, (sill+head)/2
    cyl(point(mid_z,sill,.21), point(mid_z,head,.21), .055,.055,8,"white")
    cyl(point(left,mid_y,.21), point(right,mid_y,.21), .055,.055,8,"white")


FORK_DEPTH = [(55.25,.30),(61.9,.30),(62.5,.40),(63.05,.62),(63.35,.69),(63.65,.69)]


def sides():
    # Two tiers of genuine openings. The solid shoulders sweep down to the
    # apron leaving a full-height, open-ended drive-through passage.
    for s in [-1,1]:
        bay = s * 40
        for lo, hi, end, color in [(MAIN,4.05,66.6,"green"), (4.05,4.30,61.9,"white"),
                                   (5.39,6.22,61.9,"white"), (7.54,PAX-.30,61.9,"white")]:
            spans = [(-end, end)] if lo >= 5.39 else [(-end, bay-3.7), (bay+3.7, end)]
            for start, stop in spans:
                skin(s,start,stop,lambda z:lo,lambda z:hi,color)
        for lo, hi, last, pitch, pier in [
            (4.30,5.39,43.6,4.0,.36),(6.22,7.54,53.6,4.0,.34)]:
            edges = [-last] + [i*pitch for i in range(-int(last/pitch),int(last/pitch)+1)] + [last]
            for z in edges[1:-1]:
                if lo >= 5 or abs(z-bay) >= 3.7:
                    skin(s,z-pier/2,z+pier/2,lambda z:lo,lambda z:hi,"white")
            for left,right in zip(edges,edges[1:]):
                left += pier/2 if left != -last else 0
                right -= pier/2 if right != last else 0
                if lo >= 5 or right <= bay-3.7 or left >= bay+3.7:
                    car_port(s,left,right,lo,hi)
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
            # Trace the return in narrow horizontal strips. A single cap
            # across this concave, curved plate bridges the notch on export.
            rim = [(4.05,66.6),(4.18,65.7),(4.43,64.9),(4.9,64.15),
                   (5.65,63.46),(6.55,63.03),(7.45,62.91),(8.12,63.04),
                   (8.44,63.29),(8.61,63.65)]
            def strip(y, tip):
                zs = [61.9+(tip-61.9)*i/6 for i in range(7)]
                return ([V(s*(beam(z)-.10),y,e*z) for z in zs] +
                        [V(s*(beam(z)-.32),y,e*z) for z in reversed(zs)])
            loft([strip(y,tip) for y,tip in rim],"white")
            # Close the shoulder against the sloping underside of the fork.
            shoulder = [(z,depth) for z,depth in FORK_DEPTH if 61.9 <= z <= 63.35]
            for (a,da),(b,db) in zip(shoulder,shoulder[1:]):
                for inset in (.10,.32):
                    q = [V(s*(beam(z)-inset),y,e*z) for z,y in
                         [(a,8.61),(a,PAX-da),(b,PAX-db),(b,8.61)]]
                    face(q if (s*e > 0) == (inset == .10) else q[::-1],"white")


def decks():
    # Both ramp kerbs turn with the shell. The broad parking deck narrows
    # smoothly to a single lane before descending to the apron.
    def ramp_edges(z):
        outer = beam(z)-.33
        blend = min(1,max(0,(z-32.2)/14))
        blend = blend*blend*(3-2*blend)
        width = (outer-(CASING_X-.95))*(1-blend) + (beam(59)-.33-4.45)*blend
        return outer-width,outer

    for s in [-1,1]:
        for e in [-1,1]:
            road, rail = [], []
            for z in sorted(set(stations(0,59,1) + [32.2,38.5])):
                y = UPPER - (UPPER-MAIN)*max(0,z-38.5)/20.5
                inside,outside = ramp_edges(z)
                road.append(slice_ring(s*inside,s*outside,e*z,y-.16,y))
                if z >= 38.5:
                    rail.append(V(s*inside,y,e*z))
            loft(road,"deckp")
            rail_loop(rail,.74,"steel",closed=False)
            # The stair/elevator casings split the through lanes from the wings.
            box(V(s*CASING_X,(MAIN+PAX)/2,e*16.1),(1.6,PAX-MAIN,32.2),"ceiling")
            for i in range(10):
                box(V(s*CASING_X,MAIN+.15+i*.14,e*(34.6-i*.25)),(1.6,.3+i*.28,.27),"panel")
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


def saloon_entrance(a,b,c,d,close_start=False,close_end=False,doors=False):
    # Return the doorway around the corner to form an open, shaded vestibule.
    offset = V(-math.copysign(.86,(a.x+b.x)/2),0,-math.copysign(1.05,a.z))
    h,k = a.lerp(d,.84), b.lerp(c,.84)
    face([h,d,c,k],"white")
    face([h,k,k+offset,h+offset],"ceiling")
    rear = [p+offset for p in (a,b,k,h)]
    if doors:
        # A pair of glazed leaves at the back of the sheltered entrance.
        glazed_facet(*rear,(b-a).length/2,.25,.88,"glass")
    else:
        face([rear[0],rear[3],rear[2],rear[1]],"dkwall")
    if close_start:
        face([a,h,h+offset,a+offset],"white")
    if close_end:
        face([b+offset,k+offset,k,b],"white")


def glazed_facet(a,b,c,d,pitch,sill,head,color,slant=0):
    count = max(1, round((b-a).length/pitch))
    for k in range(count):
        left, right = k/count, (k+1)/count
        lower = [a.lerp(b, t) for t in (left, right)]
        upper = [d.lerp(c, t) for t in (left, right)]
        low = [v.lerp(w, sill) for v,w in zip(lower,upper)]
        high = [v.lerp(w, head) for v,w in zip(lower,upper)]
        face([lower[0],low[0],low[1],lower[1]], "white")
        face([high[0],upper[0],upper[1],high[1]], "white")
        bottom = [0,.10,.90,1]
        heads = [0, .48 if slant < 0 else .10, .52 if slant > 0 else .90, 1]
        for i,key in enumerate(("white",color,"white")):
            face([low[0].lerp(low[1],bottom[i]), high[0].lerp(high[1],heads[i]),
                  high[0].lerp(high[1],heads[i+1]), low[0].lerp(low[1],bottom[i+1])], key)


def solarium(e):
    z = e*32.4
    walls = rect(0,SUN,z,7.9,8.05,.85)
    inside = rect(0,SUN,z,7.76,7.91,.77)
    rise = V(0,2.57,0)
    for i,a in enumerate(walls):
        j = (i+1)%len(walls)
        b = walls[j]
        if e*(a.z+b.z)/2 < 25:
            continue  # Open the inboard end and its two short corner returns.
        glazed_facet(a,b,b+rise,a+rise,1.9,.31,.77,"window")
        c,d = inside[i],inside[j]
        glazed_facet(d,c,c+rise,d+rise,1.9,.31,.77,"window")
        for outer,inner in ((a,c),(b,d)):
            if abs(e*outer.z-25.20) < .001:
                face([outer,inner,inner+rise,outer+rise],"white")
    loft([rect(0,SUN+2.57,z,8.08,8.23,.85),
          rect(0,SUN+2.76,z,8.08,8.23,.85)],"white")
    for x in range(-3,4):
        for j in range(6):
            hface(rect(x*2.04,SUN+2.78,e*(25.9+j*2.57),.94,1.185),"glass")


def passenger_deck():
    deck_plate(PAX,55.25,.10,.30)
    for e in [-1,1]:
        rails = []
        # The lookout wings surround the notch above the vehicle entrance.
        for s in [-1,1]:
            zs = sorted(set(stations(55.25,63.65) + [z for z,_ in FORK_DEPTH]))
            inner = lambda z: 3.85 + (z-55.25)*.08
            # The folded nose plate deepens over the last metre.
            loft([slice_ring(s*inner(z),s*(beam(z)-.10),e*z,PAX-sample(FORK_DEPTH,z),PAX)
                  for z in zs],"white",cap_key="white")
            rail = [V(s*(beam(z)-.23),PAX,e*z) for z in zs]
            rail += [V(s*inner(z),PAX,e*z) for z in reversed(zs)]
            rails.append(rail)
        rail_loop(rails[0] + rails[1][::-1],1.0,"green",closed=False)
    # Continuous passenger saloon following the hull taper, with end viewing decks.
    def width(z):
        return beam(z)-.39-max(0,abs(z)-50)*.28
    # The sun-deck plate is the saloon roof. End the walls at its underside
    # so the grey walkway has a single exposed surface all the way around.
    # Ease each corner from the tapered side into the flat end wall.
    side = [(width(z),z) for z in stations(0,51.5,2.35)]
    start = V(side[-1][0],0,51.5)
    corner = V(width(54),0,54)
    end = corner - V(2.5,0,0)
    for t in (.33,.67,1):
        pt = start.lerp(corner,t).lerp(corner.lerp(end,t),t)
        side.append((pt.x,pt.z))
    starboard = [(x,-z) for x,z in reversed(side[1:])] + side
    plan = starboard + [(-x,z) for x,z in reversed(starboard)]
    base = [V(x,PAX,z) for x,z in plan]
    top = [V(x,SUN-.25,z-math.copysign(max(0,abs(z)-50)*.18,z)) for x,z in plan]
    for i,a in enumerate(base):
        j = (i+1)%len(base)
        b,c,d = base[j],top[j],top[i]
        z = abs((a.z+b.z)/2)
        if abs(a.z-b.z) < .001:
            # Split the forward wall at the two fork landings.
            for u,v,portal in [(0,.18,True),(.18,.82,False),(.82,1,True)]:
                wall = a.lerp(b,u),a.lerp(b,v),d.lerp(c,v),d.lerp(c,u)
                if portal:
                    saloon_entrance(*wall,close_start=u>0,close_end=v<1,doors=True)
                else:
                    glazed_facet(*wall,1.45,.30,.76,"window")
        elif z > 50:
            saloon_entrance(a,b,c,d,close_start=abs(a.z)<50,close_end=abs(b.z)<50)
        elif z > 40:
            face([a,d,c,b],"white")
        else:
            slant = 0
            if z > 37.5:
                slant = 1 if abs(b.z)>abs(a.z) else -1
            glazed_facet(a,b,c,d,2.35,.30,.76,"window",slant)
    edge = [p + V(0,.25,0) for p in top]
    loft([top,edge],"white",caps=False)
    hface(top,"ceiling",False)
    hface(edge,"deckp")
    # The public walkway has a solid white windbreak around each bridge base.
    for s in [-1, 1]:
        side = [p for p in edge if s*p.x > 0 and abs(p.z) < 41]
        rail_loop(side, 1.02, "green", step=2.7, closed=False)
    for e in [-1, 1]:
        end = sorted([p for p in edge if p.x > 0 and e*p.z > 38], key=lambda p: e*p.z)
        path = end + [V(-p.x, p.y, p.z) for p in reversed(end)]
        windbreak_with_wings(path,e)


def windbreak_with_wings(path,e):
    # Split the top of the windbreak at each plate foot. Both meshes then
    # share the same two seams across the full thickness of the railing.
    height = .88
    rise = BRIDGE-.26-SUN
    fraction = height/rise
    foot_z = 42.88+(44.13-42.88)*fraction
    half_run = .80+(.54-.80)*fraction
    points = [path[0]]
    for a,b in zip(path,path[1:]):
        za,zb = e*a.z,e*b.z
        cuts = sorted((z for z in (foot_z-half_run,foot_z+half_run)
                       if min(za,zb)<z<max(za,zb)),reverse=za>zb)
        points.extend(a.lerp(b,(z-za)/(zb-za)) for z in cuts)
        points.append(b)

    rail = []
    for p in points:
        inside = V(p.x*.984,p.y,p.z-e*.19)
        up = V(0,min(height,(e*p.z-38)*.32),0)
        rail.append([p,inside,inside+up,p+up])

    def plate_head(ring):
        offset = (e*ring[0].z-foot_z)/half_run
        z = e*(44.13+.54*offset)
        side = math.copysign(1,ring[0].x)
        return V(side*12.03,BRIDGE-.26,z), V(side*12.23,BRIDGE-.26,z)

    def surface(vertices):
        face(vertices[::-1] if e>0 else vertices,"white")

    surface(rail[0][::-1])
    surface(rail[-1])
    for a,b in zip(rail,rail[1:]):
        carries_plate = abs(e*(a[0].z+b[0].z)/2-foot_z)<half_run
        for i in range(4):
            if i == 2 and carries_plate:
                continue
            j = (i+1)%4
            surface([a[i],a[j],b[j],b[i]])
        if carries_plate:
            ai,ao = plate_head(a)
            bi,bo = plate_head(b)
            surface([a[2],ai,bi,b[2]])
            surface([ao,a[3],b[3],bo])
            if abs(abs(e*a[0].z-foot_z)-half_run)<.0001:
                surface([a[3],ao,ai,a[2]])
            if abs(abs(e*b[0].z-foot_z)-half_run)<.0001:
                surface([b[2],bi,bo,b[3]])


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
    base = rect(0,SUN,0,8.4,19.4,2.3)
    roof = rect(0,SUN+2.82,0,7.7,18.7,2.3)
    for i,a in enumerate(base):
        j = (i+1)%len(base)
        glazed_facet(a,base[j],roof[j],roof[i],2.5,.31,.77,"window")
    hface(roof,"white")
    upper = rect(0,SUN+3.96,0,6.4,11.9,1.4)
    loft([rect(0,SUN+2.82,0,6.9,12.4,1.4),upper],"white",caps=False)
    hface(upper,"white")
    # Green-based, louvred central stack and raised black rain cap.
    y = SUN+3.96
    for bot,top,hw0,hw1,hd0,hd1,col in [
        (0,.58,3.1,3.0,6.45,6.3,"green"),(.58,4.25,3,2.48,6.3,4.8,"white"),
        (4.25,4.47,2.6,2.6,4.96,4.96,"dark")]:
        loft([rect(0,y+bot,0,hw0,hd0,.55),rect(0,y+top,0,hw1,hd1,.55)],col,caps=bot>0)
    for e in [-1,1]:
        for i in range(4):
            h=1.05+i*.78
            box(V(0,y+h,e*(6.3-(h-.58)*1.5/3.67)),(4.85,.23,.16),"dark")
    for x in [-1.15,1.15]:
        for z in [-2.7,2.7]:
            cyl(V(x,y+4.4,z),V(x,y+5.68,z),.31,.31,8,"dark")
    loft([rect(0,y+5.28,0,3.0,5.72,.8),rect(0,y+5.47,0,3.0,5.72,.8)],"dark")

    for e in [-1,1]:
        solarium(e)
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


def stretch(parts):
    # Lengthen and widen everything by STRETCH about the midships waterline,
    # heights unchanged. The rescue boats keep their size and move with their bays.
    flat = Matrix.Diagonal((STRETCH, STRETCH, 1.0, 1.0))
    for objects in parts.values():
        for ob in objects:
            if ob.name.startswith("Rescue boat"):
                ob.location.x *= STRETCH
                ob.location.y *= STRETCH
                continue
            m = ob.matrix_world.copy()
            ob.data.transform(m.inverted() @ flat @ m)


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
    stretch(parts)
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
