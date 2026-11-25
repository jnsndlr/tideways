class_name VehicleFactory
extends RefCounted
## Builds the visible vehicle and initializes its dimensions and movement for the
## terminal queue or ferry deck. Draw from the simulation RNG in spawn order.

const TRUCK_SHARE := TrafficDemand.DEFAULT_TRUCK_SHARE


static func create(rng: RandomNumberGenerator, truck_share := TRUCK_SHARE) -> Vehicle:
	var vehicle := Vehicle.new()
	var truck := rng.randf() < clampf(truck_share, 0.0, 1.0)
	if not Models.mid_cars:
		var col := rng.randi_range(0, Models.CAR_COLORS.size() - 1)
		var mesh := Models.truck(col) if truck else Models.car(col)
		vehicle.setup(_body(mesh), truck, "", Models.LEGACY_SCALE)
	elif truck:
		var model := Models.pick_weighted(Models.TRUCKS, rng.randf())
		var rig := model == "rig"
		if rig:
			model = Models.pick_weighted(Models.TRACTORS, rng.randf())
		vehicle.setup(_painted_body(model, rng), true, model, Models.VEHICLE_SCALE)
		vehicle.speed = 20.0
		if rig:
			var trailer := Models.pick_weighted(Models.TRAILERS, rng.randf())
			vehicle.attach_trailer(trailer, _painted_body(trailer, rng))
	else:
		var model := Models.pick_vehicle(rng.randf())
		vehicle.setup(_painted_body(model, rng), false, model, Models.VEHICLE_SCALE)
	return vehicle


static func _painted_body(model: String, rng: RandomNumberGenerator) -> MeshInstance3D:
	return _body(Models.vehicle(model, Models.pick_paint(rng.randf())))


static func _body(mesh: Mesh) -> MeshInstance3D:
	var body := MeshInstance3D.new()
	body.mesh = mesh
	return body
