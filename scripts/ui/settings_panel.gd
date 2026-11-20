class_name SettingsPanel
extends Control
## Settings overlay, opened from the title screen or the in-game sidebar.
## Sound: Master, Music, Radio calls and Interface sounds volume. Changes apply and save as the sliders move.
## Display: on/off options (GameSettings.FLAGS).

const PANEL_BG := Color(0.07, 0.11, 0.13, 0.96)
const DIM := Color(0, 0, 0, 0.45)
const TEXT := Color(0.9, 0.94, 0.95)
const MUTED := Color(0.58, 0.66, 0.68)
const ACCENT := Color(0.47, 0.86, 0.6)

## Bus -> label shown.
const SLIDERS := [["Master", "Master volume"], ["Music", "Music"], ["Radio", "Radio calls"],
	["Effects", "Interface sounds"]]
## Flag -> label shown.
const TOGGLES := [["floating_costs", "Show running costs over boats as they're paid"]]

var _close: Button


## Shows the panel over everything; returns it.
static func open(tree: SceneTree) -> SettingsPanel:
	var layer := CanvasLayer.new()
	layer.layer = 90
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	var panel := SettingsPanel.new()
	layer.add_child(panel)
	tree.root.add_child(layer)
	panel._close.grab_focus()
	return panel


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = DIM
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)

	var panel := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = PANEL_BG
	sb.set_corner_radius_all(12)
	sb.content_margin_left = 28
	sb.content_margin_right = 28
	sb.content_margin_top = 22
	sb.content_margin_bottom = 22
	panel.add_theme_stylebox_override("panel", sb)
	center.add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	col.custom_minimum_size.x = 380
	panel.add_child(col)

	var bold := SystemFont.new()
	bold.font_weight = 700
	var title := _label("SETTINGS", 20, TEXT)
	title.add_theme_font_override("font", bold)
	col.add_child(title)
	var section := _label("SOUND", 12, MUTED)
	section.add_theme_font_override("font", bold)
	col.add_child(section)
	for item in SLIDERS:
		col.add_child(_volume_row(item[0], item[1]))
	var display := _label("DISPLAY", 12, MUTED)
	display.add_theme_font_override("font", bold)
	col.add_child(display)
	for item in TOGGLES:
		var check := CheckButton.new()
		check.text = item[1]
		check.button_pressed = GameSettings.flag(item[0])
		check.add_theme_font_size_override("font_size", 15)
		var key: String = item[0]
		check.toggled.connect(func(on: bool) -> void: GameSettings.set_flag(key, on))
		col.add_child(check)

	_close = Button.new()
	_close.text = "Done"
	_close.custom_minimum_size = Vector2(140, 40)
	_close.size_flags_horizontal = Control.SIZE_SHRINK_END
	_close.add_theme_font_size_override("font_size", 16)
	_close.add_theme_color_override("font_hover_color", ACCENT)
	_close.add_theme_color_override("font_focus_color", ACCENT)
	_close.pressed.connect(close)
	col.add_child(_close)


func _volume_row(bus: String, text: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	var name_label := _label(text, 15, TEXT)
	name_label.custom_minimum_size.x = 130
	row.add_child(name_label)
	var slider := HSlider.new()
	slider.min_value = 0.0
	slider.max_value = 1.0
	slider.step = 0.01
	slider.value = GameSettings.volume(bus)
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.custom_minimum_size.y = 24
	row.add_child(slider)
	var pct := _label("", 14, MUTED)
	pct.custom_minimum_size.x = 44
	pct.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	row.add_child(pct)
	var show := func(v: float) -> void:
		pct.text = "Off" if v <= 0.001 else "%d%%" % roundi(v * 100.0)
	show.call(slider.value)
	slider.value_changed.connect(func(v: float) -> void:
		GameSettings.set_volume(bus, v)
		show.call(v))
	return row


func _label(text: String, size: int, col: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	return l


func close() -> void:
	get_parent().queue_free()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and (event as InputEventKey).physical_keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		close()
