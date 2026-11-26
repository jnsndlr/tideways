extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	call_deferred("_run")


func _world(kind: TerminalUpgrade.Kind, clear_water: bool) -> Simulation:
	var region := TinyRegion.build()
	# A shallow bank along both sides makes the survey's cut and quote measurable.
	region.terrain.h_grid.fill(-2.0)
	for town: MapData.Town in region.map.towns:
		town.slips[0].size = 1
	var scenario := Scenario.from_network(region.map, ["Harbour ferry"], [2])
	scenario.cash = 10000000
	var sim := Simulation.new(VehicleFactory.create)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	if clear_water:
		var target := sim.ferries[0].destination()
		var offer := target.find_upgrade(kind)
		if offer != null:
			target.site_survey.dredge(offer.v, kind == TerminalUpgrade.Kind.SLIP)
			sim.slip_sites_changed.emit()
	return sim


func _run() -> void:
	for kind in [TerminalUpgrade.Kind.SLIP, TerminalUpgrade.Kind.TIE_UP]:
		for clear_water in [false, true]:
			_check_purchase(kind, clear_water)
	finish()


func _check_purchase(kind: TerminalUpgrade.Kind, clear_water: bool) -> void:
	var sim := _world(kind, clear_water)
	var term := sim.ferries[0].destination()
	var initial_grid := sim.terrain.h_grid.duplicate()
	check(term.buy_refit(0), "Buy a widening on the existing slip before expanding the harbour")
	term._refit.advance(0, true)
	term._refit.advance(1e6, true)
	var initial_cash := sim.available_cash
	var offer := term.find_upgrade(kind)
	if offer == null or not term.buy(offer):
		check(false, "Buy a real berth on the surveyed shallows")
		sim.free()
		return
	var i := term.town.slips.size() - 1
	var snapshots := [_save(term)]
	term._refit.advance(0, true)
	snapshots.append(_save(term))
	term._refit.advance(TerminalRefit.ARRIVAL + 1, true)
	snapshots.append(_save(term))
	term._refit.advance(term.refit_remaining - 10.0, true)
	snapshots.append(_save(term))
	term._refit.advance(100, true)
	var finished := _save(term)
	snapshots.append(finished)
	check(
		(
			(initial_grid == sim.terrain.h_grid) == clear_water
			and (offer.dredge_price == 0) == clear_water
		),
		"Only a shallow site charges for dredging and changes the channel"
	)
	check(
		sim.available_cash == initial_cash - offer.price and not term.town.slips[i].building,
		"One purchase pays for the working berth or tie-up and its dredging"
	)
	for checkpoint: Dictionary in snapshots:
		_compare(checkpoint, finished, sim.terrain.h_grid, kind, clear_water)
	sim.free()


func _save(term: Terminal) -> Dictionary:
	return JSON.parse_string(
		JSON.stringify(
			{
				"purchase": TerminalBerthPurchaseSnapshot.capture(term),
				"fitted": TerminalRefitSnapshot.capture(term),
				"ledger": term.sim.ledger.snapshot(term.sim.map.routes)
			},
			"",
			true,
			true
		)
	)


func _compare(
	saved: Dictionary,
	finished: Dictionary,
	seabed: PackedFloat32Array,
	kind: TerminalUpgrade.Kind,
	clear_water: bool
) -> void:
	var sim := _world(kind, clear_water)
	var term: Terminal = sim.terminals[sim.map.town_by_key(saved.purchase.town).id]
	sim.ledger = CompanyLedgerSnapshot.restore(saved.ledger, sim.map.routes)
	var before := sim.terrain.h_grid.duplicate()
	var invalid := saved.purchase.duplicate(true) as Dictionary
	invalid.remaining = -2.0
	check(
		(
			not TerminalBerthPurchaseSnapshot.restore(invalid, term)
			and term.town.slips.size() == term.original_slip_count
			and before == sim.terrain.h_grid
		),
		"Reject an invalid crane phase before cutting the seabed or fitting a berth"
	)
	var restored := TerminalBerthPurchaseSnapshot.restore(saved.purchase, term)
	check(restored, "Restore the purchased berth without buying it again")
	if restored:
		check(
			TerminalRefitSnapshot.restore(saved.fitted, term) and term.town.slips[0].size == 2,
			"Restore the earlier widening alongside the new crane job"
		)
		check(
			_save(term) == saved and sim.terrain.h_grid == seabed,
			"Physical dredging, crane stage, berth location and balance match uninterrupted work"
		)
		var index := term.original_slip_count
		var opened: Array[int] = []
		term.slip_built.connect(func(i: int): opened.append(i))
		var owed := term.town.slips[index].building
		term._refit.advance(0.0, true)
		term._refit.advance(1e6, true)
		term._refit.advance(1e6, true)
		check(
			opened.size() == int(owed) and not term.town.slips[index].building,
			"One large step opens outstanding work exactly once"
		)
		check(
			_save(term) == finished and sim.terrain.h_grid == seabed,
			"After completion both ledger and channel still match"
		)
		check(
			not TerminalBerthPurchaseSnapshot.restore(saved.purchase, term),
			"Reinstalling a purchase cannot append a duplicate berth"
		)
	sim.free()
