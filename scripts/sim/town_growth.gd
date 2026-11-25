class_name TownGrowth
extends RefCounted
## Owns town progression: community types, accessibility (frequency, affordability,
## reliability/schedule stability, sliding connectivity), three-part attractiveness
## (residents, industry, tourism with wildlife photography), economic activity,
## organic + ferry-driven + milestone growth, and building construction jobs.

signal population_changed(town: MapData.Town, new_pop: int)
signal construction_started(job: BuildJob)
signal construction_completed(job: BuildJob)
signal milestone_unlocked(town: MapData.Town, milestone_id: String, title: String, detail: String)
signal island_radio_tower_unlocked(island: MapData.Island)

const PEOPLE_PER_HOUSE := 100
const PEOPLE_PER_COMMERCIAL := 333
const MAX_CONCURRENT_BUILDS := 2
const HOUSE_BUILD_MINUTES := 240.0       # 4 game hours
const COMMERCIAL_BUILD_MINUTES := 420.0  # 7 game hours
const LANDMARK_BUILD_MINUTES := 480.0    # 8 game hours
const STABILITY_DAYS_FULL := 5.0
const RADIO_TOWER_ISLAND_POP := 6000
const CONNECTIVITY_POP_STEP := 1000
const MAX_EXPECTED_CONNECTIONS := 6
## Multiplies every town's daily growth. A game day is 48 real minutes at 1x, so the
## profile rates alone (5-50 people/day) meant a new house every few real hours.
## Raise it to speed every town up together.
const GROWTH_SCALE := 1.0

const PROFILES := {
	"rural": {
		"label": "Rural",
		"organic_daily": 5.0,
		"base_economy": 22.0,
		"base_residents": 30.0,
		"base_industry": 18.0,
		"base_tourism": 38.0,
		"weights": Vector3(0.35, 0.20, 0.45), # residents, industry, tourism
	},
	"residential": {
		"label": "Residential",
		"organic_daily": 10.0,
		"base_economy": 38.0,
		"base_residents": 38.0,
		"base_industry": 24.0,
		"base_tourism": 30.0,
		"weights": Vector3(0.55, 0.20, 0.25),
	},
	"industrial": {
		"label": "Industrial",
		"organic_daily": 8.0,
		"base_economy": 54.0,
		"base_residents": 26.0,
		"base_industry": 42.0,
		"base_tourism": 18.0,
		"weights": Vector3(0.25, 0.60, 0.15),
	},
}


class BuildJob:
	var id := 0
	var town_id := -1
	var island_id := -1
	var lot: MapData.TownLot
	var kind := MapData.TownLot.Kind.HOUSE
	var milestone_id := ""
	var landmark_model := ""
	var duration := HOUSE_BUILD_MINUTES
	var elapsed := 0.0

	func progress() -> float:
		return clampf(elapsed / maxf(duration, 1.0), 0.0, 1.0)


class TownState:
	var town_id := 0
	var population_exact := 0.0
	var economic_activity := 40.0
	var attractiveness_residents := 45.0
	var attractiveness_industry := 40.0
	var attractiveness_tourism := 45.0
	var attractiveness := 45.0

	# Accessibility breakdown (0..1)
	var accessibility := 0.0
	var frequency_score := 0.0
	var affordability_score := 0.0
	var reliability_score := 0.0
	var connectivity_score := 0.0
	var daily_departures := 0.0
	var expected_departures := 3.0
	var active_connections := 0
	var expected_connections := 1
	var has_service := false

	# Reliability / schedule stability
	var stable_days := 0.0
	var edited_today := false
	var schedule_churn := 0.0

	# Tourism & attraction hooks (wildlife photos + extensible recreation/amenities)
	var wildlife_photo_bonus := 0.0
	var wildlife_photos := 0
	var recreation_bonus := 0.0

	# Daily growth telemetry
	var organic_daily := 0.0
	var ferry_daily := 0.0
	var total_daily := 0.0

	# Milestones & permanent modifiers
	var milestones: Array[String] = []
	var milestone_growth_bonus := 0.0
	var milestone_residents_bonus := 0.0
	var milestone_industry_bonus := 0.0
	var milestone_tourism_bonus := 0.0
	var milestone_economy_bonus := 0.0

	# Buildings
	var built_houses := 0
	var built_commercial := 0
	var pending_milestones: Array[Dictionary] = []
	var active_builds: Array[BuildJob] = []


