extends "res://tests/device/company_reopen_probe.gd"
## Two cold launches on the authored shared-slip map. Set TIDEWAYS_REOPEN_MAP
## to opening, TIDEWAYS_REOPEN_RUN to a fresh ID and TIDEWAYS_REOPEN_PHASE to
## record or resume. The second launch gets its scenario from the saved slot.

const SCENARIO := "res://maps/shared_slip.json"


func _run() -> void:
	if _phase == "record":
		Scenes.launch_options = SessionLaunchOptions.new(["--scenario=shared_slip"])
		Scenes.launch_options.entry = SessionLaunchOptions.Entry.MENU
	await super._run()


func _record(session: WorldSession) -> void:
	var sim := session.sim
	var town := _madrona(sim)
	if session.save_scenario != SCENARIO or town == null:
		_fail_review("Launch the authored shared_slip scenario")
		return
	var offer := town.find_upgrade(TerminalUpgrade.Kind.SLIP)
	var before := sim.available_cash
	if offer == null or not town.buy(offer) or before - sim.available_cash != offer.price:
		_fail_review("The second working slip was not purchased at its quoted price")
		return
	var index := town.town.slips.size() - 1
	_report.purchase = {
		"price": offer.price, "cash_before": before, "cash_after": sim.available_cash, "slip": index
	}
	_report.status = "purchased"
	_write_report()
	session.hud.set_speed(2)
	var ferry := await _approaching(sim, town, index)
	if ferry == null:
		_fail_review("No ordinary service approached the reassigned Madrona slip")
		return
	var menu := await _open_save_menu(session)
	if menu == null:
		return
	_report.checkpoint = _approach_state(ferry, town, index)
	if not _activate_save(session, menu):
		return
	await _follow_to_dock(ferry, town, index)


func _madrona(sim: Simulation) -> Terminal:
	for town: Terminal in sim.terminals.values():
		if town.town.key.begins_with("island-2/"):
			return town
	return null


func _approaching(sim: Simulation, town: Terminal, slip: int) -> Ferry:
	var deadline := Time.get_ticks_msec() + 300000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if town.town.slips[slip].building or town.town.slips[slip].routes.is_empty():
			continue
		# The captain chooses a landing side inside the guide contacts. Save after
		# that draw so both processes follow the same chosen approach.
		for ferry in sim.ferries:
			if (
				ferry.destination() == town
				and ferry.route.id in town.town.slips[slip].routes
				and ferry.state == Ferry.State.SAILING
				and ferry._landing_side != 0.0
				and ferry.path_left() > 15.0
				and ferry.path_left() < Ferry.LAND_RUN
			):
				return ferry
	return null


func _at_reopen(session: WorldSession) -> void:
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	session.hud.set_speed(2)
	var town := _madrona(session.sim)
	var ferry := _find_ferry(session.sim, _control.checkpoint.hull)
	var slip := int(_control.purchase.slip)
	if ferry != null and town != null and slip < town.town.slips.size():
		_restored = _approach_state(ferry, town, slip)


func _resume(session: WorldSession) -> void:
	_report.checkpoint = _restored
	if session.save_scenario != SCENARIO or _restored != _control.checkpoint:
		_fail_review("Cold Continue changed the route, berth, ferry or accounts")
		return
	var ferry := _find_ferry(session.sim, _restored.hull)
	await process_frame
	session.sim.process_mode = Node.PROCESS_MODE_INHERIT
	await _follow_to_dock(ferry, _madrona(session.sim), int(_control.purchase.slip))


func _approach_state(ferry: Ferry, town: Terminal, slip: int) -> Dictionary:
	var route := ferry.route
	var curve := route.curve
	var geometry := []
	for i in curve.point_count:
		geometry.append(
			[
				SnapshotVector3.encode(curve.get_point_position(i)),
				SnapshotVector3.encode(curve.get_point_in(i)),
				SnapshotVector3.encode(curve.get_point_out(i))
			]
		)
	var assignments := []
	for slot in town.town.slips:
		var keys := []
		for rid in slot.routes:
			keys.append(ferry.sim.map.routes[rid].key)
		assignments.append(keys)
	var end := curve.sample_baked(0.0 if route.a == town.town.id else curve.get_baked_length())
	return _json_form(
		{
			"hull": ferry.fleet_key,
			"ferry": _hull_state(ferry),
			"minute": ferry.sim.abs_minutes(),
			"ledger": ferry.sim.ledger.snapshot(ferry.sim.map.routes),
			"town": town.town.key,
			"slip": slip,
			"offset": town.town.slip_offset(slip),
			"assignments": assignments,
			"geometry": geometry,
			"length": route.length,
			"endpoint": SnapshotVector3.encode(end),
			"berth": SnapshotVector3.encode(town.town.berth_center(slip))
		}
	)


func _follow_to_dock(ferry: Ferry, town: Terminal, slip: int) -> void:
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if ferry.here() != town or ferry.state == Ferry.State.SAILING:
			continue
		var delta := ferry.global_position - town.town.berth_center(slip)
		var distance := Vector2(delta.x, delta.z).length()
		_report.arrival = _approach_state(ferry, town, slip)
		_report.berth_distance = distance
		var route := ferry.route
		var endpoint := route.curve.sample_baked(0.0 if route.a == town.town.id else route.length)
		if (
			ferry.slip_at(town) != slip
			or distance > 30
			or route.id in town.town.slips[0].routes
			or endpoint.distance_to(town.town.dock_center(route.id)) > 1
		):
			_fail_review("The ferry reached the wrong slip or missed its new route endpoint")
			return
		if _phase == "resume" and _report.arrival != _control.arrival:
			_fail_review("The restored arrival, geometry or ledger differed from control")
			return
		_pass()
		return
	_fail_review("Timed out before the reassigned ferry arrived")
