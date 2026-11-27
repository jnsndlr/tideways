extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	var assets := ["guemes_mid", "hiyu_mid", "ferry_mid", "issaquah_mid", "jumbo_mk_ii"]
	var authored := not "--classic-ferry" in OS.get_cmdline_user_args()
	for i in assets.size():
		var size := i + 1
		var installed := ResourceLoader.exists("res://assets/models/%s.glb" % assets[i])
		var fc := FerryClass.of(size)
		check(fc.authored_hull == (authored and installed), "Each size selects its installed hull")
		var hull := Models.ferry(fc)
		check(
			hull != null and hull.get_surface_count() == 1, "Each ferry has one visible hull mesh"
		)
		check(hull == Models.ferry(fc), "Repeated ferry instances share the hull")
		check(
			(Models.ferry_thin_shadow(fc) != null) == fc.authored_hull,
			"Only authored hulls add thin shadow geometry"
		)
		check(Models.ferry_lights(fc).get_surface_count() > 0, "Both hull families have lights")
	if authored and FerryHullAssets.available(2):
		_check_hiyu_deck()
	finish()


func _check_hiyu_deck() -> void:
	var fixed := ModelParts.merge_named(FerryHullAssets.HIYU_GLB, ["fixed"])
	var deck_faces := {}
	for index in range(0, fixed.verts.size(), 3):
		var a := fixed.verts[index]
		var b := fixed.verts[index + 1]
		var c := fixed.verts[index + 2]
		if maxf(absf(a.y - 2.5), maxf(absf(b.y - 2.5), absf(c.y - 2.5))) > 0.001:
			continue
		var triangle := [a, b, c]
		triangle.sort()
		if deck_faces.has(triangle):
			check(false, "Hiyu’s hull and apron draw the same deck face")
			return
		deck_faces[triangle] = true
	check(not deck_faces.is_empty(), "Hiyu has a car deck at its authored height")
