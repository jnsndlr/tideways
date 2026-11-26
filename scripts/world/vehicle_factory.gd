class_name VehicleFactory
extends RefCounted
## Builds the visible vehicle and initializes its dimensions and movement for the
## terminal queue or ferry deck. Draw from the simulation RNG in spawn order.

const TRUCK_SHARE := TrafficDemand.DEFAULT_TRUCK_SHARE


static func create(rng: RandomNumberGenerator, truck_share := TRUCK_SHARE) -> Vehicle:
	var truck := rng.randf() < clampf(truck_share, 0.0, 1.0)
	if not Models.mid_cars:
		return from_parts(truck, "", rng.randi_range(0, Models.CAR_COLORS.size() - 1))
	var model: String
	if truck:
		model = Models.pick_weighted(Models.TRUCKS, rng.randf())
		if model == "rig":
			model = Models.pick_weighted(Models.TRACTORS, rng.randf())
	else:
		model = Models.pick_vehicle(rng.randf())
	var paint := Models.pick_paint(rng.randf())
	if Models.TRACTORS.has(model):
		var trailer := Models.pick_weighted(Models.TRAILERS, rng.randf())
		return from_parts(truck, model, paint, trailer, Models.pick_paint(rng.randf()))
	return from_parts(truck, model, paint)


## Construct the selected body and trailer without consuming the simulation RNG.
## Empty body model selects a classic car or truck and its own color palette.
static func from_parts(
	truck: bool, model: String, paint: int, trailer := "", trailer_paint := -1
) -> Vehicle:
	if model.is_empty():
		if paint < 0 or paint >= Models.CAR_COLORS.size() or trailer != "" or trailer_paint != -1:
			return null
		var classic := Vehicle.new()
		var mesh := Models.truck(paint) if truck else Models.car(paint)
		classic.setup(_body(mesh), truck, "", Models.LEGACY_SCALE)
		classic.body_paint = paint
		return classic
	if not Models.mid_cars and not ResourceLoader.exists(Models.VEHICLES_GLB):
		return null
	var rig := Models.TRACTORS.has(model)
	if truck:
		if not rig and (not Models.TRUCKS.has(model) or model == "rig"):
			return null
	elif not Models.VEHICLES.has(model):
		return null
	if paint < 0 or paint >= Models.PAINTS.size():
		return null
	if rig:
		if (
			not Models.TRAILERS.has(trailer)
			or trailer_paint < 0
			or trailer_paint >= Models.PAINTS.size()
		):
			return null
	elif trailer != "" or trailer_paint != -1:
		return null

	var vehicle := Vehicle.new()
	vehicle.setup(_body(Models.vehicle(model, paint)), truck, model, Models.VEHICLE_SCALE)
	vehicle.body_paint = paint
	if truck:
		vehicle.speed = 20.0
	if rig:
		vehicle.attach_trailer(trailer, _body(Models.vehicle(trailer, trailer_paint)))
		vehicle.trailer_paint = trailer_paint
	return vehicle


static func _body(mesh: Mesh) -> MeshInstance3D:
	var body := MeshInstance3D.new()
	body.mesh = mesh
	return body
