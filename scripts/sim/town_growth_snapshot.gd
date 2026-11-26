class_name TownGrowthSnapshot
extends RefCounted
## A growing region is rebuilt from its original map. Restore its live values after
## terminal and service installation, which can otherwise refresh the growth metrics.

const FLOATS := [
	"population_exact",
	"economic_activity",
	"attractiveness_residents",
	"attractiveness_industry",
	"attractiveness_tourism",
	"attractiveness",
	"accessibility",
	"frequency_score",
	"affordability_score",
	"reliability_score",
	"connectivity_score",
	"daily_departures",
	"expected_departures",
	"stable_days",
	"schedule_churn",
	"wildlife_photo_bonus",
	"recreation_bonus",
	"organic_daily",
	"ferry_daily",
	"total_daily",
	"milestone_growth_bonus",
	"milestone_residents_bonus",
	"milestone_industry_bonus",
	"milestone_tourism_bonus",
	"milestone_economy_bonus",
]
const INTS := [
	"active_connections",
	"expected_connections",
	"wildlife_photos",
	"built_houses",
	"built_commercial"
]
const FLAGS := ["has_service", "edited_today"]


static func capture(sim: Simulation) -> Dictionary:
	var growth := sim.town_growth
	var towns := {}
	for town in sim.map.towns:
		var st := growth.state_for_town(town)
		var record := {
			"population": town.population, "milestones": st.milestones.duplicate(), "pending": []
		}
		for field in FLOATS + INTS + FLAGS:
			record[field] = st.get(field)
		for definition in st.pending_milestones:
			record.pending.append(definition.id)
		towns[town.key] = record
	var towers := {}
	for island in sim.map.islands:
		towers[island.key] = island.radio_tower_built
	var observer := ""
	if growth.observatory_claimed_town >= 0:
		observer = sim.map.towns[growth.observatory_claimed_town].key
	return {
		"towns": towns,
		"radio_towers": towers,
		"observatory": observer,
		"research": sim.research_done.duplicate(),
		"metrics_elapsed": growth._metrics_acc,
		"next_job": growth._next_job_id,
		"jobs": TownBuildSnapshot.capture(sim),
	}


## The company installer owns a disposable simulation until every record has passed.
static func restore(data: Variant, sim: Simulation) -> bool:
	if (
		not data is Dictionary
		or not data.get("towns") is Dictionary
		or not data.get("radio_towers") is Dictionary
	):
		return false
	if (
		data.towns.size() != sim.map.towns.size()
		or data.radio_towers.size() != sim.map.islands.size()
	):
		return false
	if not data.get("observatory") is String or not _string_set(data.get("research")):
		return false
	if not _number(data.get("metrics_elapsed")) or data.metrics_elapsed >= 15.0:
		return false
	if not _integer(data.get("next_job")) or data.next_job < 1:
		return false
	var growth := sim.town_growth
	growth._metrics_acc = data.metrics_elapsed
	growth._next_job_id = int(data.next_job)
	sim.research_done.assign(data.research)
	growth.observatory_claimed_town = -1
	for town in sim.map.towns:
		if not _restore_town(data.towns.get(town.key), town, growth):
			return false
		if town.key == data.observatory:
			if not "observatory_4000" in growth.state_for_town(town).milestones:
				return false
			growth.observatory_claimed_town = town.id
		elif "observatory_4000" in growth.state_for_town(town).milestones:
			return false
	if data.observatory != "" and growth.observatory_claimed_town < 0:
		return false
	for island in sim.map.islands:
		var built: Variant = data.radio_towers.get(island.key)
		if not built is bool:
			return false
		island.radio_tower_built = built
	growth._sync_island_populations()
	return TownBuildSnapshot.restore(data.get("jobs"), sim)


static func _restore_town(data: Variant, town: MapData.Town, growth: TownGrowth) -> bool:
	if not data is Dictionary or not _integer(data.get("population")):
		return false
	var st := growth.state_for_town(town)
	for field in FLOATS:
		if not _number(data.get(field)):
			return false
		st.set(field, float(data[field]))
	for field in INTS:
		if not _integer(data.get(field)):
			return false
		st.set(field, int(data[field]))
	for field in FLAGS:
		if not data.get(field) is bool:
			return false
		st.set(field, data[field])
	if not _string_set(data.get("milestones")) or not _string_set(data.get("pending")):
		return false
	var definitions := {}
	for definition in growth._town_milestone_defs(town.community_type):
		definitions[definition.id] = definition
	for id: String in data.milestones:
		if not definitions.has(id):
			return false
	st.milestones.assign(data.milestones)
	st.pending_milestones.clear()
	for id: String in data.pending:
		if id not in st.milestones:
			return false
		st.pending_milestones.append(definitions[id])
	town.population = int(data.population)
	return true


static func _string_set(value: Variant) -> bool:
	if not value is Array:
		return false
	var found := {}
	for key in value:
		if not key is String or key.strip_edges().is_empty() or found.has(key):
			return false
		found[key] = true
	return true


static func _number(value: Variant) -> bool:
	return (
		(value is float or value is int)
		and is_finite(value)
		and value >= 0
		and value <= CompanyClockSnapshot.MAX_JSON_INTEGER
	)


static func _integer(value: Variant) -> bool:
	return _number(value) and floor(value) == value
