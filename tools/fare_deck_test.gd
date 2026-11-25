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
	var sim := Simulation.new(Vehicle.new.unbind(1))
	var car := Vehicle.new()
	sim.collect_fare(car)
	check(is_equal_approx(sim.revenue_today, 18.5), "Fallback car fare")
	car.is_truck = true
	sim.collect_fare(car)
	check(is_equal_approx(sim.revenue_today, 60.5), "Fallback truck fare")
	car.model = "measured"
	for metres: float in [4.0, 6.7, 8.7]:
		car.length = metres * Models.VEHICLE_SCALE
		var before := sim.revenue_total
		sim.collect_fare(car)
		var expected := 29.6 if metres > 6.7 else 18.5
		check(is_equal_approx(sim.revenue_total - before, expected), "Measured fare at %s m" % metres)
	check(sim.cars_today == 5 and is_equal_approx(sim.revenue_today, 127.1), "Daily receipts")
	sim.minutes = 1439.0
	sim._process(1.0)
	check(sim.cars_today == 0 and sim.revenue_today == 0.0 and is_equal_approx(sim.revenue_total, 127.1), "Midnight preserves lifetime receipts")
	var ledger := sim.ledger
	check(is_equal_approx(ledger.cash, CompanyLedger.STARTING_CASH + 127.1), "Fares go into cash")
	check(is_equal_approx(CompanyLedger.net(ledger.yesterday), 127.1), "Yesterday's lines kept at midnight")
	ledger.spend("fuel", 30.0)
	ledger.spend("crew", 20.0)
	check(is_equal_approx(CompanyLedger.net(ledger.today), -50.0) and is_equal_approx(ledger.cash, CompanyLedger.STARTING_CASH + 77.1), "Running costs leave cash")
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
		var schedule := FareSchedule.new({"car": invalid, "truck": 51})
		check(schedule.flat(false) == 18.5 and schedule.flat(true) == 51, "Invalid rate falls back independently")
	check(FareSchedule.new([]).flat(true) == 42.0, "Malformed fare block uses defaults")
	check(FareSchedule.new({"car": 0}).measured(8.7) == 0.0, "Zero fare is valid")

	var previous: Variant = ProjectSettings.get_setting(FareSchedule.SETTING, null)
	ProjectSettings.set_setting(FareSchedule.SETTING, {
		"car": 24, "truck": 50, "included_metres": 5, "extra_fraction_per_metre": 0.25,
	})
	var sim := Simulation.new(Vehicle.new.unbind(1))
	ProjectSettings.set_setting(FareSchedule.SETTING, previous)
	var car := Vehicle.new()
	sim.collect_fare(car)
	check(sim.revenue_today == 24.0, "Configured flat car fare")
	car.is_truck = true
	sim.collect_fare(car)
	check(sim.revenue_today == 74.0, "Configured flat truck fare")
	car.model = "measured"
	car.length = 7.0 * Models.VEHICLE_SCALE
	sim.collect_fare(car)
	check(is_equal_approx(sim.revenue_today, 110.0) and sim.cars_today == 3, "Configured measured fare charged once")
	check(is_equal_approx(sim.ledger.cash, CompanyLedger.STARTING_CASH + 110.0), "Configured fares reach cash")
	car.free()
	sim.free()


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
	var sim := Simulation.new(Vehicle.new.unbind(1))
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
	var sim := Simulation.new(Vehicle.new.unbind(1))
	sim.map = MapData.new()
	var route := MapData.Route.new()
	route.b = 1
	route.length = 1852.0
	sim.map.routes.append(route)
	var dwell := FerryDwell.new({"maximum_loading": 32})
	var boat := Ferry.new(sim.operating_costs, dwell)
	boat.sim = sim
	boat.fc = FerryClass.of(2)
	boat._timetable.replace([400])
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
	var sim := Simulation.new(Vehicle.new.unbind(1))
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
	sim._process(1.0)
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
