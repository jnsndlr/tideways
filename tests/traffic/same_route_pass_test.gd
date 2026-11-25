extends SceneTree
## Two boats on one route pass each other on their own lanes. On the shared slip
## map (maps/shared_slip.json) Rhododendron is put on Hiyu's route, Port Rosario –
## Madrona, and the two run at different paces, sailing half a round apart. Passes once they
## have passed each other PASSES times, at least once both under way mid-crossing,
## always LANE_GAP or more apart (hull to hull),
## with neither ever stuck holding and never two boats lying at one slip.
##
##   godot --headless --path . --fixed-fps 30 \
##     --script tests/traffic/same_route_pass_test.gd -- --scenario=shared_slip
##
## Without --headless, `--shots=<dir>` saves a picture of each pass there.

const PASSES := 3
const LANE_GAP := 50.0
const STUCK := 90.0          # game minutes holding still under way (not for a boat at the slip) counts as stuck
const JAM := 5.0             # game minutes both still under way, each held up by the other

var main: Node
var frames := 0
var passes := 0
var under_way := 0           # passes with both boats making way
var min_gap := INF
var _ahead := 0              # sign of (Hiyu's s - Rhododendron's s) while passing
var _still := {}             # ferry -> game minutes stopped under way
var _jam := 0.0
var _switched := false
var _shots := ""
var _cam: Camera3D
var _meeting := 0             # meetings under way so far (for the shots' names)
var _shot_stage := -1


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			_shots = a.trim_prefix("--shots=")
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _fail(msg: String) -> bool:
	push_error(msg)
	quit(1)
	return true


func _term(sim: Simulation, key: String) -> Terminal:
	for t: Terminal in sim.terminals.values():
		if t.town.key.begins_with(key + "/"):
			return t
	return null


## Hull to hull: the two capsules' segments apart, less both radii.
static func _gap(a: Ferry, b: Ferry) -> float:
	var ha := a.heading2() * a.half_seg
	var hb := b.heading2() * b.half_seg
	return MarineTraffic._seg_dist(a.pos2() - ha, a.pos2() + ha, b.pos2() - hb, b.pos2() + hb) - a.hull_radius - b.hull_radius


