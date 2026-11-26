extends Control
## Launch Tideways from the ferry terminal's departure board.

const TEXT := Color(0.98, 0.91, 0.75)

const MainMapScript := preload("res://scripts/main_map.gd")
var _name_dialog: ColorRect

@onready var _terminal: TextureRect = $Terminal
@onready var _board: PanelContainer = $Board
@onready var _departures: VBoxContainer = $Board/Rows/Departures
@onready var _sandboxes: VBoxContainer = $Board/Rows/Sandboxes
@onready var _load_error: Label = $Board/Rows/LoadError


func _ready() -> void:
	match Scenes.launch_options.entry:
		SessionLaunchOptions.Entry.MAIN_MAP:
			Scenes.go.call_deferred(get_tree(), Scenes.MAIN_MAP)
		SessionLaunchOptions.Entry.SANDBOX:
			Scenes.go.call_deferred(get_tree(), Scenes.SANDBOX)
		SessionLaunchOptions.Entry.MENU:
			_build()


func _build() -> void:
	var title: HBoxContainer = $Board/Rows/Title
	for letter in "TIDEWAYS":
		var flap := Label.new()
		flap.text = letter
		flap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		flap.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		flap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		flap.custom_minimum_size.y = 126
		flap.add_theme_font_size_override("font_size", 88)
		flap.add_theme_stylebox_override("normal", _board.get_theme_stylebox("normal", "Button"))
		title.add_child(flap)
		var seam := ColorRect.new()
		seam.color = Color(0.035, 0.03, 0.025, 0.75)
		seam.mouse_filter = Control.MOUSE_FILTER_IGNORE
		flap.add_child(seam)
		seam.set_anchors_and_offsets_preset(Control.PRESET_HCENTER_WIDE)
		seam.offset_bottom = 2

	for group: VBoxContainer in [_departures, _sandboxes]:
		for child in group.get_children():
			if child is Button:
				child.draw.connect(_draw_flap.bind(child))

	var save := SaveGame.read()
	var resume: Button = _departures.get_node("Continue")
	var company: Label = _departures.get_node("Company")
	var new_company: Button = _departures.get_node("NewCompany")
	resume.visible = not save.is_empty()
	company.visible = resume.visible
	if resume.visible:
		var name_text := str(save.get("company", "")).strip_edges()
		var day_text := "Day %d" % int(save.day)
		company.text = day_text if name_text.is_empty() else "%s  ·  %s" % [name_text, day_text]
		company.tooltip_text = company.text
	var primary := resume if resume.visible else new_company
	primary.add_theme_font_size_override("font_size", 48)
	primary.add_theme_stylebox_override("normal", _board.get_theme_stylebox("pressed", "Button"))
	primary.custom_minimum_size.y = 98
	resume.pressed.connect(_load_saved)
	new_company.pressed.connect(func(): _ask_name(func(n): _play("", n)))
	_departures.get_node("Sandboxes").pressed.connect(_show_sandboxes.bind(true))
	_departures.get_node("Settings").pressed.connect(_open_settings)
	var quit_button: Button = _departures.get_node("Quit")
	quit_button.visible = not OS.has_feature("mobile")
	quit_button.pressed.connect(get_tree().quit)
	_sandboxes.get_node("Back").pressed.connect(_show_sandboxes.bind(false))
	_sandboxes.get_node("Mission").pressed.connect(
		func(): _ask_name(func(n): _play("", n, "Setting out with an open purse", true))
	)
	_sandboxes.get_node("Procedural").pressed.connect(
		func(): _start(Scenes.SANDBOX, "Rolling a fresh sandbox")
	)
	resized.connect(_layout_terminal)
	_layout_terminal()
	primary.grab_focus()
	Music.set_mood(get_tree(), Music.Mood.FULL)
	RadioChatter.on_menu(get_tree())
	UiSounds.install(get_tree())


## Draw the split and its pivot pins on each working row of the board.
func _draw_flap(button: Button) -> void:
	var y := floorf(button.size.y * 0.5)
	button.draw_line(Vector2(5, y), Vector2(button.size.x - 5, y), Color(0.04, 0.03, 0.02, 0.32))
	for x: float in [9.0, button.size.x - 9.0]:
		button.draw_rect(Rect2(x - 3, y - 5, 6, 10), Color("#181511"))
		button.draw_line(Vector2(x - 2, y - 4), Vector2(x + 2, y - 4), Color("#a28761"), 2)


