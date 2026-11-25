class_name Simulation
extends Node3D
## Owns the game clock, demand model, economy and all terminals/ferries/vehicles,
## plus the other traffic afloat (MarineTraffic).
## One real second = one game minute at 1x speed (Engine.time_scale scales it).

const WIND_DIRECTIONS := ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
const SEASON_DAYS := 30
const SEASONS := ["Spring", "Summer", "Autumn", "Winter"]
const FERRY_NAMES := ["Cedar Star", "Orca Spirit", "Madrona Belle", "Tidewater", "Salish Dawn",
	"Heron", "Sea Lark", "Kelp Runner", "Evergreen", "Cormorant", "Island Pride", "Driftwood Queen"]

var map: MapData
var terrain: Terrain
var rng := RandomNumberGenerator.new()
var minutes := 6.0 * 60.0
var day := 12
## Whether working slips use an operated transfer span or a fixed landing.
var uses_transfer_spans: bool
var uses_slip_guides: bool
var terminals := {}             # town id -> Terminal
## A dock site's terminal takes this long to build once bought (TID-319: at least 12 h).
const DOCK_BUILD_MINUTES := 12.0 * 60.0
## Terminals being built: town id -> game minutes until they open.
var docks_building := {}
var ferries: Array[Ferry] = []
## Tugs delivering boats bought, or taking sold ones away (DeliveryTow).
var tows: Array[DeliveryTow] = []
var fleet_market := FleetMarket.new(self)
## How the company started; its schedules are the only links between terminals.
var scenario: Scenario
## Builds one vehicle using this simulation's RNG. The session chooses its presentation.
var _create_vehicle: Callable
var moving_vehicles: Array[Vehicle] = []
var traffic: Node3D
var wildlife: Wildlife
var marine: MarineTraffic
## A terminal changed its holding queue or lane allocation.
signal queues_changed
## A ferry changes berth during a lay-up, return or delivery.
signal berths_changed
## A dock site was bought and its terminal is being built (buy_dock).
signal slip_sites_changed
signal dock_bought(town: MapData.Town)
## A terminal bought in play opened (open_terminal).
signal terminal_opened(term: Terminal)
## A boat's running costs went on the ledger (`trip`: as she docked).
signal running_costs_posted(ferry: Ferry, fuel: float, crew: float, trip: bool)
## Which routes are in service changed (a schedule was edited).
signal routes_changed
## A boat was bought (buy_ferry): she is in `ferries`, under tow.
signal ferry_added(ferry: Ferry)
## The tug has her where she'll lie, laid up until she is given stops.
signal ferry_delivered(ferry: Ferry)
## A boat was sold (sell_ferry); she leaves `ferries` and the scene after this.
signal ferry_removed(ferry: Ferry)

var ledger := CompanyLedger.new()
var available_cash: float:
	get: return ledger.cash
var revenue_today: float:
	get: return ledger.revenue_today
var revenue_total: float:
	get: return ledger.revenue_total
var cars_today: int:
	get: return ledger.cars_today
var weather := Weather.new()
var wind_dir := "SW"
var wind_speed := 12
var _tide_phase := 0.0


func _init(create_vehicle: Callable, transfer_spans := true, slip_guides := true) -> void:
	uses_transfer_spans = transfer_spans
	uses_slip_guides = slip_guides
	_create_vehicle = create_vehicle


## Starts from `sc`, or with no scenario puts a boat on every route of the map.
func setup(m: MapData, t: Terrain, sc: Scenario = null, charts: MarineCharts = null, frames: BuildFrameBudget = null) -> void:
	scenario = sc
	await _start(m, t, null, charts, frames if frames else BuildFrameBudget.new())


## Restore just the fleet and route identities into a fresh simulation.
## Voyage progress, economics and queues are outside this save slice.
func setup_from_network(m: MapData, t: Terrain, saved_json: String) -> String:
	if map != null:
		return "Network restore needs a fresh simulation"
	var network := CompanyNetwork.new()
	var error := network.read(saved_json, m)
	if not error.is_empty():
		return error
	_start(m, t, network, null, BuildFrameBudget.new())
	return ""


