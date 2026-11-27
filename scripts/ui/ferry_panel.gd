class_name FerryPanel
extends PanelContainer
## Tabbed vessel management panel modelled on the Tideways maritime UI mockup:
## header with live stats, Overview / Crew / Schedule / Operations tabs,
## per-route ticket pricing + embedded drag-and-drop schedule editor in Schedule.

signal follow_toggled
signal pace_changed(pace: int)
signal captain_chosen(captain: Captain)
signal service_toggled
signal sell_requested
signal move_requested(town_id: int, slip: int)

enum Tab { OVERVIEW, CREW, SCHEDULE, OPERATIONS }

const BG_OUTER := Color(0.055, 0.165, 0.185, 0.96)
const BG_CARD := Color(0.085, 0.225, 0.250, 0.92)
const BG_PILL := Color(0.115, 0.285, 0.305, 0.95)
const BORDER_CREAM := Color(0.88, 0.86, 0.77, 0.85)
const BORDER_CARD := Color(0.48, 0.68, 0.68, 0.36)
const EMERALD := Color(0.30, 0.63, 0.41, 1.0)
const EMERALD_HOVER := Color(0.36, 0.72, 0.48, 1.0)
const CREAM_TEXT := Color(0.95, 0.94, 0.89)
const SEAFOAM_MUTED := Color(0.66, 0.78, 0.78)
const TAB_NAMES := ["Overview", "Crew", "Schedule", "Operations"]

var sim: Simulation
var ferry: Ferry
var _make_label: Callable
var _tab := Tab.OVERVIEW
var _tab_buttons: Array[Button] = []
var _pages: Array[Control] = []
var _scroll: ScrollContainer

# Header
var _name_label: Label
var _class_label: Label
var _status_label: Label
var _stats := {}  # key -> Label

# Overview tab
var _leg_route: Label
var _leg_meta: Label
var _ov_captain_name: Label
var _ov_captain_strength: Label
var _pace_buttons: Array[Button] = []
var _pace_meta: Label
var _follow_button: Button

# Crew tab
var _crew_why: Label
var _captain_buttons: Array[Button] = []
var _crew_note: Label
var _crew_summary: Label

# Schedule tab
var _route_pricing_box := VBoxContainer.new()
var _priced_route_ids: Array[int] = []
var _priced_rows := {}  # route_id -> {v_price, v_tiers, v_effect, p_price, p_effect}
var _schedule_editor: ScheduleEditor
var _schedule_ferry: Ferry

# Operations tab
var _ops_grid: GridContainer
var _service_button: Button
var _sell_button: Button
# Manual orders (TID-328): any slip a route reaches, picked from a list.
var _move_pick: OptionButton
var _move_note: Label
var _move_button: Button
var _move_key := ""
var _move_targets: Array = []  # [town id, slip] per item of _move_pick

var _style_tab_idle: StyleBoxFlat
var _style_tab_active: StyleBoxFlat
var _style_pill_btn: StyleBoxFlat
var _style_emerald_btn: StyleBoxFlat
var _style_emerald_hover: StyleBoxFlat


func setup(s: Simulation, make_label: Callable) -> void:
	sim = s
	_make_label = make_label
	anchor_left = 1.0
	anchor_right = 1.0
	offset_left = -490
	offset_right = -20
	offset_top = 16
	grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_build_styles()
	add_theme_stylebox_override("panel", _box(BG_OUTER, BORDER_CREAM, 14, 2, 14, 12))

	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(_scroll)

	var root_col := VBoxContainer.new()
	root_col.add_theme_constant_override("separation", 10)
	root_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(root_col)

	root_col.add_child(_build_header())
	root_col.add_child(_build_tabs())
	_pages = [
		_build_overview_tab(),
		_build_crew_tab(),
		_build_schedule_tab(),
		_build_operations_tab(),
	]
	for p in _pages:
		root_col.add_child(p)
	_select_tab(Tab.OVERVIEW)
	hide()


