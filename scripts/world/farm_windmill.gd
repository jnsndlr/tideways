extends Node3D

@export_range(0.0, 30.0, 0.1, "suffix:RPM") var wheel_rpm := 3.0
@export_range(0.0, 90.0, 1.0, "degrees") var vane_swing_degrees := 22.0
@export_range(1.0, 120.0, 0.5, "suffix:s") var vane_period := 24.0

var breeze_phase := 0.0
@onready var vane: Node3D = find_child("VaneHead", true, false)
@onready var wheel: Node3D = vane.get_node("WindWheel")


func _process(delta: float) -> void:
	breeze_phase = fmod(breeze_phase + TAU * delta / vane_period, TAU)
	vane.rotation.y = deg_to_rad(16.0 + vane_swing_degrees * sin(breeze_phase))
	wheel.rotate_object_local(Vector3.BACK, TAU * wheel_rpm * delta / 60.0)
