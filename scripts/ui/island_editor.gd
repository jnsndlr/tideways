class_name IslandEditor
extends CanvasLayer
## The main map's island editor. Pick an island (list, arrows or click it), roll or
## dial its shape, place, height and cover, and the ground under it is stamped
## again straight away. Towns, trees, docks and routes go stale meanwhile and are
## hidden; Apply rebuilds the whole map around the new islands. Save writes
## MapLayout.MAIN_STORY, Copy / Paste move the layout as JSON.

const WIDTH := 372
const RESTAMP_DELAY := 0.18

## [key, label, min, max, step, unit]
const SHAPE := [
	["shape_seed", "Shape seed", 1, 99999, 1, ""],
	["radius", "Size", 250, 950, 5, " m"],
	["stretch", "Stretch", 1.0, 2.2, 0.01, "×"],
	["angle", "Rotation", 0, 180, 1, "°"],
	["roughness", "Coastline", 0.2, 2.0, 0.01, "×"],
]
const PLACE := [
	["x", "East – west", -3000, 3000, 5, " m"],
	["z", "North – south", -3000, 3000, 5, " m"],
]
const RELIEF := [
	["height", "Height", 0.5, 1.6, 0.01, "×"],
	["hills", "Height variance", 0.0, 2.2, 0.01, "×"],
]
const COVER := [
	["forest", "Forest", 0.0, 1.6, 0.01, "×"],
	["fields", "Fields", 0.0, 1.0, 0.01, ""],
]

## How faceted the ground looks; a look setting, kept for the session.
static var facet := 0.4

var main
var selected := 0
var _root: Control
var _panel: PanelContainer
var _toggle: Button
var _picker: OptionButton
var _name: LineEdit
var _pinned: CheckBox
var _status: Label
var _apply: Button
var _remove: Button
var _sliders := {}   # key -> [HSlider, value Label, unit]
var _syncing := false
var _stale := false
var _pending := {}   # layout indices waiting to be stamped again
var _timer: Timer
var _rng := RandomNumberGenerator.new()


func setup(m) -> void:
	main = m
	layer = 5
	_rng.randomize()
	_timer = Timer.new()
	_timer.one_shot = true
	_timer.ignore_time_scale = true
	_timer.wait_time = RESTAMP_DELAY
	_timer.timeout.connect(_restamp_pending)
	add_child(_timer)
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_root.theme = main.hud.root.theme
	add_child(_root)
	_toggle = Button.new()
	_toggle.text = "ISLANDS  (I)"
	_toggle.position = Vector2(22, 472)
	_toggle.add_theme_stylebox_override("normal", _box(Hud.PANEL_BG, 8))
	_toggle.pressed.connect(_toggle_open)
	_root.add_child(_toggle)
	_build_panel()
	_panel.visible = false
	main.builder.terrain_material.set_shader_parameter("facet", facet)
	main.rig.ground_clicked.connect(_on_ground_clicked)


func is_open() -> bool:
	return _panel.visible


func open(k := 0) -> void:
	_panel.visible = true
	_toggle.text = "CLOSE EDITOR  (I)"
	main.hud.visible = false
	main.hud.set_speed(0)
	_refresh_picker()
	_select(clampi(k, 0, main.layout.islands.size() - 1), false)


func close() -> void:
	_panel.visible = false
	_toggle.text = "ISLANDS  (I)"
	main.hud.visible = true


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and (event as InputEventKey).physical_keycode == KEY_I:
		_toggle_open()
		get_viewport().set_input_as_handled()


func _toggle_open() -> void:
	if is_open():
		close()
	else:
		open(selected)


# --- Panel ------------------------------------------------------------------------

