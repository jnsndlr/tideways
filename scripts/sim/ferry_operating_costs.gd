class_name FerryOperatingCosts
extends RefCounted
## Fuel and crew rates shared by metering, timetable forecasts and fleet quotes.

const FUEL_PRICE := 3.6  # Dollars per gallon.
const CREW_WAGE := 12.0  # Dollars per crew member per game hour.
const METRES_PER_NM := 1852.0


## Gallons per nautical mile rise with the square of speed through the water.
static func burn_at(fc: FerryClass, speed: float) -> float:
	var fraction := speed / fc.cruise
	return fc.burn * fraction * fraction


static func fuel_cost(fc: FerryClass, metres: float, speed: float) -> float:
	return FUEL_PRICE * metres / METRES_PER_NM * burn_at(fc, speed)


## Captain forecasts integrate speed squared over distance as the vessel accelerates.
static func forecast_fuel(fc: FerryClass, integrated_speed_squared: float) -> float:
	return FUEL_PRICE * fc.burn * integrated_speed_squared / (fc.cruise * fc.cruise * METRES_PER_NM)


static func crew_per_hour(fc: FerryClass) -> float:
	return fc.crew * CREW_WAGE
