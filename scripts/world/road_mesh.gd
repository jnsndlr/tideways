class_name RoadMesh
extends RefCounted
## Town road strips for road.gdshader: asphalt between gravel shoulders, with short
## skirts down into the graded ground (MapGenerator lays the road a little above it).
## UV.x is metres across from the centreline (+ right), UV.y metres along; UV2.x how
## strongly the markings show there, UV2.y the marking Style (road_detail.gdshaderinc).

enum Style { NONE, DASHED, DASHED_EDGES, DOUBLE_EDGES, CORE_WALK, LANE }

## Half the asphalt's width (must match RD_ASPHALT_HALF in road_detail.gdshaderinc),
## and half the whole road's, shoulders and all.
const ASPHALT_HALF := 3.7
const HALF := RoadGeometry.HALF_WIDTH
## The shoulders fall away this much to their outer edge.
const SHOULDER_DROP := 0.05
const SKIRT := 0.60


## Adds a strip along `points` (its centreline, at the road's surface) to `mb`,
## starting `start` metres along (a side street starts at the edge of the road it
## leaves). `show` maps metres along to how strongly the markings show (0..1).
static func strip(
	mb: MeshBuilder,
	points: PackedVector3Array,
	col: Color,
	style: Style,
	show: Callable,
	start := 0.0,
	stop := INF
) -> void:
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
			if s < stop and s + seg >= stop:
				along.append(stop)
				centres.append(points[i - 1].lerp(points[i], (stop - s) / seg))
				break
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


## A joined junction: one plain-asphalt plate where streets meet, with the kerb and
## sidewalk curving round each corner from one street's to the next. Each arm's strip
## ends at `mouths[i]`, running out along `tangents[i]` (flat unit vectors, away from
## the junction); `styles[i]` is its Style (sidewalk corners only between two
## sidewalked streets, gravel verge otherwise).
static func junction(
	mb: MeshBuilder,
	centre: Vector3,
	mouths: PackedVector3Array,
	tangents: PackedVector3Array,
	styles: Array[int],
	col: Color
) -> void:
	var n := mouths.size()
	if n < 2:
		return
	var order: Array[int] = []
	for i in n:
		order.append(i)
	order.sort_custom(
		func(a: int, b: int) -> bool:
			var da := mouths[a] - centre
			var db := mouths[b] - centre
			return atan2(da.z, da.x) < atan2(db.z, db.x)
	)
	var lift := Vector3(0, 0.03, 0)
	var rim := PackedVector3Array()
	var none := Vector2(0.0, Style.NONE)
	for oi in n:
		var i := order[oi]
		var j := order[(oi + 1) % n]
		var ri := tangents[i].cross(Vector3.UP)
		var rj := tangents[j].cross(Vector3.UP)
		rim.append(mouths[i] - ri * ASPHALT_HALF)
		rim.append(mouths[i] + ri * ASPHALT_HALF)
		# The corner from arm i's high side round to arm j's low side.
		var walk := _walked(styles[i]) and _walked(styles[j])
		var band_style: int = Style.CORE_WALK if walk else Style.DASHED
		var inner := _corner(
			mouths[i] + ri * ASPHALT_HALF, tangents[i], mouths[j] - rj * ASPHALT_HALF, tangents[j]
		)
		var outer := _corner(mouths[i] + ri * HALF, tangents[i], mouths[j] - rj * HALF, tangents[j])
		var s := 0.0
		var d := Vector2(1.0, band_style)
		for k in inner.size():
			if k > 0:
				rim.append(inner[k])
			if k == inner.size() - 1:
				break
			var seg := Vector2(inner[k + 1].x - inner[k].x, inner[k + 1].z - inner[k].z).length()
			var drop := Vector3(0, -SHOULDER_DROP, 0)
			_quad(
				mb,
				inner[k] + lift,
				outer[k] + lift + drop,
				outer[k + 1] + lift + drop,
				inner[k + 1] + lift,
				Vector2(ASPHALT_HALF, s),
				Vector2(HALF, s),
				Vector2(HALF, s + seg),
				Vector2(ASPHALT_HALF, s + seg),
				d,
				d,
				d,
				d,
				col,
				Vector3.UP
			)
			var down := Vector3(0, -SKIRT, 0)
			var away := outer[k] - inner[k]
			away.y = 0.0
			_quad(
				mb,
				outer[k] + drop,
				outer[k + 1] + drop,
				outer[k + 1] + down,
				outer[k] + down,
				Vector2(HALF, s),
				Vector2(HALF, s + seg),
				Vector2(HALF * 1.02, s + seg),
				Vector2(HALF * 1.02, s),
				d,
				d,
				d,
				d,
				col,
				away
			)
			s += seg
	for i in rim.size():
		_tri(
			mb,
			centre + lift,
			rim[i] + lift,
			rim[(i + 1) % rim.size()] + lift,
			Vector2.ZERO,
			Vector2.ZERO,
			Vector2.ZERO,
			none,
			none,
			none,
			col,
			Vector3.UP
		)


static func _walked(style: int) -> bool:
	return style >= Style.DASHED_EDGES and style <= Style.CORE_WALK


## A kerb line curving from `a` (on a street heading out along `da`) to `b` (heading
## out along `db`): a quadratic through where the two edges would meet, or straight
## across when they don't.
static func _corner(a: Vector3, da: Vector3, b: Vector3, db: Vector3) -> PackedVector3Array:
	# Solve a - da*t = b - db*u on the ground plane.
	var den := -da.x * db.z + da.z * db.x
	var ctrl := a.lerp(b, 0.5)
	if absf(den) > 0.05:
		var wx := b.x - a.x
		var wz := b.z - a.z
		var t := (-wx * db.z + wz * db.x) / den
		var u := (-da.x * wz + da.z * wx) / den
		if t > 0.0 and u > 0.0 and t < 40.0 and u < 40.0:
			ctrl = a - da * t
			ctrl.y = lerpf(a.y, b.y, 0.5)
	var out := PackedVector3Array()
	const STEPS := 8
	for k in STEPS + 1:
		var f := float(k) / STEPS
		out.append(a.lerp(ctrl, f).lerp(ctrl.lerp(b, f), f))
	return out


## How far out along each arm its street must stop so neighbouring streets' full
## widths clear each other: sharper angles push the mouth further out.
static func junction_reach(arms: Array[Vector3]) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	for i in arms.size():
		var tightest := PI
		for j in arms.size():
			if j != i:
				tightest = minf(tightest, acos(clampf(arms[i].dot(arms[j]), -1.0, 1.0)))
		var need := HALF / tan(maxf(tightest, 0.2) * 0.5) if tightest < PI * 0.5 else HALF
		out.append(clampf(need + 1.0, HALF + 1.0, 30.0))
	return out
