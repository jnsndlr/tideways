class_name IslandEditor
extends CanvasLayer
## The main map's island editor. Pick an island (list, arrows or click it), roll or
## dial its shape, place, height and cover, and the ground under it is stamped
## again straight away. Towns, trees, docks and routes go stale meanwhile and are
## hidden; Apply rebuilds the whole map around the new islands. Save writes
## MapLayout.MAIN_STORY, Copy / Paste move the layout as JSON. Place dock then a
## click by the shore locks a ferry dock there (an island can have several; one
## with none never gets a terminal). Each has a tier, its price to build in play.

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
	["x", "East – west", -3300, 3300, 5, " m"],
	["z", "North – south", -3300, 3300, 5, " m"],
]
const RELIEF := [
	["height", "Height", 0.5, 1.6, 0.01, "×"],
	["hills", "Height variance", 0.0, 2.2, 0.01, "×"],
	["peak", "Mountain", 0.0, 2.0, 0.01, "×"],
	["lakes", "Lakes", 0.0, 1.0, 0.01, ""],
]
const COVER := [
	["forest", "Forest", 0.0, 1.6, 0.01, "×"],
	["fields", "Fields", 0.0, 1.0, 0.01, ""],
]

## How faceted the ground looks; a look setting, kept for the session.
static var facet := 0.4
## The panel folded down to its title bar (H), to see more of the map; kept for
## the session, across rebuilds.
static var collapsed := false

var main
var selected := 0
var _root: Control
var _panel: PanelContainer
var _toggle: Button
var _picker: OptionButton
var _name: LineEdit
var _pinned: CheckBox
var _mainland: CheckBox
var _status: Label
var _body: ScrollContainer
var _fold: Button
var _apply: Button
var _remove: Button
var _sliders := {}   # key -> [HSlider, value Label, unit]
var _syncing := false
var _stale := false
var _pending := {}   # layout indices waiting to be stamped again
var _timer: Timer
var _rng := RandomNumberGenerator.new()
var _dock_info: Label
var _dock_btn: Button
var _move_btn: Button
var _del_btn: Button
var _dock_pick: OptionButton
var _tier: OptionButton
var _dock := 0             # the selected island's selected dock
var _ferry: CheckBox
var _facing: HSlider
var _facing_val: Label
var _placing := -1        # -1 off, 0 adding a dock, 1 moving the selected one
var _dock_dirty := false   # a dock moved since the last build
var _marker: Node3D


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
	_toggle.add_theme_stylebox_override("normal", _box(Hud.PANEL_BG, 8))
	_toggle.pressed.connect(_toggle_open)
	_root.add_child(_toggle)
	# Just under the HUD sidebar, however tall it grows.
	main.hud.sidebar.resized.connect(_place_toggle)
	_place_toggle()
	_build_panel()
	_apply_collapsed()
	_panel.visible = false
	main.builder.terrain_material.set_shader_parameter("facet", facet)
	main.rig.ground_clicked.connect(_on_ground_clicked)
	_build_marker()


func _toggle_collapsed() -> void:
	collapsed = not collapsed
	_apply_collapsed()


## Folded, the panel is just its title bar in the top right corner.
func _apply_collapsed() -> void:
	_body.visible = not collapsed
	_fold.text = "Show  (H)" if collapsed else "Hide  (H)"
	_panel.anchor_bottom = 0.0 if collapsed else 1.0
	_panel.offset_bottom = _panel.offset_top if collapsed else -16.0


func _place_toggle() -> void:
	var bar: Control = main.hud.sidebar
	_toggle.position = Vector2(bar.position.x + 2, bar.position.y + bar.size.y + 10)


func is_open() -> bool:
	return _panel.visible


func open(k := 0) -> void:
	_panel.visible = true
	_toggle.text = "CLOSE EDITOR  (I)"
	main.hud.visible = false
	main.hud.set_speed(0)
	_clear_sky(true)
	_refresh_picker()
	_select(clampi(k, 0, main.layout.islands.size() - 1), false)


func close() -> void:
	_panel.visible = false
	_set_placing(-1)
	_marker.visible = false
	_toggle.text = "ISLANDS  (I)"
	main.hud.visible = true
	_clear_sky(false)


