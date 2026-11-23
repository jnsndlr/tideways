class_name ScheduleEditor
extends PanelContainer
## Edits one boat's stops (stage 4). The draft lists her stops in turn with a
## button to drop each; below are the company's terminals to add next, each
## greyed out with the reason when she can't go there. Apply hands the stops to
## the simulation, which gives them to her at her next call at one of them.
## Below the stops is her timetable: as loading allows, or the times she leaves
## her first stop. A time she can't make (Ferry.plan_offsets) can't be set.
## Her pace is drafted here too, and below the sailings is what the draft should
## cost a day (Ferry.daily_cost) beside what her timetable now costs.
##
## Built for touch as well as a mouse (TID-23): every control is a filled button
## at least TAP high, nothing needs hover or a right click, a stepper held down
## repeats, and the sailings list scrolls by dragging anywhere on it. On a tall
## screen (an iPad in portrait) the whole editor is drawn larger.

const TAP := 52.0 ## least height of anything to tap (about 44 pt on an iPad in landscape)
const HOLD_DELAY := 0.4 ## seconds a stepper is held before it repeats
const REPEAT := 0.09 ## seconds between repeats while held
const DRAG_SLOP := 10.0 ## a press that moves this far is a drag, not a tap
const LIST_MAX := 330.0 ## tallest the sailings list grows before it scrolls

var sim: Simulation
var ferry: Ferry
var _draft: Array[int] = []
var _times: Array[int] = []
var _timed := false
var _pace := Ferry.SERVICE_PACE
var _pace_buttons: Array[Button] = []
var _cost: Label
var _cost_change: Label
var _make_label: Callable
var _title: Label
var _stops := VBoxContainer.new()
var _loop_note: Label
var _adds := VBoxContainer.new()
var _problem: Label
var _mode_auto: Button
var _mode_timed: Button
var _round_note: Label
var _sailings := VBoxContainer.new()
var _sailings_scroll := ScrollContainer.new()
var _add_sailing: Button
var _apply: Button
var _fill: StyleBoxFlat
var _fill_hover: StyleBoxFlat
## The stepper being held: {time, step, t, repeating}, or empty.
var _hold := {}
## Where a press on the sailings list began (INF if it didn't), and its scroll then.
var _press_at := Vector2.INF
var _press_scroll := 0
## Whether the current (or last) press became a drag of the list; a drag never taps.
var _dragging := false
var _scroll_to_end := false
## Where her draft and another boat's timetable want one slip at once (SlipConflicts).
var _clash_note: Label


