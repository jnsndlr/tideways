extends SceneTree
## Headless check for vehicles driving into each other: runs a map at 4x and counts
## pairs of vehicles (bumper-to-tail capsules a car wide) that overlap, printing a NEW
## line for each model pair, consecutive contacts for actual vehicles, and any vehicle
## held still for 150 checks. Add --mesh-contacts to probe rendered surfaces.
##
##   godot --headless --path . --fixed-fps 30 \
##     --script tests/traffic/vehicle_overlap_test.gd -- --seed=123 --frames=6000

const ContactSamples := preload("res://tests/traffic/vehicle_contact_samples.gd")
const HALF_W := 0.9

var main: Node
var frames := 0
var max_frames := 6000
var pairs := {}
var proximity := ContactSamples.new()
var surfaces := ContactSamples.new()
var check_surfaces := false
var worst := 0.0
var vehicles_seen := 0
var _last_pos := {}
var _still := {}
var stalls := 0


func _initialize() -> void:
	check_surfaces = "--mesh-contacts" in OS.get_cmdline_user_args()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--frames="):
			max_frames = int(a.substr(9))
	main = load("res://scenes/sandbox.tscn").instantiate()
	root.add_child(main)


func _collect(n: Node, out: Array) -> void:
	for c in n.get_children():
		if c is Vehicle:
			out.append(c)
		elif c is Node3D:
			_collect(c, out)


func _process(_delta: float) -> bool:
	frames += 1
	if frames == 5:
		Engine.time_scale = 4.0
	if frames >= max_frames:
		print("stalls %d" % stalls)
		print(
			(
				"vehicles max %d, overlapping pairs %d, pair-frames %d, worst depth %.2f"
				% [vehicles_seen, pairs.size(), proximity.observations, worst]
			)
		)
		var lasting := 0
		for p in pairs.keys():
			if pairs[p] >= 4:
				lasting += 1
				print("  ", p, " x", pairs[p])
		print("model-pair labels with >= 4 observations %d" % lasting)
		_report_episodes("proximity", proximity)
		if check_surfaces:
			_report_episodes("mesh surface", surfaces)
		if "--verify" in OS.get_cmdline_user_args():
			if stalls > 0 or vehicles_seen == 0:
				push_error("Expected traffic to run without stalled vehicles")
				quit(1)
				return false
			print("TEST PASSED")
		return true
	if frames % 5 != 0:
		return false
	proximity.begin_sample()
	if check_surfaces:
		surfaces.begin_sample()
	var vs: Array = []
	_collect(main.sim, vs)
	vehicles_seen = maxi(vehicles_seen, vs.size())
	for v: Vehicle in main.sim.moving_vehicles:
		var p := v.global_position
		if _last_pos.has(v) and p.distance_to(_last_pos[v]) < 0.01 and v.delay <= 0.0:
			_still[v] = _still.get(v, 0) + 1
			if _still[v] == 150:
				stalls += 1
				var why := ""
				for o: Vehicle in main.sim.moving_vehicles:
					if o != v and v._room_to(o) < 0.5:
						why += " %s(%s leader=%s d=%.1f fwd·=%.2f)" % [o.model, o.global_position, o == v.leader, o.global_position.distance_to(p), o._g_fwd.dot(v._g_fwd)]
				print("STALL %s at %s path %d blocked by:%s" % [v.model, p, v.path.size(), why])
		else:
			_still[v] = 0
		_last_pos[v] = p
	var seg := []
	for v: Vehicle in vs:
		var f := v._front()
		var t := v._tail()
		# (Pulled in by the half-width at each end: the capsule then ends at the bumpers.)
		var a := Vector2(f.x, f.z)
		var b := Vector2(t.x, t.z)
		var d := (b - a).normalized() * HALF_W
		seg.append([a + d, b - d, (f.y + t.y) * 0.5])
	for i in vs.size():
		for j in range(i + 1, vs.size()):
			if absf(seg[i][2] - seg[j][2]) > 1.5:
				continue
			if seg[i][0].distance_to(seg[j][0]) > 60.0:
				continue
			var cp := Geometry2D.get_closest_points_between_segments(seg[i][0], seg[i][1], seg[j][0], seg[j][1])
			var d: float = cp[0].distance_to(cp[1])
			if d < 2.0 * HALF_W:
				var a: Vehicle = vs[i]
				var b: Vehicle = vs[j]
				var key := "%s(%s)/%s(%s)" % [a.model, "m" if a.is_processing() else "p", b.model, "m" if b.is_processing() else "p"]
				if not pairs.has(key):
					var rel := Vector2(b.global_position.x - a.global_position.x, b.global_position.z - a.global_position.z)
					var fa := Vector2(a.global_transform.basis.z.x, a.global_transform.basis.z.z).normalized()
					print("NEW %s  in %s/%s  along %.1f lat %.1f  len %.1f/%.1f  slots %d/%d  leader %s  path %d/%d" % [key, a.get_parent().name, b.get_parent().name,
						rel.dot(fa), rel.cross(fa), a.length, b.length, a.slots, b.slots, a.leader == b or b.leader == a, a.path.size(), b.path.size()])
				pairs[key] = pairs.get(key, 0) + 1
				var a_id := a.get_instance_id()
				var b_id := b.get_instance_id()
				if proximity.record(a_id, b_id) == ContactSamples.LASTING:
					print("SUSTAINED frame %d %s ids %d/%d" % [frames, key, a_id, b_id])
				if check_surfaces:
					var hit := ContactSamples.surfaces_intersect(a, b)
					if hit:
						surfaces.record(a_id, b_id)
					print(
						"SURFACES frame %d %s ids %d/%d contact %s" % [frames, key, a_id, b_id, hit]
					)
				worst = maxf(worst, 2.0 * HALF_W - d)
	return false


func _report_episodes(label: String, samples: ContactSamples) -> void:
	print(
		(
			"%s observations %d, episodes >= %d consecutive samples %d, longest %d"
			% [
				label,
				samples.observations,
				ContactSamples.LASTING,
				samples.lasting_episodes,
				samples.longest
			]
		)
	)
