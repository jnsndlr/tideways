extends WorldSession
## The story map: the same world as the sandbox, built from an authored layout
## (MapLayout.MAIN_STORY) instead of a random seed. The island editor (I, or the
## ISLANDS button) rolls and dials its islands, then saves or copies the layout.
## Takes the sandbox's debug args, plus --edit=K (open the editor on island K),
## --full-network, --scenario=NAME (maps/NAME.json) and --pick=NAME (select an island).

## The starter islands. If the layout file is missing, a fresh one is rolled with these.
const ISLAND_NAMES := ["Port Rosario", "Madrona Island", "Cypress Island", "Juniper Island",
	"Bracken Island", "Kestrel Island", "Gullrock Island", "San Vela Island", "Cordero Landing",
	"Eagle Island"]

## The editor reads and updates the working layout across rebuilds.
var layout: MapLayout:
	get: return RegionEntryState.layout
	set(value): RegionEntryState.layout = value
var unsaved: bool:
	get: return RegionEntryState.unsaved
	set(value): RegionEntryState.unsaved = value

## A pin on the selected dock site for sale.
var _site_pins: Node3D
var editor: IslandEditor


static func start_session(path: String) -> void:
	RegionEntryState.scenario_path = path
	RegionEntryState.editor_restore.clear()


func _ready() -> void:
	SessionDiagnostics.attach(self)
	var options := Scenes.launch_options.values
	if layout == null:
		layout = MapLayout.load_file(MapLayout.MAIN_STORY)
		if layout == null:
			layout = MapGenerator.roll_layout(randi_range(1, 99999), ISLAND_NAMES, -2)
			unsaved = true
	# --full-network: the planned network with a boat per route, as in the sandbox.
	# --scenario=shared_slip: maps/shared_slip.json instead of the opening.
	var opening: Scenario
	var plan := "full-network"
	if not options.has("full-network"):
		var file: String = "res://maps/%s.json" % options["scenario"] if options.has("scenario") else (
			RegionEntryState.scenario_path if RegionEntryState.scenario_path != "" else Scenario.OPENING)
		opening = Scenario.load_file(file)
		plan = file.get_file().get_basename()
	# The authored islands' routes are planned once and kept (MapGenerator.route_cache_path).
	# Every dock site's routes are in them, so buying one plans nothing (TID-319).
	var route_cache_path := ""
	if not unsaved:
		route_cache_path = "res://maps/routes/%s-%s.json" % [MapLayout.MAIN_STORY.get_file().get_basename(), plan]
	await start_authored(layout, opening, route_cache_path)
	if not built:
		return
	editor = IslandEditor.new()
	add_child(editor)
	editor.setup(self)
	if RegionEntryState.editor_restore.has("cam"):
		var c: Array = RegionEntryState.editor_restore["cam"]
		rig.target_pos = c[0]
		rig.target_dist = c[1]
		rig.target_yaw = c[2]
		rig.target_pitch = c[3]
		rig.snap()
	if RegionEntryState.editor_restore.get("editor_open", false):
		editor.open(RegionEntryState.editor_restore.get("selected", 0))
	elif options.has("edit"):
		editor.open(int(options["edit"]))
	# --pick=Cypress: select the island whose name starts so (any, terminal or not).
	if options.has("pick"):
		for isl in map.islands:
			if isl.name.begins_with(str(options["pick"])):
				hud.select_island(isl, true)
				rig.snap()
				break
	RegionEntryState.editor_restore.clear()
	_site_pins = Node3D.new()
	add_child(_site_pins)
	if scenario and scenario.mission:
		scenario.mission.start(sim.day)
		var panel := MissionPanel.new()
		hud.root.add_child(panel)
		panel.setup(self, scenario.mission)


func _setup_hud() -> void:
	hud.dock_site_selected.connect(show_dock_sites)
	hud.setup(self, true)


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
	RegionEntryState.editor_restore = {
		"cam": [rig.target_pos, rig.target_dist, rig.target_yaw, rig.target_pitch],
		"editor_open": editor.is_open(),
		"selected": editor.selected,
	}
	Engine.time_scale = 1.0
	get_tree().paused = false
	get_tree().reload_current_scene()


func intro(islands: int) -> Array[String]:
	return ["MAIN MAP", "%d islands · %d route%s%s.\nPress I to edit the islands." % [
		islands, map.routes.size(), "" if map.routes.size() == 1 else "s", " · unsaved layout" if unsaved else ""]]


## G makes a new map in the sandbox; here the layout is authored.
func regenerate() -> void:
	hud.show_toast("MAIN MAP", "This map is authored. Press I to edit its islands.", 3.0)