## No clouds, cloud shadows or haze while editing, so the islands are easy to see.
func _clear_sky(on: bool) -> void:
	main.clouds.set_shown(not on and main.hud.map_controls.weather_shown)
	main.env.volumetric_fog_enabled = not on


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match (event as InputEventKey).physical_keycode:
		KEY_I:
			_toggle_open()
			get_viewport().set_input_as_handled()
		KEY_H:
			if is_open():
				_toggle_collapsed()
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
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 6)
	_panel.add_child(outer)
	var header := HBoxContainer.new()
	var title := _label("ISLAND EDITOR", 17, Hud.TEXT)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	_fold = _button("Hide  (H)", _toggle_collapsed)
	_fold.tooltip_text = "Fold the editor down to this bar to see more of the map."
	header.add_child(_fold)
	outer.add_child(header)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(scroll)
	_body = scroll
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 6)
	scroll.add_child(v)

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
	_mainland = CheckBox.new()
	_mainland.text = "Mainland"
	_mainland.tooltip_text = "Joins it to the mainland's coast, as a mainland port."
	_mainland.toggled.connect(func(on):
		if not _syncing:
			_spec().mainland = on
			_mark_unsaved()
			_reroll_position())
	nm.add_child(_name)
	nm.add_child(_mainland)
	nm.add_child(_pinned)
	v.add_child(nm)

	_section(v, "SHAPE", SHAPE)
	_row_buttons(v, [["🎲 New coastline", func(): _set_value("shape_seed", _rng.randi_range(1, 99999))],
		["🎲 Reroll shape", _reroll_shape]])
	_section(v, "POSITION", PLACE)
	_row_buttons(v, [["🎲 Reroll position", _reroll_position]])
	_build_dock_section(v)
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
	if k != selected:
		_dock = 0
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
	_mainland.button_pressed = s.mainland
	_sync_dock()
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
	if _placing >= 0:
		var w := o + d * (-o.y / d.y)
		_place_dock(Vector2(w.x, w.z))
		return
	var p := o + d * ((20.0 - o.y) / d.y)
	var k: int = main.terrain.island_at(p.x, p.z) - _first_id()
	if k >= 0 and k < main.layout.islands.size():
		_select(k, false)


# --- Ferry docks ------------------------------------------------------------------

func _build_dock_section(v: VBoxContainer) -> void:
	v.add_child(_label("FERRY DOCKS", 12, Hud.ACCENT))
	_dock_info = _label("", 12, Hud.MUTED)
	_dock_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_dock_info)
	var pick := HBoxContainer.new()
	_dock_pick = OptionButton.new()
	_dock_pick.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_dock_pick.item_selected.connect(func(i):
		if _syncing:
			return
		_dock = i
		_set_placing(false)
		_sync_dock())
	pick.add_child(_dock_pick)
	_tier = OptionButton.new()
	for t in MapLayout.DOCK_TIER_ORDER:
		_tier.add_item("%s · $%s" % [MapLayout.DOCK_TIERS[t]["name"], String.num_int64(MapLayout.dock_price(t))])
	_tier.tooltip_text = "What this site costs to build in play (MapLayout.DOCK_TIERS)."
	_tier.item_selected.connect(func(i):
		var d := _cur_dock()
		if _syncing or d == null:
			return
		d.tier = MapLayout.DOCK_TIER_ORDER[i]
		_dock_changed())
	pick.add_child(_tier)
	v.add_child(pick)
	var row := HBoxContainer.new()
	row.add_child(_fixed_label("Facing", 108))
	_facing = HSlider.new()
	_facing.min_value = 0
	_facing.max_value = 359
	_facing.step = 1
	_facing.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_facing.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_facing_val = _fixed_label("", 64)
	_facing_val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_facing.value_changed.connect(func(x):
		_facing_val.text = "%d°" % int(x)
		var d := _cur_dock()
		if _syncing or d == null:
			return
		# Turned in place: the pier meets the shore again along its new heading.
		var s := _spec()
		var dir := Vector2.from_angle(deg_to_rad(x))
		var shore := MapGenerator.snap_shore(main.terrain, s.dock_at(d), dir)
		var nd := s.dock_from_world(Vector2(shore.x, shore.z), x, d.tier)
		d.u = nd.u
		d.v = nd.v
		d.facing = nd.facing
		_dock_changed())
	row.add_child(_facing)
	row.add_child(_facing_val)
	v.add_child(row)
	_dock_btn = _button("📍 Add dock", func(): _set_placing(0 if _placing != 0 else -1))
	_move_btn = _button("Move", func(): _set_placing(1 if _placing != 1 else -1))
	_del_btn = _button("Remove", _remove_dock)
	_row_buttons(v, [], [_dock_btn, _move_btn, _del_btn])
	_ferry = CheckBox.new()
	_ferry.text = "Terminal in the full network"
	_ferry.tooltip_text = "With --full-network (no scenario), build a terminal at this island's first dock."
	_ferry.toggled.connect(func(on):
		if _syncing:
			return
		_spec().ferry = on
		_dock_changed())
	v.add_child(_ferry)


func _cur_dock() -> MapLayout.DockSpec:
	var s := _spec()
	return s.docks[_dock] if _dock >= 0 and _dock < s.docks.size() else null


