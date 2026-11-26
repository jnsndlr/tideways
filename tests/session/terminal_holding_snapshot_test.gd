extends "res://tests/rule_test_case.gd"
## Compare a purchased lane still being paved and already open in fresh simulations.


func _initialize() -> void:
	call_deferred("_run")


func _world(renumber := false, uses_staging := false) -> Simulation:
	var region := TinyRegion.build()
	if renumber:
		region.map.towns.reverse()
		for i in region.map.towns.size():
			region.map.towns[i].id = i
		for route in region.map.routes:
			route.a = 1 - route.a
			route.b = 1 - route.b
	for town in region.map.towns:
		town.open_lanes = 0 if uses_staging else 2
		town.construction_staging_lanes = 1 if uses_staging else 0
		town.lane_extension_price = 150
	return region.start(root)


func _run() -> void:
	var live := _world()
	var port: Terminal = live.terminals[0]
	var initial := port.capacity()
	var cash := live.ledger.cash
	check(port.buy_holding_lane(), "Purchase a holding lane from the real catalogue")
	var charge := live.ledger.today["purchases"] as float
	check(charge == 150 and live.ledger.cash == cash - charge, "Purchase posts exactly once")
	port._advance_construction(1)
	port._advance_construction(Terminal.ARRIVAL_MINUTES + 1)
	check(port.work_stage == Terminal.WorkStage.PAVING, "Capture construction in progress")
	var paving := _record(port)
	port._advance_construction(Terminal.BUILD_MINUTES)
	check(port.capacity() == initial + port.slots_per_lane, "Paving opens one lane")
	var open := _record(port)
	var expected := _board(port)
	live.free()
	_compare(paving, open, expected, true)
	_compare(open, open, expected, false)
	_check_staging()
	_check_overnight_wait()
	finish()


func _check_staging() -> void:
	var live := _world(false, true)
	var port: Terminal = live.terminals[0]
	check(port.buy_holding_lane(), "Buy an extension that stages in an existing holding lane")
	var lane := port.staging_lanes[0]
	check(not lane.queue.is_empty(), "Allow waiting traffic while the crew drains the lane")
	var draining := _record(port).holding as Dictionary
	while not lane.queue.is_empty():
		instance_from_id(lane.take_front()).free()
	port._advance_construction(1.0)
	var fresh := _world(false, true)
	var target: Terminal = fresh.terminals[0]
	var arriving := _record(port).holding as Dictionary
	var broken := arriving.duplicate(true)
	var rows: Array = broken.lanes.values()[0]
	rows[0].vehicles.append(rows[1].vehicles.pop_front())
	check(
		not TerminalHoldingSnapshot.restore(broken, target, VehicleFactory.from_parts),
		"Reject vehicles in a staging lane already occupied by the construction crew"
	)
	check(
		TerminalHoldingSnapshot.restore(draining, target, VehicleFactory.from_parts),
		"Restore the draining lane with its waiting vehicles"
	)
	check(_record(target).holding == draining, "Keep the crew's actual physical staging position")
	fresh.free()
	live.free()


