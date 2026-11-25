class_name PassengerView
extends Passenger
## Loads and animates the low-poly walk-on passenger models.

const MODELS := [
	"res://assets/models/person_beanie.glb",
	"res://assets/models/person_low.glb",
	"res://assets/models/person_business.glb",
	"res://assets/models/person_elder.glb",
	"res://assets/models/person_shopper.glb",
	"res://assets/models/person_construction.glb",
	"res://assets/models/person_hipster.glb",
	"res://assets/models/person_jogger.glb",
	"res://assets/models/person_kid.glb",
	"res://assets/models/person_student.glb",
	"res://assets/models/person_tourist.glb",
	"res://assets/models/person_umbrella.glb",
	"res://assets/models/person_biker.glb",
	"res://assets/models/person_dad_baby.glb",
	"res://assets/models/person_fisherman.glb",
	"res://assets/models/person_fisherman_buoy.glb",
	"res://assets/models/person_gym_kid.glb",
	"res://assets/models/person_husky_tourist.glb",
	"res://assets/models/person_stroller.glb",
	"res://assets/models/person_student_girl.glb",
	"res://assets/models/person_traveler.glb",
]
const RECOLOR_SHADER := preload("res://shaders/passenger.gdshader")
## Models whose people are too young for grey hair.
const YOUNG := ["kid", "student", "jogger", "hipster", "biker"]
## Models whose overalls/oilskin bottoms must stay orange or yellow only.
const OILSKIN_BOTTOM := ["fisherman_buoy"]
const OILSKIN_COLORS := [
	Color(0.98, 0.80, 0.21),
	Color(0.95, 0.72, 0.16),
	Color(0.92, 0.46, 0.12),
	Color(0.86, 0.36, 0.10),
]
## Recolour palettes, picked in sRGB like the Blender palettes (see
## art/person_recolor.py). Repeats weight the common picks.
const SKIN_TONES := [
	Color(0.98, 0.80, 0.66),
	Color(0.96, 0.74, 0.56),
	Color(0.92, 0.68, 0.50),
	Color(0.84, 0.60, 0.42),
	Color(0.72, 0.50, 0.34),
	Color(0.58, 0.39, 0.26),
	Color(0.45, 0.30, 0.20),
	Color(0.36, 0.23, 0.16),
]
const HAIR_COLORS := [
	Color(0.12, 0.10, 0.09),
	Color(0.12, 0.10, 0.09),
	Color(0.24, 0.16, 0.11),
	Color(0.24, 0.16, 0.11),
	Color(0.38, 0.26, 0.17),
	Color(0.55, 0.42, 0.28),
	Color(0.56, 0.26, 0.14),
	Color(0.84, 0.69, 0.42),
	Color(0.92, 0.80, 0.55),
]
const GREY_HAIR := [Color(0.66, 0.65, 0.63), Color(0.86, 0.85, 0.82)]
const TOP_COLORS := [
	Color(0.20, 0.28, 0.45),
	Color(0.36, 0.50, 0.66),
	Color(0.20, 0.47, 0.50),
	Color(0.27, 0.42, 0.30),
	Color(0.50, 0.52, 0.32),
	Color(0.84, 0.66, 0.26),
	Color(0.70, 0.36, 0.22),
	Color(0.66, 0.24, 0.22),
	Color(0.46, 0.20, 0.26),
	Color(0.90, 0.86, 0.76),
	Color(0.28, 0.29, 0.31),
	Color(0.88, 0.52, 0.44),
	Color(0.42, 0.32, 0.50),
	Color(0.62, 0.74, 0.82),
]
const BOTTOM_COLORS := [
	Color(0.30, 0.40, 0.56),
	Color(0.20, 0.25, 0.36),
	Color(0.26, 0.27, 0.29),
	Color(0.15, 0.15, 0.16),
	Color(0.70, 0.62, 0.46),
	Color(0.40, 0.42, 0.30),
	Color(0.40, 0.30, 0.22),
	Color(0.52, 0.54, 0.56),
]
## Chance a passenger keeps the model's own colour for a part.
const KEEP_CHANCE := 0.25

