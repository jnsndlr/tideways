class_name TownConstruction
extends Node3D
## Spawns animated construction sites when TownGrowth starts a building job,
## drives their staged animations (house framing crew & tower crane), and swaps
## in the finished house, commercial storefront, or milestone landmark on completion.

const HOUSE_SITE_PATH := "res://assets/models/house_construction_site.glb"
const COMMERCIAL_SITE_PATH := "res://assets/models/construction_site.glb"
const WINDSOCK_PATH := "res://assets/models/windsock.glb"

static var _house_site_scene: PackedScene
static var _commercial_site_scene: PackedScene
static var _windsock_scene: PackedScene
static var _scenes_loaded := false

var sim: Simulation
var builder: WorldBuilder
var _active := {}  # job.id -> ActiveSite
var _windsocks: Array[Node3D] = []
var _anim_time := 0.0


class ActiveSite:
	var job: TownGrowth.BuildJob
	var root: Node3D
	var is_house := true
	var parts := {}  # String -> Node3D


static func _ensure_scenes() -> void:
	if _scenes_loaded:
		return
	_scenes_loaded = true
	if ResourceLoader.exists(HOUSE_SITE_PATH):
		_house_site_scene = load(HOUSE_SITE_PATH) as PackedScene
	if ResourceLoader.exists(COMMERCIAL_SITE_PATH):
		_commercial_site_scene = load(COMMERCIAL_SITE_PATH) as PackedScene
	if ResourceLoader.exists(WINDSOCK_PATH):
		_windsock_scene = load(WINDSOCK_PATH) as PackedScene


func setup(simulation: Simulation, world_builder: WorldBuilder) -> void:
	sim = simulation
	builder = world_builder
	_ensure_scenes()
	if sim != null and sim.town_growth != null:
		if not sim.town_growth.construction_started.is_connected(_on_construction_started):
			sim.town_growth.construction_started.connect(_on_construction_started)
		if not sim.town_growth.construction_completed.is_connected(_on_construction_completed):
			sim.town_growth.construction_completed.connect(_on_construction_completed)


func _on_construction_started(job: TownGrowth.BuildJob) -> void:
	if job == null or job.lot == null or _active.has(job.id):
		return
	var lot := job.lot
	var is_house := job.kind == MapData.TownLot.Kind.HOUSE
	var half_w := 7.0 if is_house else 11.5
	var half_d := 5.5 if is_house else 8.5
	if job.landmark_model == "airplane_hangar_low":
		half_w = 13.0
		half_d = 12.0
	if builder != null:
		_level_lot_runtime(lot.pos, lot.yaw, half_w, half_d, lot.lot_y)

	var scene: PackedScene = _house_site_scene if is_house else _commercial_site_scene
	if scene == null:
		return
	var inst := scene.instantiate() as Node3D
	if inst == null:
		return
	inst.position = Vector3(lot.pos.x, lot.lot_y, lot.pos.z)
	inst.rotation.y = lot.yaw
	add_child(inst)

	var site := ActiveSite.new()
	site.job = job
	site.root = inst
	site.is_house = is_house
	if is_house:
		_cache_parts(
			site,
			[
				"Stage1_Foundation",
				"Stage2_FloorDeck",
				"Wall_Back",
				"Wall_Front",
				"Wall_Left",
				"Wall_Right",
				"Wall_InteriorAndPorch",
				"Stage4_UpperFrameAndGables",
				"Stage5a_TrussesLeft",
				"Stage5b_TrussesRight",
				"Stage5c_PorchRoof",
				"Mixer_Drum",
				"Mixer_Tilt",
				"Scaffold",
				"Worker_1_ArmL",
				"Worker_1_ArmR",
				"Worker_2_ArmL",
				"Worker_2_ArmR",
				"Pile_ConcreteBags",
				"Pile_LumberStack",
				"Pile_PlywoodSheets",
				"Pile_RoofLumber",
			]
		)
	else:
		_cache_parts(
			site,
			[
				"Stage1_Foundation",
				"Stage2_FloorDeck",
				"Stage3_FirstFloorWalls",
				"Stage4_UpperFrameAndGables",
				"Stage5_RoofTrusses",
				"Crane_Jib",
				"Crane_Trolley",
				"Crane_Cable",
				"Crane_Hook",
				"Crane_Payload_Frame",
				"Pile_ConcreteBlocks",
				"Pile_LumberStack_1",
				"Pile_LumberStack_2",
				"Pile_PlywoodSheets",
				"Pile_PrefabFrames",
			]
		)
	_active[job.id] = site
	_apply_site_animation(site, 0.0, 0.0)


