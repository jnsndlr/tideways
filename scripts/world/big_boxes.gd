class_name BigBoxes
extends RefCounted
## Big-box stores (assets/models/retail_stores) on large lots at the edge of town.
## Each lot fronts a straight stretch of an outer street or the main road out, parallel to
## it, its car
## park flush with the road edge and the store behind. Lots are reserved at map build
## and built as the town grows past each store's population; the main road shows as
## the store is built, cars drive in up the car park's end aisles and park.

## [[model, parking] or alternative pair (odd town ids), min population]
const TIERS := [
	[["hearth_and_home", "parking_small"], ["tideline_builders_supply", "parking_medium"], 1500],
	[["mega_mart", "parking_medium"], null, 3000],
	[["megabox_warehouse", "parking_large"], null, 4500],
]
## Car parks as authored in art/warehouse_retail.py: [stall columns, rows].
const PARKING := {"parking_small": [6, 1], "parking_medium": [8, 2], "parking_large": [14, 4]}
const PITCH := 2.75
const STALL := 5.1
const LANE := 6.3
# road centreline to the car park's front edge: the drawn road's edge
const ROAD_GAP := RoadMesh.HALF
const MIN_R := 90.0  # from the square
const EDGE_SHARE := 0.6  # may take only frontage lots ranked past this share (the edge)
const MAX_DROP := 5.0
const STRAIGHT := 1.0  # how far the road may bow across the lot's frontage
const END_CLEAR := 12.0  # keep off the junctions at the road's ends
const BUILD_MINUTES := 720.0
const PARKED_SHARE := 0.55

static var _meshes := {}  # model -> [mesh, foot Rect2 (store-local XZ), parking centre]


static func parking_for(model: String) -> String:
	for tier: Array in TIERS:
		for pick in [tier[0], tier[1]]:
			if pick != null and pick[0] == model:
				return pick[1]
	return "parking_small"


## The store with its car park in front (+Z) and a foundation under the store.
## Returns [mesh, footprint Rect2 in store-local XZ, car park centre].
static func mesh_of(model: String) -> Array:
	if _meshes.has(model):
		return _meshes[model]
	var parking := parking_for(model)
	var store_path := "res://assets/models/retail_stores/%s.glb" % model
	var park_path := "res://assets/models/retail_stores/%s.glb" % parking
	var mb := MeshBuilder.new()
	Models._append_part(mb, ModelParts.baked(store_path), Transform3D.IDENTITY)
	var store := mb.commit().get_aabb()
	var park := ModelParts.baked(park_path).commit().get_aabb()
	var at := Vector3(store.get_center().x, 0.02, store.end.z + 1.0 - park.position.z)
	Models._append_part(mb, ModelParts.baked(park_path), Transform3D(Basis.IDENTITY, at))
	# The gap between the store's front and the car park: paved as a walk.
	mb.box(
		Vector3(at.x, 0.06, store.end.z + 0.5),
		Vector3(park.size.x, 0.12, 1.2),
		Models.KIT_FOUNDATION
	)
	mb.box(
		Vector3(
			store.get_center().x,
			-WorldBuilder.KIT_MAX_DROP * 0.5 + 0.05,
			store.get_center().z - 1.0
		),
		Vector3(store.size.x * 0.96, WorldBuilder.KIT_MAX_DROP, store.size.z * 0.85),
		Models.KIT_FOUNDATION
	)
	var mesh := mb.commit()
	var bb := mesh.get_aabb()
	var foot := Rect2(bb.position.x, bb.position.z, bb.size.x, at.z + park.end.z - bb.position.z)
	_meshes[model] = [mesh, foot, at]
	return _meshes[model]


