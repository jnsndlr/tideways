extends SceneTree
## Lay-up commands and timed berth transitions without a scene or ferry actor.

var failures := 0


func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	check_manual_orders()
	check_scheduled_gap()
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)


func check_manual_orders() -> void:
	var lay_up := FerryLayUp.new()
	check(lay_up.in_service() and not lay_up.can_sell(), "A working ferry is in service")
	lay_up.request_lay_up()
	check(lay_up.lay_up_requested and not lay_up.in_service(), "A manual request takes effect at the next available slip")
	lay_up.request_return()
	check(lay_up.in_service() and not lay_up.return_requested, "A pending lay-up can be cancelled")
	lay_up.request_lay_up()
	lay_up.leave_working_slip(3)
	check(lay_up.berth == FerryLayUp.Berth.TO_TIE_UP and lay_up.tie_up == 3 and not lay_up.lay_up_requested, "Starting the shift consumes the request and claims that slip")
	lay_up.request_return()
	lay_up.finish_shift()
	check(lay_up.return_requested and not lay_up.can_sell(), "A return ordered in transit stays pending on arrival")
	lay_up.request_lay_up()
	check(lay_up.can_sell(), "Cancelling a pending return allows sale at a manual tie-up")
	lay_up.request_return()
	lay_up.leave_tie_up()
	check(not lay_up.return_requested and not lay_up.in_service(), "Manual return stays out of service until back in the working slip")
	lay_up.finish_shift()
	check(lay_up.in_service(), "Completing return restores service")
	lay_up.berth = FerryLayUp.Berth.DELIVERING
	lay_up.request_lay_up()
	lay_up.request_return()
	check(not lay_up.lay_up_requested and not lay_up.return_requested and not lay_up.can_sell(), "A delivery ignores both player orders")


func check_scheduled_gap() -> void:
	check(FerryLayUp.long_enough_gap(450.0, 300.0), "A gap of exactly 150 minutes qualifies")
	check(not FerryLayUp.long_enough_gap(449.9, 300.0), "A shorter gap leaves the ferry at the working slip")
	var lay_up := FerryLayUp.new()
	lay_up.leave_working_slip(2, 450.0)
	lay_up.finish_shift()
	check(lay_up.in_service() and lay_up.between_sailings() and not lay_up.can_sell(), "A gap tie-up stays assigned to service")
	lay_up.check_return_time(424.9, 15.0, 5.0)
	check(not lay_up.return_requested, "Do not start back early")
	lay_up.check_return_time(425.0, 15.0, 5.0)
	check(lay_up.return_requested, "Start back in time for the shift, boarding and margin")
	lay_up.reschedule_gap(600.0)
	check(lay_up.gap_due == 600.0 and not lay_up.return_requested, "A timetable edit replaces the due time and clears a pending return")
	lay_up.request_lay_up()
	check(not lay_up.between_sailings() and lay_up.can_sell(), "A manual lay-up takes precedence over a scheduled return")
