class_name CompanyNetwork
extends RefCounted
## The identity slice of a generated company's save. Geometry comes from the
## region. Records may move in the file; the order of slips within a lot matters.

class Assignment:
	var key: String
	var route: MapData.Route
	var display_name: String
	var purchased := false
	var size: int


var fleet: Array[Assignment] = []


static func _town_record(map: MapData, town: MapData.Town, legacy := false) -> Dictionary:
	var slips: Array[String] = []
	for slip in town.slips:
		var keys: PackedStringArray = []
		for route_id in slip.routes:
			keys.append(_route_record(map, map.routes[route_id], true).key if legacy else map.routes[route_id].key)
		slips.append("+".join(keys) if not keys.is_empty() else "idle")
	return {"key": map.island_of(town).key if legacy else town.key, "terminal": town.built, "slips": slips}


static func _route_record(map: MapData, route: MapData.Route, legacy := false) -> Dictionary:
	if legacy:
		var a := map.island_of(map.towns[route.a]).key
		var b := map.island_of(map.towns[route.b]).key
		return {"key": "link-%s-%s" % [a, b], "a": a, "b": b}
	return {"key": route.key, "a": map.towns[route.a].key, "b": map.towns[route.b].key}


static func capture(sim: Simulation) -> String:
	return JSON.stringify(record(sim))


static func record(sim: Simulation) -> Dictionary:
	var map := sim.map
	var towns := []
	var routes := []
	var ferries := []
	for town in map.towns:
		towns.append(_town_record(map, town))
	for route in map.routes:
		routes.append(_route_record(map, route))
	for ferry in sim.ferries:
		var row := {
			"key": ferry.fleet_key,
			"route": ferry.route.key,
			"name": ferry.ferry_name,
			"size": ferry.fc.size
		}
		if ferry.purchased:
			row.purchased = true
		ferries.append(row)
	# JSON numbers are parsed as doubles. Keep the entire int64 seed.
	return {"seed": str(map.map_seed), "towns": towns, "routes": routes, "ferries": ferries}


func read(data: Variant, map: MapData) -> String:
	var saved: Variant = JSON.parse_string(data) if data is String else data
	if not saved is Dictionary or saved.get("seed") != str(map.map_seed):
		return "Invalid company network or wrong region seed"
	# Older generated-company records identify one terminal by its island. Validate
	# their original topology, then resolve the saved assignments to current routes.
	var legacy: bool = saved.has("islands") and not saved.has("towns")
	var expected_routes := {}
	var route_by_key := {}
	for route in map.routes:
		var record := _route_record(map, route, legacy)
		expected_routes[record.key] = record
		route_by_key[record.key] = route
	var error := _match_records(saved.get("routes"), expected_routes, map.routes.size(), "route")
	if not error.is_empty():
		return error
	if legacy:
		var islands := {}
		for island in map.islands:
			if island.towns.size() > 1:
				return "Legacy island assignment is ambiguous on a multi-town region"
			var record := {"key": island.key, "terminal": false, "slips": []}
			if not island.towns.is_empty():
				record = _town_record(map, map.towns[island.towns[0]], true)
			islands[island.key] = record
		error = _match_records(saved.islands, islands, map.islands.size(), "island")
	else:
		var towns := {}
		for town in map.towns:
			towns[town.key] = _town_record(map, town)
		error = _match_records(saved.get("towns"), towns, map.towns.size(), "town")
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
		if not record.get("name") is String or not _valid_size(size):
			return "Invalid name or size for ferry %s" % record.key
		if record.has("purchased") and (not record.purchased is bool or not record.purchased):
			return "Invalid purchase marker for %s" % record.key
		var hull := Assignment.new()
		hull.purchased = record.has("purchased")
		hull.key = record.key
		hull.route = route_by_key[record.route]
		hull.display_name = record.name
		hull.size = int(size)
		restored.append(hull)
		seen[hull.key] = true
	fleet = restored
	return ""


static func _valid_size(size: Variant) -> bool:
	return (
		(size is int or size is float)
		and size == floor(size)
		and size >= 1
		and size <= FerryClass.MAX_SIZE
	)


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
