class_name Hud
extends CanvasLayer
## Screen-space UI, built in code: top stats bar, sidebar, floating island labels,
## selection panel, terminal status bar, fleet list, wildlife sightings, toasts,
## a minimap and the map controls at the screen edge.

const PANEL_BG := Color(0.07, 0.11, 0.13, 0.9)
const TEXT := Color(0.9, 0.94, 0.95)
const MUTED := Color(0.58, 0.66, 0.68)
const ACCENT := Color(0.47, 0.86, 0.6)
const SPEEDS := [0.0, 1.0, 3.0, 8.0]
const WILD := Color(0.98, 0.78, 0.42)

var main: Node
var sim: Simulation
var wildlife: Wildlife
var rig: CameraRig
var map: MapData
var route_overlay: Node3D
## Water zones drawn on the map, if this region has any (the sandbox has none).
var area_overlay: Node3D
var map_controls: MapControls
var selected_island: MapData.Island
var selected_ferry: Ferry
var selected_vessel: Vessel   # anything afloat but a ferry

var root: Control
var font: SystemFont
var bold: SystemFont
var _labels := {}
var _stat := {}
var _speed_buttons: Array[Button] = []
var _speed_index := 1
var _last_running_speed := 1
var _info_panel: PanelContainer
var _info_title: Label
var _info_sub: Label
var _info_grid: GridContainer
## The left-hand menu (COMPANY … SETTINGS); the island editor sits its toggle below it.
var sidebar: PanelContainer
var _lane_button := Button.new()
var _info_button: Button
var _captain_box: VBoxContainer
var _captain_why: Label
var _captain_buttons: Array[Button] = []
var _captain_note: Label
var _crossings_seen := -1
var _terminal_bar: PanelContainer
var _tb := {}
var _fleet_panel: FleetPanel
var _finance_panel: FinancePanel
var _pace_row := HBoxContainer.new()
var _pace_buttons: Array[Button] = []
var _cost_tags: Array = []      # [label, ferry, real seconds shown]
const COST_TAG_SECONDS := 2.6
var _wild_panel: PanelContainer
var _wild_list: VBoxContainer
var _wild_islands: Label
var _wild_empty: Label
var _toast: PanelContainer
var _toast_title: Label
var _toast_body: Label
var _toast_time := 0.0
var _minimap_rect: TextureRect
var _minimap_panel: PanelContainer
var _top_bar: PanelContainer
var _help: Label
var _minimap_overlay: Control
var _refresh := 0.0
var _last_hour := -1.0


func setup(m: Node) -> void:
	main = m
	sim = m.sim
	wildlife = m.sim.wildlife
	rig = m.rig
	map = m.map
	route_overlay = m.route_overlay
	area_overlay = m.get("area_overlay")
	root = Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	_build_theme()
	_build_labels()
	_build_top_bar()
	_build_sidebar()
	_build_info_panel()
	_build_terminal_bar()
	_build_fleet_panel()
	_build_finance_panel()
	_build_wildlife_panel()
	_build_minimap(m.env)
	_build_help()
	_build_toast()
	_build_map_controls()
	rig.ground_clicked.connect(_on_ground_clicked)
	wildlife.visit_started.connect(_on_visit_started)
	wildlife.sighted.connect(_on_sighted)
	wildlife.photographed.connect(_on_photographed)
	sim.running_costs_posted.connect(_on_running_costs)
	set_speed(1)
	var intro: Array = main.intro(_labels.size())
	show_toast(intro[0], intro[1])


# --- Theme & helpers ----------------------------------------------------------------

func _build_theme() -> void:
	var names := PackedStringArray(["Avenir Next", "Helvetica Neue", "Segoe UI", "Arial"])
	font = SystemFont.new()
	font.font_names = names
	font.font_weight = 500
	bold = SystemFont.new()
	bold.font_names = names
	bold.font_weight = 700
	var th := Theme.new()
	th.default_font = font
	th.default_font_size = 14
	th.set_stylebox("panel", "PanelContainer", _panel_style(PANEL_BG, 10, 14, 10))
	th.set_color("font_color", "Label", TEXT)
	var bn := StyleBoxFlat.new()
	bn.bg_color = Color(1, 1, 1, 0.0)
	bn.set_corner_radius_all(6)
	bn.set_content_margin_all(6)
	var bh := bn.duplicate() as StyleBoxFlat
	bh.bg_color = Color(1, 1, 1, 0.08)
	var bp := bn.duplicate() as StyleBoxFlat
	bp.bg_color = Color(ACCENT, 0.22)
	th.set_stylebox("normal", "Button", bn)
	th.set_stylebox("hover", "Button", bh)
	th.set_stylebox("pressed", "Button", bp)
	th.set_stylebox("hover_pressed", "Button", bp)
	th.set_stylebox("focus", "Button", StyleBoxEmpty.new())
	th.set_color("font_color", "Button", TEXT)
	th.set_color("font_hover_color", "Button", Color.WHITE)
	th.set_color("font_pressed_color", "Button", ACCENT)
	th.set_color("font_hover_pressed_color", "Button", ACCENT)
	var sep := StyleBoxLine.new()
	sep.color = Color(1, 1, 1, 0.1)
	sep.vertical = true
	th.set_stylebox("separator", "VSeparator", sep)
	root.theme = th


