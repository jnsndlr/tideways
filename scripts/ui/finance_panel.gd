class_name FinancePanel
extends PanelContainer
## The company's day: cash on hand, per-route ticket pricing, today's and
## yesterday's ledger lines, and what each boat has cost to run since midnight.
## The HUD retexts it while it is open.

signal ferry_selected(ferry: Ferry)

const LINES := [["fares", "Fares"], ["sales", "Boats sold"], ["fuel", "Fuel"], ["crew", "Crew"], ["purchases", "Purchases"]]
const LOSS := Color(0.95, 0.5, 0.45)
const VEHICLE_STEP := 1.0
const PASSENGER_STEP := 1.0

var _sim: Simulation
var _cash: Label
var _cash_note: Label
var _routes_box := VBoxContainer.new()
var _route_ids: Array[int] = []
var _route_rows := {}  # route_id -> {v_price, v_effect, v_tiers, p_price, p_effect}
var _grid := GridContainer.new()
var _cells := {}  # [line, column] -> Label
var _boats := VBoxContainer.new()
var _displayed: Array[Ferry] = []
var _make_label: Callable


## `make_label(text, size, color, bold)` builds a label in the HUD's fonts.
func setup(make_label: Callable) -> void:
	_make_label = make_label
	position = Vector2(132, 112)
	custom_minimum_size = Vector2(390, 0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	add_child(column)
	column.add_child(make_label.call("FINANCES", 13, Hud.MUTED, true))
	_cash = make_label.call("", 26, Hud.TEXT, true)
	column.add_child(_cash)
	_cash_note = make_label.call("Cash on hand", 11, Hud.MUTED, false)
	column.add_child(_cash_note)
	column.add_child(HSeparator.new())
	column.add_child(make_label.call("ROUTE TICKET PRICING", 11, Hud.MUTED, true))
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.custom_minimum_size.y = 110
	scroll.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_routes_box.add_theme_constant_override("separation", 6)
	_routes_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_routes_box)
	column.add_child(scroll)
	column.add_child(HSeparator.new())
	_grid.columns = 3
	_grid.add_theme_constant_override("h_separation", 22)
	_grid.add_theme_constant_override("v_separation", 3)
	column.add_child(_grid)
	_add_row("head", "", "TODAY", "YESTERDAY", 11, Hud.MUTED)
	for line in LINES:
		_add_row(line[0], line[1], "", "", 13, Hud.TEXT)
	_add_row("net", "Net", "", "", 14, Hud.TEXT)
	_add_row("cars", "Vehicles carried", "", "", 12, Hud.MUTED)
	_add_row("passengers", "Walk-on passengers", "", "", 12, Hud.MUTED)
	column.add_child(HSeparator.new())
	column.add_child(make_label.call("RUNNING COSTS TODAY", 11, Hud.MUTED, true))
	_boats.add_theme_constant_override("separation", 0)
	column.add_child(_boats)
	hide()


func _step_button(glyph: String, on_press: Callable) -> Button:
	var b := Button.new()
	b.text = glyph
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(30, 28)
	b.add_theme_font_size_override("font_size", 14)
	b.pressed.connect(on_press)
	return b


func _adjust_route_vehicle_fare(route_id: int, sign_dir: float) -> void:
	if _sim == null:
		return
	var cur := _sim.ledger.vehicle_fare_for(route_id)
	_sim.ledger.set_route_vehicle_fare(route_id, cur + sign_dir * VEHICLE_STEP)
	refresh(_sim)


func _adjust_route_passenger_fare(route_id: int, sign_dir: float) -> void:
	if _sim == null:
		return
	var cur := _sim.ledger.passenger_fare_for(route_id)
	_sim.ledger.set_route_passenger_fare(route_id, cur + sign_dir * PASSENGER_STEP)
	refresh(_sim)


func _rebuild_routes(routes: Array[MapData.Route]) -> void:
	_route_ids.clear()
	_route_rows.clear()
	for child in _routes_box.get_children():
		_routes_box.remove_child(child)
		child.queue_free()
	if routes.is_empty():
		_routes_box.add_child(_make_label.call("No active routes yet.", 12, Hud.MUTED, false))
		return
	for r in routes:
		_route_ids.append(r.id)
		var card := VBoxContainer.new()
		card.add_theme_constant_override("separation", 3)
		var header := HBoxContainer.new()
		var title: Label = _make_label.call(_sim.route_label(r), 12, Hud.TEXT, true)
		title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var tiers: Label = _make_label.call("", 11, Hud.MUTED, false)
		header.add_child(title)
		header.add_child(tiers)
		card.add_child(header)

		var controls := HBoxContainer.new()
		controls.add_theme_constant_override("separation", 8)
		var v_price: Label = _make_label.call("$18", 13, Hud.TEXT, true)
		v_price.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v_price.custom_minimum_size.x = 34
		var v_effect: Label = _make_label.call("", 10, Hud.MUTED, false)
		var p_price: Label = _make_label.call("$6", 13, Hud.TEXT, true)
		p_price.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		p_price.custom_minimum_size.x = 30
		var p_effect: Label = _make_label.call("", 10, Hud.MUTED, false)

		controls.add_child(_make_label.call("Car", 11, Hud.MUTED, false))
		controls.add_child(_step_button("−", _adjust_route_vehicle_fare.bind(r.id, -1.0)))
		controls.add_child(v_price)
		controls.add_child(_step_button("+", _adjust_route_vehicle_fare.bind(r.id, 1.0)))
		controls.add_child(v_effect)
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		controls.add_child(spacer)
		controls.add_child(_make_label.call("Walk", 11, Hud.MUTED, false))
		controls.add_child(_step_button("−", _adjust_route_passenger_fare.bind(r.id, -1.0)))
		controls.add_child(p_price)
		controls.add_child(_step_button("+", _adjust_route_passenger_fare.bind(r.id, 1.0)))
		controls.add_child(p_effect)
		card.add_child(controls)
		_routes_box.add_child(card)
		_route_rows[r.id] = {
			"v_price": v_price,
			"v_effect": v_effect,
			"v_tiers": tiers,
			"p_price": p_price,
			"p_effect": p_effect,
		}


