class_name TerminalUpgradesPanel
extends VBoxContainer
## Displays one terminal's quoted upgrades. The HUD owns selection and camera focus.

signal purchase_requested(terminal: Terminal, offer: TerminalUpgrade)

var _rows := VBoxContainer.new()
var _terminal: Terminal
var _offers: Array[TerminalUpgrade] = []


func setup(title: Label) -> void:
	add_theme_constant_override("separation", 4)
	add_child(title)
	add_child(HSeparator.new())
	add_child(_rows)


func refresh(terminal: Terminal) -> void:
	var offers := terminal.upgrades()
	if terminal != _terminal or not _same_rows(offers):
		for child in _rows.get_children():
			_rows.remove_child(child)
			child.queue_free()
		for offer in offers:
			var button := Button.new()
			button.focus_mode = Control.FOCUS_NONE
			button.custom_minimum_size.y = 44
			button.alignment = HORIZONTAL_ALIGNMENT_LEFT
			button.text = "%s · %s" % [offer.title, Hud.fmt_money(offer.price)]
			button.pressed.connect(purchase_requested.emit.bind(terminal, offer))
			_rows.add_child(button)
			var detail := Label.new()
			detail.add_theme_font_size_override("font_size", 12)
			detail.add_theme_color_override("font_color", Hud.MUTED)
			detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			_rows.add_child(detail)
	_terminal = terminal
	_offers = offers
	for i in offers.size():
		var offer := offers[i]
		var researched := terminal.sim.has_research(offer.research)
		var shortfall := offer.price - terminal.sim.available_cash
		var button := _rows.get_child(2 * i) as Button
		button.disabled = not offer.blocked.is_empty() or not researched or shortfall > 0
		var detail := offer.detail()
		if not researched:
			detail = "Needs research: " + offer.research
		elif offer.blocked.is_empty() and shortfall > 0:
			detail += " · %s short" % Hud.fmt_money(shortfall)
		(_rows.get_child(2 * i + 1) as Label).text = detail


func _same_rows(offers: Array[TerminalUpgrade]) -> bool:
	if offers.size() != _offers.size():
		return false
	for i in offers.size():
		var a := offers[i]
		var b := _offers[i]
		if a.kind != b.kind or a.slip != b.slip or a.title != b.title or a.price != b.price or a.build_minutes != b.build_minutes:
			return false
		if not (is_nan(a.v) and is_nan(b.v)) and not is_equal_approx(a.v, b.v):
			return false
	return true
