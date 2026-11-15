class_name FerryDeck
extends RefCounted
## Slot reservations for one crossing. A booking occupies consecutive rows in one lane.

var layout: FerryClass
var occupants := PackedInt64Array() # Vehicle instance IDs; zero marks an empty slot.


func _init(ferry_class: FerryClass) -> void:
	layout = ferry_class
	occupants.resize(layout.lanes * layout.rows)


func clear() -> void:
	occupants.fill(0)


func reserve(slot: int, length_in_slots: int, from_a: bool, vehicle_id: int) -> void:
	var step := layout.lanes if from_a else -layout.lanes
	for k in length_in_slots:
		occupants[slot + k * step] = vehicle_id


func find_space(length_in_slots: int, tall: bool, from_a: bool) -> int:
	var fallback := -1
	for offset in layout.rows - length_in_slots + 1:
		var row := offset if from_a else layout.rows - 1 - offset
		for lane in layout.lanes:
			var slot := row * layout.lanes + lane
			if not _fits(slot, length_in_slots, from_a):
				continue
			if layout.lane_suits(lane, tall):
				return slot
			if fallback < 0:
				fallback = slot
	return fallback


func _fits(slot: int, length_in_slots: int, from_a: bool) -> bool:
	var step := layout.lanes if from_a else -layout.lanes
	for k in length_in_slots:
		var cell := slot + k * step
		if occupants[cell] != 0 or layout.blocked.has(cell):
			return false
	return true
