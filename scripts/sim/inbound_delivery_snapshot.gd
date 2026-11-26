class_name InboundDeliverySnapshot
extends RefCounted
## An active inbound delivery owns its purchased hull and reserved berth until
## DeliveryTow's normal arrival callback releases it. No purchase is replayed.


static func attached(tow: DeliveryTow, sim: Simulation) -> bool:
	var ferry := tow.ferry
	return (
		not tow.outbound
		and tow.phase == DeliveryTow.Phase.TOWING
		and is_instance_valid(ferry)
		and ferry.purchased
		and ferry in sim.ferries
		and ferry.berth == Ferry.Berth.DELIVERING
		and ferry.tow == tow
		and tow.consort == ferry
		and ferry.consort == tow
	)


static func capture(ferry: Ferry) -> Dictionary:
	var delivered := ferry.berth == Ferry.Berth.TIED_UP
	var tow := ferry.tow
	if delivered:
		if ferry.assigned or tow != null or ferry.consort != null or ferry.return_requested:
			return {}
	elif not is_instance_valid(tow) or tow not in ferry.sim.tows or not attached(tow, ferry.sim):
		return {}
	if (
		ferry.manual
		or ferry.holding
		or ferry.shifting()
		or not ferry.next_stops.is_empty()
		or ferry.stops.size() != 2
	):
		return {}
	if (
		not ferry.aboard.is_empty()
		or not ferry.passengers_aboard.is_empty()
		or ferry.trips != 0
		or ferry._end_slip != [-1, -1]
	):
		return {}
	var town := ferry.here().town
	if ferry.tie_up < 0 or ferry.tie_up >= town.slips.size():
		return {}
	var delivery := {
		"town": town.key,
		"offset": town.slip_offset(ferry.tie_up),
		"tie_up": town.slips[ferry.tie_up].tie_up,
		"assigned": ferry.assigned,
		"reversed": ferry._rev,
		"ramp_synced": ferry._ramp_synced,
		"loading_since": ferry._loading_since,
		"state_time": ferry.voyage.state_time,
		"ferry_position": SnapshotVector3.encode(ferry.global_position),
		"ferry_rotation": SnapshotVector3.encode(ferry.global_rotation),
		"light_seed": ferry.room_seed,
	}
	if not delivered:
		var path := []
		for point in tow.path.pts:
			path.append([point.x, point.y])
		(
			delivery
			. merge(
				{
					"tug": tow.vessel_name,
					"path": path,
					"distance": tow.s,
					"speed": tow.speed,
					"committed": tow.committed,
					"waiting": tow.waiting,
					"bob": tow._bob,
					"dock_yaw": tow._dock_yaw,
					"flip": tow._flip,
					"side": tow._side,
					"tug_light_seed": tow.room_seed,
				}
			)
		)
	return {
		"phase": "delivered" if delivered else "delivery",
		"service": FerryCrossingSnapshot.service_record(ferry),
		"delivery": delivery
	}


static func restore(row: Dictionary, ferry: Ferry, stops: Array[int], delivered: bool) -> bool:
	if not _valid_hull(row) or row.has("tug") == delivered:
		return false
	var term := ferry.term_a if ferry.term_a.town.key == row.town else ferry.term_b
	if term.town.key != row.town or (not row.assigned and stops[0] != term.town.id):
		return false
	var slip := _berth(term, row, ferry)
	if slip < 0:
		return false
	ferry._rev = row.reversed
	ferry.start_delivery(term, slip)
	ferry.assigned = row.assigned
	ferry.itinerary.set_circuit(stops, [ferry.route, ferry.route], stops.find(term.town.id))
	ferry._ramp_synced = row.ramp_synced
	ferry._loading_since = row.loading_since
	ferry.voyage.state_time = row.state_time
	ferry.room_seed = row.light_seed
	var target := ferry.global_position
	if delivered:
		if ferry.assigned:
			return false
		ferry.end_delivery()
	elif not _restore_tow(row, ferry, target):
		return false
	# Assigning stops can put the hull alongside until the next tow tick.
	var position := SnapshotVector3.decode(row.ferry_position)
	if (
		position.distance_to(ferry.global_position) > 0.1
		and (not ferry.assigned or position.distance_to(target) > 0.5)
	):
		return false
	ferry.global_position = position
	ferry.global_rotation = SnapshotVector3.decode(row.ferry_rotation)
	return true


