extends SceneTree
## Trace one initially queued vehicle through normal simulation ticks on seed 123.

var sandbox: Node
var ferry: Ferry
var destination: Terminal
var queued := {}
var previous := {}
var receipts := 0
var vehicle_id := 0
var phase := "queue"
var frame := 0


func _initialize() -> void:
	sandbox = load(Scenes.SANDBOX).instantiate()
	root.add_child(sandbox)


func reserved() -> Dictionary:
	var result := {}
	for boat: Ferry in sandbox.sim.ferries:
		for id in boat.deck.occupants:
			if id:
				result[id] = int(result.get(id, 0)) + 1
	return result


func fail(reason: String) -> bool:
	push_error("Vehicle journey seed=%s frame=%s vehicle=%s phase=%s: %s" % [sandbox.map_seed, frame, vehicle_id, phase, reason])
	quit(1)
	return false


func _process(_delta: float) -> bool:
	frame += 1
	var occupied := reserved()
	if frame == 1:
		ferry = sandbox.sim.ferries[0]
		destination = ferry.destination()
		for lane in ferry.here().lanes[ferry.route.id]:
			for waiting in lane.queue:
				queued[waiting.vehicle_id] = true
		Engine.time_scale = 4.0
	else:
		var bookings := 0
		for id: int in occupied:
			if previous.has(id):
				continue
			bookings += 1
			if vehicle_id == 0 and queued.has(id):
				vehicle_id = id
				phase = "boarding"
				var car := instance_from_id(id) as Vehicle
				if occupied[id] != car.slots:
					return fail("Incorrect slot reservation")
		if sandbox.sim.cars_today - receipts != bookings:
			return fail("Boarding receipts differ from new reservations")
	if vehicle_id:
		var car := instance_from_id(vehicle_id) as Vehicle
		match phase:
			"boarding":
				if not car or not occupied.has(vehicle_id):
					return fail("Reservation lost before boarding")
				if car.get_parent() == ferry and ferry.aboard.has(car):
					phase = "aboard"
			"aboard":
				if not car:
					return fail("Vehicle disappeared before arrival")
				if car.get_parent() == sandbox.sim.traffic:
					if ferry.here() != destination or occupied.has(vehicle_id):
						return fail("Wrong destination or slots still occupied")
					phase = "driving off"
			"driving off":
				if not car:
					print("Completed queued vehicle journey on frame ", frame)
					print("TEST PASSED")
					quit(0)
					return false
	previous = occupied
	receipts = sandbox.sim.cars_today
	if frame >= 6000:
		return fail("Timed out")
	return false
