class_name FerryVehicleManifest
extends RefCounted
## A ferry's deck reservations and their vehicles, including paid vehicles driving on.
## Instance IDs are local to the live deck. Only manifest indices cross the save boundary.

var _cars: Array[Vehicle] = []
var _released: Array[bool] = []
var _park_from_minus: Array[bool] = []
var _slots: Array[int] = []
var _leaders: Array[int] = []
var _lanes: Array[TerminalLane] = []
var _last := -1


static func capture(ferry: Ferry) -> Variant:
	var cars: Array[Vehicle] = ferry.aboard.duplicate()
	var unloading := ferry.state == Ferry.State.UNLOADING
	cars.append_array(ferry._unload_queue)
	var cells := ferry.deck.occupants
	for car in ferry.sim.moving_vehicles:
		if cells.has(car.get_instance_id()) and not cars.has(car):
			cars.append(car)
	var records := []
	var accounted := 0
	for car in cars:
		var id := car.get_instance_id()
		var released := ferry._unload_queue.has(car)
		var parked := released or ferry.aboard.has(car)
		var from_minus := ferry._minus
		if parked:
			# The vehicle keeps its original boarding orientation across arrival.
			from_minus = car.transform.basis.z.z > 0
		var slot := cells.find(id) if from_minus else cells.rfind(id)
		if released:
			slot = _released_slot(ferry, car, from_minus)
		var expected_cells := 0 if released else car.slots
		if slot < 0 or cells.count(id) != expected_cells:
			return null
		if car.dest < -1 or car.dest >= ferry.sim.map.towns.size():
			return null
		var entry := VehiclePartsSnapshot.capture(car)
		entry.slot = slot
		entry.destination = ferry.sim.map.towns[car.dest].key if car.dest >= 0 else ""
		entry.fare_paid = car.fare_paid
		entry.last_sent = car == ferry._last_sent
		if parked:
			if not _matches_pose(ferry, car, slot, from_minus):
				return null
			if unloading or from_minus != ferry._minus:
				entry.park_from_minus = from_minus
			if unloading:
				entry.released = released
		else:
			var lane := ferry.here().boarding_lane_for(car)
			if lane == null or car.path.is_empty():
				return null
			entry.boarding = VehicleMotionSnapshot.capture(car)
			entry.boarding.lane = lane.v
			entry.boarding.leader = cars.find(car.leader) if is_instance_valid(car.leader) else -1
			if (
				entry.boarding.leader == -1
				and is_instance_valid(car.leader)
				and car.leader.is_processing()
			):
				return null
		accounted += expected_cells
		records.append(entry)
	if (
		accounted + cells.count(0) != cells.size()
		or cars.size() - ferry.aboard.size() - ferry._unload_queue.size() != ferry._boarding
	):
		return null
	return records


static func _matches_pose(ferry: Ferry, car: Vehicle, slot: int, from_minus: bool) -> bool:
	var pose := ferry.parked_pose(slot, car, from_minus)
	return (
		car.position.is_equal_approx(pose.origin)
		and is_zero_approx(angle_difference(car.rotation.y, pose.basis.get_euler().y))
	)


static func _released_slot(ferry: Ferry, car: Vehicle, from_minus: bool) -> int:
	for slot in ferry.deck.occupants.size():
		if _matches_pose(ferry, car, slot, from_minus):
			return slot
	return -1


