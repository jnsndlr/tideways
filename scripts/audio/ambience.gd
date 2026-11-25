class_name Ambience
extends Node
## Environment sounds, on the Ambience bus (Settings: Environment sounds):
## - the sea lapping, louder the lower the camera is over the water;
## - a loop of gulls, fading in as the camera nears where gulls are;
## - now and then, a soft call of distant gulls, riding on the sea's level, so it
##   is only ever as loud as the water under it.
## - a loop of forest, fading in as the camera nears trees, on the gulls' scheme;
## Gulls and forest go quieter (and call less often) at night, but never silent.
## Lives in the map scene, so it goes when the map does.

const SEA := "res://assets/audio/ambient/sea_gentle.mp3"
const GULLS_NEAR := "res://assets/audio/ambient/gulls_near_loop.mp3"
const GULL_CALLS := "res://assets/audio/ambient/gull_calls_distant.mp3"
const FOREST := "res://assets/audio/ambient/forest_near_loop.wav"
const BELL := "res://assets/audio/ambient/buoy_bell.wav"
# Bell buoys ring now and then, heard from the camera: full within BELL_FULL
# metres, falling off linearly to nothing at BELL_GONE.
const BELL_FULL := 100.0
const BELL_GONE := 300.0
const BELL_GAP := Vector2(20.0, 60.0)

# Camera height above the water at which the sea is full, and where it has faded
# out. Between, it falls off as an inverse curve (falloff / (falloff + rise)), so
# most of it is close in with a long soft tail; a smaller SEA_FALLOFF (metres)
# pulls it in tighter to the water.
const SEA_FULL := 50.0
const SEA_GONE := 4000.0
const SEA_FALLOFF := 800.0
# Camera-to-nearest-gull distance at which the gull loop is full, and where it has
# faded out; a short, steep fade, so it belongs to the gulls you're over.
const GULLS_FULL := 40.0
const GULLS_GONE := 200.0
const GULLS_CURVE := 3.0
# At full night (DayCycle.night = 1), gulls are this loud, and call this much less often.
const NIGHT_GULLS := 0.35
const NIGHT_CALL_GAP := 2.0
# Seconds between distant calls, and their level under the sea's.
const CALL_GAP := Vector2(25.0, 70.0)
const CALL_DB := -13.0
# How quickly the loops follow the camera (linear gain per second).
const EASE := 0.8
const SILENT_DB := -60.0

var rig: CameraRig
var gulls: Seagulls
var builder: WorldBuilder
var day_cycle: DayCycle
var _sea: AudioStreamPlayer
var _near: AudioStreamPlayer
var _calls: AudioStreamPlayer
var _forest: AudioStreamPlayer
var _bell: AudioStreamPlayer
var _bell_dist := INF
var _next_bell := 0.0
var _forest_gain := 0.0
var _tree_dist := INF
var _sea_gain := 0.0
var _near_gain := 0.0
var _gull_dist := INF
var _gull_check := 0.0
var _next_call := 0.0
var _rng := RandomNumberGenerator.new()


func setup(r: CameraRig, g: Seagulls, d: DayCycle, b: WorldBuilder = null) -> void:
	rig = r
	gulls = g
	builder = b
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
	_forest = _player(FOREST, true)
	_bell = _player(BELL, false)
	_next_bell = _rng.randf_range(2.0, BELL_GAP.y)
	# Start the loops at different points so they don't line up.
	_sea.play(_rng.randf() * 10.0)
	_near.play(_rng.randf() * 6.0)
	_forest.play(_rng.randf() * 5.0)
	_next_call = _rng.randf_range(8.0, CALL_GAP.y)


func _player(path: String, loop: bool) -> AudioStreamPlayer:
	var stream: AudioStream = load(path)
	if stream is AudioStreamWAV:
		var wav := stream as AudioStreamWAV
		if loop:
			wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
			wav.loop_begin = 0
			wav.loop_end = int(wav.get_length() * wav.mix_rate)
	else:
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
	var sea_want := _sea_level(rig.camera.global_position.y)
	_gull_check -= dt
	if _gull_check <= 0.0:
		_gull_check = 0.25
		if gulls:
			_gull_dist = gulls.nearest_distance(rig.camera.global_position)
		if builder:
			_tree_dist = builder.nearest_tree_distance(rig.camera.global_position, GULLS_GONE)
			_bell_dist = _nearest_bell_distance(rig.camera.global_position)
	var near_want := _ramp(_gull_dist, GULLS_GONE, GULLS_FULL, GULLS_CURVE) * gull_level
	_sea_gain = move_toward(_sea_gain, sea_want, EASE * dt)
	_near_gain = move_toward(_near_gain, near_want, EASE * dt)
	_sea.volume_db = maxf(linear_to_db(_sea_gain), SILENT_DB)
	_near.volume_db = maxf(linear_to_db(_near_gain), SILENT_DB)
	var forest_want := _ramp(_tree_dist, GULLS_GONE, GULLS_FULL, GULLS_CURVE) * gull_level
	_forest_gain = move_toward(_forest_gain, forest_want, EASE * dt)
	_forest.volume_db = maxf(linear_to_db(_forest_gain), SILENT_DB)
	# Follows the sea as it plays, so zooming out mid-call fades it with the water.
	_calls.volume_db = maxf(CALL_DB + linear_to_db(_sea_gain * gull_level), SILENT_DB)
	# The bell follows the camera as it rings; only rings when it can be heard.
	var bell_gain := _ramp(_bell_dist, BELL_GONE, BELL_FULL, 1.0)
	_bell.volume_db = maxf(linear_to_db(bell_gain), SILENT_DB)
	_next_bell -= dt
	if _next_bell <= 0.0:
		_next_bell = _rng.randf_range(BELL_GAP.x, BELL_GAP.y)
		if bell_gain > 0.0 and not _bell.playing:
			_bell.play()
	_next_call -= dt
	if _next_call <= 0.0:
		_next_call = _rng.randf_range(CALL_GAP.x, CALL_GAP.y) * lerpf(1.0, NIGHT_CALL_GAP, night)
		if not _calls.playing and _sea_gain > 0.01:
			_calls.pitch_scale = _rng.randf_range(0.94, 1.06)
			_calls.play()


## 1 at SEA_FULL and below, 0 at SEA_GONE and above, inverse in between.
static func _sea_level(height: float) -> float:
	var inv := func(h: float) -> float: return SEA_FALLOFF / (SEA_FALLOFF + maxf(h - SEA_FULL, 0.0))
	var floor_v: float = inv.call(SEA_GONE)
	return clampf((inv.call(height) - floor_v) / (1.0 - floor_v), 0.0, 1.0)


## 0 at `gone`, 1 at `full`; the higher `curve`, the more it holds off until near `full`.
static func _ramp(v: float, gone: float, full: float, curve: float) -> float:
	var t := clampf(inverse_lerp(gone, full, v), 0.0, 1.0)
	return pow(t, curve)


## Camera (or any point) to the nearest bell buoy, in metres; INF if there are none.
func _nearest_bell_distance(from: Vector3) -> float:
	var best := INF
	for b in builder.bell_buoys:
		best = minf(best, from.distance_to(b))
	return best
