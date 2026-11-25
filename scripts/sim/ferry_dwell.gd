class_name FerryDwell
extends RefCounted
## Game minutes alongside. Each company shares one timing policy across its
## live ferries, timetable projections and slip reservations.

const SETTING := "tideways/operations/dwell"

## The crew report at least half an hour before the first departure, or
## earlier when a longer boarding window needs them on the slip.
var crew_call: float:
	get: return maxf(30.0, maximum_loading)

var minimum_loading := 10.0
var maximum_loading := 24.0
var boarding_close := 8.0
var apron_lift := 2.0
var planned_car_gap := 0.8
var unload_clearance := 2.0
var minimum_dispatch_gap := 0.5
## Rough estimate for cars comparing departures before the boat begins loading.
var estimated_turnaround := 16.0


func _init(settings: Variant = {}) -> void:
	var minimum := EconomyConfig.nonnegative_rate(settings, "minimum_loading", minimum_loading)
	var maximum := EconomyConfig.nonnegative_rate(settings, "maximum_loading", maximum_loading)
	var close := EconomyConfig.nonnegative_rate(settings, "boarding_close", boarding_close)
	var lift := EconomyConfig.nonnegative_rate(settings, "apron_lift", apron_lift)
	# Keep the default window if the overrides leave no time to board or
	# would raise the apron before the last car has been admitted.
	if minimum <= maximum and close < maximum and lift <= close:
		minimum_loading = minimum
		maximum_loading = maximum
		boarding_close = close
		apron_lift = lift
	planned_car_gap = EconomyConfig.nonnegative_rate(settings, "planned_car_gap", planned_car_gap)
	unload_clearance = EconomyConfig.nonnegative_rate(settings, "unload_clearance", unload_clearance)
	minimum_dispatch_gap = EconomyConfig.nonnegative_rate(settings, "minimum_dispatch_gap", minimum_dispatch_gap)
	estimated_turnaround = EconomyConfig.nonnegative_rate(settings, "estimated_turnaround", estimated_turnaround)


func planned_unload(capacity: int) -> float:
	return Units.game_minutes(capacity * planned_car_gap + unload_clearance)


func planned_dwell(capacity: int) -> float:
	return planned_unload(capacity) + clampf(Units.game_minutes(capacity * planned_car_gap), minimum_loading, maximum_loading) + boarding_close


func boarding_open(elapsed: float, now: float, due: float, loading_since: float) -> bool:
	if due >= 0.0 and loading_since <= due - minimum_loading:
		return now >= due - maximum_loading and now < due - boarding_close
	return elapsed < maximum_loading


func ready_to_lift(elapsed: float, now: float, due: float, loading_since: float, finished: bool) -> bool:
	var loaded := elapsed >= minimum_loading and (finished or elapsed >= maximum_loading)
	if due < 0.0:
		return loaded
	return now >= due - apron_lift and (loading_since <= due - minimum_loading or loaded)
