extends SceneTree

var failures := 0

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	_check_fare_settings()
	_check_pace()
	_check_operating_rates()
	_check_early_crew_call()
	_check_midnight_costs()
	var sim := Simulation.new(Vehicle.new.unbind(2))
	var ledger := sim.ledger
	check(
		is_equal_approx(ledger.vehicle_fare, 18.0) and is_equal_approx(ledger.passenger_fare, 6.0),
		"Default ticket prices"
	)
	var car := Vehicle.new()
	car.setup(Node3D.new(), false, "sedan_modern", Models.VEHICLE_SCALE)
	check(car.slots == 1 and car.fare_multiplier() == 1, "Sedan takes 1 slot and pays 1x")
	sim.collect_fare(car)
	check(is_equal_approx(sim.revenue_today, 18.0), "Standard car fare")

	var van := Vehicle.new()
	van.setup(Node3D.new(), false, "van_cargo", Models.VEHICLE_SCALE)
	check(van.slots == 2 and van.fare_multiplier() == 2, "Van takes 2 slots and pays 2x")
	sim.collect_fare(van)
	check(is_equal_approx(sim.revenue_today, 54.0), "Van pays double vehicle fare")

	var small_truck := Vehicle.new()
	small_truck.setup(Node3D.new(), true, "truck_step", Models.VEHICLE_SCALE)
	check(
		small_truck.slots == 2 and small_truck.fare_multiplier() == 2,
		"Small truck takes 2 slots and pays 2x"
	)
	sim.collect_fare(small_truck)
	check(is_equal_approx(sim.revenue_today, 90.0), "Small truck pays double vehicle fare")

	var rig := Vehicle.new()
	rig.setup(Node3D.new(), true, "tractor_day", Models.VEHICLE_SCALE)
	rig.attach_trailer("trailer_container", Node3D.new())
	check(rig.slots >= 3 and rig.fare_multiplier() == 3, "Large truck takes ~3+ slots and pays 3x")
	sim.collect_fare(rig)
	check(is_equal_approx(sim.revenue_today, 144.0), "Large truck pays triple vehicle fare")

	sim.collect_passenger_fare()
	sim.collect_passenger_fare()
	check(
		sim.passengers_today == 2 and is_equal_approx(sim.revenue_today, 156.0),
		"Walk-on passenger fares"
	)

	# Custom per-route and default ticket prices take effect immediately and shift demand.
	ledger.set_vehicle_fare(25.0)
	ledger.set_passenger_fare(10.0)
	sim.collect_fare(van)
	sim.collect_passenger_fare()
	check(is_equal_approx(sim.revenue_today, 216.0), "Custom vehicle (2x) and walk-on fares")
	ledger.set_route_vehicle_fare(7, 30.0)
	ledger.set_route_passenger_fare(7, 8.0)
	check(
		(
			is_equal_approx(ledger.vehicle_fare_for(7), 30.0)
			and is_equal_approx(ledger.passenger_fare_for(7), 8.0)
		),
		"Per-route fare overrides"
	)
	check(
		is_equal_approx(ledger.vehicle_fare_for(2), 25.0),
		"Unset route falls back to default vehicle fare"
	)
	check(TrafficDemand.price_multiplier(10.0, 18.0) > 1.0, "Lower fare increases demand")
	check(TrafficDemand.price_multiplier(30.0, 18.0) < 1.0, "Higher fare reduces demand")
	var expected_pax_caps := {1: 20, 2: 100, 3: 300, 4: 500, 5: 1000}
	for sz in expected_pax_caps:
		check(
			FerryClass.of(sz).passenger_capacity == expected_pax_caps[sz],
			"Class %d passenger capacity" % sz
		)

	check(
		(
			sim.cars_today == 5
			and sim.passengers_today == 3
			and is_equal_approx(sim.revenue_today, 216.0)
		),
		"Daily receipts"
	)
	sim.minutes = 1439.0
	sim._process(2.0)
	check(
		(
			sim.cars_today == 0
			and sim.passengers_today == 0
			and sim.revenue_today == 0.0
			and is_equal_approx(sim.revenue_total, 216.0)
		),
		"Midnight preserves lifetime receipts"
	)
	check(
		ledger.cars_yesterday == 5 and ledger.passengers_yesterday == 3,
		"Yesterday's counts kept at midnight"
	)
	check(is_equal_approx(ledger.cash, CompanyLedger.STARTING_CASH + 216.0), "Fares go into cash")
	check(
		is_equal_approx(CompanyLedger.net(ledger.yesterday), 216.0),
		"Yesterday's lines kept at midnight"
	)
	ledger.spend("fuel", 30.0)
	ledger.spend("crew", 20.0)
	check(
		(
			is_equal_approx(CompanyLedger.net(ledger.today), -50.0)
			and is_equal_approx(ledger.cash, CompanyLedger.STARTING_CASH + 166.0)
		),
		"Running costs leave cash"
	)
	van.free()
	small_truck.free()
	rig.free()
	sim.free()

	# Easing off burns less fuel a crossing, but the crossing takes longer.
	var paced := Ferry.new()
	paced.fc = FerryClass.of(3)
	var service_burn := paced.burn_at(paced.cruise_speed())
	paced.set_pace(0)
	check(paced.burn_at(paced.cruise_speed()) < service_burn and paced.cruise_speed() < paced.fc.cruise, "Economy pace saves fuel")
	paced.free()

	var ferry := Ferry.new()
	ferry.fc = FerryClass.of(2)
	# A small synthetic deck with one obstructed cell and one tall lane.
	ferry.fc.lanes = 2
	ferry.fc.rows = 3
	ferry.fc.tall = PackedInt32Array([1])
	ferry.fc.blocked = PackedInt32Array([0])
	ferry.deck = FerryDeck.new(ferry.fc)
	car.slots = 2
	car.is_tall = true
	for from_a: bool in [true, false]:
		ferry.at_a = from_a
		ferry.deck.clear()
		var preferred := 1 if from_a else 5
		var fallback := 2 if from_a else 4
		check(ferry._free_slot(car) == preferred, "Tall lane from end A=%s" % from_a)
		ferry._take_slots(preferred, car)
		check(ferry._free_slot(car) == fallback, "Two free adjacent fallback cells required")
		ferry._take_slots(fallback, car)
		check(ferry._free_slot(car) == -1, "No room for a two-slot vehicle")
		car.slots = 1
		var last := ferry._free_slot(car)
		check(last == (5 if from_a else 1), "Exactly one usable cell left")
		if last >= 0:
			ferry._take_slots(last, car)
		check(ferry._free_slot(car) == -1, "Blocked cell stays empty on a full deck")
		car.slots = 2
	ferry.free()
	car.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func _check_fare_settings() -> void:
	for invalid: Variant in [null, "24", true, -1, INF, NAN]:
		var schedule := FareSchedule.new({"car": invalid, "passenger": 9})
		check(
			schedule.vehicle_fare == 18.0 and schedule.passenger_fare == 9.0,
			"Invalid rate falls back independently"
		)
	check(FareSchedule.new([]).vehicle_fare == 18.0, "Malformed fare block uses defaults")
	check(FareSchedule.new({"car": 0}).vehicle_fare == 0.0, "Zero fare is valid")
	var previous: Variant = ProjectSettings.get_setting(FareSchedule.SETTING, null)
	ProjectSettings.set_setting(FareSchedule.SETTING, {"car": 24, "passenger": 9})
	var ledger := CompanyLedger.new()
	ProjectSettings.set_setting(FareSchedule.SETTING, previous)
	check(ledger.credit_vehicle(3, 7) == 72.0, "Configured fare scales by vehicle class")
	var receipt := ledger.credit_passenger(7)
	ledger.set_route_passenger_fare(7, 17.0)
	ledger.refund_fare(receipt)
	check(
		receipt == 9.0 and ledger.revenue_today == 72.0,
		"Refund returns original fare after a price change"
	)
	check(
		ledger.cash == CompanyLedger.STARTING_CASH + 72.0,
		"Cash reconciles with collected and refunded fares"
	)


