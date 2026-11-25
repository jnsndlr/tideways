extends SceneTree
## Fit and replace a named ship's hull without changing its variant or room pattern.


func _initialize() -> void:
	var ship := CargoShip.new()
	ship.vessel_name = "North Star"
	var spec := VesselTypes.cargo_ships()[1]  # Feeder shares the container hull at 70% of its size.
	ship.apply_spec(spec, 2)
	var passed := ship.find_children("*", "MeshInstance3D", true, false).is_empty()
	var plate := Models.cargo_name_plate(ship.vessel_name)
	for i in 2:
		var hull := VesselHullView.new(ship)
		ship.add_child(hull)
		passed = passed and hull.mesh == Models.cargo_ship(2) and hull.material_override == Models.hull_material()
		passed = passed and hull.scale.is_equal_approx(Vector3.ONE * (0.7 * Models.LEGACY_SCALE))
		passed = passed and hull.get_instance_shader_parameter("room_seed") == ship.room_seed
		if plate != null:
			passed = passed and hull.get_child_count() == 1 and hull.get_child(0).mesh == plate
		else:
			passed = passed and hull.get_child_count() == 0
		hull.free()
	ship.free()
	if not passed:
		push_error("The named cargo ship must retain its hull, scale, cabin pattern and lettering when refitted")
		quit(1)
		return
	print("TEST PASSED")
	quit()
