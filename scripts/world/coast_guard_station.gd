class_name CoastGuardStation
extends RefCounted
## Port Rosario's coast guard station (the only one): the station kit along the
## clifftop north of town with a road in front of it into town, a ramp down the
## cliff face to an L-shaped pier, two lifeboat houses over the water off a
## shore deck, the three coast guard vessels at their berths, and a lighthouse
## on the spit. Positions are world metres, read off tools/coast_guard_shots.gd
## --grid and the clifftop heights (the cliff edge runs along x ~ 2530).

const ISLAND := "Port Rosario"
const KIT := "res://assets/models/coast_guard_station/%s.glb"
const WEST := -PI * 0.5   # yaw that turns a model's +z front (or a boat's bow) to the sea
## [model, x, z, yaw] on the clifftop, fronts to the road and the sea.
const BUILDINGS := [
	["watch_tower", 2556.0, -782.0, WEST],
	["station_house", 2566.0, -712.0, WEST],
	["equipment_garage", 2566.0, -660.0, WEST],
]
## The pier: out from the cliff foot, then north along the shore.
const ROOT := Vector2(2530.0, -692.0)
const ELBOW := Vector2(2494.0, -692.0)
const HEAD := Vector2(2494.0, -872.0)
## A deck along the cliff foot south of the pier's root, lifeboat houses off its sea side.
const SHORE_A := Vector2(2521.0, -692.0)
const SHORE_B := Vector2(2521.0, -626.0)
const SHEDS := [Vector2(2506.0, -673.0), Vector2(2506.0, -645.0)]
## The ramp climbs north up the cliff face from the root to the clifftop.
const RAMP_FOOT := Vector3(2519.0, 0.0, -697.0)
const RAMP_TOP := Vector2(2530.0, -772.0)
## The road: along the clifftop in front of the buildings, then off toward town.
const ROAD := [Vector2(2534.0, -772.0), Vector2(2548.0, -760.0), Vector2(2548.0, -600.0), Vector2(2565.0, -545.0)]
const LIGHT_AT := Vector2(2545.0, -798.0)
const RADAR_AT := Vector2(2539.0, -735.0)
const RADAR_SCANNER_Y := 14.45
const RADAR_SPIN_RAD_S := 2.4
const DECK := 2.4
const WIDTH := 6.0
## [model, x, z, yaw]: the cutter alongside the pier, the boats in the lifeboat houses.
const MOORED := [
	["national_security_cutter", 2482.6, -790.0, PI],
	["motor_lifeboat_47", 2506.0, -673.0, WEST],
	["response_boat_small", 2506.0, -645.0, WEST],
]

const PLANK := Color(0.5, 0.42, 0.33)
const PILE := Color(0.3, 0.26, 0.22)


static func build(wb: WorldBuilder) -> void:
	var isl_i := -1
	for i in wb.map.islands.size():
		if wb.map.islands[i].name == ISLAND:
			isl_i = i
	if isl_i < 0:
		return
	for b: Array in BUILDINGS:
		var xf := Transform3D(Basis(Vector3.UP, b[3]), _ground(wb, b[1], b[2]))
		wb._add_mesh(_model(KIT % b[0]), "Coast Guard " + str(b[0])).transform = xf
		wb._entry_light(xf, Vector3(0.0, 3.2, 7.0), Vector3(0.0, 0.1, 8.0), false)
		_clear(wb, Vector2(b[1], b[2]), 14.0)
	var mb := MeshBuilder.new()
	_deck(mb, ELBOW, ROOT)
	_deck(mb, HEAD, ELBOW + Vector2(0, WIDTH * 0.5))
	_deck(mb, SHORE_A, SHORE_B)
	_ramp(wb, mb)
	wb._add_mesh(mb.commit(), "Coast Guard Pier")
	for s: Vector2 in SHEDS:
		wb._add_mesh(_model(KIT % "lifeboat_house"), "Coast Guard lifeboat_house").transform = \
			Transform3D(Basis(Vector3.UP, WEST), Vector3(s.x, 0.4, s.y))
	# The vessels at their berths (MOORED) are CoastGuardBoat's: it sends them on patrol.
	_road(wb, isl_i)
	_lighthouse(wb)
	_radar_tower(wb)
	_clear(wb, Vector2(2560.0, -690.0), 40.0)


