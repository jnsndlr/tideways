class_name TerminalHoldingSnapshot
extends RefCounted
## A terminal's holding lot, walk-on queue and lane construction job.
## Rebuild the same region and service before restoring. The company owns the
## clock and ledger. Ferry deck, departing road traffic and slips are separate.

var _lanes := {}
var _vehicles: Array[Vehicle] = []
var _moving := {}
var _paved: Array[float] = []
var _passengers: Array[Dictionary] = []
var _remaining_sites: Array[float] = []
var _stage: Terminal.WorkStage
var _staging: Array[TerminalLane] = []


static func capture(term: Terminal) -> Dictionary:
	var groups := {}
	var motions: Array[Dictionary] = []
	for dest: int in term.lanes:
		var rows := []
		for lane: TerminalLane in term.lanes[dest]:
			var cars := []
			for waiting in lane.queue:
				var car := instance_from_id(waiting.vehicle_id) as Vehicle
				if car == null or car.dest < 0:
					return {}
				var record := _vehicle_record(car, term)
				if not car.path.is_empty():
					_save_motion(record, car, motions)
					record.follows_previous = (
						is_instance_valid(car.leader) and car.leader.is_processing()
					)
				cars.append(record)
			var inbound := []
			var reserved := 0
			for id: int in lane.approaching:
				var car := instance_from_id(id) as Vehicle
				if car == null or car.path.is_empty() or car.dest < 0:
					return {}
				var record := _vehicle_record(car, term)
				_save_motion(record, car, motions)
				record.transfer = lane.approaching[id]
				record.source_offset = car.lane_v
				inbound.append(record)
				reserved += car.slots
			if reserved != lane.enroute:
				return {}
			rows.append({"offset": lane.v, "vehicles": cars, "approaching": inbound})
		groups[_key(term, dest)] = rows
	# Vehicles evaluate following distance in scene order, even across lane groups.
	motions.sort_custom(func(a: Dictionary, b: Dictionary): return a.order < b.order)
	for i in motions.size():
		motions[i].order = i
	var passengers := []
	for pax in term.passenger_queue:
		var node: Passenger = pax.node
		if node != null and not node.path.is_empty():
			return {}
		passengers.append(
			{
				"destination": _key(term, pax.dest),
				"variant": pax.variant,
				"arrival": pax.arrival,
				"visible": node != null
			}
		)
	return {
		"version": 2,
		"seed": str(term.sim.map.map_seed),
		"town": term.town.key,
		"slots_per_lane": term.slots_per_lane,
		"lanes": groups,
		"paved": term.paved.duplicate(),
		"stage": Terminal.WorkStage.keys()[term.work_stage],
		"staging": term.staging_lanes.map(func(lane: TerminalLane): return lane.v),
		"remaining": term.build_remaining,
		"passengers": passengers,
		"average_wait": term.avg_wait,
		"turned_recent": term.turned_recent,
		"served": term.served_today,
		"passengers_served": term.passengers_served_today,
		"vehicle_demand": term._spawn_acc,
		"passenger_demand": term._pax_spawn_acc
	}


static func _vehicle_record(car: Vehicle, term: Terminal) -> Dictionary:
	var record := VehiclePartsSnapshot.capture(car)
	record.destination = _key(term, car.dest)
	record.arrival = car.lot_arrival
	return record


static func _save_motion(record: Dictionary, car: Vehicle, motions: Array[Dictionary]) -> void:
	record.motion = VehicleMotionSnapshot.capture(car)
	record.motion.order = car.get_index()
	motions.append(record.motion)


static func _key(term: Terminal, dest: int) -> String:
	return "" if dest == MapData.NO_ROUTE else term.sim.map.towns[dest].key


## Stage and validate the entire lot before replacing freshly prefilled queues.
static func restore(record: Variant, term: Terminal, make_vehicle: Callable) -> bool:
	if not _valid_header(record, term) or not make_vehicle.is_valid():
		return false
	if term.work_stage != Terminal.WorkStage.IDLE or not term._boarding_from.is_empty():
		return false
	if capture(term).is_empty():
		return false
	var staged := TerminalHoldingSnapshot.new()
	if not staged._prepare(record, term, make_vehicle):
		return false
	staged._install(record, term)
	return true


static func _valid_header(r: Variant, term: Terminal) -> bool:
	if not r is Dictionary or not _integer(r.get("version")) or int(r.version) not in [1, 2]:
		return false
	if (
		r.get("seed") != str(term.sim.map.map_seed)
		or r.get("town") != term.town.key
		or not _integer(r.get("slots_per_lane"))
		or r.slots_per_lane != term.slots_per_lane
	):
		return false
	for key in ["average_wait", "turned_recent", "vehicle_demand", "passenger_demand", "remaining"]:
		if not _number(r.get(key)) or r[key] < 0:
			return false
	return (
		_integer(r.get("served"))
		and r.served >= 0
		and _integer(r.get("passengers_served"))
		and r.passengers_served >= 0
		# JSON may round the highest subunit accumulator up to exactly one.
		and r.vehicle_demand <= 1
		and r.passenger_demand <= 1
		and r.get("stage") is String
		and Terminal.WorkStage.has(r.stage)
		and r.get("lanes") is Dictionary
		and r.lanes.size() == term.lanes.size()
		and r.get("staging") is Array
		and r.get("paved") is Array
		and r.get("passengers") is Array
	)


