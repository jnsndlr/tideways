class_name SaleTowSnapshot
extends RefCounted
## The sale was already paid. Recreate the two physical actors outside the fleet
## and let DeliveryTow retire them through its ordinary outbound departure.


static func capture(tow: DeliveryTow) -> Dictionary:
	var hull := tow.ferry
	if (
		not is_instance_valid(hull)
		or not hull.purchased
		or hull in tow.sim.ferries
		or hull.tow != tow
		or not tow.outbound
	):
		return {}
	var coupled := tow.phase == DeliveryTow.Phase.PULLING
	if (
		(
			tow.phase
			not in [
				DeliveryTow.Phase.FETCHING, DeliveryTow.Phase.TURNING, DeliveryTow.Phase.PULLING
			]
		)
		or (tow.consort == hull) != coupled
		or (hull.consort == tow) != coupled
	):
		return {}
	var town := hull.here().town
	if hull.tie_up < 0 or hull.tie_up >= town.slips.size() or hull.manual or hull.holding:
		return {}
	return {
		"hull": hull.fleet_key,
		"name": hull.ferry_name,
		"size": hull.fc.size,
		"town": town.key,
		"route": hull.route.key,
		"offset": town.slip_offset(hull.tie_up),
		"tie_up": town.slips[hull.tie_up].tie_up,
		"reversed": hull._rev,
		"ramp_synced": hull._ramp_synced,
		"condition": hull.condition,
		"hull_basis":
		[
			SnapshotVector3.encode(hull.global_basis.x),
			SnapshotVector3.encode(hull.global_basis.y),
			SnapshotVector3.encode(hull.global_basis.z),
		],
		"hull_position": SnapshotVector3.encode(hull.global_position),
		"hull_speed": hull.speed,
		"hull_lights": hull.room_seed,
		"tug": tow.vessel_name,
		"tug_lights": tow.room_seed,
		"phase": DeliveryTow.Phase.keys()[tow.phase],
		"path": DeliveryChannelSnapshot.capture(tow.path),
		"distance": tow.s,
		"speed": tow.speed,
		"committed": tow.committed,
		"bob": tow._bob,
		"yaw": tow._yaw,
		"dock_yaw": tow._dock_yaw,
		"flip": tow._flip,
		"tug_position": SnapshotVector3.encode(tow.global_position)
	}


static func restore(row: Variant, sim: Simulation) -> bool:
	if not _valid(row) or sim.fleet_market.key_in_use(row.hull):
		return false
	var town := sim.map.town_by_key(row.town)
	if town == null or not sim.terminals.has(town.id):
		return false
	var term: Terminal = sim.terminals[town.id]
	var route := _route(sim, term, row.route)
	var slot := _berth(term, row)
	if route == null or slot < 0:
		return false
	var hull := sim.create_ferry_actor(row.hull, route, row.name, int(row.size))
	hull.purchased = true
	hull._rev = row.reversed
	hull.start_delivery(term, slot)
	hull._ramp_synced = row.ramp_synced
	hull.room_seed = row.hull_lights
	hull.condition = row.condition
	var path := DeliveryChannelSnapshot.read(row.path, hull, hull.global_position)
	if path.is_empty():
		return false
	# The launch and turning geometry refer to the actual pose at sale.
	hull.global_position = Vector3(path[-1].x, 0.0, path[-1].y)
	hull.global_basis = Basis(Vector3.UP, row.dock_yaw)
	var tow := DeliveryTow.new()
	sim.add_child(tow)
	tow.setup(sim, hull, path, true)
	if not _install_motion(row, tow):
		return false
	sim.tows.append(tow)
	sim.marine.register(tow, MarineTraffic.RANK_FERRY)
	return true


