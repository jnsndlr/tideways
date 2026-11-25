extends SceneTree
## Verifies exact building placement ratios: 1 house per 100 people and 1 commercial
## building per 333 people, plus one civic hall in qualifying cities and zero shops
## in tiny hamlets under 333 people.

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
	var pops := [3000, 1500, 200]
	for i in 3:
		var town := MapData.Town.new()
		town.town_center.x = (i - 1) * 400.0
		town.population = pops[i]
		region.towns.append(town)
	var builder := TownBuilder.new(region, terrain)
	await builder._build_towns()
	var halls := [0, 0, 0]
	var shops := [0, 0, 0]
	var houses := [0, 0, 0]
	for shop: String in WorldBuilder.SHOP_SHELLS:
		for placement: Transform3D in builder.placements[shop]:
			var town := roundi(placement.origin.x / 400.0) + 1
			if shop == WorldBuilder.CITY_HALL:
				halls[town] += 1
			else:
				shops[town] += 1
	for i in builder.house_meshes.size():
		for placement: Transform3D in builder.placements["Houses%d" % i]:
			var town := roundi(placement.origin.x / 400.0) + 1
			houses[town] += 1
	var total_comm := [shops[0] + halls[0], shops[1] + halls[1], shops[2] + halls[2]]
	if halls != [1, 0, 0] or total_comm != [9, 4, 0] or houses != [30, 15, 2]:
		push_error("Unexpected town buildings: halls %s, comm %s, houses %s" % [halls, total_comm, houses])
		quit(1)
		return
	print("TEST PASSED")
	quit()
