extends "res://tests/support/ui_test_driver.gd"
## Verify the single quick-save slot through the menu, an F5 press, and reopening Play.


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1366, 1024)
	var path := "user://quick-save-ui-%d.json" % OS.get_process_id()
	SaveGame._path = path
	var passed := await exercise_slot(path)
	if passed:
		passed = await check_long_company()
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
	if not await check_empty_board():
		return false
	if not await enter_game("Mission sandbox", Scenes.MAIN_MAP):
		return false
	var session: WorldSession = current_scene
	session.hud.set_speed(0)
	session.sim.day = 23
	if not await press("MENU"):
		return false
	var menu := session.hud._game_menu
	if not menu.visible or menu.is_item_disabled(menu.get_item_index(0)):
		return fail("The authored map should offer Save game")
	menu.hide()
	await process_frame
	var key := InputEventKey.new()
	key.physical_keycode = KEY_F5
	key.keycode = KEY_F5
	key.pressed = true
	session.sim.minutes = 721.5
	root.push_input(key)
	if not check_slot(session):
		return false
	return await try_failed_save(session, menu, path)


func check_empty_board() -> bool:
	root.size = Vector2i(900, 900)
	await process_frame
	await process_frame
	for button: Button in current_scene.find_children("*", "Button", true, false):
		if button.text == "Continue" and button.is_visible_in_tree():
			return fail("Continue should be hidden for an empty slot")
		if (
			button.is_visible_in_tree()
			and not root.get_visible_rect().encloses(button.get_global_rect())
		):
			return fail("The square window cropped the %s control" % button.text)
	root.size = Vector2i(1366, 1024)
	return true


func check_long_company() -> bool:
	var name_text := "W".repeat(32)
	if not SaveGame.save(Scenario.OPENING, false, 123, 480, name_text):
		return fail("Could not prepare the long-name save")
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	var ink: Label = current_scene.get_node("Board")._ink[2]
	if not ink.text.begins_with("Day 123") or not ink.text.ends_with(name_text):
		return fail("The end ellipsis must preserve the day for a maximum-width name")
	var opener: Button = current_scene.get_node("Board/Rows/Departures/NewCompany")
	opener.grab_focus()
	if not await press("New company"):
		return false
	var dialog: Control = current_scene._name_dialog
	for step in 4:
		var event := InputEventAction.new()
		event.action = &"ui_focus_next"
		event.pressed = true
		root.push_input(event)
		await process_frame
		var focused := root.gui_get_focus_owner()
		if not focused or not dialog.is_ancestor_of(focused):
			return fail("Tab navigation left the open company naming panel")
	if not await press("Cancel"):
		return false
	await process_frame
	return root.gui_get_focus_owner() == opener or fail("Cancel should return focus to New company")


func check_slot(session: WorldSession) -> bool:
	var saved := SaveGame.read()
	if (
		saved.get("scenario") != Scenario.OPENING
		or saved.get("day") != 23
		or saved.get("minutes") != 721.5
	):
		return fail(
			(
				"F5 did not write the scenario and exact date: %s, toast %s"
				% [saved, session.hud._toast_title.text]
			)
		)
	if saved.get("company") != "Island Ferries" or saved.get("unlimited") != true:
		return fail("Quick save lost the company name or mission mode")
	return true


func try_failed_save(session: WorldSession, menu: PopupMenu, path: String) -> bool:
	var bytes := FileAccess.get_file_as_bytes(path)
	SaveGame._path = path.path_join("cannot-write")
	menu.id_pressed.emit(0)
	SaveGame._path = path
	if (
		session.hud._toast_title.text != "SAVE FAILED"
		or FileAccess.get_file_as_bytes(path) != bytes
	):
		return fail("A failed save must report failure and preserve the previous slot")
	menu.id_pressed.emit(2)
	await scene_changed
	return await reopen_slot()


func reopen_slot() -> bool:
	var company_line := false
	for label: Label in current_scene.find_children("*", "Label", true, false):
		if (
			label.is_visible_in_tree()
			and label.text.contains("Island Ferries")
			and label.text.contains("Day 23")
		):
			company_line = true
	if not company_line:
		return fail("The departure board did not display the saved company and day")
	if not await enter_game("Continue", Scenes.MAIN_MAP):
		return false
	var loaded: WorldSession = current_scene
	if loaded.sim.day != 23 or absf(loaded.sim.minutes - 721.5) > 2.0:
		return fail("Loading the slot did not restore the saved clock")
	if (
		loaded.scenario.cash != CompanyLedger.UNLIMITED_CASH
		or RegionEntryState.company_name != "Island Ferries"
	):
		return fail("Loading the slot did not restore the mission mode and company")
	return true
