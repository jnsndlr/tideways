extends SceneTree
## Generated regions currently use array indices as IDs at simulation entry.

func _initialize() -> void:
	var fixture: MapData
	for seed_value in [121, 123]:
		var mainland := Mainland.new(seed_value, 4000.0)
		for end in [-20000.0, 20000.0]:
			if minf(mainland.shore_w(end, 0), mainland.shore_w(end, 1)) < 500.0:
				push_error("Both channel ends need open water between their ranges")
				quit(1)
				return
		fixture = MapGenerator.new().generate(seed_value)
		var failure := inspect(fixture)
		if not failure.is_empty():
			push_error("Region seed %s: %s" % [seed_value, failure])
			quit(1)
			return
	# Use generated, valid data as the control. Each mutation breaks one reference.
	fixture.islands.reverse()
	if not inspect(fixture).contains("runtime index"):
		push_error("Region check accepted reordered runtime island IDs")
		quit(1)
		return
	fixture.islands.reverse()
	var route := fixture.routes[0]
	fixture.islands[route.a].slips.append(fixture.routes.size())
	if not inspect(fixture).contains("missing route"):
		push_error("Region check accepted a dangling terminal slip")
		quit(1)
		return
	print("TEST PASSED")
	quit(0)


func inspect(map: MapData) -> String:
	if map.routes.is_empty():
		return "no sailing routes"
	for i in map.islands.size():
		var island := map.islands[i]
		if island.id != i:
			return "island ID differs from its runtime index at %s" % i
		for rid in island.slips:
			if rid < 0 or rid >= map.routes.size():
				return "island %s references missing route %s" % [i, rid]
			var route := map.routes[rid]
			if i != route.a and i != route.b:
				return "island %s has a slip for unrelated route %s" % [i, rid]
	for i in map.routes.size():
		var route := map.routes[i]
		if route.id != i or route.a == route.b:
			return "invalid route identity or endpoints at %s" % i
		if route.curve == null or route.length <= 0.0:
			return "route %s has no navigable length" % i
		for endpoint: int in [route.a, route.b]:
			if endpoint < 0 or endpoint >= map.islands.size():
				return "route %s references missing island %s" % [i, endpoint]
			var island := map.islands[endpoint]
			if not island.has_terminal or island.slips.count(i) != 1:
				return "route %s needs exactly one terminal slip at %s" % [i, endpoint]
	return ""
