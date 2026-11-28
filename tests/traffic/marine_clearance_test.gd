extends "res://tests/rule_test_case.gd"

## Hull-only queries keep their ordered blockers, including at strip boundaries.
## A path-following vessel must still see conflicts beyond its immediate hull.


class Track:
	extends Vessel
	var origin := Vector2.ZERO
	var direction := Vector2.RIGHT

	func pos2() -> Vector2:
		return origin

	func heading2() -> Vector2:
		return direction

	func ahead(distance: float) -> Vector2:
		return origin + direction * distance

	func path_left() -> float:
		return 1000.0

	func wants_to_move() -> bool:
		return true

	func self_look() -> float:
		return 50.0

	func shown_look() -> float:
		return 100.0


func _initialize() -> void:
	var follower := Track.new()
	var crossing := Track.new()
	var peer := Track.new()
	var clearance := MarineClearance.new()
	var boats: Array[Vessel] = [follower, crossing, peer]
	# Exercise both signs and a path whose hull straddles a boundary.
	for x: float in [110, -110, 255, -257]:
		follower.direction = Vector2.DOWN
		follower.origin = Vector2(x, 0)
		follower.free_nav = true
		crossing.direction = Vector2.RIGHT
		crossing.origin = Vector2(x + 19, 25)
		crossing.half_seg = 18.0
		peer.direction = crossing.direction
		peer.origin = crossing.origin
		peer.half_seg = crossing.half_seg
		boats.assign([follower, crossing, peer])
		clearance.update(boats, 1.0 / 30.0)
		var distance := follower.clear
		check(follower.blocker == crossing and is_finite(distance), "current long hull intersects")
		boats.assign([follower, peer, crossing])
		clearance.update(boats, 1.0 / 30.0)
		check(
			follower.blocker == peer and distance == follower.clear,
			"first tied blocker in input order"
		)
	boats.assign([follower, crossing])
	follower.origin = Vector2(235, 0)
	follower.free_nav = false
	crossing.origin = Vector2(325, 28)
	crossing.direction = Vector2.LEFT
	crossing.half_seg = 3.0
	crossing.rank = 2
	clearance.update(boats, 1.0 / 30.0)
	check(
		follower.blocker == crossing and is_finite(follower.clear) and not follower.blocked_by_hull,
		"shown path crosses a strip"
	)
	follower.go_t = 3.0
	clearance.update(boats, 1.0 / 30.0)
	check(follower.blocker == null and is_inf(follower.clear), "stuck breaker ignores future paths")
	follower.go_t = 0.0
	follower.direction = Vector2.RIGHT
	follower.speed = 6.0
	follower.cruise = 6.0
	crossing.origin = follower.origin + Vector2(150, -150)
	crossing.direction = Vector2.DOWN
	crossing.speed = 6.0
	crossing.cruise = 6.0
	clearance.update(boats, 1.0 / 30.0)
	check(
		is_equal_approx(follower.cpa_cap, 2.7) and is_inf(follower.clear),
		"CPA beyond both immediate paths"
	)
	for boat in [follower, crossing, peer]:
		boat.free()
	finish()
