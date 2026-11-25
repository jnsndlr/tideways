extends SceneTree
## Check moving guide geometry, perch placement and outer-dolphin lanterns.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var parts := SlipGuidesView.MeshParts.new()
	var left := SlipGuides.new(0, Transform3D.IDENTITY)
	var terminal := Transform3D(Basis(Vector3.UP, 0.7), Vector3(90, 4, -30))
	var slip_offset := 30.0
	var right := SlipGuides.new(slip_offset, terminal)
	var terminal_node := Node3D.new()
	terminal_node.transform = terminal
	root.add_child(terminal_node)
	root.add_child(left)
	terminal_node.add_child(right)
	left.fit(2)
	right.fit(2)
	var left_view := SlipGuidesView.new(left, null, parts)
	var right_view := SlipGuidesView.new(right, null, parts)
	left.add_child(left_view)
	right.add_child(right_view)
	var failure := check_independence(left, right, left_view, right_view)
	if failure.is_empty():
		failure = check_contacts(right, right_view)
	if failure.is_empty():
		failure = check_perches(right, terminal, slip_offset)
	if failure.is_empty():
		failure = check_lantern_refit(right, terminal_node)
	left.free()
	terminal_node.free()
	if not failure.is_empty():
		push_error(failure)
		quit(1)
		return
	print("TEST PASSED")
	quit(0)


func check_independence(left: SlipGuides, right: SlipGuides, left_view: SlipGuidesView, right_view: SlipGuidesView) -> String:
	var active := left_view.fenders[0]
	var first_face := right.fenders[0].face
	if active.mesh.mesh != right_view.fenders[0].mesh.mesh:
		return "Matching fenders must reuse the same prepared mesh"
	left.walls[0].target = 1
	left.fenders[0].target = 1
	left._process(1)
	if not is_equal_approx(active.mesh.get_blend_shape_value(0), active.peak):
		return "The selected fender must compress"
	var active_wall := left_view.walls[0]
	if not active_wall.travel.position.is_equal_approx(active_wall.full):
		return "The selected wall must compress"
	for view: SlipGuidesView in [left_view, right_view]:
		for f in view.fenders:
			if f != active and not is_zero_approx(f.mesh.get_blend_shape_value(0)):
				return "Compression leaked to another fender"
		for wall in view.walls:
			if wall != active_wall and not wall.travel.position.is_equal_approx(wall.rest):
				return "An idle wall moved"
			for bushing in wall.bushings:
				var expected := wall.peak if wall == active_wall else 0.0
				if not is_equal_approx(bushing.get_blend_shape_value(0), expected):
					return "A bushing did not follow its own wall"
	right.fit(4)
	if right.fenders[0].face <= first_face or right_view.fenders[0].mesh.mesh != active.mesh.mesh:
		return "A refit must place the shared geometry for the new slip size"
	if not is_equal_approx(active.mesh.get_blend_shape_value(0), active.peak):
		return "Refitting one slip changed another fender"
	return ""


func check_contacts(guide: SlipGuides, view: SlipGuidesView) -> String:
	for size in range(1, 6):
		guide.fit(size)
		if view.fenders.size() != guide.fenders.size() or view.fenders.is_empty():
			return "The fitted model must have one live fender for every docking contact"
		for i in view.fenders.size():
			var mesh := view.fenders[i].mesh
			var center := guide.to_local(mesh.to_global(mesh.mesh.get_aabb().get_center()))
			var contact := guide.fenders[i]
			if not is_equal_approx(center.z, contact.u) or signf(center.x) != contact.side:
				return "Fender %d on size %d no longer matches its authored contact position" % [i, size]
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


func check_lantern_refit(guide: SlipGuides, terminal: Node3D) -> String:
	var builder := WorldBuilder.new(MapData.new(), null)
	builder.add_slip_guide_lights(guide)
	var failure := check_lantern_mesh(guide)
	if not failure.is_empty():
		return failure
	var lights: MeshInstance3D = guide.get_node("Lights")
	terminal.hide()
	if lights.is_visible_in_tree():
		return "A hidden terminal must hide its guide lanterns"
	terminal.show()
	if not lights.is_visible_in_tree():
		return "Opening a terminal must reveal its guide lanterns"

	guide.fit(guide.size)
	if guide.get_node_or_null("Lights") != lights:
		return "Fitting the same size must preserve the lanterns"
	guide.fit(2)
	var glow_count := 0
	for part in guide.get_children():
		if part is MeshInstance3D and part.material_override == GlowBuilder.material():
			glow_count += 1
	if glow_count != 1:
		return "Refitting a slip must leave exactly one lantern mesh"
	return check_lantern_mesh(guide)


func check_lantern_mesh(guide: SlipGuides) -> String:
	var lights := guide.get_node_or_null("Lights") as MeshInstance3D
	if not lights or not lights.mesh or lights.material_override != GlowBuilder.material():
		return "A fitted guide needs its lantern glow mesh and material"
	if not lights.top_level or lights.layers != NightLights.LAYER or lights.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
		return "Lanterns use world coordinates and the night-light layer outside the minimap"
	var arrays := lights.mesh.surface_get_arrays(0)
	var positions: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	var params: PackedFloat32Array = arrays[Mesh.ARRAY_CUSTOM0]
	if positions.size() != 16:
		return "Each outer cap needs one lamp quad and one water reflection"
	for i in 2:
		var center := guide.to_global(Models.cage_lantern_glow_at(guide.outer_caps[i], Models.DOLPHIN_LANTERN))
		var first := i * 8
		if not positions[first].is_equal_approx(center) or not positions[first + 4].is_equal_approx(center):
			return "The glow and reflection must be centered above the fitted outer cap"
		if (colors[first].g > colors[first].r) != (i == 0) or colors[first + 4] != colors[first]:
			return "Port lantern and reflection must be green and starboard red"
		for vertex in [first, first + 4]:
			var mode := GlowBuilder.GLOW if vertex == first else GlowBuilder.REFLECT
			if params[vertex * 4 + 1] != mode or not is_equal_approx(params[vertex * 4 + 2], Models.LAMP_ON_AT):
				return "Each lantern and reflection must switch on at the lamp-glass threshold"
	return ""