func _check_operating_rates() -> void:
	var hull := FerryClass.of(2)
	for invalid: Variant in [null, false, "5", -1, INF, NAN]:
		var costs := FerryOperatingCosts.new({"fuel_per_gallon": invalid, "wage_per_crew_hour": 9})
		check(is_equal_approx(costs.fuel_cost(hull, 1852.0, hull.cruise), 3.6 * hull.burn), "Invalid fuel price uses default")
		check(costs.crew_per_hour(hull) == 9 * hull.crew, "Valid wage survives invalid fuel price")
	var free_fuel := FerryOperatingCosts.new({"fuel_per_gallon": 0, "wage_per_crew_hour": -1})
	check(free_fuel.forecast_fuel(hull, 2000.0) == 0.0, "Zero fuel price is valid")
	check(free_fuel.crew_per_hour(hull) == 12.0 * hull.crew, "Invalid wage uses default")

	var previous: Variant = ProjectSettings.get_setting(FerryOperatingCosts.SETTING, null)
	ProjectSettings.set_setting(FerryOperatingCosts.SETTING, {"fuel_per_gallon": 7, "wage_per_crew_hour": 15})
	var sim := Simulation.new(Vehicle.new.unbind(2))
	ProjectSettings.set_setting(FerryOperatingCosts.SETTING, previous)
	var boat := Ferry.new(sim.operating_costs)
	boat.sim = sim
	boat.fc = hull
	boat.route = MapData.Route.new()
	boat.route.length = 1852.0
	boat.speed = boat.cruise_speed()
	var fuel := 7.0 * hull.burn * pow(boat.speed / hull.cruise, 2)
	var crew := 15.0 * hull.crew
	check(is_equal_approx(boat.crossing_fuel_estimate(), fuel), "Configured cruise quote")
	var burn := boat.next_captain.crossing_burn(1852.0, boat.paced_cruise())
	check(is_equal_approx(boat.leg_fuel(boat.route), 7.0 * hull.burn * burn / (1852.0 * hull.cruise * hull.cruise)), "Configured timetable fuel")
	var quote := FleetPanel.class_text(hull.size, sim.operating_costs)
	check(quote.contains("%s / hr · fuel ~%s / nm" % [Hud.fmt_money(crew), Hud.fmt_money(7.0 * hull.burn)]), "Fleet quotes use company rates")
	boat._burn(1852.0)
	boat.pay_crew(60.0)
	boat.post_costs(true)
	check(is_equal_approx(sim.ledger.today["fuel"], fuel), "Metered fuel matches configured cruise quote")
	check(is_equal_approx(sim.ledger.today["crew"], crew), "Posted wages match hourly quote")
	check(is_equal_approx(sim.available_cash, CompanyLedger.STARTING_CASH - fuel - crew), "Fuel and crew charges reconcile with cash")
	boat.free()
	sim.free()


