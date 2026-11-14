class_name Terrain
extends RefCounted
## Heightfield for the whole map. Islands are "stamped" into an elevation grid, shaped
## into rocky shores and rolling hills, then flattened where terminals need level ground.
## height_at() matches the rendered triangles exactly, so props sit on the surface.

## About 4 m between samples. 1600 cells across the map: the Backdrop's rings halve
## the edge's sample count twice, so the count must divide by 4.
const CELL := 6600.0 / 1600.0
const SEA_FLOOR := -16.5


## One island's footprint in the elevation grid. Its coastline and hills are
## sampled from the shared noise at `offset` plus the point's position relative
## to its centre, so an island keeps its shape wherever it is moved.
class Stamp:
	var island_id := -1
	var center := Vector2.ZERO
	var radius := 100.0
	var strength := 1.0
	var stretch := 1.0     # long axis over the radius (area kept the same)
	var angle := 0.0       # radians, of the long axis
	var roughness := 1.0   # how ragged the coastline is
	var hills := 1.0       # scales the inland relief
	var offset := Vector2.ZERO
	var ax := Vector2.RIGHT
	var ay := Vector2.DOWN

	func reach() -> float:
		return radius * 1.7 * maxf(stretch, 1.0)

	func setup() -> void:
		ax = Vector2(cos(angle), sin(angle))
		ay = Vector2(-ax.y, ax.x)


var half_size: float
var n: int  # cells per side
var e_grid := PackedFloat32Array()  # raw island "elevation" 0..~4.5
var h_grid := PackedFloat32Array()  # final heights
## Which stamp shaped each grid point (index into `stamps`), -1 for open sea.
var owner_grid := PackedInt32Array()
var stamps: Array[Stamp] = []
var warp := FastNoiseLite.new()
var detail := FastNoiseLite.new()
var rubble := FastNoiseLite.new()
var hills := FastNoiseLite.new()
var flats: Array[Dictionary] = []
## The land past the grid's edge (heights there come from it, see outer_height).
var mainland: Mainland
# Stamps that reach past the grid's edge, continued by outer_height.
var _edge_stamps: Array[Stamp] = []
# Samples the noise where it stands, for the mainland's own elevation.
var _world_stamp := Stamp.new()
# Grid rects stamped since the last finalize().
var _dirty: Array[Rect2i] = []
const WARP_STEP := 2


func _init(map_seed: int, half: float) -> void:
	half_size = half
	n = int(round(half * 2.0 / CELL))
	e_grid.resize((n + 1) * (n + 1))
	e_grid.fill(0.0)
	owner_grid.resize((n + 1) * (n + 1))
	owner_grid.fill(-1)
	warp.seed = map_seed
	warp.frequency = 0.0018
	warp.fractal_octaves = 5
	warp.fractal_gain = 0.4
	detail.seed = map_seed + 17
	detail.frequency = 0.0166667
	# Knobbly ground a few cells across: what the finer grid adds over the old 7.5 m one.
	rubble.seed = map_seed + 19
	rubble.frequency = 0.055
	hills.seed = map_seed + 23
	hills.frequency = 0.0024
	hills.fractal_octaves = 3
	mainland = Mainland.new(map_seed, half)


func _index_of(coord: float) -> int:
	return clampi(int((coord + half_size) / CELL), 0, n)


## A plain round stamp sampling the noise where it stands (mainland, islets).
func stamp_island(center: Vector2, radius: float, strength: float, island_id := -1) -> void:
	var s := Stamp.new()
	s.island_id = island_id
	s.center = center
	s.radius = radius
	s.strength = strength
	s.offset = center
	stamp(s)


## Where a shape seed samples the noise: far apart, so seeds don't share coastlines.
static func shape_offset(shape_seed: int) -> Vector2:
	var h := hash(shape_seed)
	return Vector2(float(h & 0xffff), float((h >> 16) & 0xffff)) * 7.3 + Vector2(40000.0, 40000.0)


func stamp(s: Stamp) -> void:
	s.setup()
	stamps.append(s)
	if maxf(absf(s.center.x), absf(s.center.y)) + s.reach() > half_size:
		_edge_stamps.append(s)
	var r := stamp_rect(s)
	_dirty.append(r)
	_stamp_into(stamps.size() - 1, r)


