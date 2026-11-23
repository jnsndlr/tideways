class_name RoutePlanner
extends RefCounted
## Plans a ferry route round the land between two terminals: a coarse grid of
## how far each cell is from land, A* through the water that keeps the required
## distance off, then the path string-pulled so it runs in as few straight legs as
## it can. MapGenerator joins the corners with turns and checks the result.
##
## How far off land a route keeps is `need`, which the caller passes per point:
## full clearance out in open water, tapering in to MIN_CLEAR near each terminal,
## since a slip sits on the shore.

const CELL := 30.0
## Land is anything shallower than this (as MapGenerator._route_clear).
const LAND_DEPTH := -3.6
## The least room ever kept off land: the widest hull's half beam and some.
const MIN_CLEAR := 36.0

var ext := 0.0
var n := 0
var terrain: Terrain
## Metres from each cell's centre to the nearest land cell's.
var dist := PackedFloat32Array()
var _grid := AStarGrid2D.new()
## Cells that only some clearances close (nearer land than the widest ever asked).
var _near: Array[Vector2i] = []
var _near_reach := 0.0


func _init(t: Terrain, half_size: float, should_stop := Callable()) -> void:
	terrain = t
	ext = half_size + 330.0
	n = ceili(ext * 2.0 / CELL)
	var land := PackedByteArray()
	land.resize(n * n)
	for j in n:
		if should_stop.is_valid() and should_stop.call():
			return
		for i in n:
			var c := center(Vector2i(i, j))
			var h := terrain.height_at(c.x, c.y)
			for o: Vector2 in [Vector2(-10, -10), Vector2(10, -10), Vector2(-10, 10), Vector2(10, 10)]:
				h = maxf(h, terrain.height_at(c.x + o.x, c.y + o.y))
			land[j * n + i] = 1 if h > LAND_DEPTH else 0
	dist = NavGrid.distance_field(land, n, CELL, should_stop)
	if dist.is_empty():
		return
	_grid.region = Rect2i(0, 0, n, n)
	_grid.cell_size = Vector2(CELL, CELL)
	_grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	_grid.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	_grid.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	_grid.update()
	for j in n:
		if should_stop.is_valid() and should_stop.call():
			return
		for i in n:
			if dist[j * n + i] < MIN_CLEAR:
				_grid.set_point_solid(Vector2i(i, j))


func cell(p: Vector2) -> Vector2i:
	return Vector2i(clampi(floori((p.x + ext) / CELL), 0, n - 1), clampi(floori((p.y + ext) / CELL), 0, n - 1))


func center(c: Vector2i) -> Vector2:
	return Vector2(-ext + (c.x + 0.5) * CELL, -ext + (c.y + 0.5) * CELL)


## How far `p` is from land (to the grid's resolution).
func clearance_at(p: Vector2) -> float:
	return dist[cell(p).y * n + cell(p).x]


## The room `p` must keep off land on a route whose ends lie at `s` and `g`: none
## extra at the ends, rising `slope` metres per metre out from `taper_from`
## metres, up to `full`.
static func need_at(p: Vector2, s: Vector2, g: Vector2, full: float, taper_from: float, slope: float) -> float:
	var out := minf(p.distance_to(s), p.distance_to(g)) - taper_from
	return clampf(out * slope, MIN_CLEAR, maxf(full, MIN_CLEAR))


## A path from `s` to `g` keeping need_at(...) off land, as the fewest straight
## legs (s, corners..., g), or empty if there is none.
func waypoints(s: Vector2, g: Vector2, full: float, taper_from: float, slope: float, should_stop := Callable()) -> PackedVector2Array:
	if should_stop.is_valid() and should_stop.call():
		return PackedVector2Array()
	_close_near(s, g, full, taper_from, slope)
	var out := PackedVector2Array()
	var ca := _nearest_open(cell(s))
	var cb := _nearest_open(cell(g))
	if ca.x >= 0 and cb.x >= 0:
		var ids := _grid.get_id_path(ca, cb)
		if not ids.is_empty():
			var raw := PackedVector2Array([s])
			for c in ids:
				raw.append(center(c))
			raw.append(g)
			out = _pull(raw, should_stop)
	_open_near()
	return out


## Closes the cells nearer land than this route must keep.
func _close_near(s: Vector2, g: Vector2, full: float, taper_from: float, slope: float) -> void:
	if full > _near_reach:
		_near.clear()
		for j in n:
			for i in n:
				var d := dist[j * n + i]
				if d >= MIN_CLEAR and d < full:
					_near.append(Vector2i(i, j))
		_near_reach = full
	for c in _near:
		if dist[c.y * n + c.x] < need_at(center(c), s, g, full, taper_from, slope):
			_grid.set_point_solid(c)


func _open_near() -> void:
	for c in _near:
		_grid.set_point_solid(c, false)


func _nearest_open(c: Vector2i) -> Vector2i:
	if not _grid.is_point_solid(c):
		return c
	for r in range(1, 12):
		for j in range(-r, r + 1):
			for i in range(-r, r + 1):
				var q := c + Vector2i(i, j)
				if maxi(absi(i), absi(j)) == r and _grid.region.has_point(q) and not _grid.is_point_solid(q):
					return q
	return Vector2i(-1, -1)


## Drops every point that can be skipped with a clear straight line.
func _pull(raw: PackedVector2Array, should_stop: Callable) -> PackedVector2Array:
	var out := PackedVector2Array([raw[0]])
	var i := 0
	while i < raw.size() - 1:
		if should_stop.is_valid() and should_stop.call():
			return PackedVector2Array()
		var j := raw.size() - 1
		while j > i + 1 and not _sight(raw[i], raw[j]):
			j -= 1
		out.append(raw[j])
		i = j
	return out


## True if the straight line a → b stays in open cells (its end cells aside).
func _sight(a: Vector2, b: Vector2) -> bool:
	var ca := cell(a)
	var cb := cell(b)
	var steps := ceili(a.distance_to(b) / (CELL * 0.4))
	for k in range(1, steps):
		var c := cell(a.lerp(b, float(k) / steps))
		if c != ca and c != cb and _grid.is_point_solid(c):
			return false
	return true