func _build_panel() -> void:
	_panel = PanelContainer.new()
	_panel.anchor_left = 1.0
	_panel.anchor_right = 1.0
	_panel.anchor_bottom = 1.0
	_panel.offset_left = -WIDTH - 16
	_panel.offset_right = -16
	_panel.offset_top = 16
	_panel.offset_bottom = -16
	_panel.add_theme_stylebox_override("panel", _box(Hud.PANEL_BG, 10, 14, 12))
	_root.add_child(_panel)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_panel.add_child(scroll)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 6)
	scroll.add_child(v)

	v.add_child(_label("ISLAND EDITOR", 17, Hud.TEXT))
	_status = _label("", 12, Hud.MUTED)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_status)

	var pick := HBoxContainer.new()
	var prev := _button("◀", func(): _select(posmod(selected - 1, main.layout.islands.size())))
	_picker = OptionButton.new()
	_picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_picker.item_selected.connect(func(i): _select(i))
	var next := _button("▶", func(): _select((selected + 1) % main.layout.islands.size()))
	pick.add_child(prev)
	pick.add_child(_picker)
	pick.add_child(next)
	v.add_child(pick)

	var nm := HBoxContainer.new()
	_name = LineEdit.new()
	_name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_name.placeholder_text = "Island name"
	_name.text_changed.connect(_on_name)
	_pinned = CheckBox.new()
	_pinned.text = "Pinned"
	_pinned.tooltip_text = "Pinned islands keep their shape and place when you reroll the rest."
	_pinned.toggled.connect(func(on):
		if not _syncing:
			_spec().pinned = on
			_mark_unsaved())
	nm.add_child(_name)
	nm.add_child(_pinned)
	v.add_child(nm)

	_section(v, "SHAPE", SHAPE)
	_row_buttons(v, [["🎲 New coastline", func(): _set_value("shape_seed", _rng.randi_range(1, 99999))],
		["🎲 Reroll shape", _reroll_shape]])
	_section(v, "POSITION", PLACE)
	_row_buttons(v, [["🎲 Reroll position", _reroll_position]])
	_section(v, "HEIGHT", RELIEF)
	_section(v, "COVER", COVER)

	v.add_child(_label("MAP", 12, Hud.ACCENT))
	_row_buttons(v, [["🎲 Reroll unpinned", _reroll_unpinned], ["🎲 Mainland & islets", _reroll_world]])
	_remove = _button("Remove island", _remove_island)
	_row_buttons(v, [["Add island", _add_island]], [_remove])
	var look := HBoxContainer.new()
	look.add_child(_fixed_label("Facets", 108))
	var fs := HSlider.new()
	fs.min_value = 0.0
	fs.max_value = 1.0
	fs.step = 0.01
	fs.value = facet
	fs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fs.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	fs.value_changed.connect(func(x):
		facet = x
		main.builder.terrain_material.set_shader_parameter("facet", x))
	look.add_child(fs)
	v.add_child(look)

	v.add_child(HSeparator.new())
	_apply = _button("Apply: rebuild towns, trees & routes", func(): _rebuild())
	_apply.add_theme_color_override("font_color", Hud.ACCENT)
	v.add_child(_apply)
	_row_buttons(v, [["Save", _save], ["Copy JSON", _copy], ["Paste JSON", _paste]])
	_refresh_status()


func _section(v: VBoxContainer, title: String, defs: Array) -> void:
	v.add_child(_label(title, 12, Hud.ACCENT))
	for d in defs:
		var row := HBoxContainer.new()
		row.add_child(_fixed_label(d[1], 108))
		var s := HSlider.new()
		s.min_value = d[2]
		s.max_value = d[3]
		s.step = d[4]
		s.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		var val := _fixed_label("", 64)
		val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		var key: String = d[0]
		s.value_changed.connect(func(x): _on_slider(key, x))
		row.add_child(s)
		row.add_child(val)
		v.add_child(row)
		_sliders[key] = [s, val, d[5]]


func _row_buttons(v: VBoxContainer, defs: Array, extra: Array = []) -> void:
	var row := HBoxContainer.new()
	for d in defs:
		var b := _button(d[0], d[1])
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(b)
	for b in extra:
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(b)
	v.add_child(row)


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.add_theme_stylebox_override("normal", _box(Color(1, 1, 1, 0.06), 6, 8, 5))
	b.pressed.connect(cb)
	return b


