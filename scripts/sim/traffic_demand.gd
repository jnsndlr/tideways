class_name TrafficDemand
extends RefCounted
## Arrival intensity shared by terminal queues and the island inspector.

static func factor(hour: float) -> float:
	var f := 0.18 + 1.25 * exp(-pow((hour - 7.4) / 1.1, 2.0)) + 1.0 * exp(-pow((hour - 17.3) / 1.3, 2.0)) \
		+ 0.45 * exp(-pow((hour - 12.5) / 2.5, 2.0))
	if hour < 5.0 or hour > 22.5:
		f *= 0.3
	return f


static func arrivals_per_minute(population: int, hour: float) -> float:
	return population / 5200.0 * factor(hour)


static func label(rate: float) -> String:
	if rate > 0.9:
		return "Very High"
	if rate > 0.5:
		return "High"
	if rate > 0.2:
		return "Medium"
	return "Low"
