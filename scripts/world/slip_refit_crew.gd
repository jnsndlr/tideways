class_name SlipRefitCrew
extends Node3D
## The pusher and crane scow that refit a terminal's slip for bigger boats (Terminal's
## refit). With the slip closed and clear she comes in from offshore straight down the
## slip, scow first, moors between the inner and outer dolphins while the crane drives
## the new ones and the wing walls, then backs out to sea again. The terminal owns the
## work clock and every pose comes from it (Terminal.refit_stage / refit_progress).
## A child of the terminal, so in its frame: x across the slips, z (u) out along them.
##
## While she works the crane takes the five piles off the deck one at a time: it swings
## over the stack, picks a pile by its head on a choker, tips it up with its foot
## dragging on the deck until it hangs plumb, swings it out over the water and lowers it
## in, lets go and the pile is driven down out of sight. The aluminium skiff runs in
## alongside the tow, circles the site while the crane works and goes out with her.

const PUSHER_GLB := "res://assets/models/pusher_mid.glb"
const SCOW_GLB := "res://assets/models/barge_construction_mid.glb"
const SKIFF_GLB := "res://assets/models/work_skiff_mid.glb"
const TOW_GAP := 20.38          # the scow's origin ahead of the pusher's (as scenes/pusher_gravel_tow.tscn)
const OFFSHORE := 420.0         # how far out along the slip she comes from and goes back to
const WORK_U := 90.0            # where the scow lies while the crew works

# The crane, in the scow's frame. The boom is fixed, so the hook works on a circle
# round the slew bearing; the stack lies just inside it, so she picks each pile near
# its head end.
const PICK_ORDER := [3, 4, 0, 1, 2]                  # top tier first
const PLACE_SLEW := [80.0, 280.0, 105.0, 255.0, 130.0]   # where each goes in (degrees)
const SLING := 1.6              # choker from the hook's throat to the pile
const THROAT := 1.15            # the hook's throat below its origin (the cable attachment)
const HOOK_HIGH := 9.6          # hook origin height (scow frame) swinging empty
const FOOT_CLEAR := 2.7         # a hanging pile's foot above the scow's origin as it swings
const FOOT_IN := -5.0           # its foot when she lets go of it
const START := 0.04             # work progress when the first pile's cycle starts
const CYCLE := 0.165            # work progress per pile
const DRIVE := 0.11             # work progress to drive a pile out of sight
const BLOWS := 9                # hammer blows to drive it
const SLING_COLOR := Color("c95738")

# The skiff: alongside the pusher coming and going, and meanwhile a loop out beyond
# her and the slips' outer dolphins, clear of everything standing in the water.
const SKIFF_ALONGSIDE := Vector2(9.0, 22.0)   # across from the slip's centre, out from the scow
const SKIFF_LOOP := Vector2(17.0, 11.0)   # half-widths across and along the slip
const SKIFF_CLEAR := 9.0                  # its near side off the dolphins and the pusher's stern
const SKIFF_LAPS := 4.0
const SKIFF_BLEND := 0.07                 # work progress to run off into the loop and back
const SKIFF_FREEBOARD := 0.16             # how far she rides above her modelled waterline
const SWELL_HEIGHT := 0.2                 # water.gdshader's swell_height
const UNIT := 3.0                         # water.gdshader's UNIT

var terminal: Terminal
var _tow := Node3D.new()
var _scow := Node3D.new()
var _slew := Node3D.new()
var _lines: Node3D
var _hook: Node3D
var _straps: Node3D
var _sling := MeshInstance3D.new()
var _piles: Array[Node3D] = []
var _pile_rest: Array[Transform3D] = []
var _pile_half: Array[float] = []
var _slew_rest := 0.0
var _slew_y := 0.0              # the slew bearing's height and position in the scow
var _slew_pos := Vector3.ZERO
var _reach := 0.0               # hook radius from the slew axis
var _sheave := 0.0              # the lines' top, in the boom's frame
var _hook_rest := 0.0           # hook origin height in the boom's frame, as modelled
var _skiff := Node3D.new()
var _outboards: Array[Node3D] = []
var _skiff_prev := Vector3.INF
var _skiff_heading := PI
var _skiff_turn := 0.0
var _bob := 0.0
var _tow_wake: WakeSource
var _skiff_wake: WakeSource
var _tow_mid := 0.0             # the tow's middle, along the pusher's z
var _tow_aft := 0.0             # the pusher's stern, along her z


