extends SceneTree
## The opening scenario's terminals start with two paved lanes. Buys a lane at
## Port Rosario twice: each paves the next lot position, with no lanes closed.
##
##   godot --headless --path . --fixed-fps 30 --script tools/lot_lanes_test.gd

var main: Node
var frames := 0
var bought := 0
var start_lanes := 0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _lane_count(term: Terminal) -> int:
	var n := 0
	for key in term.lanes.keys():
		n += term.lanes[key].size()
	return n


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var term: Terminal
	for t: Terminal in sim.terminals.values():
		if t.town.key.begins_with("island-1/"):
			term = t
	if frames == 5:
		Engine.time_scale = 8.0
		start_lanes = _lane_count(term)
		print("%s: %d lanes %s, %d more on the lot" % [term.town.name, start_lanes, term.lanes.values().map(func(a): return a.map(func(l): return l.v)), term.site_lanes.size()])
		if start_lanes != 2:
			return _fail("Expected two lanes at the start")
	if bought < 2 and term.buy_holding_lane():
		bought += 1
		print("Bought lane %d at %.1f (staging closes %d lanes)" % [bought, term.extension_offset(), term.staging_lanes.size()])
		if not term.staging_lanes.is_empty():
			return _fail("Closed lanes to build inside the lot")
	if bought == 2 and term.work_stage == Terminal.WorkStage.OPEN:
		print("Paved: %s · %d lanes · %d car spaces" % [term.paved, _lane_count(term), term.capacity()])
		if _lane_count(term) != start_lanes + 2:
			return _fail("Expected two more lanes")
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 20000:
		return _fail("Gave up: bought %d, stage %d" % [bought, term.work_stage])
	return false
