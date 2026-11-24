extends SceneTree
## Run a trawler's haul and catch landing with and without its presentation.

var failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var sim := TinyRegion.build().start(root)
	for with_view: bool in [false, true]:
		check_haul_and_landing(sim, with_view)
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_haul_and_landing(sim: Simulation, with_view: bool) -> void:
	sim.minutes = 23 * 60 + 30
	var boat := FishingBoat.new()
	sim.add_child(boat)
	boat.setup(sim.marine, "Test trawler", VesselTypes.fishing_boats()[0], MapData.FishQuay.new(), 0, 0)
	var view: FishingBoatView
	if with_view:
		view = FishingBoatView.new(boat)
		boat.add_child(view)
	check_gear(boat, view, [], false, "before the first trip")

	boat.ground = sim.marine.reserve_ground(boat)
	boat._start_helm(FishingBoat.State.FISHING)
	boat._begin_shooting()
	var fishing_lights := [Models.trawler_nav_lights(), Models.trawler_working_lights()]
	check_gear(boat, view, fishing_lights, true, "shooting the net")
	boat._work(FishingBoat.SHOOT_TIME.y)
	expect(boat.work == FishingBoat.Work.TOWING, "The trawler tows after shooting the net")
	check_gear(boat, view, fishing_lights, true, "towing")
	boat.position = Vector3(boat.helm.goal.x, 0, boat.helm.goal.y)
	boat._work(0.25)
	expect(boat.work == FishingBoat.Work.HAULING, "The trawler hauls at the tow endpoint")
	check_gear(boat, view, fishing_lights, false, "hauling")
	boat._work(FishingBoat.HAUL_TIME.y)
	expect(boat.hauls == 1 and boat.fish_hold > 0.0, "The completed haul adds catch once")
	expect(boat.state == FishingBoat.State.HOMEWARD and boat.ground.worked_by == null,
			"After the last haul the trawler releases its ground and steams home")
	check_gear(boat, view, [Models.trawler_nav_lights(), Models.trawler_steaming_lights()], false, "steaming home")

	boat._came_alongside()
	expect(boat.trips == 1 and boat.state == FishingBoat.State.ALONGSIDE, "Returning records one trip")
	var landing_lights := [Models.trawler_working_lights()]
	check_gear(boat, view, landing_lights, false, "landing the catch")
	sim.day += 1
	sim.minutes = 29.99
	check_gear(boat, view, landing_lights, false, "just before 60 minutes alongside")
	sim.minutes = 30.0
	check_gear(boat, view, [], false, "at 60 minutes alongside")
	boat.free()


func check_gear(boat: FishingBoat, view: FishingBoatView, lit_at_night: Array, net_out: bool, stage: String) -> void:
	if view == null:
		return
	view.refresh()
	for night: bool in [false, true]:
		boat.lights.visible = night
		var expected := {}
		for mesh: Mesh in [Models.trawler_nav_lights(), Models.trawler_steaming_lights(), Models.trawler_working_lights()]:
			expected[mesh] = night and lit_at_night.has(mesh)
		expected[Models.trawler_warps()] = net_out
		for part: MeshInstance3D in view.find_children("*", "MeshInstance3D", true, false):
			if expected.has(part.mesh):
				expect(part.is_visible_in_tree() == expected[part.mesh], "Incorrect trawler gear visibility " + stage)
				expected.erase(part.mesh)
		expect(expected.is_empty(), "Missing trawler gear " + stage)


func expect(passed: bool, message: String) -> void:
	if not passed:
		failures += 1
		push_error(message)