func _panel_style(bg: Color, radius: int, hm: int, vm: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.content_margin_left = hm
	sb.content_margin_right = hm
	sb.content_margin_top = vm
	sb.content_margin_bottom = vm
	sb.border_color = Color(1, 1, 1, 0.07)
	sb.set_border_width_all(1)
	sb.shadow_color = Color(0, 0, 0, 0.25)
	sb.shadow_size = 6
	return sb


func _label(text: String, size := 14, color := TEXT, is_bold := false) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	if is_bold:
		l.add_theme_font_override("font", bold)
	return l


static func fmt_int(n: int) -> String:
	var s := str(absi(n))
	var out := ""
	while s.length() > 3:
		out = "," + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	return ("-" if n < 0 else "") + s + out


static func fmt_money(v: float) -> String:
	if v < 0.0:
		return "-" + fmt_money(-v)
	if v >= 1e6:
		return "$%.2fM" % (v / 1e6)
	if v >= 1e3:
		return "$%.1fK" % (v / 1e3)
	return "$%d" % int(v)


# --- Top bar, sidebar, help ---------------------------------------------------------

func _build_top_bar() -> void:
	var panel := PanelContainer.new()
	panel.position = Vector2(20, 16)
	root.add_child(panel)
	_top_bar = panel
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 18)
	panel.add_child(row)
	for item in [["cash", "CASH"], ["revenue", "FARES TODAY"], ["vessels", "VESSELS"], ["routes", "ROUTES"],
			["sat", "SATISFACTION"], ["queue", "CARS WAITING"]]:
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", -2)
		var v := _label("-", 22, TEXT, true)
		box.add_child(v)
		box.add_child(_label(item[1], 11, MUTED))
		row.add_child(box)
		row.add_child(VSeparator.new())
		_stat[item[0]] = v
	var clock := VBoxContainer.new()
	clock.add_theme_constant_override("separation", 0)
	var date_row := HBoxContainer.new()
	_stat["date"] = _label("", 13, MUTED)
	_stat["time"] = _label("", 15, TEXT, true)
	date_row.add_child(_stat["date"])
	date_row.add_child(_stat["time"])
	date_row.add_theme_constant_override("separation", 10)
	clock.add_child(date_row)
	var speeds := HBoxContainer.new()
	for i in SPEEDS.size():
		var b := Button.new()
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(40, 26)
		b.tooltip_text = "Pause" if i == 0 else "Speed %d" % i
		b.pressed.connect(set_speed.bind(i))
		# Drawn rather than typed: iPad's system fonts lack the ❚❚ / ▶ glyphs.
		var icon := Control.new()
		icon.set_anchors_preset(Control.PRESET_FULL_RECT)
		icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icon.draw.connect(_draw_speed_icon.bind(icon, b, i))
		b.add_child(icon)
		b.toggled.connect(func(_on: bool) -> void: icon.queue_redraw())
		b.mouse_entered.connect(icon.queue_redraw)
		b.mouse_exited.connect(icon.queue_redraw)
		speeds.add_child(b)
		_speed_buttons.append(b)
	clock.add_child(speeds)
	row.add_child(clock)


func _build_sidebar() -> void:
	sidebar = PanelContainer.new()
	sidebar.position = Vector2(20, 112)
	sidebar.add_theme_stylebox_override("panel", _panel_style(PANEL_BG, 10, 6, 6))
	root.add_child(sidebar)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 2)
	sidebar.add_child(col)
	for item in [["COMPANY", "company"], ["RESEARCH", "research"], ["FLEET", "fleet"],
			["WILDLIFE", "wildlife"], ["FINANCES", "finances"], ["MAP", "map"],
			["SETTINGS", "settings"]]:
		var b := Button.new()
		b.text = item[0]
		b.custom_minimum_size = Vector2(96, 46)
		b.focus_mode = Control.FOCUS_NONE
		b.add_theme_font_override("font", bold)
		b.add_theme_font_size_override("font_size", 12)
		b.pressed.connect(_on_sidebar.bind(item[1]))
		col.add_child(b)


func _build_help() -> void:
	var text := "Drag: pan · Right-drag / Q E: rotate & tilt · Wheel / pinch: zoom · Click: select (or photograph wildlife)\n" + \
		"Space: pause · 1-3: speed · Tab: next ferry · Esc: deselect · G: new map · [ ]: time of day · T: follow clock · V: weather"
	if DisplayServer.is_touchscreen_available() and OS.has_feature("mobile"):
		text = "Drag: pan · Two fingers: pinch to zoom, twist to rotate · Three fingers up/down: tilt · Tap: select"
	var l := _label(text, 12, Color(1, 1, 1, 0.75))
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	l.add_theme_constant_override("shadow_offset_y", 1)
	l.anchor_top = 1.0
	l.anchor_bottom = 1.0
	l.offset_left = 20
	l.offset_top = -52
	l.offset_bottom = -14
	root.add_child(l)
	_help = l


func _on_sidebar(id: String) -> void:
	match id:
		"fleet":
			_fleet_panel.visible = not _fleet_panel.visible
			_wild_panel.visible = false
			_finance_panel.visible = false
			_fleet_panel.refresh(sim.ferries)
		"wildlife":
			_wild_panel.visible = not _wild_panel.visible
			_fleet_panel.visible = false
			_finance_panel.visible = false
			_rebuild_wildlife()
		"finances":
			_finance_panel.visible = not _finance_panel.visible
			_fleet_panel.visible = false
			_wild_panel.visible = false
			_finance_panel.refresh(sim)
		"map":
			rig.focus_on(Vector3.ZERO, 1680.0)
		"settings":
			SettingsPanel.open(get_tree())
		_:
			show_toast(id.to_upper(), "Coming soon: this screen is a placeholder in the preview.")


func _draw_speed_icon(icon: Control, b: Button, i: int) -> void:
	var col := ACCENT if b.button_pressed else (Color.WHITE if b.is_hovered() else TEXT)
	var c := icon.size * 0.5
	var h := 11.0
	if i == 0:
		icon.draw_rect(Rect2(c + Vector2(-5.0, -h * 0.5), Vector2(3.5, h)), col)
		icon.draw_rect(Rect2(c + Vector2(1.5, -h * 0.5), Vector2(3.5, h)), col)
		return
	var w := 8.0
	var step := 7.0
	var x0 := c.x - (w + step * (i - 1)) * 0.5
	for k in i:
		var x := x0 + step * k
		icon.draw_colored_polygon(PackedVector2Array([
			Vector2(x, c.y - h * 0.5), Vector2(x + w, c.y), Vector2(x, c.y + h * 0.5)]), col)


func set_speed(i: int) -> void:
	_speed_index = i
	if i > 0:
		_last_running_speed = i
	Engine.time_scale = SPEEDS[i]
	for j in _speed_buttons.size():
		_speed_buttons[j].button_pressed = j == i


# --- Island labels ------------------------------------------------------------------

func _build_labels() -> void:
	for isl in map.islands:
		if not isl.inhabited or isl.is_mainland:
			continue
		var p := PanelContainer.new()
		p.add_theme_stylebox_override("panel", _panel_style(Color(0.06, 0.09, 0.11, 0.86), 6, 10, 5))
		p.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", -3)
		var title := HBoxContainer.new()
		title.add_theme_constant_override("separation", 6)
		if isl.has_terminal:
			title.add_child(_label("•", 13, ACCENT))
		title.add_child(_label(isl.name.to_upper(), 13, TEXT, true))
		v.add_child(title)
		v.add_child(_label("pop. " + fmt_int(isl.population), 12, MUTED))
		p.add_child(v)
		p.gui_input.connect(_on_label_input.bind(isl))
		root.add_child(p)
		_labels[isl.id] = p


func _on_label_input(event: InputEvent, isl: MapData.Island) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		select_island(isl, true)