func _sync_dock() -> void:
	var s := _spec()
	_dock = clampi(_dock, 0, s.docks.size() - 1) if not s.docks.is_empty() else -1
	_ferry.button_pressed = s.ferry
	_dock_pick.clear()
	for i in s.docks.size():
		_dock_pick.add_item("Dock %d%s" % [i + 1, "  ⚠" if not _on_shore(s, s.docks[i]) else ""])
	if s.docks.is_empty():
		_dock_pick.add_item("No docks")
	_dock_pick.select(maxi(_dock, 0))
	_dock_pick.disabled = s.docks.is_empty()
	var d := _cur_dock()
	_tier.disabled = d == null
	_facing.editable = d != null
	_move_btn.disabled = d == null
	_del_btn.disabled = d == null
	if d == null:
		_facing_val.text = "—"
		_dock_info.text = "No dock locked here, so no terminal can ever be built on this island. Add dock, then click by the shore."
	else:
		var heading := fposmod(rad_to_deg(s.dock_heading(d).angle()), 360.0)
		_facing.value = roundf(heading)
		_facing_val.text = "%d°" % int(roundf(heading))
		_tier.select(MapLayout.DOCK_TIER_ORDER.find(d.tier))
		var at := s.dock_at(d)
		_dock_info.text = "%d dock%s locked here; a terminal can only be built at one. Dock %d is at %d, %d and moves with the island." % [
			s.docks.size(), "" if s.docks.size() == 1 else "s", _dock + 1, int(at.x), int(at.y)]
		if not _on_shore(s, d):
			_dock_info.text += " ⚠ It no longer meets the shore: Move it."
		if _dock_dirty or _stale:
			_dock_info.text += " Apply to rebuild the routes."
	_update_marker()


## The pier meets the shore: land just behind it, water just ahead.
func _on_shore(s: MapLayout.IslandSpec, d: MapLayout.DockSpec) -> bool:
	var at := s.dock_at(d)
	var dir := s.dock_heading(d)
	var behind := at - dir * 6.0
	var ahead := at + dir * 6.0
	return main.terrain.height_at(behind.x, behind.y) >= 0.9 and main.terrain.height_at(ahead.x, ahead.y) < 0.9


## -1 off, 0 adding a dock, 1 moving the selected one.
func _set_placing(mode: int) -> void:
	_placing = mode
	if _dock_btn:
		_dock_btn.text = "Click the shore… (cancel)" if mode == 0 else "📍 Add dock"
		_move_btn.text = "Click… (cancel)" if mode == 1 else "Move"


func _place_dock(at: Vector2) -> void:
	var s := _spec()
	var dir := MapGenerator.seaward(main.terrain, at)
	var heading := roundf(fposmod(rad_to_deg(dir.angle()), 360.0))
	dir = Vector2.from_angle(deg_to_rad(heading))
	var shore := MapGenerator.snap_shore(main.terrain, at, dir)
	var old := _cur_dock()
	var d := s.dock_from_world(Vector2(shore.x, shore.z), heading, old.tier if old and _placing == 1 else "standard")
	if _placing == 1 and old:
		s.docks[_dock] = d
	else:
		s.docks.append(d)
		_dock = s.docks.size() - 1
	_set_placing(-1)
	_dock_changed()


func _remove_dock() -> void:
	_set_placing(-1)
	var s := _spec()
	if _cur_dock() == null:
		return
	s.docks.remove_at(_dock)
	_dock = mini(_dock, s.docks.size() - 1)
	_dock_changed()


func _dock_changed() -> void:
	_dock_dirty = true
	_syncing = true
	_sync_dock()
	_syncing = false
	_mark_unsaved()


## A pole where each pier meets the shore and a bar out along it: the selected
## dock orange, the island's others white.
func _build_marker() -> void:
	_marker = Node3D.new()
	_marker.visible = false
	add_child(_marker)


func _marker_for(color: Color) -> Node3D:
	var n := Node3D.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = color
	var pole := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 6.0
	cm.bottom_radius = 6.0
	cm.height = 90.0
	pole.mesh = cm
	pole.position = Vector3(0, 45, 0)
	pole.material_override = mat
	n.add_child(pole)
	var bar := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(10, 6, Layout.DOCK_U + 60.0)
	bar.mesh = bm
	bar.position = Vector3(0, 6, bm.size.z * 0.5)
	bar.material_override = mat
	n.add_child(bar)
	return n


func _update_marker() -> void:
	for c in _marker.get_children():
		c.queue_free()
	var s := _spec()
	_marker.visible = is_open()
	if not _marker.visible:
		return
	for i in s.docks.size():
		var d := s.docks[i]
		var m := _marker_for(Color(1.0, 0.45, 0.1) if i == _dock else Color(0.95, 0.95, 0.9))
		var dir := s.dock_heading(d)
		var at := s.dock_at(d)
		var d3 := Vector3(dir.x, 0.0, dir.y)
		m.transform = Transform3D(Basis(Vector3.UP.cross(d3), Vector3.UP, d3), Vector3(at.x, 0.0, at.y))
		_marker.add_child(m)


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
	_update_marker()
	_go_stale()


## Hides everything built on the old ground until the map is rebuilt.
func _go_stale() -> void:
	if _stale:
		return
	_stale = true
	for c in main.builder.root.get_children():
		if not (str(c.name).begins_with("Terrain_") or c.name in ["Water", "WaterRing", "SeaFloor"]):
			c.visible = false
	for c in main.get_children():
		# The islands' woods are gone until Apply, so the mainland's lose theirs too.
		if c is Backdrop:
			(c as Backdrop).show_near_trees(false)
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
	# The mainland moved: mainland ports go with it.
	for s in main.layout.islands:
		if s.mainland:
			MapGenerator.roll_position(main.layout, s, _rng)
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
