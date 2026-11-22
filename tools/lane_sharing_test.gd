extends SceneTree
## maps/lane_sharing.json: Hiyu runs Port Rosario → Madrona → Gullrock → Madrona
## and back, Rhododendron shuttles Madrona ↔ Cypress, both from Madrona's one slip.
## Checks that Hiyu keeps her heading through every stop; that a car boarded at
## Port Rosario for Gullrock stays aboard at Madrona and gets off at Gullrock; that
## traffic shares a lane at Port Rosario or Gullrock, where Hiyu serves both
## destinations; and that at Madrona, where the next boat to load any lane serves
## only that lane's destination, no car ever queues in another destination's lane.
##
##   godot --headless --path . --fixed-fps 30 --script tools/lane_sharing_test.gd -- --scenario=lane_sharing

var main: Node
var frames := 0
var through: Vehicle
var through_phase := 0       # 0 none, 1 aboard leaving Madrona, 2 still aboard leaving Gullrock, 3 off at Port Rosario
var shared_ok := false
var _last_yaw := INF
var _last_pos := Vector3.ZERO
var _was_sailing := false


func _initialize() -> void:
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


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var hiyu := sim.ferries[0]
	var madrona := _term(sim, "island-2")
	var gullrock := _term(sim, "island-7")
	var rosario := _term(sim, "island-1")
	var cypress := _term(sim, "island-3")
	if frames == 5:
		Engine.time_scale = 6.0
		for t: Terminal in [madrona, gullrock, rosario, cypress]:
			print("%s lanes: %s" % [t.town.name, t.lanes.keys().map(func(k): return "%s×%d" % [sim.map.towns[k].name, t.lanes[k].size()])])
		print("Hiyu stops %s" % [hiyu.stops])
	# Her hull never jumps or swings round between frames.
	var yaw := hiyu.global_rotation.y
	if _last_yaw != INF and (absf(angle_difference(_last_yaw, yaw)) > 0.25 or hiyu.global_position.distance_to(_last_pos) > 6.0) and hiyu.berth == Ferry.Berth.WORKING:
		return _fail("Hiyu jumped at %s: yaw %.2f -> %.2f" % [hiyu.here().town.name, _last_yaw, yaw])
	_last_yaw = yaw
	_last_pos = hiyu.global_position
	# No sharing at Madrona; sharing where Hiyu serves both.
	for key in madrona.lanes.keys():
		for lane: Terminal.Lane in madrona.lanes[key]:
			for waiting in lane.queue:
				var car := instance_from_id(waiting.vehicle_id) as Vehicle
				if car.dest == key:
					continue
				return _fail("%s traffic queued in the %s lane at Madrona" % [sim.map.towns[car.dest].name, sim.map.towns[key].name])
	for t: Terminal in [rosario, gullrock]:
		for key in t.lanes.keys():
			for lane: Terminal.Lane in t.lanes[key]:
				for waiting in lane.queue:
					var car := instance_from_id(waiting.vehicle_id) as Vehicle
					if car.dest == key or shared_ok:
						continue
					print("Day %d %s: %s traffic sharing the %s lane at %s" % [sim.day, sim.clock_text(), sim.map.towns[car.dest].name, sim.map.towns[key].name, t.town.name])
					shared_ok = true
	# A through car.
	var sailing := hiyu.state == Ferry.State.SAILING
	if sailing and not _was_sailing:
		var left := hiyu.here()
		if left == rosario and through_phase == 0:
			for car in hiyu.aboard:
				if car.dest == gullrock.town.id:
					through = car
					through_phase = 1
					print("Leaving Port Rosario with a car for Gullrock aboard")
					break
		elif left == madrona and through_phase == 1:
			if not is_instance_valid(through) or through not in hiyu.aboard:
				return _fail("The Gullrock car got off at Madrona")
			through_phase = 2
			print("Still aboard leaving Madrona")
		elif left == gullrock and through_phase == 2:
			if is_instance_valid(through) and through in hiyu.aboard:
				return _fail("The Gullrock car stayed aboard at Gullrock")
			through_phase = 3
			print("Off at Gullrock")
	_was_sailing = sailing
	if through_phase == 3 and shared_ok:
		print("TEST PASSED")
		quit(0)
		return true
	if frames > 60000:
		return _fail("Gave up: through phase %d, shared %s" % [through_phase, shared_ok])
	return false