static func available() -> bool:
	return ResourceLoader.exists(PUSHER_GLB) and ResourceLoader.exists(SCOW_GLB)


func setup(t: Terminal) -> void:
	terminal = t
	name = "SlipRefitCrew"
	add_child(_tow)
	# Both are painted in vertex colours, which the shared material shows as modelled.
	var mb := MeshBuilder.new()
	Models._append_part(mb, ModelParts.baked(PUSHER_GLB), Transform3D.IDENTITY)
	_tow.add_child(_mesh(mb))
	_scow.position = Vector3(0, 0, TOW_GAP)
	_tow.add_child(_scow)
	_build_scow()
	# The tow's wake runs from the pusher's stern to the scow's bow.
	var aft := 0.0
	for p in ModelParts.baked(PUSHER_GLB).verts:
		aft = minf(aft, p.z)
	var bow := TOW_GAP + 12.0
	_tow_mid = (aft + bow) * 0.5
	_tow_aft = aft
	# A pusher and a laden scow: a heavy wash for her speed, the scow's blunt ends.
	_tow_wake = WakeSource.new((bow - aft) * 0.5, 3.9, 0.9, 0.6, Vector4(4.0, 0.75, 3.0, 0.8), 12.0, 24.0)
	add_child(_tow_wake)
	if ResourceLoader.exists(SKIFF_GLB):
		_build_skiff()
		add_child(_skiff)
		# Twin outboards on a light planing hull.
		_skiff_wake = WakeSource.new(3.3, 1.1, 0.45, 0.2, Vector4(1.8, 0.1, 0.6, 0.9), 3.0, 10.0)
		add_child(_skiff_wake)
	visible = false


func _mesh(mb: MeshBuilder) -> MeshInstance3D:
	var m := MeshInstance3D.new()
	m.mesh = mb.commit()
	return m


func _part(parts: Dictionary, key: String, parent: Node3D, xf := Transform3D.IDENTITY) -> Node3D:
	var node := Node3D.new()
	node.transform = xf
	node.add_child(_mesh(parts[key]))
	parent.add_child(node)
	return node


## The scow as a tree of moving parts: hull and deck fixed, the crane's upper works
## slewing with the boom, the hoist lines and hook block, the five piles and their straps.
func _build_scow() -> void:
	var parts := ModelParts.library(SCOW_GLB)
	var root := (load(SCOW_GLB) as PackedScene).instantiate()
	var node := func(n: String) -> Node3D: return root.find_child(n, true, false)
	var fixed := MeshBuilder.new()
	Models._append_part(fixed, parts["steelscow"], Transform3D.IDENTITY)
	Models._append_part(fixed, parts["workdeckandstores"], ModelParts.relative_xform(node.call("Work deck and stores"), root))
	_scow.add_child(_mesh(fixed))
	var slew: Node3D = node.call("CraneSlew")
	_slew.transform = ModelParts.relative_xform(slew, root)
	_slew_rest = slew.rotation.y
	_slew_pos = _slew.position
	_scow.add_child(_slew)
	_slew.add_child(_mesh(parts["craneslew"]))
	var boom: Node3D = node.call("Boom and running gear")
	var boom_node := _part(parts, "boomandrunninggear", _slew, boom.transform)
	var lines: Node3D = node.call("HoistLines")
	var hook: Node3D = node.call("HookBlock")
	_lines = _part(parts, "hoistlines", boom_node, lines.transform)
	_hook = _part(parts, "hookblock", boom_node, hook.transform)
	_slew_y = _slew_pos.y + boom.position.y
	_reach = hook.position.z
	_sheave = lines.position.y
	_hook_rest = hook.position.y
	for i in 5:
		var pile: MeshInstance3D = node.call("Pile%d" % (i + 1))
		var xf := ModelParts.relative_xform(pile, root)
		_pile_rest.append(xf)
		_pile_half.append(pile.mesh.get_aabb().size.z * 0.5)
		_piles.append(_part(parts, "pile%d" % (i + 1), _scow, xf))
	_straps = _part(parts, "pilestraps", _scow, ModelParts.relative_xform(node.call("PileStraps"), root))
	root.free()
	var sling := MeshBuilder.new()
	sling.box(Vector3(0, -0.5, 0), Vector3(0.07, 1.0, 0.07), SLING_COLOR)
	_sling.mesh = sling.commit()
	_scow.add_child(_sling)


