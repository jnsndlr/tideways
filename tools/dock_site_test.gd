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
var _cash_before := 0.0
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
		_price = cypress.dock_sites[0].price()
		_cash_before = sim.available_cash
		_day = sim.day
		print("Opening: %d terminals, %d routes; buying Cypress site 1 for $%d of $%d" % [
			sim.terminals.size(), map.routes.size(), _price, int(_cash_before)])
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
	if absf(sim.available_cash - (_cash_before - _price)) > 1.0:
		return _fail("Cash %.0f after buying, expected %.0f" % [sim.available_cash, _cash_before - _price])
	if sim.day != _day:
		return _fail("The clock didn't carry over")
	var routes := map.routes.filter(func(r): return r.a == cypress.id or r.b == cypress.id).size()
	if routes == 0:
		return _fail("No candidate routes from the new terminal")
	if not sim.terminals.has(cypress.id):
		return _fail("No terminal in the simulation at Cypress")
	print("Bought: Cypress terminal at its site, %d candidate routes from it, cash $%d" % [routes, int(sim.available_cash)])
	print("TEST PASSED")
	quit(0)
	return true
