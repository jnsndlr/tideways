extends "res://tests/support/ui_test_driver.gd"
## Exercise the menu and ferry inspector with the project's normal canvas scaling.

const LANDSCAPE_SIZES := [Vector2i(1366, 1024), Vector2i(1133, 744)]


func _initialize() -> void:
	run.call_deferred()


func key(code: Key) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.pressed = true
	root.push_input(event)
	event.pressed = false
	root.push_input(event)


func run() -> void:
	preload("res://scripts/sandbox.gd").map_seed = 123
	for size: Vector2i in LANDSCAPE_SIZES:
		root.size = size
		if not await exercise_layout():
			quit(1)
			return
		print("Fleet UI passed at %s, game canvas %s." % [root.size, root.get_visible_rect().size])
	print("TEST PASSED")
	quit(0)


func exercise_layout() -> bool:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await press("Settings") or not await press("Done"):
		return false
	if not await enter_game("Sandbox", Scenes.SANDBOX):
		return false
	var hud: Hud = current_scene.hud
	var boat: Ferry = current_scene.sim.ferries[0]
	if not await sandbox_save_enabled(hud):
		return false
	if not exercise_shortcuts(hud):
		return false
	if not await press("FLEET") or not await press(boat.ferry_name, true):
		return false
	if (
		not hud._ferry_panel.visible
		or hud._ferry_panel._name_label.text != "M/V " + boat.ferry_name.to_upper()
		or hud.rig.follow != boat
	):
		return fail("Wrong ferry inspector or follow target")
	if not await press("Stop Following"):
		return false
	if hud.rig.follow != null:
		return fail("Stop following left the camera locked")
	if not await press("Follow Vessel"):
		return false
	if hud.rig.follow != boat:
		return fail("Follow did not restore the camera target")
	key(KEY_ESCAPE)
	if hud.selected_ferry != null or hud.rig.follow != null or hud._ferry_panel.visible:
		return fail("Escape left stale selection")
	if not await exercise_map_controls(hud):
		return false
	if not await exercise_layer_controls(hud, boat):
		return false
	if not exercise_touch_camera(hud.rig):
		return false
	if not await exercise_speed_slider(hud):
		return false
	key(KEY_M)
	for i in 4:
		await process_frame
	if current_scene == null or current_scene.scene_file_path != Scenes.MENU or Engine.time_scale != 1.0:
		return fail("Return to menu or speed reset failed")
	return true


func sandbox_save_enabled(hud: Hud) -> bool:
	if not await press("MENU"):
		return false
	var menu := hud._game_menu
	var disabled := menu.is_item_disabled(menu.get_item_index(0))
	menu.hide()
	await process_frame
	return not disabled or fail("The procedural Sandbox should offer Save game")


## Physical shortcuts survive layout changes. A held key and its release apply the command only once.
func exercise_shortcuts(hud: Hud) -> bool:
	var weather := hud.sim.weather
	var expected := weather.next_kind()
	var event := InputEventKey.new()
	event.physical_keycode = KEY_V
	event.keycode = KEY_B
	event.pressed = true
	root.push_input(event)
	event.echo = true
	root.push_input(event)
	event.echo = false
	event.pressed = false
	root.push_input(event)
	if not weather.pinned or weather.kind != expected:
		return fail("The physical V shortcut should advance the weather exactly once")
	event.shift_pressed = true
	event.pressed = true
	root.push_input(event)
	event.pressed = false
	root.push_input(event)
	if weather.pinned or weather.kind != expected:
		return fail("Shift+V should resume the weather without advancing it")

	var action := InputEventAction.new()
	action.action = &"hud_speed_fast"
	action.pressed = true
	root.push_input(action)
	action.pressed = false
	root.push_input(action)
	if Engine.time_scale != 8.0:
		return fail("A named speed action must work independently of its physical key")
	key(KEY_1)
	if Engine.time_scale != 1.0:
		return fail("The physical 1 shortcut should restore normal speed")
	return true


func exercise_map_controls(hud: Hud) -> bool:
	if not await press("WILDLIFE") or not await press("• ", true):
		return false
	if hud.rig.follow == null or hud.selected_ferry != null:
		return fail("Active sighting did not switch the camera to wildlife")
	var target := hud._minimap_rect
	if not click_control(target, target.size * Vector2(0.75, 0.25), "Minimap"):
		return false
	var half_size := float(hud.map.half_size)
	var expected := Vector3(half_size * 0.5, 0, -half_size * 0.5)
	if hud.rig.follow != null or not hud.rig.target_pos.is_equal_approx(expected):
		return fail("Minimap did not center the camera on the chosen location")
	if not await press("MAP") or not hud.rig.target_pos.is_zero_approx():
		return fail("Map overview did not recenter the camera")
	return true

func frames(count: int) -> void:
	for i in count:
		await process_frame


