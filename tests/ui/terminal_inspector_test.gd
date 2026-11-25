extends SceneTree
## Selected-terminal rows subscribe to discrete changes while construction clocks
## update independently at the precision shown to the player.

var failures := 0
var layouts := 0
var titles: Array[String] = []
var changes: Array[String] = []


func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var region := TinyRegion.build()
	for town in region.map.towns:
		town.open_lanes = 2
		town.lane_extension_price = 150
		town.slips[0].size = 1
	var scenario := Scenario.from_network(region.map, ["Test ferry"], [2])
	scenario.cash = 1000000.0
	var sim := Simulation.new(VehicleFactory.create)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	if sim.ferries.is_empty():
		push_error("The inspector fixture needs a scheduled ferry")
		sim.free()
		quit(1)
		return
	var boat := sim.ferries[0]
	var term := boat.term_b if boat.here() == boat.term_a else boat.term_a
	var inspector := TerminalInspectorRows.new(term.town, term, sim, sim.wildlife, true)
	inspector.layout_changed.connect(_layout_changed)
	inspector.value_changed.connect(func(i: int, value: String) -> void: changes.append(titles[i] + ": " + value))
	inspector.refresh()
	for i in 32:
		inspector.refresh()
	check(layouts == 1 and changes.is_empty(), "Idle refreshes preserve the initial row layout and values")

	var waiting := term.total_queued()
	var boarded := term.take_car(term.lane_keys()[0])
	check(boarded != null, "The fixture needs a queued car to board")
	inspector.refresh()
	inspector.refresh()
	check(layouts == 1 and changes.count("Vehicles waiting: %d" % (waiting - 1)) == 1, "Boarding updates the waiting row once without rebuilding the layout")
	changes.clear()

	var cash := sim.available_cash
	check(term.buy_holding_lane(), "Buy a lane through the terminal")
	inspector.refresh()
	inspector.refresh()
	check(layouts == 2 and sim.available_cash == cash - 150 and titles.has("Construction"), "One purchase rebuilds the rows once and charges once")
	check(term.buy_refit(0), "Buy a simultaneous working-slip refit")
	term._process(0.01) # Both sites clear: the crew and crane are arriving.
	inspector.refresh()
	check(titles.has("Lane opens in") and titles.has("Slip reopens in"), "Show both active construction clocks")
	changes.clear()
	term._process(1.0 / Units.MINUTES_PER_SECOND)
	inspector.refresh()
	inspector.refresh()
	check(changes.count("Lane opens in: 119 game min") == 1 and changes.count("Slip reopens in: 189 game min") == 1,
		"Both countdown rows advance exactly once")
	changes.clear()
	term._process(0.1)
	inspector.refresh()
	check(changes.is_empty(), "No writes before the next displayed countdown minute")
	inspector = null
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func _layout_changed(rows: Array) -> void:
	layouts += 1
	titles.clear()
	for row in rows:
		titles.append(row[0])
