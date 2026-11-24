class_name BuildFrameBudget
extends RefCounted
## Run construction in batches on the main thread. Cancellation wakes the
## suspended batch immediately so its owner can dispose of detached nodes.

const SLICE_USEC := 10000
signal _resume
var cancelled := false
var _frame: Signal
var _deadline := 0
## Changing phases preserves the time already spent in the current frame.
var slice_usec := SLICE_USEC:
	set(value):
		if _deadline > 0:
			_deadline += value - slice_usec
		slice_usec = value


func start(frame: Signal) -> void:
	cancelled = false
	_frame = frame
	if not frame.is_null():
		frame.connect(_advance)
		_deadline = Time.get_ticks_usec() + slice_usec


func can_continue() -> bool:
	if not cancelled and _deadline > 0 and Time.get_ticks_usec() >= _deadline:
		await _resume
	return not cancelled


func _advance() -> void:
	_deadline = Time.get_ticks_usec() + slice_usec
	_resume.emit()


func finish() -> void:
	if not _frame.is_null():
		_frame.disconnect(_advance)
		_frame = Signal()
	_deadline = 0


func cancel() -> void:
	if _deadline > 0:
		cancelled = true
		_resume.emit()
