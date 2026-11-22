class_name PavingCrew
extends Node3D
## The terminal owns the work clock. All crew poses can be reconstructed from it.

const GRAVEL := Color(0.47, 0.41, 0.32)
const FLOOR_Y := Layout.LOT_Y + 0.045

var terminal: Terminal
var loader: Node3D
var roller: Node3D
var pile: Node3D
var safety := Node3D.new()
var loader_route: Curve3D
var roller_route: Curve3D
var loader_park: Vector3
var roller_park: Vector3
var pickup: Vector3
var spread: Vector3
var approach_seconds := 0.0
var loader_wait := 0.0
var roller_wait := 0.0
var mat_strip := MeshInstance3D.new()


func setup(site: Terminal) -> void:
	terminal = site
	var work_x := terminal.extension_offset()
	# Inside an unfinished lot the crew stages on the unpaved ground further out.
	var lane_x := terminal.staging_lanes[0].v if not terminal.staging_lanes.is_empty() else work_x + signf(work_x) * Layout.LANE_WIDTH
	var maneuver_x := terminal.staging_lanes.back().v as float if not terminal.staging_lanes.is_empty() else lane_x
	loader_park = Vector3(maneuver_x, FLOOR_Y, -58)
	roller_park = Vector3(work_x, FLOOR_Y, -68)
	pickup = Vector3(lane_x, FLOOR_Y, -40)
	spread = Vector3(work_x, FLOOR_Y, -31)
	loader = PavingEquipment.loader()
	roller = PavingEquipment.roller()
	pile = PavingEquipment.materials()
	for node: Node3D in [loader, roller, pile, safety, mat_strip]:
		add_child(node)
	pile.position = Vector3(lane_x, FLOOR_Y, -33)
	for lane: Terminal.Lane in terminal.staging_lanes:
		for z: float in [-16.0, -69.0]:
			var barrier := PavingEquipment.barricade()
			barrier.position = Vector3(lane.v, FLOOR_Y, z)
			safety.add_child(barrier)

	# Turn off the access road behind the toll booths, then enter from the
	# extension side. The temporary gravel drive keeps both machines off live lanes.
	var entrance := PackedVector3Array()
	var road := terminal.town.road_main_a
	for i in range(road.size() - 1, -1, -1):
		var point := terminal.to_local(road[i])
		if point.z < Layout.LOT_BACK - 15:
			entrance.append(_ground(point.x - 6.7, point.z))
	if entrance.is_empty():
		entrance.append(_ground(-6.7, Layout.LOT_BACK - 22))
	entrance.append(_ground(-10, Layout.LOT_BACK - 16))
	entrance.append(_ground(work_x + 5, Layout.LOT_BACK - 13))
	entrance.append(_ground(work_x, Layout.LOT_BACK - 7))
	entrance.append(Vector3(work_x, FLOOR_Y, Layout.LOT_BACK))
	var drive := _curve(entrance)
	var drive_mesh := MeshBuilder.new()
	drive_mesh.ribbon(drive.get_baked_points(), 4.6, GRAVEL, 0.25)
	var drive_view := MeshInstance3D.new()
	drive_view.mesh = drive_mesh.commit()
	add_child(drive_view)

	var loader_points := entrance.duplicate()
	loader_points.append(Vector3(work_x, FLOOR_Y, -66))
	loader_points.append(Vector3(maneuver_x, FLOOR_Y, -62))
	loader_points.append(loader_park)
	loader_route = _curve(loader_points)
	var roller_points := entrance.duplicate()
	roller_points.append(roller_park)
	roller_route = _curve(roller_points)
	# Pull off before the closed bay. Keep room behind the loader for the roller.
	var pull_off := entrance[entrance.size() - 3]
	loader_wait = loader_route.get_closest_offset(pull_off) / loader_route.get_baked_length()
	roller_wait = maxf(0.0, roller_route.get_closest_offset(pull_off) - 12.0) / roller_route.get_baked_length()
	var asphalt := MeshBuilder.new()
	asphalt.box(Vector3(0, 0, 0.5), Vector3(Layout.LANE_WIDTH, 0.04, 1), WorldBuilder.ASPHALT)
	mat_strip.mesh = asphalt.commit()
	mat_strip.position = Vector3(work_x, Layout.LOT_Y + 0.025, Layout.LOT_BACK)
	update_pose()


