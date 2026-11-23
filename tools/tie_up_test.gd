extends SceneTree
## Lays Rhododendron up at Madrona's tie-up slip (maps/shared_slip.json), checks
## Hiyu keeps working the slip they share while she lies there, then brings her
## back into service and waits for her next sailing.
##
##   godot --headless --path . --fixed-fps 30 --script tools/tie_up_test.gd -- --scenario=shared_slip

var main: Node
var frames := 0
var phase := 0
var hiyu_docks := 0
var _hiyu_was := false
var _mark := 0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


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
		print("Day %d %s: %s asked to lay up (%s)" % [sim.day, sim.clock_text(), rhodo.ferry_name, rhodo.status_text()])
	var at := hiyu.state != Ferry.State.SAILING and hiyu.here().town.key.begins_with("island-2/")
	if at and not _hiyu_was:
		hiyu_docks += 1
	_hiyu_was = at
	match phase:
		0:
			if rhodo.berth == Ferry.Berth.TIED_UP:
				var isl := rhodo.here().town
				var off := rhodo.global_position.distance_to(isl.berth_center(rhodo.tie_up))
				print("Day %d %s: %s tied up at %s, %.1f m from the tie-up's centre" % [sim.day, sim.clock_text(), rhodo.ferry_name, isl.name, off])
				if off > rhodo.fc.half_length:
					return _fail("Tied up away from the tie-up slip")
				phase = 1
				_mark = hiyu_docks
		1:
			if hiyu_docks >= _mark + 2:
				print("Hiyu docked at Madrona %d times while Rhododendron lay up" % (hiyu_docks - _mark))
				# Both ferries are at the shared terminal. While Hiyu is moving
				# between slips, a second movement must wait, in either direction.
				hiyu._start_shift(hiyu._tie_up_point(rhodo.tie_up))
				if not rhodo._shift_blocked(false) or not rhodo._shift_blocked(true):
					return _fail("Two ferries could start moving between nearby slips together")
				hiyu._shift = null
				rhodo.request_return()
				phase = 2
			elif rhodo.berth != Ferry.Berth.TIED_UP:
				return _fail("Left the tie-up unasked")
		2:
			if rhodo.berth == Ferry.Berth.WORKING and rhodo.state == Ferry.State.SAILING:
				print("Day %d %s: %s back in service: %s" % [sim.day, sim.clock_text(), rhodo.ferry_name, rhodo.status_text()])
				print("TEST PASSED")
				quit(0)
				return true
	var both := 0
	for f in sim.ferries:
		if f.berth == Ferry.Berth.WORKING and f.state != Ferry.State.SAILING and f.here().town.key.begins_with("island-2/"):
			both += 1
	if both > 1:
		return _fail("Two boats at Madrona's working slip on frame %d" % frames)
	if frames > 60000:
		return _fail("Gave up in phase %d: %s / %s" % [phase, rhodo.status_text(), hiyu.status_text()])
	return false
