extends "res://tests/support/terminal_snapshot_case.gd"
## Resume visible walk-ons at the terminal door and while closing the waiting queue.


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_check_old_versions()
	_check_walking_queue()
	_check_visible_limit()
	finish()


func _check_old_versions() -> void:
	var live := _world()
	var port: Terminal = live.terminals[0]
	for version in [1, 2]:
		var snapshot := _record(port).holding as Dictionary
		snapshot.version = version
		if version == 1:
			for group: Array in snapshot.lanes.values():
				for row: Dictionary in group:
					row.erase("approaching")
		for row: Dictionary in snapshot.passengers:
			row.erase("position")
			row.erase("yaw")
		var fresh := _world()
		check(
			TerminalHoldingSnapshot.restore(
				snapshot, fresh.terminals[0], VehicleFactory.from_parts
			),
			"Settled queues in version %s restore without saved walk-on poses" % version
		)
		fresh.free()
	live.free()


func _check_walking_queue() -> void:
	var live := _world()
	var port: Terminal = live.terminals[0]
	port._spawn_passenger()
	var entering: Passenger = port.passenger_queue.back().node
	entering._process(0.13)
	_compare_walking(port)
	var serves: Array[int] = [port.lane_keys()[0]]
	var boarded := port.board_next_passenger(serves)
	boarded.node.free()
	_compare_walking(port)
	live.free()


func _compare_walking(port: Terminal) -> void:
	var saved: Dictionary = _record(port).holding
	var fresh := _world(true)
	var target: Terminal = fresh.terminals[fresh.map.town_by_key(port.town.key).id]
	var initial := _record(target)
	var damaged := saved.duplicate(true)
	damaged.passengers.back().walking_to = [0, "invalid", 0]
	check(
		not TerminalHoldingSnapshot.restore(damaged, target, VehicleFactory.from_parts),
		"Reject a malformed walking target before changing the current lot"
	)
	check(_record(target) == initial, "Preserve the fresh queues after an invalid walk-on pose")
	check(
		TerminalHoldingSnapshot.restore(saved, target, VehicleFactory.from_parts),
		"Restore waiting and moving passengers during a terminal walk"
	)
	var walking := 0
	for i in port.passenger_queue.size():
		var original: Passenger = port.passenger_queue[i].node
		var copy: Passenger = target.passenger_queue[i].node
		check(
			(
				original.position.is_equal_approx(copy.position)
				and is_equal_approx(original.rotation.y, copy.rotation.y)
				and original.path == copy.path
			),
			"Each visible passenger retains position, heading and active destination"
		)
		if not original.path.is_empty():
			walking += 1
			original._process(0.015)
			copy._process(0.015)
			check(original.position.is_equal_approx(copy.position), "Next walking step matches")
			var spot := copy.path[0] if not copy.path.is_empty() else copy.position
			copy._process(10.0)
			check(
				copy.path.is_empty() and copy.position.is_equal_approx(spot), "Finish at saved spot"
			)
	check(walking > 0, "Exercise an actual incoming or closing-up queue")
	check(
		(
			target.passenger_queue.size() == port.passenger_queue.size()
			and target.passengers_served_today == port.passengers_served_today
		),
		"Walking resumes without a duplicate passenger or boarding event"
	)
	fresh.free()


func _check_visible_limit() -> void:
	var live := _world()
	var port: Terminal = live.terminals[0]
	while port.passenger_queue.size() <= Terminal.MAX_VISIBLE_PASSENGERS:
		port._spawn_passenger()
	var saved := _record(port).holding as Dictionary
	var fresh := _world()
	var target: Terminal = fresh.terminals[0]
	check(
		TerminalHoldingSnapshot.restore(saved, target, VehicleFactory.from_parts),
		"Restore the visible crowd alongside a logical passenger without a node"
	)
	check(
		(
			target._visible_passenger_count() == Terminal.MAX_VISIBLE_PASSENGERS
			and target.passenger_queue.back().node == null
		),
		"Restoring the crowd respects the existing visible limit"
	)
	fresh.free()
	live.free()
