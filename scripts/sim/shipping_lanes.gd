class_name ShippingLanes
extends RefCounted
## The shipping channels cargo ships keep to: two-way traffic lanes either side
## of a centreline marked by yellow separation buoys (SeparationBuoys). Each
## channel's centreline follows the deep water from far past one end of the map
## to far past the other, starting from a guess at where it crosses the middle
## row (`CHANNELS`). Ships keep to the right of it.
##
## Keeping to a channel is how cargo ships normally go, not a rule: a ship may
## leave it (to call at a port, say) and find its own way.

## Where each channel crosses the map's middle row, across the passage (world x
## for a north–south passage). Main map only: the red (west) and blue (east)
## channels.
const MAIN_CHANNELS := {"red": -3700.0, "blue": 2300.0}

const STEP := 120.0         # between centreline points along the passage
const REACH := 3200.0       # how far past the map's edge the channels run
const SCAN := 1600.0        # how far either side of the last point to look for the channel
const SCAN_STEP := 20.0
const DEEP := -14.0         # water at least this deep counts as channel
const MIN_WIDTH := 220.0
const MAX_SHIFT := 140.0    # the centreline swings at most this far per STEP
const LANE_OFFSET := 85.0   # each lane's track, right of the centreline

var centrelines: Array[PackedVector2Array] = []   # each running from the low end of the passage to the high
var names: Array[String] = []


## Traces each of `guesses` (name -> cross-passage coordinate at the middle row).
## `axis` is the mainland's: 1 means the passage runs along z.
static func trace(terrain: Terrain, half_size: float, axis: int, guesses: Dictionary) -> ShippingLanes:
	var lanes := ShippingLanes.new()
	for nm: String in guesses:
		var line := _trace_one(terrain, half_size, axis, guesses[nm])
		if line.size() >= 8:
			lanes.centrelines.append(line)
			lanes.names.append(nm)
		else:
			push_warning("Shipping lane %s: no channel found near %.0f" % [nm, guesses[nm]])
	return lanes


static func _trace_one(terrain: Terrain, hs: float, axis: int, guess: float) -> PackedVector2Array:
	var reach := hs + REACH
	var n := int(reach / STEP)
	var c0 := _centre(terrain, axis, 0.0, guess, SCAN)
	if is_nan(c0):
		return PackedVector2Array()
	var fwd: Array[float] = [c0]
	var back: Array[float] = []
	for dir: int in [1, -1]:
		var c := c0
		for k in range(1, n + 1):
			var nc := _centre(terrain, axis, dir * k * STEP, c, SCAN)
			if is_nan(nc):
				break
			c = clampf(nc, c - MAX_SHIFT, c + MAX_SHIFT)
			(fwd if dir == 1 else back).append(c)
	back.reverse()
	var across: Array[float] = back + fwd
	var u0 := -back.size() * STEP
	# Ease out the kinks.
	for pass_i in 3:
		var sm := across.duplicate()
		for i in range(1, across.size() - 1):
			sm[i] = (across[i - 1] + 2.0 * across[i] + across[i + 1]) * 0.25
		across = sm
	var out := PackedVector2Array()
	for i in across.size():
		var u := u0 + i * STEP
		out.append(Vector2(across[i], u) if axis == 1 else Vector2(u, across[i]))
	return out


## The middle of the deep-water span on row `u` nearest `near` (NAN if none).
static func _centre(terrain: Terrain, axis: int, u: float, near: float, scan: float) -> float:
	var best := NAN
	var best_d := INF
	var start := NAN
	var v := near - scan
	while v <= near + scan + SCAN_STEP:
		var deep := v <= near + scan and _h(terrain, axis, u, v) < DEEP
		if deep and is_nan(start):
			start = v
		elif not deep and not is_nan(start):
			var end := v - SCAN_STEP
			if end - start >= MIN_WIDTH:
				var mid := (start + end) * 0.5
				var d := 0.0 if near >= start and near <= end else absf(mid - near)
				if d < best_d:
					best_d = d
					best = mid
			start = NAN
		v += SCAN_STEP
	return best


static func _h(terrain: Terrain, axis: int, u: float, v: float) -> float:
	return terrain.height_at(v, u) if axis == 1 else terrain.height_at(u, v)


## A ship's track along channel `i`: its right-hand lane, in from the far end
## of the passage it starts at (`forward`: from the low end) and out past the other.
func track(i: int, forward: bool) -> PackedVector2Array:
	var line := centrelines[i].duplicate()
	if not forward:
		line.reverse()
	var out := PackedVector2Array()
	for k in line.size():
		var a := line[maxi(k - 1, 0)]
		var b := line[mini(k + 1, line.size() - 1)]
		var d := (b - a).normalized()
		# Right of the way she's heading (x east, y south on screen: right is (-d.y, d.x)).
		out.append(line[k] + Vector2(-d.y, d.x) * LANE_OFFSET)
	return out


## Debug (`--lanes-png=path`): the water and land around the map, the map's
## square, each channel's centreline (yellow) and its two lanes.
func save_debug(terrain: Terrain, half_size: float, path: String) -> void:
	var ext := half_size + REACH
	var px := 512
	var img := Image.create(px, px, false, Image.FORMAT_RGB8)
	var to_px := func(p: Vector2) -> Vector2i:
		return Vector2i(int((p.x + ext) / (2.0 * ext) * px), int((p.y + ext) / (2.0 * ext) * px))
	for y in px:
		for x in px:
			var w := Vector2(x, y) / px * 2.0 * ext - Vector2(ext, ext)
			var h := terrain.height_at(w.x, w.y)
			img.set_pixel(x, y, Color(0.15, 0.3, 0.55) if h < DEEP else (Color(0.4, 0.6, 0.8) if h < 0.0 else Color(0.3, 0.55, 0.25)))
	for k in 2 * px:
		var t := float(k) / (2 * px) * 2.0 * half_size - half_size
		for q: Vector2 in [Vector2(-half_size, t), Vector2(half_size, t), Vector2(t, -half_size), Vector2(t, half_size)]:
			var c: Vector2i = to_px.call(q)
			img.set_pixelv(c.clamp(Vector2i.ZERO, Vector2i(px - 1, px - 1)), Color.WHITE)
	for i in centrelines.size():
		for line: PackedVector2Array in [centrelines[i], track(i, true), track(i, false)]:
			var col := Color.YELLOW if line == centrelines[i] else (Color.RED if names[i] == "red" else Color(0.3, 0.4, 1.0))
			for p in line:
				var c: Vector2i = to_px.call(p)
				if c.x >= 0 and c.y >= 0 and c.x < px and c.y < px:
					img.set_pixelv(c, col)
	img.save_png(path)
