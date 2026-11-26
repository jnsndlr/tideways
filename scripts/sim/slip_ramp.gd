class_name SlipRamp
extends Node3D
## One working slip's transfer span and apron, in the terminal's local frame.
## The ferry lowers the span as it approaches, then lands the apron for vehicles.
## Before departure the apron folds up and the span lifts clear.

signal pose_changed(span_fraction: float, apron_fraction: float)

# Dimensions, as art/slip_mid.py has them.
const SPAN_L := 26.5
const APRON_L := 7.0
const APRON_T := 0.12                   # the plate's thickness past its deep heel
const APRON_HEEL := 1.0
const LAND := 0.35                      # height of the lowered span tip above the car deck
# Seconds to lower (or raise) the span, and the apron.
const SPAN_TIME := 5.0
const APRON_TIME := 3.0
# The apron lying on the deck, toe down: how far it slopes below the horizontal, and where
# along the slip (u) the span's tip and the apron's toe come.
static var LAND_DIP := asin((LAND - APRON_T - 0.01) / APRON_L)
static var TIP_U := Layout.RAMP_HINGE_U + sqrt(SPAN_L * SPAN_L - LAND * LAND)
static var TOE_U := TIP_U + APRON_L * cos(LAND_DIP)

var span_fraction := 1.0     # 0 down at the deck .. 1 raised
var apron_fraction := 1.0    # 0 lying on the deck .. 1 folded up
var _span_down := false
var _apron_down := false


## Where along the slip (u) a ferry's end lies docked, `gap` short of where the apron's toe
## should land on her deck (her apron line), but never in under the span or the apron's heel.
static func dock_end(gap: float) -> float:
	return maxf(TOE_U - gap, TIP_U + APRON_HEEL)


## The height above the lot of the span and apron's top, lying on a ferry, at `u` along the
## slip (0 off the end of the apron), for the cars crossing it.
static func lift_at(u: float) -> float:
	if u <= Layout.RAMP_HINGE_U or u >= TOE_U:
		return 0.0
	if u <= TIP_U:
		return LAND * (u - Layout.RAMP_HINGE_U) / (TIP_U - Layout.RAMP_HINGE_U)
	return lerpf(LAND, APRON_T + 0.01, (u - TIP_U) / (TOE_U - TIP_U))


## The crossing between the lot and the span's tip at lateral offset `dv`, shore end first
## (terminal frame).
func crossing(dv: float) -> PackedVector3Array:
	return PackedVector3Array([Vector3(position.x + dv, Layout.LOT_Y, Layout.RAMP_HINGE_U),
		Vector3(position.x + dv, Layout.LOT_Y + LAND, TIP_U)])


func _init(v: float) -> void:
	name = "SlipRamp"
	position.x = v


## A ferry is coming in: lower the span to the deck.
func lower() -> void:
	_span_down = true


## The ferry is in: lower the span (if it isn't already) and let the apron down onto her.
func land() -> void:
	_span_down = true
	_apron_down = true


## The ferry is about to leave: the apron comes up, then the span lifts clear.
func lift() -> void:
	_span_down = false
	_apron_down = false


## Continue an already-started lift from its saved pose.
func resume_lift(span: float, apron: float) -> void:
	lift()
	_resume_pose(span, apron)


func resume_landing(span: float, apron: float) -> void:
	land()
	_resume_pose(span, apron)


func _resume_pose(span: float, apron: float) -> void:
	span_fraction = span
	apron_fraction = apron
	pose_changed.emit(span_fraction, apron_fraction)


## Down and lying on the ferry's deck, as it is for a boat already in at the start.
func snap_down() -> void:
	land()
	span_fraction = 0.0
	apron_fraction = 0.0
	pose_changed.emit(span_fraction, apron_fraction)


## Cars may cross.
func is_down() -> bool:
	return span_fraction <= 0.0 and apron_fraction <= 0.0


## The apron is folded up clear of the ferry's deck: she may leave.
func is_clear() -> bool:
	return apron_fraction >= 1.0


func _process(delta: float) -> void:
	var was := Vector2(span_fraction, apron_fraction)
	# The apron only comes down onto a span already at the deck, and the span only
	# lifts with the apron folded up.
	if _apron_down and span_fraction <= 0.0:
		apron_fraction = maxf(apron_fraction - delta / APRON_TIME, 0.0)
	else:
		apron_fraction = minf(apron_fraction + delta / APRON_TIME, 1.0)
	if _span_down:
		span_fraction = maxf(span_fraction - delta / SPAN_TIME, 0.0)
	elif apron_fraction >= 1.0:
		span_fraction = minf(span_fraction + delta / SPAN_TIME, 1.0)
	if Vector2(span_fraction, apron_fraction) != was:
		pose_changed.emit(span_fraction, apron_fraction)
