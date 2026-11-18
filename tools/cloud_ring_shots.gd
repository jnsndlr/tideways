extends SceneTree
## Renders the cloud deck at full zoom-out for each kind of weather (the deck sits
## just under the camera there), plus the default tilt, to compare coverage.
##   godot --path . --resolution 1600x1000 --script tools/cloud_ring_shots.gd -- --out=DIR

var main: Node
var out := "user://"
var frames := 0
var shot := 0
# target x, target z, dist, pitch°, yaw°, weather
var shots := [
	[0.0, 0.0, 4400.0, 80.0, 200.0, "Clear"],
	[0.0, 0.0, 4400.0, 80.0, 200.0, "Few Clouds"],
	[0.0, 0.0, 4400.0, 80.0, 200.0, "Partly Cloudy"],
	[0.0, 0.0, 4400.0, 80.0, 200.0, "Mostly Cloudy"],
	[0.0, 0.0, 4400.0, 80.0, 200.0, "Overcast"],
	[0.0, 0.0, 4400.0, 80.0, 200.0, "Storm"],
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
		root.get_viewport().get_texture().get_image().save_png("%s/ring_%d.png" % [out, shot - 1])
	if shot >= shots.size():
		return true
	var s: Array = shots[shot]
	main.sim.weather.set_kind(s[5], 0.0)
	main.day_cycle.set_hour(10.3)
	main.day_cycle.apply(main.day_cycle.hour())
	main.rig.target_pos = Vector3(s[0], 0, s[1])
	main.rig.target_dist = s[2]
	main.rig.target_pitch = deg_to_rad(s[3])
	main.rig.target_yaw = deg_to_rad(s[4])
	main.rig.snap()
	shot += 1
	return false
