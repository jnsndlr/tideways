class_name FinancePanel
extends PanelContainer
## The company's day: cash on hand, today's and yesterday's ledger lines, and what
## each boat has cost to run since midnight. The HUD retexts it while it is open.

signal ferry_selected(ferry: Ferry)

const LINES := [["fares", "Fares"], ["sales", "Boats sold"], ["fuel", "Fuel"], ["crew", "Crew"], ["purchases", "Purchases"]]
const LOSS := Color(0.95, 0.5, 0.45)

var _cash: Label
var _cash_note: Label
var _grid := GridContainer.new()
var _cells := {}          # [line, column] -> Label
var _boats := VBoxContainer.new()
var _displayed: Array[Ferry] = []
var _make_label: Callable


## `make_label(text, size, color, bold)` builds a label in the HUD's fonts.
func setup(make_label: Callable) -> void:
	_make_label = make_label
	position = Vector2(132, 112)
	custom_minimum_size = Vector2(340, 0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	add_child(column)
	column.add_child(make_label.call("FINANCES", 13, Hud.MUTED, true))
	_cash = make_label.call("", 26, Hud.TEXT, true)
	column.add_child(_cash)
	_cash_note = make_label.call("Cash on hand", 11, Hud.MUTED, false)
	column.add_child(_cash_note)
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
	column.add_child(HSeparator.new())
	column.add_child(make_label.call("RUNNING COSTS TODAY", 11, Hud.MUTED, true))
	_boats.add_theme_constant_override("separation", 0)
	column.add_child(_boats)
	hide()


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
	var ledger := sim.ledger
	_cash.text = Hud.fmt_money(ledger.cash)
	_cash.add_theme_color_override("font_color", LOSS if ledger.cash < 0.0 else Hud.TEXT)
	_cash_note.text = "Cash on hand · started with %s" % Hud.fmt_money(CompanyLedger.STARTING_CASH)
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
	_refresh_boats(sim.ferries)


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