func _layout_terminal() -> void:
	var art_size := _terminal.texture.get_size()
	var art_scale := maxf(size.x / art_size.x, size.y / art_size.y)
	_terminal.size = art_size * art_scale
	_terminal.position = (size - _terminal.size) * 0.5
	var portrait := size.y > size.x
	if portrait:
		# Keep the slip in the window above the board when the device rotates.
		_terminal.position.x = size.x - _terminal.size.x
	var width := size.x * (0.88 if portrait else 0.47)
	var board_scale := minf(width / 720.0, size.y / 900.0)
	_board.scale = Vector2.ONE * board_scale
	_board.size = Vector2(720, 0)
	_board.position = size * Vector2(0.035, 0.12)
	if portrait:
		_board.position = Vector2(
			(size.x - _board.size.x * board_scale) * 0.5,
			minf(size.y * 0.52, size.y * 0.96 - _board.size.y * board_scale)
		)


func _show_sandboxes(show_choices: bool) -> void:
	_departures.visible = not show_choices
	_sandboxes.visible = show_choices
	_board.reset_size()
	_layout_terminal()
	var focus: Button
	if show_choices:
		focus = _sandboxes.get_node("Mission")
	else:
		focus = _departures.get_node("Sandboxes")
	focus.grab_focus()


func _open_settings() -> void:
	var settings_button: Button = _departures.get_node("Settings")
	SettingsPanel.open(get_tree()).tree_exited.connect(settings_button.grab_focus)


## Asks for the company name, then calls `on_done` with it.
func _ask_name(on_done: Callable) -> void:
	if is_instance_valid(_name_dialog) or get_tree().root.has_node(LoadingScreen.LAYER_NAME):
		return
	var dim := ColorRect.new()
	_name_dialog = dim
	var opener := get_viewport().gui_get_focus_owner()
	if opener:
		dim.tree_exited.connect(opener.grab_focus)
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.add_child(center)
	var panel := PanelContainer.new()
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 12)
	panel.add_child(box)
	var label := Label.new()
	label.text = "Name your ferry company"
	label.add_theme_font_size_override("font_size", 22)
	label.add_theme_color_override("font_color", TEXT)
	box.add_child(label)
	var field := LineEdit.new()
	field.placeholder_text = "Island Ferries"
	field.max_length = 32
	field.custom_minimum_size = Vector2(360, 48)
	field.add_theme_font_size_override("font_size", 20)
	box.add_child(field)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override("separation", 10)
	box.add_child(row)
	var go := func():
		var n := field.text.strip_edges()
		dim.queue_free()
		on_done.call(n if n != "" else field.placeholder_text)
	var cancel := Button.new()
	cancel.text = "Cancel"
	cancel.custom_minimum_size = Vector2(110, 44)
	cancel.pressed.connect(dim.queue_free)
	row.add_child(cancel)
	var start := Button.new()
	start.text = "Start"
	start.custom_minimum_size = Vector2(110, 44)
	start.pressed.connect(go)
	row.add_child(start)
	field.text_submitted.connect(func(_t): go.call())
	field.grab_focus()


## Play the main map from `scenario` ("" for the opening).
func _play(
	scenario: String, company: String, caption := "Setting out for the islands", unlimited := false
) -> void:
	if _start(Scenes.MAIN_MAP, caption):
		MainMapScript.start_session(scenario, unlimited, company)


func _load_saved() -> void:
	var data := SaveGame.read()
	if data.is_empty():
		return
	if _start(Scenes.MAIN_MAP, "Picking up where you left off"):
		MainMapScript.load_session(data)


func _start(path: String, caption: String) -> bool:
	Engine.time_scale = 1.0
	var screen := LoadingScreen.open(get_tree(), path, caption)
	if not screen:
		return false
	_load_error.hide()
	screen.load_failed.connect(_on_load_failed, CONNECT_ONE_SHOT)
	return true


func _on_load_failed(message: String) -> void:
	_load_error.text = message
	_load_error.show()
	RadioChatter.on_menu(get_tree())