func _start(m: MapData, t: Terrain, network: CompanyNetwork, charts: MarineCharts, frames: BuildFrameBudget) -> void:
	map = m
	terrain = t
	rng.seed = m.map_seed + 99
	wind_dir = WIND_DIRECTIONS[rng.randi_range(0, WIND_DIRECTIONS.size() - 1)]
	wind_speed = rng.randi_range(4, 24)
	weather.setup(m.map_seed + 7)
	_tide_phase = rng.randf() * TAU
	traffic = Node3D.new()
	traffic.name = "Traffic"
	add_child(traffic)
	for town in map.terminal_towns():
		_add_terminal(town)
		if not await frames.can_continue():
			return
	if network == null:
		if scenario == null:
			scenario = Scenario.from_network(map, FERRY_NAMES, _ferry_sizes())
		ledger.cash = scenario.cash
		_spawn_scheduled()
	else:
		for hull in network.fleet:
			_spawn_ferry(hull.key, hull.route, hull.display_name, hull.size)
	if not await frames.can_continue():
		return
	_build_lanes()
	_mark_routes_in_service()
	for term: Terminal in terminals.values():
		term.prefill()
		if not await frames.can_continue():
			return
	for i in ferries.size():
		ferries[i].start_staggered(i)
	_tie_up_laid_up()
	wildlife = Wildlife.new()
	wildlife.name = "Wildlife"
	add_child(wildlife)
	wildlife.setup(self)
	if not await frames.can_continue():
		return
	if marine == null:
		marine = MarineTraffic.new()
	add_child(marine)
	marine.setup(self, charts)


func _add_terminal(town: MapData.Town) -> Terminal:
	var term := Terminal.new()
	add_child(term)
	term.queue_changed.connect(queues_changed.emit)
	term.setup(self, town)
	terminals[town.id] = term
	return term


## Opens the terminal at `town` once it is built (TID-319): everything it needs
## is in the map already, so it starts with its lanes idle until a schedule
## calls there. Returns it, or null if it was open already.
func open_terminal(town: MapData.Town) -> Terminal:
	if terminals.has(town.id) or not town.has_dock:
		return null
	town.built = true
	if not scenario.terminals.has(town.key):
		scenario.terminals.append(town.key)
	var term := _add_terminal(town)
	term.build_lanes(_lane_destinations(term))
	term.prefill()
	terminal_opened.emit(term)
	return term


## One boat per schedule. Two stops shuttle; more run round in turn, leg by leg.
func _spawn_scheduled() -> void:
	var route_by_pair := {}
	var town_by_key := {}
	for t in map.towns:
		town_by_key[t.key] = t.id
	for r in map.routes:
		var a := map.towns[r.a].key
		var b := map.towns[r.b].key
		route_by_pair[a + "|" + b] = r
		route_by_pair[b + "|" + a] = r
	for schedule in scenario.schedules:
		var boat := scenario.boat(schedule.boat)
		var n := schedule.stops.size()
		var leg_routes: Array[MapData.Route] = []
		for i in n:
			var leg: MapData.Route = route_by_pair.get("%s|%s" % [schedule.stops[i], schedule.stops[(i + 1) % n]])
			if leg != null:
				leg_routes.append(leg)
		if boat == null or n < 2 or leg_routes.size() != n:
			push_warning("Schedule for %s has no boat or a stop with no route" % schedule.boat)
			continue
		if not _schedule_fits(boat, leg_routes):
			continue
		_spawn_ferry(boat.key, leg_routes[0], boat.name, boat.size)
		ferries[-1].schedule = schedule
		var stop_ids: Array[int] = []
		for key in schedule.stops:
			stop_ids.append(town_by_key[key])
		ferries[-1].set_legs(stop_ids, leg_routes)
		ferries[-1].set_timetable(schedule.departures)


## The route between two islands (either way round), or null if none was planned.
func route_between(a: int, b: int) -> MapData.Route:
	for r in map.routes:
		if (r.a == a and r.b == b) or (r.a == b and r.b == a):
			return r
	return null


## Returns the first reason the ferry cannot sail this leg, checking both berths.
func leg_problem(f: Ferry, a: int, b: int) -> String:
	if a < 0 or b < 0 or a >= map.towns.size() or b >= map.towns.size():
		return "Unknown stop"
	for id in [a, b]:
		if not terminals.has(id):
			return "%s has no terminal yet" % map.towns[id].name
	if a == b:
		return "%s is listed twice in a row" % map.towns[a].name
	var route := route_between(a, b)
	if route == null:
		return "No route between %s and %s" % [map.towns[a].name, map.towns[b].name]
	for id in [a, b]:
		var island := map.towns[id]
		var berth := island.slip_index(route.id)
		if berth < 0:
			return "%s has no slip for this route" % island.name
		var slip := island.slips[berth]
		if not slip.fits(f.fc.size):
			return "%s's %s slip is too small for her" % [island.name, slip.size_name()]
	return ""


