extends SceneTree
## Rule checks on TinyRegion, which builds in milliseconds:
##   - the region builds and a simulation starts on it quickly,
##   - the navigation grid tells water from land and routes round an island,
##   - a boat steering itself gets round that island without touching land,
##   - one ferry carries its cars across: fares match the cars aboard, she docks
##     at the far terminal and every car she left with drives off,
##   - three ferries whose routes meet never touch, never share the stretch of
##     water their routes have in common, and all keep making crossings.
##
##   godot --headless --path . --fixed-fps 30 --script tools/tiny_region_test.gd

const BUILD_BUDGET_MS := 1000
const START_BUDGET_MS := 3000
const STEERING_FRAMES := 3000
const ARRIVED := 45.0
const CROSSING_FRAMES := 4000
const MEETING_FRAMES := 6000
const MEETING_TRIPS := 2

enum Stage { SETUP, CROSSING, STEERING, MEETING }

var failures := 0
var frame := 0
var stage := Stage.SETUP
var stage_frame := 0
var sim: Simulation
var region: TinyRegion

# Steering
var launch: Launch
var steered := 0.0
var shallowest := -INF

# Crossing
var ferry: Ferry
var fares_before := 0
var left_with: Array[int] = []
var sailed := false
var docked := false

# Meeting
var closest := INF
var shared := 0


func expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _process(_delta: float) -> bool:
	frame += 1
	stage_frame += 1
	match stage:
		Stage.SETUP:
			check_build()
			check_navigation()
			begin_crossing()
		Stage.STEERING:
			tick_steering(_delta)
		Stage.CROSSING:
			tick_crossing()
		Stage.MEETING:
			tick_meeting()
	return false


func finish() -> void:
	Engine.time_scale = 1.0
	if sim:
		sim.free()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_build() -> void:
	var t0 := Time.get_ticks_msec()
	region = TinyRegion.build()
	var built := Time.get_ticks_msec() - t0
	expect(region != null, "The two-town region should build")
	if region == null:
		return
	expect(built < BUILD_BUDGET_MS, "Tiny region took %d ms to build (budget %d)" % [built, BUILD_BUDGET_MS])
	var map := region.map
	expect(map.islands.size() == 2 and map.routes.size() == 1, "Two towns and one route expected")
	var route := map.routes[0]
	var a := map.islands[route.a]
	var b := map.islands[route.b]
	expect(route.curve.sample_baked(0.0).distance_to(a.dock_center(route.id)) < 1.0, "Route should start at the first town's dock")
	expect(route.curve.sample_baked(route.length).distance_to(b.dock_center(route.id)) < 1.0, "Route should end at the second town's dock")
	expect(route.length > 270.0, "The crossing should leave a ferry room to line up at both ends; got %d m" % roundi(route.length))
	t0 = Time.get_ticks_msec()
	sim = region.start(root)
	var started := Time.get_ticks_msec() - t0
	expect(started < START_BUDGET_MS, "Simulation took %d ms to start on the tiny region (budget %d)" % [started, START_BUDGET_MS])
	expect(sim.ferries.size() == 1 and sim.terminals.size() == 2, "One ferry and two terminals expected")
	print("Tiny region built in %d ms; simulation started in %d ms; crossing %d m" % [built, started, roundi(route.length)])


func check_navigation() -> void:
	if sim == null:
		return
	var nav := sim.marine.nav
	var west := region.map.islands[0]
	var north := west.center + Vector2(0.0, -360.0)
	var south := west.center + Vector2(0.0, 360.0)
	expect(nav.open_at(Vector2.ZERO, false), "Mid-passage should be navigable")
	expect(not nav.open_at(west.center, false), "The middle of an island should be closed")
	expect(not nav.clear_line(north, south, false), "A line through the island should be blocked")
	expect(nav.clear_line(Vector2(0.0, -300.0), Vector2(0.0, 300.0), false), "A line down the open passage should be clear")
	var path := nav.find_path(north, south, false)
	expect(path.size() >= 2, "There should be a way round the island")
	if path.size() >= 2:
		var length := 0.0
		for i in range(1, path.size()):
			length += path[i - 1].distance_to(path[i])
		expect(nav.afloat(path, 3.0), "The way round the island should stay in deep water")
		expect(length > north.distance_to(south) * 1.1, "The way round should be longer than the line through the island")


## A small boat that only follows its helm: the least a HelmVessel needs.
class Launch extends HelmVessel:
	func setup(t: MarineTraffic, at: Vector2) -> void:
		traffic = t
		apply_spec(VesselTypes.fishing_boats()[0])
		position = Vector3(at.x, 0.0, at.y)
		helm = Helm.new(self, t)
		t.register(self, MarineTraffic.RANK_POWER)

	func _process(delta: float) -> void:
		helm.update(delta)
		_make_way(delta, helm.want_yaw, helm.want_speed, spec.turn)


func begin_steering() -> void:
	if sim == null or failures > 0:
		finish()
		return
	var west := region.map.islands[0]
	launch = Launch.new()
	sim.add_child(launch)
	launch.setup(sim.marine, west.center + Vector2(0.0, -360.0))
	expect(launch.helm.set_goal(west.center + Vector2(0.0, 360.0)), "The helm should find a way to the far side of the island")
	stage = Stage.STEERING
	stage_frame = 0


