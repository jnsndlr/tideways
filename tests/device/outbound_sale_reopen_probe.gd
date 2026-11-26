extends "res://tests/device/company_reopen_probe.gd"
## Reopen a sold ferry under tow and again after its two physical actors leave.
## Run record, resume, departed in separate processes with the same isolated slot.

const RESALE := 24000
var _sold_keys := []
var _exits := {}


func _run() -> void:
	if OS.get_environment("TIDEWAYS_REOPEN_OUTBOUND_SALE") != "1":
		await super._run()
		return
	if (
		_map != "opening"
		or not _run_id.is_valid_identifier()
		or _phase not in ["record", "resume", "departed"]
	):
		quit(2)
		return
	if not _prepare_sale_run():
		return
	node_added.connect(_watch_sale_world)
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await enter_game("New company" if _phase == "record" else "Continue", Scenes.MAIN_MAP):
		_fail_review("The opening company did not load")
		return
	var session := current_scene as WorldSession
	await _exercise_sale(session)


func _exercise_sale(session: WorldSession) -> void:
	if _phase == "record":
		if not await _buy_sell_and_save(session):
			return
	else:
		_report.checkpoint = _restored
		var expected: Dictionary = (
			_control.checkpoint if _phase == "resume" else _control.departed_checkpoint
		)
		if _restored != expected:
			_fail_review("The cold company or its outbound tow changed")
			return
		await process_frame
		session.sim.process_mode = Node.PROCESS_MODE_INHERIT
	if _phase == "departed":
		await _verify_gone(session)
		return
	await _check_departure(session)


func _check_departure(session: WorldSession) -> void:
	var tug := _outbound(session.sim)
	if tug == null or not DeliveryProbe.visible_pair(tug.ferry):
		_fail_review("The visible sold ferry and tug are required")
		return
	var result := await _follow_departure(session.sim, tug)
	_report.continuation = result
	_report.sale_signals = _sold_keys
	var expected_signals := [_report.purchase.new_hull] if _phase == "record" else []
	if result.is_empty() or _sold_keys != expected_signals:
		_fail_review("Missing departure, or the sale fired an unexpected number of times")
		return
	if _phase == "resume":
		if result != _control.continuation:
			_fail_review("Departure timing, motion or ledger changed")
			return
		var menu := await _open_save_menu(session)
		if menu == null:
			return
		_report.departed_checkpoint = _sale_state(session.sim)
		if not _activate_save(session, menu):
			return
	_pass()


func _prepare_sale_run() -> bool:
	_prefix = "user://reopen-%s-%s" % [_run_id, _map]
	SaveGame._path = _prefix + "-slot.json"
	_report = {
		"run": _run_id,
		"map": _map,
		"phase": _phase,
		"pid": OS.get_process_id(),
		"status": "starting"
	}
	_write_report()
	if _phase == "record" and FileAccess.file_exists(SaveGame._path):
		_fail_review("Choose a fresh isolated run identifier")
		return false
	if _phase != "record":
		var previous := "record" if _phase == "resume" else "resume"
		_control = _read_report(_prefix + "-" + previous + ".json")
		if (
			_control.get("status") != "passed"
			or OS.get_process_id() in [_control.get("pid"), _control.get("record_pid")]
		):
			_fail_review("A passing control from distinct earlier processes is required")
			return false
		_report.purchase = _control.purchase
		_report.sale = _control.sale
		_report.record_pid = _control.get("record_pid", _control.pid)
	return true


func _watch_sale_world(node: Node) -> void:
	if node is Simulation:
		node.ferry_removed.connect(func(boat: Ferry): _sold_keys.append(boat.fleet_key))
	if _phase != "record" and node is WorldSession:
		node.world_ready.connect(_freeze_sale_world.bind(node), CONNECT_ONE_SHOT)


func _freeze_sale_world(session: WorldSession) -> void:
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	session.hud.set_speed(2)
	_restored = _sale_state(session.sim)


func _buy_sell_and_save(session: WorldSession) -> bool:
	var sim := session.sim
	var bought := await _purchase_from_catalogue(session)
	if bought == null:
		_fail_review("The ordinary opening company could not buy the second ferry for $30,000")
		return false
	session.hud.clear_selection()
	session.hud.set_speed(3)
	var deadline := Time.get_ticks_msec() + 240000
	while not bought.can_sell() and Time.get_ticks_msec() < deadline:
		await process_frame
	session.hud.set_speed(0)
	session.hud.select_ferry(bought)
	var panel: FerryPanel = session.hud._ferry_panel
	var tab: Button = panel._tab_buttons[FerryPanel.TAB_NAMES.find("Operations")]
	if not bought.can_sell() or not await _press_panel_button(panel, tab):
		_fail_review("The delivered boat could not be sold through Operations")
		return false
	var before := sim.ledger.cash
	var sales: float = sim.ledger.today.sales
	if (
		panel._sell_button.text != "Sell for $24,000"
		or not await _press_panel_button(panel, panel._sell_button)
	):
		_fail_review("Expected a $24,000 sale in the selected boat's Operations panel")
		return false
	_report.sale = {
		"price": RESALE,
		"sales_before": sales,
		"sales_after": sim.ledger.today.sales,
		"cash_before": before,
		"cash_after": sim.ledger.cash
	}
	if (
		sim.ledger.cash - before != RESALE
		or sim.ledger.today.sales - sales != RESALE
		or sim.ferries.has(bought)
	):
		_fail_review("Sale proceeds or fleet membership changed incorrectly")
		return false
	return await _save_departing(session)


