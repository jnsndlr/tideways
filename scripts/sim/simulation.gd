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
var terminals := {}             # island id -> Terminal
var ferries: Array[Ferry] = []
## How the company started; its schedules are the only links between terminals.
var scenario: Scenario
var moving_vehicles: Array[Vehicle] = []
var traffic: Node3D
var wildlife: Wildlife
var marine: MarineTraffic
## A boat's running costs went on the ledger (`trip`: as she docked).
signal running_costs_posted(ferry: Ferry, fuel: float, crew: float, trip: bool)

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


## Starts from `sc`, or with no scenario puts a boat on every route of the map.
func setup(m: MapData, t: Terrain, sc: Scenario = null, charts: MarineCharts = null) -> void:
	scenario = sc
	_start(m, t, null, charts)


## Restore just the fleet and route identities into a fresh simulation.
## Voyage progress, economics and queues are outside this save slice.
func setup_from_network(m: MapData, t: Terrain, saved_json: String) -> String:
	if map != null:
		return "Network restore needs a fresh simulation"
	var network := CompanyNetwork.new()
	var error := network.read(saved_json, m)
	if not error.is_empty():
		return error
	_start(m, t, network)
	return ""


func _start(m: MapData, t: Terrain, network: CompanyNetwork, charts: MarineCharts = null) -> void:
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
	for isl in map.islands:
		if isl.has_terminal:
			var term := Terminal.new()
			add_child(term)
			term.setup(self, isl)
			terminals[isl.id] = term
	if network == null:
		if scenario == null:
			scenario = Scenario.from_network(map, FERRY_NAMES, _ferry_sizes())
		ledger.cash = scenario.cash
		_spawn_scheduled()
	else:
		for hull in network.fleet:
			_spawn_ferry(hull.key, hull.route, hull.display_name, hull.size)
	_build_lanes()
	for term: Terminal in terminals.values():
		term.prefill()
	for i in ferries.size():
		ferries[i].start_staggered(i)
	_tie_up_laid_up()
	wildlife = Wildlife.new()
	wildlife.name = "Wildlife"
	add_child(wildlife)
	wildlife.setup(self)
	if marine == null:
		marine = MarineTraffic.new()
	add_child(marine)
	marine.setup(self, charts)


## One boat per schedule. Two stops shuttle; more run round in turn, leg by leg.
func _spawn_scheduled() -> void:
	var route_by_pair := {}
	var island_by_key := {}
	for isl in map.islands:
		island_by_key[isl.key] = isl.id
	for r in map.routes:
		var a := map.islands[r.a].key
		var b := map.islands[r.b].key
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
			stop_ids.append(island_by_key[key])
		ferries[-1].set_legs(stop_ids, leg_routes)


## A multi-stop schedule can call at a different slip on each leg.
func _schedule_fits(boat: Scenario.Boat, legs: Array[MapData.Route]) -> bool:
	for route in legs:
		for id in [route.a, route.b]:
			var island := map.islands[id]
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
		var served: Array[int] = []
		for f in ferries:
			for i in f.stops.size():
				if f.stops[i] == term.island.id:
					for d in f._served_from(i):
						if d not in served:
							served.append(d)
		var dests: Array[int] = []
		for rid in term.island.route_ids():
			var r := map.routes[rid]
			var other := r.b if r.a == term.island.id else r.a
			if other in served and other not in dests:
				dests.append(other)
		for d in served:
			if d not in dests:
				dests.append(d)
		term.build_lanes(dests)


## Boats whose schedule starts laid up lie at a tie-up slip at its first stop.
func _tie_up_laid_up() -> void:
	for f in ferries:
		if f.schedule == null or not f.schedule.laid_up:
			continue
		var term: Terminal = f.term_a if f.term_a.island.key == f.schedule.stops[0] else f.term_b
		if not f.start_tied_up(term):
			push_warning("%s starts laid up but %s has no free tie-up slip for her" % [f.ferry_name, term.island.name])


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
			var isl: MapData.Island = terminals[id].island
			pop += 8000.0 if isl.is_mainland else float(isl.population)
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


func post_running_costs(ferry: Ferry, fuel: float, crew: float, trip: bool) -> void:
	ledger.spend("fuel", fuel)
	ledger.spend("crew", crew)
	running_costs_posted.emit(ferry, fuel, crew, trip)


func make_vehicle(parent: Node3D = null) -> Vehicle:
	var vehicle := VehicleFactory.create(rng)
	vehicle.moving_traffic = moving_vehicles
	(parent if parent else traffic).add_child(vehicle)
	return vehicle


func collect_fare(car: Vehicle) -> void:
	if car.model.is_empty():
		ledger.credit_flat(car.is_truck)
	else:
		ledger.credit_measured(car.length_metres())


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


func demand_rate(isl: MapData.Island) -> float:
	return TrafficDemand.arrivals_per_minute(isl.population, hour())


func demand_label(isl: MapData.Island) -> String:
	return TrafficDemand.label(demand_rate(isl))


func satisfaction() -> float:
	var total := 0.0
	var weight := 0.0
	for term: Terminal in terminals.values():
		total += term.satisfaction() * term.island.population
		weight += term.island.population
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