## The grid points a stamp can reach (vertex indices).
func stamp_rect(s: Stamp) -> Rect2i:
	var reach := s.reach()
	var i0 := _index_of(s.center.x - reach)
	var j0 := _index_of(s.center.y - reach)
	return Rect2i(i0, j0, _index_of(s.center.x + reach) - i0 + 1, _index_of(s.center.y + reach) - j0 + 1)


## Swaps stamp `idx` for `s` (an island reshaped or moved in the editor) and
## stamps the ground they cover again. Flats and beaches there are lost until the
## map is generated again. Returns the grid rect that changed.
func replace_stamp(idx: int, s: Stamp) -> Rect2i:
	s.setup()
	var old := stamps[idx]
	var r := stamp_rect(old).merge(stamp_rect(s))
	stamps[idx] = s
	var k := _edge_stamps.find(old)
	if k >= 0:
		_edge_stamps.remove_at(k)
	if maxf(absf(s.center.x), absf(s.center.y)) + s.reach() > half_size:
		_edge_stamps.append(s)
	for j in range(r.position.y, r.end.y):
		for i in range(r.position.x, r.end.x):
			var g := j * (n + 1) + i
			e_grid[g] = 0.0
			owner_grid[g] = -1
			h_grid[g] = SEA_FLOOR
	for o in stamps.size():
		var clip := stamp_rect(stamps[o]).intersection(r)
		if clip.has_area():
			_stamp_into(o, clip)
	_dirty.append(r)
	finalize()
	return r


func _stamp_into(idx: int, clip: Rect2i) -> void:
	var s := stamps[idx]
	var i0 := clip.position.x
	var j0 := clip.position.y
	var i1 := clip.end.x - 1
	var j1 := clip.end.y - 1
	# The coastline warp's finest octave is ~35 m across: sample it every WARP_STEP
	# cells and interpolate, a quarter of the noise calls for the same shores.
	var cw := (i1 - i0) / WARP_STEP + 2
	var ch := (j1 - j0) / WARP_STEP + 2
	var coarse := PackedFloat32Array()
	coarse.resize(cw * ch)
	for cj in ch:
		var z := -half_size + (j0 + cj * WARP_STEP) * CELL - s.center.y + s.offset.y
		for ci in cw:
			coarse[cj * cw + ci] = warp.get_noise_2d(-half_size + (i0 + ci * WARP_STEP) * CELL - s.center.x + s.offset.x, z)
	var amp := 0.55 * s.roughness
	var inv := 1.0 / WARP_STEP
	# Each row only needs the span inside the ellipse the warp can reach: solve
	# lx² + ly² = (radius·(1 + amp))² for x.
	var s2 := s.stretch * s.stretch
	var qa := s.ax.x * s.ax.x / s2 + s.ay.x * s.ay.x * s2
	var rr := s.radius * (1.0 + amp)
	for j in range(j0, j1 + 1):
		var pz := -half_size + j * CELL - s.center.y
		var qb := 2.0 * pz * (s.ax.x * s.ax.y / s2 + s.ay.x * s.ay.y * s2)
		var qc := pz * pz * (s.ax.y * s.ax.y / s2 + s.ay.y * s.ay.y * s2) - rr * rr
		var disc := qb * qb - 4.0 * qa * qc
		if disc <= 0.0:
			continue
		var sq := sqrt(disc)
		var ra := maxi(i0, _index_of(s.center.x + (-qb - sq) / (2.0 * qa)) - 1)
		var rb := mini(i1, _index_of(s.center.x + (-qb + sq) / (2.0 * qa)) + 1)
		var fj := (j - j0) * inv
		var cj := int(fj)
		var tj := fj - cj
		for i in range(ra, rb + 1):
			var px := -half_size + i * CELL - s.center.x
			var lx := (px * s.ax.x + pz * s.ax.y) / s.stretch
			var ly := (px * s.ay.x + pz * s.ay.y) * s.stretch
			var base := sqrt(lx * lx + ly * ly) / s.radius
			# The warp stays within ±1, so past here it can't pull the shore out this far.
			if base - amp >= 1.0:
				continue
			var fi := (i - i0) * inv
			var ci := int(fi)
			var ti := fi - ci
			var c0 := cj * cw + ci
			var wv := lerpf(lerpf(coarse[c0], coarse[c0 + 1], ti), lerpf(coarse[c0 + cw], coarse[c0 + cw + 1], ti), tj)
			var e := clampf(1.0 - base - wv * amp, 0.0, 1.0) * s.strength
			var k := j * (n + 1) + i
			if e > e_grid[k]:
				e_grid[k] = e
				owner_grid[k] = idx