## The skiff is painted from a palette texture; read it into vertex colours so she
## takes the same lighting as the rest of the fleet.
func _build_skiff() -> void:
	var root := (load(SKIFF_GLB) as PackedScene).instantiate()
	var hull := MeshBuilder.new()
	var motors := {}
	for n: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		var motor: Node3D = n if String(n.name).begins_with("Outboard") and not String(n.name).ends_with("unit") else null
		if motor == null and n.get_parent() is MeshInstance3D and String(n.get_parent().name).begins_with("Outboard"):
			motor = n.get_parent()
		if motor == null:
			Models._append_part(hull, _palette_part(n), ModelParts.relative_xform(n, root))
			continue
		if not motors.has(motor):
			motors[motor] = MeshBuilder.new()
		Models._append_part(motors[motor], _palette_part(n), ModelParts.relative_xform(n, motor))
	_skiff.add_child(_mesh(hull))
	for motor: Node3D in motors:
		var pivot := Node3D.new()
		pivot.transform = ModelParts.relative_xform(motor, root)
		pivot.add_child(_mesh(motors[motor]))
		_skiff.add_child(pivot)
		_outboards.append(pivot)
	root.free()


func _palette_part(n: MeshInstance3D) -> MeshBuilder:
	var part := MeshBuilder.new()
	for s in n.mesh.get_surface_count():
		var arrays := n.mesh.surface_get_arrays(s)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
		var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV] if arrays[Mesh.ARRAY_TEX_UV] != null else PackedVector2Array()
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
		var mat := n.get_active_material(s) as BaseMaterial3D
		var img: Image = null
		if mat and mat.albedo_texture:
			img = mat.albedo_texture.get_image()
			if img and img.is_compressed():
				img.decompress()
		var flat := mat.albedo_color if mat else Color(0.8, 0.82, 0.83)
		var count := indices.size() if not indices.is_empty() else verts.size()
		for k in count:
			var i := indices[k] if not indices.is_empty() else k
			var c := flat
			if img and not uvs.is_empty():
				var uv := uvs[i]
				c = img.get_pixel(clampi(int(uv.x * img.get_width()), 0, img.get_width() - 1),
						clampi(int(uv.y * img.get_height()), 0, img.get_height() - 1)) * flat
			part.verts.append(verts[i])
			part.normals.append(normals[i])
			part.colors.append(c)
	return part


func _process(delta: float) -> void:
	var stage := terminal.refit_stage
	var on := stage in [Terminal.RefitStage.ARRIVING, Terminal.RefitStage.WORKING, Terminal.RefitStage.LEAVING]
	visible = on
	if not on:
		_skiff_prev = Vector3.INF
		_tow_wake.step(delta, 20.0, false)
		if _skiff_wake:
			_skiff_wake.step(delta, 5.0, false)
		return
	var t := terminal.refit_progress()
	var eased := smoothstep(0.0, 1.0, t)
	var work := WORK_U + TOW_GAP   # the pusher's u, the scow ahead of her towards the shore
	var u := work
	match stage:
		Terminal.RefitStage.ARRIVING:
			u = lerpf(OFFSHORE, work, eased)
		Terminal.RefitStage.LEAVING:
			u = lerpf(work, OFFSHORE, eased)
	_bob += delta
	var v := terminal.town.slip_offset(terminal.refit_slip)
	# Heading in towards the shore (-u) the whole time: she backs out to leave.
	var tow_at := Vector3(v, 0, u)
	_tow.transform = Transform3D(Basis(Vector3.UP, PI), tow_at + Vector3(0, swell(to_global(tow_at)) + sin(_bob * 1.1) * 0.12, 0))
	_tow_wake.position = Vector3(v, 0, u - _tow_mid)
	_tow_wake.step(delta, 20.0, stage != Terminal.RefitStage.WORKING)
	_pose_crane(stage, t)
	_drive_skiff(stage, t, v, u - TOW_GAP, delta)
	if _skiff_wake:
		_skiff_wake.position = Vector3(_skiff.position.x, 0, _skiff.position.z)
		_skiff_wake.step(delta, 5.0, true)


# --- The crane -------------------------------------------------------------------

