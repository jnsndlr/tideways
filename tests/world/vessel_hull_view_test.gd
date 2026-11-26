extends "res://tests/rule_test_case.gd"
## Fit and replace every cargo hull, including its room pattern, lettering and lights.


func _initialize() -> void:
	var container := (
		not "--classic-cargo" in OS.get_cmdline_user_args()
		and ResourceLoader.exists("res://assets/models/cargo_mid.glb")
	)
	var tanker := container and ResourceLoader.exists("res://assets/models/tanker_mid.glb")
	var bulker := container and ResourceLoader.exists("res://assets/models/bulker_mid.glb")
	var specs := VesselTypes.cargo_ships()
	for i in specs.size():
		var spec := specs[i]
		var authored: bool = [container, container, tanker, bulker][i]
		var meshes := []
		for variant in spec.variants:
			var ship := CargoShip.new()
			ship.vessel_name = "North Star"
			ship.apply_spec(spec, variant)
			check(
				ship.find_children("*", "MeshInstance3D", true, false).is_empty(),
				"The simulation does not add visual nodes"
			)
			var mesh := VesselAppearance.hull(spec, variant)
			check(mesh.get_surface_count() == 1 and not mesh in meshes, "Distinct hull variants")
			meshes.append(mesh)
			if i == 1:
				check(mesh == Models.cargo_ship(variant), "Feeder reuses the container mesh")
			var size: float = [1.0, 0.7, 1.15, 1.1][i]
			var hull := VesselHullView.new(ship)
			ship.add_child(hull)
			check(
				hull.mesh == mesh and hull.material_override == Models.hull_material(),
				"Fitted hull"
			)
			check(
				hull.scale.is_equal_approx(Vector3.ONE * Models.LEGACY_SCALE * size), "Hull scale"
			)
			check(
				hull.get_instance_shader_parameter("room_seed") == ship.room_seed,
				"Cabin lighting retains the vessel seed"
			)
			if authored:
				check(hull.get_child_count() == 1, "Named authored ship has lettering")
				if hull.get_child_count() == 1:
					check(
						hull.get_child(0).mesh == Models.cargo_name_plate("North Star"),
						"Hull lettering"
					)
			else:
				check(hull.get_child_count() == 0, "Classic hull has no name plate")
			check(
				VesselAppearance.lights(spec) == Models.cargo_ship_lights(authored),
				"Navigation and bridge lights match the selected hull"
			)
			hull.free()
			var replacement := VesselHullView.new(ship)
			check(replacement.mesh == mesh, "Refitting reuses the selected hull")
			replacement.free()
			ship.free()
	finish()
