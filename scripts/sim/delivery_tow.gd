class_name DeliveryTow
extends Vessel
## A tug bringing a boat bought in play (Simulation.buy_ferry) in from the open
## channel to the slip she will lie in, laid up until the player gives her stops,
## or taking a sold one away out to sea (Simulation.sell_ferry).
##
## Bringing one in, it tows her on a hawser most of the way. Short of the
## terminal it lets go, drops back along her side and comes in under her stern,
## then pushes her straight into the slip, clear of the dolphins either side. If
## a working boat is at that slip or coming in to it, the tow holds off until it
## has gone. Taking one away, the tug comes in, turns off her outer end, takes
## her on the hawser and pulls her out and away.
##
## It has the escort tug's hull (VesselTypes.tugs); it is its own simple mover,
## not a ShipTender, since it follows one fixed path and has no station to keep.

enum Phase { TOWING, LEAVING, FETCHING, TURNING, PULLING }

## Tow speed as a share of the tug's cruise.
const TOW_PACE := 0.8
const NAMES := ["Tug Comox", "Tug Skookum", "Tug Tillicum", "Tug Swiftsure"]
## Hawser: this much water between the tug's stern and her bow.
const HAWSER := 40.0
## Approach: the last legs run straight in along the terminal's axis from this far out.
const APPROACH_FAR := 260.0
const APPROACH_NEAR := 120.0
## Bringing her in, by distance she has to go: the tug lets go of the hawser and
## comes alongside from LET_GO to ALONGSIDE, drops back along her side to ASTERN,
## and is in under her stern, pushing, by PUSHING.
const LET_GO := 620.0
const ALONGSIDE := 520.0
const ASTERN := 420.0
const PUSHING := 330.0
## The tow holds off here until the slip is clear, then commits to it.
const COMMIT_AT := LET_GO + 60.0
## Where the tow starts: beyond the map's edge, in the haze.
const EDGE_OUT := 240.0
const RUN_IN := 300.0
## Bringing one in, the tow starts no further out than this many game minutes
## at full tow speed (it joins the way in partway along). With the slower
## approach and push in, delivery takes 2–3 hours.
const MAX_TOW_MINUTES := 95.0
## How fast the tug swings round on its own (rad per game minute).
const TURN_RATE := 0.6

var sim: Simulation
var ferry: Ferry
var outbound := false        # taking a sold boat away
var phase := Phase.TOWING
## Bringing her in: the tow is past COMMIT_AT and the slip is hers (Simulation.occupant).
## Taking her away: until she is well clear of the slip.
var committed := false
var waiting := false         # holding off for a working boat to clear her slip
var path: NavPath            # in from the sea to the berth
var s := 0.0                 # the ferry's centre along `path` (or, outbound, along `_out`)
var _out: NavPath            # out from the berth to the sea
var _berth := Vector3.ZERO
var _dock_yaw := 0.0
var _flip := 0.0             # 0 or PI: which end of the (double-ended) ferry leads
var _side := 1.0             # which side of her the tug drops back along
var _back: NavPath           # the tug's own way (out after delivering, in to fetch her)
var _bob := 0.0
var _yaw := 0.0


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


## `pts`: the way in from the sea to where she lies (plan). `away`: she is sold,
## lying there, and is taken out along it the other way.
func setup(s: Simulation, f: Ferry, pts: PackedVector2Array, away := false) -> void:
	sim = s
	ferry = f
	outbound = away
	vessel_name = NAMES[(s.ferries.size() + s.tows.size()) % NAMES.size()]
	name = vessel_name
	apply_spec(VesselTypes.tugs()[0], 0)
	path = NavPath.new(pts)
	var rev := pts.duplicate()
	rev.reverse()
	_out = NavPath.new(rev)
	f.tow = self
	# Lying where she will lie (or lies): the pose she ends (or starts) in.
	_berth = f.global_position
	_dock_yaw = _yaw_of(Vector2(f.global_basis.z.x, f.global_basis.z.z))
	var lead_yaw := _yaw_of(path.tangent(path.length, 20.0)) if not away else _yaw_of(_out.tangent(0.0, 20.0))
	_flip = PI if absf(angle_difference(lead_yaw, _dock_yaw)) > PI * 0.5 else 0.0
	# Drops back along her on the side with more water (away from the other slips).
	var lat := f.here().town.lateral()
	var deep := func(k: float) -> float:
		var p := _berth + lat * k * (f.fc.half_beam + 30.0)
		return s.terrain.height_at(p.x, p.z)
	_side = 1.0 if deep.call(1.0) <= deep.call(-1.0) else -1.0
	_bob = randf() * TAU
	if away:
		# In from the sea to the hawser's length off her outer end.
		phase = Phase.FETCHING
		committed = true
		_back = NavPath.new(_trim(pts, _gap()))
		_set_pose(_back.sample(0.0), _yaw_of(_back.tangent(0.0, 20.0)), 0.0)
	else:
		consort = f
		f.consort = self
		var tow_seconds := MAX_TOW_MINUTES / Units.MINUTES_PER_SECOND
		self.s = maxf(0.0, path.length - tow_seconds * _tow_speed())
		_place(0.0)


