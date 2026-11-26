extends VideoStreamPlayer
## Each movie is registered to a crop of its corresponding terminal illustration.

const LANDSCAPE := preload("res://assets/textures/menu/harbor_landscape.ogv")
const PORTRAIT := preload("res://assets/textures/menu/harbor_portrait.ogv")
const LANDSCAPE_GLASS := preload("res://assets/textures/menu/harbor_landscape_glass.png")
const PORTRAIT_GLASS := preload("res://assets/textures/menu/harbor_portrait_glass.png")
const LANDSCAPE_CROP := Rect2(776, 8, 704, 704)
const PORTRAIT_CROP := Rect2(16, 0, 1056, 594)


func fit_art(portrait: bool, art_scale: float) -> void:
	var crop := PORTRAIT_CROP if portrait else LANDSCAPE_CROP
	position = crop.position * art_scale
	size = crop.size * art_scale
	var movie := PORTRAIT if portrait else LANDSCAPE
	if stream == movie:
		return
	stream = movie
	var glass := PORTRAIT_GLASS if portrait else LANDSCAPE_GLASS
	(material as ShaderMaterial).set_shader_parameter("glass", glass)
	play()
