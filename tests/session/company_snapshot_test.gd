extends "res://tests/rule_test_case.gd"
## A private rebuilt company resumes service with the paid lane, deck and cash intact.

const DT := 0.1
var _last_target: WeakRef


func _initialize() -> void:
	call_deferred("_run")


func _world(relief := false) -> Simulation:
	var region := TinyRegion.build()
	for town in region.map.towns:
		town.open_lanes = 2
		town.lane_extension_price = 150
	var scenario := Scenario.from_network(region.map, ["Snapshot boat"], [3])
	if relief:
		var extra := Scenario.Boat.new()
		extra.key = "relief"
		extra.name = "Relief boat"
		extra.size = 2
		scenario.fleet.append(extra)
		var second := Scenario.Schedule.new()
		second.boat = extra.key
		second.stops = scenario.schedules.front().stops.duplicate()
		scenario.schedules.append(second)
	var sim := Simulation.new(VehicleFactory.create, true, false)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	_last_target = weakref(sim)
	return sim


func _empty_queues(sim: Simulation) -> void:
	for term: Terminal in sim.terminals.values():
		for lanes: Array in term.lanes.values():
			for lane: TerminalLane in lanes:
				lane.queue.clear()
		term.passenger_queue.clear()
	for node in sim.traffic.get_children() + sim.passengers.get_children():
		node.free()


func _enqueue(term: Terminal, paint: int) -> Vehicle:
	var car := VehicleFactory.from_parts(false, "sedan_compact", paint)
	var dest := term.lane_keys()[0]
	var lane: TerminalLane = term.lanes[dest][0]
	car.moving_traffic = term.sim.moving_vehicles
	term.sim.traffic.add_child(car)
	car.dest = dest
	car.lane_v = lane.v
	car.lot_arrival = term.sim.abs_minutes()
	car.position = term.queue_position(lane.v, lane.queued_slots(), car)
	car.rotation.y = atan2(term.town.dock_dir.x, term.town.dock_dir.z)
	car.straighten()
	lane.enqueue(car.get_instance_id(), car.slots)
	return car


func _step(ferry: Ferry) -> void:
	var sim := ferry.sim
	var minutes := Units.game_minutes(DT)
	sim.minutes += minutes
	for term: Terminal in sim.terminals.values():
		if term.build_remaining > 0:
			term._advance_construction(minutes)
		for ramp in term.slip_ramps:
			if ramp:
				ramp._process(DT)
	ferry.pay_crew(minutes)
	ferry._process(DT)
	for car: Vehicle in sim.traffic.get_children():
		if not car.path.is_empty() and not car.is_queued_for_deletion():
			car._process(DT)


func _save(sim: Simulation) -> Dictionary:
	return JSON.parse_string(JSON.stringify(CompanySnapshot.capture(sim), "", true, true))


