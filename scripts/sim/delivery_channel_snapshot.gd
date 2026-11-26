class_name DeliveryChannelSnapshot
extends RefCounted
## A delivery route is stored from the sea to the berth for either direction.


static func capture(path: NavPath) -> Array:
	var points := []
	for point in path.pts:
		points.append([point.x, point.y])
	return points


static func read(points: Variant, ferry: Ferry, target: Vector3) -> PackedVector2Array:
	if not points is Array or points.size() < 2 or points.size() > 65536:
		return PackedVector2Array()
	var path := PackedVector2Array()
	var bound := (
		ferry.sim.map.half_size
		+ DeliveryTow.EDGE_OUT
		+ DeliveryTow.RUN_IN
		+ DeliveryTow.APPROACH_FAR
	)
	for point in points:
		if (
			not point is Array
			or point.size() != 2
			or not _finite(point[0])
			or not _finite(point[1])
		):
			return PackedVector2Array()
		var p := Vector2(point[0], point[1])
		if not p.is_finite() or absf(p.x) > bound or absf(p.y) > bound:
			return PackedVector2Array()
		path.append(p)
	if not _matches_channel(path, ferry, target):
		return PackedVector2Array()
	return path


## Replan against the rebuilt chart. A corrupt interior waypoint must not send a
## tow through land even when its endpoints still match the booked berth.
static func _matches_channel(path: PackedVector2Array, ferry: Ferry, target: Vector3) -> bool:
	if path[-1].distance_to(Vector2(target.x, target.z)) > 0.5:
		return false
	var endpoint := Vector3(path[-1].x, 0.0, path[-1].y)
	var expected := DeliveryTow.plan(
		ferry.sim, endpoint, ferry.here().town.dock_dir, ferry.fc.half_beam
	)
	if expected.size() != path.size():
		return false
	for index in expected.size():
		if expected[index].distance_to(path[index]) > 0.1:
			return false
	return true


static func _finite(value: Variant) -> bool:
	return (value is float or value is int) and is_finite(value)
