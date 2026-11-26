extends CenterContainer
## Center the dialog in the part of the window above the on-screen keyboard.


func _ready() -> void:
	set_process(DisplayServer.has_feature(DisplayServer.FEATURE_VIRTUAL_KEYBOARD))


func _process(_delta: float) -> void:
	var keyboard_pixels := maxi(0, DisplayServer.virtual_keyboard_get_height())
	var window_height := DisplayServer.window_get_size().y
	if window_height > 0:
		offset_bottom = -keyboard_pixels * get_viewport_rect().size.y / window_height
