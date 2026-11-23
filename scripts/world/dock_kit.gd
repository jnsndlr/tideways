extends Node3D

## Local coordinates in metres. Start at the middle of a deck edge.
## Directions use the XZ plane. Each call returns the far edge for chaining.
enum Width { MAIN, FINGER }
enum Support { FLOATS, PILES }

const RUN := 6.0
const MAIN_WIDTH := 4.0
const FINGER_WIDTH := 2.0
const LOW := 0.48
const HIGH := 1.98
const CLEAT := "res://assets/models/dock_kit/cleat.glb"
const PIECES := [
	["res://assets/models/dock_kit/main_deck.glb", "res://assets/models/dock_kit/main_floats.glb", "res://assets/models/dock_kit/main_piles.glb", "res://assets/models/dock_kit/main_ramp.glb"],
	["res://assets/models/dock_kit/finger_deck.glb", "res://assets/models/dock_kit/finger_floats.glb", "res://assets/models/dock_kit/finger_piles.glb", "res://assets/models/dock_kit/finger_ramp.glb"],
]


# Keep endpoints so a branch can be assembled before or after its main dock.
class Section:
	var start: Vector3
	var end: Vector3
	var forward: Vector3
	var half_width: float
	var cleats: Node3D

	func has_side_connection(other: Section) -> bool:
		if absf(forward.dot(other.forward)) > 0.999:
			return false
		var right := forward.cross(Vector3.UP)
		for point: Vector3 in [other.start, other.end]:
			var offset := point - start
			var along := offset.dot(forward)
			if absf(offset.y) < 0.01 and along >= -0.01 and along <= RUN + 0.01:
				if absf(absf(offset.dot(right)) - half_width) < 0.01:
					return true
		return false


var _sections: Array[Section] = []
var _pieces := {}


static func available() -> bool:
	if not ResourceLoader.exists(CLEAT, "PackedScene"):
		return false
	for width in PIECES:
		for path: String in width:
			if not ResourceLoader.exists(path, "PackedScene"):
				return false
	return true


## Hold a copy of each resource used by this assembly while placing its sections.
func _piece(path: String) -> Node3D:
	if not _pieces.has(path):
		_pieces[path] = load(path)
	return (_pieces[path] as PackedScene).instantiate()


func add_deck(width: Width, start: Vector3, direction: Vector2, support: Support) -> Vector3:
	var end := _place(width, start, direction, start.y, false)
	if end != start:
		var foundation: Node3D = _piece(PIECES[width][1 + support])
		add_child(foundation)
		foundation.transform = Transform3D(Basis.looking_at(end - start), start)
	return end


func add_ramp(width: Width, start: Vector3, direction: Vector2, end_height: float) -> Vector3:
	return _place(width, start, direction, end_height, true)


func _place(width: Width, start: Vector3, direction: Vector2, end_height: float, ramp: bool) -> Vector3:
	if direction.is_zero_approx():
		push_error("Dock direction must have a horizontal heading.")
		return start
	var forward := Vector3(direction.x, 0, direction.y).normalized()
	var rise := end_height - start.y
	var model: Node3D = _piece(PIECES[width][3 if ramp else 0])
	add_child(model)
	# Shearing the level ramp keeps the posts plumb and the projected run fixed.
	model.transform = Transform3D(Basis(forward.cross(Vector3.UP), Vector3.UP,
		-forward - Vector3.UP * rise / RUN), start)

	var half_width := (MAIN_WIDTH if width == Width.MAIN else FINGER_WIDTH) / 2
	var points := PackedVector3Array()
	for x in [-half_width, half_width]:
		for depth in [0.0, -0.18]:
			points.append(Vector3(x, depth, 0))
			points.append(Vector3(x, rise + depth, -RUN))
	var hull := ConvexPolygonShape3D.new()
	hull.points = points
	var collider := CollisionShape3D.new()
	collider.shape = hull
	var body := StaticBody3D.new()
	body.add_child(collider)
	add_child(body)
	body.transform = Transform3D(Basis.looking_at(forward), start)
	var section := Section.new()
	section.start = start
	section.end = start + forward * RUN + Vector3.UP * rise
	section.forward = forward
	section.half_width = half_width
	var fit_cleats := not ramp
	for existing in _sections:
		if existing.cleats != null and existing.has_side_connection(section):
			existing.cleats.free()
			existing.cleats = null
		if fit_cleats and section.has_side_connection(existing):
			fit_cleats = false
	if fit_cleats:
		section.cleats = Node3D.new()
		section.cleats.name = "MooringCleats"
		model.add_child(section.cleats)
		for side: float in [-1.0, 1.0]:
			for along: float in [1.5, 4.5]:
				var cleat: Node3D = _piece(CLEAT)
				section.cleats.add_child(cleat)
				cleat.position = Vector3(side * (half_width - 0.16), 0, -along)
	_sections.append(section)
	return section.end
