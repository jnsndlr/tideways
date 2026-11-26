extends "res://tests/device/company_reopen_probe.gd"
## Buy, assign and lay up an occupied opening ferry using its Operations control.
## Pass TIDEWAYS_REOPEN_LAY_UP=1 and run record, resume, tied in separate processes.

var _arrivals := []


func _run() -> void:
	if OS.get_environment("TIDEWAYS_REOPEN_LAY_UP") != "1":
		await super._run()
		return
	if not _prepare_run():
		return
	if _phase != "record":
		node_added.connect(_watch_lay_up_world)
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await enter_game("New company" if _phase == "record" else "Continue", Scenes.MAIN_MAP):
		_fail_review("Could not open the named company")
		return
	var session := current_scene as WorldSession
	if _phase == "record":
		if await _record_shift(session):
			await _finish_shift_probe(session)
	else:
		await _cold_shift(session)


func _prepare_run() -> bool:
	if (
		_map != "opening"
		or not _run_id.is_valid_identifier()
		or _phase not in ["record", "resume", "tied"]
	):
		quit(2)
		return false
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
	if _phase == "record":
		if FileAccess.file_exists(SaveGame._path):
			_fail_review("Choose an unused run identifier")
			return false
	else:
		_control = _read_report(
			_prefix + ("-record.json" if _phase == "resume" else "-resume.json")
		)
		if (
			_control.get("status") != "passed"
			or OS.get_process_id() in [_control.get("pid"), _control.get("record_pid")]
		):
			_fail_review("A passing prior launch in a distinct process is required")
			return false
		_report.record_pid = _control.get("record_pid", _control.pid)
		_report.purchase = _control.purchase
		_report.loaded = _control.loaded
	return true


func _watch_lay_up_world(node: Node) -> void:
	if node is WorldSession:
		node.world_ready.connect(_freeze_shift.bind(node), CONNECT_ONE_SHOT)


func _freeze_shift(session: WorldSession) -> void:
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	session.hud.set_speed(2)
	var ferry := _find_ferry(session.sim, _report.purchase.new_hull)
	if ferry:
		_restored = _shift_state(ferry)


func _cold_shift(session: WorldSession) -> void:
	_report.checkpoint = _restored
	var expected: Dictionary = (
		_control.checkpoint if _phase == "resume" else _control.tied_checkpoint
	)
	if expected != _restored:
		_fail_review("The restored ferry, slip, service or ledger changed at the checkpoint")
		return
	await process_frame
	session.sim.process_mode = Node.PROCESS_MODE_INHERIT
	if _phase == "resume":
		await _finish_shift_probe(session)
	else:
		await _return_to_service(session)


func _record_shift(session: WorldSession) -> bool:
	var ferry := await _purchase_from_catalogue(session)
	if (
		ferry == null
		or ferry.ferry_name != "Cedar Star"
		or not await _assign_purchased(session, ferry)
	):
		_fail_review("Could not buy and schedule Cedar Star")
		return false
	session.hud.set_speed(2)
	var deadline := Time.get_ticks_msec() + 300000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if (
			ferry.state != Ferry.State.SAILING
			or ferry.berth != Ferry.Berth.WORKING
			or ferry.aboard.is_empty()
		):
			continue
		if not ferry.aboard.all(func(car: Vehicle): return car.fare_paid > 0):
			continue
		var dest := ferry.destination()
		var slip := ferry.best_slip(dest.town.id)
		if slip < 0 or slip == ferry.slip_at(dest):
			continue
		_report.loaded = _hull_state(ferry)
		_report.loaded.target_slip = slip
		_report.loaded.service_stops = _scheduled_stops(ferry)
		if not await _service_click(session, ferry, "Lay up now"):
			_fail_review("Could not request lay-up from the occupied ferry's Operations panel")
			return false
		_report.status = "lay_up_requested"
		_write_report()
		return await _save_mid_shift(session, ferry)
	_fail_review("No purchased sailing with paid vehicles and an available tie-up reached the test")
	return false


func _service_click(session: WorldSession, ferry: Ferry, caption: String) -> bool:
	session.hud.set_speed(0)
	session.hud.select_ferry(ferry)
	var panel: FerryPanel = session.hud._ferry_panel
	var tab: Button = panel._tab_buttons[FerryPanel.TAB_NAMES.find("Operations")]
	if (
		not await _press_panel_button(panel, tab)
		or not panel._service_button.text.begins_with(caption)
	):
		return false
	var clicked := await _press_panel_button(panel, panel._service_button)
	session.hud.clear_selection()
	session.hud.set_speed(2)
	return clicked


