class_name Weather
extends RefCounted
## The sky over the map: what kind of day it is and how much cloud is up. The
## simulation steps it with the game clock; CloudLayer, the HUD and anything else
## weather-dependent read it.
##
## Left alone it rolls a new kind of weather every several hours, weighted so most
## days are fair with a few clouds and the odd one is clear or overcast, and the sky
## eases into each change over a couple of hours. set_kind() pins a kind (a story
## beat, a debug key) until resume() hands control back to the rolls.
##
## Later weather (rain, fog, storms, wind shifts) belongs here too, as more fields on
## each kind.

## Per kind:
##   coverage  the cloud deck over the map (the shared field in clouds.gdshaderinc)
##   horizon   the distant clouds round the horizon (sky.gdshader): how much of
##             the horizon has cloud, how high the towers climb (sin of elevation),
##             density (opacity) and haze over their feet. Kept low: they're a
##             hazy fringe on the horizon, not towers to rival the mountains
##   storm     0..1: how dark and heavy the clouds are (Storm only, for now)
##   weight    how often the rolls pick it
const KINDS := {
	"Clear": {"coverage": 0.04, "horizon": Vector4(0.25, 0.018, 0.7, 0.5), "storm": 0.0, "weight": 1.0},
	"Few Clouds": {"coverage": 0.18, "horizon": Vector4(0.45, 0.024, 0.8, 0.45), "storm": 0.0, "weight": 2.2},
	"Partly Cloudy": {"coverage": 0.34, "horizon": Vector4(0.6, 0.03, 0.85, 0.45), "storm": 0.0, "weight": 2.4},
	"Mostly Cloudy": {"coverage": 0.48, "horizon": Vector4(0.75, 0.032, 0.9, 0.45), "storm": 0.0, "weight": 1.4},
	"Overcast": {"coverage": 0.64, "horizon": Vector4(0.95, 0.026, 0.9, 0.5), "storm": 0.15, "weight": 1.0},
	"Storm": {"coverage": 0.86, "horizon": Vector4(1.0, 0.026, 1.0, 0.55), "storm": 1.0, "weight": 0.5},
}
const ORDER := ["Clear", "Few Clouds", "Partly Cloudy", "Mostly Cloudy", "Overcast", "Storm"]
## Game minutes between rolls, and how long the sky takes to change.
const HOLD_MINUTES := Vector2(5.0 * 60.0, 16.0 * 60.0)
const EASE_MINUTES := Vector2(90.0, 240.0)

signal changed(kind: String)

## The kind the sky is heading for (or has settled on).
var kind := "Partly Cloudy"
## Current coverage and horizon clouds, easing toward kind's.
var coverage := 0.34
var horizon := Vector4(0.6, 0.03, 0.85, 0.45)
var storm := 0.0
var pinned := false

var _rng := RandomNumberGenerator.new()
var _from := 0.34
var _from_horizon := horizon
var _from_storm := 0.0
var _ease := 0.0     # game minutes the current change takes
var _eased := 0.0    # game minutes into it
var _hold := 0.0     # game minutes until the next roll


func setup(seed: int) -> void:
	_rng.seed = seed
	kind = _roll()
	coverage = KINDS[kind].coverage
	horizon = KINDS[kind].horizon
	storm = KINDS[kind].storm
	_from = coverage
	_from_horizon = horizon
	_from_storm = storm
	_hold = _rng.randf_range(HOLD_MINUTES.x, HOLD_MINUTES.y)


func step(minutes: float) -> void:
	if _eased < _ease:
		_eased = minf(_eased + minutes, _ease)
		var f := smoothstep(0.0, 1.0, _eased / _ease)
		coverage = lerpf(_from, KINDS[kind].coverage, f)
		horizon = _from_horizon.lerp(KINDS[kind].horizon, f)
		storm = lerpf(_from_storm, KINDS[kind].storm, f)
	if pinned:
		return
	_hold -= minutes
	if _hold <= 0.0:
		_hold = _rng.randf_range(HOLD_MINUTES.x, HOLD_MINUTES.y)
		_change_to(_roll(), _rng.randf_range(EASE_MINUTES.x, EASE_MINUTES.y))


## Pins the weather to a kind, easing in over ease_minutes of game time (0 snaps).
func set_kind(k: String, ease_minutes := 30.0) -> void:
	assert(KINDS.has(k), "Unknown weather kind %s" % k)
	pinned = true
	_change_to(k, ease_minutes)


## Hands the weather back to the random rolls, starting from the current sky.
func resume() -> void:
	pinned = false
	_hold = _rng.randf_range(HOLD_MINUTES.x, HOLD_MINUTES.y) * 0.5


## The kind after this one, for cycling through them.
func next_kind() -> String:
	return ORDER[(ORDER.find(kind) + 1) % ORDER.size()]


## The kind the sky looks like right now (mid-change, the nearer one).
func label() -> String:
	var best := kind
	var best_d := INF
	for k: String in ORDER:
		var d := absf(KINDS[k].coverage - coverage)
		if d < best_d:
			best_d = d
			best = k
	return best


## How dark cloud shadows get: crisp under fair-weather cumulus, broad and soft
## once the sky fills in and the light diffuses, and deep under storm cloud.
func shadow_strength() -> float:
	return lerpf(0.65, 0.4, smoothstep(0.34, 0.64, coverage)) + storm * 0.25


## Cloud opacity: thinner, greyer sheets when overcast, thick again in a storm.
func cloud_opacity() -> float:
	return lerpf(lerpf(0.92, 0.8, smoothstep(0.48, 0.64, coverage)), 0.97, storm)


func _change_to(k: String, ease_minutes: float) -> void:
	_from = coverage
	_from_horizon = horizon
	_from_storm = storm
	kind = k
	_ease = maxf(ease_minutes, 0.0)
	_eased = 0.0
	if _ease == 0.0:
		coverage = KINDS[k].coverage
		horizon = KINDS[k].horizon
		storm = KINDS[k].storm
	changed.emit(k)


func _roll() -> String:
	var total := 0.0
	for k: String in ORDER:
		total += KINDS[k].weight
	var r := _rng.randf() * total
	for k: String in ORDER:
		r -= KINDS[k].weight
		if r <= 0.0:
			return k
	return ORDER[ORDER.size() - 1]
