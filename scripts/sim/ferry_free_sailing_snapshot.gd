class_name FerryFreeSailingSnapshot
extends RefCounted
## The route-independent steering order and the timetable to resume after it.
## The parent crossing record still owns the visible pose, cargo and accounts.


static func capture(f: Ferry) -> Dictionary:
	var plan := f.itinerary.suspended
	if plan == null or not f.manual or f.berth != Ferry.Berth.FREE:
		return {}
	var join := {}
	if not f._free_join.is_empty():
		var leg: MapData.Route = f._free_join[0]
		join = {
			"route": leg.key,
			"distance": f._free_join[1],
			"from": f.sim.map.towns[f._free_join[2]].key,
			"to": f.sim.map.towns[f._free_join[3]].key,
			"slip": f._free_join[4],
		}
	var path := []
	for point in f._free_path:
		path.append([point.x, point.y])
	return {
		"target": SnapshotVector3.encode(f._free_target),
		"path": path,
		"waypoint": f._free_wp,
		"yaw": f._free_yaw,
		"stuck": f._free_stuck,
		"join": join,
		"resume": f._orders._manual_resume_due,
		"stops": plan.stops.map(func(id): return f.sim.map.towns[id].key),
		"departures": plan.times.duplicate(),
		"stranded_cars": f.stranded_cars,
		"stranded_walkers": f.stranded_walk_ons,
		"refunds": f.stranded_refunds,
	}


## Set up the diverted service before terminal lanes are rebuilt in the private world.
static func prepare(r: Variant, service: Variant, f: Ferry) -> bool:
	if not r is Dictionary or not service is Dictionary or service.get("departures") != []:
		return false
	var stops := _stops(service.get("stops"), f)
	var original := _stops(r.get("stops"), f)
	if stops.is_empty() or original.is_empty() or not r.get("departures") is Array:
		return false
	var times: Array[int] = []
	for minute in r.departures:
		if not CompanySnapshot._integer_in(minute, 0, Timetable.DAY - 1):
			return false
		times.append(int(minute))
	var legs := _legs(original, f)
	var active_legs := _legs(stops, f)
	if legs.is_empty() or active_legs.is_empty():
		return false
	if not _restore_navigation(r, f):
		return false
	f.itinerary.suspended = FerryItinerary.Plan.new(original, legs, times)
	f.itinerary.set_circuit(stops, active_legs)
	f._orders.manual = true
	f.free_sail = true
	return true


static func _stops(values: Variant, f: Ferry) -> Array[int]:
	var out: Array[int] = []
	if not values is Array or values.size() < 2:
		return out
	for key in values:
		if not key is String:
			return []
		var town := f.sim.map.town_by_key(key)
		if town == null or not f.sim.terminals.has(town.id):
			return []
		out.append(town.id)
	return out


static func _legs(stops: Array[int], f: Ferry) -> Array[MapData.Route]:
	var routes: Array[MapData.Route] = []
	for i in stops.size():
		var route := f.sim.route_between(stops[i], stops[(i + 1) % stops.size()])
		if route == null:
			return []
		routes.append(route)
	return routes


static func _restore_navigation(r: Dictionary, f: Ferry) -> bool:
	if not (
		SnapshotVector3.valid(r.get("target"))
		and r.target[1] == 0
		and r.get("path") is Array
		and r.path.size() >= 2
		and CompanySnapshot._integer_in(r.get("waypoint"), 1, r.path.size() - 1)
		and FerryCrossingSnapshot._number(r.get("yaw"))
		and FerryCrossingSnapshot._number(r.get("stuck"))
		and r.stuck >= 0
		and CompanySnapshot._integer_in(r.get("stranded_cars"), 0, 9007199254740991)
		and CompanySnapshot._integer_in(r.get("stranded_walkers"), 0, 9007199254740991)
		and FerryCrossingSnapshot._number(r.get("refunds"))
		and r.refunds >= 0
		and r.get("join") is Dictionary
		and r.get("resume") is bool
	):
		return false
	var path := PackedVector2Array()
	for p in r.path:
		if not p is Array or p.size() != 2 or not SnapshotVector3.valid([p[0], 0, p[1]]):
			return false
		path.append(Vector2(p[0], p[1]))
	f._free_target = SnapshotVector3.decode(r.target)
	if not r.join.is_empty() and not _restore_join(r.join, f):
		return false
	f._free_path = path
	f._free_wp = int(r.waypoint)
	f._free_yaw = r.yaw
	f._free_stuck = r.stuck
	f._orders._manual_resume_due = r.resume
	f._orders.stranded_cars = int(r.stranded_cars)
	f._orders.stranded_walk_ons = int(r.stranded_walkers)
	f._orders.stranded_refunds = r.refunds
	return true


static func _restore_join(join: Dictionary, f: Ferry) -> bool:
	if not join.get("from") is String or not join.get("to") is String:
		return false
	var from := f.sim.map.town_by_key(join.from)
	var to := f.sim.map.town_by_key(join.to)
	if from == null or to == null or from == to or not f.sim.terminals.has(to.id):
		return false
	var route := f.sim.route_between(from.id, to.id)
	if (
		route == null
		or join.get("route") != route.key
		or not (
			FerryCrossingSnapshot._number(join.get("distance"))
			and join.distance >= 0
			and join.distance <= route.length
			and FerryLayUpSnapshot._slip(join.get("slip"), f.sim.terminals[to.id], f)
		)
	):
		return false
	var target := route.curve.sample_baked(join.distance)
	if not Vector2(target.x, target.z).is_equal_approx(Vector2(f._free_target.x, f._free_target.z)):
		return false
	f._free_join = [route, join.distance, from.id, to.id, int(join.slip)]
	f._orders.manual_target = to.id
	f._orders.manual_slip = int(join.slip)
	return true