## Elevation of one stamp at x, z, sampling the warp directly (past the grid's edge).
func _stamp_e(s: Stamp, x: float, z: float) -> float:
	var p := Vector2(x - s.center.x, z - s.center.y)
	var lx := p.dot(s.ax) / s.stretch
	var ly := p.dot(s.ay) * s.stretch
	var base := sqrt(lx * lx + ly * ly) / s.radius
	var amp := 0.55 * s.roughness
	if base - amp >= 1.0:
		return 0.0
	var d := base + warp.get_noise_2d(p.x + s.offset.x, p.y + s.offset.y) * amp
	return clampf(1.0 - d, 0.0, 1.0) * s.strength


## Turns elevation into heights, for the parts stamped since the last call (the
## rest is open sea, or already done). The grid's edge needs no fade: the Backdrop
## carries the land on from it (outer_height), so the mainland runs on past it.
func finalize() -> void:
	if h_grid.is_empty():
		h_grid.resize(e_grid.size())
		h_grid.fill(SEA_FLOOR)
	for r in _dirty:
		for j in range(r.position.y, r.end.y):
			var z := -half_size + j * CELL
			for i in range(r.position.x, r.end.x):
				var k := j * (n + 1) + i
				var o := owner_grid[k]
				if o >= 0:
					h_grid[k] = _height_of(e_grid[k], -half_size + i * CELL, z, stamps[o])
	_dirty.clear()


## A steep rocky shoreline, then gentle hills, broken up well inland into ridges and valleys.
## Open sea (e = 0) comes out at SEA_FLOOR exactly.
func _height_of(e: float, x: float, z: float, s: Stamp) -> float:
	if e <= 0.0:
		return SEA_FLOOR
	var nx := x - s.center.x + s.offset.x
	var nz := z - s.center.y + s.offset.y
	var land := smoothstep(0.2, 0.32, e)
	var relief := hills.get_noise_2d(nx, nz) * 66.0 * s.hills * smoothstep(1.0, 3.0, e)
	# Past the shore the ground eases off, leaving room for towns and farms.
	var rise := minf(e, 0.4) + maxf(e - 0.4, 0.0) * 0.5
	var bumps := detail.get_noise_2d(nx, nz) * 5.4 + rubble.get_noise_2d(nx, nz) * 1.3
	return SEA_FLOOR + land * 18.6 + rise * 21.0 + bumps * land + relief


## The island whose stamp shaped the ground at x, z (-1: open sea, mainland, islets).
func island_at(x: float, z: float) -> int:
	var o := owner_grid[_index_of(z) * (n + 1) + _index_of(x)]
	return stamps[o].island_id if o >= 0 else -1


## Height past the grid: the mainland's shores, hills and mountains, and the parts
## of island stamps that reach out past the edge.
func outer_height(x: float, z: float) -> float:
	var inl := mainland.inland(x, z)
	var e := mainland.elev(x, z, inl)
	var best: Stamp = null
	# Out in the open channel, stamps sink away just past the edge so they leave
	# the shipping lanes clear; near the shores they run on into the mainland.
	var out := maxf(absf(x), absf(z)) - half_size
	var keep := 1.0 - smoothstep(0.0, 180.0, out) * (1.0 - smoothstep(-660.0, -180.0, inl))
	if keep > 0.0:
		for s in _edge_stamps:
			var se := _stamp_e(s, x, z) * keep
			if se > e:
				e = se
				best = s
	if best == null:
		best = _world_stamp
	return _height_of(e, x, z, best) + mainland.relief(x, z, inl, e)


