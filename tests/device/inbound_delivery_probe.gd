extends RefCounted
## Observe the actual purchased ferry and its delivery signal across a cold launch.
## A berth remains reserved until the ferry arrives and takes physical occupancy.

var start_distance := 0.0
var start_remaining := 0.0
var checkpoint_distance := 0.0
var deliveries := []
var next_motion := {}
var after_arrival := {}


func start(tow: DeliveryTow) -> void:
	start_distance = tow.s
	start_remaining = tow.path.length - tow.s


func mid_tow(boat: Ferry) -> bool:
	var tow := boat.tow
	return (
		boat.berth == Ferry.Berth.DELIVERING
		and tow != null
		and tow.phase == DeliveryTow.Phase.TOWING
		and tow.speed > 0
		and tow.s > start_distance + 0.35 * start_remaining
		and tow.s < start_distance + 0.65 * start_remaining
	)


func delivered(boat: Ferry) -> void:
	(
		deliveries
		. append(
			{
				"hull": boat.fleet_key,
				"minute": boat.sim.abs_minutes(),
				"town": boat.here().town.key,
				"berth": boat.tie_up,
				"state": boat.berth,
				"position": SnapshotVector3.encode(boat.position),
			}
		)
	)


func capture(boat: Ferry) -> Dictionary:
	var tow := boat.tow
	if tow == null or tow.ferry != boat or not boat.sim.tows.has(tow):
		return {}
	checkpoint_distance = tow.s
	var points := []
	for point in tow.path.pts:
		points.append([point.x, point.y])
	return {
		"tug": tow.vessel_name,
		"tug_variant": tow.model_variant,
		"town": boat.here().town.key,
		"slip": boat.tie_up,
		"berth_state": boat.berth,
		"reserved": boat.sim.fleet_market.berth_reserved(boat.here(), boat.tie_up),
		"phase": tow.phase,
		"waiting": tow.waiting,
		"committed": tow.committed,
		"consorts": boat.consort == tow and tow.consort == boat,
		"path": points,
		"length": tow.path.length,
		"motion": _motion(tow),
	}


func _motion(tow: DeliveryTow) -> Dictionary:
	return {
		"distance": tow.s,
		"speed": tow.speed,
		"hull_speed": tow.ferry.speed,
		"position": SnapshotVector3.encode(tow.global_position),
		"forward": SnapshotVector3.encode(tow.global_basis.z),
		"right": SnapshotVector3.encode(tow.global_basis.x),
		"hull_position": SnapshotVector3.encode(tow.ferry.global_position),
		"hull_forward": SnapshotVector3.encode(tow.ferry.global_basis.z),
	}


func observe(boat: Ferry) -> void:
	if next_motion.is_empty() and boat.tow != null and boat.tow.s >= checkpoint_distance + 10:
		next_motion = _motion(boat.tow)
	if deliveries.is_empty() or not after_arrival.is_empty():
		return
	# Keep observing well past the delivery signal to catch repeated callbacks or charges.
	if boat.sim.abs_minutes() < float(deliveries.front().minute) + 10:
		return
	after_arrival = docked(boat)


func docked(boat: Ferry) -> Dictionary:
	return {
		"minute": boat.sim.abs_minutes(),
		"berth_state": boat.berth,
		"position": SnapshotVector3.encode(boat.global_position),
		"detached": boat.tow == null and boat.consort == null,
		"occupied_by_hull": boat.sim.occupant(boat.here(), boat.tie_up, null) == boat,
		"purchases": boat.sim.ledger.today.purchases,
		"hulls": boat.sim.ferries.size(),
	}


func outcome() -> Dictionary:
	return {"next_motion": next_motion, "deliveries": deliveries, "after_arrival": after_arrival}


func completed(boat: Ferry) -> bool:
	return (
		deliveries.size() == 1
		and deliveries[0].hull == boat.fleet_key
		and deliveries[0].state == Ferry.Berth.TIED_UP
		and deliveries[0].berth == boat.tie_up
		and not next_motion.is_empty()
		and not after_arrival.is_empty()
		and after_arrival.detached
		and after_arrival.occupied_by_hull
		and after_arrival.berth_state == Ferry.Berth.TIED_UP
		and after_arrival.hulls == 2
		and after_arrival.purchases == 30000
	)


static func visible_pair(boat: Ferry) -> bool:
	var ferry_view := boat.get_node_or_null("FerryView") as FerryView
	if boat.tow == null or ferry_view == null or not ferry_view.hull.is_visible_in_tree():
		return false
	var tug_view := boat.tow.get_node_or_null("VesselHullView") as VesselHullView
	return (
		ferry_view.hull.mesh == Models.ferry(boat.fc)
		and tug_view != null
		and tug_view.is_visible_in_tree()
		and tug_view.mesh != null
		and tug_view.mesh == Models.tug(boat.tow.model_variant)
	)