func any_town_label(hud: Hud) -> bool:
	for label: Control in hud._labels.values():
		if label.visible:
			return true
	return false


## Presses on a control and moves the pointer `by` before letting go.
func drag_control(control: Control, local_point: Vector2, by: Vector2) -> void:
	var from := control.get_global_transform_with_canvas() * local_point
	var event := InputEventMouseButton.new()
	event.position = from
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = true
	root.push_input(event, true)
	for step in 8:
		var move := InputEventMouseMotion.new()
		move.position = from + by * (step + 1) / 8.0
		move.relative = by / 8.0
		move.button_mask = MOUSE_BUTTON_MASK_LEFT
		root.push_input(move, true)
	event = InputEventMouseButton.new()
	event.position = from + by
	event.button_index = MOUSE_BUTTON_LEFT
	event.pressed = false
	root.push_input(event, true)


## Map layers from Settings, and the weather widget: the WEATHER sidebar button,
## its pin, weather visibility, room beside the inspector, and a drag that neither
## taps nor pans.
func exercise_layer_controls(hud: Hud, boat: Ferry) -> bool:
	await frames(2)
	var controls := hud.map_controls
	var widget := controls.widget
	var art := widget.size * Vector2(0.5, 0.35)
	var clouds: CloudLayer = current_scene.clouds
	var minutes := hud.sim.minutes
	# Layer flags are set in memory only, so the test never rewrites the player's file.
	var cfg := GameSettings._cfg
	for key: String in ["show_routes", "show_names", "show_areas"]:
		cfg.set_value("display", key, true)
	hud.rig.target_dist = 2000.0
	hud.rig.distance = 2000.0
	await frames(2)
	if not hud.route_overlay.visible or not any_town_label(hud):
		return fail("Routes and town names should start visible from the overview")
	cfg.set_value("display", "show_names", false)
	await frames(2)
	if any_town_label(hud) or not hud.route_overlay.visible:
		return fail("Names off should hide town names and leave routes")
	cfg.set_value("display", "show_routes", false)
	for distance: float in [2000.0, 120.0]:
		hud.rig.target_dist = distance
		hud.rig.distance = distance
		await frames(2)
		if hud.route_overlay.visible:
			return fail("Hidden routes came back at camera distance %d" % distance)
	hud.rig.target_dist = 2000.0
	hud.rig.distance = 2000.0
	cfg.set_value("display", "show_routes", true)
	cfg.set_value("display", "show_names", true)
	await frames(2)
	if not hud.route_overlay.visible or not any_town_label(hud):
		return fail("Turning layers back on did not restore them")

	# The sidebar opens and collapses the widget; unpinned, a map click tucks it away.
	controls.pinned = false
	controls.visible = false
	if not await press("WEATHER") or not controls.visible:
		return fail("WEATHER did not open the weather widget")
	if not await press("WEATHER") or controls.visible:
		return fail("WEATHER did not collapse the weather widget")
	if not await press("WEATHER"):
		return false
	hud._on_ground_clicked(Vector2(-1000, -1000))
	if controls.visible:
		return fail("An unpinned weather widget stayed open after a map click")
	controls.visible = true
	controls.pinned = true
	hud._on_ground_clicked(Vector2(-1000, -1000))
	if not controls.visible:
		return fail("A pinned weather widget closed on a map click")
	await frames(2)

	if not click_control(widget, art, "Weather widget"):
		return false
	if controls.weather_shown or clouds.shown or clouds.visible:
		return fail("Tapping the weather widget left map weather showing")
	await frames(3)
	if hud.sim.minutes <= minutes:
		return fail("Hiding map weather stopped the clock")

	hud.select_ferry(boat)
	await frames(3)
	if controls.get_rect().intersects(hud._ferry_panel.get_rect()):
		return fail("Map controls overlap the open inspector")
	if hud._ferry_panel.get_rect().intersects(hud._minimap_panel.get_rect()):
		return fail("The ferry inspector overlaps the minimap at %s" % hud._ferry_panel.get_rect())
	if not click_control(widget, art, "Weather widget beside the inspector"):
		return false
	if not controls.weather_shown or not clouds.shown:
		return fail("Weather did not come back with the inspector open")
	hud.clear_selection()
	await frames(2)

	var camera_target := hud.rig.target_pos
	var across := -(root.get_visible_rect().size.x - controls.size.x - 80.0)
	drag_control(widget, art, Vector2(across, 60.0))
	touch(0, widget.get_global_transform_with_canvas() * art, true)
	var leaked := not hud.rig._touches.is_empty()
	touch(0, widget.get_global_transform_with_canvas() * art, false)
	await frames(2)
	if leaked:
		return fail("A finger on the weather widget reached the camera")
	if not controls.weather_shown:
		return fail("Dragging the weather widget also toggled weather")
	if not hud.rig.target_pos.is_equal_approx(camera_target):
		return fail("Dragging the weather widget panned the map")
	if controls.side != -1 or not root.get_visible_rect().encloses(controls.get_rect()):
		return fail("Map controls did not settle on the left edge at %s" % controls.get_rect())
	for panel: Control in [hud._top_bar, hud.sidebar]:
		if controls.get_rect().intersects(panel.get_rect()):
			return fail("Map controls settled over %s" % panel.get_path())
	drag_control(widget, art, Vector2(-across, -60.0))
	await frames(2)
	if controls.side != 1 or not root.get_visible_rect().encloses(controls.get_rect()):
		return fail("Map controls did not return to the right edge")
	return true


