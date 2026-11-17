class_name Mainland
extends RefCounted
## The land past the map's edge: the map sits in an inside passage, with mainland
## shores along two sides and open water only up and down the channel, which bends
## and narrows into the distance. It is laid out in layers that read as distance:
## low forested hills along the shores, blue ridges a few kilometres back, and far
## behind them snow-capped peaks, one of them a lone volcano. A few far islands sit
## out in the channel.
##
## An analytic heightfield in the same "elevation" units as Terrain's island stamps,
## so Terrain can sample it past its grid (and the nav grid sees the shore) and the
## Backdrop can follow it out to the horizon. Seeded from the map seed with its own
## generators, so it never reshuffles the map itself.

## How far out the land goes (the backdrop's outer edge, square).
const FAR := 27000.0
## Elevation per metre inland; 0.27 is the waterline (see Terrain._height_of).
const SHORE_SLOPE := 0.004
const SHORE_E := 0.27
## Alongside the map the shores run inside its grid, this far in from the edge
## (give or take INSET_VARY), so their coastlines are the islands' own terrain and
## only unbroken forest crosses the edge. Past the channel's open ends they ease
## back out to their own line over SHORE_EASE.
const INSET := 240.0
const INSET_VARY := 170.0
const SHORE_EASE := 2700.0
## A side with no mainland port isn't played on: its shore stays this far out past
## the map's edge (give or take FAR_VARY), so it is all Backdrop, drawn in one style.
const FAR_CLEAR := 380.0
const FAR_VARY := 110.0
## How deep the ribs and gullies cut into the snowy peaks (share of their height).
const CRAG_DEPTH := 0.13
## The snowy peaks rise from this far inland, to their full height PEAK_RISE further.
const PEAK_FOOT := 300.0
const PEAK_RISE := 3600.0

## 0: the channel runs east-west (along X), so open water lies E and W; 1: north-south.
var axis := 0
var half: float
## Height (m) above which faces facing the sky are snow.
var snowline := 1680.0
## Whether the +v / -v side has a mainland port (Terrain.set_mainland_ports). Only
## those shores come in past the map's edge.
var port_side: Array[bool] = [false, false]

var _width := PackedFloat32Array([0.0, 0.0])  # shore distance on the +v / -v side
var _close := PackedFloat32Array([0.0, 0.0])  # how far the +u / -u reaches close up (1: shut)
var _meander := 0.0
var _phase := 0.0
var _islands: Array[Vector4] = []  # x, z, radius, strength
var _peaks: Array[Vector4] = []    # x, z, radius, height
var _volcano := Vector4.ZERO
var _shore := FastNoiseLite.new()
var _hills := FastNoiseLite.new()
var _ridges := FastNoiseLite.new()
var _warp := FastNoiseLite.new()
var _crags := FastNoiseLite.new()


