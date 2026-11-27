extends PathFollow3D
## Drives a farm tractor around a closed lane. The GLB faces local +Z.

@export_range(0, 1) var starting_fraction := 0.0
@export var cruising_speed := 3.0

var front_wheels: Array[Node] = []
var rear_wheels: Array[Node] = []


func _ready() -> void:
	use_model_front = true
	rotation_mode = PathFollow3D.ROTATION_Y
	progress_ratio = starting_fraction
	front_wheels = find_children("Front*", "Node3D", true, false)
	rear_wheels = find_children("Rear*", "Node3D", true, false)


func _physics_process(delta: float) -> void:
	# Both vehicles ease off on the headlands and accelerate along the straight.
	var straightness := absf(global_basis.z.x)
	var distance := cruising_speed * lerpf(0.65, 1.0, straightness) * delta
	progress += distance
	for wheel: Node3D in front_wheels:
		wheel.rotate_x(distance / 0.53)
	for wheel: Node3D in rear_wheels:
		wheel.rotate_x(distance / 0.80)
