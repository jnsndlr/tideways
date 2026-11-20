class_name Terminal
extends Node3D
## One island's ferry terminal. Cars spawn in town, drive to the holding lot, queue
## in per-route lanes, and board when their ferry is loading. Arriving cars drive
## off the pier, out through the exit lane and back into town.
## The node's transform is the terminal frame (see Layout).

signal extension_changed

enum WorkStage { IDLE, DRAINING, ARRIVING, PAVING, LEAVING, OPEN }

const BUILD_MINUTES := 120.0
const ARRIVAL_MINUTES := 20.0
const DEPARTURE_MINUTES := 20.0

## A holding lane reserves room for vehicles still driving in as well as those queued.
class Lane:
	var v: float
	var queue: Array[Vehicle] = []
	var enroute := 0

	func _init(offset: float) -> void:
		v = offset

	func queued_slots() -> int:
		var count := 0
		for vehicle in queue:
			count += vehicle.slots
		return count


var sim: Simulation
var island: MapData.Island
var lanes := {}        # route id -> Array[Lane]
var slip_v := {}       # route id -> lateral offset of that route's slip
var ramps := {}        # route id -> SlipRamp (none with the classic slip)
var work_stage := WorkStage.IDLE
var staging_lanes: Array[Lane] = []
# Cars dispatched from the terminal may still be driving through their old lane.
var _boarding_from: Dictionary[int, Lane] = {}
var build_remaining := 0.0
var extra_lane: Lane

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
	if island.slips.is_empty() or island.construction_staging_lanes not in [1, 2]:
		return false
	var route_lanes: Array = lanes.get(island.slips[0], [])
	var count := island.construction_staging_lanes
	return route_lanes.size() > count and route_lanes[count - 1].v <= -Layout.EXIT_CLEAR


func buy_holding_lane() -> bool:
	if island.lane_extension_price <= 0 or work_stage != WorkStage.IDLE or not can_stage_construction():
		return false
	if sim.available_cash < island.lane_extension_price:
		return false
	sim.ledger.spend("purchases", island.lane_extension_price)
	for i in island.construction_staging_lanes:
		staging_lanes.append(lanes[island.slips[0]][i])
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
		lanes[island.slips[0]].append(extra_lane)
		staging_lanes.clear()
		_set_work_stage(WorkStage.OPEN)
	elif build_remaining <= DEPARTURE_MINUTES and work_stage != WorkStage.LEAVING:
		_set_work_stage(WorkStage.LEAVING)
	elif build_remaining <= BUILD_MINUTES - ARRIVAL_MINUTES and work_stage == WorkStage.ARRIVING:
		_set_work_stage(WorkStage.PAVING)


func extension_offset() -> float:
	return -island.lot_half_width - Layout.LANE_WIDTH * 0.5


func setup(s: Simulation, isl: MapData.Island) -> void:
	sim = s
	island = isl
	name = isl.name + " Terminal"
	transform = isl.terminal_xform()
	var lane_sets := Layout.lane_positions(isl.lot_half_width, isl.slips.size())
	for i in isl.slips.size():
		var rid := isl.slips[i]
		slip_v[rid] = isl.slip_offset(i)
		if SlipRamp.available():
			var ramp := SlipRamp.new(slip_v[rid])
			add_child(ramp)
			ramps[rid] = ramp
		var arr: Array[Lane] = []
		for v in lane_sets[i]:
			arr.append(Lane.new(v))
		lanes[rid] = arr
	_build_road_paths()


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


func _local(v: float, u: float) -> Vector3:
	return to_global(Vector3(v, Layout.LOT_Y, u))


## Where `car` waits with `ahead` slots taken in front of it: the middle of its slots,
## shifted for a rig (whose tractor is ahead of its middle).
func queue_position(v: float, ahead: int, car: Vehicle) -> Vector3:
	var mid := Layout.LANE_HEAD - (ahead + (car.slots - 1) * 0.5) * Layout.SLOT
	return _local(v, mid - car.center_offset)


func _park_in_queue(car: Vehicle, lane: Lane, ahead: int) -> void:
	car.park_in_lane(queue_position(lane.v, ahead, car), atan2(island.dock_dir.x, island.dock_dir.z))


