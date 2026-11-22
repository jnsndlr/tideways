class_name DeliveryTow
extends Vessel
## A tug bringing a boat bought in play (Simulation.buy_ferry) in from the open
## channel to the slip she will lie at, laid up until the player gives her stops.
## She is towed astern on a hawser most of the way. For the last few hundred
## metres the tug comes round onto her hip, alongside, and the two go in together
## (towing on the hip, the usual way to dock a dead ship). Then the tug casts off
## and goes back out the way it came.
##
## It has the escort tug's hull (VesselTypes.tugs); it is its own simple mover,
## not a ShipTender, since it follows one fixed path and has no station to keep.

enum Phase { TOWING, LEAVING }

## Tow speed as a share of the tug's cruise.
const TOW_PACE := 0.8
## Hawser: this much water between the tug's stern and her bow.
const HAWSER := 40.0
## Approach: the last legs run straight in along the terminal's axis from this far
## out, and the tug is alongside from HIP_AT out.
const APPROACH_FAR := 260.0
const APPROACH_NEAR := 120.0
const HIP_FROM := 340.0
const HIP_AT := 170.0
## Where the tow starts: beyond the map's edge, in the haze.
const EDGE_OUT := 240.0
const RUN_IN := 300.0

var sim: Simulation
var ferry: Ferry
var phase := Phase.TOWING
var path: NavPath
var s := 0.0                 # the ferry's centre along `path`
var _berth := Vector3.ZERO
var _dock_yaw := 0.0
var _flip := 0.0             # 0 or PI: which end of the (double-ended) ferry leads
var _side := 1.0             # which side of her the tug comes alongside
var _back: NavPath           # the tug's way back out
var _bob := 0.0
var _yaw := 0.0              # the tug's heading, eased round as it leaves
## How fast the tug swings round once it has cast off (rad per game minute).
const TURN_RATE := 0.6


## The way in from the sea to `berth` (world, y = 0) at a terminal whose dock
## points out along `out`, for a hull `half_beam` wide each side. Empty if none.
static func plan(s: Simulation, berth: Vector3, out: Vector3, half_beam: float) -> PackedVector2Array:
	var nav: NavGrid = s.marine.nav if s.marine else null
	if nav == null:
		return PackedVector2Array()
	var b := Vector2(berth.x, berth.z)
	var o := Vector2(out.x, out.z).normalized()
	var far := b + o * APPROACH_FAR
	var near := b + o * APPROACH_NEAR
	var target := far if nav.open_at(far, false) else near
	var hs := s.map.half_size
	var ends := [0, 1] if s.terrain.mainland.axis == 0 else [2, 3]
	var best := PackedVector2Array()
	var best_len := INF
	for side: int in ends:
		var normal: Vector2 = [Vector2.LEFT, Vector2.RIGHT, Vector2.UP, Vector2.DOWN][side]
		# Along the edge, nearest the terminal first, then further off either way.
		var along := b.y if side < 2 else b.x
		for k in 9:
			var t := clampf(along + (k + 1) / 2 * 400.0 * (1.0 if k % 2 == 0 else -1.0), -0.7 * hs, 0.7 * hs)
			var a := Vector2(-hs - EDGE_OUT, t) if side == 0 else Vector2(hs + EDGE_OUT, t) if side == 1 \
					else Vector2(t, -hs - EDGE_OUT) if side == 2 else Vector2(t, hs + EDGE_OUT)
			if not s.marine._open_water(a, normal):
				continue
			var pts := nav.find_path(a, target, false)
			if pts.size() < 2:
				continue
			pts = nav.finish(pts, 0.0, 40.0, 3, half_beam + 4.0, 0.0)
			pts.insert(0, a + normal * RUN_IN)
			if target == far:
				pts.append(near)
			pts.append(b)
			var length := NavPath.new(pts).length
			if length < best_len:
				best_len = length
				best = pts
			break
	return best


func setup(s: Simulation, f: Ferry, pts: PackedVector2Array) -> void:
	sim = s
	ferry = f
	vessel_name = "Tug " + ["Comox", "Skookum", "Tillicum", "Swiftsure"][s.ferries.size() % 4]
	name = vessel_name
	apply_spec(VesselTypes.tugs()[0], 0)
	path = NavPath.new(pts)
	f.tow = self
	consort = f
	f.consort = self
	# Lying where she will lie: that is the pose she ends in.
	_berth = f.global_position
	_dock_yaw = _yaw_of(Vector2(f.global_basis.z.x, f.global_basis.z.z))
	var end_yaw := _yaw_of(path.tangent(path.length, 20.0))
	_flip = PI if absf(angle_difference(end_yaw, _dock_yaw)) > PI * 0.5 else 0.0
	# Alongside on the side with more water (away from the other slips).
	var town := f.here().town
	var lat := town.lateral()
	var deep := func(k: float) -> float:
		var p := _berth + lat * k * (f.fc.half_beam + 30.0)
		return s.terrain.height_at(p.x, p.z)
	_side = 1.0 if deep.call(1.0) <= deep.call(-1.0) else -1.0
	_bob = randf() * TAU
	_place(0.0)


