extends "res://tools/ui_test_driver.gd"
## Exercise Play, the first sailing's finances, and Port Rosario's first lane purchase.

func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1366, 1024)
	var passed := await play_opening()
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if passed:
		print("TEST PASSED")
	quit(0 if passed else 1)


func play_opening() -> bool:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await enter_game("Play", Scenes.MAIN_MAP):
		return false
	var sim: Simulation = current_scene.sim
	var hud: Hud = current_scene.hud
	if sim.ferries.size() != 1 or sim.ferries[0].ferry_name != "Hiyu":
		return fail("Expected Hiyu on the opening route")
	var boat := sim.ferries[0]
	var port := boat.here()
	if port.town.name != "Port Rosario" or port.capacity() != 14:
		return fail("Expected 14 holding spaces at Port Rosario before the first sailing")
	if not await press("Speed 3"):
		return false
	for frame in 1200:
		await process_frame
		if boat.trips > 0:
			break
	if boat.trips != 1 or not boat.here().town.key.begins_with("island-2/"):
		return fail("Hiyu did not complete her first sailing to Madrona")
	if not await press("Pause") or not await press("FINANCES"):
		return false
	var ledger := sim.ledger
	var panel := hud._finance_panel
	if not panel.is_visible_in_tree() or panel._cash.text != Hud.fmt_money(ledger.cash):
		return fail("Finances did not show the company's current cash")
	for line: String in ["fares", "fuel", "crew"]:
		var amount: float = ledger.today[line]
		var expected := Hud.fmt_money(amount)
		if line != "fares":
			expected = "-" + expected
		if amount <= 0.0 or panel._cells[[line, 0]].text != expected:
			return fail("Finances should show the posted first-sailing %s" % line)
	var net := CompanyLedger.net(ledger.today)
	var displayed_net := ("+" if net > 0.0 else "") + Hud.fmt_money(net)
	if panel._cells[["net", 0]].text != displayed_net:
		return fail("Finances did not show the net after operating costs")
	if not await press("FINANCES"):
		return false
	# Frame the port before clicking its map label, independent of the opening camera.
	hud.rig.focus_on(port.town.town_center, 390.0)
	hud.rig.snap()
	await process_frame
	var label: Control = hud._labels[port.town.id]
	if not click_control(label, label.size * 0.5, "Port Rosario") or hud.selected_town != port.town:
		return fail("Port Rosario's map label did not open its inspector")
	return await buy_lane(hud, port, ledger)


func buy_lane(hud: Hud, port: Terminal, ledger: CompanyLedger) -> bool:
	var cash_before := ledger.cash
	if not is_zero_approx(ledger.today["purchases"]):
		return fail("Opening company already recorded a purchase")
	if not await press("Holding lane (+7 spaces) · $150"):
		return false
	if absf(ledger.cash - (cash_before - 150.0)) > 0.0001 or ledger.today["purchases"] != 150.0:
		return fail("Buying one lane should debit exactly $150 from cash and purchases")
	if port.work_stage != Terminal.WorkStage.DRAINING or port.capacity() != 14:
		return fail("Construction should start before the extra spaces open")
	if not await press("Speed 3"):
		return false
	for frame in 1200:
		await process_frame
		if port.work_stage == Terminal.WorkStage.OPEN:
			break
	if port.work_stage != Terminal.WorkStage.OPEN or port.capacity() != 21:
		return fail("Construction did not open all 21 holding spaces")
	if ledger.today["purchases"] != 150.0:
		return fail("Finishing construction should not charge for the lane again")
	var expected_cash := CompanyLedger.STARTING_CASH + CompanyLedger.net(ledger.today)
	if absf(ledger.cash - expected_cash) > 0.0001:
		return fail("Cash no longer reconciles with the day's fares, expenses and one purchase")
	# Inspect the displayed row after the HUD's normal quarter-second refresh.
	for frame in 12:
		await process_frame
	for i in range(0, hud._info_grid.get_child_count(), 2):
		if hud._info_grid.get_child(i).text == "Holding capacity":
			if hud._info_grid.get_child(i + 1).text == "21 car spaces":
				return true
			break
	return fail("The Port Rosario inspector did not show 21 usable car spaces")
