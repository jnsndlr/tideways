extends SceneTree
## Flexible slip ends (stage 5): Hiyu and Rhododendron both prefer Madrona's first
## slip (maps/shared_slip.json), and a second slip there stands free. A boat coming in
## while the other holds the first slip takes the free one instead of waiting
## offshore. Passes once one has docked at the second slip, worked her call there and
## sailed on, with never two boats alongside one slip.
##
##   godot --headless --path . --fixed-fps 30 --script tools/flex_slip_test.gd -- --scenario=shared_slip

var main: Node
var frames := 0
var madrona: Terminal
var second := -1
var diverted: Ferry
var trips_then := 0


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(why: String) -> bool:
	push_error("Flex slip: " + why)
	quit(1)
	return true


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	if frames == 5:
		for t: Terminal in sim.terminals.values():
			if t.town.key.begins_with("island-2/"):
				madrona = t
		var slip := madrona.find_upgrade(TerminalUpgrade.Kind.SLIP)
		if slip == null or not madrona.buy(slip):
			return _fail("couldn't buy a second slip at Madrona")
		second = madrona.town.slips.size() - 1
		# Built at once.
		madrona.refit_stage = Terminal.RefitStage.WORKING
		madrona.refit_remaining = Terminal.REFIT_DEPARTURE + 0.01
		return false
	if frames == 8:
		if madrona.town.slips[second].building:
			return _fail("the slip didn't open")
		# Both routes keep the first slip as their own, so only the flexible ends use the second.
		madrona._assignments = null
		if not madrona.town.slips[second].routes.is_empty():
			return _fail("a route already calls at the new slip")
		# Different paces so the two boats meet at Madrona.
		sim.ferries[1].pace = 0
		sim.ferries[0].pace = 2
		Engine.time_scale = 6.0
		return false
	if frames < 8:
		return false
	var at := {}
	for f in sim.ferries:
		if f.berth == Ferry.Berth.WORKING and f.state != Ferry.State.SAILING and f.here() == madrona:
			var i := f.slip_at(madrona)
			if at.has(i):
				return _fail("%s and %s both alongside slip %d" % [at[i].ferry_name, f.ferry_name, i])
			at[i] = f
	if diverted == null and at.has(second):
		diverted = at[second]
		var berth := madrona.town.berth_center(second)
		var off := Vector2(diverted.global_position.x - berth.x, diverted.global_position.z - berth.z).length()
		if off > 30.0:
			return _fail("%s lies %.0f m off the second slip" % [diverted.ferry_name, off])
		trips_then = diverted.trips
		print("%s took the free slip at %s (%.0f m off its berth); at the first: %s" % [diverted.ferry_name, sim.clock_text(),
			off, at[madrona.town.slip_index(diverted.route.id)].ferry_name if at.has(madrona.town.slip_index(diverted.route.id)) else "none"])
	if diverted and diverted.trips > trips_then:
		print("%s worked her call and docked again at %s" % [diverted.ferry_name, diverted.here().town.name])
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 30000:
		return _fail("timed out at %s: no boat used the second slip" % sim.clock_text())
	return false
