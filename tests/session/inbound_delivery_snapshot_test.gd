extends "res://tests/support/company_snapshot_case.gd"
## Compare one paid tow to the same tow reopened from its company record.


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var sim := _world()
	var slot := SaveGame.new()
	slot.remember_region(sim)
	var old := _save(sim)
	old.version = 4
	var older := _restore(old)
	if older:
		older.free()
	var ferry := sim.buy_ferry(1)
	if ferry == null:
		check(false, "Fixture purchases the inbound ferry")
		sim.free()
		finish()
		return
	var tug := ferry.tow
	for tick in 60:
		tug._process(0.1)
	var far := _save(sim)
	var restored := _restore(far)
	if restored:
		_compare_tow(sim, restored)
		restored.free()
	_check_corruption(_save(sim), ferry)
	_check_slot(slot, sim)
	# The boat is on final push after entry clearance. Resume from the actual
	# vessel poses and let production arrival dispatch the handoff.
	tug.s = tug.path.length - 12.0
	tug.committed = true
	tug._place(0.0)
	var near := _save(sim)
	var closing := _restore(near)
	if closing:
		_check_handoff(sim, closing)
		var after := _save(closing)
		_check_booked_berth(after, near, ferry.fleet_key)
		var docked := _restore(after)
		if docked:
			var at_berth := docked.ferries[-1]
			check(
				(
					docked.tows.is_empty()
					and at_berth.berth == Ferry.Berth.TIED_UP
					and not at_berth.assigned
				),
				"Resume the delivered hull without creating a new tug"
			)
			check(
				(
					at_berth.tie_up == ferry.tie_up
					and at_berth.global_position.is_equal_approx(ferry.global_position)
				),
				"The purchased boat still occupies its berth"
			)
			check(
				(
					docked.ledger.today.purchases == 30000
					and _save(docked).voyages == _save(closing).voyages
				),
				"A second reopen preserves the delivery and fare records"
			)
			docked.free()
		closing.free()
	sim.free()
	_check_assigned()
	finish()


func _restore(saved: Dictionary) -> Simulation:
	var result := CompanySnapshot.restore(saved, _world, VehicleFactory.from_parts)
	check(result != null, "A valid delivery restores into a fresh region")
	return result


func _compare_tow(live: Simulation, restored: Simulation) -> void:
	var a := live.tows[0]
	var b := restored.tows[0]
	check(
		(
			restored.tows.size() == 1
			and b.ferry.tow == b
			and b.consort == b.ferry
			and b.ferry.consort == b
		),
		"Tow and ferry share one restored delivery"
	)
	check(
		(
			a.path.pts == b.path.pts
			and a.s == b.s
			and a.committed == b.committed
			and a.waiting == b.waiting
		),
		"Keep the channel path and its clearance"
	)
	check(
		(
			a.global_transform.is_equal_approx(b.global_transform)
			and a.ferry.global_transform.is_equal_approx(b.ferry.global_transform)
		),
		"Both vessel poses match at reopen"
	)
	check(is_equal_approx(a.minutes_left(), b.minutes_left()), "The delivery ETA matches")
	var bill := restored.ledger.snapshot(restored.map.routes)
	for tick in 5:
		a._process(0.1)
		b._process(0.1)
	check(
		(
			a.s == b.s
			and a.speed == b.speed
			and a.global_transform.is_equal_approx(b.global_transform)
		),
		"Restored tug moves in step with uninterrupted tug"
	)
	check(
		bill == live.ledger.snapshot(live.map.routes) and restored.ledger.today.purchases == 30000,
		"No duplicate settlement while underway"
	)


