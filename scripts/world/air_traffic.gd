class_name AirTraffic
extends Node3D
## Light planes at the authored airstrips. Each field starts with a few parked on
## its stands. From time to time one taxis out, takes off along the runway and
## either flies to another field (if a stand is free there) or climbs off the map.
## Planes also arrive from off the map: they come in on the approach, land, roll
## out to the taxiway exit and taxi to a free stand.
##
## Each field's tower clears one plane at a time to move: from pushback to
## climb-out for a departure, from the approach fix to its stand for an arrival.
## So no two planes ever taxi or use the runway together. Departures wait at
## their stand; arrivals that aren't cleared at the fix fly a holding circle until
## they are, and are cleared ahead of departures.
## Runway space (Field.local): x along the runway, z off to the apron side (-z),
## y above the graded strip.

const MODELS := ["res://assets/models/cessna_172.glb", "res://assets/models/cessna_172_red.glb"]
const EXIT_X := -141.0          # the taxiway exit (runway model)
const APRON_LANE_Z := -50.0     # the lead-in line the planes taxi along
const TOUCHDOWN_X := 190.0
const LIFTOFF_X := 40.0
const APPROACH := 1100.0        # how far out the approach fix is, along +x
const APPROACH_H := 110.0
const CRUISE_H := 160.0
const HOLD_R := 260.0           # the holding circle's radius
const OFF_MAP := 3500.0
const TAXI := 7.0
const ROLL := 30.0
const FLY := 55.0
const WHEELS := 0.3             # the models' wheels sit this far below their origin

const SEAPLANE := "res://assets/models/beaver_floatplane.glb"
const FLOATS := 0.3             # the floatplane's origin sits this far above the water
const WATER_TAXI := 5.0

enum Gate { NONE, CLAIM, RELEASE }


## A marina's seaplane float (world_builder._marina_seaplane_dock): one plane ties
## up there, nose in. It takes off and lands along `out`, straight out to sea.
class WaterDock:
	var name: String
	var moor: Vector3
	var out: Vector3
	var away: Vector3              # off the float's open face
	var taken := false
	var next_arrival := 0.0

	func _init(n: String, m: Vector3, o: Vector3, a: Vector3) -> void:
		name = n
		moor = m
		out = o.normalized()
		away = a.normalized()

	func at(u: float, v: float, h := 0.0) -> Vector3:
		return moor + out * u + away * v + Vector3.UP * h


class Field:
	var name: String
	var xf: Transform3D
	var slope: float
	var lift: float
	var stands: Array
	var stand_z: float
	var taken: Array[bool] = []
	var next_arrival := 0.0
	var cleared: Object = null     # the craft holding the runway clearance
	var waiting_air := 0           # arrivals holding for it (they go first)

	func _init(n: String, x: Transform3D, s: float, l: float, st: Array, sz: float) -> void:
		name = n
		xf = x
		slope = s
		lift = l
		stands = st
		stand_z = sz
		for _i in st:
			taken.append(false)

	func local(x: float, h: float, z: float) -> Vector3:
		return xf * Vector3(x, slope * x + lift + h, z)

	func free_stand() -> int:
		var free: Array[int] = []
		for i in taken.size():
			if not taken[i]:
				free.append(i)
		return -1 if free.is_empty() else free[randi() % free.size()]


class Craft:
	var id := 0
	var tail := ""
	var node: Node3D
	var path := PackedVector3Array()
	var speeds := PackedFloat32Array()
	var gates: Dictionary = {}     # point index -> [Gate, Field]
	var seg := 0
	var t := 0.0
	var speed := 0.0
	var field: Field               # where it's parked / heading to land
	var home: Field                # where it took off from
	var stand := -1
	var home_stand := -1           # kept until cleared to push back
	var parked := false
	var wait := 0.0
	var yaw := 0.0
	var airborne := false
	var holding := false
	var hold_angle := 0.0
	var hold_centre := Vector3.ZERO
	var hold_from := 0.0
	var held_short := false
	var water := false             # a floatplane, working the marinas' floats
	var dock: WaterDock
	var prop: Node3D
	var prop_spin := 0.0
	var landing_light: SpotLight3D
	var landing_glow: MeshInstance3D
	var wake: SlipRefitCrew.WakeSource   # the floats' trail on the water

	func status_text() -> String:
		if water and parked:
			return "Moored at %s" % dock.name
		if water:
			return ("Inbound to %s" % dock.name) if dock != null else ("Flying" if airborne else "Taxiing")
		if parked:
			return "Parked at %s" % field.name
		if holding:
			return "Holding for %s" % field.name
		if held_short:
			return "Waiting for clearance at %s" % home.name
		if airborne:
			return ("Inbound to %s" % field.name) if field != null else "Departing the area"
		return "Taxiing"


