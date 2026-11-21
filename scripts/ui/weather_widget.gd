class_name WeatherWidget
extends Control
## The miniature shoreline illustration at the top of the map controls, brought
## over from the Tideways 3D edge widget: a cut-paper sky, sun or moon, cloud for
## the current conditions, the temperature, and whether the map is showing its
## weather. It only reads the weather. A tap asks to hide or restore the map's
## weather effects and a drag asks to move the group; MapControls owns both answers.
##
## The slow drift, shimmer and twinkle are presentation only: they run on real
## time, a few redraws a second, whatever the game speed.

signal tapped
## The pin in the top-right corner was tapped.
signal pin_tapped
## A press turned into a drag. `point` is where the press began, on the canvas.
signal drag_started(point: Vector2)
signal drag_moved(point: Vector2)
signal drag_ended

## The drawing is laid out in these units and scaled to the control.
const ART_SIZE := Vector2(180, 166)
const FRAME_SIZE := Vector2(164, 150)
const FRAME_ORIGIN := Vector2(8, 12)
const GRIP_Y := 17.0
const SLOP := 8.0                # a press that travels further than this is a drag
const FEEDBACK_MSEC := 280.0     # a brief outline on release, never a lasting one
const REDRAW_MSEC := 80
const ACCENT := Color("a9e5cc")
const PIN_RADIUS := 14.0         # tap area around the pin, in control pixels

var sim: Simulation
var day_cycle: DayCycle
var font: Font
## Whether the map is drawing its weather. The illustration keeps showing conditions.
var effects_shown := true:
	set(on):
		effects_shown = on
		_refresh()

## Whether the widget stays open; drawn as a filled or hollow pin.
var pinned := false:
	set(on):
		pinned = on
		queue_redraw()

var _state := ""     # "clear", "cloudy" or "storm"
var _night := false
var _label := ""
var _temperature := ""
var _key: Array = []
var _time := 0.0
var _drawn_at := 0
var _feedback_at := -100000
var _pressed := false
var _dragging := false
var _press_at := Vector2.ZERO
var _sky_texture: ImageTexture
var _sky_key: Array = []
var _cloud_outline := PackedVector2Array()
var _panel := StyleBoxFlat.new()


func setup(s: Simulation, cycle: DayCycle, regular: Font) -> void:
	sim = s
	day_cycle = cycle
	font = regular
	custom_minimum_size = ART_SIZE
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_panel.bg_color = Color("173740")
	_panel.border_color = Color("c9c4ac")
	_panel.set_border_width_all(2)
	_panel.set_corner_radius_all(14)
	_panel.shadow_color = Color(0.015, 0.04, 0.05, 0.22)
	_panel.shadow_size = 2
	_panel.shadow_offset = Vector2(1, 2)
	_prepare_cloud()
	_refresh()


## Night once the sun is down, following the lighting (so a pinned time of day shows too).
func is_night() -> bool:
	var h := day_cycle.hour()
	return h < DayCycle.SUNRISE or h > DayCycle.SUNSET


func _process(_delta: float) -> void:
	_refresh()
	var now := Time.get_ticks_msec()
	if now - _drawn_at >= REDRAW_MSEC or now - _feedback_at < FEEDBACK_MSEC + 50.0:
		_drawn_at = now
		_time = fmod(now * 0.001, 120.0)
		queue_redraw()


