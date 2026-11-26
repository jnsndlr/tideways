class_name OutboundTrafficSnapshot
extends RefCounted
## Discharged vehicles and turned-away overflow on their final drive. These live
## outside a terminal queue and no longer occupy deck slots. The company installs
## this section after the other road traffic and all hull manifests.


static func capture(sim: Simulation) -> Variant:
	var released_by := {}
	for ferry in sim.ferries:
		if is_instance_valid(ferry._last_sent) and ferry._last_sent.is_leaving_terminal():
			released_by[ferry._last_sent] = ferry.fleet_key
	var records := []
	var indexes := {}
	var road_ahead := 0
	for car: Vehicle in sim.traffic.get_children():
		if car.is_queued_for_deletion() or car.path.is_empty():
			continue
		if not car.is_leaving_terminal():
			road_ahead += 1
			continue
		if car.dest < -1 or car.dest >= sim.map.towns.size():
			return null
		var leader := -1
		if is_instance_valid(car.leader) and car.leader.is_processing():
			if not indexes.has(car.leader):
				return null
			leader = indexes[car.leader]
		var row := VehiclePartsSnapshot.capture(car)
		row.motion = VehicleMotionSnapshot.capture(car)
		row.destination = sim.map.towns[car.dest].key if car.dest >= 0 else ""
		row.fare_paid = car.fare_paid
		row.lot_arrival = car.lot_arrival
		row.lane_offset = car.lane_v
		row.road_ahead = road_ahead
		row.leader = leader
		row.last_sent_by = released_by.get(car, "")
		indexes[car] = records.size()
		records.append(row)
	return records


## The caller owns a private target and discards it on any failure.
static func restore(rows: Array, sim: Simulation, make_vehicle: Callable) -> bool:
	var moving: Array[Vehicle] = []
	for car: Vehicle in sim.traffic.get_children():
		if car.is_leaving_terminal():
			return false
		if not car.is_queued_for_deletion() and not car.path.is_empty():
			moving.append(car)
	var ferries := {}
	for ferry in sim.ferries:
		ferries[ferry.fleet_key] = ferry
	var restored: Array[Vehicle] = []
	var previous := 0
	for row in rows:
		if not _valid(row, sim, previous, moving.size(), restored.size()):
			return false
		var car := VehiclePartsSnapshot.rebuild(row, make_vehicle)
		if car == null:
			return false
		if not VehicleMotionSnapshot.restore(row.get("motion"), car):
			car.free()
			return false
		car.lot_arrival = row.lot_arrival
		car.lane_v = row.lane_offset
		car.fare_paid = row.fare_paid
		car.dest = sim.map.town_by_key(row.destination).id if row.destination != "" else -1
		if row.leader >= 0:
			car.leader = restored[int(row.leader)]
		car.resume_drive(car.finish_road_exit)
		car.moving_traffic = sim.moving_vehicles
		sim.traffic.add_child(car)
		previous = int(row.road_ahead)
		if previous < moving.size():
			sim.traffic.move_child(car, moving[previous].get_index())
		restored.append(car)
		if row.last_sent_by != "":
			var ferry: Ferry = ferries.get(row.last_sent_by)
			if (
				ferry == null
				or ferry.state != Ferry.State.UNLOADING
				or is_instance_valid(ferry._last_sent)
			):
				return false
			ferry._last_sent = car
	return true


static func _valid(row: Variant, sim: Simulation, previous: int, moving: int, index: int) -> bool:
	if not row is Dictionary or not row.get("destination") is String:
		return false
	if row.destination != "" and sim.map.town_by_key(row.destination) == null:
		return false
	return (
		_number(row.get("fare_paid"))
		and row.fare_paid >= 0
		and _number(row.get("lot_arrival"))
		and _number(row.get("lane_offset"))
		and row.get("last_sent_by") is String
		and _number(row.get("road_ahead"))
		and floor(row.road_ahead) == row.road_ahead
		and row.road_ahead >= previous
		and row.road_ahead <= moving
		and _number(row.get("leader"))
		and floor(row.leader) == row.leader
		and row.leader >= -1
		and row.leader < index
	)


static func _number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)
