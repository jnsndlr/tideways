class_name SaveGame
## Quick save: the scenario being played and the game date and time. Loading
## replays that scenario from the start and sets the clock to the saved date.

const PATH := "user://quicksave.json"


static func exists() -> bool:
	return FileAccess.file_exists(PATH)


static func save(scenario_path: String, unlimited: bool, day: int, minutes: float) -> bool:
	var f := FileAccess.open(PATH, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(JSON.stringify({
		"scenario": scenario_path, "unlimited": unlimited, "day": day, "minutes": minutes,
		"saved_at": Time.get_datetime_string_from_system(false, true)}))
	return true


static func read() -> Dictionary:
	if not exists():
		return {}
	var data = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	return data if data is Dictionary else {}
