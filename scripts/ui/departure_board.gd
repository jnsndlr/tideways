extends Control
## The illustration is the layout. Action hit areas and moving cards share its coordinates.

const PLATE := preload("res://assets/textures/menu/terminal_board.jpg")
const PAINT := preload("res://assets/textures/menu/printed_flaps.jpg")
const WALL := preload("res://assets/textures/menu/ferry_terminal.jpg")
const PORTRAIT := preload("res://assets/textures/menu/terminal_portrait.jpg")
const FLIP := preload("res://scripts/ui/departure_flap.gdshader")
# Left and right endpoints of each row's top, hinge, and bottom, in art pixels.
const RAILS := [
	[Vector4(100, 110, 772, 162), Vector4(100, 185, 772, 229), Vector4(100, 261, 772, 291)],
	[Vector4(119, 302, 754, 327), Vector4(119, 373, 754, 385), Vector4(119, 429, 754, 435)],
	[Vector4(115, 436, 756, 439), Vector4(115, 459, 756, 461), Vector4(115, 482, 756, 483)],
	[Vector4(120, 510, 752, 511), Vector4(120, 550, 752, 545), Vector4(120, 586, 752, 580)],
	[Vector4(120, 603, 752, 593), Vector4(120, 644, 752, 631), Vector4(120, 679, 752, 665)],
	[Vector4(120, 697, 752, 677), Vector4(120, 735, 752, 714), Vector4(120, 770, 752, 748)],
]
const PRINTED := ["TIDEWAYS", "Continue", "", "New company", "Sandboxes", "Settings"]

var _materials: Array[ShaderMaterial] = []
var _ink: Array[Label] = []
var _turns: Tween

@onready var backdrop: TextureRect = $"../Terminal"
@onready var cutout: Polygon2D = $PortraitBoard


func _ready() -> void:
	var outline := PackedVector2Array(
		[Vector2(50, 53), Vector2(802, 117), Vector2(798, 775), Vector2(48, 812)]
	)
	cutout.polygon = outline
	cutout.uv = outline
	cutout.texture = PLATE
	for index in RAILS.size():
		_make_row(index)
	get_parent().resized.connect(_layout)
	_layout()


func _make_row(index: int) -> void:
	var points := PackedVector2Array()
	var mat := ShaderMaterial.new()
	mat.shader = FLIP
	var rail_names := ["top_rail", "axle", "bottom_rail"]
	for rail_index in 3:
		var ends: Vector4 = RAILS[index][rail_index]
		mat.set_shader_parameter(rail_names[rail_index], ends)
		points.append(Vector2(ends.x, ends.y))
		points.append(Vector2(ends.z, ends.w))
	mat.set_shader_parameter("blank_plate", PLATE)
	mat.set_shader_parameter("painted_type", PAINT)
	mat.set_shader_parameter("title_row", index == 0)
	mat.set_shader_parameter("has_hinge", index != 2)
	mat.set_shader_parameter("cell_count", 8 if index == 0 else 10)
	mat.set_shader_parameter("row_delay", 0.055 * index)
	var face := Polygon2D.new()
	face.polygon = points
	face.texture = PLATE
	face.uv = PackedVector2Array(
		[
			Vector2(0, 0),
			Vector2(1448, 0),
			Vector2(0, 543),
			Vector2(1448, 543),
			Vector2(0, 1086),
			Vector2(1448, 1086)
		]
	)
	face.polygons = [PackedInt32Array([0, 1, 3, 2]), PackedInt32Array([2, 3, 5, 4])]
	face.material = mat
	$Faces.add_child(face)
	_materials.append(mat)

	# Native text is rasterized only when an action or saved-company label changes.
	var viewport := SubViewport.new()
	viewport.size = Vector2i(636, [144, 115, 48, 80, 80, 80][index])
	viewport.transparent_bg = true
	viewport.disable_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	add_child(viewport)
	var label := Label.new()
	label.add_theme_font_override("font", get_theme_font("font", "Label"))
	label.add_theme_font_size_override("font_size", [88, 79, 37, 52, 52, 52][index])
	label.add_theme_color_override("font_color", Color("#ffe8b7"))
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.horizontal_alignment = (
		HORIZONTAL_ALIGNMENT_CENTER if index <= 2 else HORIZONTAL_ALIGNMENT_LEFT
	)
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	viewport.add_child(label)
	label.position.x = 12 if index <= 2 else 64
	label.size = Vector2(viewport.size) - Vector2(label.position.x + 12, 0)
	_ink.append(label)
	mat.set_shader_parameter("live_type", viewport.get_texture())


func display(words: PackedStringArray, turn_title: bool) -> void:
	if _turns:
		_turns.kill()
	for i in words.size():
		var painted: bool = not words[i].is_empty() and words[i] == PRINTED[i]
		var mat := _materials[i]
		mat.set_shader_parameter("printed", painted)
		mat.set_shader_parameter("has_type", not words[i].is_empty())
		if not painted and words[i] != _ink[i].text:
			_ink[i].text = words[i]
			_ink[i].get_viewport().render_target_update_mode = SubViewport.UPDATE_ONCE
		mat.set_shader_parameter("elapsed", 2.0)
	_turns = create_tween().set_parallel(true)
	for i in range(0 if turn_title else 1, words.size()):
		if words[i].is_empty():
			continue
		var mat := _materials[i]
		mat.set_shader_parameter("elapsed", 0.0)
		_turns.tween_method(func(t: float): mat.set_shader_parameter("elapsed", t), 0.0, 1.4, 1.4)


func place_action(control: Control, row: int) -> void:
	var top: Vector4 = RAILS[row][0]
	var bottom: Vector4 = RAILS[row][2]
	control.position = Vector2(top.x, (top.y + top.w) * 0.5)
	control.size = Vector2(top.z - top.x, (bottom.y + bottom.w - top.y - top.w) * 0.5)


func _layout() -> void:
	var view: Vector2 = get_parent().size
	if view.x < 1 or view.y < 1:
		return
	var portrait := view.y > view.x
	# When there is too little room beside the board, frame the ferry above it.
	var detached := portrait or view.aspect() > 1.95
	backdrop.texture = PORTRAIT if portrait else (WALL if detached else PLATE)
	var art_size := backdrop.texture.get_size()
	var fill := maxf(view.x / art_size.x, view.y / art_size.y)
	backdrop.size = art_size * fill
	backdrop.position = (view - backdrop.size) * 0.5
	cutout.visible = detached
	if detached:
		backdrop.position.x = view.x - backdrop.size.x
		var fit := minf(
			view.x * (0.91 if portrait else 0.51) / 758.0,
			view.y * (0.49 if portrait else 0.80) / 760.0
		)
		scale = Vector2.ONE * fit
		position = Vector2(
			(view.x - 852.0 * fit) * 0.5 if portrait else view.x * 0.03 - 48.0 * fit,
			view.y * 0.90 - 812.0 * fit if portrait else view.y * 0.08 - 53.0 * fit
		)
	else:
		backdrop.position.y = clampf(backdrop.position.y, -44.0 * fill, 0.0)
		position = backdrop.position
		scale = Vector2.ONE * fill
