extends SceneTree
## Crossing decisions run without constructing a ferry, terminal or scene mesh.

var failures := 0


func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _initialize() -> void:
	var voyage := FerryVoyage.new()
	check(voyage.state == FerryVoyage.State.LOADING and voyage.at_a, "Start loading at A")
	voyage.state_time = 20.0
	voyage.depart()
	check(voyage.state == FerryVoyage.State.SAILING and voyage.state_time == 0.0, "Departure starts the sailing clock")
	check(is_equal_approx(voyage.sailing_speed(1.0, 1000.0, 0.0, 20.0, INF, INF), 4.2), "Accelerate from rest")
	check(is_equal_approx(voyage.sailing_speed(1.0, 1000.0, 19.0, 20.0, INF, INF), 20.0), "Respect cruise speed")
	check(voyage.sailing_speed(1.0, 1000.0, 20.0, 20.0, 0.0, INF) == 0.0, "Stop for a hull")
	check(voyage.sailing_speed(1.0, 1000.0, 20.0, 20.0, INF, 1.5) == 0.0, "Stop short of an occupied corridor")
	check(is_equal_approx(voyage.sailing_speed(1.0, 1000.0, 20.0, 20.0, 7.0, 5.0), sqrt(18.9)), "Use the tighter corridor limit")
	check(is_equal_approx(voyage.sailing_speed(1.0, 1000.0, 20.0, 20.0, 2.0, 5.0), 2.0), "Use the tighter hull limit")
	check(is_equal_approx(voyage.sailing_speed(1.0, 97.8, 20.0, 20.0, INF, INF), 15.6), "Ease into the approach outside the dolphins")
	check(is_equal_approx(voyage.sailing_speed(1.0, 85.8, 20.0, 20.0, INF, INF), 9.6), "Reach approach speed at the dolphins")
	check(is_equal_approx(voyage.sailing_speed(1.0, 21.45, 20.0, 20.0, INF, INF), 5.25), "Reverse thrust slows the final approach")

	# A held crossing resumes and completes in both directions with one trip each.
	for crossing in 2:
		var departure_end := voyage.at_a
		var speed := 0.0
		voyage.depart()
		check(voyage.traveled == 0.0, "Each departure clears the previous distance")
		for frame in 4000:
			var wait := 0.0 if frame < 30 else INF
			speed = voyage.sailing_speed(1.0 / 30.0, 425.0, speed, 20.0, INF, wait)
			voyage.advance(1.0 / 30.0, speed, 425.0)
			if frame < 30:
				check(voyage.traveled == 0.0, "A corridor hold must not advance the crossing")
			if voyage.has_arrived(425.0):
				break
		check(voyage.has_arrived(425.0), "The ferry resumes and reaches the destination")
		check(voyage.at_a == departure_end and voyage.trips == crossing, "Progress alone does not dock or count a trip")
		voyage.arrive()
		check(voyage.at_a != departure_end and voyage.trips == crossing + 1, "Docking switches ends and counts the crossing")
		check(voyage.state == FerryVoyage.State.UNLOADING and voyage.state_time == 0.0, "Arrival starts unloading")
		check(voyage.traveled > 424.97, "Docking retains the last crossing distance")

	voyage.traveled = 424.96
	check(not voyage.has_arrived(425.0), "Do not dock outside the arrival tolerance")
	voyage.traveled = 424.98
	check(voyage.has_arrived(425.0), "Keep the existing arrival tolerance")
	voyage.advance(1.0, 10.0, 425.0)
	check(voyage.traveled == 425.0, "A large step cannot overshoot the dock")
	if failures == 0:
		print("TEST PASSED")
	quit(1 if failures else 0)
