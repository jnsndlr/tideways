class_name CoastGuardStation
extends RefCounted
## Port Rosario's coast guard station (the only one): the station kit along the
## clifftop north of town with a road in front of it into town, a ramp down the
## cliff face to an L-shaped pier, two lifeboat houses over the water off a
## shore deck, the three coast guard vessels at their berths, and a lighthouse
## on the spit. Positions are world metres, read off tools/coast_guard_shots.gd
## --grid and the clifftop heights (the cliff edge runs along x ~ 2530).

const DockKit := preload("res://scripts/world/dock_kit.gd")
const KIT := "res://assets/models/coast_guard_station/%s.glb"
## [model, x, z, yaw, front] on the clifftop, fronts to the road and the sea;
## front is how far the front wall stands out from the model's centre (its door light).
const BUILDINGS := [
	["watch_tower", 2537.0, -784.0, 0.0, 2.05],  # at the road's end, facing it
	["station_house", 2560.6, -712.0, CoastGuardLayout.WEST, 6.0],  # fronts 1.5 m off the road's edge
	["equipment_garage", 2558.1, -660.0, CoastGuardLayout.WEST, 3.5],
]
## The pier: out from the cliff foot, then north along the shore.
const ROOT := Vector2(2530.0, -692.0)
const ELBOW := Vector2(2494.0, -692.0)
const HEAD := Vector2(2494.0, -872.0)
## A deck along the cliff foot south of the pier's root, lifeboat houses off its sea side.
const SHORE_A := Vector2(2521.0, -692.0)
const SHORE_B := Vector2(2521.0, -626.0)
const SHEDS := [Vector2(2506.0, -673.0), Vector2(2506.0, -645.0)]
const LIGHT_AT := Vector2(2545.0, -798.0)
const RADAR_AT := Vector2(2539.0, -735.0)
const RADAR_SCANNER_Y := 14.45
const RADAR_SPIN_RAD_S := 2.4
const PILE := Color(0.3, 0.26, 0.22)

static func build(wb: WorldBuilder) -> void:
	var isl_i := -1
	for i in wb.map.islands.size():
		if wb.map.islands[i].name == CoastGuardLayout.ISLAND:
			isl_i = i
	if isl_i < 0:
		return
	for b: Array in BUILDINGS:
		var xf := Transform3D(Basis(Vector3.UP, b[3]), _ground(wb, b[1], b[2]))
		wb._add_mesh(_model(KIT % b[0]), "Coast Guard " + str(b[0])).transform = xf
		var front: float = b[4]
		wb._entry_light(xf, Vector3(0.0, 3.2, front + 0.2), Vector3(0.0, 0.1, front + 1.2), false)
		_clear(wb, Vector2(b[1], b[2]), 14.0)
	_docks(wb)
	for s: Vector2 in SHEDS:
		var house := wb._add_mesh(_model(KIT % "lifeboat_house"), "Coast Guard lifeboat_house")
		house.transform = Transform3D(Basis(Vector3.UP, CoastGuardLayout.WEST), Vector3(s.x, 0.4, s.y))
	# The vessels at their berths (CoastGuardLayout.MOORED) are CoastGuardBoat's: it sends them on patrol.
	_road(wb, isl_i)
	_lighthouse(wb)
	_radar_tower(wb)
	_clear(wb, Vector2(2560.0, -690.0), 40.0)

static func _model(path: String) -> Mesh:
	return Models._cached(path, func(): return ModelParts.baked(path).commit())

## The pier from the dock kit, fixed main deck on piles: out from the cliff foot
## (ROOT) to the elbow, north to the head (then a ramp down to a float), and the shore deck
## south past the
## lifeboat houses. Each run is a whole number of DockKit.RUN sections.
static func _docks(wb: WorldBuilder) -> void:
	if not DockKit.available():
		return
	var kit := DockKit.new()
	kit.name = "Coast Guard Pier"
	wb.root.add_child(kit)
	var half := DockKit.MAIN_WIDTH * 0.5
	# West from the cliff foot to the elbow's far edge, so the corner is covered.
	var west := int(roundf((ROOT.x + 4.0 - (ELBOW.x - half)) / DockKit.RUN))
	var p := Vector3(ELBOW.x - half + west * DockKit.RUN, CoastGuardLayout.DECK, ROOT.y)
	for k in west:
		p = kit.add_deck(DockKit.Width.MAIN, p, Vector2(-1, 0), DockKit.Support.PILES)
	# North from the elbow's north edge to the head.
	p = Vector3(ELBOW.x, CoastGuardLayout.DECK, ELBOW.y - half)
	for k in int(roundf((ELBOW.y - half - HEAD.y) / DockKit.RUN)):
		p = kit.add_deck(DockKit.Width.MAIN, p, Vector2(0, -1), DockKit.Support.PILES)
	# Off the head, a ramp down to a float landing for the small boats.
	p = kit.add_ramp(DockKit.Width.MAIN, p, Vector2(0, -1), DockKit.LOW)
	for k in 2:
		p = kit.add_deck(DockKit.Width.MAIN, p, Vector2(0, -1), DockKit.Support.FLOATS)
	# South along the cliff foot from the elbow run's south edge.
	p = Vector3(SHORE_A.x, CoastGuardLayout.DECK, SHORE_A.y + half)
	for k in int(roundf((SHORE_B.y - SHORE_A.y - half) / DockKit.RUN)):
		p = kit.add_deck(DockKit.Width.MAIN, p, Vector2(0, 1), DockKit.Support.PILES)
	_ramp(wb, kit)
	kit.bake()

