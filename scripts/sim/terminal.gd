class_name Terminal
extends Node3D
## One town's ferry terminal. Cars spawn in town, drive to the holding lot, queue
## in the lanes for their destination, and board a ferry that serves it.
## The lot's lanes divide among the destinations its boats serve from here. When a
## destination's lanes are full, its cars may queue in another destination's lane
## if the next boat to load that lane serves both; otherwise they are turned away. Arriving cars drive
## off the pier, out through the exit lane and back into town.
## The node's transform is the terminal frame (see Layout).

signal queue_changed
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
const RefitStage = TerminalRefit.Stage

const BUILD_MINUTES := 120.0
const ARRIVAL_MINUTES := 20.0
const DEPARTURE_MINUTES := 20.0
# Price of refitting a slip up to each size (by the size it becomes: medium, large).
const REFIT_PRICE := [0, 0, 8000, 20000]
const REFIT_ARRIVAL := TerminalRefit.ARRIVAL
const REFIT_WORK := TerminalRefit.WORK
const REFIT_DEPARTURE := TerminalRefit.DEPARTURE
const REFIT_HOLD := 320.0      # how far out boats for a closed slip hold off (m)
# New slips (stage 5), built by the same crane scow as a refit: one slip job at a
# time. They go along the shore beside the others (SlipSiteSurvey), dredged if need
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
const DREDGE_PRICE := 0.25      # $ per cubic metre (rounded up to $500, at least $1,000)
const DREDGE_RATE := 12000.0    # cubic metres an hour, added to the build
# Walk-on passengers wait outside the passenger terminal and board along the trestle walkway.
const PASSENGER_CAPACITY := 1000
const MAX_VISIBLE_PASSENGERS := 24
const WALK_V := -7.2  # lateral offset on the trestle's -v walkway (TRESTLE_V_WALK = -9.2)

const Lane = preload("res://scripts/sim/terminal_lane.gd")

## How far a driven road path may stray from the road's points every couple of
## metres: few enough points that Vehicle rounds the town's corners, enough that
## cars keep to the road's rise and fall.
const ROAD_TOLERANCE := 0.06

var passengers_served_today := 0
## Walk-on passengers waiting at the passenger terminal: {dest, arrival, variant, node}.
var passenger_queue: Array[Dictionary] = []


## A snapshot of the holding lot. Waiting counts vehicles; inbound counts reserved spaces.
class QueueSummary:
	class Destination:
		var town_id: int
		var lanes: int
		var sharing := 0

		func _init(id: int, lane_count: int) -> void:
			town_id = id
			lanes = lane_count

	var destinations: Array[Destination] = []
	var waiting := 0
	var has_newest := false
	var newest_waiting := 0
	var newest_inbound := 0


## How many berths existed when this terminal opened in the rebuilt region.
var original_slip_count := 0
var _queue_summary: QueueSummary
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

var _refit := TerminalRefit.new()
var refit_slip: int:
	get: return _refit.slip
var refit_stage: TerminalRefit.Stage:
	get: return _refit.stage
	set(value): _refit.stage = value
var refit_remaining: float:
	get: return _refit.remaining
	set(value): _refit.remaining = value
var refit_work: float:
	get: return _refit.work
var refit_new: bool:
	get: return _refit.new_slip
## Routes waiting to move to another working slip (route id -> slip index) once no
## boat on them is under way or alongside here (spread_routes).
var _assignments: RouteBerthAssignments
var _survey: SlipSiteSurvey
var site_survey: SlipSiteSurvey:
	get:
		if _survey == null:
			_survey = SlipSiteSurvey.new(sim, town)
		return _survey
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
var _pax_spawn_acc := 0.0


