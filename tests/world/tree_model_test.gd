extends "res://tests/rule_test_case.gd"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var authored := not "--classic-trees" in args and ResourceLoader.exists(TreeModel.TREES_GLB)
	var expected_pines := 1
	if authored:
		if "--old-pines" in args:
			expected_pines = 6
		elif "--meshy-pines" in args or not ResourceLoader.exists(TreeModel.LPINE_GLB):
			expected_pines = 4 if ResourceLoader.exists(TreeModel.MPINES_GLB) else 6
		else:
			expected_pines = 4
	for broadleaf: bool in [false, true]:
		var variants := TreeModel.variants(broadleaf)
		var expected := (6 if authored else 1) if broadleaf else expected_pines
		check(variants.size() == expected, "Keep the selected tree family and number of variants")
		for variant: Array in variants:
			var levels := TreeLod.lod_levels(variant)
			check(not levels.is_empty(), "Each tree has a visible detail level")
			var begin := 0.0
			for level: Array in levels:
				var mesh := level[0] as Mesh
				check(
					mesh != null and mesh.get_surface_count() > 0,
					"Every active level draws geometry"
				)
				check(
					is_equal_approx(level[1], begin), "Distance levels join at the same threshold"
				)
				begin = level[2]
			check(is_zero_approx(begin), "The last level is visible to the far clip")
			check(TreeLod.shadow_mesh(variant) != null, "Every tree has shadow geometry")
			if not authored:
				check(levels.size() == 1, "Classic trees use one mesh at all distances")
				check(
					TreeLod.shadow_mesh(variant) == variant[0],
					"The classic tree casts its own shadow"
				)
	finish()
