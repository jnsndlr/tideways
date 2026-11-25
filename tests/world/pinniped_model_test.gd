extends "res://tests/rule_test_case.gd"
## The meshes supply vertex colors to the animated seal and sea lion shader.


func _initialize() -> void:
	var authored := not "--classic-seals" in OS.get_cmdline_user_args()
	check(PinnipedModel.authored == authored, "The launch switch selects the expected variant")
	var seal := Models.harbor_seal()
	var lion := Models.sea_lion()
	check(seal != lion, "The two species use distinct meshes")
	check(seal == Models.harbor_seal() and lion == Models.sea_lion(), "Reuse each species' mesh")
	for mesh: ArrayMesh in [seal, lion]:
		check(mesh.get_surface_count() == 1, "Each species has one body surface")
		if mesh.get_surface_count() != 1:
			continue
		var data := mesh.surface_get_arrays(0)
		check(data[Mesh.ARRAY_VERTEX].size() > 0, "The mesh contains drawable geometry")
		check(
			data[Mesh.ARRAY_COLOR].size() == data[Mesh.ARRAY_VERTEX].size(),
			"Each vertex has coat color"
		)
		check((data[Mesh.ARRAY_INDEX] != null) == authored, "Authored geometry retains its indices")
		check(mesh.surface_get_material(0) == Models.vc_material(), "Use vertex-color material")
		check(mesh.shadow_mesh == null, "Animate the actual silhouette when drawing shadows")
	finish()