const WALK_ANIM := &"Walk"
static var _scenes: Array[PackedScene] = []
static var _loaded := false
static var _material: ShaderMaterial

var _anim: AnimationPlayer
var _skeleton: Skeleton3D
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
	_material = ShaderMaterial.new()
	_material.shader = RECOLOR_SHADER
	for p: String in MODELS:
		if ResourceLoader.exists(p):
			_scenes.append(load(p) as PackedScene)
		else:
			_scenes.append(null)


static func create_view(model_variant: int) -> Passenger:
	_ensure_loaded()
	var pax := PassengerView.new()
	pax.variant = absi(model_variant) % MODELS.size()
	pax.scale = Vector3.ONE * Units.VEHICLE_MODEL_SCALE
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
		_apply_random_colors(inst, MODELS[pax.variant])
		pax._anim = _find_animation_player(inst)
		pax._skeleton = _find_skeleton(inst)
		if pax._anim != null:
			_enable_walk_loop(pax._anim)
		if pax._skeleton != null:
			pax._cache_idle_bones()
	pax.set_process(true)
	return pax


static func _apply_vertex_color_material(node: Node) -> void:
	# Surfaces with painted textures (the tourist's map and shirt) keep their own.
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		var mi := node as MeshInstance3D
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as BaseMaterial3D
			if m == null or m.albedo_texture == null:
				mi.set_surface_override_material(i, _material)
	for c in node.get_children():
		_apply_vertex_color_material(c)


## Gives this passenger its own skin, hair, clothes and accessory colours.
static func _apply_random_colors(node: Node, model_path: String) -> void:
	var file_name := model_path.get_file()
	var young := false
	for y: String in YOUNG:
		if y in file_name:
			young = true
	var oilskin := false
	for o: String in OILSKIN_BOTTOM:
		if o in file_name:
			oilskin = true
	var hair: Array = HAIR_COLORS if young else HAIR_COLORS + GREY_HAIR
	var bottom: Array = OILSKIN_COLORS if oilskin else BOTTOM_COLORS
	var picks := {
		&"skin_col": _pick(SKIN_TONES),
		&"hair_col": _pick(hair),
		&"top_col": _pick(TOP_COLORS),
		&"bottom_col": _pick(bottom),
		&"accent_col": _pick(TOP_COLORS),
	}
	_set_colors(node, picks)


static func _pick(palette: Array) -> Color:
	if randf() < KEEP_CHANCE:
		return Color(0, 0, 0, 0)
	var c: Color = palette[randi() % palette.size()]
	# Linear, to match the vertex colours.
	var lin := c.srgb_to_linear()
	lin.a = 1.0
	return lin


static func _set_colors(node: Node, picks: Dictionary) -> void:
	if node is GeometryInstance3D:
		for k: StringName in picks:
			(node as GeometryInstance3D).set_instance_shader_parameter(k, picks[k])
	for c in node.get_children():
		_set_colors(c, picks)


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


func _set_walking(walking: bool) -> void:
	super._set_walking(walking)
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
		_skeleton.set_bone_pose_rotation(
			_torso_idx, _torso_rest * Quaternion.from_euler(Vector3(breath, sway * 0.6, sway))
		)
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
		_skeleton.set_bone_pose_rotation(
			_head_idx, _head_rest * Quaternion.from_euler(Vector3(_look_pitch, _look_yaw, 0.0))
		)
	if _arm_l_idx >= 0:
		var swing := sin(t * 1.12 + 0.7) * 0.055 * _idle_amp * _sway_dir
		_skeleton.set_bone_pose_rotation(
			_arm_l_idx, _arm_l_rest * Quaternion.from_euler(Vector3(swing, 0.0, 0.03))
		)
	if _arm_r_idx >= 0:
		var swing := -sin(t * 1.04 + 1.9) * 0.055 * _idle_amp * _sway_dir
		_skeleton.set_bone_pose_rotation(
			_arm_r_idx, _arm_r_rest * Quaternion.from_euler(Vector3(swing, 0.0, -0.03))
		)
