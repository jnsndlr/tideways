extends SceneTree
const N := 120
## Frame/GPU cost per group of models on the main map: hides each group in turn and
## measures the drop against a baseline. Groups = geometry node names with digits/@ stripped.
## godot --path . --rendering-driver vulkan --resolution 1600x1000 --script
## tools/group_perf.gd (env GP_TOP=25 GP_CAM=0)
var main: Node
var frames := 0
var groups := {}  # name -> {nodes, tris, inst}
var order: Array = []
var step := -2  # -2 warmup, -1 baseline, i = group i hidden
var t0 := 0
var gpu := 0.0
var prims := 0
var base_ms := 0.0
var base_gpu := 0.0
var top := 25
var results: Array = []
var cams := [[0, 0, 2600, 0, 45], [2640, -300, 900, 300, 40], [0, -2400, 2600, 0, 35]]
var cam := 0


func _initialize() -> void:
	top = int(OS.get_environment("GP_TOP")) if OS.has_environment("GP_TOP") else top
	cam = int(OS.get_environment("GP_CAM")) if OS.has_environment("GP_CAM") else 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	main = load("res://scenes/main_map.tscn").instantiate()
	main.set("uncapped", true)
	root.add_child(main)
	Engine.max_fps = 0


func _key(n: Node) -> String:
	var s := String(n.name)
	var re := RegEx.new()
	re.compile("[0-9@_]+$|@.*")
	return re.sub(s, "", true)


func _tris(g: GeometryInstance3D) -> Array:
	var mesh: Mesh = null
	var inst := 1
	if g is MeshInstance3D:
		mesh = g.mesh
	elif g is MultiMeshInstance3D and g.multimesh:
		mesh = g.multimesh.mesh
		inst = (
			g.multimesh.visible_instance_count
			if g.multimesh.visible_instance_count >= 0
			else g.multimesh.instance_count
		)
	var t := 0
	if mesh:
		for s in mesh.get_surface_count():
			var arr = mesh.surface_get_arrays(s)
			var idx = arr[Mesh.ARRAY_INDEX]
			t += (
				(idx.size() if idx != null and idx.size() > 0 else arr[Mesh.ARRAY_VERTEX].size())
				/ 3
			)
	return [t * inst, inst]


func _collect() -> void:
	for g in main.find_children("*", "GeometryInstance3D", true, false):
		if not g.is_visible_in_tree():
			continue
		var k := _key(g)
		if not groups.has(k):
			groups[k] = {"nodes": [], "tris": 0, "inst": 0}
		var ti := _tris(g)
		groups[k].nodes.append(g)
		groups[k].tris += ti[0]
		groups[k].inst += ti[1]
	order = groups.keys()
	order.sort_custom(func(a, b): return groups[a].tris > groups[b].tris)
	order = order.slice(0, top)


func _set_vis(k: String, v: bool) -> void:
	for g in groups[k].nodes:
		if is_instance_valid(g):
			g.visible = v


func _process(_d: float) -> bool:
	frames += 1
	if frames == 20:
		var c: Array = cams[cam]
		main.rig.target_pos = Vector3(c[0], 0, c[1])
		main.rig.target_dist = c[2]
		main.rig.target_yaw = deg_to_rad(c[3])
		main.rig.target_pitch = deg_to_rad(c[4])
		main.rig.snap()
	if frames < 60:
		return false
	var f := (frames - 60) % (N + 30)
	if f == 30:
		t0 = Time.get_ticks_usec()
		gpu = 0.0
		prims = 0
	elif f > 30:
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid())
		prims = RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME
		)
	if f == N + 29:
		var ms := (Time.get_ticks_usec() - t0) / 1000.0 / N
		var g := gpu / N
		if step == -2:
			_collect()
		elif step == -1:
			base_ms = ms
			base_gpu = g
			print(
				(
					"BASE frame %.2f ms (%.0f fps) gpu %.2f ms prims %d draws %d"
					% [
						ms,
						1000.0 / ms,
						g,
						prims,
						RenderingServer.get_rendering_info(
							RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME
						)
					]
				)
			)
		else:
			var k: String = order[step]
			_set_vis(k, true)
			print(
				(
					"GROUP %-28s nodes %5d inst %7d tris %9d | frame -%.2f ms gpu -%.2f ms"
					% [
						k,
						groups[k].nodes.size(),
						groups[k].inst,
						groups[k].tris,
						base_ms - ms,
						base_gpu - g
					]
				)
			)
		step += 1
		if step >= order.size():
			return true
		if step >= 0:
			_set_vis(order[step], false)
	return false