func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _fixed_label(text: String, w: int) -> Label:
	var l := _label(text, 13, Hud.TEXT)
	l.custom_minimum_size.x = w
	return l


func _box(bg: Color, radius: int, hm := 10, vm := 6) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.content_margin_left = hm
	sb.content_margin_right = hm
	sb.content_margin_top = vm
	sb.content_margin_bottom = vm
	return sb


# --- Selection --------------------------------------------------------------------

func _spec() -> MapLayout.IslandSpec:
	return main.layout.islands[selected]


func _refresh_picker() -> void:
	_picker.clear()
	for s in main.layout.islands:
		_picker.add_item(("📌 " if s.pinned else "") + (s.name if s.name != "" else "(unnamed)"))
	if selected < _picker.item_count:
		_picker.select(selected)


func _select(k: int, focus := true) -> void:
	if main.layout.islands.is_empty():
		return
	selected = k
	_picker.select(k)
	_sync()
	if focus:
		var s := _spec()
		main.rig.target_pos = Vector3(s.x, 0.0, s.z)
		main.rig.target_dist = clampf(s.radius * maxf(s.stretch, 1.0) * 3.0, 900.0, 4400.0)


func _sync() -> void:
	_syncing = true
	var s := _spec()
	_name.text = s.name
	_pinned.button_pressed = s.pinned
	for key in _sliders:
		var e: Array = _sliders[key]
		(e[0] as HSlider).value = s.get(key)
		_show_value(key)
	_syncing = false


func _show_value(key: String) -> void:
	var e: Array = _sliders[key]
	var x: float = (e[0] as HSlider).value
	var step: float = (e[0] as HSlider).step
	(e[1] as Label).text = (str(int(x)) if step >= 1.0 else "%.2f" % x) + e[2]


## The island under a click on the map, when it's one of the layout's.
func _on_ground_clicked(screen: Vector2) -> void:
	if not is_open():
		return
	var cam: Camera3D = main.rig.camera
	var o := cam.project_ray_origin(screen)
	var d := cam.project_ray_normal(screen)
	if d.y > -0.01:
		return
	var p := o + d * ((20.0 - o.y) / d.y)
	var k: int = main.terrain.island_at(p.x, p.z) - _first_id()
	if k >= 0 and k < main.layout.islands.size():
		_select(k, false)


# --- Editing ----------------------------------------------------------------------

## Map island id of layout entry 0: the mainland's masses come first.
func _first_id() -> int:
	var c := 0
	for isl in main.map.islands:
		if isl.is_mainland:
			c += 1
	return c


func _on_slider(key: String, x: float) -> void:
	_show_value(key)
	if _syncing:
		return
	var s := _spec()
	s.set(key, int(x) if key == "shape_seed" else x)
	_queue(selected)


func _set_value(key: String, x) -> void:
	_spec().set(key, x)
	_sync()
	_queue(selected)


func _on_name(text: String) -> void:
	if _syncing:
		return
	_spec().name = text
	_picker.set_item_text(selected, ("📌 " if _spec().pinned else "") + text)
	_mark_unsaved()


func _queue(k: int) -> void:
	_pending[k] = true
	_mark_unsaved()
	_timer.start()


## Stamps the changed islands into the ground again and rebuilds the tiles there.
func _restamp_pending() -> void:
	var first := _first_id()
	for k in _pending:
		if k >= main.layout.islands.size():
			continue
		var id: int = first + k
		var isl: MapData.Island = main.map.islands[id]
		MapGenerator.apply_spec(isl, main.layout.islands[k])
		var rect: Rect2i = main.terrain.replace_stamp(id, MapGenerator.stamp_of(isl))
		main.builder.rebuild_terrain(rect)
	_pending.clear()
	_go_stale()


## Hides everything built on the old ground until the map is rebuilt.
func _go_stale() -> void:
	if _stale:
		return
	_stale = true
	for c in main.builder.root.get_children():
		if not (str(c.name).begins_with("Terrain_") or c.name == "Water" or c.name == "SeaFloor"):
			c.visible = false
	for c in main.get_children():
		if c is Node3D and not (c is CameraRig or c is DirectionalLight3D or c is Backdrop \
				or c is CloudLayer or c == main.builder.root):
			c.visible = false
	_refresh_status()


