class_name StreetPlan
extends RefCounted
## A town's street network as a graph: junctions (nodes) joined by streets (edges).
## Laid out like a planner would, in three zones out from the ferry square:
##   CORE   a short grid bent to follow the shoreline, blocks BLOCK_ALONG × BLOCK_DEEP,
##          so two rows of lots fit back to back between parallel streets;
##   MIDDLE the grid carries on but its along-shore streets bend to hold their height;
##   OUTER  contour streets running on past the grid, ending in a turning circle,
##          and the main road winding inland.
## Step 1 of the street rework (docs/town-layout-plan.md): shapes only, drawn by the
## F7 overlay. Nothing renders or grows from it yet.

enum Zone { CORE, MIDDLE, OUTER, MAIN }

const BLOCK_ALONG := 90.0  # between cross streets (along the shore)
const BLOCK_DEEP := 60.0  # between along-shore streets: two 30 m lots back to back
const COLS := 4  # grid columns each way from the square
const ROWS := 5  # along-shore streets inland of the front street
const CORE_COLS := 1
const CORE_ROWS := 2
const LAND_H := 3.2  # ground lower than this is shore or water
const MAX_GRADE := 0.125  # a street steeper than this end to end isn't built
const STEP := 6.0
const FRONT_SET := 30.0  # the front street, in from the water
const BEND := 12.0  # how far a middle-ring node may slide to hold its height
const OUTER_MAX := 220.0
const MAIN_MAX := 420.0

## Climbs inland no steeper than MAIN_GRADE, steering from its own heading: where
## straight on is too steep it angles across the slope, and where that side runs out
## of land it turns back on itself (a switchback) a little higher up.
const MAIN_GRADE := 0.11
const CUT := 2.5  # how far the main road may cut into or build up from the ground
var nodes := PackedVector3Array()
var node_zone := PackedInt32Array()
## Each edge: {a, b, zone, pts: PackedVector3Array}; b is -1 for a dead end.
var edges: Array[Dictionary] = []

var _t: Terrain
var _others: Array[Vector3] = []  # other towns: each keeps to the land nearer itself
var _isl: MapData.Town
var _sq: Vector3

var _reach := {}


static func build(
	isl: MapData.Town, terrain: Terrain, square: Vector3, others: Array[Vector3] = []
) -> StreetPlan:
	var plan := StreetPlan.new()
	plan._others = others
	plan._t = terrain
	plan._isl = isl
	plan._sq = square
	plan._lay_out(isl, square)
	# The town keeps its plan, so let go of it (and the terrain) once laid out.
	plan._isl = null
	plan._t = null
	return plan


func _h(p: Vector3) -> float:
	return _t.height_v(p)


func _ground(p: Vector3) -> Vector3:
	return Vector3(p.x, _h(p), p.z)


