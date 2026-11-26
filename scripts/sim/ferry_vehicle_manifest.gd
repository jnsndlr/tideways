class_name FerryVehicleManifest
extends RefCounted
## A ferry's deck reservations and their vehicles, including paid vehicles driving on.
## Instance IDs are local to the live deck. Only manifest indices cross the save boundary.

var _cars: Array[Vehicle] = []
var _slots: Array[int] = []
var _leaders: Array[int] = []
var _lanes: Array[TerminalLane] = []
var _last := -1


static func capture(ferry: Ferry) -> Variant:
	var cars: Array[Vehicle] = ferry.aboard.duplicate()
	var cells := ferry.deck.occupants
	for car in ferry.sim.moving_vehicles:
		if cells.has(car.get_instance_id()) and not cars.has(car):
			cars.append(car)
	var records := []
	var accounted := 0
	for car in cars:
		var id := car.get_instance_id()
		var slot := cells.find(id) if ferry._minus else cells.rfind(id)
		if (
			slot < 0
			or cells.count(id) != car.slots
			or car.dest < 0
			or car.dest >= ferry.sim.map.towns.size()
		):
			return null
		var entry := {
			"slot": slot,
			"destination": ferry.sim.map.towns[car.dest].key,
			"truck": car.is_truck,
			"model": car.model,
			"paint": car.body_paint,
			"trailer": car.trailer_model,
			"trailer_paint": car.trailer_paint,
			"fare_paid": car.fare_paid,
			"position": _xyz(car.position),
			"rotation": _xyz(car.rotation),
			"last_sent": car == ferry._last_sent,
		}
		if not ferry.aboard.has(car):
			var lane := ferry.here().boarding_lane_for(car)
			if lane == null or car.path.is_empty():
				return null
			entry.boarding = car.boarding_motion()
			var points := []
			for point in car.path:
				points.append(_xyz(point))
			entry.boarding.path = points
			entry.boarding.axle = _xyz(entry.boarding.axle)
			entry.boarding.lane = lane.v
			entry.boarding.leader = cars.find(car.leader) if is_instance_valid(car.leader) else -1
			if (
				entry.boarding.leader == -1
				and is_instance_valid(car.leader)
				and car.leader.is_processing()
			):
				return null
		accounted += car.slots
		records.append(entry)
	if (
		accounted + cells.count(0) != cells.size()
		or cars.size() - ferry.aboard.size() != ferry._boarding
	):
		return null
	return records


static func prepare(
	saved: Variant,
	ferry: Ferry,
	from_a: bool,
	build_vehicle: Callable,
	departure: Terminal,
	sailing: bool
) -> FerryVehicleManifest:
	if (
		not saved is Array
		or saved.size() > ferry.deck.occupants.size()
		or not build_vehicle.is_valid()
	):
		return null
	var manifest := FerryVehicleManifest.new()
	var towns := {}
	for town in ferry.sim.map.towns:
		if town.key.is_empty() or towns.has(town.key):
			return null
		towns[town.key] = town.id
	var deck := FerryDeck.new(ferry.fc)
	for entry in saved:
		if not manifest._prepare_car(entry, towns, deck, from_a, build_vehicle):
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
	var car: Vehicle = build_vehicle.call(
		entry.truck, entry.model, int(entry.paint), entry.trailer, int(entry.trailer_paint)
	)
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
	car.position = _vec(entry.position)
	car.rotation = _vec(entry.rotation)
	_slots.append(slot)
	_leaders.append(-1)
	_lanes.append(null)
	return true


func _prepare_boarding(data: Variant, departure: Terminal) -> bool:
	if not data is Dictionary or not _scalar(data.get("lane")) or not _integer(data.get("leader")):
		return false
	if data.leader < -1 or data.leader >= _cars.size() - 1 or departure == null:
		return false
	var lane := departure.lane_at_offset(data.lane)
	var motion := _decode_motion(data)
	if lane == null or motion.is_empty():
		return false
	_cars[-1].restore_boarding_motion(motion)
	_lanes[-1] = lane
	_leaders[-1] = int(data.leader)
	return true


static func _decode_motion(data: Dictionary) -> Dictionary:
	for name in ["delay", "held", "creep", "body_pitch", "reach", "trailer_yaw"]:
		if not _scalar(data.get(name)):
			return {}
	if not _point(data.get("axle")) or not data.get("path") is Array or data.path.is_empty():
		return {}
	var points := PackedVector3Array()
	for point in data.path:
		if not _point(point):
			return {}
		points.append(_vec(point))
	var motion := data.duplicate()
	motion.path = points
	motion.axle = _vec(data.axle)
	return motion


func install(ferry: Ferry) -> void:
	for i in _cars.size():
		var car := _cars[i]
		car.moving_traffic = ferry.sim.moving_vehicles
		ferry._take_slots(_slots[i], car)
		if _lanes[i] == null:
			ferry.add_child(car)
			car.straighten()
			ferry.aboard.append(car)
		else:
			var terminal := ferry.here()
			terminal.resume_boarding(car, _lanes[i])
			var parked := ferry._park_xform(_slots[i], car)
			car.resume_boarding(ferry._on_boarded.bind(parked, terminal))
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
		and _point(data.get("position"))
		and _point(data.get("rotation"))
		and _integer(data.get("slot"))
		and _scalar(data.get("fare_paid"))
		and data.fare_paid >= 0
		and data.get("last_sent") is bool
		and _valid_identity(data)
	)


static func _valid_identity(data: Dictionary) -> bool:
	return (
		data.get("truck") is bool
		and data.get("model") is String
		and data.get("trailer") is String
		and _integer(data.get("paint"))
		and _integer(data.get("trailer_paint"))
	)


static func _scalar(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)


static func _integer(value: Variant) -> bool:
	return _scalar(value) and floor(value) == value and absf(value) <= 2147483647


static func _point(value: Variant) -> bool:
	return (
		value is Array
		and value.size() == 3
		and _scalar(value[0])
		and _scalar(value[1])
		and _scalar(value[2])
		and _vec(value).is_finite()
	)


static func _xyz(value: Vector3) -> Array:
	return [value.x, value.y, value.z]


static func _vec(value: Array) -> Vector3:
	return Vector3(value[0], value[1], value[2])
