extends "res://scripts/sandbox.gd"
## The story map: the same world as the sandbox, built from an authored layout
## (MapLayout.MAIN_STORY) instead of a random seed. The island editor (I, or the
## ISLANDS button) rolls and dials its islands, then saves or copies the layout.
## Takes the sandbox's debug args, plus --edit=K (open the editor on island K),
## --full-network and --scenario=NAME (maps/NAME.json).

## The starter islands. If the layout file is missing, a fresh one is rolled with these.
const ISLAND_NAMES := ["Port Rosario", "Madrona Island", "Cypress Island", "Juniper Island",
	"Bracken Island", "Kestrel Island", "Gullrock Island", "San Vela Island", "Cordero Landing",
	"Eagle Island"]

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
			layout = MapGenerator.roll_layout(randi_range(1, 99999), ISLAND_NAMES, -2)
			unsaved = true
	# --full-network: the planned network with a boat per route, as in the sandbox.
	# --scenario=shared_slip: maps/shared_slip.json instead of the opening.
	if not _args.has("full-network"):
		var file: String = "res://maps/%s.json" % _args["scenario"] if _args.has("scenario") else Scenario.OPENING
		scenario = Scenario.load_file(file)
	return gen.generate_from(layout, scenario)


func _ready() -> void:
	await super._ready()
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


func intro(islands: int) -> Array:
	return ["MAIN MAP", "%d islands · %d route%s%s.\nPress I to edit the islands." % [
		islands, map.routes.size(), "" if map.routes.size() == 1 else "s", " · unsaved layout" if unsaved else ""]]


## G makes a new map in the sandbox; here the layout is authored.
func regenerate() -> void:
	hud.show_toast("MAIN MAP", "This map is authored. Press I to edit its islands.", 3.0)
