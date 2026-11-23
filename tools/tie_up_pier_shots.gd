extends SceneTree
## Frames the shared tie-up pier at Madrona from a few angles.
##   godot --path . --script tools/tie_up_pier_shots.gd -- --scenario=tie_up_pier --out=DIR

var main: Node
var frames := 0
var out := "user://"
var shots := [[2.6, 0.5, 170.0], [3.6, 0.35, 120.0], [1.9, 0.9, 230.0], [3.1, 0.18, 70.0]]


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--out="):
			out = a.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_d: float) -> bool:
	frames += 1
	if frames < 60 or main.sim == null:
		return false
	var term: Terminal
	for t: Terminal in main.sim.terminals.values():
		if not t.town.tie_ups().is_empty():
			term = t
	var isl: MapData.Town = term.town
	var ties := isl.tie_ups()
	var v := (isl.slip_offset(ties.front()) + isl.slip_offset(ties.back())) * 0.5
	var target := term.transform * Vector3(v, 0, Layout.PIER_END + 20.0)
	var i := (frames - 60) / 20
	if i >= shots.size():
		return true
	if (frames - 60) % 20 == 0:
		var s: Array = shots[i]
		var cam := Camera3D.new()
		root.add_child(cam)
		cam.far = 4000
		var dir := Vector3(cos(s[0]), 0, sin(s[0])) * cos(s[1]) + Vector3.UP * sin(s[1])
		cam.look_at_from_position(target + dir * s[2], target)
		cam.make_current()
	if (frames - 60) % 20 == 15:
		root.get_viewport().get_texture().get_image().save_png("%s/pier_%d.png" % [out, i])
	return false
