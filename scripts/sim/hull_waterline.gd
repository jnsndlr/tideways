class_name HullWaterline
extends RefCounted
## A profile stores the bow offset and waterline length, followed by half-widths
## in metres sampled evenly from bow to stern.

const STATIONS := 24


static func from_shape(hull: Vector4, shape: Vector4) -> PackedFloat32Array:
	var out := PackedFloat32Array([0.0, hull.y])
	for i in STATIONS:
		var fb := i / float(STATIONS - 1) * hull.y
		var bu := clampf(1.0 - fb / shape.x, 0.0, 1.0)
		var su := clampf(1.0 - (hull.y - fb) / maxf(shape.z, 0.1), 0.0, 1.0)
		out.append(hull.x * lerpf(1.0, shape.y, pow(bu, 2.5)) * lerpf(1.0, shape.w, su * su))
	return out
