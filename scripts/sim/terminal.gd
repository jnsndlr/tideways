class_name Terminal
extends Node3D
## One town's ferry terminal. Cars spawn in town, drive to the holding lot, queue
## in the lanes for their destination, and board a ferry that serves it.
## The lot's lanes divide among the destinations its boats serve from here. When a
## destination's lanes are full, its cars may queue in another destination's lane
## if the next boat to load that lane serves both; otherwise they are turned away. Arriving cars drive
## off the pier, out through the exit lane and back into town.
## The node's transform is the terminal frame (see Layout).

signal extension_changed
signal refit_changed
## A slip bought here (Kind.SLIP or TIE_UP) is built and in use: `i` into town.slips.
signal slip_built(i: int)
## The seabed was dredged for a slip bought here (`rect`: Terrain grid cells changed).
signal seabed_dredged(rect: Rect2i)

enum WorkStage { IDLE, DRAINING, ARRIVING, PAVING, LEAVING, OPEN }
## Refitting a slip for bigger boats (TID-44): the slip closes to arrivals at once
## (boats on their way hold off REFIT_HOLD out), and once it is clear a pusher brings
## the crane scow in. The crew drives the new dolphins and wing walls, the slip takes
## the next size up as they leave, and it reopens when they have gone.
enum RefitStage { NONE, CLEARING, ARRIVING, WORKING, LEAVING }

const BUILD_MINUTES := 120.0
const ARRIVAL_MINUTES := 20.0
const DEPARTURE_MINUTES := 20.0
# Price of refitting a slip up to each size (by the size it becomes: medium, large).
const REFIT_PRICE := [0, 0, 8000, 20000]
const REFIT_ARRIVAL := 20.0
const REFIT_WORK := 150.0
const REFIT_DEPARTURE := 20.0
const REFIT_HOLD := 320.0      # how far out boats for a closed slip hold off (m)
# New slips (stage 5), built by the same crane scow as a refit: one slip job at a
# time. They go along the shore beside the others (new_slip_sites), dredged if need
# be, and are built small.
const MAX_WORKING_SLIPS := 3
const MAX_TIE_UPS := 2
const SLIP_PRICE := [0, 0, 12000, 18000]   # by the working slip it makes (2nd, 3rd)
const TIE_UP_PRICE := [0, 4000, 6000]      # by the tie-up it makes (1st, 2nd)
const SLIP_WORK := 440.0      # game minutes the crew works on a new working slip (8 h in all)
const TIE_UP_WORK := 200.0    # and on a tie-up (4 h)
# A route moved to a new slip keeps straight out of it this far past the berth,
# then eases back onto its old line over up to REAIM_BLEND.
const REAIM_HOLD := 150.0
const REAIM_BLEND := 500.0
# A boat leaving a slip keeps it until she is this far out (m).
const SLIP_LEAVE_CLEAR := 200.0
# Dredging (a slip where the water is too shallow): the seabed off it is cut to
# DREDGE_DEPTH, easing back over DREDGE_BLEND. Only seabed and low shore, never
# ground higher than DREDGE_MAX_HEIGHT. Priced and timed by the volume cut.
const DREDGE_DEPTH := -7.0
const DREDGE_BLEND := 18.0
const DREDGE_MAX_HEIGHT := 1.5
const DREDGE_PRICE := 0.25      # $ per cubic metre (rounded up to $500, at least $1,000)
const DREDGE_RATE := 12000.0    # cubic metres an hour, added to the build

const Lane = preload("res://scripts/sim/terminal_lane.gd")

var sim: Simulation
var town: MapData.Town
var lanes := {}        # destination town id -> Array[Lane] (MapData.NO_ROUTE when idle)
var slip_v := {}       # route id -> lateral offset of the slip it calls at
var ramps := {}        # route id -> the SlipRamp of the slip it calls at (none with the classic slip)
var slip_ramps: Array[SlipRamp] = []   # by slip index (null with the classic slip)
var slip_guides: Array[SlipGuides] = [] # by slip index: its wing walls and dolphins (null with
                                        # the classic slip)
## A terminal's slips share one road out. One ferry's outbound stream gets
## the forecourt until its last vehicle has passed the boarding approaches.
var unloading_ferry: Ferry

# The slip being refitted (-1 for none), how far along, and game minutes of work left
# once the crew is under way.
var refit_slip := -1
var refit_stage := RefitStage.NONE
var refit_remaining := 0.0
var refit_work := REFIT_WORK   # the crew's working time on this job
var refit_new := false         # building refit_slip new, rather than refitting it
## Routes waiting to move to another working slip (route id -> slip index) once no
## boat on them is under way or alongside here (spread_routes).
var pending_routes := {}
# Surveyed slip sites ("v|working" -> _site_dredge), kept until a slip is bought.
var _sites := {}
# Which way (+1 / -1 across the slips, the terminal frame's x) the flood tide sets a
# ferry lying alongside here; the ebb sets her the other way.
var flood_side := 1.0
var work_stage := WorkStage.IDLE
var staging_lanes: Array[Lane] = []
# Cars dispatched from the terminal may still be driving through their old lane.
var _boarding_from: Dictionary[int, Lane] = {}
var build_remaining := 0.0
var extra_lane: Lane
## Lot positions not paved yet, in the order they will be (empty once the lot is full).
var site_lanes: Array[float] = []
## Lanes paved since the game began, in order.
var paved: Array[float] = []

var slots_per_lane := Layout.slots_per_lane()
var avg_wait := 6.0    # minutes, moving average
var turned_recent := 0.0
var served_today := 0
var _inbound: Array[PackedVector3Array] = []
var _outbound: Array[PackedVector3Array] = []
var _spawn_acc := 0.0


## Equipment and material staging is on the outer side of the slip next to the
## extension. Every service keeps at least one full-width lane and its exit.
func can_stage_construction() -> bool:
	if not site_lanes.is_empty():
		return true   # the crew works from the unpaved ground beside the new lane
	if town.slips.is_empty() or town.construction_staging_lanes not in [1, 2]:
		return false
	var route_lanes: Array = lanes.get(lane_keys()[0], [])
	var count := town.construction_staging_lanes
	return route_lanes.size() > count and route_lanes[count - 1].v <= -Layout.EXIT_CLEAR


func buy_holding_lane() -> bool:
	return buy(find_upgrade(TerminalUpgrade.Kind.LANE))


# --- The purchase catalogue (stage 5) -----------------------------------------------

