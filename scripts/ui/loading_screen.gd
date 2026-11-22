class_name LoadingScreen
extends Control
## Little illustrated loading screen shown between the menu and a game mode.
##
## A dawn harbour scene drawn in code: a ferry crosses from one island's pier to
## the next, and how far it has sailed is the loading progress. The scene loads on
## a thread, then the screen stays up over the new scene until it has built its
## world, and fades out.

const SKY_TOP := Color(0.05, 0.09, 0.11)
const SKY_GLOW := Color(0.86, 0.56, 0.4)
const SEA_FAR := Color(0.2, 0.3, 0.34)
const SEA_NEAR := Color(0.03, 0.09, 0.12)
const ISLAND := Color(0.05, 0.11, 0.12)
const ISLAND_FAR := Color(0.33, 0.31, 0.34)
const SUN := Color(1.0, 0.8, 0.55)
const TEXT := Color(0.9, 0.94, 0.95)
const MUTED := Color(0.58, 0.66, 0.68)
const ACCENT := Color(0.47, 0.86, 0.6)

const MIN_TIME := 0.6
const CROSSING_SPEED := 1.2
const FADE_TIME := 0.45
## Share of the crossing for reading the scene file; the world build gets the rest.
const FILE_SHARE := 0.04
## Within a stage of unknown length the ferry eases toward the stage's end at this
## rate (per second, exponential), so it never stops but never overshoots.
const CREEP_RATE := 0.45

const TIPS := [
	"The islands wake early. So do the ferries.",
	"Somewhere out there, a car is waiting at the slip.",
	"Gulls know the timetable better than anyone.",
	"A full deck is a happy deck.",
	"Mind the tide on the way in.",
]

enum Phase { LOADING, ENTERING, FADING }

var _path := ""
var _phase := Phase.LOADING
var _t := 0.0
## The ferry eases toward _ceiling and never falls behind _floor.
var _floor := 0.0
var _ceiling := 0.0
var _shown := 0.0
var _frames := 0
var _scene: Node
var _stars: Array[Vector3] = []
var _caption: Label


## Covers the screen, loads `path` and switches to it.
static func open(tree: SceneTree, path: String, caption: String) -> void:
	var layer := CanvasLayer.new()
	layer.layer = 100
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	var screen := LoadingScreen.new()
	screen._path = path
	layer.add_child(screen)
	tree.root.add_child(layer)
	screen._caption.text = caption
	Music.set_mood(tree, Music.Mood.FULL)
	RadioChatter.on_loading(tree)


func _init() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i in 46:
		_stars.append(Vector3(rng.randf(), rng.randf() * 0.42, rng.randf() * TAU))
	_build_text()


func _ready() -> void:
	ResourceLoader.load_threaded_request(_path)


func _build_text() -> void:
	var col := VBoxContainer.new()
	col.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	col.grow_horizontal = Control.GROW_DIRECTION_BOTH
	col.grow_vertical = Control.GROW_DIRECTION_BEGIN
	col.offset_bottom = -44
	col.alignment = BoxContainer.ALIGNMENT_END
	col.add_theme_constant_override("separation", 6)
	add_child(col)

	var bold := SystemFont.new()
	bold.font_weight = 700
	_caption = Label.new()
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_caption.add_theme_font_override("font", bold)
	_caption.add_theme_font_size_override("font_size", 26)
	_caption.add_theme_color_override("font_color", TEXT)
	col.add_child(_caption)
	var tip := Label.new()
	tip.text = TIPS.pick_random()
	tip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tip.add_theme_font_size_override("font_size", 16)
	tip.add_theme_color_override("font_color", MUTED)
	col.add_child(tip)

	var title := Label.new()
	title.text = "TIDEWAYS"
	title.position = Vector2(32, 26)
	title.add_theme_font_override("font", bold)
	title.add_theme_font_size_override("font_size", 20)
	title.add_theme_color_override("font_color", Color(TEXT, 0.55))
	add_child(title)


