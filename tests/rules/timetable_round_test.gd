extends "res://tests/rule_test_case.gd"
## Exercise repeated, late and overnight rounds without creating a region or ferry.


func _initialize() -> void:
	_check_dwell()
	var schedule := Timetable.new()
	var times: Array[int] = [1410, 30]
	var offsets: Array[float] = [0.0, 40.0]
	schedule.replace(times)
	check(times == [1410, 30] and schedule.departures == [30, 1410], "Sorting a new plan must leave its input unchanged.")
	check(schedule.call_due(1, offsets) == -1.0, "A stop cannot be due before a round starts.")
	check(schedule.first_stop_due(1420.0, 15.0) == 1410.0, "A fresh plan may run a recently missed round late.")
	check(schedule.first_stop_due(1435.0, 15.0) == 1410.0, "The due departure must stay fixed while boarding.")
	schedule.leave_first_stop()
	check(schedule.call_due(1, offsets) == 1450.0, "The last round's second call must cross midnight.")
	check(schedule.call_due(2, offsets) == -1.0, "An unknown call cannot be due.")
	check(schedule.first_stop_due(2855.0, 15.0) == 1470.0, "A boat running late must still take the next round in order.")
	schedule.replace([60])
	check(schedule.last_departure == -1.0 and schedule.call_due(1, offsets) == -1.0, "Replacing a plan must clear the old round.")
	check(schedule.first_stop_due(200.0, 15.0) == 1500.0, "A fresh plan skips departures outside its grace period.")
	schedule.replace([])
	check(schedule.first_stop_due(100.0, 15.0) == -1.0, "Loading-based service must have no timed round.")
	finish()


func _check_dwell() -> void:
	var defaults := FerryDwell.new()
	check(
		defaults.planned_dwell(5) == 21.0, "A small deck uses the 10-minute minimum loading time."
	)
	check(defaults.planned_dwell(50) == 49.0, "The deck dispatch time converts to game minutes.")
	for invalid: Variant in [null, [], {"minimum_loading": NAN, "maximum_loading": -1}, {"minimum_loading": 25},
			{"boarding_close": 24}, {"apron_lift": 9}]:
		var dwell := FerryDwell.new(invalid)
		check(dwell.minimum_loading == 10.0 and dwell.maximum_loading == 24.0
				and dwell.boarding_close == 8.0 and dwell.apron_lift == 2.0, "Invalid boarding window uses safe defaults.")

	var partial := FerryDwell.new({"planned_car_gap": "1", "unload_clearance": 0})
	check(
		partial.planned_unload(10) == 4.0,
		"An invalid car gap preserves an explicit zero clearance."
	)
	var dwell := FerryDwell.new(
		{
			"minimum_loading": 6,
			"maximum_loading": 15,
			"boarding_close": 5,
			"apron_lift": 1,
			"planned_car_gap": 1.0,
			"unload_clearance": 3.0
		}
	)
	check(
		dwell.planned_unload(20) == 11.5 and dwell.planned_dwell(20) == 26.5,
		"Full-deck plan uses configured times."
	)
	check(
		not dwell.boarding_open(0, 84.9, 100, 80) and dwell.boarding_open(0, 85, 100, 80),
		"Scheduled boarding starts exactly at the configured boundary."
	)
	check(
		dwell.boarding_open(9, 94.9, 100, 80) and not dwell.boarding_open(10, 95, 100, 80),
		"Scheduled boarding closes exactly at the configured boundary."
	)
	check(
		(
			not dwell.ready_to_lift(18, 98, 100, 80, true)
			and dwell.ready_to_lift(19, 99, 100, 80, true)
		),
		"An on-time boat raises the apron one configured minute before departure."
	)
	check(
		(
			not dwell.ready_to_lift(5, 101, 100, 96, true)
			and dwell.ready_to_lift(6, 102, 100, 96, true)
		),
		"A late boat still spends the minimum time loading."
	)
	check(
		(
			dwell.boarding_open(14.9, 110, -1, 95)
			and not dwell.boarding_open(15, 110, -1, 95)
			and dwell.ready_to_lift(15, 110, -1, 95, false)
		),
		"Unscheduled boarding ends at the configured maximum."
	)