## Why boat `f` can't run `ids` (island ids in turn), or "" if she can.
func stops_problem(f: Ferry, ids: Array[int]) -> String:
	if ids.size() < 2:
		return "Give her at least two stops"
	for i in ids.size():
		var reason := leg_problem(f, ids[i], ids[(i + 1) % ids.size()])
		if reason != "":
			return reason
	if f.next_dock().town.id not in ids:
		return "Keep %s, where she calls next" % f.next_dock().town.name
	return ""


## A boat other than `except` lying out of service in slip `slip` at `term`, or
## being towed into it or out of it close in (a boat bought, or one sold). Boats
## for that slip hold off until she's gone (Ferry._occupied_wait).
func occupant(term: Terminal, slip: int, except: Ferry) -> Ferry:
	for boat in ferries:
		if _occupies(boat, term, slip, except):
			return boat
	for tug in tows:
		if tug.outbound and _occupies(tug.ferry, term, slip, except):
			return tug.ferry
	return null


static func _occupies(boat: Ferry, term: Terminal, slip: int, except: Ferry) -> bool:
	if not is_instance_valid(boat) or boat == except or boat.berth == Ferry.Berth.WORKING:
		return false
	if boat.tie_up != slip or boat.here() != term:
		return false
	return boat.berth != Ferry.Berth.DELIVERING or (boat.tow and boat.tow.committed)


## Whether a working boat lies at slip `slip` of `term`, or is coming in to it
## within `near` metres (a tow waits offshore for her to clear).
func slip_busy(term: Terminal, slip: int, near := 500.0) -> bool:
	for f in ferries:
		if f.berth != Ferry.Berth.WORKING or f.slip_at(term) != slip:
			continue
		if f.state != Ferry.State.SAILING and f.here() == term:
			return true
		if f.state == Ferry.State.SAILING and f.destination() == term and f.path_left() < near:
			return true
	return false


## Puts boat `f` on `ids` from her next call (Ferry.plan_stops), and on the
## departures `times` (Timetable; null keeps hers). New times on the stops she
## already runs start at once. False if she can't run them.
func reschedule(f: Ferry, ids: Array[int], times = null) -> bool:
	if stops_problem(f, ids) != "":
		return false
	var new_times: Array[int] = []
	new_times.assign(times if times != null else (f._next_timetable if not f.next_stops.is_empty() else f.timetable))
	new_times.sort()
	if not new_times.is_empty() and (new_times[0] < 0 or new_times[-1] >= Timetable.DAY):
		return false
	var offsets := f.plan_offsets(ids)
	if Timetable.any_too_soon(new_times, offsets[-1]):
		return false
	var n := ids.size()
	var leg_routes: Array[MapData.Route] = []
	for i in n:
		leg_routes.append(route_between(ids[i], ids[(i + 1) % n]))
	if not f.assigned:
		# Bought in play: these are her first stops, from where she lies.
		f.take_first_stops(ids, leg_routes, new_times)
		if f.schedule:
			f.schedule.stops.assign(ids.map(func(id): return map.towns[id].key))
			f.schedule.departures = new_times
		stops_changed(f)
		return true
	if ids == f.stops:
		f.next_stops = []
		f._next_legs = []
		if new_times != f.timetable:
			f.set_timetable(new_times)
	else:
		f.plan_stops(ids, leg_routes, new_times)
	if f.schedule:
		f.schedule.stops.assign(ids.map(func(id): return map.towns[id].key))
		f.schedule.departures = new_times
	_mark_routes_in_service()
	return true


## A boat took new stops: the lanes divide again among the new destinations.
func stops_changed(_f: Ferry) -> void:
	for term: Terminal in terminals.values():
		term.relane(_lane_destinations(term))
	# And the water she shares with other boats is found afresh for her new routes.
	if marine:
		marine.refresh_corridors()
	_mark_routes_in_service()
	# A route newly in service may share a slip while another stands free.
	for term: Terminal in terminals.values():
		term.spread_routes()


