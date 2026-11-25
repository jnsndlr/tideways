extends SceneTree
## Two working slips feed the same exit lane. A second ferry must hold her
## unloading stream until the first stream's tail clears the boarding approach.

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var region := TinyRegion.build(3)
	var sim := region.start(root)
	var first := sim.ferries[0]
	var second := sim.ferries[1]
	first.at_a = true
	second.at_a = true
	var terminal := first.here()
	var ok := terminal == second.here() and first.route.id != second.route.id
	for ferry: Ferry in [first, second]:
		var ramp := ferry._ramp(terminal)
		if ramp:
			ramp.snap_down()
		ferry._unload_queue.assign([sim.make_vehicle(ferry)])
		ferry.state = Ferry.State.UNLOADING
		ferry._dispatch_timer = 0
	first._tick_unloading(0.1)
	second._tick_unloading(0.1)
	ok = ok and first._unload_queue.is_empty() and second._unload_queue.size() == 1
	if ok:
		var car := first._last_sent
		car.global_position = terminal.to_global(Vector3(0, Layout.LOT_Y, Layout.LOT_FRONT))
		first._tick_unloading(4.0)
		second._tick_unloading(0.1)
		ok = first.state == Ferry.State.UNLOADING and second._unload_queue.size() == 1
		car.global_position = terminal.to_global(Vector3(0, Layout.LOT_Y, Layout.LOT_BACK))
		first._tick_unloading(0.1)
		second._tick_unloading(0.1)
		ok = ok and first.state == Ferry.State.LOADING and second._unload_queue.is_empty()
	sim.free()
	if not ok:
		push_error("Competing slips must wait for the first outbound stream to clear the shared forecourt.")
		quit(1)
		return
	print("TEST PASSED")
	quit(0)
