class_name SlipGuidesView
extends Node3D
## Builds one fitted slip from the authored models and poses its moving parts from
## the contact state. Each view owns its nodes, while immutable mesh data is shared.

# How far below the seabed a pile is carried, so it never shows a gap on a slope.
const PILE_SINK := 0.6


## One set per loaded region. Only immutable, model-local geometry is shared.
## Node paths distinguish authored parts with different material overrides.
class MeshParts:
	var fixed: Dictionary[String, Dictionary] = {}
	var deformable: Dictionary[String, Dictionary] = {}

	func triangles(glb: String, path: NodePath, node: MeshInstance3D) -> MeshBuilder:
		var parts: Dictionary = fixed.get_or_add(glb, {})
		if not parts.has(path):
			parts[path] = ModelParts.painted(node)
		return parts[path]

	func live_mesh(glb: String, path: NodePath, node: MeshInstance3D) -> ArrayMesh:
		var parts: Dictionary = deformable.get_or_add(glb, {})
		if not parts.has(path):
			parts[path] = ModelParts.painted_live(node)
		return parts[path]


class Fender:
	var mesh: MeshInstance3D
	var peak := 1.0


class Wall:
	var travel: Node3D
	var rest := Vector3.ZERO
	var full := Vector3.ZERO
	var bushings: Array[MeshInstance3D] = []
	var peak := 1.0


var fenders: Array[Fender] = []
var walls: Array[Wall] = []
var _guide: SlipGuides
var _terrain: Terrain
var _parts: MeshParts


func _init(guide: SlipGuides, terrain: Terrain, parts: MeshParts) -> void:
	name = "SlipGuidesView"
	_guide = guide
	_terrain = terrain
	_parts = parts


func _enter_tree() -> void:
	_guide.fitted.connect(_rebuild)
	_guide.compression_changed.connect(_apply)
	if _guide.size > 0:
		_rebuild()


func _exit_tree() -> void:
	_guide.fitted.disconnect(_rebuild)
	_guide.compression_changed.disconnect(_apply)


func _rebuild() -> void:
	for child in get_children():
		child.free()
	fenders.clear()
	walls.clear()
	var mb := MeshBuilder.new()
	for i in _guide.walls.size():
		var wall := _guide.walls[i]
		_add_wall(mb, wall)
		_add_dolphin(mb, wall.side, _guide.inner_caps[i], SlipModel.INNER_DOLPHIN_GLB)
		var cap := _guide.outer_caps[i]
		_add_dolphin(mb, wall.side, cap, SlipModel.OUTER_DOLPHIN_GLB)
		Models.add_cage_lantern(mb, cap, Models.slip_mark(wall.side < 0), Models.DOLPHIN_LANTERN)
	var fixed := MeshInstance3D.new()
	fixed.name = "Fixed"
	fixed.mesh = mb.commit()
	add_child(fixed)
	_apply()


func _apply() -> void:
	for i in fenders.size():
		var f := fenders[i]
		f.mesh.set_blend_shape_value(0, _guide.fenders[i].squish * f.peak)
	for i in walls.size():
		var w := walls[i]
		var squish := _guide.walls[i].squish
		w.travel.position = w.rest.lerp(w.full, squish)
		for bushing in w.bushings:
			bushing.set_blend_shape_value(0, squish * w.peak)


func _add_wall(mb: MeshBuilder, contact: SlipGuides.Wall) -> void:
	var p0 := contact.a
	var p1 := contact.b
	var side := contact.side
	var along := (p1 - p0).normalized()
	var out := Vector3(along.z, 0, -along.x)
	if out.x * side < 0.0:
		# (Keeping the frame right-handed.)
		out = -out
		along = -along
	# The model runs along its X with its face looking +Z: X along the wall, +Z towards
	# the slip (-out).
	var model := Basis(Vector3(0, 0, 1), Vector3.UP, Vector3(-1, 0, 0))
	var root := _place(
		mb,
		SlipModel.WING_WALL_GLB,
		Transform3D(Basis(out, Vector3.UP, along) * model, (p0 + p1) * 0.5)
	)
	var w := Wall.new()
	for node in root.find_children("*", "Node3D", true, false):
		if ModelParts._key(node) == "fenderfacetravel":
			w.travel = node
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if (mi.mesh as ArrayMesh).get_blend_shape_count() > 0:
			w.bushings.append(mi)
	if w.travel:
		w.rest = w.travel.position
		var peak := _peak_travel(root.get_meta("anim", null), w.travel)
		w.full = w.rest + peak[0]
		w.peak = peak[1]
		walls.append(w)


func _add_dolphin(mb: MeshBuilder, side: float, cap: Vector3, glb: String) -> void:
	var c := Vector3(cap.x, 0, cap.z)
	# Model +Z (the face) towards the centreline, its length (X) along the slip.
	var basis := Basis(Vector3(0, 0, side), Vector3.UP, Vector3(-side, 0, 0))
	var root := _place(mb, glb, Transform3D(basis, c))
	var peak := _peak_compression(root.get_meta("anim", null))
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var f := Fender.new()
		f.mesh = mi
		f.peak = peak
		fenders.append(f)


