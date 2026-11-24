class_name VesselHullView
extends MeshInstance3D
## Model frame of a marine vessel, including its hull and optional name plate.

func _init(vessel: Vessel) -> void:
	name = "VesselHullView"
	var spec := vessel.spec
	mesh = spec.model.call(vessel.model_variant)
	scale = Vector3.ONE * spec.scale
	material_override = Models.hull_material()
	set_instance_shader_parameter("room_seed", vessel.room_seed)
	if spec.name_plate.is_valid() and vessel.vessel_name != "":
		var plate: ArrayMesh = spec.name_plate.call(vessel.vessel_name)
		if plate:
			var lettering := MeshInstance3D.new()
			lettering.mesh = plate
			add_child(lettering)
