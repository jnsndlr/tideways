class_name Ferry
extends Vessel
## A double-ended car ferry shuttling along one route. It never turns around: cars
## board at the end facing the pier, park on the deck (as children of the ferry, so
## they ride along) and drive off the opposite end at the destination. Its size
## (FerryClass) sets how many cars it takes and how fast it goes; whatever its
## length, it docks with its end at the ramp.

const State = FerryVoyage.State

const YIELD_DECEL := FerryVoyage.YIELD_DECEL
const MIN_DWELL := 10.0
const MAX_DWELL := 24.0
const DISPATCH_GAP := 0.5
# A ferry about to leave holds in at the dock while a stretch of water it shares
# with another route, no further out than this, is taken, or while a ferry
# coming in to the same terminal, this close to it, has it still to pass.
const ARRIVAL_PRIORITY := 660.0
# Coming in, the slip's span starts down to the deck this far out (SlipRamp).
const RAMP_LOWER_AT := 40.0
# Running costs (CompanyLedger). Fuel burnt per mile goes as the square of speed
# through the water, so easing off saves fuel but takes longer, and crew are paid by
# the hour. Both are metered as she goes and posted to the ledger once a trip, when
# she docks (and at midnight, so each day's lines are whole).
const FUEL_PRICE := 3.6        # $ per gallon
const CREW_WAGE := 12.0        # $ per crew member per game hour (tuned, like the burn)
const METRES_PER_NM := 1852.0
# Pace settings: [share of the class's service speed, name]
const PACES := [[0.85, "Economy"], [1.0, "Service"], [1.1, "Full ahead"]]
const SERVICE_PACE := 1

var sim: Simulation
var fc: FerryClass
var route: MapData.Route
var fleet_key := ""                 # follows the hull through renames and route changes
var schedule: Scenario.Schedule     # the stops she runs (null when restored from a save)
## The island ids she calls at in turn, round and round, and the route of each
## leg: legs[i] runs from stops[i] to the next stop. A shuttle has two of each.
var stops: Array[int] = []
var legs: Array[MapData.Route] = []
var call := 0                       # index into stops: where she is, or is sailing to
## A schedule change from the editor (stage 4), taken at her next call at one of
## its stops: she finishes the crossing she is on first.
var next_stops: Array[int] = []
var _next_legs: Array[MapData.Route] = []
var _next_timetable: Array[int] = []
## When she leaves stops[0], in minutes after midnight (Timetable); empty: as soon
## as she has loaded. Each departure is a round of her stops.
var timetable: Array[int]:
	get: return _timetable.departures
var _timetable := Timetable.new()
var _offsets: Array[float] = []  # plan_offsets(stops), cached
var late_by := 0.0           # minutes late she left her last stop
var _loading_since := 0.0    # game minute (Simulation.abs_minutes) she began loading
## Crew come on this long before her first sailing of the day.
const CREW_CALL := 30.0
## Planned loading and unloading, per car of a full deck (game minutes).
const PLAN_CAR_GAP := 0.8
## On a timetable, the last car is let on this long before she is due (it has
## the lane and the apron to drive), and the apron starts up APRON_LIFT before.
const BOARD_CLOSE := 8.0
const APRON_LIFT := 2.0
## A timed boat back at her first stop with at least this long until her next
## sailing moves to a free tie-up slip there, if she fits one, so the working
## slip is free for other boats. Her crew stay on unless it is overnight.
const GAP_TIE_UP := 150.0
## She leaves the tie-up in time to be back at her working slip this long
## before boarding opens (MAX_DWELL before she is due).
const GAP_MARGIN := 5.0
var _gap_due := -1.0         # tied up between sailings until she is due then (game minute); -1 otherwise
## Her +Z end faces the current route's B → A rather than A → B (she came onto
## this leg from one running the other way; a double-ended ferry never turns).
var _rev := false
## Her -Z end is the one towards the terminal she is at (or last left).
var _minus: bool:
	get: return at_a != _rev
var _yaw_cache := {}                # route id -> _yaws for it
var ferry_name := ""
var term_a: Terminal
var term_b: Terminal
# Compatibility properties expose one owner to traffic, UI and setup callers.
var voyage := FerryVoyage.new()
var state: FerryVoyage.State:
	get: return voyage.state
	set(value): voyage.state = value
var at_a: bool:        # docked at A, or departed from A while sailing
	get: return voyage.at_a
	set(value): voyage.at_a = value
var hull: MeshInstance3D
# The car deck nets at -Z and +Z (FerryClass.net_z).
var _nets: Array[MeshInstance3D] = []
var _net_wind := Vector2.ZERO
var traveled: float:      # how far the hull's centre has come, dock to dock
	get: return voyage.traveled
	set(value): voyage.traveled = value
var trips: int:
	get: return voyage.trips
	set(value): voyage.trips = value
var pace := SERVICE_PACE
var fuel_today := 0.0     # $ this hull has burnt since midnight
var crew_today := 0.0
var last_crossing_fuel := 0.0
var _crossing_fuel := 0.0   # metered since she last posted
var _crew_owed := 0.0
# Her master sets how she is handled (Captain.speed_limit). A new one takes the
# helm when she next casts off, so a crossing is made under one captain.
var captain: Captain = Captain.roster()[0]
var next_captain: Captain = captain
var last_crossing := -1.0         # game minutes dock to dock, -1 before the first timed one
var last_crossing_captain: Captain
var previous_crossing := -1.0     # the timed crossing before that, to compare with
var previous_crossing_captain: Captain
var _sail_time := -1.0            # into this crossing; -1 if it wasn't timed from the dock
var _forecasts := {}              # captain id -> unhindered crossing minutes on this route
var aboard: Array[Vehicle] = []
## Walk-on passengers currently aboard: {dest: int, variant: int}.
var passengers_aboard: Array[Dictionary] = []
## Phased boarding: walk-ons board together first with no vehicle traffic,
## then cut off and clear the ramp before vehicles drive on.
enum LoadPhase { WALK_ONS, WALK_ON_CLEAR, VEHICLES }
const PAX_DISPATCH_GAP := 0.16
const PAX_CUTOFF_MINUTES := 4.5
const MAX_VISIBLE_WALKERS := 16
## In service at her working slip, or laid up: moving to, lying at, or coming
## back from a tie-up slip at the terminal she is at (`here()`).
## DELIVERING: bought in play and under tow to where she will lie (DeliveryTow).
enum Berth { WORKING, TO_TIE_UP, TIED_UP, TO_WORKING, DELIVERING }
var berth := Berth.WORKING
## Her resale value is this share of her price new, times her condition.
const RESALE_SHARE := 0.8
## 1 as good as new. Wear and tear will bring it down and maintenance back up;
## for now it is a stub that stays at 1, so every sale returns RESALE_SHARE.
var condition := 1.0
## False for a boat bought in play until she is first given stops: her stops are
## only a placeholder (the route she was delivered on) and draw no service.
var assigned := true
var tow: DeliveryTow             # bringing her in (or, sold, away) while berth is DELIVERING
var _lying_in_slip: Ferry        # the boat lying in the slip she is holding off
var lay_up_requested := false     # tie up once she has unloaded at a terminal with a free tie-up slip
var return_requested := false     # back into service once her working slip is free
var tie_up := -1                  # index into here().town.slips while laid up
var _shift: SlipShiftPath
var _shift_s := 0.0
var _return_distance := -1.0  # separation used for the cached path length
var _return_half_length := -1.0
var _return_length := 0.0
var _shift_basis := Basis()   # her basis as she set off
var _shift_shore := Vector3.ZERO  # her shoreward heading as she set off
var _shift_churn := 0.0       # how hard her props work moving slips, 0..1
var _shift_yaw := 0.0         # how far she has turned from _shift_basis (eased)
var deck: FerryDeck
var _boarding := 0
var _pax_boarding := 0
var _load_phase := LoadPhase.WALK_ONS
var _unload_queue: Array[Vehicle] = []
var _pax_unload_queue: Array[Dictionary] = []
var _dispatch_timer := 0.0
var _pax_dispatch_timer := 0.0
var _pax_walkers_sent := 0
var _last_sent: Vehicle  # the last car sent on or off, which the next one follows
var _state_time: float:
	get: return voyage.state_time
	set(value): voyage.state_time = value
var _bob_time := 0.0
var _thrust := 0.0   # forward prop reverse thrust while braking, 0..1
# Alongside at her slip she pushes ahead on her seaward prop at HOLD_THROTTLE to keep
# her landing end hard in against the apron, kicking up a little wash astern; it
# stops as soon as she casts off.
const HOLD_THROTTLE := 0.1
var _push := 0.0     # her seaward prop's throttle holding her in, 0..HOLD_THROTTLE
var _last_pos := Vector3.ZERO
var _tracking := false
var _waiting_for: Ferry = null   # holding off a corridor this ferry has reserved
var _giving_way := false         # (holding in at the dock for _waiting_for to come in)
var _casting_off := false        # loaded, waiting for the apron to come up
var _ramp_synced := false
# Landing and lying alongside (SlipGuides). Coming in, a captain who lands less surely
# (Captain.landing) may come in a little askew, her landing end off the centre of the
# slip, and ride a wing wall in, pressing its face back, before she straightens against
# the apron. Alongside, the tide sets her over to one side and she swings about her
# landing end until she lies against that side's dolphins, pressing their fenders in.
# Her pose is _base_xf (where the route puts her) turned _askew about her middle, then
# swung _lie about her landing end (radians about +Y).
const LAND_RUN := 40.0               # metres out she starts coming in askew
const WALL_GIVE := 0.35              # riding this far into a wing wall presses its face right in
const STRAIGHTEN := 0.6              # per second, straightening against the apron once alongside
# She lies over as far as it takes to reach the dolphins (a narrow hull in a wide
# slip, further); this only keeps a freak fit from spinning her round.
const MAX_LIE := deg_to_rad(15.0)
const SHORT_LIE := deg_to_rad(1.2)   # a hull too short to reach the dolphins lies over this far
const LIE_PRESS := 0.2               # how far into the fenders she leans
const FENDER_GIVE := 0.3             # leaning this far in presses a fender right in
const LIE_EASE := 0.35               # per second
var _lie := 0.0
var _askew := 0.0
var _base_xf := Transform3D.IDENTITY
var _landing_side := 0.0             # which way (her x) her landing end comes in off centre; 0 until chosen
var _landing_askew := 0.0            # how far askew (radians)
# `--rough-landings`: every landing rides a wing wall in, to see the walls give.
static var rough_landings := "--rough-landings" in OS.get_cmdline_user_args()
var _runs := {}                   # "route id|at_a" -> _corridor_runs() for that direction
# Flexible slip ends (stage 5): each route has its own slip at either end, but a boat
# coming in whose slip is taken takes another free working slip there that fits her,
# rather than wait offshore. Her track eases across to it over the last stretch in
# (Terminal.REAIM_HOLD + blend), and back onto the route's own as she leaves.
# The slip she uses at the A and B ends of her route this call (-1: the route's own).
var _end_slip: Array[int] = [-1, -1]
var _slip_chosen := false          # she has picked the slip she comes in to this crossing
# Route curves run between where a 90 m hull's centre lies docked
# (Layout.DOCK_U); a shorter one docks this much further in at both ends, a
# longer one further out (negative).
var _inset := 0.0
# Her heading every metre along the route curve from YAW_PAD before its start,
# smoothed so she swings into and out of each turn rather than taking the
# curve's 6 m chords one kink at a time (see _build_yaws).
var _yaws := PackedFloat32Array()
const YAW_PAD := 120.0
const YAW_EASE := 16.0      # m, each of the two box filters (so a turn eases in over ~32 m)
# Lanes: two boats on one route pass each other mid-crossing, each keeping to her
# own starboard lane off the line joining the docks (see lane_offset_on).
const LANE_GAP := 50.0      # m, kept between two of the biggest hulls on opposite lanes
const LANE_OUT := 60.0      # m out of the slip on the centreline before she eases over
const LANE_EASE := 320.0    # m over which she eases onto her lane
const LANE_SHIFT := 1.0 / 30.0   # of her lane per game minute, moving over when her route becomes shared (or stops being)
static var _lane_w := -1.0
var _lane_k := 0.0          # how far out on her lane she keeps (1 on a route she shares, 0 alone)


