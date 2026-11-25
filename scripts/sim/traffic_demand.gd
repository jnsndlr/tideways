class_name TrafficDemand
extends RefCounted
## Arrival intensity shared by terminal queues and the island inspector.

const DEFAULT_TRUCK_SHARE := 0.12


static func factor(hour: float) -> float:
	var f := 0.18 + 1.25 * exp(-pow((hour - 7.4) / 1.1, 2.0)) + 1.0 * exp(-pow((hour - 17.3) / 1.3, 2.0)) \
		+ 0.45 * exp(-pow((hour - 12.5) / 2.5, 2.0))
	if hour < 5.0 or hour > 22.5:
		f *= 0.3
	return f


static func arrivals_per_minute(population: int, hour: float) -> float:
	return population / 5200.0 * factor(hour)


## How strongly ticket pricing affects ridership relative to the fair base price.
## Lower fares draw more riders (up to 1.5x at free); higher fares taper demand smoothly.
static func price_multiplier(price: float, base_price: float) -> float:
	if base_price <= 0.0:
		return 1.0
	var ratio := maxf(price, 0.0) / base_price
	if ratio <= 1.0:
		return 1.0 + 0.5 * (1.0 - ratio)
	return exp(-0.9 * (ratio - 1.0))


static func vehicle_arrivals_per_minute(population: int, hour: float, vehicle_fare: float) -> float:
	return (
		arrivals_per_minute(population, hour)
		* price_multiplier(vehicle_fare, CompanyLedger.DEFAULT_VEHICLE_FARE)
	)


static func passenger_arrivals_per_minute(
	population: int, hour: float, passenger_fare: float
) -> float:
	return (
		population
		/ 4200.0
		* factor(hour)
		* price_multiplier(passenger_fare, CompanyLedger.DEFAULT_PASSENGER_FARE)
	)


static func price_effect_label(price: float, base_price: float) -> String:
	var pct := roundi((price_multiplier(price, base_price) - 1.0) * 100.0)
	if pct == 0:
		return "Normal demand"
	return "%+d%% demand" % pct


static func label(rate: float) -> String:
	if rate > 0.9:
		return "Very High"
	if rate > 0.5:
		return "High"
	if rate > 0.2:
		return "Medium"
	return "Low"
