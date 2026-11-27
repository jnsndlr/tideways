extends SceneTree
## Render the terminal rim during a low-sun pan, then hold the same camera while
## the game clock advances. Use --fixed-fps 30 to compare identical increments.
## godot --path . --resolution 1120x640 --fixed-fps 30 --script \
##   tools/terminal_shadow_sequence.gd -- --scenario=opening --out=/tmp/terminal-shadows

const START_MINUTES := 6.0 * 60.0 + 52.0
const PAN_FRAMES := 24
const STILL_FRAMES := 72


func _initialize() -> void:
	_capture.call_deferred()


func _capture() -> void:
	var output: String = Scenes.launch_options.values.get("out", "")
	if output.is_empty() or DirAccess.make_dir_recursive_absolute(output) != OK:
		push_error("Pass --out with a writable directory for the frame sequence")
		quit(1)
		return
	# A review window losing focus must never overwrite the player's company.
	SaveGame._path = output.path_join("review-slot.json")
	var session := load(Scenes.MAIN_MAP).instantiate() as WorldSession
	root.add_child(session)
	while not session.built:
		await process_frame
	var town := session.sim.ferries[0].here().town
	var lot := town.lot_xform()
	var target := lot * Vector3(0, Layout.LOT_Y, Layout.LOT_FRONT - 12.0)
	var rig := session.rig
	rig.follow = null
	rig.target_pitch = deg_to_rad(54)
	rig.target_yaw = atan2(town.dock_dir.x, town.dock_dir.z) + 0.25
	rig.target_dist = 140.0
	session.hud.set_speed(1)
	session.sim.process_mode = Node.PROCESS_MODE_DISABLED
	session.sim.minutes = START_MINUTES
	session.day_cycle.follow_clock()
	session.day_cycle.apply(session.sim.hour())
	rig.target_pos = target - lot.basis.x * 4.0
	rig.snap()
	for warmup in 8:
		await RenderingServer.frame_post_draw
	for frame in PAN_FRAMES + STILL_FRAMES:
		var fraction := minf(float(frame) / (PAN_FRAMES - 1), 1.0)
		rig.target_pos = target + lot.basis.x * lerpf(-4.0, 0.0, fraction)
		rig.snap()
		if frame == PAN_FRAMES:
			session.sim.process_mode = Node.PROCESS_MODE_INHERIT
		await RenderingServer.frame_post_draw
		var path := output.path_join("frame-%03d.png" % frame)
		if root.get_texture().get_image().save_png(path) != OK:
			push_error("Could not write " + path)
			quit(1)
			return
		await process_frame
	quit()
