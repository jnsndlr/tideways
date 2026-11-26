class_name FerryLayUpSnapshot
extends RefCounted
## A player-directed lay-up on the boat's own two-stop service. The working
## voyage owns cargo and money; this record owns the suspended orders and shift.


static func needed(f: Ferry) -> bool:
	return (
		f.manual
		or f.berth != Ferry.Berth.WORKING
		or f.lay_up_requested
		or f._positioning
		or f.stranded_cars > 0
		or f.stranded_walk_ons > 0
	)


static func capture(f: Ferry) -> Dictionary:
	var o := f._orders
	if (
		not f.assigned
		or f.berth == Ferry.Berth.DELIVERING
		or f.holding
		or f.between_sailings()
		or o._turn_t >= 0
		or not o._manual_pending.is_empty()
		or not f.next_stops.is_empty()
	):
		return {}
	if (
		f.manual
		and f.berth != Ferry.Berth.WORKING
		and (not o._manual_landed or o.manual_slip != f.tie_up)
	):
		return {}
	if (f._positioning and not f.manual) or f._end_slip != [-1, -1] or f.legs != [f.route, f.route]:
		return {}
	var record := {
		"berth": Ferry.Berth.keys()[f.berth],
		"tie": f.tie_up,
		"requested": f.lay_up_requested,
		"returning": f.return_requested,
		"positioning": f._positioning,
		"refunds": o.stranded_refunds,
		"stranded_cars": o.stranded_cars,
		"stranded_walkers": o.stranded_walk_ons,
	}
	if o.manual:
		var plan := f.itinerary.suspended
		if (
			plan == null
			or plan.legs != [f.route, f.route]
			or plan.stops.size() != 2
			or o.manual_target not in f.stops
			or not f.timetable.is_empty()
		):
			return {}
		record.order = {
			"target": f.sim.map.towns[o.manual_target].key,
			"slip": o.manual_slip,
			"landed": o._manual_landed,
			"resume": o._manual_resume_due,
			"stops": plan.stops.map(func(i): return f.sim.map.towns[i].key),
			"departures": plan.times.duplicate(),
		}
	if f.berth != Ferry.Berth.WORKING:
		record.position = SnapshotVector3.encode(f.global_position)
		record.forward = SnapshotVector3.encode(f.global_basis.z)
		if f.shifting():
			record.shift = {
				"start": SnapshotVector3.encode(f._shift.points[0]),
				"forward": SnapshotVector3.encode(f._shift_basis.z),
				"distance": f._shift_s,
				"yaw": f._shift_yaw,
				"churn": f._shift_churn,
			}
		if f.berth == Ferry.Berth.TO_TIE_UP and not f.shifting():
			var ramp := f._ramp(f.here())
			if ramp:
				record.ramp = [ramp.span_fraction, ramp.apron_fraction]
	return record


## Install manual membership before rebuilding the lanes. All edits are to a
## private fresh world; the full voyage is validated before it can become live.
static func prepare(r: Variant, service: Variant, f: Ferry) -> bool:
	if not r is Dictionary or not service is Dictionary or not service.get("stops") is Array:
		return false
	if not r.has("order"):
		return true
	var order = r.order
	var keys := [f.term_a.town.key, f.term_b.town.key]
	var reverse := [keys[1], keys[0]]
	if (
		not order is Dictionary
		or order.get("target") not in keys
		or order.get("stops") not in [keys, reverse]
		or service.stops not in [keys, reverse]
		or service.get("departures") != []
	):
		return false
	var target := f.term_a if order.target == keys[0] else f.term_b
	if (
		not _slip(order.get("slip"), target, f)
		or not order.get("landed") is bool
		or not order.get("resume") is bool
		or not order.get("departures") is Array
	):
		return false
	var times: Array[int] = []
	for time in order.departures:
		if not CompanySnapshot._integer_in(time, 0, Timetable.DAY - 1):
			return false
		times.append(int(time))
	var original: Array[int] = [f.term_a.town.id, f.term_b.town.id]
	if order.stops == reverse:
		original.reverse()
	var routes: Array[MapData.Route] = [f.route, f.route]
	f.itinerary.suspended = FerryItinerary.Plan.new(original, routes, times)
	var stops: Array[int] = [f.term_a.town.id, f.term_b.town.id]
	if service.stops == reverse:
		stops.reverse()
	f.itinerary.set_circuit(stops, routes)
	f._orders.manual = true
	f._orders.manual_target = target.town.id
	f._orders.manual_slip = int(order.slip)
	f._orders._manual_landed = order.landed
	f._orders._manual_resume_due = order.resume
	return true


