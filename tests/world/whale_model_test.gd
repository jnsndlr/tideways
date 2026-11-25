extends "res://tests/rule_test_case.gd"
## Check the two species selected by the whale switch and cached by Models.


func _initialize() -> void:
	var authored := not "--classic-whales" in OS.get_cmdline_user_args()
	check(WhaleModel.authored == authored, "The whale switch selects the expected family")
	var humpback := Models.humpback()
	var gray := Models.gray_whale()
	check(humpback == Models.humpback() and gray == Models.gray_whale(), "Both whales reuse meshes")
	check(humpback != gray, "Gray and humpback whales keep distinct geometry")
	for mesh: ArrayMesh in [humpback, gray]:
		check(mesh.get_surface_count() == 1, "Each whale has one body surface")
		if mesh.get_surface_count() != 1:
			continue
		var data := mesh.surface_get_arrays(0)
		check(data[Mesh.ARRAY_VERTEX].size() > 0, "Whale body has drawable geometry")
		check(
			data[Mesh.ARRAY_COLOR].size() == data[Mesh.ARRAY_VERTEX].size(),
			"Vertex colors carry fin weights"
		)
		check((data[Mesh.ARRAY_INDEX] != null) == authored, "Only the authored mesh is indexed")
		check(mesh.surface_get_material(0) == Models.vc_material(), "Keep vertex-color material")
		check(mesh.shadow_mesh == null, "Whale shader animation supplies the deformed silhouette")
	finish()
