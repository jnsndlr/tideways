extends SceneTree
## Check the navigation lights fitted to marine traffic by the world.

var failures := 0


func _initialize() -> void:
	check_tender_lights()
	check_cargo_after_dusk()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_tender_lights() -> void:
	var traffic := MarineTraffic.new()
	var station := MapData.PilotStation.new()
	for tender: ShipTender in [Tug.new(), PilotBoat.new()]:
		var spec := VesselTypes.tugs()[0] if tender is Tug else VesselTypes.pilot_boats()[0]
		tender.call("setup", traffic, "Test", spec, station, 1, 0)
		var view := VesselNightLights.new(tender)
		tender.add_child(view)
		var lamps := view.get_children()
		expect(lamps.size() == 2, spec.id + " needs both running lights")
		for lamp: MeshInstance3D in lamps:
			expect(not lamp.visible, spec.id + " starts alongside with its running lights off")
		for state: ShipTender.State in ShipTender.State.values():
			tender.state = state
			view._process(0.0)
			for lamp: MeshInstance3D in lamps:
				expect(lamp.visible == (state != ShipTender.State.ALONGSIDE), spec.id + " running light visibility")
		for lamp: MeshInstance3D in lamps:
			expect(lamp.mesh != null and lamp.layers == NightLights.LAYER, spec.id + " night light mesh and layer")
			expect(lamp.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF, spec.id + " lights cast no shadows")
		tender.free()
	traffic.free()


func check_cargo_after_dusk() -> void:
	var lights := NightLights.new()
	lights.static_lights = MeshInstance3D.new()
	lights.add_child(lights.static_lights)
	lights._set_on(false)
	var spec := VesselTypes.cargo_ships()[0]
	var first := CargoShip.new()
	first.apply_spec(spec, 0)
	expect(first.find_children("*", "VesselNightLights", true, false).is_empty(), "Simulation alone must not create navigation lamps")
	var day_lamps := lights.fit_vessel(first)
	expect(not day_lamps.visible, "The opening cargo ship is unlit during the day")
	lights._set_on(true)
	expect(day_lamps.visible, "Dusk lights the ship already at sea")
	var second := CargoShip.new()
	second.apply_spec(spec, 1)
	var night_lamps := lights.fit_vessel(second)
	expect(night_lamps.visible, "A ship arriving at night lights immediately")
	expect(night_lamps.mesh == Models.cargo_ship_lights() and night_lamps.scale.is_equal_approx(Vector3.ONE * Models.LEGACY_SCALE),
			"The arriving ship has its variant's lamps in model coordinates")
	first.free()
	lights._set_on(false)
	expect(not night_lamps.visible, "Dawn switches off the remaining ship after the first departs")
	second.free()
	expect(lights.switched.get_connections().is_empty(), "Departing ships release their night switch connection")
	lights.free()


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
