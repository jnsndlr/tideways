extends SceneTree
## maps/tie_up_pier.json. Lays Rhododendron up at Madrona's tie-up pier, lays
## Hiyu up in place in Madrona's working slip (the one they share), and checks
## that Rhododendron, asked back, waits at the tie-up while Hiyu lies there. Then
## brings Hiyu back, and gives Rhododendron stops that leave out Madrona: her
## crew should take her across empty and she should start them.
##
##   godot --headless --path . --fixed-fps 30 \
##     --script tests/traffic/tie_up_reposition_test.gd -- --scenario=tie_up_pier

var main: Node
var frames := 0
var phase := 0
var _mark := 0
var _ids: Array[int] = []


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
		rhodo.request_lay_up()
	var finished := false
	match phase:
		0:
			finished = _wait_for_tie_up(sim, rhodo)
		1:
			finished = _block_working_slip(hiyu, rhodo)
		2:
			finished = _check_blocked_return(sim, hiyu, rhodo)
		3:
			finished = _wait_for_return(sim, rhodo)
		4:
			finished = _change_service(sim, rhodo)
		5:
			finished = _check_new_service(sim, rhodo)
	if finished:
		return true
	if frames > 90000:
		return _fail(
			"Gave up in phase %d: %s / %s" % [phase, rhodo.status_text(), hiyu.status_text()]
		)
	return false


func _wait_for_tie_up(sim: Simulation, rhodo: Ferry) -> bool:
	if rhodo.berth == Ferry.Berth.TIED_UP:
		_log(sim, "Rhododendron tied up: " + rhodo.status_text())
		phase = 1
	return false


func _block_working_slip(hiyu: Ferry, rhodo: Ferry) -> bool:
	# Hiyu alongside Madrona and loading: lay her up where she lies.
	if (
		hiyu.berth == Ferry.Berth.WORKING
		and hiyu.state == Ferry.State.LOADING
		and hiyu.here() == rhodo.here()
		and hiyu.aboard.is_empty()
	):
		if not hiyu.order_move(hiyu.here().town.id, hiyu.slip_at(hiyu.here())):
			return _fail("Could not lie Hiyu in the shared working slip")
		rhodo.request_return()
		_mark = frames
		phase = 2
	return false


func _check_blocked_return(sim: Simulation, hiyu: Ferry, rhodo: Ferry) -> bool:
	if rhodo.berth != Ferry.Berth.TIED_UP:
		return _fail("Rhododendron left the tie-up into the slip Hiyu lies laid up in")
	if frames - _mark > 900:
		_log(sim, "Rhododendron held: " + rhodo.status_text())
		if "Hiyu" not in rhodo.status_text():
			return _fail("Status doesn't say Hiyu holds her slip")
		hiyu.request_return()
		phase = 3
	return false


func _wait_for_return(sim: Simulation, rhodo: Ferry) -> bool:
	if rhodo.berth == Ferry.Berth.WORKING:
		_log(sim, "Rhododendron back in service once Hiyu sailed: " + rhodo.status_text())
		rhodo.request_lay_up()
		phase = 4
	return false


func _change_service(sim: Simulation, rhodo: Ferry) -> bool:
	if rhodo.berth == Ferry.Berth.TIED_UP and rhodo.here().town.key.begins_with("island-2/"):
		var madrona := rhodo.here().town.id
		for t: Terminal in sim.terminals.values():
			if t.town.id != madrona and sim.route_between(madrona, t.town.id) != null:
				_ids.append(t.town.id)
		# Somewhere else and back: any two of her neighbours with a route between them.
		var pick: Array[int] = []
		for a in _ids:
			for b in sim.terminals.keys():
				if b != a and b != madrona and sim.route_between(a, b) != null and pick.is_empty():
					pick = [a, b]
		if pick.is_empty():
			return _fail("No stops without Madrona to try")
		var why := sim.stops_problem(rhodo, pick)
		if why != "":
			return _fail("New stops refused: " + why)
		if not sim.reschedule(rhodo, pick):
			return _fail("reschedule failed")
		_ids = pick
		rhodo.request_return()
		_log(sim, "Rhododendron given stops without Madrona: " + rhodo.status_text())
		phase = 5
	elif rhodo.berth == Ferry.Berth.TIED_UP:
		phase = 4  # (tied up somewhere else; wait for Madrona)
	return false


func _check_new_service(sim: Simulation, rhodo: Ferry) -> bool:
	if (
		rhodo.berth == Ferry.Berth.WORKING
		and rhodo.state == Ferry.State.SAILING
		and rhodo.speed > 1.0
		and frames % 300 == 0
	):
		_log(sim, "Rhododendron: " + rhodo.status_text())
	if rhodo.stops == _ids and rhodo.berth == Ferry.Berth.WORKING:
		if not rhodo.aboard.is_empty() and rhodo.here().town.key.begins_with("island-2/"):
			return _fail("She loaded at Madrona")
		_log(
			sim,
			(
				"Rhododendron took her new stops at %s: %s"
				% [rhodo.here().town.name, rhodo.status_text()]
			)
		)
		print("TEST PASSED")
		quit(0)
		return true
	return false