var sim: Simulation
var states := {}                  # town_id -> TownState
var island_builds := {}           # island_id -> BuildJob (radio tower)
var observatory_claimed_town := -1
var _next_job_id := 1
var _metrics_acc := 0.0


static func profile_for(community_type: String) -> Dictionary:
	return PROFILES.get(community_type, PROFILES["residential"])


static func community_label(community_type: String) -> String:
	return str(profile_for(community_type)["label"])


static func expected_connections_for(population: int, max_possible := MAX_EXPECTED_CONNECTIONS) -> int:
	var raw := 1 + int(maxi(population, 0) / CONNECTIVITY_POP_STEP)
	return clampi(raw, 1, maxi(1, mini(MAX_EXPECTED_CONNECTIONS, max_possible)))


static func target_houses_for(population: int) -> int:
	return maxi(0, int(population / PEOPLE_PER_HOUSE))


static func target_commercial_for(population: int) -> int:
	return maxi(0, int(population / PEOPLE_PER_COMMERCIAL))


func setup(simulation: Simulation) -> void:
	sim = simulation
	states.clear()
	island_builds.clear()
	observatory_claimed_town = -1
	if sim == null or sim.map == null:
		return

	for town in sim.map.towns:
		var st := TownState.new()
		st.town_id = town.id
		st.population_exact = float(town.population)
		var prof := profile_for(town.community_type)
		st.economic_activity = float(prof["base_economy"])
		st.attractiveness_residents = float(prof["base_residents"])
		st.attractiveness_industry = float(prof["base_industry"])
		st.attractiveness_tourism = float(prof["base_tourism"])
		var isl := sim.map.island_of(town)
		if isl != null:
			st.attractiveness_tourism = clampf(st.attractiveness_tourism + isl.wildlife_appeal * 4.5, 0.0, 100.0)
		st.built_houses = town.initial_houses if town.initial_houses > 0 else target_houses_for(town.population)
		st.built_commercial = town.initial_commercial if town.initial_commercial > 0 else target_commercial_for(town.population)
		_seed_starting_milestones(town, st)
		if isl != null and isl.radio_tower_built:
			_apply_radio_tower_bonuses(st)
		states[town.id] = st

	# Towns that start with active ferry service begin with 1 stable day so opening day feels responsive.
	refresh_metrics()
	for town in sim.map.towns:
		var st: TownState = states[town.id]
		if st.has_service:
			st.stable_days = 1.0
	refresh_metrics()
	_sync_island_populations()

	if sim.wildlife != null and not sim.wildlife.photographed.is_connected(_on_wildlife_photographed):
		sim.wildlife.photographed.connect(_on_wildlife_photographed)


## Establishes milestones already below a town's starting population (without triggering
## a flood of construction sites or toasts at frame 0). The unique rural observatory
## and 4k airfield remain earnable through gameplay unless already far past 4,000.
func _seed_starting_milestones(town: MapData.Town, st: TownState) -> void:
	for def in _town_milestone_defs(town.community_type):
		var pop_req := int(def["pop"])
		var mid := str(def["id"])
		if mid == "observatory_4000":
			continue
		if town.population >= pop_req:
			st.milestones.append(mid)
			_apply_milestone_bonuses(st, def)


