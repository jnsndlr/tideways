extends SceneTree
## Town roads sit in the ground: every road starts on its lot (or the junction it
## leaves), climbs no steeper than MapGenerator.ROAD_GRADE_STEEP (the road up from
## the lot, ROAD_GRADE_CLIMB; most stay within ROAD_GRADE), and has the ground graded
## just under it (Terrain.ROAD_DROP) along its middle, and clear of its shoulders
## (away from the town centre, where the streets meet).
##   godot --headless --path . --script tests/world/road_grade_test.gd

const SEEDS := [123, 4242, 777]
func _initialize() -> void:
	var roads := 0
	for seed_value: int in SEEDS:
		var gen := MapGenerator.new()
		var map := gen.generate(seed_value)
		for isl in map.towns:
			if isl.road_main_a.is_empty():
				continue
			var failure := _check(isl, gen.terrain)
			if not failure.is_empty():
				push_error("Seed %d, %s: %s" % [seed_value, isl.name, failure])
				quit(1)
				return
			roads += 1
	if roads == 0:
		push_error("No town roads to check")
		quit(1)
		return
	print("Checked the roads of %d towns" % roads)
	print("TEST PASSED")
	quit(0)


func _check(isl: MapData.Town, t: Terrain) -> String:
	var main := isl.road_main_a
	if absf(main[0].y - isl.lot_y) > 0.01:
		return "main road starts at %.2f, lot at %.2f" % [main[0].y, isl.lot_y]
	# The three ticket approaches widen the road on the inbound side.
	var length := (main[0] - main[-1]).dot(isl.dock_dir)
	for p in main:
		var spread := Layout.ticket_spread((main[0] - p).dot(isl.dock_dir), length)
		if spread <= 0.0:
			break
		var outer := p - isl.lateral() * (RoadMesh.HALF + Layout.TICKET_EXTRA_WIDTH * spread)
		var gap := p.y - t.height_v(outer)
		if gap < -0.06 or gap > 1.5:
			return "ground %.2f m below the outer ticket lane at %s" % [gap, outer]
	var lines: Array[PackedVector3Array] = [main]
	if isl.road_main_b.size() > 1:
		lines.append(isl.road_main_b)
	lines.append_array(isl.road_cross)
	var centre := main[main.size() - 1]
	for line in lines:
		if line != main and line[0].distance_to(centre) > 0.01:
			return "a street doesn't leave from the town centre"
		for i in line.size():
			var p := line[i]
			if i > 0:
				var q := line[i - 1]
				var run := Vector2(p.x - q.x, p.z - q.z).length()
				var limit := MapGenerator.ROAD_GRADE_CLIMB if line == main else MapGenerator.ROAD_GRADE_STEEP
				if absf(p.y - q.y) > run * limit + 0.001:
					return "grade %.1f%% at %s" % [absf(p.y - q.y) / run * 100.0, p]
			var d := line[mini(i + 1, line.size() - 1)] - line[maxi(i - 1, 0)]
			d.y = 0.0
			var right := d.normalized().cross(Vector3.UP)
			# Where streets meet, the ground follows whichever is nearer.
			if p.distance_to(centre) < 14.0:
				continue
			var g := t.height_v(p)
			# Grid points on a steep, curving climb interpolate a little off either
			# way: never up through the road, nor down past its skirt.
			if p.y - g < 0.0 or p.y - g > RoadMesh.SKIRT:
				return "ground %.2f m under the road's middle at %s" % [p.y - g, p]
			# At the edges, the ground between grid points may come up a little, but
			# not through the shoulder, nor so far down the skirt shows a gap.
			for v: float in [-RoadMesh.HALF, RoadMesh.HALF]:
				var gap := p.y - RoadMesh.SHOULDER_DROP - t.height_v(p + right * v)
				if gap < -0.06 or gap > RoadMesh.SKIRT:
					return "ground %.2f m under the shoulder at %s (%+.0f m across)" % [gap, p, v]
	return ""
