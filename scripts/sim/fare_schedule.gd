class_name FareSchedule
extends RefCounted
## Company defaults and player-set route overrides.

const SETTING := "tideways/economy/fares"
const DEFAULT_VEHICLE_FARE := 18.0
const DEFAULT_PASSENGER_FARE := 6.0
const MIN_VEHICLE_FARE := 0.0
const MAX_VEHICLE_FARE := 60.0
const MIN_PASSENGER_FARE := 0.0
const MAX_PASSENGER_FARE := 30.0

var vehicle_fare := DEFAULT_VEHICLE_FARE
var passenger_fare := DEFAULT_PASSENGER_FARE
## Per-route ticket prices: route id -> price (falls back to company default).
var route_vehicle_fares := {}
var route_passenger_fares := {}


func _init(settings: Variant = {}) -> void:
	set_vehicle_fare(EconomyConfig.nonnegative_rate(settings, "car", DEFAULT_VEHICLE_FARE))
	set_passenger_fare(EconomyConfig.nonnegative_rate(settings, "passenger", DEFAULT_PASSENGER_FARE))


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
