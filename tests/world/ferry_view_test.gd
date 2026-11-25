extends SceneTree
## Exercise the fitted hull and both deck gates, including a voyage with the view detached.

var failures := 0


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var sim := TinyRegion.build().start(root)
	var ferry := sim.ferries[0]
	expect(ferry.find_children("*", "MeshInstance3D", true, false).is_empty(),
			"Starting the simulation alone leaves the ferry undressed")
	var view := FerryView.new(ferry)
	ferry.add_child(view)
	check_hull(view, ferry)
	ferry.state = Ferry.State.LOADING
	ferry._process(0.0)
	check_gates(view, false, true)
	ferry.remove_child(view)
	ferry.voyage.depart()
	ferry._process(0.1)
	expect(ferry.traveled > 0.0, "A ferry with its view detached advances on its route")
	sim.wind_dir = "E"
	sim.wind_speed = 36
	ferry._update_trail(1.0)
	ferry.add_child(view)
	check_gates(view, true, true)
	var wind_local := ferry.global_basis.inverse() * Vector3.LEFT * 10.0
	var expected := Vector2(wind_local.x, wind_local.z)
	check_wind(view, expected)
	# With the same true wind, steaming ahead adds an apparent headwind, eased over time.
	var delta := 0.25
	ferry.global_position += ferry.global_basis.z * (Units.SPEED_UP * 2.0 * delta)
	ferry._update_trail(delta)
	check_wind(view, expected + Vector2(0, -2.0) * (1.5 * delta))
	ferry.voyage.arrive()
	var ramp := ferry._ramp(ferry.here())
	if ramp:
		ramp.snap_down()
	ferry._process(0.0)
	check_gates(view, true, false)
	if ramp:
		ramp.lift()
		ramp._process(0.25)
		ferry._process(0.0)
		check_gates(view, true, true)
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_hull(view: FerryView, ferry: Ferry) -> void:
	expect(view.hull.mesh == Models.ferry(ferry.fc) and view.hull.material_override == Models.hull_material(),
			"The fitted hull uses the class mesh and window material")
	var seed_value: Variant = view.hull.get_instance_shader_parameter("room_seed")
	expect(seed_value is float and seed_value == ferry.room_seed and seed_value >= 1.0 and seed_value <= 1000.0,
			"The fitted windows use the ferry's stable room seed")
	var shadow := Models.ferry_thin_shadow(ferry.fc)
	if shadow:
		var caster := view.hull.get_child(0) as MeshInstance3D
		expect(caster.mesh == shadow and caster.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY,
				"Thin hull details have their shadow-only caster")
	expect(view.nets.size() == 2, "Both ends receive a deck net")
	for i in view.nets.size():
		var net := view.nets[i]
		var end_z := (-1.0 if i == 0 else 1.0) * ferry.fc.net_z
		expect(net.mesh == Models.ferry_net(ferry.fc) and net.position.is_equal_approx(Vector3(0, 0, end_z)),
				"The fitted net sits on its class's deck edge")


func check_wind(view: FerryView, expected: Vector2) -> void:
	for net in view.nets:
		var wind: Variant = net.get_instance_shader_parameter("wind")
		expect(wind is Vector2 and wind.is_equal_approx(expected), "Both deck nets receive the eased apparent wind")


func check_gates(view: FerryView, minus_closed: bool, plus_closed: bool) -> void:
	expect(view.nets[0].visible == minus_closed and view.nets[1].visible == plus_closed,
			"Deck gates must match the docked end and apron position")


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
