class_name TownLots
extends RefCounted
## Blocks and frontage lots derived from a town's StreetPlan (docs/town-layout-plan.md
## step 3). Works on a 2 m raster in world XZ:
##   1. streets (by width) and water are burned in; what's left is land;
##   2. each land cell is owned by its nearest street edge (BFS), so a lot never
##      reaches past the midline of its block or across another street;
##   3. connected land between streets/shore = a block;
##   4. each edge is walked on both sides dropping lots of the zone's width, each
##      pushed back as deep as its owned land allows (no slivers);
##   5. lots are ranked: core first, then by street distance from the square.

const CELL := 2.0
const LAND_H := 3.2
const PAD := 80.0
## Per StreetPlan.Zone: road half-width, lot frontage, target depth, setback.
const HALF := [5.0, 4.0, 3.5, 5.0]
const FRONT := [8.0, 13.0, 18.0, 30.0]
const DEPTH := [40.0, 32.0, 36.0, 48.0]   # core runs back to the block midline
const MIN_DEPTH := 8.0
const ROAD := -1
const WATER := -2

## Each lot: {quad: PackedVector2Array (front-left, front-right, back-right, back-left),
## front: Vector2 (middle of the street face), facing: Vector2 (toward street),
## width, depth, zone, edge, block, corner: bool, rank}
var lots: Array[Dictionary] = []
var block_count := 0
var block_of := PackedInt32Array()   # per cell: block id, or -1
var owner := PackedInt32Array()      # per cell: owning edge, ROAD, or WATER
var origin := Vector2.ZERO
var w := 0
var h := 0

var _plan: StreetPlan
var _claimed := PackedByteArray()


static func build(plan: StreetPlan, terrain: Terrain, square: Vector3) -> TownLots:
	var tl := TownLots.new()
	tl._plan = plan
	tl._raster(terrain)
	tl._blocks()
	tl._frontage()
	tl._rank(square)
	return tl


func cell_of(p: Vector2) -> Vector2i:
	return Vector2i(floori((p.x - origin.x) / CELL), floori((p.y - origin.y) / CELL))


func _idx(c: Vector2i) -> int:
	return -1 if c.x < 0 or c.y < 0 or c.x >= w or c.y >= h else c.y * w + c.x


func _raster(terrain: Terrain) -> void:
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for e in _plan.edges:
		for p: Vector3 in e.pts:
			lo = lo.min(Vector2(p.x, p.z))
			hi = hi.max(Vector2(p.x, p.z))
	origin = lo - Vector2(PAD, PAD)
	w = ceili((hi.x - lo.x + 2 * PAD) / CELL)
	h = ceili((hi.y - lo.y + 2 * PAD) / CELL)
	owner.resize(w * h)
	owner.fill(-3)   # unowned land
	block_of.resize(w * h)
	block_of.fill(-1)
	_claimed.resize(w * h)
	_claimed.fill(0)
	for y in h:
		for x in w:
			var p := origin + Vector2(x + 0.5, y + 0.5) * CELL
			if terrain.height_at(p.x, p.y) < LAND_H:
				owner[y * w + x] = WATER
	# Burn the streets, seeding the BFS with the cells along each edge's verge.
	var frontier: Array[int] = []
	for ei in _plan.edges.size():
		var e: Dictionary = _plan.edges[ei]
		var r: float = HALF[e.zone]
		var pts: PackedVector3Array = e.pts
		for i in pts.size() - 1:
			var a := Vector2(pts[i].x, pts[i].z)
			var b := Vector2(pts[i + 1].x, pts[i + 1].z)
			var c0 := cell_of(a.min(b) - Vector2.ONE * (r + CELL))
			var c1 := cell_of(a.max(b) + Vector2.ONE * (r + CELL))
			for cy in range(c0.y, c1.y + 1):
				for cx in range(c0.x, c1.x + 1):
					var k := _idx(Vector2i(cx, cy))
					if k < 0 or owner[k] == WATER:
						continue
					var p := origin + Vector2(cx + 0.5, cy + 0.5) * CELL
					var d := p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b))
					if d <= r:
						owner[k] = ROAD
	# Seed: land cells touching a road cell take the nearest edge.
	for k in w * h:
		if owner[k] != -3:
			continue
		var c := Vector2i(k % w, k / w)
		for d: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var j := _idx(c + d)
			if j >= 0 and owner[j] == ROAD:
				owner[k] = _nearest_edge(origin + (Vector2(c) + Vector2(0.5, 0.5)) * CELL)
				frontier.append(k)
				break
	# BFS outward: every land cell belongs to the street it's nearest by walking.
	var head := 0
	while head < frontier.size():
		var k: int = frontier[head]
		head += 1
		var c := Vector2i(k % w, k / w)
		for d: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var j := _idx(c + d)
			if j >= 0 and owner[j] == -3:
				owner[j] = owner[k]
				frontier.append(j)


