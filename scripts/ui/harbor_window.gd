extends VideoStreamPlayer
## Project one continuous movie through either set of painted window panes.

const LANDSCAPE_GLASS := preload("res://assets/textures/menu/harbor_landscape_glass.png")
const PORTRAIT_GLASS := preload("res://assets/textures/menu/harbor_portrait_glass.png")

# Glass-mask bounds in the terminal paintings, and the corresponding 720p camera crops.
const LANDSCAPE_GLASS_RECT := Rect2(776, 8, 704, 704)
const PORTRAIT_GLASS_RECT := Rect2(16, 0, 1056, 594)
const LANDSCAPE_VIEW := Rect2(338, 0, 704, 704)
const PORTRAIT_VIEW := Rect2(0, 44, 1280, 676)
const CAMERA_SIZE := Vector2(1280, 720)


func fit_art(portrait: bool, art_scale: float) -> void:
	var bounds := PORTRAIT_GLASS_RECT if portrait else LANDSCAPE_GLASS_RECT
	position = bounds.position * art_scale
	size = bounds.size * art_scale
	var view := PORTRAIT_VIEW if portrait else LANDSCAPE_VIEW
	var glass_material := material as ShaderMaterial
	glass_material.set_shader_parameter("glass", PORTRAIT_GLASS if portrait else LANDSCAPE_GLASS)
	glass_material.set_shader_parameter("view_origin", view.position / CAMERA_SIZE)
	glass_material.set_shader_parameter("view_size", view.size / CAMERA_SIZE)
