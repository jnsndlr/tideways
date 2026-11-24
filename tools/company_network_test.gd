extends SceneTree
## Save a live generated network through JSON, then reopen its fleet against
## fresh region objects. Source order, hull names and runtime indices can change.

func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var error := _round_trip()
	if not error.is_empty():
		push_error(error)
		quit(1)
		return
	print("TEST PASSED")
	quit(0)


func _round_trip() -> String:
	var generator := MapGenerator.new()
	var map := generator.generate(123)
	var original := Simulation.new(VehicleFactory.create)
	root.add_child(original)
	original.setup(map, generator.terrain)
	var first := original.ferries[0]
	var first_key := first.fleet_key
	var route_key := first.route.key
	var endpoint_a := first.term_a.town.key
	var endpoint_b := first.term_b.town.key
	var original_route_index := first.route.id
	var old_size := first.fc.size
	first.ferry_name = "Renamed ferry"
	# A second hull has the same assignment and display name, but its own identity.
	original._spawn_ferry("relief-boat", first.route, first.ferry_name, 5)
	var saved: Dictionary = JSON.parse_string(CompanyNetwork.capture(original))
	original.free()
	for group in ["towns", "routes", "ferries"]:
		saved[group].reverse()
	var file := FileAccess.create_temp(FileAccess.WRITE_READ, "tideways-company", "json")
	if file == null:
		return "Could not create temporary save"
	file.store_string(JSON.stringify(saved))
	file.flush()
	var contents := FileAccess.get_file_as_string(file.get_path_absolute())
	var fresh := MapGenerator.new()
	var region := fresh.generate(123)
	# Dense runtime IDs remain valid even though the source ordering is different.
	region.routes.reverse()
	for i in region.routes.size():
		region.routes[i].id = i
	for island in region.towns:
		for slip in island.slips:
			for i in slip.routes.size():
				slip.routes[i] = region.routes.size() - 1 - slip.routes[i]
	var restored := Simulation.new(VehicleFactory.create)
	root.add_child(restored)
	var error := restored.setup_from_network(region, fresh.terrain, contents)
	if error.is_empty():
		error = _verify_assignments(restored, first_key, route_key, endpoint_a, endpoint_b,
			original_route_index, old_size, saved.ferries.size())
	restored.free()
	if not error.is_empty():
		return error
	var legacy := CompanyNetwork.new()
	var previous := FileAccess.get_file_as_string("res://tools/fixtures/company_network_islands_seed123.json")
	error = legacy.read(previous, region)
	if not error.is_empty():
		return error
	if legacy.fleet.size() != 4 or legacy.fleet[0].key != "hull-0" or legacy.fleet[0].route.key != route_key:
		return "Legacy island-keyed fleet lost its original route assignment"
	return _reject_corruption(region, fresh.terrain, saved)


func _verify_assignments(sim: Simulation, first_key: String, route_key: String, a: String,
		b: String, old_index: int, old_size: int, count: int) -> String:
	if sim.ferries.size() != count:
		return "Restored the wrong fleet size"
	var checked := 0
	for ferry in sim.ferries:
		if ferry.fleet_key != first_key and ferry.fleet_key != "relief-boat":
			continue
		if ferry.route.key != route_key or ferry.route.id == old_index:
			return "Assignment followed the runtime route index"
		if ferry.term_a.town.key != a or ferry.term_b.town.key != b:
			return "Ferry restored to the wrong terminal pair"
		var size := old_size if ferry.fleet_key == first_key else 5
		if ferry.fc.size != size or ferry.ferry_name != "Renamed ferry":
			return "Renamed hull lost its identity or class"
		checked += 1
	if checked != 2:
		return "Both hulls must survive the shared assignment"
	return ""


func _reject_corruption(map: MapData, terrain: Terrain, saved: Dictionary) -> String:
	var target := Simulation.new(VehicleFactory.create)
	var cases := []
	for group in ["towns", "routes", "ferries"]:
		var duplicate := saved.duplicate(true)
		duplicate[group][0].key = duplicate[group][1].key
		cases.append([duplicate, "Duplicate"])
	var lost_route := saved.duplicate(true)
	lost_route.ferries[0].route = "missing-route"
	cases.append([lost_route, "unknown route"])
	var lost_endpoint := saved.duplicate(true)
	lost_endpoint.routes[0].a = "missing-town"
	cases.append([lost_endpoint, "topology"])
	var wrong_region := saved.duplicate(true)
	wrong_region.seed = "124"
	cases.append([wrong_region, "region seed"])
	var error := ""
	for pair in cases:
		var reason := target.setup_from_network(map, terrain, JSON.stringify(pair[0]))
		if not reason.contains(pair[1]) or target.map != null or target.get_child_count() != 0:
			error = "Expected %s rejection before building the scene, got '%s'" % [pair[1], reason]
			break
	target.free()
	return error