func _process(delta: float) -> void:
	# The frame that builds the new world can take seconds; don't let it skip the animation.
	var d := minf(delta, 1.0 / 30.0)
	_t += d
	match _phase:
		Phase.LOADING:
			var progress := []
			var status := ResourceLoader.load_threaded_get_status(_path, progress)
			_ceiling = FILE_SHARE
			if not progress.is_empty():
				_floor = progress[0] * FILE_SHARE
			if status == ResourceLoader.THREAD_LOAD_LOADED and _t > MIN_TIME:
				var packed: PackedScene = ResourceLoader.load_threaded_get(_path)
				_scene = packed.instantiate()
				# Scenes that can build over several frames (sandbox.gd) report their stages.
				if "async_build" in _scene:
					_scene.async_build = true
				# If the destination exits before the fade, its overlay must
				# release the menu along with it.
				_scene.tree_exiting.connect(get_parent().queue_free, CONNECT_ONE_SHOT)
				get_tree().change_scene_to_node(_scene)
				_enter()
			elif status == ResourceLoader.THREAD_LOAD_FAILED or status == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
				push_error("Loading %s failed; falling back to a blocking load." % _path)
				get_tree().change_scene_to_file(_path)
				_enter()
		Phase.ENTERING:
			_frames += 1
			var done := _frames >= 3
			if is_instance_valid(_scene) and "built" in _scene:
				_floor = _share(_scene.build_from)
				_ceiling = _share(_scene.build_to)
				done = _scene.built and _frames >= 3
			if done:
				_floor = 1.0
				_ceiling = 1.0
				if _shown >= 0.999:
					_phase = Phase.FADING
					mouse_filter = Control.MOUSE_FILTER_IGNORE
		Phase.FADING:
			modulate.a -= d / FADE_TIME
			if modulate.a <= 0.0:
				get_parent().queue_free()
	# Creep toward the end of the current stage, never quite reaching it; catch up
	# at crossing speed when a stage finishes.
	var aim := maxf(_floor, _shown + (_ceiling - _shown) * (1.0 - exp(-d * CREEP_RATE)))
	_shown = move_toward(_shown, aim, d * CROSSING_SPEED)
	queue_redraw()


func _enter() -> void:
	_phase = Phase.ENTERING
	_frames = 0
	_floor = FILE_SHARE
	_ceiling = 0.9


## A share of the world build as a share of the whole crossing.
func _share(build: float) -> float:
	return lerpf(FILE_SHARE, 1.0, build)


# --- Illustration -------------------------------------------------------------

func _draw() -> void:
	var w := size.x
	var h := size.y
	var hz := h * 0.56
	var route_y := hz + (h - hz) * 0.32
	var sun := Vector2(w * 0.64, hz)

	_gradient(Rect2(0, 0, w, hz), SKY_TOP, SKY_GLOW)
	for s in _stars:
		var a := (0.35 + 0.35 * sin(_t * 1.7 + s.z)) * (1.0 - s.y / 0.42)
		draw_circle(Vector2(s.x * w, s.y * h), 1.3, Color(1, 1, 1, a))
	for i in 5:
		draw_circle(sun, h * (0.07 + i * 0.045), Color(SUN, 0.07))
	draw_circle(sun, h * 0.065, SUN)

	_island(w * 0.3, w * 0.46, hz + 1, h * 0.035, ISLAND_FAR, 1.0)
	_island(w * 0.52, w * 0.6, hz + 1, h * 0.02, ISLAND_FAR, 4.0)
	_island(w * 0.74, w * 0.86, hz + 1, h * 0.028, ISLAND_FAR, 2.5)

	_gradient(Rect2(0, hz, w, h - hz), SEA_FAR, SEA_NEAR)
	for i in 14:
		var y := hz + 4 + i * i * 1.6
		var half := h * 0.06 * (1.0 - i / 16.0) * (0.7 + 0.3 * sin(_t * 2.3 + i * 1.9))
		draw_line(Vector2(sun.x - half, y), Vector2(sun.x + half, y), Color(SUN, 0.5 - i * 0.03), 2.0)

	for r in 9:
		if _wave_row_y(r, hz, h) < route_y:
			_wave_row(r, hz, h, w)

	# Home island on the left, destination island with its lighthouse on the right.
	_island(-w * 0.1, w * 0.2, route_y, h * 0.3, ISLAND, 0.0)
	_island(w * 0.8, w * 1.12, route_y, h * 0.26, ISLAND, 3.0)
	var x0 := w * 0.19
	var x1 := w * 0.81
	_pier(Vector2(w * 0.15, route_y), 1.0)
	_pier(Vector2(w * 0.85, route_y), -1.0)
	_lighthouse(Vector2(w * 0.93, route_y - h * 0.215), h)

	_route(x0, x1, route_y + 6)
	_ferry(Vector2(lerpf(x0, x1, _shown), route_y + 2), h)

	for r in 9:
		if _wave_row_y(r, hz, h) >= route_y:
			_wave_row(r, hz, h, w)
	_gulls(w, h)


