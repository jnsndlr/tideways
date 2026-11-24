class_name Daylight
extends RefCounted

const SUNRISE := 5.5
const SUNSET := 20.5


static func is_night(hour: float) -> bool:
	return hour < SUNRISE or hour > SUNSET