## Every upgrade this terminal can take, with its price, build time and what (if
## anything) stops it being bought now. One that can never be had here again (a
## third slip once there are three) is left out.
func upgrades() -> Array[TerminalUpgrade]:
	var out: Array[TerminalUpgrade] = []
	if town.lane_extension_price > 0 and not (extra_lane != null and site_lanes.is_empty()):
		var lane := TerminalUpgrade.new(TerminalUpgrade.Kind.LANE, "Holding lane (+%d spaces)" % slots_per_lane,
			town.lane_extension_price, BUILD_MINUTES)
		lane.blocked = _lane_blocked()
		out.append(lane)
	var working := _slip_count(false)
	if working < MAX_WORKING_SLIPS:
		out.append_array(_slip_offers(TerminalUpgrade.Kind.SLIP, ["", "", "Second", "Third"][working + 1] + " working slip",
			SLIP_PRICE[working + 1], REFIT_ARRIVAL + SLIP_WORK + REFIT_DEPARTURE))
	var ties := _slip_count(true)
	if ties < MAX_TIE_UPS:
		out.append_array(_slip_offers(TerminalUpgrade.Kind.TIE_UP, "Tie-up slip" if ties == 0 else "Second tie-up slip",
			TIE_UP_PRICE[ties + 1], REFIT_ARRIVAL + TIE_UP_WORK + REFIT_DEPARTURE))
	for i in town.slips.size():
		var price := refit_price(i)
		if price <= 0 or town.slips[i].building:
			continue
		var s := town.slips[i]
		var kind := TerminalUpgrade.Kind.TIE_UP_REFIT if s.tie_up else TerminalUpgrade.Kind.REFIT
		var refit := TerminalUpgrade.new(kind, "Refit %s %d to %s" % ["tie-up" if s.tie_up else "slip", slip_number(i),
			MapData.Slip.SIZE_NAMES[s.size + 1]], price, REFIT_ARRIVAL + REFIT_WORK + REFIT_DEPARTURE)
		refit.slip = i
		refit.blocked = _crane_busy()
		out.append(refit)
	return out


## A new slip (or tie-up) for each side of the slips it can go on, cheapest side
## first, each with the dredging it needs there; or one entry saying why it can't.
func _slip_offers(kind: TerminalUpgrade.Kind, title: String, price: int, minutes: float) -> Array[TerminalUpgrade]:
	var out: Array[TerminalUpgrade] = []
	var sites := new_slip_sites(kind == TerminalUpgrade.Kind.TIE_UP)
	for site in sites:
		var u := TerminalUpgrade.new(kind, title + (", %s side" % _side_name(site.x) if sites.size() > 1 else ""),
			price, minutes)
		u.v = site.x
		u.dredge_m3 = site.y
		if site.y > 0.0:
			u.dredge_price = maxi(1000, ceili(site.y * DREDGE_PRICE / 500.0) * 500)
			u.price += u.dredge_price
			u.build_minutes += ceilf(site.y / DREDGE_RATE) * 60.0
		u.blocked = _crane_busy()
		out.append(u)
	if out.is_empty():
		var none := TerminalUpgrade.new(kind, title, price, minutes)
		none.blocked = _crane_busy() if _crane_busy() != "" else "No room beside the slips, even dredged"
		out.append(none)
	return out


## Which way (a compass point) a slip at `v` lies from the others.
func _side_name(v: float) -> String:
	var mid := 0.0
	for i in town.slips.size():
		mid += town.slip_offset(i) / town.slips.size()
	var d := town.lateral() * signf(v - mid)
	var a := fposmod(rad_to_deg(atan2(d.x, -d.z)) + 22.5, 360.0)
	return ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"][int(a / 45.0)]


## The catalogue's `kind` entry (for a refit, of slip `i`; for a new slip, the one
## at `v` if given), or null if there is none.
func find_upgrade(kind: TerminalUpgrade.Kind, i := -1, v := NAN) -> TerminalUpgrade:
	for u in upgrades():
		if u.kind == kind and u.slip == i and (is_nan(v) or is_equal_approx(u.v, v)):
			return u
	return null


## Buys `offer` (from upgrades()): checks it afresh, pays for it and starts the work.
## False if it can't be bought now, its research isn't done, or cash is short.
func buy(offer: TerminalUpgrade) -> bool:
	if offer == null:
		return false
	var u := find_upgrade(offer.kind, offer.slip, offer.v)
	if u == null or u.blocked != "" or not sim.has_research(u.research) or sim.available_cash < u.price:
		return false
	sim.ledger.spend("purchases", u.price)
	match u.kind:
		TerminalUpgrade.Kind.LANE:
			_start_lane()
		TerminalUpgrade.Kind.SLIP, TerminalUpgrade.Kind.TIE_UP:
			_start_slip(u)
		TerminalUpgrade.Kind.REFIT, TerminalUpgrade.Kind.TIE_UP_REFIT:
			_start_refit(u.slip, REFIT_WORK, false)
	return true


## Slip `i`'s number as the player sees it: working slips and tie-ups are each
## counted from 1, left to right along the shore.
func slip_number(i: int) -> int:
	var n := 1
	for j in town.slips.size():
		if j != i and town.slips[j].tie_up == town.slips[i].tie_up and town.slip_offset(j) < town.slip_offset(i):
			n += 1
	return n


## Working slips (or tie-ups) here, counting one being built.
func _slip_count(tie_up: bool) -> int:
	var n := 0
	for slip in town.slips:
		if slip.tie_up == tie_up:
			n += 1
	return n


func _crane_busy() -> String:
	if refit_stage == RefitStage.NONE:
		return ""
	return "Building slip %d" % slip_number(refit_slip) if refit_new else "Wait until the slip refit is done"


func _lane_blocked() -> String:
	# An idle terminal (no boat scheduled to call) has nobody to queue in a new lane.
	if not has_service():
		return "No boat calls here yet"
	if not (work_stage == WorkStage.IDLE or work_stage == WorkStage.OPEN and not site_lanes.is_empty()):
		return "A lane is being built"
	if not can_stage_construction():
		return "Keep one lane open for service"
	return ""


func _start_lane() -> void:
	if site_lanes.is_empty():
		for i in town.construction_staging_lanes:
			staging_lanes.append(lanes[lane_keys()[0]][i])
	build_remaining = BUILD_MINUTES
	_set_work_stage(WorkStage.DRAINING)


