extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	call_deferred("_run")


func _world() -> Simulation:
	var region := TinyRegion.build(3)
	# Two purchasable dock sites, as on the authored map.
	for town in region.map.towns.slice(1):
		town.built = false
		town.site = 0
		region.map.island_of(town).dock_sites.append(MapData.DockSite.new())
	var scenario := Scenario.new()
	scenario.cash = 1000000
	scenario.terminals.append(region.map.towns[0].key)
	var sim := Simulation.new(VehicleFactory.create)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	return sim


func _save(sim: Simulation) -> Dictionary:
	var state := {
		"sites": DockSiteSnapshot.capture(sim), "ledger": sim.ledger.snapshot(sim.map.routes)
	}
	return JSON.parse_string(JSON.stringify(state, "", true, true))


func _run() -> void:
	var live := _world()
	var east := live.map.towns[1]
	var north := live.map.towns[2]
	var start := live.available_cash
	var cost := live.dock_price(east) + live.dock_price(north)
	check(live.buy_dock(east), "Buy the first dock site")
	live._advance_docks(200.375)
	check(live.buy_dock(north), "Buy the second dock site")
	live._advance_docks(30)
	var both_pending := _save(live)
	live._advance_docks(500)
	var one_open := _save(live)
	live._advance_docks(1000)
	var finished := _save(live)
	check(
		live.available_cash == start - cost and live.terminals.size() == 3,
		"Both sites paid once and open"
	)
	live.free()
	for saved: Dictionary in [both_pending, one_open, finished]:
		_check_resume(saved, finished)
	finish()


func _check_resume(saved: Dictionary, finished: Dictionary) -> void:
	var fresh := _world()
	var before := DockSiteSnapshot.capture(fresh)
	var record: Dictionary = saved.sites
	for invalid: Variant in [-1, 721, "0", INF, null]:
		var bad := record.duplicate(true)
		bad.sites[fresh.map.towns[2].key] = invalid
		check(
			not DockSiteSnapshot.restore(bad, fresh) and DockSiteSnapshot.capture(fresh) == before,
			"Damaged site leaves the entire harbour intact"
		)
	var missing := record.duplicate(true)
	missing.sites.erase(fresh.map.towns[0].key)
	check(not DockSiteSnapshot.restore(missing, fresh), "Cannot erase an opening terminal")
	fresh.ledger = CompanyLedgerSnapshot.restore(saved.ledger, fresh.map.routes)
	check(
		DockSiteSnapshot.restore(record, fresh) and _save(fresh) == saved,
		"Both paid project clocks survive the JSON round trip"
	)
	var openings: Array[String] = []
	fresh.terminal_opened.connect(func(term: Terminal): openings.append(term.town.key))
	var pending := fresh.docks_building.size()
	for town in fresh.map.towns:
		check(not fresh.buy_dock(town), "An owned or pending dock cannot be bought again")
	fresh._advance_docks(1440)
	fresh._advance_docks(1440)
	check(
		openings.size() == pending and fresh.terminals.size() == 3,
		"Only still-pending sites open, exactly once"
	)
	check(_save(fresh) == finished, "Final towns and cash match uninterrupted construction")
	fresh.free()