## `pts` cut short `cut` metres before its end.
static func _trim(pts: PackedVector2Array, cut: float) -> PackedVector2Array:
	var p := NavPath.new(pts)
	var out := PackedVector2Array()
	var keep := p.length - cut
	for i in pts.size():
		if p.cum[i] < keep:
			out.append(pts[i])
	out.append(p.sample(keep))
	return out


static func _yaw_of(d: Vector2) -> float:
	return atan2(d.x, d.y)


## Her centre to the tug's centre, on the hawser.
func _gap() -> float:
	return ferry.fc.half_length + HAWSER + half_seg + hull_radius


## Game minutes until she is in where she'll lie.
func minutes_left() -> float:
	if phase != Phase.TOWING:
		return 0.0
	# At the speeds _tick_towing sets, 10 m at a time.
	var v := maxf(_tow_speed(), 0.1)
	var t := 0.0
	var rem := path.length - s
	while rem > 0.0:
		var step := minf(rem, 10.0)
		t += step / (v * (0.6 if rem < LET_GO else 1.0) * clampf(rem / 180.0, 0.25, 1.0))
		rem -= step
	return Units.game_minutes(t)


func _tow_speed() -> float:
	return TOW_PACE * minf(cruise, ferry.fc.cruise)


func _process(delta: float) -> void:
	_bob += delta
	if phase != Phase.LEAVING and not is_instance_valid(ferry):
		_leave()
	match phase:
		Phase.TOWING:
			_tick_towing(delta)
		Phase.LEAVING:
			speed = move_toward(speed, cruise, delta * 2.0)
			s += speed * delta
			_follow(_back, delta)
			if s >= _back.length:
				_done()
		Phase.FETCHING:
			speed = move_toward(speed, cruise * clampf((_back.length - s) / 120.0, 0.2, 1.0), delta * 2.0)
			s = minf(s + speed * delta, _back.length)
			_follow(_back, delta)
			if s >= _back.length - 0.01:
				phase = Phase.TURNING
				speed = 0.0
		Phase.TURNING:
			var want := _yaw_of(_out.tangent(_gap(), 20.0))
			_set_pose(pos2(), _yaw + clampf(angle_difference(_yaw, want), -TURN_RATE * delta, TURN_RATE * delta), delta)
			if absf(angle_difference(_yaw, want)) < 0.02:
				phase = Phase.PULLING
				consort = ferry
				ferry.consort = self
				s = 0.0
		Phase.PULLING:
			speed = move_toward(speed, _tow_speed(), delta * 0.5)
			s += speed * delta
			committed = s < Terminal.REFIT_HOLD
			var p := _out.sample(s)
			var t := _out.tangent(s, 20.0)
			var yaw := lerp_angle(_dock_yaw, _yaw_of(t) + _flip, smoothstep(0.0, 200.0, s))
			ferry.global_transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(p.x, 0.0, p.y))
			ferry.speed = speed
			var lead := s + _gap()
			_set_pose(_out.sample(lead), _yaw_of(_out.tangent(lead, 20.0)), delta)
			if lead >= _out.length:
				ferry.queue_free()
				ferry = null
				_done()


func _tick_towing(delta: float) -> void:
	var rem := path.length - s
	waiting = false
	if not committed and rem <= COMMIT_AT:
		var term := ferry.here()
		var slip := ferry.tie_up
		if not term.town.slips[slip].tie_up and sim.slip_busy(term, slip, Terminal.REFIT_HOLD + 200.0):
			waiting = true
		else:
			committed = true
	var want := 0.0 if waiting else _tow_speed() * (0.6 if rem < LET_GO else 1.0) * clampf(rem / 180.0, 0.25, 1.0)
	speed = move_toward(speed, want, delta * 1.5)
	s = minf(s + speed * delta, path.length)
	_place(delta)
	if s >= path.length - 0.01:
		ferry.end_delivery()
		sim.ferry_delivered.emit(ferry)
		_leave()


## Puts her `s` along the path, and the tug where it is working her: ahead on
## the hawser, then round her side to under her stern, pushing.
func _place(delta: float) -> void:
	var rem := path.length - s
	var p := path.sample(s)
	var t := path.tangent(s, 20.0)
	var yaw := lerp_angle(_yaw_of(t) + _flip, _dock_yaw, smoothstep(220.0, 30.0, rem))
	ferry.global_transform = Transform3D(Basis(Vector3.UP, yaw), Vector3(p.x, 0.0, p.y))
	ferry.speed = speed
	var lead_s := s + _gap()
	var lead := path.sample(minf(lead_s, path.length))
	var lead_yaw := _yaw_of(path.tangent(minf(lead_s, path.length), 20.0))
	# Her frame along the way she is going: `t` ahead, `right` to starboard.
	var right := Vector2(t.y, -t.x)
	var w := _side * (ferry.fc.half_beam + hull_radius + 4.0)
	var astern := -(ferry.fc.half_length + half_seg + hull_radius + 1.0)
	var at: Vector2
	if rem > LET_GO:
		at = lead
	elif rem > ALONGSIDE:
		at = lead.lerp(p + t * _gap() + right * w, smoothstep(LET_GO, ALONGSIDE, rem))
	elif rem > ASTERN:
		at = p + t * lerpf(_gap(), astern, smoothstep(ALONGSIDE, ASTERN, rem)) + right * w
	else:
		at = p + t * astern + right * lerpf(w, 0.0, smoothstep(ASTERN, PUSHING, rem))
	var tug_yaw := lerp_angle(lead_yaw, _yaw_of(t), smoothstep(LET_GO, ALONGSIDE, rem))
	_set_pose(at, tug_yaw, delta)