func _check_handoff(a: Simulation, b: Simulation) -> void:
	var counts := [0, 0]
	a.ferry_delivered.connect(func(_hull): counts[0] += 1)
	b.ferry_delivered.connect(func(_hull): counts[1] += 1)
	var tug := a.tows[0]
	var reopened := b.tows[0]
	_compare_tow(a, b)
	for tick in 2000:
		tug._process(0.1)
		reopened._process(0.1)
		if tug.phase == DeliveryTow.Phase.LEAVING:
			break
	check(
		counts == [1, 1] and reopened.phase == DeliveryTow.Phase.LEAVING,
		"Exactly one handoff in each company"
	)
	check(
		(
			reopened.ferry.tow == null
			and reopened.ferry.consort == null
			and reopened.ferry.global_position.is_equal_approx(tug.ferry.global_position)
		),
		"Both hulls arrive at the same berth"
	)
	reopened._process(0.1)
	check(
		counts == [1, 1] and b.ledger.today.purchases == 30000,
		"The departing tug cannot deliver or charge twice"
	)


func _check_booked_berth(after: Dictionary, before: Dictionary, key: String) -> void:
	var conflicting := after.duplicate(true)
	var extra: Dictionary = after.network.ferries[-1].duplicate(true)
	extra.key = "hull-2"
	conflicting.network.ferries.append(extra)
	var inbound: Dictionary = before.voyages[key].duplicate(true)
	inbound.service.hull = extra.key
	conflicting.voyages[extra.key] = inbound
	for ordering in 2:
		check(
			(
				CompanySnapshot.restore(conflicting, _world, VehicleFactory.from_parts) == null
				and _last_target.get_ref() == null
			),
			"A delivery cannot reserve the purchased hull's occupied berth"
		)
		conflicting.network.ferries.reverse()


func _check_corruption(saved: Dictionary, ferry: Ferry) -> void:
	var key := ferry.fleet_key
	for field in ["offset", "path", "distance"]:
		var damaged := saved.duplicate(true)
		var d: Dictionary = damaged.voyages[key].delivery
		match field:
			"offset":
				d.offset += 999
			"path":
				d.path[1][0] += 15
			"distance":
				d.distance = -1
		check(
			(
				CompanySnapshot.restore(damaged, _world, VehicleFactory.from_parts) == null
				and _last_target.get_ref() == null
			),
			"Discard malformed inbound " + field
		)
	var duplicate := saved.duplicate(true)
	var extra: Dictionary = duplicate.network.ferries[-1].duplicate(true)
	extra.key = "hull-99"
	duplicate.network.ferries.append(extra)
	var second: Dictionary = duplicate.voyages[key].duplicate(true)
	second.service.hull = extra.key
	duplicate.voyages[extra.key] = second
	check(
		(
			CompanySnapshot.restore(duplicate, _world, VehicleFactory.from_parts) == null
			and _last_target.get_ref() == null
		),
		"Reject two deliveries claiming one berth"
	)
	var older := saved.duplicate(true)
	older.version = 4
	check(
		CompanySnapshot.restore(older, _world, VehicleFactory.from_parts) == null,
		"Reject a delivery row in an older format"
	)
	check(_save(ferry.sim) == saved, "Invalid data left the live company untouched")


func _check_slot(slot: SaveGame, sim: Simulation) -> void:
	var previous := SaveGame._path
	SaveGame._path = "user://inbound-tow-%d.json" % OS.get_process_id()
	check(
		slot.save_company(sim, "", "Sandbox", false) == OK,
		"Write the real player slot during delivery"
	)
	var original := FileAccess.get_file_as_bytes(SaveGame._path)
	sim.tows[0].outbound = true
	check(
		(
			slot.save_company(sim, "", "Sandbox", false) == ERR_UNAVAILABLE
			and FileAccess.get_file_as_bytes(SaveGame._path) == original
		),
		"An unsupported outbound tow leaves the last saved bytes intact"
	)
	sim.tows[0].outbound = false
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SaveGame._path))
	SaveGame._path = previous


func _check_assigned() -> void:
	var sim := _world()
	var bought := sim.buy_ferry(1)
	var route: Array[int] = [bought.here().town.id, bought.destination().town.id]
	check(sim.reschedule(bought, route, [540]), "Assign a paid ferry under tow")
	bought.tow._process(0.25)
	var other := _restore(_save(sim))
	if other:
		var copy := other.ferries[-1]
		check(
			copy.assigned and copy.stops == route and copy.timetable == [540] and copy.tow != null,
			"Keep the planned first service under tow"
		)
		other.free()
	sim.free()
