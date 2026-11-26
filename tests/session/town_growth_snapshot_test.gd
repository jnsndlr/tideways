extends "res://tests/support/company_snapshot_case.gd"


func _initialize() -> void:
	call_deferred("_run")


func _with_lots() -> Simulation:
	var sim := _world()
	var town := sim.map.towns[0]
	town.community_type = "rural"
	var landmark := MapData.TownLot.new()
	landmark.kind = MapData.TownLot.Kind.LANDMARK
	landmark.pos = Vector3(57, 5, 36)
	for i in 3:
		var lot := MapData.TownLot.new()
		lot.kind = MapData.TownLot.Kind.HOUSE
		lot.pos = Vector3(17.0 * i, 3.0, 21.5)
		town.growth_lots.append(lot)
	town.growth_lots.append(landmark)
	var tower := MapData.TownLot.new()
	tower.kind = MapData.TownLot.Kind.RADIO_TOWER
	tower.pos = Vector3(400, 22, 105)
	sim.map.islands[0].radio_tower_lot = tower
	return sim


func _run() -> void:
	var sim := _with_lots()
	var town := sim.map.towns[0]
	var growth := sim.town_growth
	var st := growth.state_for_town(town)
	sim.research_done.append("test_research")
	st.population_exact = town.population + 0.75
	st.wildlife_photos = 7
	st.stable_days = 6
	st.recreation_bonus = 3.25
	st.built_houses -= 2
	growth.step(1.0)
	check(st.active_builds.size() == 2, "The town starts both house sites")
	if st.active_builds.size() != 2:
		sim.free()
		finish()
		return
	st.active_builds[0].elapsed = st.active_builds[0].duration - 0.5
	growth.step(1.0)
	check(
		growth.completed_builds.size() == 1 and st.active_builds.size() == 1,
		"One house finishes while the next is underway"
	)
	var saved := _save(sim)
	var reopened := CompanySnapshot.restore(saved, _with_lots, VehicleFactory.from_parts)
	check(reopened != null, "Reopen a growing company")
	if reopened != null:
		var restored := reopened.town_growth
		var copy := restored.state_for_town(reopened.map.towns[0])
		check(
			reopened.has_research("test_research") and copy.wildlife_photos == 7,
			"Keep earned research and town bonuses"
		)
		check(
			copy.built_houses == st.built_houses and restored.completed_builds.size() == 1,
			"Keep the completed house once"
		)
		check(
			copy.active_builds.size() == 1 and copy.active_builds[0].id == st.active_builds[0].id,
			"Rebind the existing in-flight job"
		)
		check(
			copy.active_builds[0].lot == reopened.map.towns[0].growth_lots[1],
			"Resolve the restored site in the rebuilt map"
		)
		var view := TownConstruction.new()
		root.add_child(view)
		view.setup(reopened, null)
		check(view._active.has(copy.active_builds[0].id), "Reattach the visible construction stage")
		view.free()
		for delta: float in [1.5, 14, 240]:
			growth.step(delta)
			restored.step(delta)
		var baseline := TownGrowthSnapshot.capture(sim)
		var actual := TownGrowthSnapshot.capture(reopened)
		check(
			(
				is_equal_approx(copy.population_exact, st.population_exact)
				and copy.built_houses == st.built_houses
			),
			"Continue fractional growth and complete the next house once"
		)
		check(
			actual.jobs == baseline.jobs and actual.next_job == baseline.next_job,
			"Matching construction history and next job identity"
		)
		reopened.free()
	for key in ["next_job", "metrics_elapsed", "observatory", "towns", "jobs", "research"]:
		var broken := saved.duplicate(true)
		broken.progression.erase(key)
		check(
			CompanySnapshot.restore(broken, _with_lots, VehicleFactory.from_parts) == null,
			"Reject missing " + key
		)
	var duplicate := saved.duplicate(true)
	duplicate.progression.jobs.append(duplicate.progression.jobs[0])
	check(
		CompanySnapshot.restore(duplicate, _with_lots, VehicleFactory.from_parts) == null,
		"Reject two jobs for one occupied site"
	)
	var damaged := saved.duplicate(true)
	damaged.progression.jobs[0].site = "missing pad"
	check(
		CompanySnapshot.restore(damaged, _with_lots, VehicleFactory.from_parts) == null,
		"Reject a missing regenerated site"
	)
	var older := saved.duplicate(true)
	older.version = 2
	older.erase("progression")
	var legacy := CompanySnapshot.restore(older, _with_lots, VehicleFactory.from_parts)
	check(legacy != null, "Older snapshots load their regenerated town defaults")
	if legacy != null:
		check(legacy.research_done.is_empty(), "Older snapshots have the initial research state")
		legacy.free()
	sim.free()
	_check_landmarks()
	finish()


func _check_landmarks() -> void:
	var sim := _with_lots()
	var town := sim.map.towns[0]
	var island := sim.map.island_of(town)
	island.inhabited = true
	island.is_mainland = false
	island.radio_tower_built = false
	var growth := sim.town_growth
	var st := growth.state_for_town(town)
	st.population_exact = 6010.5
	growth.step(1.0)
	check(
		growth.observatory_claimed_town == town.id and not st.pending_milestones.is_empty(),
		"Save the unique observatory claim and pending milestone queue"
	)
	check(growth.island_builds.has(island.id), "Crossing 6,000 residents starts a radio tower")
	var saved := _save(sim)
	var reopened := CompanySnapshot.restore(saved, _with_lots, VehicleFactory.from_parts)
	check(reopened != null, "Restore pending and in-flight landmarks")
	if reopened != null:
		var restored := reopened.town_growth
		var copied := restored.state_of(town.id)
		check(
			(
				restored.observatory_claimed_town == town.id
				and copied.pending_milestones == st.pending_milestones
			),
			"Preserve the town that claimed the observatory and landmark order"
		)
		check(
			(
				restored.island_builds.has(island.id)
				and reopened.map.islands[island.id].radio_tower_built
			),
			"Keep the in-flight radio tower and island bonus"
		)
		var advance := TownGrowth.LANDMARK_BUILD_MINUTES + 1
		growth.step(advance)
		restored.step(advance)
		check(
			(
				restored.island_builds.is_empty()
				and restored.completed_builds.size() == growth.completed_builds.size()
			),
			"Complete the restored radio tower just once"
		)
		check(
			copied.milestone_growth_bonus == st.milestone_growth_bonus,
			"Restoration never awards the tower twice"
		)
		reopened.free()
	sim.free()
