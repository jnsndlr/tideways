class_name FerryLayUp
extends RefCounted
## The berth, manual orders and scheduled return for one ferry.
## The ferry supplies available slips and the clearance to begin a physical shift.

signal berth_changed

enum Berth { WORKING, TO_TIE_UP, TIED_UP, TO_WORKING, DELIVERING, FREE }  # FREE: sailing on her own, off every route

## Minutes between sailings that justify freeing the working slip.
const GAP_TIE_UP := 150.0
## Minutes to spare on return, before boarding opens.
const GAP_MARGIN := 5.0

var berth := Berth.WORKING:
	set(value):
		if value != berth:
			berth = value
			berth_changed.emit()
var tie_up := -1
var lay_up_requested := false
var return_requested := false
var gap_due := -1.0  # Next scheduled sailing during a gap; negative for a manual lay-up.


func request_lay_up() -> void:
	if berth == Berth.DELIVERING:
		return
	return_requested = false
	gap_due = -1.0
	if berth == Berth.WORKING:
		lay_up_requested = true


func request_return() -> void:
	if berth == Berth.DELIVERING:
		return
	lay_up_requested = false
	if berth != Berth.WORKING:
		return_requested = true


func between_sailings() -> bool:
	return gap_due >= 0.0


func in_service() -> bool:
	return (berth == Berth.WORKING or between_sailings()) and not lay_up_requested


func can_sell() -> bool:
	return berth == Berth.TIED_UP and not between_sailings() and not return_requested


func reschedule_gap(departure: float) -> void:
	gap_due = departure
	return_requested = false


static func long_enough_gap(departure: float, now: float) -> bool:
	return departure >= 0.0 and departure - now >= GAP_TIE_UP


func check_return_time(now: float, boarding_minutes: float, shift_minutes: float) -> void:
	if between_sailings() and now >= gap_due - boarding_minutes - GAP_MARGIN - shift_minutes:
		return_requested = true


func leave_working_slip(slip: int, departure := -1.0) -> void:
	tie_up = slip
	gap_due = departure
	lay_up_requested = false
	berth = Berth.TO_TIE_UP


func leave_tie_up() -> void:
	return_requested = false
	berth = Berth.TO_WORKING


func finish_shift() -> void:
	if berth == Berth.TO_TIE_UP:
		berth = Berth.TIED_UP
	elif berth == Berth.TO_WORKING:
		berth = Berth.WORKING
		gap_due = -1.0