func _lay_out(isl: MapData.Town, sq: Vector3) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(isl.name)
	# Line the grid up with the coast near the square, not with the ferry lot.
	var u := isl.lateral()
	var v := -isl.dock_dir
	var left := _coast_point(sq - u * 90.0, v)
	var right := _coast_point(sq + u * 90.0, v)
	if left != Vector3.INF and right != Vector3.INF:
		var along := Vector3(right.x - left.x, 0.0, right.z - left.z).normalized()
		if along.dot(u) > 0.6:
			u = along
			v = (
				Vector3.UP.cross(u)
				if Vector3.UP.cross(u).dot(-isl.dock_dir) > 0.0
				else -Vector3.UP.cross(u)
			)
	# How far inland the coast sits at each column, smoothed, so the front street
	# runs FRONT_SET in from the water and the rows behind follow it.
	var raw := {}
	for i in range(-COLS - 1, COLS + 2):
		var c := _coast_point(sq + u * (i * BLOCK_ALONG), v)
		raw[i] = (c - sq).dot(v) if c != Vector3.INF else NAN
	var coast := {}
	for i in range(-COLS, COLS + 1):
		var sum := 0.0
		var n := 0
		for j: int in [i - 1, i, i, i + 1]:
			if not is_nan(raw[j]):
				sum += raw[j]
				n += 1
		coast[i] = sum / n if n > 0 else 0.0
	# Which streets curve gently: a few rows and columns in the middle ring.
	var row_wave := {}
	for k in range(0, ROWS + 1):
		row_wave[k] = rng.randf_range(6.0, 12.0) * (1.0 if k >= 2 and rng.randf() < 0.55 else 0.0)
	var col_wave := {}
	for i in range(-COLS, COLS + 1):
		col_wave[i] = (
			rng.randf_range(6.0, 12.0) * (1.0 if absi(i) >= 2 and rng.randf() < 0.5 else 0.0)
		)
	var phase := rng.randf() * TAU
	var grid := {}  # Vector2i(i, k) → node index
	var base := {}  # where each node would sit before waves and contour sliding
	for k in range(0, ROWS + 1):
		var row_h := NAN
		for i in _outward(COLS):
			var off_v: float = float(coast[i]) + FRONT_SET + k * BLOCK_DEEP
			var off_u := i * BLOCK_ALONG
			base[Vector2i(i, k)] = sq + u * off_u + v * off_v
			off_v += float(row_wave[k]) * sin(i * 1.1 + phase + k)
			off_u += float(col_wave[i]) * sin(k * 1.3 + phase + i)
			var p: Vector3 = sq + u * off_u + v * off_v
			var core := absi(i) <= CORE_COLS and k <= CORE_ROWS
			if k >= 2 and not core:
				if is_nan(row_h):
					row_h = _h(p)
				else:
					p = _hold_height(p, v, row_h)
			if not _buildable(p) or _on_lot(isl, sq, p):
				continue
			if is_nan(row_h) and k >= 2:
				row_h = _h(p)
			if _near_node(p, 20.0):
				continue
			grid[Vector2i(i, k)] = _add_node(_ground(p), Zone.CORE if core else Zone.MIDDLE)
	# Grid edges between neighbours, as smooth curves through the line's nodes.
	for key: Vector2i in grid:
		for d: Vector2i in [Vector2i(1, 0), Vector2i(0, 1)]:
			var other: Vector2i = key + d
			if not grid.has(other):
				continue
			var a: int = grid[key]
			var b: int = grid[other]
			var p0: Vector3 = (
				nodes[grid[key - d]] if grid.has(key - d) else nodes[a] * 2.0 - nodes[b]
			)
			var p3: Vector3 = (
				nodes[grid[other + d]] if grid.has(other + d) else nodes[b] * 2.0 - nodes[a]
			)
			var zone := (
				Zone.CORE
				if node_zone[a] == Zone.CORE and node_zone[b] == Zone.CORE
				else Zone.MIDDLE
			)
			var pts := _spline(p0, nodes[a], nodes[b], p3)
			if not pts.is_empty() and not _crosses(pts, a, b):
				edges.append({a = a, b = b, zone = zone, pts = pts})
	# The square joins the nearest street nodes clear of the ferry lot.
	var square := _add_node(sq, Zone.CORE)
	var near: Array = grid.values().filter(
		func(n: int) -> bool: return nodes[n].distance_to(sq) < 110.0
	)
	near.sort_custom(
		func(x: int, y: int) -> bool: return nodes[x].distance_to(sq) < nodes[y].distance_to(sq)
	)
	var linked: Array = []
	for n: int in near:
		var pts := _straight(sq, nodes[n])
		if not pts.is_empty() and not _crosses(pts, square, n):
			edges.append({a = square, b = n, zone = Zone.CORE, pts = pts})
			linked.append(n)
			break
	near = linked
	grid[Vector2i(0, -1)] = square
	_keep_connected(square)
	# Outer ring: along-shore streets run on past the grid's ends on the contour.
	for k in range(0, ROWS + 1):
		for side: int in [-1, 1]:
			var end := -1
			for i in range(COLS, -1, -1):
				var n: int = grid.get(Vector2i(i * side, k), -1)
				if n >= 0 and _connected(n):
					end = n
					break
			if end >= 0:
				_contour_street(end, u * side)
	# Main road: up the grid street nearest the square, then winding on inland from
	# its top; straight from the square where no grid street leads inland.
	var start := square
	if not near.is_empty() and _connected(near[0]):
		var key: Vector2i = grid.find_key(near[0])
		while grid.has(key + Vector2i(0, 1)) and _linked(grid[key], grid[key + Vector2i(0, 1)]):
			key += Vector2i(0, 1)
		if key.y > 0:
			start = grid[key]
	_main_road(start, v)


