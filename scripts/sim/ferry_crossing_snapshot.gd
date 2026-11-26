class_name FerryCrossingSnapshot
extends RefCounted
## One working, two-stop ferry, during boarding or its crossing. Restore into
## an empty hull after rebuilding the same network, timetable, captain and class.
## The company owns the clock, ledger and waiting queues separately. Restore the
## network's corridor reservations after installing every hull's position.
const VERSION := 6
const NUMBERS := [
	"distance",
	"speed",
	"state_minutes",
	"loading_since",
	"dispatch",
	"elapsed",
	"crossing_fuel",
	"crew_owed",
	"fuel_today",
	"crew_today",
	"last_fuel",
	"late_by",
	"lane_fraction",
	"bob",
	"lie",
	"askew",
	"landing_side",
	"landing_askew",
	"last_crossing",
	"previous_crossing",
	"last_departure",
	"round_start",
]


static func capture(ferry: Ferry) -> Dictionary:
	var lay_up := {}
	if FerryLayUpSnapshot.needed(ferry):
		lay_up = FerryLayUpSnapshot.capture(ferry)
		if lay_up.is_empty():
			return {}
	elif not _ordinary_service(ferry):
		return {}
	if ferry.state not in [Ferry.State.SAILING, Ferry.State.LOADING, Ferry.State.UNLOADING]:
		return {}
	var walking := (
		ferry.state == Ferry.State.LOADING and ferry._load_phase != Ferry.LoadPhase.VEHICLES
	)
	if (
		ferry._casting_off
		and (walking or ferry.state != Ferry.State.LOADING or ferry._boarding != 0)
	):
		return {}
	if not walking and not ferry._pax_walkers.is_empty():
		return {}
	var vehicles = FerryVehicleManifest.capture(ferry)
	if vehicles == null:
		return {}
	var command := ferry._command
	var record := {
		"version": VERSION if not lay_up.is_empty() else 5,
		"service": service_record(ferry),
		"phase": "crossing" if ferry.state == Ferry.State.SAILING else "boarding",
		"from": ferry.here().town.key,
		"reversed": ferry._rev,
		"call": ferry.call,
		"trips": ferry.trips,
		"distance": ferry.traveled,
		"speed": ferry.speed,
		"state_minutes": ferry.voyage.state_time,
		"loading_since": ferry._loading_since,
		"dispatch": ferry._dispatch_timer,
		"elapsed": command._elapsed,
		"last_crossing": command.last_crossing,
		"previous_crossing": command.previous_crossing,
		"last_captain": _captain_id(command.last_crossing_captain),
		"previous_captain": _captain_id(command.previous_crossing_captain),
		"last_departure": ferry.itinerary.clock.last_departure,
		"round_start": ferry.itinerary.clock._round_start,
		"crossing_fuel": ferry._crossing_fuel,
		"crew_owed": ferry._crew_owed,
		"fuel_today": ferry.fuel_today,
		"crew_today": ferry.crew_today,
		"last_fuel": ferry.last_crossing_fuel,
		"late_by": ferry.late_by,
		"lane_fraction": ferry._lane_k,
		"bob": ferry._bob_time,
		"lie": ferry._lie,
		"askew": ferry._askew,
		"landing_side": ferry._landing_side,
		"landing_askew": ferry._landing_askew,
		"slip_chosen": ferry._slip_chosen,
		"vehicles": vehicles,
		"passengers": _capture_passengers(ferry.passengers_aboard, ferry),
		"homeward_walkers": FerryWalkOnSnapshot.capture_walkers(ferry._homeward_walkers),
	}
	if not lay_up.is_empty():
		record.lay_up = lay_up
	if ferry.state == Ferry.State.SAILING:
		# _update_lie eases the simulation angle after place_underway applies this frame.
		record.sailing_pose = {
			"position": SnapshotVector3.encode(ferry.global_position),
			"forward": SnapshotVector3.encode(ferry.global_basis.z),
		}
	if ferry.state == Ferry.State.UNLOADING:
		var ramp := ferry._ramp(ferry.here())
		record.phase = "unloading"
		record.unloading = {
			"ramp": [ramp.span_fraction, ramp.apron_fraction] if ramp else null,
			"owns_terminal": ferry.here().unloading_ferry == ferry,
			"passengers": _capture_passengers(ferry._pax_unload_queue, ferry),
			"passenger_dispatch": ferry._pax_dispatch_timer,
			"passengers_per_tick": ferry._pax_unload_per_tick,
		}
	if ferry._casting_off:
		record.phase = "casting_off"
		var ramp := ferry._ramp(ferry.here())
		record.lifting_ramp = [ramp.span_fraction, ramp.apron_fraction] if ramp else null
	if walking:
		record.phase = "walk_ons"
		record.walk_ons = FerryWalkOnSnapshot.capture(ferry)
	return record