func _update_labels() -> void:
	var cam := rig.camera
	var named := map_controls.shows("names")
	for isl in map.islands:
		if not _labels.has(isl.id):
			continue
		var p: PanelContainer = _labels[isl.id]
		var off := not named or cam.is_position_behind(isl.label_pos) or (rig.distance < 135.0 and isl != selected_island)
		p.visible = not off
		if off:
			continue
		p.position = cam.unproject_position(isl.label_pos) - Vector2(p.size.x * 0.5, p.size.y)
		p.modulate = Color(1.15, 1.25, 1.15) if isl == selected_island else Color.WHITE


# --- Selection ----------------------------------------------------------------------

func _on_ground_clicked(screen_pos: Vector2) -> void:
	var cam := rig.camera
	var visit: Wildlife.Visit = main.pick_wildlife(screen_pos, cam)
	if visit:
		if not wildlife.photograph(visit):
			show_toast(visit.species.plural.to_upper(), "Already photographed this %s." % _group_word(visit), 3.0)
		return
	var best: Vessel = null
	var best_d := clampf(9000.0 / rig.distance, 24.0, 220.0)
	for v in sim.marine.vessels:
		var wp := v.global_position + Vector3(0, 9, 0)
		if cam.is_position_behind(wp):
			continue
		var d := cam.unproject_position(wp).distance_to(screen_pos)
		# Small boats only when actually clicked on, so they don't steal ferry clicks.
		if v.spec and v.spec.half_length < 10.5:
			d *= 2.0
		if d < best_d:
			best_d = d
			best = v
	if best is Ferry:
		select_ferry(best)
		return
	if best:
		select_vessel(best)
		return
	var hit: Variant = rig.pick_terrain(screen_pos)
	if hit == null:
		clear_selection()
		return
	var hp: Vector3 = hit
	if hp.y < 0.6:
		clear_selection()
		return
	var nearest: MapData.Island = null
	var nearest_d := 1.4
	for isl in map.islands:
		if not isl.inhabited or isl.is_mainland:
			continue
		var d := Vector2(hp.x, hp.z).distance_to(isl.center) / isl.radius
		if d < nearest_d:
			nearest_d = d
			nearest = isl
	if nearest:
		select_island(nearest, false)
	else:
		clear_selection()


func select_island(isl: MapData.Island, focus: bool) -> void:
	_reset_selection()
	selected_island = isl
	if focus:
		rig.focus_on(isl.town_center, 390.0)
	_refresh_panels()


func select_ferry(f: Ferry) -> void:
	_reset_selection()
	selected_ferry = f
	_crossings_seen = -1
	selected_island = null
	selected_vessel = null
	rig.follow = f
	if rig.target_dist > 540.0:
		rig.target_dist = 330.0
	_refresh_panels()


## Anything afloat but a ferry: shows its panel and follows it, from closer in
## the smaller it is.
func select_vessel(v: Vessel) -> void:
	_reset_selection()
	selected_vessel = v
	rig.follow = v
	var near := clampf(120.0 + v.spec.half_length * 5.0, 165.0, 420.0) if v.spec else 420.0
	if rig.target_dist > near * 1.6:
		rig.target_dist = near
	_refresh_panels()


func clear_selection() -> void:
	_reset_selection()
	_refresh_panels()


func _reset_selection() -> void:
	selected_island = null
	selected_ferry = null
	selected_vessel = null
	rig.follow = null


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match (event as InputEventKey).physical_keycode:
		KEY_SPACE:
			set_speed(0 if _speed_index > 0 else _last_running_speed)
		KEY_1:
			set_speed(1)
		KEY_2:
			set_speed(2)
		KEY_3:
			set_speed(3)
		KEY_ESCAPE:
			clear_selection()
		KEY_TAB:
			if not sim.ferries.is_empty():
				var i := sim.ferries.find(selected_ferry)
				select_ferry(sim.ferries[(i + 1) % sim.ferries.size()])
		KEY_G:
			main.regenerate()
		KEY_M:
			Scenes.go(get_tree(), Scenes.MENU)
		KEY_BRACKETLEFT, KEY_BRACKETRIGHT:
			var step := -1.0 if (event as InputEventKey).physical_keycode == KEY_BRACKETLEFT else 1.0
			main.day_cycle.set_hour(roundf(main.day_cycle.hour()) + step)
			show_toast("TIME OF DAY", "Lighting pinned to %s. Press T to follow the clock." % sim.clock_text(main.day_cycle.hour() * 60.0), 3.0)
		KEY_T:
			main.day_cycle.follow_clock()
			show_toast("TIME OF DAY", "Lighting follows the game clock.", 3.0)
		KEY_V:
			if (event as InputEventKey).shift_pressed:
				sim.weather.resume()
				show_toast("WEATHER", "Weather changes on its own again.", 3.0)
			else:
				sim.weather.set_kind(sim.weather.next_kind(), 10.0)
				show_toast("WEATHER", "Pinned to %s. Shift+V lets it change on its own." % sim.weather.kind, 3.0)


# --- Info panel (top right) ---------------------------------------------------------

