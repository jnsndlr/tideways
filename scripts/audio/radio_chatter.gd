class_name RadioChatter
extends Node
## Random VHF radio calls over the music on the title screen and loading screen.
##
## Every clip in FOLDER is in the mix: drop an .mp3, .ogg or .wav in there and it
## joins the next time the game runs (Godot imports it on the next editor scan or
## `--import`). Calls play on the Radio bus, which band-limits them like a handset.
##
## Rules: at most one call every COOLDOWN seconds; if a call played on the title
## screen, the loading screen that follows stays quiet; none start in game (one
## already going finishes).

const FOLDER := "res://assets/audio/radio"
const EXTENSIONS := ["mp3", "ogg", "wav"]
const COOLDOWN := 120.0
## Seconds after arriving before a call may come in.
const MENU_DELAY := Vector2(4.0, 10.0)
const LOADING_DELAY := Vector2(1.0, 3.0)
## After a call on the title screen, the next one (once the cooldown allows).
const MENU_REPEAT := Vector2(10.0, 40.0)

enum Place { MENU, LOADING, GAME }

## Real time the last call started (ms), kept for the whole run.
static var _last_start := -1

var _place := Place.GAME
var _played_on_menu := false
var _last_clip := ""
var _player: AudioStreamPlayer
var _timer: Timer
var _rng := RandomNumberGenerator.new()


static func on_menu(tree: SceneTree) -> void:
	_go(tree, Place.MENU)


static func on_loading(tree: SceneTree) -> void:
	_go(tree, Place.LOADING)


static func on_game(tree: SceneTree) -> void:
	_go(tree, Place.GAME)


## All the clips in the mix.
static func clips() -> Array[String]:
	var out: Array[String] = []
	for f in ResourceLoader.list_directory(FOLDER):
		if f.get_extension().to_lower() in EXTENSIONS:
			out.append(FOLDER.path_join(f))
	return out


static func _go(tree: SceneTree, place: Place) -> void:
	if DisplayServer.get_name() == "headless":
		return
	var radio := tree.root.get_node_or_null("RadioChatter") as RadioChatter
	if radio == null:
		if place == Place.GAME:
			return
		radio = RadioChatter.new()
		radio.name = "RadioChatter"
		radio._place = place
		# Callers are often mid-_ready, while the root is busy adding children.
		tree.root.add_child.call_deferred(radio)
	elif radio.is_inside_tree():
		radio._arrive(place)
	else:
		radio._place = place


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_rng.randomize()
	GameSettings.ensure()
	_setup_bus()
	_player = AudioStreamPlayer.new()
	_player.bus = "Radio"
	_player.finished.connect(_on_finished)
	add_child(_player)
	_timer = Timer.new()
	_timer.one_shot = true
	_timer.ignore_time_scale = true
	_timer.timeout.connect(_try_call)
	add_child(_timer)
	_arrive(_place)


func _arrive(place: Place) -> void:
	_place = place
	match place:
		Place.MENU:
			_played_on_menu = false
			_schedule(MENU_DELAY)
		Place.LOADING:
			if _played_on_menu:
				_timer.stop()
			else:
				_schedule(LOADING_DELAY)
		Place.GAME:
			_timer.stop()


## Waits a random time in `delay`, and at least until the cooldown is over.
func _schedule(delay: Vector2) -> void:
	_timer.start(maxf(_rng.randf_range(delay.x, delay.y), _cooldown_left() + 0.5))


func _cooldown_left() -> float:
	if _last_start < 0:
		return 0.0
	return maxf(0.0, COOLDOWN - (Time.get_ticks_msec() - _last_start) / 1000.0)


func _try_call() -> void:
	if _place == Place.GAME or _player.playing:
		return
	if _cooldown_left() > 0.0:
		_timer.start(_cooldown_left() + 0.5)
		return
	var pool := clips()
	if pool.size() > 1:
		pool.erase(_last_clip)
	if pool.is_empty():
		return
	_last_clip = pool[_rng.randi_range(0, pool.size() - 1)]
	var stream := load(_last_clip) as AudioStream
	if stream == null:
		return
	_player.stream = stream
	_player.play()
	_last_start = Time.get_ticks_msec()
	if _place == Place.MENU:
		_played_on_menu = true
	Music.duck(get_tree(), true)


func _on_finished() -> void:
	Music.duck(get_tree(), false)
	if _place == Place.MENU:
		_schedule(MENU_REPEAT)


## Handset sound: voice band only, a touch of grit.
func _setup_bus() -> void:
	var i := AudioServer.get_bus_index("Radio")
	if AudioServer.get_bus_effect_count(i) > 0:
		return
	var hp := AudioEffectHighPassFilter.new()
	hp.cutoff_hz = 350.0
	AudioServer.add_bus_effect(i, hp)
	var lp := AudioEffectLowPassFilter.new()
	lp.cutoff_hz = 3200.0
	AudioServer.add_bus_effect(i, lp)
	var grit := AudioEffectDistortion.new()
	grit.mode = AudioEffectDistortion.MODE_OVERDRIVE
	grit.drive = 0.25
	grit.post_gain = -3.0
	AudioServer.add_bus_effect(i, grit)


## Stops cleanly so the audio server drops the stream before quitting.
func _exit_tree() -> void:
	_player.stop()
	_player.stream = null
