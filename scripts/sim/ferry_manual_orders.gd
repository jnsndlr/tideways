class_name FerryManualOrders
extends RefCounted
## Manual diversions, holds and timetable restoration for one ferry.

const HOLD_FUEL_PER_MIN := 6.0  # $ a game minute idling
const HOLD_GRACE_MIN := 15.0  # riders put up with this long before it tells
const HOLD_GRUMBLE := 0.003  # turned-away weight per rider per minute after that
const TURN_BACK_SECONDS := 15.0
var holding := false
var manual := false  # under the player's own orders: her timetable is paused
var manual_target := -1  # town id she's sent to
var manual_slip := -1  # the slip there she's to lie in
var stranded_cars := 0
var stranded_walk_ons := 0
var stranded_refunds := 0.0
var _hold_at := 0.0  # where along her run she comes to a stop
var _held_for := 0.0  # game minutes she's held
var _manual_landed := false  # she's at manual_target and has set everyone down
var _manual_resume_due := false  # Return to service asked for before she's there
var _manual_pending: Array = []  # [town id, slip] given mid-shift between slips
var _manual_prev := {}  # the stops, legs and times she goes back to
var _turn_t := -1.0  # 0..1 through swinging round (_tick_turn); -1 when not
var _turn_from := Transform3D()  # her pose as she began to swing
var _turn_sweep := 0.0  # how far she turns (about +-PI), and which way
var _boat: Ferry


func _init(owner: Ferry) -> void:
	_boat = owner


## Pulls her aside where she is (only under way). False if she can't.
func order_hold() -> bool:
	if (
		_boat.berth != FerryLayUp.Berth.WORKING
		or _boat.state != FerryVoyage.State.SAILING
		or manual
	):
		return false
	if holding:
		return true
	holding = true
	_held_for = 0.0
	_hold_at = minf(
		_boat.traveled + _boat.speed * _boat.speed / (2.0 * FerryVoyage.YIELD_DECEL) + 2.0,
		_boat.run_length() - FerryVoyage.DOCKING_ZONE
	)
	_hold_at = maxf(_hold_at, _boat.traveled)
	return true


func _tick_hold(delta: float) -> void:
	var dmin := Units.game_minutes(delta)
	_held_for += dmin
	_boat._crossing_fuel += HOLD_FUEL_PER_MIN * dmin
	if _held_for < HOLD_GRACE_MIN:
		return
	var riders := {}
	for car in _boat.aboard:
		riders[car.dest] = riders.get(car.dest, 0.0) + 1.0
	for p in _boat.passengers_aboard:
		riders[int(p["dest"])] = riders.get(int(p["dest"]), 0.0) + 0.5
	for dest in riders:
		if _boat.sim.terminals.has(dest):
			_boat.sim.terminals[dest].turned_recent += riders[dest] * HOLD_GRUMBLE * dmin


## The towns she can be sent to by hand: where she is and is bound, and any
## terminal one direct route from either that her hull fits.
func manual_reach() -> Array[int]:
	var ends: Array[int] = [_boat.here().town.id]
	if _boat.berth == FerryLayUp.Berth.WORKING and _boat.state == FerryVoyage.State.SAILING:
		ends.append(_boat.destination().town.id)
	var out: Array[int] = ends.duplicate()
	for id: int in _boat.sim.terminals.keys():
		if id in out:
			continue
		for e in ends:
			if _boat.sim.route_between(e, id) != null and _boat.sim.leg_problem(_boat, e, id) == "":
				out.append(id)
				break
	return out


## The slips at `town_id` she fits, as [slip index, "Slip 1" / "Tie-up 1"].
func manual_slips(town_id: int) -> Array:
	var town := _boat.sim.map.towns[town_id]
	var out := []
	var working := 0
	var tie := 0
	for i in town.slips.size():
		var slip := town.slips[i]
		if slip.building:
			continue
		if slip.tie_up:
			tie += 1
		else:
			working += 1
		if slip.fits(_boat.fc.size):
			out.append([i, ("Tie-up %d" % tie) if slip.tie_up else ("Slip %d" % working)])
	return out


