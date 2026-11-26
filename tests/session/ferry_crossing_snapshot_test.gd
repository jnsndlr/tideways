extends "res://tests/rule_test_case.gd"
## Advance real board/arrive/unload callbacks in a controlled two-terminal region.
## Each resume gets a fresh network, traffic list, ledger and hull.
const DT := 0.1
const LIMIT := 8000


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_midnight()
	_castaway_pose()
	_run_case(false)
	_run_case(true)
	finish()


func _castaway_pose() -> void:
	var live := _world()
	var hull := live.ferries[0]
	hull.state = Ferry.State.SAILING
	hull.itinerary.call = 1
	hull.traveled = 30
	hull._lie = 0.018
	hull.place_underway()
	var visible := hull.global_transform
	hull._update_lie(DT)
	check(
		hull._lie < 0.018 and hull.global_transform == visible,
		"Landing angle eases after the visible castaway pose is applied"
	)
	var copy := _world()
	var record := FerryCrossingSnapshot.capture(hull)
	check(
		FerryCrossingSnapshot.restore(record, copy.ferries[0], VehicleFactory.from_parts),
		"Restore the first sailing pose"
	)
	check(
		(
			copy.ferries[0].global_transform.is_equal_approx(visible)
			and copy.ferries[0]._lie == hull._lie
		),
		"Restore both the displayed pose and the angle for the next frame"
	)
	_step(hull)
	_step(copy.ferries[0])
	check(
		copy.ferries[0].global_transform.is_equal_approx(hull.global_transform),
		"The next sailing frame stays in step"
	)
	var older := _world()
	record.version = 4
	record.erase("sailing_pose")
	check(
		FerryCrossingSnapshot.restore(record, older.ferries[0], VehicleFactory.from_parts),
		"Read a previous crossing without an applied pose"
	)
	older.free()
	copy.free()
	live.free()


func _midnight() -> void:
	var live := Simulation.new(Callable())
	var restored := Simulation.new(Callable())
	live.rng.seed = 123
	restored.rng.seed = 123
	live.day = 19
	live.minutes = 1439.875
	live.rng.randi()
	var record = JSON.parse_string(
		JSON.stringify(CompanyClockSnapshot.capture(live), "", true, true)
	)
	check(CompanyClockSnapshot.restore(record, restored), "Read the minute before midnight")
	var half_minute := 0.5 / Units.MINUTES_PER_SECOND
	live._process(half_minute)
	restored._process(half_minute)
	check(live.day == 20 and restored.day == 20, "Both companies roll over exactly once")
	check(
		restored.minutes == 0.375 and restored.minutes == live.minutes,
		"Midnight preserves the fractional remainder"
	)
	check(restored.rng.randi() == live.rng.randi(), "Same next random draw across midnight")
	live.free()
	restored.free()


func _run_case(reverse: bool) -> void:
	var live := _world()
	# Move past the rebuilt region's initial calendar and random sequence.
	live.day += 3
	live.minutes += 0.375
	live.rng.randi()
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
	# The next paying vehicle is already on the road at the other end.
	# Its approach and the paid rig's boarding callback belong to different owners.
	ferry.destination()._spawn_car()
	check(live.moving_vehicles.size() >= 2, "Both the approaching car and paid rig are moving")
	var boarding := _save(ferry)
	var casting_off := {}
	var departure_minute := -1.0
	var half := ferry.run_length() / 2.0
	for frame in LIMIT:
		_step(ferry)
		if (
			casting_off.is_empty()
			and ferry._casting_off
			and ferry._ramp(ferry.here()).apron_fraction >= 0.4
		):
			casting_off = _save(ferry)
		if departure_minute < 0 and ferry.state == Ferry.State.SAILING:
			departure_minute = live.minutes
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
	if boarding.is_empty() or casting_off.is_empty() or crossing.is_empty():
		check(false, "Paid boarding, casting off and crossing all produced JSON")
	else:
		_compare_resume(boarding, expected)
		_compare_resume(casting_off, expected, departure_minute)
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
	var lots := {}
	for term: Terminal in sim.terminals.values():
		var holding := TerminalHoldingSnapshot.capture(term)
		if holding.is_empty():
			return {}
		lots[term.town.key] = holding
	var record := {
		"lots": lots,
		"vehicle_poses": poses,
		"voyage": voyage,
		"ledger": sim.ledger.snapshot(sim.map.routes),
		"position": [ferry.position.x, ferry.position.y, ferry.position.z],
		"heading": ferry.rotation.y,
		"clock": CompanyClockSnapshot.capture(sim),
	}
	return JSON.parse_string(JSON.stringify(record, "", true, true))