func setup(s: Simulation, r: MapData.Route, nm: String, size: int) -> void:
	sim = s
	route = r
	fc = FerryClass.of(size)
	ferry_name = nm
	vessel_name = nm
	name = nm
	captain = Captain.roster()[r.id % Captain.roster().size()]
	next_captain = captain
	cruise = captain.cruise(paced_cruise())
	yield_decel = YIELD_DECEL
	_inset = Layout.FERRY_HALF - fc.half_length
	if SlipRamp.available():
		# In far enough for the apron's toe to land on her apron line, just outboard of the
		# yellow band across her deck at the net.
		_inset = Layout.DOCK_U - SlipRamp.dock_end(fc.half_length - fc.net_z - 0.35) - fc.half_length
	# A capsule round the hull: its corners just touch, its ends cover the bows.
	half_seg = fc.half_seg()
	hull_radius = fc.hull_radius
	claim_step = 12.0
	wake = WakeTrail.new(fc.half_length, 8.0 * fc.half_length / 15.0, 24.0, 46)
	term_a = sim.terminals[r.a]
	term_b = sim.terminals[r.b]
	stops = [r.a, r.b]
	legs = [r, r]
	deck = FerryDeck.new(fc)
	hull = MeshInstance3D.new()
	hull.mesh = Models.ferry(fc)
	# Fixes which of its rooms are lit (lit_vc.gdshader); the origin would change every frame.
	hull.material_override = Models.hull_material()
	hull.set_instance_shader_parameter("room_seed", randf_range(1.0, 1000.0))
	add_child(hull)
	var thin_shadow := Models.ferry_thin_shadow(fc)
	if thin_shadow:
		var mi := MeshInstance3D.new()
		mi.mesh = thin_shadow
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		hull.add_child(mi)
	for e: float in [-1.0, 1.0]:
		var net := MeshInstance3D.new()
		net.mesh = Models.ferry_net(fc)
		net.position.z = e * fc.net_z
		add_child(net)
		_nets.append(net)
	_build_yaws()
	_place(-_inset)


## Spreads the fleet across different phases so the preview starts busy.
func start_staggered(i: int) -> void:
	match i % 3:
		0:
			_begin_loading()
		1:
			state = State.SAILING
			call = 1
			traveled = run_length() * sim.rng.randf_range(0.25, 0.6)
			speed = cruise
			for k in sim.rng.randi_range(fc.capacity / 3, fc.capacity - fc.capacity / 9):
				var car := sim.make_vehicle(self)
				var slot := _free_slot(car)
				if slot < 0:
					car.queue_free()
					break
				_take_slots(slot, car)
				_set_parked(car, _park_xform(slot, car))
				car.dest = destination().town.id
				aboard.append(car)
			for p in sim.rng.randi_range(maxi(2, fc.passenger_capacity / 10), maxi(4, fc.passenger_capacity / 4)):
				passengers_aboard.append({
					"dest": destination().town.id,
					"variant": sim.rng.randi() % Passenger.MODELS.size(),
				})
			_place(_route_s(traveled))
		2:
			at_a = not at_a
			call = 1
			_place(_dock_s())
			_begin_loading()


## Gives her a schedule: `stop_ids` in turn, `leg_routes[i]` from stop i to the
## next. She starts at the first stop.
func set_legs(stop_ids: Array[int], leg_routes: Array[MapData.Route]) -> void:
	stops = stop_ids
	legs = leg_routes
	call = 0
	at_a = term_a.town.id == stops[0]
	_place(_dock_s())


## The terminal she next comes alongside (where she is, if laid up).
func next_dock() -> Terminal:
	if berth != Berth.WORKING:
		return here()
	if state == State.SAILING:
		return destination()
	return sim.terminals[stops[(call + 1) % stops.size()]]


## Gives her new stops from her next call at one of them (see next_stops).
## `times`: her timetable from then (null keeps the one she has).
func plan_stops(stop_ids: Array[int], leg_routes: Array[MapData.Route], times = null) -> void:
	next_stops = stop_ids
	_next_legs = leg_routes
	_next_timetable.assign(timetable if times == null else times)


## Puts her on `times` at once (her stops stay as they are).
func set_timetable(times: Array[int]) -> void:
	_timetable.replace(times)
	late_by = 0.0
	if between_sailings():
		# A ferry already away from her working slip must return for the new
		# sailing, or at once if she now sails as loading allows.
		var now := sim.abs_minutes()
		_gap_due = now if timetable.is_empty() else _timetable.first_stop_due(now, MAX_DWELL)
		return_requested = false


## Takes the planned stops if she is at one of them. Cars aboard for a stop she
## no longer reaches from here drive off here instead.
func _take_next_stops() -> bool:
	var term_id := here().town.id
	if next_stops.is_empty() or term_id not in next_stops:
		return false
	var came_from := stops[(call - 1 + stops.size()) % stops.size()]
	var k := next_stops.find(term_id)
	for i in next_stops.size():
		if next_stops[i] == term_id and next_stops[(i - 1 + next_stops.size()) % next_stops.size()] == came_from:
			k = i
	stops = next_stops
	legs = _next_legs
	call = k
	set_timetable(_next_timetable)
	_offsets.clear()
	next_stops = []
	_next_legs = []
	_next_timetable = []
	var ahead := _served_from(call)
	for car in aboard:
		if car.dest >= 0 and car.dest not in ahead:
			car.dest = term_id
	for pax in passengers_aboard:
		if pax["dest"] >= 0 and pax["dest"] not in ahead:
			pax["dest"] = term_id
	sim.stops_changed(self)
	return true


## Where on the route curve her hull lies docked at the end she is at.
func _dock_s() -> float:
	return -_inset if at_a else route.length + _inset


func calls_at(term: Terminal) -> bool:
	if stops.is_empty():
		return term == term_a or term == term_b
	return term.town.id in stops


## The islands she carries cars to from call `i`, in the order she reaches them:
## every stop until she is back at stops[i].
func _served_from(i: int) -> Array[int]:
	var out: Array[int] = []
	for k in range(1, stops.size()):
		var j := (i + k) % stops.size()
		if stops[j] == stops[i]:
			break
		if stops[j] not in out:
			out.append(stops[j])
	return out


## What she carries from the terminal she is at.
func serves_from_here() -> Array[int]:
	return _served_from(call)


## What she will carry from her next call at `term` (empty if she never calls there).
func serves_next_call_at(term: Terminal) -> Array[int]:
	for k in stops.size():
		var i := (call + k) % stops.size()
		if stops[i] == term.town.id:
			return _served_from(i)
	return []


## Onto the route of the leg she is about to sail, keeping her hull as it lies.
func _take_leg() -> void:
	var next: MapData.Route = legs[call]
	if next == route:
		return
	var term := here()
	var minus := _minus
	# Whatever water she held round the slip on the old route is free.
	for run in _corridor_runs():
		for e in run[2]:
			if e[1].owner == self:
				e[1].owner = null
	var old := route
	var lying := slip_at(term)
	route = next
	term_a = sim.terminals[route.a]
	term_b = sim.terminals[route.b]
	at_a = term == term_a
	_rev = at_a != minus
	# She stays at the slip she lies at, whichever the new leg's own is.
	_end_slip = [-1, -1]
	if lying >= 0 and lying != term.town.slip_index(route.id):
		_end_slip[0 if at_a else 1] = lying
	_build_yaws()
	_forecasts.clear()
	_place(_dock_s())
	# Off a route she no longer sails (new stops): its water is no longer shared with her.
	if old not in legs:
		sim.marine.refresh_corridors()
	# And she holds the new route's water round it, as she would have docking.
	for run in _corridor_runs():
		if run[0] <= 3.0 and _run_blocks_dock(run, at_a):
			for e in run[2]:
				if e[1].owner == null:
					e[1].owner = self


func here() -> Terminal:
	return term_a if at_a else term_b


## The span and apron at `term`'s slip for this route (null with the classic slip).
func _ramp(term: Terminal) -> SlipRamp:
	var i := slip_at(term)
	return term.slip_ramps[i] if i >= 0 else null


## `local` (a point on her deck at an end) in the world, up on the apron if that lies over it.
func _over_apron(local: Vector3) -> Vector3:
	var p := to_global(local)
	if _ramp(here()):
		p.y += SlipRamp.lift_at(here().to_local(p).z)
	return p


## Cars may cross between the slip and the deck.
func _ramp_down() -> bool:
	var ramp := _ramp(here())
	return ramp == null or ramp.is_down()


func destination() -> Terminal:
	return term_b if at_a else term_a


## How much further in than the route curve's ends this ferry lies docked.
func dock_inset() -> float:
	return _inset


## How far the hull's centre runs from dock to dock.
func run_length() -> float:
	return route.length + 2.0 * _inset


## Where on the route curve the hull's centre is, `t` into this crossing (beyond
## its ends, for a short ferry docking further in).
func _route_s(t: float) -> float:
	return t - _inset if at_a else route.length + _inset - t


## Point `s` along the route curve, carried on straight past its ends (they run
## square out from the slips).
func route_point(s: float) -> Vector3:
	return route_point_on(route, s)


## As route_point, on route `r` (one of her legs).
func route_point_on(r: MapData.Route, s: float) -> Vector3:
	var length := r.length
	if s >= 0.0 and s <= length:
		return r.curve.sample_baked(s)
	var end := 0.0 if s < 0.0 else length
	var inner := clampf(end + (4.5 if s < 0.0 else -4.5), 0.0, length)
	var p := r.curve.sample_baked(end)
	var dir := p - r.curve.sample_baked(inner)
	dir.y = 0.0
	return p + dir.normalized() * absf(s - end)


func _slot_local(i: int) -> Vector3:
	var lane := i % fc.lanes
	var shift := fc.lane_shift[lane] if fc.lane_shift.size() > 0 else 0.0
	return Vector3(fc.cols[lane], fc.deck_y(lane), fc.row_z[floori(i / float(fc.lanes))] + shift)


## Where `car` parks with its slots starting at `slot` (the far end of its run of
## rows): the run's middle, its tractor ahead of that for a rig. Cars face +Z boarding
## at A, -Z at B.
func _park_local(slot: int, car: Vehicle) -> Vector3:
	var fwd := 1.0 if _minus else -1.0
	var p := _slot_local(slot)
	p.z -= fwd * (car.slots - 1) * 0.5 * FerryClass.ROW_SPACING
	p.z -= fwd * car.center_offset
	return p


## Where and which way `car` parks from `slot`: as _park_local, facing along the hull,
## or in an arcing lane laid along the arc between its two ends.
func _park_xform(slot: int, car: Vehicle) -> Transform3D:
	var fwd := 1.0 if _minus else -1.0
	var p := _park_local(slot, car)
	var yaw := 0.0 if _minus else PI
	if fc.arcs(p.x):
		var mid := p.z + fwd * car.center_offset
		var front := _arc_point(p.x, mid + fwd * car.length * 0.5)
		var back := _arc_point(p.x, mid - fwd * car.length * 0.5)
		var dir := (front - back).normalized()
		yaw = atan2(dir.x, dir.z)
		p = (front + back) * 0.5 - dir * car.center_offset
	return Transform3D(Basis(Vector3.UP, yaw), p)


## A point on the arcing lane at `x`, at z (the hull's frame).
func _arc_point(x: float, z: float) -> Vector3:
	return Vector3(fc.arc_x(x, z), Layout.DECK_Y, z)


