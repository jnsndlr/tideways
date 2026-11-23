extends SceneTree
## Stage 4 manual timetable: the opening scenario's Hiyu is put on sailings from
## Port Rosario at 6:40 AM and a round later. She must refuse sailings closer
## than a round, keep her crew off while she waits for her first sailing, leave
## each stop on time (never early), and flag her timetable red, without moving
## it, when a slower pace makes a sailing impossible.
##
##   godot --headless --path . --fixed-fps 30 --script tools/timetable_test.gd

var main: Node
var frames := 0
var _times: Array[int] = []
var _offsets: Array[float] = []
var _was_sailing := false
var _departures := 0
var _crew_at_start := 0.0
var _unload_from := -1.0
var _unload_cars := 0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _term(sim: Simulation, key: String) -> Terminal:
	for t: Terminal in sim.terminals.values():
		if t.town.key.begins_with(key + "/"):
			return t
	return null


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var hiyu := sim.ferries[0]
	var rosario := _term(sim, "island-1")
	var madrona := _term(sim, "island-2")
	if frames == 5:
		if Timetable.parse("6:60") != -1 or Timetable.parse("6:-15") != -1 or Timetable.parse("23:59") != 1439:
			return _fail("Invalid clock fields must not roll over into another hour")
		if not Timetable.any_too_soon([360], Timetable.DAY + 1):
			return _fail("A daily sailing cannot complete a round longer than a day")
		Engine.time_scale = 6.0
		var ids: Array[int] = [rosario.town.id, madrona.town.id]
		_offsets = hiyu.plan_offsets(ids)
		var round_min := _offsets[-1]
		print("Hiyu: leg %.1f min, dwell %.1f min (full deck), round %.1f min, at %s" % [
			hiyu.leg_minutes(hiyu.legs[0]), hiyu.planned_dwell(), round_min, sim.clock_text()])
		var tight: Array[int] = [400, 400 + floori(round_min) - 5]
		if sim.reschedule(hiyu, ids, tight):
			return _fail("Accepted sailings closer than a round")
		_times = [400, 400 + ceili(round_min)]
		if not sim.reschedule(hiyu, ids, _times):
			return _fail("Refused a timetable a round apart")
		hiyu.set_pace(0)
		if not hiyu.late_sailings().has(true):
			return _fail("Economy pace didn't flag the tight sailing red")
		if hiyu.timetable != _times:
			return _fail("Changing pace moved her timetable")
		hiyu.set_pace(Ferry.SERVICE_PACE)
		if hiyu.late_sailings().has(true):
			return _fail("Service pace still flags a sailing red")
		return false
	if frames == 32:
		# (cars that began boarding before her timetable was set are on by now)
		_crew_at_start = hiyu._crew_owed
	if frames == 48:
		print("%s · %s · forecast %.1f min" % [sim.clock_text(), hiyu.status_text(), hiyu.crossing_minutes()])
		if not hiyu.off_shift() or hiyu._crew_owed > _crew_at_start + 0.01:
			return _fail("Crew were paid waiting 40 min for her first sailing")
	if hiyu.state == Ferry.State.UNLOADING and _unload_from < 0.0:
		_unload_from = sim.minutes
		_unload_cars = hiyu._unload_queue.size()
	if hiyu.state == Ferry.State.LOADING and _unload_from >= 0.0:
		print("  Unloaded %d cars at %s in %.1f min" % [_unload_cars, hiyu.here().town.name, sim.minutes - _unload_from])
		_unload_from = -1.0
	var sailing := hiyu.state == Ferry.State.SAILING
	if sailing and not _was_sailing:
		var now := fmod(sim.minutes, 1440.0)
		var from := hiyu.stops[(hiyu.call - 1 + hiyu.stops.size()) % hiyu.stops.size()]
		var due: float = _times[_departures / 2] + _offsets[_departures % 2]
		print("Left %s at %s (due %s) · %s" % [sim.map.towns[from].name, sim.clock_text(), Timetable.text(due), hiyu.status_text()])
		if now < due - 0.01:
			return _fail("Left %.1f min early" % (due - now))
		if now > due + 3.0:
			return _fail("Left %.1f min late with time to spare" % (now - due))
		_departures += 1
		if _departures == 3:
			print("TEST PASSED")
			quit(0)
			return true
	_was_sailing = sailing
	if frames > 30 * 60 * 8:
		return _fail("Timed out at %s: %s" % [sim.clock_text(), hiyu.status_text()])
	return false