func _town_milestone_defs(community_type: String) -> Array[Dictionary]:
	var defs: Array[Dictionary] = []
	match community_type:
		"rural":
			defs.append({
				"id": "tier_1500", "pop": 1500, "title": "Village Post & Market",
				"model": "post_office", "growth": 0.10, "res": 6.0, "ind": 2.0, "tour": 8.0, "econ": 4.0, "rec": 4.0,
			})
			defs.append({
				"id": "tier_2500", "pop": 2500, "title": "Harbor Inn",
				"model": "harbor_inn", "growth": 0.15, "res": 5.0, "ind": 3.0, "tour": 14.0, "econ": 6.0, "rec": 10.0,
			})
		"industrial":
			defs.append({
				"id": "tier_1500", "pop": 1500, "title": "Harbor Freight Shed",
				"model": "crab_wharf_shack", "growth": 0.10, "res": 3.0, "ind": 10.0, "tour": 0.0, "econ": 8.0, "rec": 0.0,
			})
			defs.append({
				"id": "tier_2500", "pop": 2500, "title": "Waterfront Depot",
				"model": "waterfront_depot", "growth": 0.15, "res": 4.0, "ind": 14.0, "tour": 2.0, "econ": 12.0, "rec": 0.0,
			})
		_:
			defs.append({
				"id": "tier_1500", "pop": 1500, "title": "Neighborhood Post Office",
				"model": "post_office", "growth": 0.10, "res": 10.0, "ind": 3.0, "tour": 4.0, "econ": 4.0, "rec": 3.0,
			})
			defs.append({
				"id": "tier_2500", "pop": 2500, "title": "Civic Hall",
				"model": "city_hall", "growth": 0.15, "res": 12.0, "ind": 5.0, "tour": 6.0, "econ": 8.0, "rec": 5.0,
			})
	defs.append({
		"id": "airfield_4000", "pop": 4000, "title": "Regional Airfield Hangar",
		"model": "airplane_hangar_low", "growth": 0.20, "res": 8.0, "ind": 10.0, "tour": 10.0, "econ": 12.0, "rec": 6.0,
	})
	if community_type == "rural":
		defs.append({
			"id": "observatory_4000", "pop": 4000, "title": "Coastal Observatory",
			"model": "observatory", "growth": 0.15, "res": 4.0, "ind": 2.0, "tour": 20.0, "econ": 5.0, "rec": 16.0,
		})
	return defs


func _apply_milestone_bonuses(st: TownState, def: Dictionary) -> void:
	st.milestone_growth_bonus += float(def.get("growth", 0.0))
	st.milestone_residents_bonus += float(def.get("res", 0.0))
	st.milestone_industry_bonus += float(def.get("ind", 0.0))
	st.milestone_tourism_bonus += float(def.get("tour", 0.0))
	st.milestone_economy_bonus += float(def.get("econ", 0.0))
	st.recreation_bonus += float(def.get("rec", 0.0))


func _apply_radio_tower_bonuses(st: TownState) -> void:
	st.milestone_growth_bonus += 0.15
	st.milestone_residents_bonus += 10.0
	st.milestone_industry_bonus += 10.0
	st.milestone_tourism_bonus += 10.0
	st.milestone_economy_bonus += 8.0


func state_of(town_id: int) -> TownState:
	return states.get(town_id)


func state_for_town(town: MapData.Town) -> TownState:
	return states.get(town.id) if town != null else null


## Extensible hook for future recreational buildings & attractions (e.g. hot air balloons).
func add_recreation_bonus(town_id: int, amount: float) -> void:
	var st: TownState = states.get(town_id)
	if st == null:
		return
	st.recreation_bonus = clampf(st.recreation_bonus + amount, 0.0, 45.0)
	refresh_metrics()


## Called by Simulation when a ferry's stops or timetable are edited.
## Changing routes or departure times reduces schedule stability for affected towns.
func on_schedule_changed(affected_town_ids: Array[int], stops_changed: bool) -> void:
	var seen := {}
	for tid in affected_town_ids:
		if seen.has(tid) or not states.has(tid):
			continue
		seen[tid] = true
		var st: TownState = states[tid]
		st.edited_today = true
		if stops_changed:
			st.stable_days = maxf(st.stable_days * 0.25, 0.0)
			st.schedule_churn = minf(st.schedule_churn + 1.0, 4.0)
		else:
			st.stable_days = maxf(st.stable_days - 2.0, 0.0)
			st.schedule_churn = minf(st.schedule_churn + 0.5, 4.0)
	refresh_metrics()


## Wildlife photography directly increases tourism attractiveness on credited islands.
func _on_wildlife_photographed(visit: Wildlife.Visit) -> void:
	if visit == null or sim == null or sim.map == null:
		return
	var islands: Array[MapData.Island] = []
	for isl in visit.credited:
		if isl != null and isl not in islands:
			islands.append(isl)
	if islands.is_empty() and visit.target != null:
		islands.append(visit.target)
	var boost := clampf(3.0 + visit.species.draw * 3.5, 3.0, 14.0)
	for isl in islands:
		for tid in isl.towns:
			var st: TownState = states.get(tid)
			if st == null:
				continue
			st.wildlife_photos += 1
			st.wildlife_photo_bonus = clampf(st.wildlife_photo_bonus + boost, 0.0, 35.0)
			st.attractiveness_tourism = clampf(st.attractiveness_tourism + boost * 0.55, 0.0, 100.0)
			_recompute_overall_attractiveness(sim.map.towns[tid], st)
	refresh_metrics()


