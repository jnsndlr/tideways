extends "res://tests/rule_test_case.gd"
## Opening phases vary on return. The player keeps its place on rotation and alternates sailings.

const TITLE := preload("res://scenes/menu.tscn")


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var previous := -1.0
	for visit in range(3):
		var menu: Control = TITLE.instantiate()
		root.add_child(menu)
		var harbor: VideoStreamPlayer = menu.get_node("Terminal/Harbor")
		var duration := harbor.get_stream_length()
		var start := harbor.stream_position
		check(start >= 0.0 and start < duration, "Opening must be inside the sailing")
		if visit > 0:
			var gap := absf(start - previous)
			check(minf(gap, duration - gap) >= 29.99, "Menu revisits must vary the opening")
		previous = start
		if visit == 0:
			await exercise_playback(menu, harbor)
		menu.free()
		await process_frame
	finish()


func exercise_playback(menu: Control, harbor: VideoStreamPlayer) -> void:
	var first := harbor.stream
	harbor.stream_position = 60.0
	menu.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	menu.size = Vector2(1180, 820)
	var glass := harbor.material as ShaderMaterial
	var landscape_mask: Texture2D = glass.get_shader_parameter("glass")
	menu.size = Vector2(820, 1180)
	await process_frame
	check(glass.get_shader_parameter("glass") != landscape_mask, "Rotation must fit portrait glass")
	check(
		harbor.stream == first and absf(harbor.stream_position - 60.0) < 1.0,
		"Resizing the menu must preserve playback"
	)
	for sailing in range(2):
		var before := harbor.stream
		harbor.stream_position = harbor.get_stream_length() - 0.2
		for frame in range(60):
			await process_frame
			if harbor.stream != before:
				break
		check(
			harbor.stream != before and harbor.is_playing() and harbor.stream_position < 1.0,
			"The next sailing must play from the beginning"
		)
	check(harbor.stream == first, "Both traffic sets must repeat in order")
