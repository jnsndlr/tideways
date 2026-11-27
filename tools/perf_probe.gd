extends SceneTree
## Measures frame and GPU time with render features switched off, to see what each
## costs. GPU timings need Vulkan on macOS (Metal has no timestamp queries); a game
## running at the same time skews the numbers, so compare runs made back to back.
##   godot --path . --rendering-driver vulkan --resolution 3200x1920 --script tools/perf_probe.gd \
##     -- --seed=9164 [--off=dof,ssao,vfog,glow,shadow,shadow2,aa,msaa,water,clouds,backdrop,mtrees,trees,treeshadow,grass,ground,scale75,census]
##     [--zoom=120] (camera distance, low over the grassiest ground: for the grass)
var main: Node
var frames := 0
var off := ""
var zoom := 0.0
## `--hide=A,B`: node name patterns to hide (find_children), e.g. "Pines*_lod1".
var hide_pat := ""
var t0 := 0
var n := 0
var gpu := 0.0

func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--off="):
			off = a.substr(6)
		elif a.begins_with("--hide="):
			hide_pat = a.substr(7)
		elif a.begins_with("--zoom="):
			zoom = float(a.substr(7))
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	# PP_MAIN=1: the main map instead of the sandbox; PP_CAM=0..2 picks a group_perf view.
	main = load("res://scenes/main_map.tscn" if OS.has_environment("PP_MAIN") else "res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)
	main.set("uncapped", true)
	Engine.max_fps = 0

func _apply() -> void:
	for p in hide_pat.split(",", false):
		_hide(main, p)
	var env: Environment = main.env
	for o in off.split(","):
		match o:
			"ssao": env.ssao_enabled = false
			"dof":
				main.cam_attr.dof_blur_near_enabled = false
				main.cam_attr.dof_blur_far_enabled = false
			"vfog": env.volumetric_fog_enabled = false
			"glow": env.glow_enabled = false
			"shadow": main.sun.shadow_enabled = false
			"shadow2": main.sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
			"aa": root.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
			"msaa":
				# The old setting, for comparison: MSAA 2x instead of SMAA.
				root.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
				root.msaa_3d = Viewport.MSAA_2X
			"water": _hide(main, "Water")
			"scale75": root.scaling_3d_scale = 0.75
			"clouds": _hide(main, "Clouds")
			"backdrop": _hide(main, "Backdrop")
			"mtrees": _hide(main, "MainlandPines*")
			"trees":
				_hide(main, "Pines*")
				_hide(main, "RoundTrees*")
			"alltrees":
				for nm in ["Pines*", "RoundTrees*", "MainlandPines*", "TreeCards*"]:
					_hide(main, nm)
			"treeshadow":
				# The shadow-only copies are hidden (switching their casting off would draw them).
				_hide(main, "*_shadow")
				for nm in ["Pines*", "RoundTrees*", "MainlandPines*"]:
					for c in main.find_children(nm, "GeometryInstance3D", true, false):
						if c.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
							c.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			"cards": _hide(main, "TreeCards*")
			"mland": _hide(main, "Mainland")
			"cumulus": _hide(main, "Cumulus")
			"grass": main.find_child("Grass", true, false).queue_free()
			"ground": main.builder.terrain_material.set_shader_parameter("detail", false)

## Low over the grassiest ground, looking across it.
func _frame_grass() -> void:
	var b: WorldBuilder = main.builder
	var t: Terrain = main.terrain
	var vn := t.n + 1
	var best := -1.0
	var at := Vector3.ZERO
	for j in range(40, vn - 40, 5):
		for i in range(40, vn - 40, 5):
			var k := j * vn + i
			var g := 0.0
			for o in [-24, -12, 0, 12, 24]:
				g += b.ground_rgba[(k + o) * 4 + 3] + b.ground_rgba[(k + o * vn) * 4 + 3]
			if g > best:
				best = g
				at = Vector3(-t.half_size + i * Terrain.CELL, t.h_grid[k], -t.half_size + j * Terrain.CELL)
	main.rig.focus_on(at, zoom)
	main.rig.distance = zoom
	main.rig.target_dist = zoom
	main.rig.pitch = 0.3
	main.rig.target_pitch = 0.3


func _hide(n: Node, nm: String) -> void:
	for c in n.find_children(nm, "", true, false):
		c.visible = false

func _process(_d: float) -> bool:
	frames += 1
	if frames == 20 and OS.has_environment("PP_CAM"):
		var c: Array = [[0, 0, 2600, 0, 45], [2640, -300, 900, 300, 40], [0, -2400, 2600, 0, 35], [600, 200, 250, 30, 30]][int(OS.get_environment("PP_CAM"))]
		main.rig.target_pos = Vector3(c[0], 0, c[1]); main.rig.target_dist = c[2]
		main.rig.target_yaw = deg_to_rad(c[3]); main.rig.target_pitch = deg_to_rad(c[4])
		main.rig.snap()
	if frames == 60:
		if zoom > 0.0:
			_frame_grass()
		_apply()
		if "lodcount" in off:
			_lodcount()
		if "census" in off:
			_census()
	if frames == 180:
		t0 = Time.get_ticks_usec()
	if frames > 180:
		n += 1
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(root.get_viewport_rid())
	if "shadow" in off.split(","):
		main.sun.shadow_enabled = false
	if frames == 600 and OS.has_environment("PP_SHOT"):
		root.get_texture().get_image().save_png(OS.get_environment("PP_SHOT"))
	if frames == 600:
		var rs := RenderingServer
		print("PROBE %-12s frame %.2f ms | gpu %.2f ms | px %s | prims %d | draws %d" % [off if off != "" else "baseline",
			(Time.get_ticks_usec() - t0) / 1000.0 / n, gpu / n, root.get_visible_rect().size,
			rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
			rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)])
		return true
	return false

