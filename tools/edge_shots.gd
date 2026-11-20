extends SceneTree
## Renders the map's edges where the mainland meets it, for checking by eye.
##   godot --path . --resolution 1600x1000 --script tools/edge_shots.gd -- --out=DIR [--edit] [--tag=after]

var main: Node
var out := "user://"
var tag := "shot"
var edit := false
var frames := 0
var shot := 0
# x, z, distance, yaw, pitch
var cams := [
	[2900, 0, 2600, 0, 22], [2900, 0, 2600, 90, 22], [2900, 0, 2600, 180, 22], [2900, 0, 2600, 270, 22],
	[-2900, 0, 2600, 0, 22], [-2900, 0, 2600, 90, 22], [-2900, 0, 2600, 180, 22], [-2900, 0, 2600, 270, 22],
	[-3300, 800, 500, 90, 35],
	[2640, -300, 3600, 300, 55], [2640, 0, 4400, 0, 85], [2640, -1200, 2000, 270, 40],
	[-2400, -1100, 3200, 120, 35], [-2000, -2640, 3600, 200, 30], [0, 0, 9000, 0, 89],
]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--tag="):
			tag = a.substr(6)
		elif a == "--edit":
			edit = true
	DirAccess.make_dir_recursive_absolute(out)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames == 10:
		main.day_cycle.set_hour(17.5)
		main.day_cycle.apply(main.day_cycle.hour())
		if edit:
			main.editor.open(0)
			main.editor._go_stale()
	if frames >= 20 and frames % 25 == 0:
		if shot > 0:
			root.get_viewport().get_texture().get_image().save_png("%s/%s_%d.png" % [out, tag, shot - 1])
		if shot >= cams.size():
			return true
		main.day_cycle.set_hour(16.5)
		main.day_cycle.apply(main.day_cycle.hour())
		main.editor._clear_sky(true)
		var c: Array = cams[shot]
		main.rig.target_pos = Vector3(c[0], 0, c[1])
		main.rig.target_dist = c[2]
		main.rig.target_yaw = deg_to_rad(c[3])
		main.rig.target_pitch = deg_to_rad(c[4])
		main.rig.snap()
		shot += 1
	return false