func _gradient(rect: Rect2, top: Color, bottom: Color) -> void:
	var p := rect.position
	var e := rect.end
	draw_polygon(
		PackedVector2Array([p, Vector2(e.x, p.y), e, Vector2(p.x, e.y)]),
		PackedColorArray([top, top, bottom, bottom]))


func _island(x0: float, x1: float, base: float, height: float, col: Color, seed: float) -> void:
	var pts := PackedVector2Array()
	var n := 40
	for i in n + 1:
		var f := float(i) / n
		var shape := pow(sin(f * PI), 0.65)
		var trees := (sin(f * 37.0 + seed) * 0.04 + sin(f * 17.0 + seed * 2.0) * 0.06) * shape
		pts.append(Vector2(lerpf(x0, x1, f), base - height * maxf(0.0, shape + trees)))
	draw_colored_polygon(pts, col)


func _pier(at: Vector2, dir: float) -> void:
	var len := 46.0
	var x := at.x if dir > 0 else at.x - len
	draw_rect(Rect2(x, at.y - 7, len, 5), Color(0.24, 0.2, 0.18))
	for i in 4:
		draw_line(Vector2(x + 4 + i * 13, at.y - 2), Vector2(x + 4 + i * 13, at.y + 6), Color(0.16, 0.13, 0.12), 3.0)


func _lighthouse(base: Vector2, h: float) -> void:
	var th := h * 0.06
	var tw := th * 0.28
	draw_colored_polygon(PackedVector2Array([
		base + Vector2(-tw * 0.6, 0), base + Vector2(tw * 0.6, 0),
		base + Vector2(tw * 0.38, -th), base + Vector2(-tw * 0.38, -th)]), Color(0.88, 0.86, 0.8))
	draw_rect(Rect2(base + Vector2(-tw * 0.5, -th * 0.55), Vector2(tw, th * 0.15)), Color(0.72, 0.24, 0.2))
	var lamp := base + Vector2(0, -th - 5)
	var pulse := 0.5 + 0.5 * sin(_t * 3.0)
	draw_circle(lamp, 26, Color(1, 0.9, 0.6, 0.12 * pulse))
	draw_circle(lamp, 12, Color(1, 0.9, 0.6, 0.25 * pulse))
	draw_circle(lamp, 4.5, Color(1, 0.93, 0.7))


func _wave_row_y(r: int, hz: float, h: float) -> float:
	return hz + (h - hz) * pow((r + 1) / 10.0, 1.6)


func _wave_row(r: int, hz: float, h: float, w: float) -> void:
	var y := _wave_row_y(r, hz, h)
	var amp := 1.0 + r * 0.7
	var k := 0.03 / (1.0 + r * 0.35)
	var pts := PackedVector2Array()
	var x := -10.0
	while x <= w + 10.0:
		pts.append(Vector2(x, y + sin(x * k + _t * (1.0 + r * 0.15) + r * 2.1) * amp))
		x += 12.0
	draw_polyline(pts, Color(0.75, 0.88, 0.9, 0.05 + r * 0.012), 1.0 + r * 0.2, true)


func _route(x0: float, x1: float, y: float) -> void:
	var done := lerpf(x0, x1, _shown)
	var x := x0
	while x < x1:
		var seg_end := minf(x + 10.0, x1)
		var col := Color(ACCENT, 0.9) if x < done else Color(1, 1, 1, 0.18)
		draw_line(Vector2(x, y), Vector2(seg_end, y), col, 2.0)
		x += 18.0


