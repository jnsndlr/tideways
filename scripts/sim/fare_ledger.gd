class_name FareLedger
extends RefCounted
## Boarding receipts. Measured vehicles pay by length; legacy vehicles use a flat fare.

const FARE_CAR := 18.5
const FARE_TRUCK := 42.0   # (the code-built truck)
# Fares go by length, as WSF's do: a car's fare up to 22 ft (6.7 m), then this much
# more of it for every metre over.
const CAR_FARE_LENGTH := 6.7
const FARE_PER_METRE := 0.3

var revenue_today := 0.0
var revenue_total := 0.0
var cars_today := 0


func credit_measured(metres: float) -> void:
	_credit(FARE_CAR * (1.0 + FARE_PER_METRE * maxf(metres - CAR_FARE_LENGTH, 0.0)))


func credit_flat(is_truck: bool) -> void:
	_credit(FARE_TRUCK if is_truck else FARE_CAR)


func _credit(fare: float) -> void:
	revenue_today += fare
	revenue_total += fare
	cars_today += 1


func start_day() -> void:
	revenue_today = 0.0
	cars_today = 0
