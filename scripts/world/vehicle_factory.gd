class_name VehicleFactory
extends RefCounted
## Builds the visible vehicle and initializes its dimensions and movement for the
## terminal queue or ferry deck. Draw from the simulation RNG in spawn order.

const TRUCK_SHARE := TrafficDemand.DEFAULT_TRUCK_SHARE


static func create(rng: RandomNumberGenerator, truck_share := TRUCK_SHARE) -> Vehicle:
	var truck := rng.randf() < clampf(truck_share, 0.0, 1.0)
	if not RoadVehicleModel.authored:
		return from_parts(truck, "", rng.randi_range(0, RoadVehicleModel.CAR_COLORS.size() - 1))
	var model: String
	if truck:
		model = RoadVehicleModel.pick_weighted(RoadVehicleModel.TRUCKS, rng.randf())
		if model == "rig":
			model = RoadVehicleModel.pick_weighted(RoadVehicleModel.TRACTORS, rng.randf())
	else:
		model = RoadVehicleModel.pick_vehicle(rng.randf())
	var paint := RoadVehicleModel.pick_paint(rng.randf())
	if RoadVehicleModel.TRACTORS.has(model):
		var trailer := RoadVehicleModel.pick_weighted(RoadVehicleModel.TRAILERS, rng.randf())
		return from_parts(truck, model, paint, trailer, RoadVehicleModel.pick_paint(rng.randf()))
	return from_parts(truck, model, paint)


## Construct the selected body and trailer without consuming the simulation RNG.
## Empty body model selects a classic car or truck and its own color palette.
static func from_parts(
	truck: bool, model: String, paint: int, trailer := "", trailer_paint := -1
) -> Vehicle:
	if model.is_empty():
		if (
			paint < 0
			or paint >= RoadVehicleModel.CAR_COLORS.size()
			or trailer != ""
			or trailer_paint != -1
		):
			return null
		var classic := Vehicle.new()
		var mesh := (
			RoadVehicleModel.classic_truck(paint) if truck else RoadVehicleModel.classic_car(paint)
		)
		classic.setup(_body(mesh), truck, "", Models.LEGACY_SCALE)
		classic.body_paint = paint
		return classic
	if not RoadVehicleModel.authored and not ResourceLoader.exists(RoadVehicleModel.ASSET):
		return null
	var rig := RoadVehicleModel.TRACTORS.has(model)
	if truck:
		if not rig and (not RoadVehicleModel.TRUCKS.has(model) or model == "rig"):
			return null
	elif not RoadVehicleModel.VEHICLES.has(model):
		return null
	if paint < 0 or paint >= RoadVehicleModel.PAINTS.size():
		return null
	if rig:
		if (
			not RoadVehicleModel.TRAILERS.has(trailer)
			or trailer_paint < 0
			or trailer_paint >= RoadVehicleModel.PAINTS.size()
		):
			return null
	elif trailer != "" or trailer_paint != -1:
		return null

	var vehicle := Vehicle.new()
	vehicle.setup(
		_body(RoadVehicleModel.body_mesh(model, paint)), truck, model, Units.VEHICLE_MODEL_SCALE
	)
	vehicle.body_paint = paint
	if truck:
		vehicle.speed = 20.0
	if rig:
		vehicle.attach_trailer(trailer, _body(RoadVehicleModel.body_mesh(trailer, trailer_paint)))
		vehicle.trailer_paint = trailer_paint
	return vehicle


static func _body(mesh: Mesh) -> MeshInstance3D:
	var body := MeshInstance3D.new()
	body.mesh = mesh
	return body