var fields: Array[Field] = []
var docks: Array[WaterDock] = []
var planes: Array[Craft] = []
var day_cycle: DayCycle
var _scenes: Array[PackedScene] = []
var _seaplane: PackedScene
var _next_id := 0


func setup(f: Array[Field], d: Array[WaterDock] = []) -> void:
	fields = f
	docks = d
	for m: String in MODELS:
		var s := load(m) as PackedScene
		if s:
			_scenes.append(s)
	_seaplane = load(SEAPLANE) as PackedScene
	if _seaplane:
		for dock in docks:
			dock.next_arrival = randf_range(30.0, 120.0)
			if randf() < 0.7:
				var sp := _spawn(true)
				_moor(sp, dock)
				sp.wait = randf_range(20.0, 150.0)
	if _scenes.is_empty():
		return
	for field in fields:
		field.next_arrival = randf_range(20.0, 60.0)
		for i in field.stands.size():
			if randf() < 0.65:
				var p := _spawn()
				_park(p, field, i)
				p.wait = randf_range(10.0, 90.0)


## The plane nearest `screen_pos` within `radius` px, for clicking.
func pick(screen_pos: Vector2, cam: Camera3D, radius: float) -> Craft:
	var best: Craft = null
	var best_d := radius
	for p in planes:
		var wp := p.node.global_position + Vector3.UP * 1.5
		if cam.is_position_behind(wp):
			continue
		var d := cam.unproject_position(wp).distance_to(screen_pos)
		if d < best_d:
			best_d = d
			best = p
	return best


func _spawn(water := false) -> Craft:
	var p := Craft.new()
	_next_id += 1
	p.id = _next_id
	p.water = water
	p.tail = "N%d%s" % [randi_range(100, 989), "ABCDEFGHJKLMNPRSTUWXYZ"[randi() % 22]]
	p.node = (_seaplane if water else _scenes[randi() % _scenes.size()]).instantiate() as Node3D
	p.node.name = ("Seaplane " if water else "Plane ") + p.tail
	add_child(p.node)
	p.prop = p.node.find_child("Propeller pivot", true, false) as Node3D
	_add_lights(p)
	if water:
		# Two floats about 3.5 m apart and 7.5 m long: one wake wide enough for both.
		p.wake = SlipRefitCrew.WakeSource.new(3.8, 1.9, 0.7, 0.5, Vector4(2.0, 0.3, 1.0, 0.8), 8.0, 22.0)
		add_child(p.wake)
	planes.append(p)
	return p


# Light positions per model (+z nose, +x the left/port wing).
const CESSNA_LIGHTS := {tip = Vector3(5.45, 2.55, -1.6), tail = Vector3(0, 2.9, -5.0), beacon = Vector3(0, 3.35, -4.2), nose = Vector3(-1.6, 2.5, 0.2)}
const BEAVER_LIGHTS := {tip = Vector3(7.3, 3.3, -0.9), tail = Vector3(0, 3.0, -5.9), beacon = Vector3(0, 4.1, -2.0), nose = Vector3(-2.0, 3.2, 1.0)}


