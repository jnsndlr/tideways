extends Control
## Launch Tideways from the ferry terminal's departure board.

const TEXT := Color(0.98, 0.91, 0.75)

const DepartureBoard := preload("res://scripts/ui/departure_board.gd")
const MainMapScript := preload("res://scripts/main_map.gd")
var _name_dialog: ColorRect

@onready var _board: DepartureBoard = $Board
@onready var _departures: Control = $Board/Rows/Departures
@onready var _sandboxes: Control = $Board/Rows/Sandboxes
@onready var _load_error: Label = $LoadError


func _ready() -> void:
	match Scenes.launch_options.entry:
		SessionLaunchOptions.Entry.MAIN_MAP:
			Scenes.go.call_deferred(get_tree(), Scenes.MAIN_MAP)
		SessionLaunchOptions.Entry.SANDBOX:
			Scenes.go.call_deferred(get_tree(), Scenes.SANDBOX)
		SessionLaunchOptions.Entry.MENU:
			_build()


func _build() -> void:
	var save := SaveGame.read()
	var resume: Button = _departures.get_node("Continue")
	var company: Label = _departures.get_node("Company")
	var new_company: Button = _departures.get_node("NewCompany")
	resume.visible = not save.is_empty()
	company.visible = resume.visible
	if resume.visible:
		var name_text := str(save.get("company", "")).strip_edges()
		var day_text := "Day %d" % int(save.day)
		company.text = _board.company_caption(name_text, day_text)
		company.tooltip_text = company.text
	var primary := resume if resume.visible else new_company
	if resume.visible:
		resume.tooltip_text = (
			"%s · %s · saved %s"
			% [company.text, str(save.scenario).get_file().get_basename(), save.get("saved_at", "")]
		)
	_board.place_action(primary, 1)
	_board.place_action(company, 2)
	if resume.visible:
		_board.place_action(new_company, 3)
	_board.place_action(_departures.get_node("Sandboxes"), 4 if resume.visible else 3)
	_board.place_action(_departures.get_node("Settings"), 5 if resume.visible else 4)
	_board.place_action(_sandboxes.get_node("Mission"), 1)
	_board.place_action(_sandboxes.get_node("Procedural"), 3)
	_board.place_action(_sandboxes.get_node("Back"), 5)
	resume.pressed.connect(_load_saved)
	new_company.pressed.connect(func(): _ask_name(func(n): _play("", n)))
	_departures.get_node("Sandboxes").pressed.connect(_show_sandboxes.bind(true))
	_departures.get_node("Settings").pressed.connect(_open_settings)
	var quit_button: Button = $Quit
	quit_button.visible = not OS.has_feature("mobile")
	quit_button.pressed.connect(get_tree().quit)
	_sandboxes.get_node("Back").pressed.connect(_show_sandboxes.bind(false))
	_sandboxes.get_node("Mission").pressed.connect(
		func(): _ask_name(func(n): _play("", n, "Setting out with an open purse", true))
	)
	_sandboxes.get_node("Procedural").pressed.connect(
		func(): _start(Scenes.SANDBOX, "Rolling a fresh sandbox")
	)
	_display_departures(true)
	primary.grab_focus()
	Music.set_mood(get_tree(), Music.Mood.FULL)
	RadioChatter.on_menu(get_tree())
	UiSounds.install(get_tree())


func _display_departures(turn_title: bool) -> void:
	var company: Label = _departures.get_node("Company")
	if company.visible:
		_board.display(
			["TIDEWAYS", "Continue", company.text, "New company", "Sandboxes", "Settings"],
			turn_title
		)
	else:
		_board.display(["TIDEWAYS", "New company", "", "Sandboxes", "Settings", ""], turn_title)


func _show_sandboxes(show_choices: bool) -> void:
	_departures.visible = not show_choices
	_sandboxes.visible = show_choices
	if show_choices:
		_board.display(["TIDEWAYS", "Mission sandbox", "", "Sandbox", "", "Back"], false)
		_sandboxes.get_node("Mission").grab_focus()
	else:
		_display_departures(false)
		_departures.get_node("Sandboxes").grab_focus()


func _open_settings() -> void:
	var settings_button: Button = _departures.get_node("Settings")
	_keep_focus_in(SettingsPanel.open(get_tree()), settings_button)


## Keep keyboard navigation on the open panel and return it to the invoking action.
func _keep_focus_in(panel: Node, opener: Control) -> void:
	focus_behavior_recursive = Control.FOCUS_BEHAVIOR_DISABLED
	panel.tree_exited.connect(
		func():
			focus_behavior_recursive = Control.FOCUS_BEHAVIOR_INHERITED
			if (
				is_instance_valid(opener)
				and opener.is_inside_tree()
				and opener.is_visible_in_tree()
			):
				opener.grab_focus()
	)


## Asks for the company name, then calls `on_done` with it.
func _ask_name(on_done: Callable) -> void:
	if is_instance_valid(_name_dialog) or get_tree().root.has_node(LoadingScreen.LAYER_NAME):
		return
	var dim := ColorRect.new()
	_name_dialog = dim
	var opener := get_viewport().gui_get_focus_owner()
	dim.focus_behavior_recursive = Control.FOCUS_BEHAVIOR_ENABLED
	_keep_focus_in(dim, opener)
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