## The way up the cliff: dock kit ramp sections chained from the elbow run's north
## edge (CoastGuardLayout.RAMP_FOOT) to the clifftop, on timber posts down to the rock.
static func _ramp(wb: WorldBuilder, kit: Node3D) -> void:
	var isl_i := -1
	for i in wb.map.islands.size():
		if wb.map.islands[i].name == CoastGuardLayout.ISLAND:
			isl_i = i
	var ends: PackedVector3Array = wb.map.islands[isl_i].service_ramp
	if ends.size() < 2:
		return
	var foot := ends[0]
	var top := ends[1]
	var flat := Vector2(top.x - foot.x, top.z - foot.z)
	var n := maxi(1, roundi(flat.length() / DockKit.RUN))
	var dir := flat.normalized()
	var mb := MeshBuilder.new()
	var p := foot
	for i in n:
		var next_y := lerpf(foot.y, top.y + 0.05, float(i + 1) / n)
		p = kit.add_ramp(DockKit.Width.MAIN, p, dir, next_y)
		var g := wb.terrain.height_at(p.x, p.z)
		if i < n - 1 and p.y - g > 0.5:
			for side: float in [-1.0, 1.0]:
				var q := p + Vector3(-dir.y, 0.0, dir.x) * side * (DockKit.MAIN_WIDTH * 0.5 - 0.3)
				var low := minf(g, wb.terrain.height_at(q.x, q.z)) - 1.0
				mb.box(
					Vector3(q.x, (p.y - 0.25 + low) * 0.5, q.z),
					Vector3(0.32, p.y - 0.25 - low, 0.32),
					PILE
				)
	wb._add_mesh(mb.commit(), "Coast Guard Ramp Posts")

## The station's road, graded at map generation (MapGenerator._grade_coast_guard_road)
## on to the nearest street of Port Rosario, which it joins paved.
static func _road(wb: WorldBuilder, isl_i: int) -> void:
	var pts := PackedVector3Array(wb.map.islands[isl_i].service_road)
	if pts.size() < 2:
		return
	# Tuck its end just under the street it runs on to, so the two don't flicker.
	pts[pts.size() - 1].y -= 0.03
	var mb := MeshBuilder.new()
	RoadMesh.strip(
		mb, pts, WorldBuilder.ROAD, RoadMesh.Style.DASHED, func(_s: float) -> float: return 1.0
	)
	var mat := ShaderMaterial.new()
	mat.shader = load(WorldBuilder.ROAD_SHADER)
	wb._add_mesh(mb.commit(mat), "Coast Guard Road", false)
	for i in range(0, pts.size(), 3):
		wb._block_road(pts[i], 9.0)

## A lighthouse on the tip of the spit, its beam turning at night.
static func _lighthouse(wb: WorldBuilder) -> void:
	var p := _ground(wb, LIGHT_AT.x, LIGHT_AT.y)
	var mb := MeshBuilder.new()
	var gallery := Models.add_lighthouse(mb, p - Vector3(0, 0.3, 0), 0, CoastGuardLayout.WEST)
	wb._add_mesh(mb.commit(), "Coast Guard Lighthouse")
	var lamp := gallery * (Vector3.UP * Models.LIGHTHOUSE_LENS_Y)
	var beacon := Color(1.0, 0.92, 0.75)
	wb.glows.xform = Transform3D.IDENTITY
	wb.glows.glow(lamp, beacon, 2.4, 9.0, true, 0.0, Vector3.ZERO, 0.0)
	wb.glows.beam(lamp, beacon, 6.6, 225.0, 0.5, 0.3, 0.0)
	wb._block(p, 14.0)

## Radar tower on the clifftop with a spinning open-array scanner and red beacons.
static func _radar_tower(wb: WorldBuilder) -> void:
	var xf := Transform3D(Basis(Vector3.UP, CoastGuardLayout.WEST), _ground(wb, RADAR_AT.x, RADAR_AT.y))
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
	wb.glows.glow(
		Vector3(2.35, 17.45, -2.35), red, 0.45, 14.0, false, 0.0, Vector3.ZERO, Models.LAMP_ON_AT
	)
	for sx: float in [-1.82, 1.82]:
		for sz: float in [-1.82, 1.82]:
			wb.glows.glow(
				Vector3(sx, 13.78, sz), red, 0.22, 6.0, false, 0.0, Vector3.ZERO, Models.LAMP_ON_AT
			)
	wb.glows.xform = Transform3D.IDENTITY
	_clear(wb, RADAR_AT, 18.0)


class _RadarSpinner:
	extends MeshInstance3D

	func _process(delta: float) -> void:
		rotate_y(delta * RADAR_SPIN_RAD_S)

static func _ground(wb: WorldBuilder, x: float, z: float) -> Vector3:
	var h := INF
	for o: Vector2 in [
		Vector2.ZERO, Vector2(5, 5), Vector2(-5, 5), Vector2(5, -5), Vector2(-5, -5)
	]:
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