## Moves each car in `lane` up to its place in the queue.
func _close_up(lane: Lane) -> void:
	var k := 0
	var ahead: Vehicle = null
	for c: Vehicle in lane.queue:
		_park_in_queue(c, lane, k)
		c.leader = ahead
		ahead = c
		k += c.slots


func _process(delta: float) -> void:
	if build_remaining > 0.0:
		_advance_construction(delta)
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


func _pick_route() -> int:
	var total := 0.0
	var weights := {}
	for rid in lanes.keys():
		if not MapData.is_route(rid):
			continue
		var r: MapData.Route = sim.map.routes[rid]
		var other := sim.map.islands[r.b if r.a == island.id else r.a]
		weights[rid] = other.population + 600.0
		total += weights[rid]
	var pick := sim.rng.randf() * total
	for rid in weights.keys():
		pick -= weights[rid]
		if pick <= 0.0:
			return rid
	return weights.keys()[0]


func _pick_lane(rid: int, need := 1) -> Lane:
	var best: Lane
	var best_count := slots_per_lane - need + 1
	for lane: Lane in lanes[rid]:
		if lane in staging_lanes:
			continue
		var count: int = lane.queued_slots() + lane.enroute
		if count < best_count:
			best_count = count
			best = lane
	return best


func _spawn_car() -> void:
	if not has_service():
		return
	var car := sim.make_vehicle()
	var lane := _pick_lane(_pick_route(), car.slots)
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


func _on_car_reached_lot(car: Vehicle, lane: Lane) -> void:
	lane.enroute -= car.slots
	var queue: Array[Vehicle] = lane.queue
	var ahead := lane.queued_slots()
	car.leader = queue.back() if not queue.is_empty() else null
	queue.append(car)
	car.lane_v = lane.v
	car.lot_arrival = sim.minutes
	_park_in_queue(car, lane, ahead)


## Places some already-waiting cars so the lot isn't empty at the start.
func prefill() -> void:
	for rid in lanes.keys():
		if not MapData.is_route(rid):
			continue
		for lane: Lane in lanes[rid]:
			var queue: Array[Vehicle] = lane.queue
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
				car.lot_arrival = sim.minutes - sim.rng.randf_range(0.0, 20.0)
				queue.append(car)
				k += car.slots


func _longest_fitting_lane(candidates: Array, fits: Callable) -> Lane:
	var best: Lane
	for lane: Lane in candidates:
		if lane.queue.size() > 0 and (best == null or lane.queue.size() > best.queue.size()):
			if fits.is_null() or fits.call(lane.queue[0]):
				best = lane
	return best


## Give the closing lanes a chance to drain. When their front vehicle is too
## large for the available deck slots, keep serving other lanes as usual.
func take_car(rid: int, fits := Callable()) -> Vehicle:
	var best: Lane
	if work_stage == WorkStage.DRAINING and rid == island.slips[0]:
		best = _longest_fitting_lane(staging_lanes, fits)
	if best == null:
		best = _longest_fitting_lane(lanes[rid], fits)
	if best == null:
		return null
	var queue: Array[Vehicle] = best.queue
	var car: Vehicle = queue.pop_front()
	_boarding_from[car.get_instance_id()] = best
	_close_up(best)
	avg_wait = lerpf(avg_wait, sim.minutes - car.lot_arrival, 0.1)
	served_today += 1
	return car


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
		_local(entrance, SlipRamp.HINGE_U),
	])
	if ramps.has(rid):
		# Up the span to its tip, a little above the ferry's deck (the apron slopes down onto it).
		var ramp: SlipRamp = ramps[rid]
		path.append(to_global(ramp.crossing(-3.0)[1]))
	else:
		path.append(_local(sv - 3.0, Layout.PIER_END))
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
	for rid in lanes.keys():
		total += queued_for(rid)
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
		if f.term_a != self and f.term_b != self:
			continue
		var m := f.minutes_until_departure_from(self)
		if m < best_min:
			best_min = m
			best_ferry = f
	return [best_min, best_ferry]
