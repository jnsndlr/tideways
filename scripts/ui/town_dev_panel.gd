class_name TownDevPanel
extends CanvasLayer
## Sandbox dev tool (F7): pick a town, drag its population up, and watch it grow.
## "Plan" draws the town's roads and numbers its growth lots in the order
## TownGrowth claims them (green = built, amber = free). Tuning aid for the
## town layout work in docs/town-layout-plan.md; not part of the player UI.

const MAX_POP := 20000

var sim: Simulation
var rig: CameraRig

var _panel: PanelContainer
var _towns: OptionButton
var _slider: HSlider
var _pop_label: Label
var _info: Label
var _overlay_toggle: CheckBox
var _fast_toggle: CheckBox
var _plan_toggle: CheckBox
var _overlay: Node3D
var _town: MapData.Town
var _refresh := 0.0


func setup(simulation: Simulation, camera_rig: CameraRig) -> void:
	sim = simulation
	rig = camera_rig
	layer = 20
	_build_ui()
	_panel.visible = false
	_overlay = Node3D.new()
	_overlay.name = "TownPlanOverlay"
	_overlay.visible = false
	sim.get_parent().add_child(_overlay)
	for t in sim.map.towns:
		_towns.add_item("%s (%s)" % [t.name, t.key])
	if not sim.map.towns.is_empty():
		_select(0)
	sim.town_growth.population_changed.connect(func(t: MapData.Town, _p: int) -> void:
		if t == _town:
			_sync_slider())


func _unhandled_input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k and k.pressed and not k.echo and k.physical_keycode == KEY_F7:
		_panel.visible = not _panel.visible
		_overlay.visible = _panel.visible and _overlay_toggle.button_pressed
		get_viewport().set_input_as_handled()


func _process(delta: float) -> void:
	if not _panel.visible or _town == null:
		return
	_refresh -= delta
	if _refresh <= 0.0:
		_refresh = 0.5
		_update_info()
		if _overlay.visible:
			_draw_overlay()


func _build_ui() -> void:
	_panel = PanelContainer.new()
	_panel.position = Vector2(16, 120)
	_panel.custom_minimum_size = Vector2(340, 0)
	add_child(_panel)
	var box := VBoxContainer.new()
	_panel.add_child(box)
	var title := Label.new()
	title.text = "Town growth (dev, F7)"
	box.add_child(title)
	_towns = OptionButton.new()
	_towns.item_selected.connect(_select)
	box.add_child(_towns)
	_pop_label = Label.new()
	box.add_child(_pop_label)
	_slider = HSlider.new()
	_slider.min_value = 0
	_slider.max_value = MAX_POP
	_slider.step = 25
	_slider.custom_minimum_size = Vector2(320, 24)
	_slider.drag_ended.connect(func(_changed: bool) -> void: _apply_slider())
	_slider.value_changed.connect(func(v: float) -> void: _pop_label.text = "Population → %d" % int(v))
	box.add_child(_slider)
	var row := HBoxContainer.new()
	box.add_child(row)
	for step: int in [100, 500, 2000]:
		var b := Button.new()
		b.text = "+%d" % step
		b.pressed.connect(func() -> void:
			_slider.value = mini(MAX_POP, _town.population + step)
			_apply_slider())
		row.add_child(b)
	var go := Button.new()
	go.text = "Go to"
	go.pressed.connect(_focus)
	row.add_child(go)
	_fast_toggle = CheckBox.new()
	_fast_toggle.text = "Fast builds (×40, 8 at once)"
	_fast_toggle.toggled.connect(func(on: bool) -> void:
		sim.town_growth.dev_build_speed = 40.0 if on else 1.0
		sim.town_growth.dev_max_builds = 8 if on else TownGrowth.MAX_CONCURRENT_BUILDS)
	box.add_child(_fast_toggle)
	_overlay_toggle = CheckBox.new()
	_overlay_toggle.text = "Show plan (roads, lot order)"
	_overlay_toggle.toggled.connect(func(on: bool) -> void:
		_overlay.visible = on
		if on:
			_draw_overlay())
	box.add_child(_overlay_toggle)
	_info = Label.new()
	box.add_child(_info)


