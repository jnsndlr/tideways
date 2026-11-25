class_name TerminalInspectorRows
extends RefCounted
## Rows for the selected terminal or dock site. Structure changes are coalesced until
## the next HUD refresh. Queue and clock changes can then update individual cells.

signal layout_changed(rows: Array)
signal value_changed(index: int, text: String)

var isl: MapData.Town
var island: MapData.Island
var term: Terminal
var sim: Simulation
var wildlife: Wildlife
var _can_buy_docks: bool
var _layout_dirty := true
var _queue_dirty := true
var _slips_dirty := true
var _clock := -INF
var _indices: Dictionary[String, int] = {}
var _rows: Array
var _displayed_queue: Terminal.QueueSummary
var _lane_text := ""
# Last inputs at display precision, for rows that change independently of the layout.
var _shown: Dictionary[String, Variant] = {}
var _last_species := ""


func _init(town: MapData.Town, terminal: Terminal, simulation: Simulation, animals: Wildlife, can_buy_docks: bool) -> void:
	isl = town
	term = terminal
	sim = simulation
	wildlife = animals
	island = sim.map.island_of(isl)
	_can_buy_docks = can_buy_docks
	sim.town_growth.metrics_refreshed.connect(_invalidate_layout)
	sim.town_growth.population_changed.connect(_population_changed)
	sim.town_growth.construction_started.connect(_construction_changed)
	sim.town_growth.construction_completed.connect(_construction_changed)
	sim.routes_changed.connect(_invalidate_layout)
	sim.dock_bought.connect(_dock_bought)
	if term:
		term.queue_changed.connect(_invalidate_queue)
		term.extension_changed.connect(_invalidate_layout)
		term.refit_changed.connect(_invalidate_layout)
		sim.berths_changed.connect(_invalidate_slips)
		sim.ferry_removed.connect(_fleet_changed)
		sim.ferry_added.connect(_fleet_changed)


func _population_changed(town: MapData.Town, _new_pop: int) -> void:
	if town == isl:
		_invalidate_layout()


func _construction_changed(job: TownGrowth.BuildJob) -> void:
	if job.town_id == isl.id:
		_invalidate_layout()


func _dock_bought(town: MapData.Town) -> void:
	if town == isl:
		_invalidate_layout()


func _invalidate_layout() -> void:
	_layout_dirty = true


func _invalidate_queue() -> void:
	_queue_dirty = true


func _invalidate_slips() -> void:
	_slips_dirty = true


func _fleet_changed(_ferry: Ferry) -> void:
	_invalidate_slips()


func refresh() -> void:
	var now := sim.abs_minutes()
	if _layout_dirty:
		_rows = _build_rows()
		_indices.clear()
		_shown.clear()
		for i in _rows.size():
			_indices[_rows[i][0]] = i
		_queue_dirty = true
		_slips_dirty = true
	if _slips_dirty and term:
		_update("Slips", _slips_text(isl))
	if _queue_dirty and term:
		var queue := term.queue_summary()
		if _changed("Vehicles waiting", queue.waiting):
			_update("Vehicles waiting", str(queue.waiting))
		_update("Lanes", _lanes_text(term))
		if _indices.has("In newest lane"):
			if _changed("Newest waiting", queue.newest_waiting) or _shown.get("Newest inbound") != queue.newest_inbound:
				_shown["Newest inbound"] = queue.newest_inbound
				_update("In newest lane", "%d waiting · %d spaces inbound" % [queue.newest_waiting, queue.newest_inbound])
	if _clock != now or _queue_dirty or _layout_dirty:
		_refresh_live()
	_clock = now
	_queue_dirty = false
	_slips_dirty = false
	_refresh_wildlife()
	_refresh_countdowns()
	if _indices.has("Available cash") and _changed("Available cash", sim.available_cash):
		_update("Available cash", Hud.fmt_money(sim.available_cash))
	if _layout_dirty:
		_layout_dirty = false
		layout_changed.emit(_rows)


func _refresh_countdowns() -> void:
	if _indices.has("Opens in"):
		var minutes := ceili(sim.dock_building(isl))
		if _changed("Opens in", minutes):
			_update("Opens in", Hud.hours_text(minutes))
	if _indices.has("Slip opens in"):
		var minutes := ceili(term.refit_remaining - Terminal.REFIT_DEPARTURE)
		if _changed("Slip opens in", minutes):
			_update("Slip opens in", Hud.hours_text(minutes))
	if _indices.has("Slip reopens in"):
		var minutes := ceili(term.refit_remaining)
		if _changed("Slip reopens in", minutes):
			_update("Slip reopens in", "%d game min" % minutes)
	if _indices.has("Lane opens in"):
		var minutes := ceili(term.build_remaining)
		if _changed("Lane opens in", minutes):
			_update("Lane opens in", "%d game min" % minutes)