## Routes a boat sails, or will once she takes her planned stops, are in service.
func _mark_routes_in_service() -> void:
	for r in map.routes:
		r.in_service = false
	for f in ferries:
		if not f.assigned:
			continue
		for r in f.legs + f._next_legs:
			r.in_service = true
	routes_changed.emit()


## A multi-stop schedule can call at a different slip on each leg.
func _schedule_fits(boat: Scenario.Boat, legs: Array[MapData.Route]) -> bool:
	for route in legs:
		for id in [route.a, route.b]:
			var island := map.towns[id]
			var berth := island.slip_index(route.id)
			if berth < 0 or not island.slips[berth].fits(boat.size):
				push_warning("Cannot schedule %s (size %d) at %s: no suitable slip for this leg" % [boat.name, boat.size, island.name])
				return false
	return true


## Each terminal's lanes, divided among the destinations its boats serve from
## there: first the far ends of its routes in slip order (so a plain shuttle
## network lays out as before), then anywhere further a boat carries cars to.
func _build_lanes() -> void:
	for term: Terminal in terminals.values():
		term.build_lanes(_lane_destinations(term))


func _lane_destinations(term: Terminal) -> Array[int]:
	var served: Array[int] = []
	for f in ferries:
		if not f.assigned:
			continue
		for i in f.stops.size():
			if f.stops[i] == term.town.id:
				for d in f._served_from(i):
					if d not in served:
						served.append(d)
	var dests: Array[int] = []
	for rid in term.town.route_ids():
		var r := map.routes[rid]
		var other := r.b if r.a == term.town.id else r.a
		if other in served and other not in dests:
			dests.append(other)
	for d in served:
		if d not in dests:
			dests.append(d)
	return dests


## Boats whose schedule starts laid up lie at a tie-up slip at its first stop.
func _tie_up_laid_up() -> void:
	for f in ferries:
		if f.schedule == null or not f.schedule.laid_up:
			continue
		var term: Terminal = f.term_a if f.term_a.town.key == f.schedule.stops[0] else f.term_b
		if not f.start_tied_up(term):
			push_warning("%s starts laid up but %s has no free tie-up slip for her" % [f.ferry_name, term.town.name])


func delivery_slip(size: int) -> Array:
	return fleet_market.delivery_slip(size)


func purchase_problem(size: int) -> String:
	return fleet_market.offer_problem(size, delivery_slip(size))


func buy_ferry(size: int) -> Ferry:
	return fleet_market.buy_ferry(size)


func sell_ferry(f: Ferry) -> bool:
	return fleet_market.sell_ferry(f)


func _spawn_ferry(key: String, route: MapData.Route, display_name: String, size: int) -> void:
	var ferry := Ferry.new()
	ferry.fleet_key = key
	add_child(ferry)
	ferry.setup(self, route, display_name, size)
	ferries.append(ferry)


## The size of ferry each route gets (FerryClass), by how busy it is: the mean
## population of the islands it links, the mainland counting as busy as the
## busiest island can be. `--ferry-sizes=1,3,5` on the command line hands sizes
## out to the routes in turn instead.
func _ferry_sizes() -> Array[int]:
	var demand: Array[float] = []
	for r in map.routes:
		var pop := 0.0
		for id in [r.a, r.b]:
			var town: MapData.Town = map.towns[id]
			pop += 8000.0 if map.island_of(town).is_mainland else float(town.population)
		demand.append(pop * 0.5)
	var sizes := FerryClass.sizes_by_demand(demand)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--ferry-sizes="):
			var forced := arg.substr(14).split(",")
			for i in sizes.size():
				sizes[i] = clampi(int(forced[i % forced.size()]), 1, FerryClass.MAX_SIZE)
	return sizes


func _process(delta: float) -> void:
	weather.step(delta)
	const DAY_MINUTES := 24.0 * 60.0
	while minutes + delta >= DAY_MINUTES:
		var to_midnight := DAY_MINUTES - minutes
		for ferry in ferries:
			ferry.pay_crew(to_midnight)
		delta -= to_midnight
		minutes = 0.0
		day += 1
		for ferry in ferries:
			ferry.post_costs(false)
		ledger.start_day()
		for ferry in ferries:
			ferry.start_day()
		for term: Terminal in terminals.values():
			term.served_today = 0
	minutes += delta
	for ferry in ferries:
		ferry.pay_crew(delta)
	_advance_docks(delta)