func _select(i: int) -> void:
	_town = sim.map.towns[i]
	_sync_slider()
	_update_info()
	if _overlay and _overlay.visible:
		_draw_overlay()


func _sync_slider() -> void:
	_slider.set_value_no_signal(_town.population)
	_pop_label.text = "Population %d" % _town.population


func _apply_slider() -> void:
	sim.town_growth.dev_set_population(_town, int(_slider.value))
	_sync_slider()
	_update_info()


func _focus() -> void:
	rig.target_pos = Vector3(_town.town_center.x, 0, _town.town_center.z)
	rig.target_dist = minf(rig.target_dist, 420.0)


func _update_info() -> void:
	var built := {}
	var free := {}
	for lot in _town.growth_lots:
		var d: Dictionary = built if lot.occupied else free
		d[lot.kind] = int(d.get(lot.kind, 0)) + 1
	var st: TownGrowth.TownState = sim.town_growth.states.get(_town.id)
	var names := MapData.TownLot.Kind.keys()
	var lines: Array[String] = []
	for k in names.size():
		lines.append("%s  built %d  free %d" % [names[k].capitalize(), built.get(k, 0), free.get(k, 0)])
	lines.append("Wants %d houses, %d commercial" % [TownGrowth.target_houses_for(_town.population),
		TownGrowth.target_commercial_for(_town.population)])
	if st:
		lines.append("Building now: %d" % st.active_builds.size())
	_info.text = "\n".join(lines)


## Roads as thin lines, each lot as a numbered marker in claim order per kind.
func _draw_overlay() -> void:
	for c in _overlay.get_children():
		c.queue_free()
	if _town == null:
		return
	var im := ImmediateMesh.new()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	mat.no_depth_test = true
	im.surface_begin(Mesh.PRIMITIVE_LINES, mat)
	var lines: Array[PackedVector3Array] = [_town.road_main_a, _town.road_main_b]
	lines.append_array(_town.road_cross)
	lines.append_array(_town.road_lanes)
	for line in lines:
		for i in line.size() - 1:
			im.surface_set_color(Color(0.3, 0.7, 1.0))
			im.surface_add_vertex(line[i] + Vector3.UP * 1.5)
			im.surface_set_color(Color(0.3, 0.7, 1.0))
			im.surface_add_vertex(line[i + 1] + Vector3.UP * 1.5)
	var plan := _town.street_plan
	if plan and (_plan_toggle == null or _plan_toggle.button_pressed):
		var zc := [Color(1, 0.3, 0.3), Color(1, 0.9, 0.2), Color(0.8, 0.4, 1), Color(1, 1, 1)]
		for e in plan.edges:
			var pts: PackedVector3Array = e.pts
			for i in pts.size() - 1:
				im.surface_set_color(zc[e.zone])
				im.surface_add_vertex(pts[i] + Vector3.UP * 2.5)
				im.surface_set_color(zc[e.zone])
				im.surface_add_vertex(pts[i + 1] + Vector3.UP * 2.5)
		for n in plan.nodes:
			im.surface_set_color(Color.WHITE)
			im.surface_add_vertex(n)
			im.surface_set_color(Color.WHITE)
			im.surface_add_vertex(n + Vector3.UP * 8.0)
	var order := {}
	for lot in _town.growth_lots:
		var n := int(order.get(lot.kind, 0)) + 1
		order[lot.kind] = n
		var col := Color(0.4, 1.0, 0.4) if lot.occupied else Color(1.0, 0.7, 0.2)
		var p := Vector3(lot.pos.x, lot.lot_y, lot.pos.z)
		im.surface_set_color(col)
		im.surface_add_vertex(p)
		im.surface_set_color(col)
		im.surface_add_vertex(p + Vector3.UP * 12.0)
		var label := Label3D.new()
		label.text = "%s%d" % ["HCLR"[lot.kind], n]
		label.modulate = col
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.fixed_size = true
		label.pixel_size = 0.0012
		label.position = p + Vector3.UP * 13.0
		_overlay.add_child(label)
	im.surface_end()
	var mi := MeshInstance3D.new()
	mi.mesh = im
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_overlay.add_child(mi)