func _nearest_edge(p: Vector2) -> int:
	var best := -1
	var bd := INF
	for ei in _plan.edges.size():
		var pts: PackedVector3Array = _plan.edges[ei].pts
		for i in pts.size() - 1:
			var q := Geometry2D.get_closest_point_to_segment(p, Vector2(pts[i].x, pts[i].z), Vector2(pts[i + 1].x, pts[i + 1].z))
			var d := p.distance_squared_to(q)
			if d < bd:
				bd = d
				best = ei
	return best


func _blocks() -> void:
	for k in w * h:
		if owner[k] < 0 or block_of[k] >= 0:
			continue
		var stack: Array[int] = [k]
		block_of[k] = block_count
		while not stack.is_empty():
			var i: int = stack.pop_back()
			var c := Vector2i(i % w, i / w)
			for d: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var j := _idx(c + d)
				if j >= 0 and owner[j] >= 0 and block_of[j] < 0:
					block_of[j] = block_count
					stack.append(j)
		block_count += 1


func _degree(n: int) -> int:
	var d := 0
	for e in _plan.edges:
		if e.a == n or e.b == n:
			d += 1
	return d


## Is the strip across the lot's width at this depth all owned by edge ei and free?
func _row_ok(f: Vector2, along: Vector2, nrm: Vector2, half_w: float, depth: float, ei: int) -> bool:
	# One stray cell per row is raster noise at bends, not a real obstacle.
	var bad := 0
	var s := -half_w + 1.0
	while s <= half_w - 1.0:
		var k := _idx(cell_of(f + along * s + nrm * depth))
		if k < 0 or _claimed[k] != 0 or owner[k] == WATER or (owner[k] != ei and owner[k] != ROAD):
			bad += 1
			if bad > 1 or k < 0 or (k >= 0 and _claimed[k] != 0):
				return false
		s += 1.5
	return true


func _frontage() -> void:
	for ei in _plan.edges.size():
		var e: Dictionary = _plan.edges[ei]
		var pts: PackedVector3Array = e.pts
		var flat := PackedVector2Array()
		for p in pts:
			flat.append(Vector2(p.x, p.z))
		var cum := PackedFloat32Array([0.0])
		for i in range(1, flat.size()):
			cum.append(cum[i - 1] + flat[i].distance_to(flat[i - 1]))
		var total := cum[-1]
		var zone: int = e.zone
		var fw: float = FRONT[zone]
		var half: float = HALF[zone]
		var corner_a: bool = _degree(e.a) >= 2
		var corner_b: bool = e.b >= 0 and _degree(e.b) >= 2
		for side: float in [-1.0, 1.0]:
			# Leave room for the crossing street at junction ends.
			var start := 6.0 if corner_a else 0.0
			var stop := total - (6.0 if corner_b else 0.0)
			var t := start
			var first := true
			while t + fw * 0.7 <= stop:
				var lot_w := fw * (1.3 if first and corner_a else 1.0)
				var is_corner := first and corner_a
				if t + lot_w > stop:
					lot_w = stop - t
					is_corner = corner_b
				elif t + lot_w + fw * 0.7 > stop:
					lot_w = stop - t   # absorb a would-be sliver at the far end
					is_corner = corner_b
				# Full width first, then narrower; if nothing fits, slide on 2 m and retry.
				var placed := false
				for f: float in [1.0, 0.8, 0.6]:
					var tw: float = lot_w if f == 1.0 else minf(lot_w, fw * f)
					var lot := _place(flat, cum, t + tw * 0.5, tw, side, half, zone, ei)
					if not lot.is_empty():
						lot.corner = is_corner
						lots.append(lot)
						t += tw
						placed = true
						break
				if not placed:
					t += CELL
				first = false


