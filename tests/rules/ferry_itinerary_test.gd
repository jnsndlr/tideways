extends "res://tests/rule_test_case.gd"
## Schedule edits and manual return plans use only stop IDs, routes and a clock.


func _initialize() -> void:
	var service := FerryItinerary.new()
	var outbound := MapData.Route.new()
	var inbound := MapData.Route.new()
	service.set_circuit([7, 9], [outbound, inbound])
	service.clock.replace([700, 400])
	service.advance()
	var calls: Array[int] = [7, 9, 12, 9, 7, 9]
	var legs: Array[MapData.Route] = [outbound, inbound, outbound, inbound, outbound, inbound]
	service.plan_circuit(calls, legs)
	calls[1] = 15
	check(service.service_times() == [400, 700], "An edit without times retains departures.")
	check(not service.take_pending_at(13), "An omitted terminal keeps the edit pending.")
	check(service.call == 1 and service.stops == [7, 9], "Positioning must preserve the circuit.")
	check(service.take_pending_at(9), "The planned circuit starts at a shared stop.")
	check(service.call == 5, "Use the last occurrence with the matching inbound leg.")
	check(service.legs[5] == inbound and service.pending.stops.is_empty(), "Commit stops and legs.")
	check(service.served_from(5) == [7], "The next visit to the boarding terminal ends service.")
	check(service.served_at_next_call(12) == [9, 7], "Each destination appears only once.")
	check(service.served_at_next_call(18).is_empty(), "No service to an unknown stop.")
	service.advance()
	check(service.call == 0, "A circuit wraps to its first call.")
	service.plan_circuit([9, 7, 9, 12], [inbound, outbound, inbound, outbound], [800])
	check(service.take_pending_at(9) and service.call == 0, "Fall back to first matching stop.")
	service.plan_circuit([12, 7], [inbound, outbound], [820])
	service.suspend_service()
	service.set_circuit([4, 5], [inbound, outbound])
	service.suspend_service()
	check(service.service_stops() == [12, 7], "Repeated diversions keep the pending service.")
	check(service.service_times() == [820], "The suspended timetable survives diversion.")
	service.edit_suspended([8, 10], [outbound, inbound], [730])
	check(service.stops == [4, 5], "Editing service must leave the active diversion alone.")
	check(service.suspended.times == [730], "Resume uses the revised timetable.")
	service.resume_service()
	check(service.suspended == null, "The accepted return releases the suspended plan.")
	finish()