func _build_info_panel() -> void:
	_info_panel = PanelContainer.new()
	_info_panel.anchor_left = 1.0
	_info_panel.anchor_right = 1.0
	_info_panel.offset_left = -300
	_info_panel.offset_right = -20
	_info_panel.offset_top = 16
	_info_panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	root.add_child(_info_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	_info_panel.add_child(v)
	_info_title = _label("", 19, TEXT, true)
	_info_sub = _label("", 12, MUTED)
	v.add_child(_info_title)
	v.add_child(_info_sub)
	v.add_child(HSeparator.new())
	_info_grid = GridContainer.new()
	_info_grid.columns = 2
	_info_grid.add_theme_constant_override("h_separation", 24)
	_info_grid.add_theme_constant_override("v_separation", 4)
	v.add_child(_info_grid)
	_build_captain_box(v)
	_info_button = Button.new()
	_info_button.focus_mode = Control.FOCUS_NONE
	_info_button.add_theme_stylebox_override("normal", _panel_style(Color(1, 1, 1, 0.06), 6, 8, 5))
	_info_button.pressed.connect(_on_info_button)
	v.add_child(_info_button)
	_pace_row.add_theme_constant_override("separation", 4)
	for i in Ferry.PACES.size():
		var b := Button.new()
		b.text = Ferry.PACES[i][1]
		b.toggle_mode = true
		b.focus_mode = Control.FOCUS_NONE
		b.custom_minimum_size = Vector2(0, 40)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.add_theme_font_size_override("font_size", 12)
		b.pressed.connect(_set_pace.bind(i))
		_pace_row.add_child(b)
		_pace_buttons.append(b)
	v.add_child(_pace_row)
	_lane_button.custom_minimum_size.y = 48
	_lane_button.pressed.connect(_buy_lane)
	v.add_child(_lane_button)
	_info_panel.visible = false


func _set_pace(i: int) -> void:
	if selected_ferry:
		selected_ferry.set_pace(i)
		_refresh_panels()


## The selected ferry's choice of captain: one button each, showing what the
## crossing would take under them (the simulation's forecast).
func _build_captain_box(parent: VBoxContainer) -> void:
	_captain_box = VBoxContainer.new()
	_captain_box.add_theme_constant_override("separation", 5)
	parent.add_child(_captain_box)
	_captain_box.add_child(HSeparator.new())
	_captain_box.add_child(_label("CAPTAIN", 11, MUTED, true))
	_captain_why = _label("", 12, TEXT)
	_captain_why.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_captain_box.add_child(_captain_why)
	for c in Captain.roster():
		var b := Button.new()
		b.focus_mode = Control.FOCUS_NONE
		b.toggle_mode = true
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size.y = 58
		b.add_theme_font_size_override("font_size", 13)
		b.add_theme_stylebox_override("normal", _panel_style(Color(1, 1, 1, 0.06), 6, 10, 6))
		b.pressed.connect(_on_captain_chosen.bind(c))
		_captain_box.add_child(b)
		_captain_buttons.append(b)
	_captain_note = _label("", 12, MUTED)
	_captain_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_captain_box.add_child(_captain_note)
	_captain_box.add_child(HSeparator.new())


func _on_captain_chosen(c: Captain) -> void:
	if selected_ferry:
		selected_ferry.assign_captain(c)
		_refresh_panels()


func _refresh_captains(f: Ferry) -> void:
	var roster := Captain.roster()
	var best := f.best_captain()
	var slowest := 0.0
	for c in roster:
		slowest = maxf(slowest, f.forecast_minutes(c))
	var saved := roundi(slowest - f.forecast_minutes(best))
	var km := "%.1f km" % (f.run_length() / 1000.0)
	if saved < 1:
		_captain_why.text = "A %s crossing: either captain makes it in about the same time." % km
	elif best.sea > 1.0:
		_captain_why.text = "A %s crossing is mostly open water, so speed at sea counts most. %s saves about %d min a sailing." % [km, best.surname(), saved]
	else:
		_captain_why.text = "A %s crossing is mostly getting in and out of the slips, so docking counts most. %s saves about %d min a sailing." % [km, best.surname(), saved]
	for i in roster.size():
		var c := roster[i]
		var b := _captain_buttons[i]
		b.text = "%s%s  ·  ~%d min\n%s" % ["★ " if c == best and saved >= 1 else "", c.name, roundi(f.forecast_minutes(c)), c.strength]
		b.set_pressed_no_signal(c == f.next_captain)
	if f.next_captain != f.captain:
		_captain_note.text = "%s finishes this crossing. %s takes the helm at the next sailing." % [f.captain.surname(), f.next_captain.surname()]
	else:
		_captain_note.text = "Tap a captain to put them in command from the next sailing."


## What a timed crossing took, and under whom.
func _crossing_text(minutes: float, c: Captain) -> String:
	return "%d min · %s" % [roundi(minutes), c.surname()] if minutes >= 0.0 else "—"


func _buy_lane() -> void:
	if selected_island == null:
		return
	var terminal: Terminal = sim.terminals.get(selected_island.id)
	if terminal and terminal.buy_holding_lane():
		rig.focus_on(terminal.to_global(Vector3(terminal.extension_offset(), Layout.LOT_Y, -40)), 180.0)
		_refresh_panels()


func _on_info_button() -> void:
	if selected_ferry:
		rig.follow = null if rig.follow == selected_ferry else selected_ferry
	elif selected_vessel:
		rig.follow = null if rig.follow == selected_vessel else selected_vessel
	elif selected_island:
		rig.focus_on(selected_island.town_center, 390.0)
	_refresh_panels()


## Refreshed four times a second, so existing labels are reused and only retexted.
func _set_rows(rows: Array) -> void:
	var need := rows.size() * 2
	while _info_grid.get_child_count() > need:
		var c := _info_grid.get_child(_info_grid.get_child_count() - 1)
		_info_grid.remove_child(c)
		c.queue_free()
	while _info_grid.get_child_count() < need:
		var name_l := _label("", 13, MUTED)
		var val := _label("", 13, TEXT, true)
		val.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		_info_grid.add_child(name_l)
		_info_grid.add_child(val)
	for i in rows.size():
		(_info_grid.get_child(i * 2) as Label).text = rows[i][0]
		(_info_grid.get_child(i * 2 + 1) as Label).text = rows[i][1]


func _refresh_panels() -> void:
	# Cargo ships leave the map.
	if selected_vessel and not is_instance_valid(selected_vessel):
		selected_vessel = null
	var offer_lane := false
	_info_panel.visible = selected_island != null or selected_ferry != null or selected_vessel != null
	_terminal_bar.visible = selected_island != null and sim.terminals.has(selected_island.id)
	_help.visible = not _terminal_bar.visible
	_captain_box.visible = selected_ferry != null
	if selected_ferry:
		var f := selected_ferry
		_info_title.text = f.ferry_name.to_upper()
		_info_sub.text = "M/V · %s – %s" % [f.term_a.island.name, f.term_b.island.name]
		_set_rows([
			["Status", f.status_text()],
			["Class", f.fc.label],
			["Vehicles aboard", "%d / %d" % [f.load_count(), f.fc.capacity]],
			["Speed", "%.1f kn" % Units.knots(f.speed)],
			["Captain", f.captain.name],
			["Pace", "%s · %.0f kn" % [f.pace_name(), Units.knots(f.cruise_speed())]],
			["Forecast crossing", "~%d min" % roundi(f.crossing_minutes())],
			["Last crossing", _crossing_text(f.last_crossing, f.last_crossing_captain)],
			["Before that", _crossing_text(f.previous_crossing, f.previous_crossing_captain)],
			["Fuel per crossing", "~" + fmt_money(f.crossing_fuel_estimate())],
			["Crew", "%d · %s / hr" % [f.fc.crew, fmt_money(f.crew_per_hour())]],
			["Running cost today", fmt_money(f.fuel_today + f.crew_today)],
			["Crossings", str(f.trips)],
		])
		for i in _pace_buttons.size():
			_pace_buttons[i].set_pressed_no_signal(i == f.pace)
		_refresh_captains(f)
		if f.trips != _crossings_seen:
			if _crossings_seen >= 0 and f.last_crossing >= 0.0 and f.last_crossing_captain == f.captain:
				var body := "%d min under Captain %s." % [roundi(f.last_crossing), f.captain.surname()]
				if f.previous_crossing >= 0.0 and f.previous_crossing_captain != f.captain:
					body += "\nThe crossing before took %d min under Captain %s." % [roundi(f.previous_crossing), f.previous_crossing_captain.surname()]
				show_toast("%s DOCKED AT %s" % [f.ferry_name.to_upper(), f.here().island.name.to_upper()], body, 8.0)
			_crossings_seen = f.trips
		_info_button.text = "Stop following" if rig.follow == f else "Follow"
	elif selected_vessel:
		var v := selected_vessel
		_info_title.text = v.vessel_name.to_upper()
		var rows := [["Status", v.status_text()], ["Speed", "%.1f kn" % Units.knots(v.speed)]]
		if v is Sailboat:
			_info_sub.text = "%s · out of %s" % [v.type_text(), (v as Sailboat).marina_name((v as Sailboat).marina)]
			rows.append(["Passages", str((v as Sailboat).trips)])
		elif v is MotorYacht:
			var y := v as MotorYacht
			_info_sub.text = "%s · out of %s" % [v.type_text(), y.marina_name(y.marina)]
			rows.append(["Outings", str(y.trips)])
		elif v is FishingBoat:
			var f := v as FishingBoat
			_info_sub.text = "%s · out of %s" % [v.type_text(), f.quay_name()]
			rows.append(["Hold", "%d%% full" % roundi(f.fish_hold * 100.0)])
			rows.append(["Trips", str(f.trips)])
		elif v is PilotBoat:
			var pb := v as PilotBoat
			_info_sub.text = "%s · out of %s" % [v.type_text(), pb.wharf_name()]
			rows.append(["Ships met", str(pb.jobs)])
		elif v is Tug:
			var tg := v as Tug
			_info_sub.text = "%s · out of %s" % [v.type_text(), tg.wharf_name()]
			rows.append(["Escorts", str(tg.jobs)])
		else:
			_info_sub.text = "%s · transiting" % v.type_text()
			rows.append(["Distance to go", "%.1f km" % (v.path_left() / 1000.0)])
			if v is CargoShip:
				var cs := v as CargoShip
				rows.append(["Pilot", cs.pilot_text()])
				if cs.needs_escort():
					var esc := cs.escort.vessel_name if is_instance_valid(cs.escort) else ("Escorted" if cs.escorted else "Awaiting a tug")
					rows.append(["Escort", esc])
		_set_rows(rows)
		_info_button.text = "Stop following" if rig.follow == v else "Follow"
	elif selected_island:
		var isl := selected_island
		var term: Terminal = sim.terminals.get(isl.id)
		var sat := term.satisfaction() if term else 70.0
		_info_title.text = isl.name.to_upper()
		var served := isl.slips.filter(MapData.is_route).size()
		_info_sub.text = ("No ferry service yet" if not term else
			"Ferry terminal · idle slip" if served == 0 else
			"Ferry terminal · %d route%s" % [served, "" if served == 1 else "s"])
		var rows := [
			["Population", fmt_int(isl.population)],
			["Satisfaction", "%d%%" % roundi(sat)],
			["Growth", "%+.1f%% / yr" % (isl.growth + (sat - 70.0) * 0.05)],
			["Demand", sim.demand_label(isl) if term else "-"],
		]
		rows.append(["Wildlife draw", _draw_text(isl)])
		rows.append(["Wildlife appeal", _appeal_text(wildlife.appeal(isl))])
		if term:
			rows.append(["Vehicles waiting", str(term.total_queued())])
			rows.append(["Holding capacity", "%d car spaces" % term.capacity()])
			if isl.lane_extension_price > 0:
				var route: MapData.Route = sim.map.routes[isl.slips[0]]
				var destination := sim.map.islands[route.b if route.a == isl.id else route.a].name
				rows.append(["Extra lane to", destination])
				if term.extra_lane != null:
					rows.append(["In extra lane", "%d waiting · %d spaces inbound" % [term.extra_lane.queue.size(), term.extra_lane.enroute]])
				elif term.build_remaining > 0.0:
					var count := term.staging_lanes.size()
					var phase: String = {
						Terminal.WorkStage.DRAINING: "Clearing the lanes",
						Terminal.WorkStage.ARRIVING: "Crew arriving",
						Terminal.WorkStage.PAVING: "Paving the lane",
						Terminal.WorkStage.LEAVING: "Crew leaving",
					}[term.work_stage]
					rows.append(["Construction", phase])
					rows.append(["Staging closure", _staging_loss(count, term.slots_per_lane)])
					if term.work_stage != Terminal.WorkStage.DRAINING:
						rows.append(["Lane opens in", "%d game min" % ceili(term.build_remaining)])
				elif not term.can_stage_construction():
					rows.append(["Expansion", "Keep one lane open for service"])
				else:
					rows.append(["Available cash", fmt_money(sim.available_cash)])
					rows.append(["While building", _staging_loss(isl.construction_staging_lanes, term.slots_per_lane) + " closed"])
					rows.append(["After opening", "%d car spaces" % (term.capacity() + term.slots_per_lane)])
					rows.append(["Build time", "%d min after lanes clear" % int(Terminal.BUILD_MINUTES)])
					_lane_button.text = "Buy lane (+%d spaces) · $%d" % [term.slots_per_lane, isl.lane_extension_price]
					_lane_button.disabled = sim.available_cash < isl.lane_extension_price
					offer_lane = true
			if term.has_service():
				rows.append(["Avg. wait", "%d min" % roundi(term.avg_wait)])
			rows.append(["Carried today", fmt_int(term.served_today)])
		_set_rows(rows)
		_info_button.text = "Center view"
		if term:
			_update_terminal_bar(term)
	_lane_button.visible = offer_lane
	_pace_row.visible = selected_ferry != null


func _staging_loss(count: int, slots: int) -> String:
	return "%d lane%s · %d spaces" % [count, "" if count == 1 else "s", count * slots]


# --- Terminal bar (bottom) ----------------------------------------------------------

func _build_terminal_bar() -> void:
	_terminal_bar = PanelContainer.new()
	_terminal_bar.anchor_left = 0.5
	_terminal_bar.anchor_right = 0.5
	_terminal_bar.anchor_top = 1.0
	_terminal_bar.anchor_bottom = 1.0
	_terminal_bar.offset_left = -430
	_terminal_bar.offset_right = 430
	_terminal_bar.offset_top = -100
	_terminal_bar.offset_bottom = -18
	_terminal_bar.grow_vertical = Control.GROW_DIRECTION_BEGIN
	root.add_child(_terminal_bar)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	_terminal_bar.add_child(row)
	for key in ["terminal", "departure", "weather", "wind", "tide"]:
		var v := VBoxContainer.new()
		v.add_theme_constant_override("separation", 0)
		var a := _label("", 11, MUTED, true)
		var b := _label("", 17, TEXT, true)
		var c := _label("", 13, MUTED)
		v.add_child(a)
		v.add_child(b)
		v.add_child(c)
		if key == "terminal":
			v.custom_minimum_size.x = 210
		row.add_child(v)
		if key != "tide":
			row.add_child(VSeparator.new())
		_tb[key] = [a, b, c]
	_terminal_bar.visible = false


func _tb_set(key: String, a: String, b: String, c: String) -> void:
	var l: Array = _tb[key]
	l[0].text = a
	l[1].text = b
	l[2].text = c


func _update_terminal_bar(term: Terminal) -> void:
	_tb_set("terminal", term.island.name.to_upper() + " TERMINAL",
		"Queue: %d vehicles" % term.total_queued(),
		"Wait: %d min" % roundi(term.avg_wait) if term.has_service() else "No scheduled service")
	var nd := term.next_departure()
	var f: Ferry = nd[1]
	if f:
		var mins: float = nd[0]
		var when := "Boarding now" if f.state == Ferry.State.LOADING and f.here() == term else sim.clock_text(sim.minutes + mins)
		var dest := f.term_b if f.term_a == term else f.term_a
		_tb_set("departure", "NEXT DEPARTURE", when, "%s to %s" % [f.ferry_name, dest.island.name])
	else:
		_tb_set("departure", "NEXT DEPARTURE", "-", "")
	_tb_set("weather", "WEATHER", sim.weather.label(), "%d°C" % sim.temperature())
	_tb_set("wind", "WIND", "%s %d km/h" % [sim.wind_dir, sim.wind_speed], "")
	var tide := sim.tide()
	_tb_set("tide", "TIDE", "Rising" if tide.y > 0.0 else "Falling", "%.1f m" % tide.x)


# --- Fleet list ---------------------------------------------------------------------

func _build_finance_panel() -> void:
	_finance_panel = FinancePanel.new()
	root.add_child(_finance_panel)
	_finance_panel.setup(_label)
	_finance_panel.ferry_selected.connect(select_ferry)


func _build_fleet_panel() -> void:
	_fleet_panel = FleetPanel.new()
	root.add_child(_fleet_panel)
	_fleet_panel.setup(_label("FLEET", 13, MUTED, true))
	_fleet_panel.ferry_selected.connect(select_ferry)


# --- Floating running costs ----------------------------------------------------------

## A trip's fuel and wages, floated up off the boat as she docks (a Settings option).
func _on_running_costs(ferry: Ferry, fuel: float, crew: float, trip: bool) -> void:
	if not trip or not GameSettings.flag("floating_costs"):
		return
	var tag := _label("-%s fuel  ·  -%s crew" % [fmt_money(fuel), fmt_money(crew)], 16, FinancePanel.LOSS, true)
	tag.add_theme_color_override("font_outline_color", Color(0.05, 0.07, 0.08, 0.9))
	tag.add_theme_constant_override("outline_size", 6)
	tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(tag)
	_cost_tags.append([tag, ferry, 0.0])


func _float_cost_tags(real_dt: float) -> void:
	var cam := rig.camera
	for i in range(_cost_tags.size() - 1, -1, -1):
		var entry: Array = _cost_tags[i]
		var tag: Label = entry[0]
		var ferry: Ferry = entry[1]
		entry[2] += real_dt
		var age: float = entry[2]
		if age > COST_TAG_SECONDS or not is_instance_valid(ferry):
			tag.queue_free()
			_cost_tags.remove_at(i)
			continue
		var above := ferry.global_position + Vector3(0.0, 24.0, 0.0)
		tag.visible = not cam.is_position_behind(above)
		tag.position = cam.unproject_position(above) - Vector2(tag.size.x * 0.5, tag.size.y + age * 22.0)
		tag.modulate.a = clampf((COST_TAG_SECONDS - age) / 0.8, 0.0, 1.0)


# --- Wildlife ----------------------------------------------------------------------

func _build_wildlife_panel() -> void:
	_wild_panel = PanelContainer.new()
	_wild_panel.position = Vector2(132, 112)
	_wild_panel.custom_minimum_size = Vector2(340, 0)
	root.add_child(_wild_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	_wild_panel.add_child(v)
	v.add_child(_label("RECENT SIGHTINGS", 13, MUTED, true))
	_wild_empty = _label("Nothing yet. Pods turn up once a day.", 13, MUTED)
	v.add_child(_wild_empty)
	_wild_list = VBoxContainer.new()
	_wild_list.add_theme_constant_override("separation", 2)
	v.add_child(_wild_list)
	v.add_child(HSeparator.new())
	v.add_child(_label("WILDLIFE DRAW", 13, MUTED, true))
	_wild_islands = _label("", 13)
	v.add_child(_wild_islands)
	_wild_panel.visible = false


## Newest first: live visits marked, who saw them, and whether they were photographed.
func _rebuild_wildlife() -> void:
	var shown: Array[Wildlife.Visit] = []
	for i in range(wildlife.visits.size() - 1, -1, -1):
		shown.append(wildlife.visits[i])
		if shown.size() >= 6:
			break
	_wild_empty.visible = shown.is_empty()
	if _wild_list.get_child_count() != shown.size():
		for c in _wild_list.get_children():
			_wild_list.remove_child(c)
			c.queue_free()
		for i in shown.size():
			var b := Button.new()
			b.focus_mode = Control.FOCUS_NONE
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.add_theme_font_size_override("font_size", 13)
			b.pressed.connect(_on_wild_row.bind(i))
			_wild_list.add_child(b)
	for i in shown.size():
		var v := shown[i]
		var b := _wild_list.get_child(i) as Button
		var when := "Day %d, %s" % [v.day, sim.clock_text(v.start)]
		var seen := "not seen yet" if v.active() else "nobody saw them"
		if not v.credited.is_empty():
			var names := PackedStringArray()
			for isl in v.credited:
				names.append(isl.name)
			seen = "seen from " + ", ".join(names)
		b.text = "%s%s · %s%s\n%s · %s" % ["• " if v.active() else "", v.title(), v.target.name,
			"  · photo" if v.photographed else "", when, seen]
		b.add_theme_color_override("font_color", WILD if v.active() else TEXT)
		b.set_meta("visit", v)
	var lines := PackedStringArray()
	var ranked: Array = []
	for isl in map.islands:
		if wildlife.reputation(isl) > 0.05:
			ranked.append(isl)
	ranked.sort_custom(func(a, b): return wildlife.reputation(a) > wildlife.reputation(b))
	for isl: MapData.Island in ranked.slice(0, 5):
		lines.append("%s   %s" % [isl.name, _draw_text(isl)])
	_wild_islands.text = "\n".join(lines) if not lines.is_empty() else "No island has had a sighting this season."


func _on_wild_row(i: int) -> void:
	var b := _wild_list.get_child(i)
	if not b.has_meta("visit"):
		return
	var v: Wildlife.Visit = b.get_meta("visit")
	if v.active():
		follow_visit(v)
	else:
		select_island(v.target, true)


## Points the camera at a visit's group and keeps it there.
func follow_visit(v: Wildlife.Visit) -> void:
	clear_selection()
	if is_instance_valid(v.marker):
		rig.target_pos = Vector3(v.pos.x, 0.0, v.pos.z)
		rig.follow = v.marker
		if rig.target_dist > 180.0:
			rig.target_dist = 120.0


func _group_word(v: Wildlife.Visit) -> String:
	match v.species.behavior:
		Wildlife.Behavior.HAUL_OUT:
			return "group"
		Wildlife.Behavior.PERCH:
			return "pair" if v.members.size() == 2 else "bird"
	return "pod"


func _draw_text(isl: MapData.Island) -> String:
	var r := wildlife.standing(isl)
	if r == null or r.value < 0.05:
		return "-"
	return "+%.1f · %s" % [r.value, r.last_species]


func _appeal_text(a: float) -> String:
	if a >= 2.0:
		return "Hotspot"
	if a >= 0.7:
		return "Fair"
	return "Rare"


## Only the rarer visitors (Species.callout) are announced; the rest just show up in
## the sightings list.
func _on_visit_started(v: Wildlife.Visit) -> void:
	if _wild_panel.visible:
		_rebuild_wildlife()
	if not v.species.callout:
		return
	var what := "A %s of %d is heading for %s." % [_group_word(v), v.members.size(), v.target.name]
	if v.members.size() == 1:
		what = "One is heading for %s." % v.target.name
	if v.site:
		var where := "the marina" if v.site.kind == MapData.HaulOut.Kind.DOCK else "the " + v.site.kind_name()
		what = "A %s of %d is coming in to haul out on %s at %s." % [_group_word(v), v.members.size(), where, v.target.name]
	show_toast("%s REPORTED" % v.species.plural.to_upper(),
		what + " Seen from a dock or a ferry in daylight, it draws tourists. Click one for a photo bonus.", 8.0)


func _on_sighted(v: Wildlife.Visit, isl: MapData.Island, seen_from: String) -> void:
	if not v.species.callout:
		return
	show_toast("%s SIGHTING · %s" % [v.species.name.to_upper(), isl.name.to_upper()],
		"Spotted from %s. Wildlife draw at %s is now +%.1f." % [seen_from, isl.name, wildlife.reputation(isl)])


func _on_photographed(v: Wildlife.Visit) -> void:
	var where := "every island that sees this %s" % _group_word(v)
	if not v.credited.is_empty():
		var names := PackedStringArray()
		for isl in v.credited:
			names.append(isl.name)
		where = ", ".join(names) + " and any island that sees it later"
	show_toast("PHOTOGRAPHED!", "+%d%% wildlife draw from this %s for %s." % [
		roundi(Wildlife.PHOTO_BONUS * 100.0), _group_word(v), where])


# --- Toast --------------------------------------------------------------------------

func _build_toast() -> void:
	_toast = PanelContainer.new()
	_toast.anchor_left = 1.0
	_toast.anchor_right = 1.0
	_toast.anchor_top = 1.0
	_toast.anchor_bottom = 1.0
	_toast.offset_left = -360
	_toast.offset_right = -20
	_toast.offset_bottom = -262
	_toast.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_toast.grow_vertical = Control.GROW_DIRECTION_BEGIN
	root.add_child(_toast)
	var v := VBoxContainer.new()
	_toast.add_child(v)
	_toast_title = _label("", 15, TEXT, true)
	_toast_body = _label("", 13, MUTED)
	_toast_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_toast_body.custom_minimum_size.x = 300
	v.add_child(_toast_title)
	v.add_child(_toast_body)
	_toast.visible = false


func show_toast(title: String, body: String, seconds := 6.0) -> void:
	_toast_title.text = title
	_toast_body.text = body
	_toast.visible = true
	_toast_time = seconds


# --- Map controls (screen edge) ----------------------------------------------------

func _build_map_controls() -> void:
	var layers := []
	if area_overlay:
		layers.append(["areas", "Areas", "Water areas"])
	layers.append(["routes", "Routes", "Ferry route lines"])
	layers.append(["names", "Names", "Town names"])
	map_controls = MapControls.new()
	map_controls.add_theme_stylebox_override("panel", _panel_style(PANEL_BG, 10, 4, 4))
	root.add_child(map_controls)
	map_controls.setup(layers, sim, main.day_cycle, font, bold)
	map_controls.weather_toggled.connect(_on_weather_toggled)


## Hides the cloud deck and its shadows. The weather itself carries on.
func _on_weather_toggled(shown: bool) -> void:
	main.clouds.set_shown(shown)
	show_toast("WEATHER", "Map weather shown." if shown else "Map weather hidden. Conditions keep changing.", 2.5)


## Keeps the group inside the screen's safe area and clear of whichever panels are
## open, so it stays reachable beside the inspector.
func _place_map_controls() -> void:
	var obstacles: Array[Rect2] = []
	for panel: Control in [_top_bar, sidebar, _info_panel, _fleet_panel, _wild_panel, _terminal_bar, _minimap_panel]:
		if panel.visible:
			obstacles.append(panel.get_rect())
	map_controls.place(_usable_rect(), obstacles)


## The canvas inside the HUD's usual margins and, on a device, the display's safe area.
func _usable_rect() -> Rect2:
	var usable := Rect2(Vector2.ZERO, root.size).grow_individual(-20, -16, -20, -16)
	if not OS.has_feature("mobile"):
		return usable
	var window := Vector2(DisplayServer.window_get_size())
	var safe := Rect2(DisplayServer.get_display_safe_area())
	if window.x <= 0.0 or window.y <= 0.0 or not safe.has_area():
		return usable
	var to_canvas := root.size / window
	var inset := Rect2(safe.position * to_canvas, safe.size * to_canvas).intersection(usable)
	return inset if inset.size.x > 200.0 and inset.size.y > 200.0 else usable


# --- Minimap ------------------------------------------------------------------------

func _build_minimap(env: Environment) -> void:
	var vp := SubViewport.new()
	vp.size = Vector2i(440, 440)
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	add_child(vp)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = map.half_size * 2.0
	cam.near = 3.0
	cam.far = 3000.0
	cam.position = Vector3(0, 1200, 0)
	cam.rotation_degrees = Vector3(-90, 0, 0)
	cam.cull_mask = 1 # skip the visible cloud layer
	var mini_env := env.duplicate() as Environment
	mini_env.fog_enabled = false
	mini_env.ssao_enabled = false
	mini_env.volumetric_fog_enabled = false
	# Rendered once, so give it flat daylight regardless of the time of day it starts at.
	mini_env.ambient_light_color = Color(0.85, 0.9, 1.0)
	mini_env.ambient_light_energy = 1.0
	mini_env.tonemap_exposure = 1.0
	cam.environment = mini_env
	vp.add_child(cam)

	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _panel_style(PANEL_BG, 10, 6, 6))
	panel.anchor_left = 1.0
	panel.anchor_right = 1.0
	panel.anchor_top = 1.0
	panel.anchor_bottom = 1.0
	panel.offset_left = -242
	panel.offset_top = -242
	panel.offset_right = -20
	panel.offset_bottom = -20
	root.add_child(panel)
	_minimap_panel = panel
	_minimap_rect = TextureRect.new()
	_minimap_rect.texture = vp.get_texture()
	_minimap_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_minimap_rect.stretch_mode = TextureRect.STRETCH_SCALE
	_minimap_rect.custom_minimum_size = Vector2(210, 210)
	_minimap_rect.mouse_filter = Control.MOUSE_FILTER_STOP
	_minimap_rect.gui_input.connect(_on_minimap_input)
	panel.add_child(_minimap_rect)
	_minimap_overlay = Control.new()
	_minimap_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_minimap_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_minimap_overlay.draw.connect(_draw_minimap)
	_minimap_rect.add_child(_minimap_overlay)


func _to_minimap(p: Vector3) -> Vector2:
	var hs := map.half_size
	var sz := _minimap_overlay.size
	return Vector2((p.x + hs) / (2.0 * hs) * sz.x, (p.z + hs) / (2.0 * hs) * sz.y)


func _draw_minimap() -> void:
	var o := _minimap_overlay
	var vr := get_viewport().get_visible_rect().size
	var pts := PackedVector2Array()
	for c: Vector2 in [Vector2.ZERO, Vector2(vr.x, 0), vr, Vector2(0, vr.y)]:
		var g: Variant = rig.ground_at(c)
		if g == null:
			pts.clear()
			break
		pts.append(_to_minimap(g).clamp(Vector2.ZERO, o.size))
	if pts.size() == 4:
		pts.append(pts[0])
		o.draw_polyline(pts, Color(1, 1, 1, 0.9), 1.5)
	o.draw_circle(_to_minimap(rig.position), 2.5, Color(1, 1, 1, 0.9))
	for v in sim.marine.vessels:
		if v is Ferry:
			continue
		# Small craft lying at a berth or at anchor are left off.
		var small := v.spec != null and v.spec.half_length < 10.5
		if small and not v.wants_to_move() and v != selected_vessel:
			continue
		var at := _to_minimap(v.global_position)
		var vc := ACCENT if v == selected_vessel else (Color(0.85, 0.9, 0.95, 0.8) if small else Color(0.95, 0.6, 0.35))
		var r := 1.5 if small else (2.2 if v.spec and v.spec.half_length < 36.0 else 3.0)
		o.draw_circle(at, r, vc)
	for f in sim.ferries:
		var col := ACCENT if f == selected_ferry else Color(1, 1, 1)
		o.draw_circle(_to_minimap(f.global_position), 3.5, Color(0, 0, 0, 0.5))
		o.draw_circle(_to_minimap(f.global_position), 2.5, col)
	for v in wildlife.active_visits():
		var at := _to_minimap(v.pos)
		o.draw_circle(at, 4.0, Color(0.05, 0.06, 0.07, 0.9))
		o.draw_arc(at, 5.5, 0, TAU, 16, WILD, 1.5)
	if selected_island:
		o.draw_arc(_to_minimap(selected_island.town_center), 9.0, 0, TAU, 24, ACCENT, 1.5)


func _on_minimap_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var p: Vector2 = event.position / _minimap_rect.size
		var hs := map.half_size
		rig.focus_on(Vector3(p.x * 2.0 * hs - hs, 0, p.y * 2.0 * hs - hs))


# --- Per frame ----------------------------------------------------------------------

func _process(delta: float) -> void:
	_update_labels()
	_minimap_overlay.queue_redraw()
	if route_overlay:
		route_overlay.visible = map_controls.shows("routes")
	if area_overlay:
		area_overlay.visible = map_controls.shows("areas")
	_place_map_controls()

	var real_dt := delta / maxf(Engine.time_scale, 0.001) if Engine.time_scale > 0.0 else 1.0 / 60.0
	if _toast.visible:
		_toast_time -= real_dt
		if _toast_time <= 0.0:
			_toast.visible = false

	_float_cost_tags(real_dt)

	var h := sim.hour()
	if _last_hour >= 0.0:
		if _last_hour < 6.5 and h >= 6.5:
			show_toast("MORNING RUSH", "Peak demand on most routes runs from 6:30 to 8:00 AM.")
		elif _last_hour < 16.5 and h >= 16.5:
			show_toast("EVENING COMMUTE", "Expect long queues heading home until about 6:30 PM.")
	_last_hour = h

	_refresh -= real_dt
	if _refresh > 0.0:
		return
	_refresh = 0.25
	_stat["cash"].text = fmt_money(sim.available_cash)
	_stat["cash"].add_theme_color_override("font_color", FinancePanel.LOSS if sim.available_cash < 0.0 else TEXT)
	_stat["revenue"].text = fmt_money(sim.revenue_today)
	_stat["vessels"].text = str(sim.ferries.size())
	_stat["routes"].text = str(map.routes.size())
	_stat["sat"].text = "%d%%" % roundi(sim.satisfaction())
	_stat["queue"].text = fmt_int(sim.total_queued())
	_stat["date"].text = sim.date_text()
	_stat["time"].text = sim.clock_text()
	_refresh_panels()
	if _fleet_panel.visible:
		_fleet_panel.refresh(sim.ferries)
	if _wild_panel.visible:
		_rebuild_wildlife()
	if _finance_panel.visible:
		_finance_panel.refresh(sim)