## Advances smooth population accumulation and active construction sites by `dmin` game minutes.
func step(dmin: float) -> void:
	if sim == null or sim.map == null or dmin <= 0.0:
		return
	_metrics_acc += dmin
	if _metrics_acc >= 15.0:
		_metrics_acc = 0.0
		refresh_metrics()

	var day_frac := dmin / 1440.0
	var any_pop_changed := false
	for town in sim.map.towns:
		var st: TownState = states.get(town.id)
		if st == null:
			continue
		if st.total_daily > 0.0:
			st.population_exact += st.total_daily * day_frac
			var new_pop := int(floor(st.population_exact))
			if new_pop > town.population:
				town.population = new_pop
				any_pop_changed = true
				population_changed.emit(town, new_pop)
				_check_town_milestones(town, st)
		_advance_town_builds(town, st, dmin)
		_queue_needed_builds(town, st)

	if any_pop_changed:
		_sync_island_populations()
		_check_island_radio_towers()
	_advance_island_builds(dmin)


## Daily rollover at midnight: updates schedule stability streaks, drifts economy and
## three-part attractiveness toward their service targets, and checks milestones.
func start_day() -> void:
	if sim == null or sim.map == null:
		return
	refresh_metrics()
	for town in sim.map.towns:
		var st: TownState = states.get(town.id)
		if st == null:
			continue
		if st.has_service:
			if not st.edited_today:
				st.stable_days = minf(st.stable_days + 1.0, 14.0)
		else:
			st.stable_days = maxf(st.stable_days - 1.0, 0.0)
		st.edited_today = false
		st.schedule_churn = maxf(st.schedule_churn - 0.35, 0.0)
		# Photo fame fades gently over ~20 days while leaving lasting momentum through tourism growth.
		st.wildlife_photo_bonus = maxf(st.wildlife_photo_bonus * 0.94, 0.0)

		var targets := _pillar_targets(town, st)
		var drift := 0.22
		st.attractiveness_residents = clampf(lerpf(st.attractiveness_residents, targets["residents"], drift), 5.0, 100.0)
		st.attractiveness_industry = clampf(lerpf(st.attractiveness_industry, targets["industry"], drift), 5.0, 100.0)
		st.attractiveness_tourism = clampf(lerpf(st.attractiveness_tourism, targets["tourism"], drift), 5.0, 100.0)
		_recompute_overall_attractiveness(town, st)
		st.economic_activity = clampf(lerpf(st.economic_activity, targets["economy"], drift), 5.0, 100.0)
	refresh_metrics()


## Recomputes accessibility, connectivity, frequency, affordability, reliability, and
## current daily growth projections for all towns.
func refresh_metrics() -> void:
	if sim == null or sim.map == null:
		return
	var dock_count := sim.map.dock_towns().size()
	var max_other_docks := maxi(dock_count - 1, 1)

	for town in sim.map.towns:
		var st: TownState = states.get(town.id)
		if st == null:
			continue
		var term: Terminal = sim.terminals.get(town.id)
		var service_info := _measure_service(town.id)
		var deps: float = service_info["departures"]
		var dests: Array[int] = service_info["destinations"]
		var mainland_link: bool = service_info["mainland"]

		st.daily_departures = deps
		st.expected_departures = clampf(3.0 + float(town.population) / 800.0, 3.0, 18.0)
		st.active_connections = dests.size()
		st.expected_connections = expected_connections_for(town.population, max_other_docks)
		st.has_service = term != null and deps > 0.0 and not dests.is_empty()

		if st.has_service:
			st.frequency_score = clampf(deps / st.expected_departures, 0.0, 1.0)
			st.affordability_score = _affordability_score(town)
			st.reliability_score = _reliability_score(st, term)
			var base_conn := float(st.active_connections) / float(st.expected_connections)
			st.connectivity_score = clampf(base_conn + (0.10 if mainland_link else 0.0), 0.0, 1.0)
			st.accessibility = clampf(
				st.frequency_score * 0.30
				+ st.affordability_score * 0.25
				+ st.reliability_score * 0.25
				+ st.connectivity_score * 0.20,
				0.0, 1.0
			)
		else:
			st.frequency_score = 0.0
			st.affordability_score = 0.0
			st.reliability_score = 0.0
			st.connectivity_score = 0.0
			st.accessibility = 0.0

		_recompute_overall_attractiveness(town, st)
		var prof := profile_for(town.community_type)
		st.organic_daily = float(prof["organic_daily"]) * GROWTH_SCALE * (1.0 + st.milestone_growth_bonus)
		if st.has_service:
			var attract_factor := 0.70 + 0.45 * (st.attractiveness / 100.0)
			var ferry_mult := clampf(4.0 * st.accessibility * attract_factor, 0.0, 4.0)
			st.ferry_daily = st.organic_daily * ferry_mult
		else:
			st.ferry_daily = 0.0
		st.total_daily = st.organic_daily + st.ferry_daily


