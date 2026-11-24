class_name CaptainAssignment
extends RefCounted
## Command of one ferry and the captains credited with her two latest timed crossings.

var current: Captain
var scheduled: Captain
var last_crossing := -1.0
var last_crossing_captain: Captain
var previous_crossing := -1.0
var previous_crossing_captain: Captain
var _elapsed := -1.0  # A ferry can start a scenario already underway.


func _init(initial: Captain) -> void:
	current = initial
	scheduled = initial


func assign(captain: Captain, underway: bool) -> void:
	scheduled = captain
	if not underway:
		current = captain


func depart() -> void:
	current = scheduled
	_elapsed = 0.0


func advance(delta: float) -> void:
	if _elapsed >= 0.0:
		_elapsed += delta


func arrive() -> void:
	if _elapsed >= 0.0:
		previous_crossing = last_crossing
		previous_crossing_captain = last_crossing_captain
		last_crossing = _elapsed
		last_crossing_captain = current
		_elapsed = -1.0
