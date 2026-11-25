class_name VesselLightGroup
extends Node3D
## Groups a vessel's individual lamps under its existing day/night switch.

var _vessel_lights: MeshInstance3D


func _init(vessel_lights: MeshInstance3D) -> void:
	_vessel_lights = vessel_lights
	_vessel_lights.visibility_changed.connect(_sync_visibility)
	_sync_visibility()


func add_lamp(mesh: Mesh) -> MeshInstance3D:
	var lamp := MeshInstance3D.new()
	lamp.mesh = mesh
	lamp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lamp.layers = NightLights.LAYER
	add_child(lamp)
	return lamp


func _sync_visibility() -> void:
	visible = _vessel_lights.visible