func _build_styles() -> void:
	_style_tab_idle = _box(BG_CARD, BORDER_CARD, 10, 1, 10, 7)
	_style_tab_active = _box(EMERALD, Color(0.68, 0.92, 0.74, 0.85), 10, 1, 10, 7)
	_style_pill_btn = _box(BG_PILL, BORDER_CARD, 8, 1, 10, 7)
	_style_emerald_btn = _box(EMERALD, Color(0.70, 0.92, 0.76, 0.8), 10, 1, 12, 9)
	_style_emerald_hover = _box(EMERALD_HOVER, Color(0.82, 0.96, 0.85, 0.95), 10, 1, 12, 9)


static func _box(bg: Color, border: Color, radius: int, bw: int, hm: int, vm: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_corner_radius_all(radius)
	sb.content_margin_left = hm
	sb.content_margin_right = hm
	sb.content_margin_top = vm
	sb.content_margin_bottom = vm
	return sb


func _card(parent: Control) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _box(BG_CARD, BORDER_CARD, 10, 1, 12, 10))
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	panel.add_child(col)
	return col


func _build_header() -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)

	var left := VBoxContainer.new()
	left.add_theme_constant_override("separation", 4)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name_label = _make_label.call("M/V FERRY", 22, CREAM_TEXT, true)
	_class_label = _make_label.call("Class", 12, SEAFOAM_MUTED, false)
	var status_pill := PanelContainer.new()
	status_pill.add_theme_stylebox_override(
		"panel", _box(Color(0.11, 0.30, 0.28, 0.95), Color(0.45, 0.78, 0.58, 0.65), 12, 1, 10, 4)
	)
	_status_label = _make_label.call("● In service", 11, CREAM_TEXT, true)
	_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status_pill.add_child(_status_label)
	left.add_child(_name_label)
	left.add_child(_class_label)
	left.add_child(status_pill)
	row.add_child(left)

	var sep := VSeparator.new()
	row.add_child(sep)

	var stats_grid := GridContainer.new()
	stats_grid.columns = 2
	stats_grid.add_theme_constant_override("h_separation", 12)
	stats_grid.add_theme_constant_override("v_separation", 2)
	for item in [
		["vehicles", "Deck spaces used"],
		["walkons", "Walk-ons aboard"],
		["speed", "Speed"],
		["trips", "Crossings"],
		["fuel", "Fuel / crossing"],
		["cost", "Cost today"],
	]:
		var k: Label = _make_label.call(item[1], 11, SEAFOAM_MUTED, false)
		var v: Label = _make_label.call("-", 12, CREAM_TEXT, true)
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		v.custom_minimum_size.x = 64
		stats_grid.add_child(k)
		stats_grid.add_child(v)
		_stats[item[0]] = v
	row.add_child(stats_grid)
	return row


func _build_tabs() -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	for i in TAB_NAMES.size():
		var b := Button.new()
		b.text = TAB_NAMES[i]
		b.focus_mode = Control.FOCUS_NONE
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.custom_minimum_size.y = 34
		b.add_theme_font_size_override("font_size", 12)
		b.add_theme_color_override("font_color", CREAM_TEXT)
		b.pressed.connect(_select_tab.bind(i))
		row.add_child(b)
		_tab_buttons.append(b)
	return row


func open_schedule() -> ScheduleEditor:
	_select_tab(Tab.SCHEDULE)
	return _schedule_editor


func _select_tab(t: int) -> void:
	_tab = t as Tab
	for i in _pages.size():
		_pages[i].visible = (i == _tab)
		_tab_buttons[i].add_theme_stylebox_override(
			"normal", _style_tab_active if i == _tab else _style_tab_idle
		)
		_tab_buttons[i].add_theme_stylebox_override(
			"hover", _style_emerald_hover if i == _tab else _style_pill_btn
		)
	if _tab == Tab.SCHEDULE and ferry != null and _schedule_ferry != ferry:
		_schedule_ferry = ferry
		_schedule_editor.open(ferry)


