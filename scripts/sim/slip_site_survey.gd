class_name SlipSiteSurvey
extends RefCounted
## Plans berth positions, measures the required seabed cuts, and applies the chosen cut.

const DREDGE_DEPTH := -7.0
const DREDGE_BLEND := 18.0

var sim: Simulation
var town: MapData.Town
var _sites := {}


func _init(simulation: Simulation, terminal_town: MapData.Town) -> void:
	sim = simulation
	town = terminal_town
	sim.slip_sites_changed.connect(_invalidate)


func _invalidate() -> void:
	_sites.clear()


func dredge(v: float, working: bool) -> Rect2i:
	var reach := reach_for(working)
	sim.terrain.dredge(position_at(v, 0.0), town.dock_dir, Layout.PIER_END + 4.0, reach.x + 10.0, reach.y + 7.0,
		DREDGE_DEPTH, DREDGE_BLEND, true)
	return sim.terrain.touched


## Where a new working slip (or tie-up) can go along the shore: beside the end
## slip on either side, facing the same way, as Vector2(v, cubic metres to dredge
## there, 0 for none). The side with clear water comes first; with both clear (or
## both needing dredging), tie-ups keep to the side they are on (the right to begin
## with) and working slips go to the other. Empty if neither side can take one.
func sites(tie_up: bool) -> Array[Vector2]:
	var out: Array[Vector2] = []
	if town.slips.is_empty():
		return out
	var lo := INF
	var hi := -INF
	var sums := [0.0, 0.0]     # working, tie-up
	var counts := [0, 0]
	for i in town.slips.size():
		var v := town.slip_offset(i)
		lo = minf(lo, v)
		hi = maxf(hi, v)
		var k := 1 if town.slips[i].tie_up else 0
		sums[k] += v
		counts[k] += 1
	var tie_side := 1.0
	if counts[0] > 0 and counts[1] > 0 and sums[1] / counts[1] < sums[0] / counts[0]:
		tie_side = -1.0
	# Tie-ups go side by side; a slip next to a working slip keeps a slip spacing.
	var lo_tie := false
	var hi_tie := false
	for i in town.slips.size():
		if is_equal_approx(town.slip_offset(i), lo):
			lo_tie = town.slips[i].tie_up
		if is_equal_approx(town.slip_offset(i), hi):
			hi_tie = town.slips[i].tie_up
	var right := hi + (Layout.TIE_UP_SPACING if tie_up and hi_tie else Layout.SLIP_SPACING)
	var left := lo - (Layout.TIE_UP_SPACING if tie_up and lo_tie else Layout.SLIP_SPACING)
	var first := right if tie_up == (tie_side > 0.0) else left
	for v: float in [first, left if first == right else right]:
		var m3 := volume_at(v, not tie_up)
		if m3 >= 0.0:
			out.append(Vector2(v, m3))
	if out.size() == 2 and out[1].y < out[0].y:
		out.reverse()
	return out


## How far out (x) and how far either side (y) a new slip needs deep water: out past
## its dolphins and a boat's straight run in for a working slip, or for a tie-up
## just where a boat lies.
static func reach_for(working: bool) -> Vector2:
	if working:
		return Vector2(Layout.CHANNEL_BUOY_U + Terminal.REAIM_HOLD + 120.0, 15.0)
	return Vector2(Layout.DOCK_U + Layout.FERRY_HALF, 10.0)


## Whether a slip can go at `v`: 0 if the water off it is deep already, the cubic
## metres to dredge if only shallows are in the way, -1 if it can't (land in the way,
## no shore for its pier, or too near another dock's slips).
func volume_at(v: float, working: bool) -> float:
	var key := "%d|%s" % [roundi(v), working]
	if not _sites.has(key):
		_sites[key] = _survey_site(v, working)
	return _sites[key]


func _survey_site(v: float, working: bool) -> float:
	var terrain := sim.terrain
	if terrain == null:
		return -1.0   # (a bare test terminal: no shore to build along)
	# Its pier meets the shore about where the lot's does.
	if terrain.height_v(position_at(v, Layout.LOT_FRONT)) < -6.0:
		return -1.0
	var berth := position_at(v, Layout.DOCK_U)
	for t in sim.map.dock_towns():
		if t == town:
			continue
		for i in t.slips.size():
			if t.berth_center(i).distance_to(berth) < Layout.SLIP_SPACING * 1.5:
				return -1.0
		if t.slips.is_empty() and t.shore.distance_to(berth) < Layout.SLIP_SPACING * 1.5:
			return -1.0
	var reach := reach_for(working)
	var deep := true
	var u := Layout.PIER_END + 12.0
	while u < reach.x:
		for dv: float in [-reach.y, 0.0, reach.y]:
			var h := terrain.height_v(position_at(v + dv, u))
			if h > Terrain.DREDGE_MAX_HEIGHT:
				return -1.0
			deep = deep and h <= -3.6
		u += 9.0
	if deep:
		return 0.0
	return terrain.dredge(position_at(v, 0.0), town.dock_dir, Layout.PIER_END + 4.0, reach.x + 10.0, reach.y + 7.0,
		DREDGE_DEPTH, DREDGE_BLEND)


## Point (v, u) of the terminal frame in the world, at sea level.
func position_at(v: float, u: float) -> Vector3:
	return town.shore + town.dock_dir * u + town.lateral() * v
