class_name Passenger
extends Node3D
## Moves one walk-on passenger between the waiting area, ferry and destination.

const VARIANT_COUNT := 21
const WALK_SPEED := 10.5  # game units/s (~44% of car speed: brisk walk along pier & ramp)
const TURN_RATE := 12.0

var variant := 0
var speed := WALK_SPEED
var delay := 0.0
var path := PackedVector3Array()
var _on_arrive := Callable()
var _stand_yaw := NAN
var _walking := false


static func create(model_variant: int) -> Passenger:
	var passenger := Passenger.new()
	passenger.variant = absi(model_variant) % VARIANT_COUNT
	return passenger


func stand_at(pos: Vector3, yaw: float) -> void:
	stand_facing(pos, yaw + randf_range(-0.18, 0.18))


## Install a saved waiting pose without choosing another facing direction.
func stand_facing(pos: Vector3, yaw: float) -> void:
	position = pos
	rotation.y = yaw
	path.clear()
	_on_arrive = Callable()
	_stand_yaw = NAN
	_set_walking(false)


func walk(
	points: PackedVector3Array, on_arrive := Callable(), start_delay := 0.0, end_yaw := NAN
) -> void:
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


func _tick_idle(_delta: float) -> void:
	pass


func _finish_walk() -> void:
	if not is_nan(_stand_yaw):
		rotation.y = _stand_yaw + randf_range(-0.18, 0.18)
		_stand_yaw = NAN
	_set_walking(false)
	var cb := _on_arrive
	_on_arrive = Callable()
	if cb.is_valid():
		cb.call(self)


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
				rotation.y = lerp_angle(
					rotation.y, atan2(dir.x, dir.z), minf(1.0, delta * TURN_RATE)
				)
