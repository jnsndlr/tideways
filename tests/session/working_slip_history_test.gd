extends "res://tests/support/company_snapshot_case.gd"
## The same paid slip, approach curve, cargo and next landing in a new company.


func _initialize() -> void:
	_run.call_deferred()


func _ports() -> Simulation:
	var region := TinyRegion.build()
	var route := region.map.routes[0]
	region.terrain.h_grid.fill(-5.0)
	# Give the shuttle enough open water for the production approach blend.
	var curve := Curve3D.new()
	curve.bake_interval = 6.0
	var a := region.map.towns[route.a]
	var b := region.map.towns[route.b]
	var start := a.dock_center(route.id)
	var end := b.dock_center(route.id)
	curve.add_point(start)
	curve.add_point(start + a.dock_dir * 110)
	curve.add_point(start.lerp(end, 0.45) + Vector3(0, 0, 450))
	curve.add_point(end + b.dock_dir * 110)
	curve.add_point(end)
	route.curve = curve
	route.length = curve.get_baked_length()
	var scenario := Scenario.from_network(region.map, ["Slip trial"], [2])
	scenario.cash = 1000000
	var sim := Simulation.new(VehicleFactory.create, true, false)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	_last_target = weakref(sim)
	return sim


func _run() -> void:
	var sim := _ports()
	var ferry := sim.ferries[0]
	var terminal := ferry.destination()
	var route := ferry.route
	var offer := terminal.find_upgrade(TerminalUpgrade.Kind.SLIP)
	if offer == null or not terminal.buy(offer):
		check(false, "Purchase a working berth through the terminal catalogue")
		sim.free()
		finish()
		return
	terminal._refit.advance(0.0, true)
	terminal._refit.advance(1e6, true)
	var original := route.curve.get_baked_points()
	var saved := _save(sim)
	var legacy := CompanySnapshot.restore(saved, _ports, VehicleFactory.from_parts)
	check(legacy != null and saved.version == 6, "Read the pre-reassignment company format")
	if legacy:
		legacy.free()
	if not terminal.move_route_now(route.id, 1):
		check(false, "Move the shuttle into the purchased berth through the normal route owner")
		sim.free()
		finish()
		return
	var first := _save(sim)
	_check_slot(sim, terminal, first)
	_compare(first, sim)
	check(terminal.move_route_now(route.id, 0), "Move back to the original berth")
	check(
		original != route.curve.get_baked_points(),
		"Moving back rebakes even when the final slip number matches the opening"
	)
	_compare(_save(sim), sim)
	check(terminal.move_route_now(route.id, 1), "Move again to the paid berth")
	_empty_queues(sim)
	_enqueue(ferry.here(), 3)
	for frame in 14000:
		_step(ferry)
		if ferry.state == Ferry.State.SAILING and ferry.traveled > 130:
			break
	check(
		ferry.state == Ferry.State.SAILING and ferry.aboard.size() == 1,
		"Depart with a paid manifest for the reassigned berth"
	)
	var moving := _save(sim)
	var resumed := _compare(moving, sim, true)
	if resumed:
		for frame in 20000:
			_step(ferry)
			_step(resumed.ferries[0])
			if ferry.state == Ferry.State.UNLOADING:
				break
		var arrived := resumed.ferries[0]
		check(
			(
				arrived.state == Ferry.State.UNLOADING
				and arrived.here().town.slip_index(route.id) == 1
			),
			"Reopened ferry lands at the purchased working slip"
		)
		check(
			(
				ferry.global_position.is_equal_approx(arrived.global_position)
				and (
					sim.ledger.snapshot(sim.map.routes)
					== resumed.ledger.snapshot(resumed.map.routes)
				)
			),
			"Identical approach, fares and next sailing costs"
		)
		resumed.free()
	for field in ["from", "to", "town", "route", "shapes", "missing", "empty"]:
		var broken := moving.duplicate(true)
		match field:
			"from":
				broken.working_slips.moves[0].from = 1
			"to":
				broken.working_slips.moves[0].to = 99
			"town":
				broken.working_slips.moves[0].town = "unknown"
			"route":
				broken.working_slips.moves[0].route = "unknown"
			"shapes":
				broken.working_slips.shapes[route.key] = "invalid"
			"missing":
				broken.working_slips.moves.pop_front()
			"empty":
				broken.working_slips = {}
		var bad := CompanySnapshot.restore(broken, _ports, VehicleFactory.from_parts)
		check(
			bad == null and (field == "empty" or _last_target.get_ref() == null),
			"Discard invalid move history: " + field
		)
		if bad:
			bad.free()
	sim.free()
	finish()


func _compare(saved: Dictionary, sim: Simulation, keep := false) -> Simulation:
	var loaded := CompanySnapshot.restore(saved, _ports, VehicleFactory.from_parts)
	check(
		loaded != null and saved.get("version") == 7, "Restore versioned working slip assignments"
	)
	if not loaded:
		return null
	var route := sim.map.routes[0]
	var other := loaded.map.routes[0]
	check(
		(
			route.curve.get_baked_points() == other.curve.get_baked_points()
			and route.length == other.length
		),
		"Every point and distance survives replay"
	)
	var a := sim.terminals[route.b] as Terminal
	var b := loaded.terminals[route.b] as Terminal
	var slip := b.town.slip_index(route.id)
	check(
		(
			slip == a.town.slip_index(route.id)
			and b.ramps[route.id] == b.slip_ramps[slip]
			and a.slip_v == b.slip_v
		),
		"Working berth offset and ramp point to the saved slip"
	)
	check(
		_save(loaded).working_slips == saved.working_slips and _save(loaded).ledger == saved.ledger,
		"Subsequent saves retain the same history and purchase receipt"
	)
	if keep:
		return loaded
	loaded.free()
	return null


func _check_slot(sim: Simulation, term: Terminal, saved: Dictionary) -> void:
	var slot := SaveGame.new()
	slot.remember_region(sim)
	var previous := SaveGame._path
	SaveGame._path = "user://working-slip-%d.json" % OS.get_process_id()
	check(
		slot.save_company(sim, "", "Trial", false) == OK and SaveGame.read().snapshot == saved,
		"Player quick-save writes and reads a completed move"
	)
	var bytes := FileAccess.get_file_as_bytes(SaveGame._path)
	term._assignments._pending[sim.ferries[0].route.id] = 0
	check(
		(
			slot.save_company(sim, "", "Trial", false) == ERR_UNAVAILABLE
			and FileAccess.get_file_as_bytes(SaveGame._path) == bytes
		),
		"Pending reassignment preserves the last complete player slot"
	)
	term._assignments._pending.clear()
	var slipped := term.town.slips[1]
	slipped.routes.clear()
	check(
		(
			slot.save_company(sim, "", "Trial", false) == ERR_UNAVAILABLE
			and FileAccess.get_file_as_bytes(SaveGame._path) == bytes
		),
		"An untracked topology edit cannot replace the slot"
	)
	slipped.routes.append(sim.ferries[0].route.id)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(SaveGame._path))
	SaveGame._path = previous
