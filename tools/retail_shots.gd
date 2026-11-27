extends SceneTree
## Shots of the retail stores in towns: each instance of the named model groups.
##   godot --path . --resolution 1600x1000 --script tools/retail_shots.gd -- --out=DIR [--models=a,b] [--max=4]

var main: Node
var frames := 0
var out := "user://"
var models: PackedStringArray = ["saltwater_grocery"]
var max_shots := 4
var views: Array = []
var shots := 0
var ready_at := -1
var wait := -1
var mark := false


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
		elif a.begins_with("--models="):
			models = a.substr(9).split(",")
		elif a == "--mark":
			mark = true
		elif a.begins_with("--max="):
			max_shots = int(a.substr(6))
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _find(n: Node, name: String, acc: Array) -> void:
	if n.name == name or (name.ends_with("_") and String(n.name).begins_with(name)):
		acc.append(n)
	for c in n.get_children():
		_find(c, name, acc)


func _instances(name: String) -> Array:
	var groups: Array = []
	_find(main, name, groups)
	var xs: Array = []
	for g: Node in groups:
		if name.ends_with("_"):
			xs.append((g as Node3D).global_transform)
			continue
		for mi in g.find_children("*", "MultiMeshInstance3D", true, false):
			var mm: MultiMesh = mi.multimesh
			for i in mm.instance_count:
				xs.append(mi.global_transform * mm.get_instance_transform(i))
		for mi in g.find_children("*", "MeshInstance3D", true, false):
			xs.append(mi.global_transform)
		if g is MeshInstance3D:
			xs.append(g.global_transform)
	return xs


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("rig") == null or main.get("sim") == null or main.get("map") == null:
		return false
	if ready_at < 0:
		ready_at = frames
	if frames - ready_at < 60:
		return false
	if views.is_empty():
		if mark:
			_mark_streets()
		for m in models:
			var xs := _instances(m)
			print("RETAIL ", m, " instances: ", xs.size())
			for i in mini(xs.size(), max_shots):
				var xf: Transform3D = xs[i]
				print("  ", m, " at ", xf.origin)
				var f := xf.basis.z.normalized()
				var yaw := atan2(f.x, f.z)
				views.append(["%s_%d" % [m, i], xf.origin, 110.0, 0.55, yaw])
				views.append(["%s_%d_wide" % [m, i], xf.origin, 300.0, 0.75, yaw + 0.6])
				if mark:
					views.append(["%s_%d_top" % [m, i], xf.origin, 160.0, 1.5, yaw])
		if views.is_empty():
			return true
	if shots >= views.size():
		return true
	var v: Array = views[shots]
	main.sim.minutes = 12 * 60.0
	main.rig.focus_on(v[1], v[2])
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
	root.get_viewport().get_texture().get_image().save_png("%s/%s.png" % [out, v[0]])
	shots += 1
	return false


## Red posts on every big-box lot's street centreline (plan points).
func _mark_streets() -> void:
	for isl in main.map.towns:
		for lot in isl.growth_lots:
			if lot.kind != MapData.TownLot.Kind.BIG_BOX:
				continue
			for q in isl.street_plan.edges[lot.street].pts:
				var mi := MeshInstance3D.new()
				var bm := BoxMesh.new()
				bm.size = Vector3(0.6, 6, 0.6)
				var mat := StandardMaterial3D.new()
				mat.albedo_color = Color(1, 0, 0)
				mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
				bm.material = mat
				mi.mesh = bm
				mi.position = q + Vector3(0, 3, 0)
				main.builder.root.add_child(mi)