func _build_overview_tab() -> Control:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)

	var top_cards := HBoxContainer.new()
	top_cards.add_theme_constant_override("separation", 8)
	col.add_child(top_cards)

	# Current Leg card
	var leg_col := _card(top_cards)
	leg_col.add_child(_make_label.call("Current Leg", 13, CREAM_TEXT, true))
	var leg_pill := PanelContainer.new()
	leg_pill.add_theme_stylebox_override("panel", _box(BG_PILL, BORDER_CARD, 8, 1, 8, 6))
	_leg_route = _make_label.call("-", 12, CREAM_TEXT, true)
	_leg_route.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_leg_route.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	leg_pill.add_child(_leg_route)
	leg_col.add_child(leg_pill)
	_leg_meta = _make_label.call("-", 11, SEAFOAM_MUTED, false)
	_leg_meta.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	leg_col.add_child(_leg_meta)

	# Captain card
	var cap_col := _card(top_cards)
	cap_col.add_child(_make_label.call("Captain", 13, CREAM_TEXT, true))
	var cap_row := HBoxContainer.new()
	cap_row.add_theme_constant_override("separation", 6)
	_ov_captain_name = _make_label.call("-", 13, CREAM_TEXT, true)
	_ov_captain_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var swap := Button.new()
	swap.text = "Swap"
	swap.focus_mode = Control.FOCUS_NONE
	swap.custom_minimum_size = Vector2(54, 28)
	swap.add_theme_font_size_override("font_size", 11)
	swap.add_theme_stylebox_override("normal", _style_pill_btn)
	swap.pressed.connect(_select_tab.bind(Tab.CREW))
	cap_row.add_child(_ov_captain_name)
	cap_row.add_child(swap)
	cap_col.add_child(cap_row)
	_ov_captain_strength = _make_label.call("", 11, Hud.ACCENT, false)
	_ov_captain_strength.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cap_col.add_child(_ov_captain_strength)

	# Pace card
	var pace_col := _card(col)
	var pace_row := HBoxContainer.new()
	pace_row.add_theme_constant_override("separation", 6)
	pace_row.add_child(_make_label.call("Pace", 13, CREAM_TEXT, true))
	for i in FerryPace.SETTINGS.size():
		var b := Button.new()
		b.text = FerryPace.label(i)
		b.focus_mode = Control.FOCUS_NONE
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.custom_minimum_size.y = 34
		b.add_theme_font_size_override("font_size", 12)
		b.pressed.connect(pace_changed.emit.bind(i))
		pace_row.add_child(b)
		_pace_buttons.append(b)
	pace_col.add_child(pace_row)
	_pace_meta = _make_label.call("-", 11, SEAFOAM_MUTED, false)
	_pace_meta.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pace_col.add_child(_pace_meta)

	# Follow Vessel button
	_follow_button = Button.new()
	_follow_button.text = "Follow Vessel"
	_follow_button.focus_mode = Control.FOCUS_NONE
	_follow_button.custom_minimum_size.y = 40
	_follow_button.add_theme_font_size_override("font_size", 14)
	_follow_button.add_theme_color_override("font_color", CREAM_TEXT)
	_follow_button.add_theme_stylebox_override("normal", _style_emerald_btn)
	_follow_button.add_theme_stylebox_override("hover", _style_emerald_hover)
	_follow_button.pressed.connect(follow_toggled.emit)
	col.add_child(_follow_button)
	return col


func _build_crew_tab() -> Control:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	var cap_card := _card(col)
	cap_card.add_child(_make_label.call("CAPTAIN ROSTER", 11, SEAFOAM_MUTED, true))
	_crew_why = _make_label.call("", 12, CREAM_TEXT, false)
	_crew_why.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cap_card.add_child(_crew_why)
	for c in Captain.roster():
		var b := Button.new()
		b.focus_mode = Control.FOCUS_NONE
		b.toggle_mode = true
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size.y = 52
		b.add_theme_font_size_override("font_size", 12)
		b.add_theme_stylebox_override("normal", _style_pill_btn)
		b.add_theme_stylebox_override("pressed", _style_emerald_btn)
		b.pressed.connect(captain_chosen.emit.bind(c))
		cap_card.add_child(b)
		_captain_buttons.append(b)
	_crew_note = _make_label.call("", 11, SEAFOAM_MUTED, false)
	_crew_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	cap_card.add_child(_crew_note)

	var crew_card := _card(col)
	crew_card.add_child(_make_label.call("DECK & ENGINE CREW", 11, SEAFOAM_MUTED, true))
	_crew_summary = _make_label.call("", 12, CREAM_TEXT, false)
	crew_card.add_child(_crew_summary)
	return col


