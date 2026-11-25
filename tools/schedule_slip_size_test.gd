extends SceneTree
## A multi-stop schedule needs a suitable slip on every leg, including after the first.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var region := TinyRegion.build(3)
	var company := Scenario.from_network(region.map, ["Test ferry"], [4, 2, 2])
	var service := company.schedules[0]
	for island in region.map.towns:
		for slip in island.slips:
			slip.size = 2
	service.stops = [region.map.towns[0].key, region.map.towns[1].key, region.map.towns[2].key]
	service.departures = [390, 1085]
	var last := region.map.towns[2]
	# The 1 -> 2 leg is after the first and has a different berth from the 2 -> 0 leg.
	var berth := last.slips[last.slip_index(region.map.routes[2].id)]
	berth.size = 1
	var sim := Simulation.new()
	root.add_child(sim)
	sim.setup(region.map, region.terrain, company)
	var rejected := sim.ferries.size() == 2
	for ferry in sim.ferries:
		rejected = rejected and ferry.fleet_key != service.boat
	sim.free()
	berth.size = 2
	sim = Simulation.new()
	root.add_child(sim)
	sim.setup(region.map, region.terrain, company)
	var accepted := sim.ferries.size() == 3 and sim.ferries[0].fleet_key == service.boat
	if accepted:
		var ferry := sim.ferries[0]
		var ids: Array[int] = [0, 1, 2]
		accepted = ferry.timetable == service.departures
		accepted = accepted and not sim.reschedule(ferry, ids, [-1]) and not sim.reschedule(ferry, ids, [1440])
		# Another slip at the town that fits is used instead (TID-329)...
		berth.size = 1
		accepted = accepted and sim.stops_problem(ferry, ids) == ""
		# ...but with none big enough there, she's refused.
		for slip in last.slips:
			slip.size = 1
		accepted = accepted and sim.stops_problem(ferry, ids) != ""
		accepted = accepted and sim.leg_problem(ferry, -1, 0) != ""
	sim.free()
	if not rejected or not accepted:
		push_error("Schedule spawn/edit failed to enforce both berths, preserve authored departures, or reject invalid inputs.")
		quit(1)
		return
	print("TEST PASSED")
	quit(0)
