class_name FleetPanel
extends PanelContainer
## Shows the current fleet, and buys boats: pick a class (price and running
## costs), then buy her. A tug delivers her to a free tie-up, or failing that an
## open slip (Simulation.delivery_slip). The HUD owns selection and camera follow.

signal ferry_selected(ferry: Ferry)
## The player bought a boat of `size`.
signal buy_requested(size: int)

var sim: Simulation
var _list := VBoxContainer.new()
var _displayed: Array[Ferry] = []
var _buy_button := Button.new()
var _buy_box := VBoxContainer.new()
var _classes := VBoxContainer.new()
var _confirm := Button.new()
var _where_title := Label.new()
var _size := 0                 # the class picked (0: none yet)


func setup(title: Label, s: Simulation) -> void:
	sim = s
	position = Vector2(132, 112)
	custom_minimum_size = Vector2(340, 0)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	add_child(column)
	column.add_child(title)
	column.add_child(_list)
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
	_confirm.focus_mode = Control.FOCUS_NONE
	_confirm.custom_minimum_size.y = 48
	_confirm.pressed.connect(func(): _buy(_size))
	_buy_box.add_child(_confirm)
	hide()


func _toggle_buy() -> void:
	_buy_box.visible = not _buy_box.visible
	_buy_button.text = "Close" if _buy_box.visible else "Buy a boat"
	_size = 0
	_refresh_buy()


func _pick(size: int) -> void:
	_size = size
	_refresh_buy()


## Text for class `size`: what she is, what she costs and what she costs to run.
static func class_text(size: int) -> String:
	var fc := FerryClass.of(size)
	var slip := "small" if fc.size <= MapData.Slip.LARGEST_BOAT[1] else "medium" if fc.size <= MapData.Slip.LARGEST_BOAT[2] else "large"
	return "Size %d · %s · %d cars · %s\ncrew %d · %s / hr · fuel ~%s / nm · needs a %s slip" % [
		size, fc.label, fc.capacity, "$" + Hud.fmt_int(fc.price()),
		fc.crew, Hud.fmt_money(FerryOperatingCosts.crew_per_hour(fc)), Hud.fmt_money(FerryOperatingCosts.fuel_cost(fc, FerryOperatingCosts.METRES_PER_NM, fc.cruise)), slip]


func _refresh_buy() -> void:
	if sim == null or not _buy_box.visible:
		return
	for i in _classes.get_child_count():
		var b := _classes.get_child(i) as Button
		b.text = class_text(i + 1)
		b.set_pressed_no_signal(i + 1 == _size)
	_confirm.visible = _size != 0
	if _size == 0:
		_where_title.text = "Pick a class. A tug tows her in to a free tie-up, or an open slip if there's none, where she lies laid up until you give her stops."
		return
	var where := sim.delivery_slip(_size)
	var why := sim.fleet_market.offer_problem(_size, where)
	if where.is_empty():
		_where_title.text = "No free slip she fits."
	else:
		var term: Terminal = where[0]
		var slip: int = where[1]
		if term.town.slips[slip].tie_up:
			_where_title.text = "Delivered to the tie-up at %s." % term.town.name
		elif Ferry.idle_slip(term, _size) == slip:
			_where_title.text = "No tie-up free: delivered to the slip at %s." % term.town.name
		else:
			_where_title.text = "No tie-up free: delivered to the slip at %s. Boats that call there hold off until you give her stops." % term.town.name
	_confirm.text = "Buy for %s" % ("$" + Hud.fmt_int(FerryClass.of(_size).price())) if why == "" else why
	_confirm.disabled = why != ""


func _buy(size: int) -> void:
	buy_requested.emit(size)
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
