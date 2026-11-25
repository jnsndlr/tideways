extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	var authored := not "--classic-net" in OS.get_cmdline_user_args()
	check(FerryNetModel.authored == authored, "The startup switch selects the expected net")
	var meshes: Array[ArrayMesh] = []
	for size in range(1, 6):
		var hull := FerryClass.of(size)
		var mesh := Models.ferry_net(hull)
		check(not meshes.has(mesh), "Each class owns its fitted net")
		meshes.append(mesh)
		check(mesh == Models.ferry_net(hull), "Reuse both ends of the same class")
		check(mesh.get_surface_count() == 1, "The net is a single surface")
		if mesh.get_surface_count() != 1:
			continue
		var bounds := mesh.get_aabb()
		check(bounds.position.x <= -hull.net_half_w + 0.001, "Net reaches the port deck edge")
		check(bounds.end.x >= hull.net_half_w - 0.001, "Net reaches the starboard deck edge")
		var colors: PackedColorArray = mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
		var lowest_alpha := 1.0
		var highest_alpha := 0.0
		for color in colors:
			lowest_alpha = minf(lowest_alpha, color.a)
			highest_alpha = maxf(highest_alpha, color.a)
		check(is_equal_approx(highest_alpha, 1.0), "The posts remain fixed")
		check((lowest_alpha < 0.75) == authored, "Authored rope carries wind weights")
		var material := mesh.surface_get_material(0) as ShaderMaterial
		if authored:
			check(material.shader.resource_path == "res://shaders/net.gdshader", "Wind shader")
			check(mesh.shadow_mesh == null, "Animate the net when drawing shadows")
		else:
			check(material == Models.vc_material(), "Classic rope uses the vertex-color shader")
			check(mesh.shadow_mesh != null, "Classic rope retains its static shadow geometry")
	finish()
