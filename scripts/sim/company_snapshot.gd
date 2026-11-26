class_name CompanySnapshot
extends RefCounted
## Compose verified company records over a freshly rebuilt network. The caller
## supplies a private simulation with its own map and terrain. Only a completely
## restored simulation is returned. No current game or save slot is replaced.
const VERSION := 7


static func capture(sim: Simulation) -> Dictionary:
	if not sim.working_slips.matches(sim.map):
		return {}
	var sales := []
	for tow in sim.tows:
		if tow.outbound:
			var sale := SaleTowSnapshot.capture(tow)
			if sale.is_empty():
				return {}
			sales.append(sale)
		elif not tow.delivery_complete() and not InboundDeliverySnapshot.attached(tow, sim):
			return {}
	if not _accounts_for_traffic(sim) or not _unique_berths(sim):
		return {}
	var terminals := {}
	for term: Terminal in sim.terminals.values():
		var site := _terminal_record(term)
		if site.is_empty() or term.town.key.is_empty() or terminals.has(term.town.key):
			return {}
		terminals[term.town.key] = site
	var voyages := {}
	for ferry in sim.ferries:
		var voyage := (
			InboundDeliverySnapshot.capture(ferry)
			if (
				ferry.purchased
				and (
					ferry.berth == Ferry.Berth.DELIVERING
					or (ferry.berth == Ferry.Berth.TIED_UP and not ferry.assigned)
				)
			)
			else FerryCrossingSnapshot.capture(ferry)
		)
		if voyage.is_empty() or ferry.fleet_key.is_empty() or voyages.has(ferry.fleet_key):
			return {}
		voyages[ferry.fleet_key] = voyage
	var ledger := sim.ledger.snapshot(sim.map.routes)
	if ledger.is_empty():
		return {}
	var outbound = OutboundTrafficSnapshot.capture(sim)
	if outbound == null:
		return {}
	var reservations := {}
	for corridor: MarineTraffic.Corridor in _corridors(sim).values():
		if corridor.owner != null:
			reservations[corridor.key] = corridor.owner.fleet_key
	var record := {
		"version": 6,
		"network": CompanyNetwork.record(sim),
		"clock": CompanyClockSnapshot.capture(sim),
		"ledger": ledger,
		"docks": DockSiteSnapshot.capture(sim),
		"terminals": terminals,
		"voyages": voyages,
		"reservations": reservations,
		"outbound": outbound,
		"sale_tows": sales,
		"progression": TownGrowthSnapshot.capture(sim),
	}
	if not sim.working_slips.moves.is_empty():
		record.version = VERSION
		record.working_slips = sim.working_slips.capture(sim.map)
	return record


static func _terminal_record(term: Terminal) -> Dictionary:
	var holding := TerminalHoldingSnapshot.capture(term)
	var refit := TerminalRefitSnapshot.capture(term)
	if holding.is_empty() or refit.is_empty():
		return {}
	var record := {"holding": holding, "refit": refit}
	if term.town.slips.size() != term.original_slip_count:
		var purchase := TerminalBerthPurchaseSnapshot.capture(term)
		if purchase.is_empty():
			return {}
		record.purchase = purchase
	return record


## The factory transfers ownership of its fully built staging simulation. It may
## be inside a private scene tree so transforms and vehicle callbacks are usable.
static func restore(
	data: Variant, make_private_world: Callable, make_vehicle: Callable
) -> Simulation:
	if not supports(data) or not make_private_world.is_valid() or not make_vehicle.is_valid():
		return null
	var sim := make_private_world.call() as Simulation
	if sim == null:
		return null
	if not _install(data, sim, make_vehicle):
		sim.free()
		return null
	return sim


