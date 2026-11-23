extends SceneTree

var failures := 0


func _initialize() -> void:
	var mission := Scenario.load_file("res://maps/mission_trial.json").mission
	var sim := Simulation.new()
	sim.map = MapData.new()
	var island := MapData.Island.new()
	island.key = "island-3"
	island.name = "Cypress Island"
	sim.map.islands.append(island)
	var panel := MissionPanel.new()
	panel.mission = mission
	for goal in mission.goals:
		_check(not mission.goal_met(sim, goal), "Trial should start with open goals.")
	_check(mission.start_day == -1, "Reading goals must not start the mission clock.")
	mission.start(sim.day)
	sim.day += mission.days - 1
	mission.start(sim.day)
	_check(not mission.late(sim) and mission.day_of(sim) == mission.days, "Deadline should include its final day after a rebuild.")
	sim.day += 1
	_check(mission.late(sim), "The day after the deadline should be late.")
	sim.ledger.cars_total = 250
	sim.ledger.cash = 60000
	var terminal := Terminal.new()
	terminal.island = island
	sim.add_child(terminal)
	sim.terminals[island.id] = terminal
	var ferry := Ferry.new()
	ferry.next_stops.append(island.id)
	sim.add_child(ferry)
	sim.ferries.append(ferry)
	for goal in mission.goals:
		_check(mission.goal_met(sim, goal), "Expected completed goal %s" % goal.kind)
	_check(panel._goal_label(sim, mission.goals[1]) == "Open a terminal on Cypress Island", "Terminal label must resolve its island.")
	_check(panel._goal_label(sim, mission.goals[3]) == "Grow cash to $60.0K", "Author's goal label must take precedence.")
	_check(panel._goal_progress(sim, mission.goals[0]) == "250 / 250", "Panel should include pre-rebuild passenger counts.")
	_check(panel._goal_progress(sim, mission.goals[3]) == "$60.0K", "Panel should format cash using HUD conventions.")
	ferry.next_stops.clear()
	_check(not mission.goal_met(sim, mission.goals[2]), "Removing the scheduled call must reopen the service goal.")
	panel.free()
	sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(int(failures > 0))


func _check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