static func _restore_tow(row: Dictionary, ferry: Ferry, target: Vector3) -> bool:
	if not _valid_tow(row):
		return false
	var path := PackedVector2Array()
	var bound := (
		ferry.sim.map.half_size
		+ DeliveryTow.EDGE_OUT
		+ DeliveryTow.RUN_IN
		+ DeliveryTow.APPROACH_FAR
	)
	for point in row.path:
		if (
			not point is Array
			or point.size() != 2
			or not _finite(point[0])
			or not _finite(point[1])
		):
			return false
		var p := Vector2(point[0], point[1])
		if not p.is_finite() or absf(p.x) > bound or absf(p.y) > bound:
			return false
		path.append(p)
	if not _matches_channel(path, ferry, target):
		return false
	var tow := DeliveryTow.new()
	ferry.sim.add_child(tow)
	tow.setup(ferry.sim, ferry, path)
	if (
		row.distance < 0
		or row.distance >= tow.path.length
		or row.speed < 0
		or row.speed > tow._tow_speed() + 0.001
	):
		return false
	if (
		(row.waiting or row.committed)
		and tow.path.length - row.distance > DeliveryTow.COMMIT_AT + 0.01
	):
		return false
	tow.vessel_name = row.tug
	tow.name = row.tug
	tow.room_seed = row.tug_light_seed
	tow.s = row.distance
	tow.speed = row.speed
	tow.committed = row.committed
	tow.waiting = row.waiting
	tow._bob = row.bob
	tow._dock_yaw = row.dock_yaw
	tow._flip = row.flip
	tow._side = row.side
	tow._place(0.0)
	ferry.sim.tows.append(tow)
	ferry.sim.marine.register(tow, MarineTraffic.RANK_FERRY)
	return true


## Replan against the rebuilt chart. A corrupt interior waypoint must not send a
## tow through land even when its endpoints still match the booked berth.
static func _matches_channel(path: PackedVector2Array, ferry: Ferry, target: Vector3) -> bool:
	if path[-1].distance_to(Vector2(target.x, target.z)) > 0.5:
		return false
	var endpoint := Vector3(path[-1].x, 0.0, path[-1].y)
	var expected := DeliveryTow.plan(
		ferry.sim, endpoint, ferry.here().town.dock_dir, ferry.fc.half_beam
	)
	if expected.size() != path.size():
		return false
	for index in expected.size():
		if expected[index].distance_to(path[index]) > 0.1:
			return false
	return true


static func _berth(term: Terminal, row: Dictionary, ferry: Ferry) -> int:
	for index in term.town.slips.size():
		var slip := term.town.slips[index]
		if not is_equal_approx(term.town.slip_offset(index), row.offset):
			continue
		if slip.building or slip.tie_up != row.tie_up or not slip.fits(ferry.fc.size):
			return -1
		for other in ferry.sim.ferries:
			if (
				other != ferry
				and other.berth in [Ferry.Berth.TIED_UP, Ferry.Berth.DELIVERING]
				and other.here() == term
				and other.tie_up == index
			):
				return -1
		return index
	return -1


static func _valid_hull(row: Dictionary) -> bool:
	for key in ["assigned", "reversed", "ramp_synced", "tie_up"]:
		if not row.get(key) is bool:
			return false
	for key in ["offset", "loading_since", "state_time", "light_seed"]:
		if not _finite(row.get(key)):
			return false
	return (
		row.get("town") is String
		and row.state_time >= 0
		and SnapshotVector3.valid(row.get("ferry_position"))
		and SnapshotVector3.valid(row.get("ferry_rotation"))
	)


static func _valid_tow(row: Dictionary) -> bool:
	for key in ["distance", "speed", "bob", "dock_yaw", "flip", "side", "tug_light_seed"]:
		if not _finite(row.get(key)):
			return false
	return (
		row.get("tug") is String
		and row.tug in DeliveryTow.NAMES
		and row.get("committed") is bool
		and row.get("waiting") is bool
		and row.get("path") is Array
		and row.path.size() >= 2
		and row.path.size() <= 65536
		and absf(row.side) == 1.0
		and (is_zero_approx(row.flip) or is_equal_approx(row.flip, PI))
		and not (row.committed and row.waiting)
	)


static func _finite(value: Variant) -> bool:
	return (value is float or value is int) and is_finite(value)
