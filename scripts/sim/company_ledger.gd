class_name CompanyLedger
extends RefCounted
## The company's one ledger: fares in, fuel, crew and purchases out, and the cash
## that leaves. Each day's lines roll into `yesterday` at midnight.
## Measured vehicles pay by length; legacy vehicles use a flat fare.

const STARTING_CASH := 50000.0
const INCOME := ["fares", "sales"]
const EXPENSES := ["fuel", "crew", "purchases"]

const FARE_CAR := 18.5
const FARE_TRUCK := 42.0   # (the code-built truck)
# Fares go by length, as WSF's do: a car's fare up to 22 ft (6.7 m), then this much
# more of it for every metre over.
const CAR_FARE_LENGTH := 6.7
const FARE_PER_METRE := 0.3

var cash := STARTING_CASH
var today := _blank_day()
var yesterday := _blank_day()
var revenue_total := 0.0
var cars_today := 0
var cars_yesterday := 0
## Every vehicle carried since the company started.
var cars_total := 0

var revenue_today: float:
	get: return today["fares"]


static func _blank_day() -> Dictionary:
	var d := {}
	for k in INCOME + EXPENSES:
		d[k] = 0.0
	return d


static func net(day: Dictionary) -> float:
	var n := 0.0
	for k in INCOME:
		n += day[k]
	for k in EXPENSES:
		n -= day[k]
	return n


func credit_measured(metres: float) -> void:
	_credit(FARE_CAR * (1.0 + FARE_PER_METRE * maxf(metres - CAR_FARE_LENGTH, 0.0)))


func credit_flat(is_truck: bool) -> void:
	_credit(FARE_TRUCK if is_truck else FARE_CAR)


func _credit(fare: float) -> void:
	today["fares"] += fare
	revenue_total += fare
	cash += fare
	cars_today += 1
	cars_total += 1


## Takes in `amount` that isn't a fare (a boat sold) under one of INCOME.
func receive(category: String, amount: float) -> void:
	today[category] += amount
	cash += amount


## Pays out `amount` under one of EXPENSES. Running costs may take cash below zero.
func spend(category: String, amount: float) -> void:
	today[category] += amount
	cash -= amount


func start_day() -> void:
	yesterday = today
	today = _blank_day()
	cars_yesterday = cars_today
	cars_today = 0