## Cars and walk-ons aboard that sending her to `town_id` would set down short.
func manual_strands(town_id: int) -> Vector2i:
	var cars := 0
	var pax := 0
	for car in _boat.aboard:
		if car.dest >= 0 and car.dest != town_id:
			cars += 1
	for p in _boat.passengers_aboard:
		if p["dest"] >= 0 and p["dest"] != town_id:
			pax += 1
	return Vector2i(cars, pax)


## Sends her by hand to slip `slip` at `town_id` (one of manual_reach()). False if
## she can't go there from where she is.
func order_move(town_id: int, slip: int) -> bool:
	if (
		_boat.berth == FerryLayUp.Berth.DELIVERING
		or not _boat.assigned
		or town_id not in manual_reach()
	):
		return false
	var slips := _boat.sim.map.towns[town_id].slips
	if (
		slip < 0
		or slip >= slips.size()
		or slips[slip].building
		or not slips[slip].fits(_boat.fc.size)
	):
		return false
	if _boat.berth == FerryLayUp.Berth.TO_TIE_UP or _boat.berth == FerryLayUp.Berth.TO_WORKING:
		_manual_pending = [town_id, slip]  # (once she's done moving between slips)
		return true
	_manual_pending = []
	holding = false
	if not manual:
		if not _boat.next_stops.is_empty():
			_manual_prev = {
				"stops": _boat.next_stops.duplicate(),
				"legs": _boat._next_legs.duplicate(),
				"times": _boat._next_timetable.duplicate()
			}
		else:
			_manual_prev = {
				"stops": _boat.stops.duplicate(),
				"legs": _boat.legs.duplicate(),
				"times": _boat.timetable.duplicate()
			}
	manual = true
	manual_target = town_id
	manual_slip = slip
	_manual_landed = false
	_manual_resume_due = false
	_boat._lay_up.lay_up_requested = false
	_boat._lay_up.return_requested = false
	_boat._lay_up.gap_due = -1.0
	_boat.next_stops = []
	_boat._next_legs = []
	_boat._next_timetable = []
	_boat.set_timetable([])
	_boat._offsets.clear()
	var here_id := _boat.here().town.id
	if _boat.berth == FerryLayUp.Berth.TIED_UP:
		if town_id == here_id:
			_manual_landed = true
			if slip != _boat.tie_up:
				_boat._lay_up.return_requested = true  # (to her working slip, then on to `slip`)
		else:
			var leg := _boat.sim.route_between(here_id, town_id)
			_boat.stops = [here_id, town_id]
			_boat.legs = [leg, leg]
			_boat.call = 0
			_boat._positioning = true
			_boat._take_leg()
			for run in _boat._corridor_runs():
				for e in run[2]:
					if e[1].owner == _boat:
						e[1].owner = null
			_boat.global_position = _boat._tie_up_point(_boat.tie_up)
			_boat._lay_up.return_requested = true
	elif _boat.state == FerryVoyage.State.SAILING:
		_redirect(town_id)
	else:
		# Alongside, loading or unloading.
		if town_id == here_id:
			_boat._casting_off = false
			_boat._positioning = false
			if _boat.state == FerryVoyage.State.LOADING:
				_boat._begin_unloading()  # (sets everyone down: _manual_set_down)
			else:
				_manual_set_down()
				_boat._queue_disembarking()
		else:
			var leg := _boat.sim.route_between(here_id, town_id)
			_boat.stops = [here_id, town_id]
			_boat.legs = [leg, leg]
			_boat.call = 0
			_boat._positioning = true  # (boarding shut: she casts off as soon as she can)
	_boat.sim.stops_changed(_boat)
	return true


