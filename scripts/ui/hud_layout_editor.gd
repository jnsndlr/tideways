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
var _done := Button.new()


func setup(items: Dictionary) -> void:
	panels = items
	positions = GameSettings.hud_positions()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_done.text = "Done editing layout"
	_done.custom_minimum_size = Vector2(150, 44)
	_done.pressed.connect(finish)
	add_child(_done)
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


func place(bounds: Rect2) -> void:
	_bounds = bounds
	for key: String in panels:
		var panel: Control = panels[key]
		var fraction: Variant = positions.get(key)
		if panel.visible and fraction is Vector2 and fraction.is_finite():
			var travel := (bounds.size - panel.size).max(Vector2.ZERO)
			panel.position = bounds.position + travel * fraction.clamp(Vector2.ZERO, Vector2.ONE)
	if visible:
		_done.position = Vector2(
			bounds.get_center().x - _done.size.x * 0.5, bounds.position.y + 8.0
		)
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
