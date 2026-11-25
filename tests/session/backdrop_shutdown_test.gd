extends "res://tests/session/world_build_shutdown_test.gd"
## Leave while the land mesh is being generated, then quit during vegetation assembly.


func unfinished_construction(scene: Node, second_load: bool) -> Node:
	var backdrop: Backdrop = scene._building_backdrop
	if backdrop == null:
		return null
	if second_load:
		if backdrop.get_child_count() > 1:
			return backdrop
	elif not backdrop._trees.is_empty() and not backdrop.has_node("Mainland"):
		return backdrop
	return null
