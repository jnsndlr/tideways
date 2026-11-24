extends SceneTree
## Generate the production Sandbox region and step a voyage along one of its routes.


func _initialize() -> void:
	if not check_marine_catalogue():
		fail("Marine types must support clearance and wake calculations without imported art")
		return
	for size in range(1, 6):
		var hull := FerryClass.of(size)
		var measured := FerryWaterlineProfiles.profile(size, hull.half_length)
		if measured.size() != HullWaterline.STATIONS + 2 or measured[1] <= 0.0 or measured[2] <= 0.0:
			fail("Art-free ferry size %d has no measured waterline" % size)
			return
		if hull.half_width_at(0.0) <= 0.0 or hull.half_width_at(2.0 * hull.half_length) != 0.0:
			fail("Art-free ferry size %d has an invalid hull outline" % size)
			return
		var deck := FerryDeck.new(hull)
		var slot := deck.find_space(1, false, true)
		if slot < 0:
			fail("Art-free ferry size %d has no space for its first car" % size)
			return
		deck.reserve(slot, 1, true, 1)
		if deck.find_space(1, false, true) == slot:
			fail("An occupied slot must be unavailable for the next car")
			return
	var generator := MapGenerator.new()
	var region := generator.generate(123)
	if region == null or region.routes.size() != 4:
		fail("Seed 123 should produce four routes")
		return
	var route := region.routes[0]
	if route.a == route.b or route.curve == null or route.length <= 0.0:
		fail("The crossing needs a nonempty route between two different terminals")
		return

	var voyage := FerryVoyage.new()
	voyage.depart()
	var speed := voyage.sailing_speed(1.0, route.length, 0.0, 20.0, 0.0, INF)
	if voyage.state != FerryVoyage.State.SAILING or speed != 0.0:
		fail("The ferry must wait while traffic blocks departure")
		return
	var steps := 0
	while not voyage.has_arrived(route.length) and steps < 10000:
		speed = voyage.sailing_speed(0.25, route.length, speed, 20.0, INF, INF)
		voyage.advance(0.25, speed, route.length)
		steps += 1
	if not voyage.has_arrived(route.length) or steps == 0:
		fail("The ferry did not reach the destination after traffic cleared")
		return
	voyage.arrive()
	if voyage.at_a or voyage.trips != 1 or voyage.state != FerryVoyage.State.UNLOADING:
		fail("Arrival should record one crossing and start unloading at the other terminal")
		return
	print("Seed 123: %d routes; %s to %s, %.3f m, %d voyage steps" % [
		region.routes.size(), region.towns[route.a].key, region.towns[route.b].key, route.length, steps])
	print("TEST PASSED")
	quit(0)


func check_marine_catalogue() -> bool:
	var fleet := VesselTypes.sailboats() + VesselTypes.cargo_ships()
	fleet.append_array(VesselTypes.fishing_boats())
	fleet.append_array(VesselTypes.motor_yachts())
	fleet.append_array(VesselTypes.pilot_boats())
	fleet.append_array(VesselTypes.tugs())
	for spec: VesselSpec in fleet:
		if spec.half_seg() <= 0.0 or spec.radius() < spec.half_beam:
			return false
		var trail := spec.make_wake()
		trail.update(1.0, Vector3.FORWARD * spec.cruise, Vector3.FORWARD, spec.cruise, 1.0, true)
		if trail.is_empty() or not is_equal_approx(trail.odometer, spec.cruise):
			return false
	return not fleet.is_empty()


func fail(message: String) -> void:
	push_error(message)
	quit(1)