func _save_departing(session: WorldSession) -> bool:
	var sim := session.sim
	session.hud.clear_selection()
	session.hud.set_speed(2)
	var tug := _outbound(sim)
	var deadline := Time.get_ticks_msec() + 240000
	while is_instance_valid(tug) and Time.get_ticks_msec() < deadline:
		if (
			tug.phase == DeliveryTow.Phase.PULLING
			and tug.s > tug._out.length * 0.3
			and tug.speed > 0
		):
			var menu := await _open_save_menu(session)
			if menu == null:
				return false
			_report.checkpoint = _sale_state(sim)
			return _activate_save(session, menu)
		await process_frame
	_fail_review("The sold ferry did not reach a moving outbound checkpoint")
	return false


func _outbound(sim: Simulation) -> DeliveryTow:
	for tow in sim.tows:
		if tow.outbound:
			return tow
	return null


func _sale_state(sim: Simulation) -> Dictionary:
	var fleet := []
	for boat in sim.ferries:
		fleet.append(_hull_state(boat))
	var data := {
		"fleet": fleet,
		"minute": sim.abs_minutes(),
		"ledger": sim.ledger.snapshot(sim.map.routes),
		"outbound": {}
	}
	var tow := _outbound(sim)
	if tow != null:
		var path := []
		for point in tow._out.pts:
			path.append([point.x, point.y])
		data.outbound = {
			"hull": _hull_state(tow.ferry),
			"tug": tow.vessel_name,
			"variant": tow.model_variant,
			"phase": tow.phase,
			"slip": tow.ferry.tie_up,
			"path": path,
			"consorts": tow.consort == tow.ferry and tow.ferry.consort == tow,
			"motion": _delivery._motion(tow)
		}
	return _json_form(data)


func _note_exit(actor: String, sim: Simulation) -> void:
	_exits[actor] = {
		"count": _exits.get(actor, {}).get("count", 0) + 1, "minute": sim.abs_minutes()
	}


func _gone(sim: Simulation) -> bool:
	for child in sim.get_children():
		if child is Ferry and child.fleet_key == _report.purchase.new_hull:
			return false
		if child is DeliveryTow and child.outbound:
			return false
	return (
		_outbound(sim) == null
		and sim.ferries.size() == 1
		and sim.ferries[0].fleet_key == _report.purchase.original_hull
		and sim.ledger.today.sales == RESALE
		and sim.ledger.today.purchases == 30000
	)


func _follow_departure(sim: Simulation, tow: DeliveryTow) -> Dictionary:
	var distance := tow.s
	tow.tree_exited.connect(_note_exit.bind("tug", sim))
	tow.ferry.tree_exited.connect(_note_exit.bind("hull", sim))
	var motion := {}
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if motion.is_empty() and is_instance_valid(tow) and tow.s >= distance + 10:
			motion = _delivery._motion(tow)
		if (
			_exits.size() != 2
			or sim.abs_minutes() < maxf(_exits.hull.minute, _exits.tug.minute) + 10
		):
			continue
		if motion.is_empty() or not _gone(sim) or _exits.hull.count != 1 or _exits.tug.count != 1:
			return {}
		return _json_form(
			{
				"next_motion": motion,
				"tree_exits": _exits,
				"minute": sim.abs_minutes(),
				"ledger": sim.ledger.snapshot(sim.map.routes)
			}
		)
	return {}


func _verify_gone(session: WorldSession) -> void:
	var sim := session.sim
	var start := sim.abs_minutes()
	var deadline := Time.get_ticks_msec() + 120000
	while sim.abs_minutes() < start + 10 and Time.get_ticks_msec() < deadline:
		if not _gone(sim) or not _sold_keys.is_empty():
			_fail_review("The departed sale, hull or tug returned")
			return
		await process_frame
	_report.continuation = {
		"start": start,
		"end": sim.abs_minutes(),
		"sales": sim.ledger.today.sales,
		"purchases": sim.ledger.today.purchases,
		"sale_signals": _sold_keys
	}
	if sim.abs_minutes() < start + 10 or not _gone(sim):
		_fail_review("Post-departure observation did not finish")
		return
	_pass()
