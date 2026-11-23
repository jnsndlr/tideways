"""Run with Blender in background mode to build the historic ferry mooring kit."""
import math
import random
from pathlib import Path

import numpy as np
import bpy
from mathutils import Vector, geometry

ART = Path(__file__).resolve().parent
MODELS = ART.parent / "assets/models"
TAU = math.tau
rng = random.Random(321)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.context.preferences.filepaths.save_version = 0


def material(name, rgb, metallic=0, roughness=.78):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    for key, value in [("Base Color", (*rgb, 1)), ("Metallic", metallic), ("Roughness", roughness)]:
        shader.inputs[key].default_value = value
    return mat


def shades(name, rgb, factors):
    return [material(f"{name} {i+1}", [c * f for c in rgb]) for i, f in enumerate(factors)]


wood = shades("Salt-worn fir", (.31, .147, .062), [.62, .78, .89, 1, 1.14, 1.27])
wet = shades("Tide stain", (.09, .065, .034), [.8, 1, 1.2])
ends = shades("Sawn end grain", (.43, .256, .131), [.82, .94, 1.04, 1.12])
steel = material("Oxidized strap", (.21, .22, .215), .66, .56)
edge = material("Worn steel edge", (.38, .36, .31), .68, .44)
bolt = material("Iron fasteners", (.105, .086, .065), .58)
checks = material("Seasoning checks", (.078, .04, .02))


def mesh(name, verts, faces, materials, indices):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    for mat in materials:
        data.materials.append(mat)
    for poly, index in zip(data.polygons, indices):
        poly.material_index = index
    return obj


def painted_timber():
    """Paint a seamless, ten-metre strip of wet bark with clustered acorn shells."""
    randomizer = random.Random(715)
    width, height = 512, 2048
    y, x = np.ogrid[:height, :width]
    phase = TAU*x/width
    grain = .95 + .11*np.sin(17*phase + .4*np.sin(y/89)) + .07*np.cos(59*phase)
    pixels = np.ones((height, width, 4), dtype=np.float32)
    pixels[:, :, :3] = grain[:, :, None] * np.array([83, 70, 50])/255
    for _ in range(58):
        longitude = randomizer.random()
        depth = .16 + 2.75*randomizer.random()**1.7
        for _ in range(randomizer.randint(4, 9)):
            cx = int(width*(longitude + randomizer.gauss(0, .026))) % width
            cz = max(.09, depth + randomizer.gauss(0, .09))
            cy = int(height*(1-(cz+.2)/10))
            radius = randomizer.uniform(.021, .049)
            rx, ry = radius*width/2.25, radius*height/10
            dx = np.arange(-math.ceil(rx*1.2), math.ceil(rx*1.2)+1)
            dy = np.arange(-math.ceil(ry*1.2), math.ceil(ry*1.2)+1)
            u, v = dx[None,:]/rx, dy[:,None]/ry
            theta = np.arctan2(v,u)
            facets = np.cos(6*theta + randomizer.random()*TAU)
            r = np.sqrt(u*u+v*v)*(1+.075*facets)
            shade = (.80+.16*v-.13*u+.10*facets)*randomizer.uniform(.8,1.08)
            color = shade[:,:,None]*np.array([202,185,151])/255
            color[r<.33] = [.26,.23,.19]
            color[(r>=.33)&(r<.48)] *= 1.14
            alpha = np.clip((1-r)*min(rx,ry),0,1)[:,:,None]
            patch = np.ix_(cy+dy,(cx+dx)%width)
            pixels[patch[0],patch[1],:3] = pixels[patch[0],patch[1],:3]*(1-alpha)+color*alpha
    image = bpy.data.images.new("Wet timber and barnacle colonies", width, height, alpha=False)
    image.pixels.foreach_set(pixels.ravel())
    image.pack()
    mat = material("Painted submerged timber", (.09,.065,.034))
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    return mat


paint = painted_timber()


