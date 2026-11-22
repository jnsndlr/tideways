extends SceneTree
## Stage 4, ties-ups between sailings (Ferry.GAP_TIE_UP): on the shared-slip map
## Rhododendron runs Madrona → Gullrock on two sailings with a long gap between
## them. Back at Madrona after the first she must move to its tie-up slip with
## her crew still paid, come back and leave on time for the second, and after
## the last sailing of the day tie up again with her crew stood down. Hiyu, who
## shares Madrona's slip, is put on one evening sailing so she stays out of the way
## (a boat sailing as loading allows would take the free slip and make her late).
##
##   godot --headless --path . --fixed-fps 30 --script tools/gap_tie_up_test.gd -- --scenario=shared_slip

var main: Node
var frames := 0
var phase := 0
var _times: Array[int] = []
var _was_sailing := false
var _departures := 0


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


## Whether a few minutes' wages would be paid to her crew now.
func _crew_paid(f: Ferry) -> bool:
	var before := f._crew_owed
	f.pay_crew(5.0)
	var paid := f._crew_owed > before
	f._crew_owed = before
	return paid


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var rhodo := sim.ferries[1]
	var madrona := _term(sim, "island-2")
	var gullrock := _term(sim, "island-7")
	if frames == 5:
		Engine.time_scale = 12.0
		var ids: Array[int] = [madrona.island.id, gullrock.island.id]
		var round_min := rhodo.plan_offsets(ids)[-1]
		var first := int(ceil(fmod(sim.minutes, 1440.0) / 5.0)) * 5 + 180
		_times = [first, first + ceili(round_min) + 200]
		print("%s: Rhododendron round %.0f min, sailings %s and %s" % [
			sim.clock_text(), round_min, Timetable.text(_times[0]), Timetable.text(_times[1])])
		if not sim.reschedule(rhodo, ids, _times):
			return _fail("Refused the timetable")
		var hiyu := sim.ferries[0]
		var evening: Array[int] = [1260]
		if not sim.reschedule(hiyu, hiyu.stops, evening):
			return _fail("Refused Hiyu's evening sailing")
		return false
	var sailing := rhodo.state == Ferry.State.SAILING and rhodo.berth == Ferry.Berth.WORKING
	if sailing and not _was_sailing and rhodo.stops[0] == madrona.island.id and rhodo.call == 1:
		var due := float(_times[_departures % 2])
		var now := fmod(sim.minutes, 1440.0)
		print("%s: left Madrona (due %s)" % [sim.clock_text(), Timetable.text(due)])
		if _departures >= 1:
			if now < due - 0.01:
				return _fail("Left %.1f min early" % (due - now))
			if now > due + 3.0:
				return _fail("Left %.1f min late after lying at the tie-up" % (now - due))
		_departures += 1
	_was_sailing = sailing
	match phase:
		0:
			if _departures == 1 and rhodo.berth == Ferry.Berth.TIED_UP:
				print("%s: %s" % [sim.clock_text(), rhodo.status_text()])
				if not rhodo.between_sailings() or not rhodo.in_service():
					return _fail("Tied up but not between sailings")
				if not _crew_paid(rhodo):
					return _fail("Crew stood down in a daytime gap")
				if rhodo.here() != madrona:
					return _fail("Tied up away from Madrona")
				phase = 1
		1:
			if _departures == 2:
				phase = 2
		2:
			if rhodo.berth == Ferry.Berth.TIED_UP and rhodo.here() == madrona:
				print("%s: after the last sailing · %s" % [sim.clock_text(), rhodo.status_text()])
				phase = 3
		3:
			# Overnight: crew off once she is due back and unloaded (shift_tail).
			if rhodo.off_shift():
				if _crew_paid(rhodo):
					return _fail("Crew paid overnight at the tie-up")
				print("%s: crew stood down overnight at the tie-up" % sim.clock_text())
				print("TEST PASSED")
				quit(0)
				return true
			if rhodo.berth != Ferry.Berth.TIED_UP:
				return _fail("Left the tie-up overnight (%s)" % rhodo.status_text())
	if frames > 30 * 60 * 20:
		return _fail("Timed out at %s (phase %d): %s" % [sim.clock_text(), phase, rhodo.status_text()])
	return false
