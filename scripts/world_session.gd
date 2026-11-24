@abstract
class_name WorldSession
extends Node3D
## Owns construction, live presentation and cancellation of one region.

var map: MapData
var terrain: Terrain
var _building_backdrop: Backdrop
var builder: WorldBuilder
var _slip_guide_parts := SlipGuidesView.MeshParts.new()
var sim: Simulation
## How the company starts (null: a boat on every planned route).
var scenario: Scenario
var rig: CameraRig
var hud: Hud
var sun: DirectionalLight3D
var env: Environment
var sky_mat: ShaderMaterial
var day_cycle: DayCycle
var clouds: CloudLayer
var water_mat: ShaderMaterial
var route_overlay: MeshInstance3D
var cetaceans: Cetaceans
var pinnipeds: Pinnipeds
var eagles: Eagles
var cam_attr: CameraAttributesPractical
var tree_shadows: Array[MultiMeshInstance3D] = []
var _tree_shadow_reach := -1.0

## Frame caps: the sim is slow-paced, so 60 fps is plenty, and nobody is watching
## when the window is in the background. Headless runs (soak tests) stay uncapped.
const MAX_FPS := 60
# By path, so the editor resolves it even before its class list catches up.
const RefitCrew := preload("res://scripts/world/slip_refit_crew.gd")
const BACKGROUND_FPS := 15
## Benchmarks render flat out regardless of focus.
var uncapped := false

## Set by LoadingScreen before the scene enters the tree: build the world over
## several frames, the heavy parts on a worker thread, so the loading screen keeps
## animating. Left off, startup builds everything at once (tools rely on that).
var async_build := false
## Data workers are joined before the scene releases their inputs.
var _data_thread: Thread
var _generating: MapGenerator
var _building_charts: MarineCharts
var _setup_frames := BuildFrameBudget.new()
## The stage being built runs from build_from to build_to (0..1 of the whole
## build); the loading screen sails the ferry between them.
var build_from := 0.0
var build_to := 0.0
## The world is fully built.
var built := false
signal world_ready


@abstract func intro(islands: int) -> Array
@abstract func regenerate() -> void


func start_generated(seed_value: int) -> void:
	var generator := MapGenerator.new()
	await _start_region(generator, generator.generate.bind(seed_value))


func start_authored(layout: MapLayout, opening: Scenario, route_cache_path: String) -> void:
	var generator := MapGenerator.new()
	generator.route_cache_path = route_cache_path
	scenario = opening
	var plan := opening.region_plan() if opening else null
	await _start_region(generator, generator.generate_from.bind(layout, plan))


func _start_region(gen: MapGenerator, generate: Callable) -> void:
	if not uncapped and DisplayServer.get_name() != "headless":
		Engine.max_fps = MAX_FPS
	set_process(false)
	var t0 := Time.get_ticks_msec()
	# Stage ends are measured shares of the build (main map, threaded: ~4.1 s generate,
	# ~5.6 s world, ~1.3 s sea charts, ~0.6 s simulation, ~2.1 s backdrop).
	_generating = gen
	await _data_stage(0.3, generate)
	_generating = null
	if not is_inside_tree():
		return
	map = gen.map
	terrain = gen.terrain
	_setup_environment()
	# Tree stand-ins read imported mesh surfaces. Populate their shared cache
	# before assembling the world and backdrop.
	if async_build:
		Models.tree_variants(false)
		Models.tree_variants(true)
	builder = WorldBuilder.new(map, terrain)
	build_from = build_to
	build_to = 0.71
	var world := await builder.build(get_tree().process_frame if async_build else Signal())
	if world == null:
		return
	# Finish the backdrop while its tree meshes are still off the live render tree.
	build_from = build_to
	build_to = 0.855
	var backdrop := Backdrop.new()
	_building_backdrop = backdrop
	var backdrop_ready := await backdrop.setup(terrain, builder, get_tree().process_frame if async_build else Signal())
	_building_backdrop = null
	if not backdrop_ready:
		world.free()
		return
	add_child(world)
	add_child(backdrop)
	route_overlay = builder.route_overlay
	tree_shadows = builder.tree_shadows
	water_mat = builder.water_material
	print("Map %d built in %d ms: %d islands, %d routes" % [map.map_seed, Time.get_ticks_msec() - t0, map.islands.size(), map.routes.size()])

	rig = CameraRig.new()
	rig.terrain = terrain
	rig.bounds = map.half_size * 0.8
	add_child(rig)
	_setup_dof()
	var charts := MarineCharts.new(map, terrain)
	_building_charts = charts
	await _data_stage(0.95, charts.build)
	_building_charts = null
	if not is_inside_tree():
		return
	# Scene-owned nodes can now be attached in batches without advancing the
	# clock, vessels or presentation before the first playable frame.
	build_from = build_to
	build_to = 0.99
	var previous_mode := process_mode
	process_mode = Node.PROCESS_MODE_DISABLED
	_setup_frames.start(get_tree().process_frame if async_build else Signal())
	await _setup_simulation(charts)
	_setup_frames.finish()
	if _setup_frames.cancelled:
		return
	process_mode = previous_mode
	set_process(true)
	build_from = 1.0
	build_to = 1.0
	built = true
	world_ready.emit()
	Music.set_mood(get_tree(), Music.Mood.SOFT)
	RadioChatter.on_game(get_tree())
	UiSounds.install(get_tree())