static func _model(path: String) -> Mesh:
	return Models._cached(path, func(): return ModelParts.baked(path).commit())


## A plank deck on piles from a to b (axis-aligned), down to the seabed.
static func _deck(mb: MeshBuilder, a: Vector2, b: Vector2) -> void:
	var c := (a + b) * 0.5
	var size := (b - a).abs() + Vector2(WIDTH, WIDTH)
	mb.box(Vector3(c.x, DECK, c.y), Vector3(size.x, 0.35, size.y), PLANK)
	var along := (b - a).normalized()
	var side := Vector2(-along.y, along.x)
	var t := 0.0
	var n := (b - a).length()
	while t <= n:
		for s: float in [-1.0, 1.0]:
			var q := a + along * t + side * s * (WIDTH * 0.5 - 0.3)
			mb.box(Vector3(q.x, DECK - 9.0, q.y), Vector3(0.45, 18.0, 0.45), PILE)
		t += 6.0


## A timber ramp on trestles up the cliff face, with a rail on its sea side.
static func _ramp(wb: WorldBuilder, mb: MeshBuilder) -> void:
	var foot := Vector3(RAMP_FOOT.x, DECK, RAMP_FOOT.z)
	var top := _ground(wb, RAMP_TOP.x, RAMP_TOP.y)
	var n := 14
	for i in n:
		var a := foot.lerp(top, float(i) / n)
		var b := foot.lerp(top, float(i + 1) / n)
		var mid := (a + b) * 0.5
		var run := b - a
		mb.xform = Transform3D(Basis.looking_at(run.normalized()), mid)
		mb.box(Vector3.ZERO, Vector3(4.0, 0.3, run.length() + 0.1), PLANK)
		mb.box(Vector3(-1.9, 1.0, 0.0), Vector3(0.12, 0.12, run.length() + 0.1), PILE)
		mb.xform = Transform3D.IDENTITY
		mb.box(Vector3(a.x - 1.8, a.y - 6.0, a.z), Vector3(0.4, 12.0, 0.4), PILE)
	mb.xform = Transform3D.IDENTITY


## The station's road: along the clifftop, then to the nearest street of
## Port Rosario, which it joins paved.
static func _road(wb: WorldBuilder, isl_i: int) -> void:
	var pts := PackedVector3Array()
	for i in ROAD.size() - 1:
		var a: Vector2 = ROAD[i]
		var b: Vector2 = ROAD[i + 1]
		var n := maxi(2, ceili(a.distance_to(b) / 3.0))
		for k in n:
			var q := a.lerp(b, float(k) / n)
			pts.append(Vector3(q.x, wb.terrain.height_at(q.x, q.y) + 0.45, q.y))
	var out: Vector2 = ROAD[ROAD.size() - 1]
	var best := Vector3.ZERO
	var best_d := INF
	var best_town: MapData.Town = null
	var best_lane := -1
	for t in wb.map.towns:
		if t.island != isl_i:
			continue
		var lines: Array[PackedVector3Array] = [t.road_main_a, t.road_main_b]
		lines.append_array(t.road_cross)
		lines.append_array(t.road_lanes)
		for li in lines.size():
			for q in lines[li]:
				var dd := Vector2(q.x - out.x, q.z - out.y).length()
				if dd < best_d:
					best_d = dd
					best = q
					best_town = t
					best_lane = li - (lines.size() - t.road_lanes.size())
	var n := maxi(2, ceili(best_d / 3.0))
	for k in range(0, n + 1):
		var q := Vector3(out.x, 0, out.y).lerp(best, float(k) / n)
		var h := wb.terrain.height_at(q.x, q.z)
		if h < 0.6:
			print("coast guard road: water in the way at ", q)
			break
		pts.append(Vector3(q.x, h + 0.45, q.z) if k < n else best)
	if best_town != null and best_lane >= 0:
		best_town.street_pinned[best_lane] = true
	var mb := MeshBuilder.new()
	RoadMesh.strip(mb, pts, WorldBuilder.ROAD, RoadMesh.Style.DASHED, func(_s: float) -> float: return 1.0)
	var mat := ShaderMaterial.new()
	mat.shader = load(WorldBuilder.ROAD_SHADER)
	wb._add_mesh(mb.commit(mat), "Coast Guard Road", false)
	for i in range(0, pts.size(), 2):
		wb._block_road(pts[i], 9.0)


