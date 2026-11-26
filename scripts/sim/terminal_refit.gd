class_name TerminalRefit
extends RefCounted
## One crane job at a terminal, from waiting for clearance until the crew leaves.

signal stage_changed
signal widen_slip(index: int)
signal open_new_slip(index: int)

enum Stage { NONE, CLEARING, ARRIVING, WORKING, LEAVING }

const ARRIVAL := 20.0
const WORK := 150.0
const DEPARTURE := 20.0

var stage := Stage.NONE
var slip := -1
var remaining := 0.0
var work := WORK
var new_slip := false


func start(index: int, working_minutes: float, building: bool) -> void:
	slip = index
	work = working_minutes
	new_slip = building
	remaining = ARRIVAL + work + DEPARTURE
	_set_stage(Stage.CLEARING)


func advance(delta: float, slip_clear: bool) -> void:
	if stage == Stage.NONE:
		return
	if stage == Stage.CLEARING:
		if slip_clear:
			_set_stage(Stage.ARRIVING)
		return
	remaining = maxf(0.0, remaining - delta)
	if remaining <= DEPARTURE and stage != Stage.LEAVING:
		if not new_slip:
			widen_slip.emit(slip)
		_set_stage(Stage.LEAVING)
		if new_slip:
			open_new_slip.emit(slip)
	elif remaining <= work + DEPARTURE and stage == Stage.ARRIVING:
		_set_stage(Stage.WORKING)
	# One update can cross both completion boundaries. Apply the work before releasing the crane.
	if remaining == 0.0:
		slip = -1
		new_slip = false
		_set_stage(Stage.NONE)


## The widening payment and any enlargement at LEAVING already belong to the save.
func resume_widening(index: int, saved_stage: Stage, saved_remaining: float) -> void:
	slip = index
	work = WORK
	new_slip = false
	remaining = saved_remaining
	_set_stage(saved_stage)


func occupies(index: int) -> bool:
	return stage != Stage.NONE and index == slip


func slip_shut(index: int) -> bool:
	return occupies(index) and not (new_slip and stage == Stage.LEAVING)


func progress() -> float:
	match stage:
		Stage.ARRIVING:
			return clampf((ARRIVAL + work + DEPARTURE - remaining) / ARRIVAL, 0.0, 1.0)
		Stage.WORKING:
			return clampf((work + DEPARTURE - remaining) / work, 0.0, 1.0)
		Stage.LEAVING:
			return clampf(1.0 - remaining / DEPARTURE, 0.0, 1.0)
	return 0.0


func _set_stage(next: Stage) -> void:
	stage = next
	stage_changed.emit()
