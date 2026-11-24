class_name SessionDiagnostics
extends Node
## Debug args (after `--` on the command line):
##   --seed=N  --speed=0..3  --cam=x,z,dist,yaw_deg,pitch_deg  --select=K (Kth terminal island)
##   --follow=K (Kth ferry)  --time=H (pin time of day, e.g. 19.5)  --shot=path.png  --shot-delay=seconds
##   --bench=seconds (print frame/GPU time and render stats, then quit)
##   --orcas (start an orca visit now and follow it)  --wildlife=ID (the same for any species:
##     humpback, gray, sea_lion, dalls_porpoise, harbor_porpoise, harbor_seal)
##   --vessel=cargo|sail|yacht|pilot|tug (follow a cargo ship, a sailboat under way, a
##     motor yacht, a pilot boat or a tug)
##   --aa=msaa|smaa|none (anti-aliasing, to compare)  --dof=0 (no depth-of-field blur)

var _session: WorldSession
var _demo_ferry: Ferry
var _demo_wait := 0.0

## --shift-demo: the ferry that starts laid up keeps moving between her tie-up and
## her working slip: back to service a few seconds after tying up, and laid up
## again at her next call there. The camera follows her.
func _process(delta: float) -> void:
	if _demo_ferry == null:
		for f in _session.sim.ferries:
			if f.berth == Ferry.Berth.TIED_UP:
				_demo_ferry = f
				_session.hud.select_ferry(f)
				break
		return
	var f := _demo_ferry
	if f.berth == Ferry.Berth.TIED_UP:
		_demo_wait += delta
		if _demo_wait > 3.0 and not f.return_requested:
			f.request_return()
	else:
		_demo_wait = 0.0
		if f.berth == Ferry.Berth.WORKING and not f.lay_up_requested and f.can_lay_up():
			f.request_lay_up()


static func attach(session: WorldSession) -> void:
	var options := Scenes.launch_options.values
	if options.is_empty():
		return
	var diagnostics := SessionDiagnostics.new()
	diagnostics._session = session
	session.add_child(diagnostics)
	diagnostics.set_process(false)
	session.world_ready.connect(diagnostics._apply.bind(options), CONNECT_ONE_SHOT)


func _apply(options: Dictionary[String, String]) -> void:
	set_process(options.has("shift-demo"))
	if options.has("aa"):
		var aa := str(options["aa"])
		get_viewport().msaa_3d = Viewport.MSAA_2X if aa == "msaa" else Viewport.MSAA_DISABLED
		get_viewport().screen_space_aa = Viewport.SCREEN_SPACE_AA_SMAA if aa == "smaa" else Viewport.SCREEN_SPACE_AA_DISABLED
	if options.has("time"):
		_session.day_cycle.set_hour(float(options["time"]))
		_session.day_cycle.apply(_session.day_cycle.hour())
	if options.has("speed"):
		_session.hud.set_speed(int(options["speed"]))
	if options.has("cam"):
		var p: PackedStringArray = str(options["cam"]).split(",")
		_session.rig.target_pos = Vector3(float(p[0]), 0, float(p[1]))
		_session.rig.target_dist = float(p[2])
		if p.size() > 3:
			_session.rig.target_yaw = deg_to_rad(float(p[3]))
		if p.size() > 4:
			_session.rig.target_pitch = deg_to_rad(float(p[4]))
		_session.rig.snap()
	if options.has("select"):
		var k := int(options["select"])
		var terms: Array = _session.sim.terminals.values()
		if k < terms.size():
			_session.hud.select_island(_session.sim.map.island_of((terms[k] as Terminal).town), true)
			_session.rig.snap()
	if options.has("follow"):
		var k := int(options["follow"])
		if k < _session.sim.ferries.size():
			_session.hud.select_ferry(_session.sim.ferries[k])
	if options.has("orcas") or options.has("wildlife"):
		var sp := _session.sim.wildlife.find_species(str(options.get("wildlife", "orca")))
		var v := _session.sim.wildlife.start_visit(sp) if sp else null
		if v:
			_session.hud.follow_visit(v)
			_session.rig.target_dist = 210.0
			_session.rig.target_pitch = 0.55
			_session.rig.snap()
	if options.has("vessel"):
		var want := str(options["vessel"])
		for v in _session.sim.marine.vessels:
			if (want == "cargo" and v is CargoShip) or (want == "sail" and v is Sailboat and v.wants_to_move()) \
					or (want == "yacht" and v is MotorYacht) or (want == "pilot" and v is PilotBoat) or (want == "tug" and v is Tug):
				_session.hud.select_vessel(v)
				_session.rig.target_pos = v.global_position
				_session.rig.snap()
				break
	if options.has("shot"):
		_take_screenshot(str(options["shot"]), float(options.get("shot-delay", "3")))
	if options.has("bench"):
		_bench(float(options["bench"]))


## Prints averaged frame / GPU time and render stats after a warm-up, then quits.
## GPU time needs a driver with timestamp queries (e.g. --rendering-driver vulkan).
func _bench(seconds: float) -> void:
	_session.uncapped = true
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
