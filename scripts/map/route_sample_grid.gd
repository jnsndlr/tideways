extends RefCounted
## Indexes the baked route points used for shoreline placement. Sampling remains
## a caller decision. The grid filters candidates; the final test uses metres.
const CELL := 120.0
var _cells := {}


func add(point: Vector2) -> void:
	var cell := Vector2i((point / CELL).floor())
	if not _cells.has(cell):
		var points: Array[Vector2] = []
		_cells[cell] = points
	_cells[cell].append(point)


func near(point: Vector2, radius: float) -> bool:
	var offset := Vector2(radius, radius)
	var first := Vector2i(((point - offset) / CELL).floor())
	var last := Vector2i(((point + offset) / CELL).floor())
	var limit := radius * radius
	for z in range(first.y, last.y + 1):
		for x in range(first.x, last.x + 1):
			var cell := Vector2i(x, z)
			if _cells.has(cell):
				for sample: Vector2 in _cells[cell]:
					if sample.distance_squared_to(point) < limit:
						return true
	return false
