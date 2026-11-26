class_name HoldingLaneView
extends MeshInstance3D
## Local to the terminal's lot (Island.lot_offset()). Construction begins after the traffic lanes clear.

var crew: PavingCrew


func setup(terminal: Terminal) -> void:
	transform = terminal.town.lot_offset()  # in the lot's frame, like everything on the lot
	terminal.extension_changed.connect(_refresh.bind(terminal))
	_refresh(terminal)


func _refresh(terminal: Terminal) -> void:
	var stage := terminal.work_stage
	if stage in [Terminal.WorkStage.IDLE, Terminal.WorkStage.OPEN]:
		if crew:
			remove_child(crew)
			crew.queue_free()
			crew = null
		if not terminal.paved.is_empty():
			mesh = _surface(terminal, NAN)
		return
	if crew == null:
		crew = PavingCrew.new()
		add_child(crew)
		crew.setup(terminal)
	if stage != Terminal.WorkStage.DRAINING:
		mesh = _surface(terminal, terminal.extension_offset())
	elif not terminal.paved.is_empty():
		mesh = _surface(terminal, NAN)


## Every lane paved so far, and gravel where one is being built (`building`, NAN for none).
func _surface(terminal: Terminal, building: float) -> ArrayMesh:
	var mb := MeshBuilder.new()
	for v in terminal.paved:
		_lane(mb, v, true)
	if not is_nan(building):
		_lane(mb, building, false)
	return mb.commit()


func _lane(mb: MeshBuilder, v: float, finished: bool) -> void:
	var y := Layout.LOT_Y
	var u := (Layout.LOT_FRONT + Layout.LOT_BACK) * 0.5
	var width := Layout.LANE_WIDTH
	mb.box(Vector3(v, y - 0.95 + (0.02 if finished else 0.0), u), Vector3(width, 1.9, Layout.LOT_LENGTH), WorldBuilder.ASPHALT if finished else PavingCrew.GRAVEL)
	if finished:
		var start := Layout.LOT_BACK + 7.5
		var end := Layout.LANE_HEAD + 3.0
		for side: float in [-0.5, 0.5]:
			mb.box(Vector3(v + side * (width - 0.36), y + 0.03, (start + end) * 0.5), Vector3(0.36, 0.06, end - start), WorldBuilder.LINE_WHITE)
		mb.box(Vector3(v, y + 0.03, end), Vector3(width, 0.06, 0.6), WorldBuilder.LINE_WHITE)
