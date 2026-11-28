class_name CoastGuardBoat
extends NavalVessel
## One of Port Rosario's three coast guard vessels (see CoastGuardStation). It lies
## at its berth for a few hours, then backs out, steams a patrol through a few
## open-water waypoints (the cutter ranges across the map, the small boats keep
## nearer home) and comes back in bow first. Drawn from its Blender glb.

const GLB := "res://assets/models/coast_guard/%s.glb"
## kind -> [type name, half length, half beam, draft, cruise m/s, patrol range m]
const KINDS := {
	"national_security_cutter": ["Coast Guard cutter", 63.6, 9.6, 6.0, 9.0, 4200.0],
	"motor_lifeboat_47": ["Coast Guard 47' motor lifeboat", 7.2, 2.2, 1.4, 8.0, 1600.0],
	"response_boat_small": ["Coast Guard response boat", 4.4, 1.6, 0.8, 12.0, 1400.0],
}
const IN_PORT := Vector2(90.0, 300.0)  # game minutes alongside between patrols
const LANE_PAD := 30.0  # straight run past its own length into and out of a berth
const ASTERN := 2.2  # m/s backing out
const ASTERN_HOLD := 0.6  # m/s at the ends of the astern run

var kind := ""
var berths: Array = []  # [Vector2 at, yaw]
var berth := Vector2.ZERO
var berth_yaw := 0.0  # bow heading when in (it berths bow first)
var docked := true
var _sail_at := 0.0
var _patrols := 0
var _phase := ""  # "astern", "pivot", "" (under way) while not docked
var _ps := 0.0  # distance backed so far
var _yaw_now := 0.0
var _next_berth: Array = []  # the berth this patrol comes home to


static func spawn_fleet(t: MarineTraffic) -> Array[CoastGuardBoat]:
	var out: Array[CoastGuardBoat] = []
	var here := false
	for isl in t.sim.map.islands:
		here = here or isl.name == CoastGuardLayout.ISLAND
	if not here:
		return out
	for m: Array in CoastGuardLayout.MOORED:
		var b := CoastGuardBoat.new()
		t.sim.add_child(b)
		b.setup_berth(t, m[0], m[1])
		t.register(b, MarineTraffic.RANK_CARGO)
		out.append(b)
	return out


func setup_berth(t: MarineTraffic, k: String, list: Array) -> void:
	traffic = t
	kind = k
	var info: Array = KINDS[k]
	vessel_name = "%s %d" % [info[0], 101 + KINDS.keys().find(k)]
	name = vessel_name.validate_node_name()
	var sp := VesselSpec.new()
	sp.id = k
	sp.kind = "Coast Guard"
	sp.type_name = info[0]
	sp.half_length = info[1]
	sp.half_beam = info[2]
	sp.draft = info[3]
	sp.wash = 0.9
	sp.cruise = info[4]
	sp.accel = 0.6
	sp.decel = 1.2
	sp.wake_spacing = 8.0
	sp.wake_life = 20.0
	sp.kelvin = 0.6
	sp.shape = Vector4(sp.half_length * 0.6, 0.1, sp.half_beam * 0.5, 0.85)
	apply_spec(sp)
	var path_glb := GLB % k
	var scene := load(path_glb) as PackedScene
	if scene:
		var art: Node3D = scene.instantiate()
		add_child(art)
	for b: Array in list:
		berths.append([Vector2(b[0], b[1]), float(b[2])])
	_take_berth(berths[0])
	_bob = t.rng.randf() * TAU
	_drift = Vector3.ZERO
	path = NavPath.new(PackedVector2Array([berth, berth + Vector2(0, 1)]))
	_dock()
	# Stagger the first sorties so they don't all go at once.
	_sail_at = _now() + t.rng.randf_range(5.0, IN_PORT.y)


func _take_berth(b: Array) -> void:
	berth = b[0]
	berth_yaw = b[1]


func _now() -> float:
	return traffic.sim.day * 1440.0 + traffic.sim.minutes


func _bow(yaw: float) -> Vector2:
	return Vector2(sin(yaw), cos(yaw))


## Where the straight lane into its berth begins: its own length and a bit back
## out from the berth, so the hull is lined up before it comes alongside.
func _lane_end(at: Vector2, yaw: float) -> Vector2:
	return at - _bow(yaw) * (spec.half_length * 2.0 + LANE_PAD)


func _dock() -> void:
	docked = true
	_phase = ""
	speed = 0.0
	wake.clear()
	_yaw_now = berth_yaw
	position = Vector3(berth.x, 0.0, berth.y)
	basis = Basis(Vector3.UP, berth_yaw)


