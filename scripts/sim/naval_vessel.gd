class_name NavalVessel
extends Vessel
## A navy vessel passing through the channel in a little convoy: a nuclear
## submarine leading, a navy tug flanking it on each side (now and then the
## Nautilus in place of the submarine). The lead keeps the path and gives way like a cargo ship; the
## flankers hold station on it, `offset` across and behind its track.
## Drawn straight from their Blender glbs, materials and all.

const DIVE_FROM := 1150.0  # the sub starts down this far short of its path's end (inside the map),
const DIVE_RUN := 520.0  # and is under after this far
const DIVE_DEPTH := 36.0
const ART_SCALE := 1.7  # the glbs are life-size; the world is drawn a bit larger

var traffic: MarineTraffic
var path: NavPath
var s := 0.0
var lead: NavalVessel  # null for the lead
var offset := Vector2.ZERO  # (across to starboard, back) from the lead's track
var _bob := 0.0
var _drift := Vector3.ZERO  # phases of its slow wander about its station
var _yaw := INF  # its heading, easing after the track's (flankers lag a little in turns)
var _waterline := PackedFloat32Array()


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
	return sp


func setup(
	t: MarineTraffic,
	nm: String,
	kind: String,
	p: NavPath,
	start: float,
	leader: NavalVessel = null,
	off := Vector2.ZERO
) -> void:
	traffic = t
	vessel_name = nm
	name = nm.validate_node_name()
	lead = leader
	offset = off
	consort = leader
	apply_spec(make_spec(kind))
	path = p
	s = start
	speed = cruise
	_bob = t.rng.randf() * TAU
	_drift = Vector3(t.rng.randf(), t.rng.randf(), t.rng.randf()) * TAU
	_place()


func set_waterline(profile: PackedFloat32Array) -> void:
	_waterline = profile


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
	wake.update(
		delta,
		Vector3(global_position.x, 0.0, global_position.z),
		Vector3(h.x, 0.0, h.y),
		speed * delta,
		speed / cruise * (1.0 - under),
		speed > 0.3 and under <= 0.0
	)


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
	position = Vector3(
		p.x, sin(_bob * 0.6) * 0.2 * (1.0 - under) - DIVE_DEPTH * smoothstep(0.0, 1.0, under), p.y
	)
	var yaw := atan2(t.x, t.y)
	if lead != null and _yaw != INF:
		# Comes round a beat behind, plus the small heading its sideways wander needs.
		var dt := get_process_delta_time()
		yaw = lerp_angle(_yaw, yaw + 0.012 * cos(_bob * 0.045 + _drift.z), 1.0 - exp(-dt * 0.9))
	_yaw = yaw
	# Nose down as it goes under, levelling off once it's down.
	basis = (
		Basis(Vector3.UP, yaw)
		* Basis(Vector3.RIGHT, 0.07 * sin(PI * under))
		* Basis(Vector3.BACK, sin(_bob * 0.45) * 0.01)
	)


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
