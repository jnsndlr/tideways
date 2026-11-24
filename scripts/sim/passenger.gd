class_name Passenger
extends Node3D
## A walk-on ferry passenger animated with one of the two stand-in character models
## (person_beanie.glb and person_low.glb). Follows waypoints between the passenger
## terminal, waiting area, trestle walkway and ferry deck, playing its Walk cycle
## while moving and a lightweight universal skeletal idle animation while waiting.

const MODELS := [
	"res://assets/models/person_beanie.glb",
	"res://assets/models/person_low.glb",
]
const WALK_ANIM := &"Walk"
const WALK_SPEED := 10.5  # game units/s (~44% of car speed: brisk walk along pier & ramp)
const TURN_RATE := 12.0

static var _scenes: Array[PackedScene] = []
static var _loaded := false
static var _material: StandardMaterial3D

var variant := 0
var speed := WALK_SPEED
var delay := 0.0
var path := PackedVector3Array()
var _on_arrive := Callable()
var _anim: AnimationPlayer
var _skeleton: Skeleton3D
var _stand_yaw := NAN
var _walking := false
var _idle_time := 0.0
var _idle_phase := 0.0
var _idle_speed := 1.0
var _idle_amp := 1.0
var _sway_dir := 1.0
var _look_timer := 0.0
var _look_yaw := 0.0
var _look_pitch := 0.0
var _look_target_yaw := 0.0
var _look_target_pitch := 0.0
var _torso_idx := -1
var _head_idx := -1
var _arm_l_idx := -1
var _arm_r_idx := -1
var _torso_rest := Quaternion.IDENTITY
var _head_rest := Quaternion.IDENTITY
var _arm_l_rest := Quaternion.IDENTITY
var _arm_r_rest := Quaternion.IDENTITY


static func _ensure_loaded() -> void:
	if _loaded:
		return
	_loaded = true
	_material = StandardMaterial3D.new()
	_material.vertex_color_use_as_albedo = true
	_material.roughness = 0.88
	_material.metallic = 0.0
	for p: String in MODELS:
		if ResourceLoader.exists(p):
			_scenes.append(load(p) as PackedScene)
		else:
			_scenes.append(null)


static func create(model_variant: int) -> Passenger:
	_ensure_loaded()
	var pax := Passenger.new()
	pax.variant = absi(model_variant) % MODELS.size()
	pax.scale = Vector3.ONE * Models.VEHICLE_SCALE
	pax._idle_phase = randf() * TAU
	pax._idle_speed = randf_range(0.72, 1.32)
	pax._idle_amp = randf_range(0.75, 1.3)
	pax._sway_dir = -1.0 if randf() < 0.5 else 1.0
	pax._look_timer = randf_range(0.4, 4.5)
	pax._look_target_yaw = randf_range(-0.28, 0.28)
	pax._look_target_pitch = randf_range(-0.06, 0.07)
	var scene: PackedScene = _scenes[pax.variant] if pax.variant < _scenes.size() else null
	if scene != null:
		var inst := scene.instantiate()
		pax.add_child(inst)
		_apply_vertex_color_material(inst)
		pax._anim = _find_animation_player(inst)
		pax._skeleton = _find_skeleton(inst)
		if pax._anim != null:
			_enable_walk_loop(pax._anim)
		if pax._skeleton != null:
			pax._cache_idle_bones()
	pax.set_process(true)
	return pax


static func _apply_vertex_color_material(node: Node) -> void:
	if node is MeshInstance3D:
		(node as MeshInstance3D).material_override = _material
	for c in node.get_children():
		_apply_vertex_color_material(c)


static func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for c in node.get_children():
		var found := _find_animation_player(c)
		if found != null:
			return found
	return null


static func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for c in node.get_children():
		var found := _find_skeleton(c)
		if found != null:
			return found
	return null


static func _enable_walk_loop(ap: AnimationPlayer) -> void:
	if not ap.has_animation(WALK_ANIM):
		return
	var anim := ap.get_animation(WALK_ANIM)
	if anim != null and anim.loop_mode != Animation.LOOP_LINEAR:
		anim.loop_mode = Animation.LOOP_LINEAR


func _cache_idle_bones() -> void:
	_torso_idx = _skeleton.find_bone("Torso")
	_head_idx = _skeleton.find_bone("Head")
	_arm_l_idx = _skeleton.find_bone("Arm_L")
	_arm_r_idx = _skeleton.find_bone("Arm_R")
	if _torso_idx >= 0:
		_torso_rest = _skeleton.get_bone_rest(_torso_idx).basis.get_rotation_quaternion()
	if _head_idx >= 0:
		_head_rest = _skeleton.get_bone_rest(_head_idx).basis.get_rotation_quaternion()
	if _arm_l_idx >= 0:
		_arm_l_rest = _skeleton.get_bone_rest(_arm_l_idx).basis.get_rotation_quaternion()
	if _arm_r_idx >= 0:
		_arm_r_rest = _skeleton.get_bone_rest(_arm_r_idx).basis.get_rotation_quaternion()