func _cache_parts(site: ActiveSite, names: Array[String]) -> void:
	for n in names:
		var node := site.root.find_child(n, true, false) as Node3D
		if node != null:
			site.parts[n] = node


func _on_construction_completed(job: TownGrowth.BuildJob) -> void:
	if job == null:
		return
	if _active.has(job.id):
		var site: ActiveSite = _active[job.id]
		_active.erase(job.id)
		if is_instance_valid(site.root):
			site.root.queue_free()
	if job.lot != null:
		_spawn_finished_building(job)


func _process(delta: float) -> void:
	if not _windsocks.is_empty() and sim != null:
		var wind_y := sim.wind_yaw()
		for ws in _windsocks:
			if is_instance_valid(ws):
				ws.rotation.y = wind_y
	if _active.is_empty():
		return
	_anim_time += delta
	for site: ActiveSite in _active.values():
		if is_instance_valid(site.root):
			_apply_site_animation(site, site.job.progress(), _anim_time)


func _apply_site_animation(site: ActiveSite, p: float, t: float) -> void:
	if site.is_house:
		_animate_house_site(site.parts, p, t)
	else:
		_animate_commercial_site(site.parts, p)


func _animate_house_site(parts: Dictionary, p: float, t: float) -> void:
	_pop_stage(parts.get("Stage1_Foundation"), p, 0.05, 0.16)
	_pop_stage(parts.get("Stage2_FloorDeck"), p, 0.20, 0.30)

	_tilt_wall(parts.get("Wall_Back"), p, 0.34, 0.42, Vector3(deg_to_rad(86.0), 0.0, 0.0))
	_tilt_wall(parts.get("Wall_Left"), p, 0.42, 0.49, Vector3(0.0, 0.0, deg_to_rad(-86.0)))
	_tilt_wall(parts.get("Wall_Right"), p, 0.49, 0.56, Vector3(0.0, 0.0, deg_to_rad(86.0)))
	_tilt_wall(parts.get("Wall_Front"), p, 0.56, 0.62, Vector3(deg_to_rad(-86.0), 0.0, 0.0))
	_pop_stage(parts.get("Wall_InteriorAndPorch"), p, 0.60, 0.66)

	_pop_stage(parts.get("Stage4_UpperFrameAndGables"), p, 0.66, 0.76)
	_pop_stage(parts.get("Stage5a_TrussesLeft"), p, 0.78, 0.85)
	_pop_stage(parts.get("Stage5b_TrussesRight"), p, 0.85, 0.91)
	_pop_stage(parts.get("Stage5c_PorchRoof"), p, 0.91, 0.98)

	_set_vis(parts.get("Pile_ConcreteBags"), p < 0.18)
	_set_vis(parts.get("Pile_LumberStack"), p < 0.58)
	_set_vis(parts.get("Pile_PlywoodSheets"), p < 0.76)
	_set_vis(parts.get("Pile_RoofLumber"), p < 0.93)
	_set_vis(parts.get("Scaffold"), p >= 0.62)

	var drum: Node3D = parts.get("Mixer_Drum")
	if drum != null and p < 0.28:
		drum.rotation.y = t * 5.0
	var tilt: Node3D = parts.get("Mixer_Tilt")
	if tilt != null:
		tilt.rotation.x = deg_to_rad(-28.0 + (22.0 * sin(t * 2.4) if p < 0.22 else 0.0))

	# Workers hammer and raise arms actively throughout construction.
	var hammer_a := deg_to_rad(55.0 + 42.0 * sin(t * 9.0))
	var hammer_b := deg_to_rad(50.0 + 38.0 * sin(t * 8.2 + 1.4))
	var arm1r: Node3D = parts.get("Worker_1_ArmR")
	if arm1r != null:
		arm1r.rotation.x = hammer_a
	var arm2r: Node3D = parts.get("Worker_2_ArmR")
	if arm2r != null:
		arm2r.rotation.x = hammer_b
	var lifting := p >= 0.34 and p <= 0.63
	var arm1l: Node3D = parts.get("Worker_1_ArmL")
	if arm1l != null:
		arm1l.rotation.x = deg_to_rad(95.0) if lifting else deg_to_rad(18.0 * sin(t * 4.5))
	var arm2l: Node3D = parts.get("Worker_2_ArmL")
	if arm2l != null:
		arm2l.rotation.x = deg_to_rad(95.0) if lifting else deg_to_rad(18.0 * cos(t * 4.1))


