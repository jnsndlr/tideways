extends SceneTree
## Touch editing of a boat's stops and timetable (TID-23), driven by emulated
## finger events (InputEventScreenTouch / ScreenDrag, which Godot turns into
## mouse events as it does on an iPad). Checks that a tap on a stepper moves a
## sailing once, that holding one repeats, that dragging the sailings list
## scrolls it without tapping what the finger started on, that stops come off
## and go on by tap, that every control is finger-sized, and that the editor
## fits the screen. The map camera mustn't move under a drag on the editor.
##
##   godot --headless --path . --fixed-fps 30 --script tests/ui/touch_edit_test.gd
##
## With a window, --shots=DIR also saves PNGs of the editor; run it with
## --resolution 1024x1366 (iPad portrait, in points) or 1366x1024 (landscape).

var main: Node
var ed: ScheduleEditor
var shots := ""
var tag := ""


func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--shots="):
			shots = arg.substr(8)
	main = load("res://scenes/main_map.tscn").instantiate()
	root.add_child(main)
	# In a window, the desk's own mouse would land between the emulated touches.
	root.add_child(RealMouseFilter.new())
	_run.call_deferred()


## Swallows mouse events that don't come from the emulated touches. It's the
## root's last child, so it sees input before the HUD does.
class RealMouseFilter extends Node:
	func _input(e: InputEvent) -> void:
		if e is InputEventMouse and e.device != InputEvent.DEVICE_ID_EMULATION:
			get_viewport().set_input_as_handled()


func _frames(n: int) -> void:
	for i in n:
		await process_frame


func _fail(msg: String) -> void:
	if shots != "":
		root.get_viewport().get_texture().get_image().save_png("%s/touch_%s_failed.png" % [shots, tag])
	push_error(msg)
	quit(1)


## A point in the HUD's coordinates as the window sees it, where touches land.
func _screen(p: Vector2) -> Vector2:
	return root.get_final_transform() * p


func _touch(p: Vector2, down: bool) -> void:
	var e := InputEventScreenTouch.new()
	e.index = 0
	e.position = _screen(p)
	e.pressed = down
	Input.parse_input_event(e)


func _drag(from: Vector2, to: Vector2, steps := 8) -> void:
	_touch(from, true)
	await _frames(2)
	for i in range(1, steps + 1):
		var e := InputEventScreenDrag.new()
		e.index = 0
		var a := from.lerp(to, float(i - 1) / steps)
		var b := from.lerp(to, float(i) / steps)
		e.position = _screen(b)
		e.relative = _screen(b) - _screen(a)
		Input.parse_input_event(e)
		await _frames(1)
	_touch(to, false)
	await _frames(2)


func _tap(b: Control) -> void:
	await _frames(2)
	var p := b.get_global_rect().get_center()
	if OS.get_environment("TAP_DEBUG") != "":
		print("tap %s at %s → screen %s, window %s" % [b.text, p, _screen(p), DisplayServer.window_get_size()])
	_touch(p, true)
	await _frames(2)
	_touch(p, false)
	await _frames(3)


func _hold(b: Control, seconds: float) -> void:
	await _frames(2)
	var p := b.get_global_rect().get_center()
	_touch(p, true)
	await create_timer(seconds).timeout
	_touch(p, false)
	await _frames(3)


func _button(prefix: String) -> Button:
	for b: Button in ed.find_children("*", "Button", true, false):
		if b.is_visible_in_tree() and b.text.begins_with(prefix):
			return b
	return null


## The `which`th sailing row's control named `name` (Step+5, DropSailing).
func _row_button(which: int, name: String) -> Button:
	var rows := ed._sailings.get_children()
	return rows[which].find_child(name, true, false) as Button


## The first row's `name` control whose centre shows in the sailings list.
func _visible_row_button(name: String) -> Button:
	var shown := ed._sailings_scroll.get_global_rect()
	for i in ed._sailings.get_child_count():
		var b := _row_button(i, name)
		if shown.has_point(b.get_global_rect().get_center()):
			return b
	return null


func _shot(name: String) -> void:
	if shots == "":
		return
	await _frames(2)
	var path := "%s/touch_%s_%s.png" % [shots, tag, name]
	root.get_viewport().get_texture().get_image().save_png(path)
	print("Saved " + path)


## Every visible button is at least TAP high and wide enough for a fingertip,
## and the whole editor lies on screen.
func _check_sizes() -> String:
	var view := root.get_visible_rect()
	var s := ed.scale.y
	for b: Button in ed.find_children("*", "Button", true, false):
		if not b.is_visible_in_tree():
			continue
		if b.size.y < ScheduleEditor.TAP - 0.5 or b.size.x < ScheduleEditor.TAP - 0.5:
			return "Button %s is %s, under %d" % [b.text, b.size, ScheduleEditor.TAP]
	var r := ed.get_global_rect()
	if not view.grow(1.0).encloses(r):
		return "Editor %s spills off the %s screen" % [r, view.size]
	print("Editor at %s on a %s screen, drawn ×%.2f" % [r, view.size, s])
	return ""


