extends SceneTree
## Stage 4 stop editor: the opening scenario has routes planned between all its
## terminals, only Port Rosario–Madrona in service. Hiyu is put on Port Rosario →
## Madrona → Gullrock → Madrona while she runs. She must take the new stops at her
## next call, keep her hull steady through the switch, reach Gullrock, and the
## lanes at Madrona must divide between Port Rosario and Gullrock.
##
##   godot --headless --path . --fixed-fps 30 --script tests/traffic/schedule_edit_test.gd

var main: Node
var frames := 0
var _last_yaw := INF
var _last_pos := Vector3.ZERO
var _switched := false


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _term(sim: Simulation, key: String) -> Terminal:
	for t: Terminal in sim.terminals.values():
		if t.town.key.begins_with(key + "/"):
			return t
	return null


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var hiyu := sim.ferries[0]
	var rosario := _term(sim, "island-1")
	var madrona := _term(sim, "island-2")
	var gullrock := _term(sim, "island-7")
	if frames == 5:
		Engine.time_scale = 6.0
		var served := sim.map.routes.filter(func(r): return r.in_service).size()
		print("Routes planned %d, in service %d" % [sim.map.routes.size(), served])
		if served != 1:
			return _fail("Expected only the scheduled route in service, got %d" % served)
		if sim.route_between(madrona.town.id, gullrock.town.id) == null:
			return _fail("No candidate route between Madrona and Gullrock")
		# Cypress Island lies between these two: the route goes round it.
		if sim.route_between(rosario.town.id, gullrock.town.id) == null:
			return _fail("No route round Cypress Island between Port Rosario and Gullrock")
		var ids: Array[int] = [rosario.town.id, madrona.town.id, gullrock.town.id, madrona.town.id]
		var problem := sim.stops_problem(hiyu, ids)
		if problem != "":
			return _fail("Editor rejected the new stops: " + problem)
		var bad: Array[int] = [rosario.town.id, rosario.town.id]
		if sim.stops_problem(hiyu, bad) == "":
			return _fail("Editor accepted a stop listed twice in a row")
		sim.reschedule(hiyu, ids)
		print("Planned %s, next call %s" % [hiyu.next_stops, hiyu.next_dock().town.name])
	var yaw := hiyu.global_rotation.y
	if _last_yaw != INF and hiyu.berth == Ferry.Berth.WORKING and (absf(angle_difference(_last_yaw, yaw)) > 0.25 or hiyu.global_position.distance_to(_last_pos) > 6.0):
		return _fail("Hiyu jumped at %s: yaw %.2f -> %.2f" % [hiyu.here().town.name, _last_yaw, yaw])
	_last_yaw = yaw
	_last_pos = hiyu.global_position
	if not _switched and hiyu.next_stops.is_empty() and hiyu.stops.size() == 4:
		_switched = true
		print("Switched at %s, frame %d. Madrona lanes: %s" % [hiyu.here().town.name, frames,
			madrona.lanes.keys().map(func(k): return "%s×%d" % [sim.map.towns[k].name, madrona.lanes[k].size()])])
		if madrona.lanes.size() != 2:
			return _fail("Madrona's lanes did not divide between two destinations")
	if _switched and hiyu.state != Ferry.State.SAILING and hiyu.here() == gullrock:
		print("Hiyu reached Gullrock at frame %d. In service: %d routes" % [frames, sim.map.routes.filter(func(r): return r.in_service).size()])
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 30 * 60 * 6:
		return _fail("Hiyu never reached Gullrock (switched: %s, stops %s, status %s)" % [_switched, hiyu.stops, hiyu.status_text()])
	return false
