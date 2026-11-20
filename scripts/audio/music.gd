class_name Music
extends Node
## The soundtrack: one looping track that carries on across scene changes (it
## lives under the tree root, not in a scene). Full on the menu and loading
## screen, fading down to a soft bed once a map is built. Its level is set by the
## Music bus (GameSettings).

const TRACK := "res://assets/audio/harbor_exploration.mp3"

enum Mood { FULL, SOFT }

## Level of each mood on top of the Music bus volume.
const MOOD_DB := {Mood.FULL: 0.0, Mood.SOFT: -11.0}
const SILENT_DB := -40.0
## Seconds to fade between moods (and in from silence).
const FADE := 2.5
## Dip under a radio call, and how quickly it dips and recovers.
const DUCK_DB := -8.0
const DUCK_FADE := 0.6

var _player: AudioStreamPlayer
var _tween: Tween
var _mood := Mood.FULL
var _ducked := false


## Starts the music if needed and fades it to `mood`.
static func set_mood(tree: SceneTree, mood: Mood) -> void:
	# Headless runs (tests, CI) have nobody listening, and the dummy audio driver
	# never lets go of the stream, which shows as a leak at exit.
	if DisplayServer.get_name() == "headless":
		return
	var music := tree.root.get_node_or_null("Music") as Music
	if music == null:
		music = Music.new()
		music.name = "Music"
		music._mood = mood
		# Callers are often mid-_ready, while the root is busy adding children.
		tree.root.add_child.call_deferred(music)
	elif music.is_inside_tree():
		music._fade_to(mood)
	else:
		music._mood = mood


## Dips the music under a radio call (`on`), or brings it back.
static func duck(tree: SceneTree, on: bool) -> void:
	var music := tree.root.get_node_or_null("Music") as Music
	if music and music.is_inside_tree():
		music._ducked = on
		music._fade_to(music._mood, DUCK_FADE)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	GameSettings.ensure()
	var stream: AudioStreamMP3 = load(TRACK)
	stream.loop = true
	_player = AudioStreamPlayer.new()
	_player.stream = stream
	_player.bus = "Music"
	_player.volume_db = SILENT_DB
	add_child(_player)
	_player.play()
	_fade_to(_mood)


## Let the audio server drop the stream before quitting, or it reports it leaked.
func _exit_tree() -> void:
	_player.stop()
	_player.stream = null


func _fade_to(mood: Mood, seconds := FADE) -> void:
	_mood = mood
	var target: float = MOOD_DB[mood] + (DUCK_DB if _ducked else 0.0)
	if _tween:
		_tween.kill()
	_tween = create_tween()
	# Game speed is Engine.time_scale; the fade should take real seconds.
	_tween.set_ignore_time_scale(true)
	_tween.tween_property(_player, "volume_db", target, seconds) \
		.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
