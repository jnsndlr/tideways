extends "res://tools/ui_test_driver.gd"
## Interrupt real cold and warm loads at two points in detached world assembly.
## The fast runner also checks errors and leak diagnostics emitted during quit.


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	for second_load: bool in [false, true]:
		if not await press("Play"):
			quit(1)
			return
		await scene_changed
		if current_scene.scene_file_path != Scenes.MAIN_MAP:
			push_error("Play did not enter Main Map.")
			quit(1)
			return
		var scene := current_scene
		var deadline := Time.get_ticks_msec() + 60000
		var partial: Node = null
		while not scene.built and Time.get_ticks_msec() < deadline:
			partial = unfinished_construction(scene, second_load)
			if partial != null:
				break
			await process_frame
		if partial == null:
			push_error("Missed the expected construction milestone on load %d." % (int(second_load) + 1))
			quit(1)
			return
		if not second_load:
			var partial_node := weakref(partial) as WeakRef
			var partial_world := weakref(scene.builder.root) as WeakRef
			change_scene_to_file(Scenes.MENU)
			await scene_changed
			if current_scene.scene_file_path != Scenes.MENU or partial_node.get_ref() != null or partial_world.get_ref() != null:
				push_error("Returning to Menu did not dispose of the unfinished world.")
				quit(1)
				return
			var fade_deadline := Time.get_ticks_msec() + 10000
			while _loading() and Time.get_ticks_msec() < fade_deadline:
				await process_frame
	print("TEST PASSED")
	quit()


## Identify the detached node to check for disposal on return to the menu.
func unfinished_construction(scene: Node, second_load: bool) -> Node:
	var builder: WorldBuilder = scene.builder
	if scene.build_to != 0.71 or builder == null or not is_instance_valid(builder.root):
		return null
	return builder.root if builder.root.has_node("SeaFloor" if second_load else "Water") else null
