extends SceneTree
## Screenshots of the projected daily cost (TID-24): the stop editor's cost line
## for a first timetable, then a draft (one more sailing, at Economy) against the
## timetable she runs, and the ferry panel. Needs a window (not --headless).
##
##   godot --path . --script tools/daily_cost_ui_shot.gd -- --out=/tmp

var main: Node
var frames := 0
var out := "."


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--out="):
			out = arg.substr(6)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)


func _press(ed: Control, prefix: String) -> void:
	for b: Button in ed.find_children("*", "Button", true, false):
		if b.is_visible_in_tree() and not b.disabled and b.text.begins_with(prefix):
			b.pressed.emit()
			return
	push_error("No enabled button " + prefix)


func _shot(name: String) -> void:
	var path := "%s/daily_cost_%s.png" % [out, name]
	root.get_viewport().get_texture().get_image().save_png(path)
	print("Saved " + path)


func _process(_delta: float) -> bool:
	frames += 1
	if main.sim == null or main.hud == null:
		return false
	var hud: Hud = main.hud
	var ed: ScheduleEditor = hud._ferry_panel._schedule_editor
	var hiyu: Ferry = main.sim.ferries[0]
	match frames:
		30:
			hud.select_ferry(hiyu)
			hud._ferry_panel.open_schedule()
			_press(ed, "Set times")
			_press(ed, "Add a sailing")
		40:
			_shot("first")
			_press(ed, "Apply")
		50:
			_shot("panel")
			ed.open(hiyu)
			_press(ed, "Add a sailing")
			_press(ed, "Economy")
		60:
			_shot("draft_vs_now")
			print("TEST PASSED")
			quit(0)
	return false
