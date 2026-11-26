extends "res://tests/support/ui_test_driver.gd"
## Exercise the real menu and ResourceLoader, including a failed dependency
## repaired in place. PID-specific fixtures keep concurrent runs independent.

var fixture := "user://region_retry_%d.tscn" % OS.get_process_id()
var dependency := "user://region_part_%d.tscn" % OS.get_process_id()
var transitions := 0


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	root.size = Vector2i(1366, 1024)
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	scene_changed.connect(func(): transitions += 1)
	var passed := await exercise()
	for path in [fixture, dependency]:
		if FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
	if passed:
		print("TEST PASSED")
	quit(0 if passed else 1)


func exercise() -> bool:
	if not await fails_in_menu(fixture):
		return false
	var file := FileAccess.open(fixture, FileAccess.WRITE)
	file.store_string('[gd_scene format=3]\n[ext_resource type="PackedScene" path="%s" id="1"]\n[node name="RetryRegion" instance=ExtResource("1")]\n' % dependency)
	file.close()
	if not await fails_in_menu(fixture):
		return false

	# Retry the very same path after repairing its missing dependency.
	file = FileAccess.open(dependency, FileAccess.WRITE)
	file.store_string('[gd_scene format=3]\n[node name="WorkingRegion" type="Node"]\n')
	file.close()
	var menu: WeakRef = weakref(current_scene)
	current_scene._start(fixture, "Retrying")
	if not await wait_for_destination(fixture) or transitions != 1 or menu.get_ref() != null:
		return fail("Repair and retry did not replace the original menu exactly once")
	var repaired: WeakRef = weakref(current_scene)
	# A pending file read must not replace a newer destination.
	LoadingScreen.open(self, fixture, "Loading")
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await wait_for_destination(Scenes.MENU) or transitions != 2:
		return fail("A stale region request replaced the menu")
	if repaired.get_ref() != null:
		return fail("Repaired scene was retained after returning to the menu")
	return await reopen_company()


func reopen_company() -> bool:
	# Simulate a previous company's editor state.
	RegionEntryState.editor_restore["editor_open"] = true
	if not await press("New company") or not await start_named_company():
		return false
	if not RegionEntryState.editor_restore.is_empty():
		return fail("Play inherited the previous editor state")
	# A second activation may already be queued before the overlay takes input.
	for button: Button in current_scene.find_children("*", "Button", true, false):
		if button.text in ["New company", "Mission sandbox"]:
			button.pressed.emit()
	var overlays := 0
	for layer in root.get_children():
		if layer is CanvasLayer and layer.get_child_count() and layer.get_child(0) is LoadingScreen:
			overlays += 1
	if overlays != 1:
		return fail("Two Play requests created %d loading screens" % overlays)
	if not await wait_for_destination(Scenes.MAIN_MAP) or transitions != 3 or not current_scene.built:
		return fail("Double Play did not produce one playable session")
	if current_scene.sim.ferries.size() != 1 or current_scene.sim.ferries[0].ferry_name != "Hiyu":
		return fail("An ignored mission request changed the opening selected by Play")
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	# Exit while the fresh resource request is still owned by the overlay.
	# The CI runner checks engine diagnostics after quit.
	return await press("New company") and await start_named_company()


func fails_in_menu(path: String) -> bool:
	var menu := current_scene
	menu._start(path, "Loading")
	var overlay: WeakRef = weakref(root.get_node("RegionLoading"))
	for frame in 600:
		await process_frame
		if not _loading():
			break
	if current_scene != menu or transitions != 0 or _loading() or overlay.get_ref() != null:
		return fail("Failed request retained an overlay or changed scenes")
	if not menu._load_error.is_visible_in_tree() or not "Try" in menu._load_error.text:
		return fail("The menu did not show recovery instructions")
	return true


func wait_for_destination(path: String) -> bool:
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if current_scene and current_scene.scene_file_path == path and not _loading():
			return true
	return false
