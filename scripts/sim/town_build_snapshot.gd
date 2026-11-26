class_name TownBuildSnapshot
extends RefCounted
## Build history is bounded by the region's reserved sites. Match jobs to the
## regenerated native lot by its fixed horizontal coordinates and original kind.


static func capture(sim: Simulation) -> Array:
	var jobs := []
	var growth := sim.town_growth
	for finished in growth.completed_builds:
		jobs.append(_record(finished, sim.map, true))
	for town in sim.map.towns:
		for job in growth.state_for_town(town).active_builds:
			jobs.append(_record(job, sim.map, false))
	for island in sim.map.islands:
		if growth.island_builds.has(island.id):
			jobs.append(_record(growth.island_builds[island.id], sim.map, false))
	return jobs


static func _record(job: TownGrowth.BuildJob, map: MapData, completed: bool) -> Dictionary:
	return {
		"id": job.id,
		"town": map.towns[job.town_id].key if job.town_id >= 0 else "",
		"island": map.islands[job.island_id].key,
		"site": _site(job.lot),
		"kind": job.kind,
		"milestone": job.milestone_id,
		"duration": job.duration,
		"elapsed": minf(job.elapsed, job.duration),
		"completed": completed,
	}


static func _site(lot: MapData.TownLot) -> String:
	return "%d/%d/%d" % [lot.kind, roundi(lot.pos.x * 100), roundi(lot.pos.z * 100)]


static func restore(records: Variant, sim: Simulation) -> bool:
	if not records is Array:
		return false
	var towns := {}
	var sites := {}
	for town in sim.map.towns:
		towns[town.key] = town
		sim.town_growth.state_for_town(town).active_builds.clear()
		var pads := {}
		for lot in town.growth_lots:
			var key := _site(lot)
			if pads.has(key):
				return false
			pads[key] = lot
			lot.occupied = false
		sites[town.key] = pads
	var islands := {}
	for island in sim.map.islands:
		islands[island.key] = island
		if island.radio_tower_lot != null:
			island.radio_tower_lot.occupied = island.radio_tower_built
	var ids := {}
	var occupied := {}
	var growth := sim.town_growth
	growth.completed_builds.clear()
	growth.island_builds.clear()
	for record in records:
		var job := _read(record, towns, islands, sites, growth)
		if job == null or ids.has(job.id) or occupied.has(job.lot):
			return false
		ids[job.id] = true
		occupied[job.lot] = true
		job.lot.occupied = true
		if record.completed:
			growth.completed_builds.append(job)
		elif job.kind == MapData.TownLot.Kind.RADIO_TOWER:
			growth.island_builds[job.island_id] = job
		else:
			growth.state_of(job.town_id).active_builds.append(job)
	return true


static func _read(
	data: Variant, towns: Dictionary, islands: Dictionary, sites: Dictionary, growth: TownGrowth
) -> TownGrowth.BuildJob:
	if not data is Dictionary or not data.get("completed") is bool:
		return null
	if (
		not _integer(data.get("id"), 1, growth._next_job_id - 1)
		or not _integer(
			data.get("kind"), MapData.TownLot.Kind.HOUSE, MapData.TownLot.Kind.RADIO_TOWER
		)
	):
		return null
	if not _time(data.get("duration")) or not _time(data.get("elapsed")):
		return null
	if (
		data.duration <= 0
		or data.elapsed > data.duration
		or (data.elapsed == data.duration) != data.completed
	):
		return null
	if (
		not data.get("milestone") is String
		or not data.get("site") is String
		or not data.get("town") is String
	):
		return null
	var island: MapData.Island = islands.get(data.get("island"))
	var town: MapData.Town = towns.get(data.town)
	if (
		island == null
		or (not data.town.is_empty() and town == null)
		or (town != null and town.island != island.id)
	):
		return null
	var job := TownGrowth.BuildJob.new()
	job.id = int(data.id)
	job.island_id = island.id
	job.town_id = town.id if town != null else -1
	job.kind = int(data.kind)
	job.duration = data.duration
	job.elapsed = data.elapsed
	job.milestone_id = data.milestone
	if job.kind == MapData.TownLot.Kind.RADIO_TOWER:
		if not island.radio_tower_built or job.milestone_id != "radio_tower_6000":
			return null
		if job.town_id != (island.towns[0] if not island.towns.is_empty() else -1):
			return null
		job.lot = island.radio_tower_lot
		job.landmark_model = "radio_tower"
	else:
		if town == null:
			return null
		job.lot = sites[town.key].get(data.site)
		if job.lot == null:
			return null
		if job.kind == MapData.TownLot.Kind.LANDMARK:
			if (
				job.lot.kind not in [MapData.TownLot.Kind.LANDMARK, MapData.TownLot.Kind.COMMERCIAL]
				or job.milestone_id not in growth.state_for_town(town).milestones
			):
				return null
			for definition in growth._town_milestone_defs(town.community_type):
				if definition.id == job.milestone_id:
					job.landmark_model = definition.model
					break
		elif job.lot.kind != job.kind or not job.milestone_id.is_empty():
			return null
	if job.lot == null or _site(job.lot) != data.site:
		return null
	return job


static func _integer(n: Variant, low: int, high: int) -> bool:
	return (n is int or n is float) and n >= low and n <= high and floor(n) == n


static func _time(n: Variant) -> bool:
	return (
		(n is int or n is float)
		and is_finite(n)
		and n >= 0
		and n <= CompanyClockSnapshot.MAX_JSON_INTEGER
	)