static func supports(data: Variant) -> bool:
	if not data is Dictionary or not _integer_in(data.get("version"), 1, VERSION):
		return false
	if data.has("working_slips") != (data.version >= 7):
		return false
	if data.has("working_slips") and not WorkingSlipHistory.supports(data.working_slips):
		return false
	if data.has("sale_tows") != (data.version >= 6) or not data.get("sale_tows", []) is Array:
		return false
	if data.version == 1 and data.has("outbound"):
		return false
	if data.version >= 2 and not data.get("outbound") is Array:
		return false
	if data.version >= 3 and not data.get("progression") is Dictionary:
		return false
	if data.version < 3 and data.has("progression"):
		return false
	for section in ["network", "ledger", "clock", "docks", "terminals", "voyages", "reservations"]:
		if not data.get(section) is Dictionary:
			return false
	return true


static func _install(data: Dictionary, sim: Simulation, make_vehicle: Callable) -> bool:
	if (
		data.network.get("seed") != str(sim.map.map_seed)
		or not DockSiteSnapshot.restore(data.docks, sim)
	):
		return false
	if not _install_berths(data.terminals, sim, data.get("working_slips", {})):
		return false
	var network := CompanyNetwork.new()
	if not network.read(data.network, sim.map).is_empty():
		return false
	if not PurchasedFleetSnapshot.rebuild(network.fleet, data.voyages, sim, int(data.version)):
		return false
	for term: Terminal in sim.terminals.values():
		var site: Dictionary = data.terminals[term.town.key]
		if not TerminalHoldingSnapshot.restore(site.get("holding"), term, make_vehicle):
			return false
	var ledger := CompanyLedgerSnapshot.restore(data.ledger, sim.map.routes)
	if ledger == null:
		return false
	sim.ledger = ledger
	if not _install_fleet(network, data, sim, make_vehicle):
		return false
	for sale in data.get("sale_tows", []):
		if not SaleTowSnapshot.restore(sale, sim):
			return false
	if not OutboundTrafficSnapshot.restore(data.get("outbound", []), sim, make_vehicle):
		return false
	if data.has("progression") and not TownGrowthSnapshot.restore(data.progression, sim):
		return false
	# Initial demand and regenerated background traffic may use random draws.
	return CompanyClockSnapshot.restore(data.clock, sim)


static func _install_berths(records: Dictionary, sim: Simulation, moves: Dictionary) -> bool:
	if records.size() != sim.terminals.size():
		return false
	for term: Terminal in sim.terminals.values():
		var record = records.get(term.town.key)
		if not record is Dictionary:
			return false
		if (
			record.has("purchase")
			and not TerminalBerthPurchaseSnapshot.restore(record.purchase, term)
		):
			return false
	if not moves.is_empty() and not sim.working_slips.restore(moves, sim):
		return false
	for term: Terminal in sim.terminals.values():
		if not TerminalRefitSnapshot.restore(records[term.town.key].get("refit"), term):
			return false
	return true


static func _install_fleet(
	network: CompanyNetwork, data: Dictionary, sim: Simulation, make_vehicle: Callable
) -> bool:
	var ferries := {}
	for ferry in sim.ferries:
		ferries[ferry.fleet_key] = ferry
	if network.fleet.size() != ferries.size() or ferries.size() != data.voyages.size():
		return false
	for hull in network.fleet:
		var ferry: Ferry = ferries.get(hull.key)
		if ferry == null or hull.size != ferry.fc.size or hull.route != ferry.route:
			return false
		var voyage = data.voyages.get(hull.key)
		if not voyage is Dictionary or not _restore_service(voyage.get("service"), ferry):
			return false
		# A generated region can initially place a prefilled hull underway.
		for car in ferry.aboard:
			ferry.deck.release(car.get_instance_id())
			car.free()
		ferry.aboard.clear()
		ferry.passengers_aboard.clear()
		if voyage.get("phase") in ["delivery", "delivered"]:
			if (
				not ferry.purchased
				or ferry.berth not in [Ferry.Berth.DELIVERING, Ferry.Berth.TIED_UP]
				or voyage.service != FerryCrossingSnapshot.service_record(ferry)
			):
				return false
		else:
			# A scenario can start this working hull parked at a different slip.
			ferry.berth = Ferry.Berth.WORKING
			ferry._lay_up.tie_up = -1
			if not FerryCrossingSnapshot.restore(voyage, ferry, make_vehicle):
				return false
		ferry.ferry_name = hull.display_name
		ferry.vessel_name = hull.display_name
	return _unique_berths(sim) and _install_reservations(data.reservations, sim, ferries)