func _setup_simulation(charts: MarineCharts) -> void:
	sim = Simulation.new(VehicleFactory.create, Models.mid_slip, Models.mid_slip_guides)
	sim.name = "Simulation"
	add_child(sim)
	# The rest of the simulation spawns nodes into the live tree, so it stays on the
	# main thread.
	await sim.setup(map, terrain, scenario, charts, _setup_frames)
	sim.routes_changed.connect(builder.rebuild_route_overlay)
	if not await _setup_frames.can_continue():
		return
	for ferry in sim.ferries:
		_add_ferry_view(ferry)
		if not await _setup_frames.can_continue():
			return
	sim.ferry_added.connect(_add_ferry_view)
	for terminal: Terminal in sim.terminals.values():
		_dress_terminal(terminal)
		if not await _setup_frames.can_continue():
			return
	sim.terminal_opened.connect(_on_terminal_opened)
	clouds = CloudLayer.new()
	clouds.setup(sim.weather, sim.wind_from(), sim.wind_speed)
	add_child(clouds)
	var grass := Grass.new()
	grass.setup(terrain, builder, rig, sim)
	add_child(grass)
	if not await _setup_frames.can_continue():
		return
	day_cycle = DayCycle.new()
	day_cycle.name = "DayCycle"
	day_cycle.sim = sim
	day_cycle.sun = sun
	day_cycle.env = env
	day_cycle.sky_mat = sky_mat
	day_cycle.water_mat = water_mat
	add_child(day_cycle)
	var wakes := WakeField.new()
	wakes.name = "WakeField"
	wakes.sim = sim
	wakes.water_mat = water_mat
	add_child(wakes)
	var lights := NightLights.new()
	add_child(lights)
	lights.setup(sim, rig, day_cycle, builder.night_lights)
	sim.marine.vessel_registered.connect(_dress_vessel.bind(lights))
	for vessel in sim.marine.vessels:
		_dress_vessel(vessel, lights)
		if not await _setup_frames.can_continue():
			return
	var gulls := Seagulls.new()
	add_child(gulls)
	for terminal: Terminal in sim.terminals.values():
		for guide in terminal.slip_guides:
			if guide:
				builder.add_slip_perches(guide)
	gulls.setup(sim, day_cycle, builder.gull_perches)
	if not await _setup_frames.can_continue():
		return
	var ambience := Ambience.new()
	ambience.name = "Ambience"
	ambience.setup(rig, gulls, day_cycle, builder)
	add_child(ambience)
	eagles = Eagles.new()
	add_child(eagles)
	eagles.setup(sim.wildlife, day_cycle, builder.eagle_perches, gulls)
	cetaceans = Cetaceans.new()
	add_child(cetaceans)
	cetaceans.setup(sim.wildlife, terrain)
	pinnipeds = Pinnipeds.new()
	add_child(pinnipeds)
	pinnipeds.setup(sim.wildlife, terrain, water_mat)
	day_cycle.apply(sim.hour())
	hud = Hud.new()
	add_child(hud)
	hud.setup(self)


