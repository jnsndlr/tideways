extends "res://tests/support/company_snapshot_case.gd"
## Save both on arrival and while real passengers and vehicles are leaving.


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	for reverse in [false, true]:
		_crossing(reverse)
	finish()


func _advance(ferry: Ferry) -> void:
	_step(ferry)
	for walker: Passenger in ferry.sim.passengers.get_children():
		if not walker.is_queued_for_deletion() and not walker.path.is_empty():
			walker._process(DT)


func _crossing(reverse: bool) -> void:
	var sim := _world()
	_empty_queues(sim)
	var ferry := sim.ferries[0]
	if reverse:
		ferry.start_staggered(2)
	var port := ferry.here()
	var stay := _enqueue_vehicle(
		port, VehicleFactory.from_parts(true, "tractor_day", 2, "trailer_container", 5)
	)
	_enqueue(port, 3)
	_enqueue(port, 4)
	_enqueue(ferry.destination(), 1)
	for i in 5:
		port._spawn_passenger()
	var landing := {}
	var dispatching := {}
	var initial_poses := []
	for frame in 10000:
		_advance(ferry)
		if ferry.state == Ferry.State.SAILING:
			# A through booking retains its occupied cells after arrival.
			stay.dest = port.town.id
			ferry.passengers_aboard[0].dest = port.town.id
		if ferry.state != Ferry.State.UNLOADING:
			continue
		if landing.is_empty():
			check(not ferry._ramp_down(), "Save while the apron is landing")
			landing = _save(sim)
		if ferry._unload_queue.size() == 1 and not ferry._homeward_walkers.is_empty():
			dispatching = _save(sim)
			initial_poses = _deck_poses(ferry)
			break
	check(
		not landing.is_empty() and not dispatching.is_empty(), "Captured both unloading checkpoints"
	)
	if not landing.is_empty() and not dispatching.is_empty():
		_check_damage(dispatching, ferry.fleet_key)
		var next_boarding := {}
		for saved: Dictionary in [landing, dispatching]:
			var copy := CompanySnapshot.restore(saved, _world, VehicleFactory.from_parts)
			check(copy != null, "Restore unloading in direction %s" % reverse)
			if copy == null:
				continue
			var hull := copy.ferries[0]
			if saved == landing:
				for i in 300:
					if hull._unload_queue.size() == 1:
						break
					_advance(hull)
			_compare_dispatch(ferry, hull, initial_poses)
			for i in 1000:
				if copy.ledger.cars_total == 4:
					break
				_advance(hull)
			check(
				copy.ledger.cars_total == 4 and copy.ledger.passengers_total == 5,
				"Next boarding credits one new fare"
			)
			var expected := _save(copy)
			check(
				not expected.is_empty(), "Next loading checkpoint accounts for every active actor"
			)
			if saved == landing:
				next_boarding = expected
			else:
				check(
					expected == next_boarding,
					"Both restore points give the same next loading record"
				)
			copy.free()
		for i in 1000:
			if sim.ledger.cars_total == 4:
				break
			_advance(ferry)
		check(_save(sim) == next_boarding, "Uninterrupted and restored next boarding match")
	sim.free()


func _deck_poses(ferry: Ferry) -> Array:
	var rows := []
	for car in ferry.aboard + ferry._unload_queue:
		rows.append(
			[
				car.body_paint,
				car.transform,
				car.trailer.transform if car.trailer else null,
				ferry.deck.occupants.count(car.get_instance_id())
			]
		)
	return rows


func _compare_dispatch(live: Ferry, copy: Ferry, poses: Array) -> void:
	check(_deck_poses(copy) == poses, "Parked transforms and retained/released cells match")
	check(
		copy.here().unloading_ferry == copy and copy._last_sent != null,
		"The correct hull owns the terminal and last discharged vehicle"
	)
	check(
		copy._last_sent.body_paint == live._last_sent.body_paint,
		"Last discharge matches the source actor"
	)
	check(
		copy._pax_unload_queue == live._pax_unload_queue,
		"Remaining passengers retain their order and paid fares"
	)
	check(
		copy._homeward_walkers.size() == live._homeward_walkers.size(),
		"All passengers already going home are restored"
	)
	for i in mini(copy._homeward_walkers.size(), live._homeward_walkers.size()):
		var a := live._homeward_walkers[i]
		var b := copy._homeward_walkers[i]
		check(
			a.path == b.path and a.position.is_equal_approx(b.position) and a.variant == b.variant,
			"Homeward walker continues the same path"
		)
	check(
		(
			is_equal_approx(copy._pax_dispatch_timer, live._pax_dispatch_timer)
			and is_equal_approx(copy._dispatch_timer, live._dispatch_timer)
		),
		"Vehicle and pedestrian dispatch resume on the same tick"
	)


func _check_damage(saved: Dictionary, hull_key: String) -> void:
	var target := _world(true)
	var hull := target.ferries[0]
	var voyage: Dictionary = saved.voyages[hull_key]
	var port := hull.term_a if voyage.from == hull.term_a.town.key else hull.term_b
	port.unloading_ferry = target.ferries[1]
	check(
		not FerryCrossingSnapshot.restore(voyage, hull, VehicleFactory.from_parts),
		"Two hulls cannot claim the same unloading terminal"
	)
	check(
		port.unloading_ferry == target.ferries[1] and hull._unload_queue.is_empty(),
		"Failure preserves the other hull's lock and the empty manifest"
	)
	target.free()
	var wrong := saved.duplicate(true)
	wrong.voyages[hull_key].unloading.ramp = [0.2, 0.4]
	check(
		CompanySnapshot.restore(wrong, _world, VehicleFactory.from_parts) == null,
		"Reject an impossible landing pose"
	)
	wrong = saved.duplicate(true)
	wrong.voyages[hull_key].vehicles.back().released = false
	check(
		CompanySnapshot.restore(wrong, _world, VehicleFactory.from_parts) == null,
		"Reject a released booking claiming deck cells"
	)
	wrong = saved.duplicate(true)
	wrong.voyages[hull_key].homeward_walkers[0].path = []
	check(
		CompanySnapshot.restore(wrong, _world, VehicleFactory.from_parts) == null,
		"Reject a damaged homeward walker"
	)
	wrong = saved.duplicate(true)
	wrong.voyages[hull_key].version = 3
	check(
		CompanySnapshot.restore(wrong, _world, VehicleFactory.from_parts) == null,
		"Older schemas cannot encode unloading"
	)