## Reserves this town's big-box lots, building those its population already has.
static func reserve(b: WorldBuilder, isl: MapData.Town) -> void:
	var plan := isl.street_plan
	if plan == null or b.terrain == null:
		return
	for tier: Array in TIERS:
		var pick: Array = tier[0]
		if tier[1] != null and isl.id % 2 == 1:
			pick = tier[1]
		var got := mesh_of(pick[0])
		var spot := _find(b, isl, got[1])
		if spot.is_empty():
			continue
		var lot := MapData.TownLot.new()
		lot.kind = MapData.TownLot.Kind.BIG_BOX
		lot.model = pick[0]
		lot.need_pop = int(tier[2])
		lot.pos = spot[0]
		lot.yaw = spot[1]
		lot.lot_y = spot[0].y
		lot.street = spot[2]
		isl.growth_lots.append(lot)
		isl.street_lots[lot.street] = int(isl.street_lots.get(lot.street, 0)) + 1
		var fwd := Vector3(sin(lot.yaw), 0.0, cos(lot.yaw))
		var right := Vector3(fwd.z, 0.0, -fwd.x)
		var foot: Rect2 = got[1]
		var u := foot.position.y
		while u <= foot.end.y:
			var v := foot.position.x
			while v <= foot.end.x:
				b._block(lot.pos + fwd * u + right * v, 6.0)
				v += 6.0
			u += 6.0
		if isl.population >= lot.need_pop:
			lot.occupied = true
			level(b, lot)
			b.root.add_child(spawn(lot))
			isl.street_built[lot.street] = int(isl.street_built.get(lot.street, 0)) + 1
			opened(isl, lot)


## A built store's street is paved, and with it the way back to the square.
static func opened(isl: MapData.Town, lot: MapData.TownLot) -> void:
	isl.street_pinned[lot.street] = true


## [store origin (y = pad height), yaw, main-road edge] for a lot of `foot`, or [].
static func _find(b: WorldBuilder, isl: MapData.Town, foot: Rect2) -> Array:
	var plan := isl.street_plan
	var half_w := foot.size.x * 0.5
	for ei in plan.edges.size():
		var e: Dictionary = plan.edges[ei]
		if e.zone < StreetPlan.Zone.OUTER or e.pts.size() < 2:
			continue
		var pts: PackedVector3Array = e.pts
		var near := _streets_near(plan, pts)
		var lamps: Array = []
		if ei < isl.road_lanes.size() and isl.road_main_a.size() > 0:
			for spot: Array in WorldBuilder.street_lamp_spots(
				isl.road_lanes[ei], isl.road_main_a[isl.road_main_a.size() - 1]
			):
				lamps.append(spot[0])
		var walked := 0.0
		var total := RoadMesh.length_of(pts)
		for i in range(1, pts.size()):
			var a := pts[i - 1]
			var p := pts[i]
			walked += Vector2(p.x - a.x, p.z - a.z).length()
			if walked < half_w + END_CLEAR or total - walked < half_w + END_CLEAR:
				continue
			if Vector2(p.x - plan._sq.x, p.z - plan._sq.z).length() < MIN_R:
				continue
			# Tangent across the frontage, and the road must be straight along it.
			var tan := _straight_tangent(pts, p, half_w + 4.0)
			if tan == Vector3.ZERO:
				continue
			for side: float in [1.0, -1.0]:
				var n := Vector3(-tan.z, 0.0, tan.x) * side  # away from the road
				var fwd := -n  # the store faces the road
				var right := Vector3(fwd.z, 0.0, -fwd.x)
				var at := (
					Vector3(p.x, 0.0, p.z)
					+ n * (ROAD_GAP + foot.end.y)
					- right * foot.get_center().x
				)
				var y := _fit(b, at, fwd, foot, near)
				if (
					is_nan(y)
					or _covers_lamp(at, fwd, foot, lamps)
					or _covers_lot(isl, at, fwd, foot)
				):
					continue
				# Pad at the road's height, so the car park meets it level.
				return [Vector3(at.x, p.y, at.z), atan2(fwd.x, fwd.z), ei]
	return []


## Would the lot take any but the town's last-built frontage lots (its edge)?
static func _covers_lot(isl: MapData.Town, at: Vector3, fwd: Vector3, foot: Rect2) -> bool:
	if isl.town_lots == null or isl.town_lots.lots.is_empty():
		return false
	var lots := isl.town_lots.lots
	var edge_rank := int(lots.size() * EDGE_SHARE)
	var right := Vector3(fwd.z, 0.0, -fwd.x)
	var r := foot.grow(4.0)
	for l: Dictionary in lots:
		if int(l.rank) >= edge_rank:
			continue
		for q: Vector2 in l.quad:
			var d := Vector3(q.x - at.x, 0.0, q.y - at.z)
			if r.has_point(Vector2(d.dot(right), d.dot(fwd))):
				return true
	return false


