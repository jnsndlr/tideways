extends SceneTree
## Shots of Port Rosario's coast guard station: a top-down 50 m grid (--grid) for
## reading positions, and oblique views like the player's camera.
##   godot --path . --resolution 1600x1000 --script tools/coast_guard_shots.gd -- --out=DIR [--grid]

const AT := Vector3(2520.0, 0.0, -680.0)
var main: Node
var frames := 0
var out := "user://"
var grid := false
var views: Array = []
var shots := 0
var ready_at := -1
var wait := -1


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a == "--grid":
			grid = true
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _labels(c: Vector3, r: float, step: float) -> void:
	var x := floorf((c.x - r) / step) * step
	while x <= c.x + r:
		var z := floorf((c.z - r) / step) * step
		while z <= c.z + r:
			var l := Label3D.new()
			l.text = "%d,%d" % [x, z]
			l.font_size = 120
			l.pixel_size = 0.1
			l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			l.no_depth_test = true
			l.modulate = Color(1, 0.1, 0.1)
			l.outline_size = 20
			l.position = Vector3(x, 40, z)
			main.builder.root.add_child(l)
			z += step
		x += step


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("rig") == null or main.get("sim") == null or main.get("map") == null:
		return false
	if ready_at < 0:
		ready_at = frames
		if grid:
			_labels(AT, 260.0, 50.0)
			views.append(["grid", AT, 700.0, 1.45, 0.0])
		else:
			views.append(["wide", AT + Vector3(80, 0, 150), 600.0, 0.6, -PI * 0.5])
			views.append(["close", AT, 260.0, 0.5, -PI * 0.5])
			views.append(["close_b", AT, 220.0, 0.45, -PI * 0.2])
			views.append(["radar", Vector3(2539.0, 10.0, -735.0), 90.0, 0.35, -PI * 0.35])
	if frames - ready_at < 60:
		return false
	if shots >= views.size():
		return true
	var v: Array = views[shots]
	main.sim.minutes = 12 * 60.0
	main.rig.focus_on(v[1], v[2])
	main.rig.target_pos = v[1]
	main.rig.position = v[1]
	main.rig.distance = v[2]
	main.rig.target_dist = v[2]
	main.rig.target_pitch = v[3]
	main.rig.pitch = v[3]
	main.rig.target_yaw = v[4]
	main.rig.yaw = v[4]
	if wait < 0:
		wait = frames
	if frames - wait < 40:
		return false
	wait = -1
	root.get_viewport().get_texture().get_image().save_png("%s/cg_%s.png" % [out, v[0]])
	shots += 1
	return false
