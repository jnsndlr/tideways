class_name Units
extends RefCounted
## Lengths are metres throughout. Things that move about the map (vessels, cars,
## wildlife) go SPEED_UP times faster than their real speed, so that with the
## clock's MINUTES_PER_SECOND game minutes per real second a crossing still takes
## a sensible part of a game hour; the HUD shows their real speed.

## Game metres per model metre for road vehicles and ferries built to the same scale.
const VEHICLE_MODEL_SCALE := 1.26
const KNOT := 0.514444          # m/s
const SPEED_UP := 3.6
const MINUTES_PER_SECOND := 0.5  # 2 real seconds = 1 game minute at 1x
const REAL_TIME_SCALE := 1.0 / (60.0 * MINUTES_PER_SECOND)


## Game minutes elapsed in `seconds` of simulation time (at 1x).
static func game_minutes(seconds: float) -> float:
	return seconds * MINUTES_PER_SECOND


## Real speed, in knots, of something moving at `v` (m/s on the map).
static func knots(v: float) -> float:
	return v / SPEED_UP / KNOT


## Speed on the map (m/s) of something making `kn` knots.
static func from_knots(kn: float) -> float:
	return kn * KNOT * SPEED_UP