## Picks up a change in the conditions. The shared weather has cloud cover and
## storm cloud but no rain or fog yet, so those scenes are not drawn here.
func _refresh() -> void:
	if sim == null:
		return
	var label := sim.weather.label()
	var state := "storm" if label == "Storm" else ("clear" if label in ["Clear", "Few Clouds"] else "cloudy")
	var night := is_night()
	var temperature := "%d°C" % sim.temperature()
	var key := [label, night, temperature, effects_shown]
	if key == _key:
		return
	_key = key
	_state = state
	_night = night
	_temperature = temperature
	_label = label
	if label == "Clear":
		_label = "Clear night" if night else "Clear skies"
	_prepare_sky()
	tooltip_text = "%s%s · %s. Tap to %s map weather; drag to move; pin to keep open." % [label, " at night" if night else "",
		"Weather shown" if effects_shown else "Map effects hidden", "hide" if effects_shown else "show"]
	queue_redraw()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index != MOUSE_BUTTON_LEFT:
			return
		if mb.pressed:
			_pressed = true
			_dragging = false
			_press_at = _on_canvas(mb.position)
		elif _pressed:
			_pressed = false
			_feedback_at = Time.get_ticks_msec()
			if _dragging:
				_dragging = false
				drag_ended.emit()
			elif mb.position.distance_to(_pin_center()) <= PIN_RADIUS:
				pin_tapped.emit()
			else:
				tapped.emit()
		accept_event()
	elif event is InputEventMouseMotion and _pressed:
		var point := _on_canvas((event as InputEventMouseMotion).position)
		if not _dragging and point.distance_to(_press_at) > SLOP:
			_dragging = true
			drag_started.emit(_press_at)
		if _dragging:
			drag_moved.emit(point)
		accept_event()
	elif event is InputEventScreenTouch or event is InputEventScreenDrag:
		# The finger is on this control: keep it from the camera underneath.
		accept_event()


func _pin_center() -> Vector2:
	return Vector2(size.x - 22.0 * size.x / ART_SIZE.x, GRIP_Y * size.y / ART_SIZE.y)


## A point on this control in canvas coordinates. The control moves under the
## finger during a drag, so its own coordinates can't measure one.
func _on_canvas(local: Vector2) -> Vector2:
	return get_global_transform_with_canvas() * local


func _frame_transform() -> void:
	draw_set_transform(FRAME_ORIGIN * size / ART_SIZE, 0.0, size / ART_SIZE)


## A flat cut-paper sheet: a few soft offset shadows under it and a lighter rim.
func _paper_shape(points: PackedVector2Array, color: Color, depth := 2.0) -> void:
	for layer in range(3, 0, -1):
		var shadow := PackedVector2Array()
		for point in points:
			shadow.append(point + Vector2(depth * 0.45, depth + layer * 0.5))
		draw_colored_polygon(shadow, Color(0.025, 0.07, 0.09, 0.045))
	draw_colored_polygon(points, color)
	var rim := points.duplicate()
	rim.append(points[0])
	draw_polyline(rim, color.lightened(0.12), 0.5, true)


func _sky_top() -> Color:
	return Color("17354f") if _night else (Color("5293b4") if _state == "clear" else Color("526e82"))


func _sky_horizon() -> Color:
	return Color("526c87") if _night else (Color("e5d9b2") if _state == "clear" else Color("a6b9b8"))


## A small grained gradient, rebuilt only when the conditions or day and night change.
## Soft corner coverage keeps the sky inside the frame's rounded corners.
func _prepare_sky() -> void:
	var key := [_state == "clear", _night]
	if key == _sky_key:
		return
	_sky_key = key
	var top := _sky_top()
	var horizon := _sky_horizon()
	var image := Image.create(150, 96, false, Image.FORMAT_RGBA8)
	for y in 96:
		var row := top.lerp(horizon, minf(1.0, y / 85.0))
		for x in 150:
			var grain := (fposmod(sin(x * 12.9898 + y * 78.233) * 43758.5453, 1.0) - 0.5) * 0.035
			var color := Color(row.r + grain, row.g + grain, row.b + grain, row.a)
			if y < 10 and (x < 10 or x > 139):
				var center := Vector2(10 if x < 10 else 140, 10)
				color.a = clampf(10.5 - Vector2(x + 0.5, y + 0.5).distance_to(center), 0.0, 1.0)
			image.set_pixel(x, y, color)
	_sky_texture = ImageTexture.create_from_image(image)