func _ground(x: float, z: float) -> Vector3:
	var world := terminal.to_global(Vector3(x, 0, z))
	return Vector3(x, terminal.sim.terrain.height_v(world) + 0.22, z)


func _curve(points: PackedVector3Array) -> Curve3D:
	var curve := Curve3D.new()
	for i in points.size():
		var point := points[i]
		var before := points[maxi(i - 1, 0)]
		var after := points[mini(i + 1, points.size() - 1)]
		var tangent := (after - before).normalized()
		curve.add_point(point, -tangent * point.distance_to(before) * 0.2, tangent * point.distance_to(after) * 0.2)
	return curve


func _drive(machine: Node3D, route: Curve3D, progress: float, reverse: bool) -> void:
	var length := route.get_baked_length()
	var d := clampf(progress, 0, 1) * length
	machine.position = route.sample_baked(d)
	var direction := route.sample_baked(minf(d + 0.35, length)) - route.sample_baked(maxf(d - 0.35, 0))
	machine.rotation.y = atan2(direction.x, direction.z)
	if reverse:
		# Back out of the narrow work site and turn to face town on the wider approach.
		machine.rotation.y += PI * smoothstep(0.2, 0.65, 1.0 - progress)


func _process(delta: float) -> void:
	if terminal.work_stage == Terminal.WorkStage.DRAINING:
		approach_seconds = minf(approach_seconds + delta, 14.0)
	update_pose()


func update_pose() -> void:
	var t := terminal.stage_progress()
	var paved := 0.0
	var delivered := 0.0
	var loader_start := loader_wait * smoothstep(0.0, 10.0, approach_seconds)
	var roller_start := roller_wait * smoothstep(4.0, 14.0, approach_seconds)
	match terminal.work_stage:
		Terminal.WorkStage.DRAINING:
			_drive(loader, loader_route, loader_start, false)
			roller.visible = approach_seconds > 4.0
			_drive(roller, roller_route, roller_start, false)
			safety.visible = false
		Terminal.WorkStage.ARRIVING:
			_drive(loader, loader_route, lerpf(loader_start, 1.0, clampf(t / 0.78, 0, 1)), false)
			roller.visible = approach_seconds > 4.0 or t >= 0.24
			_drive(roller, roller_route, lerpf(roller_start, 1.0, clampf((t - 0.24) / 0.76, 0, 1)), false)
			delivered = smoothstep(0.55, 1.0, t)
			safety.visible = t > 0.5
		Terminal.WorkStage.PAVING:
			roller.visible = true
			safety.visible = true
			var loading := clampf(t / 0.54, 0.0, 1.0)
			var passes := loading * 3.0
			var cycle := fmod(passes, 1.0)
			var reach := sin(PI * cycle)
			var base := loader_park.lerp(pickup, sin(PI * loading))
			loader.position = base.lerp(spread, reach)
			loader.rotation.y = lerp_angle(0, atan2(spread.x - base.x, spread.z - base.z), reach)
			loader.get_node("Boom").rotation.x = -0.35 * reach
			delivered = 1.0 - loading * 0.85
			var rolling := clampf((t - 0.54) / 0.46, 0.0, 1.0)
			roller.position = roller_park.lerp(Vector3(roller_park.x, FLOOR_Y, -12), sin(PI * rolling))
			roller.rotation.y = 0.0
			paved = sin(PI * minf(rolling, 0.5))
		Terminal.WorkStage.LEAVING:
			_drive(roller, roller_route, 1.0 - t / 0.76, true)
			roller.visible = t < 0.76
			_drive(loader, loader_route, 1.0 - (t - 0.24) / 0.76, true)
			safety.visible = t < 0.24
			delivered = 0.15 * (1.0 - smoothstep(0.0, 0.24, t))
			paved = 1.0
	pile.visible = delivered > 0.01
	pile.scale.y = maxf(delivered, 0.01)
	mat_strip.visible = paved > 0.001
	mat_strip.scale.z = maxf(0.001, Layout.LOT_LENGTH * paved)
