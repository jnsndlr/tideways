class_name Terminal
extends Node3D
## One island's ferry terminal. Cars spawn in town, drive to the holding lot, queue
## in the lanes for their destination, and board a ferry that serves it.
## The lot's lanes divide among the destinations its boats serve from here. When a
## destination's lanes are full, its cars may queue in another destination's lane
## if the next boat to load that lane serves both; otherwise they are turned away. Arriving cars drive
## off the pier, out through the exit lane and back into town.
## The node's transform is the terminal frame (see Layout).

signal extension_changed
signal refit_changed

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

const Lane = preload("res://scripts/sim/terminal_lane.gd")

var sim: Simulation
var island: MapData.Island
var lanes := {}        # destination island id -> Array[Lane] (MapData.NO_ROUTE when idle)
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
	if island.slips.is_empty() or island.construction_staging_lanes not in [1, 2]:
		return false
	var route_lanes: Array = lanes.get(lane_keys()[0], [])
	var count := island.construction_staging_lanes
	return route_lanes.size() > count and route_lanes[count - 1].v <= -Layout.EXIT_CLEAR


func buy_holding_lane() -> bool:
	var ready := work_stage == WorkStage.IDLE or work_stage == WorkStage.OPEN and not site_lanes.is_empty()
	if island.lane_extension_price <= 0 or not ready or not can_stage_construction():
		return false
	if sim.available_cash < island.lane_extension_price:
		return false
	sim.ledger.spend("purchases", island.lane_extension_price)
	if site_lanes.is_empty():
		for i in island.construction_staging_lanes:
			staging_lanes.append(lanes[lane_keys()[0]][i])
	build_remaining = BUILD_MINUTES
	_set_work_stage(WorkStage.DRAINING)
	return true


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
	var slip := island.slips[i]
	if slip.size >= MapData.Slip.LARGEST_BOAT.size() - 1:
		return 0
	return REFIT_PRICE[slip.size + 1]


## The working slip (or with `tie_up`, the tie-up slip) to offer a refit for: the
## smallest one that can still grow (-1 if none, or one is already being refitted).
func next_refit(tie_up := false) -> int:
	if refit_stage != RefitStage.NONE:
		return -1
	var best := -1
	for i in island.slips.size():
		if island.slips[i].tie_up != tie_up:
			continue
		if refit_price(i) > 0 and (best < 0 or island.slips[i].size < island.slips[best].size):
			best = i
	return best


func buy_refit(i: int) -> bool:
	var price := refit_price(i)
	if price <= 0 or refit_stage != RefitStage.NONE or sim.available_cash < price:
		return false
	sim.ledger.spend("purchases", price)
	refit_slip = i
	refit_remaining = REFIT_ARRIVAL + REFIT_WORK + REFIT_DEPARTURE
	_set_refit_stage(RefitStage.CLEARING)
	return true


## Whether tie-up slip `i` is closed for a refit (no boat may make for it).
func tie_up_closed(i: int) -> bool:
	return refit_stage != RefitStage.NONE and i == refit_slip


## Whether the slip `rid` calls at here is closed for a refit.
func slip_closed(rid: int) -> bool:
	return refit_stage != RefitStage.NONE and island.slip_index(rid) == refit_slip


## How far through its current stage the refit is (0..1).
func refit_progress() -> float:
	match refit_stage:
		RefitStage.ARRIVING:
			return clampf((REFIT_ARRIVAL + REFIT_WORK + REFIT_DEPARTURE - refit_remaining) / REFIT_ARRIVAL, 0.0, 1.0)
		RefitStage.WORKING:
			return clampf((REFIT_WORK + REFIT_DEPARTURE - refit_remaining) / REFIT_WORK, 0.0, 1.0)
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
		_set_refit_stage(RefitStage.NONE)
	elif refit_remaining <= REFIT_DEPARTURE and refit_stage != RefitStage.LEAVING:
		# The work is done: the slip takes the next size up, with its new guides.
		var slip := island.slips[refit_slip]
		slip.size += 1
		if slip_guides[refit_slip]:
			slip_guides[refit_slip].fit(MapData.Slip.LARGEST_BOAT[slip.size])
		_set_refit_stage(RefitStage.LEAVING)
	elif refit_remaining <= REFIT_WORK + REFIT_DEPARTURE and refit_stage == RefitStage.ARRIVING:
		_set_refit_stage(RefitStage.WORKING)


## No boat lies at the slip being refitted, and none is coming in under the closure
## (inside REFIT_HOLD when it closed, so let finish her call).
func _refit_slip_clear() -> bool:
	if island.slips[refit_slip].tie_up:
		# A tie-up: no boat lies there or is on her way in or out.
		for f in sim.ferries:
			if f.berth != Ferry.Berth.WORKING and f.here() == self and f.tie_up == refit_slip:
				return false
		return true
	for f in sim.ferries:
		if f.berth != Ferry.Berth.WORKING or island.slip_index(f.route.id) != refit_slip:
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
	return -island.lot_half_width - Layout.LANE_WIDTH * 0.5


