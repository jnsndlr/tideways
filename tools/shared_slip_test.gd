extends SceneTree
## Two boats on different routes share Madrona's one slip (maps/shared_slip.json).
## The boats run at different paces so they meet there. Passes once one has held
## offshore for the other and then docked, with never two at the slip at once.
##
##   godot --headless --path . --fixed-fps 30 --script tools/shared_slip_test.gd -- --scenario=shared_slip

var main: Node
var frames := 0
var docked_at := {}     # ferry name -> times docked at the shared slip
var held_offshore := false
var _was := {}
var _held := []   # [the boat that held, its dockings then]


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	if frames == 5:
		Engine.time_scale = 6.0
		# Different paces so the two boats drift into each other at the slip.
		sim.ferries[1].pace = 0
		sim.ferries[0].pace = 2
		for isl in sim.map.islands:
			if isl.has_terminal:
				pass
		for r in sim.map.routes:
			for c in sim.marine.corridors[r.id]:
				print("Route %d (%.0f m) corridor span %s docked %s" % [r.id, r.length, c.span[r.id], c.docked[r.id]])
		for isl in sim.map.islands:
			if isl.has_terminal:
				print("%s: %s" % [isl.name, ", ".join(isl.slips.map(func(s): return "%s %s" % [s.size_name(), s.routes]))])
	var madrona: Terminal
	for term: Terminal in sim.terminals.values():
		if term.island.key == "island-2":
			madrona = term
	var here := 0
	for f in sim.ferries:
		var at_madrona := f.state != Ferry.State.SAILING and f.here() == madrona
		if at_madrona:
			here += 1
			if f.state == Ferry.State.UNLOADING and f._state_time < 0.05:
				docked_at[f.ferry_name] = docked_at.get(f.ferry_name, 0) + 1
		var waiting := f._waiting_for != null and f._waiting_for.here() == madrona and f._waiting_for.state != Ferry.State.SAILING
		if f.state == Ferry.State.SAILING and f.destination() == madrona and f.speed < 0.2 and waiting:
			if not held_offshore:
				print("Day %d %s: %s holds offshore %.0f m out while %s is at the slip" % [
					sim.day, sim.clock_text(), f.ferry_name, f.path_left(), f._waiting_for.ferry_name])
			held_offshore = true
			_held = [f.ferry_name, docked_at.get(f.ferry_name, 0)]
	for f in sim.ferries:
		var key := f.ferry_name
		var now: bool = f.state != Ferry.State.SAILING and f.here() == madrona
		if now != _was.get(key, false):
			print("  %s %s Madrona at %s" % [key, "at" if now else "leaves", sim.clock_text()])
			_was[key] = now
	if here > 1:
		push_error("Two boats docked at Madrona's one slip on frame %d" % frames)
		quit(1)
		return true
	if held_offshore and docked_at.get(_held[0], 0) > _held[1]:
		print("%s docked after holding" % _held[0])
		print("Docked at Madrona: %s" % docked_at)
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 40000:
		push_error("Gave up: docked %s, held offshore %s" % [docked_at, held_offshore])
		quit(1)
		return true
	return false