static func _capture_passengers(aboard: Array[Dictionary], ferry: Ferry) -> Array:
	var passengers := []
	for pax in aboard:
		var dest: int = pax.dest
		(
			passengers
			. append(
				{
					"town": ferry.sim.map.towns[dest].key if dest >= 0 else "",
					"variant": pax.variant,
					"fare_paid": pax.fare_paid,
				}
			)
		)
	return passengers


static func _ordinary_service(ferry: Ferry) -> bool:
	return (
		ferry.berth == Ferry.Berth.WORKING
		and not ferry.manual
		and not ferry.holding
		and not ferry._positioning
		and not ferry.lay_up_requested
		and ferry.next_stops.is_empty()
		and ferry.stops.size() == 2
		and ferry.term_a != ferry.term_b
		and ferry._end_slip == [-1, -1]
	)


static func _captain_id(person: Captain) -> String:
	return "" if person == null else person.id


static func service_record(ferry: Ferry) -> Dictionary:
	var stops := []
	for id in ferry.stops:
		stops.append(ferry.sim.map.towns[id].key)
	return {
		"seed": str(ferry.sim.map.map_seed),
		"hull": ferry.fleet_key,
		"class": float(ferry.fc.size),
		"route": ferry.route.key,
		"stops": stops,
		"departures": ferry.timetable.map(func(minute: int): return float(minute)),
		"pace": float(ferry.pace),
		"captain": ferry.captain.id,
		"next_captain": ferry.next_captain.id,
	}


