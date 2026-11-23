extends SceneTree
## A shoreline search must find samples in neighbouring and negative cells,
## with the same strict clearance threshold as a linear scan.

func _initialize() -> void:
	var grid := MapGenerator.RouteSampleGrid.new()
	var points := [Vector2(-120, -120), Vector2(-0.1, 120.1), Vector2(240, 241)]
	for point in points:
		grid.add(point)
	for x in range(-300, 501, 10):
		for z in range(-300, 402, 20):
			var at := Vector2(x, z)
			for radius: float in [5.0, 102.0, 120.0, 241.0]:
				var expected := points.any(func(p: Vector2): return p.distance_squared_to(at) < radius * radius)
				if expected != grid.near(at, radius):
					push_error("Route proximity mismatch at %s with radius %s" % [at, radius])
					quit(1)
					return
	print("TEST PASSED")
	quit(0)
