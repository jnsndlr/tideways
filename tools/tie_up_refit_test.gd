extends SceneTree
## Refitting Madrona's small tie-up slip to medium in the shared-slip scenario. Passes
## once the refit has run its course: no boat may make for the tie-up while it is
## closed, and it comes back medium. (Its dolphins already stand wide enough for any
## boat: tie-ups lie side by side at Layout.TIE_UP_SPACING.)
##
##   godot --headless --path . --fixed-fps 30 --script tools/tie_up_refit_test.gd -- --scenario=shared_slip

var main: Node
var frames := 0
var madrona: Terminal
var tie := -1
var stages := {}


func _initialize() -> void:
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(why: String) -> bool:
	push_error("Tie-up refit: " + why)
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
		if madrona == null:
			return _fail("no Madrona terminal")
		tie = madrona.next_refit(true)
		if tie < 0 or not madrona.town.slips[tie].tie_up or madrona.town.slips[tie].size != 1:
			return _fail("Madrona has no small tie-up to refit")
		var cash := sim.available_cash
		if not madrona.buy_refit(tie):
			return _fail("could not buy the refit")
		if not is_equal_approx(cash - sim.available_cash, Terminal.REFIT_PRICE[2]):
			return _fail("paid %.0f, not %d" % [cash - sim.available_cash, Terminal.REFIT_PRICE[2]])
		Engine.time_scale = 8.0
	stages[madrona.refit_stage] = true
	if madrona.refit_stage != Terminal.RefitStage.NONE:
		for f in sim.ferries:
			if (f.term_a == madrona or f.term_b == madrona) and f.free_tie_up(madrona) == tie:
				return _fail("%s could make for the tie-up while it was closed" % f.ferry_name)
		return frames > 12000 and _fail("timed out at %s (stage %s)" % [sim.clock_text(), Terminal.RefitStage.keys()[madrona.refit_stage]])
	for s in [Terminal.RefitStage.CLEARING, Terminal.RefitStage.ARRIVING, Terminal.RefitStage.WORKING, Terminal.RefitStage.LEAVING]:
		if not stages.has(s):
			return _fail("never went through %s" % Terminal.RefitStage.keys()[s])
	var slip := madrona.town.slips[tie]
	if slip.size != 2:
		return _fail("tie-up is %s after the refit, not medium" % slip.size_name())
	if madrona.next_refit(true) != tie:
		return _fail("the medium tie-up isn't offered the refit to large")
	print("Tie-up refit done on day %d at %s: medium" % [sim.day, sim.clock_text()])
	print("TEST PASSED")
	quit(0)
	return true
