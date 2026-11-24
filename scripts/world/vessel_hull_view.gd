class_name VesselHullView
extends MeshInstance3D
## Model frame of a marine vessel, including its hull and optional name plate.

func _init(vessel: Vessel) -> void:
	name = "VesselHullView"
	var spec := vessel.spec
	mesh = VesselAppearance.hull(spec, vessel.model_variant)
	scale = Vector3.ONE * VesselAppearance.model_scale(spec)
	material_override = Models.hull_material()
	set_instance_shader_parameter("room_seed", vessel.room_seed)
	var plate := VesselAppearance.name_plate(spec, vessel.vessel_name)
	if plate:
		var lettering := MeshInstance3D.new()
		lettering.mesh = plate
		add_child(lettering)
