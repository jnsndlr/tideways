class_name SaveGame
## The player's single slot. Unversioned files retain their original date-only replay.

const PATH := "user://quicksave.json"
const VERSION := 2
const INVALID := "Couldn’t load this company. Its save file has been kept."
static var _path := PATH


var _opening_service := {}
var _opening_slips := {}


## Current restore builds the original hulls, stops and route-to-slip assignments.
## Decline changed topology before replacing the last usable player save.
func remember_region(sim: Simulation) -> void:
	_opening_service = _fleet_service(sim)
	_opening_slips = _slip_routes(sim.map)


static func _fleet_service(sim: Simulation) -> Dictionary:
	var service := {}
	for ferry in sim.ferries:
		if not ferry.purchased:
			service[ferry.fleet_key] = [ferry.route.key, ferry.fc.size, ferry.stops.duplicate()]
	return service


static func _slip_routes(map: MapData) -> Dictionary:
	var routes := {}
	for town in map.dock_towns():
		for index in town.slips.size():
			var slip := town.slips[index]
			if not slip.routes.is_empty():
				routes[Vector2i(town.id, index)] = slip.routes.duplicate()
	return routes


func save_company(sim: Simulation, scenario: String, company: String, unlimited: bool) -> Error:
	if _fleet_service(sim) != _opening_service or _slip_routes(sim.map) != _opening_slips:
		return ERR_UNAVAILABLE
	var snapshot := CompanySnapshot.capture(sim)
	if snapshot.is_empty():
		return ERR_UNAVAILABLE
	var data := {
		"version": VERSION,
		"region": "generated" if scenario.is_empty() else "authored",
		"scenario": scenario,
		"company": company,
		"unlimited": unlimited,
		"day": sim.day,
		"minutes": sim.minutes,
		"snapshot": snapshot,
		"mission_start": sim.scenario.mission.start_day if sim.scenario.mission else -1,
		"saved_at": Time.get_datetime_string_from_system(false, true),
	}
	if not _valid(data):
		return ERR_INVALID_DATA
	return SavedText.replace(_path, JSON.stringify(data, "", true, true))


static func read() -> Dictionary:
	var file := FileAccess.open(_path, FileAccess.READ)
	if not file:
		return {}
	var json := JSON.new()
	if json.parse(file.get_as_text()) != OK or not json.data is Dictionary:
		return {}
	var data: Dictionary = json.data
	return data if _valid(data) else {}


static func _valid(data: Dictionary) -> bool:
	var path = data.get("scenario")
	var day = data.get("day")
	var minutes = data.get("minutes")
	if not (
		path is String
		and data.get("company", "") is String
		and data.get("unlimited") is bool
		and _integer(day)
		and day >= 1
		and day <= CompanyClockSnapshot.MAX_JSON_INTEGER
		and (minutes is int or minutes is float)
		and minutes >= 0
		and minutes < 1440
	):
		return false
	var authored: bool = (
		path.get_base_dir() == "res://maps"
		and path.get_extension() == "json"
		and FileAccess.file_exists(path)
	)
	if not data.has("version"):
		return authored and not data.has("region") and not data.has("snapshot")
	if data.version != VERSION or not CompanySnapshot.supports(data.get("snapshot")):
		return false
	var snapshot: Dictionary = data.snapshot
	var seed_text = snapshot.network.get("seed")
	if (
		not seed_text is String
		or not seed_text.is_valid_int()
		or str(seed_text.to_int()) != seed_text
	):
		return false
	return (
		(
			(data.get("region") == "authored" and authored)
			or (data.get("region") == "generated" and path == "" and not data.unlimited)
		)
		and snapshot.clock.get("day") == day
		and snapshot.clock.get("minutes") == minutes
		and _integer(data.get("mission_start"))
		and data.mission_start >= -1
		and data.mission_start <= day
	)


static func _integer(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(value) and floor(value) == value