func touch(index: int, point: Vector2, pressed: bool) -> void:
	var event := InputEventScreenTouch.new()
	event.index = index
	event.position = point
	event.pressed = pressed
	root.push_input(event, true)


func drag(index: int, start: Vector2, end: Vector2) -> void:
	var event := InputEventScreenDrag.new()
	event.index = index
	event.position = end
	event.relative = end - start
	root.push_input(event, true)


func exercise_touch_camera(rig: CameraRig) -> bool:
	var center := root.get_visible_rect().size * 0.5
	var left := center - Vector2(60, 0)
	var right := center + Vector2(60, 0)
	var spread := right + Vector2(90, 0)
	var distance := rig.target_dist
	touch(0, left, true)
	touch(1, right, true)
	drag(1, right, spread)
	if rig.target_dist >= distance:
		return fail("Spreading fingers did not zoom in")
	drag(1, spread, right)
	if not is_equal_approx(rig.target_dist, distance):
		return fail("Pinching back did not restore the zoom")
	touch(2, center, true)
	var pitch := rig.target_pitch
	var shifted := center + Vector2(0, -30)
	drag(2, center, shifted)
	touch(2, shifted, false)
	touch(1, right, false)
	touch(0, left, false)
	if rig.target_pitch >= pitch:
		return fail("Three-finger drag did not tilt toward the horizon")
	return true


func exercise_speed_slider(hud: Hud) -> bool:
	const LABELS := ["Paused", "Real time", "1x", "8x", "16x", "32x"]
	const RATES := [0.0, 1.0 / 30.0, 1.0, 8.0, 16.0, 32.0]
	for stop in LABELS.size():
		if not await click_speed_stop(stop):
			return false
		if (
			hud._speed_label.text != LABELS[stop]
			or not is_equal_approx(Engine.time_scale, RATES[stop])
		):
			return fail("Wrong speed at slider stop %d" % stop)
		if stop == 1 and not await exercise_real_time(hud):
			return false
	return exercise_speed_drag(hud)


func exercise_real_time(hud: Hud) -> bool:
	var clock_before := hud.sim.clock_text()
	var before := hud.sim.abs_minutes()
	hud.sim._process(60.0 * Engine.time_scale)
	if not is_equal_approx(hud.sim.abs_minutes() - before, 1.0):
		return fail("A real minute should advance the clock by one game minute")
	for frame in 16:
		await process_frame
		if hud._stat["time"].text == hud.sim.clock_text():
			break
	if hud._stat["time"].text != hud.sim.clock_text() or hud.sim.clock_text() == clock_before:
		return fail("The HUD clock should display the next minute at Real time")
	key(KEY_SPACE)
	if hud._speed_slider.value != 0 or Engine.time_scale != 0:
		return fail("Space should pause from Real time")
	key(KEY_SPACE)
	if hud._speed_slider.value != 1 or hud._speed_label.text != "Real time":
		return fail("Space should restore Real time")
	return true


func exercise_speed_drag(hud: Hud) -> bool:
	# Drag the grabber from the right edge while holding the mouse button.
	var slider := hud._speed_slider
	var transform := slider.get_global_transform_with_canvas()
	var start := transform * Vector2(slider.size.x - 1, slider.size.y * 0.5)
	var end := transform * Vector2(1, slider.size.y * 0.5)
	var button := InputEventMouseButton.new()
	button.position = start
	button.button_index = MOUSE_BUTTON_LEFT
	button.pressed = true
	root.push_input(button, true)
	var drag := InputEventMouseMotion.new()
	drag.position = end
	drag.relative = end - start
	drag.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(drag, true)
	if Engine.time_scale != 0.0 or hud._speed_label.text != "Paused":
		return fail("Dragging to the first stop should pause before releasing the slider")
	button.position = end
	button.pressed = false
	root.push_input(button, true)
	key(KEY_1)
	if (
		slider.has_focus()
		or slider.value != 2
		or hud._speed_label.text != "1x"
		or Engine.time_scale != 1.0
	):
		return fail("The normal-speed shortcut should still work after a slider drag")
	return true
