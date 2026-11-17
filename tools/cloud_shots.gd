extends SceneTree
## Renders the cloud deck over Port Rosario for each weather's base coverage, from the
## default play angle and a high wide view, to check cloud shape and how much sky is clear.
##   godot --path . --resolution 1600x1000 --script tools/cloud_shots.gd -- --out=DIR

var main: Node
var out := "user://"
var frames := 0
var shot := 0
# weather, hour, dist, pitch°, yaw°
var shots := [
	["Sunny", 11.0, 1500.0, 54.0, 200.0],
	["Light Breeze", 11.0, 1500.0, 54.0, 200.0],
	["Partly Cloudy", 11.0, 1500.0, 54.0, 200.0],
	["Overcast", 11.0, 1500.0, 54.0, 200.0],
	["Partly Cloudy", 11.0, 3600.0, 70.0, 200.0],
	["Partly Cloudy", 18.8, 1800.0, 38.0, 270.0],
	["Partly Cloudy", 11.0, 4400.0, 22.0, 200.0],
	["Overcast", 11.0, 4400.0, 22.0, 200.0],
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
	if frames >= 20 and frames % 25 == 0:
		if shot > 0:
			var s0: Array = shots[shot - 1]
			root.get_viewport().get_texture().get_image().save_png("%s/clouds_%d_%s.png" % [out, shot - 1, String(s0[0]).replace(" ", "_")])
		if shot >= shots.size():
			return true
		var s: Array = shots[shot]
		main.day_cycle.set_hour(s[1])
		main.day_cycle.apply(main.day_cycle.hour())
		RenderingServer.global_shader_parameter_set("cloud_coverage", CloudLayer.COVERAGE[s[0]])
		main.rig.target_pos = Vector3(2900, 0, -50)
		main.rig.target_dist = s[2]
		main.rig.target_pitch = deg_to_rad(s[3])
		main.rig.target_yaw = deg_to_rad(s[4])
		main.rig.snap()
		shot += 1
	return false