func _build_schedule_tab() -> Control:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)

	var price_card := _card(col)
	price_card.add_child(_make_label.call("ROUTE TICKET PRICING", 11, SEAFOAM_MUTED, true))
	_route_pricing_box.add_theme_constant_override("separation", 6)
	price_card.add_child(_route_pricing_box)

	var sched_card := _card(col)
	sched_card.add_child(
		_make_label.call("SCHEDULE & STOPS (DRAG ≡ TO REORDER)", 11, SEAFOAM_MUTED, true)
	)
	_schedule_editor = ScheduleEditor.new()
	_schedule_editor.setup(sim, _make_label, true)
	_schedule_editor.applied.connect(
		func():
			if ferry:
				refresh(ferry, false)
	)
	sched_card.add_child(_schedule_editor)
	return col


func _build_operations_tab() -> Control:
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)

	var info_card := _card(col)
	info_card.add_child(_make_label.call("VESSEL OPERATIONS", 11, SEAFOAM_MUTED, true))
	_ops_grid = GridContainer.new()
	_ops_grid.columns = 2
	_ops_grid.add_theme_constant_override("h_separation", 16)
	_ops_grid.add_theme_constant_override("v_separation", 4)
	info_card.add_child(_ops_grid)

	var move_card := _card(col)
	move_card.add_child(_make_label.call("LAY HER UP AT", 11, SEAFOAM_MUTED, true))
	_move_pick = OptionButton.new()
	_move_pick.focus_mode = Control.FOCUS_NONE
	_move_pick.custom_minimum_size.y = 40
	_move_pick.fit_to_longest_item = false
	_move_pick.item_selected.connect(
		func(_i):
			if ferry:
				_refresh_move_note(ferry)
	)
	move_card.add_child(_move_pick)
	_move_note = _make_label.call("", 12, SEAFOAM_MUTED, false)
	_move_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	move_card.add_child(_move_note)
	_move_button = Button.new()
	_move_button.focus_mode = Control.FOCUS_NONE
	_move_button.custom_minimum_size.y = 40
	_move_button.text = "Lay her up there"
	_move_button.add_theme_stylebox_override("normal", _style_pill_btn)
	_move_button.pressed.connect(
		func():
			var i := _move_pick.selected
			if i >= 0 and i < _move_targets.size():
				move_requested.emit(_move_targets[i][0], _move_targets[i][1])
	)
	move_card.add_child(_move_button)

	_service_button = Button.new()
	_service_button.focus_mode = Control.FOCUS_NONE
	_service_button.custom_minimum_size.y = 40
	_service_button.add_theme_stylebox_override("normal", _style_pill_btn)
	_service_button.pressed.connect(service_toggled.emit)
	col.add_child(_service_button)

	_sell_button = Button.new()
	_sell_button.focus_mode = Control.FOCUS_NONE
	_sell_button.custom_minimum_size.y = 40
	_sell_button.add_theme_stylebox_override("normal", _style_pill_btn)
	_sell_button.pressed.connect(sell_requested.emit)
	col.add_child(_sell_button)
	return col


func _step_button(glyph: String, on_press: Callable) -> Button:
	var b := Button.new()
	b.text = glyph
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(30, 28)
	b.add_theme_font_size_override("font_size", 14)
	b.add_theme_stylebox_override("normal", _style_pill_btn)
	b.pressed.connect(on_press)
	return b


func _adjust_route_vehicle(route_id: int, delta_dir: float) -> void:
	sim.ledger.set_route_vehicle_fare(route_id, sim.ledger.vehicle_fare_for(route_id) + delta_dir)
	if ferry:
		_refresh_route_pricing(ferry)


