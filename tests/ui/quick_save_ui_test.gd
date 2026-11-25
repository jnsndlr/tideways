extends "res://tests/support/ui_test_driver.gd"
## Verify the single quick-save slot through the menu, an F5 press, and reopening Play.

func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1366, 1024)
	var path := "user://quick-save-ui-%d.json" % OS.get_process_id()
	SaveGame._path = path
	var passed := await exercise_slot(path)
	SaveGame._path = SaveGame.PATH
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if passed:
		print("TEST PASSED")
	quit(0 if passed else 1)


func exercise_slot(path: String) -> bool:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	for button: Button in current_scene.find_children("*", "Button", true, false):
		if button.text == "Load saved game" and not button.disabled:
			return fail("Load should be disabled for an empty slot")
	if not await enter_game("Mission sandbox", Scenes.MAIN_MAP):
		return false
	var session: WorldSession = current_scene
	session.hud.set_speed(0)
	session.sim.day = 23
	session.sim.minutes = 721.5
	if not await press("MENU"):
		return false
	var menu := session.hud._game_menu
	if not menu.visible or menu.is_item_disabled(menu.get_item_index(0)):
		return fail("The authored map should offer Save game")
	menu.hide()
	var key := InputEventKey.new()
	key.physical_keycode = KEY_F5
	key.pressed = true
	root.push_input(key)
	var saved := SaveGame.read()
	if saved.get("scenario") != Scenario.OPENING or saved.get("day") != 23 or saved.get("minutes") != 721.5:
		return fail("F5 did not write the scenario and exact date")
	if saved.get("company") != "Island Ferries" or saved.get("unlimited") != true:
		return fail("Quick save lost the company name or mission mode")
	var bytes := FileAccess.get_file_as_bytes(path)
	SaveGame._path = path.path_join("cannot-write")
	menu.id_pressed.emit(0)
	SaveGame._path = path
	if session.hud._toast_title.text != "SAVE FAILED" or FileAccess.get_file_as_bytes(path) != bytes:
		return fail("A failed save must report failure and preserve the previous slot")
	menu.id_pressed.emit(2)
	await scene_changed
	if not await enter_game("Load saved game", Scenes.MAIN_MAP):
		return false
	var loaded: WorldSession = current_scene
	if loaded.sim.day != 23 or absf(loaded.sim.minutes - 721.5) > 2.0:
		return fail("Loading the slot did not restore the saved clock")
	if loaded.scenario.cash != CompanyLedger.UNLIMITED_CASH or RegionEntryState.company_name != "Island Ferries":
		return fail("Loading the slot did not restore the mission mode and company")
	return true
