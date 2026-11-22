extends "res://tools/ui_test_driver.gd"
## Interrupt real cold and warm loads at two points in detached world assembly.
## The fast runner also checks errors and leak diagnostics emitted during quit.


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	for landmark in ["Water", "SeaFloor"]:
		if not await press("Play"):
			quit(1)
			return
		await scene_changed
		if current_scene.scene_file_path != Scenes.MAIN_MAP:
			push_error("Play did not enter Main Map.")
			quit(1)
			return
		var scene := current_scene
		var world_found := false
		var deadline := Time.get_ticks_msec() + 60000
		while scene.build_to <= 0.71 and Time.get_ticks_msec() < deadline:
			var builder: WorldBuilder = scene.builder
			if builder != null and is_instance_valid(builder.root) and builder.root.has_node(landmark):
				world_found = true
				break
			await process_frame
		if not world_found:
			push_error("Missed world construction at %s." % landmark)
			quit(1)
			return
		if landmark == "Water":
			var partial_world := weakref(scene.builder.root) as WeakRef
			change_scene_to_file(Scenes.MENU)
			await scene_changed
			if current_scene.scene_file_path != Scenes.MENU or partial_world.get_ref() != null:
				push_error("Returning to Menu did not dispose of the unfinished world.")
				quit(1)
				return
			var fade_deadline := Time.get_ticks_msec() + 10000
			while _loading() and Time.get_ticks_msec() < fade_deadline:
				await process_frame
	print("TEST PASSED")
	quit()
