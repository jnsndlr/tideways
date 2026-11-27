extends SceneTree
## The classic deck, road, and rendered lot meet even on a high inland site.


func _initialize() -> void:
	var island := MapData.Town.new()
	island.approach_bays = Layout.TRESTLE_MAX_BAYS
	island.lot_y = Layout.LOT_Y + Layout.approach_rise(island.approach_bays)
	var front := island.lot_front_u()
	var hinge := Layout.RAMP_HINGE_U
	var lot_edge := island.lot_offset() * Vector3(0, Layout.LOT_Y, Layout.LOT_FRONT)
	if not lot_edge.is_equal_approx(Vector3(0, island.road_y(front), front)) or not is_equal_approx(island.road_y(hinge), Layout.LOT_Y):
		return _fail("The road must join the raised lot and the slip hinge at their exact elevations")
	var deck := MeshBuilder.new()
	WorldBuilder._build_plain_trestle(deck, island, 0, Layout.PIER_END, false)
	var samples := 0
	for i in deck.verts.size():
		var p := deck.verts[i]
		if deck.normals[i].y > 0.99 and is_equal_approx(absf(p.x), 7.5):
			if not is_equal_approx(p.y, island.road_y(p.z)):
				return _fail("The concrete deck is off the vehicle path at %s" % p)
			samples += 1
	if samples < 6 or not Vector3(7.5, island.lot_y, front) in deck.verts:
		return _fail("Missing driveable deck at the raised lot edge")
	var foundation := MeshBuilder.new()
	foundation.xform = island.lot_offset()
	WorldBuilder._build_lot_foundation(foundation, 40)
	var rim_area := 0.0
	for i in range(0, foundation.verts.size(), 3):
		if foundation.normals[i].y < 0.99:
			continue
		var a := foundation.verts[i]
		var b := foundation.verts[i + 1]
		var c := foundation.verts[i + 2]
		for vertex in [a, b, c]:
			if not is_equal_approx(vertex.y, island.lot_y - 0.05):
				return _fail("The raised foundation rim must meet the gravel above the terrain")
		rim_area += (b - a).cross(c - a).length() * 0.5
	var expected := (80.0 + 3.6) * (Layout.LOT_LENGTH + 3.6) - 80.0 * Layout.LOT_LENGTH
	if not is_equal_approx(rim_area, expected):
		return _fail("Only the perimeter outside the paved and gravel lot should be capped")
	print("TEST PASSED")
	quit(0)


func _fail(message: String) -> void:
	push_error(message)
	quit(1)