def pile(x, y, radius, top, depth, name, sides):
    angles = [TAU * (i + rng.uniform(-.19, .19)) / sides for i in range(sides)]
    radii = [radius * rng.uniform(.965, 1.03) for _ in angles]
    low = [rng.uniform(-.04, .065) for _ in angles]
    slope = rng.uniform(-.085, .085)
    grain = [max(0, min(5, round(rng.gauss(rng.uniform(2, 3), 1)))) for _ in angles]
    verts, faces, ids = [], [], []
    rings = [(-depth, 1.10), (.12, 1.025), (.34, 1.02), (top-.07, 1), (top, .93)]
    for row, (z, scale) in enumerate(rings):
        for i, a in enumerate(angles):
            h = z + (low[i] if row in (1, 2) else slope * math.cos(a) if row >= 3 else 0)
            # Battered piles spread at the foot and come together at their heads.
            lean = 1 + (top-h)*.077
            verts.append((x*lean + scale*radii[i]*math.cos(a),
                          y*lean + scale*radii[i]*math.sin(a), h))
        if row:
            for i in range(sides):
                j = (i+1) % sides
                base = (row-1)*sides
                faces.append((base+i, base+j, base+j+sides, base+i+sides))
                ids.append(6 + grain[i] % 3 if row == 1 else grain[i])
    faces.append(tuple(reversed(range(sides))))
    ids.append(6)
    # Nested, eccentric growth rings and a pair of radial splits on the cut face.
    rim = verts[-sides:]
    previous = len(verts)-sides
    core = Vector((x+.08*radius, y-.12*radius, top))
    for k, fraction in enumerate([.69, .63]):
        start = len(verts)
        verts.extend(tuple(core.lerp(Vector(v), fraction)) for v in rim)
        for i in range(sides):
            j = (i+1) % sides
            faces.append((previous+i, previous+j, start+j, start+i))
            ids.append(9 + [2, 0][k])
        previous = start
    faces.append(tuple(range(previous, previous+sides)))
    ids.append(11)
    for i in rng.sample(range(sides), 2):
        a, b = Vector(rim[i]), Vector(rim[(i+1)%sides])
        start = len(verts)
        for v in [a, a.lerp(b, .53), a.lerp(core, rng.uniform(.39, .73))]:
            verts.append(tuple(v + Vector((0, 0, .002))))
        faces.append((start, start+1, start+2))
        ids.append(13)
    obj = mesh(name, verts, faces, wood+wet+ends+[checks, paint], ids)
    uv = obj.data.uv_layers.new(name="Bark wrap")
    shift = (math.atan2(y, x)/TAU + top*.61) % 1
    for i, poly in enumerate(list(obj.data.polygons)[:sides]):
        poly.material_index = len(obj.data.materials)-1
        for corner, loop in enumerate(poly.loop_indices):
            z = verts[obj.data.loops[loop].vertex_index][2]
            uv.data[loop].uv = (shift + (i + int(corner in (1,2)))/sides, 1+(z-.2)/10)
    return x, y, top, angles, radii


def strap(piles, z, height):
    points = []
    for x, y, top, angles, radii in piles:
        lean = 1 + (top-z)*.077
        for a, r in zip(angles, radii):
            points.append(Vector((x*lean + (r*1.024+.012)*math.cos(a),
                                  y*lean + (r*1.024+.012)*math.sin(a))))
    hull = [points[i] for i in geometry.convex_hull_2d(points)]
    if sum(p.x*q.y-q.x*p.y for p,q in zip(hull, hull[1:]+hull[:1])) < 0:
        hull.reverse()
    verts, faces, ids = [], [], []
    profile = [(-.012, 0), (.024, .012), (.024, height-.012), (-.012, height)]
    n = len(hull)
    for row, (offset, h) in enumerate(profile):
        for i, p in enumerate(hull):
            v = p + p.normalized()*offset
            verts.append((*v, z+h))
            j = (i+1)%n
            nxt = (row+1)%len(profile)
            faces.append((row*n+i, row*n+j, nxt*n+j, nxt*n+i))
            ids.append(0 if row == 1 else 1)
    mesh("Rolled steel binding", verts, faces, [steel, edge], ids)
    for p, q in zip(hull, hull[1:]+hull[:1]):
        if (q-p).length < .3:
            continue
        normal = Vector((q.y-p.y, p.x-q.x, 0)).normalized()
        for t in (.26, .74):
            center = Vector((*p.lerp(q,t), z+height*.5)) + normal*.03
            bpy.ops.mesh.primitive_uv_sphere_add(segments=6, ring_count=2, location=center)
            obj = bpy.context.object
            obj.name = "Domed rivet"
            obj.rotation_euler = normal.to_track_quat('Z','Y').to_euler()
            obj.scale = (.035, .035, .018)
            obj.data.materials.append(bolt)


