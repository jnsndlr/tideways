class_name Music
extends Node
## The soundtrack: every track in FOLDER, played in a random order without an
## immediate repeat, carrying on across scene changes (it lives under the tree
## root, not in a scene). Drop an .mp3, .ogg or .wav in FOLDER to add a track. Full on the menu and loading
## screen, fading down to a soft bed once a map is built. Its level is set by the
## Music bus (GameSettings).

const FOLDER := "res://assets/audio/music"
const EXTENSIONS := ["mp3", "ogg", "wav"]

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
var _tracks: PackedStringArray = []
var _queue: PackedStringArray = []
var _last := ""
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
	for f in ResourceLoader.list_directory(FOLDER):
		if f.get_extension().to_lower() in EXTENSIONS:
			_tracks.append(FOLDER.path_join(f))
	_player = AudioStreamPlayer.new()
	_player.bus = "Music"
	_player.volume_db = SILENT_DB
	_player.finished.connect(_play_next)
	add_child(_player)
	_play_next()
	_fade_to(_mood)


## Plays a random track; each plays once before any repeats, never back to back.
func _play_next() -> void:
	if _tracks.is_empty():
		return
	if _queue.is_empty():
		var order := Array(_tracks)
		order.shuffle()
		if order.size() > 1 and order[0] == _last:
			order.push_back(order.pop_front())
		_queue = PackedStringArray(order)
	_last = _queue[0]
	_queue.remove_at(0)
	var stream := load(_last) as AudioStream
	if stream is AudioStreamMP3:
		(stream as AudioStreamMP3).loop = false
	elif stream is AudioStreamOggVorbis:
		(stream as AudioStreamOggVorbis).loop = false
	_player.stream = stream
	_player.play()


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
