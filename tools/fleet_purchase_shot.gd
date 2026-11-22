extends SceneTree
## Screenshots of buying a boat (stage 6): the fleet panel's buy flow, the tug
## towing her in, the tug alongside on her hip, her lying delivered, and her
## ferry panel. Needs a window (not --headless).
##
##   godot --path . --script tools/fleet_purchase_shot.gd -- --out=/tmp

var main: Node
var frames := 0
var out := "."
var boat: Ferry
var _hip_shot := false
var _done_at := -1


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _shot(name: String) -> void:
	var path := "%s/fleet_%s.png" % [out, name]
	root.get_viewport().get_texture().get_image().save_png(path)
	print("Saved " + path)


func _process(_delta: float) -> bool:
	frames += 1
	if main.get("sim") == null or main.get("hud") == null:
		return false
	var sim: Simulation = main.sim
	var hud: Hud = main.hud
	var panel: FleetPanel = hud._fleet_panel
	if frames == 40:
		hud._on_sidebar("fleet")
		panel._toggle_buy()
		panel._pick(1)
	elif frames == 50:
		_shot("buy")
	elif frames == 55:
		var gull: Terminal
		for t: Terminal in sim.terminals.values():
			if t.town.key.begins_with("island-7"):
				gull = t
		panel._buy(1, gull)
		hud._on_sidebar("fleet")
		boat = sim.ferries[-1]
		Engine.time_scale = 6.0
	elif frames == 90:
		hud.rig.target_dist = 260.0
	elif frames == 160:
		_shot("towing")
	elif boat and boat.tow and not _hip_shot and boat.tow.path.length - boat.tow.s < 200.0:
		_hip_shot = true
		Engine.time_scale = 1.0
		_shot("hip")
	elif boat and boat.berth == Ferry.Berth.TIED_UP and _done_at < 0:
		_done_at = frames
	elif _done_at > 0 and frames == _done_at + 20:
		_shot("delivered")
	elif _done_at > 0 and frames == _done_at + 300:
		_shot("tug_leaving")
		quit(0)
	if frames > 20000:
		quit(1)
	return false
