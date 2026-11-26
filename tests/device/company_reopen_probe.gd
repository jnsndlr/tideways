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
## On the recording launch, set TIDEWAYS_REOPEN_MIN_TRIPS=3 to wait for three
## new fleet arrivals, or TIDEWAYS_REOPEN_EDIT_SERVICE=1 on the authored opening
## to edit a departure and pace through the ferry's Schedule tab before saving.
## Set TIDEWAYS_REOPEN_BUY_FERRY=1 on an opening recording to confirm a $30,000
## size 1 delivery using the normal company balance. Apply her schedule in the
## player inspector, then save with two occupied boats. To repeat the check after
## the departing tug has left the map, also set TIDEWAYS_REOPEN_WAIT_TUG=1.
## For an unassigned hull under tow, use TIDEWAYS_REOPEN_INBOUND_TOW=1 instead.
## This case compares the inbound path, two moving poses, berth reservation and
## single arrival plus ten game minutes of docked service. After resume saves the
## delivered hull in the same slot, launch phase delivered to verify its berth
## and ledger through another interval. Production exports exclude tests.

const DeliveryProbe := preload("res://tests/device/inbound_delivery_probe.gd")

var _phase := OS.get_environment("TIDEWAYS_REOPEN_PHASE")
var _run_id := OS.get_environment("TIDEWAYS_REOPEN_RUN")
var _map := OS.get_environment("TIDEWAYS_REOPEN_MAP")
var _min_trips := OS.get_environment("TIDEWAYS_REOPEN_MIN_TRIPS").to_int()
var _edit_service := OS.get_environment("TIDEWAYS_REOPEN_EDIT_SERVICE") == "1"
var _buy_ferry := OS.get_environment("TIDEWAYS_REOPEN_BUY_FERRY") == "1"
var _wait_tug := OS.get_environment("TIDEWAYS_REOPEN_WAIT_TUG") == "1"
var _inbound := OS.get_environment("TIDEWAYS_REOPEN_INBOUND_TOW") == "1"
var _delivery := DeliveryProbe.new()
var _prefix: String
var _control := {}
var _report := {}
var _restored := {}


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	if (
		not _run_id.is_valid_identifier()
		or _phase not in ["record", "resume", "delivered"]
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
	if _phase != "record":
		_control = _read_report(
			_prefix + ("-resume.json" if _phase == "delivered" else "-record.json")
		)
		if _control.get("status") != "passed" or _control.get("pid") == OS.get_process_id():
			_fail_review("Continue needs a completed control from a different process")
			return
		_inbound = _control.checkpoint.has("inbound_tow")
		if (
			_phase == "delivered"
			and (
				not _control.has("delivered_checkpoint")
				or not _inbound
				or _control.get("record_pid") == OS.get_process_id()
			)
		):
			_fail_review(
				"The third launch needs the delivered save from two distinct earlier processes"
			)
			return
	if _phase != "record" or _inbound:
		node_added.connect(_watch_session)
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	var path := Scenes.SANDBOX if _map == "sandbox" else Scenes.MAIN_MAP
	if _phase != "record":
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
	elif _phase == "delivered":
		await _verify_docked(session)
	else:
		await _resume(session)


func _watch_session(node: Node) -> void:
	if _inbound and node is Simulation:
		node.ferry_delivered.connect(_delivery.delivered)
	if _phase != "record" and node is WorldSession:
		node.world_ready.connect(_at_reopen.bind(node), CONNECT_ONE_SHOT)


func _at_reopen(session: WorldSession) -> void:
	# Freeze all service immediately at the ready signal, before the loading
	# screen fades. SceneTree pause leaves the loading screen timer suspended;
	# freezing just the simulation keeps the menu/loading path observable.
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	session.hud.set_speed(2)
	var ferry := _find_ferry(session.sim, _control.checkpoint.hull)
	if ferry:
		_restored = _checkpoint(ferry)


func _record(session: WorldSession) -> void:
	session.hud.set_speed(2)
	if _buy_ferry or _inbound:
		if _map != "opening" or not await _buy_ferry_from_catalogue(session):
			_fail_review(
				"Could not purchase the second boat with the opening balance or prepare its service"
			)
			return
	var started := _fleet_trips(session.sim)
	var ferry: Ferry
	var deadline := Time.get_ticks_msec() + 240000
	while Time.get_ticks_msec() < deadline and ferry == null:
		await process_frame
		if _inbound:
			var purchased := session.sim.ferries.back() as Ferry
			if _delivery.mid_tow(purchased):
				ferry = purchased
			continue
		if _buy_ferry and not session.sim.ferries.all(_working_with_cars):
			continue
		if _wait_tug and not session.sim.tows.is_empty():
			continue
		if _fleet_trips(session.sim) - started < _min_trips:
			continue
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
	_report.fleet_trips_at_start = started
	_report.new_fleet_trips = _fleet_trips(session.sim) - started
	if _edit_service:
		if not await _edit_opening_service(session, ferry):
			_fail_review("Could not apply the edited departure and pace through the Schedule tab")
			return
	await _record_checkpoint(session, ferry)


func _record_checkpoint(session: WorldSession, ferry: Ferry) -> void:
	var menu := await _open_save_menu(session)
	if menu == null:
		return
	if _inbound and not _visible_delivery(ferry):
		return
	if _buy_ferry or _inbound:
		_report.delivery_tug_phases = session.sim.tows.map(
			func(tug: DeliveryTow): return DeliveryTow.Phase.keys()[tug.phase]
		)
	var before := _checkpoint(ferry)
	_report.checkpoint = before
	if not _activate_save(session, menu):
		return
	_report.status = "saved"
	_write_report()
	var observed := await _follow_receipts(session.sim, before.ledger)
	_finish(session, observed)


func _working_with_cars(boat: Ferry) -> bool:
	return boat.berth == Ferry.Berth.WORKING and not boat.aboard.is_empty()


func _buy_ferry_from_catalogue(session: WorldSession) -> bool:
	var bought := await _purchase_from_catalogue(session)
	if bought == null:
		return false
	return _start_inbound(session, bought) if _inbound else await _assign_purchased(session, bought)


func _purchase_from_catalogue(session: WorldSession) -> Ferry:
	var sim := session.sim
	session.hud.set_speed(0)
	if sim.ferries.size() != 1 or sim.ledger.cash >= CompanyLedger.UNLIMITED_CASH:
		return null
	for caption in ["FLEET", "Buy a boat", "Size 1"]:
		if not await press(caption, caption == "Size 1"):
			return null
	const PRICE := 30000
	var before := sim.ledger.cash
	var purchases_before: float = sim.ledger.today.purchases
	if not await press("Buy for $30,000") or sim.ferries.size() != 2:
		return null
	var bought := sim.ferries.back() as Ferry
	_report.purchase = {
		"price": PRICE,
		"cash_before": before,
		"cash_after": sim.ledger.cash,
		"purchases_before": purchases_before,
		"purchases_after": sim.ledger.today.purchases,
		"new_hull": bought.fleet_key,
		"original_hull": sim.ferries[0].fleet_key,
	}
	if before - sim.ledger.cash != PRICE or sim.ledger.today.purchases - purchases_before != PRICE:
		return null
	return bought


func _start_inbound(session: WorldSession, bought: Ferry) -> bool:
	if bought.tow != null and not bought.assigned:
		_delivery.start(bought.tow)
		session.hud.clear_selection()
		session.hud.set_speed(2)
		return true
	return false


func _assign_purchased(session: WorldSession, bought: Ferry) -> bool:
	var panel: FerryPanel = session.hud._ferry_panel
	var tab := panel._tab_buttons[FerryPanel.TAB_NAMES.find("Schedule")]
	if (
		not await _press_panel_button(panel, tab)
		or not await _press_panel_button(panel, panel._schedule_editor._apply)
	):
		return false
	session.hud.clear_selection()
	session.hud.set_speed(2)
	var assigned := bought.assigned and bought.fleet_key != session.sim.ferries[0].fleet_key
	if assigned:
		_report.status = "assigned"
		_write_report()
	return assigned


func _fleet_trips(sim: Simulation) -> int:
	var total := 0
	for ferry in sim.ferries:
		total += ferry.trips
	return total


func _service(ferry: Ferry) -> Dictionary:
	return {
		"departures": ferry.timetable.duplicate(),
		"pace": ferry.pace,
		"captain": ferry.captain.id,
		"next_captain": ferry.next_captain.id,
	}


func _edit_opening_service(session: WorldSession, ferry: Ferry) -> bool:
	if _map != "opening" or not ferry.timetable.is_empty():
		return false
	var prior := _service(ferry)
	session.hud.set_speed(0)
	session.hud.select_ferry(ferry)
	var panel: FerryPanel = session.hud._ferry_panel
	var tab := panel._tab_buttons[FerryPanel.TAB_NAMES.find("Schedule")]
	if not await _press_panel_button(panel, tab):
		return false
	var editor := panel._schedule_editor
	if not await _press_panel_button(panel, editor._mode_timed):
		return false
	var step := editor._sailings.find_child("Step+15", true, false) as Button
	if not await _press_panel_button(panel, step) or editor._times != [375]:
		return false
	for button in [editor._pace_buttons[FerryPace.ECONOMY], editor._apply]:
		if not await _press_panel_button(panel, button):
			return false
	session.hud.clear_selection()
	session.hud.set_speed(2)
	_report.service_before_edit = prior
	return ferry.timetable == [375] and ferry.pace == FerryPace.ECONOMY


func _press_panel_button(panel: FerryPanel, button: Button) -> bool:
	if button == null or button.disabled:
		return false
	await process_frame
	await process_frame
	panel._scroll.ensure_control_visible(button)
	await process_frame
	await process_frame
	if not button.is_visible_in_tree():
		return false
	var clicked := click_control(button, button.size * 0.5, button.text)
	await process_frame
	return clicked


func _resume(session: WorldSession) -> void:
	_report.checkpoint = _restored
	var expected: Dictionary = _control.checkpoint
	if _inbound and not _visible_delivery(_find_ferry(session.sim, expected.hull)):
		return
	if _restored != expected:
		var different := []
		for key in expected:
			if _restored.get(key) != expected[key]:
				different.append(key)
		_fail_review("Company changed before its first resumed frame: %s" % str(different))
		return
	# The first resumed frame must have the same 8x delta as the control.
	await process_frame
	session.sim.process_mode = Node.PROCESS_MODE_INHERIT
	var observed := await _follow_receipts(session.sim, _restored.ledger)
	_finish(session, observed)


func _checkpoint(ferry: Ferry) -> Dictionary:
	var sim := ferry.sim
	var record := _hull_state(ferry)
	(
		record
		. merge(
			{
				"seed": str(sim.map.map_seed),
				"fleet_trips": _fleet_trips(sim),
				"day": sim.day,
				"minutes": sim.minutes,
				"ledger": sim.ledger.snapshot(sim.map.routes),
			}
		)
	)
	if _inbound:
		if ferry.tow != null:
			record.inbound_tow = _delivery.capture(ferry)
		else:
			record.docked = _delivery.docked(ferry)
	if _buy_ferry or _inbound or _control.has("purchase"):
		var hulls := {}
		for boat in sim.ferries:
			hulls[boat.fleet_key] = _hull_state(boat)
		record.fleet = hulls
	return _json_form(record)


func _hull_state(ferry: Ferry) -> Dictionary:
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
	return {
		"hull": ferry.fleet_key,
		"service": _service(ferry),
		"name": ferry.ferry_name,
		"purchased": ferry.purchased,
		"assigned": ferry.assigned,
		"class": ferry.fc.size,
		"trips": ferry.trips,
		"route": ferry.route.key,
		"stops": ferry.stops.map(func(id: int): return sim.map.towns[id].key),
		"origin": ferry.here().town.key,
		"destination": ferry.destination().town.key,
		"state": ferry.state,
		"distance": ferry.traveled,
		"position": SnapshotVector3.encode(ferry.position),
		"heading": ferry.rotation.y,
		"vehicles": vehicles,
		"passengers": ferry.passengers_aboard,
		"paid_manifest": FerryVehicleManifest.capture(ferry),
	}


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
		if not transactions.has("next_fare") and ledger.revenue_total != initial.revenue_total:
			transactions.next_fare = {
				"cents": roundi((ledger.revenue_total - initial.revenue_total) * 100),
				"cars": ledger.cars_total - int(initial.cars_total),
				"walk_ons": ledger.passengers_total - int(initial.passengers_total),
			}
		if _inbound:
			var key: String = (
				(_report.purchase if _phase == "record" else _control.purchase).new_hull
			)
			_delivery.observe(_find_ferry(sim, key))
			if _delivery.after_arrival.is_empty():
				continue
		if transactions.has("next_fare"):
			return transactions
	return {}


func _finish(session: WorldSession, observed: Dictionary) -> void:
	session.hud.set_speed(0)
	_report.transactions = _json_form(observed)
	if _inbound:
		_report.delivery = _json_form(_delivery.outcome())
		var key: String = (_report.purchase if _phase == "record" else _control.purchase).new_hull
		if not _delivery.completed(_find_ferry(session.sim, key)):
			_fail_review(
				"Delivery must move forward, arrive exactly once and retain its $30,000 charge"
			)
			return
		if _phase == "resume" and _report.delivery != _control.delivery:
			_fail_review(
				"The resumed tow movement, arrival or docked interval differed from control"
			)
			return
	if not observed.has("first") or not observed.has("next_fare"):
		_fail_review("No subsequent posting and fare were observed")
		return
	if _phase == "resume" and _report.transactions != _control.transactions:
		_fail_review("The next posting or next fare differed from the uninterrupted company")
		return
	if _phase == "resume" and _inbound:
		if not await _save_docked(session):
			return
	_pass()


func _visible_delivery(boat: Ferry) -> bool:
	_report.visible_delivery_pair = boat != null and DeliveryProbe.visible_pair(boat)
	if not _report.visible_delivery_pair:
		_fail_review(
			"The purchased ferry and attached tug must both have their fitted visible hull meshes"
		)
	return _report.visible_delivery_pair


func _save_docked(session: WorldSession) -> bool:
	var boat := _find_ferry(session.sim, _control.purchase.new_hull)
	var menu := await _open_save_menu(session)
	if menu == null:
		return false
	_report.delivered_checkpoint = _checkpoint(boat)
	_report.record_pid = _control.pid
	if not _activate_save(session, menu):
		return false
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	if not await _docked_interval(session, boat):
		return false
	return true


func _open_save_menu(session: WorldSession) -> PopupMenu:
	if not await press("MENU"):
		_fail_review("Cannot reach the HUD menu")
		return null
	var menu := session.hud._game_menu
	var item := menu.get_item_index(0)
	if not menu.visible or item < 0 or menu.is_item_disabled(item):
		_fail_review("Save game is unavailable in this session")
		return null
	return menu


func _activate_save(session: WorldSession, menu: PopupMenu) -> bool:
	# Native menu windows consume physical input outside the scene viewport.
	# Activate the visible Save item through the same signal as a native selection.
	menu.id_pressed.emit(menu.get_item_id(menu.get_item_index(0)))
	menu.hide()
	var saved := SaveGame.read()
	if not saved.get("snapshot") is Dictionary or session.hud._toast_title.text != "GAME SAVED":
		_fail_review(
			"The HUD did not persist a company snapshot: %s" % session.hud._toast_title.text
		)
		return false
	return true


func _verify_docked(session: WorldSession) -> void:
	_report.checkpoint = _restored
	if _restored != _control.delivered_checkpoint or not _delivery.deliveries.is_empty():
		_fail_review(
			"Cold reopen of the delivered hull changed its checkpoint or emitted a delivery signal"
		)
		return
	var boat := _find_ferry(session.sim, _restored.hull)
	if not await _docked_interval(session, boat):
		return
	if _report.docked_interval != _control.docked_interval:
		_fail_review(
			"The delivered company's next ten minutes differed from the uninterrupted control"
		)
		return
	_pass()


func _docked_interval(session: WorldSession, boat: Ferry) -> bool:
	var count := _delivery.deliveries.size()
	var until := session.sim.abs_minutes() + 10
	var deadline := Time.get_ticks_msec() + 90000
	session.hud.set_speed(2)
	await process_frame
	session.sim.process_mode = Node.PROCESS_MODE_INHERIT
	while session.sim.abs_minutes() < until and Time.get_ticks_msec() < deadline:
		await process_frame
	session.hud.set_speed(0)
	_report.docked_interval = _json_form(_delivery.docked(boat))
	if (
		session.sim.abs_minutes() < until
		or _delivery.deliveries.size() != count
		or boat.tow != null
		or not _report.docked_interval.occupied_by_hull
		or _report.docked_interval.purchases != 30000
	):
		_fail_review(
			"Docked observation lost the berth, repeated a handoff or changed the purchase debit"
		)
		return false
	return true


func _pass() -> void:
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
