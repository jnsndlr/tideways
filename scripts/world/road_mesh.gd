class_name RoadMesh
extends RefCounted
## Town road strips for road.gdshader: asphalt between gravel shoulders, with short
## skirts down into the graded ground (MapGenerator lays the road a little above it).
## UV.x is metres across from the centreline (+ right), UV.y metres along; UV2.x how
## strongly the markings show there, UV2.y the marking Style (road_detail.gdshaderinc).

enum Style { NONE, DASHED, DASHED_EDGES, DOUBLE_EDGES }

## Half the asphalt's width (must match RD_ASPHALT_HALF in road_detail.gdshaderinc),
## and half the whole road's, shoulders and all.
const ASPHALT_HALF := 3.7
const HALF := 5.1
## The shoulders fall away this much to their outer edge.
const SHOULDER_DROP := 0.05
const SKIRT := 0.45


## Horizontal length of a polyline.
static func length_of(points: PackedVector3Array) -> float:
	var total := 0.0
	for i in points.size() - 1:
		total += Vector2(points[i + 1].x - points[i].x, points[i + 1].z - points[i].z).length()
	return total


## Adds a strip along `points` (its centreline, at the road's surface) to `mb`,
## starting `start` metres along (a side street starts at the edge of the road it
## leaves). `show` maps metres along to how strongly the markings show (0..1).
static func strip(mb: MeshBuilder, points: PackedVector3Array, col: Color, style: Style, show: Callable, start := 0.0) -> void:
	# Stations: metres along, centre, and the right-hand unit vector (mitred).
	var along := PackedFloat32Array()
	var centres := PackedVector3Array()
	var s := 0.0
	for i in points.size():
		if i > 0:
			var seg := Vector2(points[i].x - points[i - 1].x, points[i].z - points[i - 1].z).length()
			if seg < 0.01:
				continue
			if s < start and s + seg > start:
				along.append(start)
				centres.append(points[i - 1].lerp(points[i], (start - s) / seg))
			s += seg
		if s >= start:
			along.append(s)
			centres.append(points[i])
	if centres.size() < 2:
		return
	var rights := PackedVector3Array()
	for i in centres.size():
		var d := centres[mini(i + 1, centres.size() - 1)] - centres[maxi(i - 1, 0)]
		d.y = 0.0
		rights.append(d.normalized().cross(Vector3.UP))
	var xs: Array[float] = [-HALF, -ASPHALT_HALF, ASPHALT_HALF, HALF]
	var drops: Array[float] = [SHOULDER_DROP, 0.0, 0.0, SHOULDER_DROP]
	for i in centres.size() - 1:
		var row0: Array[Vector3] = []
		var row1: Array[Vector3] = []
		for k in 4:
			row0.append(centres[i] + rights[i] * xs[k] + Vector3(0, -drops[k], 0))
			row1.append(centres[i + 1] + rights[i + 1] * xs[k] + Vector3(0, -drops[k], 0))
		var d0 := Vector2(show.call(along[i]), style)
		var d1 := Vector2(show.call(along[i + 1]), style)
		for k in 3:
			_quad(mb, row0[k], row0[k + 1], row1[k + 1], row1[k],
				Vector2(xs[k], along[i]), Vector2(xs[k + 1], along[i]), Vector2(xs[k + 1], along[i + 1]), Vector2(xs[k], along[i + 1]),
				d0, d0, d1, d1, col, Vector3.UP)
		# Skirts down the outer edges.
		var down := Vector3(0, -SKIRT, 0)
		for k: int in [0, 3]:
			var out := rights[i] * signf(xs[k])
			_quad(mb, row0[k], row1[k], row1[k] + down, row0[k] + down,
				Vector2(xs[k], along[i]), Vector2(xs[k], along[i + 1]), Vector2(xs[k] * 1.02, along[i + 1]), Vector2(xs[k] * 1.02, along[i]),
				d0, d1, d1, d0, col, out)
	# And across the far end, where a street stops.
	var last := centres.size() - 1
	var end_d := Vector2(0.0, style)
	var fwd := -rights[last].cross(Vector3.UP)
	var down := Vector3(0, -SKIRT, 0)
	for k in 3:
		var a := centres[last] + rights[last] * xs[k] + Vector3(0, -drops[k], 0)
		var b := centres[last] + rights[last] * xs[k + 1] + Vector3(0, -drops[k + 1], 0)
		_quad(mb, a, b, b + down, a + down,
			Vector2(xs[k], along[last]), Vector2(xs[k + 1], along[last]), Vector2(xs[k + 1], along[last] + 0.4), Vector2(xs[k], along[last] + 0.4),
			end_d, end_d, end_d, end_d, col, fwd)


static func _quad(mb: MeshBuilder, a: Vector3, b: Vector3, c: Vector3, d: Vector3,
		ua: Vector2, ub: Vector2, uc: Vector2, ud: Vector2,
		va: Vector2, vb: Vector2, vc: Vector2, vd: Vector2, col: Color, outward: Vector3) -> void:
	_tri(mb, a, b, c, ua, ub, uc, va, vb, vc, col, outward)
	_tri(mb, a, c, d, ua, uc, ud, va, vc, vd, col, outward)


## As MeshBuilder.tri (untransformed), with both UV sets.
static func _tri(mb: MeshBuilder, a: Vector3, b: Vector3, c: Vector3, ua: Vector2, ub: Vector2, uc: Vector2,
		va: Vector2, vb: Vector2, vc: Vector2, col: Color, outward: Vector3) -> void:
	var n := (b - a).cross(c - a)
	if n.length_squared() < 1e-10:
		return
	n = n.normalized()
	if n.dot(outward) < 0.0:
		n = -n
		var tb := b
		b = c
		c = tb
		var tu := ub
		ub = uc
		uc = tu
		var tv := vb
		vb = vc
		vc = tv
	# Clockwise is front-facing in Godot: emit in reverse of the right-hand order.
	mb.verts.append_array([a, c, b])
	mb.normals.append_array([n, n, n])
	mb.colors.append_array([col, col, col])
	mb.uvs.append_array([ua, uc, ub])
	mb.uv2s.append_array([va, vc, vb])
