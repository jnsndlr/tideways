class_name PublicWorksGarage
extends Node3D
## Bay numbers run from 1 to 3, left to right when viewed from the apron.

const SECTIONS := 8
const SECTION_HEIGHT := 0.6
const CURVE_START := 4.5
const RADIUS := 0.65
const ARC := RADIUS * PI / 2.0
const FULL_TRAVEL := CURVE_START + ARC
const SPEED := 2.1

var _sections: Array[Node3D] = []
var _travel := PackedFloat32Array([0, 0, 0])
var _targets := PackedFloat32Array([0, 0, 0])


func _ready() -> void:
	for bay in range(1, 4):
		for row in range(1, SECTIONS + 1):
			_sections.append($Building.find_child("Bay%dPanel%d" % [bay, row], true, false))


func set_bay_open(bay: int, opened: bool) -> void:
	assert(bay >= 1 and bay <= 3)
	_targets[bay - 1] = FULL_TRAVEL if opened else 0.0


func is_bay_open(bay: int) -> bool:
	return is_equal_approx(_travel[bay - 1], FULL_TRAVEL)


func _process(delta: float) -> void:
	for bay in _targets.size():
		if is_equal_approx(_travel[bay], _targets[bay]):
			continue
		_travel[bay] = move_toward(_travel[bay], _targets[bay], SPEED * delta)
		for row in SECTIONS:
			var section := _sections[bay * SECTIONS + row]
			var distance := _travel[bay] + (row + 0.5) * SECTION_HEIGHT
			var angle := clampf((distance - CURVE_START) / RADIUS, 0.0, PI / 2.0)
			section.position.y = minf(distance, CURVE_START) + RADIUS * sin(angle)
			section.position.z = (
				7.12 - RADIUS * (1.0 - cos(angle)) - maxf(0, distance - FULL_TRAVEL)
			)
			section.rotation.x = -angle
