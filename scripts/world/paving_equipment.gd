class_name PavingEquipment
extends RefCounted
## Terminal paving kit, in metres. Each root sits on the ground and faces +Z.
## Instances share meshes; only the loader's lifting boom needs a separate draw.

const YELLOW := Color("#ebb437")
const OCHRE := Color("#bc791e")
const STEEL := Color("#465158")
const RUBBER := Color("#252a2e")
const GLASS := Color("#487785")
const ORANGE := Color("#ef7044")
const BOOM_PIVOT := Vector3(0, 1.68, 0.18)

static var _loader_mesh: ArrayMesh
static var _boom_mesh: ArrayMesh
static var _roller_mesh: ArrayMesh
static var _materials_mesh: ArrayMesh
static var _barricade_mesh: ArrayMesh


## Wheel loader, 3.1 m wide across the bucket and 7 m long. Tilt Boom about
## its local X axis (negative to lift). Child geometry follows its hinge.
static func loader() -> Node3D:
	if _loader_mesh == null:
		_loader_mesh = _build_loader()
		_boom_mesh = _build_boom()
	var root := _instance(_loader_mesh, "WheelLoader")
	var boom := _instance(_boom_mesh, "Boom")
	boom.position = BOOM_PIVOT
	root.add_child(boom)
	return root


## Tandem road roller, 2.5 m wide and 5.1 m long.
static func roller() -> Node3D:
	if _roller_mesh == null:
		_roller_mesh = _build_roller()
	return _instance(_roller_mesh, "RoadRoller")


## Aggregate and road fabric stockpile, fits a 4 × 7 m staging footprint.
static func materials() -> Node3D:
	if _materials_mesh == null:
		_materials_mesh = _build_materials()
	return _instance(_materials_mesh, "PavingMaterials")


## Freestanding striped barricade, 2.4 m wide, 0.8 m deep.
static func barricade() -> Node3D:
	if _barricade_mesh == null:
		_barricade_mesh = _build_barricade()
	return _instance(_barricade_mesh, "WorkBarricade")


static func _instance(mesh: ArrayMesh, label: String) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = label
	node.mesh = mesh
	return node


## Wheel/drum axis is transverse. The cap colour picks out the hub or rim
## without adding extra material slots.
static func _axle(mb: MeshBuilder, center: Vector3, width: float, radius: float, body: Color, cap: Color) -> void:
	mb.xform = Transform3D(Basis(Vector3.FORWARD, PI * 0.5), center - Vector3.RIGHT * width * 0.5)
	mb.cylinder(Vector3.ZERO, radius, radius, width, 12, body, cap, 0, true)
	mb.xform = Transform3D.IDENTITY


static func _strut(mb: MeshBuilder, a: Vector3, b: Vector3, width: float, depth: float, col: Color) -> void:
	var axis := b - a
	# Lift linkage and cab pillars run in a longitudinal plane.
	mb.xform = Transform3D(Basis(Vector3.RIGHT, atan2(-axis.y, axis.z)), (a + b) * 0.5)
	mb.box(Vector3.ZERO, Vector3(width, depth, axis.length()), col)
	mb.xform = Transform3D.IDENTITY


static func _build_loader() -> ArrayMesh:
	var mb := MeshBuilder.new()
	mb.box(Vector3(0, 0.97, -0.55), Vector3(1.65, 0.65, 5.3), STEEL)
	for z: float in [-2.08, 1.43]:
		for side: float in [-1.0, 1.0]:
			_axle(mb, Vector3(side * 1.05, 0.88, z), 0.66, 0.88, RUBBER, RUBBER)
			_axle(mb, Vector3(side * 1.39, 0.88, z), 0.07, 0.48, OCHRE, YELLOW)
			_axle(mb, Vector3(side * 1.44, 0.88, z), 0.05, 0.21, STEEL, OCHRE)
	# Rounded counterweight, raised engine cover and exhaust behind the cab.
	mb.extrude(PackedVector2Array([Vector2(-1.2, -2.96), Vector2(-0.85, -3.36), Vector2(0.85, -3.36),
		Vector2(1.2, -2.96), Vector2(1.2, -0.07), Vector2(-1.2, -0.07)]), 1.04, 1.88, OCHRE, YELLOW)
	mb.box(Vector3(0, 2.04, -2.35), Vector3(1.84, 0.44, 1.53), YELLOW)
	for z: float in [-2.78, -2.50, -2.22]:
		mb.box(Vector3(0, 2.27, z), Vector3(1.15, 0.04, 0.12), STEEL)
	mb.cylinder(Vector3(0.82, 2.1, -1.72), 0.12, 0.12, 0.84, 6, STEEL)
	mb.box(Vector3(0, 1.9, -0.77), Vector3(1.8, 0.48, 1.52), YELLOW)
	mb.box(Vector3(0, 2.71, -0.76), Vector3(1.63, 1.25, 1.4), GLASS)
	for x: float in [-0.82, 0.82]:
		for z: float in [-1.47, -0.06]:
			mb.box(Vector3(x, 2.72, z), Vector3(0.09, 1.29, 0.10), STEEL)
	mb.box(Vector3(0, 3.40, -0.76), Vector3(1.99, 0.19, 1.72), YELLOW)
	mb.cylinder(Vector3(0.7, 3.49, -1.24), 0.12, 0.1, 0.16, 6, ORANGE)
	for side: float in [-1.0, 1.0]:
		mb.box(Vector3(side * 1.1, 1.20, -0.52), Vector3(0.5, 0.15, 0.76), STEEL)
		mb.box(Vector3(side * 1.0, 1.8, 1.35), Vector3(0.65, 0.14, 1.65), YELLOW)
	return mb.commit()