func _adjust_route_passenger(route_id: int, delta_dir: float) -> void:
	sim.ledger.set_route_passenger_fare(
		route_id, sim.ledger.passenger_fare_for(route_id) + delta_dir
	)
	if ferry:
		_refresh_route_pricing(ferry)


func _rebuild_route_pricing(routes: Array[MapData.Route]) -> void:
	_priced_route_ids.clear()
	_priced_rows.clear()
	for child in _route_pricing_box.get_children():
		_route_pricing_box.remove_child(child)
		child.queue_free()
	for r in routes:
		_priced_route_ids.append(r.id)
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 3)
		var hdr := HBoxContainer.new()
		var lbl: Label = _make_label.call(sim.route_label(r), 12, CREAM_TEXT, true)
		lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var tiers: Label = _make_label.call("", 11, SEAFOAM_MUTED, false)
		hdr.add_child(lbl)
		hdr.add_child(tiers)
		box.add_child(hdr)

		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		var vp: Label = _make_label.call("$18", 13, CREAM_TEXT, true)
		vp.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vp.custom_minimum_size.x = 34
		var ve: Label = _make_label.call("", 10, SEAFOAM_MUTED, false)
		var pp: Label = _make_label.call("$6", 13, CREAM_TEXT, true)
		pp.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		pp.custom_minimum_size.x = 30
		var pe: Label = _make_label.call("", 10, SEAFOAM_MUTED, false)

		row.add_child(_make_label.call("Car", 11, SEAFOAM_MUTED, false))
		row.add_child(_step_button("−", _adjust_route_vehicle.bind(r.id, -1.0)))
		row.add_child(vp)
		row.add_child(_step_button("+", _adjust_route_vehicle.bind(r.id, 1.0)))
		row.add_child(ve)
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(spacer)
		row.add_child(_make_label.call("Walk", 11, SEAFOAM_MUTED, false))
		row.add_child(_step_button("−", _adjust_route_passenger.bind(r.id, -1.0)))
		row.add_child(pp)
		row.add_child(_step_button("+", _adjust_route_passenger.bind(r.id, 1.0)))
		row.add_child(pe)
		box.add_child(row)
		_route_pricing_box.add_child(box)
		_priced_rows[r.id] = {
			"v_price": vp, "v_tiers": tiers, "v_effect": ve, "p_price": pp, "p_effect": pe
		}


func _refresh_route_pricing(f: Ferry) -> void:
	var routes := f.schedule_routes()
	var ids: Array[int] = []
	for r in routes:
		ids.append(r.id)
	if ids != _priced_route_ids:
		_rebuild_route_pricing(routes)
	for rid in _priced_route_ids:
		var row: Dictionary = _priced_rows[rid]
		var vf := sim.ledger.vehicle_fare_for(rid)
		var pf := sim.ledger.passenger_fare_for(rid)
		(row["v_price"] as Label).text = "$%d" % roundi(vf)
		(row["v_tiers"] as Label).text = "2× $%d · 3× $%d" % [roundi(vf * 2.0), roundi(vf * 3.0)]
		(row["v_effect"] as Label).text = FinancePanel._short_effect(
			vf, CompanyLedger.DEFAULT_VEHICLE_FARE
		)
		(row["p_price"] as Label).text = "$%d" % roundi(pf)
		(row["p_effect"] as Label).text = FinancePanel._short_effect(
			pf, CompanyLedger.DEFAULT_PASSENGER_FARE
		)