## Run data preparation on the worker during Play, or inline for direct loads.
func _data_stage(to: float, work: Callable) -> void:
	if not async_build:
		work.call()
		return
	build_from = build_to
	build_to = to
	var thread := Thread.new()
	_data_thread = thread
	if thread.start(work) != OK:
		_data_thread = null
		work.call()
		return
	while thread.is_alive():
		await get_tree().process_frame
	if thread.is_started():
		thread.wait_to_finish()
	_data_thread = null


func _exit_tree() -> void:
	_setup_frames.cancel()
	if _building_backdrop != null:
		# Let setup unwind before disposing of the node receiving cancel_build.
		var pending := _building_backdrop
		pending.cancel_build()
		pending.free()
	if builder != null:
		builder.cancel_build()
	if _generating != null:
		_generating.cancel()
	if _building_charts != null:
		_building_charts.cancel()
	if _data_thread != null and _data_thread.is_started():
		_data_thread.wait_to_finish()


## The wildlife group whose animal is nearest `screen` (and showing), if any.
func pick_wildlife(screen: Vector2, cam: Camera3D) -> Wildlife.Visit:
	var v := cetaceans.pick(screen, cam)
	if v == null:
		v = pinnipeds.pick(screen, cam)
	return v if v else eagles.pick(screen, cam)


func _setup_environment() -> void:
	# Colours, ambient, fog and sun direction are driven per frame by DayCycle.
	sky_mat = ShaderMaterial.new()
	sky_mat.shader = load("res://shaders/sky.gdshader")
	var sky := Sky.new()
	sky.sky_material = sky_mat
	# DayCycle changes the sky every game minute or so; spread each radiance
	# re-render over several frames instead of doing it all at once.
	sky.process_mode = Sky.PROCESS_MODE_INCREMENTAL
	env = Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_exposure = 1.0
	env.ssao_enabled = true
	env.ssao_radius = 7.5
	env.ssao_intensity = 1.6
	env.glow_enabled = true
	env.glow_intensity = 0.25
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color(0.74, 0.82, 0.88)
	env.fog_density = 0.85
	env.fog_depth_begin = 1800.0
	env.fog_depth_end = 4800.0
	# The sky draws its own haze (sky.gdshader); fogging it over washed out the
	# horizon clouds and flattened the gradient.
	env.fog_sky_affect = 0.15
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.12
	# Thin volumetric haze so sunlight scatters and cloud shadows read as shafts.
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.0004
	env.volumetric_fog_anisotropy = 0.6
	env.volumetric_fog_ambient_inject = 0.1
	env.volumetric_fog_sky_affect = 0.15
	env.volumetric_fog_temporal_reprojection_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -35, 0)
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	sun.shadow_blur = 1.5
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 1200.0
	# Shadows thin out over the last 40% of their range rather than ending in a line.
	sun.directional_shadow_fade_start = 0.6
	add_child(sun)


func _notification(what: int) -> void:
	if uncapped or DisplayServer.get_name() == "headless":
		return
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		Engine.max_fps = BACKGROUND_FPS
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		Engine.max_fps = MAX_FPS


func _process(_delta: float) -> void:
	# Keep shadows crisp and fog sensible at every zoom level. Zoomed in, the first
	# cascade reaches just past the point looked at, so whatever the player is looking
	# at gets the finest shadow texels (~3 cm: fine enough for rails); zoomed out,
	# Godot's default splits.
	var d := rig.distance
	var shadow_far := clampf(d * 2.6, 360.0, 3600.0)
	var close := smoothstep(320.0, 160.0, d)
	var near := lerpf(0.1, clampf(d * 1.3 / shadow_far, 0.1, 0.3), close)
	sun.directional_shadow_max_distance = shadow_far
	sun.directional_shadow_split_1 = near
	sun.directional_shadow_split_2 = lerpf(0.2, near * 2.0, close)
	sun.directional_shadow_split_3 = lerpf(0.5, maxf(0.5, near * 3.5), close)
	# Tree shadows reach as far as the cascades do, so they fade out with the sun's
	# shadow (directional_shadow_fade_start) instead of popping tile by tile as the
	# camera pans.
	var reach := shadow_far * 1.05
	if absf(reach - _tree_shadow_reach) > _tree_shadow_reach * 0.03:
		_tree_shadow_reach = reach
		for t in tree_shadows:
			t.visibility_range_end = reach
	# Fog by distance past the point looked at, not a multiple of the zoom: the
	# camera's depth to anything out there grows ~1:1 with zoom, so a fixed offset
	# keeps the far shores equally hazy at every zoom instead of fogging them out
	# as the camera comes in. It starts past the far bank, so the shores across the
	# water stay crisp; the Backdrop's blue haze (haze.gdshaderinc) handles the
	# ranges behind.
	env.fog_depth_begin = rig.distance + 4000.0
	env.fog_depth_end = rig.distance + 18000.0
	RenderingServer.global_shader_parameter_set("fog_range", Vector2(env.fog_depth_begin, env.fog_depth_end))
	env.volumetric_fog_length = clampf(rig.distance * 2.4, 750.0, 4800.0)
	_update_dof()