func _init(map_seed: int, half_size: float) -> void:
	half = half_size
	var rng := RandomNumberGenerator.new()
	rng.seed = map_seed * 7919 + 13
	axis = rng.randi_range(0, 1)
	_width[0] = rng.randf_range(half + 780.0, half + 1560.0)
	_width[1] = rng.randf_range(half + 780.0, half + 1560.0)
	# Both ends of the passage stay open to the horizon: one narrows between the
	# ranges to a gap, the other round a bend. (`shut` names the narrower end.)
	var shut := rng.randi_range(0, 1)
	_close[shut] = rng.randf_range(0.55, 0.7)
	_close[1 - shut] = rng.randf_range(0.45, 0.7)
	_meander = rng.randf_range(1500.0, 2700.0) * (1.0 if rng.randf() < 0.5 else -1.0)
	_phase = rng.randf() * TAU
	snowline = rng.randf_range(1560.0, 1800.0)

	_shore.seed = map_seed + 101
	_shore.frequency = 0.00053333
	_shore.fractal_octaves = 3
	_hills.seed = map_seed + 102
	_hills.frequency = 0.001
	_hills.fractal_octaves = 2
	_ridges.seed = map_seed + 103
	_ridges.frequency = 0.00026667
	_ridges.fractal_type = FastNoiseLite.FRACTAL_RIDGED
	_ridges.fractal_octaves = 2
	_warp.seed = map_seed + 104
	_warp.frequency = 0.0026667
	_warp.fractal_octaves = 2
	# Broad ribs and the gullies between them on the peaks' flanks, ~1.5 km apart.
	# One octave only: finer ones fall between the backdrop's samples as sawteeth.
	_crags.seed = map_seed + 105
	_crags.frequency = 0.00065
	_crags.fractal_type = FastNoiseLite.FRACTAL_RIDGED
	_crags.fractal_octaves = 1
	_crags.domain_warp_enabled = true
	_crags.domain_warp_amplitude = 420.0
	_crags.domain_warp_frequency = 0.0004

	# Far islands out in the channel, clear of the map and of the shores.
	var want := rng.randi_range(4, 7)
	for attempt in 80:
		if _islands.size() >= want:
			break
		var u := rng.randf_range(half + 1050.0, 13500.0) * (1.0 if rng.randf() < 0.5 else -1.0)
		var r := rng.randf_range(270.0, 780.0)
		var xz := _from_uv(u, _centre_v(u) + rng.randf_range(-2100.0, 2100.0))
		if inland(xz.x, xz.y) > -r * 1.4:
			continue
		var clash := false
		for o in _islands:
			if Vector2(o.x, o.y).distance_to(xz) < r + o.z + 450.0:
				clash = true
		if not clash:
			_islands.append(Vector4(xz.x, xz.y, r, rng.randf_range(2.0, 6.0)))

	# Snowy peaks far back on both sides and either side of the narrow end's gap; a
	# volcano stands alone on one side.
	for sgn: float in [1.0, -1.0]:
		for k in rng.randi_range(5, 8):
			var xz := _from_uv(rng.randf_range(-19500.0, 19500.0), sgn * rng.randf_range(14400.0, 22200.0))
			_peaks.append(Vector4(xz.x, xz.y, rng.randf_range(3900.0, 6900.0), rng.randf_range(1950.0, 3150.0)))
	for k in rng.randi_range(2, 3):
		# Pushed off the channel's line so the water runs out between them.
		var across := rng.randf_range(-1.0, 1.0)
		var xz := _from_uv((1.0 if shut == 0 else -1.0) * rng.randf_range(18000.0, 22200.0), signf(across) * (4500.0 + absf(across) * 6000.0))
		_peaks.append(Vector4(xz.x, xz.y, rng.randf_range(3900.0, 6900.0), rng.randf_range(1950.0, 3000.0)))
	var vs := 1.0 if rng.randf() < 0.5 else -1.0
	var vxz := _from_uv(rng.randf_range(-10500.0, 10500.0), vs * rng.randf_range(18000.0, 21000.0))
	_volcano = Vector4(vxz.x, vxz.y, rng.randf_range(9000.0, 10500.0), rng.randf_range(3750.0, 4350.0))


## The side of the channel (+1 / -1) facing x, z.
func side_of(x: float, z: float) -> float:
	var uv := _to_uv(x, z)
	return 1.0 if uv.y - _centre_v(uv.x) >= 0.0 else -1.0


## Along-channel (u) and across-channel (v) coordinates.
func _to_uv(x: float, z: float) -> Vector2:
	return Vector2(x, z) if axis == 0 else Vector2(z, x)


func _from_uv(u: float, v: float) -> Vector2:
	return Vector2(u, v) if axis == 0 else Vector2(v, u)


## The channel's centreline: straight past the map, bending further out.
func _centre_v(u: float) -> float:
	return _meander * smoothstep(half + 900.0, half + 9000.0, absf(u)) * sin(u / 9600.0 + _phase)


## How far across the channel (from its centreline) the shore on `side` (0: +v,
## 1: -v) stands at along-channel position `u`.
func shore_w(u: float, side: int) -> float:
	var far := _width[side] + _shore.get_noise_1d(u + side * 15000.0) * 660.0
	var near := half - INSET - _shore.get_noise_1d(u * 3.0 + side * 31000.0) * INSET_VARY
	if not port_side[side]:
		near = half + FAR_CLEAR + _shore.get_noise_1d(u * 3.0 + side * 31000.0) * FAR_VARY
	var w := lerpf(near, maxf(far, near), smoothstep(half - 300.0, half + SHORE_EASE, absf(u)))
	return w * (1.0 - smoothstep(7800.0, 18600.0, absf(u)) * _close[0 if u >= 0.0 else 1])


