class_name FerryPace
extends RefCounted
## A ferry's selected pace and the service-speed multipliers used for planning.

enum { ECONOMY, SERVICE, FULL_AHEAD }
const SETTINGS := [[0.85, "Economy"], [1.0, "Service"], [1.1, "Full ahead"]]

var selected := SERVICE


func select(setting: int) -> void:
	selected = clampi(setting, ECONOMY, FULL_AHEAD)


static func label(setting: int) -> String:
	return SETTINGS[setting][1]


func cruise(service_speed: float, setting := selected) -> float:
	return service_speed * SETTINGS[setting][0]