func _add_row(key: String, name_text: String, a: String, b: String, size: int, color: Color) -> void:
	var is_bold := key == "net"
	var n: Label = _make_label.call(name_text, size, Hud.MUTED if key != "net" else Hud.TEXT, is_bold)
	n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_grid.add_child(n)
	for i in 2:
		var v: Label = _make_label.call(a if i == 0 else b, size, color, is_bold or key == "head")
		v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		v.custom_minimum_size.x = 78
		_grid.add_child(v)
		_cells[[key, i]] = v


func refresh(sim: Simulation) -> void:
	_sim = sim
	var ledger := sim.ledger
	_cash.text = Hud.fmt_money(ledger.cash)
	_cash.add_theme_color_override("font_color", LOSS if ledger.cash < 0.0 else Hud.TEXT)
	_cash_note.text = "Cash on hand · started with %s" % Hud.fmt_money(CompanyLedger.STARTING_CASH)
	var routes := sim.active_routes()
	var ids: Array[int] = []
	for r in routes:
		ids.append(r.id)
	if ids != _route_ids or (_route_ids.is_empty() and _routes_box.get_child_count() == 0):
		_rebuild_routes(routes)
	for rid in _route_ids:
		var row: Dictionary = _route_rows[rid]
		var vf := ledger.vehicle_fare_for(rid)
		var pf := ledger.passenger_fare_for(rid)
		(row["v_price"] as Label).text = "$%d" % roundi(vf)
		(row["v_tiers"] as Label).text = "2× $%d · 3× $%d" % [roundi(vf * 2.0), roundi(vf * 3.0)]
		(row["v_effect"] as Label).text = _short_effect(vf, CompanyLedger.DEFAULT_VEHICLE_FARE)
		(row["p_price"] as Label).text = "$%d" % roundi(pf)
		(row["p_effect"] as Label).text = _short_effect(pf, CompanyLedger.DEFAULT_PASSENGER_FARE)
	var days := [ledger.today, ledger.yesterday]
	for i in 2:
		var day: Dictionary = days[i]
		for line in LINES:
			var v: float = day[line[0]]
			var cell: Label = _cells[[line[0], i]]
			cell.text = Hud.fmt_money(v) if line[0] in CompanyLedger.INCOME else ("-" + Hud.fmt_money(v) if v > 0.0 else "$0")
		var net := CompanyLedger.net(day)
		var net_cell: Label = _cells[["net", i]]
		net_cell.text = ("+" if net > 0.0 else "") + Hud.fmt_money(net)
		net_cell.add_theme_color_override("font_color", LOSS if net < 0.0 else Hud.ACCENT)
	_cells[["cars", 0]].text = Hud.fmt_int(ledger.cars_today)
	_cells[["cars", 1]].text = Hud.fmt_int(ledger.cars_yesterday)
	_cells[["passengers", 0]].text = Hud.fmt_int(ledger.passengers_today)
	_cells[["passengers", 1]].text = Hud.fmt_int(ledger.passengers_yesterday)
	_refresh_boats(sim.ferries)


static func _short_effect(price: float, base_price: float) -> String:
	var pct := roundi((TrafficDemand.price_multiplier(price, base_price) - 1.0) * 100.0)
	return "0%" if pct == 0 else "%+d%%" % pct


func _refresh_boats(ferries: Array[Ferry]) -> void:
	if _displayed != ferries:
		_displayed = ferries.duplicate()
		for row in _boats.get_children():
			_boats.remove_child(row)
			row.queue_free()
		for ferry in ferries:
			var row := Button.new()
			row.focus_mode = Control.FOCUS_NONE
			row.alignment = HORIZONTAL_ALIGNMENT_LEFT
			row.add_theme_font_size_override("font_size", 12)
			row.pressed.connect(ferry_selected.emit.bind(ferry))
			_boats.add_child(row)
	for i in ferries.size():
		var f := ferries[i]
		(_boats.get_child(i) as Button).text = "%s  ·  %s  ·  fuel %s  ·  crew %s" % [
			f.ferry_name, f.pace_name(), Hud.fmt_money(f.fuel_today), Hud.fmt_money(f.crew_today)]
