extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	var dalls := Models.dalls_porpoise()
	var harbor := Models.harbor_porpoise()
	check(dalls != harbor, "Porpoise species have distinct meshes")
	check(dalls == Models.dalls_porpoise(), "Reuse Dall's porpoise mesh")
	check(harbor == Models.harbor_porpoise(), "Reuse the harbor porpoise mesh")
	for mesh: ArrayMesh in [dalls, harbor]:
		check(mesh.get_surface_count() == 1, "One body surface per animal")
		if mesh.get_surface_count() != 1:
			continue
		var arrays := mesh.surface_get_arrays(0)
		var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
		check(colors.size() == mesh.surface_get_array_len(0), "Every vertex carries coat color")
		var fin := false
		var body := false
		for color in colors:
			if color.a < 0.95:
				fin = true
			else:
				body = true
		check(fin and body, "The shader can distinguish fin vertices from the body")
		check(mesh.surface_get_material(0) == Models.vc_material(), "Use the vertex-color material")
		check(mesh.shadow_mesh == null, "Use the animated silhouette for shadows")
	finish()
