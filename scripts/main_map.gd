extends "res://scripts/sandbox.gd"
## The story map: the same world as the sandbox, built from an authored layout
## (MapLayout.MAIN_STORY) instead of a random seed. The island editor (I, or the
## ISLANDS button) rolls and dials its islands, then saves or copies the layout.
## Takes the sandbox's debug args, plus --edit=K (open the editor on island K),
## --full-network, --scenario=NAME (maps/NAME.json) and --pick=NAME (select an island).

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
## A pin on the selected dock site for sale.
var _site_pins: Node3D
## A scenario file for the next Play instead of the opening (the menu's Mission
## trial sets it; "" plays the opening).
static var scenario_path := ""
## Mission sandbox: the main mission with money that never runs out (more debug
## and quick-test tools to come).
static var unlimited_cash := false
## A loaded quick save's date: [day, minutes], applied once the map is built.
static var _load_date: Array = []

var editor: IslandEditor


static func start_session(path: String, unlimited := false) -> void:
	scenario_path = path
	unlimited_cash = unlimited
	_carry.clear()
	_load_date = []


## Plays the quick save: its scenario from the top, with the clock at its date.
static func load_session(data: Dictionary) -> void:
	start_session(str(data.get("scenario", "")), bool(data.get("unlimited", false)))
	_load_date = [int(data.get("day", 12)), float(data.get("minutes", 360.0))]


## F5: saves the scenario name and the game date.
func quick_save() -> void:
	var name := scenario_path if scenario_path != "" else Scenario.OPENING
	if SaveGame.save(name, unlimited_cash, sim.day, sim.minutes):
		hud.show_toast("GAME SAVED", "%s · day %d, %s" % [name.get_file().get_basename(), sim.day, sim.clock_text(sim.minutes)], 3.0)
	else:
		hud.show_toast("SAVE FAILED", "Couldn't write the save file.", 3.0)


func _generation_job(gen: MapGenerator) -> Callable:
	if layout == null:
		layout = MapLayout.load_file(MapLayout.MAIN_STORY)
		if layout == null:
			layout = MapGenerator.roll_layout(randi_range(1, 99999), ISLAND_NAMES, -2)
			unsaved = true
	# --full-network: the planned network with a boat per route, as in the sandbox.
	# --scenario=shared_slip: maps/shared_slip.json instead of the opening.
	var plan := "full-network"
	if not _args.has("full-network"):
		var file: String = "res://maps/%s.json" % _args["scenario"] if _args.has("scenario") else (
			scenario_path if scenario_path != "" else Scenario.OPENING)
		scenario = Scenario.load_file(file)
		if unlimited_cash:
			scenario.cash = CompanyLedger.UNLIMITED_CASH
		plan = file.get_file().get_basename()
	# The authored islands' routes are planned once and kept (MapGenerator.route_cache_path).
	# Every dock site's routes are in them, so buying one plans nothing (TID-319).
	if not unsaved:
		gen.route_cache_path = "res://maps/routes/%s-%s.json" % [MapLayout.MAIN_STORY.get_file().get_basename(), plan]
	return gen.generate_from.bind(layout, scenario)


func _ready() -> void:
	await super._ready()
	if not built:
		return
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
	# --pick=Cypress: select the island whose name starts so (any, terminal or not).
	if _args.has("pick"):
		for isl in map.islands:
			if isl.name.begins_with(str(_args["pick"])):
				hud.select_island(isl, true)
				rig.snap()
				break
	_carry.clear()
	if not _load_date.is_empty():
		sim.day = _load_date[0]
		sim.minutes = _load_date[1]
		_load_date = []
	_site_pins = Node3D.new()
	add_child(_site_pins)
	if scenario and scenario.mission:
		scenario.mission.start(sim.day)
		var panel := MissionPanel.new()
		hud.root.add_child(panel)
		panel.setup(self, scenario.mission)


## Buys `town`'s dock site: its terminal is built in place over
## Simulation.DOCK_BUILD_MINUTES and opens on its own, with no rebuild (TID-319).
func buy_dock(town: MapData.Town) -> void:
	if not sim.buy_dock(town):
		return
	hud.show_toast("NEW TERMINAL", "Building %s's terminal. It opens in %d hours." % [town.name, int(Simulation.DOCK_BUILD_MINUTES / 60.0)], 4.0)


## Pins `town`'s dock site (null: none).
func show_dock_sites(town: MapData.Town) -> void:
	if _site_pins == null:
		return
	var key := "" if town == null else town.key
	if _site_pins.get_meta("key", "") == key:
		return
	_site_pins.set_meta("key", key)
	for c in _site_pins.get_children():
		c.queue_free()
	if town == null:
		return
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Hud.ACCENT
	var pole := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 3.0
	cm.bottom_radius = 3.0
	cm.height = 60.0
	pole.mesh = cm
	pole.material_override = mat
	pole.position = town.shore + Vector3(0, cm.height * 0.5 + 2.0, 0)
	_site_pins.add_child(pole)
	var bar := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(6, 3, Layout.DOCK_U + 40.0)
	bar.mesh = bm
	bar.material_override = mat
	bar.transform = Transform3D(Basis(Vector3.UP.cross(town.dock_dir), Vector3.UP, town.dock_dir), town.shore + town.dock_dir * bm.size.z * 0.5 + Vector3(0, 3, 0))
	_site_pins.add_child(bar)


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
