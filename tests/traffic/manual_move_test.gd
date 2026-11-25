extends SceneTree
## TID-328: manual orders. maps/tie_up_pier.json.
##  1. Under way with traffic aboard, Rhododendron is turned back to the terminal
##     she left: she turns where she is, sets everyone down there (those bound
##     across refunded and counted against their terminal), and lies alongside.
##  2. She stays there (her timetable paused) until Return to service, then sails.
##  3. Alongside, Hiyu is sent to Madrona's tie-up slip: she crosses, sets down,
##     and moves onto the tie-up. Return to service brings her back to work.
##
##   godot --headless --path . --fixed-fps 30 \
##     --script tests/traffic/manual_move_test.gd -- --scenario=tie_up_pier

var main: Node
var frames := 0
var phase := -2
var _mark := 0
var _origin := -1
var _bound := -1
var _sat_before := 0.0
var _expected_refund := 0.0
var _yaw0 := 0.0
var _lead := false
var _turned := false
var _held_riders := Vector2i.ZERO
var _hold_started := 0.0
var _hold_fuel := 0.0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _log(sim: Simulation, msg: String) -> void:
	print("Day %d %s: %s" % [sim.day, sim.clock_text(), msg])


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var hiyu := sim.ferries[0]
	var rhodo := sim.ferries[1]
	if frames == 5:
		Engine.time_scale = 6.0
	var finished := false
	match phase:
		-2:
			finished = _start_hold(sim, rhodo)
		-1:
			finished = _check_hold(sim, rhodo)
		0:
			finished = _turn_back(sim, rhodo)
		1:
			finished = _check_landing(sim, rhodo)
		2:
			finished = _return_to_service(sim, rhodo)
		3:
			finished = _check_departure(sim, rhodo)
		4:
			finished = _move_to_tie_up(sim, hiyu)
		5:
			finished = _check_tie_up(sim, hiyu)
		6:
			finished = _check_service(sim, hiyu)
	if finished:
		return true
	if frames > 90000:
		return _fail(
			"Gave up in phase %d: %s / %s" % [phase, rhodo.status_text(), hiyu.status_text()]
		)
	return false


func _start_hold(sim: Simulation, boat: Ferry) -> bool:
	if boat.state != Ferry.State.SAILING or boat.traveled < 250.0 or boat.path_left() < 500.0:
		return false
	if not boat.order_hold():
		return _fail("The sailing ferry refused the open-water hold")
	_held_riders = Vector2i(boat.aboard.size(), boat.passengers_aboard.size())
	_hold_started = sim.abs_minutes()
	_hold_fuel = boat._crossing_fuel
	phase = -1
	return false


func _check_hold(sim: Simulation, boat: Ferry) -> bool:
	var elapsed := sim.abs_minutes() - _hold_started
	if elapsed < FerryManualOrders.HOLD_GRACE_MIN + 8.0:
		return false
	if not boat.holding or boat.speed > 0.5:
		return _fail("The ferry did not stop in open water")
	if _held_riders != Vector2i(boat.aboard.size(), boat.passengers_aboard.size()):
		return _fail("Riders were lost during the hold")
	if boat._crossing_fuel - _hold_fuel + 1.0 < FerryManualOrders.HOLD_FUEL_PER_MIN * elapsed:
		return _fail("The hold did not meter idle fuel")
	boat.request_return()
	if boat.holding or not boat.in_service():
		return _fail("Return to service did not release the hold")
	phase = 0
	return false


func _turn_back(sim: Simulation, rhodo: Ferry) -> bool:
	# Under way, a good way out, with someone aboard bound across.
	if (
		rhodo.berth == Ferry.Berth.WORKING
		and rhodo.state == Ferry.State.SAILING
		and rhodo.traveled > 250.0
		and rhodo.path_left() > 250.0
		and (not rhodo.aboard.is_empty() or not rhodo.passengers_aboard.is_empty())
	):
		_origin = rhodo.here().town.id
		_bound = rhodo.destination().town.id
		_sat_before = sim.terminals[_bound].turned_recent
		for car in rhodo.aboard:
			if car.dest == _bound:
				_expected_refund += car.fare_paid
		for pax in rhodo.passengers_aboard:
			if pax["dest"] == _bound:
				_expected_refund += float(pax["fare_paid"])
		if _expected_refund <= 0.0:
			return _fail("Expected travelers with paid fares")
		sim.ledger.set_route_vehicle_fare(rhodo.route.id, CompanyLedger.MAX_VEHICLE_FARE)
		sim.ledger.set_route_passenger_fare(rhodo.route.id, CompanyLedger.MAX_PASSENGER_FARE)
		var pos := rhodo.global_position
		var short := rhodo.manual_strands(_origin)
		if not rhodo.order_move(_origin, rhodo.slip_at(rhodo.here())):
			return _fail("order_move refused turning her back")
		if rhodo.global_position.distance_to(pos) > 2.0:
			return _fail("She jumped %.1f m turning back" % rhodo.global_position.distance_to(pos))
		_yaw0 = rhodo.global_basis.get_euler().y
		_lead = rhodo._minus
		if rhodo.destination().town.id != _origin:
			return _fail("Turned back but bound for %s" % rhodo.destination().town.name)
		_log(
			sim,
			(
				"Rhododendron turned back with %d cars, %d walk-ons bound across: %s"
				% [short.x, short.y, rhodo.status_text()]
			)
		)
		phase = 1
	return false


