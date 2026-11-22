extends SceneTree
## Screenshots of buying a boat (stage 6): the fleet panel's buy flow, the tug
## towing her in, dropping back along her side, pushing her into Port Rosario's
## tie-up, her lying delivered, then sold and towed away. Needs a window (not --headless).
##
##   godot --path . --script tools/fleet_purchase_shot.gd -- --out=/tmp

var main: Node
var frames := 0
var out := "."
var boat: Ferry
var _shots := {}
var _done_at := -1


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _shot(name: String) -> void:
	if _shots.has(name):
		return
	_shots[name] = true
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
		panel._buy(1)
		hud._on_sidebar("fleet")
		boat = sim.ferries[-1]
		Engine.time_scale = 8.0
	elif frames == 90:
		hud.rig.target_dist = 300.0
	elif frames == 160:
		_shot("towing")
	if boat and is_instance_valid(boat) and boat.tow and boat.tow.phase == DeliveryTow.Phase.TOWING:
		var rem := boat.tow.path.length - boat.tow.s
		if rem < 700.0:
			Engine.time_scale = 2.0
		if rem < 470.0:
			_shot("dropping_back")
		if rem < 220.0:
			_shot("pushing")
		if rem < 40.0:
			_shot("pushing_in")
	if boat and is_instance_valid(boat) and boat.berth == Ferry.Berth.TIED_UP and _done_at < 0 and boat.tow == null:
		_done_at = frames
	if _done_at > 0 and frames == _done_at + 60:
		_shot("delivered")
		Engine.time_scale = 8.0
		sim.sell_ferry(boat)
		hud.select_vessel(sim.tows[-1])
	if _done_at > 0 and boat and is_instance_valid(boat) and boat.tow and boat.tow.phase == DeliveryTow.Phase.PULLING and boat.tow.s > 60.0:
		_shot("towed_away")
		quit(0)
	if frames > 30000:
		quit(1)
	return false
