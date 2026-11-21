extends SceneTree
## Exercise the actual cast-off path with waiting cars belonging to another lane.
## One guest stays eligible at Rosario. At Madrona, one can return to its own
## lane and another must leave because the first car reserved the last space.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var game = load(Scenes.MAIN_MAP).instantiate()
	root.add_child(game)
	var error := _check(game.sim)
	game.queue_free()
	await process_frame
	await process_frame
	if error.is_empty():
		print("TEST PASSED")
	else:
		push_error(error)
	quit(0 if error.is_empty() else 1)


func _empty_lot(term: Terminal) -> void:
	for lanes in term.lanes.values():
		for lane: Terminal.Lane in lanes:
			for waiting in lane.queue:
				instance_from_id(waiting.vehicle_id).queue_free()
			lane.queue.clear()


func _park(term: Terminal, lane: Terminal.Lane, dest: int) -> Vehicle:
	var car := Vehicle.new()
	term.sim.traffic.add_child(car)
	car.dest = dest
	car.lane_v = lane.v
	car.lot_arrival = term.sim.minutes - 15.0
	car.position = term.queue_position(lane.v, lane.queued_slots(), car)
	lane.enqueue(car.get_instance_id(), car.slots)
	return car


func _depart(ferry: Ferry) -> void:
	# Model a fully raised ramp with all boarding complete.
	ferry.here().ramps.erase(ferry.route.id)
	ferry._casting_off = true
	ferry._tick_loading(0.0)


func _check(sim: Simulation) -> String:
	var hiyu := sim.ferries[0]
	var shuttle := sim.ferries[1]
	var rosario := hiyu.here()
	var madrona := shuttle.here()
	var cypress := shuttle.destination().island.id
	var gullrock := hiyu.stops[2]

	_empty_lot(rosario)
	var shared: Terminal.Lane = rosario.lanes[madrona.island.id][0]
	var staying := _park(rosario, shared, gullrock)
	_depart(hiyu)
	if hiyu.state != Ferry.State.SAILING or shared.queue.size() != 1 or shared.queue[0].vehicle_id != staying.get_instance_id():
		return "A guest served by the next boat lost its place on departure"

	_empty_lot(madrona)
	madrona.slots_per_lane = 1
	var borrowed: Terminal.Lane = madrona.lanes[cypress][0]
	var own: Terminal.Lane = madrona.lanes[gullrock][0]
	var returning := _park(madrona, borrowed, gullrock)
	var turned := _park(madrona, borrowed, gullrock)
	var resident := _park(madrona, borrowed, cypress)
	var original_arrival := returning.lot_arrival
	var turns_before := madrona.turned_recent
	_depart(shuttle)
	if shuttle.state != Ferry.State.SAILING or borrowed.queue.size() != 1 or borrowed.queue[0].vehicle_id != resident.get_instance_id():
		return "Ineligible guests should leave while the resident keeps its place"
	if own.enroute != returning.slots or not own.queue.is_empty() or madrona.turned_recent != turns_before + 1:
		return "The first guest should reserve the last space and the second should turn away"
	for step in 1200:
		if not turned.is_queued_for_deletion():
			turned._process(0.1)
		if own.queue.is_empty():
			returning._process(0.1)
		if not own.queue.is_empty() and turned.is_queued_for_deletion():
			break
	if own.enroute != 0 or own.queue.size() != 1 or own.queue[0].vehicle_id != returning.get_instance_id() or not turned.is_queued_for_deletion():
		return "The return trip must consume the reservation and the turned car must leave the lot"
	if returning.lane_v != own.v or returning.dest != gullrock or returning.lot_arrival != original_arrival:
		return "Changing lanes should preserve the car's destination and original wait time"
	# A guest still on the road at cast-off must release its borrowed reservation.
	var late := Vehicle.new()
	sim.traffic.add_child(late)
	late.dest = gullrock
	borrowed.enroute += late.slots
	madrona._on_car_reached_lot(late, borrowed)
	if borrowed.enroute != 0 or borrowed.queue.size() != 1 or madrona.turned_recent != turns_before + 2:
		return "An inbound guest should recheck its service when its ferry has already left"
	return ""
