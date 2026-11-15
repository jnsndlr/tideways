extends SceneTree

var failures := 0

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	var sim := Simulation.new()
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
	sim.free()

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
	quit(1 if failures else 0)
