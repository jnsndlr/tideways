extends SceneTree
## Renders the town roads of a few terminal islands close up and further out, by day,
## at dusk, at night and in a storm, for checking roads and their grading by eye.
## Trees are hidden so they don't stand in the way.
##   godot --path . --resolution 1600x1000 --script tools/road_shots.gd -- --seed=123 --out=DIR [--towns=3] [--hours=11,19.5,23] [--storm]

var main: Node
var frames := 0
var out := "user://"
var towns := 3
var hours: Array[float] = [11.0]
var storm := false
var views: Array = []
var shots := 0
var ready_at := -1
var wait := -1
# [where, distance, pitch, yaw offset from inland]
const FRAMES := [
	["mid", 35.0, 0.3, 0.9], ["mid", 80.0, 0.5, 2.2], ["centre", 60.0, 0.45, 0.5], ["centre", 160.0, 0.7, 1.8],
]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--towns="):
			towns = int(a.substr(8))
		elif a.begins_with("--hours="):
			hours.clear()
			for h in a.substr(8).split(","):
				hours.append(float(h))
		elif a == "--storm":
			storm = true
	main = load("res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)


func _plan() -> void:
	var n := 0
	for isl: MapData.Island in main.map.islands:
		if n >= towns or isl.road_main_a.size() < 4:
			continue
		var road := isl.road_main_a
		var mid := road[road.size() / 2]
		var inland := -isl.dock_dir
		for h in hours:
			for f in FRAMES:
				var at: Vector3 = mid if f[0] == "mid" else isl.town_center
				views.append([isl.name, at, f[1], f[2], atan2(inland.x, inland.z) + f[3], h, f[0]])
		n += 1


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("rig") == null or main.get("sim") == null or main.sim.get("weather") == null:
		return false
	if ready_at < 0:
		ready_at = frames
		_plan()
		if storm:
			main.sim.weather.set_kind("Storm", 1.0)
		for c in main.builder.root.get_children():
			if c.name.begins_with("Pines") or c.name.begins_with("RoundTrees"):
				c.visible = false
	if frames - ready_at < 60:
		return false
	if shots >= views.size():
		return true
	var v: Array = views[shots]
	main.sim.minutes = v[5] * 60.0
	main.rig.focus_on(v[1], v[2])
	# The rig pivots at sea level; towns stand on hills.
	main.rig.target_pos = v[1]
	main.rig.position = v[1]
	main.rig.distance = v[2]
	main.rig.target_dist = v[2]
	main.rig.target_pitch = v[3]
	main.rig.pitch = v[3]
	main.rig.target_yaw = v[4]
	main.rig.yaw = v[4]
	if wait < 0:
		wait = frames
	if frames - wait < 40:
		return false
	wait = -1
	var tag := "%s_%s_%d_h%d%s" % [str(v[0]).to_snake_case(), v[6], int(v[2]), int(v[5] * 10), "_storm" if storm else ""]
	root.get_viewport().get_texture().get_image().save_png("%s/road_%02d_%s.png" % [out, shots, tag])
	shots += 1
	return false
