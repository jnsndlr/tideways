extends SceneTree
## Renders the horizon clouds (sky.gdshader) from low, shallow views for each kind of
## weather and a few times of day.
##   godot --path . --resolution 1600x1000 --script tools/horizon_shots.gd -- --out=DIR

var main: Node
var out := "user://"
var frames := 0
var shot := 0
# target x, target z, dist, pitch°, yaw°, weather, hour
var shots := [
	[0.0, 0.0, 1800.0, 8.0, 200.0, "Few Clouds", 11.0],
	[0.0, 0.0, 1800.0, 8.0, 200.0, "Partly Cloudy", 11.0],
	[0.0, 0.0, 1800.0, 8.0, 20.0, "Mostly Cloudy", 11.0],
	[0.0, 0.0, 1800.0, 8.0, 200.0, "Storm", 11.0],
	[0.0, 0.0, 1800.0, 8.0, 200.0, "Mostly Cloudy", 6.8],
	[0.0, 0.0, 1800.0, 8.0, 200.0, "Mostly Cloudy", 23.0],
	[0.0, 0.0, 2600.0, 3.5, 200.0, "Mostly Cloudy", 10.5],
	[0.0, 0.0, 2600.0, 3.5, 200.0, "Storm", 14.0],
]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	DirAccess.make_dir_recursive_absolute(out)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 90 or frames % 30 != 0:
		return false
	if shot > 0:
		root.get_viewport().get_texture().get_image().save_png("%s/horizon_%d.png" % [out, shot - 1])
	if shot >= shots.size():
		return true
	var s: Array = shots[shot]
	main.sim.weather.set_kind(s[5], 0.0)
	main.day_cycle.set_hour(s[6])
	main.day_cycle.apply(main.day_cycle.hour())
	main.rig.target_pos = Vector3(s[0], 0, s[1])
	main.rig.target_dist = s[2]
	main.rig.target_pitch = deg_to_rad(s[3])
	main.rig.target_yaw = deg_to_rad(s[4])
	main.rig.snap()
	shot += 1
	return false