func _init() -> void:
	_refit.stage_changed.connect(refit_changed.emit)
	_refit.widen_slip.connect(_widen_slip)
	_refit.open_new_slip.connect(_open_slip)


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
	var sites := site_survey.sites(kind == TerminalUpgrade.Kind.TIE_UP)
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
	if u == null or u.blocked != "" or u.price != offer.price or u.build_minutes != offer.build_minutes or not sim.has_research(u.research) or sim.available_cash < u.price:
		return false
	sim.ledger.spend("purchases", u.price)
	match u.kind:
		TerminalUpgrade.Kind.LANE:
			_start_lane()
		TerminalUpgrade.Kind.SLIP, TerminalUpgrade.Kind.TIE_UP:
			_start_slip(u)
		TerminalUpgrade.Kind.REFIT, TerminalUpgrade.Kind.TIE_UP_REFIT:
			_refit.start(u.slip, REFIT_WORK, false)
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
		_queue_changed()
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


## Lays out a bought slip where `u` says (hidden and closed while it is built) and
## brings the crane scow in to build it.
func _start_slip(u: TerminalUpgrade) -> void:
	var index := place_purchased_slip(u)
	_refit.start(index, u.build_minutes - REFIT_ARRIVAL - REFIT_DEPARTURE, true)


## Rebuild the physical site from its surveyed offer without charging or starting the crane.
func place_purchased_slip(u: TerminalUpgrade) -> int:
	if u.dredge_m3 > 0.0:
		seabed_dredged.emit(site_survey.dredge(u.v, u.kind == TerminalUpgrade.Kind.SLIP))
	town.freeze_slip_offsets()
	var tie := u.kind == TerminalUpgrade.Kind.TIE_UP
	var slip := MapData.Slip.new(1, tie)
	slip.v = u.v
	slip.building = true
	town.slips.append(slip)
	slip_ramps.append(null)
	slip_guides.append(null)
	sim.slip_sites_changed.emit()
	return town.slips.size() - 1


## A bought slip is built: it takes its ramp and guides and comes into use, and
## the routes boats sail from here spread over the working slips.
func _open_slip(i: int) -> void:
	var slip := town.slips[i]
	slip.building = false
	var v := town.slip_offset(i)
	if sim.uses_transfer_spans and not slip.tie_up:
		slip_ramps[i] = SlipRamp.new(v)
		add_child(slip_ramps[i])
	if sim.uses_slip_guides and not slip.tie_up:
		slip_guides[i] = SlipGuides.new(v, transform)
		add_child(slip_guides[i])
		slip_guides[i].fit(MapData.Slip.LARGEST_BOAT[slip.size])
	slip_built.emit(i)
	if not slip.tie_up:
		spread_routes()


# --- Spreading routes over the slips ------------------------------------------------

func spread_routes() -> void:
	if _assignments == null:
		_assignments = RouteBerthAssignments.new(self)
	_assignments.plan()


## Puts route `rid` on working slip `to` now (see RouteBerthAssignments.move_now).
func move_route_now(rid: int, to: int) -> bool:
	if _assignments == null:
		_assignments = RouteBerthAssignments.new(self)
	return _assignments.move_now(rid, to)


## Whether slip `i` is closed for a refit (not a new slip whose crew is leaving).
func slip_shut(i: int) -> bool:
	return _refit.slip_shut(i)


## Whether tie-up slip `i` is closed for a refit (no boat may make for it).
func tie_up_closed(i: int) -> bool:
	return _refit.occupies(i)


## Whether the slip `rid` calls at here is closed for a refit.
func slip_closed(rid: int) -> bool:
	return refit_stage != RefitStage.NONE and _refit.occupies(town.slip_index(rid))


## How far through its current stage the refit is (0..1).
func refit_progress() -> float:
	return _refit.progress()


func _widen_slip(i: int) -> void:
	fit_slip(i, town.slips[i].size + 1)


