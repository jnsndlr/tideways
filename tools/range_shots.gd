extends SceneTree
## Renders the far mountain ranges (Backdrop) from low views all round, for checking
## the painted look by eye.
##   godot --path . --resolution 1600x1000 --script tools/range_shots.gd -- --out=DIR [--tag=after]

var main: Node
var out := "user://"
var tag := "range"
var frames := 0
var shot := 0
# target x, target z, dist, pitch°, yaw°
var shots := [
	[0.0, 0.0, 1800.0, 8.0, 0.0],
	[0.0, 0.0, 1800.0, 8.0, 90.0],
	[0.0, 0.0, 1800.0, 8.0, 180.0],
	[0.0, 0.0, 1800.0, 8.0, 270.0],
	[0.0, 0.0, 3000.0, 14.0, 45.0],
	[0.0, 0.0, 3000.0, 14.0, 225.0],
	# From the map's edge, close in on each side's ranges.
	["edge", 0.0, 1400.0, 6.0, 0.0],
	["edge", 0.0, 1400.0, 6.0, 90.0],
	["edge", 0.0, 1400.0, 6.0, 180.0],
	["edge", 0.0, 1400.0, 6.0, 270.0],
]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--tag="):
			tag = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 90 or frames % 30 != 0:
		return false
	if shot > 0:
		root.get_viewport().get_texture().get_image().save_png("%s/%s_%d.png" % [out, tag, shot - 1])
	if shot >= shots.size():
		return true
	var s: Array = shots[shot]
	main.sim.weather.set_kind("Few Clouds", 0.0)
	main.day_cycle.set_hour(11.0)
	main.day_cycle.apply(main.day_cycle.hour())
	var at := Vector3.ZERO
	if s[0] is String:
		var y := deg_to_rad(s[4])
		at = Vector3(-sin(y), 0.0, -cos(y)) * 2700.0
	else:
		at = Vector3(s[0], 0, s[1])
	main.rig.target_pos = at
	main.rig.target_dist = s[2]
	main.rig.target_pitch = deg_to_rad(s[3])
	main.rig.target_yaw = deg_to_rad(s[4])
	main.rig.snap()
	shot += 1
	return false
