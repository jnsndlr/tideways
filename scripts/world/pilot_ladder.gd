class_name PilotLadder
extends MeshInstance3D
## The ship's boarding ladder, drawn in the pilot boat hull's local frame.

func _init(boat: PilotBoat) -> void:
	hide()
	boat.transfer_started.connect(_deploy.bind(boat.spec.scale))
	boat.transfer_ended.connect(hide)


func _deploy(cargo: CargoShip, offset: float, hull_scale: float) -> void:
	var deck_height := 3.2 * cargo.spec.scale
	mesh = Models.pilot_ladder(absf(offset) / hull_scale, deck_height / hull_scale)
	rotation = Vector3(0, 0 if offset > 0.0 else PI, 0)
	show()