## Instances `glb` at `xf` and keeps only its moving parts live: meshes with blend
## shapes, and one merged mesh for whatever rides on a "Fender face travel" node.
## Everything else goes into `mb` (the slip's one fixed mesh), each pile carried on
## down to the seabed. The model's animation is kept as the root's "anim" meta, for
## how far it presses its parts.
func _place(mb: MeshBuilder, glb: String, xf: Transform3D) -> Node3D:
	var root := (load(glb) as PackedScene).instantiate() as Node3D
	root.transform = xf
	add_child(root)
	for ap: AnimationPlayer in root.find_children("*", "AnimationPlayer", true, false):
		var names := ap.get_animation_list()
		if not names.is_empty():
			root.set_meta("anim", ap.get_animation(names[0]))
		ap.free()
	var travel: Node3D = null
	for node in root.find_children("*", "Node3D", true, false):
		if ModelParts._key(node) == "fenderfacetravel":
			travel = node
	var riding := MeshBuilder.new()
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if (mi.mesh as ArrayMesh).get_blend_shape_count() > 0:
			mi.mesh = _parts.live_mesh(glb, root.get_path_to(mi), mi)
			continue
		var part := _parts.triangles(glb, root.get_path_to(mi), mi)
		if travel and travel.is_ancestor_of(mi):
			Models._append_part(riding, part, ModelParts.relative_xform(mi, travel))
		else:
			var at := ModelParts.relative_xform(mi, self)
			Models._append_part(mb, part, at)
			var key := ModelParts._key(mi)
			if key.contains("pile") and not key.contains("cap") and not key.contains("wale"):
				_pile_to_seabed(mb, part, at)
		mi.free()
	if travel:
		var face := MeshInstance3D.new()
		face.name = "Face"
		face.mesh = riding.commit()
		travel.add_child(face)
	return root


## Carries a pile (its triangles `part`, placed by `at` in the slip frame) on from its
## foot, along its own axis, to PILE_SINK under the seabed below.
func _pile_to_seabed(mb: MeshBuilder, part: MeshBuilder, at: Transform3D) -> void:
	if _terrain == null or part.verts.is_empty():
		return
	var pts := at * part.verts
	var low := INF
	var all := Vector3.ZERO
	for p in pts:
		low = minf(low, p.y)
		all += p
	all /= pts.size()
	var foot := Vector3.ZERO
	var col := Color(0, 0, 0, 0)
	var n := 0
	for i in pts.size():
		if pts[i].y < low + 0.1:
			foot += pts[i]
			col += part.colors[i]
			n += 1
	foot /= n
	col /= n
	var r := 0.0
	for p in pts:
		if p.y < low + 0.1:
			r += Vector2(p.x - foot.x, p.z - foot.z).length()
	r /= n
	var down := (foot - all).normalized()
	if down.y > -0.5:
		down = Vector3.DOWN
	var w := _guide.slip_to_world * foot
	var bed := _terrain.height_at(w.x, w.z) - PILE_SINK
	if bed > foot.y - 0.05:
		return
	var length := (foot.y - bed) / -down.y
	var up := -down
	var x := up.cross(Vector3.FORWARD if absf(up.z) < 0.9 else Vector3.RIGHT).normalized()
	var saved := mb.xform
	mb.xform = Transform3D(Basis(x, up, x.cross(up)), foot + down * length)
	# A touch past the foot, so no seam shows where they meet.
	mb.cylinder(Vector3.ZERO, r, r, length + 0.05, 10, col)
	mb.xform = saved


## How far the wall's animation slides its face back, and the bushings' Compression
## at that moment: [travel offset, compression].
static func _peak_travel(anim: Animation, travel: Node3D) -> Array:
	var best := [Vector3(0, 0, -0.07), 1.0]
	if anim == null:
		return best
	var pos_track := -1
	var shape_track := -1
	for t in anim.get_track_count():
		var path := str(anim.track_get_path(t))
		if anim.track_get_type(t) == Animation.TYPE_POSITION_3D and path.ends_with(str(travel.name)):
			pos_track = t
		elif anim.track_get_type(t) == Animation.TYPE_BLEND_SHAPE and shape_track < 0:
			shape_track = t
	if pos_track < 0:
		return best
	var rest: Vector3 = anim.position_track_interpolate(pos_track, 0.0)
	var most := 0.0
	var t := 0.0
	while t <= anim.length:
		var d: Vector3 = anim.position_track_interpolate(pos_track, t) - rest
		if d.length() > most:
			most = d.length()
			best = [d, anim.blend_shape_track_interpolate(shape_track, t) if shape_track >= 0 else 1.0]
		t += 1.0 / 30.0
	return best


## The most any blend shape track of `anim` presses its part.
static func _peak_compression(anim: Animation) -> float:
	if anim == null:
		return 1.0
	var most := 0.0
	for tr in anim.get_track_count():
		if anim.track_get_type(tr) != Animation.TYPE_BLEND_SHAPE:
			continue
		for k in anim.track_get_key_count(tr):
			most = maxf(most, float(anim.track_get_key_value(tr, k)))
	return most if most > 0.0 else 1.0
