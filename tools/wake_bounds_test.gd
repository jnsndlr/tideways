extends SceneTree
## Verify the CPU bounds sent to the water shader for a turning trail, a partial
## group, and overlapping crumbs. Coordinates are already in water-shader units.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var field := WakeField.new()
	field._ready()
	var slot := 3
	var positions := PackedVector2Array([
		Vector2(0, 4), Vector2(1, 7), Vector2(3, 6), Vector2(4, 4),
		Vector2(3, 0), Vector2(1, -1), Vector2(-2, 3), Vector2(-3, 8),
	])
	field._info[slot] = Vector4(130, positions.size(), 30, 0)
	field._hull[slot] = Vector4(4, 20, 1, 1)
	for i in positions.size():
		var pos := positions[i]
		field._pts[slot * WakeField.MAX_POINTS + i] = Vector4(pos.x, pos.y, 130 - 5 * i, i)
	field._pack_segment_bounds(slot, positions.size())
	var first := slot * WakeField.GROUPS_PER_SLOT
	var radii := field._group_radius[first / 4]
	var valid := (field._group_box[first] == Vector4(-2, -1, 4, 7)
			and field._group_box[first + 1] == Vector4(-3, 3, -2, 8))
	# The oldest endpoint is 35 units behind. Half-segment extrapolation can
	# widen its wash another 2.5 units along the trail; the end fade adds 5.5.
	var reach := 1.85 * 4.0 * (0.75 + 0.13 * sqrt(37.5)) + 5.5
	valid = valid and radii.x > 0.0 and radii.y >= reach
	field._pts[slot * WakeField.MAX_POINTS + 7] = field._pts[slot * WakeField.MAX_POINTS + 6]
	field._pack_segment_bounds(slot, positions.size())
	radii = field._group_radius[first / 4]
	valid = valid and radii.x > 0.0 and radii.y < 0.0
	# The vessel at x=12 is outside the right edge of the view. Its trail
	# stays until the last crumb (including the edge margin) clears that edge.
	var planes: Array[Plane] = [Plane(Vector3.RIGHT, 10.0)]
	valid = valid and not WakeField._outside_view(Vector2(5, 0), Vector2(12, 2), planes)
	valid = valid and not WakeField._outside_view(Vector2(11, 0), Vector2(12, 2), planes)
	valid = valid and WakeField._outside_view(Vector2(12, 0), Vector2(20, 2), planes)
	valid = valid and not WakeField._outside_view(Vector2(12, 0), Vector2(20, 2), [])
	valid = _check_repeated_slots() and valid
	field.free()
	if valid:
		print("TEST PASSED")
	else:
		push_error("Wake bounds must retain visible segments, end wash and trails crossing a camera edge.")
	quit(0 if valid else 1)

# Both vessels have identical geometry and coordinates. Reuse is valid only
# for consecutive slots owned by the same instance, even when trails overlap.
func _check_repeated_slots() -> bool:
	var field := WakeField.new()
	var simulation := Simulation.new()
	var traffic := MarineTraffic.new()
	simulation.marine = traffic
	field.sim = simulation
	field.water_mat = ShaderMaterial.new()
	field.water_mat.shader = preload("res://shaders/water.gdshader")
	root.add_child(field)
	var a := Vessel.new()
	var b := Vessel.new()
	for v: Vessel in [a, b]:
		field.add_child(v)
		v.wake = WakeTrail.new(8, 4, 30, 16)
		v.wake.update(0.1, Vector3.ZERO, Vector3.FORWARD, 4, 1, true)
	var valid := true
	for row: Array in [[[a], 0], [[a, b], 0], [[a, a, b], 2], [[a, b, a], 0], [[b, a, a], 4], [[b], 0]]:
		traffic.vessels.assign(row[0])
		field._process(0.0)
		if field.water_mat.get_shader_parameter("wake_repeat_mask") != row[1] or field.water_mat.get_shader_parameter("wake_count") != traffic.vessels.size():
			push_error("Unexpected repeat mask or wake count for slot case %s" % [row])
			valid = false
	field.free()
	simulation.free()
	traffic.free()
	return valid
