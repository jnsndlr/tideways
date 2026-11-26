class_name FerryWalkOnSnapshot
extends RefCounted
## Fare credit already lives in the ledger and passenger manifest. These walkers
## only finish the visual approach and release the ramp for vehicle loading.


static func capture(ferry: Ferry) -> Dictionary:
	return {
		"clearing": ferry._load_phase == Ferry.LoadPhase.WALK_ON_CLEAR,
		"started": ferry._walk_ons_since,
		"clear_since": ferry._walk_on_clear_since,
		"dispatch": ferry._pax_dispatch_timer,
		"sent": ferry._pax_walkers_sent,
		"walkers": capture_walkers(ferry._pax_walkers),
	}


static func capture_walkers(actors: Array[Passenger]) -> Array:
	var walkers := []
	for walker in actors:
		var path := []
		for point in walker.path:
			path.append(SnapshotVector3.encode(point))
		(
			walkers
			. append(
				{
					"variant": walker.variant,
					"position": SnapshotVector3.encode(walker.position),
					"yaw": walker.rotation.y,
					"path": path,
				}
			)
		)
	return walkers


static func valid(data: Variant, passengers: Array[Dictionary]) -> bool:
	if (
		not data is Dictionary
		or not data.get("clearing") is bool
		or not data.get("walkers") is Array
	):
		return false
	for field in ["started", "clear_since", "dispatch", "sent"]:
		var value: Variant = data.get(field)
		if not (value is int or value is float) or not is_finite(value):
			return false
	if data.started < -1 or data.clear_since < 0 or floor(data.sent) != data.sent:
		return false
	if data.sent > passengers.size() or data.sent < data.walkers.size():
		return false
	var counts := {}
	for pax in passengers:
		counts[pax.variant] = counts.get(pax.variant, 0) + 1
	if not valid_walkers(data.walkers):
		return false
	for row in data.walkers:
		var variant := int(row.variant)
		if counts.get(variant, 0) == 0:
			return false
		counts[variant] -= 1
	return true


static func valid_walkers(walkers: Variant) -> bool:
	if not walkers is Array:
		return false
	for row in walkers:
		if not row is Dictionary or not SnapshotVector3.valid(row.get("position")):
			return false
		var variant: Variant = row.get("variant")
		if (
			not (variant is int or variant is float)
			or not is_finite(variant)
			or floor(variant) != variant
			or variant < 0
			or variant >= Passenger.VARIANT_COUNT
		):
			return false
		var yaw: Variant = row.get("yaw")
		if not (yaw is float or yaw is int) or not is_finite(yaw):
			return false
		if (
			not row.get("path") is Array
			or row.path.is_empty()
			or not row.path.all(SnapshotVector3.valid)
		):
			return false
	return true


static func install(data: Dictionary, ferry: Ferry) -> void:
	ferry._load_phase = Ferry.LoadPhase.WALK_ON_CLEAR if data.clearing else Ferry.LoadPhase.WALK_ONS
	ferry._walk_ons_since = data.started
	ferry._walk_on_clear_since = data.clear_since
	ferry._pax_dispatch_timer = data.dispatch
	ferry._pax_walkers_sent = int(data.sent)
	install_walkers(data.walkers, ferry, ferry._pax_walkers, ferry._on_walker_aboard)


static func install_walkers(
	rows: Array, ferry: Ferry, actors: Array[Passenger], arrived: Callable
) -> void:
	for row in rows:
		var walker := ferry.sim.make_passenger(int(row.variant))
		walker.position = SnapshotVector3.decode(row.position)
		walker.rotation.y = row.yaw
		var path := PackedVector3Array()
		for point in row.path:
			path.append(SnapshotVector3.decode(point))
		actors.append(walker)
		walker.walk(path, arrived)