## `make_label(text, size, color, bold)` builds a label in the HUD's fonts.
func setup(s: Simulation, make_label: Callable) -> void:
	sim = s
	_make_label = make_label
	anchor_left = 0.5
	anchor_right = 0.5
	offset_left = -220
	offset_right = 220
	offset_top = 96
	grow_horizontal = Control.GROW_DIRECTION_BOTH
	_fill = StyleBoxFlat.new()
	_fill.bg_color = Color(1, 1, 1, 0.07)
	_fill.set_corner_radius_all(6)
	_fill.set_content_margin_all(6)
	_fill_hover = _fill.duplicate()
	_fill_hover.bg_color = Color(1, 1, 1, 0.12)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	add_child(column)
	_title = make_label.call("", 13, Hud.MUTED, true)
	column.add_child(_title)
	column.add_child(HSeparator.new())
	_stops.add_theme_constant_override("separation", 4)
	column.add_child(_stops)
	_loop_note = make_label.call("", 12, Hud.MUTED, false)
	_loop_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_loop_note)
	column.add_child(HSeparator.new())
	column.add_child(make_label.call("ADD A STOP", 11, Hud.MUTED, true))
	_adds.add_theme_constant_override("separation", 4)
	column.add_child(_adds)
	column.add_child(HSeparator.new())
	column.add_child(make_label.call("TIMETABLE", 11, Hud.MUTED, true))
	var modes := HBoxContainer.new()
	modes.add_theme_constant_override("separation", 6)
	column.add_child(modes)
	var paces := HBoxContainer.new()
	paces.add_theme_constant_override("separation", 6)
	for i in Ferry.PACES.size():
		var b := _button(Ferry.PACES[i][1])
		b.toggle_mode = true
		b.pressed.connect(_set_pace.bind(i))
		paces.add_child(b)
		_pace_buttons.append(b)
	_mode_auto = _button("As loading allows")
	_mode_auto.toggle_mode = true
	_mode_auto.pressed.connect(_set_timed.bind(false))
	modes.add_child(_mode_auto)
	_mode_timed = _button("Set times")
	_mode_timed.toggle_mode = true
	_mode_timed.pressed.connect(_set_timed.bind(true))
	modes.add_child(_mode_timed)
	_round_note = make_label.call("", 13, Hud.MUTED, false)
	_round_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_round_note)
	_sailings.add_theme_constant_override("separation", 4)
	_sailings.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_sailings_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	# Dragging is ours (_input), so it works over the buttons too; this stops
	# Godot's own touch dragging from scrolling the list a second time.
	_sailings_scroll.scroll_deadzone = 1 << 20
	_sailings_scroll.add_child(_sailings)
	column.add_child(_sailings_scroll)
	_add_sailing = _button("Add a sailing")
	_add_sailing.pressed.connect(_on_add_sailing)
	column.add_child(_add_sailing)
	_clash_note = make_label.call("", 12, SlipConflictText.WARN, false)
	_clash_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_clash_note)
	column.add_child(paces)
	_cost = make_label.call("", 14, Hud.TEXT, true)
	_cost.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_cost)
	_cost_change = make_label.call("", 13, Hud.MUTED, false)
	_cost_change.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_cost_change)
	column.add_child(HSeparator.new())
	_problem = make_label.call("", 13, FinancePanel.LOSS, false)
	_problem.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_problem)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	column.add_child(row)
	var cancel := _button("Cancel")
	cancel.pressed.connect(hide)
	row.add_child(cancel)
	_apply = _button("Apply")
	_apply.pressed.connect(_on_apply)
	row.add_child(_apply)
	hide()


func _ready() -> void:
	get_viewport().size_changed.connect(func(): if visible: _fit())
	# Grows from its top centre, wherever its width settles.
	resized.connect(func(): pivot_offset = Vector2(size.x * 0.5, 0.0))


func open(f: Ferry) -> void:
	ferry = f
	_draft.assign(f.next_stops if not f.next_stops.is_empty() else f.stops)
	_times.assign(f._next_timetable if not f.next_stops.is_empty() else f.timetable)
	_timed = not _times.is_empty()
	_pace = f.pace
	_rebuild()
	show()


func _button(text: String, width := 0.0) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(width, TAP)
	b.add_theme_stylebox_override("normal", _fill)
	b.add_theme_stylebox_override("hover", _fill_hover)
	if width == 0.0:
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return b


## Frees `box`'s children now, so its size is right before the next _fit.
static func _clear(box: Node) -> void:
	for c in box.get_children():
		box.remove_child(c)
		c.queue_free()


func _name(id: int) -> String:
	return sim.map.islands[id].name.trim_suffix(" Island")


func _rebuild() -> void:
	_title.text = "STOPS · " + ferry.ferry_name.to_upper()
	_clear(_stops)
	_clear(_adds)
	for i in _draft.size():
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		var label: Label = _make_label.call("%d.  %s" % [i + 1, _name(_draft[i])], 16, Hud.TEXT, true)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		var drop := _button("Remove", 104)
		drop.pressed.connect(_on_drop.bind(i))
		row.add_child(drop)
		_stops.add_child(row)
	_loop_note.text = _loop_text()
	var last := _draft[-1] if not _draft.is_empty() else -1
	for term: Terminal in sim.terminals.values():
		var id := term.island.id
		var why := _add_problem(last, id)
		var b := _button(_name(id) if why == "" else "%s · %s" % [_name(id), why])
		b.disabled = why != ""
		b.pressed.connect(_on_add.bind(id))
		_adds.add_child(b)
	var problem := sim.stops_problem(ferry, _draft)
	var offsets: Array[float] = []
	if problem == "":
		offsets = ferry.plan_offsets(_draft, _pace)
	_rebuild_timetable(offsets)
	_rebuild_clashes(offsets)
	_rebuild_cost(offsets)
	if problem == "" and _timed and _times.is_empty():
		problem = "Add a sailing, or let her sail as loading allows"
	if problem == "" and Timetable.any_too_soon(_times, offsets[-1]):
		problem = "A sailing in red comes too soon after the one before: a round takes %d min" % ceili(offsets[-1])
	var stops_same := _draft == ferry.stops and ferry.next_stops.is_empty()
	var unchanged := stops_same and _times == ferry.timetable and _pace == ferry.pace
	_problem.text = problem
	_problem.visible = problem != ""
	_apply.disabled = problem != "" or unchanged
	_apply.text = "Apply"
	if problem == "" and not unchanged:
		_apply.text = "Apply · now" if _draft == ferry.stops else "Apply · from her next call at %s" % _name(ferry.next_dock().island.id)
	_fit.call_deferred()


