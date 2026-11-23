extends SceneTree
## Locked dock sites on the main map (TID-16). The opening's terminals stand at
## the docks placed in maps/main_story.json, whatever the scheduled links; an
## island with no locked dock has no terminal; Cypress Island's locked site can be
## bought in play, which rebuilds the map with the company carried over and a
## terminal at exactly that site.
##
##   godot --headless --path . --fixed-fps 30 --script tools/dock_site_test.gd

var frames := 0
var _bought := false
var _opening_balance := 0.0
var _prior_purchases := 0.0
var _price := 0
var _day := 0


func _initialize() -> void:
	var main: Node = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)
	current_scene = main


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _island(map: MapData, nm: String) -> MapData.Island:
	for isl in map.islands:
		if isl.name == nm:
			return isl
	return null


func _process(_delta: float) -> bool:
	frames += 1
	if frames > 30000:
		return _fail("Timed out waiting for the purchased dock to open")
	var main = current_scene
	if main == null or main.get("sim") == null or not main.built:
		return false
	var sim: Simulation = main.sim
	var map: MapData = main.map
	var layout: MapLayout = main.layout
	if not _bought:
		# Every terminal stands exactly where its dock was locked.
		for k in layout.islands.size():
			var spec := layout.islands[k]
			var isl := _island(map, spec.name)
			if isl.has_terminal:
				if spec.docks.is_empty():
					return _fail("%s has a terminal but no locked dock" % spec.name)
				var at := spec.dock_at(spec.docks[isl.site])
				if Vector2(isl.shore.x, isl.shore.z).distance_to(at) > 0.01:
					return _fail("%s's terminal is %.2f m off its locked dock" % [spec.name, Vector2(isl.shore.x, isl.shore.z).distance_to(at)])
		var cypress := _island(map, "Cypress Island")
		if cypress.has_terminal or cypress.dock_sites.is_empty():
			return _fail("Expected Cypress Island to start with a locked site and no terminal")
		var port: Terminal = sim.terminals[_island(map, "Port Rosario").id]
		if not port.buy_holding_lane():
			return _fail("Could not start a lane before buying the new dock")
		port._advance_construction(1.0)
		port._advance_construction(Terminal.BUILD_MINUTES)
		if port.paved.size() != 1 or not port.buy_holding_lane():
			return _fail("Could not queue the next paid lane after paving the first")
		if not port.buy_refit(0):
			return _fail("Could not order a slip refit before buying the site")
		sim.ferries[0].set_pace(0)
		sim.ledger.credit_flat(false)
		_price = cypress.dock_sites[0].price()
		_opening_balance = sim.available_cash - CompanyLedger.net(sim.ledger.today)
		_prior_purchases = sim.ledger.today["purchases"]
		_day = sim.day
		print("Opening: %d terminals, %d routes; buying Cypress site 1 for $%d of $%d" % [
			sim.terminals.size(), map.routes.size(), _price, int(sim.available_cash)])
		_bought = true
		main.buy_dock(cypress, 0)
		return false
	var cypress := _island(map, "Cypress Island")
	if not cypress.has_terminal:
		return false   # still the old scene
	var spec: MapLayout.IslandSpec = null
	for s in layout.islands:
		if s.name == "Cypress Island":
			spec = s
	var off := Vector2(cypress.shore.x, cypress.shore.z).distance_to(spec.dock_at(spec.docks[0]))
	if off > 0.01:
		return _fail("Cypress's new terminal is %.2f m off its site" % off)
	if not is_equal_approx(sim.available_cash, _opening_balance + CompanyLedger.net(sim.ledger.today)):
		return _fail("Cash after buying does not reconcile to the day’s opening balance and transactions")
	if sim.day != _day:
		return _fail("The clock didn't carry over")
	var rebuilt_port: Terminal = sim.terminals[_island(map, "Port Rosario").id]
	if rebuilt_port.paved.size() != 1 or rebuilt_port.work_stage in [Terminal.WorkStage.IDLE, Terminal.WorkStage.OPEN]:
		return _fail("Dock purchase discarded the paid lane construction at Port Rosario")
	if rebuilt_port.refit_stage == Terminal.RefitStage.NONE or rebuilt_port.refit_slip != 0:
		return _fail("Dock purchase discarded a paid slip refit")
	if sim.ledger.cars_total < 1 or sim.ledger.today["purchases"] != _prior_purchases + _price:
		return _fail("Dock rebuild lost fare history or charged the wrong purchase total")
	if sim.ferries[0].pace != 0:
		return _fail("Dock rebuild reset the assigned pace")
	var routes := map.routes.filter(func(r): return r.a == cypress.id or r.b == cypress.id).size()
	if routes == 0:
		return _fail("No candidate routes from the new terminal")
	if not sim.terminals.has(cypress.id):
		return _fail("No terminal in the simulation at Cypress")
	print("Bought: Cypress terminal at its site, %d candidate routes from it, cash $%d" % [routes, int(sim.available_cash)])
	print("TEST PASSED")
	quit(0)
	return true