## Under way: on for `town_id` from where she is. Her own destination or the
## terminal she left (she's double-ended: she turns back where she is), or one a
## route reaches from either, by whichever way is shorter.
func _redirect(town_id: int) -> void:
	var from_id := _boat.here().town.id
	var dest_id := _boat.destination().town.id
	var via := -1
	if town_id == from_id:
		_turn_back()
	elif town_id != dest_id:
		var on := _boat.sim.route_between(dest_id, town_id)
		var back := _boat.sim.route_between(from_id, town_id)
		var on_len := (
			_boat.path_left() + on.length
			if on != null and _boat.sim.leg_problem(_boat, dest_id, town_id) == ""
			else INF
		)
		var back_len := (
			_boat.traveled + back.length
			if back != null and _boat.sim.leg_problem(_boat, from_id, town_id) == ""
			else INF
		)
		if back_len < on_len:
			_turn_back()
		via = _boat.destination().town.id
	var now_from := _boat.here().town.id
	var now_dest := _boat.destination().town.id
	if via < 0:
		_boat.stops = [now_from, now_dest]
		_boat.legs = [_boat.route, _boat.route]
	else:
		var onward := _boat.sim.route_between(via, town_id)
		_boat.stops = [now_from, via, town_id]
		_boat.legs = [_boat.route, onward, onward]
		_boat._positioning = true  # (she calls at `via` only to set down whoever is bound there)
	_boat.call = 1
	_boat._slip_chosen = false
	_boat._command.cancel_crossing()


## Mid-crossing, back the way she came: she stops and swings round where she is
## (over to the other lane if the route is shared), and the end that led still leads.
func _turn_back() -> void:
	for run in _boat._corridor_runs():
		for e in run[2]:
			if e[1].owner == _boat:
				e[1].owner = null
	var from := _boat._base_xf if _turn_t < 0.0 else _turn_pose()
	var run_len := _boat.run_length()
	_boat.at_a = not _boat.at_a
	_boat._rev = not _boat._rev  # (so _minus, the end that leads, is the same end)
	_boat.traveled = maxf(run_len - _boat.traveled, 0.0)
	_boat._slip_chosen = false
	_boat.speed = 0.0
	_turn_from = from
	_turn_t = 0.0
	# Where she'll be lying once round, and the way round that takes her towards it
	# (to starboard, if she stays on the centreline).
	_boat._place(_boat._route_s(_boat.traveled))
	var to := _boat._base_xf
	var y0 := from.basis.get_euler().y
	var y1 := to.basis.get_euler().y
	var d := wrapf(y1 - y0, -PI, PI)
	var across := to.origin - from.origin
	across.y = 0.0
	# She heads +Z when _minus (she left from her -Z end), and turning +yaw swings
	# +Z towards +X: turn towards the side she's crossing to.
	var heading := 1.0 if _boat._minus else -1.0
	var want := 1.0 if across.length() < 1.0 or across.dot(from.basis.x) * heading >= 0.0 else -1.0
	if signf(d) != want and absf(d) > PI * 0.5:
		d -= signf(d) * TAU
	_turn_sweep = d
	_boat.global_transform = from
	_boat._base_xf = from
	_boat.wake.clear()


## Her pose `_turn_t` through swinging round: turning about her middle as she
## eases across from where she began to where she'll lie on her way back.
func _turn_pose() -> Transform3D:
	var k := smoothstep(0.0, 1.0, _turn_t)
	var to := _boat._base_xf
	var y0 := _turn_from.basis.get_euler().y
	var origin := _turn_from.origin.lerp(to.origin, smoothstep(0.15, 1.0, _turn_t))
	return Transform3D(Basis(Vector3.UP, y0 + _turn_sweep * k), origin)


## Swinging round (see _turn_back). True while she is still turning.
func _tick_turn(delta: float) -> bool:
	_turn_t = minf(_turn_t + delta / TURN_BACK_SECONDS, 1.0)
	_boat.speed = 0.0
	_boat.hold = INF
	_boat._place(_boat._route_s(_boat.traveled))  # (where she'll lie once round, in _base_xf)
	var xf := _turn_pose()
	if _turn_t >= 1.0:
		_turn_t = -1.0
		return false
	_boat._base_xf = xf
	_boat.global_transform = xf
	# Her props churn as she swings.
	_boat._thrust = move_toward(_boat._thrust, 0.6, delta * 0.8)
	_boat._bob_time += delta
	_boat.position.y = sin(_boat._bob_time * 1.3) * 0.21
	return true