func _run() -> void:
	var live := _world()
	_empty_queues(live)
	var ferry := live.ferries[0]
	ferry.ferry_name = "Renamed after purchase"
	ferry.assign_captain(Captain.roster()[1])
	ferry.set_pace(FerryPace.ECONOMY)
	var port := ferry.here()
	var destination := ferry.destination()
	check(port.buy_holding_lane(), "Buy the $150 lane before sailing")
	_enqueue(port, 2)
	_enqueue(destination, 4)
	for frame in 8000:
		_step(ferry)
		if ferry.state == Ferry.State.SAILING and ferry.traveled >= ferry.run_length() * 0.45:
			break
	check(
		ferry.state == Ferry.State.SAILING and ferry.aboard.size() == 1,
		"Save an actual paid crossing"
	)
	ferry.assign_captain(Captain.roster()[0])
	ferry.set_timetable([420, 780])
	live.rng.randi()
	var saved := _save(live)
	if saved.is_empty():
		check(false, "Company snapshot captures the entire supported company")
		live.free()
		finish()
		return
	var outgoing := VehicleFactory.from_parts(false, "sedan_compact", 1)
	live.traffic.add_child(outgoing)
	check(CompanySnapshot.capture(live).is_empty(), "Decline an unowned road vehicle")
	outgoing.free()
	var source_ref: WeakRef = weakref(live)
	_check_failures(saved, live)
	var restored := CompanySnapshot.restore(saved, _world, VehicleFactory.from_parts)
	check(restored != null, "Restore all components into a newly built company")
	if restored != null:
		var hull := restored.ferries[0]
		check(
			hull.fleet_key == ferry.fleet_key and hull.ferry_name == ferry.ferry_name,
			"Restore the renamed ferry by permanent hull key"
		)
		check(
			hull.aboard.size() == 1 and hull.aboard[0].body_paint == ferry.aboard[0].body_paint,
			"The same paid vehicle stays on the same crossing"
		)
		check(
			(
				hull.position.is_equal_approx(ferry.position)
				and is_equal_approx(hull.traveled, ferry.traveled)
			),
			"Reopen at the saved voyage position"
		)
		check(
			restored.ledger.today.purchases == 150.0 and restored.ledger.cars_total == 1,
			"Restoring a purchase and a paid deck posts no transactions"
		)
		check(
			(
				restored.rng.randi() == live.rng.randi()
				and absf(restored.minutes - live.minutes) < 1e-10
			),
			"Restore the simulation clock and next random draw"
		)
		var resumed_receipt := _next_receipt(restored)
		var original_receipt := _next_receipt(live)
		# The JSON decimal boundary can change binary64 costs below one cent.
		for key in ["crew", "fuel", "fares", "purchases", "sales"]:
			check(
				absf(resumed_receipt.today[key] - original_receipt.today[key]) < 1e-8,
				"The next settlement posts the same %s" % key
			)
		check(
			(
				absf(resumed_receipt.cash - original_receipt.cash) < 1e-8
				and resumed_receipt.cars_total == original_receipt.cars_total
				and resumed_receipt.revenue_total == original_receipt.revenue_total
			),
			"The next fare and final company balance match uninterrupted service"
		)
		restored.free()
	check(source_ref.get_ref() == live, "The original company remains available")
	live.free()
	_check_relief_fleet()
	finish()


func _next_receipt(sim: Simulation) -> Dictionary:
	for frame in 8000:
		_step(sim.ferries[0])
		if sim.ledger.cars_total == 2:
			break
	check(
		sim.ledger.cars_total == 2 and sim.ledger.revenue_total == 36,
		"Two vehicle boardings earn exactly $36"
	)
	return sim.ledger.snapshot(sim.map.routes)


func _check_failures(saved: Dictionary, live: Simulation) -> void:
	var unknown := saved.duplicate(true)
	unknown.version = 999
	check(
		CompanySnapshot.restore(unknown, _world, VehicleFactory.from_parts) == null,
		"Reject unknown whole-company formats"
	)
	var damaged := saved.duplicate(true)
	damaged.clock.rng_state = "not a state"
	check(
		CompanySnapshot.restore(damaged, _world, VehicleFactory.from_parts) == null,
		"Reject invalid late data after preparing the fleet and purchases"
	)
	check(
		_last_target.get_ref() == null and _save(live) == saved,
		"Discard the failed private world and keep the live company intact"
	)
	var older := saved.duplicate(true)
	for term: Dictionary in older.terminals.values():
		term.holding.version = 1
		for group: Array in term.holding.lanes.values():
			for lane: Dictionary in group:
				lane.erase("approaching")
		term.refit.version = 1
		for slip: Dictionary in term.refit.slips:
			slip.erase("building")
	var old_world := CompanySnapshot.restore(older, _world, VehicleFactory.from_parts)
	check(old_world != null, "Compose legacy settled-queue and widening records")
	if old_world != null:
		old_world.free()


func _check_relief_fleet() -> void:
	var sim := _world(true)
	var first := sim.ferries[0]
	first._load_phase = Ferry.LoadPhase.VEHICLES
	var relief := sim.ferries[1]
	check(not relief.aboard.is_empty(), "Generated relief hull starts with a prefilled deck")
	var saved := _save(sim)
	if saved.is_empty():
		check(false, "Capture two independently identified hulls sharing a route")
		sim.free()
		return
	check(not saved.reservations.is_empty(), "At least one hull owns a real shared approach")
	saved.network.ferries.reverse()
	var restored := CompanySnapshot.restore(saved, _world.bind(true), VehicleFactory.from_parts)
	check(restored != null, "Restore both ordinary voyages despite reordered fleet records")
	if restored != null:
		var result := _save(restored)
		check(
			(
				not result.is_empty()
				and result.reservations == saved.reservations
				and restored.ferries[1].fleet_key == relief.fleet_key
				and restored.ferries[1].aboard.size() == relief.aboard.size()
			),
			"Keep the saved corridor owner and replace the generated starter deck once"
		)
		restored.free()
	sim.free()
