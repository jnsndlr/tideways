class_name Ambience
extends Node
## Environment sounds, on the Ambience bus (Settings: Environment sounds):
## - the sea lapping, fading in as the camera comes down close to the water;
## - a loop of gulls, fading in as the camera nears where gulls are;
## - now and then, a soft call of distant gulls, at any zoom.
## Gulls go quieter (and call less often) at night, but never silent.
## Lives in the map scene, so it goes when the map does.

const SEA := "res://assets/audio/ambient/sea_gentle.mp3"
const GULLS_NEAR := "res://assets/audio/ambient/gulls_near_loop.mp3"
const GULL_CALLS := "res://assets/audio/ambient/gull_calls_distant.mp3"

# Camera distance (CameraRig.distance) at which the sea is full, and where it has
# faded out; a long, gentle fade between.
const SEA_FULL := 140.0
const SEA_GONE := 1400.0
const SEA_CURVE := 2.0
# Camera-to-nearest-gull distance at which the gull loop is full, and where it has
# faded out; a short, steep fade, so it belongs to the gulls you're over.
const GULLS_FULL := 40.0
const GULLS_GONE := 200.0
const GULLS_CURVE := 3.0
# At full night (DayCycle.night = 1), gulls are this loud, and call this much less often.
const NIGHT_GULLS := 0.35
const NIGHT_CALL_GAP := 2.0
# Seconds between distant calls, and their level under the bus.
const CALL_GAP := Vector2(25.0, 70.0)
const CALL_DB := -13.0
# How quickly the loops follow the camera (linear gain per second).
const EASE := 0.8
const SILENT_DB := -60.0

var rig: CameraRig
var gulls: Seagulls
var day_cycle: DayCycle
var _sea: AudioStreamPlayer
var _near: AudioStreamPlayer
var _calls: AudioStreamPlayer
var _sea_gain := 0.0
var _near_gain := 0.0
var _gull_dist := INF
var _gull_check := 0.0
var _next_call := 0.0
var _rng := RandomNumberGenerator.new()


func setup(r: CameraRig, g: Seagulls, d: DayCycle) -> void:
	rig = r
	gulls = g
	day_cycle = d


func _ready() -> void:
	# Headless runs (tests, CI) have nobody listening, and the dummy driver holds
	# streams past exit (see Music).
	if DisplayServer.get_name() == "headless":
		set_process(false)
		return
	GameSettings.ensure()
	_rng.randomize()
	_sea = _player(SEA, true)
	_near = _player(GULLS_NEAR, true)
	_calls = _player(GULL_CALLS, false)
	_calls.volume_db = CALL_DB
	# Start the loops at different points so they don't line up.
	_sea.play(_rng.randf() * 10.0)
	_near.play(_rng.randf() * 6.0)
	_next_call = _rng.randf_range(8.0, CALL_GAP.y)


func _player(path: String, loop: bool) -> AudioStreamPlayer:
	var stream: AudioStreamMP3 = load(path)
	stream.loop = loop
	var p := AudioStreamPlayer.new()
	p.stream = stream
	p.bus = "Ambience"
	p.volume_db = SILENT_DB if loop else 0.0
	add_child(p)
	return p


func _process(delta: float) -> void:
	# Real time, so the fades and gaps don't race at 8x.
	var dt := delta / maxf(Engine.time_scale, 0.001) if Engine.time_scale > 0.0 else delta
	if rig == null:
		return
	var night := day_cycle.night if day_cycle else 0.0
	var gull_level := lerpf(1.0, NIGHT_GULLS, night)
	var sea_want := _ramp(rig.distance, SEA_GONE, SEA_FULL, SEA_CURVE)
	_gull_check -= dt
	if _gull_check <= 0.0 and gulls:
		_gull_check = 0.25
		_gull_dist = gulls.nearest_distance(rig.camera.global_position)
	var near_want := _ramp(_gull_dist, GULLS_GONE, GULLS_FULL, GULLS_CURVE) * gull_level
	_sea_gain = move_toward(_sea_gain, sea_want, EASE * dt)
	_near_gain = move_toward(_near_gain, near_want, EASE * dt)
	_sea.volume_db = maxf(linear_to_db(_sea_gain), SILENT_DB)
	_near.volume_db = maxf(linear_to_db(_near_gain), SILENT_DB)
	_next_call -= dt
	if _next_call <= 0.0:
		_next_call = _rng.randf_range(CALL_GAP.x, CALL_GAP.y) * lerpf(1.0, NIGHT_CALL_GAP, night)
		if not _calls.playing:
			_calls.volume_db = CALL_DB + linear_to_db(gull_level)
			_calls.pitch_scale = _rng.randf_range(0.94, 1.06)
			_calls.play()


## 0 at `gone`, 1 at `full`; the higher `curve`, the more it holds off until near `full`.
static func _ramp(v: float, gone: float, full: float, curve: float) -> float:
	var t := clampf(inverse_lerp(gone, full, v), 0.0, 1.0)
	return pow(t, curve)