func _prepare_cloud() -> void:
	var corners := PackedVector2Array([Vector2(-43, 9), Vector2(-46, 2), Vector2(-40, -6), Vector2(-29, -8),
		Vector2(-23, -17), Vector2(-11, -20), Vector2(0, -16), Vector2(12, -20), Vector2(27, -16), Vector2(32, -8),
		Vector2(43, -5), Vector2(47, 3), Vector2(41, 10), Vector2(23, 12), Vector2(1, 11), Vector2(-20, 12)])
	var curve := Curve2D.new()
	curve.bake_interval = 1.5
	for i in corners.size() + 1:
		var index := i % corners.size()
		var tangent := (corners[(index + 1) % corners.size()] - corners[posmod(index - 1, corners.size())]) * 0.16
		curve.add_point(corners[index], -tangent, tangent)
	_cloud_outline = curve.get_baked_points()


func _cloud(center: Vector2, scale_factor: float, color: Color) -> void:
	var points := PackedVector2Array()
	for point in _cloud_outline:
		points.append(center + point * scale_factor)
	_paper_shape(points, color, 3.5 * scale_factor)
	# A thin offset backing sheet gives a cut-paper edge instead of shaded puffs.
	var lower_edge := PackedVector2Array()
	for point in points:
		lower_edge.append(point + Vector2(0, 0.8))
	lower_edge.append(lower_edge[0])
	draw_polyline(lower_edge, color.lightened(0.2), 0.75, true)


func _pine(x: float, y: float, height: float, color: Color) -> void:
	draw_line(Vector2(x, y - height), Vector2(x, y), color, 2.0, true)
	for tier in 3:
		var top := y - height + height * tier * 0.22
		var width := height * (0.19 + tier * 0.055)
		_paper_shape(PackedVector2Array([Vector2(x, top), Vector2(x - width, top + height * 0.45),
			Vector2(x + width, top + height * 0.45)]), color, 1.2)


