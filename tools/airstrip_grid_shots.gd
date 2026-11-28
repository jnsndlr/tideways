extends SceneTree
## Top-down shots of the story map's islands with a labelled 200 m grid, for
## reading off world positions (e.g. where an airstrip should go).
## godot --path . --resolution 1600x1600 --script tools/airstrip_grid_shots.gd -- --out=DIR
## --islands=Madrona Island,Bracken Island

var main: Node
var frames := 0
var out := "user://"
var names: PackedStringArray = ["Madrona Island", "Bracken Island"]
var views: Array = []
var shots := 0
var ready_at := -1
var wait := -1
var runway := false  # --runway: oblique shots of each island's airstrip instead, no grid


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a == "--runway":
			runway = true
		elif a.begins_with("--islands="):
			names = a.substr(10).split(",")
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _grid(c: Vector3, r: float) -> void:
	var step := 200.0
	var x0 := floorf((c.x - r) / step) * step
	var z0 := floorf((c.z - r) / step) * step
	var x := x0
	while x <= c.x + r:
		var z := z0
		while z <= c.z + r:
			var l := Label3D.new()
			l.text = "%d,%d" % [x, z]
			l.font_size = 400
			l.pixel_size = 0.1
			l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			l.no_depth_test = true
			l.modulate = Color(1, 0.1, 0.1)
			l.outline_size = 40
			l.position = Vector3(x, 120, z)
			main.builder.root.add_child(l)
			z += step
		x += step


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("rig") == null or main.get("sim") == null or main.get("map") == null:
		return false
	if ready_at < 0:
		ready_at = frames
		for isl: MapData.Island in main.map.islands:
			if runway and isl.airstrip:
				views.append([isl.name + "_runway", isl.airstrip_at, 520.0, 0.6, 0.4])
				views.append(
					[
						isl.name + "_end27",
						isl.airstrip_at + isl.airstrip_dir * 240.0,
						260.0,
						0.45,
						2.2
					]
				)
				views.append(
					[
						isl.name + "_end09",
						isl.airstrip_at - isl.airstrip_dir * 240.0,
						260.0,
						0.45,
						-1.0
					]
				)
				views.append(
					[
						isl.name + "_hangar",
						isl.airstrip_at + isl.airstrip_dir * -141.0,
						160.0,
						0.55,
						2.6
					]
				)
			elif not runway and names.has(isl.name):
				var c := Vector3(isl.center.x, 0, isl.center.y)
				_grid(c, isl.radius * 1.3)
				views.append([isl.name, c, isl.radius * 3.2, 1.45, 0.0])
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
	root.get_viewport().get_texture().get_image().save_png(
		"%s/grid_%s.png" % [out, str(v[0]).to_snake_case()]
	)
	shots += 1
	return false