func _set_work_stage(stage: WorkStage) -> void:
	work_stage = stage
	extension_changed.emit()


func stage_progress() -> float:
	match work_stage:
		WorkStage.ARRIVING:
			return (BUILD_MINUTES - build_remaining) / ARRIVAL_MINUTES
		WorkStage.PAVING:
			return (BUILD_MINUTES - ARRIVAL_MINUTES - build_remaining) / (BUILD_MINUTES - ARRIVAL_MINUTES - DEPARTURE_MINUTES)
		WorkStage.LEAVING:
			return 1.0 - build_remaining / DEPARTURE_MINUTES
	return 0.0


func _staging_clear() -> bool:
	for lane in staging_lanes:
		if lane.enroute > 0 or not lane.queue.is_empty() or _boarding_from.values().has(lane):
			return false
	return true


func _advance_construction(delta: float) -> void:
	if delta <= 0.0:
		return
	if work_stage == WorkStage.DRAINING:
		if _staging_clear():
			_set_work_stage(WorkStage.ARRIVING)
		return
	build_remaining = maxf(0.0, build_remaining - delta)
	if build_remaining == 0.0:
		extra_lane = Lane.new(extension_offset())
		paved.append(extra_lane.v)
		if not site_lanes.is_empty():
			site_lanes.pop_front()
		lanes[lane_keys()[0]].append(extra_lane)
		staging_lanes.clear()
		_set_work_stage(WorkStage.OPEN)
	elif build_remaining <= DEPARTURE_MINUTES and work_stage != WorkStage.LEAVING:
		_set_work_stage(WorkStage.LEAVING)
	elif build_remaining <= BUILD_MINUTES - ARRIVAL_MINUTES and work_stage == WorkStage.ARRIVING:
		_set_work_stage(WorkStage.PAVING)


# --- Refitting a slip ---------------------------------------------------------------

## What refitting slip `i` (working or tie-up) to the next size up costs (0 if it
## can't be: already large).
func refit_price(i: int) -> int:
	var slip := town.slips[i]
	if slip.size >= MapData.Slip.LARGEST_BOAT.size() - 1:
		return 0
	return REFIT_PRICE[slip.size + 1]


## The working slip (or with `tie_up`, the tie-up slip) to offer a refit for: the
## smallest one that can still grow (-1 if none, or one is already being refitted).
func next_refit(tie_up := false) -> int:
	if refit_stage != RefitStage.NONE:
		return -1
	var best := -1
	for i in town.slips.size():
		if town.slips[i].tie_up != tie_up or town.slips[i].building:
			continue
		if refit_price(i) > 0 and (best < 0 or town.slips[i].size < town.slips[best].size):
			best = i
	return best


func buy_refit(i: int) -> bool:
	if i < 0 or i >= town.slips.size():
		return false
	return buy(find_upgrade(TerminalUpgrade.Kind.TIE_UP_REFIT if town.slips[i].tie_up else TerminalUpgrade.Kind.REFIT, i))


func _start_refit(i: int, work: float, new_slip: bool) -> void:
	refit_slip = i
	refit_work = work
	refit_new = new_slip
	refit_remaining = REFIT_ARRIVAL + work + REFIT_DEPARTURE
	_set_refit_stage(RefitStage.CLEARING)


## Lays out a bought slip where `u` says (hidden and closed while it is built) and
## brings the crane scow in to build it.
func _start_slip(u: TerminalUpgrade) -> void:
	_sites.clear()
	if u.dredge_m3 > 0.0:
		var reach := _site_reach(u.kind == TerminalUpgrade.Kind.SLIP)
		sim.terrain.dredge(_at(u.v, 0.0), town.dock_dir, Layout.PIER_END + 4.0, reach.x + 10.0, reach.y + 7.0,
			DREDGE_DEPTH, DREDGE_BLEND, true)
		seabed_dredged.emit(sim.terrain.touched)
	town.freeze_slip_offsets()
	var tie := u.kind == TerminalUpgrade.Kind.TIE_UP
	var slip := MapData.Slip.new(1, tie)
	slip.v = u.v
	slip.building = true
	town.slips.append(slip)
	slip_ramps.append(null)
	slip_guides.append(null)
	_start_refit(town.slips.size() - 1, TIE_UP_WORK if tie else SLIP_WORK, true)


## Where a new working slip (or tie-up) can go along the shore: beside the end
## slip on either side, facing the same way, as Vector2(v, cubic metres to dredge
## there, 0 for none). The side with clear water comes first; with both clear (or
## both needing dredging), tie-ups keep to the side they are on (the right to begin
## with) and working slips go to the other. Empty if neither side can take one.
func new_slip_sites(tie_up: bool) -> Array[Vector2]:
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
		var m3 := _site_dredge(v, not tie_up)
		if m3 >= 0.0:
			out.append(Vector2(v, m3))
	if out.size() == 2 and out[0].y > 0.0 and out[1].y == 0.0:
		out.reverse()
	return out


## Where the first of new_slip_sites puts a slip (NAN if nowhere).
func new_slip_v(tie_up: bool) -> float:
	var sites := new_slip_sites(tie_up)
	return sites[0].x if not sites.is_empty() else NAN


## How far out (x) and how far either side (y) a new slip needs deep water: out past
## its dolphins and a boat's straight run in for a working slip, or for a tie-up
## just where a boat lies.
func _site_reach(working: bool) -> Vector2:
	if working:
		return Vector2(Layout.CHANNEL_BUOY_U + REAIM_HOLD + 120.0, 15.0)
	return Vector2(Layout.DOCK_U + Layout.FERRY_HALF, 10.0)


## Whether a slip can go at `v`: 0 if the water off it is deep already, the cubic
## metres to dredge if only shallows are in the way, -1 if it can't (land in the way,
## no shore for its pier, or too near another dock's slips).
func _site_dredge(v: float, working: bool) -> float:
	var key := "%d|%s" % [roundi(v), working]
	if not _sites.has(key):
		_sites[key] = _survey_site(v, working)
	return _sites[key]


