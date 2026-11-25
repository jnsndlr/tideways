class_name CompanyLedger
extends RefCounted
## The company's one ledger: fares in, fuel, crew and purchases out, and the cash
## that leaves. Each day's lines roll into `yesterday` at midnight.
## Players set the base vehicle ticket and walk-on passenger ticket prices;
## vans/small trucks pay 2x and large trucks (rigs) pay 3x the vehicle price.

const STARTING_CASH := 50000.0
const INCOME := ["fares", "sales"]
const EXPENSES := ["fuel", "crew", "purchases"]

const DEFAULT_VEHICLE_FARE := 18.0
const DEFAULT_PASSENGER_FARE := 6.0
const MIN_VEHICLE_FARE := 0.0
const MAX_VEHICLE_FARE := 60.0
const MIN_PASSENGER_FARE := 0.0
const MAX_PASSENGER_FARE := 30.0

var cash := STARTING_CASH
var vehicle_fare := DEFAULT_VEHICLE_FARE
var passenger_fare := DEFAULT_PASSENGER_FARE
## Per-route ticket prices: route id -> price (falls back to company default).
var route_vehicle_fares := {}
var route_passenger_fares := {}
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
	vehicle_fare = clampf(price, MIN_VEHICLE_FARE, MAX_VEHICLE_FARE)


func set_passenger_fare(price: float) -> void:
	passenger_fare = clampf(price, MIN_PASSENGER_FARE, MAX_PASSENGER_FARE)


func vehicle_fare_for(route_id: int) -> float:
	if route_id >= 0 and route_vehicle_fares.has(route_id):
		return float(route_vehicle_fares[route_id])
	return vehicle_fare


func passenger_fare_for(route_id: int) -> float:
	if route_id >= 0 and route_passenger_fares.has(route_id):
		return float(route_passenger_fares[route_id])
	return passenger_fare


func set_route_vehicle_fare(route_id: int, price: float) -> void:
	if route_id < 0:
		set_vehicle_fare(price)
		return
	route_vehicle_fares[route_id] = clampf(price, MIN_VEHICLE_FARE, MAX_VEHICLE_FARE)


func set_route_passenger_fare(route_id: int, price: float) -> void:
	if route_id < 0:
		set_passenger_fare(price)
		return
	route_passenger_fares[route_id] = clampf(price, MIN_PASSENGER_FARE, MAX_PASSENGER_FARE)


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
	cash -= amount


func start_day() -> void:
	yesterday = today
	today = _blank_day()
	cars_yesterday = cars_today
	cars_today = 0
	passengers_yesterday = passengers_today
	passengers_today = 0
