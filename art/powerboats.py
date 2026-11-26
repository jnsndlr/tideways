"""Build the five powerboats with blender -b -P art/powerboats.py.
Blender -Y is the bow (+Z in Godot); waterline is at zero.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector

ART = Path(__file__).resolve().parent
OUT = ART.parent / "assets/models/powerboats"
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, rgb, metal=0, rough=.42):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    for key, val in [("Base Color", (*rgb, 1)), ("Metallic", metal), ("Roughness", rough)]:
        p.inputs[key].default_value = val
    return m


navy = material("Midnight enamel", (.012, .038, .093), 0, .28)
cream = material("Warm gelcoat", (.92, .865, .72), 0, .35)
white = material("Porcelain white", (.91, .94, .93), 0, .32)
silver = material("Brushed alloy", (.46, .53, .56), .58, .36)
chrome = material("Stainless tubing", (.76, .80, .82), .78, .22)
wood = material("Varnished mahogany", (.41, .115, .035), 0, .26)
teak = material("Honey teak", (.48, .29, .145), 0, .48)
glass = material("Blue smoke glazing", (.028, .095, .135), .35, .14)
rubber = material("Nonskid charcoal", (.045, .061, .068), 0, .65)
canvas = material("Marine canvas", (.026, .074, .16), 0, .72)
aqua = material("Bottom paint", (.075, .25, .22), 0, .45)
gold = material("Bootstripe gold", (.76, .58, .22), .35, .32)
port_red = material("Nav light red", (.78, .06, .04), 0, .22)
stbd_grn = material("Nav light green", (.05, .62, .16), 0, .22)
lifering_orange = material("Safety orange", (.88, .24, .04), 0, .42)


def mesh(name, verts, faces, mat, smooth=False):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    if smooth:
        for p in data.polygons:
            p.use_smooth = True
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    data.materials.append(mat)
    if smooth:
        mod = obj.modifiers.new("EdgeSplit", "EDGE_SPLIT")
        mod.split_angle = math.radians(38)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def box(name, loc, dims, mat, bevel=.035):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    for v in obj.data.vertices:
        for i in range(3):
            v.co[i] *= dims[i]
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Soft corners", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        mod = obj.modifiers.new("Normals", "WEIGHTED_NORMAL")
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cyl(name, loc, radius, depth, mat, verts=12, rot=(0, 0, 0), smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
        mod = obj.modifiers.new("EdgeSplit", "EDGE_SPLIT")
        mod.split_angle = math.radians(40)
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def rod(a, b, radius=.025, mat=chrome):
    delta = Vector(b) - Vector(a)
    if delta.length < 1e-4:
        return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius, depth=delta.length,
                                        location=(Vector(a)+Vector(b))/2)
    obj = bpy.context.object
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return obj


def loft(name, rings, mat, bottom=True, top=True, smooth=False):
    n = len(rings[0])
    faces = [tuple(reversed(range(n)))] if bottom else []
    for i in range(len(rings)-1):
        for j in range(n):
            k = (j+1) % n
            faces.append((i*n+j, i*n+k, (i+1)*n+k, (i+1)*n+j))
    if top:
        faces.append(tuple(range((len(rings)-1)*n, len(rings)*n)))
    return mesh(name, sum(rings, []), faces, mat, smooth=smooth)


def add_cleat(x, y, z, scale=1.0):
    box("Cleat base", (x, y, z + .02*scale), (.045*scale, .14*scale, .035*scale), chrome, .01*scale)
    box("Cleat horn", (x, y, z + .055*scale), (.055*scale, .24*scale, .03*scale), chrome, .012*scale)


def add_steering_wheel(x, y, z, radius=.21, tilt=0.55):
    # Steering column + angled wheel rim
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius, minor_radius=.022,
        major_segments=16, minor_segments=6,
        location=(x, y, z), rotation=(math.pi/2 - tilt, 0, 0)
    )
    wheel = bpy.context.object
    wheel.name = "Steering wheel"
    wheel.data.materials.append(chrome)
    cyl("Helm hub", (x, y - .04, z - .02), .045, .10, rubber, verts=10,
        rot=(math.pi/2 - tilt, 0, 0))


def add_outboard(x, y_transom, z_water, scale=1.0, cowling_mat=white, leg_mat=silver):
    # Sculpted outboard motor with lower unit, skeg, prop hub, and rounded cowling
    s = scale
    box("Outboard bracket", (x, y_transom + .08*s, z_water + .36*s),
        (.24*s, .20*s, .28*s), rubber, .04*s)
    box("Outboard leg", (x, y_transom + .18*s, z_water + .04*s),
        (.18*s, .34*s, .76*s), leg_mat, .07*s)
    box("Outboard cav plate", (x, y_transom + .20*s, z_water - .24*s),
        (.32*s, .44*s, .04*s), leg_mat, .015*s)
    cyl("Prop hub", (x, y_transom + .26*s, z_water - .34*s),
        .065*s, .26*s, rubber, verts=10, rot=(math.pi/2, 0, 0))
    box("Outboard cowling", (x, y_transom + .22*s, z_water + .56*s),
        (.48*s, .66*s, .62*s), cowling_mat, .17*s)
    box("Outboard stripe", (x, y_transom + .22*s, z_water + .60*s),
        (.50*s, .52*s, .10*s), navy, .03*s)


def add_swim_ladder(x, y, z):
    for dx in (-.16, .16):
        rod((x + dx, y, z + .06), (x + dx, y + .12, z - .36), .018, chrome)
    for rz in (z - .06, z - .26):
        rod((x - .16, y + .05, rz), (x + .16, y + .05, rz), .018, chrome)


def add_life_ring(loc, rot_y=0.0):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=.24, minor_radius=.055,
        major_segments=16, minor_segments=8,
        location=loc, rotation=(0, rot_y, 0)
    )
    ring = bpy.context.object
    ring.name = "Life ring"
    ring.data.materials.append(lifering_orange)


def cabin(front, rear, width, z, height, rake, frame, cap, visor=.18):
    # Raked panes follow the cabin envelope. The sill and roof overhang the glazing.
    def ring(w, f, r, h):
        return [(-w, f, h), (w, f, h), (w, r, h), (-w, r, h)]
    sill = z + height*.26
    top = z + height
    lower = ring(width, front, rear, z)
    panes = ring(width*.98, front + rake*.26, rear, sill)
    upper = ring(width*.90, front + rake, rear - .055, top)
    loft("Cabin sill", [lower, panes], frame)
    loft("Pilothouse glass", [panes, upper], glass)
    for a, b in zip(panes, upper):
        rod(a, b, .062, frame)
    for side in (-1, 1):
        for t in (.36, .70):
            rod((side*width*.98, panes[0][1]*(1-t) + rear*t, sill),
                (side*width*.90, upper[0][1]*(1-t) + (rear-.055)*t, top), .042, frame)
    rod((0, panes[0][1], sill), (0, upper[0][1], top), .038, frame)
    # Slightly sleeker hardtop with forward brow overhang
    roof_len = rear - front - rake + .42 + visor
    roof_cy = (front + rake - visor + rear) / 2
    box("Overhanging hardtop", (0, roof_cy, top + .055),
        (width*2 + .18, roof_len, .14), cap, .065)
    # Subtle crown cap on the hardtop
    box("Hardtop crown", (0, roof_cy + .04, top + .12),
        (width*1.65, roof_len*.82, .05), cap, .02)
    # Port (red) and starboard (green) navigation sidelights
    nav_y = front + rake*.65 + .18
    nav_z = top - .04
    box("Port nav light", (-width*.95, nav_y, nav_z), (.07, .16, .08), port_red, .02)
    box("Stbd nav light", (width*.95, nav_y, nav_z), (.07, .16, .08), stbd_grn, .02)
    return top + .135


def build(name, length, beam, freeboard):
    pilot = name == "alloy_pilothouse"
    classic = name == "picnic_launch"
    yacht = name == "flybridge_yacht"
    sport = name == "cuddy_runabout"
    downeast = name == "downeast_cruiser"
    paint = silver if pilot else white if yacht else navy
    deck = silver if pilot else cream if classic else white
    trim = wood if classic else (cream if downeast else deck)
    half = beam/2

    # Finer stations from a sleek raised stem to the broad transom.
    stations = [
        (-.500, .010), (-.485, .13), (-.460, .27), (-.425, .43),
        (-.375, .58), (-.310, .73), (-.230, .86), (-.135, .95),
        (-.030, .995), (.085, 1.00), (.205, .992), (.325, .968),
        (.420, .930), (.490, .880),
    ]
    outlines = []
    for level, breadth, shift in [(-.55, .26, .065), (-.19, .82, .040), (.02, .88, .030),
                                   (.10, .89, .026), (.89, .995, .003), (.95, 1.0, 0), (1.0, .997, 0)]:
        star = []
        for t, w in stations:
            lift = max(0, (-t - .08)/.42)**2
            star.append((half*w*breadth, (t + shift*lift)*length,
                         freeboard*(level + lift*(.22 if level > 0 else .38))))
        outlines.append(star + [(-x, y, z) for x, y, z in reversed(star)])

    bootstripe = navy if yacht else (gold if downeast else white)
    for i, mat in enumerate([aqua if classic else rubber, deck, bootstripe, paint,
                             wood if classic else rubber, deck]):
        # Smooth-shaded hull strakes with crisp chine/sheer splits
        loft("Hull strake", outlines[i:i+2], mat, bottom=(i == 0), top=False, smooth=True)

    # Cambered foredeck and side decks around a recessed aft cockpit.
    rim = outlines[-1][:len(stations)]
    cockpit = .065 if sport else .23
    inside = []
    for x, y, z in rim:
        t = y/length
        inside.append((x*.82 if t >= cockpit and t < .49 else .012, y, z - .018))
    for sign in (-1, 1):
        for j in range(len(rim)-1):
            pts = [rim[j], rim[j+1], inside[j+1], inside[j]]
            mesh("Side deck", [(sign*x, y, z) for x, y, z in pts],
                 [(0, 1, 2, 3) if sign == 1 else (3, 2, 1, 0)], deck)
    loop = inside + [(-x, y, z) for x, y, z in reversed(inside)]
    low = [(x, y, z - .33) for x, y, z in loop]
    loft("Cockpit lining", [loop, low], deck, bottom=False, top=False)
    mesh("Cockpit sole", low, [tuple(range(len(low)))], rubber if pilot else teak)
    for j in range(len(inside)-1):
        if inside[j][0] <= .012 and inside[j+1][0] <= .012:
            a, b = inside[j:j+2]
            mesh("Foredeck centre", [a, b, (-b[0], b[1], b[2]), (-a[0], a[1], a[2])],
                 [(0, 1, 2, 3)], deck)

    # Bow roller + tucked anchor at the stem
    bow_x, bow_y, bow_z = rim[0]
    box("Bow roller", (0, bow_y - .08, bow_z + .03), (.12, .28, .07), chrome, .015)
    box("Anchor fluke", (0, bow_y - .18, bow_z - .05), (.16, .18, .08), silver, .02)

    # Fore and aft mooring cleats
    cleat_s = .85 if sport else (1.2 if yacht else 1.0)
    for side in (-1, 1):
        cx, cy, cz = rim[2]
        add_cleat(side*cx*.78, cy, cz + .01, cleat_s)
        sx, sy, sz = rim[-2]
        add_cleat(side*sx*.91, sy, sz + .01, cleat_s)

    # Aft bench seating
    bench_mat = cream if (classic or yacht) else canvas
    box("Aft bench", (0, .395*length, freeboard + .07), (beam*.66, .46, .22), bench_mat, .10)
    box("Bench back", (0, .424*length, freeboard + .24), (beam*.68, .18, .42), bench_mat, .08)

    if classic:
        # Small varnished teak cockpit table
        cyl("Table pedestal", (0, .325*length, freeboard - .08), .045, .44, chrome, verts=10)
        box("Cockpit table", (0, .325*length, freeboard + .16), (.68, .44, .05), wood, .02)

    if sport:
        # Helm console, steering wheel, and twin bucket seats
        box("Helm console", (0, -.04*length, freeboard + .12), (beam*.76, .52, .42), deck, .06)
        box("Dash panel", (0, -.01*length, freeboard + .32), (beam*.72, .22, .12), rubber, .03)
        add_steering_wheel(beam*.20, .01*length, freeboard + .34, radius=.19, tilt=.55)
        for side in (-1, 1):
            x = side*beam*.20
            box("Helm cushion", (x, .10*length, freeboard + .11), (.49, .50, .18), cream, .08)
            box("Helm seat back", (x, .13*length, freeboard + .28), (.49, .14, .41), cream, .065)
        # Single outboard motor on transom
        add_outboard(0, .488*length, .04, scale=.82, cowling_mat=navy, leg_mat=silver)

    if not pilot:
        plat_mat = teak if (classic or downeast or yacht) else deck
        box("Swim step", (0, .502*length, .14), (beam*.75, .055*length, .15), plat_mat, .065)
        if not sport:
            add_swim_ladder(half*.48, .502*length + .027*length, .14)

    # Bow pulpit sweeps with the sheer.
    if not classic:
        for side in (-1, 1):
            prev = None
            for j in (0, 2, 4, 6, 8):
                x, y, z = rim[j]
                a = (side*x*.95, y, z)
                b = (a[0], y - .06, z + (.30 if sport else .54))
                rod(a, b, .022)
                if prev:
                    rod(prev, b, .030)
                prev = b

    if sport:
        # Wraparound windscreen with clean frame and swept side wings
        for sign in (-1, 1):
            pts = [(0, -.16*length, freeboard + .12),
                   (sign*half*.83, -.12*length, freeboard + .12),
                   (sign*half*.76, .005*length, freeboard + .74),
                   (0, -.02*length, freeboard + .76)]
            mesh("Windshield", pts, [(0, 1, 2, 3)], glass)
            wing = (sign*half*.86, .19*length, freeboard + .08)
            mesh("Vent wing", [pts[1], wing, pts[2]], [(0, 1, 2)], glass)
            for a, b in [(pts[2], wing), (pts[1], pts[2]), (pts[2], pts[3]), (pts[0], pts[3])]:
                rod(a, b, .022, chrome)
            # Sleeker swept wakeboard / bimini arch
            base_f = (sign*half*.84, .12*length, freeboard)
            base_r = (sign*half*.84, .32*length, freeboard)
            top_p = (sign*half*.76, .24*length, freeboard + 1.58)
            rod(base_f, top_p, .030, chrome)
            rod(base_r, top_p, .028, chrome)
        rod((-half*.76, .24*length, freeboard + 1.58),
            (half*.76, .24*length, freeboard + 1.58), .034, chrome)
        box("Folded bimini", (0, .24*length, freeboard + 1.62), (beam*.78, .22, .16), canvas, .07)
    else:
        f = -.29 if yacht else -.08 if classic else -.17
        rear = .32 if yacht else .235
        roof = cabin(f*length, rear*length, half*.85, freeboard - .035,
                     1.82 if yacht else 1.38, -.32 if pilot else .65, trim, deck)

        if yacht:
            # Open flybridge deck with wraparound venturi windscreen, helm, seating & radar arch
            fb_w = half*.68
            fb_f = -.13*length
            fb_r = .24*length
            # Low coaming around flybridge deck
            box("Flybridge coaming L", (-fb_w, (fb_f + fb_r)/2, roof + .24), (.12, fb_r - fb_f, .46), white, .04)
            box("Flybridge coaming R", (fb_w, (fb_f + fb_r)/2, roof + .24), (.12, fb_r - fb_f, .46), white, .04)
            box("Flybridge coaming F", (0, fb_f, roof + .28), (fb_w*2 + .10, .28, .54), white, .06)
            # Smoked glass venturi windscreen
            ws_z0 = roof + .52
            ws_z1 = roof + 1.02
            for sign in (-1, 1):
                p0 = (0, fb_f - .06, ws_z0)
                p1 = (sign*fb_w*.96, fb_f + .08, ws_z0)
                p2 = (sign*fb_w*.92, fb_f + .55, ws_z1)
                p3 = (0, fb_f + .38, ws_z1)
                mesh("Flybridge glass", [p0, p1, p2, p3], [(0, 1, 2, 3)], glass)
                p4 = (sign*fb_w*.96, fb_f + 1.35, ws_z0 + .06)
                mesh("Flybridge wing", [p1, p4, p2], [(0, 1, 2)], glass)
                rod(p3, p2, .024, chrome)
                rod(p2, p4, .024, chrome)
            # Upper helm console, wheel, and captain/guest benches
            box("Upper helm", (0, fb_f + .55, roof + .38), (fb_w*1.4, .55, .52), white, .07)
            add_steering_wheel(fb_w*.32, fb_f + .88, roof + .68, radius=.22, tilt=.5)
            box("Bridge helm bench", (0, fb_f + 1.55, roof + .34), (fb_w*1.35, .52, .22), cream, .09)
            box("Bridge helm back", (0, fb_f + 1.78, roof + .58), (fb_w*1.35, .18, .44), cream, .07)
            box("Bridge aft lounge", (0, fb_r - .42, roof + .30), (fb_w*1.55, .52, .22), cream, .09)
            # Stainless aft bridge railing
            for side in (-1, 1):
                for ry in (fb_f + 1.45, fb_r - .05):
                    rod((side*fb_w, ry, roof + .44), (side*fb_w, ry, roof + .92), .024, chrome)
                rod((side*fb_w, fb_f + 1.45, roof + .92), (side*fb_w, fb_r - .05, roof + .92), .026, chrome)
            rod((-fb_w, fb_r - .05, roof + .92), (fb_w, fb_r - .05, roof + .92), .026, chrome)
            # Swept radar arch over flybridge
            arch_y0 = fb_f + 2.05
            arch_y1 = fb_f + 2.65
            arch_z = roof + 1.85
            for side in (-1, 1):
                rod((side*fb_w*.96, arch_y0, roof + .42), (side*fb_w*.80, arch_y1, arch_z), .085, white)
            box("Radar arch beam", (0, arch_y1, arch_z + .04), (fb_w*1.70, .38, .18), white, .07)
            cyl("Radar dome", (0, arch_y1 - .02, arch_z + .24), .32, .22, white, verts=16)
            rod((0, arch_y1 + .05, arch_z + .34), (0, arch_y1 + .08, arch_z + 1.05), .022, chrome)
            cyl("Anchor light", (0, arch_y1 + .08, arch_z + 1.08), .045, .07, cream, verts=10)

        if classic:
            # Raised varnished trunk tapers with the long foredeck.
            rows = []
            for t, w, h in [(-.435, .16, .13), (-.39, .43, .22), (-.29, .65, .28), (-.08, .81, .34)]:
                y = t*length
                rows.append([(-half*w, y, freeboard + .04), (-half*w*.96, y, freeboard + h),
                             (half*w*.96, y, freeboard + h), (half*w, y, freeboard + .04)])
            trunk = loft("Mahogany trunk", rows, wood)
            trunk.data.materials.append(cream)
            for p in trunk.data.polygons:
                if p.normal.z > .8:
                    p.material_index = 1

        if classic or yacht:
            for side in (-1, 1):
                if yacht:
                    for t, w in ((-.23, .86), (-.09, .975), (.075, 1), (.24, .99)):
                        box("Hull port", (side*half*w*.974, t*length, freeboard*.72),
                            (.065, .44, .16), glass, .042)
                else:
                    for t, w in ((-.29, .65), (-.19, .73), (-.105, .79)):
                        pane = box("Trunk port", (side*half*w*.989, t*length, freeboard + .17),
                                   (.06, .48, .105), glass, .035)
                        pane.rotation_euler.z = -side*.11

        if not yacht:
            # Cabin roof grab rails
            for side in (-1, 1):
                x = side*half*.65
                ends = [(x, y, roof + .085) for y in (f*length + .93, rear*length - .34)]
                for end in ends:
                    rod((end[0], end[1], roof), end, .026, trim)
                rod(*ends, .035, wood if classic else chrome)
            # Spotlight on forward cabin brow
            cyl("Brow spotlight", (0, f*length + (.05 if pilot else .55), roof + .11),
                .075, .14, chrome, verts=12, rot=(math.pi/2, 0, 0))
            # Mast, radar dome, and masthead light
            mast_y = .07*length
            rod((0, mast_y, roof), (0, mast_y + .30, roof + .76), .085, wood if classic else chrome)
            rod((0, mast_y + .30, roof + .76), (0, mast_y + .33, roof + 1.44), .018, chrome)
            cyl("Anchor light", (0, mast_y + .33, roof + 1.46), .04, .06, cream, verts=10)
            if not classic:
                cyl("Radar dome", (0, mast_y + .14, roof + .46), .26, .18, white, verts=16)
            else:
                # Classic yardarm cross-spar
                rod((-.38, mast_y + .22, roof + .58), (.38, mast_y + .22, roof + .58), .022, wood)

        # Foredeck hatch
        hatch_y = (-.34 if yacht else -.29)*length
        hatch_z = freeboard + (.31 if classic else .095)
        box("Forehatch bezel", (0, hatch_y, hatch_z), (beam*.31, .57, .10), chrome)
        box("Smoked hatch", (0, hatch_y, hatch_z + .058), (beam*.27, .49, .045), glass)

        if downeast:
            # Life ring on starboard cabin side
            add_life_ring((half*.84, .14*length, freeboard + .42), rot_y=math.pi/2)

        if pilot:
            # Twin sculpted outboards + aft gantry arch + roof rocket-launcher rod holders
            for sign in (-1, 1):
                x = sign*half*.46
                add_outboard(x, .49*length, .04, scale=1.0, cowling_mat=white, leg_mat=silver)
                rod((sign*half*.83, .30*length, freeboard),
                    (sign*half*.83, .40*length, freeboard + .95), .045, silver)
            rod((-half*.83, .40*length, freeboard + .95),
                (half*.83, .40*length, freeboard + .95), .05, silver)
            # Rocket launcher rod holders along aft edge of hardtop
            rl_y = rear*length + .16
            rl_z = roof + .14
            rod((-half*.70, rl_y, rl_z), (half*.70, rl_y, rl_z), .028, chrome)
            for rx in (-half*.52, -half*.18, half*.18, half*.52):
                rod((rx, rl_y, rl_z), (rx, rl_y + .10, rl_z + .28), .028, chrome)
            add_life_ring((-half*.84, .12*length, freeboard + .42), rot_y=math.pi/2)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.name = name
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name + ".glb")), use_selection=True)
    return obj


fleet = []
for spec in [("downeast_cruiser", 10.4, 3.4, 1.02), ("flybridge_yacht", 15.4, 4.45, 1.42),
             ("picnic_launch", 10.9, 3.18, .92), ("alloy_pilothouse", 8.4, 2.92, 1.00),
             ("cuddy_runabout", 6.3, 2.38, .68)]:
    boat = build(*spec)
    fleet.append(boat)
    bpy.ops.object.select_all(action="DESELECT")
    boat.hide_set(True)

for obj, pos in zip(fleet, [(-5, -6), (3, -6), (-7, 8), (-.5, 8), (5.4, 8)]):
    obj.hide_set(False)
    obj.location = (pos[0], pos[1], 0)
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ART/"powerboats.blend"))
