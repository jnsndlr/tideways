extends SceneTree
## A pair that has flown away must release both birds and their completed visit.


func _initialize() -> void:
	var eagles := Eagles.new()
	eagles._mm = MultiMesh.new()
	var departed := _departed_pair(eagles)
	eagles._process(0.1)
	var released := eagles._birds.is_empty()
	for ref: WeakRef in departed:
		released = released and ref.get_ref() == null
	eagles.free()
	if not released:
		push_error("Departed eagles retained their mate, flight leader or visit.")
		quit(1)
		return
	print("TEST PASSED")
	quit(0)


func _departed_pair(eagles: Eagles) -> Array[WeakRef]:
	var visit := Wildlife.Visit.new()
	visit.phase = Wildlife.Phase.GONE
	var first := Eagles.Bird.new()
	var second := Eagles.Bird.new()
	first.mate = second
	second.mate = first
	first.leader = second
	second.leader = first
	for b: Eagles.Bird in [first, second]:
		b.state = Eagles.State.AWAY
		b.visit = visit
		eagles._birds.append(b)
	return [weakref(first), weakref(second), weakref(visit)]