## Navigation lights (red port tip, green starboard, white tail), a flashing red
## beacon and white wingtip strobes: night-only glows. Plus a landing light,
## switched on by _dress for take-off and landing.
func _add_lights(p: Craft) -> void:
	var l: Dictionary = BEAVER_LIGHTS if p.water else CESSNA_LIGHTS
	var tip: Vector3 = l.tip
	var gb := GlowBuilder.new()
	gb.glow(tip, GlowBuilder.RED, 0.22, 4.0, false, 0.0, Vector3.ZERO, 0.0)
	gb.glow(Vector3(-tip.x, tip.y, tip.z), GlowBuilder.GREEN, 0.22, 4.0, false, 0.0, Vector3.ZERO, 0.0)
	gb.glow(l.tail, GlowBuilder.LED, 0.18, 3.0, false, 0.0, Vector3.ZERO, 0.0)
	var phase := randf()
	gb.glow(l.beacon, GlowBuilder.RED, 0.3, 6.0, false, Models.blink_of(phase), Vector3.ZERO, 0.0)
	for x: float in [tip.x, -tip.x]:
		gb.glow(Vector3(x, tip.y, tip.z - 0.15), Color(1, 1, 1), 0.3, 8.0, false, Models.blink_of(fmod(phase + 0.5, 1.0)), Vector3.ZERO, 0.0)
	var nav := MeshInstance3D.new()
	nav.mesh = gb.commit()
	nav.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	nav.layers = NightLights.LAYER
	p.node.add_child(nav)
	var lg := GlowBuilder.new()
	lg.glow(l.nose, GlowBuilder.HEADLIGHT, 0.4, 10.0, false, 0.0, Vector3(0, -0.15, 1), 0.0)
	p.landing_glow = MeshInstance3D.new()
	p.landing_glow.mesh = lg.commit()
	p.landing_glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.landing_glow.layers = NightLights.LAYER
	p.landing_glow.visible = false
	p.node.add_child(p.landing_glow)
	p.landing_light = SpotLight3D.new()
	p.landing_light.position = l.nose
	p.landing_light.rotation = Vector3(-0.12, PI, 0)   # SpotLight3D shines down -z
	p.landing_light.spot_range = 180.0
	p.landing_light.spot_angle = 14.0
	p.landing_light.light_energy = 6.0
	p.landing_light.light_color = GlowBuilder.HEADLIGHT
	p.landing_light.shadow_enabled = false
	p.landing_light.visible = false
	p.node.add_child(p.landing_light)


## Props turn whenever the engine runs (idle on the ground, full in the air), and
## the landing light is on below ~250 m in the air and on the take-off/landing roll.
func _dress(p: Craft, delta: float) -> void:
	var rpm := 0.0
	if not p.parked:
		rpm = 70.0 if (p.airborne or p.speed > TAXI + 1.0) else 22.0
	p.prop_spin = move_toward(p.prop_spin, rpm, delta * 40.0)
	if p.prop and p.prop_spin > 0.0:
		p.prop.rotate_object_local(Vector3.BACK, p.prop_spin * delta)
	if p.wake:
		# The trail's head is drawn at the source, so once the floats leave the
		# water the source stays where they lifted off and the trail just fades.
		var at := p.node.global_position
		var wet := at.y < FLOATS + 0.6
		if wet:
			p.wake.position = Vector3(at.x, 0.0, at.z)
		p.wake.step(delta, ROLL, not p.parked and wet)
	var night := day_cycle.night if day_cycle else 0.0
	var low := p.node.global_position.y < 250.0 + (0.0 if p.water else _ground_y(p))
	var on := night > 0.05 and not p.parked and not p.holding and low and (p.airborne or p.speed > TAXI + 1.0)
	if p.landing_light.visible != on:
		p.landing_light.visible = on
		p.landing_glow.visible = on


func _ground_y(p: Craft) -> float:
	var g := _ground(p.node.global_position)
	return 0.0 if g == -INF else g


func _moor(p: Craft, d: WaterDock) -> void:
	p.dock = d
	d.taken = true
	p.parked = true
	p.airborne = false
	_clear_path(p)
	p.yaw = _yaw_of(-d.out)
	_place(p, d.moor, p.yaw, 0.0)


