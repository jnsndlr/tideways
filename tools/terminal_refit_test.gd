extends SceneTree
## Advance a terminal's crane job without scene nodes or hulls.

var job := TerminalRefit.new()
var events: Array[String] = []
var failures := 0


func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)


func _initialize() -> void:
	job.stage_changed.connect(func() -> void: events.append(TerminalRefit.Stage.keys()[job.stage]))
	job.widen_slip.connect(func(i: int) -> void: events.append("widen %d during %s" % [i, TerminalRefit.Stage.keys()[job.stage]]))
	job.open_new_slip.connect(func(i: int) -> void: events.append("open %d during %s" % [i, TerminalRefit.Stage.keys()[job.stage]]))
	for building: bool in [false, true]:
		check_job(building)
		for starting_stage in [TerminalRefit.Stage.ARRIVING, TerminalRefit.Stage.WORKING, TerminalRefit.Stage.LEAVING]:
			for extra: float in [0.0, 30.0]:
				check_large_step(building, starting_stage, extra)
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_job(building: bool) -> void:
	events.clear()
	job.start(2, 60.0, building)
	check(job.occupies(2) and job.slip_shut(2) and not job.occupies(1), "Only the purchased slip closes")
	job.advance(50.0, false)
	check(job.stage == TerminalRefit.Stage.CLEARING and job.remaining == 100.0, "The crane waits for clearance without consuming time")
	job.advance(50.0, true)
	check(job.stage == TerminalRefit.Stage.ARRIVING and job.remaining == 100.0, "The arrival clock starts when the slip clears")
	job.advance(10.0, false)
	check(job.progress() == 0.5, "Halfway through arrival")
	job.advance(10.0, false)
	check(job.stage == TerminalRefit.Stage.WORKING and job.progress() == 0.0, "Work starts at the arrival boundary")
	job.advance(30.0, false)
	check(job.progress() == 0.5, "Work progress uses this purchase's duration")
	job.advance(30.0, false)
	check(job.stage == TerminalRefit.Stage.LEAVING and job.progress() == 0.0, "Departure starts at the work boundary")
	check(job.occupies(2) and job.slip_shut(2) != building, "Only new slips can open while the crane is leaving")
	job.advance(10.0, false)
	check(job.progress() == 0.5, "Halfway through departure")
	job.advance(100.0, false)
	job.advance(20.0, true)
	check(job.slip == -1 and not job.new_slip and job.remaining == 0.0 and not job.occupies(2), "A completed job releases the crane")
	var changes := ["CLEARING", "ARRIVING", "WORKING"]
	if not building:
		changes.append("widen 2 during WORKING")
	changes.append("LEAVING")
	if building:
		changes.append("open 2 during LEAVING")
	changes.append("NONE")
	check(events == changes, "Work effects and stage notifications run once in order: %s" % [events])


func check_large_step(building: bool, starting_stage: TerminalRefit.Stage, extra: float) -> void:
	job.start(2, 60.0, building)
	job.advance(0.0, true)
	if starting_stage >= TerminalRefit.Stage.WORKING:
		job.advance(TerminalRefit.ARRIVAL, true)
	if starting_stage == TerminalRefit.Stage.LEAVING:
		job.advance(job.work, true)
	events.clear()
	job.advance(job.remaining + extra, true)
	job.advance(10.0, true)
	var expected := []
	if starting_stage != TerminalRefit.Stage.LEAVING:
		if not building:
			expected.append("widen 2 during %s" % TerminalRefit.Stage.keys()[starting_stage])
		expected.append("LEAVING")
		if building:
			expected.append("open 2 during LEAVING")
	expected.append("NONE")
	check(events == expected, "A jump from %s must apply every outstanding effect once: %s" % [TerminalRefit.Stage.keys()[starting_stage], events])
	check(not job.occupies(2) and job.slip == -1 and job.remaining == 0.0, "The crane is free after the large step")
