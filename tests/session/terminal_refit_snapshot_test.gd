extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	call_deferred("_run")


func _world() -> Simulation:
	var region := TinyRegion.build()
	for town in region.map.towns:
		town.slips[0].size = 1
		town.slips.append(MapData.Slip.new(1, true))
	var scenario := Scenario.from_network(region.map, ["Refit ferry"], [2])
	scenario.cash = 1000000
	var sim := Simulation.new(VehicleFactory.create)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	return sim


func _run() -> void:
	for tie_up in [false, true]:
		_check_project(tie_up)
	finish()


func _check_project(tie_up: bool) -> void:
	var live := _world()
	var term := live.ferries[0].destination()
	var index := term.next_refit(tie_up)
	var price := term.refit_price(index)
	var balance := live.available_cash
	check(term.buy_refit(index), "Buy an existing berth widening from the real catalogue")
	var checkpoints := [_save(term)]
	term._process(0)
	checkpoints.append(_save(term))
	term._process((TerminalRefit.ARRIVAL + 2) / Units.MINUTES_PER_SECOND)
	checkpoints.append(_save(term))
	term._process((term.refit_remaining - 10) / Units.MINUTES_PER_SECOND)
	checkpoints.append(_save(term))
	term._process(100 / Units.MINUTES_PER_SECOND)
	var finished := _save(term)
	checkpoints.append(finished)
	check(
		live.available_cash == balance - price and price == 8000, "Exactly one purchase is posted"
	)
	check(
		term.town.slips[index].size == 2 and term.refit_stage == TerminalRefit.Stage.NONE,
		"Working and tie-up refits finish at medium"
	)
	live.free()
	for snapshot: Dictionary in checkpoints:
		_compare(snapshot, finished, index)


func _save(term: Terminal) -> Dictionary:
	var data := {
		"harbour": TerminalRefitSnapshot.capture(term),
		"ledger": term.sim.ledger.snapshot(term.sim.map.routes)
	}
	return JSON.parse_string(JSON.stringify(data, "", true, true))


func _compare(saved: Dictionary, expected: Dictionary, index: int) -> void:
	var fresh := _world()
	var term: Terminal = fresh.terminals[fresh.map.town_by_key(saved.harbour.town).id]
	fresh.ledger = CompanyLedgerSnapshot.restore(saved.ledger, fresh.map.routes)
	var corrupt: Dictionary = saved.harbour.duplicate(true)
	corrupt.slips[-1].size = 999
	var before := _save(term)
	check(
		not TerminalRefitSnapshot.restore(corrupt, term) and _save(term) == before,
		"Reject corrupt slip before fitting any berth or changing cash"
	)
	var shuffled: Dictionary = saved.harbour.duplicate(true)
	shuffled.slips.reverse()
	var restored := TerminalRefitSnapshot.restore(shuffled, term)
	check(
		restored and _save(term) == saved,
		"Restore the actual crane stage and fitted sizes by berth position"
	)
	if restored:
		var widened: Array[int] = []
		term._refit.widen_slip.connect(func(i: int): widened.append(i))
		var owed := (
			term.refit_stage
			in [
				TerminalRefit.Stage.CLEARING,
				TerminalRefit.Stage.ARRIVING,
				TerminalRefit.Stage.WORKING
			]
		)
		term._process(0)
		term._process(1000 / Units.MINUTES_PER_SECOND)
		term._process(1000 / Units.MINUTES_PER_SECOND)
		check(
			widened.size() == int(owed),
			"Apply remaining widening exactly once, including a single long step"
		)
		check(_save(term) == expected, "Match uninterrupted harbour and ledger after completion")
		var slip := term.town.slips[index]
		check(slip.fits(4) and not slip.fits(5), "Restored berth takes the same hull classes")
		if term.slip_guides[index]:
			check(
				term.slip_guides[index].size == 4, "Physical guide clearance matches fitted berth"
			)
	fresh.free()
