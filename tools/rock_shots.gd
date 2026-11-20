extends SceneTree
## Renders a few steep shores from the sea, close and further out, for checking the
## shore rocks by eye.
##   godot --path . --resolution 1600x1000 --script tools/rock_shots.gd -- --out=DIR [--time=11.0]

var main: Node
var frames := 0
var out := "user://"
var hour := 11.0
var shots := 0
var ready_at := -1
# [position, seaward direction]
var spots: Array = []
var spots_meadow := Vector3.ZERO
# [distance, pitch]
const VIEWS := [[55.0, 0.18], [130.0, 0.35], [380.0, 0.55]]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--time="):
			hour = float(a.substr(7))
	main = load("res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)


## Steep shores at the waterline, away from docks and towns and from each other.
func _find_spots() -> void:
	var b: WorldBuilder = main.builder
	var t: Terrain = main.terrain
	var vn := t.n + 1
	var found: Array = []
	for j in range(60, vn - 60, 3):
		for i in range(60, vn - 60, 3):
			var h := t.h_grid[j * vn + i]
			if h < 0.5 or h > 4.0:
				continue
			var gx := t.h_grid[j * vn + i + 2] - t.h_grid[j * vn + i - 2]
			var gz := t.h_grid[(j + 2) * vn + i] - t.h_grid[(j - 2) * vn + i]
			var g := sqrt(gx * gx + gz * gz) / (4.0 * Terrain.CELL)
			var p := Vector3(-t.half_size + i * Terrain.CELL, h, -t.half_size + j * Terrain.CELL)
			if g > 1.0 and not b._is_blocked(p.x, p.z):
				found.append([g, p, Vector3(-gx, 0, -gz).normalized()])
	found.sort_custom(func(a, c): return a[0] > c[0])
	for f in found:
		var far := true
		for s in spots:
			if (s[0] as Vector3).distance_to(f[1]) < 600.0:
				far = false
		if far:
			spots.append([f[1], f[2]])
		if spots.size() >= 3:
			break
	# And the most open field, for the grass.
	var best := -1.0
	for j in range(60, vn - 60, 4):
		for i in range(60, vn - 60, 4):
			var k := j * vn + i
			var p := Vector3(-t.half_size + i * Terrain.CELL, t.h_grid[k], -t.half_size + j * Terrain.CELL)
			var g := float(b.ground_rgba[k * 4 + 3]) / 255.0 * b.field_at(p.x, p.z)
			if g > best:
				best = g
				spots_meadow = p
	spots.append([spots_meadow, Vector3(1, 0, 0)])
	print("rock spots ", spots)


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("rig") == null or main.get("sim") == null or main.sim.get("weather") == null:
		return false
	if ready_at < 0:
		ready_at = frames
		_find_spots()
	if frames - ready_at < 60:
		return false
	main.sim.minutes = hour * 60.0
	if shots >= spots.size() * VIEWS.size():
		return true
	var s: Array = spots[shots / VIEWS.size()]
	var v: Array = VIEWS[shots % VIEWS.size()]
	var p: Vector3 = s[0]
	var o: Vector3 = s[1]
	main.rig.focus_on(p, v[0])
	main.rig.distance = v[0]
	main.rig.target_dist = v[0]
	main.rig.target_pitch = v[1]
	main.rig.pitch = v[1]
	# Looking in from the sea, a little off square.
	var yaw := atan2(o.x, o.z) + 0.5
	main.rig.target_yaw = yaw
	main.rig.yaw = yaw
	if not has_meta("wait"):
		set_meta("wait", frames)
	if frames - int(get_meta("wait")) < 40:
		return false
	remove_meta("wait")
	root.get_viewport().get_texture().get_image().save_png("%s/rocks_%d_%d.png" % [out, shots / VIEWS.size(), int(v[0])])
	shots += 1
	return false