func _measure_service(town_id: int) -> Dictionary:
	var departures := 0.0
	var dests: Array[int] = []
	var mainland := false
	for f in sim.ferries:
		if not is_instance_valid(f) or not f.assigned or f.stops.size() < 2:
			continue
		if f.berth == Ferry.Berth.TIED_UP and not f.between_sailings() and not f.return_requested:
			continue
		var calls := 0
		for sid in f.stops:
			if sid == town_id:
				calls += 1
		if calls == 0:
			continue
		var rounds_per_day := 0.0
		if not f.timetable.is_empty():
			rounds_per_day = float(f.timetable.size())
		else:
			var offsets := f.plan_offsets(f.stops)
			var round_min := offsets[-1] if not offsets.is_empty() else 60.0
			rounds_per_day = clampf(1440.0 / maxf(round_min, 20.0), 1.0, 24.0)
		departures += rounds_per_day * float(calls)
		for sid in f.stops:
			if sid != town_id and sid not in dests:
				dests.append(sid)
				var other := sim.map.towns[sid]
				if other != null and sim.map.island_of(other).mainland_port:
					mainland = true
	return {"departures": departures, "destinations": dests, "mainland": mainland}


func _affordability_score(town: MapData.Town) -> float:
	var v_ratio := sim.avg_vehicle_fare_at(town) / CompanyLedger.DEFAULT_VEHICLE_FARE
	var p_ratio := sim.avg_passenger_fare_at(town) / CompanyLedger.DEFAULT_PASSENGER_FARE
	var ratio := (v_ratio + p_ratio) * 0.5
	if ratio <= 0.75:
		return 1.0
	if ratio <= 1.0:
		return lerpf(1.0, 0.85, (ratio - 0.75) / 0.25)
	return clampf(0.85 * exp(-1.35 * (ratio - 1.0)), 0.0, 0.85)


func _reliability_score(st: TownState, term: Terminal) -> float:
	var stability := lerpf(0.35, 1.0, clampf(st.stable_days / STABILITY_DAYS_FULL, 0.0, 1.0))
	if st.schedule_churn > 0.5:
		stability = maxf(0.15, stability - (st.schedule_churn - 0.5) * 0.14)
	var sat := term.satisfaction() if term != null else 70.0
	var ops := clampf((sat - 25.0) / 70.0, 0.1, 1.0)
	return clampf(stability * 0.65 + ops * 0.35, 0.0, 1.0)


func _pillar_targets(town: MapData.Town, st: TownState) -> Dictionary:
	var prof := profile_for(town.community_type)
	var isl := sim.map.island_of(town)
	var wildlife_appeal := isl.wildlife_appeal if isl != null else 1.0
	var wildlife_rep := sim.wildlife.reputation(isl) if (sim.wildlife != null and isl != null) else 0.0
	var wildlife_contrib := clampf(wildlife_appeal * 5.0 + wildlife_rep * 2.5, 0.0, 26.0)

	# Residents prioritize affordability (plus frequency & connectivity).
	var residents := clampf(
		float(prof["base_residents"])
		+ st.affordability_score * 36.0
		+ st.frequency_score * 12.0
		+ st.connectivity_score * 8.0
		+ st.milestone_residents_bonus,
		5.0, 100.0
	)
	# Industry prioritizes stability/reliability (plus connectivity & frequency).
	var industry := clampf(
		float(prof["base_industry"])
		+ st.reliability_score * 38.0
		+ st.connectivity_score * 12.0
		+ st.frequency_score * 6.0
		+ st.milestone_industry_bonus,
		5.0, 100.0
	)
	# Tourism prioritizes amenities & attractions: wildlife appeal, wildlife photos,
	# milestones, and future hot air balloons / recreational buildings.
	var tourism := clampf(
		float(prof["base_tourism"])
		+ wildlife_contrib
		+ st.wildlife_photo_bonus
		+ st.recreation_bonus
		+ st.accessibility * 14.0
		+ st.milestone_tourism_bonus,
		5.0, 100.0
	)
	var economy := clampf(
		float(prof["base_economy"])
		+ (industry / 100.0) * 28.0
		+ st.accessibility * 14.0
		+ minf(float(st.built_commercial) * 1.4, 16.0)
		+ st.milestone_economy_bonus,
		5.0, 100.0
	)
	return {
		"residents": residents,
		"industry": industry,
		"tourism": tourism,
		"economy": economy,
	}


