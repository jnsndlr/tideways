extends "res://tests/support/company_snapshot_case.gd"
## The sale posts once. Its tug and hull continue outside the working roster.


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var sim := _world()
	var slot := SaveGame.new()
	slot.remember_region(sim)
	var bought := sim.buy_ferry(1)
	if bought == null:
		check(false, "Buy the second hull")
		sim.free()
		finish()
		return
	var delivery := bought.tow
	delivery.s = delivery.path.length - 1
	delivery.committed = true
	for tick in 100:
		delivery._process(0.1)
		if delivery.phase == DeliveryTow.Phase.LEAVING:
			break
	var before := sim.available_cash
	check(sim.sell_ferry(bought), "Sell the delivered purchased ferry")
	var sale := bought.tow
	check(
		sale.outbound and bought not in sim.ferries and bought not in sim.marine.vessels,
		"A sold hull is present only for the tow"
	)
	check(
		sim.available_cash == before + 24000 and sim.ledger.today.sales == 24000,
		"Credit the $24,000 sale immediately"
	)
	var ledger := sim.ledger.snapshot(sim.map.routes)
	var phases := {}
	for tick in 20000:
		sale._process(0.2)
		if sale not in sim.tows:
			break
		if phases.has(sale.phase):
			continue
		if sale.phase == DeliveryTow.Phase.PULLING and sale.s < 100:
			continue
		phases[sale.phase] = true
		var saved := _save(sim)
		_compare_phase(saved, sim, sale)
		if sale.phase == DeliveryTow.Phase.PULLING:
			_check_invalid(_save(sim), slot, sim)
	check(
		phases.size() == 3 and sale not in sim.tows,
		"The tug fetches, turns and removes the sold hull"
	)
	var cleared := _save(sim)
	check(
		not cleared.is_empty() and cleared.sale_tows.is_empty(), "The next save has no outgoing tow"
	)
	var cold := _restore(cleared)
	if cold:
		check(
			(
				cold.ferries.size() == 1
				and cold.tows.is_empty()
				and cold.ledger.snapshot(cold.map.routes) == ledger
			),
			"Reopen after departure without selling or spawning the boat again"
		)
		var next := sim.buy_ferry(1)
		var next_cold := cold.buy_ferry(1)
		check(
			next != null and next_cold != null and next.fleet_key == next_cold.fleet_key,
			"The next purchased hull gets the same identity after departure"
		)
		cold.free()
	sim.free()
	_check_original_guard()
	finish()


func _restore(record: Dictionary) -> Simulation:
	var result := CompanySnapshot.restore(record, _world, VehicleFactory.from_parts)
	check(result != null, "A valid paid sale reopens")
	return result


func _compare_phase(record: Dictionary, sim: Simulation, live: DeliveryTow) -> void:
	var copy := _restore(record)
	if copy == null:
		return
	var tow := copy.tows[0]
	check(
		copy.tows.size() == 1 and tow.outbound and tow.phase == live.phase and tow.ferry.tow == tow,
		"Only the sale tow returns"
	)
	check(
		(
			tow.ferry.fleet_key == live.ferry.fleet_key
			and tow.ferry not in copy.ferries
			and tow.ferry not in copy.marine.vessels
			and copy.marine.vessels.count(tow) == 1
		),
		"Restore the sold identity and correct traffic registrations"
	)
	check(
		(
			tow.global_transform.is_equal_approx(live.global_transform)
			and tow.ferry.global_transform == live.ferry.global_transform
		),
		"Both actors keep their visible poses"
	)
	check(
		tow.path.pts == live.path.pts and tow.s == live.s and tow.committed == live.committed,
		"Retain the channel, progress and berth clearance"
	)
	check(
		copy.ledger.snapshot(copy.map.routes) == sim.ledger.snapshot(sim.map.routes),
		"Reopening never posts a second sale"
	)
	if tow.phase == DeliveryTow.Phase.PULLING:
		check(tow.ferry.consort == tow and tow.consort == tow.ferry, "The towline stays attached")
	live._process(0.125)
	tow._process(0.125)
	check(
		(
			tow.phase == live.phase
			and tow.global_transform.is_equal_approx(live.global_transform)
			and tow.ferry.global_transform.is_equal_approx(live.ferry.global_transform)
		),
		"The next tow step matches uninterrupted movement"
	)
	if tow.phase == DeliveryTow.Phase.PULLING and live.s > 100:
		_check_reused_berth(copy, tow)
	copy.free()


