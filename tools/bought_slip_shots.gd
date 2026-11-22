extends SceneTree
## Port Rosario in the opening scenario with a second working slip and a tie-up
## bought and built (stage 5), seen from offshore. For checking by eye.
##   godot --path . --script tools/bought_slip_shots.gd -- --out=DIR [--yaw=RAD] [--dist=M]

var main: Node
var frames := 0
var out := "user://"
var yaw := 0.5
var dist := 260.0
var _term: Terminal
var _step := 0
var _wait := 0


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=")
		match kv[0]:
			"--out": out = kv[1]
			"--yaw": yaw = float(kv[1])
			"--dist": dist = float(kv[1])
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


## Buys `kind` and runs its build on to the moment the slip opens.
func _build(kind: TerminalUpgrade.Kind) -> void:
	var u := _term.find_upgrade(kind)
	if u == null or not _term.buy(u):
		push_warning("Couldn't buy %s: %s" % [TerminalUpgrade.Kind.keys()[kind], u.blocked if u else "not offered"])
		return
	_term.refit_stage = Terminal.RefitStage.WORKING
	_term.refit_remaining = Terminal.REFIT_DEPARTURE + 0.01


func _process(_delta: float) -> bool:
	frames += 1
	if frames < 5 or main.sim == null:
		return false
	if _term == null:
		for t: Terminal in main.sim.terminals.values():
			if t.town.key.begins_with("island-1/"):
				_term = t
		main.sim.ledger.cash = 100000.0
		_build(TerminalUpgrade.Kind.SLIP)
		_wait = 30
		return false
	_wait -= 1
	if _wait > 0:
		return false
	match _step:
		0:
			_term.refit_remaining = 0.01
			main.sim.ferries[0].request_lay_up()
			_step = 1
			_wait = 10
		1:
			_build(TerminalUpgrade.Kind.TIE_UP)
			_step = 2
			_wait = 30
		2:
			_term.refit_remaining = 0.01
			_step = 3
			_wait = 60
		3:
			main.rig.follow = null
			main.rig.target_pos = _term.to_global(Vector3(0, 0, 40))
			main.rig.target_dist = dist
			main.rig.target_pitch = 0.6
			var dock := -_term.global_transform.basis.z
			main.rig.target_yaw = atan2(dock.x, dock.z) + PI + yaw
			main.rig.snap()
			_step = 4
			_wait = 20
		4:
			var img := root.get_viewport().get_texture().get_image()
			img.save_png("%s/slips.png" % out)
			print("Saved %s/slips.png" % out)
			quit(0)
			return true
	return false