## The sailings, each with its time at every stop and steppers to move it.
## A move or a new sailing that would leave her too little time is disabled.
func _rebuild_timetable(offsets: Array[float]) -> void:
	_clear(_sailings)
	_mode_auto.set_pressed_no_signal(not _timed)
	_mode_timed.set_pressed_no_signal(_timed)
	var have_round := not offsets.is_empty()
	var round_min: float = offsets[-1] if have_round else 0.0
	_sailings_scroll.visible = _timed and have_round
	_add_sailing.visible = _timed and have_round
	if not have_round:
		_round_note.text = "Times follow once her stops make a round."
		return
	var stops_text := "%d min under way, %d min alongside at each stop for a full deck" % [
		roundi(round_min - _draft.size() * ferry.planned_dwell()), roundi(ferry.planned_dwell())]
	if not _timed:
		_round_note.text = "She sails from each stop as soon as she has loaded. A round takes about %d min (%s)." % [ceili(round_min), stops_text]
		return
	_round_note.text = "Times she leaves %s. A round takes %d min (%s), so sailings must be at least that far apart." % [
		_name(_draft[0]), ceili(round_min), stops_text]
	var red := Timetable.too_soon(_times, round_min)
	for k in _times.size():
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 2)
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		var colour: Color = FinancePanel.LOSS if red[k] else Hud.TEXT
		var time: Label = _make_label.call(Timetable.text(_times[k]), 18, colour, true)
		time.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(time)
		for step: int in [-15, -5, 5, 15]:
			var b := _button("%+d" % step, 56)
			b.name = "Step%+d" % step
			b.disabled = not _allowed(_moved(k, step), round_min, red)
			# A tap steps once when it lifts; held, it repeats (_process).
			b.button_down.connect(_on_step_down.bind(k, step))
			row.add_child(b)
		var drop := _button("✕", TAP)
		drop.name = "DropSailing"
		drop.pressed.connect(_on_drop_sailing.bind(k))
		row.add_child(drop)
		box.add_child(row)
		var calls: Array[String] = []
		for i in range(1, _draft.size()):
			calls.append("%s %s" % [_name(_draft[i]), Timetable.text(_times[k] + offsets[i])])
		var sub: Label = _make_label.call(" · ".join(calls), 12, colour if red[k] else Hud.MUTED, false)
		sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(sub)
		_sailings.add_child(box)
	var next := _next_sailing(round_min)
	_add_sailing.disabled = next < 0 or not _allowed(_times + [next], round_min, red)
	_add_sailing.text = "Add a sailing at %s" % Timetable.text(next) if not _add_sailing.disabled else "No room for another sailing"


## The timetable with sailing `k` moved `step` minutes (kept in order), or [] if
## it would leave the day or pass another sailing.
func _moved(k: int, step: int) -> Array[int]:
	var t := _times[k] + step
	if t < 0 or t >= Timetable.DAY:
		return []
	if (k > 0 and t <= _times[k - 1]) or (k + 1 < _times.size() and t >= _times[k + 1]):
		return []
	var out: Array[int] = []
	out.assign(_times)
	out[k] = t
	return out


## Whether `times` is no worse than now: no sailing red that wasn't, and none passing another.
func _allowed(times: Array, round_min: float, red_now: Array[bool]) -> bool:
	if times.is_empty():
		return false
	var proposed: Array[int] = []
	proposed.assign(times)
	var red := Timetable.too_soon(proposed, round_min)
	for i in red.size():
		if red[i] and (i >= red_now.size() or not red_now[i]):
			return false
	return true


## A round after her last sailing, rounded up to 5 minutes; 6:00 AM for the first.
func _next_sailing(round_min: float) -> int:
	if _times.is_empty():
		return 360
	var t := ceili((_times[-1] + round_min) / 5.0) * 5
	return t if t < Timetable.DAY else -1


