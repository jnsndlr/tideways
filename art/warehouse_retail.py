"""Build the warehouse retailers and independently placeable parking lots."""
import sys
from math import radians
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retail_stores import (OUT, blue, box, cream, dark, export_model, glass,
                           green, paint, preview, red, sand, shell, sign, steel,
                           window, wood)

orange = paint('Tool orange', 'dd702c')
white = paint('Warehouse porcelain', 'e6e8df')
navy = paint('Builders navy', '263e52')
asphalt = paint('Asphalt', '51575a')
leaf = paint('Coastal shrub', '74946a')


def sloping_beam(name, start, end, width, depth, material):
    span = Vector(end) - Vector(start)
    obj = box(name, (Vector(start)+Vector(end))/2, (width, depth, span.length), material)
    obj.rotation_euler = span.to_track_quat('Z', 'Y').to_euler()


def warehouse():
    shell(48, 32, 8.4, white, steel)
    # Fluted warehouse skin, interrupted by the horizontal membership-club band.
    for x in range(-23, 24):
        box('Sheet lap', (x, -16.04, 4.44), (.075, .09, 8.36), steel)
    box('Club red belt', (0, 0, 4.71), (48.20, 32.24, .53), red)
    box('Name panel', (-9, -16.24, 7.42), (18, .54, 4.34), white)
    sign('MEGABOX', -9, -16.54, 7.96, 2.85, red)
    sign('W A R E H O U S E   C L U B', -9, -16.54, 6.19, .78, blue)
    for x in (-15, -9, -3):
        window(x, -16.20, 5.6, entry=True)
    box('Member canopy', (-9, -17.48, 4.1), (20, 3.58, .45), red)
    for x in (-18.4, .4):
        box('Canopy leg', (x, -19, 2.05), (.28, .28, 4.1), red)
    for x in (10, 16):
        box('Tyre service jamb', (x, -16.11, 2.06), (5.35, .26, 3.72), navy)
        box('Tyre bay shutter', (x, -16.27, 1.98), (4.88, .1, 3.46), steel)
        for dx in (-1.45, 0, 1.45):
            box('Bay vision panel', (x+dx, -16.34, 2.68), (1.26, .05, .44), glass)
    box('Service sign panel', (13, -16.14, 5.78), (10, .22, 1.36), navy)
    sign('TIRE CENTER', 13, -16.26, 5.78, 1.05, cream)
    for x in (-16, -8, 0, 8, 16):
        box('Roof light curb', (x, -4, 9.03), (3.8, 1.94, .3), steel)
        box('Translucent roof light', (x, -4, 9.23), (3.54, 1.72, .18), glass)


def builders():
    shell(32, 23, 6.9, sand, navy)
    box('Workshop orange belt', (0, 0, 4.9), (32.18, 23.2, .51), orange)
    box('Entry sign tower', (-6, -11.78, 4.64), (13, .92, 8.8), navy)
    sign('TIDELINE', -6, -12.26, 7.58, 1.98, cream)
    sign('BUILDERS SUPPLY', -6, -12.26, 5.98, .91, cream)
    window(-6, -12.33, 6.2, entry=True)
    box('Entry hood', (-6, -13, 4.26), (14, 2.9, .42), orange)
    for x in (3.8, 10.4):
        window(x, -11.63, 5.8)
    # Open-sided lumber pickup shed with exposed trusses and stickered bundles.
    box('Lumber apron', (20.8, 0, .11), (9.65, 23.5, .22), sand)
    for y in (-10.6, 0, 10.6):
        for x in (16.4, 24.9):
            box('Shed column', (x, y, 2.84), (.31, .31, 5.28), navy)
            sloping_beam('Rafter', (x, y, 5.36), (20.65, y, 7.24), .26, .25, orange)
        box('Truss tie', (20.65, y, 5.34), (8.65, .24, .23), orange)
    for side in (-1, 1):
        box('Shed roof', (20.65+side*2.35, 0, 6.40), (5.22, 23.6, .22), navy).rotation_euler.y = side*radians(24)
    for y in (-6.8, 1.3, 7.5):
        for level in range(3):
            box('Lumber bundle', (22.7, y, .54+level*.61), (2.9, 4.3, .48), wood)
            for dy in (-1.32, 1.32):
                box('Bundle strap', (22.7, y+dy, .54+level*.61), (2.94, .09, .5), dark)
    box('Pickup fascia', (20.65, -11.56, 4.83), (9, .18, 1.07), orange)
    sign('LUMBER PICKUP', 20.65, -11.67, 4.82, .84, navy)


def parking(columns, rows):
    pitch, stall, lane = 2.75, 5.1, 6.3
    block = 2*stall+lane
    depth = stall+lane if rows == 1 else rows//2*block
    width = columns*pitch
    # Open end aisles connect every row. All lot assets pivot at ground center.
    box('Asphalt pad', (0, 0, .07), (width+2*lane, depth+1, .14), asphalt)
    for row in range(rows):
        near = depth/2 - row//2*block
        direction = -1 if row%2 == 0 else 1
        head = near if direction == -1 else near-block
        y = head+direction*stall/2
        for i in range(columns+1):
            x = -width/2+i*pitch
            box('Stall divider', (x, y, .155), (.10, stall, .025), white)
        for i in range(columns):
            x = -width/2+(i+.5)*pitch
            box('Wheel stop', (x, head+direction*.62, .24), (1.55, .21, .20), sand)
    for side in (-1, 1):
        x, y = side*(width/2+lane/2), depth/2-1
        box('Planted curb', (x, y, .25), (4.65, 1.54, .28), sand)
        box('Planting bed', (x, y, .4), (4.28, 1.22, .12), green)
        for dx in (-1.4, 1.4):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.64, location=(x+dx, y, .7))
            bpy.context.object.name = 'Saltbush'
            bpy.context.object.data.materials.append(leaf)
        box('Lot light post', (x, y, 2.88), (.16, .16, 4.96), dark)
        box('Light head', (x, y-.35, 5.32), (.52, .96, .20), steel)


export_model('megabox_warehouse', warehouse, (36, 7))
export_model('tideline_builders_supply', builders, (-19, 7))
for name, columns, rows, pos in [
    ('parking_small', 6, 1, (-57, -8)),
    ('parking_medium', 8, 2, (-17, -16)),
    ('parking_large', 14, 4, (36, -30)),
]:
    export_model(name, lambda: parking(columns, rows), pos)

# The neighborhood grocery gives the six-space lot a familiar scale.
bpy.ops.import_scene.gltf(filepath=str(OUT/'saltwater_grocery.glb'))
for obj in bpy.context.selected_objects:
    if not obj.parent:
        obj.location += Vector((-57, 7, 0))
preview('warehouse_retail', Vector((2, -9, 1)), Vector((22, -90, 69)), 150, 960)
