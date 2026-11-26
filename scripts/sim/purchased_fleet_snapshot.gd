class_name PurchasedFleetSnapshot
extends RefCounted
## Recreate paid hulls directly in the staging simulation. Buying a hull here
## would dispatch a second delivery and post another charge to the ledger.


static func rebuild(
	fleet: Array[CompanyNetwork.Assignment],
	voyages: Dictionary,
	sim: Simulation,
	allow_purchases: bool
) -> bool:
	var opening := {}
	for ferry in sim.ferries:
		opening[ferry.fleet_key] = ferry
	var added := false
	for hull in fleet:
		if not hull.purchased:
			if not opening.erase(hull.key):
				return false
			continue
		if not allow_purchases or not _restore_hull(hull, voyages.get(hull.key), sim):
			return false
		added = true
	if not opening.is_empty():
		return false
	if added:
		for term: Terminal in sim.terminals.values():
			var destinations := sim._lane_destinations(term)
			var keys: Array[int] = destinations.duplicate()
			if keys.is_empty():
				keys.append(MapData.NO_ROUTE)
			if keys != term.lane_keys():
				TerminalHoldingSnapshot.discard_initial_traffic(term)
				term.build_lanes(destinations)
		sim._mark_routes_in_service()
		sim.marine.refresh_corridors()
	return true


static func _restore_hull(
	hull: CompanyNetwork.Assignment, voyage: Variant, sim: Simulation
) -> bool:
	var number := hull.key.trim_prefix("hull-")
	if not number.is_valid_int() or number.to_int() < 0 or hull.key != "hull-%d" % number.to_int():
		return false
	if sim.ferries.any(func(f): return f.fleet_key == hull.key):
		return false
	if not voyage is Dictionary or not voyage.get("service") is Dictionary:
		return false
	var stops = voyage.service.get("stops")
	var route := hull.route
	if not sim.terminals.has(route.a) or not sim.terminals.has(route.b):
		return false
	var a := sim.map.towns[route.a]
	var b := sim.map.towns[route.b]
	if stops != [a.key, b.key] and stops != [b.key, a.key]:
		return false
	for town in [a, b]:
		var index: int = town.slip_index(route.id)
		if index < 0 or not town.slips[index].fits(hull.size):
			return false
	sim._spawn_ferry(hull.key, route, hull.display_name, hull.size)
	var ferry := sim.ferries[-1]
	ferry.purchased = true
	var ids: Array[int] = [a.id, b.id]
	if stops[0] == b.key:
		ids.reverse()
	ferry.set_legs(ids, [route, route])
	sim.marine.register(ferry, MarineTraffic.RANK_FERRY)
	return true