func _refresh_live() -> void:
	var sat := term.satisfaction() if term else 70.0
	var percent := roundi(sat)
	if _changed("Satisfaction", percent):
		_update("Satisfaction", "%d%%" % percent)
	var growth := island.growth + (sat - 70.0) * 0.05
	if not sim.town_growth.state_for_town(isl) and _changed("Growth", _tenth_key(growth)):
		_update("Growth", "%+.1f%% / yr" % growth)
	if term:
		var demand := sim.demand_label(isl)
		if _changed("Demand", demand):
			_update("Demand", demand)
		if _changed("Cars carried", term.served_today) or _shown.get("Walk-ons carried") != term.passengers_served_today:
			_shown["Walk-ons carried"] = term.passengers_served_today
			_update("Carried today", "%s cars · %s walk-ons" % [Hud.fmt_int(term.served_today), Hud.fmt_int(term.passengers_served_today)])
		var waiting := term.passengers_queued()
		if _changed("Walk-ons waiting", waiting):
			_update("Walk-ons waiting", str(waiting))
		if _indices.has("Avg. wait") and _changed("Avg. wait", roundi(term.avg_wait)):
			_update("Avg. wait", "%d min" % roundi(term.avg_wait))


func _refresh_wildlife() -> void:
	var rep := wildlife.standing(island)
	var draw := -1.0 if rep == null or rep.value < 0.05 else _tenth_key(rep.value)
	var species := rep.last_species if draw >= 0.0 else ""
	if _changed("Wildlife draw", draw) or species != _last_species:
		_last_species = species
		_update("Wildlife draw", Hud.wildlife_draw_text(wildlife, island))
	var appeal := wildlife.appeal(island)
	if _changed("Wildlife appeal", appeal):
		_update("Wildlife appeal", _appeal_text(appeal))


## Keep exact half-tenths distinct so the formatter decides ties; retain the sign of a displayed zero.
static func _tenth_key(value: float) -> float:
	var magnitude := absf(value) * 10.0
	var rounded := roundf(magnitude)
	if absf(magnitude - rounded) == 0.5:
		rounded = magnitude
	return -(rounded + 1.0) if value < 0.0 else rounded + 1.0


func _changed(key: String, value: Variant) -> bool:
	if _shown.get(key) == value:
		return false
	_shown[key] = value
	return true


func _update(key: String, text: String) -> void:
	var index := _indices[key]
	if _rows[index][1] != text:
		_rows[index][1] = text
		if not _layout_dirty:
			value_changed.emit(index, text)


