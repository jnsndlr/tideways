extends "res://tests/support/ui_test_driver.gd"
## Two separate process launches. The recording follows the uninterrupted game
## past Save Game. The second launch reopens that same slot through Continue.
## Set TIDEWAYS_REOPEN_MAP to sandbox, opening or mission, TIDEWAYS_REOPEN_RUN
## to a fresh identifier, and TIDEWAYS_REOPEN_PHASE to record. On desktop, use
## godot --headless --fixed-fps 30 --script res://tests/device/company_reopen_probe.gd.
## For a physical iPad, include the probe and UI driver in a review-only export
## and set its main loop to a registered subclass of this probe. Once the
## record report passes, terminate the app and relaunch with phase resume.
## The reports and isolated slot share the user://reopen-<run>-<map> prefix.
## Production export presets exclude tests.

var _phase := OS.get_environment("TIDEWAYS_REOPEN_PHASE")
var _run_id := OS.get_environment("TIDEWAYS_REOPEN_RUN")
var _map := OS.get_environment("TIDEWAYS_REOPEN_MAP")
var _prefix: String
var _control := {}
var _report := {}
var _restored := {}


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	if (
		not _run_id.is_valid_identifier()
		or _phase not in ["record", "resume"]
		or _map not in ["opening", "mission", "sandbox"]
	):
		push_error("Set TIDEWAYS_REOPEN_PHASE, TIDEWAYS_REOPEN_RUN and TIDEWAYS_REOPEN_MAP")
		quit(2)
		return
	_prefix = "user://reopen-%s-%s" % [_run_id, _map]
	SaveGame._path = _prefix + "-slot.json"
	_report = {
		"run": _run_id,
		"map": _map,
		"phase": _phase,
		"pid": OS.get_process_id(),
		"status": "starting"
	}
	if _phase == "record" and FileAccess.file_exists(SaveGame._path):
		_fail_review("The review run already has a slot. Choose a new run identifier.")
		return
	_write_report()
	if _phase == "resume":
		_control = _read_report(_prefix + "-record.json")
		if _control.get("status") != "passed" or _control.get("pid") == OS.get_process_id():
			_fail_review("Continue needs a completed control from a different process")
			return
		node_added.connect(_watch_session)
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	var path := Scenes.SANDBOX if _map == "sandbox" else Scenes.MAIN_MAP
	if _phase == "resume":
		if not await enter_game("Continue", path):
			_fail_review("Continue did not open the saved world")
			return
	else:
		RegionEntryState.sandbox_seed = 123
		var button: String = {
			"sandbox": "Sandbox", "mission": "Mission sandbox", "opening": "New company"
		}[_map]
		if not await enter_game(button, path):
			_fail_review("Could not launch %s from the menu" % _map)
			return
	var session := current_scene as WorldSession
	if _phase == "record":
		await _record(session)
	elif _restored.is_empty():
		_fail_review("Continue never exposed the rebuilt company before its first simulation frame")
	else:
		await _resume(session)


func _watch_session(node: Node) -> void:
	if node is WorldSession:
		node.world_ready.connect(_at_reopen.bind(node), CONNECT_ONE_SHOT)


func _at_reopen(session: WorldSession) -> void:
	# Freeze all service immediately at the ready signal, before the loading
	# screen fades. SceneTree pause leaves the loading screen timer suspended;
	# freezing just the simulation keeps the menu/loading path observable.
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	var ferry := _find_ferry(session.sim, _control.checkpoint.hull)
	if ferry:
		_restored = _checkpoint(ferry)


func _record(session: WorldSession) -> void:
	session.hud.set_speed(2)
	var ferry: Ferry
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline and ferry == null:
		await process_frame
		for boat in session.sim.ferries:
			if (
				boat.state == Ferry.State.SAILING
				and not boat.aboard.is_empty()
				and boat.traveled > boat.run_length() * 0.38
				and boat.traveled < boat.run_length() * 0.62
			):
				ferry = boat
				break
	if ferry == null:
		_fail_review("No paid occupied ferry reached the middle of its crossing")
		return
	if not await press("MENU"):
		_fail_review("Cannot reach the HUD menu")
		return
	var menu := session.hud._game_menu
	var item := menu.get_item_index(0)
	if not menu.visible or item < 0 or menu.is_item_disabled(item):
		_fail_review("Save game is unavailable in this session")
		return
	var before := _checkpoint(ferry)
	# Native menu windows consume physical input outside the scene viewport.
	# Activate the visible Save item through the same signal as a native selection.
	menu.id_pressed.emit(menu.get_item_id(item))
	menu.hide()
	var saved := SaveGame.read()
	if not saved.get("snapshot") is Dictionary or session.hud._toast_title.text != "GAME SAVED":
		_fail_review(
			"The HUD did not persist a company snapshot: %s" % session.hud._toast_title.text
		)
		return
	_report.checkpoint = before
	_report.status = "saved"
	_write_report()
	var observed := await _follow_receipts(session.sim, before.ledger)
	_finish(session, observed)


