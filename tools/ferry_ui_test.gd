extends SceneTree
## Exercise the menu and ferry inspector with the project's normal canvas scaling.

const LANDSCAPE_SIZES := [Vector2i(1366, 1024), Vector2i(1133, 744)]


func _initialize() -> void:
	run.call_deferred()


func press(label: String, prefix := false) -> bool:
	# Fleet rows and inspector controls are laid out after their panel is shown.
	await process_frame
	await process_frame
	for button: Button in root.find_children("*", "Button", true, false):
		if not button.is_visible_in_tree():
			continue
		if button.text != label and button.tooltip_text != label and not (prefix and button.text.begins_with(label)):
			continue
		return click_control(button, button.size * 0.5, label)
	return fail("Missing visible button: " + label)


func click_control(control: Control, local_point: Vector2, label: String) -> bool:
	var point := control.get_global_transform_with_canvas() * local_point
	if not root.get_visible_rect().has_point(point):
		return fail("%s is outside the viewport at %s" % [label, point])
	var move := InputEventMouseMotion.new()
	move.position = point
	root.push_input(move, true)
	var hit := root.gui_get_hovered_control()
	if hit != control and (hit == null or not control.is_ancestor_of(hit)):
		return fail("%s at %s is blocked by %s" % [label, point, hit.get_path() if hit else "no control"])
	for down: bool in [true, false]:
		var click := InputEventMouseButton.new()
		click.position = point
		click.button_index = MOUSE_BUTTON_LEFT
		click.pressed = down
		root.push_input(click, true)
	return true


func key(code: Key) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.pressed = true
	root.push_input(event)
	event.pressed = false
	root.push_input(event)


func fail(message: String) -> bool:
	push_error("Ferry UI at %s: %s" % [root.size, message])
	return false


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


## The loading screen is still over the game (it fades out once the world is built).
func _loading() -> bool:
	for c in root.get_children():
		if c is CanvasLayer and c.get_child_count() > 0 and c.get_child(0) is LoadingScreen:
			return true
	return false


func exercise_layout() -> bool:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await press("Settings") or not await press("Done"):
		return false
	if not await press("Sandbox"):
		return false
	# The menu goes through the loading screen first. Bound the wait even if the
	# control is disconnected.
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if current_scene != null and current_scene.scene_file_path == Scenes.SANDBOX and not _loading():
			break
	if current_scene == null or current_scene.scene_file_path != Scenes.SANDBOX or not current_scene.built or _loading():
		return fail("Sandbox button did not navigate")
	var hud: Hud = current_scene.hud
	var boat: Ferry = current_scene.sim.ferries[0]
	if not await press("FLEET") or not await press(boat.ferry_name, true):
		return false
	if not hud._info_panel.visible or hud._info_title.text != boat.ferry_name.to_upper() or hud.rig.follow != boat:
		return fail("Wrong ferry inspector or follow target")
	if not await press("Stop following"):
		return false
	if hud.rig.follow != null:
		return fail("Stop following left the camera locked")
	if not await press("Follow"):
		return false
	if hud.rig.follow != boat:
		return fail("Follow did not restore the camera target")
	key(KEY_ESCAPE)
	if hud.selected_ferry != null or hud.rig.follow != null or hud._info_panel.visible:
		return fail("Escape left stale selection")
	if not await exercise_map_controls(hud):
		return false
	if not await exercise_layer_controls(hud, boat):
		return false
	if not exercise_touch_camera(hud.rig):
		return false
	if not await press("Speed 3"):
		return false
	if Engine.time_scale <= 1.0:
		return fail("Speed control did not accelerate")
	key(KEY_M)
	for i in 4:
		await process_frame
	if current_scene == null or current_scene.scene_file_path != Scenes.MENU or Engine.time_scale != 1.0:
		return fail("Return to menu or speed reset failed")
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
	if not await press("ROUTES") or not hud.routes_forced:
		return fail("Routes control did not enable the overlay")
	if not await press("ROUTES") or hud.routes_forced:
		return fail("Routes control did not restore automatic visibility")
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


## The edge group: weather visibility, independent layers, hide all, room beside
## the inspector, and a drag that neither taps nor pans.
func exercise_layer_controls(hud: Hud, boat: Ferry) -> bool:
	await frames(2)
	var controls := hud.map_controls
	var widget := controls.widget
	var art := widget.size * Vector2(0.5, 0.35)
	var clouds: CloudLayer = current_scene.clouds
	var minutes := hud.sim.minutes
	if not click_control(widget, art, "Weather widget"):
		return false
	if controls.weather_shown or clouds.shown or clouds.visible:
		return fail("Tapping the weather widget left map weather showing")
	hud.rig.target_dist = 2000.0
	hud.rig.distance = 2000.0
	await frames(3)
	if hud.sim.minutes <= minutes:
		return fail("Hiding map weather stopped the clock")
	if not hud.route_overlay.visible or not any_town_label(hud):
		return fail("Routes and town names should start visible from the overview")
	if not await press("Names"):
		return false
	await frames(2)
	if any_town_label(hud) or not hud.route_overlay.visible:
		return fail("Names off should hide town names and leave routes")
	if not await press("Routes"):
		return false
	for distance: float in [2000.0, 120.0]:
		hud.rig.target_dist = distance
		hud.rig.distance = distance
		await frames(2)
		if hud.route_overlay.visible:
			return fail("Hidden routes came back at camera distance %d" % distance)
	hud.rig.target_dist = 2000.0
	hud.rig.distance = 2000.0
	if not await press("Routes"):
		return false
	await frames(2)
	if not hud.route_overlay.visible or any_town_label(hud):
		return fail("Routes on with names off did not hold as a mixed state")
	if not await press("Hide all"):
		return false
	await frames(2)
	if controls.any_shown() or hud.route_overlay.visible or any_town_label(hud):
		return fail("Hide all left a map layer visible")
	if not await press("Show all"):
		return false
	await frames(2)
	if not hud.route_overlay.visible or not any_town_label(hud):
		return fail("Show all did not restore the map layers")
	if controls.weather_shown or clouds.shown:
		return fail("Hide all or Show all changed weather visibility")

	hud.select_ferry(boat)
	await frames(3)
	if controls.get_rect().intersects(hud._info_panel.get_rect()):
		return fail("Map controls overlap the open inspector")
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