func stand_at(pos: Vector3, yaw: float) -> void:
	position = pos
	rotation.y = yaw + randf_range(-0.18, 0.18)
	path.clear()
	_on_arrive = Callable()
	_stand_yaw = NAN
	_set_walking(false)


func walk(points: PackedVector3Array, on_arrive := Callable(), start_delay := 0.0, end_yaw := NAN) -> void:
	path = points.duplicate()
	_on_arrive = on_arrive
	delay = start_delay
	_stand_yaw = end_yaw
	if path.is_empty():
		_finish_walk()
		return
	set_process(true)
	if delay <= 0.0:
		_set_walking(true)
	else:
		_set_walking(false)


func _set_walking(walking: bool) -> void:
	_walking = walking
	set_process(true)
	if _anim == null or not _anim.has_animation(WALK_ANIM):
		return
	if walking:
		if not _anim.is_playing() or _anim.current_animation != WALK_ANIM:
			_anim.speed_scale = speed / 2.2
			_anim.play(WALK_ANIM)
			_anim.seek(fmod(float(get_instance_id() % 100) * 0.01, 1.0), true)
	else:
		_anim.stop()
		if _skeleton != null:
			_skeleton.reset_bone_poses()


func _finish_walk() -> void:
	if not is_nan(_stand_yaw):
		rotation.y = _stand_yaw + randf_range(-0.18, 0.18)
		_stand_yaw = NAN
	_set_walking(false)
	var cb := _on_arrive
	_on_arrive = Callable()
	if cb.is_valid():
		cb.call(self)


## Gentle universal idle motion shared across all characters on this rig:
## staggered breathing/sway tempo per person, relaxed arm drift, and independent
## occasional head glances so a waiting queue never moves in unison.
func _tick_idle(delta: float) -> void:
	if _skeleton == null:
		return
	# Keep idle gentle in real time even when time_scale is sped up.
	var dt := minf(delta, 0.05)
	_idle_time += dt * _idle_speed
	var t := _idle_time + _idle_phase
	if _torso_idx >= 0:
		var breath := sin(t * 1.85) * 0.024 * _idle_amp
		var sway := sin(t * 0.78 + _idle_phase * 0.5) * 0.032 * _idle_amp * _sway_dir
		_skeleton.set_bone_pose_rotation(_torso_idx, _torso_rest * Quaternion.from_euler(Vector3(breath, sway * 0.6, sway)))
	if _head_idx >= 0:
		_look_timer -= dt
		if _look_timer <= 0.0:
			_look_timer = randf_range(1.6, 5.5)
			if randf() < 0.35:
				# Glance back toward the front of the line / ferry.
				_look_target_yaw = randf_range(-0.08, 0.08)
				_look_target_pitch = randf_range(-0.04, 0.04)
			else:
				_look_target_yaw = randf_range(-0.38, 0.38)
				_look_target_pitch = randf_range(-0.08, 0.09)
		var blend := minf(1.0, dt * 3.0)
		_look_yaw = lerpf(_look_yaw, _look_target_yaw, blend)
		_look_pitch = lerpf(_look_pitch, _look_target_pitch, blend)
		_skeleton.set_bone_pose_rotation(_head_idx, _head_rest * Quaternion.from_euler(Vector3(_look_pitch, _look_yaw, 0.0)))
	if _arm_l_idx >= 0:
		var swing := sin(t * 1.12 + 0.7) * 0.055 * _idle_amp * _sway_dir
		_skeleton.set_bone_pose_rotation(_arm_l_idx, _arm_l_rest * Quaternion.from_euler(Vector3(swing, 0.0, 0.03)))
	if _arm_r_idx >= 0:
		var swing := -sin(t * 1.04 + 1.9) * 0.055 * _idle_amp * _sway_dir
		_skeleton.set_bone_pose_rotation(_arm_r_idx, _arm_r_rest * Quaternion.from_euler(Vector3(swing, 0.0, -0.03)))


func _process(delta: float) -> void:
	if delay > 0.0:
		delay -= delta
		_tick_idle(delta)
		if delay <= 0.0 and not path.is_empty():
			_set_walking(true)
		return
	if path.is_empty():
		_tick_idle(delta)
		return
	var step := speed * delta
	while step > 0.0 and not path.is_empty():
		var target := path[0]
		var to := target - position
		var dist := to.length()
		if dist <= step:
			position = target
			step -= dist
			path.remove_at(0)
			if path.is_empty():
				_finish_walk()
				return
		else:
			var dir := to / dist
			position += dir * step
			step = 0.0
			var flat := dir.x * dir.x + dir.z * dir.z
			if flat > 0.0001:
				rotation.y = lerp_angle(rotation.y, atan2(dir.x, dir.z), minf(1.0, delta * TURN_RATE))
