class_name NavalVessel
extends Vessel
## A navy vessel passing through the channel in a little convoy: a nuclear
## submarine leading, a navy tug flanking it on each side (now and then the
## Nautilus in place of the submarine). The lead keeps the path and gives way like a cargo ship; the
## flankers hold station on it, `offset` across and behind its track.
## Drawn straight from their Blender glbs, materials and all.

const TUG_GLB := "res://assets/models/navy_tug_mid.glb"
const SUB_GLB := "res://assets/models/nuclear_sub_mid.glb"
const NAUTILUS_GLB := "res://assets/models/fantasy_sub_mid.glb"
const DIVE_FROM := 1150.0       # the sub starts down this far short of its path's end (inside the map),
const DIVE_RUN := 520.0         # and is under after this far
const DIVE_DEPTH := 36.0
const ART_SCALE := 1.7          # the glbs are life-size; the world is drawn a bit larger

var traffic: MarineTraffic
var path: NavPath
var s := 0.0
var lead: NavalVessel           # null for the lead
var offset := Vector2.ZERO      # (across to starboard, back) from the lead's track
var _bob := 0.0
var _drift := Vector3.ZERO      # phases of its slow wander about its station
var _yaw := INF                 # its heading, easing after the track's (flankers lag a little in turns)
var _waterline := PackedFloat32Array()
static var _waterlines := {}    # glb -> its waterline, measured from the mesh (model metres)


static func make_spec(kind: String) -> VesselSpec:
	var sp := VesselSpec.new()
	sp.id = kind
	sp.kind = "Navy"
	match kind:
		"tug":
			sp.type_name = "Navy tug"
			sp.half_length = 14.0 * ART_SCALE
			sp.half_beam = 4.9 * ART_SCALE
			sp.draft = 6.0
			sp.wash = 1.0
		"nautilus":
			sp.type_name = "Submarine?"
			sp.half_length = 30.0 * ART_SCALE
			sp.half_beam = 6.4 * ART_SCALE
			sp.draft = 12.0
			sp.wash = 0.8
		_:
			sp.type_name = "Submarine"
			sp.half_length = 48.0 * ART_SCALE
			sp.half_beam = 6.0 * ART_SCALE
			sp.draft = 14.0
			sp.wash = 0.7
	sp.cruise = 11.0
	sp.accel = 0.5
	sp.decel = 1.0
	sp.wake_spacing = 15.0
	sp.wake_life = 26.0
	sp.kelvin = 0.6
	sp.shape = Vector4(sp.half_length * 0.6, 0.1, sp.half_beam * 0.5, 0.85)
	sp.model = func(_v: int) -> ArrayMesh: return null
	sp.lights = func(_v: int) -> ArrayMesh: return null
	return sp


func setup(t: MarineTraffic, nm: String, kind: String, p: NavPath, start: float, leader: NavalVessel = null,
		off := Vector2.ZERO) -> void:
	traffic = t
	vessel_name = nm
	name = nm.validate_node_name()
	lead = leader
	offset = off
	consort = leader
	apply_spec(make_spec(kind))
	var glb: String = {"tug": TUG_GLB, "nautilus": NAUTILUS_GLB}.get(kind, SUB_GLB)
	var scene := load(glb) as PackedScene
	if scene:
		var art: Node3D = scene.instantiate()
		art.scale = Vector3.ONE * ART_SCALE
		_use_vertex_colours(art)
		add_child(art)
		_fit_waterline(glb, art)
	path = p
	s = start
	speed = cruise
	_bob = t.rng.randf() * TAU
	_drift = Vector3(t.rng.randf(), t.rng.randf(), t.rng.randf()) * TAU
	_place()


## The foam hugs the hull where it meets the water: its outline there, measured
## from the model's vertices near y = 0, in STATIONS half-widths stem to stern.
## The trail and hull fit it too.
func _fit_waterline(glb: String, art: Node3D) -> void:
	if not _waterlines.has(glb):
		_waterlines[glb] = _measure(art)
	var m: Dictionary = _waterlines[glb]
	if m.is_empty():
		return
	var bow: float = m.bow * ART_SCALE
	var length: float = m.length * ART_SCALE
	_waterline = PackedFloat32Array([spec.half_length - bow, length])
	for w: float in m.widths:
		_waterline.append(w * ART_SCALE)


static func _measure(art: Node3D) -> Dictionary:
	const BAND := 0.9
	var pts := PackedVector3Array()
	var stack: Array[Node] = [art]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		stack.append_array(n.get_children())
		if not (n is MeshInstance3D and n.mesh):
			continue
		var xf: Transform3D = Transform3D.IDENTITY
		var up: Node = n
		while up != art and up is Node3D:
			xf = (up as Node3D).transform * xf
			up = up.get_parent()
		for i in n.mesh.get_surface_count():
			for v: Vector3 in n.mesh.surface_get_arrays(i)[Mesh.ARRAY_VERTEX]:
				var q := xf * v
				if absf(q.y) < BAND:
					pts.append(q)
	if pts.size() < 8:
		return {}
	var zmin := INF
	var zmax := -INF
	for q in pts:
		zmin = minf(zmin, q.z)
		zmax = maxf(zmax, q.z)
	var n := WakeField.STATIONS
	var length := zmax - zmin
	var widths := PackedFloat32Array()
	widths.resize(n)
	widths.fill(-1.0)
	for q in pts:
		var k := clampi(roundi((zmax - q.z) / length * (n - 1)), 0, n - 1)
		widths[k] = maxf(widths[k], absf(q.x))
	# Stations no vertex fell near: between their neighbours.
	for k in n:
		if widths[k] < 0.0:
			var a := k - 1
			while a >= 0 and widths[a] < 0.0:
				a -= 1
			var b := k + 1
			while b < n and widths[b] < 0.0:
				b += 1
			var wa := widths[a] if a >= 0 else 0.0
			var wb := widths[b] if b < n else 0.0
			widths[k] = lerpf(wa, wb, float(k - a) / float(b - a)) if a >= 0 and b < n else maxf(wa, wb) * 0.5
	return {"bow": zmax, "length": length, "widths": widths}