func _save_mid_shift(session: WorldSession, ferry: Ferry) -> bool:
	var deadline := Time.get_ticks_msec() + 300000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if (
			ferry.berth != Ferry.Berth.TO_TIE_UP
			or not ferry.shifting()
			or ferry._shift_s < ferry._shift.length * 0.35
		):
			continue
		var menu := await _open_save_menu(session)
		if menu == null:
			return false
		if (
			not ferry.shifting()
			or not ferry.aboard.is_empty()
			or not ferry.passengers_aboard.is_empty()
			or ferry.here().town.key != _report.loaded.destination
			or ferry.tie_up != _report.loaded.target_slip
		):
			_fail_review("The ferry did not finish unloading before moving between slips")
			return false
		_report.checkpoint = _shift_state(ferry)
		return _activate_save(session, menu)
	_fail_review("Cedar Star never moved toward her lay-up berth")
	return false


func _scheduled_stops(ferry: Ferry) -> Array:
	return ferry.service_stops().map(func(id: int): return ferry.sim.map.towns[id].key)


func _shift_state(ferry: Ferry) -> Dictionary:
	var sim := ferry.sim
	var path := {}
	if ferry.shifting():
		path = {"distance": ferry._shift_s, "length": ferry._shift.length, "speed": ferry.speed}
	return _json_form(
		{
			"hull": _hull_state(ferry),
			"minute": sim.abs_minutes(),
			"berth": ferry.berth,
			"town": ferry.here().town.key,
			"slip": ferry.tie_up,
			"path": path,
			"manual": ferry.manual,
			"landed": ferry._manual_landed,
			"service_stops": _scheduled_stops(ferry),
			"service_times": ferry.service_times(),
			"occupies_berth": sim.occupant(ferry.here(), ferry.tie_up, null) == ferry,
			"forward": SnapshotVector3.encode(ferry.global_basis.z),
			"ledger": sim.ledger.snapshot(sim.map.routes)
		}
	)


func _arrival(ferry: Ferry) -> void:
	if ferry.berth == Ferry.Berth.TIED_UP:
		_arrivals.append(
			{"minute": ferry.sim.abs_minutes(), "hull": ferry.fleet_key, "slip": ferry.tie_up}
		)


func _finish_shift_probe(session: WorldSession) -> void:
	var ferry := _find_ferry(session.sim, _report.purchase.new_hull)
	if ferry == null or not ferry.shifting():
		_fail_review("The purchased ferry has no active shift")
		return
	ferry._lay_up.berth_changed.connect(_arrival.bind(ferry))
	var next_motion := {}
	var distance := ferry._shift_s
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if next_motion.is_empty() and ferry._shift_s >= distance + 3:
			next_motion = _shift_state(ferry)
		if (
			not _arrivals.is_empty()
			and session.sim.abs_minutes() >= float(_arrivals[0].minute) + 10
		):
			break
	_report.continuation = _json_form(
		{"next_motion": next_motion, "arrivals": _arrivals, "tied": _shift_state(ferry)}
	)
	if (
		_arrivals.size() != 1
		or next_motion.is_empty()
		or session.sim.abs_minutes() < float(_arrivals[0].minute) + 10
		or ferry.berth != Ferry.Berth.TIED_UP
		or not _report.continuation.tied.occupies_berth
	):
		_fail_review("The ferry must move and complete its lay-up once in the reserved slip")
		return
	if _phase == "resume":
		if _control.continuation != _report.continuation:
			_fail_review("The next motion, tie-up completion, or ledger differed from control")
			return
		var menu := await _open_save_menu(session)
		if menu == null:
			return
		_report.tied_checkpoint = _shift_state(ferry)
		if not _activate_save(session, menu):
			return
	_pass()


func _return_to_service(session: WorldSession) -> void:
	var ferry := _find_ferry(session.sim, _report.purchase.new_hull)
	if (
		ferry == null
		or ferry.berth != Ferry.Berth.TIED_UP
		or not await _service_click(session, ferry, "Return to service")
	):
		_fail_review("The restored tied ferry could not be returned to service through Operations")
		return
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if (
			ferry.in_service()
			and ferry.state == Ferry.State.SAILING
			and not ferry.aboard.is_empty()
			and ferry.aboard.all(func(car: Vehicle): return car.fare_paid > 0)
		):
			_report.returned = _shift_state(ferry)
			if (
				_scheduled_stops(ferry) != _report.loaded.service_stops
				or session.sim.ledger.today.purchases != 30000
			):
				_fail_review("The working service or purchase debit changed after return")
				return
			_pass()
			return
	_fail_review("The restored ferry did not carry vehicles on its next service")