## Apply the capacity to the harbour record and its physical contacts together.
func fit_slip(i: int, size: int) -> void:
	town.slips[i].size = size
	if slip_guides[i]:
		slip_guides[i].fit(MapData.Slip.LARGEST_BOAT[size])


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
	original_slip_count = isl.slips.size()
	name = isl.name + " Terminal"
	transform = isl.terminal_xform()
	flood_side = 1.0 if hash(isl.key if isl.key != "" else str(isl.id)) % 2 == 0 else -1.0
	for i in isl.slips.size():
		var ramp: SlipRamp = null
		if sim.uses_transfer_spans and not isl.slips[i].tie_up:
			ramp = SlipRamp.new(isl.slip_offset(i))
			add_child(ramp)
		slip_ramps.append(ramp)
		var g: SlipGuides = null
		# (A tie-up's dolphins are shared with its neighbours: WorldBuilder._build_tie_up.)
		if sim.uses_slip_guides and not isl.slips[i].tie_up:
			g = SlipGuides.new(isl.slip_offset(i), transform)
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
	_queue_changed()


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
	_redirect_overflow()
	_prune_unserved_passengers(dests)
	_queue_changed()


## The wing walls and dolphins of the slip `rid` calls at here (null if none).
func guides_for(rid: int) -> SlipGuides:
	return guides_at(town.slip_index(rid))


## Slip `i`'s wing walls and dolphins (null if none).
func guides_at(i: int) -> SlipGuides:
	return slip_guides[i] if i >= 0 and i < slip_guides.size() else null


## The preferred working berth, or the nearest compatible free one.
## The live arrival uses boat reservations; the timetable uses predicted occupancy.
func arrival_slip(preferred: int, hull_size: int, is_busy: Callable) -> int:
	if preferred < 0 or not slip_shut(preferred) and not is_busy.call(preferred):
		return preferred
	var best := -1
	for i in town.slips.size():
		var slip := town.slips[i]
		if i == preferred or slip.tie_up or slip.building or not slip.fits(hull_size) or slip_shut(i) or is_busy.call(i):
			continue
		if best < 0 or absf(town.slip_offset(i) - town.slip_offset(preferred)) < absf(town.slip_offset(best) - town.slip_offset(preferred)):
			best = i
	return best if best >= 0 else preferred


## The boat occupying this berth or arriving ahead of this ferry.
func slip_user(i: int, f: Ferry) -> Ferry:
	var occupied := sim.occupant(self, i, f)
	if occupied:
		return occupied
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
			_inbound.append(simplify(ticket_path, ROAD_TOLERANCE))
		var outbound := town.road_main_a.duplicate()
		outbound.append_array(b)
		_outbound.append(_keep_right(simplify(outbound, ROAD_TOLERANCE)))


## Douglas-Peucker: the fewest of `pts` (ends kept) that stay within `tol` of the rest.
static func simplify(pts: PackedVector3Array, tol: float) -> PackedVector3Array:
	if pts.size() < 3:
		return pts
	var keep := PackedByteArray()
	keep.resize(pts.size())
	keep[0] = 1
	keep[pts.size() - 1] = 1
	var stack: Array[Vector2i] = [Vector2i(0, pts.size() - 1)]
	while not stack.is_empty():
		var span: Vector2i = stack.pop_back()
		var a := pts[span.x]
		var ab := pts[span.y] - a
		var len2 := maxf(ab.length_squared(), 1e-9)
		var worst := -1
		var far := tol
		for i in range(span.x + 1, span.y):
			var t := clampf((pts[i] - a).dot(ab) / len2, 0.0, 1.0)
			var d := pts[i].distance_to(a + ab * t)
			if d > far:
				far = d
				worst = i
		if worst >= 0:
			keep[worst] = 1
			stack.append(Vector2i(span.x, worst))
			stack.append(Vector2i(worst, span.y))
	var out := PackedVector3Array()
	for i in pts.size():
		if keep[i]:
			out.append(pts[i])
	return out


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


## A point on the lot (Layout's lot coordinates, in the lot's raised, set-back frame).
func _local(v: float, u: float) -> Vector3:
	return to_global(town.lot_offset() * Vector3(v, Layout.LOT_Y, u))


func lot_point(v: float, u: float) -> Vector3:
	return _local(v, u)