func _check_overnight_wait() -> void:
	var live := _world()
	var port: Terminal = live.terminals[0]
	var dest := port.lane_keys()[0]
	var lane: TerminalLane = port.lanes[dest][0]
	while not lane.queue.is_empty():
		instance_from_id(lane.take_front()).free()
	for pax in port.passenger_queue:
		if pax.node:
			pax.node.free()
	port.passenger_queue.clear()
	live.minutes = 1439
	var car := live.make_vehicle()
	car.dest = dest
	car.position = port.queue_position(lane.v, 0, car)
	lane.enroute += car.slots
	port._on_car_reached_lot(car, lane)
	port._spawn_passenger()
	var walker: Passenger = port.passenger_queue.front().node
	for frame in 300:
		car._process(0.1)
		walker._process(0.1)
		if car.path.is_empty() and walker.path.is_empty():
			break
	var holding := _record(port).holding as Dictionary
	var fresh := _world()
	fresh.day = live.day
	fresh.minutes = live.minutes
	var restored: Terminal = fresh.terminals[0]
	check(
		TerminalHoldingSnapshot.restore(holding, restored, VehicleFactory.from_parts),
		"Restore late-night vehicle and walk-on queues"
	)
	for term in [port, restored] as Array[Terminal]:
		term.sim._process(1442.0 / Units.game_minutes(1.0))
		var dispatch := term._dispatch(term.lanes[dest][0])
		term.finish_boarding(dispatch)
		dispatch.free()
		var after_vehicle := lerpf(6, 1442, 0.1)
		check(
			is_equal_approx(term.avg_wait, after_vehicle),
			"Vehicle wait includes midnight and the full following day"
		)
		var serves: Array[int] = [dest]
		term.board_next_passenger(serves)
		check(
			is_equal_approx(term.avg_wait, lerpf(after_vehicle, 1442, 0.05)),
			"Walk-on wait includes both calendar boundaries"
		)
	live.free()
	fresh.free()


func _record(port: Terminal) -> Dictionary:
	var holding := TerminalHoldingSnapshot.capture(port)
	check(not holding.is_empty(), "Capture a settled terminal holding lot")
	return JSON.parse_string(
		JSON.stringify(
			{"holding": holding, "ledger": port.sim.ledger.snapshot(port.sim.map.routes)},
			"",
			true,
			true
		)
	)


func _compare(start: Dictionary, opened: Dictionary, expected: Dictionary, paving: bool) -> void:
	var sim := _world(true)
	var port: Terminal = sim.terminals[sim.map.town_by_key(start.holding.town).id]
	check(port.town.id == 1, "Restore to the same town under a different runtime ID")
	sim.ledger = CompanyLedgerSnapshot.restore(start.ledger, sim.map.routes)
	var saved: Dictionary = start.holding
	var damaged := saved.duplicate(true)
	var lanes: Array = damaged.lanes.values()[0]
	lanes[-1].vehicles.append({"model": "invalid"})
	var initial := _record(port)
	check(
		not TerminalHoldingSnapshot.restore(damaged, port, VehicleFactory.from_parts),
		"Reject damaged queued vehicle"
	)
	check(_record(port) == initial, "Failed decode preserves prefilled queues and cash")
	var restored := TerminalHoldingSnapshot.restore(saved, port, VehicleFactory.from_parts)
	check(restored, "Restore lot into fresh running simulation")
	if restored:
		check(
			_record(port) == start, "JSON round trip preserves ordered queues, demand and purchase"
		)
		if paving:
			port._advance_construction(Terminal.BUILD_MINUTES)
		check(
			port.lane_at_offset(opened.holding.paved.back()) == port.extra_lane,
			"Rounded JSON offset resolves to the purchased lane"
		)
		check(_record(port) == opened, "Finishing or restoring completed lane charges no more cash")
		check(_board(port) == expected, "Next dispatch and fare match uninterrupted terminal")
	sim.free()


func _board(port: Terminal) -> Dictionary:
	var ferry: Ferry = port.sim.ferries[0]
	var dest := port.lane_keys()[0]
	var serves: Array[int] = [dest]
	var car := port.board_next(serves, func(_car: Vehicle): return true)
	check(car != null, "A prefilled car is available for boarding")
	if car == null:
		return {}
	var original := port.sim.ledger.revenue_total
	ferry._drive_on(car, port)
	check(port.sim.ledger.revenue_total == original + car.fare_paid, "Drive-on posts one fare")
	var person := port.board_next_passenger(serves)
	check(not person.is_empty(), "Preserve waiting walk-ons")
	return {
		"model": car.model,
		"trailer": car.trailer_model,
		"paint": car.body_paint,
		"ticket": car.fare_paid,
		"waiting": port.total_queued(),
		"passenger": person.variant,
		"arrival": person.arrival,
		"ledger": port.sim.ledger.snapshot(port.sim.map.routes)
	}
