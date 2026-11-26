extends "res://tests/support/company_snapshot_case.gd"
## A $30,000 hull keeps its durable identity, booked deck and ledger when rebuilt.


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var sim := _world()
	var starter := sim.ferries[0]
	var older := _save(sim)
	older.version = 3
	var legacy := CompanySnapshot.restore(older, _world, VehicleFactory.from_parts)
	check(
		legacy != null and legacy.ferries.size() == 1, "Version 3 still restores the original fleet"
	)
	if legacy:
		legacy.free()
	var bought := sim.buy_ferry(1)
	check(bought != null, "Purchase a second ferry through FleetMarket")
	if bought == null:
		sim.free()
		finish()
		return
	check(CompanySnapshot.capture(sim).is_empty(), "A purchase under tow keeps the previous slot")
	var town := bought.here()
	var stops: Array[int] = [town.town.id, bought.destination().town.id]
	check(sim.reschedule(bought, stops), "Assign the bought ferry to two-stop service")
	# Complete the reserved delivery and let the tug leave the chart.
	var tug := bought.tow
	for tick in 8000:
		if tug.phase == DeliveryTow.Phase.LEAVING:
			break
		tug.committed = true
		tug._process(0.5)
	check(
		tug.phase == DeliveryTow.Phase.LEAVING and not tug.delivery_complete(),
		"The empty tug detached while the boat still lay at her delivery berth"
	)
	# Bring the first boat clear of the berth before the new hull takes service.
	starter.start_staggered(1)
	sim.marine.refresh_corridors()
	for frame in 15000:
		_step(bought)
		if bought.berth == Ferry.Berth.WORKING:
			break
	check(bought.berth == Ferry.Berth.WORKING, "Purchased hull has entered service")
	_empty_queues(sim)
	_enqueue(bought.here(), 2)
	for frame in 15000:
		_step(bought)
		if bought.state == Ferry.State.SAILING and bought.traveled > 150:
			break
	check(
		bought.state == Ferry.State.SAILING and not bought.aboard.is_empty(),
		"Purchased ferry sails with paid cargo"
	)
	check(tug.delivery_complete(), "Both boats work while the empty tug sails clear")
	bought.ferry_name = "Blue Heron"
	var checkpoint := _save(sim)
	var restored := CompanySnapshot.restore(checkpoint, _world, VehicleFactory.from_parts)
	check(restored != null, "Restore both original and purchased hull")
	if restored != null:
		_check_restored(sim, bought, checkpoint, restored)
		restored.free()
	if not checkpoint.is_empty():
		var damaged := checkpoint.duplicate(true)
		damaged.network.ferries[-1].purchased = false
		check(
			CompanySnapshot.restore(damaged, _world, VehicleFactory.from_parts) == null,
			"Reject conflicting purchase metadata"
		)
		check(
			_last_target.get_ref() == null, "Discard the damaged fleet and its staging simulation"
		)
		damaged = checkpoint.duplicate(true)
		damaged.version = 3
		check(
			CompanySnapshot.restore(damaged, _world, VehicleFactory.from_parts) == null,
			"Older formats cannot introduce paid hulls"
		)
	sim.free()
	finish()


func _check_restored(
	sim: Simulation, bought: Ferry, checkpoint: Dictionary, restored: Simulation
) -> void:
	var reopened := restored.ferries[-1]
	check(restored.tows.is_empty(), "The completed tow has no outstanding company work")
	check(
		(
			restored.ferries.size() == 2
			and reopened.purchased
			and reopened.fleet_key == bought.fleet_key
		),
		"Purchased key survives scene reconstruction"
	)
	check(
		(
			reopened.ferry_name == "Blue Heron"
			and reopened.stops == bought.stops
			and reopened.fc.size == 1
		),
		"Restore renamed hull and route"
	)
	check(
		(
			reopened.aboard.size() == bought.aboard.size()
			and is_equal_approx(reopened.traveled, bought.traveled)
		),
		"Restore the moving loaded deck"
	)
	check(
		(
			restored.ledger.snapshot(restored.map.routes) == sim.ledger.snapshot(sim.map.routes)
			and restored.ledger.today.purchases == 30000
		),
		"Reconstruction posts neither a purchase nor a fare"
	)
	check(
		restored.marine.vessels.count(reopened) == 1,
		"One traffic registration for the purchased hull"
	)
	var resaved := _save(restored)
	check(
		resaved.network == checkpoint.network and resaved.voyages == checkpoint.voyages,
		"Repeated save retains both identities and manifests"
	)
	restored.ledger.cash += 30000
	sim.ledger.cash += 30000
	var next := sim.buy_ferry(1)
	var next_restored := restored.buy_ferry(1)
	check(
		(
			next != null
			and next_restored != null
			and next.fleet_key == next_restored.fleet_key
			and next.fleet_key != bought.fleet_key
		),
		"Next purchase allocates the same distinct hull ID"
	)
