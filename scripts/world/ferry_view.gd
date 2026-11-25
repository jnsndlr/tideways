class_name FerryView
extends Node3D
## The hull, thin shadow geometry and car deck nets of one ferry.

var hull := MeshInstance3D.new()
var nets: Array[MeshInstance3D] = []
var _ferry: Ferry


func _init(ferry: Ferry) -> void:
	name = "FerryView"
	_ferry = ferry
	var fc := ferry.fc
	hull.mesh = Models.ferry(fc)
	hull.material_override = Models.hull_material()
	hull.set_instance_shader_parameter("room_seed", ferry.room_seed)
	add_child(hull)
	var thin_shadow := Models.ferry_thin_shadow(fc)
	if thin_shadow:
		var shadow := MeshInstance3D.new()
		shadow.mesh = thin_shadow
		shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		hull.add_child(shadow)
	for end: float in [-1.0, 1.0]:
		var net := MeshInstance3D.new()
		net.mesh = Models.ferry_net(fc)
		net.position.z = end * fc.net_z
		add_child(net)
		nets.append(net)


func _enter_tree() -> void:
	_ferry.net_state_changed.connect(_sync_nets)
	_sync_nets()


func _exit_tree() -> void:
	_ferry.net_state_changed.disconnect(_sync_nets)


func _sync_nets() -> void:
	nets[0].visible = _ferry.open_net_end != -1
	nets[1].visible = _ferry.open_net_end != 1
	for net in nets:
		net.set_instance_shader_parameter("wind", _ferry.net_wind)
