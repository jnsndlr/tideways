extends VideoStreamPlayer
## Alternate two sailings through either set of painted window panes.

const TRAFFIC_SETS := [
	preload("res://assets/textures/menu/harbor_cycle.ogv"),
	preload("res://assets/textures/menu/harbor_cycle_b.ogv"),
]

const LANDSCAPE_GLASS := preload("res://assets/textures/menu/harbor_landscape_glass.png")
const PORTRAIT_GLASS := preload("res://assets/textures/menu/harbor_portrait_glass.png")

# Glass-mask bounds in the terminal paintings, and the corresponding 720p camera crops.
const LANDSCAPE_GLASS_RECT := Rect2(776, 8, 704, 704)
const PORTRAIT_GLASS_RECT := Rect2(16, 0, 1056, 594)
const LANDSCAPE_VIEW := Rect2(338, 0, 704, 704)
const PORTRAIT_VIEW := Rect2(0, 44, 1280, 676)
const CAMERA_SIZE := Vector2(1280, 720)

# On a return to the title screen, start at least half a minute away from
# the previous opening, even when the other three-minute sailing is picked.
const MIN_OPENING_GAP := 1.0 / 6.0
static var _last_opening_phase := -1.0


func _ready() -> void:
	set_process(false)
	finished.connect(_next_sailing)
	stream = TRAFFIC_SETS.pick_random()
	play()
	var phase := randf()
	if _last_opening_phase >= 0.0:
		var offset := randf_range(MIN_OPENING_GAP, 1.0 - MIN_OPENING_GAP)
		phase = fposmod(_last_opening_phase + offset, 1.0)
	_last_opening_phase = phase
	stream_position = minf(phase * get_stream_length(), get_stream_length() - 1.0 / 24.0)


func _next_sailing() -> void:
	# Keep the empty harbor on the glass while the next decoder supplies its first frame.
	$SeamFrame.texture = get_video_texture()
	set_process(true)
	stream = TRAFFIC_SETS[1] if stream == TRAFFIC_SETS[0] else TRAFFIC_SETS[0]
	play()


func _process(_delta: float) -> void:
	if stream_position > 0.0:
		$SeamFrame.texture = null
		set_process(false)


func fit_art(portrait: bool, art_scale: float) -> void:
	var bounds := PORTRAIT_GLASS_RECT if portrait else LANDSCAPE_GLASS_RECT
	position = bounds.position * art_scale
	size = bounds.size * art_scale
	var view := PORTRAIT_VIEW if portrait else LANDSCAPE_VIEW
	var glass_material := material as ShaderMaterial
	glass_material.set_shader_parameter("glass", PORTRAIT_GLASS if portrait else LANDSCAPE_GLASS)
	glass_material.set_shader_parameter("view_origin", view.position / CAMERA_SIZE)
	glass_material.set_shader_parameter("view_size", view.size / CAMERA_SIZE)
