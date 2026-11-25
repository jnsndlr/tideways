class_name SaveGame
## A quick save replays an authored scenario at its saved date and time.

const PATH := "user://quicksave.json"
static var _path := PATH


static func save(
	scenario_path: String, unlimited: bool, day: int, minutes: float, company := ""
) -> bool:
	var data := {
		"scenario": scenario_path,
		"company": company,
		"unlimited": unlimited,
		"day": day,
		"minutes": minutes,
		"saved_at": Time.get_datetime_string_from_system(false, true)
	}
	return _valid(data) and SavedText.replace(_path, JSON.stringify(data)) == OK


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
	return (
		path is String
		and path.get_base_dir() == "res://maps"
		and path.get_extension() == "json"
		and FileAccess.file_exists(path)
		and data.get("unlimited") is bool
		and data.get("company", "") is String
		and (day is int or day is float)
		and day >= 1
		and day == floor(day)
		and (minutes is int or minutes is float)
		and minutes >= 0.0
		and minutes < 1440.0
	)
