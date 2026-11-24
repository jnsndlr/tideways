extends SceneTree
## On-disk settings and authored layout recovery, using only a temporary directory.

var failures := 0


func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var dir := DirAccess.create_temp("tideways-persistence")
	if dir == null:
		push_error("Could not create the persistence fixture")
		quit(1)
		return
	var folder := dir.get_current_dir()
	check_layouts(folder.path_join("layout.json"))
	check_settings(folder.path_join("settings.cfg"))
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_layouts(path: String) -> void:
	check(MapLayout.load_file(path) == null, "Missing layout")
	var layout := MapLayout.load_file(MapLayout.MAIN_STORY)
	check(layout != null, "The shipped layout must load")
	if layout == null:
		return
	check(layout.save_file(path) == OK, "First layout save")
	var reopened := MapLayout.load_file(path)
	check(reopened != null and reopened.to_dict() == layout.to_dict(), "Current layout round trip")
	var saved := FileAccess.get_file_as_string(path)
	var invalid_edit := layout.duplicate()
	invalid_edit.islands[0].radius = NAN
	check(invalid_edit.save_file(path) == ERR_INVALID_DATA, "Reject a non-finite edit")
	check(FileAccess.get_file_as_string(path) == saved, "Rejected edit leaves the last good file intact")
	var legacy := '{"world_seed":17,"islands":[{"name":"A","x":10,"z":20,"angle":90,"dock":true,"dock_x":13,"dock_z":24,"dock_angle":180}]}'
	check(SavedText.replace(path, legacy) == OK, "Install legacy fixture")
	var old := MapLayout.load_file(path)
	if old == null or old.islands[0].docks.size() != 1:
		check(false, "Legacy single dock must migrate")
		return
	var island := old.islands[0]
	var dock := island.docks[0]
	check(island.dock_at(dock).is_equal_approx(Vector2(13, 24)), "Legacy dock stays in place")
	check(island.dock_heading(dock).is_equal_approx(Vector2.LEFT), "Legacy dock keeps its heading")
	check(old.save_file(path) == OK and MapLayout.load_file(path).to_dict() == old.to_dict(), "Legacy layout round trip")
	for invalid: String in [
		'{"version":2,"extra":"preserve","islands":[]}', '{"version":"1","islands":[]}',
		'not json', '[]', '{}', '{"islands":{}}', '{"islands":[null]}',
		'{"world_seed":1.5,"islands":[]}', '{"islands":[{"x":"broken"}]}',
		'{"islands":[{"dock":"yes"}]}', '{"islands":[{"docks":{}}]}',
		'{"islands":[{"docks":[false]}]}', '{"islands":[{"docks":[{"facing":[]}]}]}',
	]:
		check(SavedText.replace(path, invalid) == OK, "Install protected layout")
		check(MapLayout.load_file(path) == null, "Reject unsupported or malformed layout: " + invalid)
		check(layout.save_file(path) == ERR_FILE_UNRECOGNIZED, "Refuse to replace protected layout")
		check(FileAccess.get_file_as_string(path) == invalid, "Preserve original layout bytes")
	DirAccess.remove_absolute(path)


func check_settings(path: String) -> void:
	GameSettings._path = path
	GameSettings._cfg = null
	check(GameSettings.flag("show_routes"), "Missing settings use defaults")
	check(GameSettings.set_volume("Radio", 0.36) == OK, "Write first audio setting")
	var good := FileAccess.get_file_as_string(path)
	# Block the destination itself so staging can succeed but replacement must fail.
	var backup := path + ".previous"
	check(DirAccess.rename_absolute(path, backup) == OK and DirAccess.make_dir_absolute(path) == OK, "Block the settings destination")
	var panel := SettingsPanel.new()
	root.add_child(panel)
	var toggle: CheckButton = panel.find_children("*", "CheckButton", true, false)[1]
	toggle.button_pressed = false
	check(panel._save_error.visible and toggle.button_pressed and GameSettings.flag("show_routes"), "A failed display save is shown and the switch reverts")
	var radio := panel.find_children("*", "HSlider", true, false)[2] as HSlider
	radio.value = 0.11
	check(panel._save_error.visible and is_equal_approx(radio.value, 0.36), "Failed volume save restores the slider")
	var bus := AudioServer.get_bus_index("Radio")
	check(is_equal_approx(AudioServer.get_bus_volume_linear(bus), 0.36), "Failed volume change must not affect the audio bus")
	var controls := MapControls.new()
	controls.add_child(controls.widget)
	controls.pinned = true
	controls.widget.pinned = true
	var pin_errors: Array[Error] = []
	controls.pin_save_failed.connect(func(err: Error) -> void: pin_errors.append(err))
	controls.toggle_open()
	check(controls.visible and controls.pinned and controls.widget.pinned and pin_errors.size() == 1, "Unpin failure keeps the widget open and reports the error")
	check(FileAccess.get_file_as_string(backup) == good, "Prior settings survive the failure")
	check(DirAccess.remove_absolute(path) == OK and DirAccess.rename_absolute(backup, path) == OK, "Restore destination")
	toggle.button_pressed = false
	check(not panel._save_error.visible, "Successful retry clears the warning")
	radio.value = 0.11
	controls.toggle_open()
	GameSettings._cfg = null
	check(not GameSettings.flag("show_routes") and not GameSettings.flag("weather_pinned") and is_equal_approx(GameSettings.volume("Radio"), 0.11), "Retried preferences survive reload")
	check(not controls.visible and not controls.pinned, "Weather pin can be retried")
	controls.free()
	panel.free()
	GameSettings._cfg = null
	GameSettings._path = GameSettings.PATH
	DirAccess.remove_absolute(path)