## Signed distance (m) inland from the channel's shore; negative out in the channel.
func inland(x: float, z: float) -> float:
	var uv := _to_uv(x, z)
	var v := uv.y - _centre_v(uv.x)
	return absf(v) - shore_w(uv.x, 0 if v >= 0.0 else 1)


## Whether the side of the channel facing x, z has a mainland port.
func has_port(x: float, z: float) -> bool:
	return port_side[0 if side_of(x, z) > 0.0 else 1]


## Along-channel / across-channel position of x, z (u, v).
func to_uv(x: float, z: float) -> Vector2:
	return _to_uv(x, z)


## Island-style elevation of the shores and far islands (no mountains).
func elev(x: float, z: float, inl: float) -> float:
	var e := 0.0
	if inl > -SHORE_E / SHORE_SLOPE:
		e = clampf(SHORE_E + inl * SHORE_SLOPE, 0.0, 1.3)
	for isl in _islands:
		var d := Vector2(x - isl.x, z - isl.y).length() / isl.z
		if d < 1.5:
			e = maxf(e, clampf(1.0 - d - _warp.get_noise_2d(x, z) * 0.3, 0.0, 1.0) * isl.w)
	return e


## Hills, ridges and peaks (m) added on top of the shore heights, only past the
## map's grid (so the two meet exactly at its edge) and only on land.
func relief(x: float, z: float, inl: float, e: float) -> float:
	var sq := maxf(absf(x), absf(z))
	var out := sq - half
	if out <= 0.0 or e < 0.3 or inl < 0.0:
		return 0.0
	var g := smoothstep(0.0, 240.0 + 0.5 * maxf(inl - out, 0.0), out) * smoothstep(0.3, 0.7, e) * (1.0 - smoothstep(FAR * 0.9, FAR, sq))
	# Low forested hills along the shore...
	var h := smoothstep(60.0, 2100.0, inl) * (60.0 + 330.0 * (_hills.get_noise_2d(x, z) * 0.5 + 0.5))
	# ...then a layer of blue ridges, kept below the snow...
	var ridge := _ridges.get_noise_2d(x, z) * 0.5 + 0.5
	var crag := -2.0
	var back := smoothstep(2700.0, 7800.0, inl)
	if back > 0.0:
		# (spurs and side valleys running down off their crests)
		crag = _crag(x, z)
		h += back * (270.0 + 750.0 * ridge) * (1.0 + 0.16 * crag * smoothstep(0.2, 0.6, ridge))
	# ...and the snowy peaks far behind.
	# The peaks' flanks ease down to the water over a few kilometres instead of
	# stopping dead short of it (which stood them up as sheer walls on the channel).
	var rise := smoothstep(PEAK_FOOT, PEAK_FOOT + PEAK_RISE, inl)
	if rise > 0.0:
		for p in _peaks:
			var d := Vector2(x - p.x, z - p.y).length()
			if d < p.z:
				if crag < -1.0:
					crag = _crag(x, z)
				# Ribs and gullies cut deepest on the upper flanks, fading out at
				# the foot and on the very top.
				var f := 1.0 - d / p.z
				var carve := 1.0 + CRAG_DEPTH * crag * smoothstep(0.0, 0.35, f) * (1.0 - 0.5 * smoothstep(0.7, 1.0, f))
				h = maxf(h, p.w * pow(f, 1.25) * (0.7 + 0.45 * ridge) * carve * rise)
		var dv := Vector2(x - _volcano.x, z - _volcano.y).length()
		if dv < _volcano.z:
			# Concave flanks up to a broad, slightly cut-off summit, scored by
			# gullies running straight down from the top.
			var ang := atan2(z - _volcano.y, x - _volcano.x)
			var gully := _crags.get_noise_2d(ang * _volcano.z * 0.4, dv * 0.18)
			var f := 1.0 - dv / _volcano.z
			var cone := _volcano.w * pow(f, 1.9) * (1.0 + 0.08 * gully * smoothstep(0.05, 0.4, f))
			h = maxf(h, minf(cone, _volcano.w * 0.93) * (0.94 + 0.12 * ridge) * rise)
	return h * g


## Ridged crags around zero: ribs stand up (+), gullies cut down (-).
func _crag(x: float, z: float) -> float:
	return _crags.get_noise_2d(x, z) * 1.2 - 0.25