func _ferry(at: Vector2, h: float) -> void:
	var s := h / 960.0 * 1.3
	var bob := sin(_t * 2.2) * 2.5 * s
	var roll := sin(_t * 1.6) * 0.025
	var pos := at + Vector2(0, bob)

	# Wake fanning out behind the stern, drawn in screen space so it stays on the water.
	var stern := pos + Vector2(-54 * s, 14 * s)
	for i in 10:
		var f := fmod(i / 10.0 + _t * 0.35, 1.0)
		var back := f * 150.0 * s
		var spread := (2.0 + f * 16.0) * s
		var a := 0.32 * (1.0 - f)
		draw_line(stern + Vector2(-back, -spread * 0.4), stern + Vector2(-back - 14 * s, -spread * 0.5), Color(1, 1, 1, a), 2.0 * s)
		draw_line(stern + Vector2(-back, spread * 0.5), stern + Vector2(-back - 14 * s, spread * 0.6), Color(1, 1, 1, a), 2.0 * s)

	# Smoke from the funnel, drifting back.
	for i in 5:
		var f := fmod(_t * 0.6 + i * 0.2, 1.0)
		var puff := pos + Vector2((-8 - f * 70) * s, (-54 - f * 38) * s)
		draw_circle(puff, (4 + f * 10) * s, Color(0.85, 0.85, 0.85, 0.35 * (1.0 - f)))

	draw_set_transform(pos, roll, Vector2(s, s))
	var hull := Color(0.74, 0.22, 0.2)
	var white := Color(0.94, 0.94, 0.91)
	var lit := Color(1.0, 0.85, 0.55)
	draw_colored_polygon(PackedVector2Array([
		Vector2(-58, -2), Vector2(68, -9), Vector2(54, 16), Vector2(-54, 16)]), hull)
	draw_line(Vector2(-57, 4), Vector2(62, -1), white, 2.0)
	draw_rect(Rect2(-50, -20, 96, 18), white)
	draw_rect(Rect2(-34, -33, 60, 13), white)
	draw_rect(Rect2(12, -43, 16, 10), white)
	draw_rect(Rect2(14, -41, 12, 4), Color(0.2, 0.3, 0.36))
	for i in 9:
		draw_rect(Rect2(-44 + i * 10, -15, 6, 6), lit)
	for i in 5:
		draw_rect(Rect2(-28 + i * 10, -29, 6, 5), lit)
	draw_rect(Rect2(-14, -50, 12, 17), Color(0.95, 0.74, 0.3))
	draw_rect(Rect2(-14, -50, 12, 4), Color(0.12, 0.12, 0.12))
	draw_line(Vector2(34, -43), Vector2(34, -58), Color(0.3, 0.3, 0.3), 1.5)
	# Bow wave.
	var foam := 0.5 + 0.5 * sin(_t * 6.0)
	draw_circle(Vector2(62, 12), 4 + foam * 2, Color(1, 1, 1, 0.5))
	draw_circle(Vector2(54, 15), 3 + foam, Color(1, 1, 1, 0.4))
	draw_set_transform(Vector2.ZERO)


func _gulls(w: float, h: float) -> void:
	for i in 3:
		var x := fmod(w * (0.25 + i * 0.22) + _t * (18.0 + i * 7.0), w + 80.0) - 40.0
		var y := h * (0.2 + i * 0.07) + sin(_t * 0.9 + i * 2.0) * 10.0
		var flap := sin(_t * (6.0 + i)) * 4.0
		var gs := 1.0 - i * 0.18
		draw_polyline(PackedVector2Array([
			Vector2(x - 9 * gs, y - 2 - flap * gs), Vector2(x - 3 * gs, y - 1),
			Vector2(x, y + 1), Vector2(x + 3 * gs, y - 1), Vector2(x + 9 * gs, y - 2 - flap * gs)]),
			Color(0.92, 0.92, 0.9, 0.85), 1.8, true)
