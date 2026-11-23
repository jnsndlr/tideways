class_name FleetMarket
extends RefCounted
## Selects a delivery berth and settles boat purchases and sales for a company.

var sim: Simulation


func _init(company: Simulation) -> void:
	sim = company


## Where a boat of `size` bought now is delivered to lie, as [Terminal, slip],
## or [] if nowhere: a free tie-up slip she fits (the opening's is at Port
## Rosario), else a working slip she fits that no boat calls at, else any working
## slip she fits that no boat lies in. A boat working that slip then has to hold
## off until she is given stops: the player's call.
func delivery_slip(size: int) -> Array:
	if size < 1 or size > FerryClass.MAX_SIZE:
		return []
	for term: Terminal in sim.terminals.values():
		for i in term.town.tie_ups():
			if term.town.slips[i].fits(size) and not term.tie_up_closed(i) and not berth_reserved(term, i) and _delivery_route(term) != null:
				return [term, i]
	for idle_only in [true, false]:
		for term: Terminal in sim.terminals.values():
			var town := term.town
			for j in town.slips.size():
				if town.slips[j].building or town.slips[j].tie_up or not town.slips[j].fits(size) or term.tie_up_closed(j):
					continue
				if berth_reserved(term, j) or _delivery_route(term) == null:
					continue
				if idle_only and Ferry.idle_slip(term, size) != j:
					continue
				return [term, j]
	return []


## Reserve inbound deliveries from purchase, and outbound sales until clear.
func berth_reserved(term: Terminal, slip: int, except: Ferry = null) -> bool:
	if sim.occupant(term, slip, except) != null:
		return true
	for t in sim.tows:
		if not t.outbound and is_instance_valid(t.ferry) and t.ferry != except and t.ferry.tow == t and t.ferry.here() == term and t.ferry.tie_up == slip:
			return true
	return false


## Her initial route anchors the ferry to this terminal. The tow places her at
## the chosen berth independently, including a newly built slip with no route.
func _delivery_route(term: Terminal) -> MapData.Route:
	var town := term.town
	var best: MapData.Route
	for r in sim.map.routes:
		if r.a != town.id and r.b != town.id:
			continue
		if not sim.terminals.has(r.b if r.a == town.id else r.a):
			continue
		var at := town.slip_index(r.id)
		if at < 0:
			continue
		if best == null or r.length < best.length:
			best = r
	return best


## Why a boat of `size` can't be bought now, or "".
func offer_problem(size: int, where: Array) -> String:
	if size < 1 or size > FerryClass.MAX_SIZE:
		return "Unknown ferry size"
	if where.is_empty():
		return "No free slip she fits"
	if sim.available_cash < FerryClass.of(size).price():
		return "Needs %s" % _money(FerryClass.of(size).price())
	return ""


static func _money(v: float) -> String:
	var digits := str(roundi(absf(v)))
	var out := ""
	while digits.length() > 3:
		out = "," + digits.right(3) + out
		digits = digits.left(digits.length() - 3)
	return "$" + digits + out


## Buys a new boat of `size` (FerryClass.price on the ledger's purchases) and has
## a tug tow her in to delivery_slip, where she lies laid up until she is given
## stops (Edit stops). Returns her, or null if she can't be bought.
func buy_ferry(size: int) -> Ferry:
	var where := delivery_slip(size)
	if offer_problem(size, where) != "":
		return null
	var term: Terminal = where[0]
	var slip: int = where[1]
	var route := _delivery_route(term)
	var key := ""
	var n := sim.ferries.size()
	while key == "" or sim.ferries.any(func(f): return f.fleet_key == key):
		key = "hull-%d" % n
		n += 1
	var display_name := ""
	for nm in Simulation.FERRY_NAMES:
		if not sim.ferries.any(func(f): return f.ferry_name == nm):
			display_name = nm
			break
	if display_name == "":
		display_name = "Hull %d" % n
	sim._spawn_ferry(key, route, display_name, size)
	var f := sim.ferries[-1]
	f.start_delivery(term, slip)
	var pts := DeliveryTow.plan(sim, f.global_position, term.town.dock_dir, f.fc.half_beam)
	if pts.size() < 2:
		sim.ferries.pop_back()
		f.free()
		return null
	sim.ledger.spend("purchases", f.fc.price())
	var tug := DeliveryTow.new()
	sim.add_child(tug)
	tug.setup(sim, f, pts)
	sim.tows.append(tug)
	if sim.marine:
		sim.marine.register(f, MarineTraffic.RANK_FERRY)
		sim.marine.register(tug, MarineTraffic.RANK_FERRY)
	sim.ferry_added.emit(f)
	return f


## Sells laid-up boat `f` for her resale value (Ferry.resale_value) and takes her
## out of the game. False unless she lies laid up.
func sell_ferry(f: Ferry) -> bool:
	if not is_instance_valid(f) or f not in sim.ferries or not f.can_sell():
		return false
	sim.ledger.receive("sales", f.resale_value())
	f.post_costs(false)
	sim.ferries.erase(f)
	if sim.marine:
		sim.marine.remove(f)
	sim.ferry_removed.emit(f)
	for car in f.aboard:
		car.queue_free()
	f.aboard.clear()
	sim.stops_changed(f)
	# A tug comes for her and sim.tows her away out to sea (DeliveryTow, outbound).
	var pts := DeliveryTow.plan(sim, f.global_position, f.here().town.dock_dir, f.fc.half_beam) if sim.marine else PackedVector2Array()
	if pts.size() < 2:
		f.queue_free()
		return true
	f.berth = Ferry.Berth.DELIVERING
	var tug := DeliveryTow.new()
	sim.add_child(tug)
	tug.setup(sim, f, pts, true)
	sim.tows.append(tug)
	sim.marine.register(tug, MarineTraffic.RANK_FERRY)
	return true
