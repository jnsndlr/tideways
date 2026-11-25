class_name VesselNightLights
extends MeshInstance3D
## A marine vessel's lamp mesh and, for a pilot boat or tug, its running lights.

var _tender: ShipTender
var _running_lights: Array[MeshInstance3D] = []


func _init(vessel: Vessel) -> void:
	name = "VesselNightLights"
	mesh = VesselAppearance.lights(vessel.spec)
	scale = Vector3.ONE * VesselAppearance.model_scale(vessel.spec)
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	layers = NightLights.LAYER
	hide()
	_tender = vessel as ShipTender
	if _tender:
		for lamp_mesh in VesselAppearance.running_lights(vessel.spec):
			var lamp := MeshInstance3D.new()
			lamp.mesh = lamp_mesh
			lamp.cast_shadow = cast_shadow
			lamp.layers = layers
			lamp.visible = _tender.state != ShipTender.State.ALONGSIDE
			add_child(lamp)
			_running_lights.append(lamp)


func _ready() -> void:
	set_process(_tender != null)


func _process(_delta: float) -> void:
	for lamp in _running_lights:
		lamp.visible = _tender.state != ShipTender.State.ALONGSIDE
