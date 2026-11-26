extends "res://tests/support/terminal_snapshot_case.gd"
## The fare posts when the person leaves the waiting queue, before they cross the ramp.

const DT := 0.1


func _initialize() -> void:
	call_deferred("_run")


func _step(ferry: Ferry) -> void:
	ferry.sim.minutes += Units.game_minutes(DT)
	for ramp in ferry.here().slip_ramps:
		if ramp:
			ramp._process(DT)
	ferry._process(DT)
	for person: Passenger in ferry.sim.passengers.get_children():
		if not person.is_queued_for_deletion() and not person.path.is_empty():
			person._process(DT)


func _save(ferry: Ferry) -> Dictionary:
	return JSON.parse_string(
		JSON.stringify(
			{
				"voyage": FerryCrossingSnapshot.capture(ferry),
				"holding": TerminalHoldingSnapshot.capture(ferry.here()),
				"ledger": ferry.sim.ledger.snapshot(ferry.sim.map.routes),
				"clock": CompanyClockSnapshot.capture(ferry.sim)
			},
			"",
			true,
			true
		)
	)


func _run() -> void:
	var sim := _world()
	var ferry := sim.ferries[0]
	var term := ferry.here()
	for row in term.passenger_queue:
		if row.node:
			row.node.free()
	term.passenger_queue.clear()
	for i in 3:
		term._spawn_passenger()
	var paid := {}
	var clearing := {}
	for i in 5000:
		_step(ferry)
		if paid.is_empty() and ferry._pax_walkers.size() == 1:
			paid = _save(ferry)
		if clearing.is_empty() and ferry._load_phase == Ferry.LoadPhase.WALK_ON_CLEAR:
			clearing = _save(ferry)
		if ferry._load_phase == Ferry.LoadPhase.VEHICLES:
			break
	var expected := _save(ferry)
	check(
		not paid.is_empty() and not clearing.is_empty(),
		"Captured a paid passenger walking on and the ramp clearing"
	)
	check(
		sim.passengers_today == 3 and ferry.passengers_aboard.size() == 3,
		"All three waiting people paid and boarded"
	)
	sim.free()
	var legacy := _world()
	var v1: Dictionary = expected.voyage.duplicate(true)
	v1.version = 1.0
	v1.erase("homeward_walkers")
	check(
		FerryCrossingSnapshot.restore(v1, legacy.ferries[0], VehicleFactory.from_parts),
		"Existing vehicle-boarding saves still load"
	)
	legacy.free()
	for saved: Dictionary in [paid, clearing]:
		if not saved.is_empty():
			_resume(saved, expected)
	finish()


func _resume(saved: Dictionary, expected: Dictionary) -> void:
	var sim := _world()
	var ferry := sim.ferries[0]
	check(CompanyClockSnapshot.restore(saved.clock, sim), "Restore the same instant")
	sim.ledger = CompanyLedgerSnapshot.restore(saved.ledger, sim.map.routes)
	check(
		TerminalHoldingSnapshot.restore(saved.holding, ferry.here(), VehicleFactory.from_parts),
		"Restore people still in line"
	)
	var damaged: Dictionary = saved.voyage.duplicate(true)
	damaged.walk_ons.walkers.back().path = [[0, "bad", 0]]
	var count := sim.passengers.get_child_count()
	check(
		(
			not FerryCrossingSnapshot.restore(damaged, ferry, VehicleFactory.from_parts)
			and sim.passengers.get_child_count() == count
		),
		"Bad path creates no walkers"
	)
	check(
		FerryCrossingSnapshot.restore(saved.voyage, ferry, VehicleFactory.from_parts),
		"Resume paid walk-ons"
	)
	check(
		_save(ferry) == saved, "Restore walking poses, paths, timers, seats, queue and paid ledger"
	)
	for i in 5000:
		_step(ferry)
		if ferry._load_phase == Ferry.LoadPhase.VEHICLES:
			break
	check(
		_save(ferry) == expected,
		"The same three fares post and vehicles may load at the same minute"
	)
	sim.free()