static func install(r: Dictionary, f: Ferry) -> bool:
	var berth := Ferry.Berth.keys().find(r.get("berth"))
	if berth < 0 or berth == Ferry.Berth.DELIVERING:
		return false
	for key in ["requested", "returning", "positioning"]:
		if not r.get(key) is bool:
			return false
	if (
		not CompanySnapshot._integer_in(r.get("tie"), -1, f.here().town.slips.size() - 1)
		or not CompanySnapshot._integer_in(r.get("stranded_cars"), 0, 9007199254740991)
		or not CompanySnapshot._integer_in(r.get("stranded_walkers"), 0, 9007199254740991)
		or not FerryCrossingSnapshot._number(r.get("refunds"))
		or r.refunds < 0
	):
		return false
	if (
		f.manual
		and f._orders._manual_landed
		and (f.here().town.id != f._orders.manual_target or f.state == Ferry.State.SAILING)
	):
		return false
	if (
		(r.positioning and not f.manual)
		or (r.requested and (f.manual or berth != Ferry.Berth.WORKING))
		or (r.returning and berth != Ferry.Berth.TIED_UP)
	):
		return false
	if (
		f.manual
		and berth != Ferry.Berth.WORKING
		and (not f._orders._manual_landed or f._orders.manual_slip != int(r.tie))
	):
		return false
	if (
		not f.manual
		and berth == Ferry.Berth.WORKING
		and not r.requested
		and r.stranded_cars == 0
		and r.stranded_walkers == 0
	):
		return false
	if berth != Ferry.Berth.WORKING:
		if (
			not _slip(r.tie, f.here(), f)
			or f.state != Ferry.State.LOADING
			or not f.aboard.is_empty()
			or not f.passengers_aboard.is_empty()
			or f._boarding != 0
			or f._casting_off
		):
			return false
		if not SnapshotVector3.valid(r.get("position")) or not _forward(r.get("forward")):
			return false
		if not _install_berth(r, f, berth):
			return false
	elif r.has("shift") or r.has("ramp") or r.has("position") or r.has("forward"):
		return false
	f._lay_up.tie_up = int(r.tie)
	f.berth = berth as Ferry.Berth
	f._lay_up.lay_up_requested = r.requested
	f._lay_up.return_requested = r.returning
	f._positioning = r.positioning
	f._orders.stranded_cars = int(r.stranded_cars)
	f._orders.stranded_walk_ons = int(r.stranded_walkers)
	f._orders.stranded_refunds = r.refunds
	return true


static func _install_berth(r: Dictionary, f: Ferry, berth: int) -> bool:
	var tie := f._tie_up_point(int(r.tie))
	var working := f._tie_up_point(f.slip_at(f.here()))
	var pos := SnapshotVector3.decode(r.position)
	if (
		(berth == Ferry.Berth.TO_WORKING and not r.has("shift"))
		or (berth == Ferry.Berth.TIED_UP and r.has("shift"))
	):
		return false
	var toward_work := berth == Ferry.Berth.TO_WORKING
	# A ferry at the working ramp can still be leaning on its fenders.
	var dock_allowance := 2.0 * f.fc.half_length * sin(Ferry.MAX_LIE * 0.5) + 0.2
	if r.has("shift"):
		var origin := tie if toward_work else working
		var destination := working if toward_work else tie
		if not _install_shift(r, f, origin, destination, 0.1 if toward_work else dock_allowance):
			return false
	elif berth == Ferry.Berth.TIED_UP:
		if pos.distance_to(tie) > 0.1:
			return false
	elif pos.distance_to(working) > dock_allowance:
		return false
	if r.has("ramp"):
		var ramp := f._ramp(f.here())
		if (
			berth != Ferry.Berth.TO_TIE_UP
			or r.has("shift")
			or not ramp
			or not FerryCrossingSnapshot._valid_lift(r.ramp, ramp)
		):
			return false
		ramp.resume_lift(r.ramp[0], r.ramp[1])
	f.global_transform = Transform3D(_basis(r.forward), pos)
	f._ramp_synced = true
	return true


static func _install_shift(
	r: Dictionary, f: Ferry, origin: Vector3, destination: Vector3, allowance: float
) -> bool:
	var shift = r.shift
	if (
		not shift is Dictionary
		or not SnapshotVector3.valid(shift.get("start"))
		or not _forward(shift.get("forward"))
	):
		return false
	for key in ["distance", "yaw", "churn"]:
		if not FerryCrossingSnapshot._number(shift.get(key)):
			return false
	var start := SnapshotVector3.decode(shift.start)
	if (
		start.distance_to(origin) > allowance
		or absf(shift.yaw) > TAU
		or shift.churn < 0
		or shift.churn > 1
	):
		return false
	f.global_transform = Transform3D(_basis(shift.forward), start)
	f._start_shift(destination)
	if shift.distance < 0 or shift.distance > f._shift.length:
		return false
	var expected := _point_on_shift(f._shift.points, shift.distance)
	if expected.distance_to(SnapshotVector3.decode(r.position)) > 0.05:
		return false
	var heading := Basis(Vector3.UP, shift.yaw) * f._shift_basis.z
	if heading.distance_to(SnapshotVector3.decode(r.forward)) > 0.001:
		return false
	f._shift_s = shift.distance
	f._shift_yaw = shift.yaw
	f._shift_churn = shift.churn
	return true


static func _point_on_shift(points: PackedVector3Array, distance: float) -> Vector3:
	for i in range(1, points.size()):
		var length := points[i - 1].distance_to(points[i])
		if distance <= length:
			return points[i - 1].lerp(points[i], distance / maxf(length, 0.001))
		distance -= length
	return points[-1]


static func _slip(i: Variant, term: Terminal, f: Ferry) -> bool:
	return (
		CompanySnapshot._integer_in(i, 0, term.town.slips.size() - 1)
		and not term.town.slips[int(i)].building
		and term.town.slips[int(i)].fits(f.fc.size)
	)


static func _basis(forward: Array) -> Basis:
	var z := SnapshotVector3.decode(forward)
	return Basis(Vector3.UP.cross(z), Vector3.UP, z)


static func _forward(value: Variant) -> bool:
	if not SnapshotVector3.valid(value):
		return false
	var z := SnapshotVector3.decode(value)
	return is_zero_approx(z.y) and is_equal_approx(z.length_squared(), 1)