func _set_timed(on: bool) -> void:
	_timed = on
	if not on:
		_times.clear()
	elif _times.is_empty():
		_times.append(360)
	_rebuild()


func _on_step_down(k: int, step: int) -> void:
	_hold = {"time": _times[k], "step": step, "t": 0.0, "repeating": false}


## Moves the held sailing one step, if that is allowed; false if it isn't.
func _step_held() -> bool:
	var k := _times.find(_hold.time)
	var offsets := ferry.plan_offsets(_draft, _pace)
	if k < 0 or offsets.is_empty():
		return false
	var moved := _moved(k, _hold.step)
	if not _allowed(moved, offsets[-1], Timetable.too_soon(_times, offsets[-1])):
		return false
	_times.assign(moved)
	_hold.time += _hold.step
	_rebuild()
	return true


func _process(delta: float) -> void:
	if _hold.is_empty():
		return
	if not visible:
		_hold.clear()
		return
	_hold.t += delta
	var due: float = REPEAT if _hold.repeating else HOLD_DELAY
	if _hold.t < due:
		return
	_hold.t -= due
	_hold.repeating = true
	if not _step_held():
		_hold.clear()


## Presses and drags reach the editor here before its buttons see them. Touch
## arrives as emulated mouse events (Godot's default), so one path serves both.
func _input(event: InputEvent) -> void:
	if not visible:
		return
	var mb := event as InputEventMouseButton
	if mb and mb.button_index == MOUSE_BUTTON_LEFT:
		if mb.pressed:
			_dragging = false
			var on_list := _sailings_scroll.is_visible_in_tree() and _sailings_scroll.get_global_rect().has_point(mb.position)
			_press_at = mb.position if on_list else Vector2.INF
			_press_scroll = _sailings_scroll.scroll_vertical
		else:
			if not _hold.is_empty() and not _hold.repeating and not _dragging:
				_step_held()
			_hold.clear()
			_press_at = Vector2.INF
		return
	var mm := event as InputEventMouseMotion
	if mm and _press_at != Vector2.INF and mm.button_mask & MOUSE_BUTTON_MASK_LEFT:
		var dy := mm.position.y - _press_at.y
		if not _dragging and absf(dy) > DRAG_SLOP * scale.y:
			_dragging = true
			_hold.clear()
		if _dragging:
			_sailings_scroll.scroll_vertical = _press_scroll - roundi(dy / scale.y)


func _on_drop_sailing(k: int) -> void:
	if _dragging:
		return
	_times.remove_at(k)
	_rebuild()


func _on_add_sailing() -> void:
	var offsets := ferry.plan_offsets(_draft, _pace)
	var t := _next_sailing(offsets[-1])
	if t >= 0:
		_times.append(t)
		_times.sort()
		_scroll_to_end = true
	_rebuild()


func _loop_text() -> String:
	match _draft.size():
		0, 1:
			return "Add stops in the order she calls at them."
		2:
			return "She shuttles back and forth."
	var back := "then back to %s, and round again" % _name(_draft[0])
	if sim.route_between(_draft[-1], _draft[0]) == null:
		back = "but there is no route from %s back to %s" % [_name(_draft[-1]), _name(_draft[0])]
	return "She calls at each in turn, %s." % back


## Why she can't call at `id` straight after `last` ("" if she can).
func _add_problem(last: int, id: int) -> String:
	if last < 0:
		return ""
	return sim.leg_problem(ferry, last, id)


func _on_drop(i: int) -> void:
	_draft.remove_at(i)
	_rebuild()


func _on_add(id: int) -> void:
	_draft.append(id)
	_rebuild()


func _on_apply() -> void:
	var was := ferry.pace
	ferry.set_pace(_pace)
	if sim.reschedule(ferry, _draft.duplicate(), _times.duplicate() if _timed else []):
		hide()
	else:
		ferry.set_pace(was)


