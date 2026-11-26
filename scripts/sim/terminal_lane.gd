class_name TerminalLane
extends RefCounted
## One holding lane. Runtime IDs connect waiting records to their vehicle nodes.
## Rules can also run with ordinary integer IDs, as on the ferry deck.

class WaitingVehicle:
	var vehicle_id: int
	var slots: int

	func _init(id: int, size_in_slots: int) -> void:
		vehicle_id = id
		slots = size_in_slots


var v: float
var queue: Array[WaitingVehicle] = []
var enroute := 0
## Vehicles still driving toward this lane. A transfer retains its first lot arrival.
var approaching: Dictionary[int, bool] = {}


func reserve_arrival(vehicle_id: int, slots: int, transfer: bool) -> void:
	approaching[vehicle_id] = transfer
	enroute += slots


func _init(offset: float) -> void:
	v = offset


func queued_slots() -> int:
	var count := 0
	for waiting in queue:
		count += waiting.slots
	return count


func enqueue(vehicle_id: int, slots: int) -> void:
	queue.append(WaitingVehicle.new(vehicle_id, slots))


func arrive(vehicle_id: int, slots: int) -> void:
	enroute -= slots
	enqueue(vehicle_id, slots)


func take_front() -> int:
	var waiting: WaitingVehicle = queue.pop_front()
	return waiting.vehicle_id


static func for_arrival(candidates: Array, closed: Array, capacity: int, need: int) -> TerminalLane:
	var best: TerminalLane
	var best_count := capacity - need + 1
	for lane: TerminalLane in candidates:
		if lane in closed:
			continue
		var count := lane.queued_slots() + lane.enroute
		if count < best_count:
			best_count = count
			best = lane
	return best


## Count vehicles for dispatch; use occupied slots for admitting arrivals.
## Ties keep the first eligible lane. Only the head may board.
static func for_boarding(candidates: Array, fits: Callable) -> TerminalLane:
	var best: TerminalLane
	for lane: TerminalLane in candidates:
		if not lane.queue.is_empty() and (best == null or lane.queue.size() > best.queue.size()):
			if fits.is_null() or fits.call(lane.queue[0].vehicle_id):
				best = lane
	return best