func _compare_resume(saved: Dictionary, expected: Dictionary, departure_minute := -1.0) -> void:
	var sim := _world()
	var ferry := sim.ferries[0]
	sim.ledger = CompanyLedgerSnapshot.restore(saved.ledger, sim.map.routes)
	_check_clock_rejections(saved.clock, sim)
	check(CompanyClockSnapshot.restore(saved.clock, sim), "Restore the company clock and RNG")
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
	# Install the queues before reconnecting the paid rig to its departure lane.
	for term: Terminal in sim.terminals.values():
		check(
			TerminalHoldingSnapshot.restore(
				saved.lots[term.town.key], term, VehicleFactory.from_parts
			),
			"Reconnect terminal traffic at %s" % term.town.key
		)
	if saved.voyage.phase == "casting_off":
		var impossible := saved.voyage.duplicate(true) as Dictionary
		impossible.lifting_ramp = [0.5, 0.5]
		check(
			not FerryCrossingSnapshot.restore(impossible, ferry, VehicleFactory.from_parts),
			"Reject a span raised before its apron cleared"
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
		if departure_minute >= 0:
			for i in LIMIT:
				_step(ferry)
				if ferry.state == Ferry.State.SAILING:
					break
			check(
				ferry.state == Ferry.State.SAILING and absf(sim.minutes - departure_minute) < 1e-8,
				"The restored apron clears and the ferry departs on the original tick"
			)
		check(
			_arrive_and_board_again(ferry) == expected,
			"Restored sailing matches uninterrupted unloading and next fare"
		)
	sim.free()


func _check_clock_rejections(record: Dictionary, sim: Simulation) -> void:
	var before := CompanyClockSnapshot.capture(sim)
	for change: Dictionary in [
		{"day": -1},
		{"minutes": 1440},
		{"minutes": NAN},
		{"version": 2},
		{"seed": "wrong region"},
		{"rng_state": 123.0},
		{"rng_state": "9223372036854775808"}
	]:
		var damaged := record.duplicate()
		damaged.merge(change, true)
		check(not CompanyClockSnapshot.restore(damaged, sim), "Reject damaged clock %s" % change)
		check(CompanyClockSnapshot.capture(sim) == before, "Failed restore preserves clock and RNG")


func _arrive_and_board_again(ferry: Ferry) -> Dictionary:
	var next: Vehicle
	for car: Vehicle in ferry.sim.traffic.get_children():
		if car.dest == ferry.here().town.id:
			next = car
			break
	check(next != null, "The vehicle approaching the far terminal survives the save")
	if next == null:
		return {}
	var fare := ferry.sim.ledger.vehicle_fare_for(ferry.route.id) * next.fare_multiplier()
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
		(
			next.fare_paid == fare
			and ferry.sim.cars_today == 3
			and ferry.sim.revenue_today == 72 + fare
		),
		"Only the next boarding adds a third fare"
	)
	return {
		"ledger": ferry.sim.ledger.snapshot(ferry.sim.map.routes),
		"unloading": unloading,
		"trips": ferry.trips,
		"arrival_terminal": ferry.here().town.key,
		"next_random_draw": ferry.sim.rng.randi(),
		"last_crossing": ferry.last_crossing,
		"last_fuel": ferry.last_crossing_fuel,
	}
