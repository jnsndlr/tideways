class_name Captain
extends RefCounted
## A ferry's master. Each handles the boat differently in the two parts of a
## crossing: the open-water run at cruise, and the run-in to the slip. Which
## captain suits a route depends on how much of it is open water, so a long
## crossing favours one and a short hop the other.
##
## This owns the rule for how fast a ferry may go at each point of a crossing
## (speed_limit). Ferry sails by it and the HUD's forecast integrates the same
## function, so what the player is shown is what the boat does.

var id := ""
var name := ""
var strength := ""    # a few words for the HUD
var sea := 1.0        # times the class's cruise speed in open water
var harbour := 1.0    # times the approach speed and braking coming in to the slip

static var _roster: Array[Captain] = []


static func roster() -> Array[Captain]:
	if _roster.is_empty():
		_roster = [
			_make("halloran", "Ines Halloran", "Fast in open water, careful into the slip", 1.12, 0.9),
			_make("tran", "Bo Tran", "Quick, sure dockings, easy pace at sea", 0.92, 1.3),
		]
	return _roster


static func _make(i: String, n: String, s: String, sea_f: float, harbour_f: float) -> Captain:
	var c := Captain.new()
	c.id = i
	c.name = n
	c.strength = s
	c.sea = sea_f
	c.harbour = harbour_f
	return c


func surname() -> String:
	return name.get_slice(" ", name.get_slice_count(" ") - 1)


## Open-water speed in a ferry whose class cruises at `class_cruise`.
func cruise(class_cruise: float) -> float:
	return class_cruise * sea


## The fastest this captain takes a ferry `remaining` metres from being docked:
## cruise in open water, easing to the approach speed along the run-in, then
## braking to a stop from the outer dolphins.
func speed_limit(remaining: float, class_cruise: float) -> float:
	var approach := Ferry.APPROACH_SPEED * harbour
	var rem := maxf(remaining, 0.0)
	var brake_v: float
	if rem > Ferry.BRAKE_ZONE:
		brake_v = approach + sqrt(2.0 * Ferry.DECEL * harbour * (rem - Ferry.BRAKE_ZONE))
	else:
		brake_v = 0.9 + (approach - 0.9) * sqrt(rem / Ferry.BRAKE_ZONE)
	return minf(cruise(class_cruise), brake_v)


## Game minutes for an unhindered crossing of `run` metres dock to dock (other
## traffic can still hold a ferry up). Steps the same rule Ferry sails by.
func crossing_minutes(run: float, class_cruise: float) -> float:
	const STEP := 0.05
	var t := 0.0
	var gone := 0.0
	var v := 0.0
	while gone < run - 0.03 and t < 3600.0:
		v = minf(speed_limit(run - gone, class_cruise), v + Ferry.ACCEL * STEP)
		gone += v * STEP
		t += STEP
	return t


## Whichever of the roster makes the quickest unhindered crossing of `run`.
static func best_for(run: float, class_cruise: float) -> Captain:
	var best: Captain = null
	var best_t := INF
	for c in roster():
		var t := c.crossing_minutes(run, class_cruise)
		if t < best_t:
			best_t = t
			best = c
	return best
