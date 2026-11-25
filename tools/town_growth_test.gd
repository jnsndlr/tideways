extends SceneTree
## Verifies Town Growth & Long-Term Progression:
## - Community types & main_story.json island assignments (keeping Cypress as Rural)
## - Sliding connectivity expectation (+1 connection per 1,000 pop)
## - 4-factor accessibility (frequency, affordability, reliability/schedule stability, connectivity)
## - Three-part attractiveness (residents -> affordability, industry -> stability, tourism -> wildlife photos)
## - Organic (5/8/10/day), ferry-driven (up to 5x), and milestone growth
## - 1 house / 100 pop and 1 commercial / 333 pop construction triggers & TownConstruction lifecycle
## - 4,000 pop Hangar + Windsock, unique first-rural-only Observatory, and Madrona + 6,000 island Radio Tower
##
##   godot --headless --path . --fixed-fps 30 --script tools/town_growth_test.gd

var _region: TinyRegion
var _sim: Simulation
var _ran := false


func _fail(msg: String) -> bool:
	push_error("TOWN GROWTH TEST FAILED: " + msg)
	if is_instance_valid(_sim):
		_sim.free()
	quit(1)
	return true


func _assert_true(cond: bool, msg: String) -> bool:
	if not cond:
		return _fail(msg)
	return false