func _survey_site(v: float, working: bool) -> float:
	var terrain := sim.terrain
	if terrain == null:
		return -1.0   # (a bare test terminal: no shore to build along)
	# Its pier meets the shore about where the lot's does.
	if terrain.height_v(_at(v, Layout.LOT_FRONT)) < -6.0:
		return -1.0
	var berth := _at(v, Layout.DOCK_U)
	for t in sim.map.dock_towns():
		if t == town:
			continue
		for i in t.slips.size():
			if t.berth_center(i).distance_to(berth) < Layout.SLIP_SPACING * 1.5:
				return -1.0
		if t.slips.is_empty() and t.shore.distance_to(berth) < Layout.SLIP_SPACING * 1.5:
			return -1.0
	var reach := _site_reach(working)
	var deep := true
	var u := Layout.PIER_END + 12.0
	while u < reach.x:
		for dv: float in [-reach.y, 0.0, reach.y]:
			var h := terrain.height_v(_at(v + dv, u))
			if h > DREDGE_MAX_HEIGHT:
				return -1.0
			deep = deep and h <= -3.6
		u += 9.0
	if deep:
		return 0.0
	return terrain.dredge(_at(v, 0.0), town.dock_dir, Layout.PIER_END + 4.0, reach.x + 10.0, reach.y + 7.0,
		DREDGE_DEPTH, DREDGE_BLEND)


## Point (v, u) of the terminal frame in the world, at sea level.
func _at(v: float, u: float) -> Vector3:
	return town.shore + town.dock_dir * u + town.lateral() * v


## A bought slip is built: it takes its ramp and guides and comes into use, and
## the routes boats sail from here spread over the working slips.
func _open_slip(i: int) -> void:
	var slip := town.slips[i]
	slip.building = false
	var v := town.slip_offset(i)
	if SlipRamp.available() and not slip.tie_up:
		slip_ramps[i] = SlipRamp.new(v)
		add_child(slip_ramps[i])
	if SlipGuides.available() and not slip.tie_up:
		slip_guides[i] = SlipGuides.new(v, transform, sim.terrain, sim.slip_guide_parts)
		add_child(slip_guides[i])
		slip_guides[i].fit(MapData.Slip.LARGEST_BOAT[slip.size])
	slip_built.emit(i)
	if not slip.tie_up:
		spread_routes()


# --- Spreading routes over the slips ------------------------------------------------

## Gives routes that share a working slip with another a slip of their own where
## one is free and big enough for their boats. A route only moves if a boat sails
## it; a boat that calls here on two legs keeps both on one slip. The move waits
## until no boat on it is under way or alongside here (_move_pending_routes).
func spread_routes() -> void:
	var working: Array[int] = []
	for i in town.slips.size():
		if not town.slips[i].tie_up and not town.slips[i].building:
			working.append(i)
	if working.size() < 2:
		return
	var calls := {}
	for i in working:
		calls[i] = 0
	var busy := []
	for g in _route_groups():
		if g.any(func(rid): return sim.map.routes[rid].in_service):
			busy.append(g)
			calls[_slip_of(g[0])] = calls.get(_slip_of(g[0]), 0) + 1
	while true:
		var best_g: Array = []
		var best_i := -1
		var best_score := INF
		for g in busy:
			var at := _slip_of(g[0])
			if calls.get(at, 0) <= 1:
				continue
			var side := _departure_side(g)
			for i in working:
				if i == at or calls[i] + 1 >= calls[at] or not _group_fits(g, i) or slip_shut(i):
					continue
				# The emptiest slip, on the side the route heads off to.
				var score: float = calls[i] * 10.0 - side * signf(town.slip_offset(i) - town.slip_offset(at))
				if score < best_score:
					best_score = score
					best_g = g
					best_i = i
		if best_i < 0:
			break
		calls[_slip_of(best_g[0])] -= 1
		calls[best_i] += 1
		for rid in best_g:
			if town.slip_index(rid) == best_i:
				pending_routes.erase(rid)
			else:
				pending_routes[rid] = best_i


## Whether slip `i` is closed for a refit (not a new slip whose crew is leaving).
func slip_shut(i: int) -> bool:
	return refit_stage != RefitStage.NONE and i == refit_slip and not (refit_new and refit_stage == RefitStage.LEAVING)


## Which slip route `rid` calls at here, or will once it has moved.
func _slip_of(rid: int) -> int:
	return pending_routes.get(rid, town.slip_index(rid))


## The routes calling here in groups that must share a slip: a boat that comes in
## on one and leaves on another (a multi-stop schedule) joins them.
func _route_groups() -> Array:
	var parent := {}
	for rid in town.route_ids():
		parent[rid] = rid
	var find := func(rid: int) -> int:
		while parent[rid] != rid:
			rid = parent[rid]
		return rid
	for f in sim.ferries:
		for plan in [[f.stops, f.legs], [f.next_stops, f._next_legs]]:
			var stops: Array = plan[0]
			var legs: Array = plan[1]
			if legs.size() != stops.size():
				continue
			for i in stops.size():
				if stops[i] != town.id:
					continue
				var a: int = legs[(i - 1 + legs.size()) % legs.size()].id
				var b: int = legs[i].id
				if parent.has(a) and parent.has(b):
					parent[find.call(a)] = find.call(b)
	var groups := {}
	for rid in parent:
		var r: int = find.call(rid)
		if not groups.has(r):
			groups[r] = []
		groups[r].append(rid)
	return groups.values()


## Whether every boat sailing a route in `g` fits slip `i`.
func _group_fits(g: Array, i: int) -> bool:
	for f in sim.ferries:
		for r in f.legs + f._next_legs:
			if r.id in g and not town.slips[i].fits(f.fc.size):
				return false
	return true


## Which way (+1 / -1 across the slips, about 0 straight out) the routes of `g` head.
func _departure_side(g: Array) -> float:
	var total := 0.0
	for rid in g:
		var r := sim.map.routes[rid]
		var s := minf(400.0, r.length * 0.4)
		var p := r.curve.sample_baked(s if r.a == town.id else r.length - s)
		total += (p - town.dock_center(rid)).normalized().dot(town.lateral())
	return total / maxf(g.size(), 1)