static func prepare(
	saved: Variant,
	ferry: Ferry,
	from_a: bool,
	build_vehicle: Callable,
	departure: Terminal,
	sailing: bool,
	unloading := false
) -> FerryVehicleManifest:
	if (
		not saved is Array
		or saved.size() > ferry.deck.occupants.size()
		or not build_vehicle.is_valid()
	):
		return null
	var manifest := FerryVehicleManifest.new()
	var towns := {"": -1}
	for town in ferry.sim.map.towns:
		if town.key.is_empty() or towns.has(town.key):
			return null
		towns[town.key] = town.id
	var deck := FerryDeck.new(ferry.fc)
	for entry in saved:
		if not entry is Dictionary or entry.has("released") != unloading:
			return null
		if (
			entry.has("park_from_minus")
			and (not entry.park_from_minus is bool or entry.has("boarding"))
		):
			return null
		if (
			unloading
			and (
				not entry.get("released") is bool
				or not entry.has("park_from_minus")
				or entry.get("last_sent") != false
				or entry.released != (entry.get("destination") in ["", departure.town.key])
			)
		):
			return null
		var parked_from: bool = entry.get("park_from_minus", from_a)
		if not manifest._prepare_car(entry, towns, deck, parked_from, build_vehicle):
			return null
		if (
			entry.has("boarding")
			and (sailing or not manifest._prepare_boarding(entry.boarding, departure))
		):
			return null
	return manifest


func _prepare_car(
	entry: Variant, towns: Dictionary, deck: FerryDeck, from_a: bool, build_vehicle: Callable
) -> bool:
	if not _valid_entry(entry, towns):
		return false
	var car := VehiclePartsSnapshot.rebuild(entry, build_vehicle)
	if car == null:
		return false
	_cars.append(car)
	var slot := int(entry.slot)
	var lanes := deck.layout.lanes
	var end := slot + (car.slots - 1) * (lanes if from_a else -lanes)
	if (
		mini(slot, end) < 0
		or maxi(slot, end) >= deck.occupants.size()
		or not deck.layout.lane_allows(slot % lanes, car.is_tall)
	):
		return false
	if not deck._fits(slot, car.slots, from_a) or (entry.last_sent and _last >= 0):
		return false
	deck.reserve(slot, car.slots, from_a, car.get_instance_id())
	if entry.last_sent:
		_last = _cars.size() - 1
	car.dest = towns[entry.destination]
	car.fare_paid = entry.fare_paid
	_slots.append(slot)
	_park_from_minus.append(from_a)
	_released.append(entry.get("released", false))
	_leaders.append(-1)
	_lanes.append(null)
	return true


func _prepare_boarding(data: Variant, departure: Terminal) -> bool:
	if not data is Dictionary or not _scalar(data.get("lane")) or not _integer(data.get("leader")):
		return false
	if data.leader < -1 or data.leader >= _cars.size() - 1 or departure == null:
		return false
	var lane := departure.lane_at_offset(data.lane)
	if lane == null or not VehicleMotionSnapshot.restore(data, _cars[-1]):
		return false
	_lanes[-1] = lane
	_leaders[-1] = int(data.leader)
	return true


func install(ferry: Ferry) -> void:
	for i in _cars.size():
		var car := _cars[i]
		car.moving_traffic = ferry.sim.moving_vehicles
		if not _released[i]:
			ferry.deck.reserve(_slots[i], car.slots, _park_from_minus[i], car.get_instance_id())
		if _lanes[i] == null:
			ferry.add_child(car)
			ferry._set_parked(car, ferry.parked_pose(_slots[i], car, _park_from_minus[i]))
			if _released[i]:
				ferry._unload_queue.append(car)
			else:
				ferry.aboard.append(car)
		else:
			var terminal := ferry.here()
			terminal.resume_boarding(car, _lanes[i])
			var parked := ferry._park_xform(_slots[i], car)
			car.resume_drive(ferry._on_boarded.bind(parked, terminal))
			if _leaders[i] >= 0:
				car.leader = _cars[_leaders[i]]
			ferry._boarding += 1
			ferry._boarding_spaces += car.slots
			ferry.sim.traffic.add_child(car)
	ferry._last_sent = _cars[_last] if _last >= 0 else null
	_cars.clear()


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		for car in _cars:
			car.free()


static func _valid_entry(data: Variant, towns: Dictionary) -> bool:
	if not data is Dictionary:
		return false
	return (
		towns.has(data.get("destination"))
		and _integer(data.get("slot"))
		and _scalar(data.get("fare_paid"))
		and data.fare_paid >= 0
		and data.get("last_sent") is bool
	)


static func _scalar(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)


static func _integer(value: Variant) -> bool:
	return _scalar(value) and floor(value) == value and absf(value) <= 2147483647
