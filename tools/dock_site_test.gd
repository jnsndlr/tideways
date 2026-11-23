extends SceneTree
## Locked dock sites on the main map (TID-16, TID-319). Every locked site is a
## town of its own. The opening's terminals stand exactly at their docks; every
## other site is baked into the map unbuilt, with routes to the rest. Buying
## Cypress Island's site charges its price and starts a terminal there that opens
## Simulation.DOCK_BUILD_MINUTES later, in the same scene: nothing is rebuilt.
##
##   godot --headless --path . --fixed-fps 30 --script tools/dock_site_test.gd

var frames := 0
var _main: Node
var _cypress: MapData.Town
var _cash_before := 0.0
var _price := 0
var _purchases := 0.0
var _port: Terminal
var _bought_at := -1.0


func _initialize() -> void:
	_main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(_main)
	current_scene = _main


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _process(_delta: float) -> bool:
	frames += 1
	if frames > 30000:
		return _fail("Timed out waiting for dock construction")
	if current_scene != _main:
		return _fail("The scene was replaced: buying a dock must not rebuild the map")
	if _main.get("sim") == null or not _main.built:
		return false
	var sim: Simulation = _main.sim
	var map: MapData = _main.map
	var layout: MapLayout = _main.layout
	if _cypress == null:
		# Every town with a dock stands exactly where its dock was locked.
		var sites := 0
		for spec in layout.islands:
			sites += spec.docks.size()
		var docks := map.dock_towns()
		if docks.size() != sites:
			return _fail("%d dock towns for %d locked sites" % [docks.size(), sites])
		var spec_of := {}
		for spec in layout.islands:
			spec_of[spec.name] = spec
		for t in docks:
			var spec: MapLayout.IslandSpec = spec_of[map.island_of(t).name]
			var at := spec.dock_at(spec.docks[t.site])
			if Vector2(t.shore.x, t.shore.z).distance_to(at) > 0.01:
				return _fail("%s's dock is %.2f m off its locked site" % [t.name, Vector2(t.shore.x, t.shore.z).distance_to(at)])
		for isl in map.islands:
			if not isl.is_mainland and isl.inhabited and isl.dock_sites.is_empty():
				for id in isl.towns:
					if map.towns[id].has_dock:
						return _fail("%s has no locked dock but a dock town" % isl.name)
		_cypress = map.town_by_key("island-3/0")
		if _cypress == null or _cypress.built or sim.terminals.has(_cypress.id):
			return _fail("Expected Cypress Island's site to start unbuilt")
		# A route to every other dock water joins it to (one the planner can't
		# reach at all, like a site facing land, gets none).
		var reached := 0
		for t in docks:
			if t != _cypress and map.routes.any(func(r): return r.a == t.id or r.b == t.id):
				reached += 1
		var routes := map.routes.filter(func(r): return r.a == _cypress.id or r.b == _cypress.id).size()
		if routes < reached - 3:
			return _fail("Cypress has %d planned routes; %d other docks have routes" % [routes, reached])
		print("Cypress: routes to %d of the %d other docks with any" % [routes, reached])
		_port = sim.terminals[map.town_by_key("island-1/0").id]
		if not _port.buy_holding_lane():
			return _fail("Could not buy the first lane")
		_port._advance_construction(1.0)
		_port._advance_construction(Terminal.BUILD_MINUTES)
		if _port.paved.size() != 1 or not _port.buy_holding_lane() or not _port.buy_refit(0):
			return _fail("Could not stage consecutive lane work and a slip refit")
		sim.ledger.credit_flat(false)
		sim.ferries[0].set_pace(0)
		_purchases = sim.ledger.today["purchases"]
		_price = sim.dock_price(_cypress)
		_cash_before = sim.available_cash
		print("Opening: %d terminals of %d dock towns, %d routes; buying %s for $%d of $%d" % [
			sim.terminals.size(), docks.size(), map.routes.size(), _cypress.name, _price, int(_cash_before)])
		_main.buy_dock(_cypress)
		_bought_at = sim.abs_minutes()
		if absf(sim.available_cash - (_cash_before - _price)) > 1.0:
			return _fail("Cash %.0f after buying, expected %.0f" % [sim.available_cash, _cash_before - _price])
		if sim.dock_building(_cypress) <= 0.0 or sim.terminals.has(_cypress.id):
			return _fail("Buying should start a build, not open the terminal at once")
		if sim.buy_dock(_cypress):
			return _fail("The same site was bought twice")
		if sim.ledger.today["purchases"] != _purchases + _price or sim.ledger.cars_total < 1:
			return _fail("Dock purchase changed fare history or was charged incorrectly")
		if _port.paved.size() != 1 or _port.work_stage == Terminal.WorkStage.IDLE or _port.refit_slip != 0:
			return _fail("Dock purchase displaced lane or slip construction")
		Engine.time_scale = 60.0
		return false
	if not sim.terminals.has(_cypress.id):
		if frames > 20000:
			return _fail("Cypress never opened (%.0f min left)" % sim.dock_building(_cypress))
		return false
	Engine.time_scale = 1.0
	if sim.terminals[_port.town.id] != _port or _port.paved.size() != 2 or sim.ferries[0].pace != 0:
		return _fail("Opening the new terminal lost paid work or the assigned service pace")
	var took := sim.abs_minutes() - _bought_at
	if took < Simulation.DOCK_BUILD_MINUTES - 1.0:
		return _fail("Cypress opened after %.0f min, before its %.0f min build" % [took, Simulation.DOCK_BUILD_MINUTES])
	if not _cypress.built or not sim.scenario.terminals.has(_cypress.key):
		return _fail("The open terminal isn't recorded as the company's")
	var site: Node3D = _main.builder.root.find_child(_cypress.name + " Terminal (site)", true, false)
	if site == null or not site.visible:
		return _fail("Cypress's terminal is still hidden")
	var term: Terminal = sim.terminals[_cypress.id]
	if term.has_service():
		return _fail("A new terminal should be idle until a boat calls")
	print("Opened %s after %.1f h, in the same scene; cash $%d" % [_cypress.name, took / 60.0, int(sim.available_cash)])
	print("TEST PASSED")
	quit(0)
	return true
