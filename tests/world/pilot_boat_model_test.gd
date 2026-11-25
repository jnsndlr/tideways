extends "res://tests/rule_test_case.gd"
## Verify the pilot launch's three liveries and the shared transfer and night-light meshes.


func _initialize() -> void:
	var authored := not "--classic-pilot" in OS.get_cmdline_user_args()
	check(PilotBoatModel.authored == authored, "Launch switch selects the pilot model")
	var spec := VesselTypes.pilot_boats()[0]
	var paint: Array[PackedColorArray] = []
	for variant in spec.variants:
		var mesh := VesselAppearance.hull(spec, variant)
		check(mesh == Models.pilot_boat(variant), "Reuse hull mesh for the same livery")
		check(mesh.get_surface_count() == 1, "Hull has one painted surface")
		if mesh.get_surface_count() != 1:
			continue
		var colors: PackedColorArray = mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
		check(colors.size() == mesh.surface_get_array_len(0), "Paint reaches every hull vertex")
		check(not colors in paint, "Each pilot livery has distinct colors")
		paint.append(colors)
		check(mesh.surface_get_material(0) == Models.vc_material(), "Hull keeps vertex color")
	check(paint.size() == 3, "The fleet offers three pilot liveries")
	var ladder := Models.pilot_ladder(1.7, 3.5)
	check(ladder == Models.pilot_ladder(1.7, 3.5), "Reuse the fitted ladder")
	check(ladder != Models.pilot_ladder(1.7, 4.5), "A taller deck needs a separate ladder")
	var lamps := VesselAppearance.running_lights(spec)
	check(
		lamps == [Models.pilot_boat_nav_lights(), Models.pilot_boat_duty_lights()], "Running lamps"
	)
	lamps.append(VesselAppearance.lights(spec))
	for mesh in lamps:
		check(
			mesh.surface_get_material(0) == GlowBuilder.material(),
			"Night lights use the glow shader"
		)
	finish()
