class_name SnapshotVector3
extends RefCounted
## Three finite components in JSON, in the coordinate space chosen by the record owner.


static func valid(value: Variant) -> bool:
	return (
		value is Array
		and value.size() == 3
		and _scalar(value[0])
		and _scalar(value[1])
		and _scalar(value[2])
		and decode(value).is_finite()
	)


static func encode(value: Vector3) -> Array:
	return [value.x, value.y, value.z]


static func decode(value: Array) -> Vector3:
	return Vector3(value[0], value[1], value[2])


static func _scalar(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value)