func _prepare(r: Dictionary, term: Terminal, make_vehicle: Callable) -> bool:
	var offsets: Array[float] = []
	for dest: int in term.lanes:
		for lane: TerminalLane in term.lanes[dest]:
			offsets.append(lane.v)
	if not _read_paved(r.paved, term, offsets):
		return false
	for dest: int in term.lanes:
		var rows = r.lanes.get(_key(term, dest))
		if not rows is Array:
			return false
		var lanes: Array[TerminalLane] = []
		for row in rows:
			if not row is Dictionary or not _number(row.get("offset")):
				return false
			var index := offsets.find_custom(func(v: float): return is_equal_approx(v, row.offset))
			if index == -1:
				return false
			var lane := TerminalLane.new(offsets.pop_at(index))
			var approaching = [] if r.version == 1 else row.get("approaching")
			if not (
				_read_cars(row.get("vehicles"), lane, term, make_vehicle, false)
				and _read_cars(approaching, lane, term, make_vehicle, true)
			):
				return false
			lanes.append(lane)
		_lanes[dest] = lanes
	_stage = Terminal.WorkStage[r.stage]
	return (
		offsets.is_empty()
		and _complete_motion_order()
		and _valid_job(r, term)
		and _read_passengers(r.passengers, term)
	)


func _complete_motion_order() -> bool:
	for order in _moving.size():
		if not _moving.has(order):
			return false
	return true


func _read_paved(paved: Array, term: Terminal, offsets: Array[float]) -> bool:
	_remaining_sites = term.site_lanes.duplicate()
	if not paved.is_empty() and term.town.lane_extension_price <= 0:
		return false
	var available := _remaining_sites.size()
	if available == 0 and term.town.construction_staging_lanes in [1, 2]:
		available = 1
	if paved.size() > available:
		return false
	for v in paved:
		var expected := (
			term.extension_offset()
			if _remaining_sites.is_empty()
			else float(_remaining_sites.pop_front())
		)
		if not _number(v) or not is_equal_approx(v, expected) or offsets.has(expected):
			return false
		offsets.append(expected)
		_paved.append(expected)
	return true


func _valid_job(r: Dictionary, term: Terminal) -> bool:
	if _stage == Terminal.WorkStage.IDLE or _stage == Terminal.WorkStage.OPEN:
		return (
			r.staging.is_empty()
			and r.remaining == 0
			and (_stage == Terminal.WorkStage.IDLE) == _paved.is_empty()
		)
	if not _valid_remaining(_stage, r.remaining) or term.town.lane_extension_price <= 0:
		return false
	if not _remaining_sites.is_empty():
		return r.staging.is_empty()
	var count := term.town.construction_staging_lanes
	if not _paved.is_empty() or count not in [1, 2] or r.staging.size() != count:
		return false
	for v in r.staging:
		if not _add_staging_lane(v):
			return false
	return true


func _add_staging_lane(v: Variant) -> bool:
	if not _number(v) or v > -Layout.EXIT_CLEAR:
		return false
	for group: Array in _lanes.values():
		for lane: TerminalLane in group:
			if is_equal_approx(lane.v, v):
				if (
					lane in _staging
					or (
						_stage != Terminal.WorkStage.DRAINING
						and (not lane.queue.is_empty() or lane.enroute > 0)
					)
				):
					return false
				_staging.append(lane)
				return true
	return false


static func _valid_remaining(stage: Terminal.WorkStage, remaining: float) -> bool:
	match stage:
		Terminal.WorkStage.DRAINING:
			return remaining == Terminal.BUILD_MINUTES
		Terminal.WorkStage.ARRIVING:
			return (
				remaining >= Terminal.BUILD_MINUTES - Terminal.ARRIVAL_MINUTES
				and remaining <= Terminal.BUILD_MINUTES
			)
		Terminal.WorkStage.PAVING:
			return (
				remaining >= Terminal.DEPARTURE_MINUTES
				and remaining <= Terminal.BUILD_MINUTES - Terminal.ARRIVAL_MINUTES
			)
		Terminal.WorkStage.LEAVING:
			return remaining > 0 and remaining <= Terminal.DEPARTURE_MINUTES
	return false


func _read_cars(
	rows: Variant, lane: TerminalLane, term: Terminal, make_vehicle: Callable, approaching: bool
) -> bool:
	if not rows is Array or rows.size() > term.slots_per_lane:
		return false
	for row in rows:
		if not _read_car(row, lane, term, make_vehicle, approaching):
			return false
	return lane.queued_slots() + lane.enroute <= term.slots_per_lane


