extends Node
## All flight and perch positions are in the harbor movie's 1280 × 720 camera.

enum Flight { CROSSING, LANDING, TAKEOFF }

# Two spots on the left handrail and two timber pilings on the right.
const PERCHES := [Vector2(444, 545), Vector2(500, 531), Vector2(944, 515), Vector2(993, 501)]
const FLARE := 12
const STANDING := 13
const LOOKING_DOWN := 14
const LIFT_OFF := 15
const REST_SIZE := 63.0

var _rng := RandomNumberGenerator.new()
var _perch_index := -1
var _direction := 1
@onready var _glass: ShaderMaterial = get_parent().material


func _ready() -> void:
	_rng.randomize()
	_wait_for_visit(_rng.randf_range(6.0, 15.0))


func _wait_for_visit(seconds: float) -> void:
	_glass.set_shader_parameter("gull_size", 0.0)
	var timer := create_tween()
	timer.tween_interval(seconds)
	timer.tween_callback(_visit)


func _visit() -> void:
	_direction = 1 if _rng.randf() < 0.5 else -1
	_glass.set_shader_parameter("gull_facing", float(_direction))
	var entrance := _sky_edge(-_direction)
	var exit_point := _sky_edge(_direction)
	var visit := create_tween()
	if _rng.randf() < 0.58:
		# Select another physical perch on the next landing.
		if _perch_index == -1:
			_perch_index = _rng.randi_range(0, PERCHES.size() - 1)
		else:
			_perch_index = (_perch_index + _rng.randi_range(1, PERCHES.size() - 1)) % PERCHES.size()
		var perch: Vector2 = PERCHES[_perch_index]
		_flight(visit, entrance, entrance + Vector2(_direction * 210, 25),
				perch - Vector2(_direction * 55, 18), perch, Flight.LANDING)
		var rest := _rng.randf_range(14.0, 36.0)
		visit.tween_interval(rest * 0.45)
		visit.tween_method(_look, 0.0, 1.0, 0.30)
		visit.tween_interval(_rng.randf_range(0.8, 2.4))
		visit.tween_method(_look, 1.0, 0.0, 0.34)
		visit.tween_interval(rest * 0.55)
		_flight(visit, perch, perch + Vector2(_direction * 45, -120),
				exit_point - Vector2(_direction * 180, 50), exit_point, Flight.TAKEOFF)
	else:
		var dip := _rng.randf_range(235.0, 350.0)
		_flight(visit, entrance, Vector2(entrance.lerp(exit_point, 0.32).x, dip),
				Vector2(entrance.lerp(exit_point, 0.71).x, dip + 36), exit_point, Flight.CROSSING)
	visit.tween_callback(_wait_for_visit.bind(_rng.randf_range(18.0, 47.0)))


func _sky_edge(side: int) -> Vector2:
	return Vector2(-85 if side < 0 else 1365, _rng.randf_range(135.0, 245.0))


func _flight(visit: Tween, start: Vector2, a: Vector2, b: Vector2, end: Vector2, kind: Flight) -> void:
	var seconds := clampf(start.distance_to(end) / _rng.randf_range(120.0, 165.0), 3.5, 11.0)
	var size_in_air := _rng.randf_range(82.0, 105.0)
	visit.tween_method(_fly.bind(start, a, b, end, kind, seconds, size_in_air), 0.0, 1.0, seconds)


func _fly(t: float, start: Vector2, a: Vector2, b: Vector2, end: Vector2,
		kind: Flight, seconds: float, size_in_air: float) -> void:
	_glass.set_shader_parameter("gull_anchor", start.bezier_interpolate(a, b, end, t))
	var size_px := size_in_air
	if kind == Flight.LANDING:
		size_px = lerpf(size_in_air, REST_SIZE, t)
	elif kind == Flight.TAKEOFF:
		size_px = lerpf(REST_SIZE, size_in_air, t)
	_glass.set_shader_parameter("gull_size", size_px)
	# Two wingbeats followed by a glide with the wings spread.
	var beat := fmod(t * seconds * 18.0, 34.0)
	var frame := int(beat) % 10 if beat < 20.0 else 0
	if kind == Flight.LANDING and t > 0.93:
		_pose(FLARE, STANDING, smoothstep(0.93, 1.0, t))
	elif kind == Flight.LANDING and t > 0.84:
		_pose(frame, FLARE, smoothstep(0.84, 0.93, t))
	elif kind == Flight.TAKEOFF and t < 0.045:
		_pose(STANDING, LIFT_OFF, smoothstep(0.0, 0.045, t))
	elif kind == Flight.TAKEOFF and t < 0.14:
		_pose(LIFT_OFF, frame, smoothstep(0.045, 0.14, t))
	else:
		_pose(frame, (frame + 1) % 10, fmod(beat, 1.0) if beat < 20.0 else 0.0)


func _look(amount: float) -> void:
	_pose(STANDING, LOOKING_DOWN, amount)


func _pose(first: int, second: int, weight: float) -> void:
	_glass.set_shader_parameter("gull_frames", Vector3(first, second, weight))
