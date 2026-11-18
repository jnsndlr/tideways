class_name WeatherWidget
extends Control
## The illustrated sky at the top of the map controls: sun or moon, cloud for the
## current weather, and the temperature beneath. It only reads the weather. A tap
## asks to hide or restore the map's weather effects and a drag asks to move the
## group; MapControls owns both answers.

signal tapped
## Total offset from where the press began, in canvas units.
signal drag_moved(offset: Vector2)
signal drag_ended

const ART := Vector2(88, 88)
const DRAG_START := 10.0     # a press that travels further than this is a drag
const FLASH_MSEC := 280.0    # tap feedback: a brief ring, not a lasting outline
const TEXT := Color(0.9, 0.94, 0.95)
const MUTED := Color(0.58, 0.66, 0.68)

var sim: Simulation
var day_cycle: DayCycle
var font: Font
var bold: Font
## Whether the map is drawing its weather. The sky here keeps showing conditions.
var effects_shown := true:
	set(on):
		effects_shown = on
		queue_redraw()

var _pressed := false
var _dragging := false
var _press_at := Vector2.ZERO
var _flash_at := -100000
var _drawn := ""
var _card := StyleBoxFlat.new()
var _ring := StyleBoxFlat.new()


func setup(s: Simulation, cycle: DayCycle, regular: Font, heavy: Font) -> void:
	sim = s
	day_cycle = cycle
	font = regular
	bold = heavy
	custom_minimum_size = ART + Vector2(8, 38)
	mouse_filter = Control.MOUSE_FILTER_STOP
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	tooltip_text = "Weather"
	_card.set_corner_radius_all(14)
	_card.border_color = Color(1, 1, 1, 0.14)
	_card.set_border_width_all(1)
	_ring.draw_center = false
	_ring.set_corner_radius_all(14)
	_ring.set_border_width_all(3)


## 0 at night .. 1 by day, following the lighting (so a pinned time of day shows too).
func daylight() -> float:
	var h := day_cycle.hour()
	return smoothstep(DayCycle.SUNRISE - 0.5, DayCycle.SUNRISE + 0.5, h) \
		* (1.0 - smoothstep(DayCycle.SUNSET - 0.5, DayCycle.SUNSET + 0.5, h))


func _process(_delta: float) -> void:
	# Real time, so the ring still fades while the game is paused.
	if Time.get_ticks_msec() - _flash_at < FLASH_MSEC + 50.0:
		queue_redraw()
		return
	var state := "%s %d %d %s" % [sim.weather.label(), roundi(daylight() * 8.0), sim.temperature(), effects_shown]
	if state != _drawn:
		_drawn = state
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
			if _dragging:
				_dragging = false
				drag_ended.emit()
			else:
				_flash_at = Time.get_ticks_msec()
				tapped.emit()
		accept_event()
	elif event is InputEventMouseMotion and _pressed:
		var offset := _on_canvas((event as InputEventMouseMotion).position) - _press_at
		if not _dragging and offset.length() > DRAG_START:
			_dragging = true
		if _dragging:
			drag_moved.emit(offset)
		accept_event()
	elif event is InputEventScreenTouch or event is InputEventScreenDrag:
		# The finger is on this control: keep it from the camera underneath.
		accept_event()


## A point on this control in canvas coordinates. The control moves under the
## finger during a drag, so its own coordinates can't measure one.
func _on_canvas(local: Vector2) -> Vector2:
	return get_global_transform_with_canvas() * local