## Slew angle and hook origin height (scow frame) at this point of the work, and how
## each pile lies.
func _pose_crane(stage: int, t: float) -> void:
	var p := t if stage == Terminal.RefitStage.WORKING else (0.0 if stage == Terminal.RefitStage.ARRIVING else 1.0)
	var slew := _slew_rest
	var hook_y := _slew_y + _hook_rest
	var carrying := -1
	_sling.visible = false
	_straps.visible = p < START + CYCLE * 0.28
	var done := START + CYCLE * PICK_ORDER.size()
	for k in PICK_ORDER.size():
		var i: int = PICK_ORDER[k]
		var a := START + CYCLE * k
		var c := (p - a) / CYCLE
		if c < 0.0:
			_piles[i].visible = true
			_piles[i].transform = _pile_rest[i]
			continue
		if c <= 1.0:
			var pose := _cycle(k, c)
			slew = pose.x
			hook_y = pose.y
			carrying = i
			continue
		_pose_driven(i, k, (p - a - CYCLE) / DRIVE)
	if p > done:
		var r := smoothstep(0.0, 1.0, clampf((p - done) / (0.95 - done), 0.0, 1.0))
		slew = lerp_angle(deg_to_rad(PLACE_SLEW[-1]), _slew_rest, r)
		hook_y = lerpf(HOOK_HIGH, _slew_y + _hook_rest, r)
	_slew.rotation.y = slew
	var local_y := hook_y - _slew_y
	_hook.position.y = local_y
	_lines.scale.y = maxf(0.01, (_sheave - local_y) / (_sheave - _hook_rest))
	if carrying >= 0:
		var k := PICK_ORDER.find(carrying)
		_pose_carried(carrying, k, slew, hook_y, (p - START - CYCLE * k) / CYCLE)


## The pick slew for pile i: the hook straight over its axis, near its head end.
func _pick_slew(i: int) -> float:
	return PI - asin(clampf(_pile_rest[i].origin.x / _reach, -1.0, 1.0))


func _hook_at(slew: float) -> Vector3:
	return _slew_pos + Vector3(sin(slew), 0, cos(slew)) * _reach


## How far along pile i its choker is from its centre (local z, towards the head).
func _pick_z(i: int) -> float:
	return _hook_at(_pick_slew(i)).z - _pile_rest[i].origin.z


func _pick_hook_y(i: int) -> float:
	return _pile_rest[i].origin.y + 0.41 + SLING + THROAT


## The hook's height with pile i hanging plumb and its foot at `foot`.
func _hanging_hook_y(i: int, foot: float) -> float:
	return foot + (_pile_half[i] - _pick_z(i)) + 0.41 + SLING + THROAT


## Keyframes of one pile's cycle: (cycle fraction, slew, hook origin height).
func _cycle(k: int, c: float) -> Vector2:
	var i: int = PICK_ORDER[k]
	var pick := _pick_slew(i)
	var place := deg_to_rad(PLACE_SLEW[k])
	var prev_slew := _slew_rest if k == 0 else deg_to_rad(PLACE_SLEW[k - 1])
	var prev_hook := _slew_y + _hook_rest if k == 0 else HOOK_HIGH
	var top := _hanging_hook_y(i, FOOT_CLEAR)
	var keys := [
		[0.00, prev_slew, prev_hook],
		[0.18, pick, HOOK_HIGH],
		[0.28, pick, _pick_hook_y(i)],
		[0.34, pick, _pick_hook_y(i)],      # slinging her
		[0.52, pick, top],                  # tipped up and hanging clear of the deck
		[0.72, place, top],
		[0.86, place, _hanging_hook_y(i, FOOT_IN)],
		[0.90, place, _hanging_hook_y(i, FOOT_IN)],   # let go
		[1.00, place, HOOK_HIGH],
	]
	for j in range(1, keys.size()):
		if c <= keys[j][0] or j == keys.size() - 1:
			var f := smoothstep(0.0, 1.0, clampf((c - keys[j - 1][0]) / (keys[j][0] - keys[j - 1][0]), 0.0, 1.0))
			return Vector2(lerp_angle(keys[j - 1][1], keys[j][1], f), lerpf(keys[j - 1][2], keys[j][2], f))
	return Vector2(prev_slew, prev_hook)


