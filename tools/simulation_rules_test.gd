extends SceneTree

var failures := 0

func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	check_saved_volume()
	check_weather()
	check_wind()
	check_demand()
	check_departures()
	check_lane_capacity()
	check_navigation()
	check_pilot_transfer()
	check_harbour_access()
	check_wildlife_daylight()
	check_wildlife_photo()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_wind() -> void:
	var sim := Simulation.new(Vehicle.new.unbind(1))
	var bearings := {"N": Vector2.UP, "NE": Vector2(1, -1), "E": Vector2.RIGHT,
		"SE": Vector2(1, 1), "S": Vector2.DOWN, "SW": Vector2(-1, 1),
		"W": Vector2.LEFT, "NW": Vector2(-1, -1)}
	for bearing: String in bearings:
		sim.wind_dir = bearing
		var expected: Vector2 = bearings[bearing].normalized()
		expect(sim.wind_from().is_equal_approx(expected), "Wind from " + bearing)
		var heading := Vector2(sin(sim.wind_yaw()), cos(sim.wind_yaw()))
		expect(heading.is_equal_approx(expected), "Facing into wind from " + bearing)
	sim.free()


func check_demand() -> void:
	var sim := Simulation.new(Vehicle.new.unbind(1))
	var island := MapData.Town.new()
	island.population = 5200
	sim.minutes = 2 * 60
	var overnight := sim.demand_rate(island)
	sim.minutes = 7 * 60 + 24
	var morning := sim.demand_rate(island)
	sim.minutes = 12 * 60 + 30
	var midday := sim.demand_rate(island)
	sim.minutes = 17 * 60 + 18
	var evening := sim.demand_rate(island)
	expect(morning > midday and evening > midday and midday > overnight, "Rush hours should generate stronger demand than midday and night")
	island.population *= 2
	expect(is_equal_approx(sim.demand_rate(island), 2 * evening), "Demand should scale with town population")
	island.population = 0
	expect(is_zero_approx(sim.demand_rate(island)), "An empty settlement should generate no traffic")
	expect(TrafficDemand.label(0.2) == "Low" and TrafficDemand.label(0.5) == "Medium", "Lower demand label boundaries")
	expect(TrafficDemand.label(0.9) == "High" and TrafficDemand.label(0.91) == "Very High", "Upper demand label boundaries")
	sim.free()


func check_lane_capacity() -> void:
	var first := TerminalLane.new(-2.0)
	var second := TerminalLane.new(2.0)
	var lanes := [first, second]
	first.enqueue(41, 2)
	first.enroute = 1
	second.enroute = 2
	expect(TerminalLane.for_arrival(lanes, [], 4, 2) == second, "Use the lane with room for the whole vehicle")
	second.enroute += 2
	expect(TerminalLane.for_arrival(lanes, [], 4, 2) == null, "Approaching vehicles must reserve their space")
	expect(TerminalLane.for_arrival(lanes, [], 4, 1) == first, "One remaining slot still fits a car")
	first.arrive(42, 1)
	second.arrive(43, 3)
	expect(first.enroute == 0 and first.queued_slots() == 3, "Arrival converts reserved slots into waiting slots")
	expect(TerminalLane.for_boarding(lanes, Callable()) == first, "Serve the longest line by vehicle count")
	expect(TerminalLane.for_boarding(lanes, func(id: int): return id != 41) == second, "Only a lane head can board")
	expect(first.take_front() == 41 and first.queued_slots() == 1, "The head leaves with all its slots")
	expect(TerminalLane.for_boarding(lanes, Callable()) == first, "Equal waiting counts keep lane order")
	expect(TerminalLane.for_arrival(lanes, [first], 4, 1) == null, "Closed lanes cannot take new traffic")


func check_departures() -> void:
	var sim := Simulation.new(Vehicle.new.unbind(1))
	var origin := Terminal.new()
	var destination := Terminal.new()
	var elsewhere := Terminal.new()
	origin.sim = sim
	var route := MapData.Route.new()
	route.length = 1000.0
	var first := loading_ferry(route, origin, destination)
	var second := loading_ferry(route, origin, destination)
	second._state_time = 5.0
	var unrelated := loading_ferry(MapData.Route.new(), elsewhere, destination)
	unrelated._state_time = 100.0
	sim.ferries.assign([first, unrelated, second])
	var expected := [second.minutes_until_departure_from(origin), second]
	expect(origin.next_departure() == expected, "Departure board should pick the earliest ferry serving the terminal")
	sim.ferries.reverse()
	expect(origin.next_departure() == expected, "Different fleet order changed the earliest departure")
	first._state_time = second._state_time
	expect(origin.next_departure()[1] == second, "Equal departures should retain fleet order")
	sim.ferries.erase(second)
	expect(origin.next_departure()[1] == first, "Removed ferry still appears on the board")
	first.term_a = elsewhere
	expect(origin.next_departure() == [INF, null], "A terminal without service should show no departure")
	for node in [first, second, unrelated, origin, destination, elsewhere, sim]:
		node.free()


func loading_ferry(route: MapData.Route, a: Terminal, b: Terminal) -> Ferry:
	var boat := Ferry.new()
	boat.route = route
	boat.fc = FerryClass.of(1)
	boat.term_a = a
	boat.term_b = b
	boat.state = Ferry.State.LOADING
	boat.at_a = true
	return boat


