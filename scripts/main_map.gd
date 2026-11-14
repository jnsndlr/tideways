extends "res://scripts/sandbox.gd"
## The story map: the same world as the sandbox, built from an authored layout
## (MapLayout.MAIN_STORY) instead of a random seed. The island editor (I, or the
## ISLANDS button) rolls and dials its islands, then saves or copies the layout.
## Takes the sandbox's debug args, plus --edit=K (open the editor on island K).

## Until the real island names are in, a fresh layout is rolled with these.
const PLACEHOLDER_NAMES := ["Island A", "Island B", "Island C", "Island D", "Island E",
	"Island F", "Island G", "Island H", "Island I", "Island J"]

## The working copy, kept across rebuilds (a rebuild reloads the scene).
static var layout: MapLayout
## The working copy differs from the saved file.
static var unsaved := false
## Camera and editor state carried across a rebuild.
static var _carry := {}

var editor: IslandEditor


func _generate(gen: MapGenerator) -> MapData:
	if layout == null:
		layout = MapLayout.load_file(MapLayout.MAIN_STORY)
		if layout == null:
			layout = MapGenerator.roll_layout(randi_range(1, 99999), PLACEHOLDER_NAMES, -2)
			unsaved = true
	return gen.generate_from(layout)


func _ready() -> void:
	super._ready()
	editor = IslandEditor.new()
	add_child(editor)
	editor.setup(self)
	if _carry.has("cam"):
		var c: Array = _carry["cam"]
		rig.target_pos = c[0]
		rig.target_dist = c[1]
		rig.target_yaw = c[2]
		rig.target_pitch = c[3]
		rig.snap()
	if _carry.get("editor_open", false):
		editor.open(_carry.get("selected", 0))
	elif _args.has("edit"):
		editor.open(int(_args["edit"]))
	_carry.clear()


## Builds the whole map again from the working layout.
func rebuild() -> void:
	_carry = {
		"cam": [rig.target_pos, rig.target_dist, rig.target_yaw, rig.target_pitch],
		"editor_open": editor.is_open(),
		"selected": editor.selected,
	}
	Engine.time_scale = 1.0
	get_tree().paused = false
	get_tree().reload_current_scene()


## G makes a new map in the sandbox; here the layout is authored.
func regenerate() -> void:
	hud.show_toast("MAIN MAP", "This map is authored. Press I to edit its islands.", 3.0)
