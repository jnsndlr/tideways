extends SceneTree

var failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var ocean := Node3D.new()
	root.add_child(ocean)
	var index := VesselNeighborhood.new(ocean)
	var vessels: Array[Vessel] = []
	for i in 80:
		var boat := Vessel.new()
		ocean.add_child(boat)
		boat.position = Vector3((i - 40) * 420.0, 0.0, (i % 3 - 1) * 420.0)
		vessels.append(boat)
		index.add(boat)
	check(index, vessels, Vector2.ZERO)
	vessels[2].position = Vector3(-1.0, 2.0, 0.0)
	vessels[3].position = Vector3(421.0, 2.0, 0.0)
	vessels[6].half_seg = 1250.0
	vessels[6].position = Vector3(1600.0, 0.0, 0.0)
	check(index, vessels, Vector2.ZERO)
	var removed := vessels.pop_at(2) as Vessel
	index.remove(removed)
	removed.free()
	check(index, vessels, Vector2.ZERO)
	ocean.position = Vector3(1600.0, 0.0, -900.0)
	check(index, vessels, Vector2(1600.0, -900.0))
	vessels[1].top_level = true
	vessels[1].global_position = Vector3(1600.0, 0.0, -900.0)
	check(index, vessels, Vector2(1600.0, -900.0))
	var other := Node3D.new()
	root.add_child(other)
	vessels[0].reparent(other)
	vessels[0].global_position = Vector3(1600.0, 0.0, -900.0)
	check(index, vessels, Vector2(1600.0, -900.0))
	ocean.rotate_y(0.4)
	check(index, vessels, Vector2(1600.0, -900.0))
	check_fleet_growth()
	other.free()
	ocean.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_fleet_growth() -> void:
	var sim := Simulation.new(Callable())
	root.add_child(sim)
	var traffic := MarineTraffic.new()
	sim.add_child(traffic)
	traffic.sim = sim
	for i in MarineTraffic.HELM_INDEX_MIN_FLEET + 1:
		var boat := Vessel.new()
		sim.add_child(boat)
		boat.position.x = i * 419.0
		traffic.register(boat, 0)
		if i >= MarineTraffic.HELM_INDEX_MIN_FLEET - 2:
			var candidates := traffic.helm_candidates(Vector2.ZERO, 420.0)
			var expected := in_range(traffic.vessels, Vector2.ZERO)
			if in_range(candidates, Vector2.ZERO) != expected:
				push_error("Fleet growth changed the nearby vessels")
				failures += 1
			if (
				(candidates.size() < traffic.vessels.size())
				!= (i + 1 >= MarineTraffic.HELM_INDEX_MIN_FLEET)
			):
				push_error("The larger fleet must switch to neighborhood queries")
				failures += 1
	sim.free()


func check(index: VesselNeighborhood, vessels: Array[Vessel], center: Vector2) -> void:
	var actual := in_range(index.candidates(vessels, center, 420.0), center)
	if actual != in_range(vessels, center):
		push_error("The neighborhood missed a hull or changed registration order")
		failures += 1


func in_range(vessels: Array[Vessel], center: Vector2) -> Array[Vessel]:
	var found: Array[Vessel] = []
	for boat in vessels:
		var d := (boat.pos2() - center).abs()
		if maxf(d.x, d.y) <= 420.0 + boat.half_seg + boat.hull_radius:
			found.append(boat)
	return found
