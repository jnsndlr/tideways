class_name HoldingLaneView
extends MeshInstance3D
## Local to the terminal. Construction begins after the traffic lanes clear.

var crew: PavingCrew


func setup(terminal: Terminal) -> void:
	terminal.extension_changed.connect(_refresh.bind(terminal))


func _refresh(terminal: Terminal) -> void:
	match terminal.work_stage:
		Terminal.WorkStage.DRAINING:
			crew = PavingCrew.new()
			add_child(crew)
			crew.setup(terminal)
		Terminal.WorkStage.ARRIVING:
			mesh = _surface(terminal, false)
		Terminal.WorkStage.OPEN:
			if crew:
				remove_child(crew)
				crew.queue_free()
				crew = null
			mesh = _surface(terminal, true)


func _surface(terminal: Terminal, finished: bool) -> ArrayMesh:
	var mb := MeshBuilder.new()
	var v := terminal.extension_offset()
	var y := Layout.LOT_Y
	var u := (Layout.LOT_FRONT + Layout.LOT_BACK) * 0.5
	var width := Layout.LANE_WIDTH
	mb.box(Vector3(v, y - 0.95, u), Vector3(width, 1.9, Layout.LOT_LENGTH), WorldBuilder.ASPHALT if finished else PavingCrew.GRAVEL)
	if finished:
		var start := Layout.LOT_BACK + 7.5
		var end := Layout.LANE_HEAD + 3.0
		for side: float in [-0.5, 0.5]:
			mb.box(Vector3(v + side * (width - 0.36), y + 0.03, (start + end) * 0.5), Vector3(0.36, 0.06, end - start), WorldBuilder.LINE_WHITE)
		mb.box(Vector3(v, y + 0.03, end), Vector3(width, 0.06, 0.6), WorldBuilder.LINE_WHITE)
	return mb.commit()