## Casts off nose in: swings out off the float, taxis out to sea, takes off along
## `out` and flies to another free float (most of the time) or off the map.
func _depart_water(p: Craft) -> void:
	var d := p.dock
	p.parked = false
	_clear_path(p)
	_route(p, [d.moor, d.at(-8.0, 14.0), d.at(10.0, 26.0), d.at(60.0, 22.0), d.at(80.0, 20.0)],
		[2.0, 3.0, WATER_TAXI, WATER_TAXI, 4.0])
	_route(p, [d.at(300.0, 20.0), d.at(480.0, 20.0, 30.0), d.at(1300.0, 20.0, CRUISE_H)], [ROLL * 1.5, FLY * 0.8, FLY])
	d.taken = false
	var free := docks.filter(func(o: WaterDock) -> bool: return o != d and not o.taken)
	if not free.is_empty() and randf() < 0.6:
		var to: WaterDock = free[randi() % free.size()]
		to.taken = true
		p.dock = to
		_route(p, [to.at(1900.0, 0.0, CRUISE_H)], [FLY])
		_add_water_landing(p, to)
	else:
		p.dock = null
		var out := p.path[p.path.size() - 1]
		_route(p, [out + d.out.rotated(Vector3.UP, randf_range(-0.8, 0.8)) * OFF_MAP + Vector3.UP * 60.0], [FLY])


## Comes in from the sea along -out, touches down well out, slows to a taxi and
## swings in alongside the float nose in.
func _add_water_landing(p: Craft, d: WaterDock) -> void:
	_route(p, [d.at(APPROACH, 22.0, APPROACH_H), d.at(520.0, 22.0, 20.0), d.at(380.0, 22.0, 0.0),
		d.at(120.0, 22.0), d.at(40.0, 22.0), d.at(14.0, 12.0), d.moor],
		[FLY * 0.8, FLY * 0.6, ROLL, WATER_TAXI, WATER_TAXI, 3.0, 1.5])


func _park(p: Craft, f: Field, stand: int) -> void:
	p.field = f
	p.stand = stand
	f.taken[stand] = true
	p.parked = true
	_clear_path(p)
	var at := f.local(f.stands[stand], 0.0, f.stand_z)
	p.yaw = _yaw_of(f.local(f.stands[stand], 0.0, f.stand_z + 10.0) - at)
	_place(p, at, p.yaw, 0.0)


func _clear_path(p: Craft) -> void:
	p.path = PackedVector3Array()
	p.speeds = PackedFloat32Array()
	p.gates = {}
	p.seg = 0
	p.t = 0.0


func _process(delta: float) -> void:
	if delta <= 0.0 or (_scenes.is_empty() and _seaplane == null):
		return
	for f in fields:
		if _scenes.is_empty():
			break
		f.next_arrival -= delta
		if f.next_arrival <= 0.0:
			f.next_arrival = randf_range(70.0, 160.0)
			var s := f.free_stand()
			if s >= 0:
				var p := _spawn()
				p.field = f
				p.stand = s
				p.airborne = true
				f.taken[s] = true
				var start := _approach_fix(f) + _outward(f) * (OFF_MAP - APPROACH) + Vector3.UP * (CRUISE_H - APPROACH_H)
				_route(p, [start], [FLY])
				_add_landing(p, f, s)
	for d in docks:
		if _seaplane == null:
			break
		d.next_arrival -= delta
		if d.next_arrival <= 0.0:
			d.next_arrival = randf_range(120.0, 300.0)
			if not d.taken:
				var sp := _spawn(true)
				sp.dock = d
				sp.airborne = true
				d.taken = true
				_route(sp, [d.at(OFF_MAP, randf_range(-800.0, 800.0), CRUISE_H)], [FLY])
				_add_water_landing(sp, d)
	for p in planes.duplicate():
		_dress(p, delta)
		if p.parked:
			p.wait -= delta
			if p.wait <= 0.0:
				if p.water:
					_depart_water(p)
				else:
					_depart(p)
			continue
		if p.holding:
			_hold(p, delta)
			continue
		_advance(p, delta)


