extends "res://tests/rule_test_case.gd"
## Verify the tug’s three liveries and its wheelhouse, navigation and mast lights.


func _initialize() -> void:
	var authored := not "--classic-tug" in OS.get_cmdline_user_args()
	check(TugModel.authored == authored, "Launch switch selects the tug model")
	var spec := VesselTypes.tugs()[0]
	var paint: Array[PackedColorArray] = []
	for variant in spec.variants:
		var mesh := VesselAppearance.hull(spec, variant)
		check(mesh == Models.tug(variant), "Reuse hull mesh for the same livery")
		check(mesh.get_surface_count() == 1, "Hull has one painted surface")
		if mesh.get_surface_count() != 1:
			continue
		var colors: PackedColorArray = mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
		check(colors.size() == mesh.surface_get_array_len(0), "Paint reaches every hull vertex")
		check(not colors in paint, "Each tug livery has distinct colors")
		paint.append(colors)
		check(mesh.surface_get_material(0) == Models.vc_material(), "Hull keeps vertex color")
	check(paint.size() == 3, "The fleet offers three tug liveries")
	var lamps := VesselAppearance.running_lights(spec)
	check(lamps == [Models.tug_nav_lights(), Models.tug_mast_light()], "Running lamps")
	lamps.append(VesselAppearance.lights(spec))
	for mesh in lamps:
		check(
			mesh.surface_get_material(0) == GlowBuilder.material(),
			"Night lights use the glow shader"
		)
	finish()
