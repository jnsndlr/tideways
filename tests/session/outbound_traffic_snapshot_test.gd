extends "res://tests/support/company_snapshot_case.gd"


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var live := _world()
	_empty_queues(live)
	var ferry := live.ferries[0]
	_enqueue(ferry.here(), 1)
	_enqueue(ferry.here(), 3)
	var saw_first := false
	var saw_pair := false
	var saw_loading := false
	for frame in 10000:
		_step(ferry)
		var rows: Array = OutboundTrafficSnapshot.capture(live)
		if rows.size() == 1 and not saw_first:
			saw_first = true
			# Interleave an incoming car between the two exits in scene order.
			ferry.here()._spawn_car()
		if rows.size() == 2 and not saw_pair:
			saw_pair = true
			_compare_pair(live, rows)
		if saw_pair and not rows.is_empty() and ferry.state == Ferry.State.LOADING:
			var saved := _save(live)
			if not saved.is_empty():
				var fresh := CompanySnapshot.restore(saved, _world, VehicleFactory.from_parts)
				check(
					fresh != null,
					"A new loading phase and remaining outbound roads restore together"
				)
				if fresh != null:
					check(
						fresh.ledger.cars_total == 2 and fresh.ledger.revenue_total == 36,
						"Departed customers pay no second fare on reopening"
					)
					check(
						OutboundTrafficSnapshot.capture(fresh).size() == rows.size(),
						"Every outgoing vehicle is still present on the reopened road"
					)
					fresh.free()
				saw_loading = true
				break
	check(
		saw_first and saw_pair and saw_loading,
		"Exercise two actual discharges and the next loading phase"
	)
	live.free()
	_overflow()
	finish()


func _compare_pair(live: Simulation, rows: Array) -> void:
	var fresh := _world()
	var ferry := live.ferries[0]
	var hull := fresh.ferries[0]
	hull.at_a = ferry.at_a
	hull.state = Ferry.State.UNLOADING
	var target := hull.here()
	var saved_lot := TerminalHoldingSnapshot.capture(ferry.here())
	check(
		TerminalHoldingSnapshot.restore(saved_lot, target, VehicleFactory.from_parts),
		"Restore the incoming car before inserting the discharged stream"
	)
	var records: Array = JSON.parse_string(JSON.stringify(rows, "", true, true))
	check(
		(
			records[0].road_ahead < records[1].road_ahead
			and records[1].leader == 0
			and records[1].last_sent_by == hull.fleet_key
		),
		"Two departures retain their order around the incoming car and their ferry"
	)
	if not OutboundTrafficSnapshot.restore(records, fresh, VehicleFactory.from_parts):
		check(false, "Rebuild both outgoing actors")
		fresh.free()
		return
	check(
		hull._last_sent != ferry._last_sent and hull._last_sent.model == ferry._last_sent.model,
		"Reconnect the hull to its own restored last discharge"
	)
	var original := _active_cars(live)
	var copy := _active_cars(fresh)
	check(original.size() == copy.size(), "Same active traffic at the checkpoint")
	for i in mini(original.size(), copy.size()):
		check(
			(
				original[i].position.is_equal_approx(copy[i].position)
				and original[i].path == copy[i].path
			),
			"Actual source processing order, exact positions and rounded paths survive"
		)
		original[i]._process(0.025)
		copy[i]._process(0.025)
		check(original[i].position.is_equal_approx(copy[i].position), "Next traffic step matches")
	check(
		hull._last_vehicle_clear_of_lot() == ferry._last_vehicle_clear_of_lot(),
		"Lot clearance uses the restored last vehicle"
	)
	var ledger := fresh.ledger.snapshot(fresh.map.routes)
	for frame in 6000:
		for car in _active_cars(fresh):
			car._process(DT)
		if OutboundTrafficSnapshot.capture(fresh).is_empty():
			break
	check(
		(
			OutboundTrafficSnapshot.capture(fresh).is_empty()
			and hull._last_sent.is_queued_for_deletion()
		),
		"Both discharged vehicles leave at the end of their saved roads"
	)
	check(fresh.ledger.snapshot(fresh.map.routes) == ledger, "Finishing the exits posts no fare")
	fresh.free()


func _active_cars(sim: Simulation) -> Array[Vehicle]:
	var cars: Array[Vehicle] = []
	for car: Vehicle in sim.traffic.get_children():
		if not car.path.is_empty() and not car.is_queued_for_deletion():
			cars.append(car)
	return cars


func _overflow() -> void:
	var sim := _world()
	_empty_queues(sim)
	var port := sim.ferries[0].here()
	var dest := port.lane_keys()[0]
	var lanes: Array = port.lanes[dest]
	# No lane can take this guest on redirection.
	port.lanes[dest] = []
	var car := sim.make_vehicle()
	car.dest = dest
	car.lane_v = -12
	car.position = port.lot_point(car.lane_v, Layout.LANE_HEAD)
	port._redirect_guest(car)
	port.lanes[dest] = lanes
	var rows: Array = JSON.parse_string(
		JSON.stringify(OutboundTrafficSnapshot.capture(sim), "", true, true)
	)
	check(
		rows.size() == 1 and rows[0].last_sent_by == "",
		"Overflow heading home has no dispatching hull"
	)
	var fresh := _world()
	if rows.size() == 1:
		var malformed := rows.duplicate(true)
		malformed[0].leader = 0
		check(
			not OutboundTrafficSnapshot.restore(malformed, fresh, VehicleFactory.from_parts),
			"Reject a cyclic traffic leader"
		)
		check(
			OutboundTrafficSnapshot.restore(rows, fresh, VehicleFactory.from_parts),
			"Resume the turned-away vehicle on its exit path"
		)
	fresh.free()
	sim.free()