func add_flat(origin: Vector3, dir: Vector3, u0: float, u1: float, v0: float, v1: float, height: float, blend: float) -> void:
	flats.append({"o": origin, "n": dir, "t": Vector3.UP.cross(dir), "u0": u0, "u1": u1,
		"v0": v0, "v1": v1, "h": height, "blend": blend})


func apply_flats() -> void:
	for f in flats:
		var o: Vector3 = f.o
		var nd: Vector3 = f.n
		var td: Vector3 = f.t
		var u0: float = f.u0
		var u1: float = f.u1
		var v0: float = f.v0
		var v1: float = f.v1
		var blend: float = f.blend
		var target: float = f.h
		var reach := maxf(absf(u0), absf(u1)) + maxf(absf(v0), absf(v1)) + blend
		var i0 := _index_of(o.x - reach)
		var i1 := _index_of(o.x + reach)
		var j0 := _index_of(o.z - reach)
		var j1 := _index_of(o.z + reach)
		for j in range(j0, j1 + 1):
			for i in range(i0, i1 + 1):
				var p := Vector3(-half_size + i * CELL, 0.0, -half_size + j * CELL) - o
				var u := p.dot(nd)
				var v := p.dot(td)
				var du := maxf(maxf(u0 - u, u - u1), 0.0)
				var dv := maxf(maxf(v0 - v, v - v1), 0.0)
				var dd := sqrt(du * du + dv * dv)
				if dd >= blend:
					continue
				var k := j * (n + 1) + i
				h_grid[k] = lerpf(h_grid[k], target, 1.0 - smoothstep(0.0, blend, dd))


## Cuts a pocket beach into the shore at `origin` (on the waterline), facing out
## along `dir`: a gentle slope from `back` inland, curving deeper in at the middle,
## down to `front` out to sea, `half_w` either side, blending into the banks.
func carve_beach(origin: Vector3, dir: Vector3, half_w: float, back: float, front: float) -> void:
	var td := Vector3.UP.cross(dir)
	var reach := half_w + back + front + 12.0
	for j in range(_index_of(origin.z - reach), _index_of(origin.z + reach) + 1):
		for i in range(_index_of(origin.x - reach), _index_of(origin.x + reach) + 1):
			var p := Vector3(-half_size + i * CELL, 0.0, -half_size + j * CELL) - origin
			var u := p.dot(dir)
			var v := p.dot(td)
			var across := absf(v) / half_w
			if across >= 1.0:
				continue
			var u_back := -back * (1.0 - 0.45 * across * across)
			var w := (1.0 - smoothstep(0.55, 1.0, across)) * smoothstep(u_back - 12.0, u_back, u) \
				* (1.0 - smoothstep(front - 9.0, front + 9.0, u))
			if w <= 0.0:
				continue
			var s := clampf((u - u_back) / (front - u_back), 0.0, 1.0)
			var k := j * (n + 1) + i
			# Only ever cut down: no spits built out into deep water off a point.
			h_grid[k] = minf(h_grid[k], lerpf(h_grid[k], lerpf(4.5, -7.8, pow(s, 0.85)), w))


func h_index(i: int, j: int) -> float:
	return h_grid[j * (n + 1) + i]


## Height of the rendered surface (matches the alternating-diagonal triangulation).
func height_at(x: float, z: float) -> float:
	var fx := (x + half_size) / CELL
	var fz := (z + half_size) / CELL
	if fx < 0.0 or fz < 0.0 or fx >= n or fz >= n:
		return outer_height(x, z)
	var i := int(fx)
	var j := int(fz)
	var tx := fx - i
	var tz := fz - j
	var k := j * (n + 1) + i
	var a := h_grid[k]
	var b := h_grid[k + 1]
	var c := h_grid[k + n + 1]
	var d := h_grid[k + n + 2]
	if (i + j) % 2 == 0:
		if tx >= tz:
			return a + (b - a) * tx + (d - b) * tz
		return a + (c - a) * tz + (d - c) * tx
	if tx + tz <= 1.0:
		return a + (b - a) * tx + (c - a) * tz
	return d + (c - d) * (1.0 - tx) + (b - d) * (1.0 - tz)


func height_v(p: Vector3) -> float:
	return height_at(p.x, p.z)
