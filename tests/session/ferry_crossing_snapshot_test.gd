extends "res://tests/rule_test_case.gd"
## Advance real board/arrive/unload callbacks in a controlled two-terminal region.
## Each resume gets a fresh network, traffic list, ledger and hull.
const DT := 0.1
const LIMIT := 8000


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_run_case(false)
	_run_case(true)
	finish()


func _run_case(reverse: bool) -> void:
	var live := _world()
	var ferry := live.ferries[0]
	if reverse:
		ferry.start_staggered(2)
	var outbound := ferry.here()
	var car := _enqueue(outbound, VehicleFactory.from_parts(false, "sedan_compact", 4))
	var rig := _enqueue(
		outbound, VehicleFactory.from_parts(true, "tractor_day", 2, "trailer_container", 5)
	)
	# Both cars are dispatched from a real terminal queue. Hold the rig on its
	# approach for the first save; its reserved spaces aren't yet in ferry.aboard.
	for frame in LIMIT:
		_step(ferry)
		if car in ferry.aboard and rig.fare_paid > 0 and rig not in ferry.aboard:
			break
	check(
		car in ferry.aboard and rig not in ferry.aboard and not rig.path.is_empty(),
		"One parked car and one rig still driving on"
	)
	check(
		live.cars_today == 2 and rig.fare_paid == 54,
		"The rig paid before reaching its reserved slots"
	)
	var boarding := _save(ferry)
	var half := ferry.run_length() / 2.0
	for frame in LIMIT:
		_step(ferry)
		if ferry.state == Ferry.State.SAILING and ferry.traveled >= half:
			break
	check(
		ferry.state == Ferry.State.SAILING and ferry.aboard == [car, rig],
		"The same two vehicles left together"
	)
	var crossing := _save(ferry)
	check(
		ferry.traveled >= half and ferry.traveled < half + 10,
		"Save halfway across the actual route"
	)
	var expected := _arrive_and_board_again(ferry)
	live.free()
	if boarding.is_empty() or crossing.is_empty():
		check(false, "Both supported checkpoints produced JSON")
	else:
		_compare_resume(boarding, expected)
		_compare_resume(crossing, expected)


func _world() -> Simulation:
	var region := TinyRegion.build()
	var sim := Simulation.new(VehicleFactory.create, true, false)
	root.add_child(sim)
	var scenario := Scenario.from_network(region.map, ["Snapshot ferry"], [3])
	sim.setup(region.map, region.terrain, scenario)
	sim.ferries[0].set_pace(FerryPace.ECONOMY)
	sim.ferries[0].assign_captain(Captain.roster()[1])
	for terminal: Terminal in sim.terminals.values():
		terminal.passenger_queue.clear()
		for lanes: Array in terminal.lanes.values():
			for lane: TerminalLane in lanes:
				lane.queue.clear()
	for node in sim.traffic.get_children():
		node.free()
	for node in sim.passengers.get_children():
		node.free()
	return sim


func _enqueue(term: Terminal, car: Vehicle) -> Vehicle:
	var dest := term.lane_keys()[0]
	var lane: TerminalLane = term.lanes[dest][0]
	car.moving_traffic = term.sim.moving_vehicles
	term.sim.traffic.add_child(car)
	car.position = term.queue_position(lane.v, lane.queued_slots(), car)
	car.rotation.y = atan2(term.town.dock_dir.x, term.town.dock_dir.z)
	car.straighten()
	car.lane_v = lane.v
	car.dest = dest
	lane.enqueue(car.get_instance_id(), car.slots)
	return car


func _step(ferry: Ferry) -> void:
	var minutes := Units.game_minutes(DT)
	ferry.sim.minutes += minutes
	for term: Terminal in ferry.sim.terminals.values():
		for ramp in term.slip_ramps:
			if ramp:
				ramp._process(DT)
	ferry.pay_crew(minutes)
	ferry._process(DT)
	for car: Vehicle in ferry.sim.traffic.get_children():
		if not car.path.is_empty() and not car.is_queued_for_deletion():
			car._process(DT)