static func _yaw_of(d: Vector2) -> float:
	return atan2(d.x, d.y)


## Game minutes until she is alongside where she'll lie.
func minutes_left() -> float:
	if phase != Phase.TOWING:
		return 0.0
	return (path.length - s) / maxf(_tow_speed(), 0.1)


func _tow_speed() -> float:
	return TOW_PACE * minf(cruise, ferry.fc.cruise)


func _process(delta: float) -> void:
	_bob += delta
	if phase == Phase.TOWING:
		if not is_instance_valid(ferry):
			_leave()
			return
		var rem := path.length - s
		speed = _tow_speed() * clampf(rem / 180.0, 0.25, 1.0)
		s = minf(s + speed * delta, path.length)
		_place(delta)
		if s >= path.length - 0.01:
			ferry.end_delivery()
			sim.ferry_delivered.emit(ferry)
			_leave()
		return
	speed = move_toward(speed, cruise, delta * 2.0)
	s += speed * delta
	var p := _back.sample(minf(s, _back.length))
	var t := _back.tangent(minf(s, _back.length), 20.0)
	var want := _yaw_of(t)
	_yaw += clampf(angle_difference(_yaw, want), -TURN_RATE * delta, TURN_RATE * delta)
	_set_pose(p, _yaw, delta)
	if s >= _back.length:
		sim.marine.remove(self)
		queue_free()


## Puts her `s` along the path and the tug ahead of her on the hawser, or on her
## hip for the last stretch.
func _place(delta: float) -> void:
	var rem := path.length - s
	var p := path.sample(s)
	var t := path.tangent(s, 20.0)
	var yaw := lerp_angle(_yaw_of(t) + _flip, _dock_yaw, smoothstep(220.0, 30.0, rem))
	ferry.global_transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(p.x, 0.0, p.y))
	ferry.speed = speed
	var lead_s := s + ferry.fc.half_length + HAWSER + half_seg + hull_radius
	var lead := path.sample(minf(lead_s, path.length))
	var lead_yaw := _yaw_of(path.tangent(minf(lead_s, path.length), 20.0))
	var across := Vector2(cos(yaw), -sin(yaw))   # her starboard (+x) in the world
	var hip := p + across * _side * (ferry.fc.half_beam + hull_radius + 2.0)
	var k := smoothstep(HIP_FROM, HIP_AT, rem)
	_set_pose(lead.lerp(hip, k), lerp_angle(lead_yaw, _yaw_of(t), k), delta)


func _set_pose(p: Vector2, yaw: float, delta: float) -> void:
	_yaw = yaw
	var was := global_position
	global_transform = Transform3D(Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, sin(_bob * 0.7) * 0.008)
			* Basis(Vector3.BACK, sin(_bob * 0.8) * 0.02), Vector3(p.x, 0.0, p.y))
	if wake and delta > 0.0:
		var fwd := Vector3(sin(yaw), 0.0, cos(yaw))
		wake.update(delta, global_position, fwd, global_position.distance_to(was), clampf(speed / cruise, 0.0, 1.0), speed > 0.3)


## Casts off and heads back out the way it came.
func _leave() -> void:
	phase = Phase.LEAVING
	consort = null
	if is_instance_valid(ferry):
		ferry.consort = null
		ferry.tow = null
	var pts := PackedVector2Array([pos2()])
	var out := heading2() * -1.0
	if is_instance_valid(ferry):
		var d := ferry.here().town.dock_dir
		out = Vector2(d.x, d.z)
		# Backs off clear of her first, then swings round and heads out.
		var away := (pos2() - ferry.pos2()).normalized()
		pts.append(pos2() + away * 25.0 + out * 20.0)
	pts.append(pos2() + out * APPROACH_NEAR)
	var raw := path.pts
	for i in range(raw.size() - 3, -1, -1):
		pts.append(raw[i])
	_back = NavPath.new(pts)
	s = 0.0
	speed = 0.0


func wants_to_move() -> bool:
	return true


func ahead(d: float) -> Vector2:
	if phase == Phase.LEAVING:
		return _back.sample(minf(s + d, _back.length))
	var lead_s := s + ferry.fc.half_length + HAWSER + half_seg + hull_radius if is_instance_valid(ferry) else s
	return path.sample(minf(lead_s + d, path.length))


func path_left() -> float:
	return (_back.length - s) if phase == Phase.LEAVING else path.length - s


func road() -> Road:
	return Road.RESTRICTED


func restricted_text() -> String:
	return "towing " + ferry.ferry_name if phase == Phase.TOWING and is_instance_valid(ferry) else ""


func kind_text() -> String:
	return "Tug"


func status_text() -> String:
	var holding := holding_text()
	if holding != "":
		return holding
	if phase == Phase.TOWING and is_instance_valid(ferry):
		return "Towing %s in to %s" % [ferry.ferry_name, ferry.here().town.name]
	return "Heading back out to sea"