func _animate_commercial_site(parts: Dictionary, p: float) -> void:
	_pop_stage(parts.get("Stage1_Foundation"), p, 0.14, 0.20)
	_pop_stage(parts.get("Stage2_FloorDeck"), p, 0.34, 0.40)
	_pop_stage(parts.get("Stage3_FirstFloorWalls"), p, 0.54, 0.60)
	_pop_stage(parts.get("Stage4_UpperFrameAndGables"), p, 0.74, 0.80)
	_pop_stage(parts.get("Stage5_RoofTrusses"), p, 0.90, 0.97)

	_set_vis(parts.get("Pile_ConcreteBlocks"), p < 0.12)
	_set_vis(parts.get("Pile_LumberStack_1"), p < 0.32)
	_set_vis(parts.get("Pile_PrefabFrames"), p < 0.52)
	_set_vis(parts.get("Pile_LumberStack_2"), p < 0.72)
	_set_vis(parts.get("Pile_PlywoodSheets"), p < 0.88)

	# 5 synchronized crane pick-and-place cycles (one per building stage).
	var cycle := fmod(p * 5.0, 1.0)
	var jib_deg := -108.0
	var trolley_x := 7.2
	var drop := 3.4
	var carrying := false
	if cycle < 0.18:
		var u := smoothstep(0.0, 0.18, cycle)
		jib_deg = lerpf(-108.0, -104.0, u)
		trolley_x = 7.4
		drop = lerpf(3.4, 7.2, u)
	elif cycle < 0.32:
		var u := smoothstep(0.18, 0.32, cycle)
		jib_deg = -104.0
		trolley_x = 7.4
		drop = lerpf(7.2, 3.2, u)
		carrying = true
	elif cycle < 0.60:
		var u := smoothstep(0.32, 0.60, cycle)
		jib_deg = lerpf(-104.0, -16.0, u)
		trolley_x = lerpf(7.4, 5.6, u)
		drop = 3.2
		carrying = true
	elif cycle < 0.74:
		var u := smoothstep(0.60, 0.74, cycle)
		jib_deg = -16.0
		trolley_x = 5.6
		drop = lerpf(3.2, 6.4, u)
		carrying = true
	elif cycle < 0.84:
		var u := smoothstep(0.74, 0.84, cycle)
		jib_deg = -16.0
		trolley_x = 5.6
		drop = lerpf(6.4, 3.4, u)
	else:
		var u := smoothstep(0.84, 1.0, cycle)
		jib_deg = lerpf(-16.0, -108.0, u)
		trolley_x = lerpf(5.6, 7.2, u)
		drop = 3.4

	var jib: Node3D = parts.get("Crane_Jib")
	if jib != null:
		jib.rotation.y = deg_to_rad(jib_deg)
	var trolley: Node3D = parts.get("Crane_Trolley")
	if trolley != null:
		trolley.position.x = trolley_x
	var cable: Node3D = parts.get("Crane_Cable")
	if cable != null:
		cable.scale.y = maxf(drop, 0.5)
	var hook: Node3D = parts.get("Crane_Hook")
	if hook != null:
		hook.position.y = -0.16 - drop
	_set_vis(parts.get("Crane_Payload_Frame"), carrying)