func _draw() -> void:
	_frame_transform()
	draw_style_box(_panel, Rect2(Vector2.ZERO, FRAME_SIZE))
	if _sky_texture != null:
		draw_texture_rect(_sky_texture, Rect2(7, 8, 150, 96), false)
	var celestial := Vector2(119, 32)
	if _night:
		for i in 13:
			var star := Vector2(17 + fmod(i * 37.7, 130.0), 15 + fmod(i * 19.3, 46.0))
			draw_circle(star, 0.7, Color(0.85, 0.94, 1, 0.45 + 0.2 * sin(_time * TAU / 10.0 + i)))
		for glow in range(4, 0, -1):
			draw_circle(celestial, 10 + glow * 3, Color(0.8, 0.87, 1, 0.025))
		draw_circle(celestial, 9.0, Color("efe9cb"))
		# A half-lit moon: the shared weather has no moon phase yet.
		draw_circle(celestial + Vector2(-9, 0), 9.0, _sky_top().lerp(_sky_horizon(), 24.0 / 85.0), true, -1.0, true)
	else:
		for glow in range(5, 0, -1):
			draw_circle(celestial, 10 + glow * 3, Color(1, 0.85, 0.5, 0.035))
		draw_circle(celestial, 10.0, Color("ffe8a6"))
		draw_circle(celestial + Vector2(-2, -2), 7.0, Color("fff2c7"))
	var cloud_color := Color("6c7f96") if _night else (Color("879ba5") if _state == "storm" else Color("d7e0dc"))
	var drift := sin(_time * TAU / 60.0) * 6.0
	_cloud(Vector2(42 + drift, 25), 0.68, cloud_color.lightened(0.13))
	if _state == "clear":
		_cloud(Vector2(71 - drift, 49), 0.38, cloud_color)
	else:
		_cloud(Vector2(103 - drift, 36), 0.95, cloud_color)
		_cloud(Vector2(34 + drift, 45), 0.72, cloud_color.darkened(0.12))
	# Layered rocky shore silhouettes, deliberately asymmetric.
	_paper_shape(PackedVector2Array([Vector2(7, 77), Vector2(20, 68), Vector2(33, 70), Vector2(49, 57), Vector2(61, 62),
		Vector2(77, 75), Vector2(98, 78), Vector2(157, 76), Vector2(157, 100), Vector2(7, 100)]),
		Color("344d65") if _night else Color("617e83"))
	var water := Color("203d55") if _night else Color("366877")
	# Three separate paper water planes, each casting a small shadow.
	for plane in 3:
		var points := PackedVector2Array()
		var y := 79 + plane * 8
		for i in 16:
			points.append(Vector2(7 + i * 10, y + sin(i * 0.7 + plane) * 1.2))
		points.append(Vector2(157, 104))
		points.append(Vector2(7, 104))
		_paper_shape(points, water.lerp(Color("173e4c"), plane / 3.0), 1.3)
	for i in 17:
		var x := 47 + fmod(i * 31.7, 106.0)
		var y := 82 + fmod(i * 11.3, 20.0)
		var shimmer := 0.12 + 0.1 * sin(_time * TAU / 4.0 + i * 2)
		draw_line(Vector2(x, y), Vector2(minf(155.0, x + 5 + fmod(i * 3, 12.0)), y), Color(0.81, 0.91, 0.84, shimmer), 1.0, true)
	_paper_shape(PackedVector2Array([Vector2(7, 82), Vector2(22, 74), Vector2(34, 77), Vector2(43, 86), Vector2(59, 91),
		Vector2(69, 103), Vector2(7, 103)]), Color("172e40") if _night else Color("284e53"))
	_paper_shape(PackedVector2Array([Vector2(7, 90), Vector2(21, 84), Vector2(29, 86), Vector2(25, 95), Vector2(45, 98),
		Vector2(51, 103), Vector2(7, 103)]), Color("243c4b") if _night else Color("426869"))
	draw_polyline(PackedVector2Array([Vector2(8, 89), Vector2(20, 84), Vector2(28, 86)]),
		Color("45596a") if _night else Color("8c9a80"), 1.0, true)
	for tree: Vector3 in [Vector3(14, 85, 29), Vector3(27, 88, 36), Vector3(39, 94, 24)]:
		_pine(tree.x, tree.y, tree.z, Color("102936") if _night else Color("183e42"))
	# The words sit on a quiet solid base, never on the moving scene.
	draw_line(Vector2(10, 105), Vector2(154, 105), Color("47706f"), 1.0, true)
	var temperature_width := font.get_string_size(_temperature, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
	# The longer condition names step down a size to keep clear of the temperature.
	var label_size := 15 if font.get_string_size(_label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x < 132.0 - temperature_width else 13
	draw_string(font, Vector2(12, 124), _label, HORIZONTAL_ALIGNMENT_LEFT, -1, label_size, Color("edf3e8"))
	draw_string(font, Vector2(152 - temperature_width, 124), _temperature, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color("d0dfd5"))
	draw_circle(Vector2(14, 138), 2.0, Color("95cbb3") if effects_shown else Color("e2bd79"))
	draw_string(font, Vector2(22, 142), "Weather shown" if effects_shown else "Map effects hidden",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color("abc8be") if effects_shown else Color("edcd91"))

	# Over the scene, in the control's own coordinates: the grip and tap feedback.
	draw_set_transform(Vector2.ZERO)
	for i in 3:
		draw_circle(Vector2(size.x * 0.5 - 5 + i * 5, GRIP_Y * size.y / ART_SIZE.y), 1.0, Color("a9c9c4"))
	_draw_pin(_pin_center())
	var feedback := 1.0 - (Time.get_ticks_msec() - _feedback_at) / FEEDBACK_MSEC
	if feedback > 0.0:
		draw_rect(Rect2(Vector2.ZERO, size), Color(ACCENT, feedback), false, 2.0)


## A small map pin on a disc that covers the frame's border: solid when pinned.
func _draw_pin(at: Vector2) -> void:
	draw_circle(at, 9.0, Color("173740"))
	draw_circle(at, 9.0, Color("c9c4ac"), false, 1.5, true)
	var col := ACCENT if pinned else Color("a9c9c4")
	draw_line(at + Vector2(0, 0), at + Vector2(0, 5.5), col, 1.5, true)
	if pinned:
		draw_circle(at + Vector2(0, -1.5), 3.5, col)
	else:
		draw_circle(at + Vector2(0, -1.5), 3.2, col, false, 1.3, true)
