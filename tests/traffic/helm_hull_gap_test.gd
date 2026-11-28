extends "res://tests/rule_test_case.gd"


class OpenWater:
	extends Terrain

	func height_at(_x: float, _z: float) -> float:
		return -30.0


class Traffic:
	extends MarineTraffic
	var current := INF
	var proposed := INF
	var queries := 0

	func hull_gap(_v: Vessel, p: Vector2, _h: Vector2) -> float:
		queries += 1
		return current if p == Vector2.ZERO else proposed


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var boat := HelmVessel.new()
	root.add_child(boat)
	boat.spec = VesselTypes.sailboats()[0]
	var traffic := Traffic.new()
	var sim := Simulation.new(Callable())
	sim.terrain = OpenWater.new(0, 10.0)
	traffic.sim = sim
	boat.traffic = traffic
	for row: Array in [
		[INF, INF, 1], [0.9 - 0.003, 1.0, 1], [0.895, 1.0, 2], [-0.2, -0.3, 2], [-0.3, -0.2, 2]
	]:
		traffic.proposed = row[0]
		traffic.current = row[1]
		var expected := traffic.proposed >= minf(0.9, traffic.current) - 0.003
		for known: bool in [false, true]:
			traffic.queries = 0
			var safe := boat._safe(
				Vector2.ONE, Vector2.DOWN, Vector2.DOWN, traffic.current if known else NAN
			)
			check(safe == expected, "Hull clearance for gaps %s, known=%s" % [row, known])
			check(traffic.queries == (1 if known else row[2]), "Hull query count for %s" % [row])
	boat.free()
	traffic.free()
	sim.free()
	finish()
