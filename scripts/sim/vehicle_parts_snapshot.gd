class_name VehiclePartsSnapshot
extends RefCounted


## The same vehicle identity travels with a car from the holding lot to the ferry.
static func capture(car: Vehicle) -> Dictionary:
	return {
		"truck": car.is_truck,
		"model": car.model,
		"paint": car.body_paint,
		"trailer": car.trailer_model,
		"trailer_paint": car.trailer_paint
	}


static func rebuild(row: Dictionary, factory: Callable) -> Vehicle:
	if (
		not row.get("truck") is bool
		or not row.get("model") is String
		or not row.get("trailer") is String
		or not _palette_index(row.get("paint"))
		or not _palette_index(row.get("trailer_paint"))
	):
		return null
	return factory.call(row.truck, row.model, int(row.paint), row.trailer, int(row.trailer_paint))


static func _palette_index(v: Variant) -> bool:
	return (
		(v is int or v is float) and is_finite(v) and v >= -1 and v <= 2147483647 and floor(v) == v
	)
