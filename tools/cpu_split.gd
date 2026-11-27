extends SceneTree
## Windowed main map: frame time with vessels / arbiter / all 3D hidden, to split CPU sim vs render-submit cost.
var main: Node
var frames := 0
var t0 := 0
var step := 0
var gpu := 0.0
const N := 90
func _initialize() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	main = load("res://scenes/main_map.tscn").instantiate()
	main.set("uncapped", true)
	root.add_child(main)
	Engine.max_fps = 0
func _pm(nodes: Array, on: bool) -> void:
	for n in nodes: if is_instance_valid(n): n.process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED
func _process(_d: float) -> bool:
	frames += 1
	if frames < 60: return false
	var f := (frames - 60) % (N + 20)
	if f == 20: t0 = Time.get_ticks_usec(); gpu = 0.0
	elif f > 20: gpu += RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid())
	if f != N + 19: return false
	var ms := (Time.get_ticks_usec() - t0) / 1000.0 / N
	var sim = main.sim
	var labels := ["all on (%d vessels)" % sim.marine.vessels.size(), "vessels off", "vessels+arbiter off", "+ 3D world hidden"]
	print("CPU %-28s frame %.2f ms  gpu %.2f ms  draws %d" % [labels[step], ms, gpu / N, RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)])
	step += 1
	match step:
		1: _pm(sim.marine.vessels.filter(func(v): return not v is Ferry), false)
		2: _pm([sim.marine], false)
		3:
			for c in main.get_children(): if c is Node3D and not c is Camera3D and c != main.rig: c.visible = false
		4: return true
	return false