func _pop_stage(node: Node3D, p: float, p0: float, p1: float) -> void:
	if node == null:
		return
	if p < p0:
		node.visible = false
		return
	node.visible = true
	var u := clampf((p - p0) / maxf(p1 - p0, 0.01), 0.0, 1.0)
	node.scale.y = lerpf(0.05, 1.0, smoothstep(0.0, 1.0, u))


func _tilt_wall(node: Node3D, p: float, p0: float, p1: float, flat_rot: Vector3) -> void:
	if node == null:
		return
	if p < p0:
		node.visible = false
		return
	node.visible = true
	var u := clampf((p - p0) / maxf(p1 - p0, 0.01), 0.0, 1.0)
	var s := smoothstep(0.0, 1.0, u)
	node.rotation = flat_rot.lerp(Vector3.ZERO, s)


func _set_vis(node: Node3D, vis: bool) -> void:
	if node != null:
		node.visible = vis


func _spawn_finished_building(job: TownGrowth.BuildJob) -> void:
	if builder == null:
		return
	var lot := job.lot
	var basis := Basis(Vector3.UP, lot.yaw).scaled(Vector3.ONE * lot.scale)
	var xf := Transform3D(basis, Vector3(lot.pos.x, lot.lot_y, lot.pos.z))

	match job.kind:
		MapData.TownLot.Kind.HOUSE:
			if builder.house_meshes.is_empty():
				return
			var idx := absi(lot.variant) % builder.house_meshes.size()
			var mi := MeshInstance3D.new()
			mi.mesh = builder.house_meshes[idx]
			mi.transform = xf
			add_child(mi)
			var kit_name := builder.house_kit_names[idx]
			var lamp := Models.kit_marker(kit_name, "PorchLight")
			var entry := Models.kit_marker(kit_name, "Entry")
			_add_runtime_building_light(
				xf,
				lamp + Vector3(0, 0, 0.08),
				GlowBuilder.WARM,
				0.22,
				lot.waterfront,
				Vector3(lamp.x, entry.y + 0.05, entry.z - 0.6)
			)

		MapData.TownLot.Kind.COMMERCIAL:
			if builder.shop_meshes.is_empty():
				return
			var idx := absi(lot.variant) % builder.shop_meshes.size()
			var mi := MeshInstance3D.new()
			mi.mesh = builder.shop_meshes[idx]
			mi.transform = xf
			add_child(mi)
			var shop_name := builder.shop_names_list[idx]
			var front_z: float = WorldBuilder.SHOP_SHELLS[shop_name].y * 0.5
			if shop_name == "glass_hall":
				front_z += 0.46
			_add_runtime_building_light(
				xf,
				Vector3(0.83, 2.59, front_z + 0.38),
				GlowBuilder.WARM,
				0.22,
				lot.waterfront,
				Vector3(0.83, 0.39, front_z + 0.04)
			)

		MapData.TownLot.Kind.LANDMARK:
			var model_name := (
				job.landmark_model if not job.landmark_model.is_empty() else "city_hall"
			)
			var mesh := builder.landmarks.mesh_for(model_name)
			if mesh != null:
				var mi := MeshInstance3D.new()
				mi.name = "Landmark_%s_%d" % [model_name, job.id]
				mi.mesh = mesh
				mi.transform = xf
				add_child(mi)
			if model_name == "airplane_hangar_low":
				_spawn_windsock(xf)
				_add_runtime_building_light(
					xf, Vector3(0.0, 9.2, 7.8), GlowBuilder.WARM, 0.35, lot.waterfront
				)
			elif model_name == "observatory":
				_add_runtime_building_light(
					xf, Vector3(0.0, 3.0, 4.6), GlowBuilder.WARM, 0.28, lot.waterfront
				)
			else:
				_add_runtime_building_light(
					xf, Vector3(0.0, 3.0, 4.2), GlowBuilder.WARM, 0.26, lot.waterfront
				)

		MapData.TownLot.Kind.RADIO_TOWER:
			var mesh := builder.landmarks.mesh_for("radio_tower")
			if mesh != null:
				var mi := MeshInstance3D.new()
				mi.name = "RadioTower_%d" % job.island_id
				mi.mesh = mesh
				mi.transform = xf
				add_child(mi)
			_add_runtime_building_light(
				xf, Vector3(0.0, 55.2, 0.0), Color(1.0, 0.22, 0.16), 0.75, false
			)


