extends "res://tests/rule_test_case.gd"
## The wing shader and shared geometry must agree on the selected gull variant.


func _initialize() -> void:
	var authored := not "--classic-gull" in OS.get_cmdline_user_args()
	var mesh := Models.seagull()
	check(mesh == Models.seagull(), "All gulls of the same variant share their mesh")
	check(mesh.get_surface_count() == 1, "The gull has one shader surface")
	if mesh.get_surface_count() == 1:
		var data := mesh.surface_get_arrays(0)
		check(data[Mesh.ARRAY_VERTEX].size() > 0, "The gull has drawable geometry")
		check((data[Mesh.ARRAY_TEX_UV2] != null) == authored, "Only authored wings use folded UV2")
	var material := SeagullModel.wing_material()
	check(material.get_shader_parameter("baked_fold") == authored, "Wing pose matches the mesh")
	finish()