func _process(delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var hiyu := sim.ferries[0]
	var rhodo := sim.ferries[1]
	var rosario := _term(sim, "island-1")
	var madrona := _term(sim, "island-2")
	if frames == 5:
		Engine.time_scale = 6.0
		hiyu.set_pace(FerryPace.FULL_AHEAD)
		rhodo.set_pace(FerryPace.ECONOMY)
		var ids: Array[int] = [rosario.town.id, madrona.town.id]
		# Both on one timetable's beat, Rhododendron leaving Port Rosario so that
		# halfway across she meets Hiyu halfway back (at their different paces).
		var beat := maxf(hiyu.plan_offsets(ids)[-1], rhodo.plan_offsets(ids)[-1]) + 20.0
		var n := floori(Timetable.DAY / beat)
		var period := Timetable.DAY / n
		var cross_h := hiyu.leg_minutes(hiyu.route)
		var cross_r := rhodo.leg_minutes(hiyu.route)
		var lag := posmod(int(hiyu.plan_offsets(ids)[1] + (cross_h - cross_r) * 0.5), period)
		var hiyu_times: Array[int] = []
		var rhodo_times: Array[int] = []
		for k in n:
			hiyu_times.append(k * period)
			rhodo_times.append(k * period + lag)
		rhodo_times.sort()
		if not sim.reschedule(hiyu, ids, hiyu_times):
			return _fail("Could not put Hiyu on a sailing every %d minutes" % period)
		if not sim.reschedule(rhodo, ids, rhodo_times):
			return _fail("Could not put Rhododendron on Port Rosario – Madrona: " + sim.stops_problem(rhodo, ids))
		print("Sailings every %d min, Rhododendron %d min after Hiyu (crossings %.0f and %.0f min)" % [period, lag, cross_h, cross_r])
		print("Lane %.1f m off the centreline; Rhododendron takes Port Rosario – Madrona at her next call" % Ferry.lane_width())
	var route := hiyu.route
	if not _switched and rhodo.next_stops.is_empty() and rhodo.route == route:
		_switched = true
		print("Day %d %s: Rhododendron on Hiyu's route (%.0f m). Corridors: %s" % [sim.day, sim.clock_text(), route.length,
			sim.marine.corridors[route.id].map(func(c): return "%s %s" % [c.key, c.span[route.id]])])
	# Never two at one slip.
	for term: Terminal in sim.terminals.values():
		var at := sim.ferries.filter(func(f): return f.berth == Ferry.Berth.WORKING and f.state != Ferry.State.SAILING and f.here() == term)
		if at.size() > 1:
			return _fail("%s and %s both at %s's slip" % [at[0].ferry_name, at[1].ferry_name, term.town.name])
	# Never stuck.
	var minutes := delta   # (already scaled; a second is a game minute)
	var held := func(f: Ferry, by: Ferry) -> bool:
		return f.state == Ferry.State.SAILING and f.speed < 0.3 and (f._waiting_for == by or f.blocker == by)
	if held.call(hiyu, rhodo) and held.call(rhodo, hiyu):
		_jam += minutes
		if _jam > JAM:
			return _fail("Jammed: Hiyu %s, Rhododendron %s" % [hiyu.status_text(), rhodo.status_text()])
	else:
		_jam = 0.0
	for f: Ferry in sim.ferries:
		# (Holding offshore for a boat lying at the slip is fine, however long she lies there.)
		var at_slip := f._waiting_for != null and f._waiting_for.state != Ferry.State.SAILING
		if f.state == Ferry.State.SAILING and f.speed < 0.3 and not at_slip:
			_still[f] = _still.get(f, 0.0) + minutes
			if _still[f] > STUCK:
				for g: Ferry in sim.ferries:
					print("  %s: %s to %s, %.0f m left, route %d at_a %s, stops %s next %s, %s, clear %.0f hold %.0f blocker %s speed %.2f traveled %.0f wf %s" % [g.ferry_name, Ferry.State.keys()[g.state],
						g.destination().town.name, g.path_left(), g.route.id, g.at_a, g.stops, g.next_stops, g.status_text(), g.clear, g.hold, g.blocker.vessel_name if g.blocker else "-", g.speed, g.traveled, g._waiting_for.ferry_name if g._waiting_for else "-"])
				for id in sim.marine.corridors:
					for c in sim.marine.corridors[id]:
						print("  corridor %s on %d %s owner %s" % [c.key, id, c.span[id], c.owner.ferry_name if c.owner else "-"])
				return _fail("%s stuck %.0f m out: %s" % [f.ferry_name, f.path_left(), f.status_text()])
		else:
			_still[f] = 0.0
	if not _switched:
		return false
	# Passing: both under way on the route in opposite directions.
	var sailing := hiyu.state == Ferry.State.SAILING and rhodo.state == Ferry.State.SAILING and rhodo.route == route
	if sailing and hiyu.at_a != rhodo.at_a:
		var gap := _gap(hiyu, rhodo)
		min_gap = minf(min_gap, gap)
		if gap < LANE_GAP:
			return _fail("Passing only %.1f m apart (Hiyu %.0f m out, Rhododendron %.0f m out)" % [gap, hiyu.path_left(), rhodo.path_left()])
		var d := hiyu._route_s(hiyu.traveled) - rhodo._route_s(rhodo.traveled)
		var side := signi(int(signf(d)))
		if _ahead == 0:
			_meeting += 1
			_shot_stage = -1
		if _ahead != 0 and side != _ahead:
			passes += 1
			if hiyu.speed > hiyu.cruise * 0.5 and rhodo.speed > rhodo.cruise * 0.5:
				under_way += 1
			print("Day %d %s: pass %d, %.1f m apart. Hiyu %.0f m from %s, %s; Rhododendron %.0f m from %s, %s" % [sim.day, sim.clock_text(), passes, gap,
				hiyu.path_left(), hiyu.destination().town.name, hiyu.status_text(), rhodo.path_left(), rhodo.destination().town.name, rhodo.status_text()])
		_ahead = side
		if _shots != "":
			_film(hiyu, rhodo, d)
	else:
		_ahead = 0
		if _shots != "" and _cam:
			Engine.time_scale = 6.0
	if passes >= PASSES and under_way > 0:
		print("Closest pass %.1f m hull to hull; %d of %d passes with both under way" % [min_gap, under_way, passes])
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 12000:
		return _fail("Only %d passes (switched %s): Hiyu %s, Rhododendron %s" % [passes, _switched, hiyu.status_text(), rhodo.status_text()])
	return false


## With --shots (and a window): slows down as they close, looks down on the two
## from abeam and saves the approach, the pass and the two drawing apart.
func _film(a: Ferry, b: Ferry, d: float) -> void:
	if DisplayServer.get_name() == "headless":
		return
	if _cam == null:
		_cam = Camera3D.new()
		_cam.fov = 45.0
		_cam.far = 20000.0
		root.add_child(_cam)
	if absf(d) > 700.0:
		Engine.time_scale = 6.0
		return
	Engine.time_scale = 1.0
	_cam.current = true
	var mid := (a.global_position + b.global_position) * 0.5
	var along := Vector3(a.heading2().x, 0.0, a.heading2().y)
	var abeam := along.cross(Vector3.UP).normalized()
	_cam.global_position = mid + abeam * 420.0 - along * 160.0 + Vector3.UP * 360.0
	_cam.look_at(mid, Vector3.UP)
	# Closing, abeam, then drawing apart: one shot each, once per meeting.
	var stage := 0 if absf(d) > 40.0 and _shot_stage == -1 else (1 if _shot_stage <= 0 and absf(d) <= 40.0 else 2)
	if stage == 2 and (_shot_stage != 1 or absf(d) < 400.0):
		return
	if stage == 0 and absf(d) > 500.0:
		return
	if stage <= _shot_stage:
		return
	_shot_stage = stage
	await RenderingServer.frame_post_draw
	var path := "%s/pass_%d_%s.png" % [_shots, _meeting, ["a_closing", "b_abeam", "c_apart"][stage]]
	root.get_viewport().get_texture().get_image().save_png(path)
	print("Saved %s, %.0f m apart" % [path, _gap(a, b)])
