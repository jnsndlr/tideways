extends SceneTree
## Saves the minimap at day and at night, for checking it by eye.
##   godot --path . --script tools/minimap_shots.gd -- --out=DIR

const HOURS := [12.0, 23.0]
var main: Node
var frames := 0
var out := "user://"
var ready_at := -1


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	main = load("res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("hud") == null or main.hud.get("_minimap_rect") == null or main.get("sim") == null:
		return false
	if ready_at < 0:
		ready_at = frames
	var step := (frames - ready_at) / 60
	if (frames - ready_at) % 60 == 0 and step < HOURS.size():
		main.sim.minutes = HOURS[step] * 60.0
	if (frames - ready_at) % 60 == 40 and step < HOURS.size():
		var vp: SubViewport = main.hud._minimap_rect.texture.get_viewport() if false else null
		for c in main.hud.get_children():
			if c is SubViewport:
				c.render_target_update_mode = SubViewport.UPDATE_ONCE
	if (frames - ready_at) % 60 == 55 and step < HOURS.size():
		main.hud._minimap_rect.texture.get_image().save_png(
			"%s/minimap_h%d.png" % [out, int(HOURS[step])]
		)
		root.get_viewport().get_texture().get_image().save_png(
			"%s/screen_h%d.png" % [out, int(HOURS[step])]
		)
	return step >= HOURS.size()
