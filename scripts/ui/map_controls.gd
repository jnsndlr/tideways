class_name MapControls
extends PanelContainer
## The weather widget at the screen edge. The sidebar's WEATHER button opens or
## collapses it; the pin on the widget keeps it open (and open next session).
## Unpinned, it tucks away again when the player opens another panel or clicks
## the map. Which map layers show lives in Settings (GameSettings), not here.
##
## It rests against the left or right edge, part-way down, for the session. A drag
## on the illustration picks the edge and the height.

signal weather_toggled(shown: bool)

const GAP := 8.0
## Map layer id -> GameSettings flag.
const LAYER_FLAGS := {"routes": "show_routes", "names": "show_names", "areas": "show_areas"}

var widget := WeatherWidget.new()
var weather_shown := true
var pinned := false
## The screen edge it rests against (1 right, -1 left) and how far down that edge
## (0 top .. 1 bottom).
var side := 1
var fraction := 0.45

var _grab_y := 0.0
var _bounds := Rect2()
var _obstacles: Array[Rect2] = []


func setup(sim: Simulation, day_cycle: DayCycle, font: Font) -> void:
	widget.setup(sim, day_cycle, font)
	widget.tapped.connect(func() -> void: set_weather_shown(not weather_shown))
	widget.pin_tapped.connect(func() -> void: set_pinned(not pinned))
	widget.drag_started.connect(func(point: Vector2) -> void: _grab_y = point.y - position.y)
	widget.drag_moved.connect(_on_drag_moved)
	add_child(widget)
	pinned = GameSettings.flag("weather_pinned")
	widget.pinned = pinned
	visible = pinned


## Whether the player wants this map layer drawn (Settings > Map).
static func shows(layer: String) -> bool:
	return GameSettings.flag(LAYER_FLAGS[layer]) if LAYER_FLAGS.has(layer) else false


## The sidebar button: open it, or collapse it (which also unpins it).
func toggle_open() -> void:
	if visible:
		visible = false
		set_pinned(false)
	else:
		visible = true


## Collapses it unless pinned, when the player turns their attention elsewhere.
func dismiss() -> void:
	if not pinned:
		visible = false


func set_pinned(on: bool) -> void:
	pinned = on
	widget.pinned = on
	GameSettings.set_flag("weather_pinned", on)


func set_weather_shown(on: bool) -> void:
	if weather_shown == on:
		return
	weather_shown = on
	widget.effects_shown = on
	weather_toggled.emit(on)


## Rests the group against its edge inside `bounds`, clear of `obstacles` (other HUD
## panels). It takes the clear height nearest the one the player chose; if that
## edge has none, it keeps its height and moves in beside whatever is in the way,
## so it stays on the side the player put it and within reach.
func place(bounds: Rect2, obstacles: Array[Rect2]) -> void:
	_bounds = bounds
	_obstacles = obstacles
	var room := maxf(0.0, bounds.size.y - size.y)
	var top := bounds.position.y
	var desired := top + fraction * room
	var x := bounds.end.x - size.x if side > 0 else bounds.position.x
	var heights: Array[float] = [desired]
	for o in obstacles:
		heights.append(o.position.y - GAP - size.y)
		heights.append(o.end.y + GAP)
	var best := INF
	var r := Rect2(Vector2(x, desired), size)
	for height in heights:
		var y := clampf(height, top, top + room)
		if absf(y - desired) < best and _is_clear(Rect2(Vector2(x, y), size), obstacles):
			best = absf(y - desired)
			r.position.y = y
	if best == INF:
		for attempt in 4:
			var clear := true
			for o in obstacles:
				var keep := o.grow(GAP)
				if r.intersects(keep):
					r.position.x = keep.position.x - r.size.x if side > 0 else keep.end.x
					clear = false
			if clear:
				break
	position = r.position.clamp(bounds.position, (bounds.end - size).max(bounds.position))


func _is_clear(r: Rect2, obstacles: Array[Rect2]) -> bool:
	for o in obstacles:
		if r.intersects(o.grow(GAP - 0.5)):
			return false
	return true


## The group follows the finger: whichever edge is nearer, at the finger's height.
func _on_drag_moved(point: Vector2) -> void:
	side = 1 if point.x >= _bounds.get_center().x else -1
	fraction = clampf((point.y - _grab_y - _bounds.position.y) / maxf(1.0, _bounds.size.y - size.y), 0.0, 1.0)
	place(_bounds, _obstacles)