## Once the tower clears it, pushes out of its stand, taxis out, takes off along
## +x and climbs away: to another field with a free stand (most of the time),
## else off the map.
func _depart(p: Craft) -> void:
	var f := p.field
	var sx: float = f.stands[p.stand]
	p.home_stand = p.stand
	p.parked = false
	p.home = f
	_clear_path(p)
	_route(p, [f.local(sx, 0, f.stand_z)], [3.0])
	_gate(p, Gate.CLAIM, f)
	_route(p, [f.local(sx, 0, APRON_LANE_Z), f.local(EXIT_X, 0, APRON_LANE_Z), f.local(EXIT_X, 0, -12.0),
		f.local(EXIT_X + 12.0, 0, 0.0)], [TAXI, TAXI, TAXI, 4.0])
	_route(p, [f.local(LIFTOFF_X, 0, 0), f.local(LIFTOFF_X + 400.0, 35.0, 0)], [ROLL * 1.6, FLY * 0.8])
	_gate(p, Gate.RELEASE, f)
	_route(p, [f.local(LIFTOFF_X + 1200.0, CRUISE_H, 0)], [FLY])
	var others := fields.filter(func(o: Field) -> bool: return o != f and o.free_stand() >= 0)
	p.stand = -1
	if not others.is_empty() and randf() < 0.6:
		var to: Field = others[randi() % others.size()]
		var s := to.free_stand()
		p.field = to
		p.stand = s
		to.taken[s] = true
		var high := _approach_fix(to) + _outward(to) * 600.0 + Vector3.UP * (CRUISE_H - APPROACH_H)
		_route(p, [high], [FLY])
		_add_landing(p, to, s)
	else:
		p.field = null
		p.stand = -1
		var out := p.path[p.path.size() - 1]
		var dir := out - p.path[p.path.size() - 2]
		dir.y = 0.0
		_route(p, [out + dir.normalized().rotated(Vector3.UP, randf_range(-0.8, 0.8)) * OFF_MAP + Vector3.UP * 60.0], [FLY])


## Asks for the runway at the approach fix, comes in from +x, touches down, rolls
## out to the exit and taxis in to `stand`, handing the clearance back once parked.
func _add_landing(p: Craft, f: Field, stand: int) -> void:
	var sx: float = f.stands[stand]
	_route(p, [_approach_fix(f)], [FLY * 0.8])
	_gate(p, Gate.CLAIM, f)
	_route(p, [f.local(TOUCHDOWN_X + 250.0, 18.0, 0), f.local(TOUCHDOWN_X, 0, 0),
		f.local(EXIT_X + 30.0, 0, 0), f.local(EXIT_X, 0, -12.0), f.local(EXIT_X, 0, APRON_LANE_Z),
		f.local(sx, 0, APRON_LANE_Z), f.local(sx, 0, f.stand_z)],
		[FLY * 0.6, ROLL, TAXI, TAXI, TAXI, TAXI, 2.0])


func _approach_fix(f: Field) -> Vector3:
	return f.local(TOUCHDOWN_X + APPROACH, APPROACH_H, 0)


func _outward(f: Field) -> Vector3:
	return f.xf.basis.x.normalized()


func _route(p: Craft, pts: Array, speeds: Array) -> void:
	for i in pts.size():
		p.path.append(pts[i])
		p.speeds.append(speeds[i])


## A gate at the path's last point so far.
func _gate(p: Craft, g: Gate, f: Field) -> void:
	p.gates[p.path.size() - 1] = [g, f]


## At a gate: CLAIM waits for the tower (false = not yet), RELEASE hands back.
func _pass_gate(p: Craft, i: int) -> bool:
	if not p.gates.has(i):
		return true
	var g: Array = p.gates[i]
	var f: Field = g[1]
	if g[0] == Gate.RELEASE:
		if f.cleared == p:
			f.cleared = null
		return true
	if f.cleared == p:
		return true
	# Arrivals first: a departure waits while any arrival is holding.
	if f.cleared == null and (p.airborne or f.waiting_air == 0):
		f.cleared = p
		if p.home_stand >= 0:
			p.home.taken[p.home_stand] = false
			p.home_stand = -1
		return true
	return false