func _read_car(
	row: Variant, lane: TerminalLane, term: Terminal, make_vehicle: Callable, approaching: bool
) -> bool:
	if not _valid_waiter(row, term):
		return false
	var car := VehiclePartsSnapshot.rebuild(row, make_vehicle)
	if car == null:
		return false
	_vehicles.append(car)
	car.dest = term.sim.map.town_by_key(row.destination).id
	car.lot_arrival = row.arrival
	if row.has("motion") and not _read_motion(row.motion, car):
		return false
	if approaching:
		if (
			not row.has("motion")
			or not row.get("transfer") is bool
			or not _number(row.get("source_offset"))
		):
			return false
		car.lane_v = row.source_offset
		lane.reserve_arrival(car.get_instance_id(), car.slots, row.transfer)
		car.resume_drive(term._on_car_reached_lot.bind(lane, row.transfer))
		return true
	return _place_in_queue(row, car, term, lane)


func _read_motion(motion: Variant, car: Vehicle) -> bool:
	if not VehicleMotionSnapshot.restore(motion, car):
		return false
	if not _integer(motion.get("order")) or motion.order < 0 or _moving.has(int(motion.order)):
		return false
	_moving[int(motion.order)] = car
	return true


func _place_in_queue(row: Dictionary, car: Vehicle, term: Terminal, lane: TerminalLane) -> bool:
	car.lane_v = lane.v
	var heading := atan2(term.town.dock_dir.x, term.town.dock_dir.z)
	var spot := term.queue_position(lane.v, lane.queued_slots(), car)
	if car.path.is_empty():
		car.position = spot
		car.rotation.y = heading
		car.straighten()
	else:
		if not row.get("follows_previous") is bool or not car.path[-1].is_equal_approx(spot):
			return false
		car.resume_parking(heading)
		if row.follows_previous:
			if lane.queue.is_empty():
				return false
			car.leader = instance_from_id(lane.queue.back().vehicle_id) as Vehicle
	lane.enqueue(car.get_instance_id(), car.slots)
	return true


func _read_passengers(rows: Array, term: Terminal) -> bool:
	if rows.size() > Terminal.PASSENGER_CAPACITY:
		return false
	var visible := 0
	for row in rows:
		if not _valid_waiter(row, term) or not row.get("visible") is bool:
			return false
		if (
			not _integer(row.get("variant"))
			or row.variant < 0
			or row.variant >= Passenger.VARIANT_COUNT
		):
			return false
		visible += int(row.visible)
		_passengers.append(
			{
				"dest": term.sim.map.town_by_key(row.destination).id,
				"arrival": row.arrival,
				"variant": int(row.variant),
				"visible": row.visible
			}
		)
	return visible <= Terminal.MAX_VISIBLE_PASSENGERS


static func _valid_waiter(row: Variant, term: Terminal) -> bool:
	if (
		not row is Dictionary
		or not _number(row.get("arrival"))
		or not row.get("destination") is String
	):
		return false
	var town := term.sim.map.town_by_key(row.destination)
	return town != null and town != term.town and term.lanes.has(town.id)


func _install(r: Dictionary, term: Terminal) -> void:
	for group: Array in term.lanes.values():
		for lane: TerminalLane in group:
			for id: int in lane.approaching:
				instance_from_id(id).free()
			for waiting in lane.queue:
				instance_from_id(waiting.vehicle_id).free()
	for pax in term.passenger_queue:
		if pax.node != null:
			pax.node.free()
	term.passenger_queue.clear()
	term.lanes = _lanes
	term.site_lanes = _remaining_sites
	term.paved = _paved
	term.extra_lane = null if _paved.is_empty() else term.lane_at_offset(_paved.back())
	term.staging_lanes = _staging
	term.work_stage = _stage
	term.build_remaining = r.remaining
	var ordered: Array[Vehicle] = []
	for car in _vehicles:
		if car.path.is_empty():
			ordered.append(car)
	for i in _moving.size():
		ordered.append(_moving[i])
	for car in ordered:
		car.moving_traffic = term.sim.moving_vehicles
		term.sim.traffic.add_child(car)
	_vehicles.clear()
	var visible := 0
	for pax in _passengers:
		var node: Passenger = null
		if pax.visible:
			node = term.sim.make_passenger(pax.variant)
			node.stand_at(
				term._waiting_spot(visible), atan2(term.town.dock_dir.x, term.town.dock_dir.z)
			)
			visible += 1
		pax.erase("visible")
		pax.node = node
		term.passenger_queue.append(pax)
	term.avg_wait = r.average_wait
	term.turned_recent = r.turned_recent
	term.served_today = int(r.served)
	term.passengers_served_today = int(r.passengers_served)
	term._spawn_acc = r.vehicle_demand
	term._pax_spawn_acc = r.passenger_demand
	term._queue_changed()
	term.extension_changed.emit()


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		for car in _vehicles:
			car.free()


static func _number(v: Variant) -> bool:
	return (v is float or v is int) and is_finite(v)


static func _integer(v: Variant) -> bool:
	return _number(v) and floor(v) == v and abs(v) <= 2147483647
