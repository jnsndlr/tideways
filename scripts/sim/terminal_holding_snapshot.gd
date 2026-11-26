class_name TerminalHoldingSnapshot
extends RefCounted
## A terminal's settled holding lot, walk-on queue and lane construction job.
## Rebuild the same region and service before restoring. The company owns the
## clock and ledger. Approaching vehicles, moving queues and slips are separate.

var _lanes := {}
var _vehicles: Array[Vehicle] = []
var _paved: Array[float] = []
var _passengers: Array[Dictionary] = []
var _remaining_sites: Array[float] = []
var _stage: Terminal.WorkStage
var _staging: Array[TerminalLane] = []


static func capture(term: Terminal) -> Dictionary:
	var groups := {}
	for dest: int in term.lanes:
		var rows := []
		for lane: TerminalLane in term.lanes[dest]:
			var cars := []
			if lane.enroute:
				return {}
			for waiting in lane.queue:
				var car := instance_from_id(waiting.vehicle_id) as Vehicle
				if car == null or not car.path.is_empty() or car.dest < 0:
					return {}
				var record := VehiclePartsSnapshot.capture(car)
				record.destination = term.sim.map.towns[car.dest].key
				record.arrival = car.lot_arrival
				cars.append(record)
			rows.append({"offset": lane.v, "vehicles": cars})
		groups[_key(term, dest)] = rows
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
		"version": 1,
		"seed": str(term.sim.map.map_seed),
		"town": term.town.key,
		"slots_per_lane": term.slots_per_lane,
		"lanes": groups,
		"paved": term.paved.duplicate(),
		"stage": Terminal.WorkStage.keys()[term.work_stage],
		"remaining": term.build_remaining,
		"passengers": passengers,
		"average_wait": term.avg_wait,
		"turned_recent": term.turned_recent,
		"served": term.served_today,
		"passengers_served": term.passengers_served_today,
		"vehicle_demand": term._spawn_acc,
		"passenger_demand": term._pax_spawn_acc
	}


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
	if not r is Dictionary or not _integer(r.get("version")) or r.version != 1:
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
		and r.vehicle_demand < 1
		and r.passenger_demand < 1
		and r.get("stage") is String
		and Terminal.WorkStage.has(r.stage)
		and r.get("lanes") is Dictionary
		and r.lanes.size() == term.lanes.size()
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
			if not _read_cars(row.get("vehicles"), lane, term, make_vehicle):
				return false
			lanes.append(lane)
		_lanes[dest] = lanes
	_stage = Terminal.WorkStage[r.stage]
	return offsets.is_empty() and _valid_job(r, term) and _read_passengers(r.passengers, term)


func _read_paved(paved: Array, term: Terminal, offsets: Array[float]) -> bool:
	_remaining_sites = term.site_lanes.duplicate()
	if not paved.is_empty() and term.town.lane_extension_price <= 0:
		return false
	var available := _remaining_sites.size()
	if available == 0 and term.can_stage_construction():
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
		return r.remaining == 0 and (_stage == Terminal.WorkStage.IDLE) == _paved.is_empty()
	if not _valid_remaining(_stage, r.remaining) or term.town.lane_extension_price <= 0:
		return false
	if not _remaining_sites.is_empty():
		return true
	if not _paved.is_empty() or not term.can_stage_construction():
		return false
	var group: Array = _lanes[term.lane_keys()[0]]
	if group.size() <= term.town.construction_staging_lanes:
		return false
	for index in term.town.construction_staging_lanes:
		_staging.append(group[index])
	return true


static func _valid_remaining(stage: Terminal.WorkStage, remaining: float) -> bool:
	match stage:
		Terminal.WorkStage.DRAINING:
			return remaining == Terminal.BUILD_MINUTES
		Terminal.WorkStage.ARRIVING:
			return (
				remaining > Terminal.BUILD_MINUTES - Terminal.ARRIVAL_MINUTES
				and remaining <= Terminal.BUILD_MINUTES
			)
		Terminal.WorkStage.PAVING:
			return (
				remaining > Terminal.DEPARTURE_MINUTES
				and remaining <= Terminal.BUILD_MINUTES - Terminal.ARRIVAL_MINUTES
			)
		Terminal.WorkStage.LEAVING:
			return remaining > 0 and remaining <= Terminal.DEPARTURE_MINUTES
	return false


func _read_cars(rows: Variant, lane: TerminalLane, term: Terminal, make_vehicle: Callable) -> bool:
	if not rows is Array or rows.size() > term.slots_per_lane:
		return false
	for row in rows:
		if not _valid_waiter(row, term):
			return false
		var car := VehiclePartsSnapshot.rebuild(row, make_vehicle)
		if car == null:
			return false
		_vehicles.append(car)
		car.dest = term.sim.map.town_by_key(row.destination).id
		car.lot_arrival = row.arrival
		car.lane_v = lane.v
		car.position = term.queue_position(lane.v, lane.queued_slots(), car)
		car.rotation.y = atan2(term.town.dock_dir.x, term.town.dock_dir.z)
		car.straighten()
		lane.enqueue(car.get_instance_id(), car.slots)
	return lane.queued_slots() <= term.slots_per_lane


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
	for car in _vehicles:
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
