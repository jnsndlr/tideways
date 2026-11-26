extends "res://tests/rule_test_case.gd"
## Compare a purchased lane still being paved and already open in fresh simulations.


func _initialize() -> void:
	call_deferred("_run")


func _world(renumber := false) -> Simulation:
	var region := TinyRegion.build()
	if renumber:
		region.map.towns.reverse()
		for i in region.map.towns.size():
			region.map.towns[i].id = i
		for route in region.map.routes:
			route.a = 1 - route.a
			route.b = 1 - route.b
	for town in region.map.towns:
		town.open_lanes = 2
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
	finish()


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
