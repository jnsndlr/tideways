extends SceneTree
## Exercise the menu and ferry inspector with the project's normal canvas scaling.

const LANDSCAPE_SIZES := [Vector2i(1366, 1024), Vector2i(1133, 744)]


func _initialize() -> void:
	run.call_deferred()


func press(label: String, prefix := false) -> bool:
	# Fleet rows and inspector controls are laid out after their panel is shown.
	await process_frame
	await process_frame
	for button: Button in current_scene.find_children("*", "Button", true, false):
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


func exercise_layout() -> bool:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not await press("Sandbox"):
		return false
	# Bound scene transitions even if the control is disconnected.
	for i in 4:
		await process_frame
	if current_scene == null or current_scene.scene_file_path != Scenes.SANDBOX:
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
