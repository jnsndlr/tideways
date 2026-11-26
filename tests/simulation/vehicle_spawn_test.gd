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
	check_injected_spawner()
	var original_mode := Models.mid_cars
	for authored: bool in [true, false]:
		Models.mid_cars = authored
		check_spawned_traffic(authored)
	check_invalid_parts()
	check_queue_parking()
	check_boarding_approaches()
	check_world_isolation()
	Models.mid_cars = original_mode
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


## A rules-only simulation can spawn and charge a fare without constructing a model.
func check_injected_spawner() -> void:
	var draws: Array[int] = []
	var create := func(rng: RandomNumberGenerator, _truck_share: float) -> Vehicle:
		draws.append(rng.randi())
		return Vehicle.new()
	var sim := Simulation.new(create)
	sim.traffic = Node3D.new()
	sim.add_child(sim.traffic)
	var deck := Node3D.new()
	sim.add_child(deck)
	var expected := RandomNumberGenerator.new()
	expected.seed = 123
	sim.rng.seed = 123
	var road_vehicle := sim.make_vehicle()
	var deck_vehicle := sim.make_vehicle(deck)
	expect(draws == [expected.randi(), expected.randi()] and expected.state == sim.rng.state, "Each spawn should use the simulation RNG once with this creator")
	expect(road_vehicle.get_parent() == sim.traffic and deck_vehicle.get_parent() == deck, "Simulation should attach injected vehicles to the requested parent")
	expect(is_same(road_vehicle.moving_traffic, sim.moving_vehicles) and is_same(deck_vehicle.moving_traffic, sim.moving_vehicles), "Both vehicles should share their simulation's traffic registry")
	sim.collect_fare(deck_vehicle)
	expect(
		is_equal_approx(sim.revenue_today, 18.0),
		"A vehicle without a mesh should earn the same car fare"
	)
	sim.free()


func check_spawned_traffic(authored: bool) -> void:
	var sim := Simulation.new(VehicleFactory.create)
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
		var body := car.get_child(0) as MeshInstance3D
		expect(body != null and body.mesh != null, "Spawned vehicle has no visible body")
		expect(car.slots >= 1 and car.length > 0, "Vehicle has no usable dimensions")
		saw_car = saw_car or not car.is_truck
		saw_truck = saw_truck or car.is_truck
		if authored:
			expect(not car.model.is_empty(), "Authored vehicle missing its model key")
			expect(car.speed == (20.0 if car.is_truck else 24.0), "Authored vehicle cruise speed changed")
			if car.trailer != null:
				saw_trailer = true
				var trailer_body := car.trailer.get_child(0) as MeshInstance3D
				expect(trailer_body != null and trailer_body.mesh != null, "Spawned trailer has no visible body")
				expect(car.is_truck and car.trailer.get_parent() == car and car.slots > 1, "Rig must tow its trailer and occupy multiple deck slots")
		else:
			expect(
				car.model.is_empty() and car.trailer == null,
				"Classic traffic unexpectedly used authored assets"
			)
			expect(
				car.slots == (2 if car.is_truck else 1) and car.speed == 24.0,
				"Classic vehicle behavior changed"
			)
		check_reconstructed_vehicle(car, body.mesh)
		car.free()
	expect(saw_car and saw_truck, "Seed 123 should exercise both car and truck construction")
	if authored:
		expect(saw_trailer, "Seed 123 should exercise a tractor with an attached trailer")
	sim.free()


func check_reconstructed_vehicle(car: Vehicle, mesh: Mesh) -> void:
	var copy := VehicleFactory.from_parts(
		car.is_truck, car.model, car.body_paint, car.trailer_model, car.trailer_paint
	)
	expect(copy != null, "Reconstruct the selected vehicle")
	if not copy:
		return
	var body := copy.get_child(0) as MeshInstance3D
	expect(body.mesh == mesh, "Reconstructed vehicle uses the same painted mesh")
	expect(
		(
			copy.slots == car.slots
			and copy.length == car.length
			and copy.speed == car.speed
			and copy.fare_multiplier() == car.fare_multiplier()
		),
		"Reconstructed vehicle keeps its deck and fare rules"
	)
	if car.trailer:
		var original := car.trailer.get_child(0) as MeshInstance3D
		var rebuilt := copy.trailer.get_child(0) as MeshInstance3D
		expect(
			original.mesh == rebuilt.mesh and copy.trailer_paint == car.trailer_paint,
			"Reconstructed trailer keeps its selected paint, including fixed-color trailers"
		)
	copy.free()


func check_invalid_parts() -> void:
	expect(
		VehicleFactory.from_parts(false, "", Models.CAR_COLORS.size()) == null,
		"Reject classic paint outside its palette"
	)
	expect(VehicleFactory.from_parts(true, "tractor_day", 0) == null, "Reject incomplete rigs")
	expect(VehicleFactory.from_parts(true, "rig", 0) == null, "Reject the selection placeholder")
	expect(
		VehicleFactory.from_parts(false, "truck_box", 0) == null,
		"Reject a truck presented as a car"
	)
	expect(
		VehicleFactory.from_parts(false, "sedan_compact", 0, "trailer_van", 0) == null,
		"Reject trailer on a car"
	)
	expect(
		VehicleFactory.from_parts(true, "tractor_day", 0, "trailer_van", -1) == null,
		"Reject an unknown trailer paint"
	)


func make_world() -> Simulation:
	var sim := Simulation.new(VehicleFactory.create)
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
	rig.setup(Node3D.new(), true, "tractor_classic", Models.VEHICLE_SCALE)
	rig.attach_trailer("trailer_van", Node3D.new())
	sim.traffic.add_child(rig)
	var terminal := Terminal.new()
	terminal.town = MapData.Town.new()
	terminal.town.dock_dir = Vector3.BACK
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
	terminal.town = MapData.Town.new()  # the lot's frame and the trestle's profile
	root.add_child(terminal)
	terminal.rotation.y = 1.1
	terminal.position = Vector3(45, 0, 80)
	var slip := 30.0
	terminal.town = MapData.Town.new()
	var berth := MapData.Slip.new()
	berth.v = slip
	terminal.town.slips.append(berth)
	terminal.slip_ramps.append(null)
	var car := Vehicle.new()
	var widest := 0.0
	for data: Dictionary in VehicleData.VARIANTS.values():
		widest = maxf(widest, data.size.x * Models.VEHICLE_SCALE)
	for mid: bool in [false, true]:
		if mid:
			var ramp := SlipRamp.new(slip)
			terminal.add_child(ramp)
			terminal.slip_ramps[0] = ramp
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