## At manual_target: everyone aboard goes off here. Those bound elsewhere are
## refunded and count against the terminal they were going to.
func _manual_set_down() -> void:
	if not manual or _boat.here().town.id != manual_target:
		return
	_manual_landed = true
	_boat._positioning = false
	_set_down_short(manual_target)


## Everyone aboard bound anywhere but `stop` gets off there: fares refunded, and
## the town they were bound for counts it against the service.
func _set_down_short(stop: int, keep_destinations: Array[int] = []) -> void:
	for car in _boat.aboard:
		if car.dest >= 0 and car.dest != stop and car.dest not in keep_destinations:
			_strand(car.dest, 1.0, car.fare_paid)
			stranded_cars += 1
			car.dest = stop
	for p in _boat.passengers_aboard:
		if p["dest"] >= 0 and p["dest"] != stop and p["dest"] not in keep_destinations:
			_strand(int(p["dest"]), 0.5, float(p.get("fare_paid", 0.0)))
			stranded_walk_ons += 1
			p["dest"] = stop


func _strand(dest: int, weight: float, fare: float) -> void:
	if _boat.sim.terminals.has(dest):
		_boat.sim.terminals[dest].turned_recent += weight
	_boat.sim.ledger.refund_fare(fare)
	stranded_refunds += fare


## Each frame under manual orders (or with one waiting for her to finish a move).
func _manual_tick() -> void:
	if not _manual_pending.is_empty():
		if _boat.berth == FerryLayUp.Berth.WORKING or _boat.berth == FerryLayUp.Berth.TIED_UP:
			var order: Array = _manual_pending
			_manual_pending = []
			order_move(order[0], order[1])
		return
	if not manual or not _manual_landed:
		return
	if _boat.berth == FerryLayUp.Berth.WORKING and _boat.state == FerryVoyage.State.LOADING:
		if _boat._boarding > 0:
			return
		if not _boat.aboard.is_empty() or not _boat.passengers_aboard.is_empty():
			_boat._begin_unloading()  # (any who came aboard as the order was given)
			return
		if _manual_resume_due:
			_manual_resume()
			return
		var term := _boat.here()
		if (
			manual_slip >= 0
			and manual_slip != _boat.slip_at(term)
			and not _boat._held_close_in()
			and _boat.sim.occupant(term, manual_slip, _boat) == null
			and term.slip_user(manual_slip, _boat) == null
		):
			# On to the slip she was sent to (_tick_berth moves her once the water's clear).
			_boat._lay_up.tie_up = manual_slip
			_boat.berth = FerryLayUp.Berth.TO_TIE_UP
			_boat._shift = null
			_boat._state_time = 0.0
			_boat.speed = 0.0
	elif _boat.berth == FerryLayUp.Berth.TIED_UP and _manual_resume_due:
		_manual_resume()


## While moving under a manual order the temporary stops describe the diversion.
## Schedule edits update the service to resume, without redirecting that order.
func service_stops() -> Array[int]:
	return _manual_prev.stops if manual else _boat.stops


func service_times() -> Array[int]:
	if manual:
		return _manual_prev.times
	return _boat._next_timetable if not _boat.next_stops.is_empty() else _boat.timetable


func set_manual_service_plan(
	ids: Array[int], leg_routes: Array[MapData.Route], times: Array[int]
) -> void:
	_manual_prev = {
		"stops": ids.duplicate(), "legs": leg_routes.duplicate(), "times": times.duplicate()
	}


