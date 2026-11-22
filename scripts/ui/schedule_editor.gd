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


## `make_label(text, size, color, bold)` builds a label in the HUD's fonts.
func setup(s: Simulation, make_label: Callable) -> void:
	sim = s
	_make_label = make_label
	anchor_left = 0.5
	anchor_right = 0.5
	offset_left = -190
	offset_right = 190
	offset_top = 96
	grow_horizontal = Control.GROW_DIRECTION_BOTH
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
	_round_note = make_label.call("", 12, Hud.MUTED, false)
	_round_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_round_note)
	_sailings.add_theme_constant_override("separation", 4)
	_sailings.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_sailings_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_sailings_scroll.add_child(_sailings)
	column.add_child(_sailings_scroll)
	_add_sailing = _button("Add a sailing")
	_add_sailing.pressed.connect(_on_add_sailing)
	column.add_child(_add_sailing)
	column.add_child(paces)
	_cost = make_label.call("", 13, Hud.TEXT, true)
	_cost.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_cost)
	_cost_change = make_label.call("", 12, Hud.MUTED, false)
	_cost_change.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_cost_change)
	column.add_child(HSeparator.new())
	_problem = make_label.call("", 12, FinancePanel.LOSS, false)
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


func open(f: Ferry) -> void:
	ferry = f
	_draft.assign(f.next_stops if not f.next_stops.is_empty() else f.stops)
	_times.assign(f._next_timetable if not f.next_stops.is_empty() else f.timetable)
	_timed = not _times.is_empty()
	_pace = f.pace
	_rebuild()
	show()


func _button(text: String) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(0, 44)
	b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return b


func _name(id: int) -> String:
	return sim.map.islands[id].name.trim_suffix(" Island")


func _rebuild() -> void:
	_title.text = "STOPS · " + ferry.ferry_name.to_upper()
	for c in _stops.get_children() + _adds.get_children():
		c.queue_free()
	for i in _draft.size():
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		var label: Label = _make_label.call("%d.  %s" % [i + 1, _name(_draft[i])], 15, Hud.TEXT, true)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		var drop := Button.new()
		drop.text = "Remove"
		drop.focus_mode = Control.FOCUS_NONE
		drop.custom_minimum_size = Vector2(88, 40)
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
	var offsets: Array[float] = ferry.plan_offsets(_draft, _pace) if problem == "" else []
	_rebuild_timetable(offsets)
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


## The sailings, each with its time at every stop and steppers to move it.
## A move or a new sailing that would leave her too little time is disabled.
func _rebuild_timetable(offsets: Array[float]) -> void:
	for c in _sailings.get_children():
		c.queue_free()
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
		row.add_theme_constant_override("separation", 4)
		var colour: Color = FinancePanel.LOSS if red[k] else Hud.TEXT
		var time: Label = _make_label.call(Timetable.text(_times[k]), 15, colour, true)
		time.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(time)
		for step: int in [-15, -5, 5, 15]:
			var b := Button.new()
			b.text = "%+d" % step
			b.focus_mode = Control.FOCUS_NONE
			b.custom_minimum_size = Vector2(44, 40)
			b.disabled = not _allowed(_moved(k, step), round_min, red)
			b.pressed.connect(_on_step.bind(k, step))
			row.add_child(b)
		var drop := Button.new()
		drop.text = "✕"
		drop.focus_mode = Control.FOCUS_NONE
		drop.custom_minimum_size = Vector2(40, 40)
		drop.pressed.connect(_on_drop_sailing.bind(k))
		row.add_child(drop)
		box.add_child(row)
		var calls: Array[String] = []
		for i in range(1, _draft.size()):
			calls.append("%s %s" % [_name(_draft[i]), Timetable.text(_times[k] + offsets[i])])
		var sub: Label = _make_label.call(" · ".join(calls), 11, colour if red[k] else Hud.MUTED, false)
		sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(sub)
		_sailings.add_child(box)
	_sailings_scroll.custom_minimum_size.y = minf(_times.size() * 64.0, 260.0)
	_fit.call_deferred()
	var next := _next_sailing(round_min)
	_add_sailing.disabled = next < 0 or not _allowed(_times + [next], round_min, red)
	_add_sailing.text = "Add a sailing at %s" % Timetable.text(next) if not _add_sailing.disabled else "No room for another sailing"


## The timetable with sailing `k` moved `step` minutes (kept in order), or [] if
## it would leave the day.
func _moved(k: int, step: int) -> Array[int]:
	var t := _times[k] + step
	if t < 0 or t >= Timetable.DAY:
		return []
	var out: Array[int] = []
	out.assign(_times)
	out[k] = t
	out.sort()
	return out


## Whether `times` is no worse than now: no sailing red that wasn't, and none passing another.
func _allowed(times: Array, round_min: float, red_now: Array[bool]) -> bool:
	if times.is_empty():
		return false
	var sorted: Array[int] = []
	sorted.assign(times)
	sorted.sort()
	var red := Timetable.too_soon(sorted, round_min)
	var reds_now := red_now.count(true)
	if red.count(true) > reds_now:
		return false
	return reds_now > 0 or not red.has(true)


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


func _on_step(k: int, step: int) -> void:
	_times.assign(_moved(k, step))
	_rebuild()


func _on_drop_sailing(k: int) -> void:
	_times.remove_at(k)
	_rebuild()


func _on_add_sailing() -> void:
	var offsets := ferry.plan_offsets(_draft, _pace)
	var t := _next_sailing(offsets[-1])
	if t >= 0:
		_times.append(t)
		_times.sort()
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
	if id == last:
		return "already her last stop"
	var r := sim.route_between(last, id)
	if r == null:
		return "no route from " + _name(last)
	var isl := sim.map.islands[id]
	if not isl.slips[isl.slip_index(r.id)].fits(ferry.fc.size):
		return "slip too small"
	return ""


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


## Shortens the sailings list so the editor (Apply included) stays on screen.
func _fit() -> void:
	var over := offset_top + get_combined_minimum_size().y + 12.0 - get_viewport_rect().size.y
	if over > 0.0:
		_sailings_scroll.custom_minimum_size.y = maxf(_sailings_scroll.custom_minimum_size.y - over, 64.0)
	# (it grows back to its minimum height, which is now what it needs)
	offset_bottom = offset_top


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
	var round_fuel := 0.0
	for i in _draft.size():
		round_fuel += ferry.leg_fuel(sim.route_between(_draft[i], _draft[(i + 1) % _draft.size()]), _pace)
	var all_day := 24.0 * ferry.crew_per_hour()
	if not _timed or _times.is_empty():
		_cost.text = "Crew on all day: %s a day in wages, plus about %s fuel a round at %s." % [
			_money(all_day), _money(round_fuel), Ferry.PACES[_pace][1].to_lower()]
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
