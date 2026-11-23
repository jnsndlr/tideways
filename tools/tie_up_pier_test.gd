extends SceneTree
## Place completed tie-ups through the same WorldBuilder entry point as a purchase.
## Fixtures pin the offset, as Terminal does when adding a slip to either shore side.

var failures := 0


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var town := MapData.Town.new()
	town.name = "Pier test"
	town.shore = Vector3(82, 0, -18)
	town.dock_dir = Vector3.RIGHT
	_add_slip(town, 0.0, false)
	var builder := WorldBuilder.new(MapData.new(), null)
	builder.root = Node3D.new()
	root.add_child(builder.root)
	builder.night_lights = MeshInstance3D.new()
	builder.root.add_child(builder.night_lights)
	_add_slip(town, 60.0, true)
	builder.build_bought_slip(town, 1)
	var old := builder.root.get_node_or_null("Pier test Tie-up Pier") as TieUpPier
	if old == null:
		push_error("Expected the imported timber pier on purchase.")
		builder.root.free()
		quit(1)
		return
	_check(old.transform.is_equal_approx(town.terminal_xform()), "The first purchased pier must use its town's frame.")
	_add_slip(town, 105.0, true)
	builder.build_bought_slip(town, 2)
	var pier := builder.root.get_node("Pier test Tie-up Pier") as TieUpPier
	_check(pier.rows == [37.5, 82.5, 127.5], "Two adjacent berths must share the middle row of dolphins.")
	_check(old.get_parent() == null, "An extended pier must immediately replace its old geometry and colliders.")
	_check(builder.eagle_perches.size() == 3 and builder.night_lights.get_child_count() == 2,
		"Adding the adjacent berth must retain lookouts and lights without duplicating an existing row.")
	_add_slip(town, -60.0, true)
	builder.build_bought_slip(town, 3)
	pier = builder.root.get_node("Pier test Tie-up Pier") as TieUpPier
	_check(pier.rows == [-82.5, -37.5, 37.5, 82.5, 127.5], "A separate berth needs its own two rows of dolphins.")
	var groups := 0
	for kit in pier.get_children():
		if not kit is TieUpPier.Kit:
			continue
		groups += 1
		var reaches_shore := false
		for section in kit._sections:
			_check(signf(section.start.x) == signf(section.end.x), "A timber deck must not pass through the working slip.")
			if section.start.z <= Layout.LOT_FRONT and is_equal_approx(section.start.y, Layout.LOT_Y):
				reaches_shore = absf(section.start.x) <= town.lot_half_width
		_check(reaches_shore, "Each pier's access ramp must reach the shore at lot height.")
	_check(groups == 2, "Working water between tie-ups must split the pier into two groups.")
	await process_frame
	await process_frame
	_check(not is_instance_valid(old), "Replaced pier geometry must be freed.")
	builder.root.free()
	_check_showcase_depth()
	if failures == 0:
		print("TEST PASSED")
	quit(int(failures > 0))


## Both berths in the art review scenario must have water beneath a moored hull.
func _check_showcase_depth() -> void:
	var generator := MapGenerator.new()
	generator.route_cache_path = "res://maps/routes/main_story-tie_up_pier.json"
	var map := generator.generate_from(MapLayout.load_file(MapLayout.MAIN_STORY), Scenario.load_file("res://maps/tie_up_pier.json"))
	for town in map.towns:
		if not town.built or not town.key.begins_with("island-2/") or town.tie_ups().size() != 2:
			continue
		for index in town.tie_ups():
			var lateral := town.slip_offset(index)
			for u in range(36, 120, 6):
				for side in [-8, 0, 8]:
					var p := town.terminal_xform() * Vector3(lateral + side, 0, u)
					if generator.terrain.height_at(p.x, p.z) > -3.6:
						_check(false, "The review scenario places part of a hull on land or in shallow water.")
						return
		return
	_check(false, "Expected two open Madrona tie-ups in the review scenario.")


func _add_slip(town: MapData.Town, offset: float, tie_up: bool) -> void:
	var slip := MapData.Slip.new(1, tie_up)
	slip.v = offset
	town.slips.append(slip)


func _check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