func setup(s: Simulation, isl: MapData.Island) -> void:
	sim = s
	island = isl
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
		if SlipGuides.available():
			g = SlipGuides.new(isl.slip_offset(i), transform, s.terrain)
			add_child(g)
			g.fit(MapData.Slip.LARGEST_BOAT[isl.slips[i].size])
		slip_guides.append(g)
		for rid in isl.slips[i].routes:
			slip_v[rid] = isl.slip_offset(i)
			if ramp:
				ramps[rid] = ramp
	_build_road_paths()


## Divides the lot's lanes among `dests` (island ids, in lot order), once the
## boats and their schedules are known.
func build_lanes(dests: Array[int]) -> void:
	var isl := island
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


## The wing walls and dolphins of the slip `rid` calls at here (null if none).
func guides_for(rid: int) -> SlipGuides:
	var i := island.slip_index(rid)
	return slip_guides[i] if i >= 0 else null


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
	var to_lot := island.road_main_a.duplicate()
	to_lot.reverse()
	var branches: Array[PackedVector3Array] = []
	if island.road_main_b.size() > 1:
		branches.append(island.road_main_b)
	branches.append_array(island.road_cross)
	if branches.is_empty():
		branches.append(PackedVector3Array([island.road_main_a[island.road_main_a.size() - 1]]))
	for b in branches:
		var inbound := b.duplicate()
		inbound.reverse()
		inbound.append_array(to_lot)
		_inbound.append(_keep_right(inbound))
		var outbound := island.road_main_a.duplicate()
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


## A point on the lot (Layout's lot coordinates, in the lot's raised, set-back frame).
func _local(v: float, u: float) -> Vector3:
	return to_global(island.lot_offset() * Vector3(v, Layout.LOT_Y, u))


func lot_point(v: float, u: float) -> Vector3:
	return _local(v, u)


## Down the trestle at `v` (terminal frame) from the lot's edge to the span's hinge,
## every few metres on the road's profile (reversed: back up it).
func _approach(v: float, reverse := false) -> PackedVector3Array:
	var pts := PackedVector3Array()
	var u0 := island.lot_front_u()
	var steps := maxi(1, ceili((SlipRamp.HINGE_U - u0) / 4.0))
	for k in range(1, steps + 1):
		var u := lerpf(u0, SlipRamp.HINGE_U, float(k) / steps)
		pts.append(to_global(Vector3(v, island.road_y(u), u)))
	if reverse:
		pts.reverse()
	return pts


## Where `car` waits with `ahead` slots taken in front of it: the middle of its slots,
## shifted for a rig (whose tractor is ahead of its middle).
func queue_position(v: float, ahead: int, car: Vehicle) -> Vector3:
	var mid := Layout.LANE_HEAD - (ahead + (car.slots - 1) * 0.5) * Layout.SLOT
	return _local(v, mid - car.center_offset)


func _park_in_queue(car: Vehicle, lane: Lane, ahead: int) -> void:
	car.park_in_lane(queue_position(lane.v, ahead, car), atan2(island.dock_dir.x, island.dock_dir.z))


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
	_spawn_acc += sim.demand_rate(island) * delta
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
		weights[dest] = sim.map.islands[dest].population + 600.0
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
	path.append(_local(-Layout.EXIT_V, Layout.LOT_BACK + 2.4))
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
				car.rotation.y = atan2(island.dock_dir.x, island.dock_dir.z)
				car.straighten()
				car.lane_v = lane.v
				car.dest = rid
				car.lot_arrival = sim.minutes - sim.rng.randf_range(0.0, 20.0)
				lane.enqueue(car.get_instance_id(), car.slots)
				k += car.slots


## The next car for a boat serving `serves` (island ids, her stops in order): from
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


func boarding_path(car: Vehicle, rid: int) -> PackedVector3Array:
	var sv: float = slip_v[rid]
	# Approach from opposite sides of the lot in parallel before converging on
	# the boarding lane. Leave room at the curb and for unloading.
	var entrance := sv + (-4.5 if car.lane_v < sv - 3.0 else -0.6)
	var path := PackedVector3Array([
		_local(car.lane_v, Layout.LANE_HEAD + 6.0),
		_local(entrance, Layout.LOT_FRONT + 1.5),
	])
	path.append_array(_approach(entrance))
	if ramps.has(rid):
		# Up the span to its tip, a little above the ferry's deck (the apron slopes down onto it).
		var ramp: SlipRamp = ramps[rid]
		path.append(to_global(ramp.crossing(-3.0)[1]))
	else:
		path.append(to_global(Vector3(sv - 3.0, Layout.LOT_Y, Layout.PIER_END)))
	return path


func exit_path(rid: int) -> PackedVector3Array:
	var sv: float = slip_v[rid]
	var path := PackedVector3Array()
	if ramps.has(rid):
		var ramp: SlipRamp = ramps[rid]
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
