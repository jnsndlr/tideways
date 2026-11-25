extends SceneTree
## Exercise repeated, late and overnight rounds without creating a region or ferry.

var failures := 0


func _initialize() -> void:
	_check_dwell()
	var schedule := Timetable.new()
	var times: Array[int] = [1410, 30]
	var offsets: Array[float] = [0.0, 40.0]
	schedule.replace(times)
	_check(times == [1410, 30] and schedule.departures == [30, 1410], "Sorting a new plan must leave its input unchanged.")
	_check(schedule.call_due(1, offsets) == -1.0, "A stop cannot be due before a round starts.")
	_check(schedule.first_stop_due(1420.0, 15.0) == 1410.0, "A fresh plan may run a recently missed round late.")
	_check(schedule.first_stop_due(1435.0, 15.0) == 1410.0, "The due departure must stay fixed while boarding.")
	schedule.leave_first_stop()
	_check(schedule.call_due(1, offsets) == 1450.0, "The last round's second call must cross midnight.")
	_check(schedule.call_due(2, offsets) == -1.0, "An unknown call cannot be due.")
	_check(schedule.first_stop_due(2855.0, 15.0) == 1470.0, "A boat running late must still take the next round in order.")
	schedule.replace([60])
	_check(schedule.last_departure == -1.0 and schedule.call_due(1, offsets) == -1.0, "Replacing a plan must clear the old round.")
	_check(schedule.first_stop_due(200.0, 15.0) == 1500.0, "A fresh plan skips departures outside its grace period.")
	schedule.replace([])
	_check(schedule.first_stop_due(100.0, 15.0) == -1.0, "Loading-based service must have no timed round.")
	if failures == 0:
		print("TEST PASSED")
	quit(int(failures > 0))


func _check_dwell() -> void:
	var defaults := FerryDwell.new()
	_check(defaults.planned_dwell(5) == 24.0, "A small deck uses the 10-minute minimum loading time.")
	_check(defaults.planned_dwell(50) == 74.0, "A large deck uses the 24-minute maximum loading time.")
	for invalid: Variant in [null, [], {"minimum_loading": NAN, "maximum_loading": -1}, {"minimum_loading": 25},
			{"boarding_close": 24}, {"apron_lift": 9}]:
		var dwell := FerryDwell.new(invalid)
		_check(dwell.minimum_loading == 10.0 and dwell.maximum_loading == 24.0
				and dwell.boarding_close == 8.0 and dwell.apron_lift == 2.0, "Invalid boarding window uses safe defaults.")

	var partial := FerryDwell.new({"planned_car_gap": "1", "unload_clearance": 0})
	_check(partial.planned_unload(10) == 8.0, "An invalid car gap preserves an explicit zero clearance.")
	var dwell := FerryDwell.new({"minimum_loading": 6, "maximum_loading": 15, "boarding_close": 5,
			"apron_lift": 1, "planned_car_gap": 1.0, "unload_clearance": 3.0})
	_check(dwell.planned_unload(20) == 23.0 and dwell.planned_dwell(20) == 43.0, "Full-deck plan uses configured times.")
	_check(not dwell.boarding_open(0, 84.9, 100, 80) and dwell.boarding_open(0, 85, 100, 80),
			"Scheduled boarding starts exactly at the configured boundary.")
	_check(dwell.boarding_open(9, 94.9, 100, 80) and not dwell.boarding_open(10, 95, 100, 80),
			"Scheduled boarding closes exactly at the configured boundary.")
	_check(not dwell.ready_to_lift(18, 98, 100, 80, true) and dwell.ready_to_lift(19, 99, 100, 80, true),
			"An on-time boat raises the apron one configured minute before departure.")
	_check(not dwell.ready_to_lift(5, 101, 100, 96, true) and dwell.ready_to_lift(6, 102, 100, 96, true),
			"A late boat still spends the minimum time loading.")
	_check(dwell.boarding_open(14.9, 110, -1, 95) and not dwell.boarding_open(15, 110, -1, 95)
			and dwell.ready_to_lift(15, 110, -1, 95, false), "Unscheduled boarding ends at the configured maximum.")


func _check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
