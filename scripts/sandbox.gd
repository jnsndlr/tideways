extends Node3D
## Entry point: generate a map, build the 3D world, start the simulation, add the HUD.
##
## Debug args (after `--` on the command line):
##   --seed=N  --speed=0..3  --cam=x,z,dist,yaw_deg,pitch_deg  --select=K (Kth terminal island)
##   --follow=K (Kth ferry)  --time=H (pin time of day, e.g. 19.5)  --shot=path.png  --shot-delay=seconds
##   --bench=seconds (print frame/GPU time and render stats, then quit)
##   --orcas (start an orca visit now and follow it)  --wildlife=ID (the same for any species:
##     humpback, gray, sea_lion, dalls_porpoise, harbor_porpoise, harbor_seal)
##   --vessel=cargo|sail|yacht|pilot|tug (follow a cargo ship, a sailboat under way, a
##     motor yacht, a pilot boat or a tug)
##   --aa=msaa|smaa|none (anti-aliasing, to compare)  --dof=0 (no depth-of-field blur)

static var map_seed := 0

var map: MapData
var terrain: Terrain
var builder: WorldBuilder
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
var _args := {}

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
## animating. Left off, _ready builds everything at once (tools rely on that).
var async_build := false
## Generation only uses region data, so it can finish while the scene exits.
var _generation_thread: Thread
## The stage being built runs from build_from to build_to (0..1 of the whole
## build); the loading screen sails the ferry between them.
var build_from := 0.0
var build_to := 0.0
## The world is fully built.
var built := false
signal world_ready


func _ready() -> void:
	_parse_args()
	if not uncapped and DisplayServer.get_name() != "headless":
		Engine.max_fps = MAX_FPS
	set_process(false)
	var t0 := Time.get_ticks_msec()
	var gen := MapGenerator.new()
	# Stage ends are measured shares of the build (main map, threaded: ~4.1 s generate,
	# ~5.6 s world, ~1.3 s sea charts, ~0.6 s simulation, ~2.1 s backdrop).
	if async_build:
		_generation_thread = Thread.new()
	await _stage(0.3, true, _generation_job(gen), _generation_thread)
	_generation_thread = null
	if not is_inside_tree():
		return
	map = gen.map
	terrain = gen.terrain
	_setup_environment()
	# Tree stand-ins read imported mesh surfaces. Populate their shared cache
	# on the rendering thread before the worker starts placing instances.
	if async_build:
		Models.tree_variants(false)
		Models.tree_variants(true)
	builder = WorldBuilder.new(map, terrain)
	var world := []  # lambdas capture locals by value; the array carries the result out
	await _stage(0.71, true, func(): world.append(builder.build()))
	# Finish the backdrop while its tree meshes are still off the live render tree.
	var backdrop := Backdrop.new()
	await _stage(0.855, true, func(): backdrop.setup(terrain, builder))
	add_child(world[0])
	add_child(backdrop)
	route_overlay = builder.route_overlay
	tree_shadows = builder.tree_shadows
	var fixed_lights := builder.night_lights
	water_mat = builder.water_material
	print("Map %d built in %d ms: %d islands, %d routes" % [map.map_seed, Time.get_ticks_msec() - t0, map.islands.size(), map.routes.size()])

	rig = CameraRig.new()
	rig.terrain = terrain
	rig.bounds = map.half_size * 0.8
	add_child(rig)
	_setup_dof()
	sim = Simulation.new()
	sim.name = "Simulation"
	# Marine traffic's charts (nav grid, fishing grounds, anchorages) are pure data.
	sim.map = map
	sim.terrain = terrain
	sim.marine = MarineTraffic.new()
	await _stage(0.95, true, func(): sim.marine.prepare(sim))
	sim.process_mode = Node.PROCESS_MODE_DISABLED
	add_child(sim)
	# The rest of the simulation spawns nodes into the live tree, so it stays on the
	# main thread.
	await _stage(0.99, false, func(): sim.setup(map, terrain, scenario))
	for terminal: Terminal in sim.terminals.values():
		if RefitCrew.available():
			var crew := RefitCrew.new()
			terminal.add_child(crew)
			crew.setup(terminal)
		if terminal.island.lane_extension_price > 0:
			var extension := HoldingLaneView.new()
			terminal.add_child(extension)
			extension.setup(terminal)
	clouds = CloudLayer.new()
	clouds.setup(sim.weather, sim.wind_from(), sim.wind_speed)
	add_child(clouds)
	var grass := Grass.new()
	grass.setup(terrain, builder, rig, sim)
	add_child(grass)
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
	lights.setup(sim, rig, day_cycle, fixed_lights)
	var gulls := Seagulls.new()
	add_child(gulls)
	for terminal: Terminal in sim.terminals.values():
		for g in terminal.slip_guides:
			if g:
				g.add_perches(builder.gull_perches, builder.eagle_perches)
	gulls.setup(sim, day_cycle, builder.gull_perches)
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
	sim.process_mode = Node.PROCESS_MODE_INHERIT
	_apply_debug_args()
	set_process(true)
	build_from = 1.0
	build_to = 1.0
	built = true
	world_ready.emit()
	Music.set_mood(get_tree(), Music.Mood.SOFT)
	RadioChatter.on_game(get_tree())
	UiSounds.install(get_tree())


