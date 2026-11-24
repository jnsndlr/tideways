class_name MotorYachtView
extends Node3D
## Running lights, anchor light and anchor line drawn in the yacht model's frame.

var _yacht: MotorYacht
var _night_lights := Node3D.new()
var _navigation := MeshInstance3D.new()
var _mast := MeshInstance3D.new()
var _rode := MeshInstance3D.new()


func _init(yacht: MotorYacht) -> void:
	_yacht = yacht
	scale = Vector3.ONE * yacht.spec.scale
	add_child(_night_lights)
	_navigation.mesh = Models.motor_yacht_nav_lights()
	_mast.mesh = Models.motor_yacht_mast_light()
	for lamp: MeshInstance3D in [_navigation, _mast]:
		lamp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		lamp.layers = NightLights.LAYER
		_night_lights.add_child(lamp)
	yacht.lights.visibility_changed.connect(_sync_night_lights)
	_sync_night_lights()
	_rode.mesh = Models.motor_yacht_rode()
	_rode.hide()
	add_child(_rode)


func _sync_night_lights() -> void:
	_night_lights.visible = _yacht.lights.visible


func _process(_delta: float) -> void:
	refresh()


func refresh() -> void:
	var state := _yacht.state
	var under_way := _yacht.road() != Vessel.Road.MOORED
	var at_anchor := state == MotorYacht.State.ANCHORED or state == MotorYacht.State.SETTING
	_navigation.visible = under_way
	_mast.visible = under_way or at_anchor or state == MotorYacht.State.WEIGHING
	_rode.visible = at_anchor or (state == MotorYacht.State.WEIGHING and _yacht.weighing_progress() < 0.85)