def build(size, count, radius, height, depth, offset):
    existing = set(scene.objects)
    sides = 18 if size == "small" else 12
    orbit = radius / math.sin(math.pi/count)
    piles = []
    for i in range(count):
        a = TAU*i/count + .22
        piles.append(pile(orbit*math.cos(a), orbit*math.sin(a), radius,
                          height + rng.uniform(-.15, .17), depth, f"{size} timber {i+1}", sides))
    if count == 6:
        piles.append(pile(0, 0, radius, height+.21, depth, "Heart pile", 10))
    strap(piles, height*.21, height*.061)
    strap(piles, height*.77, height*.075)
    objects = set(scene.objects)-existing
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(MODELS/f"timber_dolphin_{size}.glb"), use_selection=True)
    coll = bpy.data.collections.new(size.title()+" mooring dolphin")
    scene.collection.children.link(coll)
    for obj in objects:
        for parent in list(obj.users_collection):
            parent.objects.unlink(obj)
        coll.objects.link(obj)
        obj.location.x += offset


build("small", 4, .31, 2.65, 7.0, -2.12)
build("large", 6, .385, 3.45, 9.0, 1.4)

# The water and lighting belong only to the comparison scene.
bpy.ops.mesh.primitive_plane_add(size=200)
water_plane = bpy.context.object
water = material("Harbor water", (.019, .087, .091), .22, .27)
bpy.context.object.data.materials.append(water)
nodes = water.node_tree.nodes
links = water.node_tree.links
noise = nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 4
tex = nodes.new("ShaderNodeTexCoord")
links.new(tex.outputs["Object"], noise.inputs["Vector"])
bump = nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = .19
bump.inputs["Distance"].default_value = .065
links.new(noise.outputs["Fac"], bump.inputs["Height"])
links.new(bump.outputs["Normal"], nodes["Principled BSDF"].inputs["Normal"])

def aim(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

bpy.ops.object.camera_add(location=(5,-13,6.75))
scene.camera = bpy.context.object
aim(scene.camera, (0,0,1.45))
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = 8.25
for pos, power, size in [((-3,-5,8), 1050, 5), ((2,4,6), 1450, 4)]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    light = bpy.context.object
    light.data.energy, light.data.shape, light.data.size = power, 'DISK', size
    aim(light, (0,0,1))
scene.world = bpy.data.worlds.new("Overcast sky")
scene.world.color = (.32,.34,.36)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 12
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 1000, 680
scene.render.resolution_percentage = 100
scene.render.filepath = "//timber_dolphins_preview.png"
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        area.spaces.active.shading.color_type = 'MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(ART/"timber_dolphins.blend"))
bpy.ops.render.render(write_still=True)

# Reveal the full embedment for the second inspection view.
water_plane.location.z = -9.02
scene.camera.location = (4, -20, 1.2)
aim(scene.camera, (0, 0, -2.65))
scene.camera.data.ortho_scale = 14.7
scene.render.resolution_x, scene.render.resolution_y = 760, 1080
scene.render.filepath = "//timber_dolphins_submerged_preview.png"
bpy.ops.render.render(write_still=True)
