extends SceneTree
## Refitting Madrona's small slip to medium in the opening scenario (TID-44). Passes
## once the refit has run its course: Hiyu never lies at the slip while the crew is
## there and holds offshore while it is closed, the slip comes back medium with its
## dolphins standing out for the bigger boats, and Hiyu docks there again after.
##
##   godot --headless --path . --fixed-fps 30 --script tools/slip_refit_test.gd -- --scenario=opening

var main: Node
var frames := 0
var madrona: Terminal
var hiyu: Ferry
var cash_before := 0.0
var face_before := 0.0
var stages := {}
var held := false
var reopened := false


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(why: String) -> bool:
	push_error("Slip refit: " + why)
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
		hiyu = sim.ferries[0]
		if madrona == null:
			return _fail("no Madrona terminal")
		var i := madrona.next_refit()
		if i < 0 or madrona.town.slips[i].size != 1:
			return _fail("Madrona has no small slip to refit")
		face_before = madrona.slip_guides[i].fenders[0].face
		cash_before = sim.available_cash
		if not madrona.buy_refit(i):
			return _fail("could not buy the refit")
		if not is_equal_approx(cash_before - sim.available_cash, Terminal.REFIT_PRICE[2]):
			return _fail("paid %.0f, not %d" % [cash_before - sim.available_cash, Terminal.REFIT_PRICE[2]])
		stages[madrona.refit_stage] = true
		Engine.time_scale = 8.0
		return false
	stages[madrona.refit_stage] = true
	var crew_there := madrona.refit_stage in [Terminal.RefitStage.ARRIVING, Terminal.RefitStage.WORKING, Terminal.RefitStage.LEAVING]
	var alongside := hiyu.state != Ferry.State.SAILING and hiyu.here() == madrona
	if crew_there and alongside:
		return _fail("Hiyu lay at the slip while the crew was working (%s)" % Terminal.RefitStage.keys()[madrona.refit_stage])
	if hiyu.status_text().begins_with("Holding off"):
		held = true
	if madrona.refit_stage == Terminal.RefitStage.NONE and not reopened:
		reopened = true
		var slip := madrona.town.slips[0]
		if slip.size != 2:
			return _fail("slip is %s after the refit, not medium" % slip.size_name())
		for s in [Terminal.RefitStage.CLEARING, Terminal.RefitStage.ARRIVING, Terminal.RefitStage.WORKING, Terminal.RefitStage.LEAVING]:
			if not stages.has(s):
				return _fail("never went through %s" % Terminal.RefitStage.keys()[s])
		var face: float = madrona.slip_guides[0].fenders[0].face
		if face <= face_before + 1.0:
			return _fail("dolphins didn't stand out for bigger boats (face %.2f -> %.2f)" % [face_before, face])
		if not held:
			return _fail("Hiyu never held offshore while the slip was closed")
		print("Refit done on day %d at %s: slip medium, dolphin face %.2f -> %.2f m" % [sim.day, sim.clock_text(), face_before, face])
	if reopened and alongside:
		print("Hiyu back alongside at Madrona")
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 12000:
		return _fail("timed out at %s (stage %s)" % [sim.clock_text(), Terminal.RefitStage.keys()[madrona.refit_stage]])
	return false
