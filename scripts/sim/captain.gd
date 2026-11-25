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
var landing := 1.0    # how surely she lands centred in the slip (0..1); the rest of the
                      # time she comes in off centre and rides a wing wall in

static var _roster: Array[Captain] = []


static func roster() -> Array[Captain]:
	if _roster.is_empty():
		_roster = [
			_make("halloran", "Ines Halloran", "Fast in open water, careful into the slip", 1.12, 0.9, 0.5),
			_make("tran", "Bo Tran", "Quick, sure dockings, easy pace at sea", 0.92, 1.3, 0.9),
		]
	return _roster


static func _make(i: String, n: String, s: String, sea_f: float, harbour_f: float, land_f: float) -> Captain:
	var c := Captain.new()
	c.id = i
	c.name = n
	c.strength = s
	c.sea = sea_f
	c.harbour = harbour_f
	c.landing = land_f
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
	return FerryVoyage.speed_limit(remaining, cruise(class_cruise), harbour)


## Game minutes for an unhindered crossing of `run` metres dock to dock (other
## traffic can still hold a ferry up). Steps the same rule Ferry sails by.
func crossing_minutes(run: float, class_cruise: float) -> float:
	return _step_crossing(run, class_cruise).x


## The sum of speed² × distance over an unhindered crossing of `run` metres
## (m³/s²): fuel burnt per mile goes as speed², so Ferry.leg_fuel scales this.
func crossing_burn(run: float, class_cruise: float) -> float:
	return _step_crossing(run, class_cruise).y


## [game minutes, Σ v² ds] for an unhindered crossing, stepped as Ferry sails it.
func _step_crossing(run: float, class_cruise: float) -> Vector2:
	const STEP := 0.05
	var t := 0.0
	var gone := 0.0
	var v := 0.0
	var burn := 0.0
	while gone < run - 0.03 and t < 3600.0:
		v = minf(speed_limit(run - gone, class_cruise), v + FerryVoyage.ACCEL * STEP)
		var ds := minf(v * STEP, run - gone)
		gone += v * STEP
		burn += v * v * ds
		t += STEP
	return Vector2(Units.game_minutes(t), burn)


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
