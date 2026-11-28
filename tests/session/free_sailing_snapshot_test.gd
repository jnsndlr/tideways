extends "res://tests/support/company_snapshot_case.gd"
## A paid vehicle stays aboard a diverted ferry through save, free sailing and a dock order.


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var live := _world()
	_empty_queues(live)
	var boat := live.ferries[0]
	_enqueue(boat.here(), 2)
	for frame in 8000:
		_step(boat)
		if boat.state == Ferry.State.SAILING and boat.traveled > boat.run_length() * 0.35:
			break
	check(boat.aboard.size() == 1 and live.ledger.cars_total == 1, "Start with a paid crossing")
	boat.set_timetable([420, 780])
	boat.here()._spawn_passenger()
	check(not boat.here().passenger_queue.is_empty(), "A customer is waiting when service changes")
	check(boat.order_sail_to(boat.global_position + Vector3(50, 0, 100)), "Order a free sailing")
	check(not boat.here().departing_walkers.is_empty(), "The unserved customer walks to the door")
	_check_round_trip(live, false)
	for frame in 8:
		_step(boat)
	_check_round_trip(live, false)
	boat.request_return()
	check(not boat._free_join.is_empty(), "Order a return to service across open water")
	_check_round_trip(live, true)
	live.free()
	finish()


func _check_round_trip(live: Simulation, returning: bool) -> void:
	var ferry := live.ferries[0]
	var saved := _save(live)
	if saved.is_empty():
		check(false, "Capture a free ferry")
		return
	var copy := CompanySnapshot.restore(saved, _world, VehicleFactory.from_parts)
	if copy == null:
		check(false, "Restore a free ferry")
		return
	var boat := copy.ferries[0]
	check(
		boat.here().departing_walkers.size() == ferry.here().departing_walkers.size(),
		"Restore each departing customer"
	)
	check(boat.free_sail and boat.berth == Ferry.Berth.FREE, "Restore the steering mode")
	check(boat.global_transform.is_equal_approx(ferry.global_transform), "Restore the precise pose")
	check(
		boat._free_path == ferry._free_path and boat._free_wp == ferry._free_wp,
		"Resume the saved path"
	)
	check(boat.itinerary.suspended.times == [420, 780], "Restore the original service")
	check(
		boat.aboard.size() == 1 and boat.aboard[0].fare_paid == ferry.aboard[0].fare_paid,
		"Restore paid cargo once"
	)
	check(boat._orders._manual_resume_due == returning, "Restore pending return to service")
	if returning:
		check(
			(
				boat._free_join[0].key == ferry._free_join[0].key
				and boat._free_join.slice(1) == ferry._free_join.slice(1)
			),
			"Keep the requested route and slip"
		)
	for frame in 10:
		_step(ferry)
		_step(boat)
	check(
		boat.global_transform.is_equal_approx(ferry.global_transform),
		"The restored boat follows the same path"
	)
	check(
		copy.ledger.snapshot(copy.map.routes) == live.ledger.snapshot(live.map.routes),
		"Resume fuel and fares without duplicate charges"
	)
	copy.free()
	var invalid := saved.duplicate(true)
	invalid.voyages[ferry.fleet_key].free_sailing.waypoint = -1
	check(
		CompanySnapshot.restore(invalid, _world, VehicleFactory.from_parts) == null,
		"Reject an invalid steering waypoint"
	)
