extends SceneTree
## Screenshots of the slip clash warnings (TID-23 slice 4): the Hiyu on two
## sailings, the Heron's editor with one sailing that comes in to Madrona while
## the Hiyu is there and one clear of her, then the Heron's ferry panel once
## applied. Needs a window (not --headless).
##
##   godot --path . --script tools/slip_conflict_shot.gd -- --scenario=two_boats --out=/tmp

var main: Node
var frames := 0
var out := "."
var _docked_at := -1


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _shot(name: String) -> void:
	var path := "%s/slip_clash_%s.png" % [out, name]
	root.get_viewport().get_texture().get_image().save_png(path)
	print("Saved " + path)


func _id(sim: Simulation, key: String) -> int:
	for isl in sim.map.islands:
		if isl.key == key:
			return isl.id
	return -1


func _process(_delta: float) -> bool:
	frames += 1
	if main.sim == null or main.hud == null:
		return false
	var sim: Simulation = main.sim
	var hud: Hud = main.hud
	var ed: ScheduleEditor = hud._schedule_editor
	var hiyu: Ferry = sim.ferries[0]
	var heron: Ferry = sim.ferries[1]
	match frames:
		30:
			var hiyu_ids: Array[int] = [_id(sim, "island-1"), _id(sim, "island-2")]
			var heron_ids: Array[int] = [_id(sim, "island-7"), _id(sim, "island-2")]
			var oh := hiyu.plan_offsets(hiyu_ids)
			var orr := heron.plan_offsets(heron_ids)
			var heron_t := 400
			var hiyu_t := roundi(heron_t + orr[1] - heron.planned_dwell() - oh[1] + hiyu.planned_dwell() * 0.5)
			var hiyu_times: Array[int] = [hiyu_t, hiyu_t + 300]
			if not sim.reschedule(hiyu, hiyu_ids, hiyu_times):
				push_error("Couldn't time the Hiyu")
			hud.select_ferry(heron)
			ed.open(heron)
			ed._timed = true
			ed._times.assign([heron_t, heron_t + 370, heron_t + 740])
			ed._rebuild()
		35:
			# (again, once the old rows are gone: on this branch _fit counts them)
			ed._rebuild()
		40:
			_shot("editor")
			ed._on_apply()
		50:
			hud.select_ferry(hiyu)
		200:
			_shot("panel_hiyu")
			hud.select_ferry(heron)
		210:
			_shot("panel")
			Engine.time_scale = 6.0
	# Then the Heron coming in to Madrona's dock, which faces Port Rosario.
	if frames > 210 and _docked_at < 0 and heron.state != Ferry.State.SAILING and heron.here().island.key == "island-2":
		_docked_at = frames
	if _docked_at > 0 and frames == _docked_at + 3:
		_shot("heron_at_madrona")
		print("TEST PASSED")
		quit(0)
	if frames > 6000:
		push_error("The Heron never reached Madrona")
		quit(1)
	return false
