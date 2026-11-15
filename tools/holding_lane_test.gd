extends SceneTree
## Purchase once, keep original capacity during construction, then trace a car
## from the added lane to the deck using normal demand and ferry dispatch.

var game: Node
var terminal: Terminal
var frame := 0
var original_capacity: int
var observed := {}

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
		terminal = game.sim.terminals.values()[0]
		original_capacity = terminal.capacity()
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
		if not is_equal_approx(before - price, game.sim.available_cash) or terminal.capacity() != original_capacity:
			return fail("Wrong charge or premature capacity increase")
		Engine.time_scale = 8.0
	if terminal.extra_lane != null:
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
