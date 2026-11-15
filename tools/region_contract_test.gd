extends SceneTree
## Generated regions currently use array indices as IDs at simulation entry.

func _initialize() -> void:
	for seed_value in [121, 123]:
		var map := MapGenerator.new().generate(seed_value)
		var failure := inspect(map)
		if not failure.is_empty():
			push_error("Region seed %s: %s" % [seed_value, failure])
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