func _save(ferry: Ferry) -> Dictionary:
	var voyage := FerryCrossingSnapshot.capture(ferry)
	if voyage.is_empty():
		return {}
	var sim := ferry.sim
	var poses := {}
	for car: Vehicle in ferry.aboard + ferry.sim.moving_vehicles:
		if not ferry.deck.occupants.has(car.get_instance_id()):
			continue
		var pose := [var_to_str(car.global_transform)]
		if car.trailer:
			pose.append(var_to_str(car.trailer.global_transform))
		poses[car.model] = pose
	var record := {
		"vehicle_poses": poses,
		"voyage": voyage,
		"ledger": sim.ledger.snapshot(sim.map.routes),
		"position": [ferry.position.x, ferry.position.y, ferry.position.z],
		"heading": ferry.rotation.y,
		"day": sim.day,
		"minutes": sim.minutes,
	}
	return JSON.parse_string(JSON.stringify(record, "", true, true))


func _compare_resume(saved: Dictionary, expected: Dictionary) -> void:
	var sim := _world()
	var ferry := sim.ferries[0]
	sim.ledger = CompanyLedgerSnapshot.restore(saved.ledger, sim.map.routes)
	sim.day = int(saved.day)
	sim.minutes = saved.minutes
	var wrong_call: Dictionary = saved.voyage.duplicate(true)
	wrong_call.call = 1 - int(wrong_call.call)
	check(
		not FerryCrossingSnapshot.restore(wrong_call, ferry, VehicleFactory.from_parts),
		"Reject a timetable call inconsistent with the crossing direction"
	)
	var bad: Dictionary = saved.voyage.duplicate(true)
	bad.vehicles.append({})
	var before := sim.traffic.get_child_count()
	check(
		not FerryCrossingSnapshot.restore(bad, ferry, VehicleFactory.from_parts),
		"Reject a bad manifest after staging valid vehicles"
	)
	check(
		(
			ferry.aboard.is_empty()
			and sim.traffic.get_child_count() == before
			and ferry.deck.occupants.count(0) == ferry.deck.occupants.size()
		),
		"Failed restore leaves the hull, reservations and traffic empty"
	)
	var restored := FerryCrossingSnapshot.restore(saved.voyage, ferry, VehicleFactory.from_parts)
	check(restored, "Restore %s into a fresh simulation" % saved.voyage.phase)
	if restored:
		var replay := _save(ferry)
		check(
			replay == saved,
			"Restored position, paths, slots, vehicles and ledger match serialized checkpoint"
		)
		check(
			sim.cars_today == 2 and sim.revenue_today == 72,
			"Installing a paid rig does not credit another fare"
		)
		check(
			_arrive_and_board_again(ferry) == expected,
			"Restored sailing matches uninterrupted unloading and next fare"
		)
	sim.free()


func _arrive_and_board_again(ferry: Ferry) -> Dictionary:
	# Place one new paying car at the far terminal to prove the next transaction.
	var next := _enqueue(ferry.destination(), VehicleFactory.from_parts(false, "sedan_compact", 1))
	var unloading: Array[String] = []
	for frame in LIMIT:
		_step(ferry)
		if ferry.state == Ferry.State.UNLOADING and unloading.is_empty():
			for car in ferry._unload_queue:
				unloading.append(car.model)
		if next.fare_paid > 0:
			break
	check(
		unloading.size() == 2 and "tractor_day" in unloading and "sedan_compact" in unloading,
		"Both original vehicles unload at their destination"
	)
	check(
		next.fare_paid == 18 and ferry.sim.cars_today == 3 and ferry.sim.revenue_today == 90,
		"Only the next boarding adds a third fare"
	)
	return {
		"ledger": ferry.sim.ledger.snapshot(ferry.sim.map.routes),
		"unloading": unloading,
		"trips": ferry.trips,
		"arrival_terminal": ferry.here().town.key,
		"last_crossing": ferry.last_crossing,
		"last_fuel": ferry.last_crossing_fuel,
	}