## Moves each group of routes waiting for another slip once no boat on them is
## under way or at this terminal. A route whose new end would run over land stays.
func _move_pending_routes() -> void:
	for g in _route_groups():
		var moving: Array = g.filter(func(rid): return pending_routes.has(rid))
		if moving.is_empty():
			continue
		var clear := true
		for f in sim.ferries:
			if f.route.id in g and (f.state == Ferry.State.SAILING or f.here() == self):
				clear = false
		if not clear:
			continue
		var curves := {}
		for rid in moving:
			var to: int = pending_routes[rid]
			var c := _reaimed_curve(sim.map.routes[rid], town.slip_offset(to) - town.slip_offset(town.slip_index(rid)))
			if c == null:
				push_warning("%s: route %d can't move to slip %d (land in the way)" % [town.name, rid, to])
				curves.clear()
				break
			curves[rid] = c
		if curves.is_empty():
			for rid in moving:
				pending_routes.erase(rid)
			continue
		for rid in moving:
			var to: int = pending_routes[rid]
			pending_routes.erase(rid)
			town.slips[town.slip_index(rid)].routes.erase(rid)
			town.slips[to].routes.append(rid)
			slip_v[rid] = town.slip_offset(to)
			if slip_ramps[to]:
				ramps[rid] = slip_ramps[to]
			else:
				ramps.erase(rid)
			var r := sim.map.routes[rid]
			r.curve = curves[rid]
			r.length = r.curve.get_baked_length()
			for f in sim.ferries:
				f.route_reshaped(r)
		if sim.marine:
			sim.marine.refresh_corridors()
		sim.routes_changed.emit()


## Route `r`'s curve with its end here moved `dv` across the slips: straight out of
## the new slip for REAIM_HOLD, then easing back onto the old line. Null if that
## would take it over land or the route is too short to ease back.
func _reaimed_curve(r: MapData.Route, dv: float) -> Curve3D:
	var blend := minf(REAIM_BLEND, r.length - REAIM_HOLD - 200.0)
	if blend < 120.0:
		return null
	var pts := r.curve.get_baked_points()
	var from_here := r.a == town.id
	if not from_here:
		pts.reverse()
	var shift := town.lateral() * dv
	var out := PackedVector3Array()
	var d := 0.0
	for k in pts.size():
		if k > 0:
			d += pts[k].distance_to(pts[k - 1])
		var w := 1.0 - smoothstep(REAIM_HOLD, REAIM_HOLD + blend, d)
		var p := pts[k] + shift * w
		if w > 0.0 and d > 36.0 and k + 1 < pts.size():
			var side := Vector3.UP.cross((pts[k + 1] - pts[k]).normalized()) * 18.0
			for o: Vector3 in [Vector3.ZERO, side, -side]:
				if sim.terrain.height_v(p + o) > -3.6:
					return null
		out.append(p)
	if not from_here:
		out.reverse()
	var c := Curve3D.new()
	c.bake_interval = r.curve.bake_interval
	for p in out:
		c.add_point(p)
	return c


## Whether tie-up slip `i` is closed for a refit (no boat may make for it).
func tie_up_closed(i: int) -> bool:
	return refit_stage != RefitStage.NONE and i == refit_slip


## Whether the slip `rid` calls at here is closed for a refit.
func slip_closed(rid: int) -> bool:
	return refit_stage != RefitStage.NONE and town.slip_index(rid) == refit_slip


## How far through its current stage the refit is (0..1).
func refit_progress() -> float:
	match refit_stage:
		RefitStage.ARRIVING:
			return clampf((REFIT_ARRIVAL + refit_work + REFIT_DEPARTURE - refit_remaining) / REFIT_ARRIVAL, 0.0, 1.0)
		RefitStage.WORKING:
			return clampf((refit_work + REFIT_DEPARTURE - refit_remaining) / refit_work, 0.0, 1.0)
		RefitStage.LEAVING:
			return clampf(1.0 - refit_remaining / REFIT_DEPARTURE, 0.0, 1.0)
	return 0.0


func _set_refit_stage(stage: RefitStage) -> void:
	refit_stage = stage
	refit_changed.emit()


func _advance_refit(delta: float) -> void:
	if refit_stage == RefitStage.CLEARING:
		if _refit_slip_clear():
			_set_refit_stage(RefitStage.ARRIVING)
		return
	refit_remaining = maxf(0.0, refit_remaining - delta)
	if refit_remaining == 0.0:
		refit_slip = -1
		refit_new = false
		_set_refit_stage(RefitStage.NONE)
	elif refit_remaining <= REFIT_DEPARTURE and refit_stage != RefitStage.LEAVING:
		if not refit_new:
			# The work is done: the slip takes the next size up, with its new guides.
			var slip := town.slips[refit_slip]
			slip.size += 1
			if slip_guides[refit_slip]:
				slip_guides[refit_slip].fit(MapData.Slip.LARGEST_BOAT[slip.size])
		_set_refit_stage(RefitStage.LEAVING)
		if refit_new:
			# A new slip is built: it comes into use as the crew leaves.
			_open_slip(refit_slip)
	elif refit_remaining <= refit_work + REFIT_DEPARTURE and refit_stage == RefitStage.ARRIVING:
		_set_refit_stage(RefitStage.WORKING)


## No boat lies at the slip being refitted, and none is coming in under the closure
## (inside REFIT_HOLD when it closed, so let finish her call).
func _refit_slip_clear() -> bool:
	if town.slips[refit_slip].tie_up:
		# A tie-up: no boat lies there or is on her way in or out.
		for f in sim.ferries:
			if f.berth != Ferry.Berth.WORKING and f.here() == self and f.tie_up == refit_slip:
				return false
		return true
	for f in sim.ferries:
		if f.berth != Ferry.Berth.WORKING or f.slip_at(self) != refit_slip:
			continue
		if f.state != Ferry.State.SAILING and f.here() == self:
			return false
		if f.state == Ferry.State.SAILING and f.destination() == self and f.path_left() < REFIT_HOLD - 5.0:
			return false
	return true


## Where the next lane goes: the next unpaved lot position, else alongside the lot.
func extension_offset() -> float:
	if not site_lanes.is_empty():
		return site_lanes[0]
	return -town.lot_half_width - Layout.LANE_WIDTH * 0.5


func setup(s: Simulation, isl: MapData.Town) -> void:
	sim = s
	town = isl
	name = isl.name + " Terminal"
	transform = isl.terminal_xform()
	flood_side = 1.0 if hash(isl.key if isl.key != "" else str(isl.id)) % 2 == 0 else -1.0
	for i in isl.slips.size():
		var ramp: SlipRamp = null
		if SlipRamp.available() and not isl.slips[i].tie_up:
			ramp = SlipRamp.new(isl.slip_offset(i))
			add_child(ramp)
		slip_ramps.append(ramp)
		var g: SlipGuides = null
		# (A tie-up's dolphins are shared with its neighbours: WorldBuilder._build_tie_up.)
		if SlipGuides.available() and not isl.slips[i].tie_up:
			g = SlipGuides.new(isl.slip_offset(i), transform, s.terrain, s.slip_guide_parts)
			add_child(g)
			g.fit(MapData.Slip.LARGEST_BOAT[isl.slips[i].size])
		slip_guides.append(g)
		for rid in isl.slips[i].routes:
			slip_v[rid] = isl.slip_offset(i)
			if ramp:
				ramps[rid] = ramp
	_build_road_paths()


