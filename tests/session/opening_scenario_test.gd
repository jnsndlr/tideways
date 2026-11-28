extends SceneTree
## Verify the company a player gets when Play opens the authored map.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var play = load(Scenes.MAIN_MAP).instantiate()
	root.add_child(play)
	current_scene = play
	var error: String
	if OS.get_cmdline_user_args().has("--full-network"):
		error = _check_full_network(play.sim)
	else:
		error = _check(play.sim, play.hud)
	play.queue_free()
	await process_frame
	await process_frame
	if error.is_empty():
		print("TEST PASSED")
	else:
		push_error(error)
	quit(0 if error.is_empty() else 1)


func _check(sim: Simulation, hud: Hud) -> String:
	if sim.ledger.cash != 50000.0 or sim.terminals.size() != 3 or sim.ferries.size() != 1:
		return "Play needs $50,000, three terminals and one ferry at startup"
	var airports := 0
	for island in sim.map.islands:
		if island.airstrip:
			airports += 1
			var hangar := (
				current_scene.find_child(island.name + " Hangar", true, false) as MeshInstance3D
			)
			if hangar == null or hangar.mesh == null:
				return "%s should have a hangar when the company opens" % island.name
	if airports != 2:
		return "The authored opening should have two airports with hangars"
	var ferry := sim.ferries[0]
	# Routes between the other terminals are planned for the stop editor (stage 4)
	# but only Hiyu's is in service.
	var in_service := sim.map.routes.filter(func(r): return r.in_service).size()
	if ferry.ferry_name != "Hiyu" or ferry.fc.size != 2 or in_service != 1:
		return "The opening needs the size-2 Hiyu on a single route"
	var keys := [ferry.term_a.town.key, ferry.term_b.town.key]
	if not keys.has("island-1/0") or not keys.has("island-2/0"):
		return "Hiyu should shuttle between Port Rosario and Madrona"
	var idle: Terminal
	for terminal: Terminal in sim.terminals.values():
		if terminal.town.working_slips() != 1:
			return "An opening terminal should have one working slip"
		var ties := terminal.town.tie_ups().size()
		if ties != (1 if terminal.town.key == "island-1/0" else 0):
			return "Only Port Rosario should have a tie-up (its maintenance facility), not %s" % terminal.town.name
		if terminal.town.key.begins_with("island-7/"):
			idle = terminal
	if idle == null:
		return "Gullrock needs an idle terminal"
	idle._spawn_car()
	if idle.has_service() or idle.total_queued() != 0 or idle.buy_holding_lane():
		return "Gullrock should start idle with no waiting cars or lane purchase"
	hud.select_town(idle.town, false)
	if hud._info_sub.text != "Ferry terminal · idle slip" or hud._tb["terminal"][2].text != "No scheduled service":
		return "The idle terminal should show its service status instead of a wait estimate"
	for label: Label in hud._info_grid.get_children():
		if label.text == "Avg. wait":
			return "The idle terminal inspector should omit its unused wait estimate"
	return ""


func _check_full_network(sim: Simulation) -> String:
	if sim.map.routes.size() < 2 or sim.ferries.size() != sim.map.routes.size():
		return "Full-network Play should assign one boat to each planned route"
	var served := {}
	for ferry in sim.ferries:
		if served.has(ferry.route.id):
			return "Full-network Play assigned two boats to the same route"
		served[ferry.route.id] = true
	for route in sim.map.routes:
		if not served.has(route.id):
			return "Full-network Play left a planned route unserved"
	return ""
