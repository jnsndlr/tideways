extends SceneTree
## Dredging for a slip (stage 5): in the opening scenario, buys slips and tie-ups at
## each terminal until one is offered only with dredging, then buys that one. Passes
## once the seabed off it is cut deep, the dredging was charged in its price, the
## terrain there was rebuilt in place, and the slip opens.
##
##   godot --headless --path . --fixed-fps 30 --script tools/dredge_slip_test.gd -- --scenario=opening

var main: Node
var frames := 0
var term: Terminal
var offer: TerminalUpgrade
var index := -1


func _initialize() -> void:
	if not _protected_shore():
		return
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(why: String) -> bool:
	push_error("Dredge slip: " + why)
	quit(1)
	return true


## A cut cannot remove high ground, including where the cut blends into shore.
func _protected_shore() -> bool:
	var terrain := Terrain.new(123, Terrain.CELL * 8)
	terrain.h_grid.resize((terrain.n + 1) * (terrain.n + 1))
	terrain.h_grid.fill(-2.0)
	var center := terrain.n / 2
	var core := center * (terrain.n + 1) + center
	terrain.h_grid[core] = 3.0
	var before := terrain.h_grid.duplicate()
	if terrain.dredge(Vector3.ZERO, Vector3.FORWARD, -8.0, 8.0, 5.0, -7.0, 9.0, true) >= 0.0 or before != terrain.h_grid:
		_fail("Headland in the required channel must reject the entire cut")
		return false
	terrain.h_grid[core] = -2.0
	var edge := core + 2
	terrain.h_grid[edge] = 3.0
	var volume := terrain.dredge(Vector3.ZERO, Vector3.FORWARD, -8.0, 8.0, 5.0, -7.0, 9.0, true)
	if volume <= 0.0 or terrain.h_grid[core] != -7.0 or terrain.h_grid[edge] != 3.0:
		_fail("A dredged channel should leave high ground beside it intact")
		return false
	return true


## Builds `t`'s slip job at once.
func _finish(t: Terminal) -> void:
	t.refit_stage = Terminal.RefitStage.WORKING
	t.refit_remaining = Terminal.REFIT_DEPARTURE + 0.01


func _process(_delta: float) -> bool:
	frames += 1
	if frames > 24000:
		return _fail("timed out")
	if main == null or frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	sim.ledger.cash = maxf(sim.ledger.cash, 500000.0) if offer == null else sim.ledger.cash
	if frames == 5:
		# Include the other authored dock sites so the fixture exercises an
		# actual dredgeable shoreline even when the opening ports have headlands.
		for town: MapData.Town in sim.map.dock_towns():
			if town.built:
				continue
			var survey := SlipSiteSurvey.new(sim, town)
			for site in survey.sites(false) + survey.sites(true):
				if site.y > 0.0:
					print("Opening %s for its naturally shallow expansion site" % town.name)
					sim.open_terminal(town)
					break
			if town.built:
				break
	if offer == null:
		# Every few frames, build the next free slip somewhere until a dredged one is offered.
		if frames % 4 != 0:
			return false
		for t: Terminal in sim.terminals.values():
			if t.refit_stage != Terminal.RefitStage.NONE:
				return false
		for t: Terminal in sim.terminals.values():
			for u in t.upgrades():
				if u.dredge_price > 0 and u.blocked == "":
					term = t
					offer = u
					print("%s: %s · $%d · %s" % [t.town.name, u.title, u.price, u.detail()])
					var cash := sim.available_cash
					var tiles: int = main.builder.root.get_child_count()
					if not t.buy(u):
						return _fail("couldn't buy it")
					if not is_equal_approx(cash - sim.available_cash, u.price):
						return _fail("paid %.0f, not %d" % [cash - sim.available_cash, u.price])
					if not is_equal_approx(t.refit_remaining, u.build_minutes):
						return _fail("Job scheduled for %.0f minutes, quoted %.0f" % [t.refit_remaining, u.build_minutes])
					index = t.town.slips.size() - 1
					var reach := SlipSiteSurvey.reach_for(u.kind == TerminalUpgrade.Kind.SLIP)
					var shallow := 0
					var uu := Layout.PIER_END + 12.0
					while uu < reach.x:
						for dv: float in [-reach.y, 0.0, reach.y]:
							if sim.terrain.height_v(t.site_survey.position_at(u.v + dv, uu)) > -3.6:
								shallow += 1
						uu += 9.0
					if shallow > 0:
						return _fail("%d points off the slip still shallow after dredging" % shallow)
					if t.site_survey.volume_at(u.v, u.kind == TerminalUpgrade.Kind.SLIP) != 0.0:
						return _fail("the dredged site still needs dredging")
					print("Dredged %.0f m³ for $%d; terrain tiles %d -> %d" % [u.dredge_m3, u.dredge_price, tiles, main.builder.root.get_child_count()])
					_finish(t)
					return false
		for t: Terminal in sim.terminals.values():
			for u in t.upgrades():
				if u.kind in [TerminalUpgrade.Kind.SLIP, TerminalUpgrade.Kind.TIE_UP] and u.blocked == "" and u.dredge_price == 0:
					t.buy(u)
					print("Built %s at %s" % [u.title, t.town.name])
					_finish(t)
					return false
		return _fail("no slip anywhere needs dredging, and none is left to build")
	if term.refit_stage == Terminal.RefitStage.NONE:
		if term.town.slips[index].building:
			return _fail("the dredged slip didn't open")
		print("TEST PASSED")
		quit(0)
		return true
	return false
