extends SceneTree
## Sends Port Rosario's coast guard boats out at once, runs fast, and shoots each
## boat under way plus a log of when each one sails and berths again.
##   godot --path . --resolution 1600x1000 --script tools/coast_guard_patrol_test.gd -- --out=DIR

var main: Node
var frames := 0
var out := "user://"
var started := -1
var was := {}
var shot := 0


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("sim") == null or main.sim.get("marine") == null or main.sim.marine.coast_guard.is_empty():
		return frames > 3000
	var boats: Array = main.sim.marine.coast_guard
	if started < 0:
		started = frames
		for b: CoastGuardBoat in boats:
			b._sail_at = 0.0
			was[b] = true
		Engine.time_scale = 6.0
	for b: CoastGuardBoat in boats:
		if was[b] != b.docked:
			print("%s %s at frame %d (s %.0f / %.0f)" % [b.vessel_name, "berthed" if b.docked else "sailed", frames, b.s, b.path.length])
			was[b] = b.docked
	var t := frames - started
	if t % 3000 == 0:
		for b: CoastGuardBoat in boats:
			print("  %s s %.0f/%.0f speed %.1f yield %.1f %s" % [b.vessel_name, b.s, b.path.length, b.speed, b.yield_speed(), b.holding_text()])
	if t in [300, 700, 1100] and shot < boats.size():
		var b: CoastGuardBoat = boats[shot]
		var p := b.global_position
		Engine.time_scale = 0.0
		main.rig.focus_on(p, 140.0)
		main.rig.target_pos = p
		main.rig.position = p
		main.rig.distance = 140.0
		main.rig.target_dist = 140.0
		main.rig.target_pitch = 0.5
		main.rig.pitch = 0.5
	if t in [330, 730, 1130] and shot < boats.size():
		var img := root.get_viewport().get_texture().get_image()
		if img:
			img.save_png("%s/patrol_%d.png" % [out, shot])
		shot += 1
		Engine.time_scale = 6.0
	return t > 40000 or (t > 400 and boats.all(func(b): return b.docked))