static func _build_boom() -> ArrayMesh:
	var mb := MeshBuilder.new()
	for x: float in [-0.66, 0.66]:
		var joint := Vector3(x, -0.04, 1.69)
		var foot := Vector3(x, -0.91, 2.47)
		_strut(mb, Vector3(x, 0, 0), joint, 0.28, 0.30, YELLOW)
		_strut(mb, joint, foot, 0.28, 0.32, OCHRE)
		_strut(mb, Vector3(x, -0.65, 0.23), joint, 0.13, 0.13, STEEL)
		_axle(mb, joint, 0.38, 0.15, STEEL, OCHRE)
	# Open scoop: thin side cheeks and a long cutting edge visible from above.
	var left := Vector3(-1.55, -1.45, 3.51)
	var heel := Vector3(-1.55, -1.43, 2.41)
	var lip := Vector3(-1.55, -0.35, 2.16)
	var right := Vector3.RIGHT * 3.10
	mb.quad(lip, lip + right, heel + right, heel, STEEL, Vector3.BACK)
	mb.quad(heel, heel + right, left + right, left, STEEL.lightened(0.17), Vector3.UP)
	for x: float in [-1.5, 1.5]:
		var shift := Vector3.RIGHT * (x + 1.55)
		mb.tri(lip + shift, heel + shift, left + shift, OCHRE, Vector3.RIGHT * signf(x))
		mb.tri(lip + shift, heel + shift, left + shift, OCHRE.darkened(0.15), Vector3.LEFT * signf(x))
	mb.box(left + right * 0.5, Vector3(3.1, 0.1, 0.15), Color("#929895"))
	mb.box(lip + right * 0.5, Vector3(3.1, 0.11, 0.14), YELLOW)
	return mb.commit()


static func _build_roller() -> ArrayMesh:
	var mb := MeshBuilder.new()
	for z: float in [-1.56, 1.56]:
		_axle(mb, Vector3(0, 0.82, z), 2.1, 0.82, Color("#818a8b"), STEEL)
		for side: float in [-1.0, 1.0]:
			_axle(mb, Vector3(side * 1.08, 0.82, z), 0.10, 0.34, OCHRE, YELLOW)
			_strut(mb, Vector3(side * 1.14, 0.84, z), Vector3(side * 1.14, 1.36, z * 0.5), 0.19, 0.31, YELLOW)
		mb.box(Vector3(0, 0.98, signf(z) * 2.47), Vector3(2.12, 0.2, 0.13), STEEL)
	mb.box(Vector3(0, 1.22, 0), Vector3(1.84, 0.54, 2.1), OCHRE)
	mb.box(Vector3(0, 1.81, -0.93), Vector3(1.87, 0.54, 1.67), YELLOW)
	mb.box(Vector3(0, 1.98, -0.04), Vector3(0.67, 0.43, 0.7), RUBBER)
	mb.box(Vector3(0, 2.24, -0.36), Vector3(0.67, 0.60, 0.14), RUBBER)
	mb.box(Vector3(0, 1.84, 0.66), Vector3(1.02, 0.58, 0.50), STEEL)
	for x: float in [-0.86, 0.86]:
		_strut(mb, Vector3(x, 1.5, -0.55), Vector3(x, 2.97, -0.76), 0.14, 0.14, STEEL)
	mb.box(Vector3(0, 3.03, -0.03), Vector3(2.09, 0.17, 1.86), YELLOW)
	return mb.commit()


static func _build_materials() -> ArrayMesh:
	var mb := MeshBuilder.new()
	# Angular aggregate heap with a short ridge and a flatter worked face.
	var edge := PackedVector3Array([Vector3(-1.72, 0, -2.93), Vector3(0.33, 0, -3.31),
		Vector3(1.74, 0, -2.44), Vector3(1.85, 0, -0.65), Vector3(0.95, 0, 0.87),
		Vector3(-1.12, 0, 1.00), Vector3(-1.86, 0, -0.39)])
	var top := Vector3(-0.13, 1.42, -1.32)
	var gravel := Color("#938d82")
	for i in edge.size():
		mb.tri(edge[i], edge[(i + 1) % edge.size()], top, gravel.darkened(0.035 * (i % 3)), Vector3.UP)
	# Two strapped rolls of road fabric on timber sleepers.
	for x: float in [-0.82, 0.82]:
		mb.box(Vector3(x, 0.10, 2.3), Vector3(0.28, 0.2, 2.07), Color("#946d45"))
	for z: float in [1.86, 2.80]:
		_axle(mb, Vector3(0, 0.68, z), 3.05, 0.48, Color("#b5afa4"), Color("#878374"))
		for x: float in [-0.84, 0.84]:
			_axle(mb, Vector3(x, 0.68, z), 0.13, 0.50, OCHRE, OCHRE)
	return mb.commit()


static func _build_barricade() -> ArrayMesh:
	var mb := MeshBuilder.new()
	for x: float in [-0.83, 0.83]:
		mb.box(Vector3(x, 0.06, 0), Vector3(0.26, 0.12, 0.8), RUBBER)
		mb.box(Vector3(x, 0.48, 0), Vector3(0.15, 0.86, 0.14), STEEL)
	mb.box(Vector3(0, 0.83, 0), Vector3(2.4, 0.47, 0.17), Color("#eaddc9"))
	for face: float in [-1.0, 1.0]:
		var z := face * 0.087
		for x: float in [-1.07, -0.48, 0.11, 0.70]:
			mb.quad(Vector3(x, 0.595, z), Vector3(x + 0.25, 0.595, z), Vector3(x + 0.47, 1.065, z), Vector3(x + 0.22, 1.065, z), ORANGE, Vector3.BACK * face)
	return mb.commit()