func _advance(p: Craft, delta: float) -> void:
	if p.path.size() < 2 or p.seg >= p.path.size() - 1:
		_arrive(p)
		return
	if p.t == 0.0 and not _pass_gate(p, p.seg):
		if p.airborne:
			_start_hold(p)
		else:
			p.held_short = true
			p.speed = 0.0
		return
	p.held_short = false
	var length := maxf(p.path[p.seg].distance_to(p.path[p.seg + 1]), 0.01)
	var target := maxf(lerpf(p.speeds[p.seg], p.speeds[p.seg + 1], p.t), 2.0)
	p.speed = move_toward(p.speed, target, delta * (6.0 if p.airborne else 4.0))
	p.t += p.speed * delta / length
	if p.t >= 1.0:
		var over := (p.t - 1.0) * length
		p.seg += 1
		p.t = 0.0
		if p.seg >= p.path.size() - 1:
			_arrive(p)
			return
		if not _pass_gate(p, p.seg):
			_place_on(p, delta)
			return
		p.t = minf(over / maxf(p.path[p.seg].distance_to(p.path[p.seg + 1]), 0.01), 0.99)
	_place_on(p, delta)


func _place_on(p: Craft, delta: float) -> void:
	var a := p.path[p.seg]
	var b := p.path[mini(p.seg + 1, p.path.size() - 1)]
	var d := b - a
	var flat := Vector2(d.x, d.z).length()
	if flat > 0.01:
		p.yaw = lerp_angle(p.yaw, _yaw_of(d), clampf(delta * 3.0, 0.0, 1.0))
	if p.water:
		p.airborne = a.y > 1.0 or b.y > 1.0
	else:
		p.airborne = a.y - _ground(a) > 1.0 or b.y - _ground(b) > 1.0
	_place(p, a.lerp(b, p.t), p.yaw, atan2(d.y, flat) if p.airborne else 0.0)


## Not cleared at the approach fix: fly a circle through the fix until the tower
## clears it, then carry on down the approach from the fix.
func _start_hold(p: Craft) -> void:
	var f: Field = p.gates[p.seg][1]
	p.holding = true
	f.waiting_air += 1
	var fix := p.path[p.seg]
	var side := Vector3.UP.cross(_outward(f)).normalized()
	p.hold_centre = fix + side * HOLD_R
	p.hold_from = atan2(fix.x - p.hold_centre.x, fix.z - p.hold_centre.z)
	p.hold_angle = 0.0


func _hold(p: Craft, delta: float) -> void:
	p.speed = FLY * 0.8
	p.hold_angle += p.speed * delta / HOLD_R
	var a := p.hold_from + p.hold_angle
	var at := p.hold_centre + Vector3(sin(a), 0.0, cos(a)) * HOLD_R
	p.yaw = _yaw_of(Vector3(cos(a), 0.0, -sin(a)))
	var bank := Basis(Vector3.UP, p.yaw) * Basis(Vector3.BACK, -0.35)
	p.node.transform = Transform3D(bank, at + Vector3.UP * (FLOATS if p.water else WHEELS))
	# Back round at the fix: in if cleared, else another lap.
	if p.hold_angle >= TAU:
		p.hold_angle -= TAU
		var f: Field = p.gates[p.seg][1]
		if f.cleared == null:
			f.cleared = p
			f.waiting_air -= 1
			p.holding = false
			p.t = 0.0


func _ground(q: Vector3) -> float:
	for f in fields:
		var l := f.xf.affine_inverse() * q
		if absf(l.x) < 260.0 and l.z < 15.0 and l.z > -90.0:
			return (f.xf * Vector3(l.x, f.slope * l.x + f.lift, 0)).y
	return -INF


func _arrive(p: Craft) -> void:
	if p.water:
		if p.dock != null:
			_moor(p, p.dock)
			p.wait = randf_range(90.0, 260.0)
			return
		planes.erase(p)
		p.node.queue_free()
		p.wake.queue_free()
		return
	if p.field != null and p.stand >= 0:
		if p.field.cleared == p:
			p.field.cleared = null
		p.parked = true
		p.airborne = false
		p.wait = randf_range(60.0, 200.0)
		_clear_path(p)
		_place(p, p.field.local(p.field.stands[p.stand], 0.0, p.field.stand_z), p.yaw, 0.0)
		return
	planes.erase(p)
	p.node.queue_free()


## Models' noses point +z.
func _yaw_of(d: Vector3) -> float:
	return atan2(d.x, d.z)


func _place(p: Craft, at: Vector3, yaw: float, pitch: float) -> void:
	p.node.transform = Transform3D(Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, -pitch), at + Vector3.UP * (FLOATS if p.water else WHEELS))