func _check_turn(sim: Simulation, rhodo: Ferry) -> bool:
	if not _turned and rhodo._turn_t < 0.0 and rhodo.speed > 1.0:
		_turned = true
		var swung := absf(wrapf(rhodo.global_basis.get_euler().y - _yaw0, -PI, PI))
		if swung < PI * 0.8:
			return _fail("She didn't swing round: turned %.0f°" % rad_to_deg(swung))
		if rhodo._minus != _lead:
			return _fail("A different end leads after turning round")
		_log(
			sim, "Swung round %.0f°, under way back: %s" % [rad_to_deg(swung), rhodo.status_text()]
		)
	return false


func _check_landing(sim: Simulation, rhodo: Ferry) -> bool:
	if _check_turn(sim, rhodo):
		return true
	if (
		rhodo.state == Ferry.State.LOADING
		and rhodo._manual_landed
		and rhodo.aboard.is_empty()
		and rhodo.passengers_aboard.is_empty()
	):
		if rhodo.here().town.id != _origin:
			return _fail("Landed at the wrong terminal")
		if rhodo.stranded_cars + rhodo.stranded_walk_ons == 0:
			return _fail("Nobody counted as set down short")
		if not is_equal_approx(rhodo.stranded_refunds, _expected_refund):
			return _fail(
				(
					"Refunded %s instead of the original %s"
					% [rhodo.stranded_refunds, _expected_refund]
				)
			)
		if sim.terminals[_bound].turned_recent <= _sat_before:
			return _fail("No satisfaction hit at the terminal they were bound for")
		_log(
			sim,
			(
				"Set down %d cars, %d walk-ons, refunded $%d: %s"
				% [
					rhodo.stranded_cars,
					rhodo.stranded_walk_ons,
					roundi(rhodo.stranded_refunds),
					rhodo.status_text()
				]
			)
		)
		_mark = frames
		phase = 2
	return false


func _return_to_service(sim: Simulation, rhodo: Ferry) -> bool:
	if rhodo.state == Ferry.State.SAILING:
		return _fail("She sailed while under manual orders")
	if frames - _mark > 1200:
		if rhodo.in_service():
			return _fail("in_service() true under manual orders")
		rhodo.request_return()
		_log(sim, "Return to service: " + rhodo.status_text())
		phase = 3
	return false


func _check_departure(sim: Simulation, rhodo: Ferry) -> bool:
	if rhodo.manual:
		return _fail("Still manual after Return to service")
	if rhodo.state == Ferry.State.SAILING and rhodo.berth == Ferry.Berth.WORKING:
		_log(sim, "Rhododendron back on her stops: " + rhodo.status_text())
		phase = 4
	return false


func _move_to_tie_up(sim: Simulation, hiyu: Ferry) -> bool:
	# Hiyu, alongside away from Madrona: to Madrona's tie-up.
	if (
		hiyu.berth == Ferry.Berth.WORKING
		and hiyu.state == Ferry.State.LOADING
		and not hiyu.here().town.key.begins_with("island-2/")
	):
		var madrona := -1
		for id in hiyu.manual_reach():
			if sim.map.towns[id].key.begins_with("island-2/"):
				madrona = id
		if madrona < 0:
			return _fail("Madrona not in Hiyu's reach")
		var tie := -1
		for s in hiyu.manual_slips(madrona):
			if sim.map.towns[madrona].slips[s[0]].tie_up:
				tie = s[0]
		if tie < 0 or not hiyu.order_move(madrona, tie):
			return _fail("Couldn't send Hiyu to Madrona's tie-up")
		_bound = madrona
		_origin = tie
		_log(sim, "Hiyu sent to Madrona's tie-up: " + hiyu.status_text())
		phase = 5
	return false


func _check_tie_up(sim: Simulation, hiyu: Ferry) -> bool:
	if (
		hiyu.berth == Ferry.Berth.TIED_UP
		and hiyu.tie_up == _origin
		and hiyu.here().town.id == _bound
	):
		_log(sim, "Hiyu lies at the tie-up: " + hiyu.status_text())
		hiyu.request_return()
		phase = 6
	return false


func _check_service(sim: Simulation, hiyu: Ferry) -> bool:
	if not hiyu.manual and hiyu.berth == Ferry.Berth.WORKING:
		_log(sim, "Hiyu back in service: " + hiyu.status_text())
		print("TEST PASSED")
		quit(0)
		return true
	return false
