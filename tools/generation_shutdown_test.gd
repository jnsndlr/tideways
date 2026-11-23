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
		await create_timer(0.1).timeout
		if current_scene.build_to != 0.3:
			push_error("Generation finished before interruption.")
			quit(1)
			return
		if attempt == 0:
			var overlay: CanvasLayer
			for layer in root.get_children():
				if layer is CanvasLayer and layer.get_child_count() > 0 and layer.get_child(0) is LoadingScreen:
					overlay = layer
					break
			if overlay == null:
				push_error("Expected an active loading overlay.")
				quit(1)
				return
			var start := Time.get_ticks_msec()
			change_scene_to_file(Scenes.MENU)
			await scene_changed
			await process_frame
			if is_instance_valid(overlay):
				push_error("Cancelled loading screen still covers the menu.")
				quit(1)
				return
			var elapsed := Time.get_ticks_msec() - start
			print("Interrupted generation returned to Menu in %d ms" % elapsed)
			if elapsed > 1000:
				push_error("Menu waited over a second for region generation.")
				quit(1)
				return
			if current_scene.scene_file_path != Scenes.MENU:
				push_error("Interrupted generation did not return to the menu.")
				quit(1)
				return
	print("TEST PASSED")
	quit()
