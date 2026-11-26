class_name FerryWalkOnSnapshot
extends RefCounted
## Fare credit already lives in the ledger and passenger manifest. These walkers
## only finish the visual approach and release the ramp for vehicle loading.


static func capture(ferry: Ferry) -> Dictionary:
	var walkers := []
	for walker in ferry._pax_walkers:
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
	return {
		"clearing": ferry._load_phase == Ferry.LoadPhase.WALK_ON_CLEAR,
		"started": ferry._walk_ons_since,
		"clear_since": ferry._walk_on_clear_since,
		"dispatch": ferry._pax_dispatch_timer,
		"sent": ferry._pax_walkers_sent,
		"walkers": walkers,
	}


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
	for row in data.walkers:
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
		if counts.get(int(variant), 0) == 0:
			return false
		counts[int(variant)] -= 1
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
	for row in data.walkers:
		var walker := ferry.sim.make_passenger(int(row.variant))
		walker.position = SnapshotVector3.decode(row.position)
		walker.rotation.y = row.yaw
		var path := PackedVector3Array()
		for point in row.path:
			path.append(SnapshotVector3.decode(point))
		ferry._pax_walkers.append(walker)
		walker.walk(path, ferry._on_walker_aboard)
