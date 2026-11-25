extends "res://tests/session/world_build_shutdown_test.gd"
## Interrupt actual partial simulation state on either side of fleet creation.


func unfinished_construction(scene: Node, second_load: bool) -> Node:
	var sim: Simulation = scene.sim
	if sim == null or scene.built or scene.build_to != 0.99:
		return null
	if second_load:
		return scene.get_node_or_null("Grass") if scene.hud == null else null
	if not sim.terminals.is_empty() and sim.marine == null:
		return sim.terminals.values()[0]
	return null
