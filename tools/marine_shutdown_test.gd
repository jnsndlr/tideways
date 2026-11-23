extends "res://tools/world_build_shutdown_test.gd"
## Leave while plotting navigable water, then quit during the later cove search.

var previous_charts: WeakRef


func unfinished_construction(scene: Node, second_load: bool) -> Node:
	var charts: MarineCharts = scene._building_charts
	if charts == null:
		return null
	var target := MarineCharts.Phase.ANCHORAGES if second_load else MarineCharts.Phase.NAVIGATION
	if charts.phase() != target:
		return null
	if not second_load:
		previous_charts = weakref(charts)
	elif previous_charts.get_ref() != null:
		push_error("The previous scene retained its marine charts after returning to Menu.")
		quit(1)
		return null
	return scene
