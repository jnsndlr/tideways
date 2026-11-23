class_name MissionPanel
extends PanelContainer
## The trial mission's goals, ticked off as they are met, beside the HUD sidebar.
## Tap the title to fold it down to one line.

var main: Node
var mission: Mission
var _title: Label
var _day: Label
var _brief: Label
var _rows: VBoxContainer
var _folded := false
var _done := false
var _since := 0.0


func setup(m: Node, mi: Mission) -> void:
	main = m
	mission = mi
	var hud: Hud = main.hud
	add_theme_stylebox_override("panel", hud._panel_style(Hud.PANEL_BG, 10, 14, 10))
	custom_minimum_size.x = 300
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	add_child(v)
	var head := HBoxContainer.new()
	_title = hud._label("MISSION · " + mission.title.to_upper(), 13, Hud.ACCENT, true)
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_title.mouse_filter = Control.MOUSE_FILTER_STOP
	_title.gui_input.connect(func(e):
		if e is InputEventMouseButton and e.pressed and e.button_index == MOUSE_BUTTON_LEFT:
			_folded = not _folded
			_brief.visible = not _folded and mission.brief != ""
			_rows.visible = not _folded)
	head.add_child(_title)
	_day = hud._label("", 12, Hud.MUTED)
	head.add_child(_day)
	v.add_child(head)
	_brief = hud._label(mission.brief, 12, Hud.MUTED)
	_brief.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_brief.custom_minimum_size.x = 272
	_brief.visible = mission.brief != ""
	v.add_child(_brief)
	_rows = VBoxContainer.new()
	_rows.add_theme_constant_override("separation", 2)
	v.add_child(_rows)
	for i in mission.goals.size():
		var row := HBoxContainer.new()
		var tick := hud._label("○", 13, Hud.MUTED)
		tick.custom_minimum_size.x = 18
		row.add_child(tick)
		var name := hud._label("", 13, Hud.TEXT)
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		name.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.add_child(name)
		row.add_child(hud._label("", 12, Hud.MUTED))
		_rows.add_child(row)
	_place()
	hud.sidebar.resized.connect(_place)
	_refresh()


## Just right of the sidebar, level with its top.
func _place() -> void:
	var bar: Control = main.hud.sidebar
	position = Vector2(bar.position.x + bar.size.x + 12, bar.position.y)


func _process(delta: float) -> void:
	_since += delta / maxf(Engine.time_scale, 0.001)
	if _since < 0.5:
		return
	_since = 0.0
	_refresh()


func _refresh() -> void:
	var sim: Simulation = main.sim
	if sim == null:
		return
	var all_done := not mission.goals.is_empty()
	for i in mission.goals.size():
		var goal := mission.goals[i]
		var row: HBoxContainer = _rows.get_child(i)
		var done := mission.goal_met(sim, goal)
		all_done = all_done and done
		(row.get_child(0) as Label).text = "✓" if done else "○"
		(row.get_child(0) as Label).add_theme_color_override("font_color", Hud.ACCENT if done else Hud.MUTED)
		(row.get_child(1) as Label).text = _goal_label(sim, goal)
		(row.get_child(1) as Label).add_theme_color_override("font_color", Hud.MUTED if done else Hud.TEXT)
		(row.get_child(2) as Label).text = "" if done else _goal_progress(sim, goal)
	var day := mission.day_of(sim)
	_day.text = ("Day %d of %d" % [day, mission.days]) if mission.days > 0 else ("Day %d" % day)
	_day.add_theme_color_override("font_color", Color(0.95, 0.55, 0.35) if mission.late(sim) else Hud.MUTED)
	if not _done and all_done:
		_done = true
		main.hud.show_toast("MISSION COMPLETE", "%s: every goal met on day %d%s." % [
			mission.title, day, "" if not mission.late(sim) else " (past the %d-day mark)" % mission.days], 8.0)


func _goal_progress(sim: Simulation, goal: Dictionary) -> String:
	match goal.get("kind", ""):
		"carried":
			return "%d / %d" % [mission.carried(sim), int(goal.get("target", 0))]
		"cash":
			return Hud.fmt_money(sim.available_cash)
	return ""


static func _goal_label(sim: Simulation, goal: Dictionary) -> String:
	var label := str(goal.get("label", ""))
	if label != "":
		return label
	var key := str(goal.get("island", ""))
	match goal.get("kind", ""):
		"carried":
			return "Carry %d vehicles" % int(goal.get("target", 0))
		"cash":
			return "Have %s in hand" % Hud.fmt_money(float(goal.get("target", 0)))
		"terminal":
			return "Open a terminal on %s" % _name(sim, key)
		"serve":
			return "Run a boat to %s" % _name(sim, key)
	return "Unknown goal: %s" % goal.get("kind", "")


static func _name(sim: Simulation, key: String) -> String:
	for town in sim.map.towns:
		if town.key == key:
			return town.name
	for isl in sim.map.islands:
		if isl.key == key:
			return isl.name
	return key
