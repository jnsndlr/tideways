extends SceneTree
## Frames the shared tie-up pier at Madrona from a few angles.
##   godot --path . --script tools/tie_up_pier_shots.gd -- --scenario=tie_up_pier --out=DIR

var main: Node
var frames := 0
var out := "user://"
var shots := [[0.65, 0.55, 150.0], [2.45, 0.5, 145.0], [1.55, 1.05, 185.0], [0.9, 0.3, 90.0]]
var cam := Camera3D.new()


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
	if frames < 60 or main.sim == null:
		return false
	if frames == 60:
		main.sim.minutes = 12.0 * 60.0
		main.day_cycle.apply(main.sim.hour())
	var term: Terminal
	for t: Terminal in main.sim.terminals.values():
		if t.town.key.begins_with("island-2/") and t.town.tie_ups().size() >= 2:
			term = t
	if term == null:
		push_error("Expected the two Madrona tie-ups in the tie_up_pier scenario.")
		quit(1)
		return true
	var isl: MapData.Town = term.town
	var ties := isl.tie_ups()
	var v := (isl.slip_offset(ties.front()) + isl.slip_offset(ties.back())) * 0.5
	var target := term.transform * Vector3(v, 0, Layout.PIER_END + 20.0)
	var i := (frames - 60) / 20
	if i >= shots.size():
		return true
	if (frames - 60) % 20 == 0:
		var s: Array = shots[i]
		var dir := Vector3(cos(s[0]), 0, sin(s[0])) * cos(s[1]) + Vector3.UP * sin(s[1])
		cam.look_at_from_position(target + term.transform.basis * dir * s[2], target)
		cam.make_current()
	if (frames - 60) % 20 == 15:
		root.get_viewport().get_texture().get_image().save_png("%s/pier_%d.png" % [out, i])
	return false
