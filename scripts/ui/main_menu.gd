extends Control
## Title screen: Play (the main mission), Mission sandbox (the main mission with
## unlimited money, for quick testing), Sandbox (the procedural test map) or Quit.
##
## Debug args after `--` skip the menu so the existing command-line workflow keeps
## working: `--main` opens the main map, any other arg (e.g. --seed=123) the sandbox.

const BG := Color(0.05, 0.09, 0.11)
const TEXT := Color(0.9, 0.94, 0.95)
const MUTED := Color(0.58, 0.66, 0.68)
const ACCENT := Color(0.47, 0.86, 0.6)

const MainMapScript := preload("res://scripts/main_map.gd")
var _load_error: Label


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty():
		Scenes.go.call_deferred(get_tree(), Scenes.MAIN_MAP if "--main" in args else Scenes.SANDBOX)
		return
	_build()


func _build() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 14)
	center.add_child(col)

	var bold := SystemFont.new()
	bold.font_weight = 700
	var title := Label.new()
	title.text = "TIDEWAYS"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_override("font", bold)
	title.add_theme_font_size_override("font_size", 72)
	title.add_theme_color_override("font_color", TEXT)
	col.add_child(title)
	var sub := Label.new()
	sub.text = "Run the ferries that keep the islands moving."
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.add_theme_font_size_override("font_size", 18)
	sub.add_theme_color_override("font_color", MUTED)
	col.add_child(sub)
	var gap := Control.new()
	gap.custom_minimum_size.y = 28
	col.add_child(gap)

	var play := _button(col, "Play", func(): _ask_name(func(n): _play("", n)))
	var load_btn := _button(col, "Load saved game", _load_saved)
	var save := SaveGame.read()
	load_btn.disabled = save.is_empty()
	if not save.is_empty():
		load_btn.tooltip_text = "%s · %s · day %d · saved %s" % [save.get("company", ""), str(save.get("scenario", "")).get_file().get_basename(), int(save.get("day", 0)), save.get("saved_at", "")]
	_button(col, "Mission sandbox", func(): _ask_name(func(n): _play("", n, "Setting out with an open purse", true)))
	_button(col, "Sandbox", func(): _start(Scenes.SANDBOX, "Rolling a fresh sandbox"))
	_button(col, "Settings", func(): SettingsPanel.open(get_tree()).tree_exited.connect(play.grab_focus))
	_button(col, "Quit", func(): get_tree().quit())
	_load_error = Label.new()
	_load_error.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_load_error.hide()
	col.add_child(_load_error)
	play.grab_focus()
	Music.set_mood(get_tree(), Music.Mood.FULL)
	RadioChatter.on_menu(get_tree())
	UiSounds.install(get_tree())


## Asks for the company name, then calls `on_done` with it.
func _ask_name(on_done: Callable) -> void:
	var dim := ColorRect.new()
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
func _play(scenario: String, company: String, caption := "Setting out for the islands", unlimited := false) -> void:
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


func _button(parent: Control, text: String, on_press: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(280, 52)
	b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	b.add_theme_font_size_override("font_size", 22)
	b.add_theme_color_override("font_hover_color", ACCENT)
	b.add_theme_color_override("font_focus_color", ACCENT)
	b.pressed.connect(on_press)
	parent.add_child(b)
	return b
