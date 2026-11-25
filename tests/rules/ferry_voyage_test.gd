extends "res://tests/rule_test_case.gd"
## Crossing decisions run without constructing a ferry, terminal or scene mesh.


## A manoeuvre must back straight out, reverse direction beyond the buoys, and
## approach along the new slip, on either side of the starting slip.
func check_slip_moves() -> void:
	var town := MapData.Town.new()
	town.dock_dir = Vector3.RIGHT
	var start := Vector3(-24, 0, 13)
	for offset in [-60.0, 60.0]:
		var finish := start + town.lateral() * float(offset)
		var move := SlipShiftPath.build(start, finish, town, 30.0)
		var points := move.points
		check(points[0].is_equal_approx(start) and points[-1].is_equal_approx(finish), "Move joins both berths")
		check((points[1] - start).normalized().dot(town.dock_dir) > 0.999, "Move starts straight astern")
		check((finish - points[-2]).normalized().dot(town.dock_dir) < -0.999, "Move finishes straight into berth")
		var turn := move.back_count - 1
		check((points[turn] - points[turn - 1]).normalized().dot((points[turn + 1] - points[turn]).normalized()) < -0.99, "Boat reverses her way at the turn")
		var measured := 0.0
		for k in range(1, points.size()):
			measured += points[k].distance_to(points[k - 1])
			if k == turn:
				check(is_equal_approx(move.cusp, measured), "Stop distance agrees with the path")
		check(is_equal_approx(move.length, measured), "Return forecast uses the full path length")


func _initialize() -> void:
	check_slip_moves()
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

	# Both captains retain their distinct handling through the extracted voyage owner.
	for captain in Captain.roster():
		for distance in [470.0, 2050.0]:
			var trip := FerryVoyage.new()
			trip.depart()
			var speed := 0.0
			var elapsed := 0.0
			while not trip.has_arrived(distance) and elapsed < 3600.0:
				speed = trip.sailing_speed(0.05, distance, speed, captain.cruise(20.0), INF, INF, captain.harbour)
				trip.advance(0.05, speed, distance)
				elapsed += 0.05
			check(absf(Units.game_minutes(elapsed) - captain.crossing_minutes(distance, 20.0)) < 0.1, "Captain forecast matches voyage integration")
		check(voyage.sailing_speed(1.0, 85.8, 25.0, captain.cruise(20.0), 0.0, INF, captain.harbour) == 0.0, "Captain cannot bypass a hull hold")
		check(voyage.sailing_speed(1.0, 85.8, 25.0, captain.cruise(20.0), INF, 1.5, captain.harbour) == 0.0, "Captain cannot bypass a corridor hold")
	var first := Captain.roster()[0]
	var relief := Captain.roster()[1]
	var command := CaptainAssignment.new(first)
	command.advance(5.0)
	command.arrive()
	check(command.last_crossing < 0.0, "A crossing already underway at startup has no recorded time")
	command.depart()
	command.advance(11.0)
	command.assign(relief, true)
	command.advance(9.0)
	command.arrive()
	check(command.last_crossing == 20.0 and command.last_crossing_captain == first, "The departing captain receives credit despite an underway reassignment")
	command.depart()
	check(command.current == relief, "The scheduled captain takes command at departure")
	command.advance(16.0)
	command.arrive()
	check(command.last_crossing == 16.0 and command.last_crossing_captain == relief, "The relief captain receives the next crossing")
	check(command.previous_crossing == 20.0 and command.previous_crossing_captain == first, "Crossing history preserves the previous captain and time")
	var ferry := Ferry.new()
	ferry.fc = FerryClass.of(3)
	ferry.assign_captain(Captain.roster()[0])
	ferry.state = Ferry.State.SAILING
	var underway_cruise := ferry.cruise
	ferry.assign_captain(Captain.roster()[1])
	check(ferry.captain == Captain.roster()[0] and ferry.cruise == underway_cruise, "Changing captain underway preserves current handling")
	check(ferry.next_captain == Captain.roster()[1], "Changing captain schedules the next sailing")
	ferry.state = Ferry.State.LOADING
	ferry.assign_captain(Captain.roster()[1])
	check(ferry.captain == Captain.roster()[1], "Alongside assignment takes effect immediately")
	ferry.free()

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
	finish()