## Runs one stage of the world build. With async_build, `work` runs on a worker
## thread (`threaded`) or on the main thread after a frame has been drawn, and the
## progress window moves on to end at `to`. Without it, `work` just runs.
func _stage(to: float, threaded: bool, work: Callable, worker: Thread = null) -> void:
	if not async_build:
		work.call()
		return
	build_from = build_to
	build_to = to
	if not threaded:
		await get_tree().process_frame
		work.call()
		return
	var thread := worker if worker != null else Thread.new()
	if thread.start(work) != OK:
		work.call()
		return
	while thread.is_alive():
		await get_tree().process_frame
	if thread.is_started():
		thread.wait_to_finish()


func _exit_tree() -> void:
	if _generation_thread != null and _generation_thread.is_started():
		_generation_thread.wait_to_finish()


## The wildlife group whose animal is nearest `screen` (and showing), if any.
func pick_wildlife(screen: Vector2, cam: Camera3D) -> Wildlife.Visit:
	var v := cetaceans.pick(screen, cam)
	if v == null:
		v = pinnipeds.pick(screen, cam)
	return v if v else eagles.pick(screen, cam)


## The map to build: a random one from the seed (--seed=N, or a new one each time).
func _generation_job(gen: MapGenerator) -> Callable:
	if map_seed == 0:
		map_seed = int(_args["seed"]) if _args.has("seed") else randi_range(1, 99999)
	return gen.generate.bind(map_seed)


## The HUD's opening toast: [title, body].
func intro(islands: int) -> Array:
	return ["PROCEDURAL ARCHIPELAGO", "Map seed %d · %d islands · %d routes.\nPress G for a new map." % [
		map.map_seed, islands, map.routes.size()]]


func regenerate() -> void:
	Engine.time_scale = 1.0
	map_seed = randi_range(1, 99999)
	get_tree().reload_current_scene()


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
	var on := str(_args.get("dof", "1")) != "0"
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


# --- Debug / screenshot args ----------------------------------------------------------

func _parse_args() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--"):
			var kv := a.substr(2).split("=", true, 1)
			_args[kv[0]] = kv[1] if kv.size() > 1 else "1"


func _apply_debug_args() -> void:
	if _args.has("aa"):
		var aa := str(_args["aa"])
		get_viewport().msaa_3d = Viewport.MSAA_2X if aa == "msaa" else Viewport.MSAA_DISABLED
		get_viewport().screen_space_aa = Viewport.SCREEN_SPACE_AA_SMAA if aa == "smaa" else Viewport.SCREEN_SPACE_AA_DISABLED
	if _args.has("time"):
		day_cycle.set_hour(float(_args["time"]))
		day_cycle.apply(day_cycle.hour())
	if _args.has("speed"):
		hud.set_speed(int(_args["speed"]))
	if _args.has("cam"):
		var p: PackedStringArray = str(_args["cam"]).split(",")
		rig.target_pos = Vector3(float(p[0]), 0, float(p[1]))
		rig.target_dist = float(p[2])
		if p.size() > 3:
			rig.target_yaw = deg_to_rad(float(p[3]))
		if p.size() > 4:
			rig.target_pitch = deg_to_rad(float(p[4]))
		rig.snap()
	if _args.has("select"):
		var k := int(_args["select"])
		var terms: Array = sim.terminals.values()
		if k < terms.size():
			hud.select_island((terms[k] as Terminal).island, true)
			rig.snap()
	if _args.has("follow"):
		var k := int(_args["follow"])
		if k < sim.ferries.size():
			hud.select_ferry(sim.ferries[k])
	if _args.has("orcas") or _args.has("wildlife"):
		var sp := sim.wildlife.find_species(str(_args.get("wildlife", "orca")))
		var v := sim.wildlife.start_visit(sp) if sp else null
		if v:
			hud.follow_visit(v)
			rig.target_dist = 210.0
			rig.target_pitch = 0.55
			rig.snap()
	if _args.has("vessel"):
		var want := str(_args["vessel"])
		for v in sim.marine.vessels:
			if (want == "cargo" and v is CargoShip) or (want == "sail" and v is Sailboat and v.wants_to_move()) \
					or (want == "yacht" and v is MotorYacht) or (want == "pilot" and v is PilotBoat) or (want == "tug" and v is Tug):
				hud.select_vessel(v)
				rig.target_pos = v.global_position
				rig.snap()
				break
	if _args.has("shot"):
		_take_screenshot(str(_args["shot"]), float(_args.get("shot-delay", "3")))
	if _args.has("bench"):
		_bench(float(_args["bench"]))


## Prints averaged frame / GPU time and render stats after a warm-up, then quits.
## GPU time needs a driver with timestamp queries (e.g. --rendering-driver vulkan).
func _bench(seconds: float) -> void:
	uncapped = true
	Engine.max_fps = 0
	var vp := get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	await get_tree().create_timer(3.0, true, false, true).timeout
	var frames := 0
	var gpu := 0.0
	var t0 := Time.get_ticks_usec()
	while (Time.get_ticks_usec() - t0) / 1e6 < seconds:
		await get_tree().process_frame
		frames += 1
		gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
	var rs := RenderingServer
	print("BENCH frame %.2f ms | gpu %.2f ms | draws %d | primitives %d | objects %d | nodes %d" % [
		(Time.get_ticks_usec() - t0) / 1000.0 / frames, gpu / frames,
		rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		rs.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
		Performance.get_monitor(Performance.OBJECT_NODE_COUNT)])
	get_tree().quit()


func _take_screenshot(path: String, delay: float) -> void:
	await get_tree().create_timer(delay, true, false, true).timeout
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(path)
	print("Saved screenshot to ", path)
	get_tree().quit()