func refresh(
	f: Ferry, is_following: bool, timetable_text := "", clash_text := "", hours_fmt := Callable()
) -> void:
	var changed := ferry != f
	ferry = f
	if changed and _tab == Tab.SCHEDULE:
		_schedule_ferry = f
		_schedule_editor.open(f)
	elif changed:
		_schedule_ferry = null

	# Header
	_name_label.text = "M/V " + f.ferry_name.to_upper()
	_class_label.text = "Class " + f.fc.label
	_status_label.text = "● " + f.status_text()
	(_stats["vehicles"] as Label).text = "%d / %d" % [f.load_count(), f.fc.capacity]
	(_stats["walkons"] as Label).text = "%d / %d" % [f.passenger_count(), f.fc.passenger_capacity]
	(_stats["speed"] as Label).text = "%.1f kn" % Units.knots(f.speed)
	(_stats["trips"] as Label).text = str(f.trips)
	(_stats["fuel"] as Label).text = "~" + Hud.fmt_money(f.crossing_fuel_estimate())
	(_stats["cost"] as Label).text = Hud.fmt_money(f.fuel_today + f.crew_today)

	# Overview
	var km := "%.1f km" % (f.run_length() / 1000.0)
	var mins := roundi(f.crossing_minutes())
	_leg_route.text = sim.route_label(f.route) if f.route else "-"
	_leg_meta.text = "%s crossing  ·  ~%d min" % [km, mins]
	_ov_captain_name.text = f.captain.name
	_ov_captain_strength.text = f.captain.strength
	for i in _pace_buttons.size():
		var active := i == f.pace
		_pace_buttons[i].add_theme_stylebox_override(
			"normal", _style_emerald_btn if active else _style_pill_btn
		)
		_pace_buttons[i].add_theme_stylebox_override(
			"hover", _style_emerald_hover if active else _style_pill_btn
		)
	_pace_meta.text = (
		"%.1f kn  ·  ~%d min crossing  ·  ~%s fuel"
		% [Units.knots(f.cruise_speed()), mins, Hud.fmt_money(f.crossing_fuel_estimate())]
	)
	_follow_button.text = "Stop Following" if is_following else "Follow Vessel"

	# Crew
	var roster := Captain.roster()
	var best := f.best_captain()
	var slowest := 0.0
	for c in roster:
		slowest = maxf(slowest, f.forecast_minutes(c))
	var saved := roundi(slowest - f.forecast_minutes(best))
	if saved < 1:
		_crew_why.text = "A %s crossing: either captain makes it in about the same time." % km
	elif best.sea > 1.0:
		_crew_why.text = (
			"A %s crossing is mostly open water. %s saves about %d min a sailing."
			% [km, best.surname(), saved]
		)
	else:
		_crew_why.text = (
			"A %s crossing is mostly harbour work. %s saves about %d min a sailing."
			% [km, best.surname(), saved]
		)
	for i in roster.size():
		var c := roster[i]
		var b := _captain_buttons[i]
		b.text = (
			"%s%s  ·  ~%d min\n%s"
			% [
				"★ " if c == best and saved >= 1 else "",
				c.name,
				roundi(f.forecast_minutes(c)),
				c.strength
			]
		)
		b.set_pressed_no_signal(c == f.next_captain)
	if f.next_captain != f.captain:
		_crew_note.text = (
			"%s finishes this crossing. %s takes the helm next sailing."
			% [f.captain.surname(), f.next_captain.surname()]
		)
	else:
		_crew_note.text = "Tap a captain to put them in command from the next sailing."
	_crew_summary.text = (
		"%d crew  ·  %s / hr  ·  %s paid today"
		% [f.fc.crew, Hud.fmt_money(f.crew_per_hour()), Hud.fmt_money(f.crew_today)]
	)

	# Schedule tab route pricing
	_refresh_route_pricing(f)

	# Operations
	var rows := [
		["Timetable", timetable_text if timetable_text != "" else "As loading allows"],
		[
			"Last crossing",
			(
				"%d min · %s" % [roundi(f.last_crossing), f.last_crossing_captain.surname()]
				if f.last_crossing >= 0.0
				else "—"
			)
		],
		[
			"Resale value",
			(
				"$%s (%d%% of $%s)"
				% [
					Hud.fmt_int(f.resale_value()),
					roundi(Ferry.RESALE_SHARE * f.condition * 100.0),
					Hud.fmt_int(f.fc.price())
				]
			)
		],
	]
	if clash_text != "":
		rows.insert(1, ["Slip clash", clash_text])
	_set_ops_rows(rows)
	if f.berth == Ferry.Berth.DELIVERING:
		var left_txt: String = (
			hours_fmt.call(f.tow.minutes_left()) if (f.tow and hours_fmt.is_valid()) else ""
		)
		_service_button.text = "Under tow · %s to go" % left_txt if left_txt != "" else "Under tow"
		_service_button.disabled = true
	elif not f.assigned:
		_service_button.text = "Give her stops in Schedule tab to start her"
		_service_button.disabled = true
	elif f.holding:
		_service_button.text = "Return to service"
		_service_button.disabled = false
	elif f.in_service():
		_service_button.text = "Lay up now · at %s" % f.next_dock().town.name
		_service_button.disabled = false
	else:
		_service_button.text = "Return to service"
		_service_button.disabled = f.return_requested and not f.manual
	_sell_button.text = (
		"Sell for $%s" % Hud.fmt_int(f.resale_value())
		if f.can_sell()
		else "Sell · lay her up and empty her first"
	)
	_refresh_move(f)
	_sell_button.disabled = not f.can_sell()