func _process(_delta: float) -> bool:
	if _ran:
		return false
	_ran = true

	# 1. Verify main_story.json community type assignments & Cypress kept as Rural.
	var layout := MapLayout.load_file(MapLayout.MAIN_STORY)
	if _assert_true(layout != null, "Could not load main_story.json"):
		return true
	var expected_types := {
		"Port Rosario": "industrial",
		"Madrona Island": "residential",
		"Cypress Island": "rural",
		"Juniper Island": "residential",
		"Bracken Island": "industrial",
		"Kestrel Island": "residential",
		"Gullrock Island": "industrial",
		"San Vela Island": "residential",
		"Cordero Landing": "rural",
		"Eagle Island": "rural",
	}
	for spec in layout.islands:
		if _assert_true(expected_types.has(spec.name), "Unexpected island in main_story: %s" % spec.name):
			return true
		if _assert_true(spec.community_type == expected_types[spec.name],
				"%s expected %s, got %s" % [spec.name, expected_types[spec.name], spec.community_type]):
			return true
	if _assert_true(layout.islands.size() == expected_types.size(), "Expected 10 islands in main_story.json"):
		return true

	# 2. Verify sliding connectivity expectation (+1 per 1,000 pop).
	var conn_cases := [
		[500, 1], [999, 1], [1000, 2], [1999, 2], [2000, 3], [3000, 4], [4000, 5], [5000, 6], [8000, 6],
	]
	for c in conn_cases:
		var got := TownGrowth.expected_connections_for(c[0], 10)
		if _assert_true(got == c[1], "Pop %d expected %d connections, got %d" % [c[0], c[1], got]):
			return true

	# 3. Verify 1 house / 100 pop and 1 commercial / 333 pop formulas.
	if _assert_true(TownGrowth.target_houses_for(1250) == 12, "1250 pop -> 12 houses"):
		return true
	if _assert_true(TownGrowth.target_commercial_for(1000) == 3, "1000 pop -> 3 commercial"):
		return true

	# 4. Spin up a 3-town TinyRegion simulation for live progression tests.
	_region = TinyRegion.build(3)
	_region.map.islands[0].community_type = "industrial"
	_region.map.islands[1].community_type = "residential"
	_region.map.islands[2].community_type = "rural"
	_region.map.islands[1].name = "Madrona Island"
	_region.map.islands[1].radio_tower_built = true

	for i in 3:
		var town := _region.map.towns[i]
		town.community_type = _region.map.islands[i].community_type
		town.population = [1100, 1100, 1100][i]
		# Give each town plenty of unoccupied growth lots (house, commercial, landmark).
		for k in 15:
			var hlot := MapData.TownLot.new()
			hlot.pos = town.town_center + Vector3(12.0 + k * 8.0, 6.0, 0.0)
			hlot.lot_y = 6.0
			hlot.kind = MapData.TownLot.Kind.HOUSE
			town.growth_lots.append(hlot)
		for k in 6:
			var clot := MapData.TownLot.new()
			clot.pos = town.town_center + Vector3(12.0 + k * 10.0, 6.0, 12.0)
			clot.lot_y = 6.0
			clot.kind = MapData.TownLot.Kind.COMMERCIAL
			town.growth_lots.append(clot)
		for k in 4:
			var llot := MapData.TownLot.new()
			llot.pos = town.town_center + Vector3(-20.0 - k * 15.0, 6.0, 18.0)
			llot.lot_y = 6.0
			llot.kind = MapData.TownLot.Kind.LANDMARK
			town.growth_lots.append(llot)
		var rlot := MapData.TownLot.new()
		rlot.pos = town.town_center + Vector3(0.0, 18.0, -35.0)
		rlot.lot_y = 18.0
		rlot.kind = MapData.TownLot.Kind.RADIO_TOWER
		_region.map.islands[i].radio_tower_lot = rlot

	_sim = _region.start(root)
	var tg := _sim.town_growth
	var t_ind := _region.map.towns[0]
	var t_res := _region.map.towns[1]
	var t_rur := _region.map.towns[2]
	var st_ind := tg.state_for_town(t_ind)
	var st_res := tg.state_for_town(t_res)
	var st_rur := tg.state_for_town(t_rur)

	# Verify organic baselines (Madrona has starting radio tower +15% bonus).
	if _assert_true(is_equal_approx(st_ind.organic_daily, 8.0), "Industrial organic baseline should be 8/day"):
		return true
	if _assert_true(is_equal_approx(st_res.organic_daily, 10.0 * 1.15), "Madrona residential baseline + radio tower should be 11.5/day"):
		return true
	if _assert_true(is_equal_approx(st_rur.organic_daily, 5.0), "Rural organic baseline should be 5/day"):
		return true

	# Verify ferry-driven growth accelerates served towns without exceeding 5x total.
	if _assert_true(st_ind.has_service and st_ind.ferry_daily > 0.0, "Served town must earn ferry-driven growth"):
		return true
	if _assert_true(st_ind.total_daily <= st_ind.organic_daily * 5.0 + 0.01, "Total growth must cap at 5x baseline"):
		return true

	# Verify affordability affects Residents attractiveness & accessibility.
	_sim.ledger.set_vehicle_fare(10.0)
	_sim.ledger.set_passenger_fare(3.0)
	tg.refresh_metrics()
	var cheap_aff := st_res.affordability_score
	for _d in 4:
		tg.start_day()
	var cheap_res_attr := st_res.attractiveness_residents

	_sim.ledger.set_vehicle_fare(55.0)
	_sim.ledger.set_passenger_fare(28.0)
	tg.refresh_metrics()
	var pricey_aff := st_res.affordability_score
	if _assert_true(cheap_aff > pricey_aff + 0.4, "Lower fares must improve affordability (%.2f vs %.2f)" % [cheap_aff, pricey_aff]):
		return true
	for _d in 4:
		tg.start_day()
	if _assert_true(st_res.attractiveness_residents < cheap_res_attr, "High fares must lower resident attractiveness"):
		return true

	# Reset to fair fares and test Reliability / schedule stability (Industry prioritizes stability).
	_sim.ledger.set_vehicle_fare(CompanyLedger.DEFAULT_VEHICLE_FARE)
	_sim.ledger.set_passenger_fare(CompanyLedger.DEFAULT_PASSENGER_FARE)
	for _d in 5:
		tg.start_day()
	var stable_rel := st_ind.reliability_score
	var stable_ind_attr := st_ind.attractiveness_industry
	tg.on_schedule_changed([t_ind.id], true)
	var churned_rel := st_ind.reliability_score
	if _assert_true(churned_rel < stable_rel - 0.15, "Changing route must reduce reliability (%.2f -> %.2f)" % [stable_rel, churned_rel]):
		return true
	for _d in 3:
		tg.on_schedule_changed([t_ind.id], false)
		tg.start_day()
	if _assert_true(st_ind.attractiveness_industry < stable_ind_attr, "Schedule churn must hurt industry attractiveness"):
		return true

	# Verify wildlife photography plugs into Tourism attractiveness!
	var tour_before := st_rur.attractiveness_tourism
	var visit := Wildlife.Visit.new()
	visit.species = _sim.wildlife.find_species("orca")
	visit.target = _region.map.islands[2]
	visit.credited = [_region.map.islands[2]]
	visit.phase = Wildlife.Phase.CIRCLE
	if _assert_true(_sim.wildlife.photograph(visit), "Wildlife.photograph should succeed"):
		return true
	if _assert_true(st_rur.wildlife_photos == 1 and st_rur.wildlife_photo_bonus > 5.0 and st_rur.attractiveness_tourism > tour_before + 3.0,
			"Wildlife photography must boost tourism attractiveness"):
		return true

	# Verify economic activity raises commercial truck share & vehicle demand,
	# and attractiveness raises passenger demand.
	st_ind.economic_activity = 90.0
	st_rur.economic_activity = 20.0
	if _assert_true(tg.commercial_truck_share(t_ind) > tg.commercial_truck_share(t_rur) + 0.10,
			"Higher economic activity must raise commercial truck share"):
		return true
	if _assert_true(tg.vehicle_demand_multiplier(t_ind) > tg.vehicle_demand_multiplier(t_rur) + 0.30,
			"Higher economic activity must raise vehicle demand multiplier"):
		return true
	st_rur.attractiveness_tourism = 92.0
	st_ind.attractiveness_tourism = 20.0
	if _assert_true(tg.passenger_demand_multiplier(t_rur) > tg.passenger_demand_multiplier(t_ind) + 0.25,
			"Higher tourism attractiveness must raise passenger demand multiplier"):
		return true

	# Verify 1 house/100 pop and 1 commercial/333 pop trigger construction jobs & complete cleanly.
	var started_kinds: Array[int] = []
	var completed_models: Array[String] = []
	tg.construction_started.connect(func(job: TownGrowth.BuildJob): started_kinds.append(job.kind))
	tg.construction_completed.connect(func(job: TownGrowth.BuildJob):
		completed_models.append(job.landmark_model if job.kind >= MapData.TownLot.Kind.LANDMARK else str(job.kind)))

	# Attach TownConstruction to verify scene instantiation & cleanup with zero errors.
	var tc := TownConstruction.new()
	root.add_child(tc)
	tc.setup(_sim, null)

	var houses_before := st_rur.built_houses
	var comm_before := st_rur.built_commercial
	st_rur.population_exact = 1350.0 # crosses +2 houses (11->13) and +1 commercial (3->4)
	tg.step(1.0)
	if _assert_true(MapData.TownLot.Kind.HOUSE in started_kinds or MapData.TownLot.Kind.COMMERCIAL in started_kinds,
			"Crossing 100/333 pop thresholds must start construction jobs"):
		return true
	# Advance enough game minutes to finish queued house & commercial builds.
	for _s in 60:
		tg.step(30.0)
	if _assert_true(st_rur.built_houses >= houses_before + 2,
			"Expected at least 2 new houses built (was %d, now %d)" % [houses_before, st_rur.built_houses]):
		return true
	if _assert_true(st_rur.built_commercial >= comm_before + 1,
			"Expected at least 1 new commercial building (was %d, now %d)" % [comm_before, st_rur.built_commercial]):
		return true

	# Verify 4,000 pop Hangar + unique first-rural-only Observatory!
	var milestones_hit: Array[String] = []
	tg.milestone_unlocked.connect(func(town: MapData.Town, mid: String, _title: String, _detail: String):
		milestones_hit.append("%d:%s" % [town.id, mid]))
	st_rur.population_exact = 4005.0
	tg.step(1.0)
	if _assert_true("%d:airfield_4000" % t_rur.id in milestones_hit, "Rural town at 4k must unlock airfield_4000"):
		return true
	if _assert_true("%d:observatory_4000" % t_rur.id in milestones_hit, "First rural town at 4k must unlock observatory_4000"):
		return true
	if _assert_true(tg.observatory_claimed_town == t_rur.id, "Observatory must be claimed by first rural town"):
		return true

	# Make town 0 rural too and push it past 4k -> must get airfield_4000, MUST NOT get observatory_4000!
	t_ind.community_type = "rural"
	st_ind.population_exact = 4005.0
	tg.step(1.0)
	if _assert_true("%d:airfield_4000" % t_ind.id in milestones_hit, "Second town at 4k must still unlock airfield_4000"):
		return true
	if _assert_true(not ("%d:observatory_4000" % t_ind.id in milestones_hit), "Only the FIRST rural town at 4k may get the Observatory"):
		return true

	# Verify Island Radio Tower at 6,000 island total pop (Madrona started with one; island 2 earns one).
	var radio_islands: Array[int] = []
	tg.island_radio_tower_unlocked.connect(func(isl: MapData.Island): radio_islands.append(isl.id))
	st_rur.population_exact = 6010.0
	tg.step(1.0)
	if _assert_true(t_rur.island in radio_islands and _region.map.islands[t_rur.island].radio_tower_built,
			"Island hitting 6,000 total population must unlock Radio Tower"):
		return true
	# Advance to finish all milestone & radio tower builds cleanly.
	for _s in 60:
		tg.step(30.0)
	if _assert_true("airplane_hangar_low" in completed_models and "observatory" in completed_models and "radio_tower" in completed_models,
			"Hangar, Observatory, and Radio Tower builds must complete (got %s)" % [completed_models]):
		return true

	tc.free()
	_sim.free()
	print("TEST PASSED")
	quit(0)
	return true