func _reroll_shape() -> void:
	var s := _spec()
	MapGenerator.roll_shape(s, _rng)
	_sync()
	_queue(selected)
	if not MapGenerator.fits(main.layout, s):
		_flash("The new shape crowds a neighbour. Reroll its position or shrink it.")


func _reroll_position() -> void:
	if MapGenerator.roll_position(main.layout, _spec(), _rng):
		_sync()
		_queue(selected)
		_select(selected)
	else:
		_flash("No room for it anywhere at this size.")


## Every unpinned island gets a new shape and place, around the pinned ones.
func _reroll_unpinned() -> void:
	var todo: Array = []
	for s in main.layout.islands:
		if not s.pinned:
			todo.append(s)
	if todo.is_empty():
		_flash("Every island is pinned.")
		return
	for s in todo:
		MapGenerator.roll_shape(s, _rng)
	var waiting := todo.duplicate()
	for s in todo:
		waiting.erase(s)
		for shrink in 6:
			if MapGenerator.roll_position(main.layout, s, _rng, waiting):
				break
			s.radius *= 0.88
	_mark_unsaved()
	_rebuild()


func _reroll_world() -> void:
	main.layout.world_seed = _rng.randi_range(1, 99999)
	_mark_unsaved()
	_rebuild()


func _add_island() -> void:
	var s := MapLayout.IslandSpec.new()
	s.name = "Island %d" % (main.layout.islands.size() + 1)
	MapGenerator.roll_shape(s, _rng)
	for shrink in 6:
		if MapGenerator.roll_position(main.layout, s, _rng):
			break
		s.radius *= 0.88
	main.layout.islands.append(s)
	selected = main.layout.islands.size() - 1
	_mark_unsaved()
	_rebuild()


func _remove_island() -> void:
	if _remove.text != "Click again to remove":
		_remove.text = "Click again to remove"
		get_tree().create_timer(2.5, true, false, true).timeout.connect(func(): _remove.text = "Remove island")
		return
	main.layout.islands.remove_at(selected)
	selected = maxi(selected - 1, 0)
	_mark_unsaved()
	_rebuild()


# --- Rebuild, save, copy ----------------------------------------------------------

func _rebuild() -> void:
	_status.text = "Rebuilding the map…"
	_apply.disabled = true
	await get_tree().process_frame
	await get_tree().process_frame
	main.rebuild()


func _save() -> void:
	var err: Error = main.layout.save_file(MapLayout.MAIN_STORY)
	var where := MapLayout.MAIN_STORY
	if err != OK:
		# An exported build can't write into the project: keep it in user:// instead.
		where = "user://main_story.json"
		err = main.layout.save_file(where)
	if err == OK:
		main.unsaved = false
		_flash("Saved to %s" % where)
	else:
		_flash("Couldn't save (%s). Use Copy JSON instead." % error_string(err))


func _copy() -> void:
	DisplayServer.clipboard_set(main.layout.to_json())
	_flash("Layout copied to the clipboard.")


func _paste() -> void:
	var lay := MapLayout.from_json(DisplayServer.clipboard_get())
	if lay == null or lay.islands.is_empty():
		_flash("The clipboard doesn't hold a layout.")
		return
	main.layout = lay
	selected = 0
	_mark_unsaved()
	_rebuild()


func _mark_unsaved() -> void:
	if not main.unsaved:
		main.unsaved = true
		_refresh_status()


func _refresh_status() -> void:
	var parts: Array[String] = []
	parts.append("Unsaved changes" if main.unsaved else "Saved")
	if _stale:
		parts.append("ground preview: Apply to rebuild towns, trees, docks and routes")
	parts.append("world seed %d" % main.layout.world_seed)
	_status.text = " · ".join(parts)
	_apply.disabled = false


func _flash(text: String) -> void:
	_status.text = text
	get_tree().create_timer(3.0, true, false, true).timeout.connect(_refresh_status)
