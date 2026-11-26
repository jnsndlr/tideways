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
const IN_PORT := Vector2(90.0, 300.0)   # game minutes alongside between patrols
const APPROACH := 60.0                  # metres off the berth, out along its bow

var kind := ""
var berth := Vector2.ZERO
var berth_yaw := 0.0
var docked := true
var _sail_at := 0.0
var _patrols := 0


static func spawn_fleet(t: MarineTraffic) -> Array[CoastGuardBoat]:
	var out: Array[CoastGuardBoat] = []
	var here := false
	for isl in t.sim.map.islands:
		here = here or isl.name == CoastGuardStation.ISLAND
	if not here:
		return out
	for m: Array in CoastGuardStation.MOORED:
		var b := CoastGuardBoat.new()
		t.sim.add_child(b)
		b.setup_berth(t, m[0], Vector2(m[1], m[2]), m[3])
		t.register(b, MarineTraffic.RANK_CARGO)
		out.append(b)
	return out


func setup_berth(t: MarineTraffic, k: String, at: Vector2, yaw: float) -> void:
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
	sp.model = func(_v: int) -> ArrayMesh: return null
	sp.lights = func(_v: int) -> ArrayMesh: return null
	apply_spec(sp)
	var path_glb := GLB % k
	var scene := load(path_glb) as PackedScene
	if scene:
		var art: Node3D = scene.instantiate()
		add_child(art)
	berth = at
	berth_yaw = yaw
	_bob = t.rng.randf() * TAU
	_drift = Vector3.ZERO
	path = NavPath.new(PackedVector2Array([at, at + Vector2(0, 1)]))
	_dock()
	# Stagger the first sorties so they don't all go at once.
	_sail_at = _now() + t.rng.randf_range(5.0, IN_PORT.y)


func _now() -> float:
	return traffic.sim.day * 1440.0 + traffic.sim.minutes


func _bow(yaw: float) -> Vector2:
	return Vector2(sin(yaw), cos(yaw))


func _dock() -> void:
	docked = true
	speed = 0.0
	wake.clear()
	position = Vector3(berth.x, 0.0, berth.y)
	basis = Basis(Vector3.UP, berth_yaw)


## A patrol: out along the bow to the approach, through two or three open-water
## waypoints within range, and back to the approach and in.
func _plan_patrol() -> bool:
	var info: Array = KINDS[kind]
	var big: bool = info[1] > 20.0
	var out := berth + _bow(berth_yaw) * APPROACH
	var pts := PackedVector2Array([berth, out])
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
	var home := traffic.nav.find_path(at, out, big)
	if home.size() < 2 or pts.size() < 4:
		return false
	for i in range(1, home.size()):
		pts.append(home[i])
	pts.append(berth)
	var core := pts.slice(1, pts.size() - 1)
	core = traffic.nav.finish(core, 10.0, 30.0, 3, info[2] + 6.0, 0.0)
	var full := PackedVector2Array([berth])
	full.append_array(core)
	full.append(berth)
	path = NavPath.new(full)
	s = 0.0
	return true


func _process(delta: float) -> void:
	_bob += delta
	if docked:
		position.y = sin(_bob * 0.6) * 0.08
		if _now() >= _sail_at:
			if _plan_patrol():
				docked = false
				_patrols += 1
			else:
				_sail_at = _now() + 30.0
		return
	# Slow in the last stretch home, so it eases into its berth.
	var target := cruise if path_left() > 120.0 else maxf(1.2, cruise * path_left() / 120.0)
	speed = move_toward(speed, target, (spec.accel if target > speed else spec.decel) * delta)
	speed = minf(speed, yield_speed())
	s += speed * delta
	if s >= path.length:
		_dock()
		_sail_at = _now() + traffic.rng.randf_range(IN_PORT.x, IN_PORT.y)
		return
	_place()
	var h := heading2()
	wake.update(delta, Vector3(global_position.x, 0.0, global_position.z), Vector3(h.x, 0.0, h.y), speed * delta,
			speed / cruise, speed > 0.3)


## Leaving, its first stretch runs out along its bow; coming home it turns in
## the approach so it berths bow out again, ready for the next call.
func _place() -> void:
	var p := path.sample(s)
	var t := path.tangent(s, spec.half_length * 0.4)
	position = Vector3(p.x, sin(_bob * 0.6) * 0.15, p.y)
	var yaw := atan2(t.x, t.y)
	var left := path_left()
	if left < APPROACH:
		# Backs the last stretch in, stern first.
		yaw = lerp_angle(yaw + PI, berth_yaw, clampf(1.0 - left / APPROACH, 0.0, 1.0))
	basis = Basis(Vector3.UP, yaw) * Basis(Vector3.BACK, sin(_bob * 0.45) * 0.015)


func wants_to_move() -> bool:
	return not docked


func status_text() -> String:
	if docked:
		return "Alongside at the coast guard station"
	var holding := holding_text()
	if holding != "":
		return holding
	return "On patrol" if path_left() > APPROACH * 3.0 else "Returning to station"