func tick_steering(delta: float) -> void:
	var at := launch.pos2()
	steered += launch.speed * delta
	shallowest = maxf(shallowest, region.terrain.height_at(at.x, at.y))
	if shallowest > -1.0:
		expect(false, "The boat ran into %.1f m of water at %s on frame %d" % [-shallowest, at.round(), frame])
		finish()
		return
	if launch.helm.distance_left() < ARRIVED:
		var straight := 720.0
		expect(steered > straight * 1.05, "The boat covered %d m; the island is in the way of the %d m straight line" % [roundi(steered), roundi(straight)])
		print("Steered %d m round the island by frame %d; shallowest water %.1f m" % [roundi(steered), frame, -shallowest])
		sim.free()
		sim = null
		begin_meeting()
	elif stage_frame > STEERING_FRAMES:
		expect(false, "The boat was still %d m from its goal after %d frames" % [roundi(launch.helm.distance_left()), STEERING_FRAMES])
		finish()


func begin_crossing() -> void:
	if sim == null or failures > 0:
		finish()
		return
	ferry = sim.ferries[0]
	fares_before = sim.cars_today
	Engine.time_scale = 4.0
	stage = Stage.CROSSING
	stage_frame = 0


func tick_crossing() -> void:
	if not sailed and ferry.state == Ferry.State.SAILING:
		sailed = true
		for car in ferry.aboard:
			left_with.append(car.get_instance_id())
		expect(not left_with.is_empty(), "The ferry should leave with cars from the waiting queue")
		expect(sim.cars_today - fares_before == left_with.size(),
			"Fares credited (%d) should equal cars aboard at departure (%d)" % [sim.cars_today - fares_before, left_with.size()])
		expect(ferry.here() == sim.terminals[ferry.route.a], "The first crossing should leave from the route's first town")
	elif sailed and not docked and ferry.state == Ferry.State.SAILING:
		expect(ferry.aboard.size() == left_with.size(), "Cars aboard changed mid-crossing")
	elif sailed and not docked and ferry.state != Ferry.State.SAILING:
		docked = true
		var far := region.map.islands[ferry.route.b]
		expect(ferry.trips == 1 and ferry.here() == sim.terminals[far.id], "The ferry should dock at the far town after one crossing")
		var off := ferry.global_position.distance_to(far.dock_center(ferry.route.id))
		expect(off < 60.0, "The ferry docked %d m from the far slip" % roundi(off))
	elif docked and ferry.state == Ferry.State.LOADING:
		for car in ferry.aboard:
			expect(not left_with.has(car.get_instance_id()), "A car that crossed is still aboard after unloading")
		print("One crossing: %d cars carried, docked on frame %d" % [left_with.size(), frame])
		begin_steering()
		return
	if stage_frame > CROSSING_FRAMES:
		expect(false, "The crossing did not finish in %d frames (sailed %s, docked %s)" % [CROSSING_FRAMES, sailed, docked])
		finish()


func begin_meeting() -> void:
	if failures > 0:
		finish()
		return
	var triangle := TinyRegion.build(3)
	expect(triangle != null, "The three-town region should build")
	if triangle == null:
		finish()
		return
	sim = triangle.start(root)
	for r in triangle.map.routes:
		shared += sim.marine.corridors[r.id].size()
	expect(shared > 0, "The three-town region should have routes that meet")
	stage = Stage.MEETING
	stage_frame = 0


func tick_meeting() -> void:
	var boats := sim.ferries
	for i in boats.size():
		var a := boats[i]
		var ha := a.heading2() * a.half_seg
		for j in range(i + 1, boats.size()):
			var b := boats[j]
			var hb := b.heading2() * b.half_seg
			var gap := MarineTraffic._seg_dist(a.pos2() - ha, a.pos2() + ha, b.pos2() - hb, b.pos2() + hb) - a.hull_radius - b.hull_radius
			closest = minf(closest, gap)
			if gap < 0.0:
				expect(false, "%s and %s overlap on frame %d" % [a.ferry_name, b.ferry_name, frame])
				finish()
				return
	for r in sim.map.routes:
		for c: MarineTraffic.Corridor in sim.marine.corridors[r.id]:
			var inside: Array[String] = []
			for f in boats:
				if f.state != Ferry.State.SAILING or not c.span.has(f.route.id):
					continue
				var s := f._route_s(f.traveled)
				var span: Vector2 = c.span[f.route.id]
				if s > span.x and s < span.y:
					inside.append(f.ferry_name)
			if inside.size() > 1:
				expect(false, "%s are in the same shared stretch on frame %d" % [" and ".join(inside), frame])
				finish()
				return
	var done := true
	for f in boats:
		if f.trips < MEETING_TRIPS:
			done = false
	if done:
		print("Three ferries made %d crossings each by frame %d; closest pass %.1f m" % [MEETING_TRIPS, frame, closest])
		finish()
	elif stage_frame > MEETING_FRAMES:
		var counts := boats.map(func(f: Ferry): return "%s %d (%s)" % [f.ferry_name, f.trips, f.status_text()])
		expect(false, "Not every ferry made %d crossings in %d frames: %s" % [MEETING_TRIPS, MEETING_FRAMES, ", ".join(counts)])
		finish()
