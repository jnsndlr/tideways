class_name SlipGuides
extends Node3D
## One slip's wing walls and guide dolphins (Models.SLIP_*_GLB): a four-pile dolphin
## for each of the inner pair, a six-pile one for each of the lit outer pair, and a
## splayed wing wall either side of the landing. The node sits in the terminal frame
## at the slip's lateral offset, like SlipRamp: x across the slip, z (u) out along it.
##
## The dolphins stand as wide as the slip's size (FerryClass size of the widest hull
## it takes) puts them (Layout.slip_face_v); `fit` rebuilds them for another size.
## Everything that doesn't move is one mesh, and the piles carry on down to the
## seabed under each. The parts that give are live: each dolphin fender's Compression
## blend shape, and each wing wall's fender face, which slides back on its rubber
## bushings. Set `Fender.target` / `Wall.target` (0 at rest .. 1 as hard as the
## models' own animations press them) and they ease there.

const LANTERN := 3.9
# Each wing wall stands this far clear of the landed end of the widest hull the slip
# takes, so a landing off the centre of the slip rides it.
const WALL_CLEAR := 0.3
const WALL_ANGLES := Vector2i(14, 40)   # the splays (degrees off the centreline) a wall may take
const WALL_V_MIN := 8.0
# How quickly the parts ease to their targets (per second).
const EASE := 2.5
# How far below the seabed a pile is carried, so it never shows a gap on a slope.
const PILE_SINK := 0.6


class Fender:
	var mesh: MeshInstance3D
	var side := 1.0
	var u := 0.0          # along the slip, at the fender's middle
	var face := 0.0       # lateral offset of its face from the slip's centreline (|v|)
	var peak := 1.0       # the Compression the model's animation presses it to
	var target := 0.0
	var squish := 0.0


class Wall:
	var side := 1.0
	var a := Vector3.ZERO   # ends of its fendered face (slip frame, y = 0)
	var b := Vector3.ZERO
	var travel: Node3D
	var rest := Vector3.ZERO
	var full := Vector3.ZERO
	var bushings: Array[MeshInstance3D] = []
	var peak := 1.0
	var target := 0.0
	var squish := 0.0


var v := 0.0
var size := 0
var fenders: Array[Fender] = []
var walls: Array[Wall] = []
# Deck tops of the inner and outer dolphins (slip frame), for the wildlife's perches.
var inner_caps: Array[Vector3] = []
var outer_caps: Array[Vector3] = []
var _terrain: Terrain
var _world := Transform3D.IDENTITY


static func available() -> bool:
	return Models.mid_slip_guides


func _init(slip_v: float, terminal_xform: Transform3D, terrain: Terrain) -> void:
	name = "SlipGuides"
	v = slip_v
	position.x = slip_v
	_terrain = terrain
	_world = terminal_xform * Transform3D(Basis.IDENTITY, position)


