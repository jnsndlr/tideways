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
## The company carried across a rebuild after buying a dock site: its scenario
## (terminals, schedules, cash after the purchase) and the clock.
static var _company: Scenario
static var _clock := []
## Dock sites bought in play, "<island key>" -> site index (keys the route cache).
static var _bought := {}
## Pins on the shown island's locked dock sites.
var _site_pins: Node3D
## A scenario file for the next Play instead of the opening (the menu's Mission
## trial sets it; "" plays the opening).
static var scenario_path := ""
## Which scenario's routes the rebuild after buying a site starts from.
static var _plan := "opening"

var editor: IslandEditor


func _generation_job(gen: MapGenerator) -> Callable:
	if layout == null:
		layout = MapLayout.load_file(MapLayout.MAIN_STORY)
		if layout == null:
			layout = MapGenerator.roll_layout(randi_range(1, 99999), ISLAND_NAMES, -2)
			unsaved = true
	# --full-network: the planned network with a boat per route, as in the sandbox.
	# --scenario=shared_slip: maps/shared_slip.json instead of the opening.
	var plan := "full-network"
	if _company:
		scenario = _company
		_company = null
		plan = _plan
	elif not _args.has("full-network"):
		var file: String = "res://maps/%s.json" % _args["scenario"] if _args.has("scenario") else (
			scenario_path if scenario_path != "" else Scenario.OPENING)
		scenario = Scenario.load_file(file)
		plan = file.get_file().get_basename()
		_plan = plan
	# The authored islands' routes are planned once and kept (MapGenerator.route_cache_path).
	if not unsaved and _bought.is_empty():
		gen.route_cache_path = "res://maps/routes/%s-%s.json" % [MapLayout.MAIN_STORY.get_file().get_basename(), plan]
	elif not unsaved:
		# Bought sites: a network of the player's own, its routes kept out of the repo.
		gen.route_cache_path = "user://routes/%s-%s-%d.json" % [MapLayout.MAIN_STORY.get_file().get_basename(), plan, hash(JSON.stringify(_bought))]
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
	if not _clock.is_empty():
		sim.day = _clock[0]
		sim.minutes = _clock[1]
		_clock = []
	_site_pins = Node3D.new()
	add_child(_site_pins)
	if scenario and scenario.mission:
		var panel := MissionPanel.new()
		hud.root.add_child(panel)
		panel.setup(self, scenario.mission)


## Builds a terminal at `isl`'s locked dock site `k`: pays for it, then rebuilds
## the map with the company as it stands (terminals, schedules, cash and clock;
## boats start their day again from their first stops) and the new terminal in it.
func buy_dock(isl: MapData.Island, k: int) -> void:
	if isl.has_terminal or k < 0 or k >= isl.dock_sites.size():
		return
	var price := isl.dock_sites[k].price()
	if sim.available_cash < price:
		return
	var sc := sim.scenario
	sc.cash = sim.available_cash - price
	sc.terminals.append(isl.key)
	sc.docks[isl.key] = k
	sc.slips[isl.key] = [1]
	sc.tie_ups[isl.key] = []
	sc.lanes[isl.key] = 2
	_bought[isl.key] = k
	if sc.mission:
		sc.mission.carried_before = sc.mission.carried(sim)
	_company = sc
	_clock = [sim.day, sim.minutes]
	hud.show_toast("NEW TERMINAL", "Building %s's terminal at site %d. Planning its routes…" % [isl.name, k + 1], 4.0)
	await get_tree().process_frame
	await get_tree().process_frame
	rebuild()


## Pins the locked dock sites of `isl` (null: none), the shown one taller.
func show_dock_sites(isl: MapData.Island, shown: int) -> void:
	if _site_pins == null:
		return
	var key := "" if isl == null else "%s/%d" % [isl.key, shown]
	if _site_pins.get_meta("key", "") == key:
		return
	_site_pins.set_meta("key", key)
	for c in _site_pins.get_children():
		c.queue_free()
	if isl == null:
		return
	for i in isl.dock_sites.size():
		var site := isl.dock_sites[i]
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Hud.ACCENT if i == shown else Color(0.95, 0.95, 0.9)
		var pole := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 3.0
		cm.bottom_radius = 3.0
		cm.height = 60.0 if i == shown else 34.0
		pole.mesh = cm
		pole.material_override = mat
		pole.position = site.shore + Vector3(0, cm.height * 0.5 + 2.0, 0)
		_site_pins.add_child(pole)
		var bar := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(6, 3, Layout.DOCK_U + 40.0)
		bar.mesh = bm
		bar.material_override = mat
		bar.transform = Transform3D(Basis(Vector3.UP.cross(site.dir), Vector3.UP, site.dir), site.shore + site.dir * bm.size.z * 0.5 + Vector3(0, 3, 0))
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
