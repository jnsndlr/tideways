class_name HudLayoutEditor
extends Control
## Captures drags only while the player is arranging the map HUD. Positions are
## fractions of the available travel so the same layout fits a resized viewport.

signal save_failed(error: Error)

var panels: Dictionary
var positions: Dictionary
var _bounds: Rect2
var _moving := ""
var _grab := Vector2.ZERO
var _tools := PanelContainer.new()
var _default_offsets: Dictionary


func setup(items: Dictionary) -> void:
	panels = items
	var stored := GameSettings.hud_positions()
	for key: String in panels:
		var panel: Control = panels[key]
		_default_offsets[key] = Vector2(panel.offset_left, panel.offset_top)
		var saved: Variant = stored.get(key)
		if saved is Vector2 and saved.is_finite():
			positions[key] = saved
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_tools)
	var row := HBoxContainer.new()
	_tools.add_child(row)
	var reset := Button.new()
	reset.text = "Reset layout"
	reset.custom_minimum_size = Vector2(128, 44)
	reset.pressed.connect(_reset)
	row.add_child(reset)
	var done := Button.new()
	done.text = "Done editing layout"
	done.custom_minimum_size = Vector2(150, 44)
	done.pressed.connect(finish)
	row.add_child(done)
	hide()


func begin() -> void:
	_moving = ""
	show()
	get_parent().move_child(self, -1)
	queue_redraw()


func finish() -> void:
	var err := GameSettings.save_hud_positions(positions)
	if err != OK:
		save_failed.emit(err)
		return
	_moving = ""
	hide()


func _reset() -> void:
	for key: String in positions:
		var panel: Control = panels[key]
		var offset := Vector2(panel.offset_left, panel.offset_top)
		var initial: Vector2 = _default_offsets[key]
		panel.position += initial - offset
	positions.clear()
	_moving = ""


func place(bounds: Rect2) -> void:
	_bounds = bounds
	for key: String in panels:
		var panel: Control = panels[key]
		var fraction: Variant = positions.get(key)
		if panel.visible and fraction is Vector2 and fraction.is_finite():
			var travel := (bounds.size - panel.size).max(Vector2.ZERO)
			panel.position = bounds.position + travel * fraction.clamp(Vector2.ZERO, Vector2.ONE)
	if visible:
		_tools.position = Vector2(bounds.end.x - _tools.size.x - 8.0, bounds.position.y + 8.0)
		queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_moving = ""
		if event.pressed:
			for key: String in panels:
				var panel: Control = panels[key]
				if panel.visible and panel.get_rect().has_point(event.position):
					if _moving.is_empty() or panel.get_index() > panels[_moving].get_index():
						_moving = key
						_grab = event.position - panel.position
		accept_event()
	elif event is InputEventMouseMotion and not _moving.is_empty():
		var panel: Control = panels[_moving]
		var travel := (_bounds.size - panel.size).max(Vector2.ZERO)
		var local: Vector2 = (event.position - _grab - _bounds.position).clamp(Vector2.ZERO, travel)
		positions[_moving] = local / travel.max(Vector2.ONE)
		place(_bounds)
		accept_event()


func _draw() -> void:
	for panel: Control in panels.values():
		if panel.visible:
			draw_rect(panel.get_rect().grow(-1.0), Color("82dba9"), false, 2.0)