## Divides the lot's lanes among `dests` (town ids, in lot order), once the
## boats and their schedules are known.
func build_lanes(dests: Array[int]) -> void:
	var isl := town
	lanes.clear()
	var keys := dests.duplicate()
	if keys.is_empty():
		keys.append(MapData.NO_ROUTE)
	var lane_sets := Layout.lane_positions(isl.lot_half_width, keys.size())
	if isl.open_lanes > 0:
		var order := Layout.lane_opening_order(isl.lot_half_width)
		site_lanes = order.slice(isl.open_lanes)
		var open := Layout.open_lanes(isl.lot_half_width, isl.open_lanes)
		lane_sets.clear()
		var start := 0
		for i in keys.size():
			var n := open.size() / keys.size() + (1 if i < open.size() % keys.size() else 0)
			lane_sets.append(PackedFloat32Array(open.slice(start, start + n)))
			start += n
	for i in keys.size():
		var arr: Array[Lane] = []
		for v in lane_sets[i]:
			arr.append(Lane.new(v))
		lanes[keys[i]] = arr


## After a schedule change: divides the lanes the lot has now (bought ones too)
## among `dests` again, left to right, keeping each lane and the cars in it. Cars
## left in a lane that now goes somewhere else move to their own or go home
## (sort_overflow), as they do when a shared boat leaves without them.
func relane(dests: Array[int]) -> void:
	var keys := dests.duplicate()
	if keys.is_empty():
		keys.append(MapData.NO_ROUTE)
	if keys == lane_keys():
		return
	var all: Array[Lane] = []
	for key in lanes:
		all.append_array(lanes[key])
	all.sort_custom(func(a: Lane, b: Lane): return a.v < b.v)
	lanes.clear()
	var start := 0
	for i in keys.size():
		var n := all.size() / keys.size() + (1 if i < all.size() % keys.size() else 0)
		var arr: Array[Lane] = []
		arr.assign(all.slice(start, start + n))
		lanes[keys[i]] = arr
		start += n
	sort_overflow()


## The wing walls and dolphins of the slip `rid` calls at here (null if none).
func guides_for(rid: int) -> SlipGuides:
	return guides_at(town.slip_index(rid))


## Slip `i`'s wing walls and dolphins (null if none).
func guides_at(i: int) -> SlipGuides:
	return slip_guides[i] if i >= 0 and i < slip_guides.size() else null


## The boat using working slip `i` here other than `f`: alongside, leaving and not yet
## clear, or coming in to it ahead of `f`. Null if it is free for her.
func slip_user(i: int, f: Ferry) -> Ferry:
	var left := f.path_left() if f.state == Ferry.State.SAILING and f.destination() == self else INF
	for g in sim.ferries:
		if g == f or g.slip_at(self) != i:
			continue
		if g.berth == Ferry.Berth.TO_WORKING and g.here() == self:
			return g
		if g.berth != Ferry.Berth.WORKING:
			continue
		if g.state != Ferry.State.SAILING:
			if g.here() == self:
				return g
		elif g.here() == self:
			if g.traveled < SLIP_LEAVE_CLEAR:
				return g
		elif g.destination() == self and g.path_left() < left:
			return g
	return null


## Which way across the slips (+1 / -1, the terminal frame's x) the tide sets a docked
## ferry now: the flood one way, the ebb the other.
func lie_side() -> float:
	return flood_side if sim.tide().y > 0.0 else -flood_side


## What the lot's lane groups are keyed by, in lot order: each destination served
## from here, or MapData.NO_ROUTE for the one group of an idle terminal.
func lane_keys() -> Array[int]:
	var keys: Array[int] = []
	keys.assign(lanes.keys())
	if keys.is_empty():
		keys.append(MapData.NO_ROUTE)
	return keys


func _build_road_paths() -> void:
	var to_lot := town.road_main_a.duplicate()
	to_lot.reverse()
	var branches: Array[PackedVector3Array] = []
	if town.road_main_b.size() > 1:
		branches.append(town.road_main_b)
	branches.append_array(town.road_cross)
	if branches.is_empty():
		branches.append(PackedVector3Array([town.road_main_a[town.road_main_a.size() - 1]]))
	for b in branches:
		var inbound := b.duplicate()
		inbound.reverse()
		inbound.append_array(to_lot)
		var road_path := _keep_right(inbound)
		var entrance := to_lot[-1]
		var length := (entrance - to_lot[0]).dot(town.dock_dir)
		for v: float in Layout.TICKET_LANES:
			var ticket_path := road_path.duplicate()
			for j in to_lot.size():
				var inland := (entrance - to_lot[j]).dot(town.dock_dir)
				ticket_path[b.size() + j] += town.lateral() * (v + Layout.EXIT_V) * Layout.ticket_spread(inland, length)
			_inbound.append(ticket_path)
		var outbound := town.road_main_a.duplicate()
		outbound.append_array(b)
		_outbound.append(_keep_right(outbound))


## Offsets a centre-line path onto the right-hand lane.
static func _keep_right(pts: PackedVector3Array) -> PackedVector3Array:
	var out := PackedVector3Array()
	var last_dir := Vector3.FORWARD
	for i in pts.size():
		var d := pts[mini(i + 1, pts.size() - 1)] - pts[maxi(i - 1, 0)]
		d.y = 0.0
		if d.length_squared() > 0.0001:
			last_dir = d.normalized()
		out.append(pts[i] + last_dir.cross(Vector3.UP) * 2.4)
	return out


func _local(v: float, u: float) -> Vector3:
	return to_global(Vector3(v, Layout.LOT_Y, u))


## Where `car` waits with `ahead` slots taken in front of it: the middle of its slots,
## shifted for a rig (whose tractor is ahead of its middle).
func queue_position(v: float, ahead: int, car: Vehicle) -> Vector3:
	var mid := Layout.LANE_HEAD - (ahead + (car.slots - 1) * 0.5) * Layout.SLOT
	return _local(v, mid - car.center_offset)