## Pile i on the hook: until it hangs plumb it pivots about the choker with its foot on
## the deck; then it hangs and turns with the crane.
func _pose_carried(i: int, k: int, slew: float, hook_y: float, c: float) -> void:
	var rest := _pile_rest[i]
	var pick := _pick_slew(i)
	var zp := _pick_z(i)
	var tail := _pile_half[i] - zp          # choker to foot
	if c < 0.28 or c > 0.90:
		# Not slung yet, or let go: on the deck or where she let it go.
		if c < 0.28:
			_piles[i].transform = rest
		else:
			_pose_driven(i, k, 0.0)
		return
	var hook := _hook_at(slew)
	var choke_y := hook_y - THROAT - SLING - 0.41
	# Once it hangs plumb it stays plumb, however low she lowers it.
	var tilt := PI / 2 if c >= 0.52 else asin(clampf((choke_y - rest.origin.y) / tail, 0.0, 1.0))
	var basis := Basis(Vector3.UP, slew - pick) * Basis(Vector3.RIGHT, tilt)
	var choke := Vector3(hook.x, choke_y, hook.z)
	_piles[i].transform = Transform3D(basis, choke - basis * Vector3(0, 0, zp))
	_sling.visible = true
	var throat := Vector3(hook.x, hook_y - THROAT, hook.z)
	_sling.transform = Transform3D(Basis.IDENTITY.scaled(Vector3(1, throat.y - choke_y, 1)), throat)


## Pile i after it was let go: standing where it went in, driven down blow by blow
## until it is out of sight.
func _pose_driven(i: int, k: int, d: float) -> void:
	var place := deg_to_rad(PLACE_SLEW[k])
	var at := _hook_at(place)
	var basis := Basis(Vector3.UP, place - _pick_slew(i)) * Basis(Vector3.RIGHT, PI / 2)
	var zp := _pick_z(i)
	var start := FOOT_IN + _pile_half[i] - zp   # choker height at release
	var end := -0.6 - (_pile_half[i] + zp)   # head 0.6 below the water
	var blows := clampf(d, 0.0, 1.0) * BLOWS
	var sunk := (floorf(blows) + smoothstep(0.0, 0.25, fmod(blows, 1.0))) / BLOWS if d < 1.0 else 1.0
	var choke := Vector3(at.x, lerpf(start, end, sunk), at.z)
	_piles[i].transform = Transform3D(basis, choke - basis * Vector3(0, 0, zp))
	_piles[i].visible = d < 1.0


# --- The skiff -------------------------------------------------------------------

func _drive_skiff(stage: int, t: float, v: float, scow_u: float, delta: float) -> void:
	if not _skiff.is_inside_tree():
		return
	var pos: Vector3
	match stage:
		Terminal.RefitStage.ARRIVING, Terminal.RefitStage.LEAVING:
			pos = Vector3(v + SKIFF_ALONGSIDE.x, 0, scow_u + SKIFF_ALONGSIDE.y)
		_:
			# Out from alongside along the slip to the loop, and back in the same way.
			var along := Vector3(v + SKIFF_ALONGSIDE.x, 0, WORK_U + SKIFF_ALONGSIDE.y)
			var loop := _skiff_loop(v, t)
			var out := smoothstep(0.0, 1.0, clampf(t / SKIFF_BLEND, 0.0, 1.0))
			var back := smoothstep(0.0, 1.0, clampf((1.0 - t) / SKIFF_BLEND, 0.0, 1.0))
			var w := minf(out, back)
			var turn := Vector3(along.x, 0, loop.z)
			pos = along.lerp(turn, smoothstep(0.0, 0.6, w)).lerp(loop, smoothstep(0.4, 1.0, w))
	if _skiff_prev == Vector3.INF:
		_skiff_prev = pos
	var vel := (pos - _skiff_prev) / maxf(delta, 1e-4)
	_skiff_prev = pos
	var speed := Vector2(vel.x, vel.z).length()
	var turn := 0.0
	if speed > 0.3:
		var want := atan2(vel.x, vel.z)
		var step := angle_difference(_skiff_heading, want)
		var turned := clampf(step, -2.0 * delta, 2.0 * delta) if delta > 0.0 else 0.0
		_skiff_heading += turned
		turn = turned / maxf(delta, 1e-4)
	_skiff_turn = lerpf(_skiff_turn, turn, clampf(delta * 3.0, 0.0, 1.0))
	# Bow up a touch under way; she rides the swell with her sole well clear of it.
	var pitch := -clampf(speed * 0.006, 0.0, 0.03)
	var roll := clampf(_skiff_turn * 0.1, -0.08, 0.08)
	var bob := SKIFF_FREEBOARD + swell(to_global(pos)) + sin(_bob * 2.3) * 0.03
	_skiff.transform = Transform3D(
		Basis(Vector3.UP, _skiff_heading) * Basis(Vector3.RIGHT, pitch + sin(_bob * 1.7) * 0.015) * Basis(Vector3.BACK, roll),
		pos + Vector3(0, bob, 0))
	for o in _outboards:
		o.rotation.y = clampf(-_skiff_turn * 0.5, -0.5, 0.5)