## Would the lot (grown a little) stand over one of the street's lamps?
static func _covers_lamp(at: Vector3, fwd: Vector3, foot: Rect2, lamps: Array) -> bool:
	var right := Vector3(fwd.z, 0.0, -fwd.x)
	var r := foot.grow(1.5)
	r.size.y += 2.0  # out to the lamp row at the road's edge
	for l: Vector3 in lamps:
		var d := l - at
		if r.has_point(Vector2(d.dot(right), d.dot(fwd))):
			return true
	return false


## The road's direction at p if it runs straight (within STRAIGHT) for `reach` either
## side of p, else ZERO.
static func _straight_tangent(pts: PackedVector3Array, p: Vector3, reach: float) -> Vector3:
	var lo := Vector3.INF
	var hi := Vector3.INF
	for q in pts:
		var d := Vector2(q.x - p.x, q.z - p.z).length()
		if d <= reach:
			if lo == Vector3.INF:
				lo = q
			hi = q
	if lo == Vector3.INF or hi == lo:
		return Vector3.ZERO
	var tan := Vector3(hi.x - lo.x, 0.0, hi.z - lo.z)
	if tan.length() < reach * 1.6:
		return Vector3.ZERO  # the road doesn't run on far enough either side
	tan = tan.normalized()
	var n := Vector3(-tan.z, 0.0, tan.x)
	for q in pts:
		var d := Vector3(q.x - p.x, 0.0, q.z - p.z)
		if absf(d.dot(tan)) <= reach and absf(d.dot(n)) > STRAIGHT:
			return Vector3.ZERO
	return tan


## Every plan street segment near this road, for clearance checks.
static func _streets_near(plan: StreetPlan, pts: PackedVector3Array) -> Array:
	var box := Rect2(Vector2(pts[0].x, pts[0].z), Vector2.ZERO)
	for q in pts:
		box = box.expand(Vector2(q.x, q.z))
	box = box.grow(140.0)
	var out: Array = []
	for e in plan.edges:
		for k in range(1, e.pts.size()):
			var s0: Vector3 = e.pts[k - 1]
			if box.has_point(Vector2(s0.x, s0.z)):
				out.append([Vector2(s0.x, s0.z), Vector2(e.pts[k].x, e.pts[k].z)])
	return out


## Pad height for the lot, or NAN if the ground is taken, wet or too steep. The front
## row of samples is the car park's edge, which sits on the road's edge.
static func _fit(b: WorldBuilder, at: Vector3, fwd: Vector3, foot: Rect2, streets: Array) -> float:
	var right := Vector3(fwd.z, 0.0, -fwd.x)
	var lo := INF
	var hi := -INF
	var sum := 0.0
	var count := 0
	var u := foot.position.y - 2.0
	while u <= foot.end.y + 0.01:
		var v := foot.position.x - 2.0
		while v <= foot.end.x + 2.01:
			var q := at + fwd * u + right * v
			if b._is_blocked_off_road(q.x, q.z):
				return NAN
			var q2 := Vector2(q.x, q.z)
			for sg: Array in streets:
				if (
					q2.distance_to(Geometry2D.get_closest_point_to_segment(q2, sg[0], sg[1]))
					< ROAD_GAP - 0.3
				):
					return NAN
			var h := b.terrain.height_v(q)
			lo = minf(lo, h)
			hi = maxf(hi, h)
			sum += h
			count += 1
			v += 4.0
		u += 4.0
	if lo < 3.5 or hi - lo > MAX_DROP:
		return NAN
	return sum / count


## Levels the lot's ground to its pad, stopping at the road edge.
static func level(b: WorldBuilder, lot: MapData.TownLot) -> void:
	var foot: Rect2 = mesh_of(lot.model)[1]
	var fwd := Vector3(sin(lot.yaw), 0.0, cos(lot.yaw))
	b.terrain.level_now(
		Vector3(lot.pos.x, 0.0, lot.pos.z),
		fwd,
		foot.position.y - 2.0,
		foot.end.y,
		foot.position.x - 2.0,
		foot.end.x + 2.0,
		lot.lot_y,
		WorldBuilder.KIT_LOT_BLEND
	)