func _check_reused_berth(sim: Simulation, sale: DeliveryTow) -> void:
	var term := sale.ferry.here()
	var berth := sale.ferry.tie_up
	for tick in 2000:
		if not sale.committed:
			break
		sale._process(0.2)
	check(not sale.committed, "The sold hull cleared its berth")
	var next := sim.buy_ferry(1)
	check(
		next != null and next.fleet_key != sale.ferry.fleet_key,
		"Reserve a new hull identity before the old boat leaves the chart"
	)
	if next == null:
		return
	check(
		next.here() == term and next.tie_up == berth,
		"The next delivery can reserve the cleared berth"
	)
	var checkpoint := _save(sim)
	var reopened := _restore(checkpoint)
	if reopened:
		check(
			reopened.tows.size() == 2 and reopened.ferries[-1].fleet_key == next.fleet_key,
			"Restore overlapping inbound and outbound trips with distinct hulls"
		)
		reopened.free()
	for phase in ["FETCHING", "TURNING"]:
		var blocked := checkpoint.duplicate(true)
		blocked.sale_tows[0].committed = true
		blocked.sale_tows[0].phase = phase
		check(
			CompanySnapshot.restore(blocked, _world, VehicleFactory.from_parts) == null,
			"An outbound tug cannot reserve an inbound boat’s berth while " + phase
		)


func _check_invalid(saved: Dictionary, slot: SaveGame, sim: Simulation) -> void:
	var previous := SaveGame._path
	SaveGame._path = "user://sale-tow-%d.json" % OS.get_process_id()
	check(
		slot.save_company(sim, "", "Sandbox", false) == OK, "The public slot saves an outgoing tow"
	)
	var bytes := FileAccess.get_file_as_bytes(SaveGame._path)
	for field in [
		"phase",
		"owned",
		"duplicate",
		"berth",
		"path",
		"distance",
		"position",
		"basis",
		"commit",
		"format"
	]:
		var damaged := saved.duplicate(true)
		var row: Dictionary = damaged.sale_tows[0]
		match field:
			"phase":
				row.phase = "FETCHING"
			"owned":
				row.hull = sim.ferries[0].fleet_key
			"duplicate":
				damaged.sale_tows.append(row.duplicate(true))
			"berth":
				row.offset += 999
			"path":
				row.path[1][0] += 20
			"distance":
				row.distance = -1
			"position":
				row.hull_position[0] += 20
			"basis":
				row.hull_basis[0] = row.hull_basis[1]
			"commit":
				row.committed = not row.committed
			"format":
				damaged.version = 5
		check(
			CompanySnapshot.restore(damaged, _world, VehicleFactory.from_parts) == null,
			"Reject damaged outbound " + field
		)
	check(
		FileAccess.get_file_as_bytes(SaveGame._path) == bytes and _save(sim) == saved,
		"Rejected sale data leaves live company and slot unchanged"
	)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SaveGame._path))
	SaveGame._path = previous


func _check_original_guard() -> void:
	var live := _world()
	var slot := SaveGame.new()
	slot.remember_region(live)
	var previous := SaveGame._path
	SaveGame._path = "user://original-sale-%d.json" % OS.get_process_id()
	check(slot.save_company(live, "", "Sandbox", false) == OK, "Seed the original company's slot")
	var bytes := FileAccess.get_file_as_bytes(SaveGame._path)
	var starter := live.ferries[0]
	starter._orders.holding = true
	check(live.sell_ferry(starter), "The original boat can be sold in play")
	check(
		(
			slot.save_company(live, "", "Sandbox", false) == ERR_UNAVAILABLE
			and FileAccess.get_file_as_bytes(SaveGame._path) == bytes
		),
		"Selling an original authored hull keeps its last recoverable player slot"
	)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SaveGame._path))
	SaveGame._path = previous
	live.free()