## The tie-up remains booked during either shift and throughout inbound delivery.
## Ordinary calls at a shared working slip never reserve the berth this way.
static func _unique_berths(sim: Simulation) -> bool:
	var reserved := {}
	for f in sim.ferries:
		if f.berth == Ferry.Berth.WORKING:
			continue
		var berth := Vector2i(f.here().town.id, f.tie_up)
		if reserved.has(berth):
			return false
		reserved[berth] = true
	return true


## Reapply the player's choices before the voyage verifies hull, route and stops.
## No route edit or captain handoff is dispatched during reconstruction.
static func _restore_service(service: Variant, ferry: Ferry) -> bool:
	if not service is Dictionary or not service.get("departures") is Array:
		return false
	var pace = service.get("pace")
	if not _integer_in(pace, FerryPace.ECONOMY, FerryPace.FULL_AHEAD):
		return false
	var departures: Array[int] = []
	for minute in service.departures:
		if not _integer_in(minute, 0, Timetable.DAY - 1):
			return false
		departures.append(int(minute))
	var roster := {}
	for person in Captain.roster():
		roster[person.id] = person
	var current: Captain = roster.get(service.get("captain"))
	var next: Captain = roster.get(service.get("next_captain"))
	if current == null or next == null:
		return false
	ferry._command.assign(current, false)
	ferry._command.assign(next, true)
	ferry.set_pace(int(pace))
	ferry.set_timetable(departures)
	return true


static func _integer_in(value: Variant, lower: int, upper: int) -> bool:
	return (
		(value is float or value is int)
		and value >= lower
		and value <= upper
		and floor(value) == value
	)


static func _corridors(sim: Simulation) -> Dictionary:
	var corridors := {}
	for group: Array in sim.marine.corridors.values():
		for corridor: MarineTraffic.Corridor in group:
			corridors[corridor.key] = corridor
	return corridors


static func _install_reservations(
	records: Dictionary, sim: Simulation, ferries: Dictionary
) -> bool:
	var corridors := _corridors(sim)
	for corridor: MarineTraffic.Corridor in corridors.values():
		corridor.owner = null
	for key in records:
		var corridor: MarineTraffic.Corridor = corridors.get(key)
		var owner: Ferry = ferries.get(records[key])
		if owner == null or corridor == null or owner not in corridor.boats:
			return false
		corridor.owner = owner
	return true


## A passenger headed home still has no terminal record.
## Never silently omit a company passenger or vehicle when capturing this format.
static func _accounts_for_traffic(sim: Simulation) -> bool:
	var owned := {}
	for term: Terminal in sim.terminals.values():
		for lanes: Array in term.lanes.values():
			for lane: TerminalLane in lanes:
				for row in lane.queue:
					owned[row.vehicle_id] = true
				owned.merge(lane.approaching)
		for pax in term.passenger_queue:
			if pax.node != null:
				owned[pax.node.get_instance_id()] = true
	for ferry in sim.ferries:
		for id in ferry.deck.occupants:
			owned[id] = true
		for walker in ferry._pax_walkers + ferry._homeward_walkers:
			if not is_instance_valid(walker):
				return false
			owned[walker.get_instance_id()] = true
	for node in sim.traffic.get_children() + sim.passengers.get_children():
		if node is Vehicle and node.is_leaving_terminal():
			continue
		if not node.is_queued_for_deletion() and not owned.has(node.get_instance_id()):
			return false
	return true