static func _install_motion(row: Dictionary, tow: DeliveryTow) -> bool:
	var hull := tow.ferry
	var phase: DeliveryTow.Phase = DeliveryTow.Phase[row.phase]
	var leaving := phase == DeliveryTow.Phase.PULLING
	var limit := tow._out.length - tow._gap() if leaving else tow._back.length
	if row.distance < 0 or row.distance > limit or row.speed < 0 or row.speed > tow.cruise + 0.001:
		return false
	if (
		phase == DeliveryTow.Phase.TURNING
		and (not is_equal_approx(row.distance, limit) or row.speed != 0)
	):
		return false
	if not is_equal_approx(row.hull_speed, row.speed if leaving else 0.0):
		return false
	if row.committed != (not leaving or row.distance < Terminal.REFIT_HOLD):
		return false
	var hull_at := tow._out.sample(row.distance) if leaving else Vector2(tow._berth.x, tow._berth.z)
	var tug_at := (
		tow._out.sample(row.distance + tow._gap()) if leaving else tow._back.sample(row.distance)
	)
	var saved_hull := SnapshotVector3.decode(row.hull_position)
	var saved_tug := SnapshotVector3.decode(row.tug_position)
	if (
		saved_hull.distance_to(Vector3(hull_at.x, 0, hull_at.y)) > 0.1
		or saved_tug.distance_to(Vector3(tug_at.x, 0, tug_at.y)) > 0.1
	):
		return false
	tow.phase = phase
	tow.s = row.distance
	tow.speed = row.speed
	tow.committed = row.committed
	tow._dock_yaw = row.dock_yaw
	tow._flip = row.flip
	tow._bob = row.bob
	tow.vessel_name = row.tug
	tow.name = row.tug
	tow.room_seed = row.tug_lights
	tow._set_pose(Vector2(saved_tug.x, saved_tug.z), row.yaw, 0)
	var axes: Array = row.hull_basis
	var basis := Basis(
		SnapshotVector3.decode(axes[0]),
		SnapshotVector3.decode(axes[1]),
		SnapshotVector3.decode(axes[2])
	)
	hull.global_transform = Transform3D(basis, saved_hull)
	hull.speed = row.hull_speed
	if leaving:
		tow.consort = hull
		hull.consort = tow
	return true


static func _route(sim: Simulation, term: Terminal, key: String) -> MapData.Route:
	for id in term.town.route_ids():
		var route := sim.map.routes[id]
		if route.key == key and sim.terminals.has(route.a) and sim.terminals.has(route.b):
			return route
	return null


static func _berth(term: Terminal, row: Dictionary) -> int:
	for index in term.town.slips.size():
		var slip := term.town.slips[index]
		if not is_equal_approx(term.town.slip_offset(index), row.offset):
			continue
		if slip.building or slip.tie_up != row.tie_up or not slip.fits(int(row.size)):
			return -1
		if row.committed and term.sim.fleet_market.berth_reserved(term, index):
			return -1
		return index
	return -1


static func _valid(row: Variant) -> bool:
	if not row is Dictionary:
		return false
	for key in ["hull", "name", "town", "route", "tug", "phase"]:
		if not row.get(key) is String or row[key].is_empty():
			return false
	for key in [
		"size",
		"offset",
		"condition",
		"hull_speed",
		"hull_lights",
		"tug_lights",
		"distance",
		"speed",
		"bob",
		"yaw",
		"dock_yaw",
		"flip"
	]:
		var value = row.get(key)
		if not (value is int or value is float) or not is_finite(value):
			return false
	return (
		FleetMarket.is_purchase_key(row.hull)
		and row.size == floor(row.size)
		and row.size >= 1
		and row.size <= FerryClass.MAX_SIZE
		and row.tug in DeliveryTow.NAMES
		and row.phase in ["FETCHING", "TURNING", "PULLING"]
		and row.get("reversed") is bool
		and row.get("tie_up") is bool
		and row.get("committed") is bool
		and row.get("ramp_synced") is bool
		and row.condition >= 0
		and row.condition <= 1
		and row.hull_speed >= 0
		and (is_zero_approx(row.flip) or is_equal_approx(row.flip, PI))
		and SnapshotVector3.valid(row.get("hull_position"))
		and _valid_basis(row.get("hull_basis"))
		and SnapshotVector3.valid(row.get("tug_position"))
		and row.get("path") is Array
	)


static func _valid_basis(axes: Variant) -> bool:
	if not axes is Array or axes.size() != 3:
		return false
	for axis in axes:
		if not SnapshotVector3.valid(axis):
			return false
	var basis := Basis(
		SnapshotVector3.decode(axes[0]),
		SnapshotVector3.decode(axes[1]),
		SnapshotVector3.decode(axes[2])
	)
	return (
		is_equal_approx(basis.determinant(), 1.0) and basis.is_equal_approx(basis.orthonormalized())
	)
