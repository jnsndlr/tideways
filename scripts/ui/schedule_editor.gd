class_name ScheduleEditor
extends PanelContainer
## Edits one boat's stops (stage 4). The draft lists her stops in turn with a
## button to drop each; below are the company's terminals to add next, each
## greyed out with the reason when she can't go there. Apply hands the stops to
## the simulation, which gives them to her at her next call at one of them.

var sim: Simulation
var ferry: Ferry
var _draft: Array[int] = []
var _make_label: Callable
var _title: Label
var _stops := VBoxContainer.new()
var _loop_note: Label
var _adds := VBoxContainer.new()
var _problem: Label
var _apply := Button.new()


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
	var unchanged := _draft == ferry.stops and ferry.next_stops.is_empty()
	_problem.text = problem
	_problem.visible = problem != ""
	_apply.disabled = problem != "" or unchanged
	_apply.text = "Apply · from her next call at %s" % _name(ferry.next_dock().island.id) if problem == "" and not unchanged else "Apply"


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
	if sim.reschedule(ferry, _draft.duplicate()):
		hide()
