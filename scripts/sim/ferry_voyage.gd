class_name FerryVoyage
extends RefCounted
## Crossing state and speed rules, independent of hull meshes and scene nodes.
## The vessel supplies its current speed and traffic limits; it remains the shared
## owner of speed for MarineTraffic. Reservations and dock/vehicle effects stay there.

enum State { UNLOADING, LOADING, SAILING }

const ACCEL := 4.2
const DECEL := 1.5
const YIELD_DECEL := 2.7
const APPROACH_SPEED := 9.6
# Distance from the bow reaching the outer dolphins to being docked.
const DOCKING_ZONE := Layout.DOLPHIN_OUTER.x - Layout.PIER_END - 1.2

var state := State.LOADING
var at_a := true
var traveled := 0.0
var trips := 0
var state_time := 0.0


func depart() -> void:
	state = State.SAILING
	traveled = 0.0
	state_time = 0.0


## Called after the vessel has secured its destination corridors. Keep traveled
## at the end of the completed crossing until the next departure, as before.
func arrive() -> void:
	at_a = not at_a
	trips += 1
	state = State.UNLOADING
	state_time = 0.0


func sailing_speed(delta: float, run_length: float, current_speed: float,
		cruise: float, traffic_limit: float, corridor_wait: float) -> float:
	var rem := maxf(run_length - traveled, 0.0)
	var brake_v: float
	if rem > DOCKING_ZONE:
		brake_v = APPROACH_SPEED + sqrt(2.0 * DECEL * (rem - DOCKING_ZONE))
	else:
		brake_v = 0.9 + (APPROACH_SPEED - 0.9) * sqrt(rem / DOCKING_ZONE)
	# Picks up from wherever it is (it may have stopped for traffic mid-crossing).
	var target := minf(cruise, minf(brake_v, traffic_limit))
	target = minf(target, sqrt(2.0 * YIELD_DECEL * maxf(corridor_wait - 1.5, 0.0)))
	return minf(target, current_speed + ACCEL * delta)


func advance(delta: float, speed: float, run_length: float) -> void:
	traveled = minf(traveled + speed * delta, run_length)


func has_arrived(run_length: float) -> bool:
	return traveled >= run_length - 0.03
