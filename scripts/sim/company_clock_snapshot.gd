class_name CompanyClockSnapshot
extends RefCounted
## Restore the calendar and the next simulation RNG draw after rebuilding the region.
## Godot RNG state is a signed 64-bit integer. Store its decimal text across JSON.
const MAX_JSON_INTEGER := 9007199254740991


static func capture(sim: Simulation) -> Dictionary:
	return {
		"version": 1,
		"day": sim.day,
		"minutes": sim.minutes,
		"seed": str(sim.rng.seed),
		"rng_state": str(sim.rng.state),
	}


static func restore(record: Variant, sim: Simulation) -> bool:
	if not record is Dictionary:
		return false
	var version: Variant = record.get("version")
	if not (version is int or version is float) or version != 1:
		return false
	if not record.get("seed") is String or record.seed != str(sim.rng.seed):
		return false
	var day: Variant = record.get("day")
	var minutes: Variant = record.get("minutes")
	var state: Variant = record.get("rng_state")
	if not (day is int or day is float) or not (minutes is int or minutes is float):
		return false
	if not is_finite(day) or floor(day) != day or day < 1 or day > MAX_JSON_INTEGER:
		return false
	if not is_finite(minutes) or minutes < 0 or minutes >= 1440:
		return false
	if not state is String or not state.is_valid_int() or str(state.to_int()) != state:
		return false
	sim.day = int(day)
	sim.minutes = minutes
	sim.rng.state = state.to_int()
	return true
