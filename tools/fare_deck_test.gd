extends SceneTree

var failures := 0

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
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
	var fuel := FerryOperatingCosts.FUEL_PRICE * boat.fc.burn
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
