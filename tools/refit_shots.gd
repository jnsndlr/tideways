extends SceneTree
## Frames of the slip refit crew at work on Madrona's slip in the opening scenario: the
## crane lifting and placing piles and the skiff running round. For checking by eye.
##   godot --path . --script tools/refit_shots.gd -- --out=DIR [--at=0.1,0.2,...] [--yaw=RAD] [--dist=M] [--skiff]
## `at` is the work progress (0..1) of each frame; a negative one is how far the tow
## has come in (-0.5 for halfway), and that frame runs on for a while first so the
## wakes have time to show.

var main: Node
var frames := 0
var out := "user://"
var at: Array[float] = [0.0, 0.08, 0.1, 0.12, 0.13, 0.16, 0.2, 0.5, 0.75, 0.97]
var yaw := 0.9
var dist := 55.0
var on_skiff := false
var _term: Terminal
var _crew: SlipRefitCrew
var _cam := Camera3D.new()
var _shot := 0
var _wait := 0


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=")
		match kv[0]:
			"--out": out = kv[1]
			"--yaw": yaw = float(kv[1])
			"--dist": dist = float(kv[1])
			"--skiff": on_skiff = true
			"--at":
				at.clear()
				for s in kv[1].split(","):
					at.append(float(s))
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	if _term == null:
		for t: Terminal in main.sim.terminals.values():
			if t.island.name.begins_with("Madrona"):
				_term = t
		_term.buy_refit(_term.next_refit())
		_crew = _term.get_node("SlipRefitCrew")
		Engine.time_scale = 0.05
		root.add_child(_cam)
		_cam.current = true
		_cam.fov = 50
		_wait = -1
		return false
	if _wait < 0:
		if _shot >= at.size():
			quit(0)
			return true
		if at[_shot] < 0.0:
			_term.refit_stage = Terminal.RefitStage.ARRIVING
			_term.refit_remaining = Terminal.REFIT_ARRIVAL + Terminal.REFIT_WORK + Terminal.REFIT_DEPARTURE + at[_shot] * Terminal.REFIT_ARRIVAL
			Engine.time_scale = 0.4
			_wait = 120
		else:
			_term.refit_stage = Terminal.RefitStage.WORKING
			_term.refit_remaining = Terminal.REFIT_WORK + Terminal.REFIT_DEPARTURE - at[_shot] * Terminal.REFIT_WORK
			Engine.time_scale = 0.05
			_wait = 8
		return false
	var target: Vector3 = _crew._skiff.global_position if on_skiff else _crew._scow.global_position + Vector3(0, 5, 0)
	var fwd := _term.global_basis.z
	var side := _term.global_basis.x
	_cam.global_position = target + (fwd * cos(yaw) + side * sin(yaw)) * dist + Vector3.UP * dist * 0.45
	_cam.look_at(target)
	_wait -= 1
	if _wait == 0:
		var img := root.get_viewport().get_texture().get_image()
		img.save_png("%s/refit_%02d_%03d.png" % [out, _shot, int(at[_shot] * 1000)])
		_shot += 1
		_wait = -1
	return false