func _place(flat: PackedVector2Array, cum: PackedFloat32Array, at: float, lot_w: float,
		side: float, half: float, zone: int, ei: int) -> Dictionary:
	var i := 0
	while i < cum.size() - 2 and cum[i + 1] < at:
		i += 1
	var seg := flat[i + 1] - flat[i]
	var along := seg.normalized()
	var p := flat[i] + along * (at - cum[i])
	var nrm := Vector2(-along.y, along.x) * side
	var f := p + nrm * (half + 0.5)
	var hw := lot_w * 0.5
	var target: float = DEPTH[zone]
	var depth := 0.0
	while depth + CELL <= target and _row_ok(f, along, nrm, hw, depth + 1.0, ei):
		depth += CELL
	if depth < MIN_DEPTH:
		return {}
	var quad := PackedVector2Array([f - along * hw, f + along * hw,
		f + along * hw + nrm * depth, f - along * hw + nrm * depth])
	_claim(quad)
	return {quad = quad, front = f, facing = -nrm, width = lot_w, depth = depth, zone = zone,
		edge = ei, block = block_of[_idx(cell_of(f + nrm * 2.0))], corner = false, rank = -1, along = 0.0}


func _claim(quad: PackedVector2Array) -> void:
	var lo := quad[0].min(quad[1]).min(quad[2]).min(quad[3])
	var hi := quad[0].max(quad[1]).max(quad[2]).max(quad[3])
	var c0 := cell_of(lo)
	var c1 := cell_of(hi)
	for cy in range(c0.y, c1.y + 1):
		for cx in range(c0.x, c1.x + 1):
			var k := _idx(Vector2i(cx, cy))
			if k >= 0 and Geometry2D.is_point_in_polygon(origin + Vector2(cx + 0.5, cy + 0.5) * CELL, quad):
				_claimed[k] = 1


## Rank = build order: core zone first, then by walking distance from the square.
func _rank(square: Vector3) -> void:
	var n := _plan.nodes.size()
	var dist := PackedFloat32Array()
	dist.resize(n)
	dist.fill(INF)
	var sq_node := 0
	var bd := INF
	for i in n:
		var d := _plan.nodes[i].distance_to(square)
		if d < bd:
			bd = d
			sq_node = i
	dist[sq_node] = 0.0
	var lens := []
	for e in _plan.edges:
		var L := 0.0
		for i in range(1, e.pts.size()):
			L += e.pts[i].distance_to(e.pts[i - 1])
		lens.append(L)
	for _iter in n:   # Bellman-Ford; graphs are tiny
		var changed := false
		for ei in _plan.edges.size():
			var e: Dictionary = _plan.edges[ei]
			if e.b < 0:
				continue
			for pair: Array in [[e.a, e.b], [e.b, e.a]]:
				if dist[pair[0]] + lens[ei] < dist[pair[1]]:
					dist[pair[1]] = dist[pair[0]] + lens[ei]
					changed = true
		if not changed:
			break
	var zone_cost := [0.0, 150.0, 400.0, 600.0]
	for lot in lots:
		var e: Dictionary = _plan.edges[lot.edge]
		var a := Vector2(_plan.nodes[e.a].x, _plan.nodes[e.a].z)
		var from_a: float = dist[e.a] + lot.front.distance_to(a)
		var score := from_a
		if e.b >= 0:
			var b := Vector2(_plan.nodes[e.b].x, _plan.nodes[e.b].z)
			score = minf(score, dist[e.b] + lot.front.distance_to(b))
		lot.along = score
		lot.score = score + zone_cost[lot.zone]
	lots.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return x.score < y.score)
	for i in lots.size():
		lots[i].rank = i
