extends SceneTree
## Shared player input and scene navigation for headless UI checks.


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


func click_speed_stop(stop: int) -> bool:
	await process_frame
	var slider: HSlider = current_scene.hud._speed_slider
	var point := Vector2(slider.size.x * stop / slider.max_value, slider.size.y * 0.5)
	point.x = clampf(point.x, 1, slider.size.x - 1)
	return click_control(slider, point, "Game speed stop %d" % stop)


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


func fail(message: String) -> bool:
	push_error("UI check at %s: %s" % [root.size, message])
	return false


func start_named_company() -> bool:
	var field := root.gui_get_focus_owner() as LineEdit
	if field == null:
		return fail("Company name field did not receive focus")
	root.push_text_input("Island Ferries")
	return await press("Start")


## The loading screen is still over the game (it fades out once the world is built).
func _loading() -> bool:
	for c in root.get_children():
		if c is CanvasLayer and c.get_child_count() > 0 and c.get_child(0) is LoadingScreen:
			return true
	return false


func enter_game(button_text: String, scene_path: String) -> bool:
	if button_text in ["Sandbox", "Mission sandbox"] and not await press("Sandboxes"):
		return false
	if not await press(button_text):
		return false
	if button_text in ["New company", "Mission sandbox"] and not await start_named_company():
		return false
	# The menu goes through the loading screen first. Bound the wait even if the
	# control is disconnected.
	var deadline := Time.get_ticks_msec() + 90000
	while Time.get_ticks_msec() < deadline:
		await process_frame
		if current_scene != null and current_scene.scene_file_path == scene_path and not _loading():
			break
	if current_scene == null or current_scene.scene_file_path != scene_path or not current_scene.built or _loading():
		return fail("%s button did not navigate to %s" % [button_text, scene_path])
	return true
