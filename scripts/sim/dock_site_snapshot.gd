class_name DockSiteSnapshot
extends RefCounted
## Restore which towns have terminals and the clocks on sites already paid for.
## Install before restoring individual terminal queues, the ledger and company RNG.


static func capture(sim: Simulation) -> Dictionary:
	var sites := {}
	for town in sim.map.dock_towns():
		if town.built:
			sites[town.key] = 0.0
		elif sim.docks_building.has(town.id):
			sites[town.key] = sim.dock_building(town)
	return {"version": 1, "seed": str(sim.map.map_seed), "sites": sites}


## A zero remaining time denotes an open terminal. Validate against the rebuilt
## region before creating any terminals or installing any pending timers.
static func restore(record: Variant, sim: Simulation) -> bool:
	if not record is Dictionary or not record.get("sites") is Dictionary:
		return false
	var version: Variant = record.get("version")
	if not (version is int or version is float) or version != 1:
		return false
	if record.get("seed") != str(sim.map.map_seed) or not sim.docks_building.is_empty():
		return false
	var waiting := {}
	var opened: Array[MapData.Town] = []
	for town in sim.map.terminal_towns():
		if not record.sites.has(town.key):
			return false
	for key in record.sites:
		if not key is String:
			return false
		var town := sim.map.town_by_key(key)
		var left: Variant = record.sites[key]
		if town == null or not (left is int or left is float) or not is_finite(left):
			return false
		if left < 0 or left > Simulation.DOCK_BUILD_MINUTES:
			return false
		if town.built:
			if left != 0 or not sim.terminals.has(town.id):
				return false
		elif sim.dock_price(town) <= 0:
			return false
		elif left > 0:
			waiting[town.id] = float(left)
		else:
			opened.append(town)
	for town in opened:
		sim.open_terminal(town)
	sim.docks_building = waiting
	return true
