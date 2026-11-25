class_name FerryItinerary
extends RefCounted
## The circuit being sailed, its clock, and the service to take up after an edit or diversion.


class Plan:
	var stops: Array[int]
	var legs: Array[MapData.Route]
	var times: Array[int]

	func _init(
		ids: Array[int] = [], routes: Array[MapData.Route] = [], departures: Array[int] = []
	):
		stops = ids.duplicate()
		legs = routes.duplicate()
		times = departures.duplicate()


var stops: Array[int] = []
var legs: Array[MapData.Route] = []
var call := 0
var clock := Timetable.new()
var pending := Plan.new()
var suspended: Plan


func set_circuit(ids: Array[int], routes: Array[MapData.Route], at_call := 0) -> void:
	stops = ids.duplicate()
	legs = routes.duplicate()
	call = at_call


func advance() -> void:
	call = (call + 1) % stops.size()


func plan_circuit(ids: Array[int], routes: Array[MapData.Route], times = null) -> void:
	var departures: Array[int] = []
	departures.assign(clock.departures if times == null else times)
	pending = Plan.new(ids, routes, departures)


func clear_pending() -> void:
	pending = Plan.new()


## If a terminal occurs twice, continue from the same inbound leg when possible.
func take_pending_at(terminal_id: int) -> bool:
	var index := pending.stops.find(terminal_id)
	if index < 0:
		return false
	var previous := stops[call - 1]
	for i in pending.stops.size():
		if pending.stops[i] == terminal_id and pending.stops[i - 1] == previous:
			index = i
	set_circuit(pending.stops, pending.legs, index)
	clock.replace(pending.times)
	clear_pending()
	return true


func suspend_service() -> void:
	if suspended == null:
		if pending.stops.is_empty():
			suspended = Plan.new(stops, legs, clock.departures)
		else:
			suspended = pending
	clear_pending()


func edit_suspended(ids: Array[int], routes: Array[MapData.Route], times: Array[int]) -> void:
	suspended = Plan.new(ids, routes, times)


func resume_service() -> void:
	suspended = null


func service_stops() -> Array[int]:
	return suspended.stops if suspended != null else stops


func service_times() -> Array[int]:
	if suspended != null:
		return suspended.times
	return pending.times if not pending.stops.is_empty() else clock.departures


## Carry riders to each distinct destination before the circuit returns to their boarding stop.
func served_from(index: int) -> Array[int]:
	var served: Array[int] = []
	for step in range(1, stops.size()):
		var destination := stops[(index + step) % stops.size()]
		if destination == stops[index]:
			break
		if destination not in served:
			served.append(destination)
	return served


func served_at_next_call(terminal_id: int) -> Array[int]:
	for step in stops.size():
		var index := (call + step) % stops.size()
		if stops[index] == terminal_id:
			return served_from(index)
	return []