func _recompute_overall_attractiveness(town: MapData.Town, st: TownState) -> void:
	var w: Vector3 = profile_for(town.community_type)["weights"]
	st.attractiveness = clampf(
		st.attractiveness_residents * w.x
		+ st.attractiveness_industry * w.y
		+ st.attractiveness_tourism * w.z,
		0.0, 100.0
	)


# --- Demand modifiers (consumed by Simulation / Terminal / VehicleFactory) ----------

## Vehicle arrival multiplier driven by economic activity & resident/industry demand.
func vehicle_demand_multiplier(town: MapData.Town) -> float:
	var st := state_for_town(town)
	if st == null:
		return 1.0
	return lerpf(0.75, 1.45, st.economic_activity / 100.0)


## Commercial vehicle (van / truck / rig) share driven by economic activity & industry appeal.
func commercial_truck_share(town: MapData.Town) -> float:
	var st := state_for_town(town)
	if st == null:
		return VehicleFactory.TRUCK_SHARE
	var drive := clampf((st.economic_activity * 0.65 + st.attractiveness_industry * 0.35) / 100.0, 0.0, 1.0)
	return lerpf(0.08, 0.34, drive)


## Walk-on passenger / tourist arrival multiplier driven by tourism & resident attractiveness.
func passenger_demand_multiplier(town: MapData.Town) -> float:
	var st := state_for_town(town)
	if st == null:
		return 1.0
	var drive := clampf((st.attractiveness_tourism * 0.60 + st.attractiveness_residents * 0.40) / 100.0, 0.0, 1.0)
	return lerpf(0.70, 1.65, drive)


## Destination pull weight multiplier for trips heading to `town`.
func destination_pull_multiplier(town: MapData.Town) -> float:
	var st := state_for_town(town)
	if st == null:
		return 1.0
	var drive := clampf((st.attractiveness_tourism * 0.50 + st.economic_activity * 0.30 + st.attractiveness_residents * 0.20) / 100.0, 0.0, 1.0)
	return lerpf(0.75, 1.55, drive)


# --- Milestones & Construction Jobs -------------------------------------------------

func _check_town_milestones(town: MapData.Town, st: TownState) -> void:
	for def in _town_milestone_defs(town.community_type):
		var mid := str(def["id"])
		if mid in st.milestones:
			continue
		if town.population < int(def["pop"]):
			continue
		if mid == "observatory_4000":
			if observatory_claimed_town >= 0 or town.community_type != "rural":
				continue
			observatory_claimed_town = town.id
		st.milestones.append(mid)
		_apply_milestone_bonuses(st, def)
		st.pending_milestones.append(def)
		var title := str(def["title"])
		var detail := "%s reached %d residents and unlocked %s (+%d%% base growth)." % [
			town.name, int(def["pop"]), title, roundi(float(def["growth"]) * 100.0)
		]
		milestone_unlocked.emit(town, mid, title, detail)


func _sync_island_populations() -> void:
	for isl in sim.map.islands:
		if isl.towns.is_empty():
			continue
		var total := 0
		for tid in isl.towns:
			total += sim.map.towns[tid].population
		isl.population = total


func _check_island_radio_towers() -> void:
	for isl in sim.map.islands:
		if isl.is_mainland or not isl.inhabited or isl.radio_tower_built or island_builds.has(isl.id):
			continue
		if isl.population < RADIO_TOWER_ISLAND_POP:
			continue
		isl.radio_tower_built = true
		for tid in isl.towns:
			var st: TownState = states.get(tid)
			if st != null:
				_apply_radio_tower_bonuses(st)
		if isl.radio_tower_lot != null and not isl.radio_tower_lot.occupied:
			isl.radio_tower_lot.occupied = true
			var job := BuildJob.new()
			job.id = _next_job_id
			_next_job_id += 1
			job.island_id = isl.id
			job.town_id = isl.towns[0] if not isl.towns.is_empty() else -1
			job.lot = isl.radio_tower_lot
			job.kind = MapData.TownLot.Kind.RADIO_TOWER
			job.milestone_id = "radio_tower_6000"
			job.landmark_model = "radio_tower"
			job.duration = LANDMARK_BUILD_MINUTES
			island_builds[isl.id] = job
			construction_started.emit(job)
		island_radio_tower_unlocked.emit(isl)