## Down the trestle at `v` (terminal frame) from the lot's edge to the span's hinge,
## every few metres on the road's profile (reversed: back up it).
func _approach(v: float, reverse := false) -> PackedVector3Array:
	var pts := PackedVector3Array()
	var u0 := town.lot_front_u()
	var steps := maxi(1, ceili((Layout.RAMP_HINGE_U - u0) / 4.0))
	for k in range(1, steps + 1):
		var u := lerpf(u0, Layout.RAMP_HINGE_U, float(k) / steps)
		pts.append(to_global(Vector3(v, town.road_y(u), u)))
	if reverse:
		pts.reverse()
	return pts


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
	var dmin := Units.game_minutes(delta)
	if build_remaining > 0.0:
		_advance_construction(dmin)
	if refit_stage != RefitStage.NONE:
		_refit.advance(dmin, refit_stage == RefitStage.CLEARING and _refit_slip_clear())
	if _assignments != null and _assignments.has_moves():
		_assignments.apply_when_clear()
	_spawn_acc += sim.demand_rate(town) * dmin
	while _spawn_acc >= 1.0:
		_spawn_acc -= 1.0
		_spawn_car()
	_pax_spawn_acc += sim.passenger_demand_rate(town) * dmin
	while _pax_spawn_acc >= 1.0:
		_pax_spawn_acc -= 1.0
		_spawn_passenger()
	turned_recent *= pow(0.985, dmin)


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
		var dest_town := sim.map.towns[dest]
		weights[dest] = (
			(dest_town.population + 600.0) * sim.town_growth.destination_pull_multiplier(dest_town)
		)
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
	var car := sim.make_vehicle(null, sim.town_growth.commercial_truck_share(town))
	car.dest = _pick_destination()
	var lane := _pick_lane(car.dest, car.slots)
	if lane == null:
		lane = _shared_lane(car.dest, car.slots)
	if lane == null:
		turned_recent += 1.0
		car.queue_free()
		return
	lane.enroute += car.slots
	if lane == extra_lane:
		_queue_changed()
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
		car.lot_arrival = sim.abs_minutes()
	# A ferry can cast off while overflow traffic is still driving to this lot.
	if lane not in lanes.get(car.dest, []):
		for key in lanes:
			if lane in lanes[key]:
				var loader := next_loader(key)
				if loader == null or car.dest not in loader.serves_next_call_at(self):
					lane.enroute -= car.slots
					car.lane_v = lane.v
					_redirect_guest(car)
					_queue_changed()
					return
				break
	var ahead := lane.queued_slots()
	car.leader = _car(lane.queue.back()) if not lane.queue.is_empty() else null
	lane.arrive(car.get_instance_id(), car.slots)
	car.lane_v = lane.v
	_park_in_queue(car, lane, ahead)
	_queue_changed()


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
				car.lot_arrival = sim.abs_minutes() - sim.rng.randf_range(0.0, 20.0)
				lane.enqueue(car.get_instance_id(), car.slots)
				k += car.slots
	_prefill_passengers()
	_queue_changed()


func _passenger_door_pos() -> Vector3:
	return _local(town.lot_half_width + 6.5, -36.0)


func _waiting_spot(slot_index: int) -> Vector3:
	# Two orderly queue lines outside the passenger terminal porch, head closest to the pier.
	var col := slot_index % 2
	var row := (slot_index / 2) % 12
	var v := town.lot_half_width + 2.2 + col * 1.45
	var u := -26.0 - row * 1.65 - (0.35 if col == 1 else 0.0)
	return _local(v, u)


func _close_up_passengers() -> void:
	var face := atan2(town.dock_dir.x, town.dock_dir.z)
	var vis := 0
	for p in passenger_queue:
		var node: Passenger = p["node"]
		if node != null and is_instance_valid(node):
			var spot := _waiting_spot(vis)
			if node.position.distance_squared_to(spot) > 0.25:
				node.walk(PackedVector3Array([spot]), Callable(), 0.0, face)
			vis += 1


func _visible_passenger_count() -> int:
	var n := 0
	for p in passenger_queue:
		if p["node"] != null and is_instance_valid(p["node"]):
			n += 1
	return n


