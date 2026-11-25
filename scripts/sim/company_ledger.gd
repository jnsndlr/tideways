class_name CompanyLedger
extends RefCounted
## The company's one ledger: fares in, fuel, crew and purchases out, and the cash
## that leaves. Each day's lines roll into `yesterday` at midnight.
## Players set the base vehicle ticket and walk-on passenger ticket prices;
## vans/small trucks pay 2x and large trucks (rigs) pay 3x the vehicle price.

const STARTING_CASH := 50000.0
## Mission sandbox cash: spending never brings it down.
const UNLIMITED_CASH := 999999999.0
const INCOME := ["fares", "sales"]
const EXPENSES := ["fuel", "crew", "purchases"]

const DEFAULT_VEHICLE_FARE := FareSchedule.DEFAULT_VEHICLE_FARE
const DEFAULT_PASSENGER_FARE := FareSchedule.DEFAULT_PASSENGER_FARE
const MIN_VEHICLE_FARE := FareSchedule.MIN_VEHICLE_FARE
const MAX_VEHICLE_FARE := FareSchedule.MAX_VEHICLE_FARE
const MIN_PASSENGER_FARE := FareSchedule.MIN_PASSENGER_FARE
const MAX_PASSENGER_FARE := FareSchedule.MAX_PASSENGER_FARE

var cash := STARTING_CASH
var vehicle_fare: float:
	get:
		return _fares.vehicle_fare
var passenger_fare: float:
	get:
		return _fares.passenger_fare
var today := _blank_day()
var yesterday := _blank_day()
var revenue_total := 0.0
var cars_today := 0
var cars_yesterday := 0
## Every vehicle carried since the company started.
var cars_total := 0
var passengers_today := 0
var passengers_yesterday := 0
## Every walk-on passenger carried since the company started.
var passengers_total := 0

var revenue_today: float:
	get: return today["fares"]

var _fares := FareSchedule.new(ProjectSettings.get_setting(FareSchedule.SETTING, {}))


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


func set_vehicle_fare(price: float) -> void:
	_fares.set_vehicle_fare(price)


func set_passenger_fare(price: float) -> void:
	_fares.set_passenger_fare(price)


func vehicle_fare_for(route_id: int) -> float:
	return _fares.vehicle_fare_for(route_id)


func passenger_fare_for(route_id: int) -> float:
	return _fares.passenger_fare_for(route_id)


func set_route_vehicle_fare(route_id: int, price: float) -> void:
	_fares.set_route_vehicle_fare(route_id, price)


func set_route_passenger_fare(route_id: int, price: float) -> void:
	_fares.set_route_passenger_fare(route_id, price)


func credit_vehicle(multiplier: int, route_id := -1) -> float:
	var fare := vehicle_fare_for(route_id) * maxi(1, multiplier)
	_credit_fare(fare)
	cars_today += 1
	cars_total += 1
	return fare


func credit_passenger(route_id := -1) -> float:
	var fare := passenger_fare_for(route_id)
	_credit_fare(fare)
	passengers_today += 1
	passengers_total += 1
	return fare


func credit_flat(is_truck: bool) -> void:
	credit_vehicle(2 if is_truck else 1)


func _credit_fare(fare: float) -> void:
	today["fares"] += fare
	revenue_total += fare
	cash += fare


## Hands back a fare already taken (a traveller set down short by manual orders).
func refund_fare(fare: float) -> void:
	today["fares"] -= fare
	revenue_total -= fare
	cash -= fare


## Takes in `amount` that isn't a fare (a boat sold) under one of INCOME.
func receive(category: String, amount: float) -> void:
	today[category] += amount
	cash += amount


## Pays out `amount` under one of EXPENSES. Running costs may take cash below zero.
func spend(category: String, amount: float) -> void:
	today[category] += amount
	if cash < UNLIMITED_CASH:
		cash -= amount


func start_day() -> void:
	yesterday = today
	today = _blank_day()
	cars_yesterday = cars_today
	cars_today = 0
	passengers_yesterday = passengers_today
	passengers_today = 0