func _advance_town_builds(town: MapData.Town, st: TownState, dmin: float) -> void:
	for i in range(st.active_builds.size() - 1, -1, -1):
		var job := st.active_builds[i]
		job.elapsed += dmin
		if job.elapsed >= job.duration:
			st.active_builds.remove_at(i)
			if job.kind == MapData.TownLot.Kind.HOUSE:
				st.built_houses += 1
			elif job.kind == MapData.TownLot.Kind.COMMERCIAL:
				st.built_commercial += 1
			construction_completed.emit(job)


func _advance_island_builds(dmin: float) -> void:
	for isl_id in island_builds.keys():
		var job: BuildJob = island_builds[isl_id]
		job.elapsed += dmin
		if job.elapsed >= job.duration:
			island_builds.erase(isl_id)
			construction_completed.emit(job)


func _queue_needed_builds(town: MapData.Town, st: TownState) -> void:
	while st.active_builds.size() < MAX_CONCURRENT_BUILDS:
		# 1. Priority: milestone landmarks.
		if not st.pending_milestones.is_empty():
			var lot := _claim_lot(town, MapData.TownLot.Kind.LANDMARK)
			if lot == null:
				lot = _claim_lot(town, MapData.TownLot.Kind.COMMERCIAL)
			if lot == null:
				break  # (keep it pending until a lot frees up)
			var def: Dictionary = st.pending_milestones.pop_front()
			_start_build(town, st, lot, MapData.TownLot.Kind.LANDMARK, LANDMARK_BUILD_MINUTES,
				str(def["id"]), str(def["model"]))
			continue

		# 2. Commercial buildings: 1 per 333 people.
		var pending_comm := _count_active(st, MapData.TownLot.Kind.COMMERCIAL)
		if st.built_commercial + pending_comm < target_commercial_for(town.population):
			var lot := _claim_lot(town, MapData.TownLot.Kind.COMMERCIAL)
			if lot != null:
				_start_build(town, st, lot, MapData.TownLot.Kind.COMMERCIAL, COMMERCIAL_BUILD_MINUTES)
				continue

		# 3. Houses: 1 per 100 people.
		var pending_houses := _count_active(st, MapData.TownLot.Kind.HOUSE)
		if st.built_houses + pending_houses < target_houses_for(town.population):
			var lot := _claim_lot(town, MapData.TownLot.Kind.HOUSE)
			if lot != null:
				_start_build(town, st, lot, MapData.TownLot.Kind.HOUSE, HOUSE_BUILD_MINUTES)
				continue
		break


func _count_active(st: TownState, kind: int) -> int:
	var n := 0
	for job in st.active_builds:
		if job.kind == kind:
			n += 1
	return n


func _claim_lot(town: MapData.Town, kind: int) -> MapData.TownLot:
	for lot in town.growth_lots:
		if not lot.occupied and lot.kind == kind:
			lot.occupied = true
			return lot
	return null


func _start_build(town: MapData.Town, st: TownState, lot: MapData.TownLot, kind: int,
		duration: float, milestone_id := "", landmark_model := "") -> void:
	var job := BuildJob.new()
	job.id = _next_job_id
	_next_job_id += 1
	job.town_id = town.id
	job.island_id = town.island
	job.lot = lot
	job.kind = kind
	job.milestone_id = milestone_id
	job.landmark_model = landmark_model
	job.duration = duration
	st.active_builds.append(job)
	construction_started.emit(job)


## Next upcoming population milestone for HUD display (or empty Dictionary if all unlocked).
func next_milestone_for(town: MapData.Town) -> Dictionary:
	var st := state_for_town(town)
	if st == null:
		return {}
	var best := {}
	for def in _town_milestone_defs(town.community_type):
		var mid := str(def["id"])
		if mid in st.milestones:
			continue
		if mid == "observatory_4000" and observatory_claimed_town >= 0:
			continue
		if best.is_empty() or int(def["pop"]) < int(best["pop"]):
			best = def
	return best
