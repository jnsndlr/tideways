extends SceneTree
## TID-328: frames Rhododendron swinging round when turned back mid-crossing.
##   godot --path . --script tools/manual_turn_shots.gd -- --scenario=tie_up_pier --out=DIR

var main: Node
var frames := 0
var out := "user://"
var cam := Camera3D.new()
var _ordered := false
var _shot := 0
var _centre := Vector3.ZERO
var _marks := [0.0, 0.3, 0.6, 0.9]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)
	root.add_child(cam)
	cam.far = 4000


func _process(_d: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	var sim: Simulation = main.sim
	var rhodo := sim.ferries[1]
	if frames == 5:
		Engine.time_scale = 6.0
	if not _ordered:
		if (
			rhodo.berth == Ferry.Berth.WORKING
			and rhodo.state == Ferry.State.SAILING
			and rhodo.traveled > 300.0
			and rhodo.path_left() > 300.0
		):
			Engine.time_scale = 1.0
			_centre = rhodo.global_position
			rhodo.order_move(rhodo.here().town.id, rhodo.slip_at(rhodo.here()))
			_ordered = true
		return false
	cam.look_at_from_position(_centre + Vector3(60, 170, 90), _centre)
	cam.make_current()
	if _shot < _marks.size() and rhodo._turn_t >= _marks[_shot]:
		root.get_viewport().get_texture().get_image().save_png("%s/turn_%d.png" % [out, _shot])
		_shot += 1
	elif _shot == _marks.size() and rhodo._turn_t < 0.0 and rhodo.speed > 2.0:
		root.get_viewport().get_texture().get_image().save_png("%s/turn_%d.png" % [out, _shot])
		quit(0)
		return true
	return frames > 40000