## Draws the editor larger on a tall screen, then shortens the sailings list so
## it (Apply included) stays on screen; if it still doesn't fit, draws it a
## little smaller. Runs again when the screen turns.
func _fit() -> void:
	var view := get_viewport_rect().size
	var room := view.y - offset_top - 12.0
	var s := clampf(view.y / 1600.0, 1.0, 1.4)
	var shown := _sailings_scroll.visible
	var want := minf(_sailings.get_combined_minimum_size().y, LIST_MAX) if shown else 0.0
	var list := want
	var need := get_combined_minimum_size().y + want
	if shown:
		need -= _sailings_scroll.custom_minimum_size.y
	if need * s > room:
		list = maxf(want - (need - room / s), TAP + 20.0)
		need -= want - list
	if need * s > room:
		s = maxf(room / need, 0.8)
	_sailings_scroll.custom_minimum_size.y = list
	scale = Vector2(s, s)
	# (it grows back to its minimum height, which is now what it needs)
	offset_left = -220
	offset_right = 220
	offset_bottom = offset_top
	if _scroll_to_end:
		_scroll_to_end = false
		await get_tree().process_frame
		_sailings_scroll.scroll_vertical = int(_sailings_scroll.get_v_scroll_bar().max_value)


func _set_pace(p: int) -> void:
	_pace = p
	_rebuild()


static func _money(v: float) -> String:
	return "$%d" % roundi(v)


## The draft's projected cost a day, and the change from her timetable now.
func _rebuild_cost(offsets: Array[float]) -> void:
	for i in _pace_buttons.size():
		_pace_buttons[i].set_pressed_no_signal(i == _pace)
		_pace_buttons[i].text = "%s%s" % [Ferry.PACES[i][1], " (now)" if i == ferry.pace and _pace != ferry.pace else ""]
	_cost_change.text = ""
	_cost_change.add_theme_color_override("font_color", Hud.MUTED)
	if offsets.is_empty():
		_cost.text = ""
		return
	var all_day := 24.0 * ferry.crew_per_hour()
	if not _timed or _times.is_empty():
		_cost.text = "Crew on all day: %s a day in wages, plus about %s fuel a round at %s." % [
			_money(all_day), _money(ferry.round_fuel(_draft, _pace)), Ferry.PACES[_pace][1].to_lower()]
		return
	var draft := ferry.daily_cost(_draft, _times, _pace)
	var total: float = draft.fuel + draft.crew
	_cost.text = "About %s a day · fuel %s · crew %s (%s h)" % [
		_money(total), _money(draft.fuel), _money(draft.crew), _hours(draft.hours)]
	var now := ferry.planned_daily_cost()
	if now.is_empty():
		_cost_change.text = "Now: as loading allows, crew on all day (%s in wages alone)" % _money(all_day)
		return
	var diff: float = total - (now.fuel + now.crew)
	if absf(diff) < 0.5:
		_cost_change.text = "Same as her timetable now"
		return
	_cost_change.text = "%s%s a day on her timetable now (%s)" % [
		"+" if diff > 0.0 else "−", _money(absf(diff)), _money(now.fuel + now.crew)]
	_cost_change.add_theme_color_override("font_color", FinancePanel.LOSS if diff > 0.0 else Hud.ACCENT)


static func _hours(h: float) -> String:
	var m := roundi(h * 60.0)
	return "%d:%02d" % [m / 60, m % 60]


# --- Slip clashes with the other boats (stage 4, slice 4) ---------------------------

## Warns, under the sailings and on each one it touches, where the draft and
## another boat's timetable want one slip at once. Never blocks Apply.
func _rebuild_clashes(offsets: Array[float]) -> void:
	_clash_note.text = ""
	_clash_note.visible = false
	if offsets.is_empty() or not _timed or _times.is_empty():
		return
	var result := SlipConflicts.check(ferry, _draft, _times, _pace)
	var lines := SlipConflictText.summary(ferry, result)
	_clash_note.text = "\n".join(lines)
	_clash_note.visible = not lines.is_empty()
	var boxes := _sailings.get_children().filter(func(c): return not c.is_queued_for_deletion())
	for k in mini(boxes.size(), _times.size()):
		var clashes := SlipConflicts.on_sailing(result, k)
		if clashes.is_empty():
			continue
		var text: Array[String] = []
		for c in clashes:
			text.append(SlipConflictText.clash_text(sim, c))
		var note: Label = _make_label.call("\n".join(text), 11, SlipConflictText.WARN, false)
		note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		boxes[k].add_child(note)
		# (room in the list for the note; _fit shortens it again if off screen)
		_sailings_scroll.custom_minimum_size.y += 16.0 * text.size()