## What building a terminal at `town`'s dock site costs (its tier), or 0 if it can't be bought.
func dock_price(town: MapData.Town) -> int:
	if not town.has_dock or town.built or town.site < 0 or town.route_ids().is_empty():
		return 0
	return map.island_of(town).dock_sites[town.site].price()


## Game minutes until `town`'s terminal opens, or -1 if it isn't being built.
func dock_building(town: MapData.Town) -> float:
	return docks_building.get(town.id, -1.0)


## Buys `town`'s dock site and starts building its terminal there. It opens
## DOCK_BUILD_MINUTES later, whatever the hour (open_terminal). False if it
## can't be bought or the company can't afford it.
func buy_dock(town: MapData.Town) -> bool:
	var price := dock_price(town)
	if price <= 0 or docks_building.has(town.id) or available_cash < price:
		return false
	ledger.spend("purchases", price)
	docks_building[town.id] = DOCK_BUILD_MINUTES
	dock_bought.emit(town)
	return true


func _advance_docks(delta: float) -> void:
	for id in docks_building.keys():
		docks_building[id] -= delta
		if docks_building[id] <= 0.0:
			docks_building.erase(id)
			open_terminal(map.towns[id])


## Research projects finished (stage 8 fills this; nothing is researched yet).
var research_done: Array[String] = []


## Whether research `key` is done ("" needs none). Upgrades ask before they are bought.
func has_research(key: String) -> bool:
	return key == "" or key in research_done


func post_running_costs(ferry: Ferry, fuel: float, crew: float, trip: bool) -> void:
	ledger.spend("fuel", fuel)
	ledger.spend("crew", crew)
	running_costs_posted.emit(ferry, fuel, crew, trip)


func make_vehicle(parent: Node3D = null) -> Vehicle:
	var vehicle: Vehicle = _create_vehicle.call(rng)
	vehicle.moving_traffic = moving_vehicles
	(parent if parent else traffic).add_child(vehicle)
	return vehicle


func collect_fare(car: Vehicle) -> void:
	if car.model.is_empty():
		ledger.credit_flat(car.is_truck)
	else:
		ledger.credit_measured(car.length_metres())


## Game minutes since the start of day 0, running on past midnight.
func abs_minutes() -> float:
	return day * 1440.0 + minutes


func hour() -> float:
	return fmod(minutes / 60.0, 24.0)


## Unit vector (x, z) pointing to where the wind blows from (it is named for that;
## -Z is north).
func wind_from() -> Vector2:
	var a := WIND_DIRECTIONS.find(wind_dir) * TAU / WIND_DIRECTIONS.size()
	return Vector2(sin(a), -cos(a))


## Rotation about Y for animals or vessels facing into the wind (+Z forward).
func wind_yaw() -> float:
	var direction := wind_from()
	return atan2(direction.x, direction.y)


## Commuter-shaped demand: morning and evening peaks, quiet nights.
func demand_factor() -> float:
	return TrafficDemand.factor(hour())


func demand_rate(isl: MapData.Town) -> float:
	return TrafficDemand.arrivals_per_minute(isl.population, hour())


func demand_label(isl: MapData.Town) -> String:
	return TrafficDemand.label(demand_rate(isl))


func satisfaction() -> float:
	var total := 0.0
	var weight := 0.0
	for term: Terminal in terminals.values():
		total += term.satisfaction() * term.town.population
		weight += term.town.population
	return total / weight if weight > 0.0 else 0.0


func total_queued() -> int:
	var total := 0
	for term: Terminal in terminals.values():
		total += term.total_queued()
	return total


func clock_text(m: float = -1.0) -> String:
	if m < 0.0:
		m = minutes
	var total := int(m) % 1440
	var h := floori(total / 60.0)
	var h12 := h % 12
	if h12 == 0:
		h12 = 12
	return "%d:%02d %s" % [h12, total % 60, "AM" if h < 12 else "PM"]


func date_text() -> String:
	return "May %d, Year 8" % day


## Seasons since the game began (day 1 opens the first spring).
func season() -> int:
	return floori((day - 1) / float(SEASON_DAYS))


func season_name() -> String:
	return SEASONS[season() % SEASONS.size()]


func temperature() -> int:
	return roundi(12.0 + 5.0 * sin((hour() - 9.0) / 24.0 * TAU))


func tide() -> Vector2:
	var t := minutes / (12.42 * 60.0) * TAU + _tide_phase
	return Vector2(1.6 * sin(t), cos(t))  # level (m), rising if y > 0