func _spawn_passenger() -> void:
	if not has_service():
		return
	if passenger_queue.size() >= PASSENGER_CAPACITY:
		turned_recent += 0.5
		return
	var dest := _pick_destination()
	var variant := sim.rng.randi() % Passenger.VARIANT_COUNT
	var node: Passenger = null
	if _visible_passenger_count() < MAX_VISIBLE_PASSENGERS:
		node = sim.make_passenger(variant)
		var door := _passenger_door_pos()
		var spot := _waiting_spot(_visible_passenger_count())
		var face := atan2(town.dock_dir.x, town.dock_dir.z)
		node.position = door
		node.walk(PackedVector3Array([spot]), Callable(), 0.0, face)
	(
		passenger_queue
		. append(
			{
				"dest": dest,
				"arrival": sim.abs_minutes(),
				"variant": variant,
				"node": node,
			}
		)
	)


func _prefill_passengers() -> void:
	if not has_service():
		return
	var count := sim.rng.randi_range(4, 10)
	var face := atan2(town.dock_dir.x, town.dock_dir.z)
	for i in count:
		var dest := _pick_destination()
		var variant := sim.rng.randi() % Passenger.VARIANT_COUNT
		var node := sim.make_passenger(variant)
		node.stand_at(_waiting_spot(i), face)
		(
			passenger_queue
			. append(
				{
					"dest": dest,
					"arrival": sim.abs_minutes() - sim.rng.randf_range(0.0, 15.0),
					"variant": variant,
					"node": node,
				}
			)
		)


func _prune_unserved_passengers(dests: Array[int]) -> void:
	var door := _passenger_door_pos()
	for i in range(passenger_queue.size() - 1, -1, -1):
		var p := passenger_queue[i]
		if p["dest"] not in dests:
			var node: Passenger = p["node"]
			if node != null and is_instance_valid(node):
				node.walk(PackedVector3Array([door]), func(w: Passenger): w.queue_free())
			passenger_queue.remove_at(i)


## Boards the next walk-on passenger heading to one of `serves`. Returns {} if none wait.
func board_next_passenger(serves: Array[int]) -> Dictionary:
	for i in passenger_queue.size():
		if passenger_queue[i]["dest"] in serves:
			var pax := passenger_queue[i]
			passenger_queue.remove_at(i)
			avg_wait = lerpf(avg_wait, maxf(0.0, sim.abs_minutes() - float(pax["arrival"])), 0.05)
			passengers_served_today += 1
			_close_up_passengers()
			return pax
	return {}


func has_waiting_passengers(serves: Array[int]) -> bool:
	for p in passenger_queue:
		if p["dest"] in serves:
			return true
	return false


func passengers_queued() -> int:
	return passenger_queue.size()


## Walk-on boarding path from outside the passenger terminal down the trestle walkway onto slip `i`.
func passenger_boarding_path(i: int, lateral_jitter := 0.0) -> PackedVector3Array:
	var sv := town.slip_offset(i)
	var walk_v := sv + WALK_V + lateral_jitter
	var path := PackedVector3Array(
		[
			_local(town.lot_half_width + 2.2 + lateral_jitter, Layout.LOT_FRONT + 1.5),
			_local(walk_v, Layout.LOT_FRONT + 1.5),
		]
	)
	path.append_array(_approach(walk_v))
	if slip_ramps[i]:
		var ramp := slip_ramps[i]
		path.append(to_global(ramp.crossing(-5.0 + clampf(lateral_jitter, -0.6, 0.6))[1]))
	else:
		path.append(to_global(Vector3(sv - 4.8 + lateral_jitter, Layout.LOT_Y, Layout.PIER_END)))
	return path


