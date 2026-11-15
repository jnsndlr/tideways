extends SceneTree
## Exercise the actual menu and HUD control bindings, with a fixed Sandbox map.


func _initialize() -> void:
	run.call_deferred()


func press(label: String, prefix := false) -> bool:
	for button: Button in current_scene.find_children("*", "Button", true, false):
		if button.is_visible_in_tree() and (button.text == label or (prefix and button.text.begins_with(label))):
			button.pressed.emit()
			return true
	push_error("Missing visible button: " + label)
	return false


func key(code: Key) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.pressed = true
	root.push_input(event)
	event.pressed = false
	root.push_input(event)


func check(ok: bool, message: String) -> bool:
	if not ok:
		push_error(message)
		quit(1)
	return ok


func run() -> void:
	preload("res://scripts/sandbox.gd").map_seed = 123
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	if not check(press("Sandbox"), "Could not open Sandbox"):
		return
	# Bound scene transitions even if the control is disconnected.
	for i in 4:
		await process_frame
	if not check(current_scene != null and current_scene.scene_file_path == Scenes.SANDBOX, "Sandbox button did not navigate"):
		return
	var hud: Hud = current_scene.hud
	var boat: Ferry = current_scene.sim.ferries[0]
	if not check(press("FLEET") and press(boat.ferry_name, true), "Could not select first ferry via fleet"):
		return
	if not check(hud._info_panel.visible and hud._info_title.text == boat.ferry_name.to_upper() and hud.rig.follow == boat, "Wrong ferry inspector or follow target"):
		return
	if not check(press("Stop following") and hud.rig.follow == null and press("Follow") and hud.rig.follow == boat, "Follow button did not toggle"):
		return
	key(KEY_ESCAPE)
	if not check(hud.selected_ferry == null and hud.rig.follow == null and not hud._info_panel.visible, "Escape left stale ferry selection"):
		return
	key(KEY_3)
	if not check(Engine.time_scale > 1.0, "Speed control did not accelerate"):
		return
	key(KEY_M)
	for i in 4:
		await process_frame
	if not check(current_scene != null and current_scene.scene_file_path == Scenes.MENU and Engine.time_scale == 1.0, "Return to menu or speed reset failed"):
		return
	print("Fleet selection, camera follow, clearing selection and return to menu passed.")
	quit(0)
