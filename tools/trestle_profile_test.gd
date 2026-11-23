extends SceneTree
## The classic deck, road, and rendered lot meet even on a high inland site.


func _initialize() -> void:
	var island := MapData.Island.new()
	island.approach_bays = Layout.TRESTLE_MAX_BAYS
	island.lot_y = Layout.LOT_Y + Layout.approach_rise(island.approach_bays)
	var front := island.lot_front_u()
	var hinge := SlipRamp.HINGE_U
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
	print("TEST PASSED")
	quit(0)


func _fail(message: String) -> void:
	push_error(message)
	quit(1)
