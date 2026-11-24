extends SceneTree

var polls := 0
var cancel_at := 0


func _initialize() -> void:
	var land := PackedByteArray([
		0, 0, 1,
		0, 0, 0,
		1, 0, 0,
	])
	var cell := 3.0
	var diagonal := sqrt(2.0) * cell
	var expected := [6.0, cell, 0.0, cell, diagonal, cell, 0.0, cell, 6.0]
	var distances := LandDistanceField.compute(land, 3, cell)
	if distances.size() != expected.size():
		fail("Unexpected number of distances")
		return
	for i in expected.size():
		if not is_equal_approx(distances[i], expected[i]):
			fail("Cell %d: expected %s, got %s" % [i, expected[i], distances[i]])
			return
	if LandDistanceField.compute(PackedByteArray([0]), 1, cell) != PackedFloat32Array([INF]):
		fail("Open water without land should have infinite clearance")
		return
	# Stop during each sweep, before a partial grid can reach either caller.
	for stop: int in [1, 2, 5]:
		polls = 0
		cancel_at = stop
		if not LandDistanceField.compute(land, 3, cell, should_stop).is_empty() or polls != stop:
			fail("Cancellation failed at row poll %d" % stop)
			return
	print("TEST PASSED")
	quit(0)


func should_stop() -> bool:
	polls += 1
	return polls == cancel_at


func fail(message: String) -> void:
	push_error(message)
	quit(1)