func check_pilot_transfer() -> void:
	var boat := PilotBoat.new()
	var traffic := MarineTraffic.new()
	var cargo := CargoShip.new()
	cargo.spec = VesselTypes.cargo_ships()[0]
	boat.setup(traffic, "Test", VesselTypes.pilot_boats()[0], MapData.PilotStation.new(), 0, 0)
	boat.ship = cargo
	boat._start_work()
	expect(not boat._work_done(0.0) and boat._work_done(40.0), "Pilot transfer completes without a view")

	var hull := VesselHullView.new(boat)
	boat.add_child(hull)
	var ladder := PilotLadder.new(boat)
	hull.add_child(ladder)
	expect(not ladder.visible, "Pilot ladder starts stowed")
	for side: float in [-1.0, 1.0]:
		boat.side = side
		boat.ship = cargo
		cargo.pilot_boat = boat
		boat._start_work()
		expect(ladder.visible and ladder.mesh != null, "Pilot transfer deploys a ladder")
		expect(ladder.basis.z.z * side > 0.0, "Ladder faces the transfer side")
		if side < 0.0:
			boat._release_ship()
			expect(cargo.pilot_boat == null, "Releasing the ship clears the pilot assignment")
		else:
			expect(boat._work_done(40.0), "Transfer finishes with a ladder attached")
		expect(not ladder.visible, "Completed and interrupted transfers stow the ladder")
	boat.free()
	cargo.free()
	traffic.free()


func check_navigation() -> void:
	var path := NavPath.new(PackedVector2Array([Vector2.ZERO, Vector2(3, 0), Vector2(3, 4)]))
	expect(is_equal_approx(path.length, 7.0), "Route length should include both legs")
	expect(path.sample(-1) == Vector2.ZERO and path.sample(9) == Vector2(3, 4), "Sampling beyond a route should stop at the endpoints")
	expect(path.sample(5) == Vector2(3, 2), "Distance travelled should follow the bend")
	expect(path.tangent(5, 0.5).is_equal_approx(Vector2.DOWN), "Heading should follow the current leg")


func check_harbour_access() -> void:
	var traffic := MarineTraffic.new()
	var harbour := MapData.Harbour.new()
	var arriving := Vessel.new()
	var next := Vessel.new()
	var leaving := Vessel.new()
	traffic.queue_for(harbour, arriving)
	traffic.queue_for(harbour, next)
	expect(not traffic.try_lock(harbour, leaving), "Departures should yield to queued arrivals")
	expect(traffic.try_lock(harbour, arriving), "First arrival should enter")
	traffic.unlock(harbour, next)
	expect(not traffic.try_lock(harbour, next), "Only the holder may free the harbour")
	traffic.unlock(harbour, arriving)
	expect(traffic.try_lock(harbour, next), "Next arrival should enter after release")
	next.free()
	expect(traffic.lock_holder(harbour) == null, "A removed holder should leave the harbour clear")
	expect(traffic.try_lock(harbour, leaving), "A vessel can enter after the previous holder disappears")
	traffic.free()
	arriving.free()
	leaving.free()


func check_wildlife_daylight() -> void:
	var sim := Simulation.new(Vehicle.new.unbind(1))
	sim.map = MapData.new()
	var island := MapData.Island.new()
	sim.map.islands.append(island)
	var terminal := Terminal.new()
	terminal.town = MapData.Town.new()
	sim.terminals[0] = terminal
	var wildlife := Wildlife.new()
	wildlife.sim = sim
	var species := Wildlife.table()[0]
	for minute: int in [329, 330, 331, 1229, 1230, 1231]:
		sim.minutes = minute
		var visit := Wildlife.Visit.new()
		visit.species = species
		var reputation := Wildlife.Reputation.new()
		wildlife._rep[island.id] = reputation
		wildlife._look(visit)
		wildlife._look(visit)
		var expected := 1 if minute >= 330 and minute <= 1230 else 0
		expect(reputation.sightings == expected, "Dock sightings at game minute %d" % minute)
	wildlife.free()
	terminal.free()
	sim.free()


func check_wildlife_photo() -> void:
	var wildlife := Wildlife.new()
	var visit := Wildlife.Visit.new()
	var island := MapData.Island.new()
	wildlife._rep[island.id] = Wildlife.Reputation.new()
	visit.species = Wildlife.table()[0]
	visit.credited.append(island)
	expect(wildlife.photograph(visit), "First photograph of an active visit should count")
	var earned := wildlife.reputation(island)
	expect(earned > 0.0 and not wildlife.photograph(visit), "A repeat photo should earn no further credit")
	expect(is_equal_approx(wildlife.reputation(island), earned), "Repeat photo changed island reputation")
	var departed := Wildlife.Visit.new()
	departed.phase = Wildlife.Phase.GONE
	expect(not wildlife.photograph(departed), "A departed group should no longer be photographable")
	wildlife.free()

func check_weather() -> void:
	var weather := Weather.new()
	weather.setup(123)
	weather.set_kind("Clear", 0.0)
	weather.set_kind("Storm", 120.0)
	weather.step(60.0)
	expect(is_equal_approx(weather.storm, 0.5), "Storm should build gradually")
	weather.step(2000.0)
	expect(weather.kind == "Storm" and is_equal_approx(weather.storm, 1.0), "Pinned storm must persist")
	weather.setup(123)
	var fresh := Weather.new()
	fresh.setup(123)
	expect(not weather.pinned and weather.kind == fresh.kind, "Starting a region resets manual weather")

func check_saved_volume() -> void:
	# Use an in-memory configuration so running the test preserves player settings.
	GameSettings._cfg = ConfigFile.new()
	GameSettings._cfg.set_value("audio", "radio", "broken")
	expect(is_equal_approx(GameSettings.volume("Radio"), GameSettings.VOLUMES.Radio), "Invalid saved radio volume uses its default")
	GameSettings._cfg.set_value("audio", "radio", 2.0)
	expect(is_equal_approx(GameSettings.volume("Radio"), 1.0), "Out-of-range saved radio volume stays bounded")
	GameSettings._cfg = null