static func _outward(n: int) -> Array[int]:
	var out: Array[int] = [0]
	for i in range(1, n + 1):
		out.append(i)
		out.append(-i)
	return out


## The first solid land met walking inland from 200 m out to sea along v.
func _coast_point(at: Vector3, v: Vector3) -> Vector3:
	var run := 0
	for s in range(-50, 50):
		var q := at + v * (s * 4.0)
		run = run + 1 if _h(q) > LAND_H else 0
		if run == 3:
			return q - v * 8.0
	return Vector3.INF


## Catmull-Rom from b to c, sampled every STEP on the ground; empty if it leaves land
## or climbs too steeply end to end.
func _spline(a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> PackedVector3Array:
	var flat := Vector2(c.x - b.x, c.z - b.z).length()
	if flat < 1.0 or absf(c.y - b.y) > flat * MAX_GRADE:
		return PackedVector3Array()
	var n := maxi(2, ceili(flat / STEP))
	var pts := PackedVector3Array()
	for s in n + 1:
		var t := float(s) / n
		var p := (
			0.5
			* (
				(2.0 * b)
				+ (-a + c) * t
				+ (2.0 * a - 5.0 * b + 4.0 * c - d) * t * t
				+ (-a + 3.0 * b - 3.0 * c + d) * t * t * t
			)
		)
		p = _ground(p)
		if p.y < LAND_H - 0.4:
			return PackedVector3Array()
		pts.append(p)
	return pts


func _coast_depth(at: Vector3, v: Vector3) -> float:
	# Walk inland from seaward of the point until the ground is land.
	for s in range(-10, 30):
		if _h(at + v * (s * 4.0)) > LAND_H:
			return s * 4.0
	return 0.0


func _hold_height(p: Vector3, v: Vector3, target: float) -> Vector3:
	var best := p
	var best_err := absf(_h(p) - target)
	var off := -BEND
	while off <= BEND:
		var q := p + v * off
		var err := absf(_h(q) - target) + absf(off) * 0.02
		if err < best_err:
			best_err = err
			best = q
		off += 4.0
	return best


func _on_lot(isl: MapData.Town, sq: Vector3, p: Vector3) -> bool:
	var own := Vector2(p.x - sq.x, p.z - sq.z).length() + 30.0
	for o in _others:
		if Vector2(p.x - o.x, p.z - o.z).length() < own:
			return true
	var d := p - sq
	return (
		d.dot(isl.dock_dir) > 2.0
		and absf(d.dot(isl.lateral())) < isl.lot_half_width + 12.0
		and d.dot(isl.dock_dir) < 140.0
	)


func _buildable(p: Vector3) -> bool:
	var h := _h(p)
	if h < LAND_H:
		return false
	for d: Vector3 in [Vector3(8, 0, 0), Vector3(0, 0, 8)]:
		if absf(_h(p + d) - _h(p - d)) > 16.0 * 0.3:
			return false
	return true


func _near_node(p: Vector3, gap: float) -> bool:
	for n in nodes:
		if Vector2(n.x - p.x, n.z - p.z).length() < gap:
			return true
	return false


func _add_node(p: Vector3, zone: int) -> int:
	nodes.append(p)
	node_zone.append(zone)
	return nodes.size() - 1


## Ground points along a to b, or empty if the street would leave land or climb too steeply.
func _straight(a: Vector3, b: Vector3) -> PackedVector3Array:
	var flat := Vector2(b.x - a.x, b.z - a.z).length()
	if flat < 1.0 or absf(b.y - a.y) > flat * MAX_GRADE:
		return PackedVector3Array()
	var n := maxi(2, ceili(flat / STEP))
	var pts := PackedVector3Array()
	for s in n + 1:
		var p := _ground(a.lerp(b, float(s) / n))
		if p.y < LAND_H - 0.4:
			return PackedVector3Array()
		pts.append(p)
	return pts


func _keep_connected(root: int) -> void:
	_reach.clear()
	if root < 0:
		edges.clear()
		return
	var stack: Array[int] = [root]
	_reach[root] = true
	while not stack.is_empty():
		var n: int = stack.pop_back()
		for e in edges:
			for pair: Array in [[e.a, e.b], [e.b, e.a]]:
				if pair[0] == n and pair[1] >= 0 and not _reach.has(pair[1]):
					_reach[pair[1]] = true
					stack.append(pair[1])
	edges = edges.filter(func(e: Dictionary) -> bool: return _reach.has(e.a))


func _linked(a: int, b: int) -> bool:
	for e in edges:
		if (e.a == a and e.b == b) or (e.a == b and e.b == a):
			return true
	return false


func _connected(n: int) -> bool:
	return _reach.has(n)


## Runs on from a grid end holding its height, bending with the ground; ends in a
## turning circle (dead end) where the land runs out or it nears other streets.
func _contour_street(from: int, dir: Vector3) -> void:
	var start := nodes[from]
	var pts := PackedVector3Array([start])
	var p := start
	var heading := dir
	var length := 0.0
	while length < OUTER_MAX:
		var best := Vector3.INF
		var best_cost := INF
		for deg: float in [-24.0, -12.0, 0.0, 12.0, 24.0]:
			var d := heading.rotated(Vector3.UP, deg_to_rad(deg))
			var q := _ground(p + d * STEP)
			if q.y < LAND_H or _on_lot(_isl, _sq, q):
				continue
			var cost := absf(q.y - start.y) + absf(deg) * 0.02
			if cost < best_cost:
				best_cost = cost
				best = q
		if (
			best == Vector3.INF
			or best_cost > 4.0
			or _near_other(best, pts, 30.0)
			or _near_own(best, pts, 30.0)
		):
			break
		heading = (best - p).normalized()
		heading.y = 0.0
		heading = heading.normalized()
		p = best
		pts.append(p)
		length += STEP
	if length >= 36.0:
		var end := _add_node(p, Zone.OUTER)
		_reach[end] = true
		edges.append({a = from, b = end, zone = Zone.OUTER, pts = pts})


func _main_road(from: int, v: Vector3) -> void:
	var p := nodes[from]
	var pts := PackedVector3Array([p])
	var length := 0.0
	var heading := v
	var turns := 0
	var y := p.y  # the road's own height: it cuts and fills up to CUT against the ground
	while length < MAIN_MAX and turns < 12:
		var best := Vector3.INF
		var best_cost := INF
		var fans: Array = [[0.0, 10.0, -10.0, 20.0, -20.0], [30.0, -30.0]]
		for fan: Array in fans:
			for deg: float in fan:
				var d := heading.rotated(Vector3.UP, deg_to_rad(deg))
				var q := _ground(p + d * STEP)
				if q.y < LAND_H or _on_lot(_isl, _sq, q) or _near_own(q, pts, 26.0):
					continue
				var ny := clampf(q.y, y - MAIN_GRADE * STEP, y + MAIN_GRADE * STEP)
				var cut := absf(q.y - ny)
				if cut > CUT:
					continue
				var cost := cut * 1.5 - (ny - y) * 3.0 - d.dot(v) * 2.0 + absf(deg) * 0.01
				if cost < best_cost:
					best_cost = cost
					best = Vector3(q.x, ny, q.z)
			if best != Vector3.INF:
				if fan != fans[0]:
					turns += 1
				break
		if best == Vector3.INF:
			break
		heading = Vector3(best.x - p.x, 0.0, best.z - p.z).normalized()
		y = best.y
		p = best
		pts.append(p)
		length += STEP
		# Up on top: stop once the climb levels out well inland.
		if length > 160.0 and (p - _sq).dot(v) > 220.0:
			break
	if length >= 36.0:
		var end := _add_node(p, Zone.MAIN)
		edges.append({a = from, b = end, zone = Zone.MAIN, pts = pts})


func _near_own(q: Vector3, own: PackedVector3Array, gap: float) -> bool:
	for i in own.size() - 6:
		if Vector2(own[i].x - q.x, own[i].z - q.z).length() < gap:
			return true
	return false


## Does the polyline cross a street already laid, other than at its own ends a, b?
func _crosses(pts: PackedVector3Array, a: int, b: int) -> bool:
	for e in edges:
		if e.a == a or e.a == b or e.b == a or e.b == b:
			continue
		var other: PackedVector3Array = e.pts
		for i in pts.size() - 1:
			var p1 := Vector2(pts[i].x, pts[i].z)
			var p2 := Vector2(pts[i + 1].x, pts[i + 1].z)
			for j in other.size() - 1:
				var q1 := Vector2(other[j].x, other[j].z)
				if q1.distance_to(p1) > 40.0:
					continue
				if (
					Geometry2D.segment_intersects_segment(
						p1, p2, q1, Vector2(other[j + 1].x, other[j + 1].z)
					)
					!= null
				):
					return true
	return false


## Is q close to a street already laid (other than the one being walked, own)?
func _near_other(q: Vector3, own: PackedVector3Array, gap: float) -> bool:
	for e in edges:
		for p: Vector3 in e.pts:
			if Vector2(p.x - q.x, p.z - q.z).length() < gap and p.distance_to(own[0]) > gap + 1.0:
				return true
	return false


## Shortest street paths from the square: [start node, dist, prev_e] where
## prev_e[n] is the edge used to reach n.
func _square_tree() -> Array:
	var start := 0
	for i in nodes.size():
		if nodes[i].distance_to(_sq) < nodes[start].distance_to(_sq):
			start = i
	# Dijkstra over street lengths; prev_e[n] = edge index used to reach n.
	var dist := PackedFloat32Array()
	dist.resize(nodes.size())
	dist.fill(INF)
	var prev_e := PackedInt32Array()
	prev_e.resize(nodes.size())
	prev_e.fill(-1)
	dist[start] = 0.0
	var open: Array[int] = [start]
	while not open.is_empty():
		var bi := 0
		for k in open.size():
			if dist[open[k]] < dist[open[bi]]:
				bi = k
		var n: int = open[bi]
		open.remove_at(bi)
		for ei in edges.size():
			var e: Dictionary = edges[ei]
			var m: int = e.b if e.a == n else (e.a if e.b == n else -2)
			if m < 0:
				continue
			var d := dist[n] + RoadGeometry.length_of(e.pts)
			if d < dist[m]:
				dist[m] = d
				prev_e[m] = ei
				open.append(m)
	return [start, dist, prev_e]


## The street points from the square to node `n` (empty if unreachable).
func path_to_node(n: int) -> PackedVector3Array:
	var tree := _square_tree()
	var start: int = tree[0]
	var prev_e: PackedInt32Array = tree[2]
	if n != start and prev_e[n] < 0:
		return PackedVector3Array()
	var path := PackedVector3Array([nodes[start]])
	while n != start:
		var e: Dictionary = edges[prev_e[n]]
		var pts: PackedVector3Array = e.pts.duplicate()
		var from: int = e.a if e.b == n else e.b
		if e.a == n:
			pts.reverse()
		if path.size() > 1:
			pts.append_array(path.slice(1))
		path = pts
		n = from
	return path


## Drives for cars: from the square out along the streets to up to `count` junctions
## spread through the town (farthest first), each as one polyline of street points.
func drives_from_square(count := 10) -> Array[PackedVector3Array]:
	var out: Array[PackedVector3Array] = []
	if nodes.is_empty() or edges.is_empty():
		return out
	var tree := _square_tree()
	var start: int = tree[0]
	var dist: PackedFloat32Array = tree[1]
	var prev_e: PackedInt32Array = tree[2]
	var reach: Array[int] = []
	for i in nodes.size():
		if i != start and dist[i] < INF:
			reach.append(i)
	reach.sort_custom(func(x: int, y: int) -> bool: return dist[x] > dist[y])
	var stride := maxi(1, reach.size() / count)
	for r in range(0, reach.size(), stride):
		var path := PackedVector3Array()
		var n: int = reach[r]
		while n != start:
			var e: Dictionary = edges[prev_e[n]]
			var pts: PackedVector3Array = e.pts.duplicate()
			var from: int = e.a if e.b == n else e.b
			if e.a == n:
				pts.reverse()  # pts now run from → n
			# prepend
			if not path.is_empty():
				pts.append_array(path.slice(1))
			path = pts
			n = from
		if path.size() > 1:
			out.append(path)
		if out.size() >= count:
			break
	return out
