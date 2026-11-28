extends SceneTree
## Exercise the anchor cycle with and without the yacht's lights and anchor line.

var failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var sim := TinyRegion.build().start(root)
	sim.minutes = 12.0 * 60.0
	for with_view: bool in [false, true]:
		var yacht := MotorYacht.new()
		sim.add_child(yacht)
		var marina := MapData.Marina.new()
		yacht.setup(sim.marine, "Test yacht", VesselTypes.motor_yachts()[0], marina, 0, 0, 60.0)
		var lamps: VesselNightLights
		var view: MotorYachtView
		if with_view:
			lamps = VesselNightLights.new(yacht)
			yacht.add_child(lamps)
			view = MotorYachtView.new(yacht, lamps)
			yacht.add_child(view)
			check_gear(yacht, view, lamps, false, false, false, "moored")

		var spot := Anchorage.Spot.new()
		spot.pos = Vector2(40.0, 40.0)
		spot.taken_by = yacht
		yacht.spot = spot
		yacht.dest = marina
		yacht._let_go_anchor()
		yacht._process(1.0)
		expect(yacht.state == MotorYacht.State.SETTING, "The yacht pays out its anchor line")
		if with_view:
			check_gear(yacht, view, lamps, false, true, true, "setting")
		yacht._process(MotorYacht.SCOPE / MotorYacht.SET_SPEED)
		expect(
			yacht.state == MotorYacht.State.ANCHORED,
			"The yacht lies at anchor once the line is paid out"
		)
		expect(
			yacht.straight_prediction_direction() == Vector2.ZERO,
			"An anchored yacht has no straight-course prediction"
		)
		if with_view:
			check_gear(yacht, view, lamps, false, true, true, "anchored")

		yacht._leave_at = yacht._now()
		yacht._process(0.25)
		expect(yacht.state == MotorYacht.State.WEIGHING, "The yacht weighs anchor when due")
		yacht._process(16.75)
		if with_view:
			check_gear(yacht, view, lamps, false, true, true, "before 17 seconds")
		yacht._process(0.25)
		if with_view:
			check_gear(yacht, view, lamps, false, true, false, "at 17 seconds")
		yacht._process(0.25)
		if with_view:
			check_gear(yacht, view, lamps, false, true, false, "after 17 seconds")
		yacht._process(2.75)
		expect(yacht.state == MotorYacht.State.CRUISING and spot.taken_by == null,
			"The yacht frees its spot and cruises home at 20 seconds")
		if with_view:
			check_gear(yacht, view, lamps, true, true, false, "cruising")
		yacht.free()
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_gear(yacht: MotorYacht, view: MotorYachtView, lamps: VesselNightLights, nav: bool, mast: bool, rode: bool, stage: String) -> void:
	view.refresh()
	for night: bool in [false, true]:
		lamps.visible = night
		var expected := {
			Models.motor_yacht_nav_lights(): nav and night,
			Models.motor_yacht_mast_light(): mast and night,
			Models.motor_yacht_rode(): rode,
		}
		for part: MeshInstance3D in yacht.find_children("*", "MeshInstance3D", true, false):
			if expected.has(part.mesh):
				expect(part.is_visible_in_tree() == expected[part.mesh],
					"Incorrect yacht gear visibility while " + stage)
				expected.erase(part.mesh)
		expect(expected.is_empty(), "The yacht has navigation lights, a mast light and an anchor line")


func expect(passed: bool, message: String) -> void:
	if not passed:
		failures += 1
		push_error(message)