func _spawn_windsock(hangar_xf: Transform3D) -> void:
	if _windsock_scene == null:
		return
	var ws := _windsock_scene.instantiate() as Node3D
	if ws == null:
		return
	var world_pos := hangar_xf * Vector3(13.5, 0.0, 7.0)
	if builder != null and builder.terrain != null:
		world_pos.y = builder.terrain.height_at(world_pos.x, world_pos.z)
	ws.position = world_pos
	if sim != null:
		ws.rotation.y = sim.wind_yaw()
	add_child(ws)
	var anim := ws.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if anim != null:
		var list := anim.get_animation_list()
		if not list.is_empty():
			var a := anim.get_animation(list[0])
			if a != null:
				a.loop_mode = Animation.LOOP_LINEAR
			anim.play(list[0])
	_windsocks.append(ws)


## Levels a single building lot in play and updates the affected builder.terrain tile(s).
func _level_lot_runtime(
	pos: Vector3, yaw: float, half_w: float, half_d: float, target_y: float
) -> void:
	if builder.terrain == null:
		return
	var dir := Vector3(sin(yaw), 0.0, cos(yaw))
	builder.terrain.level_now(
		Vector3(pos.x, 0.0, pos.z),
		dir,
		-half_d - WorldBuilder.KIT_LOT_MARGIN,
		half_d + WorldBuilder.KIT_LOT_MARGIN,
		-half_w - WorldBuilder.KIT_LOT_MARGIN,
		half_w + WorldBuilder.KIT_LOT_MARGIN,
		target_y,
		WorldBuilder.KIT_LOT_BLEND
	)
	var reach := (
		maxf(half_w, half_d) + WorldBuilder.KIT_LOT_MARGIN + WorldBuilder.KIT_LOT_BLEND + 2.0
	)
	var i0 := clampi(
		floori((pos.x - reach + builder.terrain.half_size) / Terrain.CELL), 0, builder.terrain.n
	)
	var i1 := clampi(
		ceili((pos.x + reach + builder.terrain.half_size) / Terrain.CELL), 0, builder.terrain.n
	)
	var j0 := clampi(
		floori((pos.z - reach + builder.terrain.half_size) / Terrain.CELL), 0, builder.terrain.n
	)
	var j1 := clampi(
		ceili((pos.z + reach + builder.terrain.half_size) / Terrain.CELL), 0, builder.terrain.n
	)
	builder.rebuild_terrain(Rect2i(i0, j0, maxi(1, i1 - i0), maxi(1, j1 - j0)))


## Adds a night glow (entry lamp or tower beacon) for a building constructed at runtime.
func _add_runtime_building_light(
	xf: Transform3D,
	local_pos: Vector3,
	color: Color,
	radius: float,
	waterfront := false,
	pool_pos := Vector3.INF
) -> void:
	if builder.night_lights == null:
		return
	var g := GlowBuilder.new()
	g.xform = xf
	g.glow(
		local_pos, color, radius, radius * 16.0, waterfront, 0.0, Vector3.ZERO, Models.LAMP_ON_AT
	)
	if pool_pos != Vector3.INF:
		g.pool(pool_pos, color, 4.5, 0.3)
	var mesh := g.commit()
	if mesh == null:
		return
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	builder.night_lights.add_child(mi)
