class_name RoadGeometry
extends RefCounted
## Shared dimensions and measurements of town roads, in metres.

const HALF_WIDTH := 5.1


## Horizontal length of a polyline.
static func length_of(points: PackedVector3Array) -> float:
	var total := 0.0
	for i in points.size() - 1:
		total += Vector2(points[i + 1].x - points[i].x, points[i + 1].z - points[i].z).length()
	return total
