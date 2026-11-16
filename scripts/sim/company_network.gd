class_name CompanyNetwork
extends RefCounted
## The identity slice of a generated company's save. Geometry comes from the
## region. Records may move in the file; the order of slips within a lot matters.

class Assignment:
	var key: String
	var route: MapData.Route
	var display_name: String
	var size: int


var fleet: Array[Assignment] = []


static func _island_record(map: MapData, island: MapData.Island) -> Dictionary:
	var slips: Array[String] = []
	for route_id in island.slips:
		slips.append(map.routes[route_id].key)
	return {"key": island.key, "terminal": island.has_terminal, "slips": slips}


static func _route_record(map: MapData, route: MapData.Route) -> Dictionary:
	return {"key": route.key, "a": map.islands[route.a].key, "b": map.islands[route.b].key}


static func capture(sim: Simulation) -> String:
	var map := sim.map
	var islands := []
	var routes := []
	var ferries := []
	for island in map.islands:
		islands.append(_island_record(map, island))
	for route in map.routes:
		routes.append(_route_record(map, route))
	for ferry in sim.ferries:
		ferries.append({"key": ferry.fleet_key, "route": ferry.route.key,
			"name": ferry.ferry_name, "size": ferry.fc.size})
	# JSON numbers are parsed as doubles. Keep the entire int64 seed.
	return JSON.stringify({"seed": str(map.map_seed), "islands": islands,
		"routes": routes, "ferries": ferries})


func read(saved_json: String, map: MapData) -> String:
	var saved = JSON.parse_string(saved_json)
	if not saved is Dictionary or saved.get("seed") != str(map.map_seed):
		return "Invalid company network or wrong region seed"
	var expected_islands := {}
	for island in map.islands:
		expected_islands[island.key] = _island_record(map, island)
	var error := _match_records(saved.get("islands"), expected_islands, map.islands.size(), "island")
	if not error.is_empty():
		return error
	var expected_routes := {}
	var route_by_key := {}
	for route in map.routes:
		expected_routes[route.key] = _route_record(map, route)
		route_by_key[route.key] = route
	error = _match_records(saved.get("routes"), expected_routes, map.routes.size(), "route")
	if not error.is_empty():
		return error
	if not saved.get("ferries") is Array:
		return "Missing ferry records"
	var restored: Array[Assignment] = []
	var seen := {}
	for record in saved.ferries:
		if not record is Dictionary or not _valid_key(record.get("key")):
			return "Missing ferry key"
		if seen.has(record.key):
			return "Duplicate ferry key: %s" % record.key
		if not _valid_key(record.get("route")) or not route_by_key.has(record.route):
			return "Ferry %s references an unknown route" % record.key
		var size = record.get("size")
		if not record.get("name") is String or not size is float or size != floor(size) or size < 1 or size > 5:
			return "Invalid name or size for ferry %s" % record.key
		var hull := Assignment.new()
		hull.key = record.key
		hull.route = route_by_key[record.route]
		hull.display_name = record.name
		hull.size = int(size)
		restored.append(hull)
		seen[hull.key] = true
	fleet = restored
	return ""


static func _valid_key(value: Variant) -> bool:
	return value is String and not value.is_empty()


static func _match_records(records: Variant, expected: Dictionary, count: int, kind: String) -> String:
	if expected.size() != count or expected.has(""):
		return "Missing or duplicate %s key in region" % kind
	if not records is Array or records.size() != count:
		return "Wrong %s record count" % kind
	var seen := {}
	for record in records:
		if not record is Dictionary or not _valid_key(record.get("key")):
			return "Missing %s key" % kind
		if seen.has(record.key):
			return "Duplicate %s key: %s" % [kind, record.key]
		if not expected.has(record.key):
			return "Unknown %s key: %s" % [kind, record.key]
		seen[record.key] = true
	for record in records:
		# Comparing topology also rejects a known key attached to another endpoint
		# or a terminal whose saved slip order no longer fits the physical lot.
		if record != expected[record.key]:
			return "Saved %s %s differs from region topology: expected %s, got %s" % [
				kind, record.key, expected[record.key], record]
	return ""