## The finished store, car park and parked cars, as one node at the lot.
static func spawn(lot: MapData.TownLot) -> Node3D:
	var got := mesh_of(lot.model)
	var node := Node3D.new()
	node.name = "BigBox_%s_%d_%d" % [lot.model, roundi(lot.pos.x), roundi(lot.pos.z)]
	node.transform = Transform3D(
		Basis(Vector3.UP, lot.yaw), Vector3(lot.pos.x, lot.lot_y, lot.pos.z)
	)
	var mi := MeshInstance3D.new()
	mi.mesh = got[0]
	node.add_child(mi)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector2i(roundi(lot.pos.x), roundi(lot.pos.z)))
	for stall: Transform3D in stalls(lot.model):
		if rng.randf() > PARKED_SHARE:
			continue
		var car := MeshInstance3D.new()
		var s := Models.LEGACY_SCALE
		if RoadVehicleModel.authored or ResourceLoader.exists(RoadVehicleModel.ASSET):
			car.mesh = RoadVehicleModel.body_mesh(
				RoadVehicleModel.pick_vehicle(rng.randf()), RoadVehicleModel.pick_paint(rng.randf())
			)
			s = Units.VEHICLE_MODEL_SCALE
		else:
			car.mesh = RoadVehicleModel.classic_car(
				rng.randi_range(0, RoadVehicleModel.CAR_COLORS.size() - 1)
			)
		car.transform = stall.scaled_local(Vector3.ONE * s)
		node.add_child(car)
	return node


## Each stall's centre in store-local space, +Z toward its wheel stop (nose in).
static func stalls(model: String) -> Array[Transform3D]:
	var got := mesh_of(model)
	var at: Vector3 = got[2]
	var cr: Array = PARKING[parking_for(model)]
	var columns: int = cr[0]
	var rows: int = cr[1]
	var block := 2.0 * STALL + LANE
	var depth := STALL + LANE if rows == 1 else rows / 2 * block
	var width := columns * PITCH
	var out: Array[Transform3D] = []
	for row in rows:
		# Authored in Blender (y up the lot); glTF z = -y.
		var near := depth / 2.0 - row / 2 * block
		var dir := -1.0 if row % 2 == 0 else 1.0
		var head := near if dir < 0.0 else near - block
		var z := -(head + dir * STALL / 2.0)
		var nose := Basis(Vector3.UP, 0.0 if dir > 0.0 else PI)
		for i in columns:
			var x := -width / 2.0 + (i + 0.5) * PITCH
			out.append(Transform3D(nose, at + Vector3(x, 0.05, z)))
	return out


## A drive for town cars: from the square along the streets and the main road to the
## lot, in off the road up the car park's end aisle nearer the town.
static func drive(isl: MapData.Town, lot: MapData.TownLot) -> PackedVector3Array:
	var plan := isl.street_plan
	if plan == null or lot.street < 0:
		return PackedVector3Array()
	var e: Dictionary = plan.edges[lot.street]
	var pts: PackedVector3Array = e.pts.duplicate()
	if pts[0].distance_to(plan.nodes[e.a]) > pts[pts.size() - 1].distance_to(plan.nodes[e.a]):
		pts.reverse()
	var path := plan.path_to_node(e.a)
	if path.is_empty():
		return path
	var got := mesh_of(lot.model)
	var foot: Rect2 = got[1]
	var at: Vector3 = got[2]
	var cr: Array = PARKING[parking_for(lot.model)]
	var rows: int = cr[1]
	var depth := STALL + LANE if rows == 1 else rows / 2 * (2.0 * STALL + LANE)
	var aisle: float = cr[0] * PITCH / 2.0 + LANE / 2.0
	var xf := Transform3D(Basis(Vector3.UP, lot.yaw), Vector3(lot.pos.x, lot.lot_y, lot.pos.z))
	# The aisle whose road point comes first along the road from the town.
	var best := []
	for x: float in [at.x - aisle, at.x + aisle]:
		var on_road := xf * Vector3(x, 0.0, foot.end.y + ROAD_GAP)
		var k := 0
		for j in pts.size():
			if pts[j].distance_to(on_road) < pts[k].distance_to(on_road):
				k = j
		if best.is_empty() or k < best[1]:
			best = [x, k, on_road]
	var road := pts.slice(0, best[1])
	if path.size() > 0 and road.size() > 0 and path[path.size() - 1].distance_to(road[0]) < 0.5:
		road = road.slice(1)
	path.append_array(road)
	var x: float = best[0]
	var y := lot.lot_y + 0.05
	var on_road: Vector3 = best[2]
	on_road.y = pts[best[1]].y
	path.append(on_road)
	for z: float in [foot.end.y - 1.0, at.z - depth / 2.0 + 3.5]:
		var q := xf * Vector3(x, 0.0, z)
		q.y = y
		path.append(q)
	return path