func _resume(session: WorldSession) -> void:
	_report.checkpoint = _restored
	var expected: Dictionary = _control.checkpoint
	if _restored != expected:
		var different := []
		for key in expected:
			if _restored.get(key) != expected[key]:
				different.append(key)
		_fail_review("Company changed before its first resumed frame: %s" % str(different))
		return
	session.hud.set_speed(2)
	session.sim.process_mode = Node.PROCESS_MODE_INHERIT
	var observed := await _follow_receipts(session.sim, _restored.ledger)
	_finish(session, observed)


func _checkpoint(ferry: Ferry) -> Dictionary:
	var sim := ferry.sim
	var vehicles := []
	for car in ferry.aboard:
		var row := VehiclePartsSnapshot.capture(car)
		row.destination = "" if car.dest < 0 else sim.map.towns[car.dest].key
		row.paid = car.fare_paid
		row.cells = []
		for cell in ferry.deck.occupants.size():
			if ferry.deck.occupants[cell] == car.get_instance_id():
				row.cells.append(cell)
		vehicles.append(row)
	return _json_form(
		{
			"hull": ferry.fleet_key,
			"seed": str(sim.map.map_seed),
			"origin": ferry.here().town.key,
			"destination": ferry.destination().town.key,
			"state": ferry.state,
			"distance": ferry.traveled,
			"position": SnapshotVector3.encode(ferry.position),
			"heading": ferry.rotation.y,
			"vehicles": vehicles,
			"passengers": ferry.passengers_aboard,
			"day": sim.day,
			"minutes": sim.minutes,
			"ledger": sim.ledger.snapshot(sim.map.routes)
		}
	)


func _find_ferry(sim: Simulation, key: String) -> Ferry:
	for ferry in sim.ferries:
		if ferry.fleet_key == key:
			return ferry
	return null


func _follow_receipts(sim: Simulation, initial: Dictionary) -> Dictionary:
	var transactions := {}
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		var ledger := sim.ledger
		var deltas := {}
		for key in ledger.today:
			var cents := roundi((ledger.today[key] - initial.today[key]) * 100)
			if cents != 0:
				deltas[key] = cents
		if not transactions.has("first") and not deltas.is_empty():
			transactions.first = {"cents": deltas, "day": sim.day}
		if ledger.revenue_total != initial.revenue_total:
			transactions.next_fare = {
				"cents": roundi((ledger.revenue_total - initial.revenue_total) * 100),
				"cars": ledger.cars_total - int(initial.cars_total),
				"walk_ons": ledger.passengers_total - int(initial.passengers_total),
			}
			return transactions
	return {}


func _finish(session: WorldSession, observed: Dictionary) -> void:
	session.hud.set_speed(0)
	_report.transactions = _json_form(observed)
	if not observed.has("first") or not observed.has("next_fare"):
		_fail_review("No subsequent posting and fare were observed")
		return
	if _phase == "resume" and _report.transactions != _control.transactions:
		_fail_review("The next posting or next fare differed from the uninterrupted company")
		return
	_report.status = "passed"
	_write_report()
	if not OS.has_feature("mobile"):
		quit(0)


func _fail_review(message: String) -> void:
	_report.status = "failed"
	_report.error = message
	_write_report()
	push_error(message)
	if not OS.has_feature("mobile"):
		quit(1)


func _json_form(value: Dictionary) -> Dictionary:
	return JSON.parse_string(JSON.stringify(value, "", true, true))


func _read_report(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return data if data is Dictionary else {}


func _write_report() -> void:
	var path := _prefix + "-" + _phase + ".json"
	var err := SavedText.replace(path, JSON.stringify(_report, "", true, true))
	if err != OK:
		push_error("Cannot write %s (error %s)" % [path, err])
	print("REOPEN PROBE %s %s" % [_phase, _report.status])
