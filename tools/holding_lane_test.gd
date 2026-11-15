extends SceneTree
## Verify safe staging closures, then trace a car
## from the added lane to the deck using normal demand and ferry dispatch.

var game: Node
var terminal: Terminal
var frame := 0
var original_capacity: int
var observed := {}
var served_at_purchase: int
var saw_crew := false

func check_drain(staging_count: int) -> String:
	var sim := Simulation.new()
	var term := Terminal.new()
	sim.add_child(term)
	term.sim = sim
	term.island = MapData.Island.new()
	term.island.slips = [0, 1]
	term.island.lane_extension_price = 100
	term.island.construction_staging_lanes = staging_count
	sim.fares.revenue_total = 200
	var first := Terminal.Lane.new(-30)
	var second := Terminal.Lane.new(-23)
	var active := Terminal.Lane.new(-16)
	var other_route := Terminal.Lane.new(8.7)
	term.lanes = {0: [first, second, active], 1: [other_route]}
	var rig := Vehicle.new()
	var dispatched := Vehicle.new()
	var fitting := Vehicle.new()
	rig.slots = 3
	# A car was sent toward the ferry before the player opened the purchase UI.
	first.queue.append(dispatched)
	term.take_car(0)
	first.enroute = rig.slots
	if not term.buy_holding_lane() or term.buy_holding_lane():
		return "A construction request must charge exactly once"
	var capacity := (4 - staging_count) * term.slots_per_lane
	if term.capacity() != capacity or term._pick_lane(0, 3) in term.staging_lanes or term._pick_lane(1) != other_route:
		return "Staging closed the wrong lanes or admitted an arrival"
	term._advance_construction(20)
	if term.work_stage != Terminal.WorkStage.DRAINING:
		return "Crew entered before the inbound rig cleared"
	first.enroute -= rig.slots
	first.queue.append(rig)
	active.queue.append(fitting)
	term._advance_construction(20)
	if term.work_stage != Terminal.WorkStage.DRAINING:
		return "Crew entered an occupied queue"
	if term.take_car(0, func(car: Vehicle): return car.slots < 3) != fitting:
		return "Waiting staging rig blocked a fitting car in an active lane"
	term.finish_boarding(fitting)
	if term.take_car(0) != rig:
		return "The reserved rig could not board"
	term.finish_boarding(rig)
	term._advance_construction(20)
	if term.work_stage != Terminal.WorkStage.DRAINING or term.build_remaining != Terminal.BUILD_MINUTES:
		return "Crew entered while an already-dispatched car was still maneuvering"
	term.finish_boarding(dispatched)
	term._advance_construction(1)
	if term.work_stage != Terminal.WorkStage.ARRIVING:
		return "Crew should arrive once the final vehicle is safely aboard"
	term._advance_construction(0)
	if term.stage_progress() != 0.0:
		return "Construction continued while paused"
	term._advance_construction(Terminal.ARRIVAL_MINUTES)
	if term.work_stage != Terminal.WorkStage.PAVING:
		return "Paving must follow arrival"
	term._advance_construction(Terminal.BUILD_MINUTES - Terminal.ARRIVAL_MINUTES - Terminal.DEPARTURE_MINUTES)
	if term.work_stage != Terminal.WorkStage.LEAVING or term.capacity() != capacity:
		return "Vehicles regained access before the crew left"
	term._advance_construction(Terminal.DEPARTURE_MINUTES)
	if term.work_stage != Terminal.WorkStage.OPEN or term.capacity() != 5 * term.slots_per_lane or sim.available_cash != 100:
		return "Expected one charge, all original spaces and one new lane"
	for car in [rig, fitting, dispatched]:
		car.free()
	# A small site could have room to pave, but no safe place to stage.
	term.work_stage = Terminal.WorkStage.IDLE
	term.lanes[0] = [first]
	if term.buy_holding_lane() or sim.available_cash != 100:
		return "Unsafe construction was sold"
	sim.free()
	return ""


func _initialize() -> void:
	game = load(Scenes.SANDBOX).instantiate()
	root.add_child(game)

func fail(message: String) -> bool:
	push_error(message)
	quit(1)
	return false

func _process(_dt: float) -> bool:
	frame += 1
	if frame == 1:
		for count in [1, 2]:
			var error := check_drain(count)
			if not error.is_empty():
				return fail(error)
		terminal = game.sim.terminals.values()[0]
		original_capacity = terminal.capacity()
		served_at_purchase = terminal.served_today
		var price := terminal.island.lane_extension_price
		var initial_funds: float = game.sim.available_cash
		game.sim.terminal_spending += initial_funds
		if terminal.buy_holding_lane():
			return fail("Unaffordable lane purchased")
		game.sim.terminal_spending -= initial_funds
		while game.sim.available_cash < price:
			game.sim.fares.credit_flat(false)
		var before: float = game.sim.available_cash
		if not terminal.buy_holding_lane() or terminal.buy_holding_lane():
			return fail("Expected exactly one successful purchase")
		if not is_equal_approx(before - price, game.sim.available_cash) or terminal.capacity() != original_capacity - terminal.island.construction_staging_lanes * terminal.slots_per_lane:
			return fail("Wrong charge or premature capacity increase")
		Engine.time_scale = 8.0
	if terminal.work_stage == Terminal.WorkStage.PAVING:
		saw_crew = true
		if not terminal._staging_clear():
			return fail("Equipment and traffic occupied the same lanes")
	if terminal.extra_lane != null:
		if not saw_crew or terminal.served_today <= served_at_purchase:
			return fail("Terminal did not keep boarding while its new lane was built")
		if terminal.capacity() != original_capacity + terminal.slots_per_lane or terminal.buy_holding_lane():
			return fail("Expansion exceeded the site limit")
		for vehicle: Vehicle in terminal.extra_lane.queue:
			observed[vehicle.get_instance_id()] = true
		for ferry: Ferry in game.sim.ferries:
			for car: Vehicle in ferry.aboard:
				if observed.has(car.get_instance_id()):
					if ferry.route.id != terminal.island.slips[0]:
						return fail("Vehicle boarded the wrong service")
					print("New lane at %s: observed %d queued vehicles; one boarded %s on frame %d." % [terminal.island.name, observed.size(), ferry.ferry_name, frame])
					print("TEST PASSED")
					quit(0)
					return false
	if frame >= 6000:
		return fail("No vehicle from the purchased lane boarded")
	return false
