extends SceneTree
## Exercise the normal creation path for the queue and for vehicles that begin
## aboard, with authored traffic and the classic fallback models.

var failures := 0


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var original_mode := Models.mid_cars
	for authored: bool in [true, false]:
		Models.mid_cars = authored
		check_spawned_traffic(authored)
	check_queue_parking()
	check_boarding_approaches()
	check_world_isolation()
	Models.mid_cars = original_mode
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_spawned_traffic(authored: bool) -> void:
	var sim := Simulation.new()
	sim.rng.seed = 123
	sim.traffic = Node3D.new()
	sim.add_child(sim.traffic)
	var ferry := Node3D.new()
	sim.add_child(ferry)
	var saw_car := false
	var saw_truck := false
	var saw_trailer := false
	for i in 32:
		var aboard := i % 2 == 0
		var car := sim.make_vehicle(ferry) if aboard else sim.make_vehicle()
		expect(car.get_parent() == (ferry if aboard else sim.traffic), "Vehicle spawned under the wrong parent")
		expect(car.slots >= 1 and car.length > 0, "Vehicle has no usable dimensions")
		saw_car = saw_car or not car.is_truck
		saw_truck = saw_truck or car.is_truck
		if authored:
			expect(not car.model.is_empty(), "Authored vehicle missing its model key")
			expect(car.speed == (20.0 if car.is_truck else 24.0), "Authored vehicle cruise speed changed")
			if car.trailer != null:
				saw_trailer = true
				expect(car.is_truck and car.trailer.get_parent() == car and car.slots > 1, "Rig must tow its trailer and occupy multiple deck slots")
		else:
			expect(car.model.is_empty() and car.trailer == null, "Classic traffic unexpectedly used authored assets")
			expect(car.slots == 1 and car.speed == 24.0, "Classic vehicle behavior changed")
		car.free()
	expect(saw_car and saw_truck, "Seed 123 should exercise both car and truck construction")
	if authored:
		expect(saw_trailer, "Seed 123 should exercise a tractor with an attached trailer")
	sim.free()



func make_world() -> Simulation:
	var sim := Simulation.new()
	sim.traffic = Node3D.new()
	sim.add_child(sim.traffic)
	root.add_child(sim)
	return sim


func moving_car(sim: Simulation, z: float) -> Vehicle:
	var car := sim.make_vehicle()
	car.position.z = z
	car.drive(PackedVector3Array([Vector3(0, 0, z + 50)]))
	return car


func check_world_isolation() -> void:
	var first := make_world()
	var second := make_world()
	var follower := moving_car(first, 0)
	var other_world_car := moving_car(second, 12)
	expect(is_inf(follower._room_ahead()), "A car in another simulation should never block the road")
	var lead := moving_car(first, 12)
	expect(not is_inf(follower._room_ahead()), "A moving car ahead in the same world should constrain the following car")
	lead.free()
	expect(first.moving_vehicles.size() == 1 and is_inf(follower._room_ahead()), "Removing a car should clear its traffic registration")
	first.free()
	expect(second.moving_vehicles == [other_world_car], "Closing one world changed the other world's traffic")
	second.free()


func check_queue_parking() -> void:
	var sim := make_world()
	var rig := Vehicle.new()
	rig.setup(BoxMesh.new(), true, "tractor_classic", Models.VEHICLE_SCALE)
	rig.attach_trailer("trailer_van", BoxMesh.new())
	sim.traffic.add_child(rig)
	var terminal := Terminal.new()
	terminal.island = MapData.Island.new()
	terminal.island.dock_dir = Vector3.BACK
	terminal.sim = sim
	sim.add_child(terminal)
	var lane := Terminal.Lane.new(Layout.LANE_WIDTH)
	lane.enroute = rig.slots
	var spot := terminal.queue_position(lane.v, 0, rig)
	rig.position = spot - Vector3(0, 0, 14)
	rig.trailer.rotation.y = deg_to_rad(35)
	terminal._on_car_reached_lot(rig, lane)
	rig._process(0.1)
	expect(absf(rig.trailer.rotation.y) > 0.01, "Rig should ease into its lane over the approach")
	for tick in 100:
		if rig.path.is_empty():
			break
		rig._process(0.033)
	expect(rig.position.is_equal_approx(spot), "Rig should arrive at the reserved queue position")
	expect(absf(rig._tail().x - lane.v) < 0.01, "Parked trailer should fit in its own lane")
	terminal._close_up(lane)
	rig._process(0.033)
	expect(absf(rig._tail().x - lane.v) < 0.01, "Closing a queue should preserve the parked pose")
	sim.free()


func check_boarding_approaches() -> void:
	var terminal := Terminal.new()
	root.add_child(terminal)
	terminal.rotation.y = 1.1
	terminal.position = Vector3(45, 0, 80)
	var slip := 30.0
	terminal.slip_v[0] = slip
	var car := Vehicle.new()
	var widest := 0.0
	for data: Dictionary in VehicleData.VARIANTS.values():
		widest = maxf(widest, data.size.x * Models.VEHICLE_SCALE)
	for mid: bool in [false, true]:
		if mid:
			var ramp := SlipRamp.new(slip)
			terminal.add_child(ramp)
			terminal.ramps[0] = ramp
		car.lane_v = slip - 18
		var left := terminal.boarding_path(car, 0)
		car.lane_v = slip + 18
		var right := terminal.boarding_path(car, 0)
		var left_center := terminal.to_local(left[1]).x - slip
		var right_center := terminal.to_local(right[1]).x - slip
		# The authored transfer span has curbs at ±6.6 and an exit lane at +3.
		expect(left_center - widest * 0.5 > -6.6, "Approach meets the ramp curb")
		expect(right_center - left_center > widest, "Boarding streams cross at the lot edge")
		expect(3.0 - right_center > widest, "Boarding approach meets the unloading lane")
		expect(left[-1].is_equal_approx(right[-1]), "Boarding vehicles should converge before the ferry")
	terminal.free()
	car.free()
