class_name UiSounds
extends Node
## Interface sounds: a click on every button press, anywhere in the game. Watches
## the tree for new buttons, so panels built later click too. Effects bus.

const CLICK := "res://assets/audio/ui/click.wav"

var _player: AudioStreamPlayer


## Starts listening for buttons, once per run.
static func install(tree: SceneTree) -> void:
	if DisplayServer.get_name() == "headless" or tree.root.has_node("UiSounds"):
		return
	var ui := UiSounds.new()
	ui.name = "UiSounds"
	# Callers are often mid-_ready, while the root is busy adding children.
	tree.root.add_child.call_deferred(ui)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	GameSettings.ensure()
	_player = AudioStreamPlayer.new()
	_player.stream = load(CLICK)
	_player.bus = "Effects"
	_player.max_polyphony = 3
	add_child(_player)
	for b in get_tree().root.find_children("*", "BaseButton", true, false):
		_hook(b)
	get_tree().node_added.connect(func(n: Node) -> void:
		if n is BaseButton:
			_hook(n))


func _hook(b: BaseButton) -> void:
	if not b.pressed.is_connected(_click):
		b.pressed.connect(_click)


func _click() -> void:
	_player.play()


func _exit_tree() -> void:
	_player.stop()
	_player.stream = null
