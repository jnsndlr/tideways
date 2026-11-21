extends SceneTree
## A multi-stop schedule needs a suitable slip on every leg, including after the first.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var region := TinyRegion.build(3)
	var company := Scenario.from_network(region.map, ["Test ferry"], [4, 2, 2])
	var service := company.schedules[0]
	for island in region.map.islands:
		for slip in island.slips:
			slip.size = 2
	service.stops = [region.map.islands[0].key, region.map.islands[1].key, region.map.islands[2].key]
	var last := region.map.islands[2]
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
	sim.free()
	if not rejected or not accepted:
		push_error("A size-four boat must be rejected at a small slip on a later leg, then accepted after refitting it to medium.")
		quit(1)
		return
	print("TEST PASSED")
	quit(0)
