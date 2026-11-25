class_name FerryOperatingCosts
extends RefCounted
## Fuel and crew rates shared by metering, timetable forecasts and fleet quotes.

const SETTING := "tideways/economy/operating_costs"
const METRES_PER_NM := 1852.0

var _fuel_per_gallon: float
var _wage_per_crew_hour: float


func _init(settings: Variant = {}) -> void:
	_fuel_per_gallon = EconomyConfig.nonnegative_rate(settings, "fuel_per_gallon", 3.6)
	_wage_per_crew_hour = EconomyConfig.nonnegative_rate(settings, "wage_per_crew_hour", 12.0)


## Gallons per nautical mile rise with the square of speed through the water.
static func burn_at(fc: FerryClass, speed: float) -> float:
	var fraction := speed / fc.cruise
	return fc.burn * fraction * fraction


func fuel_cost(fc: FerryClass, metres: float, speed: float) -> float:
	return _fuel_per_gallon * metres / METRES_PER_NM * burn_at(fc, speed)


## Captain forecasts integrate speed squared over distance as the vessel accelerates.
func forecast_fuel(fc: FerryClass, integrated_speed_squared: float) -> float:
	return _fuel_per_gallon * fc.burn * integrated_speed_squared / (fc.cruise * fc.cruise * METRES_PER_NM)


func crew_per_hour(fc: FerryClass) -> float:
	return fc.crew * _wage_per_crew_hour
