extends SceneTree
## A civic building gets one qualifying downtown lot in each town. Small towns stay residential.

class TownBuilder extends WorldBuilder:
	var placements := {}

	func _multimesh(_mesh: Mesh, xforms: Array[Transform3D], _colors: Array[Color], node_name: String, _variant: Array = []) -> void:
		placements[node_name] = xforms


func _initialize() -> void:
	var region := MapData.new()
	region.map_seed = 123
	var terrain := Terrain.new(region.map_seed, 620.0)
	terrain.h_grid.resize((terrain.n + 1) * (terrain.n + 1))
	terrain.h_grid.fill(10.0)
	for i in 3:
		var island := MapData.Island.new()
		island.town_center.x = (i - 1) * 400.0
		island.population = 3000 if i == 2 else 50000
		region.islands.append(island)
	var builder := TownBuilder.new(region, terrain)
	await builder._build_towns()
	var halls := [0, 0, 0]
	var shops := [0, 0, 0]
	for shop: String in WorldBuilder.SHOP_SHELLS:
		for placement: Transform3D in builder.placements[shop]:
			var town := roundi(placement.origin.x / 400.0) + 1
			if shop == WorldBuilder.CITY_HALL:
				halls[town] += 1
			else:
				shops[town] += 1
	if halls != [1, 1, 0] or shops[0] == 0 or shops[1] == 0 or shops[2] != 0:
		push_error("Unexpected downtown lots across two cities and one small town: halls %s, shops %s" % [halls, shops])
		quit(1)
		return
	print("TEST PASSED")
	quit()
