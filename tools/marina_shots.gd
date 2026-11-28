extends SceneTree
## Renders a few marinas close up and further out, for checking them by eye.
## godot --path . --resolution 1600x1000 --script tools/marina_shots.gd -- --seed=123
## --out=DIR [--towns=3] [--hours=11,22]

# [where, distance, pitch, yaw offset from inland]
const FRAMES := [
	["mid", 35.0, 0.3, 0.9],
	["mid", 80.0, 0.5, 2.2],
	["centre", 60.0, 0.45, 0.5],
	["centre", 160.0, 0.7, 1.8],
]
const MFRAMES := [[70.0, 0.55, 0.6], [150.0, 0.75, 2.0]]
var main: Node
var frames := 0
var out := "user://"
var towns := 3
var hours: Array[float] = [11.0]
var storm := false
var scene := "res://scenes/sandbox.tscn"
var views: Array = []
var shots := 0
var ready_at := -1
var wait := -1


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
		elif a == "--main":
			scene = "res://scenes/main_map.tscn"
		elif a == "--storm":
			storm = true
	main = load(scene).instantiate()
	root.add_child(main)


func _plan() -> void:
	print("marinas: %d, towns: %d" % [main.map.marinas.size(), main.map.towns.size()])
	var n := 0
	for m: MapData.Marina in main.map.marinas:
		if n >= towns:
			break
		var at: Vector3 = m.shore + m.dir * 30.0
		for h in hours:
			for f in MFRAMES:
				views.append(
					[
						main.map.islands[m.island].name + str(m.id),
						at,
						f[0],
						f[1],
						atan2(m.dir.x, m.dir.z) + f[2],
						h,
						"m"
					]
				)
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
	var tag := (
		"%s_%s_%d_h%d%s"
		% [str(v[0]).to_snake_case(), v[6], int(v[2]), int(v[5] * 10), "_storm" if storm else ""]
	)
	root.get_viewport().get_texture().get_image().save_png(
		"%s/marina_%02d_%s.png" % [out, shots, tag]
	)
	shots += 1
	return false