func _check_early_crew_call() -> void:
	var sim := Simulation.new(Vehicle.new.unbind(2))
	sim.map = MapData.new()
	var route := MapData.Route.new()
	route.b = 1
	route.length = 1852.0
	sim.map.routes.append(route)
	var dwell := FerryDwell.new({"maximum_loading": 32})
	var boat := Ferry.new(sim.operating_costs, dwell)
	boat.sim = sim
	boat.fc = FerryClass.of(2)
	boat.set_timetable([400])
	var ids: Array[int] = [0, 1]
	var planned := boat.daily_cost(ids, [400])
	var paid_minutes := 32.0 + boat.shift_tail(boat.plan_offsets(ids))
	check(is_equal_approx(planned.crew, paid_minutes / 60.0 * boat.crew_per_hour()), "Forecast pays from the opening of a long boarding window")
	sim.minutes = 367.9
	check(boat.off_shift(), "Crew stand down before a long boarding window")
	sim.minutes = 368.0
	check(not boat.off_shift(), "Crew are on duty when boarding starts 32 minutes before departure")
	boat.free()
	sim.free()


func _check_midnight_costs() -> void:
	var sim := Simulation.new(Vehicle.new.unbind(2))
	var boat := Ferry.new()
	boat.sim = sim
	boat.fc = FerryClass.of(2)
	boat.speed = boat.fc.cruise
	sim.ferries.append(boat)
	sim.minutes = 1439.5
	sim.ledger.cash = 0.0
	boat._burn(FerryOperatingCosts.METRES_PER_NM)
	var fuel := 3.6 * boat.fc.burn
	var half_minute_pay := boat.crew_per_hour() / 120.0
	sim._process(1.0 / Units.MINUTES_PER_SECOND)
	check(is_equal_approx(sim.ledger.yesterday["fuel"], fuel), "Midnight posts fuel once")
	check(is_equal_approx(sim.ledger.yesterday["crew"], half_minute_pay), "Yesterday ends at midnight")
	boat.post_costs(true)
	boat.post_costs(true)
	check(is_equal_approx(boat.crew_today, half_minute_pay), "Docking posts only wages earned since midnight")
	check(is_zero_approx(boat.fuel_today), "Docking cannot double-charge yesterday's fuel")
	check(is_equal_approx(sim.ledger.cash, -fuel - 2.0 * half_minute_pay), "Both days reconcile to the cash balance")
	boat.free()
	sim.free()


func _check_pace() -> void:
	var pace := FerryPace.new()
	check(pace.selected == FerryPace.SERVICE and pace.cruise(20.0) == 20.0, "Service is the default pace")
	pace.select(-1)
	check(FerryPace.label(pace.selected) == "Economy" and pace.cruise(20.0) == 17.0, "A low selection clamps to Economy")
	check(pace.cruise(20.0, FerryPace.FULL_AHEAD) == 22.0 and pace.selected == FerryPace.ECONOMY, "Previewing another pace preserves the selected pace")
	pace.select(99)
	check(FerryPace.label(pace.selected) == "Full ahead" and pace.cruise(20.0) == 22.0, "A high selection clamps to Full ahead")
