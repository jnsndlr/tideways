extends "res://tests/rule_test_case.gd"
## Build independent test companies on the same region and step their production traffic.

const DT := 0.1
var _last_target: WeakRef


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
