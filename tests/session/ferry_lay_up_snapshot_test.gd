extends "res://tests/support/company_snapshot_case.gd"
## Reopen the same manual lay-up and post-service return at each physical stage.


func _initialize() -> void:
	_run.call_deferred()


func _ports() -> Simulation:
	var region := TinyRegion.build()
	region.map.towns[1].slips.append(MapData.Slip.new(3, true))
	var scenario := Scenario.from_network(region.map, ["Working ferry"], [3])
	var sim := Simulation.new(VehicleFactory.create, true, false)
	root.add_child(sim)
	sim.setup(region.map, region.terrain, scenario)
	return sim


func _check_point(live: Simulation, stage: String) -> void:
	var f := live.ferries[0]
	var saved := _save(live)
	var reopened := CompanySnapshot.restore(saved, _ports, VehicleFactory.from_parts)
	check(reopened != null, "Reopen %s" % stage)
	if not reopened:
		return
	var other := reopened.ferries[0]
	check(
		(
			other.global_transform.is_equal_approx(f.global_transform)
			and f.aboard.size() == other.aboard.size()
			and f.manual == other.manual
			and f.tie_up == other.tie_up
		),
		"Restore pose, orders, berth and manifest during %s" % stage
	)
	check(
		_save(reopened).voyages == saved.voyages and _save(reopened).ledger == saved.ledger,
		"Preserve voyage and accounting at %s" % stage
	)
	for step in 8:
		_step(f)
		_step(other)
	check(
		(
			f.global_position.is_equal_approx(other.global_position)
			and f.berth == other.berth
			and _save(reopened).ledger == _save(live).ledger
		),
		"Continue motion and accounting from %s" % stage
	)
	if stage == "moving to the berth":
		var wrong := saved.duplicate(true)
		wrong.voyages[f.fleet_key].lay_up.shift.start[0] += 200
		_reject(wrong, "Reject a shift originating away from its slip")
		var changed := saved.duplicate(true)
		changed.voyages[f.fleet_key].lay_up.shift.distance += 8
		_reject(changed, "Reject saved motion that disagrees with the hull's position")
	if stage == "parked":
		var inbound := _ports()
		var purchase := inbound.buy_ferry(1)
		check(
			purchase.here().town.id == f.here().town.id and purchase.tie_up == f.tie_up,
			"Independent purchase is booked into the parked boat's berth"
		)
		var bought := _save(inbound)
		var collision := saved.duplicate(true)
		collision.network.ferries.append(bought.network.ferries[-1])
		collision.voyages[purchase.fleet_key] = bought.voyages[purchase.fleet_key]
		_reject(collision, "Reject an inbound tow assigned to an occupied tie-up")
		collision.network.ferries.reverse()
		_reject(collision, "Check the berth independent of fleet record order")
		inbound.free()
	if saved.voyages[f.fleet_key].has("lay_up"):
		var record: Dictionary = saved.voyages[f.fleet_key].lay_up
		record.tie = 12345
		var broken := CompanySnapshot.restore(saved, _ports, VehicleFactory.from_parts)
		check(broken == null, "Reject unknown berth in %s" % stage)
		if broken:
			broken.free()
	reopened.free()


func _reject(saved: Dictionary, message: String) -> void:
	var broken := CompanySnapshot.restore(saved, _ports, VehicleFactory.from_parts)
	check(broken == null, message)
	if broken:
		broken.free()


func _run() -> void:
	var sim := _ports()
	_empty_queues(sim)
	var f := sim.ferries[0]
	_enqueue(f.here(), 4)
	for step in 15000:
		_step(f)
		if f.state == Ferry.State.SAILING and f.traveled > 140:
			break
	check(f.aboard.size() == 1, "A paid vehicle is aboard at the lay-up request")
	f.set_timetable([420, 790])
	f.request_lay_up()
	_check_point(sim, "requested while carrying a paid vehicle")
	for step in 16000:
		_step(f)
		if f.shifting() and f._shift_s > 40:
			break
	check(
		f.berth == Ferry.Berth.TO_TIE_UP and f.shifting(),
		"Unload and maneuver toward the reserved tie-up"
	)
	_check_point(sim, "moving to the berth")
	for step in 8000:
		_step(f)
		if f.berth == Ferry.Berth.TIED_UP:
			break
	check(f.berth == Ferry.Berth.TIED_UP, "Reach the parking slip")
	_check_point(sim, "parked")
	f.request_return()
	for step in 8000:
		_step(f)
		if f.shifting() and f._shift_s > 40:
			break
	check(f.berth == Ferry.Berth.TO_WORKING, "Return toward the working slip")
	_check_point(sim, "returning to service")
	for step in 8000:
		_step(f)
		if f.berth == Ferry.Berth.WORKING:
			break
	check(
		f.berth == Ferry.Berth.WORKING and not f.manual and f.timetable == [420, 790],
		"Restore the original two-stop timetable"
	)
	sim.free()
	var empty := _ports()
	_empty_queues(empty)
	var hull := empty.ferries[0]
	hull.request_lay_up(hull.destination().town.id)
	for step in 10000:
		_step(hull)
		if hull.state == Ferry.State.SAILING and hull.traveled > 100:
			break
	check(
		hull.state == Ferry.State.SAILING and hull.aboard.is_empty(),
		"Sail empty to the selected lay-up"
	)
	_check_point(empty, "sailing empty to lay-up")
	empty.free()
	finish()
