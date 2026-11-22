class_name Terrain
extends RefCounted
## Heightfield for the whole map. Islands are "stamped" into an elevation grid, shaped
## into rocky shores and rolling hills, then flattened where terminals need level ground.
## height_at() matches the rendered triangles exactly, so props sit on the surface.

## About 4 m between samples. 1600 cells across the map: the Backdrop's rings halve
## the edge's sample count twice, so the count must divide by 4.
const CELL := 6600.0 / 1600.0
const SEA_FLOOR := -16.5
## Lowest an inland valley comes with Lakes at 0 (m above the sea).
const LAKE_FLOOR := 2.5


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
	var peak := 0.0        # a mountain rising over the island's middle
	var lakes := 1.0       # 1: valleys may dip under the sea; 0: they ease off above it
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
## owner_grid's mark for ground the mainland shaped (not an island's stamp).
const MAINLAND := -2
## Island stamps sink away over this far in from the grid's edge, so only the
## mainland crosses it and the Backdrop has nothing else to carry on.
const EDGE_FADE := 150.0
## How far the mainland's coastline wanders either side of its line (m).
const MAINLAND_RAGGED := 170.0
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
	_world_stamp.offset = Vector2.ZERO


## Which sides of the channel have a mainland port (points on them), then stamps
## those shores into the grid. Call once, before any island stamps.
func set_mainland_ports(ports: Array[Vector2]) -> void:
	for p in ports:
		mainland.port_side[0 if mainland.side_of(p.x, p.y) > 0.0 else 1] = true
	var all := Rect2i(0, 0, n + 1, n + 1)
	_mainland_into(all)
	_dirty.append(all)


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
	for j in range(r.position.y, r.end.y):
		for i in range(r.position.x, r.end.x):
			var g := j * (n + 1) + i
			e_grid[g] = 0.0
			owner_grid[g] = -1
			h_grid[g] = SEA_FLOOR
	_mainland_into(r)
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
			var edge := half_size - maxf(absf(px + s.center.x), absf(pz + s.center.y))
			if edge < EDGE_FADE:
				e *= smoothstep(0.0, EDGE_FADE, edge)
			var k := j * (n + 1) + i
			if e > e_grid[k]:
				e_grid[k] = e
				owner_grid[k] = idx


## The mainland's elevation at x, z (with `inl`, its distance inland, roughened
## so its coastline is as ragged as an island's). Shared by the grid and
## outer_height, so the two agree exactly at the grid's edge.
func mainland_e(x: float, z: float) -> Vector2:
	var inl := mainland.inland(x, z) + warp.get_noise_2d(x + 91000.0, z) * MAINLAND_RAGGED
	return Vector2(mainland.elev(x, z, inl), inl)


## Stamps the mainland's shores into the grid inside `r` (vertex indices): the
## strips along the channel's sides where they come in past the edge.
func _mainland_into(r: Rect2i) -> void:
	var reach := half_size - Mainland.INSET - Mainland.INSET_VARY - MAINLAND_RAGGED - Mainland.SHORE_E / Mainland.SHORE_SLOPE - 40.0
	for j in range(r.position.y, r.end.y):
		var z := -half_size + j * CELL
		for i in range(r.position.x, r.end.x):
			var x := -half_size + i * CELL
			var v := absf(x) if mainland.axis == 1 else absf(z)
			if v < reach or not mainland.has_port(x, z):
				continue
			var e := mainland_e(x, z).x
			var k := j * (n + 1) + i
			if e > e_grid[k]:
				e_grid[k] = e
				owner_grid[k] = MAINLAND


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
				elif o == MAINLAND:
					h_grid[k] = _height_of(e_grid[k], -half_size + i * CELL, z, _world_stamp)
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
	var ground := SEA_FLOOR + land * 18.6 + rise * 21.0 + bumps * land
	if s.peak > 0.0:
		# How far in from the shore, 0..1 (e over the stamp's full strength), so the
		# mountain follows the island's own shape; the hill noise breaks up its flanks.
		var t := clampf(e / maxf(s.strength, 0.01), 0.0, 1.0)
		var mount := smoothstep(0.15, 1.0, t)
		ground += s.peak * 150.0 * mount * mount * (0.8 + 0.35 * hills.get_noise_2d(nx * 1.7, nz * 1.7))
	if relief < 0.0 and s.lakes < 1.0:
		# Valleys ease off as they near the sea instead of cutting under it.
		var room := maxf(ground - LAKE_FLOOR, 0.01)
		relief = lerpf(-room * (1.0 - exp(relief / room)), relief, s.lakes)
	return ground + relief


## The island whose stamp shaped the ground at x, z (-1: open sea, mainland, islets).
func island_at(x: float, z: float) -> int:
	var o := owner_grid[_index_of(z) * (n + 1) + _index_of(x)]
	return stamps[o].island_id if o >= 0 else -1


## Height past the grid: the mainland's shores, hills and mountains. (Island
## stamps sink away before the edge, so nothing else crosses it.)
func outer_height(x: float, z: float) -> float:
	var m := mainland_e(x, z)
	return _height_of(m.x, x, z, _world_stamp) + mainland.relief(x, z, m.y, m.x)


func add_flat(origin: Vector3, dir: Vector3, u0: float, u1: float, v0: float, v1: float, height: float, blend: float) -> void:
	flats.append({"o": origin, "n": dir, "t": Vector3.UP.cross(dir), "u0": u0, "u1": u1,
		"v0": v0, "v1": v1, "h": height, "blend": blend})


