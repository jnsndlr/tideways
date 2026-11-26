class_name WorkingSlipHistory
extends RefCounted
## Moving a route rebakes its existing curve. Replaying every successful move in
## order reproduces both ends even when a route returns to its original slip.

var moves: Array[Dictionary] = []
var _expected := {}


func remember(map: MapData) -> void:
	_expected = _assignments(map)
	moves.clear()


static func _assignments(map: MapData) -> Dictionary:
	var result := {}
	for town in map.dock_towns():
		for i in town.slips.size():
			if not town.slips[i].routes.is_empty():
				result[Vector2i(town.id, i)] = town.slips[i].routes.duplicate()
	return result


func matches(map: MapData) -> bool:
	return _expected == _assignments(map)


func moved(town: MapData.Town, route: MapData.Route, from: int, to: int) -> void:
	var old := Vector2i(town.id, from)
	var target := Vector2i(town.id, to)
	if _expected.has(old):
		_expected[old].erase(route.id)
		if _expected[old].is_empty():
			_expected.erase(old)
	if not _expected.has(target):
		_expected[target] = []
	_expected[target].append(route.id)
	moves.append({"town": town.key, "route": route.key, "from": from, "to": to})


func capture(map: MapData) -> Dictionary:
	return {"moves": moves.duplicate(true), "shapes": _shapes(map)}


func _shapes(map: MapData) -> Dictionary:
	var shapes := {}
	for move in moves:
		shapes[move.route] = ""
	for route in map.routes:
		if shapes.has(route.key):
			shapes[route.key] = _shape(route)
	return shapes


static func supports(record: Variant) -> bool:
	return (
		record is Dictionary
		and record.get("moves") is Array
		and not record.moves.is_empty()
		and record.get("shapes") is Dictionary
		and not record.shapes.is_empty()
	)


func restore(record: Dictionary, sim: Simulation) -> bool:
	if not supports(record):
		return false
	var routes := {}
	for r in sim.map.routes:
		routes[r.key] = r
	for move in record.moves:
		if not _replay_move(move, sim, routes):
			return false
	if record.shapes != _shapes(sim.map):
		return false
	if sim.marine:
		sim.marine.refresh_corridors()
	return true


static func _replay_move(move: Variant, sim: Simulation, routes: Dictionary) -> bool:
	if not move is Dictionary or not move.get("town") is String or not move.get("route") is String:
		return false
	var town := sim.map.town_by_key(move.town)
	var route: MapData.Route = routes.get(move.route)
	if town == null or route == null or town.id not in [route.a, route.b]:
		return false
	var term: Terminal = sim.terminals.get(town.id)
	if term == null or not _working(town, move.get("from")) or not _working(town, move.get("to")):
		return false
	if move.from == move.to or int(move.from) != town.slip_index(route.id):
		return false
	return term.move_route_now(route.id, int(move.to))


static func _working(town: MapData.Town, index: Variant) -> bool:
	if not CompanySnapshot._integer_in(index, 0, town.slips.size() - 1):
		return false
	var slip := town.slips[int(index)]
	return not slip.building and not slip.tie_up


static func _shape(route: MapData.Route) -> String:
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	hash.update(route.curve.get_baked_points().to_byte_array())
	return hash.finish().hex_encode()