## Waypoints (global) along the arcing lane at `x` from z0 (not included) to z1.
func _arc_path(x: float, z0: float, z1: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	var n := maxi(1, ceili(absf(z1 - z0) / 2.0))
	for i in range(1, n + 1):
		out.append(to_global(_arc_point(x, lerpf(z0, z1, float(i) / n))))
	return out


## Waypoints (global) between a tween deck's lane at `x` and the main deck at the
## end `e` (+1 or -1): from just inside the ramp's top along the lane, the top, the
## foot, a little on toward the end; reversed coming aboard (`down` false).
func _ramp_path(x: float, e: float, down: bool) -> PackedVector3Array:
	var sx := signf(x)
	var pts := [
		Vector3(x, fc.upper_y, e * (fc.ramp_top.y - 5.0)),
		Vector3(sx * fc.ramp_top.x, fc.upper_y, e * fc.ramp_top.y),
		Vector3(sx * fc.ramp_foot.x, Layout.DECK_Y, e * fc.ramp_foot.y),
		Vector3(sx * fc.ramp_foot.x, Layout.DECK_Y, e * (fc.ramp_foot.y + 2.5)),
	]
	if not down:
		pts.reverse()
	var out := PackedVector3Array()
	for p: Vector3 in pts:
		out.append(to_global(p))
	return out


## Waypoints (global) between the main deck's wing lane at `x` under a tween deck and
## the end `e`: the lane's end under the deck's edge, then down the middle of the
## opening under the ramp and in past its foot; reversed coming aboard (`out` false).
func _wing_path(x: float, e: float, out: bool) -> PackedVector3Array:
	var pts := [Vector3(x, Layout.DECK_Y, e * fc.wing_out_z)]
	for v in fc.wing_via:
		pts.append(Vector3(signf(x) * v.x, Layout.DECK_Y, e * v.y))
	if not out:
		pts.reverse()
	var res := PackedVector3Array()
	for p: Vector3 in pts:
		res.append(to_global(p))
	return res


## The slots of `car`'s run from `slot`, going back toward the end it boards from.
func _take_slots(slot: int, car: Vehicle) -> void:
	deck.reserve(slot, car.slots, _minus, car.get_instance_id())


func _free_slot(car: Vehicle) -> int:
	return deck.find_space(car.slots, car.is_tall, _minus)


func _process(delta: float) -> void:
	_state_time += Units.game_minutes(delta)
	if not _ramp_synced:
		# (A ferry starting the game alongside already has the apron on her deck.)
		_ramp_synced = true
		if state != State.SAILING and _ramp(here()):
			_ramp(here()).snap_down()
	# Both nets up under way; alongside, the one at the docked end (-Z at A) is down
	# while cars drive off and on over it, once the apron is down on the deck.
	var docked := state != State.SAILING and _ramp_down()
	_nets[0].visible = not (docked and _minus)
	_nets[1].visible = not (docked and not _minus)
	if berth != Berth.WORKING:
		_let_go_of_slip()
		_tick_berth(delta)
		if _shift == null:
			_thrust = move_toward(_thrust, 0.0, delta * 0.4)
			_push = 0.0
		wake.hold = false
		_update_trail(delta)
		return
	match state:
		State.UNLOADING:
			_tick_unloading(delta)
		State.LOADING:
			_tick_loading(delta)
		State.SAILING:
			_tick_sailing(delta)
	if state != State.SAILING:
		# Holds the ferry against the dock for a moment after arriving.
		_thrust = move_toward(_thrust, 0.0, delta * 0.4)
		# Then her seaward prop takes up pushing her in as the forward one eases off.
		_push = move_toward(_push, HOLD_THROTTLE, delta * 0.05)
	else:
		_push = 0.0
	wake.hold = _push > 0.0
	_update_lie(delta)
	_update_trail(delta)


func _begin_unloading() -> void:
	_take_next_stops()
	state = State.UNLOADING
	if _ramp(here()):
		_ramp(here()).land()
	_state_time = 0.0
	_dispatch_timer = 0.0
	_last_sent = null
	# Only the cars for this stop drive off; the rest stay aboard for later stops.
	var stop := here().town.id
	_unload_queue = aboard.filter(func(c: Vehicle): return c.dest == stop or c.dest < 0)
	aboard = aboard.filter(func(c: Vehicle): return not (c.dest == stop or c.dest < 0))
	var pax_off: Array[Dictionary] = []
	var pax_stay: Array[Dictionary] = []
	for pax in passengers_aboard:
		if pax["dest"] == stop or pax["dest"] < 0:
			pax_off.append(pax)
		else:
			pax_stay.append(pax)
	passengers_aboard = pax_stay
	_pax_unload_queue = pax_off.slice(0, MAX_VISIBLE_WALKERS)
	_pax_dispatch_timer = 0.0
	var exit_sign := -1.0 if _minus else 1.0
	_unload_queue.sort_custom(func(a: Vehicle, b: Vehicle): return a.position.z * exit_sign > b.position.z * exit_sign)
	for car in _unload_queue:
		deck.release(car.get_instance_id())


func _tick_unloading(delta: float) -> void:
	if not _ramp_down():
		return
	_dispatch_timer -= delta
	_pax_dispatch_timer -= delta
	if not _pax_unload_queue.is_empty() and _pax_dispatch_timer <= 0.0:
		var pax: Dictionary = _pax_unload_queue.pop_front()
		_pax_dispatch_timer = PAX_DISPATCH_GAP
		_walk_off(int(pax["variant"]))
	if not _unload_queue.is_empty():
		var term := here()
		if _dispatch_timer <= 0.0 and (term.unloading_ferry == null or term.unloading_ferry == self):
			term.unloading_ferry = self
			var car: Vehicle = _unload_queue.pop_front()
			_dispatch_timer = _gap_after(car)
			_drive_off(car)
	elif _dispatch_timer < -2.0 and _last_vehicle_clear_of_lot():
		if here().unloading_ferry == self:
			here().unloading_ferry = null
		if lay_up_requested and lay_up_slip(here()) >= 0 and not _held_close_in():
			_begin_tie_up()
		elif _wants_gap_tie_up() and not _held_close_in():
			_gap_due = due()
			_begin_tie_up()
		else:
			_begin_loading()


## Whether, just unloaded at her first stop, her next sailing is far enough off
## (GAP_TIE_UP) to lie at a free tie-up slip here until then.
func _wants_gap_tie_up() -> bool:
	if timetable.is_empty() or call != 0 or not aboard.is_empty() or not passengers_aboard.is_empty() or not next_stops.is_empty():
		return false
	var d := due()
	return d >= 0.0 and d - sim.abs_minutes() >= GAP_TIE_UP and free_tie_up(here()) >= 0


## Outbound vehicles cross the boarding approaches before joining the central
## exit lane. Give the last vehicle room to clear the crossing before loading.
func _last_vehicle_clear_of_lot() -> bool:
	if not is_instance_valid(_last_sent):
		return true
	return here().to_local(_last_sent._tail()).z < Layout.LANE_HEAD


## Seconds before the next car may follow `car`: long enough for it to pull its own
## length (and a gap) clear. Each car then follows the one before it.
func _gap_after(car: Vehicle) -> float:
	return maxf(DISPATCH_GAP, (car.length + Vehicle.FOLLOW_GAP) / car.speed)


func _send(car: Vehicle, path: PackedVector3Array, on_arrive: Callable) -> void:
	car.drive(path, on_arrive)
	car.leader = _last_sent
	_last_sent = car


func _drive_off(car: Vehicle) -> void:
	var exit_z := -fc.end_z if _minus else fc.end_z
	var path := PackedVector3Array()
	var x := car.position.x
	if fc.is_upper(car.position.y):
		# Off a tween deck: along its lane to the ramp's top, down it, and in to the end.
		path.append_array(_ramp_path(x, signf(exit_z), true))
		x = clampf(x, -fc.throat_x, fc.throat_x)
	elif fc.wing_out_z > 0.0 and absf(x) > fc.throat_x:
		# Out of a wing under a tween deck: along it, then in past the ramp's foot.
		path.append_array(_wing_path(x, signf(exit_z), true))
		x = clampf(x, -fc.throat_x, fc.throat_x)
	elif fc.arcs(x):
		# Out of a wing: ahead to the car's nose, then round the hull's curve to the end.
		var lane: float = fc.cols[0]
		for c in fc.cols:
			if absf(c - x) < absf(lane - x):
				lane = c
		var ahead := Vector3(sin(car.rotation.y), 0.0, cos(car.rotation.y))
		var nose := car.position + ahead * (car.center_offset + car.length * 0.5)
		path.append(to_global(_arc_point(lane, nose.z)))
		path.append_array(_arc_path(lane, nose.z, exit_z))
		x = fc.arc_x(lane, exit_z)
	elif absf(x) > fc.throat_x:
		# Out of a wing lane: turn in to the apron's opening past the fork's end.
		path.append(to_global(Vector3(x, Layout.DECK_Y, signf(exit_z) * fc.turn_z)))
		x = clampf(x, -fc.throat_x, fc.throat_x)
	path.append(_over_apron(Vector3(x, Layout.DECK_Y, exit_z)))
	car.reparent(sim.traffic)
	path.append_array(here().exit_path(slip_at(here())))
	_send(car, path, func(c: Vehicle): c.queue_free())


func passenger_count() -> int:
	return passengers_aboard.size()


## The route id used for ticket pricing when boarding for `dest` from `here()`.
func _fare_route_id(dest: int) -> int:
	if sim != null and dest >= 0:
		var direct := sim.route_between(here().town.id, dest)
		if direct != null:
			return direct.id
	if not legs.is_empty():
		return legs[call % legs.size()].id
	return route.id if route != null else -1


## Unique routes served by this ferry's schedule (for per-route pricing UI).
func schedule_routes() -> Array[MapData.Route]:
	var out: Array[MapData.Route] = []
	for r in legs:
		if r != null and r not in out:
			out.append(r)
	if out.is_empty() and route != null:
		out.append(route)
	return out


func _walk_off(variant: int) -> void:
	var exit_z := -fc.end_z if _minus else fc.end_z
	var walk_x := -minf(fc.throat_x, 3.8)
	var pax := sim.make_passenger(variant)
	var start := to_global(Vector3(walk_x, Layout.DECK_Y, exit_z * 0.72))
	pax.position = start
	var path := PackedVector3Array([_over_apron(Vector3(walk_x, Layout.DECK_Y, exit_z))])
	path.append_array(here().passenger_exit_path(slip_at(here())))
	pax.walk(path, func(w: Passenger): w.queue_free())


func _walk_on(pax_data: Dictionary, term: Terminal) -> void:
	var node: Passenger = pax_data.get("node")
	if node == null or not is_instance_valid(node):
		if _pax_walkers_sent >= MAX_VISIBLE_WALKERS:
			return
		node = sim.make_passenger(int(pax_data["variant"]))
		node.position = term._passenger_door_pos()
	_pax_walkers_sent += 1
	_pax_boarding += 1
	var jitter := ((_pax_walkers_sent % 3) - 1) * 0.45
	var entry_z := -fc.end_z if _minus else fc.end_z
	var walk_x := -minf(fc.throat_x, 3.8) + jitter * 0.4
	var path := term.passenger_boarding_path(slip_at(term), jitter)
	path.append(_over_apron(Vector3(walk_x, Layout.DECK_Y, entry_z)))
	path.append(to_global(Vector3(walk_x, Layout.DECK_Y, entry_z * 0.72)))
	node.walk(path, func(w: Passenger):
		_pax_boarding = maxi(0, _pax_boarding - 1)
		w.queue_free())


func _begin_loading() -> void:
	if aboard.is_empty():
		_take_next_stops()
	state = State.LOADING
	_load_phase = LoadPhase.WALK_ONS
	_state_time = 0.0
	_loading_since = sim.abs_minutes()
	_dispatch_timer = 0.0
	_pax_dispatch_timer = 0.0
	_pax_walkers_sent = 0
	_pax_boarding = 0
	_last_sent = null
	speed = 0.0


func _tick_loading(delta: float) -> void:
	_dispatch_timer -= delta
	_pax_dispatch_timer -= delta
	var term := here()
	if not _casting_off and term.unloading_ferry != null and term.unloading_ferry != self:
		_state_time -= Units.game_minutes(delta)  # Waiting for the shared crossing does not spend loading time.
		return
	var serves := serves_from_here()
	var fits := func(c: Vehicle): return _free_slot(c) >= 0
	# On a timetable she boards from MAX_DWELL until BOARD_CLOSE before she is due,
	# and sails on time. Late (in too late for MIN_DWELL before then), she sails
	# as soon as she has loaded.
	var due_at := due()
	var now := sim.abs_minutes()
	var timed := due_at >= 0.0
	var late := timed and _loading_since > due_at - MIN_DWELL
	var boarding_open := _state_time < MAX_DWELL
	if timed and not late:
		boarding_open = now >= due_at - MAX_DWELL and now < due_at - BOARD_CLOSE
	if boarding_open and not _casting_off and _ramp_down():
		match _load_phase:
			LoadPhase.WALK_ONS:
				var timed_cutoff := timed and not late and now >= due_at - BOARD_CLOSE - 4.0
				var has_pax := passengers_aboard.size() < fc.passenger_capacity and term.has_waiting_passengers(serves)
				if timed_cutoff or not has_pax:
					_load_phase = LoadPhase.WALK_ON_CLEAR
				elif _pax_dispatch_timer <= 0.0:
					# Stream animated walkers onto the ramp, then batch any additional queued
					# walk-ons up to this ferry class's passenger capacity before cars load.
					var batch := 1 if _pax_walkers_sent < MAX_VISIBLE_WALKERS else 25
					for _k in batch:
						if passengers_aboard.size() >= fc.passenger_capacity:
							break
						var pax := term.board_next_passenger(serves)
						if pax.is_empty():
							break
						passengers_aboard.append({"dest": pax["dest"], "variant": pax["variant"]})
						sim.collect_passenger_fare(_fare_route_id(int(pax["dest"])))
						_walk_on(pax, term)
					_pax_dispatch_timer = PAX_DISPATCH_GAP
			LoadPhase.WALK_ON_CLEAR:
				if _pax_boarding == 0:
					_load_phase = LoadPhase.VEHICLES
					if not timed:
						_state_time = 0.0
			LoadPhase.VEHICLES:
				if _dispatch_timer <= 0.0:
					var car := term.board_next(serves, fits)
					if car != null:
						_dispatch_timer = _gap_after(car)
						_drive_on(car, term)
	elif not boarding_open and _load_phase == LoadPhase.WALK_ONS:
		_load_phase = LoadPhase.WALK_ON_CLEAR
	elif _load_phase == LoadPhase.WALK_ON_CLEAR and _pax_boarding == 0:
		_load_phase = LoadPhase.VEHICLES
		if not timed:
			_state_time = 0.0
	# (full: nothing waiting would fit; only depart once walk-on phase finished and all walkers are aboard)
	var full := _load_phase == LoadPhase.VEHICLES and not term.has_waiting(serves, fits)
	var queue_empty := _load_phase == LoadPhase.VEHICLES and not term.has_waiting(serves, func(_c: Vehicle): return true)
	var loaded := _load_phase == LoadPhase.VEHICLES and _state_time >= MIN_DWELL and (full or queue_empty or _state_time >= MAX_DWELL)
	if timed:
		loaded = _load_phase == LoadPhase.VEHICLES and now >= due_at - APRON_LIFT and (not late or loaded)
	if _casting_off or (_boarding == 0 and _pax_boarding == 0 and loaded):
		# Apron up before she goes.
		_casting_off = true
		var ramp := _ramp(term)
		if ramp:
			ramp.lift()
			if not ramp.is_clear():
				return
		if timed and now < due_at:
			return
		_casting_off = false
		late_by = maxf(now - due_at, 0.0) if timed else 0.0
		if timed and call == 0:
			_timetable.leave_first_stop()
		captain = next_captain
		_take_leg()
		call = (call + 1) % stops.size()
		cruise = captain.cruise(paced_cruise())
		voyage.depart()
		_slip_chosen = false
		term.sort_overflow()
		_sail_time = 0.0
		# The last crossing's wake has long faded by now, and it lies along the same
		# water, so start a fresh trail.
		wake.clear()


func _drive_on(car: Vehicle, term: Terminal) -> void:
	var slot := _free_slot(car)
	_take_slots(slot, car)
	_boarding += 1
	var park := _park_xform(slot, car)
	var local := park.origin
	var entry_z := -fc.end_z if _minus else fc.end_z
	var path := term.boarding_path(car, slip_at(term))
	var lane := fc.cols[slot % fc.lanes]
	if fc.upper.has(slot % fc.lanes):
		# Up to a tween deck: in over the end, up the ramp on its side, along to the slot.
		path.append(_over_apron(Vector3(clampf(local.x, -fc.throat_x, fc.throat_x), Layout.DECK_Y, entry_z)))
		path.append_array(_ramp_path(local.x, signf(entry_z), false))
	elif fc.wing_out_z > 0.0 and absf(local.x) > fc.throat_x:
		# Into a wing under a tween deck: in past the ramp's foot, then along it.
		path.append(_over_apron(Vector3(clampf(local.x, -fc.throat_x, fc.throat_x), Layout.DECK_Y, entry_z)))
		path.append_array(_wing_path(local.x, signf(entry_z), false))
	elif fc.arcs(lane):
		# Into a wing: in over the end and round the hull's curve to the car's tail,
		# then on along its heading into place.
		var tail := local - park.basis.z * (car.length * 0.5 - car.center_offset)
		path.append(_over_apron(_arc_point(lane, entry_z)))
		path.append_array(_arc_path(lane, entry_z, tail.z))
	else:
		var mouth := clampf(local.x, -fc.throat_x, fc.throat_x)
		path.append(_over_apron(Vector3(mouth, Layout.DECK_Y, entry_z)))
		if mouth != local.x:
			# Into a wing lane: in through the apron's opening, then out round the fork's end.
			path.append(to_global(Vector3(local.x, Layout.DECK_Y, signf(entry_z) * fc.turn_z)))
	path.append(to_global(local))
	_send(car, path, _on_boarded.bind(park, term))
	sim.collect_fare(car, _fare_route_id(car.dest))


func _on_boarded(car: Vehicle, park: Transform3D, term: Terminal) -> void:
	car.reparent(self)
	term.finish_boarding(car)
	_set_parked(car, park)
	aboard.append(car)
	_boarding -= 1


func _set_parked(car: Vehicle, park: Transform3D) -> void:
	car.position = park.origin
	car.rotation = Vector3(0.0, park.basis.get_euler().y, 0.0)
	car.straighten()


func _tick_sailing(delta: float) -> void:
	if _sail_time >= 0.0:
		_sail_time += Units.game_minutes(delta)
	var remaining := run_length() - traveled
	var zone := FerryVoyage.DOCKING_ZONE
	var rem := maxf(remaining, 0.0)
	var traffic_limit := yield_speed()
	var reach := _flex_reach()
	var leaving_end := 0 if at_a else 1
	if _end_slip[leaving_end] >= 0 and traveled - _inset > reach + 5.0:
		_end_slip[leaving_end] = -1   # her track is the route's own again out here
	if not _slip_chosen and remaining - _inset < reach + 60.0:
		_slip_chosen = true
		_choose_slip()
	var wait := minf(minf(_corridor_wait(), _refit_wait()), minf(_slip_wait(), _occupied_wait()))
	wait = minf(wait, _shift_wait())
	hold = wait
	speed = voyage.sailing_speed(delta, run_length(), speed, cruise, traffic_limit, wait, captain.harbour)
	_thrust = move_toward(_thrust, 1.0 if rem < zone and rem > 1.5 else 0.0, delta * 0.8)
	if rem < RAMP_LOWER_AT and _ramp(destination()):
		_ramp(destination()).lower()
	var was := traveled
	# Onto her lane (or back to the centreline) gently when her route has just
	# become shared (or stopped being).
	_lane_k = move_toward(_lane_k, 1.0 if sim.marine.shared(route) else 0.0, delta * LANE_SHIFT)
	# `traveled` counts along the centreline; out on her lane round a bend she has
	# further (or less far) to go, at the same speed through the water.
	voyage.advance(delta, speed / _lane_stretch(_route_s(traveled)), run_length())
	_burn(traveled - was)
	_place(_route_s(traveled))
	_bob_time += delta
	position.y = sin(_bob_time * 1.3) * 0.21
	if voyage.has_arrived(run_length()):
		_dock_corridors()
		hold = INF
		speed = 0.0
		position.y = 0.0
		voyage.arrive()
		if _sail_time >= 0.0:
			previous_crossing = last_crossing
			previous_crossing_captain = last_crossing_captain
			last_crossing = _sail_time
			last_crossing_captain = captain
		_sail_time = -1.0
		last_crossing_fuel = _crossing_fuel
		post_costs(true)
		_begin_unloading()


## The corridors this crossing passes through, in order, grouped into runs where
## one starts before the last ends, as [start, end, [[end, corridor], ...]]
## (distances along the crossing, as `traveled`). A ferry takes a whole run at once, so under
## way it never sits holding one corridor while it waits for the next, and no
## ring of ferries can each be waiting on the one ahead.
func _corridor_runs() -> Array:
	var all := _route_runs()
	var into := _end_slip[1 if at_a else 0] >= 0
	var out := _end_slip[0 if at_a else 1] >= 0
	if not into and not out:
		return all
	# At a slip not the route's own she keeps off its water round that end, and the
	# routes sharing it don't wait for her there (she isn't in their way).
	var reach := _flex_reach() + fc.half_length + _inset
	return all.filter(func(run): return not (into and run[1] > run_length() - reach) and not (out and run[0] < reach))


func _route_runs() -> Array:
	var key := "%d|%s" % [route.id, at_a]
	if _runs.has(key):
		return _runs[key]
	var list := []
	for c: MarineTraffic.Corridor in sim.marine.corridors[route.id]:
		var span: Vector2 = c.span[route.id]
		var t0 := span.x + _inset if at_a else route.length + _inset - span.y
		var t1 := span.y + _inset if at_a else route.length + _inset - span.x
		list.append([t0, t1, c])
	list.sort_custom(func(a, b): return a[0] < b[0])
	var runs := []
	for e in list:
		if not runs.is_empty() and e[0] <= runs[-1][1] + 3.0:
			runs[-1][1] = maxf(runs[-1][1], e[1])
			runs[-1][2].append([e[1], e[2]])
		else:
			runs.append([e[0], e[1], [[e[1], e[2]]]])
	_runs[key] = runs
	return runs


## Distance to go before she must hold off her destination while another ferry
## there is moving between slips. A ferry already inside the hold line waits
## where she is until the manoeuvre is complete.
func _shift_wait() -> float:
	if berth != Berth.WORKING:
		return INF
	var term := destination()
	var dock := term.town.dock_center(route.id)
	var moving := false
	for f in sim.ferries:
		# At her terminal, or at another dock close by whose turn she'd sail through.
		if f != self and f.shifting() and (f.here() == term or f.global_position.distance_to(dock) < SHIFT_NEAR):
			moving = true
			break
	if not moving:
		return INF
	# Inside the hold line she was already holding off (a move can't start with a
	# ferry coming in that close otherwise): she stays where she is.
	return maxf(0.0, path_left() - Terminal.REFIT_HOLD)


## Distance to go before she must hold off her destination's slip while another
## boat lies laid up in it, or is being towed in or out of it (Simulation.occupant):
## Terminal.REFIT_HOLD out, or where she is if she's already inside that. INF if
## the slip is clear, or she is all but alongside.
func _occupied_wait() -> float:
	_lying_in_slip = null
	if berth != Berth.WORKING:
		return INF
	var dest := destination()
	var o := sim.occupant(dest, slip_at(dest), self)
	var left := path_left()
	if o == null or left < 60.0:
		return INF
	_lying_in_slip = o
	return maxf(0.0, left - Terminal.REFIT_HOLD)


## Distance to go before she must hold off her destination's slip while it is refitted
## (Terminal.REFIT_HOLD out; INF if it's open, or she was already inside that when it
## closed, and finishes her call).
func _refit_wait() -> float:
	if berth != Berth.WORKING or not destination().slip_shut(slip_at(destination())):
		return INF
	var left := path_left()
	if left < Terminal.REFIT_HOLD - 5.0:
		return INF
	return maxf(0.0, left - Terminal.REFIT_HOLD)


## Distance to go before the next run of corridors another ferry holds part of
## (INF if none). Reserves the next run when it is free and frees corridors as
## the ferry leaves them behind.
func _corridor_wait() -> float:
	_waiting_for = null
	_giving_way = false
	if traveled < 1.5 and _blocked_at_dock():
		return 0.0
	for run in _corridor_runs():
		# (Not the water round the slip she is coming in to, if lying there she will
		# be in another route's way: she keeps that when she docks, _dock_corridors.)
		var keep := _kept_docked(run)
		for e in run[2]:
			if traveled > e[0] and e[1].owner == self and not keep:
				e[1].owner = null
		if traveled > run[1]:
			continue
		if run[0] - traveled > self_look() + 30.0:
			break
		var holder := _run_holder(run, traveled)
		if holder == null:
			for e in run[2]:
				if traveled <= e[0]:
					e[1].owner = self
		else:
			_waiting_for = holder
			return run[0] - traveled
		break
	return INF


## Ready to cast off: whether to hold in at the dock instead, because a stretch
## of shared water not far out is taken by another ferry (rather than going out
## only to stop short of it), or one coming in here has it still to pass (the
## arrival goes first). Never for a ferry already waiting on this one, which
## this one may be lying in the way of.
func _blocked_at_dock() -> bool:
	# Another ferry moving between slips close by: her way out may cross its turn.
	for f in sim.ferries:
		if f != self and f.shifting() and f.global_position.distance_to(global_position) < SHIFT_NEAR:
			_waiting_for = f
			return true
	for run in _corridor_runs():
		if run[0] - traveled > ARRIVAL_PRIORITY:
			break
		var holder := _run_holder(run, traveled)
		if holder != null and holder._waiting_for != self:
			_waiting_for = holder
			return true
		holder = _arriving_through(run)
		if holder != null:
			_waiting_for = holder
			_giving_way = true
			return true
	return false


## Another ferry coming in to the terminal this one is leaving that has a corridor
## of `run` still to pass and is nearly there: the arrival goes first. (Not one
## already waiting on this ferry, which may be lying in its way.)
func _arriving_through(run: Array) -> Ferry:
	for e in run[2]:
		var c: MarineTraffic.Corridor = e[1]
		for f: Ferry in c.boats:
			if f == self or f.state != State.SAILING or f.destination() != here() or f._waiting_for == self:
				continue
			if f.slip_at(here()) != here().town.slip_index(f.route.id):
				continue   # coming in to another slip: not through this water
			var to_go := f.distance_to(c)
			if to_go >= 0.0 and to_go < ARRIVAL_PRIORITY:
				return f
	return null


## How far this ferry has to go to the run of corridors that holds `c` (0 once
## in it), or -1 if it has passed it or isn't sailing.
func distance_to(c: MarineTraffic.Corridor) -> float:
	if state != State.SAILING:
		return -1.0
	for run in _corridor_runs():
		for e in run[2]:
			if e[1] == c:
				if traveled > e[0]:
					return -1.0
				return maxf(run[0] - traveled, 0.0)
	return -1.0


## Whether a ferry docked at the A end (`end_a`) or B end of the route is in the
## way of another route in `run`.
func _run_blocks_dock(run: Array, end_a: bool) -> bool:
	for e in run[2]:
		var d: Vector2i = e[1].docked[route.id]
		if (d.x if end_a else d.y) == 1:
			return true
	return false


## Another ferry (under way, or docked by it) holding a corridor of `run` this one
## has still to pass, `at` along its crossing.
func _run_holder(run: Array, at: float) -> Ferry:
	for e in run[2]:
		var c: MarineTraffic.Corridor = e[1]
		if at <= e[0] and c.owner != null and c.owner != self:
			return c.owner
	return null


## At the start of the game: a ferry docked at a slip some other route runs
## through takes the run of corridors round it (as one arriving would have); one
## mid-crossing takes the run it is in. If another ferry already has it, this one
## drops back to wait outside, turned round to be arriving if it was docked.
func claim_corridors_at_start() -> void:
	if berth != Berth.WORKING:
		return
	var at := 0.0 if state != State.SAILING else traveled
	for run in _corridor_runs():
		if at < run[0] or at > run[1]:
			continue
		# Docked where it is in nobody's way: it takes the run when it leaves.
		if state != State.SAILING and not _run_blocks_dock(run, at_a):
			return
		if _run_holder(run, at) == null:
			for e in run[2]:
				if at <= e[0]:
					e[1].owner = self
			return
		var was := traveled
		var turned := state != State.SAILING
		if turned:
			at_a = not at_a
			state = State.SAILING
			_state_time = 0.0
			for r in _corridor_runs():
				if r[1] >= run_length() - 3.0:
					at = r[0]
		else:
			at = run[0]
		traveled = maxf(at - fc.half_length, 0.0)
		speed = 0.0
		_place(_route_s(traveled))
		# Try again from where she fell back to, unless she couldn't fall back any
		# further (a run held by another boat starts at her route's very start):
		# then she waits where she is.
		if turned or traveled < was - 0.5:
			claim_corridors_at_start()
		return


## After the corridors were found afresh (a boat took new stops): forgets the
## runs she had worked out, and takes what she would hold now if it is free:
## docked, the water round her slip that is in the way of others; under way,
## the run she is in.
func reclaim_corridors() -> void:
	_runs.clear()
	if berth != Berth.WORKING:
		return
	for run in _corridor_runs():
		if state != State.SAILING:
			if run[0] <= 3.0 and _run_blocks_dock(run, at_a) and _run_holder(run, 0.0) == null:
				for e in run[2]:
					if e[1].owner == null:
						e[1].owner = self
		elif traveled >= run[0] and traveled <= run[1] and _run_holder(run, traveled) == null:
			for e in run[2]:
				if traveled <= e[0]:
					e[1].owner = self


## Whether `run` reaches the slip she is sailing to and, lying there, she will be
## in another route's way: she keeps it from coming in until she leaves again.
func _kept_docked(run: Array) -> bool:
	return run[1] >= run_length() - 3.0 and _run_blocks_dock(run, not at_a)


## Docking: if another route runs so close past this slip that the docked ferry
## is in its way, keeps the run of corridors round it (and takes back any of it
## that it passed coming in and are free), so nothing comes by until it has left
## again. Frees the rest.
func _dock_corridors() -> void:
	for run in _corridor_runs():
		var keep := _kept_docked(run)
		for e in run[2]:
			if keep:
				# (Never from another ferry: one that has taken a corridor this one
				# already passed keeps it.)
				if e[1].owner == null:
					e[1].owner = self
			elif e[1].owner == self:
				e[1].owner = null


func wants_to_move() -> bool:
	return state == State.SAILING


func waiting_on() -> Array[Vessel]:
	var out := super()
	if is_instance_valid(_waiting_for):
		out.append(_waiting_for)
	return out


func ahead(d: float) -> Vector2:
	# Docked, `traveled` still counts the last crossing but at_a has flipped.
	if state != State.SAILING:
		return pos2()
	var s := _route_s(minf(traveled + d, run_length()))
	var p := lane_pose_on(route, s, at_a, _lane_k)
	var shift := _end_shift(s)
	return Vector2(p.x + shift.x, p.z + shift.z)


func path_left() -> float:
	return run_length() - traveled if state == State.SAILING else 0.0


## Positions the ferry at distance s along the route curve. +Z always faces A → B.
func _place(s: float) -> void:
	if state != State.SAILING and sim and sim.marine:
		_lane_k = 1.0 if sim.marine.shared(route) else 0.0
	var p := lane_pose_on(route, s, at_a, _lane_k)
	if _end_slip[0] >= 0 or _end_slip[1] >= 0:
		# Eased across to the slip she uses: off the route's line, and turned to follow.
		var shift := _end_shift(s)
		var t := Vector3(sin(p.w), 0.0, cos(p.w))
		var t2 := t * 2.0 + _end_shift(s + 1.0) - _end_shift(s - 1.0)
		p.w += angle_difference(atan2(t.x, t.z), atan2(t2.x, t2.z))
		p.x += shift.x
		p.z += shift.z
	_base_xf = Transform3D(Basis(Vector3.UP, p.w + (PI if _rev else 0.0)), Vector3(p.x, 0.0, p.z))
	if state == State.SAILING:
		_come_in(run_length() - traveled)
	global_transform = _pose()


## Her pose: _base_xf turned _askew about her middle and swung _lie about her landing
## end (the one towards the terminal she is at or last left: -Z if _minus).
func _pose() -> Transform3D:
	var xf := _straight_xf()
	if absf(_lie) < 1e-6:
		return xf
	var pivot := Vector3(0, 0, -fc.half_length if _minus else fc.half_length)
	var turn := Basis(Vector3.UP, _lie)
	return xf * Transform3D(turn, pivot - turn * pivot)


## Her pose before she swings: where the route puts her, turned askew about her middle.
func _straight_xf() -> Transform3D:
	if _askew == 0.0:
		return _base_xf
	return _base_xf * Transform3D(Basis(Vector3.UP, _askew), Vector3.ZERO)


## The last LAND_RUN metres in: she comes in askew as her captain lands her (chosen as
## she starts in), riding the wing wall on that side in if it's a rough landing.
func _come_in(rem: float) -> void:
	var g := destination().guides_at(slip_at(destination()))
	if g == null or rem > LAND_RUN:
		_landing_side = 0.0
		_askew = 0.0
		return
	if _landing_side == 0.0:
		_choose_landing(g)
	_askew = _landing_askew * (1.0 - smoothstep(LAND_RUN - 10.0, LAND_RUN, rem))
	_press_walls(g, true)


## Which way her landing end comes in off centre and how far askew: a clean landing
## clear of the wing walls, or (as likely as her captain is unsure, 1 - Captain.landing)
## one that rides the wall that side up to WALL_GIVE in.
func _choose_landing(g: SlipGuides) -> void:
	_landing_side = 1.0 if randf() < 0.5 else -1.0
	_landing_askew = 0.0
	# Lying at the dock: how far clear of that wall she is straight, and how much
	# nearer a degree askew brings her (turning her landing end, +Z if _minus coming
	# in, towards that side).
	var s_end := _route_s(run_length())
	var p := route_point(s_end)
	var docked := Transform3D(Basis(Vector3.UP, _yaw_at(s_end) + (PI if _rev else 0.0)), Vector3(p.x, 0.0, p.z))
	var wall := _wall_for(g, docked, _landing_side)
	if wall < 0:
		return
	var probe := _landing_side * (1.0 if _minus else -1.0) * deg_to_rad(1.0)
	var straight := _wall_pens(g, docked, true)[wall]
	var turned := _wall_pens(g, docked * Transform3D(Basis(Vector3.UP, probe), Vector3.ZERO), true)[wall]
	if straight == -INF or turned <= straight:
		return
	var per := (turned - straight) / probe
	if rough_landings or randf() > captain.landing:
		_landing_askew = (randf_range(0.3, 1.0) * WALL_GIVE - straight) / per
	else:
		_landing_askew = randf() * 0.4 * (1.0 - captain.landing) * maxf(-straight, 0.0) / per


## The index in g.walls of the wing wall on her `side` (her x), posed `xf`.
func _wall_for(g: SlipGuides, xf: Transform3D, side: float) -> int:
	var across := (g.global_basis.inverse() * (xf.basis * Vector3(side, 0, 0))).x
	for i in g.walls.size():
		if signf(g.walls[i].side) == signf(across):
			return i
	return -1


## How far (m, negative for clear of it) her landing end reaches into each of the
## slip's wing walls, posed `xf`; `coming_in` picks the end she lands with under way
## (away from the terminal she left) rather than the one she lies docked with.
func _wall_pens(g: SlipGuides, xf: Transform3D, coming_in: bool) -> Array[float]:
	var to_slip := g.global_transform.affine_inverse() * xf
	var plus_end := _minus if coming_in else not _minus
	var end_z := fc.half_length if plus_end else -fc.half_length
	var inward := -signf(end_z)
	var out: Array[float] = []
	for w in g.walls:
		var along := w.b - w.a
		var length := along.length()
		along /= length
		var n := Vector3(along.z, 0, -along.x)
		if n.x * w.side > 0.0:
			n = -n
		var most := -INF
		for k: float in [0.3, 1.5, 3.0, 5.0, 8.0, 12.0, 16.0, 22.0]:
			var z := end_z + inward * k
			var hw := fc.half_width_at(z)
			if hw <= 0.0:
				continue
			for sx: float in [-1.0, 1.0]:
				var q := to_slip * Vector3(sx * hw, 0, z)
				var t := (q - w.a).dot(along)
				if t >= 0.0 and t <= length:
					most = maxf(most, -(q - w.a).dot(n))
		out.append(most)
	return out


## Presses each wing wall in as far as she reaches into it.
func _press_walls(g: SlipGuides, coming_in: bool) -> void:
	var pens := _wall_pens(g, _straight_xf(), coming_in)
	for i in g.walls.size():
		g.walls[i].target = clampf(pens[i] / WALL_GIVE, 0.0, 1.0)


## Alongside: straightens her against the apron if she came in askew, eases her over
## towards the side the tide sets her and presses in the fenders she leans on. Casting
## off, eases her straight again as she pulls away.
func _update_lie(delta: float) -> void:
	var g := here().guides_at(slip_at(here()))
	var docked := g != null and state != State.SAILING
	var target := _lie_target(g) if docked else 0.0
	var straightening := docked and _askew != 0.0
	if absf(target - _lie) < 1e-6 and not straightening:
		return
	_lie = lerpf(_lie, target, minf(1.0, delta * LIE_EASE))
	if straightening:
		_askew = move_toward(_askew, 0.0, maxf(deg_to_rad(0.05), absf(_askew)) * delta * STRAIGHTEN)
		_press_walls(g, false)
	if state != State.SAILING:
		global_transform = _pose()
	if g:
		_press(g)
	if absf(_lie) < 1e-5 and target == 0.0:
		_lie = 0.0
		# Straight again and pulling away: let every fender out.
		for f in (g.fenders if g else []):
			f.target = 0.0


## Straight and square again, with nothing pressed, as she leaves her working slip
## for a tie-up.
func _let_go_of_slip() -> void:
	if _lie == 0.0 and _askew == 0.0:
		return
	_lie = 0.0
	_askew = 0.0
	var g := here().guides_at(slip_at(here()))
	if g:
		for f in g.fenders:
			f.target = 0.0
		for w in g.walls:
			w.target = 0.0


## A fender's face (`f`) in her unswung frame: x across her (signed), z along her.
func _fender_local(g: SlipGuides, f: SlipGuides.Fender) -> Vector3:
	return _straight_xf().affine_inverse() * (g.global_transform * Vector3(f.side * f.face, 0.0, f.u))


## How far she swings to lie against the dolphins on the side the tide sets her: until
## the first fender that side she reaches has her LIE_PRESS into it.
func _lie_target(g: SlipGuides) -> float:
	var sea := 1.0 if _minus else -1.0
	var pivot_z := -sea * fc.half_length
	# The tide's side of the slip, as a side of her.
	var across := _base_xf.basis.inverse() * (g.global_basis * Vector3.RIGHT)
	var side := signf(across.x) * here().lie_side()
	var best := INF
	for f in g.fenders:
		var at := _fender_local(g, f)
		var arm := at.z - pivot_z
		if signf(at.x) != side or arm * sea < 6.0:
			continue
		var hb := fc.half_width_at(at.z)
		if hb <= 0.0:
			continue
		var reach := maxf(0.0, absf(at.x) + LIE_PRESS - hb)
		var turn := asin(clampf(side * reach / arm, -1.0, 1.0))
		if absf(turn) < absf(best):
			best = turn
	if best == INF:
		return side * sea * SHORT_LIE
	return clampf(best, -MAX_LIE, MAX_LIE)


## Presses in each fender as far as her side, swung _lie, reaches into it.
func _press(g: SlipGuides) -> void:
	var sea := 1.0 if _minus else -1.0
	var pivot_z := -sea * fc.half_length
	for f in g.fenders:
		var at := _fender_local(g, f)
		var hb := fc.half_width_at(at.z)
		var into := 0.0
		if hb > 0.0 and (at.z - pivot_z) * sea > 0.0:
			var dx := (at.z - pivot_z) * sin(_lie)
			into = hb + signf(at.x) * dx - absf(at.x)
		f.target = clampf(into / FENDER_GIVE, 0.0, 1.0)


## The slip she uses (or is coming in to) at `term` on this leg, -1 if neither end.
func slip_at(term: Terminal) -> int:
	var e := 0 if term == term_a else (1 if term == term_b else -1)
	if e < 0:
		return -1
	return _end_slip[e] if _end_slip[e] >= 0 else term.town.slip_index(route.id)


## How far out from a slip her track differs from the route's when she uses another
## slip there: straight out of it for Terminal.REAIM_HOLD, then easing over.
func _flex_reach() -> float:
	return Terminal.REAIM_HOLD + _flex_blend()


func _flex_blend() -> float:
	return clampf(route.length - Terminal.REAIM_HOLD - 200.0, 60.0, Terminal.REAIM_BLEND)


## How far her track lies off the route's at `s` (along it from A), at either end
## where she uses a slip that isn't the route's own.
func _end_shift(s: float) -> Vector3:
	var out := Vector3.ZERO
	for e in 2:
		if _end_slip[e] < 0:
			continue
		var t: Terminal = term_a if e == 0 else term_b
		var dv := t.town.slip_offset(_end_slip[e]) - t.town.slip_offset(t.town.slip_index(route.id))
		var d := s if e == 0 else route.length - s
		out += t.town.lateral() * dv * (1.0 - smoothstep(Terminal.REAIM_HOLD, Terminal.REAIM_HOLD + _flex_blend(), d))
	return out


## Coming in: her route's own slip if it is free, else the free working slip nearest
## it that she fits. If none is free she keeps her own and waits as before.
func _choose_slip() -> void:
	var term := destination()
	var e := 1 if at_a else 0
	_end_slip[e] = -1
	var own := term.town.slip_index(route.id)
	var best := term.arrival_slip(own, fc.size, func(i: int): return term.slip_user(i, self) != null)
	if best >= 0 and best != own:
		_end_slip[e] = best
		# Whatever water round her own slip she had taken is free for its other boats.
		for run in _route_runs():
			if run[1] > run_length() - _flex_reach() - fc.half_length - _inset:
				for c in run[2]:
					if c[1].owner == self:
						c[1].owner = null


## Distance to go before she must hold off for the slip she is coming in to, where
## the boat using it isn't one the shared water already makes her wait for: one
## at a slip not its route's own, or any when she is (INF if it is free).
func _slip_wait() -> float:
	if berth != Berth.WORKING or not _slip_chosen:
		return INF
	var left := path_left()
	if left < Terminal.REFIT_HOLD - 5.0:
		return INF
	var term := destination()
	var mine := slip_at(term)
	var flexed := mine != term.town.slip_index(route.id)
	var user := term.slip_user(mine, self)
	if user == null or not (flexed or user.slip_at(term) != term.town.slip_index(user.route.id)):
		return INF
	_waiting_for = user
	return maxf(0.0, left - Terminal.REFIT_HOLD)


## Route `r` was re-aimed at another slip (Terminal.spread_routes): her headings along
## it are found afresh, and if she lies alongside on it (at its other end) she lies
## where its new length puts her.
func route_reshaped(r: MapData.Route) -> void:
	_yaw_cache.erase(r.id)
	_forecasts.clear()
	_runs.clear()
	if route == r:
		_build_yaws()
		if state != State.SAILING and berth == Berth.WORKING:
			_place(_dock_s())


## The curve is a polyline of ~6 m chords, so its own direction turns in kinks
## and changes rate abruptly where each arc meets a straight. Two passes of a box
## filter over the (unwrapped) chord headings give a turn rate that ramps up,
## holds steady round the arc and ramps down again, as under helm.
func _build_yaws() -> void:
	_yaws = _yaws_of(route)


## Her smoothed heading every metre along route `r` (A → B), cached per route.
func _yaws_of(r: MapData.Route) -> PackedFloat32Array:
	if _yaw_cache.has(r.id):
		return _yaw_cache[r.id]
	var n := int(ceil(r.length + 2.0 * YAW_PAD)) + 1
	var raw := PackedFloat32Array()
	raw.resize(n)
	var prev := 0.0
	for i in n:
		var s := i - YAW_PAD
		var d := route_point_on(r, s + 0.5) - route_point_on(r, s - 0.5)
		var y := atan2(d.x, d.z) if Vector2(d.x, d.z).length_squared() > 1e-8 else prev
		if i > 0:
			y = prev + angle_difference(prev, y)
		raw[i] = y
		prev = y
	var ys := _box(_box(raw, int(YAW_EASE)), int(YAW_EASE))
	_yaw_cache[r.id] = ys
	return ys


static func _box(a: PackedFloat32Array, w: int) -> PackedFloat32Array:
	var n := a.size()
	var h := w / 2
	var out := PackedFloat32Array()
	out.resize(n)
	var sum := 0.0
	for i in range(-h, h + 1):
		sum += a[clampi(i, 0, n - 1)]
	for i in n:
		out[i] = sum / (2 * h + 1)
		sum += a[clampi(i + h + 1, 0, n - 1)] - a[clampi(i - h, 0, n - 1)]
	return out


func _yaw_at(s: float) -> float:
	return _yaw_in(_yaws, s)


static func _yaw_in(ys: PackedFloat32Array, s: float) -> float:
	var f := clampf(s + YAW_PAD, 0.0, ys.size() - 1.001)
	var i := int(f)
	return lerpf(ys[i], ys[i + 1], f - i)


## The width of her lane off the route's centreline, at `s` along route `r`, as
## (offset to starboard sailing A → B, its rate per metre of s). Nothing for
## LANE_OUT out of each slip, then she eases over (smoothstep) across lane_ease()
## onto her lane, LANE_WIDTH off the centreline, and back again coming in.
static func lane_offset_on(r: MapData.Route, s: float) -> Vector2:
	var ease := lane_ease(r.length)
	if ease < 1.0:
		return Vector2.ZERO
	var w := minf(lane_width(), ease * 0.3)
	var u := minf(s, r.length - s)
	var x := clampf((u - LANE_OUT) / ease, 0.0, 1.0)
	var slope := w * 6.0 * x * (1.0 - x) / ease
	return Vector2(w * x * x * (3.0 - 2.0 * x), slope if s < r.length * 0.5 else -slope)


## How far she takes to ease over onto her lane on a route `length` long (less on
## a short crossing, so she is on her lane for a good part of it).
static func lane_ease(length: float) -> float:
	return clampf((length * 0.5 - LANE_OUT) * 0.75, 0.0, LANE_EASE)


## Centreline to the middle of a lane: two of the biggest hulls on opposite lanes
## keep LANE_GAP between them.
static func lane_width() -> float:
	if _lane_w < 0.0:
		var biggest := 0.0
		for size: int in FerryClass.TABLE:
			biggest = maxf(biggest, FerryClass.of(size).hull_radius)
		_lane_w = LANE_GAP * 0.5 + biggest + 1.0
	return _lane_w


## How much further she goes on her lane than along the centreline, about `s`.
func _lane_stretch(s: float) -> float:
	if lane_offset_on(route, s).x * _lane_k < 0.5:
		return 1.0
	var a := lane_pose_on(route, s - 3.0, at_a, _lane_k)
	var b := lane_pose_on(route, s + 3.0, at_a, _lane_k)
	return clampf(Vector2(b.x - a.x, b.z - a.z).length() / 6.0, 0.5, 2.0)


## Where her hull's centre lies at `s` along route `r` on the lane for sailing
## A → B (`toward_b`) or B → A, and her heading there (yaw, facing A → B). Only
## on a route two boats share: alone, she sails the centreline.
## `k`: how far out on it (0 the centreline, 1 her lane).
func lane_pose_on(r: MapData.Route, s: float, toward_b: bool, k := 1.0) -> Vector4:
	var ys := _yaws if r == route else _yaws_of(r)
	var theta := _yaw_in(ys, s)
	var c := route_point_on(r, s)
	if k <= 0.0:
		return Vector4(c.x, c.y, c.z, theta)
	var lo := lane_offset_on(r, s) * k
	var side := 1.0 if toward_b else -1.0
	var o := lo.x * side
	# Starboard of A → B: her heading turned a quarter to the right.
	var p := c + Vector3(-cos(theta), 0.0, sin(theta)) * o
	return Vector4(p.x, p.y, p.z, theta - atan(lo.y * side))


func _update_trail(delta: float) -> void:
	var moved := global_position - _last_pos
	moved.y = 0.0
	# The first frame has nothing to compare against.
	var moving := _tracking and moved.length_squared() > 1e-8
	_tracking = true
	_last_pos = global_position
	# The hull's own heading, not the way it moved this frame: that follows the
	# route curve's chords and kinks a few degrees at each, which would swing the
	# wake's bow and stern about. The end leading is the one it moved towards
	# (the ferry is double-ended).
	var fwd := global_basis.z
	fwd.y = 0.0
	fwd = fwd.normalized()
	if moved.dot(fwd) < 0.0:
		fwd = -fwd
	# Only once the ferry is actually under way: on the frame it casts off the
	# heading still points the way it arrived, which would put the first crumb at
	# the wrong end of the hull and fold the trail back on itself. The stern
	# props ease off while the forward prop brakes.
	# Alongside she only swings about her landing end as she lies over, which mustn't
	# turn her wake round: she keeps the heading she came in on.
	var under_way := moving and (state == State.SAILING or _shift != null)
	wake.update(delta, global_position, fwd if under_way else Vector3.ZERO, speed * delta,
			maxf(speed / fc.cruise * (1.0 - 0.6 * _thrust), _shift_churn if _shift != null else 0.0), under_way)
	_blow_nets(moved / delta if moving and delta > 0.0 else Vector3.ZERO, delta)


## The wind the nets feel (net.gdshader): the true wind less the ferry's own way, at
## real speeds, in the hull's frame. Eased, so a jerky frame doesn't snap them.
func _blow_nets(vel: Vector3, delta: float) -> void:
	var wf := sim.wind_from()
	var true_wind := -Vector3(wf.x, 0.0, wf.y) * sim.wind_speed / 3.6
	var local := global_basis.inverse() * (true_wind - vel / Units.SPEED_UP)
	_net_wind = _net_wind.lerp(Vector2(local.x, local.z), minf(1.0, delta * 1.5))
	for net in _nets:
		net.set_instance_shader_parameter("wind", _net_wind)


func wake_hull() -> Vector4:
	return Vector4(fc.half_beam, fc.half_length * 2.0, 1.0, 1.0)


func wake_waterline() -> PackedFloat32Array:
	return fc.waterline()


## Reverse thrust from the forward prop, 0..1 (braking for, or holding at, the dock).
func front_thrust() -> float:
	return _thrust


## Her seaward prop's throttle pushing her in against the apron, alongside.
func stern_push() -> float:
	return _push


func load_count() -> int:
	return aboard.size() + _boarding


func kind_text() -> String:
	return fc.label


func status_text() -> String:
	match berth:
		Berth.DELIVERING:
			if tow and tow.outbound:
				return "Sold · under tow out to sea"
			if tow and tow.waiting:
				return "Under tow · holding off %s until the slip is clear" % here().town.name
			return "Under tow to %s · ~%d min" % [here().town.name, ceili(tow.minutes_left())] if tow else "Under tow"
		Berth.TO_TIE_UP:
			return "Moving to the tie-up slip at " + here().town.name
		Berth.TIED_UP:
			if return_requested:
				return "Tied up at %s · waiting for her slip" % here().town.name
			if between_sailings():
				return "Tied up at %s until her %s sailing" % [here().town.name, Timetable.text(int(round(fmod(_gap_due, Timetable.DAY))))]
			if not assigned:
				return "Laid up at %s · give her stops" % here().town.name
			return ("Tied up at " if here().town.slips[tie_up].tie_up else "Laid up in her slip at ") + here().town.name
		Berth.TO_WORKING:
			return "Returning to service at " + here().town.name
	if lay_up_requested and state != State.UNLOADING:
		return ("Laying up at the next tie-up · " if can_lay_up() else "Laying up · ") + _service_text()
	return _service_text()


func _service_text() -> String:
	if state == State.SAILING and speed < 0.6 and _lying_in_slip:
		return "Holding off %s · %s lies in her slip" % [destination().town.name, _lying_in_slip.ferry_name]
	if state == State.SAILING and speed < 0.6 and _refit_wait() < 30.0:
		return "Holding off %s while her slip is refitted" % destination().town.name
	if state == State.SAILING and speed < 0.6 and _waiting_for:
		if _giving_way:
			return "Holding in for %s to come in" % _waiting_for.ferry_name
		return "Waiting for %s to clear the channel" % _waiting_for.ferry_name
	var holding := holding_text()
	if holding != "":
		return holding
	var due_at := due()
	match state:
		State.UNLOADING:
			return "Unloading at " + here().town.name
		State.LOADING:
			var phase := "Boarding walk-ons" if _load_phase != LoadPhase.VEHICLES else "Loading vehicles"
			if due_at < 0.0:
				return "%s at %s" % [phase, here().town.name]
			if off_shift():
				return "Alongside at %s, crew off · first sailing %s" % [here().town.name, Timetable.text(due_at)]
			if sim.abs_minutes() < due_at - MAX_DWELL:
				return "Alongside at %s · sails %s" % [here().town.name, Timetable.text(due_at)]
			return "%s at %s · sails %s" % [phase, here().town.name, Timetable.text(due_at)]
	var text := "En route to %s (%d min)" % [destination().town.name, ceili(eta_minutes())]
	if late_by >= 2.0:
		text += " · %d min late" % roundi(late_by)
	return text


func eta_minutes() -> float:
	return Units.game_minutes((run_length() - traveled) / (cruise * 0.85))


## Puts `c` in command from her next sailing (at once if she is alongside; a
## crossing under way is finished by the captain who began it).
func assign_captain(c: Captain) -> void:
	next_captain = c
	_offsets.clear()
	if state != State.SAILING:
		captain = c
		cruise = c.cruise(paced_cruise())


## Unhindered crossing time of this route under `c`, in game minutes.
func forecast_minutes(c: Captain) -> float:
	if not _forecasts.has(c.id):
		_forecasts[c.id] = c.crossing_minutes(run_length(), paced_cruise())
	return _forecasts[c.id]


## The captain of the roster who suits this crossing: the quickest across it.
func best_captain() -> Captain:
	var best := Captain.roster()[0]
	for c in Captain.roster():
		if forecast_minutes(c) < forecast_minutes(best):
			best = c
	return best


func minutes_until_departure_from(term: Terminal) -> float:
	var crossing := crossing_minutes()
	var turnaround := 16.0
	if between_sailings() and not lay_up_requested:
		var m := maxf(_gap_due - sim.abs_minutes(), 0.0)
		return m if here() == term else m + crossing + turnaround
	if berth != Berth.WORKING or lay_up_requested:
		return INF
	match state:
		State.LOADING:
			var m := maxf(MIN_DWELL + 2.0 - _state_time, 0.0)
			if due() >= 0.0:
				m = maxf(m, due() - sim.abs_minutes())
			return m if here() == term else m + crossing + turnaround
		State.UNLOADING:
			var m := turnaround
			return m if here() == term else m + crossing + turnaround
	if destination() == term:
		return eta_minutes() + turnaround
	return eta_minutes() + turnaround + crossing + turnaround


func crossing_minutes() -> float:
	return forecast_minutes(next_captain)


# --- Timetable (stage 4) ------------------------------------------------------------

## Planned time alongside at each call, as if every sailing were full: a whole
## deck off, a whole deck on, and the last car aboard and the apron up.
func planned_dwell() -> float:
	var deck_minutes := Units.game_minutes(fc.capacity * PLAN_CAR_GAP)
	return planned_unload() + clampf(deck_minutes, MIN_DWELL, MAX_DWELL) + BOARD_CLOSE


## Of planned_dwell, the part she spends unloading a whole deck.
func planned_unload() -> float:
	return Units.game_minutes(fc.capacity * PLAN_CAR_GAP + 2.0)


## Unhindered minutes for a leg on route `r`, at pace `p` under her next captain.
func leg_minutes(r: MapData.Route, p := pace) -> float:
	return next_captain.crossing_minutes(r.length + 2.0 * _inset, paced_cruise(p))


## Fuel ($) for an unhindered leg on route `r` at pace `p` under her next captain,
## burnt as she sails it (_burn), easing off into the slip included.
func leg_fuel(r: MapData.Route, p := pace) -> float:
	var burn := next_captain.crossing_burn(r.length + 2.0 * _inset, paced_cruise(p))
	return FUEL_PRICE * fc.burn * burn / (fc.cruise * fc.cruise * METRES_PER_NM)


## For a round of `ids` (island ids in turn): offsets[i] is how many minutes after
## she leaves ids[0] she can leave ids[i], and offsets[n] when she can next leave
## ids[0] (the shortest gap between two departures). Empty if a leg has no route.
func plan_offsets(ids: Array[int], p := pace) -> Array[float]:
	var out: Array[float] = [0.0]
	var n := ids.size()
	for i in n:
		var r := sim.route_between(ids[i], ids[(i + 1) % n])
		if r == null:
			return []
		out.append(out[i] + leg_minutes(r, p) + planned_dwell())
	return out


## How long after she leaves ids[0] on a round she is due back there and
## unloaded, for a round with `offsets` (plan_offsets): her crew's shift ends
## this long after the day's last sailing.
func shift_tail(offsets: Array[float]) -> float:
	return offsets[-1] - planned_dwell() + planned_unload()


## Fuel for one complete round of a validated stop list.
func round_fuel(ids: Array[int], p := pace) -> float:
	var fuel := 0.0
	for i in ids.size():
		fuel += leg_fuel(sim.route_between(ids[i], ids[(i + 1) % ids.size()]), p)
	return fuel


## What a day on `times` (Timetable) round `ids` at pace `p` should cost her, on
## the planning numbers the timetable is built from: each sailing makes every
## leg once, unhindered, and her crew are on from CREW_CALL before the first
## sailing until she is due back and unloaded after the last (off_shift).
## {fuel, crew, hours (crew), sailings}; empty with no times or a leg with no route.
func daily_cost(ids: Array[int], times: Array[int], p := pace) -> Dictionary:
	var o := plan_offsets(ids, p)
	if o.is_empty() or times.is_empty():
		return {}
	var span := float(times.max() - times.min()) + CREW_CALL + shift_tail(o)
	# Overnight at a tie-up (GAP_TIE_UP): her crew move her over after the last
	# sailing, and come on early enough to bring her back before the first.
	var distance := _overnight_distance(ids, times, o)
	var night := shift_minutes(distance, p)
	var move_fuel := _shift_fuel(distance, p)
	var morning := maxf(0.0, MAX_DWELL + GAP_MARGIN + night - CREW_CALL) if night > 0.0 else 0.0
	span += night + morning
	var hours := minf(span, Timetable.DAY) / 60.0
	return {"fuel": round_fuel(ids, p) * times.size() + 2.0 * move_fuel, "morning_fuel": move_fuel, "crew": hours * crew_per_hour(), "hours": hours, "sailings": times.size(),
			"morning_crew": morning / 60.0 * crew_per_hour()}


## Metres moving to the tie-up at her first stop after the day's last sailing,
## if the night is long enough to lie there (GAP_TIE_UP) and one is free; 0 if not.
func _overnight_distance(ids: Array[int], times: Array[int], o: Array[float]) -> float:
	if not sim.terminals.has(ids[0]):
		return 0.0
	var term: Terminal = sim.terminals[ids[0]]
	var tie := free_tie_up(term)
	if tie < 0 or Timetable.DAY - float(times.max() - times.min()) - shift_tail(o) < GAP_TIE_UP:
		return 0.0
	var r := sim.route_between(ids[0], ids[1])
	var town := term.town
	return _move_length(town.berth_center(tie), town.berth_center(town.slip_index(r.id)), town)


## daily_cost of the timetable she runs now (or is taking at her next call).
func planned_daily_cost() -> Dictionary:
	if not next_stops.is_empty():
		return daily_cost(next_stops, _next_timetable)
	return daily_cost(stops, timetable)


func _round_offsets() -> Array[float]:
	if _offsets.is_empty():
		_offsets = plan_offsets(stops)
	return _offsets


## The shortest gap her timetable can have between departures, at her pace now.
func round_minutes() -> float:
	var o := _round_offsets()
	return o[-1] if not o.is_empty() else 0.0


## Departures she can't make at her pace now (shown red on the timetable).
func late_sailings() -> Array[bool]:
	return Timetable.too_soon(timetable, round_minutes())


## The game minute (Simulation.abs_minutes) she is due to leave the stop she is
## at, or sailing to; -1 with no timetable, laid up, or before she has started a
## timed round at her first stop.
func due() -> float:
	if timetable.is_empty() or berth != Berth.WORKING or lay_up_requested:
		return -1.0
	if call == 0:
		return _timetable.first_stop_due(sim.abs_minutes(), MAX_DWELL)
	return _timetable.call_due(call, _round_offsets())


## Alongside at her first stop overnight: her crew are off from when she was
## due back and unloaded after the day's last sailing (shift_tail; later if she
## ran late) until shortly before the day's first sailing.
func off_shift() -> bool:
	if timetable.is_empty() or call != 0:
		return false
	# (or at a tie-up between sailings, from when she is tied up)
	var d := _gap_due
	if d < 0.0:
		if berth != Berth.WORKING or state != State.LOADING or _boarding > 0:
			return false
		d = due()
	elif berth != Berth.TIED_UP:
		return false
	if d < 0.0 or int(round(fmod(d, Timetable.DAY))) != timetable[0]:
		return false
	var now := sim.abs_minutes()
	if _timetable.last_departure >= 0.0 and now < _timetable.last_departure + shift_tail(_round_offsets()):
		return false
	return d - now > CREW_CALL


# --- Running costs ------------------------------------------------------------------

## The class's cruise speed at her pace setting; her captain then takes it from there.
func paced_cruise(p := pace) -> float:
	return fc.cruise * PACES[p][0]


## Open-water speed at her pace, under the captain who has (or is taking) the helm.
func cruise_speed() -> float:
	return next_captain.cruise(paced_cruise())


## Takes effect at once, even mid-crossing (unlike a change of captain).
func set_pace(p: int) -> void:
	pace = clampi(p, 0, PACES.size() - 1)
	cruise = captain.cruise(paced_cruise())
	_forecasts.clear()
	_offsets.clear()


func pace_name() -> String:
	return PACES[pace][1]


## Gallons per nautical mile at speed `v` (map m/s).
func burn_at(v: float) -> float:
	var f := v / fc.cruise
	return fc.burn * f * f


## Fuel for `metres` made good at the present speed.
func _burn(metres: float) -> void:
	if metres <= 0.0:
		return
	_crossing_fuel += FUEL_PRICE * metres / METRES_PER_NM * burn_at(speed)


## What a crossing's fuel comes to at her pace (cruising the whole way).
func crossing_fuel_estimate() -> float:
	return FUEL_PRICE * run_length() / METRES_PER_NM * burn_at(cruise_speed())


func crew_per_hour() -> float:
	return fc.crew * CREW_WAGE


## Crew are on the clock all day while she is in service, stood down while she
## lies at a tie-up or overnight between timetabled days (off_shift); `minutes`
## of game time.
func pay_crew(minutes: float) -> void:
	if berth == Berth.TIED_UP and not between_sailings() or berth == Berth.DELIVERING or off_shift():
		return
	_crew_owed += crew_per_hour() * minutes / 60.0


## Puts the fuel and wages metered since the last post on the ledger.
## `trip`: at the end of a crossing (shown as it happens), rather than midnight's.
func post_costs(trip: bool) -> void:
	var fuel := _crossing_fuel
	var crew := _crew_owed
	_crossing_fuel = 0.0
	_crew_owed = 0.0
	fuel_today += fuel
	crew_today += crew
	sim.post_running_costs(self, fuel, crew, trip)


func start_day() -> void:
	fuel_today = 0.0
	crew_today = 0.0


# --- Laying up ----------------------------------------------------------------------

## Speed moving between slips at one terminal, as a share of her cruise.
const SHIFT_PACE := 0.6
## Her top speed going astern between slips, as a share of her cruise.
const SHIFT_ASTERN := 0.45
## How fast she gathers and loses way between slips (share of cruise per second).
const SHIFT_ACCEL := 0.07
## Another ferry sailing this close to the terminal keeps her from moving slips.
const SHIFT_CLEAR := 450.0
## Ferries this close to one moving between slips hold off until she's done.
const SHIFT_NEAR := 500.0


## What she would fetch sold now: her price new × RESALE_SHARE × her condition.
func resale_value() -> int:
	return roundi(fc.price() * RESALE_SHARE * condition)


## Only a boat lying laid up (not between sailings, not on her way) can be sold.
func can_sell() -> bool:
	return berth == Berth.TIED_UP and not between_sailings() and not return_requested


## She can always be laid up: in a free tie-up slip if one of her stops has one,
## else in her own slip where she unloads next (lay_up_slip).
func can_lay_up() -> bool:
	return true


## Where at `term` she lies up: a free tie-up slip she fits, else, when none of
## her stops has one, the working slip she is in (stage 6: a laid-up boat in a
## working slip keeps others off it, which is the player's choice). -1 to sail on.
func lay_up_slip(term: Terminal) -> int:
	var i := free_tie_up(term)
	if i >= 0:
		return i
	for id in stops:
		if sim.terminals.has(id) and free_tie_up(sim.terminals[id]) >= 0:
			return -1   # (one further on has a tie-up: she goes there)
	var mine := slip_at(term)
	return mine if sim.occupant(term, mine, self) == null else -1


## A working slip at `term` that takes a boat of `size`, isn't being refitted,
## and that no boat but `except` calls at, is bound for or lies in (-1 if none).
static func idle_slip(term: Terminal, size: int, except: Ferry = null) -> int:
	var town := term.town
	for j in town.slips.size():
		if town.slips[j].tie_up or not town.slips[j].fits(size) or term.tie_up_closed(j):
			continue
		var used := false
		for f in term.sim.ferries:
			if f == except:
				continue
			if f.berth != Berth.WORKING and f.here() == term and f.tie_up == j:
				used = true
			elif f.assigned or f.berth == Berth.WORKING:
				for r: MapData.Route in f.legs + f._next_legs + [f.route]:
					if (r.a == town.id or r.b == town.id) and town.slip_index(r.id) == j:
						used = true
		if not used:
			return j
	return -1


## A tie-up slip at `term` she fits and no other boat holds (-1 if none).
func free_tie_up(term: Terminal) -> int:
	for i in term.town.tie_ups():
		if not term.town.slips[i].fits(fc.size) or term.tie_up_closed(i):
			continue
		if not sim.fleet_market.berth_reserved(term, i, self):
			return i
	return -1


## The player asks her out of service: she finishes the crossing under way,
## unloads, and ties up at the first terminal of her route with a free tie-up slip.
func request_lay_up() -> void:
	if berth == Berth.DELIVERING:
		return
	return_requested = false
	_gap_due = -1.0   # tied up between sailings: she stays there
	if berth == Berth.WORKING:
		lay_up_requested = true


## Back into service: from the tie-up to her working slip once it is free.
func request_return() -> void:
	if berth == Berth.DELIVERING:
		return
	lay_up_requested = false
	# Back on her timetable from the next round due.
	set_timetable(timetable)
	if berth != Berth.WORKING:
		return_requested = true


func in_service() -> bool:
	return (berth == Berth.WORKING or between_sailings()) and not lay_up_requested


## At or moving to or from a tie-up slip between timed sailings (GAP_TIE_UP),
## rather than laid up.
func between_sailings() -> bool:
	return _gap_due >= 0.0


## Starts the game already lying at a tie-up slip at `term` (one end of her route).
func start_tied_up(term: Terminal) -> bool:
	var i := free_tie_up(term)
	if i < 0:
		return false
	for car in aboard:
		car.queue_free()
	aboard.clear()
	deck.clear()
	at_a = term == term_a
	_begin_loading()
	_place(_dock_s())
	tie_up = i
	berth = Berth.TIED_UP
	global_position = _tie_up_point(i)
	return true


## Bought in play: she starts under tow (DeliveryTow) for slip `i` of `term`, an
## end of her route, where she'll lie laid up with no stops of her own yet.
func start_delivery(term: Terminal, i: int) -> void:
	assigned = false
	at_a = term == term_a
	stops = [term.town.id, (term_b if at_a else term_a).town.id]
	legs = [route, route]
	call = 0
	_begin_loading()
	_place(_dock_s())
	tie_up = i
	berth = Berth.DELIVERING
	global_position = _tie_up_point(i)


## The tug has her alongside: she lies laid up where she was brought.
func end_delivery() -> void:
	berth = Berth.TIED_UP
	speed = 0.0
	_place(_dock_s())
	global_position = _tie_up_point(tie_up)
	if assigned:
		request_return()   # (given stops while still under tow)


## Her first stops (a boat bought in play): onto the leg from where she lies, and
## back into service.
func take_first_stops(stop_ids: Array[int], leg_routes: Array[MapData.Route], times: Array[int]) -> void:
	assigned = true
	var here_id := here().town.id
	stops = stop_ids
	legs = leg_routes
	call = stop_ids.find(here_id)
	next_stops = []
	_next_legs = []
	set_timetable(times)
	_offsets.clear()
	_take_leg()
	# (_take_leg puts her at the working slip of her new first leg; she still lies here)
	for run in _corridor_runs():
		for e in run[2]:
			if e[1].owner == self:
				e[1].owner = null
	global_position = _tie_up_point(tie_up)
	if berth == Berth.TIED_UP:
		request_return()


## Where her hull lies at slip `i` of the terminal she is at (y = 0).
func _tie_up_point(i: int) -> Vector3:
	var isl := here().town
	var p := route_point(_dock_s())
	p.y = 0.0
	return p + isl.lateral() * (isl.slip_offset(i) - isl.slip_offset(isl.slip_index(route.id)))


## Starts her along a fresh _shift: notes where she stops to go ahead and her heading.
func _start_shift(to: Vector3) -> void:
	_shift = SlipShiftPath.build(global_position, to, here().town, fc.half_length)
	_shift_s = 0.0
	_shift_basis = global_basis
	_shift_shore = -here().town.dock_dir
	_shift_shore.y = 0.0
	_shift_shore = _shift_shore.normalized()
	_shift_yaw = 0.0
	# A fresh trail heading out the way she's about to back, not the way she came in.
	wake.clear()
	wake.heading = here().town.dock_dir.normalized()
	_push = 0.0
	_shift_churn = 0.0


## Whether another ferry is coming in to or just leaving this terminal, or lies at
## her working slip, so moving between slips now would put her in its way.
func _shift_blocked(into_working: bool) -> bool:
	var term := here()
	var mine := slip_at(term)
	for f in sim.ferries:
		if f == self:
			continue
		if f.shifting() and (f.here() == term or f.global_position.distance_to(global_position) < SHIFT_NEAR):
			return true
		if into_working and f.berth == Berth.TO_TIE_UP and f.here() == term and f.slip_at(term) == mine:
			return true
		# Its next call is the working slip she'd take (sailing there, or leaving
		# the far end shortly): that water is its, so wait for it to call and
		# leave rather than meet it there. A timed boat sitting alongside for a
		# later sailing hours away doesn't hold the slip.
		if into_working and f.berth == Berth.WORKING and f.destination() == term \
				and f.slip_at(term) == mine:
			var f_due := f.due()
			if f.state == State.SAILING or f_due < 0.0 \
					or f_due - sim.abs_minutes() < MAX_DWELL + shift_minutes(_shift_length(tie_up)):
				return true
		if f.state == State.SAILING:
			if f._waiting_for == self and f.speed < 0.5:
				continue   # holding off for the water she has; she is leaving it
			var near := f.path_left() if f.destination() == term else (f.traveled if f.here() == term else INF)
			# (Or one under way close by, for another dock along the shore.)
			if near < SHIFT_CLEAR or f.global_position.distance_to(global_position) < SHIFT_CLEAR:
				return true
		elif into_working and f.berth == Berth.WORKING and f.here() == term and f.slip_at(term) == mine:
			return true
	if into_working:
		for run in _corridor_runs():
			if run[0] <= 3.0 and _run_holder(run, 0.0) != null:
				return true
	return false


## Whether she has reserved the water for a move between slips.
func shifting() -> bool:
	return _shift != null


## An incoming ferry inside the hold line needs to finish her approach before
## this ferry starts backing out.
func _held_close_in() -> bool:
	var term := here()
	for f in sim.ferries:
		if f != self and f.state == State.SAILING and (f.destination() == term and f.path_left() < Terminal.REFIT_HOLD \
				or f.global_position.distance_to(global_position) < Terminal.REFIT_HOLD):
			return true
	return false


func _begin_tie_up() -> void:
	tie_up = lay_up_slip(here()) if lay_up_requested else free_tie_up(here())
	lay_up_requested = false
	berth = Berth.TO_TIE_UP
	_shift = null
	_state_time = 0.0
	speed = 0.0


func _tick_berth(delta: float) -> void:
	match berth:
		Berth.DELIVERING:
			return   # (the tow moves her)
		Berth.TIED_UP:
			if _gap_due >= 0.0 and sim.abs_minutes() >= _gap_due - MAX_DWELL - GAP_MARGIN - shift_minutes(_shift_length(tie_up)):
				return_requested = true
			if return_requested and (tie_up == slip_at(here()) or not _shift_blocked(true)):
				return_requested = false
				berth = Berth.TO_WORKING
				# Keeps whatever water round her slip a docked ferry would hold.
				for run in _corridor_runs():
					if run[0] <= 3.0 and _run_blocks_dock(run, at_a):
						for e in run[2]:
							if e[1].owner == null:
								e[1].owner = self
				_start_shift(_tie_up_point(slip_at(here())))
			return
		Berth.TO_TIE_UP:
			if _shift == null:
				# Apron up and clear water first.
				var ramp := _ramp(here())
				if ramp:
					ramp.lift()
					if not ramp.is_clear():
						return
				if tie_up != slip_at(here()) and _shift_blocked(false):
					return
				_start_shift(_tie_up_point(tie_up))
	if _follow_shift(delta):
		_shift = null
		speed = 0.0
		if berth == Berth.TO_TIE_UP:
			berth = Berth.TIED_UP
			# Out of the way: whatever she held round her working slip is free.
			for run in _corridor_runs():
				for e in run[2]:
					if e[1].owner == self:
						e[1].owner = null
		else:
			berth = Berth.WORKING
			_gap_due = -1.0
			_place(_dock_s())
			if _ramp(here()):
				_ramp(here()).land()
			_begin_loading()


## Length of the way between her working slip and slip `i` at the terminal she is at.
func _shift_length(i: int) -> float:
	var town := here().town
	var from := _tie_up_point(i)
	var to := _tie_up_point(slip_at(here()))
	return _move_length(from, to, town)


func _move_length(from: Vector3, to: Vector3, town: MapData.Town) -> float:
	# Parallel slips produce the same path length for the same separation and
	# hull length. Reuse it while waiting instead of rebuilding each frame.
	var apart := from.distance_to(to)
	if not is_equal_approx(apart, _return_distance) or fc.half_length != _return_half_length:
		_return_length = SlipShiftPath.build(from, to, town, fc.half_length).length
		_return_distance = apart
		_return_half_length = fc.half_length
	return _return_length


## Game minutes to move `length` metres between slips at her pace (as _follow_shift does).
func shift_minutes(length: float, p := pace) -> float:
	# Roughly: half the way astern and half ahead, each leg gathering way from a
	# stop and losing it again (_follow_shift).
	var c := next_captain.cruise(paced_cruise(p))
	var acc := c * SHIFT_ACCEL
	var t := 0.0
	for top: float in [c * SHIFT_ASTERN, c * SHIFT_PACE]:
		var leg := length * 0.5
		var ramp: float = top * top / acc   # gathering way and losing it again
		t += 2.0 * top / acc + (leg - ramp) / top if leg > ramp else 2.0 * sqrt(leg / acc)
	return Units.game_minutes(t)


## Fuel for backing out and coming ahead. Each leg accelerates and brakes:
## burn per metre scales with speed squared, linearly with distance on each ramp.
func _shift_fuel(length: float, p: int) -> float:
	var cruise_at_pace := next_captain.cruise(paced_cruise(p))
	var acceleration := cruise_at_pace * SHIFT_ACCEL
	var leg := length * 0.5
	var cost := 0.0
	for fraction: float in [SHIFT_ASTERN, SHIFT_PACE]:
		var top := minf(cruise_at_pace * fraction, sqrt(acceleration * leg))
		var ramps := top * top / acceleration
		cost += FUEL_PRICE * burn_at(top) * (leg - 0.5 * ramps) / METRES_PER_NM
	return cost


## Moves her along `_shift`, gathering way and slowing to each stop (the start,
## where she stops going astern to come ahead, and the end), turning to the way
## she's making (stern first on the way out). Her props wash astern of the way she
## pushes, harder as she gathers way. True once she is there.
func _follow_shift(delta: float) -> bool:
	var length := _shift.length
	if is_zero_approx(length):
		return true
	var astern := _shift_s < _shift.cusp
	var top := cruise * (SHIFT_ASTERN if astern else SHIFT_PACE)
	var acc := cruise * SHIFT_ACCEL
	# Distance to the next stop ahead of her, and since the last one.
	var to_stop := (_shift.cusp if astern else length) - _shift_s
	var since := _shift_s if astern else _shift_s - _shift.cusp
	var want := minf(top, sqrt(2.0 * acc * maxf(to_stop, 0.0)) + 0.04 * top)
	speed = minf(want, minf(speed + acc * delta, sqrt(2.0 * acc * maxf(since, 0.0)) + 0.08 * top))
	var was := _shift_s
	var next := _shift_s + speed * delta
	if astern and next > _shift.cusp:
		next = _shift.cusp + 0.01
		speed = 0.0
		wake.clear()   # she goes ahead now: her old trail is off her other end
	_shift_s = minf(next, length)
	_burn(_shift_s - was)
	# Throttle: hard as she gathers way, easing as she carries it; wash astern of her way.
	var gathering := clampf(1.0 - since / 60.0, 0.0, 1.0)
	var want_push := clampf(speed / maxf(top, 0.01), 0.0, 1.0) * 0.5 + gathering * 0.5
	if to_stop < 25.0:
		want_push *= to_stop / 25.0
	# Her props' work shows in her own wake (see _update_trail), not the jet she
	# holds herself in at the dock with, which stays pinned to her end as she turns.
	_shift_churn = move_toward(_shift_churn, want_push, delta * 1.5)
	_push = 0.0
	_thrust = 0.0
	var s := _shift_s
	var path := _shift.points
	var pos := path[-1]
	var tangent := Vector3.ZERO
	for k in range(1, path.size()):
		var seg := path[k].distance_to(path[k - 1])
		if s <= seg or k == path.size() - 1:
			pos = path[k - 1].lerp(path[k], clampf(s / maxf(seg, 0.001), 0.0, 1.0))
			# Look a little ahead along the path so the heading doesn't kink at each point.
			var j := mini(k + 2, path.size() - 1)
			var i := maxi(k - 3, 0)
			if k < _shift.back_count:
				j = mini(j, _shift.back_count - 1)
				tangent = path[i] - path[j]   # going astern: her bow points away from her way
			else:
				i = maxi(i, _shift.back_count - 1)
				tangent = path[j] - path[i]
			break
		s -= seg
	tangent.y = 0.0
	var xf := global_transform
	xf.origin = pos
	if tangent.length_squared() > 1e-6 and _shift_shore != Vector3.ZERO:
		var t := tangent.normalized()
		var target := atan2(_shift_shore.cross(t).y, _shift_shore.dot(t))
		_shift_yaw = lerp_angle(_shift_yaw, target, 1.0 - exp(-delta * 10.0))
		if _shift_s >= length - 0.01:
			_shift_yaw = 0.0
		xf.basis = Basis(Vector3.UP, _shift_yaw) * _shift_basis
	global_transform = xf
	return _shift_s >= length - 0.01