## Miniature-style depth of field: the point the camera looks at is sharp, the
## foreground at the bottom of the screen and the far islands soften a little.
func _setup_dof() -> void:
	cam_attr = CameraAttributesPractical.new()
	cam_attr.dof_blur_amount = 0.06
	var on := str(Scenes.launch_options.values.get("dof", "1")) != "0"
	cam_attr.dof_blur_near_enabled = on
	cam_attr.dof_blur_far_enabled = on
	rig.camera.attributes = cam_attr


func _update_dof() -> void:
	# Focus on the orbit target; distances scale with zoom so the look holds at every height.
	var d := rig.camera.global_position.distance_to(rig.position)
	cam_attr.dof_blur_near_distance = d * 0.6
	cam_attr.dof_blur_near_transition = d * 0.4
	cam_attr.dof_blur_far_distance = d * 1.5
	cam_attr.dof_blur_far_transition = d * 2.0


func _dress_vessel(vessel: Vessel, lights: NightLights) -> void:
	if vessel.spec == null:
		return
	var hull := VesselHullView.new(vessel)
	vessel.add_child(hull)
	var lamps := lights.fit_vessel(vessel)
	if vessel is FishingBoat:
		vessel.add_child(FishingBoatView.new(vessel, lamps))
	elif vessel is MotorYacht:
		vessel.add_child(MotorYachtView.new(vessel, lamps))
	elif vessel is Sailboat:
		hull.add_child(SailboatView.new(vessel, hull))
	elif vessel is PilotBoat:
		hull.add_child(PilotLadder.new(vessel))


func _add_ferry_view(ferry: Ferry) -> void:
	ferry.add_child(FerryView.new(ferry))


## The crews and lane views a terminal's purchases show with.
func _dress_terminal(terminal: Terminal) -> void:
	for i in terminal.slip_ramps.size():
		_dress_slip(terminal, i)
	if RefitCrew.available():
		var crew := RefitCrew.new()
		terminal.add_child(crew)
		crew.setup(terminal)
	if terminal.town.lane_extension_price > 0:
		var extension := HoldingLaneView.new()
		terminal.add_child(extension)
		extension.setup(terminal)
	terminal.slip_built.connect(_on_slip_built.bind(terminal))
	terminal.seabed_dredged.connect(builder.rebuild_terrain)


## A slip bought at `terminal` is built: it goes into the world where it stands.
func _on_slip_built(i: int, terminal: Terminal) -> void:
	_dress_slip(terminal, i)
	builder.build_bought_slip(terminal.town, i)
	hud.show_toast("SLIP OPEN", "%s's new %s is in use." % [terminal.town.name, "tie-up slip" if terminal.town.slips[i].tie_up else "working slip"], 5.0)


func _dress_slip(terminal: Terminal, i: int) -> void:
	var ramp := terminal.slip_ramps[i]
	if ramp:
		ramp.add_child(SlipRampView.new(ramp))
	var guide := terminal.slip_guides[i]
	if guide:
		guide.add_child(SlipGuidesView.new(guide, terrain, _slip_guide_parts))
		builder.add_slip_guide_lights(guide)


## A terminal bought in play finished building: it was in the world all along,
## hidden, so it only has to show (TID-319).
func _on_terminal_opened(terminal: Terminal) -> void:
	builder.show_terminal(terminal.town)
	_dress_terminal(terminal)
	hud.refresh_labels()
	hud.show_toast("TERMINAL OPEN", "%s's terminal is open. Edit a boat's stops to call there." % terminal.town.name, 6.0)
