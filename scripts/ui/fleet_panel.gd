class_name FleetPanel
extends PanelContainer
## Shows the current fleet. The HUD owns selection and camera follow.

signal ferry_selected(ferry: Ferry)

var _list := VBoxContainer.new()
var _displayed: Array[Ferry] = []


func setup(title: Label) -> void:
	position = Vector2(132, 112)
	custom_minimum_size = Vector2(320, 0)
	var column := VBoxContainer.new()
	add_child(column)
	column.add_child(title)
	column.add_child(_list)
	hide()


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