func _follow(p: NavPath, delta: float) -> void:
	var at := minf(s, p.length)
	var want := _yaw_of(p.tangent(at, 20.0))
	_set_pose(p.sample(at), _yaw + clampf(angle_difference(_yaw, want), -TURN_RATE * delta, TURN_RATE * delta), delta)


func _set_pose(p: Vector2, yaw: float, delta: float) -> void:
	_yaw = yaw
	var was := global_position
	global_transform = Transform3D(Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, sin(_bob * 0.7) * 0.008)
			* Basis(Vector3.BACK, sin(_bob * 0.8) * 0.02), Vector3(p.x, 0.0, p.y))
	if wake and delta > 0.0:
		var fwd := Vector3(sin(yaw), 0.0, cos(yaw))
		wake.update(delta, global_position, fwd, global_position.distance_to(was), clampf(speed / cruise, 0.0, 1.0), speed > 0.3)


## Done with her: backs off her outer end, swings round and heads out.
func _leave() -> void:
	phase = Phase.LEAVING
	committed = false
	waiting = false
	consort = null
	if is_instance_valid(ferry):
		ferry.consort = null
		ferry.tow = null
	var pts := PackedVector2Array([pos2()])
	var out := -heading2()
	if is_instance_valid(ferry):
		var d := ferry.here().town.dock_dir
		out = Vector2(d.x, d.z)
	pts.append(pos2() + out * 40.0)
	pts.append(pos2() + out * APPROACH_NEAR)
	var raw := path.pts
	for i in range(raw.size() - 3, -1, -1):
		pts.append(raw[i])
	_back = NavPath.new(pts)
	s = 0.0
	speed = 0.0


## Once detached from a delivered, working ferry the tug only sails out of the
## region and unregisters itself. Company restore may regenerate this background traffic.
func delivery_complete() -> bool:
	return (
		phase == Phase.LEAVING
		and not outbound
		and not waiting
		and not committed
		and consort == null
		and is_instance_valid(ferry)
		and ferry.purchased
		and (
			ferry.berth == Ferry.Berth.WORKING
			or (ferry.berth == Ferry.Berth.TIED_UP and not ferry.assigned and ferry.trips == 0)
		)
		and ferry.tow == null
		and ferry.consort == null
	)


func _done() -> void:
	sim.tows.erase(self)
	sim.marine.remove(self)
	queue_free()


func wants_to_move() -> bool:
	return phase != Phase.TURNING and not waiting


func ahead(d: float) -> Vector2:
	match phase:
		Phase.LEAVING, Phase.FETCHING:
			return _back.sample(minf(s + d, _back.length))
		Phase.PULLING:
			return _out.sample(s + _gap() + d)
		Phase.TOWING:
			if path.length - s > LET_GO:
				return path.sample(minf(s + _gap() + d, path.length))
	return pos2()


func path_left() -> float:
	match phase:
		Phase.LEAVING, Phase.FETCHING:
			return _back.length - s
		Phase.PULLING:
			return _out.length - s - _gap()
		Phase.TOWING:
			return path.length - s
	return 0.0


func road() -> Road:
	return Road.RESTRICTED if phase in [Phase.TOWING, Phase.PULLING] else Road.POWER


func restricted_text() -> String:
	return "towing " + ferry.ferry_name if phase in [Phase.TOWING, Phase.PULLING] and is_instance_valid(ferry) else ""


func kind_text() -> String:
	return "Tug"


func status_text() -> String:
	var holding := holding_text()
	if holding != "":
		return holding
	if not is_instance_valid(ferry) or phase == Phase.LEAVING:
		return "Heading back out to sea"
	match phase:
		Phase.FETCHING, Phase.TURNING:
			return "Coming for %s, sold" % ferry.ferry_name
		Phase.PULLING:
			return "Towing %s away, sold" % ferry.ferry_name
	if waiting:
		return "Holding off %s with %s until the slip is clear" % [ferry.here().town.name, ferry.ferry_name]
	if path.length - s < ASTERN:
		return "Pushing %s in to %s" % [ferry.ferry_name, ferry.here().town.name]
	return "Towing %s in to %s" % [ferry.ferry_name, ferry.here().town.name]
