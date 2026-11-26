class_name VehicleMotionSnapshot
extends RefCounted
## Remaining rounded road or deck path, including the articulated trailer pose.


static func capture(car: Vehicle) -> Dictionary:
	var motion := car.drive_motion()
	motion.position = _xyz(car.position)
	motion.rotation = _xyz(car.rotation)
	var points := []
	for point in car.path:
		points.append(_xyz(point))
	motion.path = points
	motion.axle = _xyz(motion.axle)
	return motion


static func restore(data: Variant, car: Vehicle) -> bool:
	if not data is Dictionary:
		return false
	var motion := _decode_motion(data)
	if motion.is_empty():
		return false
	car.position = _vec(data.position)
	car.rotation = _vec(data.rotation)
	car.restore_drive_motion(motion)
	return true


static func _decode_motion(data: Dictionary) -> Dictionary:
	for name in ["delay", "held", "creep", "body_pitch", "reach", "trailer_yaw"]:
		if not _scalar(data.get(name)):
			return {}
	if not _point(data.get("position")) or not _point(data.get("rotation")):
		return {}
	if (
		not _point(data.get("axle"))
		or data.reach < 0
		or not data.get("path") is Array
		or data.path.is_empty()
	):
		return {}
	var points := PackedVector3Array()
	for point in data.path:
		if not _point(point):
			return {}
		points.append(_vec(point))
	var motion := data.duplicate()
	motion.path = points
	motion.axle = _vec(data.axle)
	return motion


static func _scalar(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)


static func _point(value: Variant) -> bool:
	return (
		value is Array
		and value.size() == 3
		and _scalar(value[0])
		and _scalar(value[1])
		and _scalar(value[2])
		and _vec(value).is_finite()
	)


static func _xyz(value: Vector3) -> Array:
	return [value.x, value.y, value.z]


static func _vec(value: Array) -> Vector3:
	return Vector3(value[0], value[1], value[2])
