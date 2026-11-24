extends SceneTree

var failures := 0

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	_check_midnight_costs()
	var sim := Simulation.new()
	var ledger := sim.ledger
	check(is_equal_approx(ledger.vehicle_fare, 18.0) and is_equal_approx(ledger.passenger_fare, 6.0), "Default ticket prices")
	var car := Vehicle.new()
	car.setup(BoxMesh.new(), false, "sedan_modern", Models.VEHICLE_SCALE)
	check(car.slots == 1 and car.fare_multiplier() == 1, "Sedan takes 1 slot and pays 1x")
	sim.collect_fare(car)
	check(is_equal_approx(sim.revenue_today, 18.0), "Standard car fare")

	var van := Vehicle.new()
	van.setup(BoxMesh.new(), false, "van_cargo", Models.VEHICLE_SCALE)
	check(van.slots == 2 and van.fare_multiplier() == 2, "Van takes 2 slots and pays 2x")
	sim.collect_fare(van)
	check(is_equal_approx(sim.revenue_today, 54.0), "Van pays double vehicle fare")

	var small_truck := Vehicle.new()
	small_truck.setup(BoxMesh.new(), true, "truck_step", Models.VEHICLE_SCALE)
	check(small_truck.slots == 2 and small_truck.fare_multiplier() == 2, "Small truck takes 2 slots and pays 2x")
	sim.collect_fare(small_truck)
	check(is_equal_approx(sim.revenue_today, 90.0), "Small truck pays double vehicle fare")

	var rig := Vehicle.new()
	rig.setup(BoxMesh.new(), true, "tractor_day", Models.VEHICLE_SCALE)
	rig.attach_trailer("trailer_container", BoxMesh.new())
	check(rig.slots >= 3 and rig.fare_multiplier() == 3, "Large truck takes ~3+ slots and pays 3x")
	sim.collect_fare(rig)
	check(is_equal_approx(sim.revenue_today, 144.0), "Large truck pays triple vehicle fare")

	sim.collect_passenger_fare()
	sim.collect_passenger_fare()
	check(sim.passengers_today == 2 and is_equal_approx(sim.revenue_today, 156.0), "Walk-on passenger fares")

	# Custom per-route and default ticket prices take effect immediately and shift demand.
	ledger.set_vehicle_fare(25.0)
	ledger.set_passenger_fare(10.0)
	sim.collect_fare(van)
	sim.collect_passenger_fare()
	check(is_equal_approx(sim.revenue_today, 216.0), "Custom vehicle (2x) and walk-on fares")
	ledger.set_route_vehicle_fare(7, 30.0)
	ledger.set_route_passenger_fare(7, 8.0)
	check(is_equal_approx(ledger.vehicle_fare_for(7), 30.0) and is_equal_approx(ledger.passenger_fare_for(7), 8.0), "Per-route fare overrides")
	check(is_equal_approx(ledger.vehicle_fare_for(2), 25.0), "Unset route falls back to default vehicle fare")
	check(TrafficDemand.price_multiplier(10.0, 18.0) > 1.0, "Lower fare increases demand")
	check(TrafficDemand.price_multiplier(30.0, 18.0) < 1.0, "Higher fare reduces demand")
	var expected_pax_caps := {1: 20, 2: 100, 3: 300, 4: 500, 5: 1000}
	for sz in expected_pax_caps:
		check(FerryClass.of(sz).passenger_capacity == expected_pax_caps[sz], "Class %d passenger capacity" % sz)

	check(sim.cars_today == 5 and sim.passengers_today == 3 and is_equal_approx(sim.revenue_today, 216.0), "Daily receipts")
	sim.minutes = 1439.0
	sim._process(2.0)
	check(sim.cars_today == 0 and sim.passengers_today == 0 and sim.revenue_today == 0.0 and is_equal_approx(sim.revenue_total, 216.0), "Midnight preserves lifetime receipts")
	check(ledger.cars_yesterday == 5 and ledger.passengers_yesterday == 3, "Yesterday's counts kept at midnight")
	check(is_equal_approx(ledger.cash, CompanyLedger.STARTING_CASH + 216.0), "Fares go into cash")
	check(is_equal_approx(CompanyLedger.net(ledger.yesterday), 216.0), "Yesterday's lines kept at midnight")
	ledger.spend("fuel", 30.0)
	ledger.spend("crew", 20.0)
	check(is_equal_approx(CompanyLedger.net(ledger.today), -50.0) and is_equal_approx(ledger.cash, CompanyLedger.STARTING_CASH + 166.0), "Running costs leave cash")
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


func _check_midnight_costs() -> void:
	var sim := Simulation.new()
	var boat := Ferry.new()
	boat.sim = sim
	boat.fc = FerryClass.of(2)
	boat.speed = boat.fc.cruise
	sim.ferries.append(boat)
	sim.minutes = 1439.5
	sim.ledger.cash = 0.0
	boat._burn(Ferry.METRES_PER_NM)
	var fuel := Ferry.FUEL_PRICE * boat.fc.burn
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
