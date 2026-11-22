class_name FleetPanel
extends PanelContainer
## Shows the current fleet, and buys boats: pick a class (price and running
## costs), then where the tug delivers her (Simulation.buy_ferry). The HUD owns
## selection and camera follow.

signal ferry_selected(ferry: Ferry)
## The player bought a boat of `size` for delivery to `term`.
signal buy_requested(size: int, term: Terminal)

var sim: Simulation
var _list := VBoxContainer.new()
var _displayed: Array[Ferry] = []
var _buy_button := Button.new()
var _buy_box := VBoxContainer.new()
var _classes := VBoxContainer.new()
var _where := VBoxContainer.new()
var _where_title := Label.new()
var _size := 0                 # the class picked (0: none yet)
var _where_shown := ""         # what the delivery list was built for


func setup(title: Label, s: Simulation = null) -> void:
	sim = s
	position = Vector2(132, 112)
	custom_minimum_size = Vector2(340, 0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	add_child(column)
	column.add_child(title)
	column.add_child(_list)
	if sim == null:
		hide()
		return
	column.add_child(HSeparator.new())
	_buy_button.text = "Buy a boat"
	_buy_button.focus_mode = Control.FOCUS_NONE
	_buy_button.custom_minimum_size.y = 44
	_buy_button.pressed.connect(_toggle_buy)
	column.add_child(_buy_button)
	_buy_box.add_theme_constant_override("separation", 4)
	_buy_box.visible = false
	column.add_child(_buy_box)
	_buy_box.add_child(_classes)
	for size in range(1, FerryClass.MAX_SIZE + 1):
		var b := Button.new()
		b.focus_mode = Control.FOCUS_NONE
		b.toggle_mode = true
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size.y = 44
		b.add_theme_font_size_override("font_size", 12)
		b.pressed.connect(_pick.bind(size))
		_classes.add_child(b)
	_where_title.add_theme_font_size_override("font_size", 11)
	_where_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_buy_box.add_child(_where_title)
	_buy_box.add_child(_where)
	hide()


func _toggle_buy() -> void:
	_buy_box.visible = not _buy_box.visible
	_buy_button.text = "Close" if _buy_box.visible else "Buy a boat"
	_size = 0
	_where_shown = ""
	_refresh_buy()


func _pick(size: int) -> void:
	_size = size
	_where_shown = ""
	_refresh_buy()


## Text for class `size`: what she is, what she costs and what she costs to run.
static func class_text(size: int) -> String:
	var fc := FerryClass.of(size)
	var slip := "small" if fc.size <= MapData.Slip.LARGEST_BOAT[1] else "medium" if fc.size <= MapData.Slip.LARGEST_BOAT[2] else "large"
	return "Size %d · %s · %d cars · %s\ncrew %d · %s / hr · fuel ~%s / nm · needs a %s slip" % [
		size, fc.label, fc.capacity, "$" + Hud.fmt_int(fc.price()),
		fc.crew, Hud.fmt_money(fc.crew * Ferry.CREW_WAGE), Hud.fmt_money(Ferry.FUEL_PRICE * fc.burn), slip]


func _refresh_buy() -> void:
	if sim == null or not _buy_box.visible:
		return
	for i in _classes.get_child_count():
		var b := _classes.get_child(i) as Button
		b.text = class_text(i + 1)
		b.set_pressed_no_signal(i + 1 == _size)
	if _size == 0:
		_where_title.text = "Pick a class. A tug tows her in to a free slip at the terminal you pick, where she lies laid up until you give her stops."
		_clear_where()
		return
	_where_title.text = "DELIVER HER TO"
	# Rebuilt when what can be picked changes (cash, slips, terminals).
	var problems := []
	for term: Terminal in sim.terminals.values():
		problems.append([term, sim.purchase_problem(_size, term)])
	var key := str(_size) + "|" + ",".join(problems.map(func(p): return "%d:%s" % [p[0].town.id, p[1]]))
	if key == _where_shown:
		return
	_where_shown = key
	_clear_where()
	for p in problems:
		var term: Terminal = p[0]
		var why: String = p[1]
		var b := Button.new()
		b.focus_mode = Control.FOCUS_NONE
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.custom_minimum_size.y = 44
		b.add_theme_font_size_override("font_size", 12)
		b.text = "%s · buy for %s" % [term.town.name, "$" + Hud.fmt_int(FerryClass.of(_size).price())] if why == "" else "%s · %s" % [term.town.name, why]
		b.disabled = why != ""
		b.pressed.connect(_buy.bind(_size, term))
		_where.add_child(b)


func _clear_where() -> void:
	for c in _where.get_children():
		_where.remove_child(c)
		c.queue_free()


func _buy(size: int, term: Terminal) -> void:
	buy_requested.emit(size, term)
	_buy_box.visible = false
	_buy_button.text = "Buy a boat"
	_size = 0


func refresh(ferries: Array[Ferry]) -> void:
	if _displayed != ferries:
		_displayed = ferries.duplicate()
		for row in _list.get_children():
			_list.remove_child(row)
			row.queue_free()
		for ferry in ferries:
			var row := Button.new()
			row.focus_mode = Control.FOCUS_NONE
			row.alignment = HORIZONTAL_ALIGNMENT_LEFT
			row.add_theme_font_size_override("font_size", 13)
			row.pressed.connect(ferry_selected.emit.bind(ferry))
			_list.add_child(row)
	for i in ferries.size():
		var ferry := ferries[i]
		var row := _list.get_child(i) as Button
		row.text = "%s  ·  %d/%d  ·  %s" % [ferry.ferry_name, ferry.load_count(), ferry.fc.capacity, ferry.status_text()]
	_refresh_buy()
