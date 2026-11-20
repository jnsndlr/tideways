class_name MapControls
extends PanelContainer
## The group at the screen edge: the weather illustration above one toggle for each
## map layer the region supplies and a hide-all / show-all. It owns what the player
## chose to see; the HUD applies those choices to the map. Weather visibility is
## separate from the layers, and none of it touches the simulation.
##
## It rests against the left or right edge, part-way down, for the session. A drag
## on the illustration picks the edge and the height.

signal weather_toggled(shown: bool)
signal layers_changed

const GAP := 8.0
const CELL := Vector2(89, 44)
const ON := Color("255756")

var widget := WeatherWidget.new()
var weather_shown := true
## The screen edge it rests against (1 right, -1 left) and how far down that edge
## (0 top .. 1 bottom).
var side := 1
var fraction := 0.45

var _shown := {}      # layer id -> bool
var _buttons := {}    # layer id -> Button
var _all: Button
var _grab_y := 0.0
var _bounds := Rect2()
var _obstacles: Array[Rect2] = []


## `layers` lists [id, label, hint] for each layer this region can show, in button order.
func setup(layers: Array, sim: Simulation, day_cycle: DayCycle, font: Font, bold: Font) -> void:
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 2)
	add_child(column)
	widget.setup(sim, day_cycle, font)
	widget.tapped.connect(func() -> void: set_weather_shown(not weather_shown))
	widget.drag_started.connect(func(point: Vector2) -> void: _grab_y = point.y - position.y)
	widget.drag_moved.connect(_on_drag_moved)
	column.add_child(widget)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 2)
	grid.add_theme_constant_override("v_separation", 2)
	column.add_child(grid)
	for layer: Array in layers:
		var b := _button(layer[1], layer[2], bold)
		b.toggle_mode = true
		b.button_pressed = true
		var on := StyleBoxFlat.new()
		on.bg_color = ON
		on.set_corner_radius_all(6)
		b.add_theme_stylebox_override("pressed", on)
		b.add_theme_stylebox_override("hover_pressed", on)
		b.add_theme_color_override("font_color", Hud.MUTED)
		# A drawn tick, since the system fonts on iPad lack some symbol glyphs.
		var tick := Control.new()
		tick.set_anchors_preset(Control.PRESET_FULL_RECT)
		tick.mouse_filter = Control.MOUSE_FILTER_IGNORE
		tick.draw.connect(_draw_tick.bind(tick, b))
		b.add_child(tick)
		b.toggled.connect(_on_layer_toggled.bind(layer[0]))
		grid.add_child(b)
		_shown[layer[0]] = true
		_buttons[layer[0]] = b
	_all = _button("Hide all", "Hide or show every map layer", bold)
	_all.pressed.connect(_on_all_pressed)
	_all.visible = not layers.is_empty()
	# Fills the last cell of an odd grid, otherwise takes a row of its own.
	(grid if layers.size() % 2 == 1 else column).add_child(_all)


func _button(text: String, hint: String, bold: Font) -> Button:
	var b := Button.new()
	b.text = text
	b.tooltip_text = hint
	b.custom_minimum_size = CELL
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_override("font", bold)
	b.add_theme_font_size_override("font_size", 13)
	return b


func _draw_tick(tick: Control, b: Button) -> void:
	if b.button_pressed:
		var at := Vector2(11, tick.size.y * 0.5)
		tick.draw_polyline(PackedVector2Array([at + Vector2(-4, 0), at + Vector2(-1, 3), at + Vector2(5, -4)]),
			Hud.ACCENT, 2.0, true)


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


## Rests the group against its edge inside `bounds`, clear of `obstacles` (other HUD
## panels). It takes the clear height nearest the one the player chose; if that
## edge has none, it keeps its height and moves in beside whatever is in the way,
## so it stays on the side the player put it and within reach.
func place(bounds: Rect2, obstacles: Array[Rect2]) -> void:
	_bounds = bounds
	_obstacles = obstacles
	var room := maxf(0.0, bounds.size.y - size.y)
	var top := bounds.position.y
	var desired := top + fraction * room
	var x := bounds.end.x - size.x if side > 0 else bounds.position.x
	var heights: Array[float] = [desired]
	for o in obstacles:
		heights.append(o.position.y - GAP - size.y)
		heights.append(o.end.y + GAP)
	var best := INF
	var r := Rect2(Vector2(x, desired), size)
	for height in heights:
		var y := clampf(height, top, top + room)
		if absf(y - desired) < best and _is_clear(Rect2(Vector2(x, y), size), obstacles):
			best = absf(y - desired)
			r.position.y = y
	if best == INF:
		for attempt in 4:
			var clear := true
			for o in obstacles:
				var keep := o.grow(GAP)
				if r.intersects(keep):
					r.position.x = keep.position.x - r.size.x if side > 0 else keep.end.x
					clear = false
			if clear:
				break
	position = r.position.clamp(bounds.position, (bounds.end - size).max(bounds.position))


func _is_clear(r: Rect2, obstacles: Array[Rect2]) -> bool:
	for o in obstacles:
		if r.intersects(o.grow(GAP - 0.5)):
			return false
	return true


func _apply(layer: String, on: bool) -> void:
	_shown[layer] = on
	(_buttons[layer] as Button).set_pressed_no_signal(on)
	(_buttons[layer] as Button).get_child(0).queue_redraw()


func _refresh_all() -> void:
	_all.text = "Hide all" if any_shown() else "Show all"


func _on_layer_toggled(on: bool, layer: String) -> void:
	_apply(layer, on)
	_refresh_all()
	layers_changed.emit()


func _on_all_pressed() -> void:
	var on := not any_shown()
	for layer: String in _shown:
		_apply(layer, on)
	_refresh_all()
	layers_changed.emit()


## The group follows the finger: whichever edge is nearer, at the finger's height.
func _on_drag_moved(point: Vector2) -> void:
	side = 1 if point.x >= _bounds.get_center().x else -1
	fraction = clampf((point.y - _grab_y - _bounds.position.y) / maxf(1.0, _bounds.size.y - size.y), 0.0, 1.0)
	place(_bounds, _obstacles)