## A lazy loop off the slip (x across and z along it, in the terminal's frame), beyond
## the pusher's stern and every slip's outer dolphins, weaving in and out lap by lap.
func _skiff_loop(v: float, t: float) -> Vector3:
	var near := WORK_U + TOW_GAP - _tow_aft
	for g in terminal.slip_guides:
		if g:
			for f in g.fenders:
				near = maxf(near, f.u)
	var a := t * SKIFF_LAPS * TAU
	var wobble := 1.0 + 0.12 * sin(a * 2.5 + 0.7)
	var mid := near + SKIFF_CLEAR + SKIFF_LOOP.y
	return Vector3(v + cos(a) * SKIFF_LOOP.x * wobble, 0, mid + sin(a) * SKIFF_LOOP.y * wobble)


# --- Riding the water --------------------------------------------------------------

## The water shader's swell height at world point `p`, so small boats ride it rather
## than the swell washing over their decks (water.gdshader's swell()).
static func swell(p: Vector3) -> float:
	var q := Vector2(p.x, p.z) / UNIT
	var t := Time.get_ticks_msec() / 1000.0
	var h := _gnoise(q * 0.011 + Vector2(0.05, 0.02) * t) + 0.5 * _gnoise(q * 0.027 - Vector2(0.03, 0.07) * t + Vector2(7, 7))
	return h * SWELL_HEIGHT * UNIT


static func _grad(i: Vector2) -> Vector2:
	var p3 := Vector3(i.x, i.y, i.x) * Vector3(0.1031, 0.1030, 0.0973)
	p3 = Vector3(p3.x - floorf(p3.x), p3.y - floorf(p3.y), p3.z - floorf(p3.z))
	p3 += Vector3.ONE * p3.dot(Vector3(p3.y, p3.z, p3.x) + Vector3.ONE * 33.33)
	var g := Vector2((p3.x + p3.y) * p3.z, (p3.x + p3.z) * p3.y)
	g = Vector2(g.x - floorf(g.x), g.y - floorf(g.y)) * 2.0 - Vector2.ONE
	return g / sqrt(maxf(g.dot(g), 1e-4))


static func _gnoise(p: Vector2) -> float:
	var i := p.floor()
	var f := p - i
	var u := f * f * f * (f * (f * 6.0 - Vector2(15, 15)) + Vector2(10, 10))
	var n0 := _grad(i).dot(f)
	var n1 := _grad(i + Vector2(1, 0)).dot(f - Vector2(1, 0))
	var n2 := _grad(i + Vector2(0, 1)).dot(f - Vector2(0, 1))
	var n3 := _grad(i + Vector2(1, 1)).dot(f - Vector2(1, 1))
	return lerpf(lerpf(n0, n1, u.x), lerpf(n2, n3, u.x), u.y) * 1.5


## A wake for something that isn't a Vessel: it leaves a trail behind wherever it
## moves, which WakeField hands to the water shader with the fleet's.
class WakeSource extends Node3D:
	var wake: WakeTrail
	var _hull: Vector4
	var _shape: Vector4
	var _last := Vector3.INF

	func _init(half_length: float, half_beam: float, wash: float, kelvin: float, shape: Vector4,
			spacing: float, life: float) -> void:
		wake = WakeTrail.new(half_length, spacing, life, 44)
		_hull = Vector4(half_beam, half_length * 2.0, wash, kelvin)
		_shape = shape
		add_to_group(WakeField.WAKE_GROUP)

	## Advances the trail from how far it moved since last frame; `cruise` is the
	## speed at which it churns hardest.
	func step(delta: float, cruise: float, under_way: bool) -> void:
		var at := global_position
		var moved := Vector3.ZERO if _last == Vector3.INF else at - _last
		moved.y = 0.0
		_last = at if under_way else Vector3.INF
		var travel := moved.length()
		var speed := travel / maxf(delta, 1e-4)
		var going := under_way and speed > 0.4
		wake.update(delta, at, moved / travel if going else Vector3.ZERO, travel if going else 0.0,
				clampf(speed / cruise, 0.0, 1.0) if going else 0.0, going)

	func pos2() -> Vector2:
		return Vector2(global_position.x, global_position.z)

	func wake_hull() -> Vector4:
		return _hull

	func front_thrust() -> float:
		return 0.0

	func stern_push() -> float:
		return 0.0

	## Its waterline as Vessel.wake_waterline draws one from its hull and shape.
	func wake_waterline() -> PackedFloat32Array:
		return HullWaterline.from_shape(_hull, _shape)