func apply_flats() -> void:
	for f in flats:
		_apply_flat(f)


## Levels the ground right away (not kept in `flats`): a house lot, the rect
## `u0..u1` along `dir` and `v0..v1` across it from `origin`, at `height`, easing
## back to the ground around it over `blend`.
func level_now(origin: Vector3, dir: Vector3, u0: float, u1: float, v0: float, v1: float, height: float, blend: float) -> void:
	_apply_flat({"o": origin, "n": dir, "t": Vector3.UP.cross(dir), "u0": u0, "u1": u1,
		"v0": v0, "v1": v1, "h": height, "blend": blend})


func _apply_flat(f: Dictionary) -> void:
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


## Dredging (a slip bought where the water is shallow, Terminal): the ground over
## the rect `u0..u1` along `dir` and `-half..half` across it from `origin` cut down
## to `depth`, easing back to the seabed round it over `blend`, never raised.
## Returns the cubic metres that takes; with `apply` it is cut, and `touched` is the
## grid rect it changed (for WorldBuilder.rebuild_terrain).
var touched := Rect2i()
func dredge(origin: Vector3, dir: Vector3, u0: float, u1: float, half: float, depth: float, blend: float, apply := false) -> float:
	var td := Vector3.UP.cross(dir)
	var reach := maxf(absf(u0), absf(u1)) + half + blend
	var i0 := _index_of(origin.x - reach)
	var i1 := _index_of(origin.x + reach)
	var j0 := _index_of(origin.z - reach)
	var j1 := _index_of(origin.z + reach)
	var volume := 0.0
	var lo := Vector2i(i1, j1)
	var hi := Vector2i(i0, j0)
	for j in range(j0, j1 + 1):
		for i in range(i0, i1 + 1):
			var p := Vector3(-half_size + i * CELL, 0.0, -half_size + j * CELL) - origin
			var u := p.dot(dir)
			var v := p.dot(td)
			var du := maxf(maxf(u0 - u, u - u1), 0.0)
			var dv := maxf(absf(v) - half, 0.0)
			var dd := sqrt(du * du + dv * dv)
			if dd >= blend:
				continue
			var k := j * (n + 1) + i
			var cut := minf(h_grid[k], lerpf(h_grid[k], depth, 1.0 - smoothstep(0.0, blend, dd)))
			if cut >= h_grid[k] - 0.01:
				continue
			volume += (h_grid[k] - cut) * CELL * CELL
			if apply:
				h_grid[k] = cut
				lo = Vector2i(mini(lo.x, i), mini(lo.y, j))
				hi = Vector2i(maxi(hi.x, i), maxi(hi.y, j))
	if apply:
		touched = Rect2i(lo, hi - lo + Vector2i.ONE) if hi.x >= lo.x else Rect2i()
	return volume


## Irons the small bumps out of the ground around `center` (a town) so house lots
## come out nearly level, keeping the broad hills: the heights are box-blurred
## twice (about TOWN_BLUR cells either way), full strength out to `radius`, easing
## back to the raw ground over `fade`. Low ground (shore cliffs, beaches, the
## ferry lot) keeps its shape.
const TOWN_BLUR := 6
func smooth_town(center: Vector3, radius: float, fade: float) -> void:
	var reach := radius + fade
	var pad := TOWN_BLUR * 2
	var i0 := maxi(_index_of(center.x - reach) - pad, 0)
	var i1 := mini(_index_of(center.x + reach) + pad, n)
	var j0 := maxi(_index_of(center.z - reach) - pad, 0)
	var j1 := mini(_index_of(center.z + reach) + pad, n)
	var w := i1 - i0 + 1
	var hgt := j1 - j0 + 1
	var src := PackedFloat32Array()
	src.resize(w * hgt)
	for j in hgt:
		for i in w:
			src[j * w + i] = h_grid[(j0 + j) * (n + 1) + i0 + i]
	var blur := src.duplicate()
	for pass_ in 2:
		blur = _box_blur(blur, w, hgt, true)
		blur = _box_blur(blur, w, hgt, false)
	for j in hgt:
		var z := -half_size + (j0 + j) * CELL
		for i in w:
			var x := -half_size + (i0 + i) * CELL
			var d := Vector2(x - center.x, z - center.z).length()
			if d >= reach:
				continue
			var a := src[j * w + i]
			var b := blur[j * w + i]
			var k := (1.0 - smoothstep(radius, reach, d)) * smoothstep(4.0, 7.0, minf(a, b))
			h_grid[(j0 + j) * (n + 1) + i0 + i] = lerpf(a, b, k)


## One box-blur pass along rows (`along_x`) or columns, edges clamped.
func _box_blur(g: PackedFloat32Array, w: int, h: int, along_x: bool) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(g.size())
	var r := TOWN_BLUR
	var lines := h if along_x else w
	var span := w if along_x else h
	for l in lines:
		var sum := 0.0
		for t in range(-r, r + 1):
			var c := clampi(t, 0, span - 1)
			sum += g[l * w + c] if along_x else g[c * w + l]
		for t in span:
			out[l * w + t if along_x else t * w + l] = sum / (2 * r + 1)
			var add := clampi(t + r + 1, 0, span - 1)
			var sub := clampi(t - r, 0, span - 1)
			sum += (g[l * w + add] - g[l * w + sub]) if along_x else (g[add * w + l] - g[sub * w + l])
	return out


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
