extends SceneTree
## Interrupt the real loading path twice. CI also inspects engine diagnostics
## emitted after quit, when script assertions can no longer run.


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	change_scene_to_file(Scenes.MENU)
	await scene_changed
	for attempt in 2:
		LoadingScreen.open(self, Scenes.MAIN_MAP, "Loading")
		await scene_changed
		if current_scene.scene_file_path != Scenes.MAIN_MAP or current_scene.build_to != 0.3 or current_scene.built:
			push_error("Expected to interrupt region generation before the world build.")
			quit(1)
			return
		if attempt == 0:
			change_scene_to_file(Scenes.MENU)
			await scene_changed
			if current_scene.scene_file_path != Scenes.MENU:
				push_error("Interrupted generation did not return to the menu.")
				quit(1)
				return
	print("TEST PASSED")
	quit()