func _draw() -> void:
	var weather := sim.weather
	var art := Rect2(Vector2((size.x - ART.x) * 0.5, 0.0), ART)
	var day := daylight()
	var cover := weather.coverage
	var grey := smoothstep(0.4, 0.7, cover)
	var sky_day := Color(0.33, 0.63, 0.92).lerp(Color(0.56, 0.63, 0.69), grey).lerp(Color(0.27, 0.3, 0.36), weather.storm)
	var sky_night := Color(0.05, 0.08, 0.18).lerp(Color(0.1, 0.11, 0.15), grey)
	var sky := sky_night.lerp(sky_day, day)
	_card.bg_color = sky
	draw_style_box(_card, art)

	# Sun or moon, lost behind a full overcast.
	var clear := 1.0 - smoothstep(0.55, 0.72, cover)
	var disc := art.position + Vector2(31, 32)
	if day > 0.5:
		var sun := Color(1.0, 0.83, 0.3, clear)
		draw_circle(disc, 14.0, sun)
		for k in 8:
			var dir := Vector2.from_angle(k * TAU / 8.0)
			draw_line(disc + dir * 18.5, disc + dir * 24.0, sun, 2.5, true)
	else:
		if cover < 0.5:
			for star: Vector2 in [Vector2(62, 16), Vector2(74, 34), Vector2(52, 40), Vector2(14, 60), Vector2(70, 66)]:
				draw_circle(art.position + star, 1.3, Color(1, 1, 1, 0.8 * clear))
		draw_circle(disc, 13.0, Color(0.94, 0.93, 0.84, clear))
		draw_circle(disc + Vector2(6.5, -4.5), 11.0, Color(sky, clear))

	var cloud := Color(0.55, 0.6, 0.7).lerp(Color(0.97, 0.98, 1.0), day)
	cloud = cloud.lerp(Color(0.26, 0.28, 0.33).lerp(Color(0.45, 0.48, 0.53), day), weather.storm)
	var back := cloud.darkened(0.14)
	var o := art.position
	match weather.label():
		"Few Clouds":
			_cloud(o + Vector2(58, 60), 0.72, cloud)
		"Partly Cloudy":
			_cloud(o + Vector2(52, 56), 1.0, cloud)
		"Mostly Cloudy":
			_cloud(o + Vector2(36, 40), 0.85, back)
			_cloud(o + Vector2(53, 58), 1.05, cloud)
		"Overcast", "Storm":
			_cloud(o + Vector2(30, 34), 0.95, back)
			_cloud(o + Vector2(60, 40), 0.9, back)
			_cloud(o + Vector2(44, 56), 1.2, cloud)
	if weather.storm > 0.5:
		for k in 4:
			var top := o + Vector2(28.0 + k * 11.0, 70.0)
			draw_line(top, top + Vector2(-4.0, 10.0), Color(0.62, 0.78, 0.98), 2.0, true)

	if not effects_shown:
		_card.bg_color = Color(0.05, 0.08, 0.1, 0.6)
		draw_style_box(_card, art)
		draw_line(art.position + Vector2(18, 70), art.position + Vector2(70, 18), TEXT, 3.5, true)

	var flash := 1.0 - (Time.get_ticks_msec() - _flash_at) / FLASH_MSEC
	if flash > 0.0:
		_ring.border_color = Color(1, 1, 1, flash * 0.9)
		draw_style_box(_ring, art)

	draw_string(bold, Vector2(0, ART.y + 18.0), "%d°C" % sim.temperature(),
		HORIZONTAL_ALIGNMENT_CENTER, size.x, 15, TEXT)
	draw_string(font, Vector2(0, ART.y + 32.0), weather.label() if effects_shown else "Weather hidden",
		HORIZONTAL_ALIGNMENT_CENTER, size.x, 10, MUTED)


## A flat-bottomed cumulus about 46 wide at scale 1, centred a little above its base.
func _cloud(at: Vector2, s: float, col: Color) -> void:
	draw_circle(at + Vector2(-13, 0) * s, 9.0 * s, col)
	draw_circle(at + Vector2(0, -6) * s, 13.0 * s, col)
	draw_circle(at + Vector2(13, -1) * s, 10.0 * s, col)
	draw_rect(Rect2(at + Vector2(-13, 0) * s, Vector2(26, 9) * s), col)
