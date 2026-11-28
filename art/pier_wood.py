"""Shared weathered fir, with tapered grain cut into the low-poly mesh."""
import random
import bpy

BOARD_COLORS = ((.34, .225, .135), (.38, .26, .164),
                (.36, .246, .155), (.32, .219, .145))
TIMBER_COLOR = (.17, .118, .082)


def grain(obj, rng):
    """Split long quad faces around a wandering streak. All faces stay flush."""
    mesh = obj.data
    base = mesh.materials[0]
    name = base.name + " grain"
    ink = bpy.data.materials.get(name)
    if ink is None:
        ink = base.copy()
        ink.name = name
        rgb = [v * .74 for v in base.diffuse_color[:3]]
        ink.diffuse_color = (*rgb, 1)
        ink.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)

    vertices = [v.co.copy() for v in mesh.vertices]
    faces, markings = [], []
    for face in mesh.polygons:
        corners = list(face.vertices)
        if len(corners) != 4:
            faces.append(corners)
            continue
        a, b, c, d = (vertices[i] for i in corners)
        length = ((b-a) * obj.scale).length
        width = ((d-a) * obj.scale).length
        if width > length:
            corners = corners[1:] + corners[:1]
            a, b, c, d = (vertices[i] for i in corners)
            length, width = width, length
        if width < .05 or length < max(.45, 2.5 * width):
            faces.append(corners)
            continue
        start, end = rng.uniform(.04, .30), rng.uniform(.68, .96)
        middle = rng.uniform(.4, .64)
        across = rng.uniform(.25, .71)
        split = len(vertices)
        for u, v in [(start, across), (middle, across-.065),
                     (end, across+.045), (middle, across+.065)]:
            vertices.append(a.lerp(b, u).lerp(d.lerp(c, u), v))
        p, q, r, s = range(split, split+4)
        i, j, k, l = corners
        faces.extend([(i,j,q), (i,q,p), (j,r,q), (j,k,r),
                      (k,l,s), (k,s,r), (l,p,s), (l,i,p)])
        markings.append(len(faces))
        faces.append((p,q,r,s))
    mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(ink)
    for index in markings:
        mesh.polygons[index].material_index = 1
