extends SceneTree
## The forest loop follows the nearest tree crown even across grid cells and on hills.

func _initialize() -> void:
	var builder := WorldBuilder.new(MapData.new(), null)
	builder._add_tree_cell(Vector3(-1, 120, -1))
	builder._add_tree_cell(Vector3(10, 50, 5))
	var camera := Vector3(2, 124, 3)
	var reach := 100.0
	if not is_equal_approx(builder.nearest_tree_distance(camera, reach), 5.0):
		push_error("Expected the nearest crown across the negative grid boundary.")
		quit(1)
		return
	camera.y = 280.0
	if not is_equal_approx(builder.nearest_tree_distance(camera, 200.0), camera.distance_to(Vector3(-1, 124, -1))):
		push_error("A camera above a forested hillside should still hear the trees within reach.")
		quit(1)
		return
	if builder.nearest_tree_distance(camera, 50.0) != INF:
		push_error("The forest should be silent above its audible range.")
		quit(1)
		return
	print("TEST PASSED")
	quit(0)
