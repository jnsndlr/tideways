extends SceneTree
## Sails one Sandbox ferry back and forth under each captain in turn and prints
## how long every crossing took beside the forecast the HUD shows, so the same
## ferry and route can be compared under both.
##
##   godot --headless --path . --fixed-fps 30 \
##     --script tests/traffic/captain_crossing_test.gd -- --seed=123 --ferry=0 --rounds=1
##
## Each round is a crossing there and back under each captain. A crossing held up
## by other traffic runs longer than its forecast; those are marked.

var main: Node
var frames := 0
var ferry_index := 0
var rounds := 2
var _plan: Array[Captain] = []
var _seen_trips := -1
var _held := false
var _timing := false
var _results := {}     # captain id -> Array of [minutes, held]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--ferry="):
			ferry_index = int(a.substr(8))
		if a.begins_with("--rounds="):
			rounds = int(a.substr(9))
	main = load("res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5:
		return false
	var sim: Simulation = main.sim
	var f: Ferry = sim.ferries[ferry_index % sim.ferries.size()]
	if frames == 5:
		Engine.time_scale = 4.0
		print("Unhindered crossing forecasts (game minutes):")
		for g in sim.ferries:
			var line := "  %-16s %s <-> %s, %4.0f m:" % [g.ferry_name, g.term_a.town.name, g.term_b.town.name, g.run_length()]
			for c in Captain.roster():
				line += "  %s %.1f" % [c.surname(), g.forecast_minutes(c)]
			print(line + "  -> suits " + g.best_captain().surname())
		for r in rounds:
			for c in Captain.roster():
				_plan.append(c)
				_plan.append(c)
		print("Sailing %s under each captain:" % f.ferry_name)
		f.assign_captain(_plan[0])
		_seen_trips = f.trips
		return false
	if f.state == Ferry.State.SAILING and f.captain == _plan[0] and f.traveled < 2.0:
		_timing = true
	if f.state == Ferry.State.SAILING and f.speed < 0.6 and f.traveled > 2.0:
		_held = true
	if f.trips == _seen_trips:
		if frames > 60000:
			push_error("Captain crossing test did not complete both captains within its frame budget")
			quit(1)
		return false
	_seen_trips = f.trips
	# (Only crossings begun from the dock under the planned captain count.)
	if _timing:
		_timing = false
		var c: Captain = _plan.pop_front()
		if not _results.has(c.id):
			_results[c.id] = []
		_results[c.id].append([f.last_crossing, _held])
		print("  %-14s to %-14s %.1f min (forecast %.1f)%s" % [c.name, f.here().town.name, f.last_crossing,
			f.forecast_minutes(c), "  held up by traffic" if _held else ""])
	_held = false
	if _plan.is_empty():
		for c in Captain.roster():
			var clean := 0.0
			var n := 0
			for r in _results[c.id]:
				if not r[1]:
					clean += r[0]
					n += 1
			print("%s: %s over %d unhindered crossings" % [c.name, "%.1f min" % (clean / n) if n else "no", n])
		print("TEST PASSED")
		quit(0)
		return true
	f.assign_captain(_plan[0])
	return false