## Builds (or rebuilds) the guides for a slip of `s`.
func fit(s: int) -> void:
	if s == size:
		return
	size = s
	for c in get_children():
		c.free()
	fenders.clear()
	walls.clear()
	inner_caps.clear()
	outer_caps.clear()
	var mb := MeshBuilder.new()
	var glows := GlowBuilder.new()
	glows.xform = _world
	var face := Layout.slip_face_v(s)
	for side: float in [-1.0, 1.0]:
		_add_wall(mb, side)
		inner_caps.append(_add_dolphin(mb, side, Layout.DOLPHIN_INNER.x, face, Models.SLIP_DOLPHIN_INNER_GLB))
		var cap := _add_dolphin(mb, side, Layout.DOLPHIN_OUTER.x, face + Layout.OUTER_FLARE, Models.SLIP_DOLPHIN_OUTER_GLB)
		outer_caps.append(cap)
		# The outer dolphins carry the slip's lanterns: green to port, red to starboard.
		var mark := GlowBuilder.GREEN if side < 0 else GlowBuilder.RED
		Models.add_cage_lantern(mb, cap, mark, LANTERN)
		glows.glow(Models.cage_lantern_glow_at(cap, LANTERN), mark, 0.42, 3.5, true, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	var fixed := MeshInstance3D.new()
	fixed.name = "Fixed"
	fixed.mesh = mb.commit()
	add_child(fixed)
	# The glow builder works in world space (GlowBuilder.xform), so its mesh does too.
	var lights := MeshInstance3D.new()
	lights.name = "Lights"
	lights.mesh = glows.commit()
	lights.material_override = GlowBuilder.material()
	lights.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lights.top_level = true
	add_child(lights)
	_apply()


## The wildlife's seats on the dolphins, in world space: three gulls across each deck,
## and an eagle on each inner one (the outer ones' lanterns leave it no room).
func add_perches(gulls: Array[Seagulls.Perch], eagles: Array[Eagles.Perch]) -> void:
	for cap in inner_caps + outer_caps:
		for k in 3:
			var seat := _world * (cap + Vector3(0, 0, (k - 1) * 1.6))
			gulls.append(Seagulls.Perch.new(seat, seat, 0.0, Seagulls.Kind.DOLPHIN))
	for cap in inner_caps:
		eagles.append(Eagles.Perch.new(_world * cap, Eagles.Kind.DOLPHIN))


func _process(delta: float) -> void:
	var k := minf(1.0, delta * EASE)
	var moved := false
	for f in fenders:
		if absf(f.target - f.squish) > 0.001:
			f.squish = lerpf(f.squish, f.target, k)
			moved = true
	for w in walls:
		if absf(w.target - w.squish) > 0.001:
			w.squish = lerpf(w.squish, w.target, k)
			moved = true
	if moved:
		_apply()


func _apply() -> void:
	for f in fenders:
		f.mesh.set_blend_shape_value(0, f.squish * f.peak)
	for w in walls:
		w.travel.position = w.rest.lerp(w.full, w.squish)
		for bushing in w.bushings:
			bushing.set_blend_shape_value(0, w.squish * w.peak)


## A wing wall on `side` fitted to the slip (_wall_line): its face on the line,
## towards the slip, its piles behind.
func _add_wall(mb: MeshBuilder, side: float) -> void:
	var line := _wall_line(FerryClass.of(size))
	var w0: Vector2 = line[0]
	var w1: Vector2 = line[1]
	var p0 := Vector3(side * w0.y, 0, w0.x)
	var p1 := Vector3(side * w1.y, 0, w1.x)
	var along := (p1 - p0).normalized()
	var out := Vector3(along.z, 0, -along.x)
	if out.x * side < 0.0:
		# (Keeping the frame right-handed.)
		out = -out
		along = -along
	# The model runs along its X with its face looking +Z: X along the wall, +Z towards
	# the slip (-out).
	var model := Basis(Vector3(0, 0, 1), Vector3.UP, Vector3(-1, 0, 0))
	var root := _place(mb, Models.SLIP_WING_WALL_GLB, Transform3D(Basis(out, Vector3.UP, along) * model, (p0 + p1) * 0.5))
	var w := Wall.new()
	w.side = side
	w.a = p0
	w.b = p1
	for node in root.find_children("*", "Node3D", true, false):
		if ModelParts._key(node) == "fenderfacetravel":
			w.travel = node
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		if (mi.mesh as ArrayMesh).get_blend_shape_count() > 0:
			w.bushings.append(mi)
	if w.travel:
		w.rest = w.travel.position
		var peak := _peak_travel(root.get_meta("anim", null), w.travel, w.bushings)
		w.full = w.rest + peak[0]
		w.peak = peak[1]
		walls.append(w)


## The starboard wing wall's face (its ends, u and v off the centreline) fitted to the
## landed end of a `fc` hull lying straight in the slip, the way slips' wing walls hug
## their ferries' bows: from Layout.WING_WALL's first u, splayed whichever of
## WALL_ANGLES follows her outline most closely, WALL_CLEAR off her where it comes
## nearest, and never in nearer the centreline than WALL_V_MIN (clear of the apron).
static func _wall_line(fc: FerryClass) -> Array[Vector2]:
	var u0: float = (Layout.WING_WALL[0] as Vector2).x
	var length := Layout.WING_LENGTH
	var end_u := SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35)
	var hull: Array[Vector2] = []
	var k := 0.2
	while k < 30.0:
		var hw := fc.half_width_at(-fc.half_length + k)
		if hw > 0.0:
			hull.append(Vector2(end_u + k, hw))
		k += 0.5
	var best: Array[Vector2] = [Vector2(u0, (Layout.WING_WALL[0] as Vector2).y), Layout.WING_WALL[1]]
	var snuggest := INF
	for deg in range(WALL_ANGLES.x, WALL_ANGLES.y + 1):
		var a := deg_to_rad(deg)
		var dir := Vector2(cos(a), sin(a))
		var n := Vector2(sin(a), -cos(a))     # towards the centreline
		var span: Array[Vector2] = []
		for q in hull:
			if q.x >= u0 and q.x <= u0 + length * dir.x:
				span.append(q)
		if span.is_empty():
			continue
		# Clearance of a point is (q - w0).n: its own part plus v0 * cos(a).
		var nearest := INF
		for q in span:
			nearest = minf(nearest, (q - Vector2(u0, 0.0)).dot(n))
		var v0 := maxf(WALL_V_MIN, (WALL_CLEAR - nearest) / cos(a))
		var mean := 0.0
		for q in span:
			mean += (q - Vector2(u0, v0)).dot(n)
		mean /= span.size()
		if mean < snuggest:
			snuggest = mean
			best = [Vector2(u0, v0), Vector2(u0, v0) + dir * length]
	return best


## A dolphin from `glb` whose fender face lies `face` off the centreline on `side` at
## `u`, square to the slip and looking in at it. Returns the middle of its deck.
func _add_dolphin(mb: MeshBuilder, side: float, u: float, face: float, glb: String) -> Vector3:
	var c := Vector3(side * (face + Models.SLIP_DOLPHIN_FACE), 0, u)
	# Model +Z (the face) towards the centreline, its length (X) along the slip.
	var basis := Basis(Vector3(0, 0, side), Vector3.UP, Vector3(-side, 0, 0))
	var root := _place(mb, glb, Transform3D(basis, c))
	var anim: Animation = root.get_meta("anim", null)
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var f := Fender.new()
		f.mesh = mi
		f.side = side
		var mid := ModelParts.relative_xform(mi, self) * mi.mesh.get_aabb().get_center()
		f.u = mid.z
		f.face = face
		f.peak = _peak_compression(anim)
		fenders.append(f)
	return c + Vector3(0, Models.SLIP_DOLPHIN_DECK, 0)


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
			mi.mesh = ModelParts.painted_live(mi)
			continue
		var part := ModelParts.painted(mi)
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
	var w := _world * foot
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
static func _peak_travel(anim: Animation, travel: Node3D, bushings: Array[MeshInstance3D]) -> Array:
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
