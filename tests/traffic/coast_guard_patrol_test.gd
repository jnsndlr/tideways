extends SceneTree
## The cutter's astern lane and open-water patrol must meet on either berth heading.


class OpenWater:
	extends Terrain

	func height_at(_x: float, _z: float) -> float:
		return -30.0


func _initialize() -> void:
	var sim := Simulation.new(Callable())
	sim.map = MapData.new()
	sim.map.half_size = 2400.0
	sim.terrain = OpenWater.new(0, 10.0)
	var traffic := MarineTraffic.new()
	traffic.sim = sim
	traffic.rng.seed = 6839
	traffic.nav = NavGrid.new(sim.map, sim.terrain)
	var error := ""
	for yaw: float in [0.0, PI]:
		var cutter := CoastGuardBoat.new()
		error = _check_berth(cutter, traffic, yaw)
		cutter.free()
		if not error.is_empty():
			break
	traffic.free()
	sim.free()
	if error.is_empty():
		print("TEST PASSED")
	else:
		push_error(error)
	quit(0 if error.is_empty() else 1)


func _check_berth(cutter: CoastGuardBoat, traffic: MarineTraffic, yaw: float) -> String:
	cutter.setup_berth(traffic, "national_security_cutter", [[0.0, 0.0, yaw]])
	if not cutter._plan_patrol():
		return "Expected a seeded open-water patrol"
	var bow := Vector2(sin(yaw), cos(yaw))
	var lane_end := cutter.berth - bow * (2 * cutter.spec.half_length + CoastGuardBoat.LANE_PAD)
	if cutter.path.sample(0.0).distance_to(lane_end) > 0.01:
		return "Cutter jumps from its pivot onto the first patrol leg"
	var last_metres := 120.0
	var approach := cutter.path.sample(cutter.path.length - last_metres)
	if approach.distance_to(cutter.berth - last_metres * bow) > 0.01:
		return "Cutter should approach its berth on a straight bow-first lane"
	return ""
