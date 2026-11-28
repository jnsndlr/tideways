extends "res://tests/rule_test_case.gd"


class OpenWater:
	extends Terrain

	func height_at(_x: float, _z: float) -> float:
		return -30.0


class CrossingFerry:
	extends Ferry

	func wants_to_move() -> bool:
		return true

	func ahead(distance: float) -> Vector2:
		return pos2() + Vector2.RIGHT * distance


func _initialize() -> void:
	run.call_deferred()


func run() -> void:
	var sim := Simulation.new(Callable())
	sim.map = MapData.new()
	sim.map.half_size = 700.0
	sim.terrain = OpenWater.new(0, 10.0)
	root.add_child(sim)
	var traffic := MarineTraffic.new()
	sim.add_child(traffic)
	traffic.sim = sim
	traffic.nav = NavGrid.new(sim.map, sim.terrain)
	var boat := MotorYacht.new()
	sim.add_child(boat)
	boat.traffic = traffic
	boat.apply_spec(VesselTypes.motor_yachts()[0])
	boat.state = MotorYacht.State.CRUISING
	boat.free_nav = true
	boat.speed = boat.cruise
	boat.helm = Helm.new(boat, traffic)
	boat.helm.goal = Vector2(0.0, 500.0)
	traffic.register(boat, MarineTraffic.RANK_POWER)
	boat.helm._decide()
	check(
		boat.helm.want_yaw == 0.0 and boat.helm.want_speed == boat.cruise,
		"A cruising yacht holds course and speed in clear water"
	)
	var ferry := CrossingFerry.new()
	sim.add_child(ferry)
	ferry.vessel_name = "Crossing ferry"
	ferry.speed = 8.0
	ferry.cruise = 8.0
	ferry.half_seg = 22.0
	ferry.hull_radius = 8.0
	ferry.rotation.y = PI / 2.0
	ferry.position = Vector3(-ferry.speed * 4.0, 0.0, boat.speed * 4.0)
	traffic.register(ferry, MarineTraffic.RANK_FERRY)
	boat.helm._decide()
	check(
		boat.helm.give_way_to == ferry, "The next steering decision gives way to the crossing ferry"
	)
	check(
		boat.helm.want_yaw != 0.0 or boat.helm.want_speed < boat.cruise,
		"The yacht turns or slows for the ferry"
	)
	sim.free()
	finish()