func _run() -> void:
	await _frames(20)
	var view := root.get_visible_rect().size
	tag = "portrait" if view.y > view.x else "landscape"
	var hud: Hud = main.hud
	# Stops and times are edited in the ferry panel's Schedule tab.
	ed = hud._ferry_panel._schedule_editor
	ed._times = [360, 370, 395]
	if not ed._moved(0, 15).is_empty():
		return _fail("The stepper let a sailing pass the next one")
	# At 20 minutes per round, delaying the middle sailing by ten fixes its
	# short gap but would make the last sailing late instead.
	if ed._allowed(ed._moved(1, 10), 20, Timetable.too_soon(ed._times, 20)):
		return _fail("The stepper transferred a conflict to another sailing")
	ed._times.clear()
	var sim: Simulation = main.sim
	var hiyu: Ferry = sim.ferries[0]
	hud.select_ferry(hiyu)
	main.rig.follow = null
	# On a short screen the opening toast lies over the tabs; taps go through it.
	await _frames(10)
	var cam_before: Vector3 = main.rig.target_pos
	var tab: Button = hud._ferry_panel._tab_buttons[FerryPanel.TAB_NAMES.find("Schedule")]
	await _tap(tab)
	if not ed.is_visible_in_tree() or ed.ferry != hiyu:
		return _fail("The Schedule tab didn't open the editor by tap")
	await _tap(_button("Set times"))
	if ed._times != [360]:
		return _fail("Set times by tap gave %s" % [ed._times])
	await _tap(_row_button(0, "Step+15"))
	if ed._times != [375]:
		return _fail("A tap on +15 gave %s, not [375]" % [ed._times])
	print("Tap +15: 6:15 AM")
	await _hold(_row_button(0, "Step+5"), 1.2)
	var held: int = ed._times[0] - 375
	# 0.4 s before it repeats, then every 0.09 s: about 9 steps in 1.2 s.
	if held < 30 or held % 5 != 0:
		return _fail("Holding +5 for 1.2 s moved her %d min" % held)
	print("Hold +5 for 1.2 s: +%d min, to %s" % [held, Timetable.text(ed._times[0])])
	await _hold(_row_button(0, "Step-15"), 0.2)
	if ed._times[0] - 375 != held - 15:
		return _fail("A short press on −15 should step once, gave %s" % [ed._times])
	for i in 4:
		var add := _button("Add a sailing at")
		if add == null or add.disabled:
			break
		await _tap(add)
	print("Sailings: %s" % ", ".join(ed._times.map(func(t): return Timetable.text(t))))
	if ed._times.size() < 4:
		return _fail("Only %d sailings could be added by tap" % ed._times.size())
	await _frames(4)
	var problem := _check_sizes()
	if problem != "":
		return _fail(problem)
	await _shot("sailings")
	var scroll := ed._sailings_scroll
	var bar := scroll.get_v_scroll_bar()
	if bar.max_value - bar.page <= 1.0:
		return _fail("The sailings list fits (%d of %d), so the drag check needs more sailings" % [bar.page, bar.max_value])
	# Drag the list up from a stepper, then from a ✕: it scrolls, nothing steps or drops.
	scroll.scroll_vertical = int(bar.max_value)
	await _frames(2)
	var times_before := ed._times.duplicate()
	var top := scroll.scroll_vertical
	var start := _row_button(ed._times.size() - 1, "Step-5").get_global_rect().get_center()
	await _drag(start, start + Vector2(0, 140))
	if scroll.scroll_vertical >= top:
		return _fail("Dragging the list down didn't scroll it back (%d → %d)" % [top, scroll.scroll_vertical])
	if ed._times != times_before:
		return _fail("A drag from a stepper changed the times: %s" % [ed._times])
	print("Drag from a stepper scrolls %d → %d, times unchanged" % [top, scroll.scroll_vertical])
	top = scroll.scroll_vertical
	start = _visible_row_button("DropSailing").get_global_rect().get_center()
	await _drag(start, start - Vector2(0, 140))
	if scroll.scroll_vertical <= top or ed._times != times_before:
		return _fail("A drag from ✕ should scroll and keep every sailing (%d → %d, %s)" % [top, scroll.scroll_vertical, ed._times])
	print("Drag from ✕ scrolls %d → %d, every sailing kept" % [top, scroll.scroll_vertical])
	if not main.rig.target_pos.is_equal_approx(cam_before):
		return _fail("The map camera moved under a drag on the editor")
	# ✕ by tap drops one.
	await _tap(_row_button(ed._times.size() - 1, "DropSailing"))
	if ed._times.size() != times_before.size() - 1:
		return _fail("A tap on ✕ didn't drop a sailing")
	# Stops by tap: take Madrona off, put Gullrock and Madrona on.
	var madrona: String = ed._name(ed._draft[1])
	var removes: Array = ed._stops.find_children("*", "Button", true, false)
	await _tap(removes[1])
	if ed._draft.size() != 1:
		return _fail("A tap on Remove left %d stops" % ed._draft.size())
	await _tap(_button(main.sim.map.town_by_key("island-7/0").name))
	await _tap(_button(madrona))
	if ed._draft.size() != 3:
		return _fail("Taps on Add a stop gave %d stops" % ed._draft.size())
	print("Stops by tap: %s" % " → ".join(ed._draft.map(func(id): return ed._name(id))))
	await _frames(4)
	problem = _check_sizes()
	if problem != "":
		return _fail(problem)
	await _shot("three_stops")
	await _tap(_button("Cancel"))
	if ed.visible:
		return _fail("Cancel by tap left the editor open")
	print("TEST PASSED")
	quit(0)
