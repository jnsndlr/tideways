class_name MotorYachtView
extends Node3D
## Running lights, anchor light and anchor line drawn in the yacht model's frame.

var _yacht: MotorYacht
var _navigation: MeshInstance3D
var _mast: MeshInstance3D
var _rode := MeshInstance3D.new()


func _init(yacht: MotorYacht) -> void:
	_yacht = yacht
	scale = Vector3.ONE * yacht.spec.scale
	var lamps := VesselLightGroup.new(yacht.lights)
	add_child(lamps)
	_navigation = lamps.add_lamp(Models.motor_yacht_nav_lights())
	_mast = lamps.add_lamp(Models.motor_yacht_mast_light())
	_rode.mesh = Models.motor_yacht_rode()
	_rode.hide()
	add_child(_rode)


func _process(_delta: float) -> void:
	refresh()


func refresh() -> void:
	var state := _yacht.state
	var under_way := _yacht.road() != Vessel.Road.MOORED
	var at_anchor := state == MotorYacht.State.ANCHORED or state == MotorYacht.State.SETTING
	_navigation.visible = under_way
	_mast.visible = under_way or at_anchor or state == MotorYacht.State.WEIGHING
	_rode.visible = at_anchor or (state == MotorYacht.State.WEIGHING and _yacht.weighing_progress() < 0.85)