func _park_in_queue(car: Vehicle, lane: Lane, ahead: int) -> void:
	car.park_in_lane(queue_position(lane.v, ahead, car), atan2(town.dock_dir.x, town.dock_dir.z))


## The vehicle a lane's waiting record stands for.
static func _car(waiting: Lane.WaitingVehicle) -> Vehicle:
	return instance_from_id(waiting.vehicle_id) as Vehicle


## Moves each car in `lane` up to its place in the queue.
func _close_up(lane: Lane) -> void:
	var k := 0
	var ahead: Vehicle = null
	for waiting in lane.queue:
		var c := _car(waiting)
		_park_in_queue(c, lane, k)
		c.leader = ahead
		ahead = c
		k += c.slots


func _process(delta: float) -> void:
	if build_remaining > 0.0:
		_advance_construction(delta)
	if refit_stage != RefitStage.NONE:
		_advance_refit(delta)
	if not pending_routes.is_empty():
		_move_pending_routes()
	_spawn_acc += sim.demand_rate(town) * delta
	while _spawn_acc >= 1.0:
		_spawn_acc -= 1.0
		_spawn_car()
	turned_recent *= pow(0.985, delta)


## Whether any route calls at this terminal (an idle slip draws no traffic).
func has_service() -> bool:
	for rid in lanes.keys():
		if MapData.is_route(rid):
			return true
	return false


## A destination for a new car, weighted by how many people live there.
func _pick_destination() -> int:
	var total := 0.0
	var weights := {}
	for dest in lanes.keys():
		if not MapData.is_route(dest):
			continue
		weights[dest] = sim.map.towns[dest].population + 600.0
		total += weights[dest]
	var pick := sim.rng.randf() * total
	for rid in weights.keys():
		pick -= weights[rid]
		if pick <= 0.0:
			return rid
	return weights.keys()[0]


func _pick_lane(key: int, need := 1) -> Lane:
	return Lane.for_arrival(lanes.get(key, []), staging_lanes, slots_per_lane, need)


func _spawn_car() -> void:
	if not has_service():
		return
	var car := sim.make_vehicle()
	car.dest = _pick_destination()
	var lane := _pick_lane(car.dest, car.slots)
	if lane == null:
		lane = _shared_lane(car.dest, car.slots)
	if lane == null:
		turned_recent += 1.0
		car.queue_free()
		return
	lane.enroute += car.slots
	var path := _inbound[sim.rng.randi() % _inbound.size()].duplicate()
	path.append(_local(to_local(path[-1]).x, Layout.LOT_BACK + 2.4))
	path.append(_local(lane.v, Layout.LOT_BACK + 4.8))
	car.position = path[0]
	if path.size() > 1:
		var d := path[1] - path[0]
		car.rotation.y = atan2(d.x, d.z)
		car.straighten()
	car.drive(path, _on_car_reached_lot.bind(lane))


func _on_car_reached_lot(car: Vehicle, lane: Lane, changing_lanes := false) -> void:
	if not changing_lanes:
		car.lot_arrival = sim.minutes
	# A ferry can cast off while overflow traffic is still driving to this lot.
	if lane not in lanes.get(car.dest, []):
		for key in lanes:
			if lane in lanes[key]:
				var loader := next_loader(key)
				if loader == null or car.dest not in loader.serves_next_call_at(self):
					lane.enroute -= car.slots
					car.lane_v = lane.v
					_redirect_guest(car)
					return
				break
	var ahead := lane.queued_slots()
	car.leader = _car(lane.queue.back()) if not lane.queue.is_empty() else null
	lane.arrive(car.get_instance_id(), car.slots)
	car.lane_v = lane.v
	_park_in_queue(car, lane, ahead)


## Places some already-waiting cars so the lot isn't empty at the start.
func prefill() -> void:
	for rid in lanes.keys():
		if not MapData.is_route(rid):
			continue
		for lane: Lane in lanes[rid]:
			var want := sim.rng.randi_range(1, slots_per_lane - 2)
			var k := 0
			while k < want:
				var car := sim.make_vehicle()
				if k + car.slots > slots_per_lane:
					car.queue_free()
					break
				car.position = queue_position(lane.v, k, car)
				car.rotation.y = atan2(town.dock_dir.x, town.dock_dir.z)
				car.straighten()
				car.lane_v = lane.v
				car.dest = rid
				car.lot_arrival = sim.minutes - sim.rng.randf_range(0.0, 20.0)
				lane.enqueue(car.get_instance_id(), car.slots)
				k += car.slots


## The next car for a boat serving `serves` (town ids, her stops in order): from
## the lanes for her first stop first, so those cars park deepest and are first off.
## A lane whose front car she doesn't serve is blocked to her.
func board_next(serves: Array[int], fits: Callable) -> Vehicle:
	var eligible := func(id: int) -> bool:
		var car := instance_from_id(id) as Vehicle
		return car.dest in serves and fits.call(car)
	for dest in serves:
		if not lanes.has(dest):
			continue
		var best: Lane
		if work_stage == WorkStage.DRAINING and dest == lane_keys()[0]:
			best = Lane.for_boarding(staging_lanes, eligible)
		if best == null:
			best = Lane.for_boarding(lanes[dest], eligible)
		if best != null:
			return _dispatch(best)
	return null


## Whether a boat serving `serves` could still take a waiting car (`fits`).
func has_waiting(serves: Array[int], fits: Callable) -> bool:
	for dest in serves:
		for lane: Lane in lanes.get(dest, []):
			if not lane.queue.is_empty():
				var front := instance_from_id(lane.queue[0].vehicle_id) as Vehicle
				if front.dest in serves and fits.call(front):
					return true
	return false


func _dispatch(best: Lane) -> Vehicle:
	var car := instance_from_id(best.take_front()) as Vehicle
	_boarding_from[car.get_instance_id()] = best
	_close_up(best)
	avg_wait = lerpf(avg_wait, sim.minutes - car.lot_arrival, 0.1)
	served_today += 1
	return car


# --- Sharing lanes ------------------------------------------------------------------

## The boat that will next load the lanes for `dest` here: one alongside, then one
## coming in, then the soonest to sail here.
func next_loader(dest: int) -> Ferry:
	var best: Ferry
	var best_score := INF
	for f in sim.ferries:
		if not f.in_service() or dest not in f.serves_next_call_at(self):
			continue
		var score: float
		if f.state != Ferry.State.SAILING and f.here() == self:
			score = 0.0 if f.state == Ferry.State.LOADING else 1.0
		elif f.state == Ferry.State.SAILING and f.destination() == self:
			score = 2.0 + f.path_left() / 1.0e6
		else:
			score = 10.0 + f.minutes_until_departure_from(self)
		if score < best_score:
			best_score = score
			best = f
	return best


