extends SceneTree
## Renders the ground close up and further out: a grassy meadow (with its grass
## blades) and the steepest cliff, for checking the ground detail and grass by eye.
##   godot --path . --resolution 1600x1000 --script tools/ground_shots.gd -- --out=DIR [--time=11.0]

var main: Node
var frames := 0
var out := "user://"
var hour := 11.0
var shots := 0
## --only=beach,town: just those spots' views.
var only := ""
var ready_at := -1
var spots := {}
## Downhill from the inland rock, to look at it from below.
var crag_out := Vector3(1, 0, 0)
## Out to sea from each beach spot, to look at it from the water.
var beach_out := {}
# [spot, distance, pitch, yaw]
const VIEWS := [
	["meadow", 45.0, 0.22, 0.4], ["meadow", 90.0, 0.4, 0.4], ["meadow", 260.0, 0.6, 1.4], ["meadow", 900.0, 0.8, 1.4],
	["cliff", 70.0, 0.15, 0.0], ["cliff", 160.0, 0.3, 0.0], ["cliff", 420.0, 0.6, 0.0],
	["town", 70.0, 0.35, 0.8], ["town", 140.0, 0.5, 2.4], ["town", 320.0, 0.6, 1.6],
	["boulders", 25.0, 0.35, 0.5], ["boulders", 60.0, 0.5, 0.5], ["boulders", 140.0, 0.65, 0.5],
	["crag", 60.0, 0.45, 0.3], ["crag", 140.0, 0.6, 0.3], ["crag", 300.0, 0.7, 0.3],
	["beach", 50.0, 0.3, 0.4], ["beach", 140.0, 0.5, 0.4], ["shore_beach", 140.0, 0.5, 0.4],
	["town_beach", 260.0, 0.55, 0.0],
]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--only="):
			only = a.substr(7)
		elif a.begins_with("--time="):
			hour = float(a.substr(7))
	main = load("res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)


## The grassiest vertex with grass all round it, and the steepest tall cliff, on
## the islands (away from the map's edge).
func _find_spots() -> void:
	var b: WorldBuilder = main.builder
	var t: Terrain = main.terrain
	var vn := t.n + 1
	var best_g := -1.0
	var best_c := -1.0
	var best_k := -1.0
	var towns: Array = main.sim.terminals.values().map(func(n): return (n as Node3D).global_position)
	for j in range(40, vn - 40, 3):
		for i in range(40, vn - 40, 3):
			var k := j * vn + i
			var h := t.h_grid[k]
			if h < 2.0:
				continue
			var g := 0.0
			for o in [-24, -12, 0, 12, 24]:
				g += b.ground_rgba[(k + o) * 4 + 3] + b.ground_rgba[(k + o * vn) * 4 + 3]
			if g > best_g:
				best_g = g
				spots["meadow"] = Vector3(-t.half_size + i * Terrain.CELL, h, -t.half_size + j * Terrain.CELL)
			var drop := maxf(absf(h - t.h_grid[k + 2]), absf(h - t.h_grid[k + 2 * vn]))
			if drop > best_c:
				best_c = drop
				spots["cliff"] = Vector3(-t.half_size + i * Terrain.CELL, h * 0.5, -t.half_size + j * Terrain.CELL)
			# Inland rock: the most open, rockiest patch well above the sea.
			var cp := Vector3(-t.half_size + i * Terrain.CELL, h, -t.half_size + j * Terrain.CELL)
			if h > 25.0 and (j - 40) % 6 == 0 and (i - 40) % 6 == 0 and b.field_at(cp.x, cp.z) > 0.3 \
					and towns.all(func(tp): return Vector2(tp.x - cp.x, tp.z - cp.z).length() > 350.0):
				var steep := 0
				for dj in range(-8, 9, 2):
					for di in range(-8, 9, 2):
						var kk := k + dj * vn + di
						if absf(t.h_grid[kk + 1] - t.h_grid[kk - 1]) + absf(t.h_grid[kk + vn] - t.h_grid[kk - vn]) > 2.6 * Terrain.CELL:
							steep += 1
				if steep > best_k:
					best_k = steep
					spots["crag"] = cp
					crag_out = Vector3(t.h_grid[k - 2] - t.h_grid[k + 2], 0.0, t.h_grid[k - 2 * vn] - t.h_grid[k + 2 * vn]).normalized()
	var term: Node3D = main.sim.terminals.values()[0]
	spots["town"] = term.global_position + Vector3(0.0, 0.0, 0.0)
	# The thickest scatter of land boulders (Models.rock) above the beach.
	var best_b := -1
	for tile in main.builder.root.get_node("Rocks").get_children():
		if tile is MultiMeshInstance3D:
			var mm: MultiMesh = tile.multimesh
			var near := 0
			var at := Vector3.ZERO
			for q in range(0, mm.instance_count, 7):
				var o: Vector3 = tile.global_transform * mm.get_instance_transform(q).origin
				if o.y < 6.0:
					continue
				var c := 0
				for q2 in mm.instance_count:
					if (tile.global_transform * mm.get_instance_transform(q2).origin).distance_to(o) < 15.0:
						c += 1
				if c > near:
					near = c
					at = o
			if near > best_b:
				best_b = near
				spots["boulders"] = at
	# A beach beside a ferry lot, and one out on an island's own shore.
	# (The one beside the first terminal, with the lot in view too.)
	var near_t := INF
	for bch: MapData.Beach in main.map.beaches:
		var key := "beach" if bch.beside else "shore_beach"
		var d := bch.shore.distance_to(spots["town"]) if bch.beside else 0.0
		if not spots.has(key) or d < near_t:
			spots[key] = bch.shore
			beach_out[key] = bch.dir
			if bch.beside:
				near_t = d
				spots["town_beach"] = (bch.shore + spots["town"]) * 0.5
				beach_out["town_beach"] = bch.dir
	if not spots.has("crag"):
		spots["crag"] = spots["cliff"]
	print("spots ", spots, " beaches ", main.map.beaches.size(), " beside ", main.map.beaches.filter(func(x): return x.beside).size())


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
	if shots >= VIEWS.size():
		return true
	var v: Array = VIEWS[shots]
	# Trees out of the way for the inland rock, which is mostly under them.
	for c in main.builder.root.get_children():
		if c.name.begins_with("Pines") or c.name.begins_with("RoundTrees"):
			c.visible = v[0] != "crag" and v[0] != "boulders"
	main.rig.focus_on(spots[v[0]], v[1])
	main.rig.distance = v[1]
	main.rig.target_dist = v[1]
	main.rig.target_pitch = v[2]
	main.rig.pitch = v[2]
	var yaw: float = v[3]
	if v[0] == "crag":
		yaw = atan2(crag_out.x, crag_out.z) + v[3]
	if beach_out.has(v[0]):
		yaw = atan2(beach_out[v[0]].x, beach_out[v[0]].z) + v[3]
	if not spots.has(v[0]) or (only != "" and not v[0] in only.split(",")):
		shots += 1
		return false
	main.rig.target_yaw = yaw
	main.rig.yaw = yaw
	if not has_meta("wait"):
		set_meta("wait", frames)
	if frames - int(get_meta("wait")) < 40:
		return false
	remove_meta("wait")
	root.get_viewport().get_texture().get_image().save_png("%s/ground_%d_%s_%d.png" % [out, shots, v[0], int(v[1])])
	shots += 1
	return false
