extends SceneTree
## Check moving guide geometry and the bird seats on its fixed dolphins.

func _initialize() -> void:
	var parts := SlipGuides.MeshParts.new()
	var left := SlipGuides.new(0, Transform3D.IDENTITY, null, parts)
	var terminal := Transform3D(Basis(Vector3.UP, 0.7), Vector3(90, 4, -30))
	var slip_offset := 30.0
	var right := SlipGuides.new(slip_offset, terminal, null, parts)
	left.fit(2)
	right.fit(2)
	var failure := check_independence(left, right)
	if failure.is_empty():
		failure = check_perches(right, terminal, slip_offset)
	left.free()
	right.free()
	if not failure.is_empty():
		push_error(failure)
		quit(1)
		return
	print("TEST PASSED")
	quit(0)


func check_independence(left: SlipGuides, right: SlipGuides) -> String:
	var active := left.fenders[0]
	var other := right.fenders[0]
	if active.mesh.mesh != other.mesh.mesh:
		return "Matching fenders must reuse the same prepared mesh"
	left.walls[0].target = 1
	active.target = 1
	left._process(1)
	if active.mesh.get_blend_shape_value(0) <= 0 or not left.walls[0].travel.position.is_equal_approx(left.walls[0].full):
		return "The selected fender and wall must compress"
	for guide in [left, right]:
		for f: SlipGuides.Fender in guide.fenders:
			if f != active and not is_zero_approx(f.mesh.get_blend_shape_value(0)):
				return "Compression leaked to another fender"
		for wall: SlipGuides.Wall in guide.walls:
			if wall != left.walls[0] and not wall.travel.position.is_equal_approx(wall.rest):
				return "An idle wall moved"
			for bushing in wall.bushings:
				var expected := wall.peak if wall == left.walls[0] else 0.0
				if not is_equal_approx(bushing.get_blend_shape_value(0), expected):
					return "A bushing did not follow its own wall"
	right.fit(4)
	if right.fenders[0].face <= other.face or right.fenders[0].mesh.mesh != active.mesh.mesh:
		return "A refit must place the shared geometry for the new slip size"
	if not is_equal_approx(active.mesh.get_blend_shape_value(0), active.peak):
		return "Refitting one slip changed another fender"
	return ""


func check_perches(guide: SlipGuides, terminal: Transform3D, slip_offset: float) -> String:
	var builder := WorldBuilder.new(MapData.new(), null)
	var lamp := Seagulls.Perch.new(Vector3.ZERO, Vector3.ZERO, 0.0, Seagulls.Kind.LAMP)
	var tree := Eagles.Perch.new(Vector3.ZERO, Eagles.Kind.TREE)
	builder.gull_perches.append(lamp)
	builder.eagle_perches.append(tree)
	builder.add_slip_perches(guide)
	if builder.gull_perches.size() != 13 or builder.eagle_perches.size() != 3:
		return "A slip adds twelve gull seats and two eagle seats"
	if builder.gull_perches[0] != lamp or builder.eagle_perches[0] != tree:
		return "Adding a slip must preserve the order of existing world perches"

	# Three single-gull seats per cap, inner dolphins first, then outer.
	var caps := guide.inner_caps + guide.outer_caps
	for i in caps.size():
		var center: Vector3 = caps[i] + Vector3.RIGHT * slip_offset
		for j in 3:
			var expected := terminal * (center + Vector3.BACK * ((j - 1) * 1.6))
			var gull := builder.gull_perches[1 + 3 * i + j]
			if not gull.a.is_equal_approx(expected) or not gull.b.is_equal_approx(expected):
				return "Gull seats must follow the cap order and the rotated slip axis"
			if gull.kind != Seagulls.Kind.DOLPHIN or gull.spread != 0.0 or gull.capacity != 1:
				return "Each guide seat must be a single dolphin perch"
		if i < guide.inner_caps.size():
			var eagle := builder.eagle_perches[1 + i]
			if not eagle.at.is_equal_approx(terminal * center):
				return "Eagle seats must follow the inner cap centers"
			if eagle.kind != Eagles.Kind.DOLPHIN or not is_nan(eagle.look):
				return "An eagle can face any direction at the center of each inner cap"
	return ""
