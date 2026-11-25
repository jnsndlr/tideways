extends "res://tests/support/ui_test_driver.gd"
## Buy through the fleet catalogue and reconcile the debit against Finances.

func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1366, 1024)
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	var passed := await exercise()
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if passed:
		print("TEST PASSED")
	quit(0 if passed else 1)


func exercise() -> bool:
	if not await enter_game("Play", Scenes.MAIN_MAP):
		return false
	if not await press("Pause") or not await press("FLEET") or not await press("Buy a boat"):
		return false
	var hud: Hud = current_scene.hud
	var sim: Simulation = current_scene.sim
	var panel: FleetPanel = hud._fleet_panel
	var starting_cash := sim.available_cash
	var initial_count := sim.ferries.size()
	if not await press("Size 3", true):
		return false
	if not panel._confirm.disabled:
		return fail("Unaffordable boat offered for purchase")
	if not await press("Size 1", true):
		return false
	if not "Port Rosario" in panel._where_title.text or not "tie-up" in panel._where_title.text:
		return fail("The catalogue did not identify the delivery berth before confirmation")
	if not await press("Buy for $30,000"):
		return false
	if sim.ferries.size() != initial_count + 1 or not is_equal_approx(sim.available_cash, starting_cash - 30000):
		return fail("One confirmation should buy and charge for exactly one ferry")
	var bought := sim.ferries[-1]
	if hud.selected_ferry != bought or bought.berth != Ferry.Berth.DELIVERING:
		return fail("The purchase did not select the new ferry under tow")
	var tow_hull := bought.tow.get_node_or_null("VesselHullView") as VesselHullView
	if not tow_hull or tow_hull.mesh != Models.tug(bought.tow.model_variant):
		return fail("The delivery tug should be visible with its escort hull")
	for boat: Ferry in [sim.ferries[0], bought]:
		var views := boat.get_children().filter(func(child: Node): return child is FerryView)
		if views.size() != 1:
			return fail("Opening and newly purchased ferries should each have one fitted view")
	if not await press("FINANCES"):
		return false
	var panel_finance := hud._finance_panel
	if panel_finance._cells[["purchases", 0]].text != "-" + Hud.fmt_money(30000):
		return fail("Finances did not show the boat purchase")
	if not await press("FINANCES") or not await press("FLEET") or not await press("Buy a boat") or not await press("Size 1", true):
		return false
	if not panel._confirm.disabled or sim.ledger.today["purchases"] != 30000:
		return fail("The catalogue must recheck remaining cash before a second purchase")
	return true
