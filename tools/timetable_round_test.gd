extends SceneTree
## Exercise repeated, late and overnight rounds without creating a region or ferry.

var failures := 0


func _initialize() -> void:
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


func _check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