## A lane of another destination with room, when the next boat to load it also
## serves `dest` (the sharing rule).
func _shared_lane(dest: int, need: int) -> Lane:
	for key in lanes.keys():
		if key == dest or not MapData.is_route(key):
			continue
		var f := next_loader(key)
		if f == null or dest not in f.serves_next_call_at(self):
			continue
		var lane := _pick_lane(key, need)
		if lane != null:
			return lane
	return null


## After a boat leaves: cars queued in another destination's lane stay only if the
## next boat to load that lane serves them. Otherwise they move back to a lane of
## their own with room, or give up and go home.
func sort_overflow() -> void:
	for key in lanes.keys():
		for lane: Lane in lanes[key]:
			var loader := next_loader(key)
			var moved := false
			for waiting in lane.queue.duplicate():
				var car := instance_from_id(waiting.vehicle_id) as Vehicle
				if car.dest == key or car.dest < 0:
					continue
				if loader != null and car.dest in loader.serves_next_call_at(self):
					continue
				lane.queue.erase(waiting)
				moved = true
				_redirect_guest(car)
			if moved:
				_close_up(lane)


func _redirect_guest(car: Vehicle) -> void:
	car.leader = null
	var own := _pick_lane(car.dest, car.slots)
	if own != null:
		own.enroute += car.slots
		car.drive(_lot_path(car.lane_v, own.v), _on_car_reached_lot.bind(own, true))
	else:
		turned_recent += 1.0
		car.drive(_leave_path(car.lane_v), func(c: Vehicle): c.queue_free())


## Out of lane `from_v`, round by the exit lane and back in at the tail of `to_v`.
func _lot_path(from_v: float, to_v: float) -> PackedVector3Array:
	return PackedVector3Array([
		_local(from_v, Layout.LANE_HEAD + 6.0),
		_local(Layout.EXIT_V, Layout.LANE_HEAD + 6.0),
		_local(Layout.EXIT_V, Layout.LOT_BACK + 2.4),
		_local(to_v, Layout.LOT_BACK + 4.8),
	])


## Out of lane `from_v` and home along the exit lane.
func _leave_path(from_v: float) -> PackedVector3Array:
	var path := PackedVector3Array([
		_local(from_v, Layout.LANE_HEAD + 6.0),
		_local(Layout.EXIT_V, Layout.LANE_HEAD + 6.0),
		_local(Layout.EXIT_V, Layout.LOT_BACK + 1.5),
	])
	path.append_array(_outbound[sim.rng.randi() % _outbound.size()])
	return path


## Give the closing lanes a chance to drain. When their front vehicle is too
## large for the available deck slots, keep serving other lanes as usual.
func take_car(rid: int, fits := Callable()) -> Vehicle:
	var fits_id := Callable()
	if not fits.is_null():
		fits_id = func(id: int): return fits.call(instance_from_id(id))
	var best: Lane
	if work_stage == WorkStage.DRAINING and rid == lane_keys()[0]:
		best = Lane.for_boarding(staging_lanes, fits_id)
	if best == null:
		best = Lane.for_boarding(lanes[rid], fits_id)
	if best == null:
		return null
	return _dispatch(best)


func finish_boarding(car: Vehicle) -> void:
	_boarding_from.erase(car.get_instance_id())


## The way from `car`'s lane onto a boat at slip `i`.
func boarding_path(car: Vehicle, i: int) -> PackedVector3Array:
	var sv := town.slip_offset(i)
	# Approach from opposite sides of the lot in parallel before converging on
	# the boarding lane. Leave room at the curb and for unloading.
	var entrance := sv + (-4.5 if car.lane_v < sv - 3.0 else -0.6)
	var path := PackedVector3Array([
		_local(car.lane_v, Layout.LANE_HEAD + 6.0),
		_local(entrance, Layout.LOT_FRONT + 1.5),
		_local(entrance, SlipRamp.HINGE_U),
	])
	if slip_ramps[i]:
		# Up the span to its tip, a little above the ferry's deck (the apron slopes down onto it).
		var ramp := slip_ramps[i]
		path.append(to_global(ramp.crossing(-3.0)[1]))
	else:
		path.append(_local(sv - 3.0, Layout.PIER_END))
	return path


## The way off a boat at slip `i`, out of the lot and home.
func exit_path(i: int) -> PackedVector3Array:
	var sv := town.slip_offset(i)
	var path := PackedVector3Array()
	if slip_ramps[i]:
		var ramp := slip_ramps[i]
		var over := ramp.crossing(3.0)
		path.append(to_global(over[1]))
		path.append(to_global(over[0]))
	else:
		path.append(_local(sv + 3.0, Layout.PIER_END))
	path.append_array(PackedVector3Array([
		_local(sv + 3.0, Layout.LOT_FRONT + 1.5),
		_local(Layout.EXIT_V, Layout.LANE_HEAD + 6.0),
		_local(Layout.EXIT_V, Layout.LOT_BACK + 1.5),
	]))
	path.append_array(_outbound[sim.rng.randi() % _outbound.size()])
	return path


func queued_for(rid: int) -> int:
	var total := 0
	for lane: Lane in lanes[rid]:
		total += lane.queue.size()
	return total


func total_queued() -> int:
	var total := 0
	for key in lanes.keys():
		total += queued_for(key)
	return total


func capacity() -> int:
	var total := 0
	for rid in lanes.keys():
		total += lanes[rid].size() * slots_per_lane
	return total - staging_lanes.size() * slots_per_lane


func satisfaction() -> float:
	return clampf(96.0 - maxf(avg_wait - 18.0, 0.0) * 0.9 - turned_recent * 2.0, 15.0, 99.0)


## Returns [minutes until next departure, Ferry] across this terminal's routes.
func next_departure() -> Array:
	var best_min := INF
	var best_ferry: Ferry = null
	if sim == null:
		return [best_min, best_ferry]
	for f in sim.ferries:
		if not f.calls_at(self):
			continue
		var m := f.minutes_until_departure_from(self)
		if m < best_min:
			best_min = m
			best_ferry = f
	return [best_min, best_ferry]