func _set_ops_rows(rows: Array) -> void:
	var need := rows.size() * 2
	while _ops_grid.get_child_count() > need:
		var c := _ops_grid.get_child(_ops_grid.get_child_count() - 1)
		_ops_grid.remove_child(c)
		c.queue_free()
	while _ops_grid.get_child_count() < need:
		var k: Label = _make_label.call("", 12, SEAFOAM_MUTED, false)
		var v: Label = _make_label.call("", 12, CREAM_TEXT, true)
		v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		v.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_ops_grid.add_child(k)
		_ops_grid.add_child(v)
	for i in rows.size():
		(_ops_grid.get_child(i * 2) as Label).text = rows[i][0]
		(_ops_grid.get_child(i * 2 + 1) as Label).text = rows[i][1]


func fit_height(max_height: float) -> void:
	if not visible:
		return
	var inner := _scroll.get_child(0) as Control
	if inner == null:
		return
	var want := inner.get_combined_minimum_size().y
	_scroll.custom_minimum_size.y = minf(want, maxf(240.0, max_height))


## The slips she can be sent to by hand, kept as picked while they stay the same.
func _refresh_move(f: Ferry) -> void:
	var usable := f.assigned and f.berth != Ferry.Berth.DELIVERING
	_move_pick.disabled = not usable
	_move_button.disabled = not usable
	if not usable:
		_move_note.text = "Give her stops first."
		return
	var targets := []
	var names := []
	for id in f.manual_reach():
		var slip := f.best_slip(id)
		if slip >= 0:
			targets.append([id, slip])
			names.append(
				(
					sim.map.towns[id].name
					+ (
						" · here"
						if id == f.here().town.id and f.state != Ferry.State.SAILING
						else ""
					)
				)
			)
	var key := "%d|%s" % [f.get_instance_id(), str(targets)]
	if key != _move_key:
		var keep: Array = (
			_move_targets[_move_pick.selected]
			if _move_pick.selected >= 0 and _move_pick.selected < _move_targets.size()
			else []
		)
		_move_key = key
		_move_targets = targets
		_move_pick.clear()
		for n in names:
			_move_pick.add_item(n)
		var at := targets.find(keep)
		_move_pick.select(at if at >= 0 else (0 if not targets.is_empty() else -1))
	_refresh_move_note(f)


func _refresh_move_note(f: Ferry) -> void:
	var i := _move_pick.selected
	if i < 0 or i >= _move_targets.size():
		_move_note.text = ""
		return
	var short := f.manual_strands(_move_targets[i][0])
	if short == Vector2i.ZERO:
		_move_note.text = (
			"Everyone aboard is bound there. Right-click a dock to send her there, "
			+ "open water to sail her straight to that spot."
		)
	else:
		_move_note.text = (
			"%d vehicles and %d walk-ons get off short: fares refunded, their towns unhappy."
			% [short.x, short.y]
		)
