class_name MapControls
extends PanelContainer
## The group at the screen edge: the weather illustration, one toggle for each map
## layer the region supplies, and a hide-all / show-all. It owns what the player
## chose to see; the HUD applies those choices to the map. Weather visibility is
## separate from the layers, and none of it touches the simulation.

signal weather_toggled(shown: bool)
signal layers_changed

const GAP := 8.0
const BUTTON := Vector2(96, 44)

var widget := WeatherWidget.new()
var weather_shown := true
## The screen edge it rests against (1 right, -1 left) and how far down.
var side := 1
var dock_y := 0.0

var _shown := {}      # layer id -> bool
var _buttons := {}    # layer id -> Button
var _all: Button
var _dragging := false
var _drag_from := Vector2.ZERO
var _bounds := Rect2()


## `layers` lists [id, label] for each layer this region can show, in button order.
func setup(layers: Array, sim: Simulation, day_cycle: DayCycle, font: Font, bold: Font) -> void:
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 2)
	add_child(column)
	widget.setup(sim, day_cycle, font, bold)
	widget.tapped.connect(_on_weather_tapped)
	widget.drag_moved.connect(_on_drag_moved)
	widget.drag_ended.connect(_on_drag_ended)
	column.add_child(widget)
	for layer: Array in layers:
		var b := _button(layer[1], bold)
		b.toggle_mode = true
		b.button_pressed = true
		b.add_theme_color_override("font_color", WeatherWidget.MUTED)
		b.toggled.connect(_on_layer_toggled.bind(layer[0]))
		column.add_child(b)
		_shown[layer[0]] = true
		_buttons[layer[0]] = b
	_all = _button("Hide all", bold)
	_all.pressed.connect(_on_all_pressed)
	_all.visible = not layers.is_empty()
	column.add_child(_all)


func _button(text: String, bold: Font) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = BUTTON
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_override("font", bold)
	b.add_theme_font_size_override("font_size", 13)
	return b


## Whether the player wants this layer on the map. False for a layer the region lacks.
func shows(layer: String) -> bool:
	return _shown.get(layer, false)


func any_shown() -> bool:
	return _shown.values().has(true)


func set_layer(layer: String, on: bool) -> void:
	if not _shown.has(layer) or _shown[layer] == on:
		return
	_apply(layer, on)
	_refresh_all()
	layers_changed.emit()


func set_weather_shown(on: bool) -> void:
	if weather_shown == on:
		return
	weather_shown = on
	widget.effects_shown = on
	weather_toggled.emit(on)


## Rests the group against its edge inside `bounds`, moved inward past any of
## `obstacles` (other HUD panels) it would otherwise overlap.
func place(bounds: Rect2, obstacles: Array[Rect2]) -> void:
	_bounds = bounds
	var far := (bounds.end - size).max(bounds.position)
	if _dragging:
		position = position.clamp(bounds.position, far)
		return
	var r := Rect2(Vector2(far.x if side > 0 else bounds.position.x, clampf(dock_y, bounds.position.y, far.y)), size)
	for attempt in 4:
		var clear := true
		for o in obstacles:
			var keep := o.grow(GAP)
			if r.intersects(keep):
				r.position.x = keep.position.x - r.size.x if side > 0 else keep.end.x
				clear = false
		if clear:
			break
	position = r.position.clamp(bounds.position, far)


func _apply(layer: String, on: bool) -> void:
	_shown[layer] = on
	(_buttons[layer] as Button).set_pressed_no_signal(on)


func _refresh_all() -> void:
	_all.text = "Hide all" if any_shown() else "Show all"


func _on_layer_toggled(on: bool, layer: String) -> void:
	_shown[layer] = on
	_refresh_all()
	layers_changed.emit()


func _on_all_pressed() -> void:
	var on := not any_shown()
	for layer: String in _shown:
		_apply(layer, on)
	_refresh_all()
	layers_changed.emit()


func _on_weather_tapped() -> void:
	set_weather_shown(not weather_shown)


func _on_drag_moved(offset: Vector2) -> void:
	if not _dragging:
		_dragging = true
		_drag_from = position
	position = _drag_from + offset


func _on_drag_ended() -> void:
	_dragging = false
	side = 1 if position.x + size.x * 0.5 > _bounds.get_center().x else -1
	dock_y = position.y
