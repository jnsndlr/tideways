extends SceneTree
## Stage 4 projected daily cost (TID-24): the opening scenario's Hiyu is put on
## two sailings from Port Rosario. What she actually spends on fuel and crew from
## the time her crew come on until they stand down after the last round must
## match Ferry.daily_cost, the figure the stop editor shows. Economy pace must
## project less fuel than Service.
##
##   godot --headless --path . --fixed-fps 30 --script tools/daily_cost_test.gd

var main: Node
var frames := 0
var _plan := {}
var _fuel0 := 0.0
var _crew0 := 0.0
var _departures := 0
var _was_sailing := false


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _term(sim: Simulation, key: String) -> Terminal:
	for t: Terminal in sim.terminals.values():
		if t.island.key == key:
			return t
	return null


func _fuel(f: Ferry) -> float:
	return f.fuel_today + f._crossing_fuel


func _crew(f: Ferry) -> float:
	return f.crew_today + f._crew_owed


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var hiyu := sim.ferries[0]
	if frames == 5:
		Engine.time_scale = 6.0
		var ids: Array[int] = [_term(sim, "island-1").island.id, _term(sim, "island-2").island.id]
		var round_min := hiyu.plan_offsets(ids)[-1]
		var times: Array[int] = [400, 400 + ceili(round_min)]
		if not sim.reschedule(hiyu, ids, times):
			return _fail("Refused a timetable a round apart")
		_plan = hiyu.daily_cost(ids, times)
		var slow := hiyu.daily_cost(ids, times, 0)
		print("Projected: fuel $%.2f, crew $%.2f (%.2f h), economy fuel $%.2f, at %s" % [
			_plan.fuel, _plan.crew, _plan.hours, slow.fuel, sim.clock_text()])
		if not slow.fuel < _plan.fuel * 0.8:
			return _fail("Economy pace doesn't project less fuel")
		if hiyu.planned_daily_cost() != _plan:
			return _fail("planned_daily_cost differs from the timetable's daily_cost")
		return false
	if frames == 48:
		if not hiyu.off_shift():
			return _fail("Crew are on 40 min before her first sailing")
		_fuel0 = _fuel(hiyu)
		_crew0 = _crew(hiyu)
		return false
	if frames < 48:
		return false
	var sailing := hiyu.state == Ferry.State.SAILING
	if sailing and not _was_sailing:
		_departures += 1
		print("Sailed at %s · %s" % [sim.clock_text(), hiyu.status_text()])
	_was_sailing = sailing
	if _departures >= 4 and hiyu.call == 0 and hiyu.off_shift():
		var fuel := _fuel(hiyu) - _fuel0
		var crew := _crew(hiyu) - _crew0
		print("Actual at %s: fuel $%.2f, crew $%.2f" % [sim.clock_text(), fuel, crew])
		if absf(fuel - _plan.fuel) > _plan.fuel * 0.02:
			return _fail("Fuel $%.2f is off the projected $%.2f" % [fuel, _plan.fuel])
		if absf(crew - _plan.crew) > _plan.crew * 0.01:
			return _fail("Crew $%.2f is off the projected $%.2f" % [crew, _plan.crew])
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 30 * 60 * 10:
		return _fail("Timed out at %s: %s" % [sim.clock_text(), hiyu.status_text()])
	return false
