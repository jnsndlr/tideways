extends SceneTree
## Renders where Port Rosario's mainland meets the backdrop with a low sun from several
## sides, to check the tree cards take the light like the modelled pines.
##   godot --path . --resolution 1600x1000 --script tools/sun_shots.gd -- --out=DIR [--tag=X]

var main: Node
var out := "user://"
var tag := "sun"
var frames := 0
var dist := 2300.0
var pitch := 32.0
var shot := 0
# hour, yaw
var shots := [[7.0, 180], [7.0, 270], [19.6, 0], [19.6, 90]]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--tag="):
			tag = a.substr(6)
		elif a == "--high":
			dist = 2600.0
			pitch = 62.0
		elif a == "--close":
			# Low over Port Rosario's woods, as in play.
			dist = 380.0
			pitch = 24.0
	DirAccess.make_dir_recursive_absolute(out)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames >= 20 and frames % 25 == 0:
		if shot > 0:
			root.get_viewport().get_texture().get_image().save_png("%s/%s_%d.png" % [out, tag, shot - 1])
		if shot >= shots.size():
			return true
		var s: Array = shots[shot]
		main.day_cycle.set_hour(s[0])
		main.day_cycle.apply(main.day_cycle.hour())
		main.editor._clear_sky(true)
		main.rig.target_pos = Vector3(2900 if dist > 1000.0 else 3000, 0, -50)
		main.rig.target_dist = dist
		main.rig.target_yaw = deg_to_rad(s[1])
		main.rig.target_pitch = deg_to_rad(pitch)
		main.rig.snap()
		shot += 1
	return false