## Stage every vehicle before touching the destination hull. Installing a vehicle
## resumes its paid booking and never calls the fare collection path.
static func restore(record: Variant, ferry: Ferry, build_vehicle: Callable) -> bool:
	if (
		(
			not _ordinary_service(ferry)
			and not (ferry.manual and record is Dictionary and record.has("lay_up"))
		)
		or not _empty_hull(ferry)
		or not ferry._pax_walkers.is_empty()
	):
		return false
	if not record is Dictionary or not _valid_state(record, ferry):
		return false
	var passengers: Array[Dictionary] = []
	if not _read_passengers(record.get("passengers"), ferry, passengers):
		return false
	var walking: bool = record.phase == "walk_ons"
	if walking and not FerryWalkOnSnapshot.valid(record.get("walk_ons"), passengers):
		return false
	var at_a: bool = record.from == ferry.term_a.town.key
	var sailing: bool = record.phase == "crossing"
	var departure := ferry.term_a if at_a else ferry.term_b
	var casting_off: bool = record.phase == "casting_off"
	var ramp := ferry._ramp(departure)
	if casting_off and not _valid_lift(record.get("lifting_ramp"), ramp):
		return false
	var unloading: bool = record.phase == "unloading"
	var waiting_to_leave: Array[Dictionary] = []
	if (
		unloading
		and not _valid_unloading(record.unloading, ferry, departure, passengers, waiting_to_leave)
	):
		return false
	var homeward: Variant = record.get("homeward_walkers", [])
	if not FerryWalkOnSnapshot.valid_walkers(homeward):
		return false
	var manifest := FerryVehicleManifest.prepare(
		record.get("vehicles"),
		ferry,
		at_a != record.reversed,
		build_vehicle,
		departure,
		sailing or walking or casting_off or unloading,
		unloading
	)
	if manifest == null:
		return false
	ferry._casting_off = casting_off
	if casting_off:
		ferry._ramp_synced = true
		if ramp:
			ramp.resume_lift(record.lifting_ramp[0], record.lifting_ramp[1])
	ferry.state = Ferry.State.SAILING if sailing else Ferry.State.LOADING
	if unloading:
		var off: Dictionary = record.unloading
		ferry.state = Ferry.State.UNLOADING
		ferry._ramp_synced = true
		if ramp:
			ramp.resume_landing(off.ramp[0], off.ramp[1])
		if off.owns_terminal:
			departure.unloading_ferry = ferry
		ferry._pax_unload_queue = waiting_to_leave
		ferry._pax_dispatch_timer = off.passenger_dispatch
		ferry._pax_unload_per_tick = int(off.passengers_per_tick)
	ferry.at_a = at_a
	ferry._rev = record.reversed
	ferry._load_phase = Ferry.LoadPhase.VEHICLES
	ferry.voyage.state_time = record.state_minutes
	ferry.traveled = record.distance
	ferry.speed = record.speed
	ferry.itinerary.call = int(record.call)
	ferry.trips = int(record.trips)
	ferry._loading_since = record.loading_since
	ferry._dispatch_timer = record.dispatch
	ferry._crossing_fuel = record.crossing_fuel
	ferry._crew_owed = record.crew_owed
	ferry.fuel_today = record.fuel_today
	ferry.crew_today = record.crew_today
	ferry.last_crossing_fuel = record.last_fuel
	ferry.late_by = record.late_by
	ferry.itinerary.clock.last_departure = record.last_departure
	ferry.itinerary.clock._round_start = record.round_start
	var command := ferry._command
	command._elapsed = record.elapsed
	command.last_crossing = record.last_crossing
	command.previous_crossing = record.previous_crossing
	command.last_crossing_captain = _captain(record.last_captain)
	command.previous_crossing_captain = _captain(record.previous_captain)
	ferry._bob_time = record.bob
	ferry._lane_k = record.lane_fraction
	ferry._lie = record.lie
	ferry._askew = record.askew
	ferry._landing_side = record.landing_side
	ferry._landing_askew = record.landing_askew
	ferry._slip_chosen = record.slip_chosen
	if sailing:
		ferry.place_underway()
		if record.has("sailing_pose"):
			var forward := SnapshotVector3.decode(record.sailing_pose.forward)
			var position := SnapshotVector3.decode(record.sailing_pose.position)
			ferry.global_transform = Transform3D(
				Basis(Vector3.UP.cross(forward), Vector3.UP, forward), position
			)
	else:
		ferry._place(ferry._dock_s())
	ferry.passengers_aboard = passengers
	manifest.install(ferry)
	FerryWalkOnSnapshot.install_walkers(
		homeward, ferry, ferry._homeward_walkers, ferry._on_walker_home
	)
	if walking:
		FerryWalkOnSnapshot.install(record.walk_ons, ferry)
	return not record.has("lay_up") or FerryLayUpSnapshot.install(record.lay_up, ferry)


static func _empty_hull(ferry: Ferry) -> bool:
	return (
		ferry.aboard.is_empty()
		and ferry.passengers_aboard.is_empty()
		and ferry._boarding == 0
		and ferry._homeward_walkers.is_empty()
		and ferry._unload_queue.is_empty()
		and ferry._pax_unload_queue.is_empty()
		and ferry.deck.occupants.count(0) == ferry.deck.occupants.size()
	)


static func _valid_state(r: Dictionary, ferry: Ferry) -> bool:
	if (
		not _integer(r.get("version"), VERSION)
		or r.version < 1
		or r.has("lay_up") != (r.version >= 6)
		or (
			r.has("lay_up")
			and (not r.lay_up is Dictionary or r.lay_up.has("order") != ferry.manual)
		)
		or (r.has("walk_ons") != (r.get("phase") == "walk_ons"))
		or (r.has("walk_ons") and r.version < 2)
		or (r.has("lifting_ramp") != (r.get("phase") == "casting_off"))
		or (r.has("lifting_ramp") and r.version < 3)
		or (r.has("unloading") != (r.get("phase") == "unloading"))
		or (r.has("unloading") and r.version < 4)
		or (r.has("homeward_walkers") != (r.version >= 4))
		or (r.has("sailing_pose") != (r.version >= 5 and r.get("phase") == "crossing"))
		or r.get("service") != service_record(ferry)
		or r.get("phase") not in ["boarding", "crossing", "walk_ons", "casting_off", "unloading"]
		or r.get("from") not in [ferry.term_a.town.key, ferry.term_b.town.key]
		or not r.get("reversed") is bool
		or not r.get("slip_chosen") is bool
		or not _integer(r.get("call"), ferry.stops.size() - 1)
		or not _integer(r.get("trips"), 9007199254740991)
	):
		return false
	var call_town := ferry.sim.map.towns[ferry.stops[int(r.call)]].key
	if (r.phase != "crossing") != (call_town == r.from):
		return false
	for key in NUMBERS:
		if not _number(r.get(key)):
			return false
	if r.has("sailing_pose") and not _valid_sailing_pose(r, ferry):
		return false
	for key in ["last_captain", "previous_captain"]:
		if not r.get(key) is String or (r[key] != "" and _captain(r[key]) == null):
			return false
	return (
		r.distance >= 0
		and r.distance <= ferry.run_length()
		and r.speed >= 0
		and r.state_minutes >= 0
		and r.crossing_fuel >= 0
		and r.crew_owed >= 0
		and r.lane_fraction >= 0
		and r.lane_fraction <= 1
	)


