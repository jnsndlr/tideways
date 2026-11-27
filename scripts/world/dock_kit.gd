extends Node3D

## Local coordinates in metres. Start at the middle of a deck edge.
## Directions use the XZ plane. Each call returns the far edge for chaining.
enum Width { MAIN, FINGER }
enum Support { FLOATS, PILES }
enum Boathouse { OPEN, ENCLOSED }

const BOATHOUSES := [
	"res://assets/models/dock_kit/boathouse_open.glb",
	"res://assets/models/dock_kit/boathouse_enclosed.glb",
]

const RUN := 6.0
const MAIN_WIDTH := 4.0
const FINGER_WIDTH := 2.0
const LOW := 0.48
const HIGH := 1.98
## Camera distance (to a marina's middle) past which its cleats are not drawn.
const CLEAT_RANGE := 220.0
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


## Shelter a 12 m slip between two level fingers spaced one RUN apart.
## Start at deck height, centred between the fingers, and face open water.
func add_boathouse(kind: Boathouse, start: Vector3, direction: Vector2) -> void:
	if direction.is_zero_approx():
		push_error("Boathouse direction must have a horizontal heading.")
		return
	var shelter := _piece(BOATHOUSES[kind])
	add_child(shelter)
	shelter.transform = Transform3D(Basis.looking_at(Vector3(direction.x, 0, direction.y).normalized()), start)


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


## Merge every placed piece into one mesh per material so a whole assembly costs a
## handful of draw calls instead of one per deck, float and cleat. Call once the
## assembly is finished; colliders and other non-mesh nodes stay as they are.
func bake() -> void:
	var tools := {}      # key -> SurfaceTool
	var looks := {}      # key -> [material, cast_shadow]
	var inv := global_transform.affine_inverse() if is_inside_tree() else Transform3D.IDENTITY
	var merged: Array[MeshInstance3D] = []
	for mi: MeshInstance3D in find_children("*", "MeshInstance3D", true, false):
		if mi.mesh == null or not mi.is_visible_in_tree():
			continue
		var xf := inv * mi.global_transform if is_inside_tree() else _local_xform(mi)
		for s in mi.mesh.get_surface_count():
			var mat: Material = mi.get_active_material(s)
			var cleat := mi.find_parent("MooringCleats") != null
			var key := "%d:%d:%d" % [mat.get_instance_id() if mat else 0, mi.cast_shadow, int(cleat)]
			if not tools.has(key):
				var st := SurfaceTool.new()
				st.begin(Mesh.PRIMITIVE_TRIANGLES)
				tools[key] = st
				looks[key] = [mat, mi.cast_shadow, cleat]
			(tools[key] as SurfaceTool).append_from(mi.mesh, s, xf)
		merged.append(mi)
	if merged.is_empty():
		return
	var shadow_on := ArrayMesh.new()
	var shadow_off := ArrayMesh.new()
	var cleats := ArrayMesh.new()
	for key: String in tools:
		var target := cleats if looks[key][2] else shadow_off if looks[key][1] == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF else shadow_on
		(tools[key] as SurfaceTool).commit(target)
		target.surface_set_material(target.get_surface_count() - 1, looks[key][0])
	for mi in merged:
		mi.free()
	for pair in [[shadow_on, GeometryInstance3D.SHADOW_CASTING_SETTING_ON, "DockDecks"], [shadow_off, GeometryInstance3D.SHADOW_CASTING_SETTING_OFF, "DockDecksNoShadow"]]:
		if (pair[0] as ArrayMesh).get_surface_count() == 0:
			continue
		var out := MeshInstance3D.new()
		out.name = pair[2]
		out.mesh = pair[0]
		out.cast_shadow = pair[1]
		add_child(out)
	# Cleats are too small to see from afar: no shadow, and they drop out with distance.
	if cleats.get_surface_count() > 0:
		var c := MeshInstance3D.new()
		c.name = "DockCleats"
		c.mesh = cleats
		c.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		c.visibility_range_end = CLEAT_RANGE
		c.visibility_range_end_margin = 20.0
		c.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		add_child(c)


func _local_xform(n: Node3D) -> Transform3D:
	var xf := Transform3D.IDENTITY
	while n != null and n != self:
		xf = n.transform * xf
		n = n.get_parent() as Node3D
	return xf
