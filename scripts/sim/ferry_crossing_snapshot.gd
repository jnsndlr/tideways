class_name FerryCrossingSnapshot
extends RefCounted
## One working, two-stop ferry, during vehicle boarding or its crossing. Restore into
## an empty hull after rebuilding the same network, timetable, captain and class.
## The company owns the clock, ledger and waiting queues separately. Restore the
## network's corridor reservations after installing every hull's position.
const VERSION := 1
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
	if not _ordinary_service(ferry):
		return {}
	if (
		ferry.state != Ferry.State.SAILING
		and (ferry.state != Ferry.State.LOADING or ferry._load_phase != Ferry.LoadPhase.VEHICLES)
	):
		return {}
	var vehicles = FerryVehicleManifest.capture(ferry)
	if vehicles == null:
		return {}
	var passengers := []
	for pax in ferry.passengers_aboard:
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
	var command := ferry._command
	return {
		"version": VERSION,
		"service": _service(ferry),
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
		"passengers": passengers,
	}


static func _ordinary_service(ferry: Ferry) -> bool:
	return (
		ferry.berth == Ferry.Berth.WORKING
		and not ferry.manual
		and not ferry.holding
		and not ferry._positioning
		and not ferry._casting_off
		and not ferry.lay_up_requested
		and ferry.next_stops.is_empty()
		and ferry.stops.size() == 2
		and ferry.term_a != ferry.term_b
		and ferry._end_slip == [-1, -1]
		and ferry._pax_walkers.is_empty()
	)


static func _captain_id(person: Captain) -> String:
	return "" if person == null else person.id


static func _service(ferry: Ferry) -> Dictionary:
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
	if not _ordinary_service(ferry) or not _empty_hull(ferry):
		return false
	if not record is Dictionary or not _valid_state(record, ferry):
		return false
	var passengers: Array[Dictionary] = []
	if not _read_passengers(record.get("passengers"), ferry, passengers):
		return false
	var at_a: bool = record.from == ferry.term_a.town.key
	var sailing: bool = record.phase == "crossing"
	var manifest := FerryVehicleManifest.prepare(
		record.get("vehicles"),
		ferry,
		at_a != record.reversed,
		build_vehicle,
		ferry.term_a if at_a else ferry.term_b,
		sailing
	)
	if manifest == null:
		return false
	ferry.state = Ferry.State.SAILING if sailing else Ferry.State.LOADING
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
	else:
		ferry._place(ferry._dock_s())
	ferry.passengers_aboard = passengers
	manifest.install(ferry)
	return true


static func _empty_hull(ferry: Ferry) -> bool:
	return (
		ferry.aboard.is_empty()
		and ferry.passengers_aboard.is_empty()
		and ferry._boarding == 0
		and ferry._unload_queue.is_empty()
		and ferry._pax_unload_queue.is_empty()
		and ferry.deck.occupants.count(0) == ferry.deck.occupants.size()
	)


static func _valid_state(r: Dictionary, ferry: Ferry) -> bool:
	if (
		r.get("version") != VERSION
		or r.get("service") != _service(ferry)
		or r.get("phase") not in ["boarding", "crossing"]
		or r.get("from") not in [ferry.term_a.town.key, ferry.term_b.town.key]
		or not r.get("reversed") is bool
		or not r.get("slip_chosen") is bool
		or not _integer(r.get("call"), ferry.stops.size() - 1)
		or not _integer(r.get("trips"), 9007199254740991)
	):
		return false
	var call_town := ferry.sim.map.towns[ferry.stops[int(r.call)]].key
	if (r.phase == "boarding") != (call_town == r.from):
		return false
	for key in NUMBERS:
		if not _number(r.get(key)):
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