## A patrol: from the end of its astern run, through two or three open-water
## waypoints within range, then home to one of its berths (either side of the
## pier for the cutter) along a straight lane, bow first.
func _plan_patrol() -> bool:
	var info: Array = KINDS[kind]
	var big: bool = info[1] > 20.0
	var out := _lane_end(berth, berth_yaw)
	var pts := PackedVector2Array([out])
	var at := out
	var hs: float = traffic.sim.map.half_size - 300.0
	for leg in traffic.rng.randi_range(2, 3):
		var goal := Vector2.INF
		for attempt in 16:
			var a := traffic.rng.randf() * TAU
			var r := traffic.rng.randf_range(0.35, 1.0) * float(info[5])
			var q := berth + Vector2(cos(a), sin(a)) * r
			if absf(q.x) > hs or absf(q.y) > hs or traffic.sim.terrain.height_at(q.x, q.y) > -6.0:
				continue
			goal = q
			break
		if goal == Vector2.INF:
			continue
		var leg_pts := traffic.nav.find_path(at, goal, big)
		if leg_pts.size() < 2:
			continue
		for i in range(1, leg_pts.size()):
			pts.append(leg_pts[i])
		at = goal
	var home_b: Array = berths[traffic.rng.randi_range(0, berths.size() - 1)]
	var lane := _lane_end(home_b[0], home_b[1])
	# Lined up a little further out still, so the turn onto the lane is done in open water.
	var line_up := lane - _bow(home_b[1]) * (spec.half_length + LANE_PAD)
	var home := traffic.nav.find_path(at, line_up, big)
	if home.size() < 2 or pts.size() < 3:
		return false
	for i in range(1, home.size()):
		pts.append(home[i])
	# Taper the keep-right offset to zero where the patrol meets each berth lane.
	var core := traffic.nav.finish(pts, 10.0, 30.0, 3, info[2] + 6.0)
	core.append(lane)
	core.append(home_b[0])
	path = NavPath.new(core)
	_next_berth = home_b
	s = 0.0
	return true


func _process(delta: float) -> void:
	_bob += delta
	if docked:
		position.y = sin(_bob * 0.6) * 0.08
		if _now() >= _sail_at:
			if _plan_patrol():
				docked = false
				_phase = "astern"
				_ps = 0.0
				_patrols += 1
			else:
				_sail_at = _now() + 30.0
		return
	if _phase == "astern":
		_back_out(delta)
		return
	if _phase == "pivot":
		_pivot(delta)
		return
	# Slow in the last stretch home, so it eases into its berth.
	var ease := spec.half_length * 2.0 + 60.0
	var target := cruise if path_left() > ease else maxf(0.8, cruise * path_left() / ease)
	speed = move_toward(speed, target, (spec.accel if target > speed else spec.decel) * delta)
	speed = minf(speed, yield_speed())
	s += speed * delta
	if s >= path.length:
		_take_berth(_next_berth)
		_dock()
		_sail_at = _now() + traffic.rng.randf_range(IN_PORT.x, IN_PORT.y)
		return
	_place()
	var h := heading2()
	wake.update(
		delta,
		Vector3(global_position.x, 0.0, global_position.z),
		Vector3(h.x, 0.0, h.y),
		speed * delta,
		speed / cruise,
		speed > 0.3
	)


## Backs straight out of the berth along its lane, easing off at either end.
func _back_out(delta: float) -> void:
	var run := spec.half_length * 2.0 + LANE_PAD
	var v := clampf(minf(_ps, run - _ps) * 0.12 + ASTERN_HOLD, ASTERN_HOLD, ASTERN)
	_ps = minf(_ps + v * delta, run)
	var p := berth - _bow(berth_yaw) * _ps
	position = Vector3(p.x, sin(_bob * 0.6) * 0.15, p.y)
	basis = Basis(Vector3.UP, berth_yaw)
	speed = 0.0
	if _ps >= run:
		_phase = "pivot"


## Turns on the spot (thrusters) to the heading of its first leg, then gets under way.
func _pivot(delta: float) -> void:
	var t := path.tangent(0.0, spec.half_length * 0.4)
	var want := atan2(t.x, t.y)
	var rate := 0.12 if spec.half_length > 20.0 else 0.5
	var d := wrapf(want - _yaw_now, -PI, PI)
	_yaw_now += clampf(d, -rate * delta, rate * delta)
	basis = Basis(Vector3.UP, _yaw_now)
	position.y = sin(_bob * 0.6) * 0.15
	if absf(d) < 0.01:
		_phase = ""


func _place() -> void:
	var p := path.sample(s)
	var t := path.tangent(s, spec.half_length * 0.4)
	position = Vector3(p.x, sin(_bob * 0.6) * 0.15, p.y)
	var yaw := atan2(t.x, t.y)
	_yaw_now = yaw
	basis = Basis(Vector3.UP, yaw) * Basis(Vector3.BACK, sin(_bob * 0.45) * 0.015)


## Never dives: NavalVessel's submarine dive (the last stretch of its path) would
## shrink this hull's wake away on every trip home and smear it into a flat strip.
func _dive() -> float:
	return 0.0


func wants_to_move() -> bool:
	return not docked


func status_text() -> String:
	if docked:
		return "Alongside at the coast guard station"
	var holding := holding_text()
	if holding != "":
		return holding
	if _phase != "":
		return "Leaving the coast guard station"
	return "On patrol" if path_left() > 600.0 else "Returning to station"
