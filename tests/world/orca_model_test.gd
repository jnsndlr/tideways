extends "res://tests/rule_test_case.gd"
## Shader-painted markings use authored UVs. The classic mesh carries painted vertex colors.


func _initialize() -> void:
	var authored := not "--classic-orca" in OS.get_cmdline_user_args()
	var mesh := Models.orca()
	check(mesh == Models.orca(), "Orcas share one mesh per variant")
	check(mesh.get_surface_count() == 1, "Orca has one shader surface")
	if mesh.get_surface_count() == 1:
		var data := mesh.surface_get_arrays(0)
		check(data[Mesh.ARRAY_COLOR].size() > 0, "Orca vertices carry fin heights")
		check((data[Mesh.ARRAY_TEX_UV] != null) == authored, "Only authored orcas use UV markings")
	var orca := Cetaceans.body_material("orca")
	check(orca.get_shader_parameter("orca_markings") == authored, "Orca markings match its mesh")
	var whale := Cetaceans.body_material("humpback")
	check(whale.get_shader_parameter("orca_markings") == false, "Whales keep their own markings")
	finish()