func _tris(m: Mesh) -> int:
	if m == null:
		return 0
	var t := 0
	for i in m.get_surface_count():
		var a := m.surface_get_arrays(i)
		var idx = a[Mesh.ARRAY_INDEX]
		t += (idx.size() if idx != null else a[Mesh.ARRAY_VERTEX].size()) / 3
	return t

func _census() -> void:
	print("scale ", DisplayServer.screen_get_scale(), " tex ", root.get_texture().get_size())
	var rows := {}
	for n in main.find_children("*", "GeometryInstance3D", true, false):
		var k := ""
		var t := 0
		if n is MeshInstance3D:
			t = _tris(n.mesh)
			k = String(n.name).rstrip("0123456789@")
			if n.get_parent() is Vessel or n.get_parent().get_parent() is Vessel:
				k = "vessel:" + k
		elif n is MultiMeshInstance3D and n.multimesh:
			t = _tris(n.multimesh.mesh) * n.multimesh.visible_instance_count if n.multimesh.visible_instance_count >= 0 else _tris(n.multimesh.mesh) * n.multimesh.instance_count
			k = "MM:" + String(n.name)
		else:
			continue
		if not rows.has(k):
			rows[k] = [0, 0, 0]
		rows[k][0] += 1
		rows[k][1] += t
		if n.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
			rows[k][2] += t
	var ks := rows.keys()
	ks.sort_custom(func(a, b): return rows[a][1] > rows[b][1])
	for k in ks.slice(0, 30):
		print("CENSUS %-30s n=%4d tris=%8d shadowtris=%8d" % [k, rows[k][0], rows[k][1], rows[k][2]])

## Per tree group and level: triangles the tiles in range submit, against those of the
## trees the shader keeps (each tree's own distance inside its level's band).
func _lodcount() -> void:
	var cam := root.get_camera_3d().global_position
	var rows := {}
	for g in ["Pines*", "RoundTrees*", "MainlandPines*"]:
		for n: MultiMeshInstance3D in main.find_children(g, "MultiMeshInstance3D", true, false):
			if not n.is_visible_in_tree() or n.multimesh == null:
				continue
			var d := cam.distance_to(n.global_transform * n.get_aabb().get_center())
			var rb := n.visibility_range_begin
			var re := n.visibility_range_end
			if d < rb or (re > 0.0 and d > re):
				continue
			var mm := n.multimesh
			var tris := _tris(mm.mesh)
			var mat := n.material_override as ShaderMaterial
			if mat == null and mm.mesh is QuadMesh:
				mat = (mm.mesh as QuadMesh).material as ShaderMaterial
			var lb := 0.0
			var le := 0.0
			if mat and mat.shader and "tree" in mat.shader.resource_path:
				lb = mat.get_shader_parameter("lod_begin"); le = mat.get_shader_parameter("lod_end")
			var f := TreeLod.lod_fade * 0.5
			var kept := 0
			for i in mm.instance_count:
				var td := cam.distance_to(n.global_transform * mm.get_instance_transform(i).origin)
				if (lb <= 0.0 or td >= lb - f) and (le <= 0.0 or td <= le + f):
					kept += 1
			var k := String(n.name).split("_")[0] + ("_shadow" if String(n.name).ends_with("_shadow") else (String(n.name).right(5) if "_lod" in String(n.name) else "_lod0"))
			if not rows.has(k): rows[k] = [0, 0, 0]
			rows[k][0] += 1; rows[k][1] += tris * mm.instance_count; rows[k][2] += tris * (mm.instance_count if n.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY else kept)
	var ks := rows.keys(); ks.sort()
	for k in ks:
		print("LOD %-24s tiles %4d submitted %9d kept %9d" % [k, rows[k][0], rows[k][1], rows[k][2]])
