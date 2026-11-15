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
var moving_vehicles: Array[Vehicle] = []
var traffic: Node3D
var wildlife: Wildlife
var marine: MarineTraffic
var terminal_spending := 0.0
var available_cash: float:
	get: return revenue_total - terminal_spending
var fares := FareLedger.new()
var revenue_today: float:
	get: return fares.revenue_today
var revenue_total: float:
	get: return fares.revenue_total
var cars_today: int:
	get: return fares.cars_today
var weather := "Partly Cloudy"
var wind_dir := "SW"
var wind_speed := 12
var _tide_phase := 0.0


func setup(m: MapData, t: Terrain) -> void:
	map = m
	terrain = t
	rng.seed = m.map_seed + 99
	wind_dir = WIND_DIRECTIONS[rng.randi_range(0, WIND_DIRECTIONS.size() - 1)]
	wind_speed = rng.randi_range(4, 24)
	weather = ["Partly Cloudy", "Sunny", "Overcast", "Light Breeze"][rng.randi_range(0, 3)]
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
	var sizes := _ferry_sizes()
	for i in map.routes.size():
		var r := map.routes[i]
		var f := Ferry.new()
		add_child(f)
		f.setup(self, r, FERRY_NAMES[r.id % FERRY_NAMES.size()], sizes[i])
		ferries.append(f)
	for term: Terminal in terminals.values():
		term.prefill()
	for i in ferries.size():
		ferries[i].start_staggered(i)
	wildlife = Wildlife.new()
	wildlife.name = "Wildlife"
	add_child(wildlife)
	wildlife.setup(self)
	marine = MarineTraffic.new()
	add_child(marine)
	marine.setup(self)


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
				sizes[i] = clampi(int(forced[i % forced.size()]), 1, 5)
	return sizes


func _process(delta: float) -> void:
	minutes += delta
	if minutes >= 24.0 * 60.0:
		minutes -= 24.0 * 60.0
		day += 1
		fares.start_day()
		for term: Terminal in terminals.values():
			term.served_today = 0


func make_vehicle(parent: Node3D = null) -> Vehicle:
	var vehicle := VehicleFactory.create(rng)
	vehicle.moving_traffic = moving_vehicles
	(parent if parent else traffic).add_child(vehicle)
	return vehicle


func collect_fare(car: Vehicle) -> void:
	if car.model.is_empty():
		fares.credit_flat(car.is_truck)
	else:
		fares.credit_measured(car.length_metres())


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
