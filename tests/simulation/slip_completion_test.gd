extends SceneTree
## A paid refit and new berth both finish when one clock update spans the remaining job.

var failures := 0


func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var region := TinyRegion.build()
	for town in region.map.towns:
		town.slips[0].size = 1
	var scenario := Scenario.from_network(region.map, ["Test ferry"], [2])
	scenario.cash = 1000000.0
	var sim := Simulation.new(VehicleFactory.create)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	if sim.ferries.is_empty():
		push_error("The purchase fixture needs a scheduled ferry")
		sim.free()
		quit(1)
		return
	var boat := sim.ferries[0]
	var terminal := boat.term_b if boat.here() == boat.term_a else boat.term_a
	check_purchase(sim, terminal, boat, TerminalUpgrade.Kind.REFIT)
	check_purchase(sim, terminal, boat, TerminalUpgrade.Kind.TIE_UP)
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_purchase(sim: Simulation, terminal: Terminal, boat: Ferry, kind: TerminalUpgrade.Kind) -> void:
	var existing := kind == TerminalUpgrade.Kind.REFIT
	var offer := terminal.find_upgrade(kind, 0) if existing else terminal.find_upgrade(kind)
	var cash := sim.available_cash
	if not terminal.buy(offer):
		check(false, "Could not buy %s in the fixture" % TerminalUpgrade.Kind.keys()[kind])
		return
	var index := terminal.refit_slip
	var slip := terminal.town.slips[index]
	var size_before := slip.size
	var opened: Array[int] = []
	var on_built := func(i: int) -> void: opened.append(i)
	terminal.slip_built.connect(on_built)
	terminal._process(0.0)
	check(terminal.refit_stage == Terminal.RefitStage.ARRIVING, "The unoccupied slip is clear")
	terminal._process((terminal.refit_remaining + (0.0 if existing else 30.0)) / Units.MINUTES_PER_SECOND)
	terminal._process(1.0)
	check(terminal.refit_stage == Terminal.RefitStage.NONE and not terminal.tie_up_closed(index), "The crane releases the slip")
	check(is_equal_approx(cash - sim.available_cash, offer.price), "The completed purchase is charged once")
	if existing:
		check(slip.size == size_before + 1 and opened.is_empty(), "Widen the existing slip exactly one size")
		check(slip.fits(MapData.Slip.LARGEST_BOAT[size_before + 1]), "The wider slip accepts the larger hull")
	else:
		check(opened == [index] and not slip.building, "Open the purchased berth exactly once")
		check(boat.free_tie_up(terminal) == index, "The ferry can choose the new berth")
	terminal.slip_built.disconnect(on_built)