func _build_rows() -> Array:
	var building := sim.dock_building(isl)
	var tg: TownGrowth.TownState = sim.town_growth.state_for_town(isl)
	var rows := []
	if isl.name != island.name:
		rows.append(["Island", island.name])
	rows.append(["Community", TownGrowth.community_label(isl.community_type)])
	if tg != null:
		rows.append(["Population", "%s (+%d / day)" % [Hud.fmt_int(isl.population), roundi(tg.total_daily)]])
		rows.append(["Growth", "Organic +%d · Ferry +%d" % [roundi(tg.organic_daily), roundi(tg.ferry_daily)]])
		if tg.has_service:
			rows.append(["Accessibility", "%d%% · %d/%d links" % [roundi(tg.accessibility * 100.0), tg.active_connections, tg.expected_connections]])
			rows.append(["Service", "Freq %d%% · Fair %d%% · Rel %d%% (%dd)" % [
				roundi(tg.frequency_score * 100.0), roundi(tg.affordability_score * 100.0),
				roundi(tg.reliability_score * 100.0), int(tg.stable_days)]])
		else:
			rows.append(["Accessibility", "0%% · 0/%d links expected" % tg.expected_connections])
		rows.append(["Attractiveness", "Res %d · Ind %d · Tour %d" % [
			roundi(tg.attractiveness_residents), roundi(tg.attractiveness_industry), roundi(tg.attractiveness_tourism)]])
		rows.append(["Economy", "%d · %d%% commercial" % [
			roundi(tg.economic_activity), roundi(sim.town_growth.commercial_truck_share(isl) * 100.0)]])
		var bldg := "%d houses · %d shops" % [tg.built_houses, tg.built_commercial]
		if not tg.active_builds.is_empty():
			bldg += " · %d building" % tg.active_builds.size()
		rows.append(["Town buildings", bldg])
		var next_ms := sim.town_growth.next_milestone_for(isl)
		if not next_ms.is_empty():
			rows.append(["Next milestone", "%s (%s pop)" % [str(next_ms["title"]), Hud.fmt_int(int(next_ms["pop"]))]])
		rows.append_array([["Satisfaction", ""], ["Demand", "-"]])
	else:
		rows.append_array([
			["Population", Hud.fmt_int(isl.population)],
			["Satisfaction", ""],
			["Growth", ""],
			["Demand", sim.demand_label(isl) if term else "-"],
		])
	rows.append(["Wildlife draw", ""])
	rows.append(["Wildlife appeal", ""])
	if not term and _can_buy_docks:
		if not isl.has_dock:
			rows.append(["Dock site", "None: no terminal can be built here"])
		elif building >= 0.0:
			rows.append(["Opens in", ""])
		elif sim.dock_price(isl) <= 0:
			rows.append(["Dock site", "No navigable ferry route reaches this site"])
		else:
			var price := sim.dock_price(isl)
			var tier: Dictionary = MapLayout.DOCK_TIERS[island.dock_sites[isl.site].tier]
			rows.append(["Dock site", "%s · %s" % [tier["name"], Hud.fmt_money(price)]])
			rows.append(["Build time", Hud.hours_text(Simulation.DOCK_BUILD_MINUTES)])
			rows.append(["Available cash", ""])
	if term:
		var queue := term.queue_summary()
		rows.append(["Vehicles waiting", ""])
		rows.append(["Walk-ons waiting", ""])
		rows.append(["Holding capacity", "%d car spaces" % term.capacity()])
		rows.append(["Slips", ""])
		if term.refit_stage != Terminal.RefitStage.NONE:
			var stage: String = {
				Terminal.RefitStage.CLEARING: "Slip closed · waiting for it to clear",
				Terminal.RefitStage.ARRIVING: "Crane scow coming in",
				Terminal.RefitStage.WORKING: "Driving piles for the new slip" if term.refit_new else "Driving new dolphins and wing walls",
				Terminal.RefitStage.LEAVING: "Crane scow leaving",
			}[term.refit_stage]
			rows.append(["New slip" if term.refit_new else "Slip refit", stage])
			if term.refit_stage != Terminal.RefitStage.CLEARING:
				rows.append(["Slip opens in" if term.refit_new else "Slip reopens in", ""])
		rows.append(["Lanes", ""])
		if isl.lane_extension_price > 0 and term.has_service():
			var destination := sim.map.towns[term.lane_keys()[0]].name
			rows.append(["Extra lane to", destination])
			var lane_work := term.build_remaining > 0.0 or term.work_stage == Terminal.WorkStage.DRAINING
			if queue.has_newest and not lane_work:
				rows.append(["In newest lane", ""])
			if lane_work:
				var count := term.staging_lanes.size()
				var phase: String = {
					Terminal.WorkStage.DRAINING: "Clearing the lanes",
					Terminal.WorkStage.ARRIVING: "Crew arriving",
					Terminal.WorkStage.PAVING: "Paving the lane",
					Terminal.WorkStage.LEAVING: "Crew leaving",
				}[term.work_stage]
				rows.append(["Construction", phase])
				if count > 0:
					rows.append(["Staging closure", _staging_loss(count, term.slots_per_lane)])
				if term.work_stage != Terminal.WorkStage.DRAINING:
					rows.append(["Lane opens in", ""])
			elif not term.site_lanes.is_empty():
				rows.append(["Unpaved lot", "room for %d more lane%s" % [term.site_lanes.size(), "" if term.site_lanes.size() == 1 else "s"]])
			elif not queue.has_newest and term.can_stage_construction():
				rows.append(["While building", _staging_loss(isl.construction_staging_lanes, term.slots_per_lane) + " closed"])
		if term.has_service():
			rows.append(["Avg. wait", ""])
		rows.append(["Carried today", ""])
	return rows


func _staging_loss(count: int, slots: int) -> String:
	return "%d lane%s · %d spaces" % [count, "" if count == 1 else "s", count * slots]


func _appeal_text(a: float) -> String:
	if a >= 2.0:
		return "Hotspot"
	if a >= 0.7:
		return "Fair"
	return "Rare"


## "2 small · 1 idle" style summary of a terminal's slips.
func _slips_text(isl: MapData.Town) -> String:
	var parts: PackedStringArray = []
	for i in isl.slips.size():
		var slip := isl.slips[i]
		if slip.building:
			parts.append("%s: being built" % ("Tie-up" if slip.tie_up else "New slip"))
			continue
		if slip.tie_up:
			var boat := "free"
			for f: Ferry in sim.ferries:
				if f.berth != Ferry.Berth.WORKING and f.here().town == isl and f.tie_up == i:
					boat = f.ferry_name
			parts.append("Tie-up (%s): %s" % [slip.size_name(), boat])
			continue
		var names: PackedStringArray = []
		for rid in slip.routes:
			var r: MapData.Route = sim.map.routes[rid]
			if not r.in_service:
				continue
			names.append(sim.map.towns[r.b if r.a == isl.id else r.a].name.trim_suffix(" Island"))
		parts.append("%s: %s" % [slip.size_name().capitalize(), ", ".join(names) if not names.is_empty() else "idle"])
	return " · ".join(parts)


## "Port Rosario 2 (1 sharing) · Gullrock 1" style summary of a terminal's lanes.
func _lanes_text(term: Terminal) -> String:
	var summary := term.queue_summary()
	if summary != _displayed_queue:
		var parts: PackedStringArray = []
		for dest in summary.destinations:
			var name: String = sim.map.towns[dest.town_id].name.trim_suffix(" Island")
			parts.append("%s %d%s" % [name, dest.lanes, " (%d sharing)" % dest.sharing if dest.sharing > 0 else ""])
		_lane_text = " · ".join(parts) if not parts.is_empty() else "-"
		_displayed_queue = summary
	return _lane_text
