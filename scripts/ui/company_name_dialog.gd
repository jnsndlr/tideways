extends ColorRect
## A company registration ticket on the departure board.

signal name_chosen(company_name: String)

const STAMP_INK := Color("#376054")

@onready var _card: PanelContainer = %Card
@onready var _field: LineEdit = %NameField
@onready var _seal: Control = %FerrySeal
@onready var _rule: Control = %Perforation


func _ready() -> void:
	_seal.draw.connect(_draw_ferry_seal)
	_rule.draw.connect(_draw_perforation)
	resized.connect(_fit_width)
	_fit_width()
	%Cancel.pressed.connect(queue_free)
	%Start.pressed.connect(_confirm)
	_field.text_submitted.connect(func(_value: String): _confirm())
	_field.grab_focus()


func _fit_width() -> void:
	_card.custom_minimum_size.x = minf(730.0, maxf(0.0, size.x - 48.0))


func _confirm() -> void:
	if is_queued_for_deletion():
		return
	var company_name := _field.text.strip_edges()
	queue_free()
	name_chosen.emit(_field.placeholder_text if company_name.is_empty() else company_name)


func _draw_ferry_seal() -> void:
	# A ferry seen bow-on, like a stamp on a terminal ticket.
	_seal.draw_arc(Vector2(32, 32), 29, 0.0, TAU, 64, STAMP_INK, 2.0, true)
	_seal.draw_line(Vector2(32, 11), Vector2(32, 18), STAMP_INK, 2.0, true)
	_seal.draw_rect(Rect2(21, 19, 22, 14), STAMP_INK)
	for x in [24, 33]:
		_seal.draw_rect(Rect2(x, 22, 7, 6), Color("#f5eddc"))
	_seal.draw_colored_polygon(
		PackedVector2Array(
			[
				Vector2(16, 32),
				Vector2(32, 29),
				Vector2(48, 32),
				Vector2(42, 40),
				Vector2(32, 44),
				Vector2(22, 40)
			]
		),
		STAMP_INK
	)
	for x in [17, 27, 37]:
		_seal.draw_arc(Vector2(x + 5, 44), 6, 0.6, PI - 0.6, 12, STAMP_INK, 1.8, true)


func _draw_perforation() -> void:
	var end := Vector2(_rule.size.x, 1)
	_rule.draw_dashed_line(Vector2(0, 1), end, Color("#aa9d80"), 1.5, 7.0)
