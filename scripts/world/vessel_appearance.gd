class_name VesselAppearance
extends RefCounted
## Resolves a marine hull family to its geometry in the current art style.


static var _art := {}


static func model_scale(spec: VesselSpec) -> float:
	if spec.art_path != "":
		return 1.0  # (drawn at its real size)
	return Models.LEGACY_SCALE * spec.size_factor


## A real-size model (VesselSpec.art_path), baked once.
static func art_mesh(path: String) -> ArrayMesh:
	if not _art.has(path):
		_art[path] = ModelParts.baked(path).commit()
	return _art[path]


static func hull(spec: VesselSpec, variant: int) -> ArrayMesh:
	if spec.art_path != "":
		return art_mesh(spec.art_path)
	match spec.hull:
		VesselSpec.Hull.SLOOP:
			return Models.sailboat()
		VesselSpec.Hull.CONTAINER:
			return Models.cargo_ship(variant)
		VesselSpec.Hull.TANKER:
			return Models.tanker(variant)
		VesselSpec.Hull.BULK_CARRIER:
			return Models.bulk_carrier(variant)
		VesselSpec.Hull.TRAWLER:
			return Models.trawler(variant)
		VesselSpec.Hull.MOTOR_YACHT:
			return Models.motor_yacht(variant)
		VesselSpec.Hull.PILOT_BOAT:
			return Models.pilot_boat(variant)
		VesselSpec.Hull.TUG:
			return Models.tug(variant)
	return null


static func lights(spec: VesselSpec) -> ArrayMesh:
	if spec.art_path != "":
		return Models.sailboat_lights()
	match spec.hull:
		VesselSpec.Hull.SLOOP:
			return Models.sailboat_lights()
		VesselSpec.Hull.CONTAINER:
			return Models.cargo_ship_lights()
		VesselSpec.Hull.TANKER:
			return Models.cargo_ship_lights(CargoShipModel.authored_tanker)
		VesselSpec.Hull.BULK_CARRIER:
			return Models.cargo_ship_lights(CargoShipModel.authored_bulker)
		VesselSpec.Hull.TRAWLER:
			return Models.trawler_lights()
		VesselSpec.Hull.MOTOR_YACHT:
			return Models.motor_yacht_lights()
		VesselSpec.Hull.PILOT_BOAT:
			return Models.pilot_boat_lights()
		VesselSpec.Hull.TUG:
			return Models.tug_lights()
	return null


static func name_plate(spec: VesselSpec, vessel_name: String) -> ArrayMesh:
	if vessel_name.is_empty():
		return null
	match spec.hull:
		VesselSpec.Hull.CONTAINER:
			return Models.cargo_name_plate(vessel_name)
		VesselSpec.Hull.TANKER:
			if CargoShipModel.authored_tanker:
				return Models.cargo_name_plate(vessel_name)
		VesselSpec.Hull.BULK_CARRIER:
			if CargoShipModel.authored_bulker:
				return Models.cargo_name_plate(vessel_name)
	return null


static func running_lights(spec: VesselSpec) -> Array[ArrayMesh]:
	match spec.hull:
		VesselSpec.Hull.PILOT_BOAT:
			return [Models.pilot_boat_nav_lights(), Models.pilot_boat_duty_lights()]
		VesselSpec.Hull.TUG:
			return [Models.tug_nav_lights(), Models.tug_mast_light()]
	return []