## Return to service: back on the stops she ran before, from where she lies. If
## that isn't one of them she crosses empty to the first she can reach.
func _manual_resume() -> void:
	if (
		not _manual_landed
		or _boat.state == FerryVoyage.State.UNLOADING
		or (_boat.berth != FerryLayUp.Berth.WORKING and _boat.berth != FerryLayUp.Berth.TIED_UP)
	):
		_manual_resume_due = true  # (once she's there and has set everyone down)
		return
	var ids: Array[int] = []
	ids.assign(_manual_prev.get("stops", _boat.stops))
	var lr: Array[MapData.Route] = []
	lr.assign(_manual_prev.get("legs", _boat.legs))
	var times: Array[int] = []
	times.assign(_manual_prev.get("times", []))
	var here_id := _boat.here().town.id
	var target := -1
	if here_id not in ids:
		target = _boat.sim.positioning_stop(_boat, ids)
		if target < 0:
			_manual_resume_due = false
			return  # (no route on from here: she stays under manual orders)
	manual = false
	manual_target = -1
	manual_slip = -1
	_manual_landed = false
	_manual_resume_due = false
	_manual_prev = {}
	_boat._positioning = false
	if target < 0:
		_boat.stops = ids
		_boat.legs = lr
		_boat.call = ids.find(here_id)
		_boat.set_timetable(times)
		_boat._offsets.clear()
		_boat._take_leg()
		if _boat.berth == FerryLayUp.Berth.TIED_UP:
			for run in _boat._corridor_runs():
				for e in run[2]:
					if e[1].owner == _boat:
						e[1].owner = null
			_boat.global_position = _boat._tie_up_point(_boat.tie_up)
			_boat._lay_up.return_requested = true
		else:
			_boat._begin_loading()
	elif _boat.berth == FerryLayUp.Berth.TIED_UP:
		_boat.reposition(target, _boat.sim.route_between(here_id, target), ids, lr, times)
		_boat._lay_up.return_requested = true
	else:
		var leg := _boat.sim.route_between(here_id, target)
		_boat.stops = [here_id, target]
		_boat.legs = [leg, leg]
		_boat.call = 0
		_boat.plan_stops(ids, lr, times)
		_boat._positioning = true
		_boat.set_timetable([])
		_boat._offsets.clear()
		_boat._take_leg()
		_boat._begin_loading()
	_boat.sim.stops_changed(_boat)


func _manual_text() -> String:
	var where: String = _boat.sim.map.towns[manual_target].name
	var slip_name := ""
	for s in manual_slips(manual_target):
		if s[0] == manual_slip:
			slip_name = s[1].to_lower() + " at "
	var back := " · back in service once she's there" if _manual_resume_due else ""
	match _boat.berth:
		FerryLayUp.Berth.TO_TIE_UP:
			return "Manual · moving to %s%s%s" % [slip_name, where, back]
		FerryLayUp.Berth.TO_WORKING:
			return "Manual · leaving the tie-up for %s%s" % [where, back]
		FerryLayUp.Berth.TIED_UP:
			if _manual_landed and _boat.tie_up == manual_slip:
				return "Manual · lying at %s%s · Return to service when ready" % [slip_name, where]
			return "Manual · waiting for clear water to leave for %s" % where
	return _working_status(where, slip_name, back)


func _working_status(where: String, slip_name: String, back: String) -> String:
	if _boat.state == FerryVoyage.State.SAILING:
		var via := (
			""
			if _boat.destination().town.id == manual_target
			else " via %s" % _boat.destination().town.name
		)
		return (
			"Manual · under way to %s%s (%d min)%s" % [where, via, ceili(_boat.eta_minutes()), back]
		)
	if not _manual_landed:
		return "Manual · casting off for %s" % where
	if _boat.state == FerryVoyage.State.UNLOADING:
		return "Manual · setting everyone down at %s" % where
	if manual_slip != _boat.slip_at(_boat.here()):
		return (
			"Manual · alongside at %s · waiting for %sto clear"
			% [where, slip_name.trim_suffix("at ")]
		)
	return "Manual · alongside at %s · Return to service when ready" % where


## The slip she makes for coming in to `term`: the one she was sent to, if it's a
## working slip there, else `own` (her route's).
func _manual_arrival(term: Terminal, own: int) -> int:
	if (
		manual
		and term.town.id == manual_target
		and manual_slip >= 0
		and not term.town.slips[manual_slip].tie_up
	):
		return manual_slip
	return own