static func _valid_unloading(
	off: Variant,
	ferry: Ferry,
	term: Terminal,
	aboard: Array[Dictionary],
	leaving: Array[Dictionary]
) -> bool:
	if not off is Dictionary or not off.has("ramp") or not _valid_lift(off.ramp, ferry._ramp(term)):
		return false
	if not off.get("owns_terminal") is bool or (off.owns_terminal and term.unloading_ferry != null):
		return false
	if (
		not _number(off.get("passenger_dispatch"))
		or not _integer(off.get("passengers_per_tick"), ferry.fc.passenger_capacity)
	):
		return false
	if off.passengers_per_tick < 1 or not _read_passengers(off.get("passengers"), ferry, leaving):
		return false
	return (
		aboard.size() + leaving.size() <= ferry.fc.passenger_capacity
		and aboard.all(func(p: Dictionary): return p.dest != term.town.id and p.dest >= 0)
		and leaving.all(func(p: Dictionary): return p.dest == term.town.id or p.dest < 0)
	)


static func _valid_sailing_pose(record: Dictionary, ferry: Ferry) -> bool:
	var pose = record.sailing_pose
	if (
		not pose is Dictionary
		or not SnapshotVector3.valid(pose.get("position"))
		or not SnapshotVector3.valid(pose.get("forward"))
	):
		return false
	var forward := SnapshotVector3.decode(pose.forward)
	var position := SnapshotVector3.decode(pose.position)
	var at_a: bool = record.from == ferry.term_a.town.key
	var distance: float = (
		record.distance - ferry.dock_inset()
		if at_a
		else ferry.route.length + ferry.dock_inset() - record.distance
	)
	var lane := ferry.lane_pose_on(ferry.route, distance, at_a, record.lane_fraction)
	return (
		is_zero_approx(forward.y)
		and is_equal_approx(forward.length_squared(), 1.0)
		and absf(position.y) <= 0.22
		and (
			Vector2(position.x, position.z).distance_to(Vector2(lane.x, lane.z))
			<= ferry.fc.half_length
		)
	)


static func _valid_lift(pose: Variant, ramp: SlipRamp) -> bool:
	if ramp == null:
		return pose == null
	if not pose is Array or pose.size() != 2:
		return false
	for fraction in pose:
		if not _number(fraction) or fraction < 0 or fraction > 1:
			return false
	# The span cannot start rising before the apron finishes folding.
	return pose[0] == 0 or pose[1] == 1


static func _captain(id: String) -> Captain:
	for person in Captain.roster():
		if id == person.id:
			return person
	return null


static func _read_passengers(saved: Variant, ferry: Ferry, out: Array[Dictionary]) -> bool:
	if not saved is Array or saved.size() > ferry.fc.passenger_capacity:
		return false
	for row in saved:
		if not row is Dictionary or not row.get("town") is String:
			return false
		var town := ferry.sim.map.town_by_key(row.town)
		if row.town != "" and town == null:
			return false
		if (
			not _integer(row.get("variant"), Passenger.VARIANT_COUNT - 1)
			or not _number(row.get("fare_paid"))
			or row.fare_paid < 0
		):
			return false
		out.append(
			{
				"dest": -1 if town == null else town.id,
				"variant": int(row.variant),
				"fare_paid": float(row.fare_paid)
			}
		)
	return true


static func _integer(value: Variant, ceiling: int) -> bool:
	return _number(value) and value >= 0 and value <= ceiling and floor(value) == value


static func _number(value: Variant) -> bool:
	return (value is float or value is int) and is_finite(value)
