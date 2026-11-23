extends SceneTree
## Shared geometry must still allow one fender or wall to move on one slip.

func _initialize() -> void:
	var parts := SlipGuides.MeshParts.new()
	var left := SlipGuides.new(0, Transform3D.IDENTITY, null, parts)
	var right := SlipGuides.new(30, Transform3D.IDENTITY, null, parts)
	left.fit(2)
	right.fit(2)
	var failure := check_independence(left, right)
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