## Walk-on exit path off slip `i` up the trestle walkway into the passenger terminal.
func passenger_exit_path(i: int) -> PackedVector3Array:
	var sv := town.slip_offset(i)
	var walk_v := sv + WALK_V
	var path := PackedVector3Array()
	if slip_ramps[i]:
		var ramp := slip_ramps[i]
		var over := ramp.crossing(-5.0)
		path.append(to_global(over[1]))
		path.append(to_global(over[0]))
	else:
		path.append(to_global(Vector3(sv - 4.8, Layout.LOT_Y, Layout.PIER_END)))
	path.append_array(_approach(walk_v, true))
	(
		path
		. append_array(
			PackedVector3Array(
				[
					_local(walk_v, Layout.LOT_FRONT + 1.5),
					_local(town.lot_half_width + 2.0, Layout.LOT_FRONT + 1.5),
					_passenger_door_pos(),
				]
			)
		)
	)
	return path


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
	avg_wait = lerpf(avg_wait, sim.abs_minutes() - car.lot_arrival, 0.1)
	served_today += 1
	_queue_changed()
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
	if _redirect_overflow():
		_queue_changed()


func _redirect_overflow() -> bool:
	var changed := false
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
				changed = true
	return changed


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


func boarding_lane_for(car: Vehicle) -> Lane:
	return _boarding_from.get(car.get_instance_id())


func lane_at_offset(offset: float) -> Lane:
	for group in lanes.values():
		for lane: Lane in group:
			if is_equal_approx(lane.v, offset):
				return lane
	return null


## Restore an existing dispatch. Traffic counters and wait times already include it.
func resume_boarding(car: Vehicle, lane: Lane) -> void:
	_boarding_from[car.get_instance_id()] = lane
	car.lane_v = lane.v


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
	])
	path.append_array(_approach(entrance))
	if slip_ramps[i]:
		# Up the span to its tip, a little above the ferry's deck (the apron slopes down onto it).
		var ramp := slip_ramps[i]
		path.append(to_global(ramp.crossing(-3.0)[1]))
	else:
		path.append(to_global(Vector3(sv - 3.0, Layout.LOT_Y, Layout.PIER_END)))
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
		path.append(to_global(Vector3(sv + 3.0, Layout.LOT_Y, Layout.PIER_END)))
	path.append_array(_approach(sv + 3.0, true))
	path.append_array(PackedVector3Array([
		_local(sv + 3.0, Layout.LOT_FRONT + 1.5),
		_local(Layout.EXIT_V, Layout.LANE_HEAD + 6.0),
		_local(Layout.EXIT_V, Layout.LOT_BACK + 1.5),
	]))
	path.append_array(_outbound[sim.rng.randi() % _outbound.size()])
	return path


func _queue_changed() -> void:
	_queue_summary = null
	queue_changed.emit()


## Read-only queue data for inspectors. Build it only when observed after a change.
func queue_summary() -> QueueSummary:
	if _queue_summary:
		return _queue_summary
	var summary := QueueSummary.new()
	summary.waiting = total_queued()
	for key: int in lanes:
		if not MapData.is_route(key):
			continue
		var row := QueueSummary.Destination.new(key, lanes[key].size())
		for lane: Lane in lanes[key]:
			for waiting in lane.queue:
				if _car(waiting).dest != key:
					row.sharing += 1
		summary.destinations.append(row)
	if extra_lane:
		summary.has_newest = true
		summary.newest_waiting = extra_lane.queue.size()
		summary.newest_inbound = extra_lane.enroute
	_queue_summary = summary
	return summary


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
	var fare_effect := 0.0
	if sim != null:
		var v_ratio := sim.avg_vehicle_fare_at(town) / CompanyLedger.DEFAULT_VEHICLE_FARE
		var p_ratio := sim.avg_passenger_fare_at(town) / CompanyLedger.DEFAULT_PASSENGER_FARE
		var avg_ratio := (v_ratio + p_ratio) * 0.5
		if avg_ratio > 1.1:
			fare_effect = -(avg_ratio - 1.1) * 14.0
		elif avg_ratio < 1.0:
			fare_effect = (1.0 - avg_ratio) * 5.0
	return clampf(
		96.0 - maxf(avg_wait - 18.0, 0.0) * 0.9 - turned_recent * 2.0 + fare_effect, 15.0, 99.0
	)


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
