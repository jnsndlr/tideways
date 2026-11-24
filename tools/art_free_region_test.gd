extends SceneTree
## Generate the production Sandbox region and step a voyage along one of its routes.


func _initialize() -> void:
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


func fail(message: String) -> void:
	push_error(message)
	quit(1)
