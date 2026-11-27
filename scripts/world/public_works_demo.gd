extends Node3D
## Box truck starts parked nose-out. Both parked positions clear the door sweep.

func _ready() -> void:
	$Truck.mesh = Models.vehicle("truck_box", 0)
	$Pickup.mesh = Models.vehicle("pickup_dually", 3)
	var garage: PublicWorksGarage = $Garage
	garage.set_bay_open(3, true)
	var destination := 15.0
	while is_inside_tree():
		await get_tree().create_timer(1.2).timeout
		garage.set_bay_open(2, true)
		while not garage.is_bay_open(2):
			await get_tree().process_frame
		var drive := create_tween().set_trans(Tween.TRANS_SINE)
		drive.tween_property($Truck, "position:z", destination, 4.0)
		await drive.finished
		garage.set_bay_open(2, false)
		await get_tree().create_timer(3.6).timeout
		destination = 0.0 if destination > 0.0 else 15.0
