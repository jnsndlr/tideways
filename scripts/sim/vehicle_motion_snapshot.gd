class_name VehicleMotionSnapshot
extends RefCounted
## Remaining rounded road or deck path, including the articulated trailer pose.


static func capture(car: Vehicle) -> Dictionary:
	var motion := car.drive_motion()
	motion.position = SnapshotVector3.encode(car.position)
	motion.rotation = SnapshotVector3.encode(car.rotation)
	var points := []
	for point in car.path:
		points.append(SnapshotVector3.encode(point))
	motion.path = points
	motion.axle = SnapshotVector3.encode(motion.axle)
	return motion


static func restore(data: Variant, car: Vehicle) -> bool:
	if not data is Dictionary:
		return false
	var motion := _decode_motion(data)
	if motion.is_empty():
		return false
	car.position = SnapshotVector3.decode(data.position)
	car.rotation = SnapshotVector3.decode(data.rotation)
	car.restore_drive_motion(motion)
	return true


static func _decode_motion(data: Dictionary) -> Dictionary:
	for name in ["delay", "held", "creep", "body_pitch", "reach", "trailer_yaw"]:
		if not _scalar(data.get(name)):
			return {}
	if (
		not SnapshotVector3.valid(data.get("position"))
		or not SnapshotVector3.valid(data.get("rotation"))
	):
		return {}
	if (
		not SnapshotVector3.valid(data.get("axle"))
		or data.reach < 0
		or not data.get("path") is Array
		or data.path.is_empty()
	):
		return {}
	var points := PackedVector3Array()
	for point in data.path:
		if not SnapshotVector3.valid(point):
			return {}
		points.append(SnapshotVector3.decode(point))
	var motion := data.duplicate()
	motion.path = points
	motion.axle = SnapshotVector3.decode(data.axle)
	return motion


static func _scalar(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)
