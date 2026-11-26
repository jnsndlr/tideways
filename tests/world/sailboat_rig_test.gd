extends SceneTree
## Verify a sailboat can change propulsion and tack with or without its sail view.

var failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var sim := TinyRegion.build().start(root)
	for with_view: bool in [false, true]:
		check_passage(sim, with_view)
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_passage(sim: Simulation, with_view: bool) -> void:
	var boat := Sailboat.new()
	sim.add_child(boat)
	var marina := MapData.Marina.new()
	boat.setup(sim.marine, "Sloop", VesselTypes.sailboats()[0], marina, 0, 90.0)
	expect(boat.find_children("*", "MeshInstance3D", true, false).is_empty(), "A simulation sailboat starts without visual nodes")
	var hull: VesselHullView
	var view: SailboatView
	if with_view:
		hull = VesselHullView.new(boat)
		boat.add_child(hull)
		view = SailboatView.new(boat, hull)
		hull.add_child(view)
		check_canvas(hull, view, false)
	boat.dest = marina
	boat._goals.append(boat.pos2() + Vector2(0, 550))
	boat._backed_out()
	expect(boat.motoring and boat.road() == Vessel.Road.POWER, "The sloop clears the berth under power")
	boat._set_sails(true)
	expect(not boat.motoring and boat.road() == Vessel.Road.SAIL, "Hoisting the sails changes right of way")
	if with_view:
		check_canvas(hull, view, true)

	boat._yaw = 0.0
	boat.speed = boat.cruise
	for wind: String in ["W", "E"]:
		sim.wind_dir = wind
		var tack := 1 if wind == "W" else -1
		expect(boat._tack_side() == tack, "Wind from " + wind + " puts the sloop on the expected tack")
		expect(is_zero_approx(boat.helm_speed(sim.wind_yaw())), "The sloop cannot sail directly into the wind")
		expect(boat.helm_speed(boat._yaw) > 0.0, "A beam reach drives the sloop")
		# Change to the opposite tack while the rig is detached, then remount it.
		if with_view and wind == "E":
			hull.remove_child(view)
		boat._pose(2.0)
		if with_view:
			if not view.is_inside_tree():
				hull.add_child(view)
			check_trim(view, tack)

	boat._begin_berthing()
	expect(boat.motoring and boat.state == Sailboat.State.ARRIVING, "The sloop douses its sails on approach")
	expect(is_equal_approx(boat.helm_speed(sim.wind_yaw()), boat.spec.motor_speed), "Engine speed is independent of wind")
	if with_view:
		check_canvas(hull, view, false)
	boat._berthed()
	expect(boat.state == Sailboat.State.MOORED and is_zero_approx(boat.speed), "The sloop stops at its berth")
	boat.free()


func check_canvas(hull: VesselHullView, view: SailboatView, hoisted: bool) -> void:
	var hull_mesh: Mesh = Models.sailboat() if hoisted else Models.sailboat_furled()
	expect(hull.mesh == hull_mesh, "The hull model matches the sail state")
	for mesh: MeshInstance3D in view.get_children():
		expect(mesh.visible == hoisted, "Sail visibility matches the rig state")


func check_trim(view: SailboatView, tack: int) -> void:
	var sheet := tack * (PI / 2.0 - 0.6) * 0.55
	var authored := (
		not "--classic-sailboat" in OS.get_cmdline_user_args()
		and ResourceLoader.exists("res://assets/models/sailboat_mid.glb")
	)
	var camber := Basis.from_scale(Vector3(tack, 1, 1)) if authored else Basis.IDENTITY
	var pivot := Vector3(0, 0.62, 1.976) if authored else Vector3(0, 0.8, 1.7)
	var head := Vector3(0, 3.55, 0.391) if authored else Vector3(0, 3.6, 0.35)
	var mainsail: MeshInstance3D = view.get_child(0)
	var jib: MeshInstance3D = view.get_child(1)
	expect(
		(
			mainsail.mesh == Models.sailboat_main()
			and mainsail.position.is_equal_approx(Vector3(0, 0, 0.2))
		),
		"The mainsail is attached at the boom pivot"
	)
	expect(
		jib.mesh == Models.sailboat_jib() and jib.position.is_equal_approx(pivot),
		"The jib is attached at its tack"
	)
	var stay := (head - pivot).normalized()
	expect(
		mainsail.basis.is_equal_approx(Basis(Vector3.UP, -sheet) * camber),
		"Mainsail swings to leeward"
	)
	expect(jib.basis.is_equal_approx(Basis(stay, -sheet) * camber), "Jib trims around its stay")


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