func wake_waterline() -> PackedFloat32Array:
	var wl := _waterline if not _waterline.is_empty() else super()
	var under := _dive()
	if under <= 0.0:
		return wl
	# The foam round its hull shrinks away as it goes under.
	wl = wl.duplicate()
	for i in range(2, wl.size()):
		wl[i] *= maxf(0.0, 1.0 - under * 1.6)
	return wl


func wake_hull() -> Vector4:
	var h := super()
	# Its wash, the hull's dent in the water and its bow waves (the V) all fade as it goes under.
	var surfaced := maxf(0.0, 1.0 - _dive() * 1.6)
	h.z *= surfaced
	h.w *= surfaced
	return h


## The subs are painted in vertex colours, which the imported materials ignore.
static func _use_vertex_colours(n: Node) -> void:
	if n is MeshInstance3D and n.mesh:
		var m: Mesh = n.mesh
		for i in m.get_surface_count():
			var mat := m.surface_get_material(i) as BaseMaterial3D
			if mat and m.surface_get_format(i) & Mesh.ARRAY_FORMAT_COLOR:
				mat = mat.duplicate()
				mat.vertex_color_use_as_albedo = true
				mat.vertex_color_is_srgb = true
				n.set_surface_override_material(i, mat)
	for c in n.get_children():
		_use_vertex_colours(c)


func _process(delta: float) -> void:
	_bob += delta
	if lead != null and not is_instance_valid(lead):
		lead = null
	if lead != null:
		# Never quite in step: dropping back a few metres and catching up again,
		# easing in and out across the track.
		var lag := 3.5 * sin(_bob * 0.06 + _drift.x) + 1.5 * sin(_bob * 0.17 + _drift.y)
		var s_new := lead.s - offset.y - lag
		speed = maxf(0.0, (s_new - s) / delta) if delta > 0.0 else lead.speed
		s = s_new
	else:
		speed = move_toward(speed, cruise, (spec.accel if cruise > speed else spec.decel) * delta)
		speed = minf(speed, yield_speed())
		s += speed * delta
	# Out at the end of its path (and never run past it: pinned there, its wake would
	# keep counting distance and smear into a streak).
	if s >= path.length:
		_leave()
		return
	_place()
	var h := heading2()
	var under := _dive()
	visible = under < 1.0
	# Going down it lays no more wake; half under, its old trail has long faded and it
	# leaves the water's wakes altogether (the shader has no clean way to draw a hull
	# that is shrinking away).
	if under >= 0.45:
		wake.clear()
		return
	wake.update(delta, Vector3(global_position.x, 0.0, global_position.z), Vector3(h.x, 0.0, h.y), speed * delta,
			speed / cruise * (1.0 - under), speed > 0.3 and under <= 0.0)


## How far down a submarine is in its dive at the end, 0 (surfaced) to 1 (gone).
func _dive() -> float:
	if lead != null or spec.id == "tug":
		return 0.0
	return clampf((s - (path.length - DIVE_FROM)) / DIVE_RUN, 0.0, 1.0)


func _leave() -> void:
	traffic.remove(self)
	queue_free()


func _place() -> void:
	var p := path.sample(s)
	var t := path.tangent(s, spec.half_length * 0.4)
	var across := offset.x
	if lead != null:
		across += 2.0 * sin(_bob * 0.045 + _drift.z) + 0.8 * sin(_bob * 0.13 + _drift.x)
	p += Vector2(-t.y, t.x) * across
	var under := _dive()
	position = Vector3(p.x, sin(_bob * 0.6) * 0.2 * (1.0 - under) - DIVE_DEPTH * smoothstep(0.0, 1.0, under), p.y)
	var yaw := atan2(t.x, t.y)
	if lead != null and _yaw != INF:
		# Comes round a beat behind, plus the small heading its sideways wander needs.
		var dt := get_process_delta_time()
		yaw = lerp_angle(_yaw, yaw + 0.012 * cos(_bob * 0.045 + _drift.z), 1.0 - exp(-dt * 0.9))
	_yaw = yaw
	# Nose down as it goes under, levelling off once it's down.
	basis = Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, 0.07 * sin(PI * under)) \
			* Basis(Vector3.BACK, sin(_bob * 0.45) * 0.01)


func wants_to_move() -> bool:
	return true


func ahead(d: float) -> Vector2:
	return path.sample(s + d)


func path_left() -> float:
	return path.length - s


func status_text() -> String:
	var holding := holding_text()
	if holding != "":
		return holding
	return "Passing through in convoy" if lead == null else "Holding station on " + lead.vessel_name
