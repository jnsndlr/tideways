class_name VehicleFactory
extends RefCounted
## Builds the visible vehicle and initializes its dimensions and movement for the
## terminal queue or ferry deck. Draw from the simulation RNG in spawn order.

const TRUCK_SHARE := 0.12


static func create(rng: RandomNumberGenerator) -> Vehicle:
	var vehicle := Vehicle.new()
	var truck := rng.randf() < TRUCK_SHARE
	if not Models.mid_cars:
		var col := rng.randi_range(0, Models.CAR_COLORS.size() - 1)
		vehicle.setup(Models.truck(col) if truck else Models.car(col), truck)
	elif truck:
		var model := Models.pick_weighted(Models.TRUCKS, rng.randf())
		var rig := model == "rig"
		if rig:
			model = Models.pick_weighted(Models.TRACTORS, rng.randf())
		vehicle.setup(Models.vehicle(model, Models.pick_paint(rng.randf())), true, model, Models.VEHICLE_SCALE)
		vehicle.speed = 20.0
		if rig:
			var trailer := Models.pick_weighted(Models.TRAILERS, rng.randf())
			vehicle.attach_trailer(trailer, Models.vehicle(trailer, Models.pick_paint(rng.randf())))
	else:
		var model := Models.pick_vehicle(rng.randf())
		vehicle.setup(Models.vehicle(model, Models.pick_paint(rng.randf())), false, model, Models.VEHICLE_SCALE)
	return vehicle