## A lighthouse on the tip of the spit, its beam turning at night.
static func _lighthouse(wb: WorldBuilder) -> void:
	var p := _ground(wb, LIGHT_AT.x, LIGHT_AT.y)
	var mb := MeshBuilder.new()
	var gallery := Models.add_lighthouse(mb, p - Vector3(0, 0.3, 0), 0, WEST)
	wb._add_mesh(mb.commit(), "Coast Guard Lighthouse")
	var lamp := gallery * (Vector3.UP * Models.LIGHTHOUSE_LENS_Y)
	var beacon := Color(1.0, 0.92, 0.75)
	wb.glows.xform = Transform3D.IDENTITY
	wb.glows.glow(lamp, beacon, 2.4, 9.0, true, 0.0, Vector3.ZERO, 0.0)
	wb.glows.beam(lamp, beacon, 6.6, 225.0, 0.5, 0.3, 0.0)
	wb._block(p, 14.0)


## Radar tower on the clifftop with a spinning open-array scanner and red beacons.
static func _radar_tower(wb: WorldBuilder) -> void:
	var xf := Transform3D(Basis(Vector3.UP, WEST), _ground(wb, RADAR_AT.x, RADAR_AT.y))
	var tower := wb._add_mesh(_model(KIT % "radar_tower"), "Coast Guard radar_tower")
	tower.transform = xf
	var scanner := _RadarSpinner.new()
	scanner.name = "Coast Guard radar_scanner"
	scanner.mesh = _model(KIT % "radar_tower_scanner")
	scanner.position = Vector3(0.0, RADAR_SCANNER_Y, 0.0)
	tower.add_child(scanner)
	# Red aviation obstruction beacons (top mast + 4 upper deck corners)
	var red := Color(1.0, 0.22, 0.16)
	wb.glows.xform = xf
	wb.glows.glow(Vector3(2.35, 17.45, -2.35), red, 0.45, 14.0, false, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	for sx: float in [-1.82, 1.82]:
		for sz: float in [-1.82, 1.82]:
			wb.glows.glow(Vector3(sx, 13.78, sz), red, 0.22, 6.0, false, 0.0, Vector3.ZERO, Models.LAMP_ON_AT)
	wb.glows.xform = Transform3D.IDENTITY
	_clear(wb, RADAR_AT, 18.0)


class _RadarSpinner extends MeshInstance3D:
	func _process(delta: float) -> void:
		rotate_y(delta * RADAR_SPIN_RAD_S)


static func _ground(wb: WorldBuilder, x: float, z: float) -> Vector3:
	var h := INF
	for o: Vector2 in [Vector2.ZERO, Vector2(5, 5), Vector2(-5, 5), Vector2(5, -5), Vector2(-5, -5)]:
		h = minf(h, wb.terrain.height_at(x + o.x, z + o.y))
	return Vector3(x, h, z)


static func _clear(wb: WorldBuilder, at: Vector2, r: float) -> void:
	var u := -r
	while u <= r:
		var v := -r
		while v <= r:
			wb._block(Vector3(at.x + u, 0, at.y + v), 6.0)
			v += 9.0
		u += 9.0
