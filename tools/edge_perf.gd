extends SceneTree
## Frame and GPU time looking at the map's edge on the main map (Vulkan for GPU).
##   godot --path . --rendering-driver vulkan --resolution 1600x1000 --script tools/edge_perf.gd [-- --hide=MainlandPines*,TreeCards*]
var main: Node
var frames := 0
var gpu := 0.0
var t0 := 0
var cam := 0
var hide := ""
var cams := [[2640, -300, 3600, 300, 55], [2640, -1200, 2000, 270, 40], [0, -2400, 2600, 0, 35]]

func _initialize() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	main = load("res://scenes/main_map.tscn").instantiate()
	main.set("uncapped", true)
	root.add_child(main)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--hide="):
			hide = a.substr(7)
	Engine.max_fps = 0

func _process(_d: float) -> bool:
	frames += 1
	var f := frames % 200
	if frames > 30 and f == 0:
		if cam > 0:
			print("EDGE cam%d frame %.2f ms | gpu %.2f ms | prims %d" % [cam - 1, (Time.get_ticks_usec() - t0) / 100000.0, gpu / 100.0,
				RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)])
		if cam >= cams.size():
			return true
		for nm in hide.split(",", false):
			for c in main.find_children(nm, "", true, false):
				c.visible = false
		var c: Array = cams[cam]
		main.rig.target_pos = Vector3(c[0], 0, c[1])
		main.rig.target_dist = c[2]
		main.rig.target_yaw = deg_to_rad(c[3])
		main.rig.target_pitch = deg_to_rad(c[4])
		main.rig.snap()
		cam += 1
		gpu = 0.0
	if cam > 0 and f == 100:
		t0 = Time.get_ticks_usec()
		gpu = 0.0
	if cam > 0 and f > 100:
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid())
	return false
